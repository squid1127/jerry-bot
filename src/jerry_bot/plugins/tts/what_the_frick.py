"""Completely unrelated file that makes output that completely breaks the tts system."""

import argparse
import random

chars = r"""{}|?,.[]();:"'"""


def garbled_nonsense(length: int = 100) -> str:
    """Generate a random string of garbled nonsense characters.

    Args:
        length (int): The length of the string to generate. Defaults to 100.

    Returns:
        str: A random string of garbled nonsense characters.
    """
    return "".join(random.choice(chars) for _ in range(length))


def main():
    parser = argparse.ArgumentParser(description="Generate garbled nonsense.")
    parser.add_argument(
        "-l", "--length", type=int, default=100, help="Length of the string to generate"
    )
    args = parser.parse_args()

    print(garbled_nonsense(args.length))


if __name__ == "__main__":
    main()
