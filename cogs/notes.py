import asyncio
import json
import random
import re
import time
import typing

import aiohttp
import discord
from discord.ext import commands, tasks
from discord.ext.commands.cooldowns import BucketType
from utils.storage import Profile

from utils.context import CustomContext

if typing.TYPE_CHECKING:
    from utils.bot import CustomBot


class Bulletin:
    def __init__(self, profile: Profile, retour_sifi):
        self.profile = profile
        self.retour_sifi = retour_sifi

    @property
    def ecole(self) -> str:
        return self.retour_sifi["list1"]["list1_Details_Group_Collection"]["list1_Details_Group"]["@attributes"]["X_Ecole"]

    @property
    def annee_scolaire(self) -> str:
        return self.retour_sifi["list1"]["list1_Details_Group_Collection"]["list1_Details_Group"]["@attributes"]["X_AnnSco"]

    @property
    def nom(self) -> str:
        return self.retour_sifi["list1"]["list1_Details_Group_Collection"]["list1_Details_Group"]["@attributes"]["textbox10"]

    @property
    def niveau(self) -> str:
        return self.retour_sifi["list1"]["list1_Details_Group_Collection"]["list1_Details_Group"]["@attributes"]["niveau_LMD"]

    @property
    def rang(self) -> typing.Tuple[int, int]:
        rang_text: str = self.retour_sifi["list1"]["list1_Details_Group_Collection"]["list1_Details_Group"]["@attributes"]["textbox19"]
        #    Rang :               8 / 209
        regex = r"(?P<rang>\d{1,3}) \/ (?P<nb_etudiants>\d{1,3})"
        match = re.search(regex, rang_text)

        return int(match.group('rang')), int(match.group("nb_etudiants"))

    @property
    def moyenne(self) -> float:
        return float(self.retour_sifi["list1"]["list1_Details_Group_Collection"]["list1_Details_Group"]["table2"]["@attributes"]["textbox33"])

    def notes(self, get_categories=True):
        notes_sifi = self.retour_sifi["list1"]["list1_Details_Group_Collection"]["list1_Details_Group"]["table2"]["Detail_Collection"]["Detail"]

        notes_parsed = []

        for matiere_sifi in notes_sifi:
            vraie_matiere = matiere_sifi["@attributes"]
            category = vraie_matiere["textbox22"] == ""
            if not category or get_categories:
                note_maybe = vraie_matiere.get("textbox52", None)
                if note_maybe == "Validé":
                    note = True
                elif note_maybe:
                    note = float(note_maybe)
                else:
                    note = None
                notes_parsed.append({
                    "is_category": category,
                    "code": vraie_matiere["textbox38"].strip(),
                    "nom": vraie_matiere["textbox40"].strip(),
                    "note": note,
                    "ECTS": int(vraie_matiere["textbox22"]) if vraie_matiere["textbox22"] else None,
                })

        return notes_parsed

    @property
    def notes_count(self):
        nb = 0
        for note in self.notes(get_categories=False):
            if note["note"]:
                nb += 1
        return nb


