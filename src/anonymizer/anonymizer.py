"""
This model was developed in cooperation between the city of Rotterdam and Kyden. Copyright City of Rotterdam.

Licence: EUPL

Purpose
-------
Replace personally‑identifying information (PII) in free‑text fields with
placeholder tokens, aiming ≥95 % recall (priority) and ≥95 % precision
for patterns that can be reliably expressed with regular expressions. This
step removes low‑hanging fruit so that subsequent NLP/ML passes can focus on
context‑dependent or fuzzy entities such as person names.

Usage (CLI)
-----------
$ python -m anonymizer input.xlsx output.xlsx --text-column Toelichting_unmasked

Available CLI Options
---------------------
positional arguments:
  input                 Path to input .xlsx file containing the text to be anonymized

  output                Path to output .xlsx file where anonymized results will be written

optional arguments:
  --text-column TEXT_COLUMN
                        Name of the column in the input file containing free text to anonymize.
                        Default: 'Toelichting_unmasked'
                        
  --masked-text-column MASKED_TEXT_COLUMN
                        Name of the new column in the output file that will contain the masked text.
                        Default: 'Toelichting_masked' (auto-generated from text-column + '_masked')
                        
  --blacklist-path BLACKLIST_PATH
                        Path to the Excel file containing lists of entities to mask (names, addresses, etc.).
                        Default: bundled 'ListClassifier Basic.xlsx' (package-data).
                        Required for ListAnonymizer functionality.
                        
  --whitelist-path WHITELIST_PATH
                        Path to the Excel file containing whitelisted entities to exclude from masking.
                        Default: bundled 'Whitelist Basic.xlsx' (package-data).
                        Used by both ListAnonymizer and NERAnonymizer to preserve known safe entities.

Usage (module)
---------------
from anonymizer import CombinedAnonymizer (or RegexAnonymizer, ListAnonymizer, NERAnonymizer)

df = pd.read_excel("input.xlsx")
an = CombinedAnonymizer()
df["Toelichting_masked"] = df["Toelichting_unmasked"].map(an)   # __call__ overload
df.to_excel("output.xlsx", index=False)
"""

from __future__ import annotations

import argparse
import logging
import re # Regular Expressions (Regex)
import json
from pathlib import Path
from typing import Dict, Pattern, Iterable

import pandas as pd # For reading excel files
import flashtext # For fast processing in ListAnonymizer
from gliner import GLiNER # NER model
from symspellpy import SymSpell, Verbosity # For typo correction in List Anonymizer
from transformers import logging as transformers_logging # Suppress transformers warnings
from importlib import resources
from . import config

# --------------------------------------------------------------------------- #
# Parameters                                                                  #
# --------------------------------------------------------------------------- #

DISTINCT_TAGS = False  # If True, use different tag formats for each anonymizer: <>, <()>, <[]>. If False, use uniform <> format.
SYMSPELL = True # If True, enable SymSpell typo correction in ListAnonymizer
PRINT_NER_CONFIDENCE = False  # If True, print confidence scores in NER tags (e.g., <[Name, C0.85]>)
TAG_LANGUAGE = 'nl' # Language of tags, currently 'nl' for Dutch or 'en' for English

# Default-lijsten zijn als package-data meegebundeld (zie pyproject
# [tool.setuptools.package-data]) en worden package-relatief opgelost, zodat ze
# ook na `pip install` vindbaar zijn -- niet relatief aan de werkmap.
LIST_PATH = str(resources.files(__package__).joinpath("input_files", "ListClassifier Basic.xlsx")) # Default blacklist for ListAnonymizer
WHITELIST_PATH = str(resources.files(__package__).joinpath("input_files", "Whitelist Basic.xlsx")) # Default whitelist for both ListAnonymizer and NERAnonymizer

NER_CONFIDENCE_DICT = {
    "Name": 0.3,
    "Address": 0.3,
    "Organization": 0.84
}
WEAK_NER_WHITELIST = [] # Loaded from Excel in NERAnonymizer

translation_file = resources.files(config).joinpath("tag_translations.json")
with translation_file.open("r", encoding="utf-8") as f:
    TRANSLATIONS: dict[str, dict] = json.load(f)

# Exported symbols
__all__ = ["RegexAnonymizer", "ListAnonymizer", "NERAnonymizer", "CombinedAnonymizer", "TAGGED_PATTERNS", "__version__"]
__version__ = "1.1.0"

# Logging setup
LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)
_handler = logging.StreamHandler()
_handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
LOGGER.addHandler(_handler)

# --------------------------------------------------------------------------- #
# 1. Define high‑recall fixed patterns                                        #
# --------------------------------------------------------------------------- #

# Month name alternatives (Dutch & English, full & abbreviated)
_MONTHS = (
    r"januari|februari|maart|april|mei|juni|juli|augustus|september|oktober|"
    r"november|december|jan|feb|mrt|apr|mei|jun|jul|aug|sep|okt|nov|dec|"
    r"january|february|march|april|may|june|july|august|september|october|"
    r"november|december|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec"
)

# --------------------------------------------------------------------------- #
# TAGGED_PATTERNS – order matters (high‑specificity → low‑specificity)       #
# --------------------------------------------------------------------------- #
# Every pattern is thoroughly commented with concrete variants it captures.   #
# The negative‑lookbehind / look‑ahead guards ((?<!\w), (?!\w)) are used to  #
# ensure word boundaries without consuming punctuation like € or ‑.           #
# --------------------------------------------------------------------------- #

