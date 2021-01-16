# https://trombi.imtbs-tsp.eu/photo.php?uid=jovart_a&h=320&w=240

import typing

import aiohttp
import discord
from discord.ext import commands
from discord.ext.commands.cooldowns import BucketType
from utils.context import CustomContext

if typing.TYPE_CHECKING:
    from utils.bot import CustomBot


class Trombi(commands.Cog):
    """
    Recherches dans le trombi de l'école (grace au trombi de MiNet)
    """
    def __init__(self, bot: 'CustomBot'):
        self.bot = bot

    @commands.group(aliases=["t"])
    async def trombi(self, ctx: CustomContext):
        """
        Affichage de l'URL du trombi
        """
        if not ctx.invoked_subcommand:
            await ctx.send_to("Le trombi est disponible à l'adresse suivante : https://trombi.imtbs-tsp.eu/")

    @trombi.command(aliases=["s"])
    async def search(self, ctx: CustomContext, *, search_term:str):
        """
        Recherche d'une personne sur le trombi
        """
        #  https://trombi.minet.net/developer#people-search

        async with aiohttp.ClientSession() as session:
            async with session.get('https://trombi.minet.net/api/v1/people/search', params={"q": search_term, "type": "n"}) as resp:
                try:
                    users = await resp.json()
                except:
                    text = await resp.text()
                    self.bot.logger.exception(f"Erreur lors du chargement du trombi. Voici le HTML retourné par le serveur:\n{text}")
                    raise

        users_formatted = ["**Résultats de votre recherche :**\n"]
        for user in users['people']:
            out_year = user.get('year_out', '')
            if out_year is None:
                out_year = ''

            users_formatted.append(f"[{user['login']}] **{user['last_name']} {user['first_name']}** ({user['profession']}) - "
                                   f"{user['email']} {user['year_entrance']}-{out_year} <https://trombi.minet.net/pictures/{user['picture_src']}.jpg>")

        await ctx.send_to("\n".join(users_formatted))

        # https://trombi.minet.net/api/v1/people/search?q=jovart&type=n&page=1

    @trombi.command(aliases=["p"])
    async def photo(self, ctx: CustomContext, target_username: str = None):
        """
        Lien vers la photo d'un certain nom d'utilisateur. Vous devez etre connecté au CAS.
        """
        if target_username:
            await ctx.send_to(f"https://trombi.imtbs-tsp.eu/photo.php?uid={target_username}")
        elif await self.bot.db.has_profile(ctx.author):
            profile = await self.bot.db.get_profile(ctx.author)
            await ctx.send_to(f"Votre jolie photo : https://trombi.imtbs-tsp.eu/photo.php?uid={profile.tsp_user}")
        else:
            await ctx.send_to(f"Veuillez préciser un nom d'utilisateur...")


def setup(bot: 'CustomBot'):
    cog = Trombi(bot)
    bot.add_cog(cog)
