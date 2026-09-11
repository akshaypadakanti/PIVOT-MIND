"""
PivotMind Live Chat Assistant
Top 1% Senior Data Analyst pair-programmer for follow-up analytical queries.
Executes exact Pandas filtering/aggregations on dataset and dynamically generates Plotly charts.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any
from django.conf import settings
import pandas as pd
import numpy as np

from .semantic_classifier import SemanticClassifier
from .visualizer import Visualizer, validate_ast

logger = logging.getLogger(__name__)


CHAT_SYSTEM_PROMPT = """You are a Top 1% Senior Data Analyst & Lead Data Scientist pair-programmer.
You answer user follow-up questions about their uploaded tabular dataset with exact data precision and domain expertise.

CRITICAL ANALYST DOMAIN RULES:
1. DATA PRECISION: When the user asks for counts, percentages, or specific cohort numbers (e.g. "how many students from AIML dept"), reference the schema columns (e.g. Department, Branch) and provide exact quantitative counts.
2. IDENTIFIER ISOLATION: NEVER average or aggregate identifier/contact columns (e.g. Contact Number, Phone, ID, SSN, Roll No).
3. PLOTLY GENERATION: Whenever the user asks for a chart, distribution, relationship, comparison, or plot (or gives an insight requiring visualization), generate clean Python code wrapped in ```python ... ``` that creates a Plotly Figure variable `fig` using DataFrame `df`.
   - Use `px.bar`, `px.box`, `px.scatter`, `px.line`, `px.pie`, or `px.histogram`.
   - Set `template="plotly_dark"` and provide clear titles and axis labels.
   - Example for category counts:
     ```python
     df_counts = df['Department'].value_counts().reset_index()
     df_counts.columns = ['Department', 'Count']
     fig = px.bar(df_counts, x='Department', y='Count', text='Count', color='Department', template='plotly_dark', title='Department Distribution')
     fig.update_traces(textposition='outside')
     ```
