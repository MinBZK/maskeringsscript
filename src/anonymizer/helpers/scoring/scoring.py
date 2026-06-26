import pandas as pd
import re
import typing
import logging
import argparse
from pathlib import Path


"""
Script to score the output of the model.
Takes as input a DataFrame with the processed texts, amount of false positives and amount of false negatives per row.
Output is calculated precision, recall and F-Beta score.

Usage (CLI)
-------
python -m anonymizer.helpers.scoring results/Sample_Rotterdam_output.xlsx --text-col "Geanonimiseerde tekst" [Options]

Options
-------
  --text-col   Column name of masked texts             (default: Toelichting_masked)
  --fp-col     Column name with # of false positives   (default: "# Onterecht gemaskeerd")
  --fn-col     Column name with # of false negatives   (default: "# Gemiste maskeringen")

Usage (module)
-------
import pandas as pd
from anonymizer.helpers import scoring

filepath = 'masked_texts.xlsx'
df = pd.read_excel(filepath)
text_col = 'Toelichting_masked'
fp_col = '# Onterecht gemaskeerd'
fn_col = '# Gemiste maskeringen'
scores = scoring.score(df, text_col, fp_col, fn_col)
print(f"Precision: {scores['precision']:.2f}\nRecall: {scores['recall']:.2f}\nF-Beta Score: {scores['f_beta']:.2f}")
"""

LOGGER = logging.getLogger(__name__)
logging.basicConfig(format="[%(levelname)s] %(message)s", level=logging.INFO)

BETA = 3.0 # Weight of recall relative to precision for the F-Beta score, default is 3
TAG_RE = re.compile( # Regex to match different formats of masking tags
    r'<(?:'
    r'([a-zA-Z0-9_]+)'  # <Tag>
    r'|'
    r'\(([a-zA-Z0-9_]+)\)'  # <(Tag)>
    r'|'
    r'\[([a-zA-Z0-9_]+)\]'  # <[Tag]>
    r'|'
    r'\[([a-zA-Z0-9_]+),\s*C[-+]?\d+\.\d+\]'  # <[Tag, C0.86]>
    r')>'
)

def _sum_masked(text: str) -> int:
    # Returns the amount of found masking tags in a text
    found_tags = TAG_RE.findall(text)
    return (len(found_tags))

def score(df: pd.DataFrame, text_col: str, fp_col: str, fn_col: str) -> dict[str: float]:
    """
    Score output of the masking model, based on text column (to find total amount of tagged texts),
    column with amount of false positives and column with amount of false negatives.
    """
    try:
        fp = df[fp_col].sum() # False positives
    except KeyError:
        raise KeyError(f"False positives column {fp_col} not found in dataframe")
    try:
        fn = df[fn_col].sum() # False negatives
    except KeyError:
        raise KeyError(f"False negatives column {fn_col} not found in dataframe")
    
    amount_masked = df[text_col].apply(_sum_masked)
    tp = sum(amount_masked) - fp # True positives
    # Guard tegen deling door nul: bij niets-gemaskeerd (tp+fp==0) of geen
    # positieven (tp+fn==0) is de metriek ongedefinieerd -> 0.0 (conventie
    # sklearn zero_division=0), zodat de uitkomst altijd eindig blijft i.p.v. nan.
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f_beta_denom = BETA**2 * precision + recall
    f_beta = (1 + BETA**2) * ((precision * recall) / f_beta_denom) if f_beta_denom else 0.0

    return {
        'precision': precision,
        'recall': recall,
        'f_beta': f_beta
    }

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("filepath", type=Path, help="Tested Excel-file to be scored")
    parser.add_argument("--text-col", default="Toelichting_masked", help="Masked text column name")
    parser.add_argument("--fp-col", default="# Onterecht gemaskeerd")
    parser.add_argument("--fn-col", default="# Gemiste maskeringen")
    args = parser.parse_args()

    LOGGER.info("Loading %s ...", args.filepath)
    df = pd.read_excel(args.filepath)

    LOGGER.info("Calculating scores...")
    scores = score(df, args.text_col, args.fp_col, args.fn_col)

    LOGGER.info("Results:\n\n")
    LOGGER.info(f"Precision: {scores['precision']:.2f}\nRecall: {scores['recall']:.2f}\nF-Beta Score: {scores['f_beta']:.2f}")

if __name__ == "__main__":
    main()