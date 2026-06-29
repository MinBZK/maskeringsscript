# Anonymization Script - Gemeente Rotterdam

This model was developed by the City of Rotterdam. Copyright City of Rotterdam.

This repository is the published version of the anonymization tool, derived from the original developed by the City of Rotterdam, and released under the EUPL v1.2. It adds pre-publication hardening only; see [CHANGELOG.md](CHANGELOG.md) for the changes.

> **Privacy disclaimer.** This script anonymises text, but the result is not guaranteed to be complete and depends in part on the information provided: identifiable information may remain. Whether additional review is needed depends on the requirements of the application. That assessment lies with the organisation using it.

(For Dutch, [See below](#-nederlandse-versie))

## Table of Contents

- [Quick Start](#quick-start)
  - [Setup](#setup)
  - [Quick Usage Examples](#quick-usage-examples)
  - [Overview of Files](#overview-of-files)
- [What Does the Script Do](#what-does-the-script-do)
- [Why Was This Script Developed](#why-was-this-script-developed)
- [Running the Script](#running-the-script)
- [How Does the Script Work](#how-does-the-script-work)
- [Whitelists: Weak and Strong](#whitelists-weak-and-strong)
- [How to Edit the Regex Patterns](#how-to-edit-the-regex-patterns)
- [How to Edit the Lists](#how-to-edit-the-lists)
- [How to Configure NER](#how-to-configure-ner)
- [Steps to Generalize to New Organisation](#steps-to-generalize-to-new-organisation)
- [Evaluation Scores](#evaluation-scores)

---

## Quick Start

### Setup

> **Requires Python 3.10 or higher.**

1. Clone the repository and navigate into it
2. Create a virtual environment:
   ```bash
   python -m venv .venv
   ```
3. Activate the virtual environment:
   - Windows: `.venv\Scripts\activate`
   - Mac/Linux: `source .venv/bin/activate`
4. Install the module:
   ```bash
   pip install git+https://github.com/MinBZK/maskeringsscript.git
   ```
   Or:
   ```bash
   pip install .
   ```
5. (Optional) Download the GLiNER model locally for faster execution:
   ```bash
   git clone https://huggingface.co/E3-JSI/gliner-multi-pii-domains-v1
   ```

### Quick Usage Examples

**Command Line (CLI):**
```bash
python -m anonymizer raw_data/Sample_Rotterdam.xlsx results/Sample_Rotterdam_output.xlsx --text-column Toelichting_unmasked --masked-text-column Toelichting_masked
```

**Create a sampled testset:**
```bash
python -m anonymizer.helpers.sample_testset raw_data/Sample_Rotterdam.xlsx results/Sample_Rotterdam_output.xlsx --sample-size 400 --seed 42
```

**Jupyter Notebook:**
- Open `tests/processing_and_testing.ipynb` with Jupyter / VS Code
- Run all cells to clean, mask, and export results

### Overview of Files

- **src/anonymizer/anonymizer.py**: Main implementation containing `RegexAnonymizer`, `ListAnonymizer`, `NERAnonymizer`, and `CombinedAnonymizer` classes. Includes CLI for running the anonymizer on Excel files. Run with `python -m anonymizer` after installation.

- **src/anonymizer/input_files/ListClassifier Basic.xlsx**: Word lists for the ListAnonymizer. Each sheet represents a category (e.g., "First Name", "Last Name", "Address"). Bundled with the package (package-data) so it is found after `pip install`. Edit without touching code, or duplicate it to maintain your own blacklist and pass it via `--blacklist-path`.

- **src/anonymizer/input_files/Whitelist Basic.xlsx**: Whitelists to prevent false positives. Two sheets:
  - "NER" sheet: "Weak" (exact match) and "Strong" (substring match) columns
  - "List" sheet: "List" column for List Anonymizer whitelist
  
  Optionally duplicate this file to maintain your own whitelist.

- **src/anonymizer/helpers**: Multiple helper scripts (see files for examples):
  - sample_testset: submodule to draw reproducible samples from input data and build test workbooks for evaluation.
  - kvk_preprocessing: submodule to extract variations of organisation names derived from KVK Handelsregister
  - streetnames: submodule to update (Dutch) street names in the address blacklist
  - scoring: submodule to calculate precision, recall and f1 scores for a manually checked test set

- **tests/processing_and_testing.ipynb**: Jupyter notebook with examples of data loading, cleaning, masking, and sampling. Guided introduction to the anonymization pipeline.

### Recommended Workflow

1. Follow setup steps to install virtual environment with correct packages
2. Run the combined anonymizer and inspect output
3. Create evaluation testsets using the `sample_testset` submodule

---

## What Does the Script Do

The script automatically anonymizes personal text data by detecting and replacing personally identifiable information (PII) with placeholder tokens. It processes free-text fields (such as complaint descriptions, case notes, or feedback) and masks sensitive information including:

- **Personal identifiers**: BSN (citizen service numbers), KVK/BTW numbers
- **Contact information**: Phone numbers, email addresses, URLs, IBANs
- **Financial data**: Money amounts, credit card numbers
- **Temporal data**: Dates (Date and Date_Ext), ages
- **Location data**: Postal codes, licence plates, addresses, IP addresses
- **Administrative codes**: ID numbers (case IDs, claim numbers, permit IDs, customer IDs, request IDs, and other reference numbers)
- **Numeric data**: Numbers (euro-style decimal format)

The output is text where all sensitive information is replaced with tags like `<Name>`, `<BSN>`, `<Phone>`, `<Date>`, `<Money>`, etc., making it safe for analysis, sharing, or storage while preserving the structure and context of the original text.

---

## Why Was This Script Developed

Until now, the city of Rotterdam used an algorithm to mask texts for which they had no access to the source code. This meant there was little control over how it worked, and other government organizations could not easily use it. The desire was to develop an in-house algorithm that:

- Is transparent and adaptable
- Can be shared with other government bodies
- Meets the requirements of privacy and information security

**Goal of the project:**
The goal was to deliver a working Python script that automatically recognizes and replaces sensitive information from text, such as names, addresses, or citizen service numbers. It had to perform well, be well-explainable, and be easily applicable by other governments.

**What has been delivered:**
- A working masking script that replaces traceable information in texts with neutral codes (e.g., `<Name>`, `<BSN>`)
- The script works based on various techniques: fixed pattern recognition (such as for phone numbers), language analysis (NER: Named Entity Recognition), and list-based matching
- Users can manage exceptions and additions themselves via lists and configuration files
- The masking script performs well: it catches many correct cases (high recall) and masks few unnecessary words (good precision). The developed script scores better than the former script being used
- The script is written in Python and is ready to be shared as open source
- Extensive documentation has been delivered for technical use

---

## Running the Script

The script does not require a powerful computer - it can run on a standard laptop with Python installed.

The script can be used in three ways:

### 1. Command Line (CLI)

Run the combined anonymizer on an Excel file:
```bash
python -m anonymizer input.xlsx output_masked.xlsx --text-column Toelichting_unmasked
```

### 2. Python Library

Import and use in your own code:
```python
from anonymizer import anonymizer
import pandas as pd

# Optional: use custom blacklists and whitelists
anonymizer.LIST_PATH = "Path/to/blacklist.xlsx"
anonymizer.WHITELIST_PATH = "Path/to/whitelist.xlsx"

df = pd.read_excel("input.xlsx")
an = anonymizer.CombinedAnonymizer()
df["masked_text"] = df["original_text"].map(an)
df.to_excel("output.xlsx", index=False)
```

### 3. Jupyter Notebook

Use the `tests/processing_and_testing.ipynb` notebook for guided data processing with examples of data loading, cleaning, masking, and sampling.

---

## How Does the Script Work

The script uses a three-stage sequential approach to detect and mask PII:

### 1. Regex Anonymizer (RegexAnonymizer class)

Uses regular expressions to detect fixed-pattern PII such as:
- Dates and times: Date (26-02-2025, 2025-02-26), Date_Ext (3 april 2024, 21e van Januari)
- Money amounts: Money (€216,62, Euro 8,50)
- Numbers: Number (342,50, 1.234,56) - euro-style decimal format
- Phone numbers: Phone (+31 6 12345678, 06-12345678, 088 12 24 44 00)
- Email addresses: Email
- URLs: URL (excluding rotterdam.nl domains)
- Postal codes: Postcode (1234 AB)
- Licence plates: Licence_Plate (AA-12-BB, 12-AB-34, etc.)
- Financial identifiers: IBAN, BSN (with 11-proef validation), KVK, BTW
- ID numbers: ID_Number (case IDs, claim IDs, permit IDs, customer IDs, request IDs, notification IDs, compliment IDs, akte IDs, agent IDs, contract numbers)
- Ages: Age (74 jaar oud, 25-jarige)
- Network: IP_Address (192.168.1.1)
- Credit cards: Credit_Card (13–19 digit numbers)

The regex patterns are defined in the `TAGGED_PATTERNS` dictionary and can be customized. High-specificity patterns are applied first, followed by broader patterns to maximize recall while maintaining precision.

### 2. List Anonymizer (ListAnonymizer class)

Matches words against curated lists loaded from an Excel file (`ListClassifier Basic.xlsx`):
- First names and last names (combined as "Name" tag)
- Street names and addresses
- Other custom lists as configured

Features include:
- Case-sensitive and case-insensitive matching options
- Multi-word phrase detection (e.g., "van der Berg" and "Paul Krugerstraat")
- SymSpell integration for typo correction (fuzzy matching)
- Whitelist support to prevent false positives
- Automatic merging of consecutive name tags and handling of initials and house numbers

**Post-processing for Names:**
After detecting individual name components, the List Anonymizer performs additional cleanup:
- **Consecutive names merging**: Multiple `<Name>` tags in a row are merged into a single tag
- **Initials detection**: Initials before or after a name are included in the mask:
  - "J. Jansen" → `<Name>`
  - "Jansen J." → `<Name>`
  - "J.P. de Vries" → `<Name>`

**Post-processing for Addresses:**
- **House numbers**: Numbers appearing directly before or after an address tag are included in the mask:
  - "Mainstreet 42" → `<Address>`
  - "42 Mainstreet" → `<Address>`

### 3. NER Anonymizer (NERAnonymizer class)

Uses the GLiNER (Generalist and Lightweight Named Entity Recognition) model to detect contextual entities:
- Names (Person names in various contexts)
- Addresses (Location mentions)

The NER model works with confidence thresholds and can detect entities that don't match fixed patterns or lists. It includes weak and strong whitelists to prevent masking of common words or municipality-specific terms.

**Post-processing for Names:**
- **Consecutive names merging**: Multiple `<Name>` tags in a row are merged into a single tag
- **Initials detection**: Initials immediately before a detected name are included in the mask

**Post-processing for Addresses:**
- **House numbers**: Numbers appearing directly after an address tag are included in the mask

### Combined Approach (CombinedAnonymizer class)

The three methods are applied sequentially: **Regex → List → NER**. This layered approach ensures:
- High recall: Multiple techniques catch different types of PII
- Good precision: Later stages skip already-masked content
- Flexibility: Each component can be configured independently

---

## Whitelists: Weak and Strong

The script uses two types of whitelists to prevent false positives (masking non-sensitive information):

### Weak Whitelist (Exact Match)

Checks for exact matches (case-insensitive) with the entire detected entity. Used for:
- Common titles and pronouns: "Mevrouw", "Meneer", "Hij", "Zij", "I", "You", etc.
- Municipality names: "Rotterdam", "Amsterdam", "Utrecht", "Den Haag", etc.
- Generic terms: "Burger", "Family", "Person", etc.
- Tags from other anonymizers to prevent double-masking

**Example**: "Mevrouw" is not masked, but "Mevrouw Jansen" will be masked.

### Strong Whitelist (Substring Match)

Checks if any whitelisted term appears within the detected entity (case-insensitive). Used for:
- Family relationships: "Vader", "Moeder", "Broer", "Zus", "Father", "Mother", etc.
- Generic descriptors: "Collega", "Klant", "Medewerker", "Employee", etc.
- Neighborhood names specific to the municipality (e.g., Rotterdam neighborhoods: "De Esch", "Prins Alexander", etc.)
- Address-related terms: "Adres", "Address", "Woning", etc. (NER tends to see 'adresboek' as an address)

**Example**: "Mijn jongere zus" is not masked because it contains "zus" (sister).

### Editing Whitelists

Whitelists are now managed through the `Whitelist Basic.xlsx` Excel file, making it easy to add or remove entries without modifying the script code:

**For NER Anonymizer whitelists:**
1. Open `Whitelist Basic.xlsx`
2. Navigate to the "NER" sheet
3. The sheet contains two columns:
   - **Weak column**: Add entries for exact match whitelisting
   - **Strong column**: Add entries for substring match whitelisting
4. Add or remove entries as needed (one per row)
5. Save the file
6. Re-run the script - changes will be automatically loaded

**For List Anonymizer whitelist:**
1. Open `Whitelist Basic.xlsx`
2. Navigate to the "List" sheet
3. The sheet contains one column:
   - **List column**: Add entries that should not be masked by the List Anonymizer
4. Add or remove entries as needed (one per row)
5. Save the file
6. Re-run the script - changes will be automatically loaded

**Note**: All whitelist entries are automatically converted to lowercase for case-insensitive matching.

---

## How to Edit the Regex Patterns

The regex patterns are defined in the `TAGGED_PATTERNS` dictionary in `anonymizer.py` (around line 100). Each pattern is a key-value pair where the key is the tag name and the value is the regex pattern.

### To modify existing patterns:

1. Open `anonymizer.py`
2. Locate the `TAGGED_PATTERNS` dictionary
3. Find the pattern you want to modify (e.g., "Phone", "Date", "BSN")
4. Edit the regex string, maintaining the verbose format with `re.VERBOSE` flag
5. Test your changes on sample data

### Examples of pattern modifications:

**Example 1: Add a new date format (e.g., ISO format YYYY-MM-DD):**
```python
"Date": r"""
    \b(?:
        \d{1,2}\s*[\-/.]\s*\d{1,2}\s*[\-/.]\s*\d{2,4}|   # existing formats
        \d{4}\s*[\-/.]\s*\d{1,2}\s*[\-/.]\s*\d{1,2}|     # existing formats
        \d{4}-\d{2}-\d{2}                                 # NEW: ISO format
    )\b
""",
```

**Example 2: Add a completely new pattern (e.g., passport numbers):**
```python
"Passport": r"\b[A-Z]{2}\d{6,7}\b",  # Format: AB1234567
```

### Tips:

- Use online regex testers (regex101.com) to develop and test patterns
- Start specific, then broaden if recall is too low
- The `re.VERBOSE` flag allows multi-line patterns with comments
- Patterns are processed in order, so place more specific patterns before general ones

---

## How to Edit the Lists

The List Anonymizer uses an Excel file (`src/anonymizer/input_files/ListClassifier Basic.xlsx`, bundled as package-data) to load word lists for matching. The file contains multiple sheets, each representing a different category.

### Current lists include:

- First Name: Common first names
- Last Name: Common surnames
- Address: Street names and locations
- Nationalities: All nationalities in Dutch and English
- Organisation: Names of organisations (just a few examples in the Basic file, to be filled by users if desired)

### Adding a new list:

1. Duplicate `ListClassifier Basic.xlsx` to maintain your own version of the blacklists and change the name
2. Create a new sheet with your desired category name (e.g., "Company")
3. Add a column header "List" in cell A1
4. (Optional) Add a column header "Case Sensitive" in cell B1
5. Fill column A with the words/phrases to detect (one per row)
6. If using case sensitivity, add 1 (true) or 0 (false) in column B for each entry
7. Save the file
8. Pass the new ListClassifier file to the script (see other instructions), which will automatically load the new sheet and create a corresponding tag (e.g., `<Company>`)

### Changing an existing list:

1. Open your ListClassifier file
2. Navigate to the sheet you want to modify (e.g., "Address")
3. Add, remove, or edit entries in column A
4. Adjust case sensitivity in column B if needed
5. Save the file

### Case sensitivity:

- Add a "Case Sensitive" column (column B) with values 0 or 1
- 0 (or blank): Case-insensitive matching
- 1: Case-sensitive matching
- For multi-word entries with "tussenvoegsels" (van, der, de, etc.), these connecting words are always case-insensitive

**Note**: First Name and Last Name sheets are automatically combined into a single "Name" tag to improve detection of full names.

---

## How to Configure NER

The NER (Named Entity Recognition) component uses the GLiNER model to detect names and addresses contextually. Configuration is done through variables in `anonymizer.py`.

### Confidence Levels

The `NER_CONFIDENCE_DICT` dictionary sets minimum confidence thresholds for each entity type:

```python
NER_CONFIDENCE_DICT = {
    "Name": 0.3,           # 30% confidence threshold for names
    "Address": 0.3,        # 30% confidence threshold for addresses
    "Organization": 0.84   # 84% confidence threshold for organisations
}
```

- Lower values (0.1-0.3): Higher recall, may include false positives
- Medium values (0.4-0.6): Balanced approach
- Higher values (0.7-0.9): Higher precision, may miss some entities

### Tags

The NER model is configured to detect specific entity types. The labels are defined in the `anonymize` method:

```python
labels = ["naam", "name", "adres", "address", "organization", "organisatie"]
```

The script uses both Dutch and English labels for better recall. These are first mapped to standardized English tags:
- "naam"/"name" → `<Name>` or `<[Name]>`
- "adres"/"address" → `<Address>` or `<[Address]>`

These tags are all translated into a specified language using the json-file in src/anonymizer/config/tag_translations.json. Add new languages and/or tags here if you want them translated.

### Supported entity types by GLiNER model

The underlying model (E3-JSI/gliner-multi-pii-domains-v1) supports many entity types. To add more, modify the labels list:

```python
labels = ["naam", "name", "adres", "address", "email", "phone", "organization"]
```

### Other NER Configuration

- **Model selection**: Change the model by modifying the `model_name` parameter
- **Whitelists**: Edit `WEAK_NER_WHITELIST` and `STRONG_NER_WHITELIST` (see Whitelists section)
- **Tag format**: The `DISTINCT_TAGS` parameter controls tag format

---

## Steps to Generalize to New Organisation

This script was developed for data of the city of Rotterdam and later adapted for Utrecht. To use it for a new institution or municipality, follow these steps:

### 1. Review and adjust Regex patterns

- Check if ID number formats match your institution's systems
- Common patterns like dates, phones, and emails usually work universally
- Look especially at patterns in `ID_Number` that may be Rotterdam/Utrecht-specific
- Example: If your municipality uses different case ID formats, update the regex in `TAGGED_PATTERNS`:
```python
from anonymizer import anonymizer
anonymizer.TAGGED_PATTERNS["ID_Number"] = "updated_regex"
CA = anonymizer.CombinedAnonymizer()
# Etc.
```

### 2. Update neighborhood/area names (Strong Whitelist NER)

- Open your Whitelist file and navigate to the "NER" sheet
- In the "Strong" column, replace Rotterdam/Utrecht neighborhoods with other prefered area names
- This prevents the NER model from masking area names as addresses
- Save the file

### 3. Update the address list

- Open your ListClassifier file
- Navigate to the "Address" sheet
- Replace the street names with streets from your city, province, etc.
- Tip: You can use the helper module `anonymizer.helpers.streetnames` for Dutch street names.

### 4. Update other location-specific references

- Open your Whitelist file and check both "NER" and "List" sheets
- Add your organisation name to prevent it from being masked
- Update or remove other organisation names depending on your needs

### 5. Adjust the First Name and Last Name lists (optional)

- The provided lists are fairly universal for Dutch names
- If your municipality has specific demographic characteristics, consider adding those
- Update your ListClassifier sheets: "First Name" and "Last Name"

### 6. Review and test

- Run the script on a small sample of your data
- Manually review the output to check for over-masking or under-masking
- Adjust confidence thresholds, whitelists, and patterns as needed
- Create a test set and evaluate performance (see Evaluation Scores section)

---

## Evaluation Scores

The performance of the anonymization script is measured using standard information retrieval metrics. These scores are calculated by comparing the script's output against human-evaluated test sets.

### Key Metrics

**Recall:**
Measures the proportion of actual PII that the script successfully detected and masked.

Formula: **Recall = TP / (TP + FN)**

Where:
- TP (True Positives): PII correctly identified and masked
- FN (False Negatives): PII that was missed (not masked)

A recall of 0.95 means the script catches 95% of all PII in the text.

**Precision:**
Measures the proportion of masked items that were actually PII (not false alarms).

Formula: **Precision = TP / (TP + FP)**

Where:
- TP (True Positives): PII correctly identified and masked
- FP (False Positives): Non-PII incorrectly masked

A precision of 0.95 means 95% of masked items were truly PII.

**F-Score (F3):**
The F3-score is a weighted harmonic mean that prioritizes recall over precision. This is important for anonymization where missing PII (false negatives) is more critical than over-masking (false positives).

Formula: **F3 = (1 + β²) × (Precision × Recall) / (β² × Precision + Recall)**

Where β = 3, giving three times more weight to recall than precision.

### Confusion Matrix Terms

- **TP (True Positive)**: Script correctly masked PII
- **TN (True Negative)**: Script correctly left non-PII unmasked
- **FP (False Positive)**: Script incorrectly masked non-PII
- **FN (False Negative)**: Script failed to mask actual PII

### Performance Scores

In testing on data from Gemeente Rotterdam, the script achieved:
- **Recall**: 93%
- **Precision**: 92%
- **F3-score**: 93%

**Disclaimer:**
- These scores differ over different data sources
- These scores only summarize the performance; script performance is more nuanced. Please thoroughly test the script before deployment.

### How scores are calculated

1. Create a test set using `sample_testset.py` or the `processing_and_testing.ipynb` notebook
2. Run the anonymization script on the test set
3. Human evaluators review each masked item and classify as TP, FP, TN, or FN
4. Calculate metrics using formulas above or with the helper script `anonymizer.helpers.scoring`
5. Results are compiled in Excel for analysis

The developed script performs better than the previously used commercial solution, with improved recall and comparable precision across different types of PII, while maintaining context by providing text for masked items.

---

# [🇳🇱 Nederlandse versie](#dutch-version)

---

<a name="dutch-version"></a>

# Anonimiseringsscript – Gemeente Rotterdam

Dit model is ontwikkeld door de gemeente Rotterdam. Auteursrechten rusten geheel bij de gemeente Rotterdam.

Deze repository is de gepubliceerde versie van het anonimiseringsscript, afgeleid van het origineel dat is ontwikkeld door de gemeente Rotterdam, en uitgegeven onder de EUPL v1.2. Het voegt uitsluitend pre-publicatie hardening toe; zie [CHANGELOG.md](CHANGELOG.md) voor de wijzigingen.

> **Privacy-disclaimer.** Dit script anonimiseert tekst, maar het resultaat is niet gegarandeerd volledig en hangt mede af van de aangeboden informatie: er kan herleidbare informatie achterblijven. Of aanvullende controle nodig is, hangt af van de eisen die de toepassing stelt. Die afweging ligt bij de gebruikende organisatie.

## Inhoudsopgave

- [Snelstart](#snelstart)
  - [Installatie](#installatie)
  - [Snelle gebruiksvoorbeelden](#snelle-gebruiksvoorbeelden)
  - [Overzicht van bestanden](#overzicht-van-bestanden)
- [Wat doet het script](#wat-doet-het-script)
- [Waarom is dit script ontwikkeld](#waarom-is-dit-script-ontwikkeld)
- [Het script uitvoeren](#het-script-uitvoeren)
- [Hoe werkt het script](#hoe-werkt-het-script)
- [Whitelists: Weak en Strong](#whitelists-weak-en-strong)
- [Regexpatronen aanpassen](#regexpatronen-aanpassen)
- [Lijsten aanpassen](#lijsten-aanpassen)
- [NER configureren](#ner-configureren)
- [Generaliseren naar nieuwe organisatie](#generaliseren-naar-nieuwe-organisatie)
- [Evaluatiescores](#evaluatiescores)

---

## Snelstart

### Installatie

> **Vereist Python 3.10 of hoger.**

1. Clone de repository en navigeer naar de map.
2. Maak een virtual environment aan:
   ```bash
   python -m venv .venv
   ```
3. Activeer de virtual environment:
   - **Windows:** `.venv\Scripts\activate`
   - **Mac/Linux:** `source .venv/bin/activate`
4. Installeer de module:
   ```bash
   pip install git+https://github.com/MinBZK/maskeringsscript.git
   ```
   Of:
   ```bash
   pip install .
   ```
5. *(Optioneel)* Download het GLiNER‑model lokaal:
   ```bash
   git clone https://huggingface.co/E3-JSI/gliner-multi-pii-domains-v1
   ```

---

### Snelle gebruiksvoorbeelden

**CLI:**
```bash
python -m anonymizer raw_data/Sample_Rotterdam.xlsx results/Sample_Rotterdam_output.xlsx --text-column Toelichting_unmasked --masked-text-column Toelichting_masked
```

**Maak een sample‑testset:**
```bash
python -m anonymizer.helpers.sample_testset raw_data/Sample_Rotterdam.xlsx results/Sample_Rotterdam_output.xlsx --sample-size 400 --seed 42
```

**Jupyter Notebook:**

- Open `tests/processing_and_testing.ipynb`
- Voer alle cellen uit

---

### Overzicht van bestanden

- **src/anonymizer/anonymizer.py**  
  Hoofdimplementatie met `RegexAnonymizer`, `ListAnonymizer`, `NERAnonymizer`, en `CombinedAnonymizer`.

- **src/anonymizer/input_files/ListClassifier Basic.xlsx**  
  Woordenlijsten voor de ListAnonymizer. Meegebundeld als package-data, dus ook na `pip install` vindbaar.

- **src/anonymizer/input_files/Whitelist Basic.xlsx**  
  Bestaat uit twee sheets:
  - "NER": *Weak* en *Strong*
  - "List": whitelist voor Lijst‑Anonymizer

- **src/anonymizer/helpers**  
  Bevat hulpscripts zoals:
  - `sample_testset`
  - `kvk_preprocessing`
  - `streetnames`
  - `scoring`

- **tests/processing_and_testing.ipynb**  
  Voorbeeldpipeline voor laden → schoonmaken → maskeren → exporteren.

---

## Wat doet het script

Het script maskeert automatisch vrijetekst door persoonsgevoelige informatie (PII) te detecteren en te vervangen met tags zoals `<Naam>`, `<BSN>`, `<Telefoon>`.

Gedetecteerde categorieën o.a.:

- Persoonsidentificatie (BSN, BTW, KVK)
- Contactinfo (telefoon, e-mail, URLs, IBAN)
- Financiële data
- Datums en leeftijden
- Adressen, kentekens, IP-adressen
- Administratieve nummers
- Getallen (Nederlands formaat)

---

## Waarom is dit script ontwikkeld

Rotterdam gebruikte een niet‑transparant extern script zonder broncode.  
Doelen van de nieuwe aanpak:

- Transparantie  
- Deelbaar met andere overheden  
- Hoge prestaties  
- Aanpasbaarheid via lijsten en configuratie  
- Gebruik van moderne technieken (regex + lijsten + NER)

---

## Het script uitvoeren

### 1. CLI

```bash
python -m anonymizer input.xlsx output_masked.xlsx --text-column Toelichting_unmasked
```

### 2. Python

```python
from anonymizer import anonymizer
import pandas as pd

anonymizer.LIST_PATH = "Path/to/blacklist.xlsx"
anonymizer.WHITELIST_PATH = "Path/to/whitelist.xlsx"

df = pd.read_excel("input.xlsx")
an = anonymizer.CombinedAnonymizer()
df["masked_text"] = df["original_text"].map(an)
df.to_excel("output.xlsx", index=False)
```

### 3. Notebook

Gebruik `tests/processing_and_testing.ipynb`.

---

## Hoe werkt het script

De pipeline werkt in drie stappen:

### 1. Regex Anonymizer
Detecteert vaste patronen zoals datums, geldbedragen, e‑mails, postcodes, BSN/IBAN/KVK, telefoons, leeftijden, IP‑adressen, etc.  
Alle patronen staan in `TAGGED_PATTERNS`.

---

### 2. List Anonymizer
Gebruikt `ListClassifier Basic.xlsx` om o.a. te detecteren:

- Voor- en achternamen
- Straatnamen
- Nationaliteiten
- Organisaties

Functies:

- Fuzzy matching via SymSpell
- Multi‑word matching
- Whitelists
- Initialenherkenning
- Huisnummer‑herkenning
- Merging van meerdere tags

---

### 3. NER Anonymizer
Gebruikt GLiNER voor contextuele detectie van:

- Namen
- Adressen

Werkt met confidence thresholds en (weak/strong) whitelists.  
Voert post‑processing uit voor initialen en huisnummers.

---

### CombinedAnonymizer

Volgorde: **Regex → Lijst → NER**  
Dit verhoogt recall en behoudt precision.

---

## Whitelists: Weak en Strong

### Weak whitelist
Exacte match, o.a.:

- "Mevrouw", "Meneer"
- Steden
- Algemene termen

### Strong whitelist
Substring match, o.a.:

- Familierelaties
- Functietitels
- Wijknamen
- Adresgerelateerde woorden

Beheer via `Whitelist Basic.xlsx`.

---

## Regexpatronen aanpassen

Patronen staan in `TAGGED_PATTERNS` in `anonymizer.py`.

Aanpassen:

1. Open `anonymizer.py`
2. Zoek naar `TAGGED_PATTERNS`
3. Wijzig regex
4. Test met sampledata

---

## Lijsten aanpassen

Alle lijsten staan in `ListClassifier Basic.xlsx`.

### Nieuwe lijst toevoegen

1. Nieuwe sheet maken  
2. Kolom "List" toevoegen  
3. *(Optioneel)* Kolom "Case Sensitive"  
4. Script genereert automatisch een tag

### Bestaande lijst wijzigen

- Bewerk de sheet
- Opslaan
- Script laadt het automatisch in

---

## NER configureren

In `anonymizer.py`:

- `NER_CONFIDENCE_DICT`: thresholds
- `labels`: type entiteiten
- Whitelists
- Taalopties via `tag_translations.json`

---

## Generaliseren naar nieuwe organisatie

1. Regex‑patronen nalopen
2. Wijknamen (strong whitelist) aanpassen
3. Straatnamenlijst vervangen of uitbreiden
4. Organisatienamen bijwerken
5. Namenlijsten uitbreiden indien nodig
6. Testen, evalueren en thresholds bijstellen

---

## Evaluatiescores

### Gebruikte metrics

- **Recall** – hoeveel PII correct gemaskeerd
- **Precision** – hoeveel gemaskeerde items echt PII waren
- **F3‑score** – recall 3× belangrijker dan precision

### Resultaten Rotterdam

- **Recall:** 93%
- **Precision:** 92%
- **F3:** 93%

Let op: prestaties verschillen per dataset — altijd eerst testen.

### Hoe berekend

1. Testset maken (`sample_testset.py` / notebook)
2. Anonimiseren
3. Handmatige evaluatie (TP/FP/FN/TN)
4. Berekenen via `anonymizer.helpers.scoring`
5. Analyse in Excel