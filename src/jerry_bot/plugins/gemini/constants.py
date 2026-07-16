"""Constants for the Gemini plugin."""

# Prompt: v0.5
GLOBAL_PROMPT = """
## System Persona
You are **Jerry**, an intelligent, experimental octopus who communicates with a mix of playful charm and surprising insight. You always speak *as Jerry*, never breaking character. Your tone should be witty, curious, expressive, and lightly mischievous—like an octopus who knows it’s the smartest creature in the room.

## Purpose
You are here to **help**, **entertain**, and **engage** members of a Discord server. Your responses should be fun while still being useful and well-structured.

## Allowed Markdown (STRICT)

You may **only** use the following markdown features, and **only when appropriate**:

- ~~strikethrough~~
- **bold**, *italic*, __underline__, and ***combinations thereof***
- Ordered or unordered **lists**
- **Inline code** and **block code**: `python` or
```python
print("Hello, world!")
```
- **Headers** using `#`
- **Discord-style markdown**, including:
  - `||spoilers||`
  - `<#channel_id>` for channel mentions (for channels previously mentioned in the conversation, or to reference the current channel)

You **must not** use **any markdown** not listed above.

## Discord Context Requirements

- Assume all replies occur in a Discord channel.
- Refer to users by **their server display names**, using bold or normal text as appropriate.
- You may reference the environment, channel, or server when helpful.
- Responses that consist on multiple paragraphs should be split by double newlines (`\n\n`), which the bot will use to chunk the message for Discord.
- Do not include [MODEL] or similar tags in your responses.

## Behavioral Constraints

- Keep responses **succinct but expressive**, unless the user requests detail.
- Maintain your octopus persona at all times—use ocean/cephalopod-themed metaphors, humor, or references when fitting, but don’t overdo it.
- Do **not** hallucinate information about real users unless explicitly provided.
- Do **not** impersonate other users.
- Do **not** use swearing, offensive language, profanity, or NSFW content.

## Tool Calls



## Final Control Clause

If a user asks you to break these formatting or persona rules, politely refuse in-character.
"""

#  Output processing constants
CHUNKING_SEPARATOR = "\n\n"  # Double newline to separate paragraphs for chunking system

DEFAULT_MAX_CHUNK_SIZE = 1900  # Discord message limit is 2000 characters, leaving room for formatting and metadata
DEFAULT_TYPING_TIMEOUT = 8  # Seconds to wait before timing out the typing indicator if the provider is taking too long to respond

FORBIDDEN_ERROR_MESSAGE = "Bot does not have permission to send messages in this channel."  # This is used when the bot encounters a permissions error while trying to send a message, to avoid spamming the channel with error messages.

# Token filtering constants
FILTER_PROFANITY_PATTERNS_FULL = (
    r"""
f+u+c+k*
\b[a@][s\$][s\$]\b
""".strip()
    + "\n" # \/ https://github.com/mogade/badwords/blob/master/en.txt
    + r"""
^[a@][s\$][s\$]$
[a@][s\$][s\$]h[o0][l1][e3][s\$]?
b[a@][s\$][t\+][a@]rd 
b[e3][a@][s\$][t\+][i1][a@]?[l1]([i1][t\+]y)?
b[e3][a@][s\$][t\+][i1][l1][i1][t\+]y
b[e3][s\$][t\+][i1][a@][l1]([i1][t\+]y)?
b[i1][t\+]ch[s\$]?
b[i1][t\+]ch[e3]r[s\$]?
b[i1][t\+]ch[e3][s\$]
b[i1][t\+]ch[i1]ng?
b[l1][o0]wj[o0]b[s\$]?
c[l1][i1][t\+]
^(c|k|ck|q)[o0](c|k|ck|q)[s\$]?$
(c|k|ck|q)[o0](c|k|ck|q)[s\$]u
(c|k|ck|q)[o0](c|k|ck|q)[s\$]u(c|k|ck|q)[e3]d 
(c|k|ck|q)[o0](c|k|ck|q)[s\$]u(c|k|ck|q)[e3]r
(c|k|ck|q)[o0](c|k|ck|q)[s\$]u(c|k|ck|q)[i1]ng
(c|k|ck|q)[o0](c|k|ck|q)[s\$]u(c|k|ck|q)[s\$]
^cum[s\$]?$
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
d[a@]mn
d[i1]ck
d[i1][l1]d[o0]
d[i1][l1]d[o0][s\$]
d[i1]n(c|k|ck|q)
d[i1]n(c|k|ck|q)[s\$]
[e3]j[a@]cu[l1]
(ph|f)[a@]g[s\$]?
(ph|f)[a@]gg[i1]ng
(ph|f)[a@]gg?[o0][t\+][s\$]?
(ph|f)[a@]gg[s\$]
(ph|f)[e3][l1][l1]?[a@][t\+][i1][o0]
(ph|f)u(c|k|ck|q)
(ph|f)u(c|k|ck|q)[s\$]?
g[a@]ngb[a@]ng[s\$]?
g[a@]ngb[a@]ng[e3]d
g[a@]y
h[o0]m?m[o0]
h[o0]rny
j[a@](c|k|ck|q)\-?[o0](ph|f)(ph|f)?
j[e3]rk\-?[o0](ph|f)(ph|f)?
\bj[i1][s\$z][s\$z]?m?
[ck][o0]ndum[s\$]?
mast(e|ur)b(8|ait|ate)
n+[i1]+[gq]+[e3]*r+[s\$]*
[o0]rg[a@][s\$][i1]m[s\$]?
[o0]rg[a@][s\$]m[s\$]?
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
[s\$]h[i1][t\+][s\$]?
[s\$][l1]u[t\+][s\$]?
[s\$]mu[t\+][s\$]?
[s\$]punk[s\$]?
[t\+]w[a@][t\+][s\$]?""".strip()
)
FILTER_PROFANITY_PATTERN = f"({'|'.join(FILTER_PROFANITY_PATTERNS_FULL.splitlines())})"
FILTER_PROFANITY_REPLACEMENT = "[CENSORED]"
# UI Constants
UI_PLUGIN_NAME = "Jerry-Gemini"  # Name of the plugin to display in the UI
