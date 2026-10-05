"""Separate runnable notebook-source checks from clean-publication hygiene."""

from __future__ import annotations

import json
import re
from typing import Any


LOCAL_HOME_TOKEN = "/" + "Users" + "/"
CREDENTIAL_ASSIGNMENT = re.compile(
    r"(?i)(api[_-]?key|client[_-]?secret|password)\s*[=:]"
)


def notebook_source_text(document: dict[str, Any]) -> str:
    """Inspect code/markdown, excluding execution output and tracebacks."""
    sources = []
    for cell in document.get("cells", []):
        source = cell.get("source", "")
        sources.append(source if isinstance(source, str) else "".join(source))
    return "\n".join(sources)


def source_engineering_checks(document: dict[str, Any]) -> dict[str, bool]:
    cells = document.get("cells", [])
    ids = [cell.get("id") for cell in cells]
    valid_ids = bool(cells) and all(isinstance(item, str) and item for item in ids)
    unique_ids = valid_ids and len(ids) == len(set(ids))
    source = notebook_source_text(document)
    return {
        "nbformat major version": document.get("nbformat") == 4,
        "Unique non-empty cell IDs": bool(unique_ids),
        "No absolute local home path in source": LOCAL_HOME_TOKEN not in source,
        "No credential assignments in source": CREDENTIAL_ASSIGNMENT.search(source) is None,
    }


def publication_hygiene_checks(document: dict[str, Any]) -> dict[str, bool]:
    """Strict checks for an artifact to commit, not a live executed notebook."""
    code_cells = [cell for cell in document.get("cells", []) if cell.get("cell_type") == "code"]
    serialized = json.dumps(document, ensure_ascii=False)
    return {
        "Stored outputs equal zero": all(not cell.get("outputs", []) for cell in code_cells),
        "Non-null execution counts equal zero": all(
            cell.get("execution_count") is None for cell in code_cells
        ),
        "No absolute local home path in published file": LOCAL_HOME_TOKEN not in serialized,
        "No credential assignments in published file": CREDENTIAL_ASSIGNMENT.search(serialized) is None,
    }
