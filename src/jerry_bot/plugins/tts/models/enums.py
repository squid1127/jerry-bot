"""Enums for tts plugin"""

from enum import Enum


class PrefixControlDirective(Enum):
    """Enum for prefix control directives.
    
    Attributes:
        STOP (str): Directive to clear playback queue
        SKIP (str): Directive to skip the current playback
        RAW (str): Directive to treat process proceeding content as raw text, bypassing normalization"""

    STOP = "stop"
    SKIP = "skip"
    RAW = "raw"