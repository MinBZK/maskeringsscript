import pandas as pd
import typing
import argparse
import logging
from pathlib import Path

"""
Script to extract street names of a certain city, to be used in a blacklist.
This uses the format of the frequently updated files available at: https://github.com/LJPc-solutions/Nederlandse-adressen-en-postcodes

Usage (CLI)
-------
python -m anonymizer.helpers.streetnames Zuid-Holland.csv "src/anonymizer/input_files/ListClassifier Basic.xlsx" [Options]

Options
-------
  --blacklist-sheetname   Name of Excel-sheet with address-blacklist   (default: Address)
  --filter-col            Column to filter on                          (default: gemeente)
  --filter-value          Value to filter the filter column on         (default: Rotterdam)
  --output-path           Output path to updated blacklist             (default: results/updated_streetnames.xlsx)

Usage (module)
-------
import pandas as pd
from anonymizer.helpers import streetnames

df_zuidholland = pd.read_csv('Straatnamen/Zuid-Holland.csv', sep=';')
current_streetnames = pd.read_excel("input_files/ListClassifier Rotterdam.xlsx", sheet_name="Address")
df_rotterdam = streetnames.extract_streetnames(df_zuidholland)
df_updated = streetnames.update_streetnames(old=current_streetnames, new=df_rotterdam)
df_updated.to_excel("Straatnamen/Updated_streetnames.xlsx", sheet_name="Address", index=False)
"""

LOGGER = logging.getLogger(__name__)
logging.basicConfig(format="[%(levelname)s] %(message)s", level=logging.INFO)

def extract_streetnames(input: pd.DataFrame, filter_col: str = "gemeente", filter_value: str = "Rotterdam") -> pd.Series:
    output = input[input[filter_col] == filter_value].copy()
    output_streets = output["straat"].drop_duplicates()
    return output_streets

def update_streetnames(old: pd.DataFrame, new: pd.DataFrame, old_streetcol: str = "List") -> pd.DataFrame:
    """Add new street names to the existing file, while keeping case sensitivity settings for already known street names."""
    new_streets = new[~new.isin(old[old_streetcol])]
    new_rows = pd.DataFrame({old_streetcol: new_streets, 'Case Sensitive': 0}) # By default, make new street names case insensitive
    updated = pd.concat([old, new_rows], ignore_index=True).sort_values(by=old_streetcol, ascending=True)
    return updated

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("new_file", type=Path, help="New csv-file with updated street names")
    parser.add_argument("current_blacklist", type=Path, help="File with current blacklists (e.g. src/anonymizer/input_files/ListClassifier Basic.xlsx)")
    parser.add_argument("--blacklist-sheetname", default="Address", help="Name of Excel-sheet with address-blacklist")
    parser.add_argument("--filter-col", default="gemeente", help="Column to filter on")
    parser.add_argument("--filter-value", default="Rotterdam", help="Value to filter the filter column on")
    parser.add_argument("--output-path", type=Path, default="results/updated_streetnames.xlsx", help="Output path to updated blacklist")
    args = parser.parse_args()

    LOGGER.info("Loading %s ...", args.new_file)
    new_streetnames = pd.read_csv(args.new_file, sep=';')

    LOGGER.info("Loading %s, sheet %s ...", args.current_blacklist,args.blacklist_sheetname)
    current_streetnames = pd.read_excel(args.current_blacklist, sheet_name=args.blacklist_sheetname)

    LOGGER.info("Extracting and updating streetnames, filtered by '%s' == '%s' ...", args.filter_col, args.filter_value)
    df_filtered = extract_streetnames(new_streetnames, filter_col=args.filter_col, filter_value=args.filter_value)
    df_updated = update_streetnames(old=current_streetnames, new=df_filtered)

    LOGGER.info("Done. Wrote new list to file %s", args.output_path)
    df_updated.to_excel(args.output_path, sheet_name=args.blacklist_sheetname, index=False)

if __name__ == "__main__":
    main()