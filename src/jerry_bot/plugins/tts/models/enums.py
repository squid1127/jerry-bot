"""Enums for tts plugin"""

from enum import Enum


class PrefixControlDirective(Enum):
    """
    Enum for prefix control directives.

    Attributes:
        STOP (str): Directive to clear playback queue
        SKIP (str): Directive to skip the current playback
        RAW (str): Directive to treat process proceeding content as raw text, bypassing normalization
        FAST (str): Directive to increase playback speed of proceeding content to 2x
    """

    STOP = "stop"
    SKIP = "skip"
    RAW = "raw"
    FAST = "fast"