4. Provide structured, executive markdown with clear bold highlights and bullet points.
"""


class PivotMindChatAssistant:
    """
    Answers follow-up conversational queries on an existing dataset context
    with exact data computation and Plotly charts.
    """

    def __init__(self, df: pd.DataFrame, profile_summary: str, dataset_name: str = "Dataset"):
        self.df = df
        self.profile_summary = profile_summary
        self.dataset_name = dataset_name
        self.classifier = SemanticClassifier(df) if not df.empty else None

    def _detect_entity_name(self) -> str:
        """Determines the appropriate entity name for dataset records (borrowers, customers, employees, accounts, records)."""
        cols_lower = [str(c).lower() for c in self.df.columns]
        name_lower = str(self.dataset_name).lower()
        all_text = " ".join(cols_lower) + " " + name_lower

        if any(k in all_text for k in ["delinquent", "credit", "loan", "bank", "debt", "borrower", "account"]):
            return "accounts"
        elif any(k in all_text for k in ["customer", "churn", "client", "subscriber"]):
            return "customers"
        elif any(k in all_text for k in ["employee", "staff", "salary", "hr", "attrition"]):
            return "employees"
        elif any(k in all_text for k in ["student", "gpa", "course", "grade", "school"]):
            return "students"
        return "records"

    def _detect_query_columns(self, question: str) -> tuple[str, str]:
        """
        Parses question using camelCase tokenization, fuzzy string similarity,
        synonym maps, and value-level lookup to identify the top 2 relevant columns.
        """
        if self.df.empty:
            return ("", "")

        import difflib

        q_clean = question.strip()
        q_lower = q_clean.lower()
        q_norm = re.sub(r"[^a-z0-9]", "", q_lower)

        # Helper to split camelCase, underscores, and strip parenthetical units
        def tokenize(text: str) -> list[str]:
            cleaned = re.sub(r"\([^)]*\)", "", str(text))
            words = re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?=[A-Z][a-z]|\d|\b)|[a-zA-Z0-9]+", cleaned)
            stop_words = {"vs", "and", "the", "for", "show", "plot", "me", "what", "is", "how", "by", "of", "in", "with", "between"}
            return [w.lower() for w in words if len(w) > 1 and w.lower() not in stop_words]

        q_tokens = tokenize(q_clean)

        SYNONYMS = {
            "salary": ["income", "rate", "slab", "hike", "pay", "package", "earnings"],
            "income": ["salary", "rate", "slab", "pay", "package"],
            "experience": ["years", "worked", "level", "tenure", "seniority"],
            "department": ["dept", "field", "branch", "stream"],
            "satisfaction": ["environment", "job", "relationship"],
            "distance": ["commute", "travel", "home", "far"],
            "gpa": ["marks", "score", "grades", "percentage", "cgpa"],
            "marks": ["gpa", "score", "grades", "units"],
            "attrition": ["left", "churn", "turnover", "retention"],
            "delinquency": ["default", "late", "debt", "delinquent"],
            "age": ["dob", "birth"],
            "gender": ["sex", "female", "male"],
        }

        schema = self.classifier.get_classified_schema() if self.classifier else {}
        id_cols = set(schema.get("IDENTIFIER", []))
        cat_cols = schema.get("CATEGORICAL", [])
        quant_cols = schema.get("QUANTITATIVE", [])

        # Score each column in DataFrame
        col_scores: list[tuple[str, float]] = []

        for col in self.df.columns:
            c_str = str(col)
            # Skip Unnamed index columns and identifiers
            if c_str.startswith("Unnamed:") or c_str in id_cols:
                continue

            c_norm = re.sub(r"[^a-z0-9]", "", c_str.lower())
            c_clean_norm = re.sub(r"[^a-z0-9]", "", re.sub(r"\([^)]*\)", "", c_str.lower()))
            c_tokens = tokenize(c_str)
            score = 0.0

            # 1. Full/clean normalized substring match
            if len(c_clean_norm) >= 3 and c_clean_norm in q_norm:
                score += 10.0
            elif len(c_norm) >= 3 and c_norm in q_norm:
                score += 8.0

            # 2. Token level matching (Exact, Fuzzy, Anagram/Typo, Synonym)
            for ct in c_tokens:
                for qt in q_tokens:
                    if ct == qt:
                        score += 5.0
                    elif difflib.SequenceMatcher(None, ct, qt).ratio() >= 0.75:
                        score += 3.5
                    elif sorted(ct) == sorted(qt) and len(ct) >= 3:
                        score += 3.0
                    elif qt in SYNONYMS and ct in SYNONYMS[qt]:
                        score += 4.0
                    elif ct in SYNONYMS and qt in SYNONYMS[ct]:
                        score += 4.0

            # 3. Value-Level Lookup (Check if unique categorical values are mentioned in question)
            if c_str in cat_cols:
                try:
                    unique_vals = [str(v).lower() for v in self.df[c_str].dropna().unique()[:20]]
                    for val in unique_vals:
                        val_norm = re.sub(r"[^a-z0-9]", "", val)
                        if len(val_norm) >= 2 and val_norm in q_norm:
                            score += 4.5
                            break
                except Exception:
                    pass

            if score > 0:
                col_scores.append((c_str, score))

        col_scores.sort(key=lambda x: x[1], reverse=True)

        if not col_scores:
            x_col = cat_cols[0] if cat_cols else str(self.df.columns[0])
            y_col = quant_cols[0] if quant_cols else ""
            return (x_col, y_col)

        if len(col_scores) == 1:
            col1 = col_scores[0][0]
            if col1 in cat_cols:
                other_cats = [c for c in cat_cols if c != col1]
                y_col = quant_cols[0] if quant_cols else (other_cats[0] if other_cats else "")
                return (col1, y_col)
            else:
                x_col = cat_cols[0] if cat_cols else str(self.df.columns[0])
                return (x_col, col1)

        # Return top 2 highest scoring distinct columns
        return (col_scores[0][0], col_scores[1][0])

    def ask(self, question: str) -> dict[str, Any]:
        """
        Processes a user question, computes data insights, and returns text response + Plotly chart.
        """
        if self.df.empty:
            return {
                "success": False,
                "answer": "Dataset context is empty. Please re-run the pipeline with a valid CSV/Excel file.",
                "chart_report": None,
            }

        q_lower = question.strip().lower()

        # Handle simple greetings
        if q_lower in ["hi", "hello", "hey", "greetings", "help", "hi there", "hello there"]:
            cols_preview = ", ".join([f"`{c}`" for c in self.df.columns[:6]])
            greet_text = f"""### 👋 Hello! I am your PivotMind Assistant

I have **{self.dataset_name}** loaded in memory ({len(self.df)} {self._detect_entity_name()} across {len(self.df.columns)} columns).

**Available Primary Columns**: {cols_preview}