TAGGED_PATTERNS: Dict[str, str] = {
    # NB: keep broad enough for high recall, refine in later passes if needed.

    # -------------------------------------------------------------------
    # Money – € / euro / EUR, comma or dot decimals, ‘cent’, or plain amount
    #   € 216,62   ·  Euro 8,50   ·  0,15cent   ·  370 Euros
    # -------------------------------------------------------------------
    # "Money": r"""
    #     (
    #     ?:(?:€\s*|(?:Euro?s?|EUR)\s*)\d{1,3}(?:[\.\s]\d{3})*(?:[.,]\d{2})?|
    #     \d{1,3}(?:[\.\s]\d{3})*(?:[.,]\d{2})\s*(?:Euro?s?|EUR|cent)|
    #     \d{1,3}(?:[\.\s]\d{3})*\s*(?:Euro?s?)
    #     )
    # """,
    "Money": r"""
    (?:(?:€\s*|(?:Euro?s?|EUR)\s*)\d{1,4}(?:[\.\s]\d{3})*(?:[.,]\d{2})?|
    \d{1,4}(?:[\.\s]\d{3})*(?:[.,]\d{2})\s*(?:Euro?s?|EUR|cent)|
    \d{1,4}(?:[\.\s]\d{3})*\s*(?:Euro?s?)
    )
    """,
    
    # -------------------------------------------------------------------
    # [Number] – plain euro-style decimals without any currency word
    #            342,50   •   1.234,56   •   12 345,00
    # -------------------------------------------------------------------
    "Number":  r"\b\d{1,3}(?:[\.\s]\d{3})*,\d{2}\b",

    # -------------------------------------------------------------------
    # Date – purely numeric, various separators (‑ / .) & YY or YYYY
    #   26‑02‑2025   · 29/3/24   · 16 / 04 / 2022   · 31.05.1952   · 03‑2025
    #   The goal is to capture full dates, which may reveal birth dates. Partial dates can remained unmasked.
    # -------------------------------------------------------------------
    "Date": r"""
        \b(?:
            \d{1,2}\s*[\-/.]\s*\d{1,2}\s*[\-/.]\s*\d{2,4}|   # d‑m‑yyyy / d.m.yy
            \d{4}\s*[\-/.]\s*\d{1,2}\s*[\-/.]\s*\d{1,2}     # yyyy‑m‑d
        )\b
    """,


    # -------------------------------------------------------------------
    # Date_Ext – month names, Dutch & English, with optional year/range
    #   21e van Januari   · 3 april   · 25 Feb   · 22‑29 juli 2022   · juni 2020
    #   The goal is to capture full dates, which may reveal birth dates. Partial dates can remained unmasked.
    # -------------------------------------------------------------------
    "Date_Ext": rf"""
        \b(?:
            # ordinal + van + month + year  → 21e van Januari 2025 (DUTCH)
            \d{{1,2}}(?:e|ste)\s*(?:van\s*)?(?:{_MONTHS})(?:\s*\d{{4}})?
            |
            # ordinal + of + month + year → 30th of January 2023 (ENGLISH)
            \d{{1,2}}(?:st|nd|rd|th)\s*(?:of\s*)?(?:{_MONTHS})(?:\s*\d{{4}})?
            |
            # range 22-29 juli 2022  or 22 tot 29 juli 2025 or 22 to 29 juli 2026
            \d{{1,2}}\s*(?:tot|\-|to)\s*\d{{1,2}}\s*(?:{_MONTHS})(?:\s*\d{{2,4}})
            |
            # day month year  → 3 april 2024
            \d{{1,2}}[\s\-\\/,]*(?:{_MONTHS})[\s\-\\/,]*(?:\d{{2,4}})
            |
            # Month-first dates → August, 26, 2022 / August 24th 2024
            (?:{_MONTHS})[\s\-\\\/,]*\d{{1,2}}(?:st|nd|rd|th)?[\s\-\\\/,]*(?:\d{{4}})
        )\b
    """,

    # ------------------------------------------------------------------- #
    # TimeS / RANGES                                                     #
    # ------------------------------------------------------------------- #
    # Captures: 14:15, 17:35 PM, 14.30‑15.15, 7u tot 20u, 7u‑20u
    # "Time": r"""
    #     (?<!\d)(?:
    #         (?:[01]?\d|2[0-3])[.:][0-5]\d(?:\s?(?:AM|PM))?            # hh:mm
    #         (?:\s?[--]\s?(?:[01]?\d|2[0-3])[.:][0-5]\d(?:\s?(?:AM|PM))?)? |
    #         \d{1,2}u\s*(?:tot|-)?\s*\d{1,2}u                          # 7u tot 20u
    #     )(?!\d)
    # """,
    
    # ------------------------------------------------------------------- #
    # AgeS – e.g. "74 jaar"                                             #
    # ------------------------------------------------------------------- #
    "Age": r"\b\d{1,3}\s?jaar\s?oud\b|\d{1,3}[- \s]*jarige",

    # ------------------------------------------------------------------- #
    # CONTACT / ACCOUNT IDENTIFIERS                                      #
    # ------------------------------------------------------------------- #
    # Email
    "Email": r"""
        \b[A-Za-z0-9._%+-]+        # local‑part
        @                          # at
        [A-Za-z0-9.-]+             # domain/sub‑domains
        \.[A-Za-z]{2,}             # TLD ≥2 chars
        \b
    """,

    # IBAN: NLkk BBBB CCCC CCCC CC  (spaces optional, bank code variable)
    "IBAN": r"""
        \bNL\s?\d{2}\s?[A-Z]{4}\s?(?:\d{4}\s?){2}\d{2}\b
    """,
    
    # ------------------------------------------------------------------- #
    # POSTAL / LICENCE                                                   #
    # ------------------------------------------------------------------- #
    # Dutch postal code
    "Postcode": r"""
        \b[1-9]\d{3}\s?[A-Z]{2}\b                     # 1234 AB
    """,

    # Dutch vehicle licence plates
    "Licence_Plate": r"""
        (?<!\w)(?:
            # — variants WITH separators (‑ or space) —
            (?:[A-Z]{2}[\-\s]\d{2}[\-\s]\d{2})|         # AA-12-34
            (?:\d{2}[\-\s][A-Z]{2}[\-\s]\d{2})|         # 12-AB-34
            (?:\d{2}[\-\s]\d{2}[\-\s][A-Z]{2})|         # 12-34-AB
            (?:[A-Z]{2}[\-\s]\d{2}[\-\s][A-Z]{2})|      # AA-12-BC
            (?:[A-Z]{2}[\-\s][A-Z]{2}[\-\s]\d{2})|      # AA-BB-12
            (?:\d{2}[\-\s][A-Z]{2}[\-\s][A-Z]{2})|      # 12-AB-BB
            (?:[A-Z]{2}[\-\s]\d{3}[\-\s][A-Z])|         # AA-123-B
            (?:[A-Z]{3}[\-\s]\d{2}[\-\s][A-Z]{1})|      # AAA-12-B
            (?:[A-Z][\-\s]\d{3}[\-\s][A-Z]{2})|         # A-123-BB
            (?:\d[\-\s][A-Z]{3}[\-\s]\d{2})|            # 1-ABC-12
            (?:\d{2}[\-\s][A-Z]{3}[\-\s]\d)|            # 12-ABC-1
            (?:[A-Z]{2}[\-\s][A-Z]{2}[\-\s]\d{4})|      # Added for AA-BB-1234 (German licence plate observed in sample)
            # — SAME layouts but NO separators (length 6‑7, letters+digits)
            (?:[A-Z]{2}\d{2}\d{2})|                     # AA1234
            (?:\d{2}[A-Z]{2}\d{2})|                     # 12AB34
            (?:\d{2}\d{2}[A-Z]{2})|                     # 1234AB
            (?:[A-Z]{2}\d{2}[A-Z]{2})|                  # AA12AB
            (?:[A-Z]{2}[A-Z]{2}\d{2})|                  # AAAB12
            (?:[A-Z]{3}\d{2}[A-Z]{1})|                  # AAA12B
            (?:\d{2}[A-Z]{2}[A-Z]{2})|                  # 12ABAB
            (?:[A-Z]{2}\d{3}[A-Z])|                     # AA123B
            (?:[A-Z]\d{3}[A-Z]{2})|                     # A123BB
            (?:\d[A-Z]{3}\d{2})|                        # 1ABC12
            (?:\d{2}[A-Z]{3}\d)                         # 12ABC1
        )(?!\w)
    """,

    # ------------------------------------------------------------------- #
    # Phone & URL – last to avoid earlier numeric collisions             #
    # ------------------------------------------------------------------- #
    "Phone": r"(?<!\d)(?:(?:\+31|0)[\s\-]?(?:\d[\s\-]?){6,11}\d|088\s?\d{2}\s?\d{2}\s?\d{2}\s?00)\b",      # +31 6 12345678 / 06-12345678 / 088 12 24 44 00
    "URL": r"\b(?:(?:https?://|www\.)((?![^/\s]*rotterdam\.nl)[^\s<'\"]+))\b", # http://example.com, exluding rotterdam.nl


    # ------------------------------------------------------------------- #
    # NUMERIC ID CODES (specific → generic order)                        #
    # ------------------------------------------------------------------- #
    "ID_Number": r"""
        (\b|contractnummer|nummer|nr|nmbr|[A-Za-z])(?: 
            \d{6,7}-\d{4}|                          # 123456‑1234 / 1234567‑1234 -> CASE_ID
            \d{6}-[A-Z]{2}\d{9}|                    # 123456‑XX123456789 -> COMPLIMENT_ID
            \d{4}-\d{6}|                            # 1234‑123456 -> NOTIFICATION_ID
            \d{5}-\d{4}|                            # 12345‑1234 -> NOTIFICATION_ID
            [A-Za-z]{0,4}[,;:/]?\s*nr\s*\d{10}|     # noisy prefix + 10 digits -> CLAIM_ID
            \d{16}|                                 # 16 digits -> OV-chipcard number
            \d{10}|                                 # 1234567890 -> CLAIM_ID
            \d{6}|                                  # 123456 -> PERMIT_ID
            \d{7}|                                  # 1234567 -> CUSTOMER_ID
            [A-Z]{3}\d{7}|                          # XXX1234567 -> REQUEST_ID
            \d{1,2}[a-zA-Z]\d{4,6}|                 # 12X123456 -> AKTE_ID
            (?!01014\b|14010\b)\d{5}|               # 12345, excluding 01014 and 14010 -> AGENT_ID
            \bDV\s?\d{3}\b|                         # counter serial number -> DV 123 / DV123
            WZ-\d{8}                                # unemployment-number
        )\b
    """,

    # ------------------------------------------------------------------- #
    # NATIONAL REGISTERS                                                 #
    # ------------------------------------------------------------------- #
    "BSN": r"\b(?:\d{9}|\d{4}\.\d{2}\.\d{3})\b",    # 9‑digit citizen‑service number or 1234.12.123
    "KVK": r"\b(?:[1-9]\d{7}\b|0{4}\d{8})",         # 8‑digit Chamber of Commerce, cannot start with a 0. Or branch nr. which starts with four zeros
    "BTW": r"\bNL\d{9}B\d{2}\b",                    # NL123456789B01

    # ------------------------------------------------------------------- #
    # MISCELLANEOUS                                                      #
    # ------------------------------------------------------------------- #
    "IP_Address": r"\b(?:25[0-5]|2[0-4]\d|1?\d?\d)(?:\.(?:25[0-5]|2[0-4]\d|1?\d?\d)){3}\b",  # 192.168.1.1
    "Credit_Card": r"\b(?:\d[\s-]?){13,19}\b",    # 16‑digit Visa etc.

}


