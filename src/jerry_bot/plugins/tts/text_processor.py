"""Text processing module for the Text-to-Speech Plugin."""


from collections.abc import Iterator
from typing import TypeVar

import regex as re

from .models.config import (
    TTSControlSignalRule,
    TTSNormalizeRuleConfig,
    TTSPluginConfig,
    TTSSoundboardRule,
)

R = TypeVar("R")
T = TypeVar("T")


class TextProcessor:
    """A class for processing text input for the Text-to-Speech Plugin."""

    def __init__(self, config: TTSPluginConfig):
        self.config = config

        self.patterns: dict[str, re.Pattern[str]] = {
            rule.pattern: re.compile(
                rule.pattern, (re.IGNORECASE if not rule.case_sensitive else 0)
            )
            for rule in self.config.text.normalize_rules
        }
        self.control_patterns: list[tuple[TTSControlSignalRule, re.Pattern[str]]] = [
            (
                rule,
                re.compile(
                    rule.pattern, (re.IGNORECASE if not rule.case_sensitive else 0)
                ),
            )
            for rule in self.config.text.control_rules
        ]
        self.soundboard_patterns: list[tuple[TTSSoundboardRule, re.Pattern[str]]] = [
            (
                rule,
                re.compile(
                    rule.pattern, (re.IGNORECASE if not rule.case_sensitive else 0)
                ),
            )
            for rule in self.config.text.soundboard_rules
        ]

        self.normalize_rules: dict[str, TTSNormalizeRuleConfig] = {
            rule.pattern: rule for rule in self.config.text.normalize_rules
        }

    def tokenize(
        self, text: str
    ) -> list[str | TTSControlSignalRule | TTSSoundboardRule]:
        """Split the input text based on control and soundboard rules, returning a list of text, control rules, and soundboard rules.

        Args:
            text (str): The input text to be split

        Returns:
            list[str | TTSControlSignalRule | TTSSoundboardRule]: The list of text, control rules, and soundboard rules.
        """

        tokenized: list[str | TTSControlSignalRule | TTSSoundboardRule] = [text]

        for rule, pattern in self.control_patterns + self.soundboard_patterns:
            tokenized = self._split_list(tokenized, pattern, rule)

        return tokenized

    def _split_list(
        self, input: list[str | T], pattern: re.Pattern, replacement: R
    ) -> list[str | T | R]:
        output = []
        for i in input:
            if isinstance(i, str):
                output.extend(self._split_and_interpolate(i, pattern, replacement))
            else:
                output.append(i)
        return output

    def _split_and_interpolate(
        self, text: str, pattern: re.Pattern, replacement: R
    ) -> Iterator[str | R]:
        split = pattern.split(text)

        iterator = iter(split)
        yield next(iterator)
        for item in iterator:
            yield replacement
            yield item

    def normalize(self, text: str) -> str:
        """Normalize the input text based on the configured normalization rules.

        Args:
            text (str): The input text to be normalized.

        Returns:
            str: The normalized text.
        """
        for rule, pattern in self.patterns.items():
            match = pattern.search(text)
            replacement = self.normalize_rules[rule].replacement
            if match:
                replacement = self.format_replacement(replacement, match)
            text = pattern.sub(replacement, text)

        return text

    def format_replacement(self, text: str, match: re.Match[str]) -> str:
        """Format the replacement string based on the matched regex groups.

        Args:
            text (str): The input text.
            match (re.Match): The regex match object.

        Returns:
            str: The formatted replacement string.
        """

        format_strings = {}

        if match.groups():
            for i, group in enumerate(match.groups()):
                format_strings[f"match_{i}"] = group
        format_strings["text"] = text
        format_strings["match"] = match.group()
        try:
            text = text.format(**format_strings)
        except KeyError:
            pass
        return text
