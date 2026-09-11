"""
Agent 3: Hypothesis Engine
Top 1% Senior Data Analyst engine for formulating high-value business hypotheses
and domain-specific analytical questions from tabular dataset profiles and exact Pandas queries.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any
from django.conf import settings
import pandas as pd

from .semantic_classifier import SemanticClassifier

logger = logging.getLogger(__name__)


HYPOTHESIS_SYSTEM_PROMPT = """You are a Top 1% Senior Data Analyst & Principal Business Intelligence Lead.
Your goal is to inspect tabular dataset metadata and formulate actionable, high-value business hypotheses and analytical questions.

CRITICAL ANALYST DOMAIN RULES:
1. IDENTIFIER ISOLATION: NEVER select identifier/contact columns (e.g. 'Contact Number', 'Phone', 'Mobile', 'ID', 'Roll No', 'SSN', 'Email', 'Zip Code', 'Unnamed: 0', 'EmployeeNumber') for Y-axis metrics or statistical aggregation.
2. COLUMN DIVERSITY & NO REPEATS: Each generated hypothesis MUST analyze a DIFFERENT column or dimension! Do NOT use the same column for recommended_x in multiple hypotheses.
3. USER QUERY ALIGNMENT: If a USER QUERY is provided (e.g., "how many students are ther from aiml dept"), prioritize answering that exact business question! Identify the target column (e.g. 'Department', 'Branch', 'Course', 'Stream') and choose 'pie_chart' or 'bar_chart' to display counts per group.
4. CHART TYPE DIVERSITY: Vary target_visualization across generated hypotheses! Include a rich mix of chart types: 'pie_chart', 'line_chart', 'scatter_plot', 'box_plot', 'histogram', and 'bar_chart'.
5. AUTOPILOT QUALITY: In Autopilot Mode, focus on meaningful business metrics (Revenue, Profit, Sales, Marks, Score, Age, Salary, Units) vs primary categorical dimensions (Department, Region, Category, Role).

Return your response strictly as a JSON object matching this exact structure:
{
  "autopilot_mode": true/false,
  "top_hypothesis": {
    "id": 1,
    "title": "Short descriptive title of hypothesis",
    "question": "Clear analytical business question to answer",
    "rationale": "Why this is high-value based on data schema",
    "category": "trend_analysis" | "anomaly_detection" | "cohort_segmentation" | "correlation" | "distribution",
    "priority_rank": 1,
    "target_visualization": "line_chart" | "bar_chart" | "scatter_plot" | "histogram" | "box_plot" | "pie_chart",
    "recommended_x": "column_name",
    "recommended_y": "column_name_or_empty_for_counts"
  },
  "hypotheses": [
    {
      "id": 1,
      "title": "Short descriptive title",
      "question": "Analytical question",
      "rationale": "Rationale",
      "category": "category",
      "priority_rank": 1,
      "target_visualization": "viz_type",
      "recommended_x": "col",
      "recommended_y": "col"
    }
  ]
}

Rules:
1. Generate between 4 and 6 ranked hypotheses ordered by priority_rank (1 is highest priority).
2. Ensure target_visualization values vary across hypotheses (use pie_chart, line_chart, scatter_plot, box_plot, histogram, bar_chart).
3. Ensure recommended_x is UNIQUE for each hypothesis so every chart displays a different insight.
4. Output valid JSON ONLY. Do not include markdown code fence formatting outside the JSON object.
"""


class HypothesisEngine:
    """
    Formulates business hypotheses from dataset profiles using Gemini API + exact Pandas queries.
    Supports Autopilot Mode for zero-prompt analytical question generation.
    """

    def __init__(self, profile_summary: str, user_query: str = "", df: pd.DataFrame | None = None):
        self.profile_summary = profile_summary
        self.user_query = user_query.strip()
        self.df = df

    def generate_hypotheses(self) -> dict[str, Any]:
        """
        Runs hypothesis generation. If user_query is empty, operates in Autopilot Mode.
        """
        is_autopilot = len(self.user_query) == 0

        # Always build high-precision domain fallbacks first
        domain_hypotheses = self._build_domain_analyst_hypotheses(is_autopilot)

        api_key = getattr(settings, "GEMINI_API_KEY", "") or ""
        model_name = getattr(settings, "GEMINI_MODEL", "gemini-3.6-flash") or "gemini-3.6-flash"

        if not api_key:
            return domain_hypotheses

        prompt = f"""DATASET SCHEMA METADATA:
{self.profile_summary}

