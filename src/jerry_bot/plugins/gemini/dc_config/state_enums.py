"""State Enums for the Gemini configuration menu"""

from enum import IntEnum


class UIState(IntEnum):
    """Enum representing the different states of the UI"""

    OVERVIEW = 1
    ERROR = 2


class LLMProfileTab(IntEnum):
    """Enum representing the different tabs in the LLM profile modal"""

    PROFILE = 1
    FAIL_OVER = 2
    DELETE = 3