"""calculator -- a LOW-risk starter tool, new in operator-platform phase 2.

Not registered in policy-engine's tool_catalog (see default.yaml's own
comment: the catalog is deliberately for tools "whose misuse would be
destructive, irreversible, or high-blast-radius", not an exhaustive
listing) -- pure arithmetic on numbers the caller already supplied has no
side effects, touches no state, and can't plausibly need escalation
beyond what declaring `risk_level = "LOW"` here already gives it. Kept
as a genuinely separate implementation from search_docs specifically to
avoid the trap of every LOW-risk example tool looking alike.

Deliberately does NOT use Python's `eval()` -- a natural first instinct
for "evaluate an arithmetic expression" that would hand the model a real
code-execution primitive disguised as a calculator. Parses a restricted
arithmetic grammar via `ast` instead and only ever evaluates a fixed set
of numeric operators, so `"1; import os"` or `"__import__('os')"` are
syntax errors here, not attack surface.
"""

from __future__ import annotations

import ast
import operator
from typing import Any

from aegis_harness.tool import Tool

_ALLOWED_BINOPS: dict[type, Any] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_ALLOWED_UNARYOPS: dict[type, Any] = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


class CalculatorError(ValueError):
    """Raised for any expression this evaluator refuses or can't parse."""


class CalculatorTool(Tool):
    name = "calculator"
    description = "Evaluate a numeric arithmetic expression, e.g. '(3 + 4) * 2 / 7'."
    risk_level = "LOW"

    def argument_schema(self) -> dict[str, Any]:
        return {"expression": "string, an arithmetic expression using + - * / // % ** and ()"}

    def execute(self, arguments: dict[str, Any]) -> str:
        expression = str(arguments.get("expression", "")).strip()
        if not expression:
            return "Error: 'expression' is required."
        try:
            value = _safe_eval(expression)
        except CalculatorError as exc:
            return f"Error: {exc}"
        except ZeroDivisionError:
            return "Error: division by zero."
        return f"{expression} = {value}"


def _safe_eval(expression: str) -> float | int:
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise CalculatorError(f"not a valid expression: {exc.msg}") from exc
    return _eval_node(tree.body)


def _eval_node(node: ast.expr) -> float | int:
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return node.value
        raise CalculatorError(f"unsupported constant: {node.value!r}")
    if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_BINOPS:
        left = _eval_node(node.left)
        right = _eval_node(node.right)
        return _ALLOWED_BINOPS[type(node.op)](left, right)  # type: ignore[no-any-return]
    if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_UNARYOPS:
        return _ALLOWED_UNARYOPS[type(node.op)](_eval_node(node.operand))  # type: ignore[no-any-return]
    raise CalculatorError(f"unsupported expression element: {type(node).__name__}")
