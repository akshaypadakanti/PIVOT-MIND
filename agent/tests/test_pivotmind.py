"""
Unit & Integration Tests for PivotMind 5-Agent Pipeline
"""
import ast
import pandas as pd
from django.test import TestCase

from agent.pivotmind.semantic_classifier import SemanticClassifier
from agent.pivotmind.data_doctor import DataDoctor
from agent.pivotmind.profiler import DatasetProfiler
from agent.pivotmind.hypothesis_engine import HypothesisEngine
from agent.pivotmind.visualizer import Visualizer, ASTSandboxError, validate_ast
from agent.pivotmind.strategist import ExecutiveStrategist
from agent.pivotmind.pipeline import PivotMindPipeline


class PivotMindPipelineTests(TestCase):
    def setUp(self):
        self.sample_data = {
            "Contact Number": [9876543210, 9876543211, 9876543212, 9876543213, 9876543214, 9876543215],
            "Department": ["AIML", "AIML", "CSE", "ECE", "AIML", "CSE"],
            "Sales": [12000.0, 15000.0, 22000.0, 8000.0, 12000.0, 35000.0],
            "Profit": [3000.0, 4000.0, 5500.0, -1000.0, 3000.0, 9000.0],
            "Units": [40, 50, 75, 25, 40, 110],
        }
        self.df = pd.DataFrame(self.sample_data)

    def test_semantic_classifier_identifies_contact_number(self):
        classifier = SemanticClassifier(self.df)
        col_type = classifier.classify_column("Contact Number")
        self.assertEqual(col_type, "IDENTIFIER")

        schema = classifier.get_classified_schema()
        self.assertIn("Contact Number", schema["IDENTIFIER"])
        self.assertIn("Department", schema["CATEGORICAL"])
        self.assertIn("Sales", schema["QUANTITATIVE"])

    def test_agent1_data_doctor(self):
        doctor = DataDoctor(self.df, dataset_name="TestSales")
        report = doctor.analyze()

        self.assertIn("health_score", report)
        self.assertGreaterEqual(report["health_score"], 0.0)
        self.assertLessEqual(report["health_score"], 100.0)
        self.assertEqual(report["total_rows"], 6)
        self.assertEqual(report["total_columns"], 5)
        self.assertIn("Contact Number", report["types"]["identifiers"])

    def test_agent2_profiler(self):
        profiler = DatasetProfiler(self.df, dataset_name="TestSales")
        profile = profiler.generate_profile()
        low_token = profiler.get_low_token_representation()

        self.assertEqual(profile["shape"], (6, 5))
        self.assertIn("DATASET: TestSales", low_token)
        self.assertIn("CRITICAL: DO NOT AGGREGATE OR PLOT ON Y-AXIS", low_token)

    def test_agent3_hypothesis_engine_autopilot_mode(self):
        profiler = DatasetProfiler(self.df, dataset_name="TestSales")
        low_token = profiler.get_low_token_representation()

        engine = HypothesisEngine(profile_summary=low_token, user_query="", df=self.df)
        hyp_report = engine.generate_hypotheses()

        self.assertTrue(hyp_report["autopilot_mode"])
        self.assertIn("hypotheses", hyp_report)
        self.assertGreaterEqual(len(hyp_report["hypotheses"]), 3)
        self.assertIn("top_hypothesis", hyp_report)
        # Ensure Contact Number is NOT selected as Y-axis
        self.assertNotEqual(hyp_report["top_hypothesis"].get("recommended_y"), "Contact Number")

    def test_agent4_visualizer_ast_sandbox_security(self):
        safe_code = "fig = px.bar(df, x='Department', y='Sales')"
        ast_tree = validate_ast(safe_code)
        self.assertIsInstance(ast_tree, ast.AST)

        unsafe_code_1 = "import os; os.system('echo bad')"
        with self.assertRaises(ASTSandboxError):
            validate_ast(unsafe_code_1)

    def test_agent4_visualizer_prevents_identifier_y_axis(self):
        hypothesis = {
            "title": "Department Distribution",
            "question": "How many students are there from AIML dept?",
            "target_visualization": "bar_chart",
            "recommended_x": "Department",
            "recommended_y": "Contact Number",  # Bad hypothesis requesting contact number on Y axis
        }
        viz = Visualizer(df=self.df, hypothesis=hypothesis, dataset_name="TestSales")
        result = viz.generate_chart()

        self.assertIn("status", result)
        self.assertIn("fig_json", result)
        # Verify Y axis is Count, NOT Contact Number
        fig_dict = result["fig_json"]
        y_title = fig_dict.get("layout", {}).get("yaxis", {}).get("title", {}).get("text", "")
        self.assertNotIn("Contact Number", y_title)

    def test_agent5_executive_strategist(self):
        doctor_report = DataDoctor(self.df).analyze()
        profiler_summary = DatasetProfiler(self.df).get_low_token_representation()
        hypothesis = {"title": "Sales Trend", "question": "Are sales growing?"}
        viz_report = {"status": "success", "code": "fig = px.line()"}

        strategist = ExecutiveStrategist(
            doctor_report=doctor_report,
            profile_summary=profiler_summary,
            hypothesis=hypothesis,
            viz_report=viz_report,
            dataset_name="Delinquency_prediction_dataset.xlsx",
            df=self.df,
        )
        synthesis = strategist.generate_synthesis()

        self.assertIn("Executive Strategic Summary", synthesis)
        self.assertIn("Core Business Growth Levers", synthesis)
        self.assertIn("Projected Business", synthesis)

    def test_agent5_domain_adaptation(self):
        # 1. HR dataset
        hr_df = pd.DataFrame({
            "EmployeeNumber": [1, 2, 3],
            "Department": ["R&D", "Sales", "HR"],
            "MonthlyIncome": [5000, 7000, 6000],
            "Attrition": ["No", "Yes", "No"],
        })
        hr_doctor = DataDoctor(hr_df, dataset_name="HR_Analytics.csv").analyze()
        hr_strat = ExecutiveStrategist(doctor_report=hr_doctor, profile_summary="", hypothesis={}, viz_report={}, dataset_name="HR_Analytics.csv", df=hr_df)
        self.assertEqual(hr_strat._detect_domain(), "HR")
        hr_out = hr_strat._fallback_synthesis()
        self.assertIn("HR & Talent Operations", hr_out)
        self.assertIn("Talent Attrition Mitigation", hr_out)

        # 2. Housing dataset
        housing_df = pd.DataFrame({
            "House_ID": [101, 102],
            "Price": [350000, 450000],
            "Bedrooms": [3, 4],
            "SqFt": [1800, 2400],
        })
        housing_doctor = DataDoctor(housing_df, dataset_name="California_Housing.csv").analyze()
        housing_strat = ExecutiveStrategist(doctor_report=housing_doctor, profile_summary="", hypothesis={}, viz_report={}, dataset_name="California_Housing.csv", df=housing_df)
        self.assertEqual(housing_strat._detect_domain(), "HOUSING")
        housing_out = housing_strat._fallback_synthesis()
        self.assertIn("Real Estate & Asset Valuation Operations", housing_out)
        self.assertIn("Property Valuation & Pricing Strategy", housing_out)

        # 3. Education dataset
        edu_df = pd.DataFrame({
            "Student_ID": [1, 2],
            "GPA": [3.8, 3.2],
            "Branch": ["CSE", "ECE"],
        })
        edu_doctor = DataDoctor(edu_df, dataset_name="Student_Scores.csv").analyze()
        edu_strat = ExecutiveStrategist(doctor_report=edu_doctor, profile_summary="", hypothesis={}, viz_report={}, dataset_name="Student_Scores.csv", df=edu_df)
        self.assertEqual(edu_strat._detect_domain(), "EDUCATION")
        edu_out = edu_strat._fallback_synthesis()
        self.assertIn("Academic Performance & Student Success Operations", edu_out)

    def test_chat_assistant_bivariate_analysis(self):
        from agent.pivotmind.chat_assistant import PivotMindChatAssistant

        delinquency_data = {
            "Customer_ID": [101, 102, 103, 104, 105],
            "Employment_Status": ["Employed", "Self-Employed", "Employed", "Unemployed", "Employed"],
            "Income": [75000, 92000, 68000, 24000, 110000],
            "Age": [34, 45, 29, 52, 41],
            "Delinquent_Account": [0, 0, 0, 1, 0],
        }
        df_delinq = pd.DataFrame(delinquency_data)
        chat = PivotMindChatAssistant(df=df_delinq, profile_summary="Test Delinquency", dataset_name="Delinquency_prediction_dataset.xlsx")

        res = chat.ask("empoly status vs income")
        self.assertTrue(res["success"])
        self.assertIsNotNone(res["chart_report"])
        self.assertEqual(res["chart_report"]["status"], "success")
        self.assertIn("Employment_Status", res["answer"])
        self.assertIn("Income", res["answer"])
        self.assertNotIn("students", res["answer"])

    def test_chat_assistant_categorical_vs_categorical(self):
        from agent.pivotmind.chat_assistant import PivotMindChatAssistant

        hr_data = {
            "EmployeeNumber": [1, 2, 3, 4, 5],
            "BusinessTravel": ["Travel_Frequently", "Travel_Rarely", "Travel_Frequently", "Non-Travel", "Travel_Rarely"],
            "Attrition": ["Yes", "No", "Yes", "No", "No"],
            "Age": [30, 40, 28, 50, 35],
        }
        df_hr = pd.DataFrame(hr_data)
        chat = PivotMindChatAssistant(df=df_hr, profile_summary="HR Test", dataset_name="HR Analytics.xlsx")

        res = chat.ask("business travel vs attrition")
        self.assertTrue(res["success"])
        self.assertIsNotNone(res["chart_report"])
        self.assertEqual(res["chart_report"]["status"], "success")
        # Must match BusinessTravel and Attrition (NOT Age!)
        self.assertIn("BusinessTravel", res["answer"])
        self.assertIn("Attrition", res["answer"])
        self.assertNotIn("Age", res["answer"])


    def test_chat_assistant_value_lookup_detection(self):
        from agent.pivotmind.chat_assistant import PivotMindChatAssistant

        chat = PivotMindChatAssistant(df=self.df, profile_summary="Test", dataset_name="TestSales")
        col_x, col_y = chat._detect_query_columns("how many students are in CSE dept")
        self.assertEqual(col_x, "Department")

    def test_chat_assistant_synonym_detection(self):
        from agent.pivotmind.chat_assistant import PivotMindChatAssistant

        chat = PivotMindChatAssistant(df=self.df, profile_summary="Test", dataset_name="TestSales")
        col_x, col_y = chat._detect_query_columns("show salary distribution across departments")
        self.assertEqual(col_x, "Department")
        self.assertEqual(col_y, "Sales")

    def test_chat_assistant_chart_report_structure(self):
        from agent.pivotmind.chat_assistant import PivotMindChatAssistant

        chat = PivotMindChatAssistant(df=self.df, profile_summary="Test", dataset_name="TestSales")
        res = chat.ask("Show sales by department")
        self.assertTrue(res["success"])
        self.assertIsNotNone(res["chart_report"])
        self.assertIn("fig_json", res["chart_report"])
        self.assertIn("fig_html", res["chart_report"])
        self.assertIsNotNone(res["chart_report"]["fig_json"])

    def test_chat_assistant_distance_vs_satisfaction_typo_matching(self):
        from agent.pivotmind.chat_assistant import PivotMindChatAssistant

        hr_columns = {
            "Age": [30], "AgeGroup": ["26-35"], "Attrition": ["No"], "BusinessTravel": ["Travel_Rarely"],
            "Department": ["Sales"], "DistanceFromHome (km)": [12], "EnvironmentSatisfaction": [4],
            "JobSatisfaction": [3], "MonthlyIncome": [5000], "RelationshipSatisfaction": [4]
        }
        df_hr = pd.DataFrame(hr_columns)
        chat = PivotMindChatAssistant(df=df_hr, profile_summary="HR Test", dataset_name="HR Analytics.xlsx")

        col_x, col_y = chat._detect_query_columns("distance form home vs empolyee satisfaction")
        self.assertEqual(col_x, "DistanceFromHome (km)")
        self.assertIn(col_y, ["EnvironmentSatisfaction", "JobSatisfaction", "RelationshipSatisfaction"])


    def test_semantic_classifier_datetime_exclusions(self):
        hr_data = {
            "Education (Years)": [12, 16, 14, 18, 16],
            "MonthlyIncome": [5000, 7500, 6200, 11000, 4800],
            "MonthlyRate": [12000, 18000, 15000, 22000, 11000],
            "OverTime": ["Yes", "No", "Yes", "No", "No"],
            "JoinDate": ["2020-01-15", "2021-03-22", "2019-11-05", "2022-07-10", "2018-05-18"],
        }
        hr_df = pd.DataFrame(hr_data)
        classifier = SemanticClassifier(hr_df)

        self.assertEqual(classifier.classify_column("Education (Years)"), "QUANTITATIVE")
        self.assertEqual(classifier.classify_column("MonthlyIncome"), "QUANTITATIVE")
        self.assertEqual(classifier.classify_column("MonthlyRate"), "QUANTITATIVE")
        self.assertEqual(classifier.classify_column("OverTime"), "CATEGORICAL")
        self.assertEqual(classifier.classify_column("JoinDate"), "DATETIME")

    def test_hypothesis_engine_no_derived_pairs_and_no_fake_line_chart(self):
        df_static = pd.DataFrame({
            "Age": [25, 35, 45, 55],
            "AgeGroup": ["18-29", "30-39", "40-49", "50+"],
            "MonthlyIncome": [4000, 6000, 8000, 10000],
        })
        profiler_summary = DatasetProfiler(df_static).get_low_token_representation()
        engine = HypothesisEngine(profile_summary=profiler_summary, user_query="", df=df_static)
        hyp_report = engine.generate_hypotheses()

        for hyp in hyp_report.get("hypotheses", []):
            x = hyp.get("recommended_x", "")
            y = hyp.get("recommended_y", "")
            # Verify Age vs AgeGroup derived pair is not recommended
            if (x == "Age" and y == "AgeGroup") or (x == "AgeGroup" and y == "Age"):
                self.fail(f"Hypothesis paired raw variable Age with derived variable AgeGroup: {hyp}")

            # Verify line_chart is not suggested when no datetime exists
            if hyp.get("target_visualization") == "line_chart":
                self.fail(f"Line chart suggested for static dataset without datetime column: {hyp}")

    def test_visualizer_histogram_column_matching(self):
        df_hr = pd.DataFrame({
            "Age": [25, 30, 35, 40, 45],
            "HourlyRate": [45, 65, 80, 55, 70],
        })
        hypothesis = {
            "title": "Distribution Frequency Histogram: HourlyRate",
            "question": "What is the statistical frequency density distribution of HourlyRate?",
            "target_visualization": "histogram",
            "recommended_x": "HourlyRate",
            "recommended_y": "",
        }
        viz = Visualizer(df=df_hr, hypothesis=hypothesis, dataset_name="HR_Dataset")
        res = viz._auto_plotly_express_fallback("histogram", "HourlyRate", "")
        self.assertEqual(res["status"], "success")
        fig_dict = res["fig_json"]
        title_text = fig_dict.get("layout", {}).get("title", {}).get("text", "")
        x_title = fig_dict.get("layout", {}).get("xaxis", {}).get("title", {}).get("text", "")
        self.assertIn("HourlyRate", title_text)
        self.assertEqual(x_title, "HourlyRate")

    def test_executive_strategist_grounded_impact(self):
        hr_df = pd.DataFrame({
            "EmployeeNumber": [1, 2, 3],
            "MonthlyIncome": [5000, 7000, 6000],
            "Attrition": ["No", "Yes", "No"],
        })
        doctor = DataDoctor(hr_df, dataset_name="HR_Analytics.csv").analyze()
        strat = ExecutiveStrategist(doctor_report=doctor, profile_summary="", hypothesis={}, viz_report={}, dataset_name="HR_Analytics.csv", df=hr_df)
        out = strat._fallback_synthesis()
        # Verify no hardcoded unsupported percentages like 20–30% in impact
        self.assertNotIn("20–30%", out)
        self.assertNotIn("20-30%", out)
        self.assertIn("Potential impact", out)

    def test_pivotmind_pipeline_end_to_end(self):
        pipeline = PivotMindPipeline(df=self.df, dataset_name="TestSales", user_query="how many students are ther from aiml dept")
        result = pipeline.run()

        self.assertEqual(result["dataset_name"], "TestSales")
        self.assertIn("health_score", result)
        self.assertIn("executive_summary", result)
        self.assertNotEqual(result["top_hypothesis"].get("recommended_y"), "Contact Number")


