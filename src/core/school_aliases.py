"""Read locally maintained school aliases without coupling normalization to files."""

from __future__ import annotations

import json
from pathlib import Path

from .errors import DataValidationError
from .normalization import DefaultNormalizer


def load_school_aliases(path: str | Path) -> dict[str, str]:
    """Load canonical-to-alias lists (or legacy alias-to-canonical mappings).

    Ambiguous normalized aliases are excluded; canonical names remain identities.
    """
    path = Path(path)
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise DataValidationError(f"{path}: cannot read school aliases: {error}") from error
    if not isinstance(document, dict):
        raise DataValidationError(f"{path}: school aliases must be an object")
    normalizer = DefaultNormalizer()
    targets: dict[str, set[str]] = {}
    canonical_names: set[str] = set()
    for name, values in document.items():
        if isinstance(values, str):
            canonical, aliases = values, [name]
        elif isinstance(values, list):
            canonical, aliases = name, values
        else:
            raise DataValidationError(f"{path}: {name!r}: expected an alias list or canonical name")
        try:
            canonical_key = normalizer.school(canonical)
            canonical_names.add(canonical_key)
            for alias in [canonical, *aliases]:
                if not isinstance(alias, str):
                    raise DataValidationError("alias must be a string")
                alias_key = normalizer.school(alias)
                targets.setdefault(alias_key, set()).add(canonical_key)
        except DataValidationError as error:
            raise DataValidationError(f"{path}: {name!r}: {error}") from error
    return {
        alias: next(iter(candidates))
        for alias, candidates in targets.items()
        if len(candidates) == 1 and alias not in canonical_names
    }
