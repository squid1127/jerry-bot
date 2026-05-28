"""Enumeration types for AutoReply Plugin"""

from enum import IntEnum, auto


class ResponseType(IntEnum):
    """Enumeration for different types of auto-reply responses."""

    PLAIN = auto()
    RANDOM_YAML = auto()
    TEMPLATE = auto()


class ResponseMethod(IntEnum):
    """Enumeration for different methods of responding to messages."""

    REPLY = auto()
    SEND_MESSAGE = auto()
    SEND_AND_DELETE = auto()
    DM = auto()
    REPLY_ORIGINAL = auto()
    LOG = auto()
    REACTION = auto()


class IgnoreType(IntEnum):
    """Enumeration for different types of ignore rules."""

    USER = auto()
    CHANNEL = auto()
    GUILD = auto()
    ROLE = auto()


if __name__ == "__main__":
    # Print all enum members for testing purposes
    print("Response Types:")
    for response in ResponseType:
        print(f"{response.name} = {response.value}")

    print("\nIgnore Types:")
    for ignore in IgnoreType:
        print(f"{ignore.name} = {ignore.value}")