class Notes(commands.Cog):
    def __init__(self, bot: 'CustomBot'):
        self.bot = bot
        self.alert_notes_channel_id = 681469822214864936
        self.alert_notes_channel: discord.TextChannel = None
        self.ecole_roles = {"Télécom SudParis": 673315145421815848, "Institut Mines-Télécom Business School": 673315006259003393}
        self.refresh_users_ids = [138751484517941259, 673834847470616576]
        self.refresh_users: dict = {}
        self.bulletins = {}
        self.notify_notes_loop.start()
        self.max_downloads = asyncio.Semaphore(6)

    def cog_unload(self):
        self.notify_notes_loop.cancel()

    async def cache_notes_for_role(self, role: discord.Role, exceptions: typing.List[int] = None):
        if exceptions is None:
            exceptions = []
        role_members = role.members
        members_with_profile = []
        for member in role_members:
            if await self.bot.db.has_profile(member) and member.id not in exceptions:
                members_with_profile.append(member)

        max_caching_downloads = asyncio.Semaphore(5)  # 5 max downloads for a cache

        self.bot.logger.debug(f"[cache_notes_for_role] Starting preemptive cache for {len(members_with_profile)} users...")

        async def update_bulletin(user):
            backoff = 1
            async with max_caching_downloads:
                self.bot.logger.debug(f"[cache_notes_for_role] Starting preemptive cache for {user}...")
                while True:
                    try:
                        sleep_time = random.randint(5, 20) * backoff
                        self.bot.logger.debug(f"[cache_notes_for_role] {user}: sleeping for {sleep_time} seconds to avoid overloading...")
                        await asyncio.sleep(sleep_time)
                        await self.get_bulletin(user, force_refresh=True)
                        self.bot.logger.debug(f"[cache_notes_for_role] Finished preemptive caching for {user}...")
                        return
                    except asyncio.TimeoutError:
                        self.bot.logger.debug(f"[cache_notes_for_role] Timout caching notes for {user}, retrying...")
                        backoff += 1
                    except TypeError:
                        self.bot.logger.debug(f"[cache_notes_for_role] Type error caching notes for {user} (probably due to invalid reply from SIFI, retrying...)")
                        backoff += 1
                    except json.decoder.JSONDecodeError:
                        self.bot.logger.debug(f"[cache_notes_for_role] Json error caching notes for {user} (probably due to SIFI overload, retrying...)")
                        backoff += 1

        parralel = [update_bulletin(member) for member in members_with_profile]
        await asyncio.gather(*parralel)
        return len(parralel)

    async def notify_notes_user(self, user):
        new_bulletin = await self.get_bulletin(user, True)
        old_bulletin: Bulletin = self.refresh_users[user]

        if old_bulletin.notes_count != new_bulletin.notes_count:
            ecole_role = self.alert_notes_channel.guild.get_role(self.ecole_roles[new_bulletin.ecole])
            if not ecole_role:
                ecole_role = self.alert_notes_channel.guild.default_role

            old_notes = {f"{n['code']} - {n['nom']}" for n in old_bulletin.notes(get_categories=False) if n["note"]}
            new_notes = {f"{n['code']} - {n['nom']}" for n in new_bulletin.notes(get_categories=False) if n["note"]}

            self.bot.logger.debug(f"Anciennes notes: {old_notes}")
            self.bot.logger.debug(f"Nouvelles notes: {new_notes}")

            difference = new_notes.symmetric_difference(old_notes)

            ajout = old_bulletin.notes_count < new_bulletin.notes_count

            if ajout:
                self.bot.logger.info(f"Nouvelles notes pour {user.name} ({old_bulletin.notes_count} -> {new_bulletin.notes_count})")
                n = 0
                if not ecole_role.is_default():
                    try:
                        n = await self.cache_notes_for_role(ecole_role, exceptions=[user.id])
                    except:
                        self.bot.logger.exception(f"Erreur lors de la sauvegarde des notes: {new_notes}")
                        pass
                await self.alert_notes_channel.send(f"Des nouvelles notes ({old_bulletin.notes_count} -> {new_bulletin.notes_count}) sont disponibles :) "
                                                    f"{ecole_role.mention} [**{new_bulletin.ecole}**]\n"
                                                    f"Ajout de {', '.join(difference)}.\n"
                                                    f"{n} notes mises en cache pour accès immédiat.")


            else:
                await self.alert_notes_channel.send(f"Des notes ont été supprimées ({old_bulletin.notes_count} -> {new_bulletin.notes_count}) [**{new_bulletin.ecole}**]\n"
                                                    f"Supression de {', '.join(difference)}")

                self.bot.logger.info(f"Notes suprimées pour {user.name} ({old_bulletin.notes_count} -> {new_bulletin.notes_count})")

            self.refresh_users[user] = new_bulletin
        else:
            self.bot.logger.debug(f"Pas de nouvelles notes pour {user.name} ({old_bulletin.notes_count} -> {new_bulletin.notes_count})")

    @tasks.loop(minutes=10)
    async def notify_notes_loop(self):
        # Execute all of the users in parralel to save time
        parralel = [self.notify_notes_user(user) for user in self.refresh_users.keys()]
        try:
            await asyncio.gather(*parralel)
        except:
            self.bot.logger.exception("Error in the notify_notes loop. Ignoring and hoping for the best")

    @notify_notes_loop.before_loop
    async def before_refresh(self):
        self.bot.logger.debug(f"Lancement recherche de nouvelles notes :)")
        await self.bot.wait_until_ready()

        self.alert_notes_channel = self.bot.get_channel(self.alert_notes_channel_id)

        for user_id in self.refresh_users_ids:
            user = self.bot.get_user(user_id)
            self.refresh_users[user] = await self.get_bulletin(user)

        self.bot.logger.info(f"Recherche de nouvelles notes lancé :)")

    @notify_notes_loop.after_loop
    async def after_refresh(self):
        if self.notify_notes_loop.failed():
            self.bot.logger.exception("Oh no! The BG task failed.")

    async def cog_check(self, ctx: CustomContext):
        if not await self.bot.db.has_profile(ctx.author):
            await ctx.send_to(f"Vous n'avez pas (encore) de profile :( - Utilisez la commande {ctx.prefix}p create nom_dutilisateur mot_de_passe")
            raise commands.CommandError()
        return True

    async def get_bulletin_from_api(self, profile: Profile):
        async with aiohttp.ClientSession() as session:
            async with session.post('https://notes.api-d.com/sifiQuery.php',
                                    data={"username": profile.tsp_user, "password": profile.tsp_password}, ) as resp:
                try:
                    return Bulletin(profile, await resp.json(content_type=None))
                except:
                    text = await resp.text()
                    self.bot.logger.exception(f"Erreur lors du chargement du bulletin. Voici le HTML retourné par le serveur:\n{text}")
                    raise

    async def get_bulletin_from_cache(self, member) -> typing.Tuple[typing.Optional[int], typing.Optional[Bulletin]]:
        creation, bulletin = self.bulletins.get(member.id, (None, None))
        return creation, bulletin

    async def is_bulletin_in_cache(self, member) -> bool:
        creation, bulletin = await self.get_bulletin_from_cache(member)

        if not bulletin or not creation:
            return False

        if creation + (60*60*4) < time.time():
            return False

        else:
            return True

    async def get_bulletin(self, member, force_refresh=False) -> Bulletin:
        async with self.max_downloads:
            if not force_refresh and await self.is_bulletin_in_cache(member):
                creation, bulletin = await self.get_bulletin_from_cache(member)
                return bulletin
            else:
                profile = await self.bot.db.get_profile(member)
                bulletin = await self.get_bulletin_from_api(profile)
                creation = int(time.time())
                self.bulletins[member.id] = (creation, bulletin)
                return bulletin

    @commands.group(aliases=["n"])
    @commands.max_concurrency(1, BucketType.user)
    async def notes(self, ctx: CustomContext):
        """
        Rècupere les notes depuis le serveur et les stocke en cache pendant quelques temps.
        """
        if not await self.is_bulletin_in_cache(ctx.author):
            await ctx.send_to(f"Je vais chercher vos notes en ligne, merci de patienter...")

        async with ctx.typing():
            await self.get_bulletin(ctx.author)

        if not ctx.invoked_subcommand:
            await ctx.send_to(f"Vos notes sont téléchargées. Pour les consulter, tapez {ctx.prefix}help notes")

    @notes.command()
    async def refresh(self, ctx: CustomContext):
        """
        Supprime vos notes du cache local, afin de les rafraichir à la prochaine commande.
        """
        self.bulletins.pop(ctx.author.id)
        await ctx.send_to(f"👌 Cache de vos notes supprimé.")\

    @notes.command(aliases=["m"])
    async def moyenne(self, ctx: CustomContext):
        """
        Affiche votre moyenne.
        """
        bulletin = await self.get_bulletin(ctx.author)
        await ctx.send_to(f"Votre moyenne actuelle est de {bulletin.moyenne}/20.")

    @notes.command(aliases=["rg"])
    async def rang(self, ctx: CustomContext):
        """
        Force l'affichage de votre rang.
        """
        bulletin = await self.get_bulletin(ctx.author)
        rang, nb_etudiants = bulletin.rang
        await ctx.send_to(f"Votre rang actuel est de {rang}/{nb_etudiants}.")

    @notes.command(aliases=["res", "resumé", "résumé", "résume"])
    async def resume(self, ctx: CustomContext):
        """
        Grand message résumant votre moyenne, votre rang, et l'ensemble de vos notes par UV.
        """
        bulletin = await self.get_bulletin(ctx.author)
        profile = await self.bot.db.get_profile(ctx.author)

        notes = bulletin.notes()

        if profile.show_rang:
            rang, nb_etudiants = bulletin.rang
            rang_msg = f", vous etes classé **{rang}e sur {nb_etudiants}** etudiants"
        else:
            rang_msg = ""

        message_list = [
            f"{bulletin.ecole} — Année scolaire {bulletin.annee_scolaire} — **{bulletin.nom}**",
            f"Vous avez une moyenne de **{bulletin.moyenne}**{rang_msg}.",
            "```diff"
        ]

        for note in notes:
            if note["note"]:
                if note['is_category']:
                    if len(message_list) >= 15:
                        message_list.append("```")
                        await ctx.send_to("\n".join(message_list))
                        message_list = ["```diff"]
                    message_list.append(f"\n{note['nom']} — Moyenne générale {note['note']} pts")
                else:
                    if note['note'] is True:
                        message_list.append(f"+ {note['code']} ({note['nom']}) {note['ECTS']} ECTS")
                    else:
                        if note['note'] < 10:
                            symbol = "-"
                        else:
                            symbol = "+"

                        message_list.append(f"{symbol} {note['code']} ({note['nom']}) {note['note']} pts * {note['ECTS']} ECTS")

        message_list.append("```")
        await ctx.send_to("\n".join(message_list))

    @commands.is_owner()
    @commands.command(name="cache_notes_for_role")
    async def cache_role(self, ctx: CustomContext, role_id:int):
        """
        Rafraichit les notes de toutes les personnes avec un certain role.
        """
        role = ctx.guild.get_role(role_id)
        if not role:
            await ctx.send_to("❌ Role not found")
            return

        m = await ctx.send_to("En cours...")
        await self.cache_notes_for_role(role)
        await ctx.send_to("👌")

    @notes.command()
    async def lsh(self, ctx: CustomContext):
        """
        Renvoie vos notes en avance avec la méthode secrete de calcul des notes LSH®
        """
        await ctx.send_to(f"Votre note de LV1 : {random.randint(8, 18)}, celle de LV2 : {random.randint(8, 18)} et celle de SH : {random.randint(8, 18)}. Si vous faites une LV3, voici votre note : {random.randint(16, 20)}. Bien joué!")

    @notes.command()
    async def optique(self, ctx: CustomContext):
        """
        Renvoie vos notes d'optique avec la méthode corrigée par Mr. Gottesman®
        """
        await ctx.send_to(f"🤣 Bravo ! Tu as eu **20** ! Je suis surpris qu'autant de monde ait réussi, mais bien joué !")


def setup(bot: 'CustomBot'):
    cog = Notes(bot)
    bot.add_cog(cog)
