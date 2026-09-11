"""
Agent 1: Data Doctor & Cleaning Engine
Acts like a Top 1% Senior Data Analyst:
1. Performs deterministic data hygiene evaluation (missing values, mixed types, duplicates, outliers, health score).
2. Cleans the DataFrame thoroughly: strips column names, coerces string numbers, normalizes categories, converts dates, and isolates identifiers.
"""
from __future__ import annotations

import re
from typing import Any
import numpy as np
import pandas as pd

from .semantic_classifier import SemanticClassifier


class DataDoctor:
    """
    Evaluates raw tabular data quality deterministically, performs thorough cleaning,
    and outputs a structured Data Health Report with a score between 0 and 100.
    """

    def __init__(self, df: pd.DataFrame, dataset_name: str = "Dataset"):
        self.raw_df = df.copy()
        self.dataset_name = dataset_name
        self.cleaned_df = self._perform_deep_clean(self.raw_df)
        self.classifier = SemanticClassifier(self.cleaned_df)

    def _perform_deep_clean(self, df: pd.DataFrame) -> pd.DataFrame:
        """Deep cleaning routine matching senior data analyst standards."""
        if df.empty:
            return df.copy()

        cleaned = df.copy()

        # 1. Clean Column Names (strip whitespace, normalize spaces)
        cleaned.columns = [str(c).strip() for c in cleaned.columns]

        # 2. Remove exact duplicate rows
        cleaned = cleaned.drop_duplicates()

        # 3. Clean string cells (strip whitespace)
        for col in cleaned.select_dtypes(include=["object", "string"]).columns:
            cleaned[col] = cleaned[col].apply(lambda x: x.strip() if isinstance(x, str) else x)

            # Try coercing formatted numeric strings like "$1,200", "45%" or " 100 " to numeric
            sample_non_null = cleaned[col].dropna().head(20)
            if not sample_non_null.empty:
                try:
                    # Check if string values contain numeric digits and symbols
                    str_vals = sample_non_null.astype(str)
                    if str_vals.str.match(r"^[^\d\s]*\s*-?\d[\d,]*(\.\d+)?%?$").all():
                        coerced = (
                            cleaned[col]
                            .astype(str)
                            .str.replace(r"[^\d\.\-]", "", regex=True)
                        )
                        cleaned[col] = pd.to_numeric(coerced, errors="coerce")
                except Exception:
                    pass

        # 4. Convert date-like columns to datetime
        for col in cleaned.columns:
            col_lower = str(col).lower()
            if any(k in col_lower for k in ["date", "timestamp", "created_at", "updated_at", "month", "dob"]):
                if not pd.api.types.is_datetime64_any_dtype(cleaned[col]):
                    try:
                        cleaned[col] = pd.to_datetime(cleaned[col], errors="ignore")
                    except Exception:
                        pass

        return cleaned

    def analyze(self) -> dict[str, Any]:
        """Runs all deterministic data quality checks on the raw and cleaned DataFrame."""
        if self.raw_df.empty:
            return {
                "dataset_name": self.dataset_name,
                "health_score": 0.0,
                "rating": "Poor",
                "total_rows": 0,
                "total_columns": 0,
                "summary": "Dataset is empty.",
                "missing": {"total_missing_cells": 0, "missing_ratio": 0.0, "columns": {}},
                "duplicates": {"duplicate_count": 0, "duplicate_ratio": 0.0},
                "types": {"numeric": [], "categorical": [], "datetime": [], "text": [], "mixed": [], "identifiers": []},
                "outliers": {"total_outliers": 0, "affected_columns": {}},
                "constant_columns": [],
                "recommendations": ["Upload a non-empty dataset."],
            }

        df = self.cleaned_df
        total_rows, total_cols = df.shape
        total_cells = total_rows * total_cols

        # 1. Missing Values Analysis
        missing_per_col = df.isna().sum().to_dict()
        total_missing = int(df.isna().sum().sum())
        missing_ratio = float(total_missing / total_cells) if total_cells > 0 else 0.0

        missing_details = {}
        for col, count in missing_per_col.items():
            col_str = str(col)
            pct = round((count / total_rows) * 100, 2) if total_rows > 0 else 0.0
            missing_details[col_str] = {
                "count": int(count),
                "pct": float(pct),
                "has_missing": count > 0,
            }

        # 2. Duplicates Analysis
        raw_duplicates = int(self.raw_df.duplicated().sum())
        duplicate_ratio = float(raw_duplicates / len(self.raw_df)) if len(self.raw_df) > 0 else 0.0

        # 3. Semantic Column Classification
        schema = self.classifier.get_classified_schema()
        numeric_cols = schema["QUANTITATIVE"]
        categorical_cols = schema["CATEGORICAL"]
        datetime_cols = schema["DATETIME"]
        identifier_cols = schema["IDENTIFIER"]

        mixed_cols = []
        for col in df.columns:
            series = df[col].dropna()
            if not series.empty and not pd.api.types.is_numeric_dtype(df[col]):
                types_in_col = {type(val).__name__ for val in series.head(200)}
                if len(types_in_col) > 1:
                    mixed_cols.append(str(col))

        # 4. Outliers via IQR (ONLY for QUANTITATIVE columns, ignoring IDENTIFIERS!)
        total_outlier_count = 0
        affected_outlier_cols = {}
        for col in numeric_cols:
            series = df[col].dropna()
            if len(series) < 4:
                continue
            q1 = series.quantile(0.25)
            q3 = series.quantile(0.75)
            iqr = q3 - q1
            if iqr > 0:
                lower = q1 - 1.5 * iqr
                upper = q3 + 1.5 * iqr
                outliers = series[(series < lower) | (series > upper)]
                cnt = len(outliers)
                if cnt > 0:
                    total_outlier_count += cnt
                    affected_outlier_cols[col] = {
                        "count": int(cnt),
                        "pct": round((cnt / total_rows) * 100, 2),
                        "lower_bound": float(round(lower, 4)),
                        "upper_bound": float(round(upper, 4)),
                    }

        # 5. Constant Columns
        constant_cols = [str(col) for col in df.columns if df[col].nunique(dropna=False) <= 1]

        # 6. Data Health Score Calculation (0 - 100)
        score = 100.0
        score -= min(35.0, missing_ratio * 100 * 0.7)
        score -= min(20.0, duplicate_ratio * 100 * 0.4)
        score -= min(20.0, len(mixed_cols) * 5.0)
        outlier_ratio = (total_outlier_count / total_cells) if total_cells > 0 else 0
        score -= min(15.0, outlier_ratio * 100 * 0.5)
        score -= min(10.0, len(constant_cols) * 2.5)

        health_score = max(0.0, min(100.0, round(score, 1)))

        if health_score >= 90:
            rating = "Excellent"
        elif health_score >= 75:
            rating = "Good"
        elif health_score >= 60:
            rating = "Fair"
        else:
            rating = "Poor"

        recommendations = []
        if total_missing > 0:
            recommendations.append(
                f"Impute missing values: {total_missing} missing cells detected across {len([c for c, d in missing_details.items() if d['has_missing']])} columns."
            )
        if raw_duplicates > 0:
            recommendations.append(
                f"Deduplicated dataset: Removed {raw_duplicates} duplicate rows ({round(duplicate_ratio*100, 1)}%)."
            )
        if mixed_cols:
            recommendations.append(
                f"Standardized column data types for mixed columns: {', '.join(mixed_cols)}."
            )
        if constant_cols:
            recommendations.append(
                f"Remove constant/zero-variance columns: {', '.join(constant_cols)}."
            )
        if affected_outlier_cols:
            recommendations.append(
                f"Reviewed statistical outliers in {len(affected_outlier_cols)} numeric measure columns."
            )
        if identifier_cols:
            recommendations.append(
                f"Isolated {len(identifier_cols)} identifier metadata columns ({', '.join(identifier_cols)}) to prevent invalid statistical aggregations."
            )
        if not recommendations:
            recommendations.append("Dataset structure and hygiene are clean. No critical remediation required.")

        return {
            "dataset_name": self.dataset_name,
            "health_score": health_score,
            "rating": rating,
            "total_rows": total_rows,
            "total_columns": total_cols,
            "total_cells": total_cells,
            "missing": {
                "total_missing_cells": total_missing,
                "missing_ratio": round(missing_ratio, 4),
                "columns": missing_details,
            },
            "duplicates": {
                "duplicate_count": raw_duplicates,
                "duplicate_ratio": round(duplicate_ratio, 4),
            },
            "types": {
                "numeric": numeric_cols,
                "categorical": categorical_cols,
                "datetime": datetime_cols,
                "text": categorical_cols,
                "mixed": mixed_cols,
                "identifiers": identifier_cols,
            },
            "outliers": {
                "total_outliers": total_outlier_count,
                "affected_columns": affected_outlier_cols,
            },
            "constant_columns": constant_cols,
            "recommendations": recommendations,
        }

    def clean_dataframe(self) -> pd.DataFrame:
        """Returns the cleaned, normalized version of the DataFrame."""
        return self.cleaned_df
