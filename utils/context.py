import io
import logging
import typing

import discord
from discord import Message

from utils.logger import LoggerConstant
from discord.ext import commands
from discord.errors import InvalidArgument

if typing.TYPE_CHECKING:
    from utils.bot import CustomBot  # Good hack 👌


class CustomContext(commands.Context):
    bot: 'CustomBot'

    def __init__(self, **attrs):
        super().__init__(**attrs)
        self.logger = LoggerConstant(self.bot.logger, self.guild, self.channel, self.author)

    async def send_to(self, message: str, user: typing.Optional[discord.User] = None, **kwargs):
        if user is None:
            user = self.author

        message = f"{user.mention} > {message}"

        await self.send(message, **kwargs)

    async def send(self, content=None, *, file=None, files=None, **kwargs) -> Message:
        # Case for a too-big message
        if content and len(content) > 1990:
            self.logger.warning("Message content is too big to be sent, putting in a text file for sending.")

            message_file = discord.File(io.BytesIO(content.encode()), filename="message.txt")
            content = None

            if file is not None and files is not None:
                raise InvalidArgument('Cannot pass both file and files parameter to send()')
            elif file is not None:
                files = [message_file, file]
                file = None
            elif files is not None:
                if len(files) == 10:
                    raise InvalidArgument('Content is too big, and too many files were provided')
                else:
                    files = [message_file] + files
            else:
                file = message_file

        message = await super().send(content, file=file, files=files, **kwargs)

        return message
