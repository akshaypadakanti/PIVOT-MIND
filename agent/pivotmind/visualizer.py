"""
Agent 4: Visualizer
Plotly code generator running inside an AST sandbox with a self-healing error recovery loop.
Integrates SemanticClassifier to strictly prevent identifier columns (Contact Number, Phone, ID, etc.)
from being plotted on the Y-axis or aggregated.
"""
from __future__ import annotations

import ast
import json
import logging
import traceback
from typing import Any
from django.conf import settings
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from .semantic_classifier import SemanticClassifier
from .viz_validator import VisualizationSpec, validate_visualization_ast

logger = logging.getLogger(__name__)

UNSAFE_MODULES = {
    "os", "sys", "subprocess", "shutil", "importlib", "pathlib",
    "socket", "urllib", "requests", "http", "ftplib", "pickle", "ctypes"
}

UNSAFE_FUNCTIONS = {
    "eval", "exec", "open", "__import__", "compile", "breakpoint", "input",
    "globals", "locals", "getattr", "setattr", "delattr"
}


class ASTSandboxError(Exception):
    """Raised when generated code contains unsafe AST nodes or fails AST semantic validation."""
    pass


def validate_ast(code: str) -> ast.AST:
    """
    Parses Python code and inspects the AST syntax tree for forbidden modules,
    unsafe function calls, or system operations.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        raise ASTSandboxError(f"Syntax error in code: {e}") from e

    class SecurityVisitor(ast.NodeVisitor):
        def visit_Import(self, node):
            for alias in node.names:
                name = alias.name.split(".")[0]
                if name in UNSAFE_MODULES:
                    raise ASTSandboxError(f"Forbidden module import: '{name}'")
            self.generic_visit(node)

        def visit_ImportFrom(self, node):
            if node.module:
                name = node.module.split(".")[0]
                if name in UNSAFE_MODULES:
                    raise ASTSandboxError(f"Forbidden module import: '{name}'")
            self.generic_visit(node)

        def visit_Call(self, node):
            if isinstance(node.func, ast.Name):
                if node.func.id in UNSAFE_FUNCTIONS:
                    raise ASTSandboxError(f"Forbidden function call: '{node.func.id}'")
            self.generic_visit(node)

        def visit_Attribute(self, node):
            if node.attr.startswith("__") and node.attr.endswith("__"):
                if node.attr not in {"__name__", "__doc__"}:
                    raise ASTSandboxError(f"Forbidden dunder attribute access: '{node.attr}'")
            self.generic_visit(node)

    visitor = SecurityVisitor()
    visitor.visit(tree)
    return tree


VISUALIZER_SYSTEM_PROMPT = """You are a Top 1% Senior Data Visualization Expert writing Plotly Python code.
Generate clean, self-contained Python code using Plotly Express (`px`) or Plotly Graph Objects (`go`) to create an interactive chart for a pandas DataFrame variable named `df`.

CRITICAL ANALYST RULES:
1. IDENTIFIER ISOLATION: NEVER plot identifier/contact columns (e.g., 'Contact Number', 'Phone', 'Mobile', 'ID', 'Roll No', 'SSN', 'Email') on the Y-axis or in boxplots/histograms!
2. CATEGORICAL COUNTS: When asked for counts or distribution across categories (e.g. "how many students per department"), compute value counts:
   `df_counts = df['Department'].value_counts().reset_index()`
   `df_counts.columns = ['Department', 'Count']`
   `fig = px.bar(df_counts, x='Department', y='Count', text='Count', color='Department', template='plotly_dark', title='Student Count by Department')`
   `fig.update_traces(textposition='outside')`
