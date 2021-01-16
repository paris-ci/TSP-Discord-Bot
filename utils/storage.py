import json

import discord


class Profile:
    def __init__(self, profile_dict: dict):
        self.tsp_user = str(profile_dict["tsp_user"])
        self.tsp_password = str(profile_dict["tsp_password"])
        self.show_rang = bool(profile_dict.get("show_rang", True))

    def to_dict(self):
        return {"tsp_user": self.tsp_user, "tsp_password": self.tsp_password, "show_rang": self.show_rang}


class Storage:
    def __init__(self, bot):
        self.bot = bot

        with open("profiles.json", "r") as f:
            self._profiles = json.load(f)

    def get_all_profiles(self):
        profiles = {}
        for member_id, profile_dict in self._profiles.items():
            profiles[member_id] = Profile(profile_dict)

        self.bot.logger.info(f"Loaded {len(profiles)} profiles.")

        return profiles

    async def save_profiles(self):
        with open("profiles.json", "w") as f:
            json.dump(self._profiles, f)

    async def save_profile(self, member: discord.Member, profile:Profile):
        self._profiles[str(member.id)] = profile.to_dict()
        await self.save_profiles()

    async def create_profile(self, member: discord.Member, tsp_user:str, tsp_password:str):
        self._profiles[str(member.id)] = Profile({"tsp_user": tsp_user, "tsp_password": tsp_password}).to_dict()
        await self.save_profiles()

    async def get_profile(self, member: discord.Member) -> Profile:
        return Profile(self._profiles[str(member.id)])

    async def has_profile(self, member: discord.Member):
        return str(member.id) in self._profiles.keys()
