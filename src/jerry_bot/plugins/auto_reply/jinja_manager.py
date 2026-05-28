"""Jinja2 manager for auto-reply rendering."""

import datetime
import math
import random
import re
import json
import yaml
from typing import Any

import asteval
import jinja2
from squid_core import Plugin


class JinjaManager:
    """Manages Jinja2 environment and template rendering."""

    def __init__(self, plugin: Plugin):
        self.plugin = plugin
        self.asteval_interpreters: dict[int, asteval.Interpreter] = {}
        self.jinja_env = self._create_jinja_environment()

    def _create_jinja_environment(self) -> jinja2.Environment:
        """Creates and configures the Jinja2 environment."""
        env = jinja2.Environment(
            loader=jinja2.BaseLoader(),
            enable_async=True,
            autoescape=False,
        )
        env.globals.update(self._make_globals())
        return env

    def _make_globals(self) -> dict:
        """Create global variables for Jinja2 templates."""

        def regex_match(pattern: str, string: str) -> bool:
            """Check if the regex pattern matches the string."""
            return re.search(pattern, string) is not None

        def ordinal(n: int) -> str:
            """Convert an integer to its ordinal representation."""
            suffix = ["th", "st", "nd", "rd"] + ["th"] * 6
            if 10 <= n % 100 <= 20:
                return f"{n}th"
            else:
                return f"{n}{suffix[n % 10]}"
            
        def yaml_load(s: str) -> Any:
            """Load a YAML string."""
            try:
                return yaml.safe_load(s)
            except yaml.YAMLError as e:
                raise ValueError(f"Error parsing YAML: {e}")
        def yaml_dump(data: Any) -> str:
            """Dump data to a YAML string."""
            try:
                return yaml.safe_dump(data)
            except yaml.YAMLError as e:
                raise ValueError(f"Error dumping YAML: {e}")
        def json_load(s: str) -> Any:
            """Load a JSON string."""
            try:
                return json.loads(s)
            except json.JSONDecodeError as e:
                raise ValueError(f"Error parsing JSON: {e}")
        def json_dump(data: Any) -> str:
            """Dump data to a JSON string."""
            try:
                return json.dumps(data, ensure_ascii=False)
            except (TypeError, ValueError) as e:
                raise ValueError(f"Error dumping JSON: {e}")

        bot = self.plugin.framework.bot.user
        now = datetime.datetime.now(datetime.timezone.utc)
        return {
            "bot": bot,
            "now": now,
            "utcnow": now,
            "math": math,
            "randint": random.randint,
            "randchoice": random.choice,
            "random": random,
            "regex_match": regex_match,
            "ordinal": ordinal,
            "asteval": self._asteval_eval,
            "asteval_safe": self._asteval_eval_safe,
            "yaml_load": yaml_load,
            "yaml_dump": yaml_dump,
            "json_load": json_load,
            "json_dump": json_dump,
        }

    def _get_asteval_interpreter(self, interpreter_id: int) -> asteval.Interpreter:
        """Get or create an asteval interpreter."""
        if interpreter_id not in self.asteval_interpreters:
            self.asteval_interpreters[interpreter_id] = asteval.Interpreter(
                use_numpy=True,
                builtins_readonly=True,
                config={"import": False},
            )
        return self.asteval_interpreters[interpreter_id]

    def _asteval_eval(self, expr: str, interpreter_id: int = 0) -> Any:
        """Evaluate a mathematical expression safely."""
        self.plugin.logger.info(
            f"Evaluating expression with asteval_eval: {expr} (interpreter_id: {interpreter_id})"
        )
        asteval_interpreter = self._get_asteval_interpreter(interpreter_id)

        try:
            result = asteval_interpreter(expr)
        except Exception as e:
            raise ValueError(f"Error evaluating expression: {e}")

        if asteval_interpreter.error:
            errors = [
                (
                    err.get_error()[1]
                    if isinstance(err.get_error(), tuple) and len(err.get_error()) >= 2
                    else str(err.get_error())
                )
                for err in asteval_interpreter.error
            ]
            raise ValueError(f"Error evaluating expression: {'; '.join(errors)}")

        return result

    def _asteval_eval_safe(self, expr: str, interpreter_id: int = 0) -> Any:
        """Evaluate a mathematical expression safely, returning error messages."""
        self.plugin.logger.info(
            f"Evaluating expression with asteval_eval_safe: {expr} (interpreter_id: {interpreter_id})"
        )
        asteval_interpreter = self._get_asteval_interpreter(interpreter_id)

        try:
            result = asteval_interpreter(expr)
        except Exception as e:
            return f"`Runtime error: {e}`"

        if asteval_interpreter.error:
            errors = [
                (
                    err.get_error()[1]
                    if isinstance(err.get_error(), tuple) and len(err.get_error()) >= 2
                    else str(err.get_error())
                )
                for err in asteval_interpreter.error
            ]
            return f"## Error\n```\n{'; '.join(errors)}\n```"

        return "👍" if result is None else result

    async def render(self, template_str: str, **context) -> str:
        """Render a Jinja2 template string with the provided context."""
        try:
            template = self.jinja_env.from_string(template_str)
            return await template.render_async(**context)
        except jinja2.TemplateError as e:
            self.plugin.logger.error(f"Jinja2 template rendering error: {e}")
            raise
        except Exception as e:
            self.plugin.logger.error(f"Unexpected error during Jinja2 rendering: {e}")
            raise
