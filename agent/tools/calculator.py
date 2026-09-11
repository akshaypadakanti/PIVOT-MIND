"""Safe calculator — AST evaluation only. Never uses eval() or exec()."""
from __future__ import annotations

import ast
import math
import operator
import re
from typing import Any

NAME = "calculator"
CATEGORY = "Local"
DESCRIPTION = "Performs safe mathematical calculations, including percentages and compound expressions."
REQUIRES_API_KEY = None
EXAMPLES = [
    "Calculate 25 × 64",
    "What is 18% of 750?",
    "Calculate compound interest on 10000 at 8% for 3 years",
    "15000 / 12",
]

_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

_FUNCTIONS = {
    "abs": abs,
    "round": round,
    "pow": pow,
    "sqrt": math.sqrt,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "asin": math.asin,
    "acos": math.acos,
    "atan": math.atan,
    "log": math.log,
    "log10": math.log10,
    "log2": math.log2,
    "exp": math.exp,
    "ceil": math.ceil,
    "floor": math.floor,
    "fabs": math.fabs,
    "factorial": math.factorial,
}

_CONSTANTS = {
    "pi": math.pi,
    "e": math.e,
    "tau": math.tau,
}

SCHEMA = {
    "type": "function",
    "function": {
        "name": NAME,
        "description": (
            "Evaluate a mathematical expression safely. Use this for arithmetic, "
            "percentages, powers, roots, and compound-interest formulas. "
            "Convert natural language math into a numeric expression first. "
            "Example: 18% of 750 becomes (18/100)*750. "
            "Compound interest: principal * (1 + rate/n)**(n*t)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "A mathematical expression such as (18/100)*750 or 25*64.",
                }
            },
            "required": ["expression"],
        },
    },
}


class CalculatorError(ValueError):
    pass


def _normalize_expression(expression: str) -> str:
    text = expression.strip()
    if not text:
        raise CalculatorError("Please provide a mathematical expression.")
    if len(text) > 400:
        raise CalculatorError("The expression is too long.")

    text = text.replace("×", "*").replace("÷", "/").replace("^", "**")
    text = re.sub(r"(\d+(?:\.\d+)?)\s*%\s*of\s*", r"(\1/100)*", text, flags=re.IGNORECASE)
    text = re.sub(r"(\d+(?:\.\d+)?)\s*percent\s*of\s*", r"(\1/100)*", text, flags=re.IGNORECASE)
    return text


def _eval_node(node: ast.AST) -> float | int:
    if isinstance(node, ast.Expression):
        return _eval_node(node.body)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise CalculatorError("Only numbers are allowed in expressions.")
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPERATORS:
        left = _eval_node(node.left)
        right = _eval_node(node.right)
        if type(node.op) in {ast.Div, ast.FloorDiv, ast.Mod} and right == 0:
            raise CalculatorError("Division by zero is not allowed.")
        if isinstance(node.op, ast.Pow):
            if abs(right) > 12 or abs(left) > 1_000_000:
                raise CalculatorError("Exponent or base is too large for safe evaluation.")
        result = _OPERATORS[type(node.op)](left, right)
        if isinstance(result, float) and (math.isinf(result) or math.isnan(result)):
            raise CalculatorError("The result is not a finite number.")
        return result
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPERATORS:
        return _OPERATORS[type(node.op)](_eval_node(node.operand))
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name) or node.func.id not in _FUNCTIONS:
            raise CalculatorError("Only approved math functions may be used.")
        if node.keywords:
            raise CalculatorError("Keyword arguments are not allowed.")
        args = [_eval_node(arg) for arg in node.args]
        func = _FUNCTIONS[node.func.id]
        try:
            result = func(*args)
        except Exception as exc:
            raise CalculatorError("The function could not be evaluated with those arguments.") from exc
        if isinstance(result, float) and (math.isinf(result) or math.isnan(result)):
            raise CalculatorError("The result is not a finite number.")
        return result
    if isinstance(node, ast.Name) and node.id in _CONSTANTS:
        return _CONSTANTS[node.id]
    raise CalculatorError("The expression contains unsupported syntax.")


def evaluate_expression(expression: str) -> float | int:
    normalized = _normalize_expression(expression)
    try:
        tree = ast.parse(normalized, mode="eval")
    except SyntaxError as exc:
        raise CalculatorError("The expression could not be parsed. Use numbers and + - * / ** ( ).") from exc
    value = _eval_node(tree)
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, float):
        return round(value, 8)
    return value


def execute(expression: str) -> dict[str, Any]:
    try:
        result = evaluate_expression(expression)
    except CalculatorError as exc:
        return {"success": False, "error": str(exc), "summary": str(exc), "data": {}}
    return {
        "success": True,
        "error": None,
        "summary": f"{expression} = {result}",
        "data": {"expression": expression, "result": result},
    }