def _build_patterns(active_tags: Iterable[str] | None = None) -> Dict[str, Pattern]:
    """
    Pre‑compile regexes for speed and maintainability.
    """
    tags = active_tags or TAGGED_PATTERNS.keys()
    
    # Patterns that should be case-sensitive
    case_sensitive_tags = {"Postcode"}
    
    return {
        tag: re.compile(
            pattern, 
            re.VERBOSE if tag in case_sensitive_tags else (re.IGNORECASE | re.VERBOSE)
        )
        for tag, pattern in TAGGED_PATTERNS.items() if tag in tags
    }

# --------------------------------------------------------------------------- #
# 2. Helper functions                                                         #
# --------------------------------------------------------------------------- #

def is_valid_bsn(bsn: str) -> bool:
    """
    Validate a Dutch BSN (Burgerservicenummer) using the 11-proef.
    
    Parameters
    ----------
    bsn : str
        The BSN to validate (can contain dots, will be stripped).
        
    Returns
    -------
    bool
        True if the BSN passes the 11-proef validation, False otherwise.
        
    Examples
    --------
    >>> is_valid_bsn("111222333")
    True
    >>> is_valid_bsn("123456789")
    False
    >>> is_valid_bsn("1234.56.789")
    False
    """
    # Remove dots if present (format: 1234.56.789)
    bsn_clean = bsn.replace(".", "")
    
    # Check if it's 9 digits
    if not bsn_clean.isdigit() or len(bsn_clean) != 9:
        return False
    
    # Apply 11-proef: multiply each digit by (9-i) for positions 0-7, subtract the last digit
    total = sum(int(d) * (9 - i) for i, d in enumerate(bsn_clean[:8])) - int(bsn_clean[8])
    
    return total % 11 == 0


