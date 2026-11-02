"""Safe `{{variable}}` substitution. Deliberately not Jinja: no expressions, no code execution."""
from __future__ import annotations

import re

VAR_RE = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}")


class TemplateError(ValueError):
    pass


def extract_variables(*texts: str) -> list[str]:
    """Variable names in order of first appearance across ``texts``."""
    seen: dict[str, None] = {}
    for text in texts:
        for match in VAR_RE.finditer(text or ""):
            seen.setdefault(match.group(1), None)
    return list(seen)


def render(template: str, values: dict[str, str], *, strict: bool = True) -> str:
    """Replace each ``{{name}}``. Missing names raise in strict mode, otherwise stay as written."""
    missing = [name for name in extract_variables(template) if name not in values]
    if missing and strict:
        raise TemplateError("Missing values for variables: " + ", ".join(missing))

    def sub(match: re.Match) -> str:
        name = match.group(1)
        return str(values[name]) if name in values else match.group(0)

    # Single pass: substituted values are never re-scanned, so a value can't inject another variable.
    return VAR_RE.sub(sub, template)


def merge_values(defaults: dict[str, str] | None, *overrides: dict[str, str] | None) -> dict[str, str]:
    """Defaults first, then each override layer; empty-string overrides are kept (they are intentional)."""
    merged: dict[str, str] = {str(k): str(v) for k, v in (defaults or {}).items()}
    for layer in overrides:
        for key, value in (layer or {}).items():
            merged[str(key)] = str(value)
    return merged
