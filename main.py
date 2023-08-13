import os
from dotenv import load_dotenv
import logging
import json

import discord
from discord.ext import commands

load_dotenv()
logging.basicConfig(
    handlers=[logging.FileHandler("./log", "a", "utf-8")],
    level=logging.INFO,
    format="%(asctime)s %(message)s",
    datefmt="%m/%d/%Y %I:%M:%S %p",
)


class Client(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix=os.getenv("PREFIX", "?"), intents=intents)

    async def setup_hook(self):
        await client.load_extension("bot")

    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CommandNotFound):
            return
        raise error


client = Client()

activity = None
with open(f"./config/{os.getenv('CONFIG')}.json", encoding="utf-8") as f:
    config = json.load(f)
    activity = config["client_args"]["status"]


@client.event
async def on_ready():
    if activity is not None:
        await client.change_presence(activity=discord.CustomActivity(activity))
    print("Logged in as {0} ({0.id})".format(client.user))

client.run(os.getenv("DISCORD_TOKEN"), reconnect=True)
