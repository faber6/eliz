import os
from dotenv import load_dotenv
import logging
import json
import yaml

import discord
from discord.ext import commands

load_dotenv()
logging.basicConfig(
    handlers=[logging.FileHandler(
        os.path.dirname(os.path.abspath(__file__))+"/log", "a", "utf-8")],
    level=logging.INFO,
    format="%(asctime)s %(message)s",
    datefmt="%m/%d/%Y %I:%M:%S %p",
)

with open(os.path.dirname(os.path.abspath(__file__))+"/config.yaml", "r") as f:
    config = yaml.safe_load(f)


class Client(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix=os.getenv(
            "DISCORD_PREFIX", config['discord_prefix']), intents=intents)

    async def setup_hook(self):
        await client.load_extension("bot")

    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CommandNotFound):
            return
        raise error


client = Client()
client.remove_command("help")

activity = None
with open(os.path.dirname(os.path.abspath(__file__))+f"/config/{os.getenv('CONFIG', config['config'])}.json", encoding="utf-8") as f:
    activity = json.load(f)["client_args"]["status"]


@client.event
async def on_ready():
    if activity and os.getenv("DISCORD_STATUS", config["discord_status"]).lower() == "on":
        await client.change_presence(activity=discord.CustomActivity(activity))
    print("Logged in as {0} ({0.id})".format(client.user))

client.run(os.getenv("DISCORD_TOKEN", config["discord_token"]), reconnect=True)
