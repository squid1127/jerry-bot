"""Text processing module for the Text-to-Speech Plugin."""

import regex as re

from .models.config import TTSNormalizeRuleConfig, TTSPluginConfig


class TextProcessor:
    """A class for processing text input for the Text-to-Speech Plugin."""

    def __init__(self, config: TTSPluginConfig):
        self.config = config

        self.patterns: dict[str, re.Pattern[str]] = {
            rule.pattern: re.compile(
                rule.pattern, (re.IGNORECASE if not rule.case_sensitive else 0)
            )
            for rule in self.config.normalize_rules
        }
        self.normalize_rules: dict[str, TTSNormalizeRuleConfig] = {
            rule.pattern: rule for rule in self.config.normalize_rules
        }

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
