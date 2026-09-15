"""
PivotMind Semantic Column Classifier
Acts like a Top 1% Senior Data Analyst to semantically classify dataset columns into:
- IDENTIFIER (Contact Number, Phone, ID, Roll No, SSN, Zip, Email, etc. - NEVER AGGREGATE OR PLOT ON Y-AXIS)
- CATEGORICAL (Department, Branch, Category, Region, Status, Gender, etc.)
- QUANTITATIVE (Sales, Revenue, Profit, Score, Marks, Age, Salary, Units, etc.)
- DATETIME (Date, Time, Timestamp, Year, Month, etc.)
"""
from __future__ import annotations

import re
from typing import Literal
import pandas as pd
import numpy as np

SemanticType = Literal["IDENTIFIER", "CATEGORICAL", "QUANTITATIVE", "DATETIME"]

IDENTIFIER_KEYWORDS = {
    "id", "identifier", "contact", "phone", "mobile", "cell", "roll", "ssn",
    "zip", "zipcode", "pin", "pincode", "email", "serial", "sr", "index",
    "aadhaar", "passport", "reg", "registration", "account_no", "acc_no",
    "card_no", "fax", "tel", "telephone", "customer_id", "user_id", "student_id",
    "unnamed", "unnamed: 0", "unnamed_0", "employeenumber", "employee_number",
    "employee_id", "emp_no", "emp_id", "seq", "sequence", "row_num", "row_id"
}

CATEGORICAL_KEYWORDS = {
    "dept", "department", "branch", "course", "stream", "major", "specialization",
    "gender", "sex", "status", "category", "region", "city", "state", "country",
    "role", "grade", "class", "tier", "segment", "level", "group", "type", "mode"
}

DATETIME_KEYWORDS = {
    "date", "time", "timestamp", "created_at", "updated_at", "month", "year", "day"
}


class SemanticClassifier:
    """
    Analyzes DataFrame columns using a deterministic-first semantic typing pipeline:
    RAW DATA -> Pandas Dtype Inspection -> Deterministic Base Type -> Refinement -> Final Semantic Type.
    """

    def __init__(self, df: pd.DataFrame):
        self.df = df

    def classify_column(self, col_name: str) -> SemanticType:
        """Determines the semantic type of a single column using deterministic rules."""
        col_str = str(col_name)
        name_clean = col_str.strip().lower()
        name_words = set(re.split(r"[_\s\-\.\/\\]+", name_clean))

        # Check explicit identifier keywords or patterns
        if name_clean.startswith("unnamed") or any(kw in name_clean for kw in IDENTIFIER_KEYWORDS) or bool(IDENTIFIER_KEYWORDS & name_words):
            return "IDENTIFIER"

        series = self.df[col_name].dropna()
        if series.empty:
            return "CATEGORICAL"

        total_rows = len(self.df)
        unique_cnt = series.nunique()

        # Step 1: Pandas Dtype Inspection & Deterministic Base Type
        if pd.api.types.is_datetime64_any_dtype(series):
            return "DATETIME"

        is_native_numeric = pd.api.types.is_numeric_dtype(series)

        # Infer base type for Object / String columns
        is_string_numeric = False
        is_string_date = False

        if not is_native_numeric and (pd.api.types.is_string_dtype(series) or pd.api.types.is_object_dtype(series)):
            # Test if numeric string values (e.g. "12.5", "100")
            numeric_parsed = pd.to_numeric(series.head(20), errors="coerce")
            if numeric_parsed.notna().sum() / len(series.head(20)) >= 0.8:
                is_string_numeric = True
            else:
                # Test if ISO / date string values (e.g. "2023-01-15")
                has_date_kw = any(k in name_clean for k in ["date", "timestamp", "created", "updated"])
                if has_date_kw:
                    date_parsed = pd.to_datetime(series.head(20), errors="coerce")
                    if date_parsed.notna().sum() / len(series.head(20)) >= 0.8:
                        is_string_date = True

        if is_string_date:
            return "DATETIME"

        # Step 2: Deterministic Guardrail for Numeric Columns
        # Numeric columns (native float64/int64 or string-numeric) MUST NOT become DATETIME
        # unless there is explicit deterministic evidence (calendar year [1900..2100] or Unix epoch > 1e9).
        if is_native_numeric or is_string_numeric:
            valid_num = series.dropna()
            if is_string_numeric:
                valid_num = pd.to_numeric(valid_num, errors="coerce").dropna()

            if not valid_num.empty:
                # Check calendar year integer (e.g., column named 'year' or 'birth_year' with values 1900..2100)
                is_year_col = (name_clean in {"year", "yr", "calendar_year", "birth_year"} or bool(name_words & {"year", "yr"}))
                if is_year_col and "education" not in name_clean and "tenure" not in name_clean and "working" not in name_clean:
                    if valid_num.min() >= 1900 and valid_num.max() <= 2100:
                        return "DATETIME"

                # Check integer Unix epoch timestamp (> 1e9)
                if valid_num.min() > 1e9 and valid_num.max() < 2e9 and (valid_num % 1 == 0).all():
                    return "DATETIME"

            # Check if integer sequence with high uniqueness (like IDs or phone numbers >= 7 digits)
            if unique_cnt > 0:
                sample_vals = valid_num.head(10).astype(str).tolist()
                is_long_num = any(len(re.sub(r"\D", "", val)) >= 7 for val in sample_vals if val != "nan")
                if is_long_num and unique_cnt / total_rows > 0.3:
                    return "IDENTIFIER"

                if unique_cnt == total_rows and total_rows > 10:
                    return "IDENTIFIER"

            # Low cardinality numeric (e.g. Rating 1-5, Grade 1-4)
            if unique_cnt <= 5 and total_rows > 20:
                return "CATEGORICAL"

            # By default, all numeric columns ARE QUANTITATIVE
            return "QUANTITATIVE"

        # Step 3: Text / String columns
        if any(kw in name_clean for kw in CATEGORICAL_KEYWORDS):
            return "CATEGORICAL"

        if unique_cnt / total_rows > 0.8 and total_rows > 10:
            if "@" in str(series.iloc[0]) or "name" in name_clean:
                return "IDENTIFIER"

        return "CATEGORICAL"

    def get_classified_schema(self) -> dict[str, list[str]]:
        """Returns lists of column names grouped by their semantic classification."""
        schema: dict[str, list[str]] = {
            "IDENTIFIER": [],
            "CATEGORICAL": [],
            "QUANTITATIVE": [],
            "DATETIME": [],
        }
        for col in self.df.columns:
            stype = self.classify_column(str(col))
            schema[stype].append(str(col))
        return schema