def _load_whitelist_excel(file_path: str, sheet_name: str) -> pd.DataFrame:
    """Load the whitelist Excel file for the List and NER Anonymizer."""
    try:
        whitelist_df = pd.read_excel(file_path, sheet_name=sheet_name)
    except FileNotFoundError:
        raise FileNotFoundError(f"Could not find the whitelist file {file_path}. Please ensure it exists in the working directory.")
    except PermissionError:
        raise PermissionError(f"Permission denied when trying to read the whitelist file {file_path}. Please make sure the file is not opened.")
    except Exception as e:
        raise Exception(f"An error occurred while reading {file_path}: {e}")
    
    # Assuming the whitelist entries are "Weak" and "Strong" columns
    if sheet_name == "NER":
        whitelist_df = whitelist_df[["Weak", "Strong"]]
        # lower case for case-insensitive matching, strip quotes
        whitelist_df["Weak"] = whitelist_df["Weak"].str.lower().str.replace('"', '').str.replace("'", '')
        whitelist_df["Strong"] = whitelist_df["Strong"].str.lower().str.replace('"', '').str.replace("'", '')
    elif sheet_name == "List":
        whitelist_df = whitelist_df[["List"]]
        whitelist_df["List"] = whitelist_df["List"].str.lower().str.replace('"', '').str.replace("'", '')
    
    return whitelist_df

class RegexAnonymizer:
    """
    Callable object that replaces occurrences of fixed-pattern PII tokens with
    '<TAG>' placeholders.  The mapping is defined in TAGGED_PATTERNS.

    Parameters
    ----------
    tags : Iterable[str] | None
        Subset of tags to activate.  ``None`` → use all.
    mask : str
        How to render the placeholder.  ``"{tag}"`` will be ``{tag}`` (e.g.
        ``<Email>``); customise if desired.
    validate_bsn : bool
        If True, apply 11-proef validation to BSN numbers (default: True).
    distinct_tags : bool | None
        If True, use distinct tag format. If None, use global DISTINCT_TAGS.
    """

    def __init__(
        self,
        tags: Iterable[str] | None = None,
        mask: str = "<{tag}>",
        validate_bsn: bool = True,
        distinct_tags: bool | None = None,
    ) -> None:
        self._mask: str = mask
        self._patterns: Dict[str, Pattern] = _build_patterns(tags)
        self._validate_bsn: bool = validate_bsn
        self._distinct_tags: bool = distinct_tags if distinct_tags is not None else DISTINCT_TAGS
        
        # Update mask format based on distinct_tags setting (only if using default mask)
        if mask == "<{tag}>" and self._distinct_tags:
            self._mask = "<{tag}>"  # RegexAnonymizer uses <> format
        elif mask == "<{tag}>" and not self._distinct_tags:
            self._mask = "<{tag}>"  # Uniform format

        # Add the tags to the NER whitelist to avoid NER masking masks
        tags_translated = [mask.format(tag=TRANSLATIONS[TAG_LANGUAGE].get(tag, tag)) for tag in self._patterns.keys()]
        for tag_format in tags_translated:
            if WEAK_NER_WHITELIST is not None and tag_format not in WEAK_NER_WHITELIST:
                WEAK_NER_WHITELIST.append(tag_format)

    # --------------------------------------------------------------------- #
    # Public API                                                            #
    # --------------------------------------------------------------------- #

    def anonymize(self, text: str) -> str:
        """Return *text* with every configured pattern replaced."""
        if not isinstance(text, str):
            return text  # ignore NaNs

        for tag, pat in self._patterns.items():
            if tag == "BSN" and self._validate_bsn:
                # Special handling for BSN: validate with 11-proef
                text = self._anonymize_bsn(text, pat)
            else:
                text = pat.sub(self._mask.format(tag=TRANSLATIONS[TAG_LANGUAGE].get(tag, tag)), text)

        # Additional masking for ID numbers after indicators
        text = self._mask_additional_id_numbers(text)

        # Post processing: mask numbers after postcode tags
        text = re.sub(r'(\<Postcode\>)\s+(\d+[A-Za-z]?)\b', '<Postcode>', text)
        return text
    
    # Words to be checked for numbers right after them ('balie 12', 'sector 3A')
    _NUMBER_INDICATORS = r"balie|sector|pier|parkeerzone|zone|agent[- \s]*id"

    def _mask_additional_id_numbers(self, text: str) -> str:
        """
        Mask numbers that appear after entries in _NUMBER_INDICATORS 
        """
        pattern = re.compile(rf'({self._NUMBER_INDICATORS})(\s*[\-:]*\s*)(\d+)\b', re.IGNORECASE)
        text = pattern.sub(rf'\1\2{self._mask.format(tag=TRANSLATIONS[TAG_LANGUAGE].get("ID_Number", "ID_Number"))}', text)
        return text

    # BSN-indicatoren: een BSN-vormig getal in deze context is óók PII als het de
    # elfproef faalt (fout ingevoerd maar reëel). Bewust strikt (geen letters tussen
    # indicator en nummer) om over-maskering van willekeurige 9-cijferreeksen te voorkomen.
    _BSN_CONTEXT_RE = re.compile(
        r"(?i)\b(bsn|burgerservicenummer)\b(\W{0,15}?)(\d{9}|\d{4}\.\d{2}\.\d{3})\b"
    )


    def _anonymize_bsn(self, text: str, pattern: Pattern) -> str:
        """
        Replace BSN numbers only if they pass 11-proef validation.
        
        Parameters
        ----------
        text : str
            Input text containing potential BSN numbers.
        pattern : Pattern
            Compiled regex pattern for BSN matching.
            
        Returns
        -------
        str
            Text with validated BSNs replaced.
        """
        mask = self._mask.format(tag=TRANSLATIONS[TAG_LANGUAGE].get("BSN", "BSN"))

        # 1) Context-pass: behoud indicator + scheidingsteken, vervang alleen het nummer.
        text = self._BSN_CONTEXT_RE.sub(lambda m: f"{m.group(1)}{m.group(2)}{mask}", text)

        # 2) Validity-pass op de rest (precisie: elders alleen 11-proef-geldige BSNs).
        def replace_if_valid(match: re.Match) -> str:
            bsn = match.group(0)
            if is_valid_bsn(bsn):
                return mask
            return bsn  # Keep original if invalid
        
        return pattern.sub(replace_if_valid, text)

    # Makes the instance directly callable (handy for DataFrame.map)
    __call__ = anonymize

    # ------------------------------------------------------------------ #
    # Utilities                                                          #
    # ------------------------------------------------------------------ #

    def verify(self, text: str) -> Dict[str, bool]:
        """
        Return a dict {tag: bool} indicating whether *text* still contains
        any unmasked pattern for each tag.  Useful for unit tests.
        """
        return {TRANSLATIONS[TAG_LANGUAGE].get(tag, tag): bool(pat.search(text)) for tag, pat in self._patterns.items()}
    
