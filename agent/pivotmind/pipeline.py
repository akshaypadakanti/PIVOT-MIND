"""
PivotMind Pipeline Orchestrator
Sequentially coordinates Data Doctor, Profiler, Hypothesis Engine, Visualizer,
and Executive Strategist into a unified autonomous 5-agent pipeline.
"""
from __future__ import annotations

import time
from typing import Any
import pandas as pd

from .data_doctor import DataDoctor
from .profiler import DatasetProfiler
from .hypothesis_engine import HypothesisEngine
from .visualizer import Visualizer
from .strategist import ExecutiveStrategist


class PivotMindPipeline:
    """
    Autonomous 5-Agent Tabular Data Analytics Pipeline.
    """

    def __init__(self, df: pd.DataFrame, dataset_name: str = "Dataset", user_query: str = ""):
        self.df = df
        self.dataset_name = dataset_name
        self.user_query = user_query.strip()

    def run(self) -> dict[str, Any]:
        """
        Executes the 5-agent pipeline end-to-end and returns a comprehensive structured report.
        """
        start_time = time.perf_counter()

        # -------------------------------------------------------------
        # Agent 1: Data Doctor (Data Hygiene & Health Score)
        # -------------------------------------------------------------
        doctor = DataDoctor(self.df, dataset_name=self.dataset_name)
        doctor_report = doctor.analyze()
        cleaned_df = doctor.clean_dataframe()

        # -------------------------------------------------------------
        # Agent 2: Profiler (Low-token Schema & Stat Summary)
        # -------------------------------------------------------------
        profiler = DatasetProfiler(cleaned_df, dataset_name=self.dataset_name)
        profile_data = profiler.generate_profile()
        low_token_summary = profiler.get_low_token_representation()

        # -------------------------------------------------------------
        # Agent 3: Hypothesis Engine (Autopilot Business Hypotheses)
        # -------------------------------------------------------------
        hypothesis_engine = HypothesisEngine(
            profile_summary=low_token_summary,
            user_query=self.user_query,
            df=cleaned_df,
        )
        hypotheses_report = hypothesis_engine.generate_hypotheses()
        top_hypothesis = hypotheses_report.get(
            "top_hypothesis",
            {
                "id": 1,
                "title": "Primary Distribution Analysis",
                "question": "What are the primary performance distributions across key dimensions?",
                "target_visualization": "bar_chart",
            },
        )

        # -------------------------------------------------------------
        # Agent 4: Visualizer (Multi-Chart Gallery for All Hypotheses)
        # -------------------------------------------------------------
        hypotheses_list = hypotheses_report.get("hypotheses", [top_hypothesis])
        visualizer = Visualizer(
            df=cleaned_df,
            hypothesis=top_hypothesis,
            dataset_name=self.dataset_name,
            max_retries=3,
        )
        all_viz_reports = visualizer.generate_all_charts(hypotheses_list)
        viz_report = all_viz_reports[0] if all_viz_reports else visualizer.generate_chart()

        # -------------------------------------------------------------
        # Agent 5: Strategist (Executive Synthesis)
        # -------------------------------------------------------------
        strategist = ExecutiveStrategist(
            doctor_report=doctor_report,
            profile_summary=low_token_summary,
            hypothesis=top_hypothesis,
            viz_report=viz_report,
            dataset_name=self.dataset_name,
            df=cleaned_df,
        )
        executive_summary = strategist.generate_synthesis()

        elapsed = round(time.perf_counter() - start_time, 2)

        return {
            "dataset_name": self.dataset_name,
            "user_query": self.user_query,
            "autopilot_mode": hypotheses_report.get("autopilot_mode", len(self.user_query) == 0),
            "health_score": doctor_report.get("health_score", 0.0),
            "rating": doctor_report.get("rating", "N/A"),
            "doctor_report": doctor_report,
            "profile_data": profile_data,
            "low_token_summary": low_token_summary,
            "hypotheses_report": hypotheses_report,
            "top_hypothesis": top_hypothesis,
            "viz_report": viz_report,
            "all_visualizations": all_viz_reports,
            "executive_summary": executive_summary,
            "execution_time_seconds": elapsed,
        }
