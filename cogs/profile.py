import asyncio
import typing

import discord
import ldap3
from discord.ext import commands
from discord.ext.commands.cooldowns import BucketType
from ldap3 import Connection

from utils.context import CustomContext

if typing.TYPE_CHECKING:
    from utils.bot import CustomBot

LDAP_SERVER = "127.0.0.1"
server = ldap3.Server(LDAP_SERVER, use_ssl=False)


def get_login_info(email_or_login):
    conn = Connection(server, auto_bind=True)
    if "@" in email_or_login:
        conn.search(u'ou=People,dc=int-evry,dc=fr', u"(mail={})".format(email_or_login), ldap3.SUBTREE, attributes=ldap3.ALL_ATTRIBUTES)
    else:
        conn.search(u'ou=People,dc=int-evry,dc=fr', u"(uid={})".format(email_or_login), ldap3.SUBTREE, attributes=ldap3.ALL_ATTRIBUTES)
    try:
        res = conn.entries[0]
    except IndexError:
        return None

    return {"mail": str(res["mail"]), "display_name": str(res["givenName"]) + " " + str(res["sn"]), "first_name": str(res["givenName"]), "last_name": str(res["sn"]),
            "uid": str(res["uid"]), "title": str(res["title"])}


class NoProfileError(commands.CommandError):
    pass


class Profiles(commands.Cog):
    """
    Ensemble des commandes sur vos profiles.
    """

    def __init__(self, bot: 'CustomBot'):
        self.bot = bot

    @commands.group(aliases=["p"])
    async def profile(self, ctx: CustomContext):
        """
        Affichage de votre profile actuel
        """
        if not ctx.invoked_subcommand:
            if await self.bot.db.has_profile(ctx.author):
                profile = await self.bot.db.get_profile(ctx.author)

                await ctx.send_to(f"**[{profile.tsp_user}]** Vous avez un profile")
            else:
                await ctx.send_to("Vous n'avez pas de profile. C'est le moment d'en creer un.")

    @profile.command()
    async def create(self, ctx: CustomContext, user: str, *, password: str = None):
        """
        Permet de creer votre profile. Pour user, forunir votre identifiant (par exemple: jovart_a), et pour le password, fournir votre mot de passe CAS.
        """
        if ctx.guild:
            await ctx.message.delete()
        if await self.bot.db.has_profile(ctx.author):
            await ctx.send_to("Vous avez déjà un profile")
        else:
            await self.bot.db.create_profile(ctx.author, user, password)
            await ctx.send_to("👌")

    @profile.group(aliases=["e"])
    async def edit(self, ctx: CustomContext):
        """
        Permet d'éditer vos préférences de profile.
        """
        if not await self.bot.db.has_profile(ctx.author):
            await ctx.send_to("❌ Vous n'avez pas de profile. C'est le moment d'en creer un.")
            raise NoProfileError()
        if not ctx.invoked_subcommand:
            await ctx.send_help(ctx.command)

    @edit.command()
    async def user(self, ctx: CustomContext, *, new_user: str):
        """
        Modifiez votre nom d'utilisateur CAS
        """
        try:
            await ctx.message.delete()
        except:
            pass
        profile = await self.bot.db.get_profile(ctx.author)
        profile.tsp_user = new_user
        await self.bot.db.save_profile(ctx.author, profile)
        await ctx.send_to(f"👌 Nom d'utilisateur modifié, **{new_user}**.")

    @edit.command()
    async def password(self, ctx: CustomContext, *, new_password: str):
        """
        Modifiez votre mot de passe CAS
        """
        try:
            await ctx.message.delete()
        except:
            pass
        profile = await self.bot.db.get_profile(ctx.author)
        profile.tsp_password = new_password
        await self.bot.db.save_profile(ctx.author, profile)
        await ctx.send_to("👌 Mot de passe modifié.")

    @edit.command()
    async def affichage_rang(self, ctx: CustomContext, *, affichage: bool):
        """
        Permet de définir l'affichange de votre rang.
        """
        profile = await self.bot.db.get_profile(ctx.author)
        profile.show_rang = affichage
        await self.bot.db.save_profile(ctx.author, profile)

        if affichage:
            await ctx.send_to("👌 Votre rang sera affiché lors d'un appel au résumé de vos notes.")
        else:
            await ctx.send_to("👌 Votre rang ne sera pas affiché lors d'un appel au résumé de vos notes.")

    @profile.command()
    async def get_role(self, ctx: CustomContext):
        profile = await self.bot.db.get_profile(ctx.author)
        if await self.set_user_roles(ctx.author, profile.tsp_user):
            await ctx.send("👌")
        else:
            await ctx.send("❌ (Avez vous un profil ? Est-il correct ?)")

    @profile.command()
    async def get_roles(self, ctx: CustomContext):
        count_added = 0
        for member in ctx.guild.members:
            try:
                profile = await self.bot.db.get_profile(member)
            except KeyError:
                pass
            else:
                count_added += await self.set_user_roles(member, profile.tsp_user)
            await asyncio.sleep(0)
        await ctx.send(f"{count_added} roles donnés :)")

    async def set_user_roles(self, member: discord.Member, user_login: str):
        ROLES_NAMES = {
            "CL_FI-EI1": 742452544802127875,
            "CL_FI-EI2": 742452566356656168,
            "CL_FI-EI3": 742452585390407681,
            "CL_FI-EI4": 742452604197535955,
            "CL_FE": 673315006259003393,
        }

        user_info = get_login_info(user_login)

        if not user_info:
            print(f"No valid user for {user_login} ({member.mention})")
            return False

        group = user_info["title"]


        for group_name, role_id in ROLES_NAMES.items():
            if group_name.startswith(group):
                break
        else:
            print(f"Unknown group {group} for user {user_login} ({member.mention})")

            return False

        role = member.guild.get_role(role_id)
        await member.add_roles(role, reason=f"Giving role for {group} in ldap.")
        return True


def setup(bot: 'CustomBot'):
    cog = Profiles(bot)
    bot.add_cog(cog)
