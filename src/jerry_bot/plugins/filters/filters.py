"""Collection of text filtering lists, compiled into regex.

Attributes:
    PATTERNS (dict): A dictionary of filter levels and their corresponding regex patterns.
"""

import re
from enum import IntEnum


class FilterLevel(IntEnum):
    """
    Enum for filter levels. Each level inherits from all levels greater than it. Therefore, the lower the number, the stricter the filter.

    Attributes:
        EVERYTHING (int): (0) Base level for all content.
        USELESS (int): (10) Doesn't make sense.
        MILD (int): (20) Damn
        SWEARS (int): (30) F***
        SEXUAL (int): (40) Sexual content
        SLURS (int): (50) Racial slurs
    """

    EVERYTHING = 0
    USELESS = 10
    MILD = 20
    SWEARS = 30
    SEXUAL = 40
    SLURS = 50


PATTERNS = {
    FilterLevel.USELESS: r"""

h[o0]m?m[o0]
[t\+]w[a@][t\+][s\$]?

""".strip(),
    FilterLevel.MILD: r"""
    
d[a@]mn
[a@][s\$][s\$]+
[a@][s\$][s\$]h[o0][l1][e3][s\$]?

""".strip(),
    FilterLevel.SWEARS: r"""
f+u+c+k*
(ph|f)[e3][l1][l1]?[a@][t\+][i1][o0]
(ph|f)u(c|k|ck|q)
(ph|f)u(c|k|ck|q)[s\$]?
b[a@][s\$][t\+][a@]rd 
b[e3][a@][s\$][t\+][i1][a@]?[l1]([i1][t\+]y)?
b[e3][a@][s\$][t\+][i1][l1][i1][t\+]y
b[e3][s\$][t\+][i1][a@][l1]([i1][t\+]y)?
b[i1][t\+]ch[s\$]?
b[i1][t\+]ch[e3]r[s\$]?
b[i1][t\+]ch[e3][s\$]
b[i1][t\+]ch[i1]ng?
[s\$]h[i1][t\+][s\$]?

""".strip(),
    FilterLevel.SEXUAL: r"""

b[l1][o0]wj[o0]b[s\$]?
c[l1][i1][t\+]
(c|k|ck|q)[o0](c|k|ck|q)[s\$]?
(c|k|ck|q)[o0](c|k|ck|q)[s\$]u
(c|k|ck|q)[o0](c|k|ck|q)[s\$]u(c|k|ck|q)[e3]d 
(c|k|ck|q)[o0](c|k|ck|q)[s\$]u(c|k|ck|q)[e3]r
(c|k|ck|q)[o0](c|k|ck|q)[s\$]u(c|k|ck|q)[i1]ng
(c|k|ck|q)[o0](c|k|ck|q)[s\$]u(c|k|ck|q)[s\$]
cum[s\$]?
cumm??[e3]r
cumm?[i1]ngcock
(c|k|ck|q)um[s\$]h[o0][t\+]
(c|k|ck|q)un[i1][l1][i1]ngu[s\$]
(c|k|ck|q)un[i1][l1][l1][i1]ngu[s\$]
(c|k|ck|q)unn[i1][l1][i1]ngu[s\$]
(c|k|ck|q)un[t\+][s\$]?
(c|k|ck|q)un[t\+][l1][i1](c|k|ck|q)
(c|k|ck|q)un[t\+][l1][i1](c|k|ck|q)[e3]r
(c|k|ck|q)un[t\+][l1][i1](c|k|ck|q)[i1]ng
cyb[e3]r(ph|f)u(c|k|ck|q)
d[i1]ck
d[i1][l1]d[o0]
d[i1][l1]d[o0][s\$]
d[i1]n(c|k|ck|q)
d[i1]n(c|k|ck|q)[s\$]
[e3]j[a@]cu[l1]
p[e3]nn?[i1][s\$]
p[i1][s\$][s\$]
p[i1][s\$][s\$][o0](ph|f)(ph|f) 
p[o0]rn
p[o0]rn[o0][s\$]?
p[o0]rn[o0]gr[a@]phy
pr[i1]ck[s\$]?
pu[s\$][s\$][i1][e3][s\$]
pu[s\$][s\$]y[s\$]?
[s\$][e3]x
[o0]rg[a@][s\$][i1]m[s\$]?
[o0]rg[a@][s\$]m[s\$]?
h[o0]rny
[s\$]punk[s\$]?
mast(e|ur)b(8|ait|ate)
[ck][o0]ndum[s\$]?
j[e3]rk\-?[o0](ph|f)(ph|f)?
j[i1][s\$z][s\$z]?m?
g[a@]ngb[a@]ng[s\$]?
g[a@]ngb[a@]ng[e3]d
[s\$][l1]u[t\+][s\$]?
[s\$]mu[t\+][s\$]?
j[a@](c|k|ck|q)\-?[o0](ph|f)(ph|f)?

""".strip(),
    FilterLevel.SLURS: r"""
    
(ph|f)[a@]g[s\$]?
(ph|f)[a@]gg[i1]ng
(ph|f)[a@]gg?[o0][t\+][s\$]?
(ph|f)[a@]gg[s\$]
n+[i1]+[gq]+[gq]+[e3]*r+[s\$]*
n+[i1]+[gq]+[gq]+[e3]*a+
""",
}


def get_filter_regex(level: FilterLevel) -> re.Pattern[str]:
    """Get the regex pattern for a given filter level."""
    patterns = []
    for lvl in FilterLevel:
        if lvl >= level and lvl in PATTERNS:
            patterns.append(PATTERNS[lvl])
    return generate_regex("\n".join(patterns))


def generate_regex(patterns: str, word_bounded: bool = True) -> re.Pattern[str]:
    """Generate a regex pattern from a string of newline-separated patterns, where each line is represents one pattern. The resulting regex will match any of the patterns as whole words, case-insensitively."""
    base_pattern = r"(?:{})"
    if word_bounded:
        base_pattern = r"\b(?:{})\b"

    return re.compile(
        base_pattern.format(
            "|".join(line.strip() for line in patterns.splitlines() if line.strip())
        ),
        re.IGNORECASE,
    )


def interactive_test() -> None:
    """Interactive test for the filter regex."""
    levels = {lvl.name: lvl for lvl in FilterLevel}
    print(f"Available filter levels: {', '.join(levels.keys())}")
    level_input = input("Enter a filter level: ").strip().upper()
    if level_input not in levels:
        print(f"Invalid filter level: {level_input}")
        return
    level = levels[level_input]
    pattern = get_filter_regex(level)
    print(f"Regex for level {level.name}: {pattern.pattern}")
    while True:
        text = input("Enter text to test (or 'exit' to quit): ")
        if text.lower() == "exit":
            break
        match = pattern.search(text)
        if match:
            print(f"Match found: {match.group(0)}")
        else:
            print("No match found.")


if __name__ == "__main__":
    interactive_test()
