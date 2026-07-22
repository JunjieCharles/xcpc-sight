from __future__ import annotations

import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass, field

from opencc import OpenCC

from .errors import DataValidationError
from .models import CompetitorId


def _letters_and_numbers(value: str) -> str:
    return "".join(character for character in value if unicodedata.category(character)[0] in "LN")


@dataclass(slots=True)
class DefaultNormalizer:
    school_aliases: Mapping[str, str] = field(default_factory=dict)
    member_aliases: Mapping[str, str] = field(default_factory=dict)
    _converter: OpenCC = field(init=False, repr=False)
    _normalized_school_aliases: dict[str, str] = field(init=False, repr=False)
    _normalized_member_aliases: dict[str, str] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._converter = OpenCC("t2s")
        self._normalized_school_aliases = {
            self._normalize(alias): self._normalize(canonical)
            for alias, canonical in self.school_aliases.items()
        }
        self._normalized_member_aliases = {
            self._normalize(alias): self._normalize(canonical)
            for alias, canonical in self.member_aliases.items()
        }

    def _normalize(self, value: str) -> str:
        normalized = unicodedata.normalize("NFKC", str(value)).strip()
        normalized = self._converter.convert(normalized).casefold()
        return _letters_and_numbers(normalized)

    def school(self, value: str) -> str:
        normalized = self._normalize(value).replace("非独立法人", "")
        normalized = self._normalized_school_aliases.get(normalized, normalized)
        if not normalized:
            raise DataValidationError("school name normalizes to an empty identity")
        return normalized

    def member(self, value: str) -> str:
        normalized = self._normalize(value)
        normalized = self._normalized_member_aliases.get(normalized, normalized)
        if not normalized:
            raise DataValidationError("member name normalizes to an empty identity")
        return normalized

    def competitor(self, school: str, member: str) -> CompetitorId:
        return CompetitorId(self.school(school), self.member(member))


def is_coach_name(value: str) -> bool:
    normalized = unicodedata.normalize("NFKC", value).strip().casefold()
    for suffix in ("(教练)", "（教练）", "教练", "(coach)", "coach"):
        if normalized.endswith(suffix.casefold()):
            return True
    return False
