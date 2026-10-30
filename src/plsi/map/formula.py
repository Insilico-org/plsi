"""Safe formulas for derived coordinates (`derive: {engine: expr, formula: ...}`).

A formula is one arithmetic expression over the coordinate's inputs plus the context variables `age` (years at the
draw), `female` and `male` (1 or 0). Allowed: numbers, + - * / **, unary -, comparisons, and the functions below.
The expression is parsed with `ast` and walked here; nothing is ever passed to eval/exec.
"""

from __future__ import annotations

import ast
import math
import operator
from collections.abc import Callable
from functools import lru_cache
from typing import Any

MAX_LENGTH = 500
CONTEXT = frozenset({"age", "female", "male"})
FUNCTIONS: dict[str, Callable[..., Any]] = {
    "log": math.log, "ln": math.log, "log10": math.log10, "exp": math.exp, "sqrt": math.sqrt,
    "abs": abs, "min": min, "max": max, "where": lambda cond, a, b: a if cond else b,
}
NON_MONOTONE = frozenset({"abs", "min", "max", "where"})  # with comparisons: a censored input cannot be bounded
_BINARY: dict[type, Callable[[Any, Any], Any]] = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv, ast.Pow: operator.pow}
_COMPARE: dict[type, Callable[[Any, Any], bool]] = {ast.Lt: operator.lt, ast.LtE: operator.le, ast.Gt: operator.gt, ast.GtE: operator.ge, ast.Eq: operator.eq, ast.NotEq: operator.ne}


@lru_cache(maxsize=256)
def parse(formula: str) -> ast.expr:
    """Parse and check a formula; raises ValueError naming the first disallowed construct."""
    if len(formula) > MAX_LENGTH:
        raise ValueError(f"formula longer than {MAX_LENGTH} characters")
    try:
        tree = ast.parse(formula, mode="eval").body
    except SyntaxError as exc:
        raise ValueError(f"formula is not a valid expression: {exc.msg}") from None
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in FUNCTIONS or node.keywords:
                raise ValueError(f"only these functions are allowed: {', '.join(sorted(FUNCTIONS))}")
        elif isinstance(node, ast.Constant):
            if not isinstance(node.value, (int, float)) or isinstance(node.value, bool):
                raise ValueError("only numeric constants are allowed")
        elif isinstance(node, ast.BinOp):
            if type(node.op) not in _BINARY:
                raise ValueError(f"operator {type(node.op).__name__} is not allowed")
        elif isinstance(node, ast.UnaryOp):
            if not isinstance(node.op, (ast.USub, ast.UAdd)):
                raise ValueError(f"operator {type(node.op).__name__} is not allowed")
        elif isinstance(node, ast.Compare):
            if any(type(op) not in _COMPARE for op in node.ops):
                raise ValueError("only <, <=, >, >=, ==, != comparisons are allowed")
        elif not isinstance(node, (ast.Name, ast.Load, *_BINARY, *_COMPARE, ast.USub, ast.UAdd)):
            raise ValueError(f"{type(node).__name__} is not allowed in a formula")
    return tree


def variables(formula: str) -> set[str]:
    """Names the formula reads, excluding function names."""
    tree = parse(formula)
    called = {n.func.id for n in ast.walk(tree) if isinstance(n, ast.Call)}  # type: ignore[union-attr]
    return {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} - called


def monotone_safe(formula: str) -> bool:
    """True when the formula has no comparison or piecewise function, so censored inputs can be bounded."""
    tree = parse(formula)
    return not any(isinstance(n, ast.Compare) or (isinstance(n, ast.Call) and n.func.id in NON_MONOTONE)  # type: ignore[union-attr]
                   for n in ast.walk(tree))


def evaluate(formula: str, values: dict[str, float], *, age: float | None, sex: str) -> float:
    """Value of the formula. Raises ValueError for a missing variable or a math error."""
    env: dict[str, Any] = dict(values)
    used = variables(formula)
    if "age" in used:
        if age is None:
            raise ValueError("formula uses age but birth_year is unknown (or withheld as 90+)")
        env["age"] = age
    if used & {"female", "male"}:
        if sex not in ("F", "M"):
            raise ValueError("formula uses sex but the subject's sex is not F or M")
        env |= {"female": 1.0 if sex == "F" else 0.0, "male": 1.0 if sex == "M" else 0.0}

    def walk(node: ast.expr) -> Any:
        if isinstance(node, ast.Constant):
            return float(node.value)  # float powers overflow (OverflowError) instead of growing big integers
        if isinstance(node, ast.Name):
            if node.id not in env:
                raise ValueError(f"unknown variable {node.id!r}")
            return env[node.id]
        if isinstance(node, ast.UnaryOp):
            return -walk(node.operand) if isinstance(node.op, ast.USub) else walk(node.operand)
        if isinstance(node, ast.BinOp):
            return _BINARY[type(node.op)](walk(node.left), walk(node.right))
        if isinstance(node, ast.Compare):
            left, ok = walk(node.left), True
            for op, right_node in zip(node.ops, node.comparators, strict=True):
                right = walk(right_node)
                ok = ok and _COMPARE[type(op)](left, right)
                left = right
            return ok
        if isinstance(node, ast.Call):
            return FUNCTIONS[node.func.id](*(walk(a) for a in node.args))  # type: ignore[union-attr]
        raise ValueError(f"{type(node).__name__} is not allowed in a formula")

    try:
        result = float(walk(parse(formula)))
    except (ArithmeticError, TypeError) as exc:
        raise ValueError(f"formula could not be evaluated: {exc}") from None
    if not math.isfinite(result):
        raise ValueError("formula produced a non-finite value")
    return result