# --------------------------------------------------------------------------- #
# 4. List Anonymizer class                                                    #
# --------------------------------------------------------------------------- #

def _load_list_excel(file_path: str) -> Dict[str, pd.DataFrame]:
    """Load the Excel file containing lists for anonymization."""
    try:
        List_Excel = pd.read_excel(file_path, sheet_name=None)
    except FileNotFoundError:
        # If the file is not found, raise an error
        raise FileNotFoundError(f"Could not find the file {file_path} for the ListAnonymizer. Please ensure it exists in the working directory.")
    except PermissionError:
        # If the file is open in another program (like Excel), a PermissionError may occur
        raise PermissionError(f"Permission denied when trying to read the file {file_path}. Please make sure the file is not opened.")
        # Raise other exceptions
    except Exception as e:
        raise Exception(f"An error occurred while reading {file_path}: {e}")
    
    return List_Excel


class ListAnonymizer:
    def __init__(self, distinct_tags: bool | None = None):
        self.list_path = LIST_PATH
        self.whitelist_path = WHITELIST_PATH

        List_Excel = _load_list_excel(self.list_path)
        self.WHITELIST_LISTANONYMIZER = _load_whitelist_excel(self.whitelist_path, sheet_name="List")["List"].tolist()

        self.ListAnonymizer_dict = {}
        self.case_sensitive_dict = {}  # Store case sensitivity per entry
        self._distinct_tags: bool = distinct_tags if distinct_tags is not None else DISTINCT_TAGS
        self.tussenvoegsels = {"van", "der", "den", "de", "ten", "ter"} # Common Dutch "tussenvoegsels", names containing these will be treated as case-insensitive

        # --- SymSpell Initialization ---
        # max_dictionary_edit_distance: How many deletions to pre-calculate.
        # prefix_length: Speeds up lookups.
        if SYMSPELL:
            self.symspell = SymSpell(max_dictionary_edit_distance=2, prefix_length=7)
            self.word_to_tag_map = {} # Maps a list word to its tag (e.g., "Jansen" -> "Name")
        # ---

        # --- Flashtext Initialization ---
        self.kp_ci = flashtext.KeywordProcessor() # Case insensitive keyword processor
        self.kp_cs = flashtext.KeywordProcessor(case_sensitive=True) # Case sensitive keyword processor
        self.kp_wl = flashtext.KeywordProcessor() # Whitelist keyword processor
        # ---

        # Initialize a combined list for "Name"
        combined_name_list = []
        combined_name_case_sensitive = []
        
        # Add each sheet in the input Excel as a list in the ListAnonymizer dictionary
        for sheet_name, df in List_Excel.items():

            # Add the tags to the NER whitelist to avoid NER masking masks
            if sheet_name in ["First Name", "Last Name"]:
                sn_translated = TRANSLATIONS[TAG_LANGUAGE].get('Name', 'Name') # First Name and Last Name are concatenated to 'Name' in the output of the model
            else:
                sn_translated = TRANSLATIONS[TAG_LANGUAGE].get(sheet_name, sheet_name)
            tag_format = f"<({sn_translated})>" if self._distinct_tags else f"<{sn_translated}>"
            if WEAK_NER_WHITELIST is not None and tag_format not in WEAK_NER_WHITELIST:
                WEAK_NER_WHITELIST.append(tag_format)

            # Strip quotes from each item
            entries = [item.replace('"', '').replace("'", "") for item in df["List"].tolist()]
            
            # Read case sensitivity (default to 0/False if column doesn't exist)
            if 'Case Sensitive' in df.columns:
                case_sensitive_flags = [bool(int(flag)) if pd.notna(flag) else False for flag in df["Case Sensitive"].tolist()]
            else:
                case_sensitive_flags = [False] * len(entries)
            
            # --- SymSpell Dictionary Loading ---
            if SYMSPELL:
                for entry, is_case_sensitive in zip(entries, case_sensitive_flags):
                    # Only add single-word, case-insensitive entries to SymSpell
                    if ' ' not in entry and not is_case_sensitive:
                        # Use lowercase for SymSpell dictionary for case-insensitive matching
                        lower_entry = entry.lower()
                        if not self.symspell.create_dictionary_entry(lower_entry, 1):
                            # Entry might already exist from another list (e.g., a name that is also a street)
                            # We prioritize the first tag found.
                            pass
                        self.word_to_tag_map[lower_entry] = sheet_name
            # ---

            if sheet_name in ["First Name", "Last Name"]:
                # Add to the combined "Name" list (preserve original case)
                combined_name_list.extend(entries)
                combined_name_case_sensitive.extend(case_sensitive_flags)
            else:
                # Store entries with their case sensitivity
                self.ListAnonymizer_dict[sheet_name] = entries
                self.case_sensitive_dict[sheet_name] = dict(zip(entries, case_sensitive_flags))
        
        # Set the combined "Name" list (preserve original case)
        if combined_name_list:
            self.ListAnonymizer_dict["Name"] = combined_name_list
            self.case_sensitive_dict["Name"] = dict(zip(combined_name_list, combined_name_case_sensitive))
            if SYMSPELL:
                # Also load the combined names into SymSpell
                for entry, is_case_sensitive in zip(combined_name_list, combined_name_case_sensitive):
                    if ' ' not in entry and not is_case_sensitive:
                        lower_entry = entry.lower()
                        if not self.symspell.create_dictionary_entry(lower_entry, 1):
                            pass
                        if lower_entry not in self.word_to_tag_map:
                            self.word_to_tag_map[lower_entry] = "Name"

        # Build Flashtext dictionaries
        for tag, list_items in self.ListAnonymizer_dict.items():
            mapping = self.case_sensitive_dict[tag]  # Cache the dict to avoid repeated attribute/index lookups
            ci_list = []
            cs_list = []
            # Add keywords to either case sensitive or insensitive keyword processor, accordingly
            for i in list_items:
                tokens = i.split()
                contains_tv = tag == "Name" and any(token.lower() in self.tussenvoegsels for token in tokens) # Always add names with 'tussenvoegsels' to the case insensitive list
                if mapping[i] and not contains_tv:
                    cs_list.append(i)
                else:
                    ci_list.append(i)
            self.kp_ci.add_keywords_from_dict({self._get_tag_format(tag): ci_list})
            self.kp_cs.add_keywords_from_dict({self._get_tag_format(tag): cs_list})

        self.kp_wl.add_keywords_from_list(self.WHITELIST_LISTANONYMIZER) # Build Whitelist dictionary

    def _build_multi_word_pattern(self, entry: str) -> str:
        """Build a regex pattern for a multi-word entry, making 'tussenvoegsels' case-insensitive."""
        
        parts = re.split(r'([\s\-])', entry) # Split by space or hyphen, keeping delimiters
        pattern_parts = []
        
        for part in parts:
            if part.lower() in self.tussenvoegsels:
                # Make "tussenvoegsel" case-insensitive
                pattern_parts.append(f"(?i:{re.escape(part)})")
            elif part in [' ', '-']:
                # Allow space or hyphen as separator
                pattern_parts.append(r'[\s\-]')
            else:
                # Keep other parts as they are (respecting case)
                pattern_parts.append(re.escape(part))
        
        return r'\b' + ''.join(pattern_parts) + r'\b'

    def _is_whitelisted(self, text: str, start_pos: int, end_pos: int) -> bool:
        """Check if the text segment matches any whitelisted phrase."""
        segment = text[start_pos:end_pos].lower()
        return segment in self.WHITELIST_LISTANONYMIZER

    def _get_tag_format(self, tag: str) -> str:
        """Return the appropriate tag format based on distinct_tags setting."""
        tag = TRANSLATIONS[TAG_LANGUAGE].get(tag, tag) # Translate tag into chosen language
        if self._distinct_tags:
            return f"<({tag})>"
        else:
            return f"<{tag}>"
        
    def _flashtext_replacer(self, text: str, kp_cs: flashtext.KeywordProcessor, kp_ci: flashtext.KeywordProcessor, kp_wl: flashtext.KeywordProcessor) -> str:
        """Prefer longest matches globally across kp_cs and kp_ci, then replace once."""
        # Gather spans from original text
        spans: list[tuple[int,int,str]] = [] # spans of replaced keywords
        spans_wl: list[tuple[int,int,str]] = [] # spans of whitelisted words, to be placed back after processing

        for _w, s, e in kp_wl.extract_keywords(text, span_info=True):
            spans_wl.append((s, e))
        for tag, s, e in kp_cs.extract_keywords(text, span_info=True):
            spans.append((s, e, tag))
        for tag, s, e in kp_ci.extract_keywords(text, span_info=True):
            spans.append((s, e, tag))

        if not spans:
            return text

        # Sort by length desc, then start asc
        spans.sort(key=lambda x: (-(x[1]-x[0]), x[0]))

        # Greedily select non-overlapping spans
        selected = []
        def overlaps(a, b):
            return not (a[1] <= b[0] or b[1] <= a[0])

        for s, e, tag in spans:
            if any(overlaps((s, e), (ss, ee)) for ss, ee, _ in selected): # don't add shorter versions of phrases already selected
                continue
            if any(ws <= s and e <= we for ws, we in spans_wl): # don't add phrases that fall within a whitelisted phrase
                continue
            selected.append((s, e, tag))

        # Apply replacements in a single pass (sorted by start)
        selected.sort(key=lambda x: x[0])
        out = []
        cur = 0
        for s, e, tag in selected:
            if s > cur:
                out.append(text[cur:s])
            out.append(tag)
            cur = e
        if cur < len(text):
            out.append(text[cur:])

        return "".join(out)


    def anonymize(self, text: str) -> str:
        """Return <(tag)> with every matched word in the text replaced."""
        if not isinstance(text, str):
            return text  # ignore NaNs
        
        # Run flashtext processor twice (case sensitive and case insensitive)
        text = text.replace("\u0130", "I") # Avoid an edge-case problem with a certain Turkish capital letter (see https://github.com/vi3k6i5/flashtext/issues/44)
        text = self._flashtext_replacer(text, self.kp_cs, self.kp_ci, self.kp_wl)

        # Apply Symspell fuzzy match
        words = text.split()
        replacements = []  # Store (original_word, replacement, position) tuples
        current_pos = 0
        
        for i, word in enumerate(words):
            # Find the actual position in the original text
            word_start = text.find(word, current_pos)
            word_end = word_start + len(word)
            current_pos = word_end
            
            # Skip if already masked
            if self._distinct_tags:
                if word.startswith('<(') and word.endswith(')>'):
                    continue
            else:
                if word.startswith('<') and word.endswith('>'):
                    continue
            
            # Skip if this position is whitelisted (check with surrounding context)
            context_start = max(0, word_start - 20)
            context_end = min(len(text), word_end + 20)
            skip = False
            for wl_item in self.WHITELIST_LISTANONYMIZER:
                if wl_item.lower() in text[context_start:context_end].lower():
                    # Check if current word is part of the whitelisted phrase
                    wl_pattern = r'\b' + re.escape(wl_item) + r'\b'
                    for wl_match in re.finditer(wl_pattern, text[context_start:context_end], flags=re.IGNORECASE):
                        actual_start = context_start + wl_match.start()
                        actual_end = context_start + wl_match.end()
                        if actual_start <= word_start < actual_end:
                            skip = True
                            break
                if skip:
                    break
            
            if skip:
                continue

            # Clean the word by removing punctuation
            word_stripped = word.replace(',', '').replace('.', '').replace("'", '').replace('"', '')

            # Fuzzy Match for single, case-insensitive words (if no exact match was found)
            # Only apply to words longer than 6 characters to avoid false positives.
            if len(word_stripped) > 6 and SYMSPELL:
                # max_edit_distance: 1 for fewer false positives, 2 for more recall.
                # Verbosity.TOP: returns the best match.
                suggestions = self.symspell.lookup(
                    word_stripped.lower(), Verbosity.TOP, max_edit_distance=1, include_unknown=False
                )
                if suggestions:
                    best_suggestion = suggestions[0].term
                    # Find the original tag for this suggested word
                    if best_suggestion in self.word_to_tag_map:
                        tag = self.word_to_tag_map[best_suggestion]
                        tag_format = self._get_tag_format(tag)
                        replacements.append((word, tag_format, word_start))

        
        # Apply replacements from right to left to preserve positions
        for original, replacement, pos in sorted(replacements, key=lambda x: x[2], reverse=True):
            text = text[:pos] + text[pos:].replace(original, replacement, 1)
        
        # Merge consecutive <(Name)> tags into one
        name_tag = self._get_tag_format("Name")
        name_pattern = re.escape(name_tag) + r'\s+' + re.escape(name_tag)
        text = re.sub(name_pattern, name_tag, text)

        # Check for initials before and after a name
        name_pattern_init = r'\b([A-Z]\.?)+[-\s\(\),]*' + re.escape(name_tag) + '|' + re.escape(name_tag) + r'[-\s\(\),]*([A-Z]\.?){2,}'
        text = re.sub(name_pattern_init, name_tag, text)

        # Check for house numbers after or before an address tags
        address_tag = self._get_tag_format("Address")
        address_pattern = re.escape(address_tag) + r'[-\s\(\),]+(\d+[A-Za-z]?(?:-[A-Za-z])?)\b|\b(\d+[A-Za-z]?(?:-[A-Za-z])?)[-\s\(\),]+' + re.escape(address_tag)
        text = re.sub(address_pattern, address_tag, text)
        
        return text

    # Makes the instance directly callable (handy for DataFrame.map)
    __call__ = anonymize

