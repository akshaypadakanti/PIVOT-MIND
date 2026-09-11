"""
Agent 2: Profiler
Schema and statistical summary generator that constructs a low-token representation
of tabular datasets for efficient LLM context consumption.
Integrates SemanticClassifier to strictly enforce Top 1% Senior Data Analyst domain rules.
"""
from __future__ import annotations

from typing import Any
import numpy as np
import pandas as pd

from .semantic_classifier import SemanticClassifier


class DatasetProfiler:
    """
    Extracts schema metadata, statistical moments, value distributions, semantic classifications,
    and sample records from a pandas DataFrame.
    """

    def __init__(self, df: pd.DataFrame, dataset_name: str = "Dataset"):
        self.df = df
        self.dataset_name = dataset_name
        self.classifier = SemanticClassifier(df)

    def generate_profile(self) -> dict[str, Any]:
        """Generates comprehensive structured profile metadata with semantic classifications."""
        if self.df.empty:
            return {
                "dataset_name": self.dataset_name,
                "shape": (0, 0),
                "columns": [],
                "sample_rows": [],
                "semantic_schema": {"IDENTIFIER": [], "CATEGORICAL": [], "QUANTITATIVE": [], "DATETIME": []},
            }

        total_rows, total_cols = self.df.shape
        columns_profile = []
        semantic_schema = self.classifier.get_classified_schema()

        for col in self.df.columns:
            col_name = str(col)
            series = self.df[col]
            dtype_str = str(series.dtype)
            missing_cnt = int(series.isna().sum())
            unique_cnt = int(series.nunique(dropna=True))
            semantic_type = self.classifier.classify_column(col_name)

            col_data: dict[str, Any] = {
                "name": col_name,
                "dtype": dtype_str,
                "semantic_type": semantic_type,
                "missing": missing_cnt,
                "unique": unique_cnt,
            }

            if semantic_type == "QUANTITATIVE":
                valid = series.dropna()
                if not valid.empty:
                    col_data["stats"] = {
                        "min": float(round(valid.min(), 4)),
                        "max": float(round(valid.max(), 4)),
                        "mean": float(round(valid.mean(), 4)),
                        "median": float(round(valid.median(), 4)),
                        "std": float(round(valid.std(), 4)) if len(valid) > 1 else 0.0,
                    }
            elif semantic_type in ["CATEGORICAL", "IDENTIFIER"]:
                valid = series.dropna()
                if not valid.empty:
                    top_freq = valid.value_counts().head(4).to_dict()
                    col_data["top_values"] = {str(k): int(v) for k, v in top_freq.items()}

            columns_profile.append(col_data)

        # Sample rows (first 3 rows)
        sample_df = self.df.head(3).copy()
        sample_rows = sample_df.to_dict(orient="records")

        return {
            "dataset_name": self.dataset_name,
            "shape": (total_rows, total_cols),
            "columns": columns_profile,
            "sample_rows": sample_rows,
            "semantic_schema": semantic_schema,
        }

    def get_low_token_representation(self) -> str:
        """
        Creates a high-density, low-token text representation optimized for
        LLM system prompts with strict semantic domain rules.
        """
        profile = self.generate_profile()
        rows, cols = profile["shape"]
        
        if rows == 0:
            return f"Dataset: {self.dataset_name} (EMPTY: 0 rows, 0 columns)"

        lines = [
            f"DATASET: {self.dataset_name} | Shape: {rows} rows x {cols} cols",
            "SEMANTIC SCHEMA SUMMARY:",
        ]

        sem = profile["semantic_schema"]
        lines.append(f"  - Quantitative Measures: {sem['QUANTITATIVE'] or 'None'}")
        lines.append(f"  - Categorical Dimensions: {sem['CATEGORICAL'] or 'None'}")
        lines.append(f"  - Identifiers / Primary Keys: {sem['IDENTIFIER'] or 'None'} (CRITICAL: DO NOT AGGREGATE OR PLOT ON Y-AXIS)")
        lines.append(f"  - Timestamps: {sem['DATETIME'] or 'None'}")
        lines.append("\nCOLUMNS OVERVIEW:")

        for col in profile["columns"]:
            name = col["name"]
            dtype = col["dtype"]
            stype = col["semantic_type"]
            missing = col["missing"]
            unique = col["unique"]
            
            line = f"- `{name}` ({dtype}) [SEMANTIC: {stype}] | Missing: {missing} | Unique: {unique}"

            if stype == "QUANTITATIVE" and "stats" in col:
                st = col["stats"]
                line += f" | Stats: min={st['min']}, max={st['max']}, mean={st['mean']}, med={st['median']}, std={st['std']}"
            elif "top_values" in col:
                top_str = ", ".join([f"'{k}':{v}" for k, v in col["top_values"].items()])
                line += f" | TopVals: [{top_str}]"
            
            lines.append(line)

        # Compact sample preview
        lines.append("\nSAMPLE PREVIEW (First 2 Rows):")
        sample_rows = profile["sample_rows"][:2]
        for idx, row in enumerate(sample_rows, 1):
            row_str = ", ".join([f"{k}={v}" for k, v in row.items()])
            lines.append(f"Row {idx}: {{{row_str}}}")

        return "\n".join(lines)
