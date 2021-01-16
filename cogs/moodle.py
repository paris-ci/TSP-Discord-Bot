import typing

import discord
from discord.ext import commands
from discord.ext.commands.cooldowns import BucketType
from utils.context import CustomContext

if typing.TYPE_CHECKING:
    from utils.bot import CustomBot

import asyncio
from asyncio.subprocess import PIPE, STDOUT


class Result:

    def __init__(self, status, stdout, stderr):
        self.status = status
        self._stdout = stdout or ""
        self._stderr = stderr or ""
        if stdout is not None:
            self.stdout = stdout.decode("utf-8")
        else:
            self.stdout = None
        if stderr is not None:
            self.stderr = stderr.decode("utf-8")
        else:
            self.stderr = None

    def __repr__(self):
        return f"<Result status={self.status} stdout={len(self._stdout)} stderr={len(self._stderr)}>"


async def run(shell_command, *args):
    p = await asyncio.create_subprocess_exec(shell_command, *args,
                                              stdin=PIPE, stdout=PIPE, stderr=STDOUT)
    stdout, stderr = await p.communicate()
    code = p.returncode
    return Result(code, stdout, stderr)


class Moodle(commands.Cog):
    """
    Ensemble des commandes sur vos profiles.
    """
    def __init__(self, bot: 'CustomBot'):
        self.bot = bot

    @commands.command(aliases=["bbbs"])
    async def bbb_slides(self, ctx: CustomContext, url:str):
        """
        Télécharge les slides d'une conference BBB
        """
        async with ctx.typing():
            r = await run("utils/download_slides_from_bigblue_button.sh", url)
        try:
            f = discord.File(str(r.stdout).splitlines()[-1])
            await ctx.send(file=f)
        except:
            ctx.logger.error("Failed to send a file, here is the output of the conversion script:")
            ctx.logger.error(r.stdout)
            ctx.logger.error(r.stderr)
            raise


def setup(bot: 'CustomBot'):
    cog = Moodle(bot)
    bot.add_cog(cog)