# --------------------------------------------------------------------------- #
# 5. GLINER NER Anonymizer class                                              #
# --------------------------------------------------------------------------- #

class NERAnonymizer:
    def __init__(self, model_name: str = "E3-JSI/gliner-multi-pii-domains-v1", distinct_tags: bool | None = None, print_confidence: bool | None = None):
        # Suppress transformers truncation warnings
        transformers_logging.set_verbosity_error()
        
        try:
            self.model = GLiNER.from_pretrained(model_name, local_files_only=True)
        except:
            print(f"Model {model_name} not found locally. Downloading from Hugging Face...")
            self.model = GLiNER.from_pretrained(model_name)

        self._distinct_tags: bool = distinct_tags if distinct_tags is not None else DISTINCT_TAGS
        self._print_confidence: bool = print_confidence if print_confidence is not None else PRINT_NER_CONFIDENCE
        
        # Mapping from Dutch labels to English labels
        self.label_mapping = {
            "naam": "Name",
            "adres": "Address",
            "name": "Name",
            "address": "Address",
            "organization": "Organization",
            "organisatie": "Organization"
        }

        self.whitelist_path = WHITELIST_PATH
        whitelist_ner = _load_whitelist_excel(self.whitelist_path, sheet_name="NER")
        # Normalize and combine global and Excel weak whitelist entries (avoid .append return None)
        weak_from_excel = [str(x).lower() for x in whitelist_ner["Weak"].dropna().tolist()]
        strong_from_excel = [str(x).lower() for x in whitelist_ner["Strong"].dropna().tolist()]
        # Do not mutate the global constant; create instance attributes
        existing_weak = [str(x).lower() for x in (WEAK_NER_WHITELIST or []) if pd.notna(x)]
        self.WEAK_NER_WHITELIST = existing_weak + weak_from_excel
        self.STRONG_NER_WHITELIST = strong_from_excel

    def _get_tag_format(self, tag: str, confidence: float | None = None) -> str:
        """Return the appropriate tag format based on distinct_tags setting."""
        tag = TRANSLATIONS[TAG_LANGUAGE].get(tag, tag) # Translate tag into chosen language
        if self._distinct_tags:
            if confidence is not None and self._print_confidence:
                return f"<[{tag}, C{confidence}]>"
            else:
                return f"<[{tag}]>"
        else:
            return f"<{tag}>"

    def anonymize(self, text: str) -> str:
        """Return *text* with every identified entity replaced."""
        if not isinstance(text, str):
            return text  # ignore NaNs

        # prepare the labels/entities to be extracted, see list of all supported entities: 
        # https://huggingface.co/E3-JSI/gliner-multi-pii-domains-v1#:~:text=This%20model%20has%20been%20trained,the%20synthetic%20dataset%20%2024
        # Works best with lower case labels, using both Dutch and English versions for better recall
        labels = ["naam", "name", "adres", "address", "organization", "organisatie"]

        # perform entity extraction with set minimum confidence threshold
        entities = self.model.predict_entities(text, labels=labels, min_confidence=min(NER_CONFIDENCE_DICT.values()))

        # replace extracted entities in the text with their labels
        for entity in sorted(entities, key=lambda x: x['start'], reverse=True):

            # Check if the mask exceeds the required confidence threshold for the given tag
            if entity['score'] < NER_CONFIDENCE_DICT[self.label_mapping.get(entity['label'], entity['label'])]:
                continue  # Skip low-confidence entities

            # First check if the detected entity exactly matches items in weak whitelist (ignore case and dots and apostrophes)
            if entity['text'].lower().replace(".","").replace("'","") in (item.lower() for item in self.WEAK_NER_WHITELIST):
                # If so, do not mask it
                continue

            # Then check if the detected entity contains any of the strong whitelist items (ignore case)
            if any(re.search(re.escape(item.lower()), entity['text'].lower()) for item in self.STRONG_NER_WHITELIST):
                # If so, do not mask it
                continue

            # Normalize label to English version
            normalized_label = self.label_mapping.get(entity['label'], entity['label'])

            tag_format = self._get_tag_format(normalized_label, round(entity['score'], 2)) if self._distinct_tags else self._get_tag_format(normalized_label)
            text = (
                text[:entity['start']] + tag_format + text[entity['end']:]
            )
        
        # Post-process: capture house numbers after address tags
        address_tag = TRANSLATIONS[TAG_LANGUAGE].get('Address', 'Address')
        address_tag_pattern = rf'<\[{address_tag}(?:, C[\d.]+)?\]>' if self._distinct_tags else rf'<{address_tag}>'
        text = re.sub(address_tag_pattern + r'\s+(\d+[A-Za-z]?)\b', self._get_tag_format("Address"), text, flags=re.IGNORECASE)

        # Post-process: merge consecutive Name tags
        name_tag = TRANSLATIONS[TAG_LANGUAGE].get('Name', 'Name')
        name_tag_pattern = rf'<\[{name_tag}(?:, C[\d.]+)?\]>' if self._distinct_tags else rf'<{name_tag}>'
        text = re.sub(name_tag_pattern + r'\s+' + name_tag_pattern, self._get_tag_format("Name"), text)

        # Post-process: check for initials before and after a name
        name_pattern_init = r'\b([A-Z]\.?)+[-\s\(\),]*' + re.escape(name_tag) + '|' + re.escape(name_tag) + r'[-\s\(\),]*([A-Z]\.?){2,}'
        text = re.sub(name_pattern_init, name_tag, text)
        
        return text
    
    # Makes the instance directly callable (handy for DataFrame.map)
    __call__ = anonymize


