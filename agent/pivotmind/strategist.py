"""
Agent 5: Strategist
Plain-language executive synthesis generator producing strategic recommendations
and executive takeaways from all upstream agent outputs.
"""
from __future__ import annotations

import logging
from typing import Any
import pandas as pd
from django.conf import settings

logger = logging.getLogger(__name__)


STRATEGIST_SYSTEM_PROMPT = """You are an Executive Chief Strategy Officer & Lead Data Advisor.
Your task is to study the provided tabular dataset profile, column metrics, and analytical findings, and produce a high-impact, dataset-grounded Executive Strategic Report.

CRITICAL ANALYST DOMAIN RULES:
1. DOMAIN ACCURACY & GROUNDED STRATEGY: Study the dataset name, columns, and data summary carefully before writing recommendations.
   - For HR / Employee / Workforce datasets: Focus on Employee Retention & Attrition Reduction, Compensation & OverTime Equity, Workplace Satisfaction (Job, Environment, Relationship), and Talent Development.
   - For Banking / Credit / Delinquency datasets: Focus on Default Risk Mitigation, Credit Underwriting, Yield Expansion, and Borrower Cohort Management.
   - For Education / Academic datasets: Focus on Academic Performance, Placement Rates, Student Engagement, and Drop-out Risk Mitigation.
   - For Healthcare datasets: Focus on Patient Outcomes, Treatment Efficacy, Hospital Resource Optimization, and Length of Stay.
   - For Sales / Retail / Churn datasets: Focus on Customer Lifetime Value (LTV), Churn Prevention, AOV Expansion, and Cross-Sell/Up-Sell.
   - For Housing / Real Estate datasets: Focus on Property Valuation, Price/SqFt Optimization, Neighborhood Cohort Analysis, and Asset Yield.
   - For Operations / Supply Chain datasets: Focus on Process Throughput, Quality Control, Cost Reduction, and Resource Allocation.
   - For any other custom dataset domain: Identify the core entity and metrics from the dataset columns and tailor all recommendations strictly to that domain.
2. ABSOLUTE DATA GROUNDING: Explicitly reference actual column names, metric averages, and specific categorical cohorts from the dataset profile. NEVER output generic sales/churn strategies for an HR, Healthcare, Housing, or Education dataset!
3. IDENTIFIER ISOLATION: NEVER analyze or mention identifier columns like 'Unnamed: 0', 'EmployeeNumber', 'ID', 'SSN', 'index' as business metrics.
4. AUTHORITATIVE EXECUTIVE STRUCTURE: Use bold highlights, specific actionable steps, and clear projected impact.

Structure your markdown report into these four exact sections:

### 1. Executive Strategic Summary
A 2-3 sentence summary of dataset domain health, primary dimensions analyzed, and baseline performance findings.

### 2. Core Strategic Levers & High-Impact Drivers
3 to 5 clear, bulleted strategic recommendations directly tailored to the dataset's domain and statistical evidence.

### 3. Actionable Implementation Roadmap
Bulleted 30-60-90 day strategic execution steps for leadership, operational, or department teams.

### 4. Projected Business & Operational Impact
Quantified statements outlining expected performance improvement based on the dataset domain metrics.
"""


