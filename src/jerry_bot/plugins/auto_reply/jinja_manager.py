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

from .globals import GLOBALS, GLOBALS_USER_ASTEVAL, global_method


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

        base_globals = GLOBALS.copy()
        base_globals.update(
            {
                "asteval": self._user_asteval_eval,
                "asteval_safe": self._user_asteval_eval_safe,
            }
        )
        return base_globals

    def _get_asteval_interpreter(self, interpreter_id: int) -> asteval.Interpreter:
        """Get or create an asteval interpreter."""
        if interpreter_id not in self.asteval_interpreters:
            self.asteval_interpreters[interpreter_id] = asteval.Interpreter(
                symtable=GLOBALS_USER_ASTEVAL.copy(),
                use_numpy=True,
                builtins_readonly=True,
                config={"import": False},
            )
        return self.asteval_interpreters[interpreter_id]

    @global_method(
        doc="Evaluate a mathematical expression safely. (str, int) -> Any", skip=True
    )
    def _user_asteval_eval(self, expr: str, interpreter_id: int = 0) -> Any:
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

    @global_method(
        doc="Evaluate a mathematical expression safely, returning error messages. (str, int) -> Any",
        skip=True,
    )
    def _user_asteval_eval_safe(self, expr: str, interpreter_id: int = 0) -> Any:
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
            return f"```\n{'; '.join(errors)}\n```\n-# This function evaluates python code. Use `help()` to see available globals and their descriptions."

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

    async def render_asteval(self, expr: str, **context) -> Any:
        """Evaluate a Python expression using the asteval library."""
        try:
            interpreter = asteval.Interpreter(
                user_symbols=context,
                use_numpy=True,
                builtins_readonly=True,
                config={"import": False},
            )
            return interpreter(expr)
        except Exception as e:
            self.plugin.logger.error(f"Error evaluating asteval expression: {e}")
            raise

    def help(self) -> str:
        """Return a help message listing available global functions."""
        output = "Available global methods:\n"
        if not self.jinja_env.globals:
            return "No available methods."
        for name, func in self.jinja_env.globals.items():
            output += f"- `{name}`{' - ' + func._help_doc if hasattr(func, '_help_doc') and func._help_doc else ''}\n"
        return output
