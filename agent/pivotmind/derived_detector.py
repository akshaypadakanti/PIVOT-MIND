"""
PivotMind Derived Column Detector
Identifies derived, binned, grouped, or partitioned columns (e.g., Age -> AgeGroup)
to prevent uninsightful self-referential hypotheses (e.g. "How does Age vary across AgeGroup?").
"""
from __future__ import annotations

import re
import pandas as pd


class DerivedColumnDetector:
    """
    Scans DataFrame columns to identify derived column pairs (source_column, derived_column).
    """

    DERIVED_SUFFIXES = {
        "group", "slab", "bucket", "bin", "binned", "category", "cat",
        "bracket", "range", "tier", "level", "segment", "cohort"
    }

    def __init__(self, df: pd.DataFrame):
        self.df = df

    def detect_derived_pairs(self) -> set[tuple[str, str]]:
        """
        Returns a set of tuples (source_col, derived_col).
        """
        if self.df is None or self.df.empty:
            return set()

        pairs: set[tuple[str, str]] = set()
        cols = list(self.df.columns)

        for col_a in cols:
            a_str = str(col_a)
            a_clean = a_str.lower().strip()

            for col_b in cols:
                if col_a == col_b:
                    continue

                b_str = str(col_b)
                b_clean = b_str.lower().strip()

                # Check 1: Name-based derivation (e.g. Age and AgeGroup / Age_binned)
                if self._is_name_derived(a_clean, b_clean):
                    pairs.add((a_str, b_str))
                    continue

                # Check 2: Value-level partition derivation
                # If col_a is numeric and col_b is string/categorical, check if col_b partitions col_a monotonically
                if pd.api.types.is_numeric_dtype(self.df[col_a]) and not pd.api.types.is_numeric_dtype(self.df[col_b]):
                    if self._is_value_derived(self.df[col_a], self.df[col_b]):
                        pairs.add((a_str, b_str))

        return pairs

    def _is_name_derived(self, source_clean: str, target_clean: str) -> bool:
        """Checks if target_clean is a derived name version of source_clean."""
        if not source_clean or not target_clean:
            return False

        # e.g., source = "age", target = "agegroup" or "age_group" or "age_binned"
        if target_clean.startswith(source_clean) and target_clean != source_clean:
            remainder = target_clean[len(source_clean):].strip("_- ")
            if remainder in self.DERIVED_SUFFIXES or any(s in remainder for s in self.DERIVED_SUFFIXES):
                return True

        # e.g., target = "group_age" or "age_range"
        for suffix in self.DERIVED_SUFFIXES:
            if target_clean == f"{source_clean}_{suffix}" or target_clean == f"{source_clean}{suffix}" or target_clean == f"{suffix}_{source_clean}":
                return True

        return False

    def _is_value_derived(self, numeric_series: pd.Series, cat_series: pd.Series) -> bool:
        """
        Returns True if cat_series defines non-overlapping numeric intervals for numeric_series.
        """
        valid = pd.DataFrame({"num": numeric_series, "cat": cat_series}).dropna()
        if valid.empty or valid["cat"].nunique() <= 1:
            return False

        # Group by cat and check if min/max numeric intervals are non-overlapping
        grp = valid.groupby("cat")["num"].agg(["min", "max", "count"])
        if len(grp) < 2:
            return False

        sorted_intervals = grp.sort_values("min")
        prev_max = None
        overlaps = False

        for _, row in sorted_intervals.iterrows():
            if prev_max is not None and row["min"] < prev_max:
                overlaps = True
                break
            prev_max = row["max"]

        # If intervals sorted by category have zero overlap and strict order, cat is derived from num!
        return not overlaps

    def is_derived_pair(self, col1: str, col2: str) -> bool:
        """Checks if col1 and col2 have a derived relationship in either direction."""
        pairs = self.detect_derived_pairs()
        return (col1, col2) in pairs or (col2, col1) in pairs