**Suggested Analytical Questions You Can Ask Me**:
- *“Show me business travel vs attrition breakdown”*
- *“What is age vs income relationship?”*
- *“How many records fall under each category?”*
- *“Plot a boxplot of credit score by delinquency status”*
"""
            return {
                "success": True,
                "answer": greet_text,
                "chart_report": None,
            }

        computed_context = self._compute_deterministic_insights(question)

        prompt = f"""DATASET NAME: {self.dataset_name} | Shape: {len(self.df)} rows x {len(self.df.columns)} cols
COLUMNS: {list(self.df.columns)}

COMPUTED DATA ANALYSIS CONTEXT (From DataFrame):
{computed_context}

USER FOLLOW-UP QUESTION:
"{question}"
"""

        api_key = getattr(settings, "GEMINI_API_KEY", "") or ""
        model_name = getattr(settings, "GEMINI_MODEL", "gemini-3.6-flash") or "gemini-3.6-flash"

        if not api_key:
            return self._fallback_answer(question, computed_context)

        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=CHAT_SYSTEM_PROMPT,
                    temperature=0.2,
                ),
            )
            raw_text = (response.text or "").strip()

            # Attempt extracting and executing Python code block generated by Gemini directly
            chart_report = None
            if "```python" in raw_text or "```" in raw_text:
                try:
                    code_text = raw_text
                    if "```python" in code_text:
                        code_text = code_text.split("```python")[1].split("```")[0]
                    elif "```" in code_text:
                        code_text = code_text.split("```")[1].split("```")[0]
                    code_text = code_text.strip()

                    code_ast = validate_ast(code_text)
                    viz = Visualizer(df=self.df, hypothesis={"question": question}, dataset_name=self.dataset_name)
                    fig = viz._execute_code_sandbox(code_ast)

                    if fig is not None:
                        fig_json = json.loads(fig.to_json())
                        fig_html = fig.to_html(include_plotlyjs="cdn", full_html=False)
                        chart_report = {
                            "status": "success",
                            "retries_used": 0,
                            "code": code_text,
                            "fig_json": fig_json,
                            "fig_html": fig_html,
                            "error": None,
                        }
                except Exception as exc:
                    logger.debug("Failed to execute inline LLM Python Plotly code: %s", str(exc))

            if not chart_report:
                col_x, col_y = self._detect_query_columns(question)
                viz_type = self._determine_chart_type(question, col_x, col_y)

                hyp = {
                    "question": question,
                    "target_visualization": viz_type,
                    "recommended_x": col_x,
                    "recommended_y": col_y,
                }
                viz = Visualizer(df=self.df, hypothesis=hyp, dataset_name=self.dataset_name)
                chart_report = viz.generate_chart()

            return {
                "success": True,
                "answer": raw_text,
                "chart_report": chart_report,
            }

        except Exception as exc:
            logger.warning("PivotMindChatAssistant LLM call offline/rate-limited, using top 1%% analyst response: %s", str(exc))
            return self._fallback_answer(question, computed_context)

    def _determine_chart_type(self, question: str, col_x: str, col_y: str) -> str:
        """Determines best Plotly chart type based on query intent and variable types."""
        q_lower = question.lower()
        schema = self.classifier.get_classified_schema() if self.classifier else {}
        quant_cols = schema.get("QUANTITATIVE", [])

        if any(k in q_lower for k in ["box", "boxplot", "variance", "spread"]):
            return "box_plot"
        if any(k in q_lower for k in ["scatter", "correlation", "trendline"]):
            return "scatter_plot"
        if any(k in q_lower for k in ["pie", "share", "percentage", "proportion"]):
            return "pie_chart"
        if any(k in q_lower for k in ["histogram", "distribution"]):
            return "histogram"

        # Multi-variable heuristics
        if col_x and col_y and col_x in self.df.columns and col_y in self.df.columns:
            if col_x in quant_cols and col_y in quant_cols:
                return "scatter_plot"
            elif col_x in quant_cols or col_y in quant_cols:
                return "box_plot"
            else:
                # Both are categorical (e.g. BusinessTravel vs Attrition)
                return "bar_chart"

        return "bar_chart"

    def _compute_deterministic_insights(self, question: str) -> str:
        """Executes exact pandas filtering/aggregations to answer user queries with 100% mathematical precision."""
        col_x, col_y = self._detect_query_columns(question)
        entity = self._detect_entity_name()
        insights = []

        if col_x in self.df.columns:
            val_counts = self.df[col_x].astype(str).value_counts().head(8)
            insights.append(f"Column '{col_x}' Distribution (Top categories out of {len(self.df)} {entity}):\n{val_counts.to_string()}")

        if col_y in self.df.columns:
            if pd.api.types.is_numeric_dtype(self.df[col_y]):
                stats = self.df[col_y].describe()
                insights.append(f"Metric '{col_y}' Summary Statistics:\n{stats.to_string()}")
                if col_x in self.df.columns and col_x != col_y:
                    grp = self.df.groupby(col_x)[col_y].agg(["count", "mean", "median", "min", "max"]).round(2)
                    insights.append(f"Bivariate Analysis: '{col_y}' grouped by '{col_x}':\n{grp.to_string()}")
            else:
                # Categorical vs Categorical Crosstab
                if col_x in self.df.columns and col_x != col_y:
                    ct = pd.crosstab(self.df[col_x].astype(str), self.df[col_y].astype(str), normalize="index").round(3) * 100
                    insights.append(f"Categorical Crosstab (%): '{col_y}' distribution by '{col_x}':\n{ct.to_string()}")

        return "\n\n".join(insights)

    def _fallback_answer(self, question: str, computed_context: str) -> dict[str, Any]:
        """Provides a top 1% data analyst structured fallback response."""
        col_x, col_y = self._detect_query_columns(question)
        entity = self._detect_entity_name()
        schema = self.classifier.get_classified_schema() if self.classifier else {}
        quant_cols = schema.get("QUANTITATIVE", [])

        viz_type = self._determine_chart_type(question, col_x, col_y)

        answer_text = f"""### 📊 Executive Data Analyst Insight: "{question}"

