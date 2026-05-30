import discord
from squid_core.components.cli import CLIContext, EmbedLevel
import typing

if typing.TYPE_CHECKING:
    from .plugin import AutoReplyPlugin

from .ui import AutoReplyMainUI, AutoReplySearchUI, AutoReplyCLIHelpUI
from .models.db import AutoReplyRule
from .models.enums import ResponseMethod, ResponseType


async def handle_cli(plugin: "AutoReplyPlugin", ctx: CLIContext):
    """CLI logic for the AutoReply plugin."""
    if ctx.message is None:
        raise ValueError(
            "CLIContext message is None. This command must be invoked with a message context."
        )

    try:
        args = ctx.args or []
        match args:
            case ["-h" | "--help", *_]:
                ui = AutoReplyCLIHelpUI(ctx.message.reply)
                await ui.render()

            case ["-l" | "--list", *_]:
                ui = AutoReplySearchUI(
                    auto_reply=plugin.ar, message_method=ctx.message.reply
                )
                await ui.render()

            case ["-s" | "--search", *query_parts] if query_parts:
                query = " ".join(query_parts)
                ui = AutoReplySearchUI(
                    auto_reply=plugin.ar, message_method=ctx.message.reply, query=query
                )
                await ui.render()

            case ["-f" | "--reload", *_]:
                await plugin.ar.load_cache()
                await ctx.respond(
                    "AutoReply cache reloaded successfully.",
                    title="Reloaded",
                    level=EmbedLevel.SUCCESS,
                )

            case ["-r" | "--remove", rule_id_str, *_]:
                try:
                    rule_id = int(rule_id_str)
                except ValueError:
                    await ctx.respond(
                        "Invalid rule ID specified.",
                        title="Error",
                        level=EmbedLevel.ERROR,
                    )
                    return

                rule = await AutoReplyRule.get_or_none(id=rule_id)
                if not rule:
                    await ctx.respond(
                        f"No rule found with ID {rule_id}.",
                        title="Not Found",
                        level=EmbedLevel.WARNING,
                    )
                    return

                await rule.delete()
                await plugin.ar.load_cache()
                await ctx.respond(
                    f"Rule ID {rule_id} removed successfully.",
                    title="Removed",
                    level=EmbedLevel.SUCCESS,
                )

            case ["-t" | "--toggle", rule_id_str, *_]:
                try:
                    rule_id = int(rule_id_str)
                except ValueError:
                    await ctx.respond(
                        "Invalid rule ID specified.",
                        title="Error",
                        level=EmbedLevel.ERROR,
                    )
                    return

                rule = await AutoReplyRule.get_or_none(id=rule_id)
                if not rule:
                    await ctx.respond(
                        f"No rule found with ID {rule_id}.",
                        title="Not Found",
                        level=EmbedLevel.WARNING,
                    )
                    return

                rule.is_active = not rule.is_active
                await rule.save()
                await plugin.ar.load_cache()
                status = "activated" if rule.is_active else "deactivated"
                await ctx.respond(
                    f"Rule ID {rule_id} {status} successfully.",
                    title="Toggled",
                    level=EmbedLevel.SUCCESS,
                )

            case ["--super-stupid-dev-only-test-command", amount_str, *_]:
                try:
                    amount = int(amount_str)
                except ValueError:
                    await ctx.respond(
                        "Invalid amount specified.",
                        title="Error",
                        level=EmbedLevel.ERROR,
                    )
                    return
                for i in range(amount):
                    await AutoReplyRule(
                        name=f"Test Rule {i+1}",
                        trigger=f"^test-{i+1}$",
                        response_type=ResponseType.PLAIN,
                        response_method=ResponseMethod.REPLY,
                        response_payload=f"This is a test auto-reply #{i+1}",
                    ).save()
                await plugin.ar.load_cache()
                await ctx.respond(
                    "The deed is done",
                    title="Test Rules Created",
                    level=EmbedLevel.SUCCESS,
                )

            case []:
                # No arguments, open main UI
                ui = AutoReplyMainUI(
                    auto_reply=plugin.ar, message_method=ctx.message.reply
                )
                await ui.render()

            case _:
                # Unrecognized flag or just search terms
                query = " ".join(args)
                ui = AutoReplySearchUI(
                    auto_reply=plugin.ar, message_method=ctx.message.reply, query=query
                )
                await ui.render()

    except Exception as e:
        plugin.logger.exception(f"Error rendering AutoReply UI: {e}")
        await ctx.message.reply(
            embed=discord.Embed(
                title="Error",
                description="Failed to open AutoReply management interface. Please try again.",
                color=discord.Color.red(),
            )
        )
