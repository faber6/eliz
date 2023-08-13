import os
from dotenv import load_dotenv
import logging
import json
import re
import requests

import discord
from discord.ext import commands

from utils import anti_spam, cut_trailing_sentence, ContextPreprocessor, ContextEntry

load_dotenv()


class DiscordBot(commands.Cog):
    def __init__(self, client):
        self.client = client
        with open(f"./config/{os.getenv('CONFIG')}.json", encoding="utf-8") as f:
            self.config = json.load(f)

    @commands.command()
    async def toggle(self, ctx):
        pass

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author == self.client.user:
            return
        if self.client.user.mentioned_in(message) or any(nickname.lower() in message.content.lower() for nickname in self.config['client_args']['nicknames']):
            conversation = await self.get_msg_ctx(message.channel)
            await self.respond(conversation, message)

    async def respond(self, conversation, message):
        async with message.channel.typing():
            conversation = await self.build_ctx(conversation)

            response = self.enma_respond(
                self.config['model_provider'], conversation)

            # this actually brokes the reponse in some case
            # response = cut_trailing_sentence(
            #     self.get_respond(response))

            response = self.get_respond(response)

            await message.channel.send(response)

    def get_respond(self, response):
        count = -1
        while True:
            re = response[0]['generated_text'].splitlines()[count]
            if re.startswith(self.config['name']):
                re = re.replace(self.config['name'] + ': ', '')
                return re
            else:
                count = count - 1
                re = response[0]['generated_text'].splitlines()[count]

    def enma_respond(self, config, prompt):
        gen = config['gensettings']
        gen['prompt'] = prompt

        endpoint = config['endpoint']
        if os.getenv('ENDPOINT') is not None:
            endpoint = f"http://{os.getenv('ENDPOINT')}:8000/completion"
        if config['endpoint'] != "http://0.0.0.0:8000/completion":
            endpoint = config['endpoint']

        reponse = requests.post(endpoint, json=gen)
        return reponse.json()

    async def build_ctx(self, conversation):
        contextmgr = ContextPreprocessor(
            self.config['client_args']['context_size'])

        prompt = self.config['prompt']
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
            suffix=f'\n{self.config["name"]}:',
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

        return contextmgr.context(self.config['client_args']['context_size'])

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
                        chain.append(f'{self.config["name"]}: {content}')
                    else:
                        chain.append(f'{message.author.name}: {content}')
                continue
        return '\n'.join(chain)


async def setup(client):
    await client.add_cog(DiscordBot(client))
