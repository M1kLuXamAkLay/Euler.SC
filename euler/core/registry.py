"""Named matrices.

The user builds a matrix in a grid, gives it a letter (``A``..``H``) and saves
it. From then on the letter behaves like a value: ``rank(F)``, ``det(F) * 2``
and ``inv(A) * B`` all work in the ordinary input field.

Storage lives in the settings file so matrices survive a restart.
"""
from __future__ import annotations

from .parser import ExprError
from . import matrix as matrix_module
from .matrix import MAX_SIZE

LETTERS = ("A", "B", "C", "D", "E", "F", "G", "H")

class Registry:
    """Matrices stored by letter; the bridge passes their grids to the parser."""

    def __init__(self) -> None:
        self._items: dict[str, list[list[str]]] = {}

    # ------------------------------------------------------------------ access
    def load(self) -> None:
        """Read saved grids from settings, discarding anything malformed.

        Older releases stored ``{"rows": n, "cols": m, "cells": [...]}`` per
        matrix. Those entries are skipped rather than raising: a corrupt
        settings file must never stop the application from starting.
        """
        from .settings import load as load_settings

        stored = load_settings().get("matrices") or {}
        items: dict[str, list[list[str]]] = {}

        if isinstance(stored, dict):
            for name, grid in stored.items():
                key = str(name).upper()
                if key not in LETTERS:
                    continue
                cleaned = self._clean_grid(grid)
                if cleaned:
                    items[key] = cleaned

        self._items = items

    @staticmethod
    def _clean_grid(grid) -> list[list[str]] | None:
        """Accept only a rectangular grid of scalars; otherwise None."""
        if not isinstance(grid, list) or not grid:
            return None

        rows: list[list[str]] = []
        width = None
        for row in grid:
            if not isinstance(row, list) or not row:
                return None
            if width is None:
                width = len(row)
            elif len(row) != width:
                return None
            rows.append([str(cell) for cell in row])

        if len(rows) > MAX_SIZE or (width or 0) > MAX_SIZE:
            return None
        return rows

    def save(self) -> None:
        from .settings import save as save_settings
        save_settings({"matrices": self._items})

    # ------------------------------------------------------------------ api
    def names(self) -> list[str]:
        return [name for name in LETTERS if name in self._items]

    def has(self, name: str) -> bool:
        return name.upper() in self._items

    def grid(self, name: str) -> list[list[str]] | None:
        return self._items.get(name.upper())

    def put(self, name: str, grid: list[list[str]]) -> dict:
        """Create or replace a matrix. Validates before storing."""
        name = (name or "").strip().upper()
        if name not in LETTERS:
            raise ExprError(f"ExprError.bad_matrix_name:{','.join(LETTERS)}")

        if not grid or not grid[0]:
            raise ExprError("ExprError.empty_matrix")

        width = len(grid[0])
        for row in grid:
            if len(row) != width:
                raise ExprError("ExprError.ragged_matrix")
        if len(grid) > MAX_SIZE or width > MAX_SIZE:
            raise ExprError(f"ExprError.matrix_too_big:{MAX_SIZE}")

        # Validate every cell now, so errors surface at save time not at use time
        matrix_module.to_matrix(grid)

        self._items[name] = [[str(cell) for cell in row] for row in grid]
        self.save()
        return {"name": name, "rows": len(grid), "cols": width}

    def delete(self, name: str) -> bool:
        name = (name or "").strip().upper()
        if name in self._items:
            del self._items[name]
            self.save()
            return True
        return False

    def describe(self) -> list[dict]:
        """Summary for the carousel in the interface."""
        out = []
        for name in self.names():
            grid = self._items[name]
            out.append({
                "name": name,
                "rows": len(grid),
                "cols": len(grid[0]) if grid else 0,
                "grid": grid,
            })
        return out


registry = Registry()
