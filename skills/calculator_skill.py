"""Safe calculator skill supporting arithmetic only."""
from __future__ import annotations

import ast
import math
import operator
import re

BINARY = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
          ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv,
          ast.Mod: operator.mod, ast.Pow: operator.pow}
UNARY = {ast.UAdd: operator.pos, ast.USub: operator.neg}


def calculate(expression: str) -> float | int:
    if len(expression) > 80:
        raise ValueError("expression is too long")
    tree = ast.parse(expression, mode="eval")

    def visit(node):
        if isinstance(node, ast.Expression):
            return visit(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in BINARY:
            left, right = visit(node.left), visit(node.right)
            if isinstance(node.op, ast.Pow) and abs(right) > 8:
                raise ValueError("exponent is too large")
            result = BINARY[type(node.op)](left, right)
            if not math.isfinite(float(result)) or abs(result) > 1e15:
                raise ValueError("result is outside the supported range")
            return result
        if isinstance(node, ast.UnaryOp) and type(node.op) in UNARY:
            return UNARY[type(node.op)](visit(node.operand))
        raise ValueError("only numeric arithmetic is supported")

    return visit(tree)


def handle(text: str, _context: dict) -> str | None:
    phrase = text.lower().strip()
    phrase = re.sub(r"\b(multiplied by|times)\b", "*", phrase)
    phrase = re.sub(r"\b(divided by)\b", "/", phrase)
    phrase = re.sub(r"\bplus\b", "+", phrase)
    phrase = re.sub(r"\bminus\b", "-", phrase)
    for prefix in ("calculate ", "compute ", "what is ", "what's "):
        if phrase.startswith(prefix):
            expression = phrase[len(prefix):].strip().rstrip("?")
            if not expression or not re.fullmatch(r"[0-9.\s()+*/%\-]+", expression):
                return None
            try:
                result = calculate(expression)
                return f"That equals {result:g}." if isinstance(result, float) else f"That equals {result}."
            except (SyntaxError, ValueError, ZeroDivisionError, OverflowError):
                return "I couldn't calculate that. Use numbers and +, -, *, /, %, parentheses, or powers."
    return None


def register(manager) -> None:
    manager.register("calculator", "Calculate basic arithmetic locally and safely.", handle,
                     ("Calculate 45 * 12", "What is (9 + 3) / 4?"))
