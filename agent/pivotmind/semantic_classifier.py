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
    Analyzes DataFrame columns and classifies them semantically to prevent
    absurd statistical operations (e.g. taking the mean or boxplot of phone numbers or index columns).
    """

    def __init__(self, df: pd.DataFrame):
        self.df = df

    def classify_column(self, col_name: str) -> SemanticType:
        """Determines the semantic type of a single column."""
        name_clean = str(col_name).strip().lower()
        name_words = set(re.split(r"[_\s\-\.\/\\]+", name_clean))

        # Check explicit identifier keywords or patterns (e.g. unnamed, employee_number)
        if name_clean.startswith("unnamed") or any(kw in name_clean for kw in IDENTIFIER_KEYWORDS) or bool(IDENTIFIER_KEYWORDS & name_words):
            return "IDENTIFIER"

        series = self.df[col_name].dropna()
        if series.empty:
            return "CATEGORICAL"

        total_rows = len(self.df)
        unique_cnt = series.nunique()

        # Priority 1: Check native pandas datetime dtype
        if pd.api.types.is_datetime64_any_dtype(series):
            return "DATETIME"

        # Explicit non-datetime business terms that contain time/month/year substrings
        NON_DATETIME_EXCLUSIONS = {
            "overtime", "monthlyincome", "monthlyrate", "hourlyrate", "dailyrate",
            "education (years)", "yearsatcompany", "yearsincurrentrole",
            "yearswithcurrmanager", "yearssincelastpromotion", "totalworkingyears",
            "tenure_years", "tenure", "income", "salary", "rate"
        }
        is_excluded = any(ex in name_clean for ex in NON_DATETIME_EXCLUSIONS)

        # Check if numeric
        if pd.api.types.is_numeric_dtype(series):
            if not is_excluded:
                # Check if calendar year column (e.g. 'year' or 'yr' with values 1900..2100)
                if name_clean in {"year", "yr", "calendar_year", "birth_year"} or name_words.intersection({"year", "yr"}):
                    valid = series.dropna()
                    if not valid.empty and valid.min() >= 1900 and valid.max() <= 2100:
                        return "DATETIME"

            # Check if integer sequence with high uniqueness (like IDs or phone numbers >= 7 digits)
            if unique_cnt > 0:
                sample_vals = series.head(10).astype(str).tolist()
                # Large integers with >= 7 digits (e.g., phone numbers like 9876543210 or 10-digit IDs)
                is_long_num = any(len(re.sub(r"\D", "", val)) >= 7 for val in sample_vals if val != "nan")
                if is_long_num and unique_cnt / total_rows > 0.3:
                    return "IDENTIFIER"

                # Check if values look like row indices or 100% unique sequential IDs
                if unique_cnt == total_rows and total_rows > 10:
                    return "IDENTIFIER"

            # Low cardinality numeric (e.g. Rating 1-5, Grade 1-4) can be categorical or numeric
            if unique_cnt <= 5 and total_rows > 20:
                return "CATEGORICAL"

            return "QUANTITATIVE"

        # Check Datetime for String/Object columns
        if not is_excluded:
            # Match date indicators in string column names (e.g. date, joindate, hiredate, timestamp, created_at)
            has_date_kw = any(k in name_clean for k in ["date", "timestamp", "created", "updated"])
            if has_date_kw:
                try:
                    parsed = pd.to_datetime(series.head(10), errors="coerce")
                    if parsed.notna().sum() > 0:
                        return "DATETIME"
                except Exception:
                    pass

        # Text/String columns
        if any(kw in name_clean for kw in CATEGORICAL_KEYWORDS) or is_excluded:
            return "CATEGORICAL"

        # High uniqueness text could be name/email identifier
        if unique_cnt / total_rows > 0.8 and total_rows > 10:
            # Check if email or name
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
