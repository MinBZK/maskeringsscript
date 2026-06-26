#!/usr/bin/env python3
"""
sample_testset.py - create a 400-row test sample per “Bron Groepering”

Dit model is ontwikkeld in samenwerking tussen de gemeente Rotterdam en Kyden. Auteursrechten rusten geheel bij de gemeente Rotterdam.

This model was developed in cooperation between the city of Rotterdam and Kyden. Copyright City of Rotterdam.

Licence: EUPL

This script selects a reproducible random sample of rows from each
source group, anonymises the free-text field with RegexAnonymizer,
and saves the result in the expected testing format.

Usage (CLI)
-------
$ python -m anonymizer.helpers.sample_testset raw_data/Sample_Rotterdam.xlsx results/Sample_Rotterdam_output.xlsx [options]

Options
-------
  --text-column   Column containing free text             (default: Toelichting_unmasked)
  --group-column  Column defining the source / grouping   (default: Bron_Groepering)
  --sample-size   Rows per group                          (default: 400)
  --seed          Random-state seed for reproducibility   (default: 42)
  --blacklist-path Path to blacklist file                 (default: bundled ListClassifier Basic.xlsx)
  --whitelist-path Path to whitelist file                 (default: bundled Whitelist Basic.xlsx)
-------
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import List

import pandas as pd
import numpy as np

from anonymizer import anonymizer

LOGGER = logging.getLogger(__name__)
logging.basicConfig(format="[%(levelname)s] %(message)s", level=logging.INFO)


def sample_per_group(
    df: pd.DataFrame,
    group_col: str,
    n: int,
    seed: int,
) -> pd.DataFrame:
    """
    Return a DataFrame with *n* random rows from each unique value
    in *group_col*.  If a group has fewer than *n* rows, all rows are taken
    and a warning is emitted.
    """
    parts: List[pd.DataFrame] = []
    rng = np.random.default_rng(seed)  # reproducible per group

    for value, grp in df.groupby(group_col, sort=False):
        if len(grp) < n:
            LOGGER.warning(
                "Group '%s' has only %d rows (< %d); taking all.",
                value, len(grp), n,
            )
            parts.append(grp)
        else:
            parts.append(grp.sample(n=n, random_state=rng))

    return pd.concat(parts, ignore_index=True)


def build_testset(
    df: pd.DataFrame,
    text_col: str,
    group_col: str,
    anonymizer: anonymizer.CombinedAnonymizer,
) -> pd.DataFrame:
    """
    Construct the five testing columns in the correct order.
    """
    return pd.DataFrame(
        {
            group_col: df[group_col],
            "Originele tekst": df[text_col],
            "Geanonimiseerde tekst": df[text_col].map(anonymizer),
            "# Gemiste maskeringen": "",        # tester will fill number of missed patterns
            "# Onterecht gemaskeerd": "",       # tester will fill number of missed patterns
            "Comment": "",                      # tester will optionally write comments
        }
    )


def main() -> None:  # pragma: no cover
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="original .xlsx file")
    parser.add_argument("output", type=Path, help="destination .xlsx file")
    parser.add_argument("--text-column", default="Toelichting_unmasked")
    parser.add_argument("--group-column", default="Bron_Groepering")
    parser.add_argument("--sample-size", type=int, default=400)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--blacklist-path", type=Path, default=anonymizer.LIST_PATH,
                        help="Path to blacklist file (default: bundled 'ListClassifier Basic.xlsx')")
    parser.add_argument("--whitelist-path", type=Path, default=anonymizer.WHITELIST_PATH,
                        help="Path to whitelist files (default: bundled 'Whitelist Basic.xlsx')")
    args = parser.parse_args()

    LOGGER.info("Loading %s ...", args.input)
    df = pd.read_excel(args.input, dtype=str, engine="openpyxl")

    LOGGER.info(
        "Sampling %d rows per '%s' (seed=%d) ...",
        args.sample_size, args.group_column, args.seed,
    )
    sampled = sample_per_group(
        df,
        group_col=args.group_column,
        n=args.sample_size,
        seed=args.seed,
    )

    LOGGER.info("Running anonymisation ...")
    anonymizer.LIST_PATH = args.blacklist_path
    anonymizer.WHITELIST_PATH = args.whitelist_path
    CA = anonymizer.CombinedAnonymizer()
    testset = build_testset(sampled, args.text_column, args.group_column, CA)

    LOGGER.info("Writing test set → %s", args.output)
    testset.to_excel(args.output, index=False, engine="openpyxl")

    LOGGER.info("Done. %d rows written.", len(testset))


if __name__ == "__main__":
    main()
