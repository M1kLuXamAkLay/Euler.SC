"""
Core package: pure mathematics with no UI and no network access.

Submodules
----------
parser      safe expression parsing with an allow-list of identifiers
solver      arithmetic, equations, systems, function summary
analysis    domain, range, limits, asymptotes, extrema, monotonicity
calculus    limits, derivatives and integrals as separate operations
matrix      named matrix registry operations (A..H)
grapher     sampling for the plot canvas, including discontinuity splits
hardware    CPU/RAM/VRAM detection used to pick a local model
llm         local Ollama client, streaming and model management
settings    persisted user preferences
"""

from .parser import ExprError, detect_variable, parse, preprocess, validate
from .solver import (
    analyze_function,
    clean,
    evaluate,
    pretty_number,
    solve_equation,
    solve_system,
)

__all__ = [
    "ExprError",
    "validate",
    "preprocess",
    "parse",
    "detect_variable",
    "pretty_number",
    "clean",
    "evaluate",
    "solve_equation",
    "solve_system",
    "analyze_function",
]
