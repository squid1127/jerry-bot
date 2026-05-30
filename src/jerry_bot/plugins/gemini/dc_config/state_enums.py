"""State Enums for the Gemini configuration menu"""

from enum import Enum


class UIState(Enum):
    """Enum representing the different states of the UI"""

    OVERVIEW = 1
    ERROR = 2


class LLMProfileTab(Enum):
    """Enum representing the different tabs in the LLM profile modal"""

    PROFILE = 1
    FAIL_OVER = 2