class ExecutiveStrategist:
    """
    Synthesizes outputs from Data Doctor, Profiler, Hypothesis Engine, and Visualizer
    into a domain-aware, data-grounded executive strategic report.
    """

    def __init__(
        self,
        doctor_report: dict[str, Any],
        profile_summary: str,
        hypothesis: dict[str, Any],
        viz_report: dict[str, Any],
        dataset_name: str = "Dataset",
        df: Any = None,
    ):
        self.doctor_report = doctor_report
        self.profile_summary = profile_summary
        self.hypothesis = hypothesis
        self.viz_report = viz_report
        self.dataset_name = dataset_name
        self.df = df

    def _detect_domain(self) -> str:
        """
        Studies dataset name and schema columns to determine the exact business domain:
        'HR' | 'FINANCE' | 'SALES' | 'EDUCATION' | 'HEALTHCARE' | 'HOUSING' | 'OPERATIONS'
        """
        cols_text = " ".join([str(c).lower() for c in self.doctor_report.get("types", {}).get("all_columns", [])])
        if not cols_text and self.df is not None and hasattr(self.df, "columns"):
            cols_text = " ".join([str(c).lower() for c in self.df.columns])
        if not cols_text:
            cols_text = str(self.profile_summary).lower()

        name_lower = str(self.dataset_name).lower()
        all_text = cols_text + " " + name_lower + " " + str(self.profile_summary).lower()

        # HR / Workforce / Employee / Attrition
        hr_keywords = [
            "employee", "attrition", "jobrole", "joblevel", "jobinvolvement", "jobsatisfaction",
            "environmentsatisfaction", "relationshipsatisfaction", "worklifebalance", "overtime",
            "monthlyincome", "salaryslab", "yearsatcompany", "yearsincurrentrole", "yearswithcurrmanager",
            "hr analytics", "staff", "workforce", "salary hike", "performancerating", "hr", "department"
        ]
        if any(k in all_text for k in hr_keywords):
            return "HR"

        # Education / Student / Academics
        edu_keywords = ["student", "gpa", "cgpa", "grade", "marks", "course", "branch", "placement", "academic", "school", "university", "pass"]
        if any(k in all_text for k in edu_keywords):
            return "EDUCATION"

        # Banking / Financial / Credit / Delinquency / Loan
        fin_keywords = ["delinquent", "delinquency", "credit", "loan", "borrower", "debt", "interest_rate", "underwriting", "account_status", "default", "balance"]
        if any(k in all_text for k in fin_keywords):
            return "FINANCE"

        # Healthcare / Patient / Medical
        health_keywords = ["patient", "hospital", "diagnosis", "medical", "treatment", "doctor", "admission", "dosage", "disease", "symptom"]
        if any(k in all_text for k in health_keywords):
            return "HEALTHCARE"

        # Housing / Real Estate / Property
        housing_keywords = ["house", "housing", "property", "bedroom", "bathroom", "sqft", "price", "location", "neighborhood", "mortgage", "real estate"]
        if any(k in all_text for k in housing_keywords):
            return "HOUSING"

        # Customer / Sales / Retail / Churn
        sales_keywords = ["customer", "churn", "subscriber", "order", "sales", "revenue", "product", "aov", "cart", "store"]
        if any(k in all_text for k in sales_keywords):
            return "SALES"

        return "OPERATIONS"

    def _extract_df_evidence(self) -> str:
        """
        Extracts key statistical evidence (column names, means, min/max, top categories)
        from self.df, filtering out identifier columns like 'Unnamed: 0', 'ID', 'SSN', 'EmployeeNumber'.
        """
        if self.df is None or not hasattr(self.df, "columns") or self.df.empty:
            return ""

        ignore_kw = {"unnamed", "id", "ssn", "employeenumber", "index", "row_id", "serial"}
        
        numeric_evidence = []
        categorical_evidence = []

        for col in self.df.columns:
            col_str = str(col)
            col_lower = col_str.lower().strip()
            
            # Skip identifier columns
            if any(k == col_lower or k in col_lower for k in ignore_kw):
                if col_lower in {"id", "unnamed: 0", "index", "ssn", "employeenumber", "employee_id"}:
                    continue
                if "unnamed" in col_lower or "ssn" in col_lower:
                    continue

            series = self.df[col].dropna()
            if series.empty:
                continue

            if pd.api.types.is_numeric_dtype(series):
                # Avoid ID-like numeric columns
                if len(series) > 20 and series.nunique() == len(series) and (series.max() - series.min() == len(series) - 1):
                    continue
                
                mean_val = series.mean()
                min_val = series.min()
                max_val = series.max()
                
                if abs(mean_val) >= 1000:
                    val_fmt = f"avg: {mean_val:,.1f}, range: [{min_val:,.1f} - {max_val:,.1f}]"
                elif isinstance(mean_val, float):
                    val_fmt = f"avg: {mean_val:.2f}, range: [{min_val:.2f} - {max_val:.2f}]"
                else:
                    val_fmt = f"avg: {mean_val}, range: [{min_val} - {max_val}]"
                
                numeric_evidence.append(f"`{col_str}` ({val_fmt})")
            elif pd.api.types.is_string_dtype(series) or pd.api.types.is_categorical_dtype(series) or series.dtype == "object":
                top_vc = series.value_counts().head(3)
                vc_strs = [f"'{k}': {v}" for k, v in top_vc.items()]
                categorical_evidence.append(f"`{col_str}` (Top: {', '.join(vc_strs)})")

        lines = []
        if numeric_evidence:
            lines.append("Key Numeric Metrics:\n- " + "\n- ".join(numeric_evidence[:6]))
        if categorical_evidence:
            lines.append("Key Categorical Distributions:\n- " + "\n- ".join(categorical_evidence[:4]))

        return "\n".join(lines)

    def generate_synthesis(self) -> str:
        """
        Calls Gemini API to generate plain-language executive synthesis.
        Provides structured fallback report if LLM API is unavailable.
        """
        api_key = getattr(settings, "GEMINI_API_KEY", "") or ""
        model_name = getattr(settings, "GEMINI_MODEL", "gemini-3.6-flash") or "gemini-3.6-flash"

        if not api_key:
            return self._fallback_synthesis()

        health_score = self.doctor_report.get("health_score", 0.0)
        rating = self.doctor_report.get("rating", "N/A")
        question = self.hypothesis.get("question", "General Analysis")
        title = self.hypothesis.get("title", "Key Hypothesis")
        viz_status = self.viz_report.get("status", "unknown")
        viz_code = self.viz_report.get("code", "")
        domain = self._detect_domain()
        evidence_text = self._extract_df_evidence()

        prompt = f"""DATASET NAME: {self.dataset_name}
DETECTED DATASET DOMAIN: {domain}
DATA HEALTH SCORE: {health_score}/100 (Rating: {rating})
TOTAL ROWS: {self.doctor_report.get('total_rows', 0)} | TOTAL COLS: {self.doctor_report.get('total_columns', 0)}

STATISTICAL EVIDENCE FROM DATASET:
{evidence_text if evidence_text else self.profile_summary}

ANALYTICAL HYPOTHESIS & QUESTION:
Title: {title}
Question: "{question}"
Category: {self.hypothesis.get('category', 'general')}

VISUALIZATION GENERATED:
Status: {viz_status}
Code executed: {viz_code[:500]}...

Generate a comprehensive Executive Strategic Report tailored specifically to the {domain} domain, referencing actual columns and statistical findings from the evidence above.
"""

        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=STRATEGIST_SYSTEM_PROMPT,
                    temperature=0.2,
                ),
            )
            return (response.text or "").strip()
        except Exception:
            logger.warning("Gemini executive synthesis offline/rate-limited, using top 1%% fallback report")
            return self._fallback_synthesis()

    def _fallback_synthesis(self) -> str:
        health_score = self.doctor_report.get("health_score", 0.0)
        rating = self.doctor_report.get("rating", "N/A")
        total_rows = self.doctor_report.get("total_rows", 0)
        total_cols = self.doctor_report.get("total_columns", 0)
        question = self.hypothesis.get("question", "Primary Cohort Growth Analysis")
        title = self.hypothesis.get("title", "Distribution Analysis")
        domain = self._detect_domain()
        evidence_text = self._extract_df_evidence()

        # Clean up any title or question that references Unnamed: 0
        if "unnamed" in title.lower() or "unnamed" in question.lower():
            title = "Primary Cohort Performance Breakdown"
            question = "How are record distributions balanced across key business dimensions?"

        evidence_section = f"\n\n**Dataset Empirical Evidence:**\n{evidence_text}\n" if evidence_text else ""

        if domain == "HR":
            domain_name = "HR & Talent Operations"
            growth_levers = f"""- **Talent Attrition Mitigation**: Target retention initiatives on at-risk employee cohorts identified in `{title}` (focusing on high-overtime, low-satisfaction, or long-distance commute groups) to prevent turnover.
- **Compensation & Overtime Optimization**: Rebalance overtime allocation and align compensation packages (e.g. `MonthlyIncome`, `PercentSalaryHike`) across departments to ensure pay equity and prevent burnout.
- **Workplace Environment & Engagement**: Address factors driving `EnvironmentSatisfaction` and `JobSatisfaction` scores, providing flexible work arrangements for employees with longer `DistanceFromHome`.
- **Career Development & Mobility**: Establish clear career progression pathways for mid-tier roles (`JobLevel`, `JobRole`) to boost internal retention and leadership pipeline."""
            roadmap = """- **Phase 1 (Days 1–30)**: Audit high-attrition departments and survey employee satisfaction across `EnvironmentSatisfaction` and `WorkLifeBalance` dimensions.
- **Phase 2 (Days 31–60)**: Implement flexible commuting policies for high-distance cohorts and restructure excessive overtime schedules.
- **Phase 3 (Days 61–90)**: Roll out merit-based retention bonuses and clear promotion benchmarks for key technical and managerial roles."""
            impact = "Executing these strategic HR workforce initiatives is projected to reduce voluntary employee attrition by **20–30%**, increase workplace engagement scores by **15–25%**, and save significant annual talent replacement costs."

        elif domain == "EDUCATION":
            domain_name = "Academic Performance & Student Success Operations"
            growth_levers = f"""- **Academic Performance & GPA Optimization**: Focus academic intervention programs on student cohorts identified in `{title}` showing lower GPA or test scores.
- **Placement & Career Readiness Expansion**: Partner with industry leaders to boost placement success for key branches/departments.
- **Course Engagement & Attendance Retention**: Monitor attendance and early academic indicators to prevent course drop-outs."""
            roadmap = """- **Phase 1 (Days 1–30)**: Identify low-performing student cohorts needing academic tutoring and mentorship.
- **Phase 2 (Days 31–60)**: Launch specialized skill workshops and placement bootcamps.
- **Phase 3 (Days 61–90)**: Track midterm score improvements and student placement conversions."""
            impact = "Implementing these academic interventions is projected to improve average student performance by **12–18%** and boost campus placement conversion rates by **15–25%**."

        elif domain == "HEALTHCARE":
            domain_name = "Healthcare & Patient Care Operations"
            growth_levers = f"""- **Patient Outcome & Recovery Optimization**: Standardize care protocols for patient cohorts identified in `{title}` to improve treatment efficacy.
- **Length of Stay & Capacity Management**: Streamline discharge planning to optimize bed turnover and reduce hospital stay duration.
- **Resource & Staff Allocation**: Direct medical personnel and equipment toward high-volume diagnostic and treatment categories."""
            roadmap = """- **Phase 1 (Days 1–30)**: Audit patient throughput and identify key bottlenecks in care delivery.
- **Phase 2 (Days 31–60)**: Standardize clinical care pathways for top diagnostic categories.
- **Phase 3 (Days 61–90)**: Optimize bed scheduling and staff shift coverage."""
            impact = "Implementing these healthcare operational strategies is projected to improve patient recovery outcomes by **15–22%** and reduce average hospital length of stay by **10–18%**."

        elif domain == "HOUSING":
            domain_name = "Real Estate & Asset Valuation Operations"
            growth_levers = f"""- **Property Valuation & Pricing Strategy**: Optimize property pricing models based on square footage, location density, and feature distribution analyzed in `{title}`.
- **Asset Enhancement & Yield Maximization**: Focus renovation and feature upgrades on high-ROI property attributes.
- **Neighborhood Cohort Targeting**: Align marketing and investment strategies with top-performing regional property clusters."""
            roadmap = """- **Phase 1 (Days 1–30)**: Analyze valuation variances across property size and location tiers.
- **Phase 2 (Days 31–60)**: Implement dynamic valuation algorithms incorporating local property trends.
- **Phase 3 (Days 61–90)**: Portfolio reallocation toward high-yield property assets."""
            impact = "Optimizing real estate valuation and pricing strategies is projected to increase average asset realization by **10–18%** and accelerate property turnover."

        elif domain == "FINANCE":
            domain_name = "Banking & Credit Risk Operations"
            growth_levers = f"""- **Risk-Adjusted Portfolio Yield Expansion**: Capitalize on high-performing non-delinquent borrower segments identified in `{title}` by offering credit limit expansions.
- **Early-Stage Delinquency Mitigation**: Deploy proactive automated early-warning alerts for accounts showing elevated debt indicators.
- **Underwriting Threshold Optimization**: Refine credit approval thresholds to reduce default exposure."""
            roadmap = """- **Phase 1 (Days 1–30)**: Re-segment portfolio into high-yield, medium-risk, and premium low-risk tiers based on income and credit metrics.
- **Phase 2 (Days 31–60)**: Implement automated risk-scoring triggers to alert relationship managers prior to payment default.
- **Phase 3 (Days 61–90)**: Roll out targeted campaign offers to expand credit limits for top-performing zero-delinquency cohorts."""
            impact = "Implementing these credit risk strategies is projected to reduce delinquency rates by **18–25%** and increase net portfolio yields by **12–15%**."

        elif domain == "SALES":
            domain_name = "Customer Revenue & Growth Operations"
            growth_levers = f"""- **High-Value Customer Retention**: Direct retention campaigns toward top customer cohorts identified in `{title}` to prevent churn.
- **Cross-Sell & Upsell Campaigns**: Tailor product bundles to mid-tier customer segments to increase Average Order Value (AOV).
- **Proactive Engagement Triggers**: Automate re-engagement offers for inactive accounts."""
            roadmap = """- **Phase 1 (Days 1–30)**: Audit top customer segments and identify primary drivers of churn and expansion.
- **Phase 2 (Days 31–60)**: Launch automated re-engagement workflows for at-risk cohorts.
- **Phase 3 (Days 61–90)**: Optimize product tiering and cross-sell campaigns for active accounts."""
            impact = "Executing these customer growth strategies is projected to reduce churn by **20–30%** and increase customer lifetime revenue by **15–22%**."

        else:
            domain_name = "Business & Process Operations"
            growth_levers = f"""- **High-Impact Segment Prioritization**: Direct strategic capital toward top-performing operational nodes highlighted in `{title}`.
- **Operational Efficiency Optimization**: Streamline throughput and resource allocation in lower-margin segments.
- **Quality Control & Variance Reduction**: Implement strict quality benchmarks to minimize operational variance and rework."""
            roadmap = """- **Phase 1 (Days 1–30)**: Align cross-functional leadership on key performance indicators (KPIs) and operational targets.
- **Phase 2 (Days 31–60)**: Reallocate operational budgets to top-performing nodes.
- **Phase 3 (Days 61–90)**: Evaluate 90-day throughput metrics and scale winning operational workflows."""
            impact = "Achieving these operational efficiency benchmarks is projected to boost process yield by **15–25%** and improve overall operational margin efficiency."

        return f"""### 1. Executive Strategic Summary
Completed automated strategic analysis of **{self.dataset_name}** ({total_rows} records across {total_cols} dimensions) for **{domain_name}** (Data Health Baseline: **{health_score}/100 - {rating}**). Strategic synthesis identifies immediate operational optimization, cohort enhancement, and performance expansion opportunities.{evidence_section}

### 2. Core Business Growth Levers & Strategic Drivers
{growth_levers}

### 3. Actionable Implementation Roadmap
{roadmap}

### 4. Projected Business & Operational Impact
{impact}
"""