Based on exact quantitative analysis of **{self.dataset_name}** ({len(self.df)} total {entity}):

"""

        # Case 1: Bivariate Analysis
        if col_x in self.df.columns and col_y in self.df.columns and col_x != col_y:
            # Case 1A: Categorical vs Quantitative (or Quantitative vs Quantitative)
            if col_y in quant_cols and pd.api.types.is_numeric_dtype(self.df[col_y]):
                grp = self.df.groupby(col_x)[col_y].agg(["count", "mean", "median"]).head(6)
                items = []
                for cat, row in grp.iterrows():
                    items.append(f"- **{cat}**: {int(row['count'])} {entity} | Mean {col_y}: **{row['mean']:,.2f}** (Median: {row['median']:,.2f})")
                
                answer_text += f"""- **Relationship Analyzed**: `{col_x}` vs `{col_y}`
- **Key Cohort Grouping Breakdown**:
{chr(10).join(items)}

> **Analytical Takeaway**: The metric `{col_y}` varies across `{col_x}` cohorts. Review the generated Plotly graph below for visual distribution comparison.
"""
            # Case 1B: Categorical vs Categorical (e.g. BusinessTravel vs Attrition)
            else:
                c_counts = pd.crosstab(self.df[col_x].astype(str), self.df[col_y].astype(str))
                c_pct = pd.crosstab(self.df[col_x].astype(str), self.df[col_y].astype(str), normalize="index") * 100
                items = []
                for cat in c_counts.index[:6]:
                    sub_items = []
                    total_cat = c_counts.loc[cat].sum()
                    for col_val in c_counts.columns:
                        cnt = c_counts.loc[cat, col_val]
                        pct = c_pct.loc[cat, col_val]
                        sub_items.append(f"{col_val}: **{cnt}** ({pct:.1f}%)")
                    items.append(f"- **{cat}** ({total_cat} {entity}): {', '.join(sub_items)}")

                answer_text += f"""- **Relationship Analyzed**: `{col_x}` vs `{col_y}`
- **Cross-Cohort Breakdown**:
{chr(10).join(items)}

> **Analytical Takeaway**: Distribution of `{col_y}` varies significantly across `{col_x}` cohorts. Review the grouped bar chart below for visual comparison.
"""

        # Case 2: Univariate Analysis
        else:
            target_col = col_x if col_x in self.df.columns else str(self.df.columns[0])
            val_counts = self.df[target_col].astype(str).value_counts().head(6)
            top_items = [f"- **{k}**: {v} {entity} ({round(v/len(self.df)*100, 1)}%)" for k, v in val_counts.items()]

            answer_text += f"""- **Primary Dimension Analyzed**: `{target_col}`
- **Breakdown of Top Categories**:
{chr(10).join(top_items)}
"""

        hyp = {
            "question": question,
            "target_visualization": viz_type,
            "recommended_x": col_x,
            "recommended_y": col_y,
        }
        viz = Visualizer(df=self.df, hypothesis=hyp, dataset_name=self.dataset_name)
        chart_report = viz.generate_chart()

        return {
            "success": True,
            "answer": answer_text,
            "chart_report": chart_report,
        }