# --------------------------------------------------------------------------- #
# 4. Combine NER-REGEX masks                                                  #
# --------------------------------------------------------------------------- #

class CombinedAnonymizer:
    """
    Combines RegexAnonymizer and NERAnonymizer to mask PII using both approaches.
    First applies regex patterns, then runs NER on the result to catch any remaining entities.
    """
    
    def __init__(
        self,
        regex_tags: Iterable[str] | None = None,
        regex_mask: str = "<{tag}>",
        ner_model: str = "E3-JSI/gliner-multi-pii-domains-v1",
        distinct_tags: bool | None = None,
        print_confidence: bool | None = None
    ) -> None:
        """
        Initialize both anonymizers.
        
        Parameters
        ----------
        regex_tags : Iterable[str] | None
            Subset of regex tags to activate. None → use all.
        regex_mask : str
            Placeholder format for regex matches.
        ner_model : str
            GLiNER model name for NER-based anonymization.
        distinct_tags : bool | None
            If True, use distinct tag formats. If None, use global DISTINCT_TAGS.
        print_confidence : bool | None
            If True, print confidence scores in NER tags. If None, use global PRINT_NER_CONFIDENCE.
        """
        distinct = distinct_tags if distinct_tags is not None else DISTINCT_TAGS
        # Initialize all anonymizers
        self.regex_anonymizer = RegexAnonymizer(tags=regex_tags, mask=regex_mask, distinct_tags=distinct)
        self.list_anonymizer = ListAnonymizer(distinct_tags=distinct)
        self.ner_anonymizer = NERAnonymizer(model_name=ner_model, distinct_tags=distinct, print_confidence=print_confidence)
        
    def anonymize(self, text: str) -> str:
        """
        Apply both regex, list, and NER anonymization sequentially.
        
        Parameters
        ----------
        text : str
            Input text to anonymize.
            
        Returns
        -------
        str
            Text with all detected PII replaced by placeholder tags.
        """
        if not isinstance(text, str):
            return text  # ignore NaNs
        
        # First pass: regex-based pattern matching
        text = self.regex_anonymizer.anonymize(text)

        # Second pass: List-based entity detection
        text = self.list_anonymizer.anonymize(text)
        
        # Third pass: NER-based entity detection
        text = self.ner_anonymizer.anonymize(text)
        
        return text
    
    # Makes the instance directly callable (handy for DataFrame.map)
    __call__ = anonymize


