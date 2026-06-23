"""Globals for jinja2 and asteval."""

import json
import yaml
from typing import Any
import random
import time
import regex as re
from tabulate import tabulate

GLOBALS: dict[str, Any] = {}
GLOBALS_USER_ASTEVAL: dict[str, Any] = {}


# * Main Decorator
def global_method(
    name: str | None = None,
    doc: str | None = None,
    user_asteval_only: bool = False,
    skip: bool = False,
) -> Any:
    """
    Decorator to add global functions to both Jinja2 and asteval, with optional help documentation.
    """

    def decorator(func) -> Any:
        if name:
            func.__name__ = name
        if doc:
            func._help_doc = doc
        if not skip:
            if not user_asteval_only:
                GLOBALS[name or func.__name__] = func
            GLOBALS_USER_ASTEVAL[name or func.__name__] = func
        return func

    return decorator


# * Global functions for Jinja2 templates and asteval expressions.


@global_method(name="from_yaml", doc="Load YAML from a string. (str) -> Any")
def yaml_load(s: str) -> Any:
    return yaml.safe_load(s)


@global_method(name="yaml", doc="Dump data to a YAML string. (Any) -> str")
def yaml_dump(data: Any) -> str:
    return yaml.safe_dump(data)


@global_method(name="from_json", doc="Load JSON from a string. (str) -> Any")
def json_load(s: str) -> Any:
    return json.loads(s)


@global_method(name="json", doc="Dump data to a JSON string. (Any) -> str")
def json_dump(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False)


@global_method(name="randint", doc="Get a random integer. (int, int) -> int")
def randint(a: int, b: int) -> int:
    return random.randint(a, b)


@global_method(name="choice", doc="Choose a random element from a list. (list) -> Any")
def choice(seq: list) -> Any:
    return random.choice(seq)


@global_method(name="random", doc="Get a random float between 0 and 1. () -> float")
def randomfloat() -> float:
    return random.random()


@global_method(name="time", doc="Get the current time. () -> float")
def current_time() -> float:
    return time.time()


@global_method(name="ftime", doc="Get the current time as a string. (str) | () -> str")
def formatted_time(format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
    return time.strftime(format_str, time.localtime())


@global_method(name="weekday", doc="Get the current day of the week. () -> str")
def current_weekday() -> str:
    return formatted_time("%A")


@global_method(doc="Ordinal function. (int) -> str")
def ordinal(n: int) -> str:
    suffix = ["th", "st", "nd", "rd"] + ["th"] * 6
    if 10 <= n % 100 <= 20:
        return f"{n}th"
    else:
        return f"{n}{suffix[n % 10]}"


@global_method(doc="Check if a string matches a regex pattern. (str, str) -> bool")
def regex_match(pattern: str, string: str) -> bool:
    return re.search(pattern, string) is not None


@global_method(
    doc="Search for a regex pattern in a string. (str, str) -> tuple[str, ...] | None"
)
def regex_search(pattern: str, string: str) -> tuple[str, ...] | None:
    match = re.search(pattern, string)
    if match:
        return match.groups()
    return None


@global_method(
    doc="Find all non-overlapping matches of a regex pattern in a string. (str, str) -> list[str]"
)
def regex_findall(pattern: str, string: str) -> list[str]:
    return re.findall(pattern, string)


@global_method(
    doc="Replace all occurrences of a regex pattern in a string with a replacement string. (str, str, str) -> str"
)
def regex_sub(pattern: str, replacement: str, string: str) -> str:
    return re.sub(pattern, replacement, string)


@global_method(doc="Split a string by a regex pattern. (str, str) -> list[str]")
def regex_split(pattern: str, string: str) -> list[str]:
    return re.split(pattern, string)


@global_method(doc="Convert input to a markdown code block. (str, str | None) -> str")
def code_block(content: str, language: str | None = None) -> str:
    if language:
        return f"```{language}\n{content}\n```"
    else:
        return f"```\n{content}\n```"


@global_method(
    doc="Create a table from a list of lists. (list[list], list[str], str | None) -> str"
)
def table(data: list[list], headers: list[str], tablefmt: str | None = None) -> str:
    return tabulate(data, headers=headers, tablefmt=tablefmt or "pipe")


@global_method(
    doc="Convert a list of dictionaries to a table format, which can be passed into the `table` function. (list[dict]) -> tuple[list[tuple], list[str]]"
)
def dict_table(records: list[dict]) -> tuple[list[tuple], list[str]]:
    headers = list(dict.fromkeys(k for r in records for k in r))
    rows = [tuple(r.get(h, "") for h in headers) for r in records]
    return rows, headers


# * Asteval-only functions


@global_method(
    name="range",
    doc="Generate a list of numbers using range. (*int) -> list",
    user_asteval_only=True,
)
def range_list(*args, **kwargs) -> list:
    return list(range(*args, **kwargs))


@global_method(
    name="zip",
    doc="Zip multiple lists together. (*list) -> list",
    user_asteval_only=True,
)
def zip_list(*args) -> list:
    return list(zip(*args))


# * Constants

weekdays = (
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
)

# Add constants to globals
GLOBALS.update({"weekdays": weekdays})
GLOBALS_USER_ASTEVAL.update(
    {"str": str, "int": int, "float": float, "bool": bool, "weekdays": weekdays}
)


# * Help method
@global_method(doc="This help message. () -> str", user_asteval_only=True)
def help():
    output = "**Available methods:**\n"
    for name, func in GLOBALS_USER_ASTEVAL.items():
        output += f"- `{name}`{' - ' + func._help_doc if hasattr(func, '_help_doc') and func._help_doc else ''}\n"
    return output