"""
        if is_autopilot:
            prompt += "USER QUERY: None provided. (AUTOPILOT MODE ACTIVATED: Generate 4 to 6 top business hypotheses autonomously)."
        else:
            prompt += f"USER QUERY: {self.user_query}"

        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=HYPOTHESIS_SYSTEM_PROMPT,
                    temperature=0.2,
                    response_mime_type="application/json",
                ),
            )

            raw_text = response.text or ""
            parsed = self._parse_json_response(raw_text)
            parsed["autopilot_mode"] = is_autopilot

            # Validate that LLM did not hallucinate an identifier on Y axis
            if self.df is not None and not self.df.empty:
                classifier = SemanticClassifier(self.df)
                id_cols = classifier.get_classified_schema()["IDENTIFIER"]
                top_y = parsed.get("top_hypothesis", {}).get("recommended_y", "")
                if top_y in id_cols:
                    parsed["top_hypothesis"]["recommended_y"] = ""

            return parsed

        except Exception as exc:
            logger.warning("Gemini hypothesis generation offline/rate-limited, using top 1%% analyst fallback: %s", str(exc))
            return domain_hypotheses

    def _parse_json_response(self, raw_text: str) -> dict[str, Any]:
        text = raw_text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        try:
            data = json.loads(text)
            if "hypotheses" in data and len(data["hypotheses"]) > 0:
                data["hypotheses"] = sorted(data["hypotheses"], key=lambda x: x.get("priority_rank", 99))
                data["top_hypothesis"] = data["hypotheses"][0]
            return data
        except Exception:
            return self._build_domain_analyst_hypotheses(len(self.user_query) == 0)

    def _build_domain_analyst_hypotheses(self, is_autopilot: bool) -> dict[str, Any]:
        """Provides high-quality, top 1% data analyst hypotheses using exact DataFrame queries."""
        cat_cols = []
        quant_cols = []
        date_cols = []

        if self.df is not None and not self.df.empty:
            classifier = SemanticClassifier(self.df)
            schema = classifier.get_classified_schema()
            cat_cols = schema["CATEGORICAL"]
            quant_cols = schema["QUANTITATIVE"]
            date_cols = schema["DATETIME"]

        cat1 = cat_cols[0] if cat_cols else (str(self.df.columns[0]) if (self.df is not None and not self.df.empty) else "")
        cat2 = cat_cols[1] if len(cat_cols) > 1 else cat1
        cat3 = cat_cols[2] if len(cat_cols) > 2 else cat2
        cat4 = cat_cols[3] if len(cat_cols) > 3 else cat3

        quant1 = quant_cols[0] if quant_cols else ""
        quant2 = quant_cols[1] if len(quant_cols) > 1 else quant1
        quant3 = quant_cols[2] if len(quant_cols) > 2 else quant2
        quant4 = quant_cols[3] if len(quant_cols) > 3 else quant3

        date_col = date_cols[0] if date_cols else ""

        user_q_lower = self.user_query.lower()
        total_rows = len(self.df) if self.df is not None else 0

        # Check if user prompt asks about department / student / branch distribution
        if self.df is not None and not self.df.empty and ("aiml" in user_q_lower or "dept" in user_q_lower or "student" in user_q_lower or "branch" in user_q_lower or "course" in user_q_lower):
            dept_cols = [c for c in self.df.columns if any(k in str(c).lower() for k in ["dept", "branch", "course", "stream", "major", "department"])]
            if dept_cols:
                cat1 = str(dept_cols[0])

            aiml_cnt = 0
            for col in (dept_cols or [cat1]):
                series = self.df[col].astype(str)
                matches = series[series.str.lower().str.contains("aiml|ai & ml|artificial intelligence", regex=True, na=False)]
                if len(matches) > 0:
                    aiml_cnt = len(matches)
                    break

            pct = round((aiml_cnt / total_rows) * 100, 1) if total_rows > 0 else 0

            h1 = {
                "id": 1,
                "title": f"Department Cohort Breakdown (AIML: {aiml_cnt} Students)",
                "question": f"How many students are in the AIML department compared to other cohorts? (Result: {aiml_cnt} AIML students, {pct}% of dataset)",
                "rationale": f"Calculated exact student volume per academic department across {total_rows} total records.",
                "category": "cohort_segmentation",
                "priority_rank": 1,
                "target_visualization": "bar_chart",
                "recommended_x": cat1,
                "recommended_y": "",
            }
        elif quant1 and cat1:
            h1 = {
                "id": 1,
                "title": f"Performance Analysis: {quant1} by {cat1}",
                "question": f"How does {quant1} vary across {cat1} cohorts?",
                "rationale": f"Segmenting {quant1} across {cat1} highlights key operational and business drivers.",
                "category": "trend_analysis",
                "priority_rank": 1,
                "target_visualization": "bar_chart",
                "recommended_x": cat1,
                "recommended_y": quant1,
            }
        else:
            h1 = {
                "id": 1,
                "title": "Cohort Volume & Category Distribution",
                "question": f"What is the distribution of records across {cat1 or 'categories'}?",
                "rationale": "Establishing baseline cohort volumes across categorical dimensions.",
                "category": "cohort_segmentation",
                "priority_rank": 1,
                "target_visualization": "bar_chart",
                "recommended_x": cat1,
                "recommended_y": "",
            }

        hypotheses = [
            h1,
            {
                "id": 2,
                "title": f"Proportional Category Share Breakdown ({cat2})",
                "question": f"What is the percentage breakdown across {cat2} cohorts?",
                "rationale": f"Evaluating relative percentage share across {cat2} segments.",
                "category": "cohort_segmentation",
                "priority_rank": 2,
                "target_visualization": "pie_chart",
                "recommended_x": cat2,
                "recommended_y": "",
            },
            {
                "id": 3,
                "title": f"Metric Trend & Progression ({quant1 or cat1})",
                "question": f"How does {quant1 or cat1} progress over sequential observations?",
                "rationale": "Tracking trajectory and sequential trend variations.",
                "category": "trend_analysis",
                "priority_rank": 3,
                "target_visualization": "line_chart",
                "recommended_x": date_col or cat1,
                "recommended_y": quant1,
            },
            {
                "id": 4,
                "title": f"Correlation Scatter: {quant2 or quant1} vs {quant1 or cat1}" if quant2 else f"Category Breakdown ({cat3})",
                "question": f"Is there a statistical correlation between {quant2} and {quant1}?" if quant2 else f"What is the distribution across {cat3}?",
                "rationale": "Identifying bivariate relationship patterns." if quant2 else f"Segmenting dataset across {cat3}.",
                "category": "correlation" if quant2 else "cohort_segmentation",
                "priority_rank": 4,
                "target_visualization": "scatter_plot" if quant2 else "bar_chart",
                "recommended_x": quant1 if quant2 else cat3,
                "recommended_y": quant2 if quant2 else "",
            },
            {
                "id": 5,
                "title": f"Quartile Variance Boxplot: {quant3 or quant1} by {cat3}",
                "question": f"What is the quartile variance and outlier spread for {quant3 or quant1} across {cat3}?",
                "rationale": f"Analyzing interquartile ranges and median stability for {quant3 or quant1}.",
                "category": "anomaly_detection",
                "priority_rank": 5,
                "target_visualization": "box_plot",
                "recommended_x": cat3,
                "recommended_y": quant3 or quant1,
            },
            {
                "id": 6,
                "title": f"Distribution Frequency Histogram: {quant4 or quant1}",
                "question": f"What is the statistical frequency density distribution of {quant4 or quant1}?",
                "rationale": f"Inspecting skewness and bin density of {quant4 or quant1}.",
                "category": "distribution",
                "priority_rank": 6,
                "target_visualization": "histogram",
                "recommended_x": quant4 or quant1,
                "recommended_y": "",
            },
        ]

        return {
            "autopilot_mode": is_autopilot,
            "top_hypothesis": hypotheses[0],
            "hypotheses": hypotheses,
        }