3. Save the final Plotly Figure object in a variable named `fig`.
4. Use modern dark styling (`template="plotly_dark"`), vibrant colors, readable title, and proper hover data.
5. COLUMN COMPLIANCE: You MUST use the exact column names provided in SUGGESTED X-AXIS / SUGGESTED Y-AXIS or in the user question/hypothesis! NEVER substitute an arbitrary column (like 'Age') when the user requested a specific metric (like 'HourlyRate').
6. Return ONLY executable Python code inside a ```python ... ``` code block.
"""


class Visualizer:
    """
    Generates Plotly interactive charts with AST security verification,
    AST semantic visualization validation, and a self-healing error recovery loop.
    """

    def __init__(
        self,
        df: pd.DataFrame,
        hypothesis: dict[str, Any],
        dataset_name: str = "Dataset",
        max_retries: int = 3,
    ):
        self.df = df
        self.hypothesis = hypothesis
        self.dataset_name = dataset_name
        self.max_retries = max_retries
        self.classifier = SemanticClassifier(df)

    def generate_chart(self) -> dict[str, Any]:
        """
        Executes code generation, AST security validation, AST semantic validation, and self-healing loop.
        Returns a dictionary containing Plotly JSON figure, HTML snippet, status, and code.
        """
        if self.df.empty:
            return self._fallback_chart("Dataset is empty.")

        schema = self.classifier.get_classified_schema()
        cols_info = (
            f"Columns: {list(self.df.columns)}\n"
            f"QUANTITATIVE MEASURES: {schema['QUANTITATIVE']}\n"
            f"CATEGORICAL DIMENSIONS: {schema['CATEGORICAL']}\n"
            f"IDENTIFIERS (DO NOT PLOT ON Y-AXIS): {schema['IDENTIFIER']}"
        )
        question = self.hypothesis.get("question", "Visualize key trends in the data")
        viz_type = self.hypothesis.get("target_visualization", "bar_chart")
        rec_x = self.hypothesis.get("recommended_x", "")
        rec_y = self.hypothesis.get("recommended_y", "")

        # Build explicit VisualizationSpec BEFORE code generation
        spec = VisualizationSpec(
            chart_type=viz_type,
            x_column=rec_x,
            y_column=rec_y if rec_y else None,
            title=self.hypothesis.get("title", ""),
        )

        # Always build guaranteed top 1% analyst fallback chart
        fallback_res = self._auto_plotly_express_fallback(viz_type, rec_x, rec_y)

        api_key = getattr(settings, "GEMINI_API_KEY", "") or ""
        model_name = getattr(settings, "GEMINI_MODEL", "gemini-3.6-flash") or "gemini-3.6-flash"

        if not api_key:
            return fallback_res

        prompt = f"""Dataset Name: {self.dataset_name}
{cols_info}

USER ANALYST QUESTION / HYPOTHESIS TO VISUALIZE:
"{question}"

REQUIRED VISUALIZATION SPECIFICATION:
Target Chart Type: {viz_type}
Target X-Axis Column: {rec_x}
Target Y-Axis Column: {rec_y}

CRITICAL: Generate Python code that strictly references x='{rec_x}' (and y='{rec_y}' if non-empty). Store Plotly Figure in `fig`.
"""

        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        attempt = 0
        error_history = []

        current_prompt = prompt

        while attempt < self.max_retries:
            attempt += 1
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=current_prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=VISUALIZER_SYSTEM_PROMPT,
                        temperature=0.1,
                    ),
                )
                code_text = response.text or ""
                clean_code = self._extract_code(code_text)

                # 1. AST Security Validation
                code_ast = validate_ast(clean_code)

                # 2. AST Semantic Visualization Validation
                is_sem_valid, sem_err = validate_visualization_ast(clean_code, spec)
                if not is_sem_valid:
                    raise ASTSandboxError(sem_err)

                # 3. Code Execution Sandbox
                fig = self._execute_code_sandbox(code_ast)

                if fig is not None:
                    fig_json = json.loads(fig.to_json())
                    fig_html = fig.to_html(include_plotlyjs="cdn", full_html=False)
                    return {
                        "status": "success",
                        "retries_used": attempt - 1,
                        "code": clean_code,
                        "fig_json": fig_json,
                        "fig_html": fig_html,
                        "error": None,
                    }
                else:
                    raise ValueError("Code executed successfully but `fig` variable was not defined.")

            except (ASTSandboxError, Exception) as exc:
                err_msg = str(exc)
                logger.warning("Visualizer attempt %d failed (using top 1%% fallback): %s", attempt, err_msg)
                error_history.append(f"Attempt {attempt}: {err_msg}")

                current_prompt = f"""{prompt}

