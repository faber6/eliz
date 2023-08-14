import os
from dotenv import load_dotenv
import logging
import json
import re
import aiohttp
import yaml

import discord
from discord.ext import commands

from utils import anti_spam, cut_trailing_sentence, ContextPreprocessor, ContextEntry

load_dotenv()


class DiscordBot(commands.Cog):
    def __init__(self, client):
        self.client = client
        with open("./config.yaml", "r") as f:
            self.config = yaml.safe_load(f)
        with open(f"./config/{os.getenv('CONFIG', self.config['config'])}.json", encoding="utf-8") as f:
            self.char_config = json.load(f)

    @commands.command()
    async def toggle(self, ctx):
        pass

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author == self.client.user:
            return
        if self.client.user.mentioned_in(message) or any(nickname.lower() in message.content.lower() for nickname in self.char_config['client_args']['nicknames']):
            conversation = await self.get_msg_ctx(message.channel)
            await self.respond(conversation, message)

    async def respond(self, conversation, message):
        async with message.channel.typing():
            conversation = await self.build_ctx(conversation)

            response = await self.enma_respond(conversation)

            # this actually brokes the reponse in some case
            # response = cut_trailing_sentence(
            #     self.get_respond(response))

            response = self.get_respond(response)

            await message.channel.send(response)

    def get_respond(self, response):
        count = -1
        while True:
            try:
                resp = response[0]['generated_text'].splitlines()[count]
                if resp.startswith(self.char_config['name']):
                    return resp.replace(self.char_config['name'] + ':', '')
                else:
                    count = count - 1
            except KeyError:
                return 'error: ' + response['error']

    async def enma_respond(self, prompt):
        gen = self.char_config['model_provider']['gensettings']
        gen['prompt'] = prompt

        endpoint = self.char_config['model_provider']['endpoint']
        has_endpoint = os.getenv('ENDPOINT', self.config['endpoint'])
        if has_endpoint:
            endpoint = f"http://{has_endpoint}:8000/completion"
        if self.char_config['model_provider']['endpoint'] != "http://0.0.0.0:8000/completion":
            endpoint = self.char_config['model_provider']['endpoint']

        async with aiohttp.ClientSession() as session:
            async with session.post(endpoint, json=gen) as resp:
                return await resp.json()

    async def build_ctx(self, conversation):
        contextmgr = ContextPreprocessor(
            self.char_config['client_args']['context_size'])

        prompt = self.char_config['prompt']
        prompt_entry = ContextEntry(
            text=prompt,
            prefix='',
            suffix='\n',
            reserved_tokens=512,
            insertion_order=1000,
            insertion_position=-1,
            insertion_type=6,
            forced_activation=True,
            cascading_activation=False
        )
        contextmgr.add_entry(prompt_entry)

        # conversation
        conversation_entry = ContextEntry(
            text=conversation,
            prefix='',
            suffix=f'\n{self.char_config["name"]}:',
            reserved_tokens=512,
            insertion_order=0,
            insertion_position=-1,
            trim_direction=0,
            trim_type=7,
            insertion_type=6,
            forced_activation=True,
            cascading_activation=False
        )
        contextmgr.add_entry(conversation_entry)

        return contextmgr.context(self.char_config['client_args']['context_size'])

    async def get_msg_ctx(self, channel):
        messages = [message async for message in channel.history(limit=40)]
        messages, to_remove = anti_spam(messages)
        if to_remove:
            logging.info(f'Removed {to_remove} messages from the context.')
        chain = []
        for message in reversed(messages):
            if not message.embeds and message.content:
                content = re.sub(r'\<[^>]*\>', '', message.content)
                if content != '':
                    if message.author.name in [self.client.user.name, self.client.user.display_name, self.client.user.display_name]:
                        chain.append(f'{self.char_config["name"]}: {content}')
                    else:
                        chain.append(f'{message.author.name}: {content}')
                continue
        return '\n'.join(chain)


async def setup(client):
    await client.add_cog(DiscordBot(client))
