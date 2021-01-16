import collections
import json
import datetime
import traceback

import discord
import typing
from discord.ext import commands

from utils import context
from utils.config import Config
from utils.logger import FakeLogger
from utils.storage import Storage


async def get_prefix(bot: 'CustomBot', message: discord.Message):
    forced_prefixes = [";"]

    if not message.guild:
        return commands.when_mentioned_or(*forced_prefixes)(bot, message)

    prefix_set = ";"
    extras = [prefix_set] + forced_prefixes

    return commands.when_mentioned_or(*extras)(bot, message)


class CustomBot(commands.AutoShardedBot):
    def __init__(self, command_prefix: typing.Union[str, typing.Callable[[discord.Message], typing.Awaitable]] = None, **options):
        if not command_prefix:
            command_prefix = get_prefix

        super().__init__(command_prefix, **options)
        self.config = Config()
        self.logger = FakeLogger()
        self.db = Storage(self)
        self.commands_used = collections.Counter()

        with open("credentials.json", "r") as f:
            credentials = json.load(f)

        self.token = credentials["discord_token"]
        self.uptime = datetime.datetime.utcnow()
        self.loop.set_debug(True)

    async def on_message(self, message):
        if message.author.bot:
            return  # ignore messages from other bots

        ctx = await self.get_context(message, cls=context.CustomContext)
        if ctx.prefix is not None:
            await self.invoke(ctx)

    async def on_command(self, ctx):
        self.commands_used[ctx.command.name] += 1
        ctx.logger.info(f"<{ctx.author.name}> {ctx.message.clean_content}")

    async def on_ready(self):
        game = discord.Activity(type=discord.ActivityType.watching, name=self.user.name)
        await self.change_presence(status=discord.Status.online, activity=game)
        self.logger.info("We are all set, on_ready was fired! Yeah!")
        total_members = len(self.users)
        self.logger.info(f"I see {len(self.guilds)} guilds, and {total_members} members")