# --------------------------------------------------------------------------- #
# 5. Command‑line interface                                                   #
# --------------------------------------------------------------------------- #

def main() -> None:  # pragma: no cover – CLI wrapper
    # De anonymizer-classes lezen deze module-globals bij constructie; main() zet ze
    # (niet lokale variabelen). Declaratie staat boven elk gebruik van LIST_PATH/
    # WHITELIST_PATH in deze functie (ook de argparse-defaults hieronder).
    global LIST_PATH, WHITELIST_PATH
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("input", type=Path, help=".xlsx file to read")
    parser.add_argument("output", type=Path, help=".xlsx file to write")
    parser.add_argument("--text-column", default="Toelichting_unmasked",
                        help="Name of the column containing free text")
    parser.add_argument("--masked-text-column", default="Toelichting_masked",
                        help="Name of the new column containing masked text")
    parser.add_argument("--blacklist-path", type=Path, default=LIST_PATH,
                        help="Path to blacklist file (default: bundled 'ListClassifier Basic.xlsx')")
    parser.add_argument("--whitelist-path", type=Path, default=WHITELIST_PATH,
                        help="Path to whitelist files (default: bundled 'Whitelist Basic.xlsx')")
    args = parser.parse_args()

    LIST_PATH = str(args.blacklist_path)
    WHITELIST_PATH = str(args.whitelist_path)

    masked_col_name = args.masked_text_column

    anonymizer = CombinedAnonymizer()
    LOGGER.info("Loading %s ...", args.input)

    df = pd.read_excel(args.input, dtype=str, engine="openpyxl")
    df[masked_col_name] = df[args.text_column].map(anonymizer)

    LOGGER.info("Writing %s ...", args.output)
    df.to_excel(args.output, index=False, engine="openpyxl")
    LOGGER.info("Done.")


if __name__ == "__main__":
    main()


# --------------------------------------------------------------------------- #
# Doctest                                                                    #
# --------------------------------------------------------------------------- #
# >>> a = RegexAnonymizer()
# >>> sample = (
# ...     "Claim 0000000000 Euro 8,50 op 16 / 04 / 2022 (7u tot 20u); melding 0000-000000; "
# ...     "compliment 000000-XX000000000 op 26-02-2025; juni 2020."
# ... )
# >>> a(sample)
# '<CLAIM_ID> <Money> op <Date> (<Time>); <NOTIFICATION_ID>; <COMPLIMENT_ID> op <Date>; <Date_Ext>'