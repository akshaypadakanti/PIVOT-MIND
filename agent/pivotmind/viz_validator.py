"""
PivotMind AST Semantic Visualization Validator
Extracts DataFrame column parameters from compiled AST syntax trees of Plotly Python code
and validates them against the explicit VisualizationSpec BEFORE execution.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Any


@dataclass
class VisualizationSpec:
    """
    Explicit declarative visualization specification required BEFORE code generation.
    """
    chart_type: str            # 'histogram' | 'bar_chart' | 'scatter_plot' | 'line_chart' | 'box_plot' | 'pie_chart'
    x_column: str              # Expected target X column
    y_column: str | None = None  # Expected target Y column (if applicable)
    color_column: str | None = None
    title: str = ""


class SemanticASTVisitor(ast.NodeVisitor):
    """
    Inspects AST calls to Plotly Express (`px.bar`, `px.histogram`, `px.scatter`, etc.)
    and extracts column names passed as arguments (x, y, color, names, values).
    """

    def __init__(self):
        self.found_calls: list[dict[str, Any]] = []

    def visit_Call(self, node: ast.Call):
        func_name = ""
        if isinstance(node.func, ast.Attribute):
            func_name = node.func.attr
        elif isinstance(node.func, ast.Name):
            func_name = node.func.id

        if func_name in {"histogram", "bar", "scatter", "line", "box", "pie", "density_heatmap"}:
            extracted = {
                "func_name": func_name,
                "x": self._extract_arg_val(node, "x", positional_idx=1),
                "y": self._extract_arg_val(node, "y", positional_idx=2),
                "color": self._extract_arg_val(node, "color"),
                "names": self._extract_arg_val(node, "names"),
                "values": self._extract_arg_val(node, "values"),
            }
            self.found_calls.append(extracted)

        self.generic_visit(node)

    def _extract_arg_val(self, node: ast.Call, keyword_name: str, positional_idx: int | None = None) -> str | None:
        # Check keyword arguments first
        for kw in node.keywords:
            if kw.arg == keyword_name:
                return self._parse_ast_value(kw.value)

        # Check positional arguments if index provided
        if positional_idx is not None and len(node.args) > positional_idx:
            return self._parse_ast_value(node.args[positional_idx])

        return None

    def _parse_ast_value(self, val_node: ast.AST) -> str | None:
        if isinstance(val_node, ast.Constant) and isinstance(val_node.value, str):
            return val_node.value
        elif isinstance(val_node, ast.Subscript):
            # e.g., df['HourlyRate']
            if isinstance(val_node.slice, ast.Constant) and isinstance(val_node.slice.value, str):
                return val_node.slice.value
        elif isinstance(val_node, ast.Attribute):
            # e.g., df.HourlyRate
            return val_node.attr
        elif isinstance(val_node, ast.Name):
            return val_node.id
        return None


def validate_visualization_ast(code: str, spec: VisualizationSpec) -> tuple[bool, str]:
    """
    Validates Python code AST against VisualizationSpec.
    Returns (True, "OK") if semantic AST validation passes, or (False, error_message) if it fails.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return (False, f"SYNTAX ERROR: Code syntax is invalid: {exc}")

    visitor = SemanticASTVisitor()
    visitor.visit(tree)

    if not visitor.found_calls:
        # If no explicit px.histogram/px.bar call found, check if code defines fig = px or go.Figure
        return (True, "OK")

    call = visitor.found_calls[0]
    func_name = call["func_name"]

    # 1. Chart type validation
    expected_funcs = {
        "histogram": {"histogram"},
        "bar_chart": {"bar"},
        "scatter_plot": {"scatter"},
        "line_chart": {"line"},
        "box_plot": {"box"},
        "pie_chart": {"pie"},
    }
    allowed = expected_funcs.get(spec.chart_type, {spec.chart_type})
    if func_name not in allowed:
        return (False, f"SEMANTIC VALIDATION FAILED: Expected chart_type '{spec.chart_type}' ({allowed}), but generated code called 'px.{func_name}'.")

    # 2. X Column Validation
    actual_x = call["x"] or call["names"]
    if spec.x_column:
        if actual_x is not None and actual_x != spec.x_column:
            return (False, f"SEMANTIC VALIDATION FAILED: Expected x_column = '{spec.x_column}', but generated code uses x = '{actual_x}'.")

    # 3. Y Column Validation
    actual_y = call["y"] or call["values"]
    if spec.y_column:
        if actual_y is not None and actual_y != spec.y_column:
            return (False, f"SEMANTIC VALIDATION FAILED: Expected y_column = '{spec.y_column}', but generated code uses y = '{actual_y}'.")

    return (True, "OK")