PREVIOUS ATTEMPT #{attempt} FAILED WITH ERROR:
{err_msg}

Please fix the Python code so that it runs cleanly on `df` with columns {list(self.df.columns)}. Make sure `fig` is created. Do NOT plot identifier columns on Y-axis.
"""

        fallback_res["retries_used"] = self.max_retries
        fallback_res["error_history"] = error_history
        fallback_res["hypothesis_title"] = self.hypothesis.get("title", "Analysis")
        return fallback_res

    def generate_all_charts(self, hypotheses: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Generates Plotly charts for all 3 to 5 formulated hypotheses in batch.
        """
        results = []
        for index, hyp in enumerate(hypotheses, 1):
            viz = Visualizer(
                df=self.df,
                hypothesis=hyp,
                dataset_name=self.dataset_name,
                max_retries=self.max_retries,
            )
            report = viz.generate_chart()
            report["hypothesis_id"] = hyp.get("id", index)
            report["hypothesis_title"] = hyp.get("title", f"Hypothesis #{index}")
            report["hypothesis_question"] = hyp.get("question", "")
            report["priority_rank"] = hyp.get("priority_rank", index)
            report["category"] = hyp.get("category", "general")
            results.append(report)
        return results

    def _extract_code(self, text: str) -> str:
        text = text.strip()
        if "```python" in text:
            text = text.split("```python")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
        return text.strip()

    def _execute_code_sandbox(self, code_ast: ast.AST) -> go.Figure | None:
        """Executes compiled AST in a controlled dictionary namespace."""
        compiled_code = compile(code_ast, filename="<visualizer_sandbox>", mode="exec")
        safe_globals = {
            "__builtins__": __builtins__,
            "df": self.df.copy(),
            "pd": pd,
            "np": np,
            "px": px,
            "go": go,
            "fig": None,
        }
        exec(compiled_code, safe_globals)
        return safe_globals.get("fig")

    def _auto_plotly_express_fallback(self, viz_type: str, x_col: str, y_col: str) -> dict[str, Any]:
        """Generates a guaranteed safe, top 1% analyst Plotly figure across diverse chart types."""
        schema = self.classifier.get_classified_schema()
        quant_cols = schema["QUANTITATIVE"]
        cat_cols = schema["CATEGORICAL"]
        id_cols = schema["IDENTIFIER"]
        date_cols = schema["DATETIME"]

        # Filter out identifiers
        if y_col in id_cols:
            y_col = ""
        if x_col in id_cols:
            x_col = ""

        x = x_col if (x_col in self.df.columns and x_col not in id_cols) else (cat_cols[0] if cat_cols else self.df.columns[0])
        y = y_col if (y_col in self.df.columns and y_col not in id_cols) else (quant_cols[0] if quant_cols else "")

        try:
            if viz_type == "pie_chart":
                val_counts = self.df[x].astype(str).value_counts().reset_index()
                val_counts.columns = [x, "Count"]
                fig = px.pie(
                    val_counts,
                    names=x,
                    values="Count",
                    hole=0.4,
                    template="plotly_dark",
                    title=f"Proportional Share Breakdown by {x}",
                )
                code_str = (
                    f"val_counts = df['{x}'].astype(str).value_counts().reset_index()\n"
                    f"val_counts.columns = ['{x}', 'Count']\n"
                    f"fig = px.pie(val_counts, names='{x}', values='Count', hole=0.4, template='plotly_dark')"
                )
            elif viz_type == "line_chart":
                if date_cols:
                    d_col = date_cols[0]
                    df_sorted = self.df.sort_values(d_col)
                    if y:
                        fig = px.line(df_sorted, x=d_col, y=y, template="plotly_dark", title=f"Timeline Trend of {y} over {d_col}")
                        code_str = f"df_sorted = df.sort_values('{d_col}')\nfig = px.line(df_sorted, x='{d_col}', y='{y}', template='plotly_dark')"
                    else:
                        val_counts = self.df[x].astype(str).value_counts().reset_index()
                        val_counts.columns = [x, "Count"]
                        fig = px.line(val_counts, x=x, y="Count", markers=True, template="plotly_dark", title=f"Line Trend of {x} Counts")
                        code_str = f"val_counts = df['{x}'].astype(str).value_counts().reset_index()\nval_counts.columns = ['{x}', 'Count']\nfig = px.line(val_counts, x='{x}', y='Count', markers=True, template='plotly_dark')"
                elif y and quant_cols:
                    fig = px.line(self.df.head(60), y=y, markers=True, template="plotly_dark", title=f"Sequential Trend of {y}")
                    code_str = f"fig = px.line(df.head(60), y='{y}', markers=True, template='plotly_dark')"
                else:
                    val_counts = self.df[x].astype(str).value_counts().reset_index()
                    val_counts.columns = [x, "Count"]
                    fig = px.line(val_counts, x=x, y="Count", markers=True, template="plotly_dark", title=f"Line Trend Across {x}")
                    code_str = (
                        f"val_counts = df['{x}'].astype(str).value_counts().reset_index()\n"
                        f"val_counts.columns = ['{x}', 'Count']\n"
                        f"fig = px.line(val_counts, x='{x}', y='Count', markers=True, template='plotly_dark')"
                    )
            elif viz_type == "scatter_plot":
                if x in self.df.columns and y in self.df.columns:
                    color_c = x if x in cat_cols else (y if y in cat_cols else None)
                    fig = px.scatter(self.df, x=x, y=y, color=color_c, template="plotly_dark", title=f"Scatter Distribution: {y} vs {x}")
                    code_str = f"fig = px.scatter(df, x='{x}', y='{y}', color={repr(color_c)}, template='plotly_dark')"
                elif len(quant_cols) >= 2:
                    q1, q2 = quant_cols[0], quant_cols[1]
                    color_c = cat_cols[0] if cat_cols else None
                    fig = px.scatter(self.df, x=q1, y=q2, color=color_c, template="plotly_dark", title=f"Correlation Scatter: {q2} vs {q1}")
                    code_str = f"fig = px.scatter(df, x='{q1}', y='{q2}', color={repr(color_c)}, template='plotly_dark')"
                else:
                    val_counts = self.df[x].astype(str).value_counts().reset_index()
                    val_counts.columns = [x, "Count"]
                    fig = px.scatter(val_counts, x=x, y="Count", size="Count", color=x, template="plotly_dark", title=f"Scatter Distribution of {x}")
                    code_str = f"val_counts = df['{x}'].astype(str).value_counts().reset_index()\nval_counts.columns = ['{x}', 'Count']\nfig = px.scatter(val_counts, x='{x}', y='Count', size='Count', color='{x}', template='plotly_dark')"
            elif viz_type == "box_plot":
                if y in self.df.columns and x in self.df.columns and x != y:
                    fig = px.box(self.df, x=x, y=y, color=x, template="plotly_dark", title=f"Boxplot Distribution of {y} across {x}")
                    code_str = f"fig = px.box(df, x='{x}', y='{y}', color='{x}', template='plotly_dark')"
                elif quant_cols:
                    q_c = y if (y in self.df.columns) else quant_cols[0]
                    fig = px.box(self.df, y=q_c, template="plotly_dark", title=f"Statistical Boxplot of {q_c}")
                    code_str = f"fig = px.box(df, y='{q_c}', template='plotly_dark')"
                else:
                    val_counts = self.df[x].astype(str).value_counts().reset_index()
                    val_counts.columns = [x, "Count"]
                    fig = px.box(val_counts, y="Count", template="plotly_dark", title=f"Distribution Variance of {x} Counts")
                    code_str = f"val_counts = df['{x}'].astype(str).value_counts().reset_index()\nval_counts.columns = ['{x}', 'Count']\nfig = px.box(val_counts, y='Count', template='plotly_dark')"
            elif viz_type == "histogram":
                h_col = x_col if (x_col in self.df.columns and x_col not in id_cols) else (y_col if (y_col in self.df.columns and y_col not in id_cols) else (quant_cols[0] if quant_cols else self.df.columns[0]))
                fig = px.histogram(self.df, x=h_col, nbins=25, template="plotly_dark", title=f"Distribution Frequency Histogram: {h_col}")
                code_str = f"fig = px.histogram(df, x='{h_col}', nbins=25, template='plotly_dark')"
            else:
                # Default Bar Chart
                if y in quant_cols and x in self.df.columns and x != y:
                    df_grp = self.df.groupby(x)[y].mean().reset_index().round(2)
                    fig = px.bar(df_grp, x=x, y=y, text=y, color=x, template="plotly_dark", title=f"Average {y} by {x}")
                    fig.update_traces(textposition="outside")
                    code_str = f"df_grp = df.groupby('{x}')['{y}'].mean().reset_index()\nfig = px.bar(df_grp, x='{x}', y='{y}', text='{y}', color='{x}', template='plotly_dark')"
                elif y in self.df.columns and x in self.df.columns and x != y:
                    df_counts = self.df.groupby([x, y]).size().reset_index(name="Count")
                    fig = px.bar(df_counts, x=x, y="Count", color=y, barmode="group", text="Count", template="plotly_dark", title=f"Grouped Distribution: {y} by {x}")
                    fig.update_traces(textposition="outside")
                    code_str = f"df_counts = df.groupby(['{x}', '{y}']).size().reset_index(name='Count')\nfig = px.bar(df_counts, x='{x}', y='Count', color='{y}', barmode='group', text='Count', template='plotly_dark')"
                else:
                    val_counts = self.df[x].astype(str).value_counts().reset_index()
                    val_counts.columns = [x, "Count"]
                    fig = px.bar(
                        val_counts,
                        x=x,
                        y="Count",
                        text="Count",
                        color=x,
                        template="plotly_dark",
                        title=f"Category Distribution of {x}",
                    )
                    fig.update_traces(textposition="outside")
                    code_str = (
                        f"val_counts = df['{x}'].astype(str).value_counts().reset_index()\n"
                        f"val_counts.columns = ['{x}', 'Count']\n"
                        f"fig = px.bar(val_counts, x='{x}', y='Count', text='Count', color='{x}', template='plotly_dark')"
                    )

            return {
                "status": "success",
                "retries_used": 0,
                "code": code_str,
                "fig_json": json.loads(fig.to_json()),
                "fig_html": fig.to_html(include_plotlyjs="cdn", full_html=False),
                "error": None,
            }
        except Exception as e:
            return self._fallback_chart(str(e))

    def _fallback_chart(self, msg: str) -> dict[str, Any]:
        fig = go.Figure()
        fig.add_annotation(text=f"Chart unavailable: {msg}", showarrow=False, font=dict(size=14, color="red"))
        fig.update_layout(template="plotly_dark", title="Visualization Status")
        return {
            "status": "failed",
            "retries_used": 0,
            "code": "",
            "fig_json": json.loads(fig.to_json()),
            "fig_html": fig.to_html(include_plotlyjs="cdn", full_html=False),
            "error": msg,
        }
