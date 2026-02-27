"""Detect naming patterns and generate anonymized replacements."""

from __future__ import annotations

import enum
import random

from word_pool import ALL_WORDS


class CasePattern(enum.Enum):
    CAMEL = "CamelCase"
    UPPER_SNAKE = "UPPER_SNAKE"
    LOWER_SNAKE = "lower_snake"
    PLAIN = "plain"


def detect_case_pattern(name: str) -> CasePattern:
    """Detect the casing convention of an identifier."""
    if "_" in name:
        if name == name.upper():
            return CasePattern.UPPER_SNAKE
        return CasePattern.LOWER_SNAKE
    # No underscores — check for mixed case
    if any(c.isupper() for c in name) and any(c.islower() for c in name):
        return CasePattern.CAMEL
    if name == name.upper() and len(name) > 1:
        return CasePattern.UPPER_SNAKE
    return CasePattern.PLAIN if name == name.lower() else CasePattern.CAMEL


class NameGenerator:
    """Generate unique anonymized names from the word pool."""

    def __init__(self, seed: int | None = None):
        self._rng = random.Random(seed)
        self._counter = 0
        self._used: set[str] = set()

    def generate(self, pattern: CasePattern) -> str:
        """Generate a unique name matching the given case pattern."""
        while True:
            w1 = self._rng.choice(ALL_WORDS)
            w2 = self._rng.choice(ALL_WORDS)
            self._counter += 1
            suffix = str(self._counter)

            if pattern == CasePattern.CAMEL:
                name = w1.capitalize() + w2.capitalize() + suffix
            elif pattern == CasePattern.UPPER_SNAKE:
                name = w1.upper() + "_" + w2.upper() + "_" + suffix
            elif pattern == CasePattern.LOWER_SNAKE:
                name = w1 + "_" + w2 + "_" + suffix
            else:  # PLAIN
                name = w1 + suffix

            if name not in self._used:
                self._used.add(name)
                return name
