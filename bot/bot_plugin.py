import asyncio
import json
import os
import random
import secrets
import urllib.parse
from collections import defaultdict

import bcrypt

from houdini import handlers
from houdini.data.item import PenguinItem
from houdini.data.penguin import Penguin
from houdini.data.plugin import PenguinAttribute
from houdini.data.room import Room
from houdini.crypto import Crypto
from houdini.handlers import XTPacket
from houdini.houdini import Houdini
from houdini.plugins import IPlugin
from houdini.plugins.bot.penguin_bot import PenguinBot
from houdini.plugins.bot.constants import ITEM_TYPE


class BotPlugin(IPlugin):
    author = "brosquinha"
    description = "Bot plugin"
    version = "1.0.0"
    
    config_file = os.path.join(os.path.dirname(__file__), 'config.json')
    default_room_ids = [
        100, 110, 111, 120, 121, 130, 300, 310, 320, 330, 340, 200, 220,
        230, 801, 802, 800, 400, 410, 411, 809, 805, 810, 806, 808, 807
    ]
    max_bot_population = 200
    bot_rotation_range = range(60, 180)

    def __init__(self, server: Houdini):
        self.server = server
        self.bots = []
        
        self.items_by_type = defaultdict(list)
        for x in self.server.items:
            item = self.server.items[x]
            self.items_by_type[item.type].append(item)

        with open(self.config_file) as f:
            self.plugin_config: dict = json.load(f)
            
    async def ready(self):
        # quick debugging
        # import logging; self.server.logger.setLevel(logging.DEBUG)
        if self.server.config.type != 'world':
            return
        self.server.logger.info("Bot plugin loaded")
        bot_population = self.plugin_config.get('bot_population')
        existing_bot_ids = await PenguinAttribute.select('penguin_id').where(PenguinAttribute.name == "bot").gino.all()
        existing_bot_ids = [x[0] for x in existing_bot_ids]
        self.existing_penguin_bots = await Penguin.query.where(Penguin.id.in_(existing_bot_ids)).gino.all()
        set_bot_ids = self.plugin_config.get('bot_penguin_ids', [])
        penguin_bots = await Penguin.query.where(Penguin.id.in_(set_bot_ids)).gino.all()
        penguin_bots += random.sample(self.existing_penguin_bots, min(bot_population, len(self.existing_penguin_bots)))
        
        if bot_population and bot_population > self.max_bot_population:
            self.server.logger.warn(f'Bot population was set too large, defaulting to max value of {self.max_bot_population}')
            bot_population = self.max_bot_population

        if bot_population and len(penguin_bots) < bot_population:
            self.server.logger.info('Creating penguin bot accounts...')
            penguins = await self.create_penguin_bots(2 * bot_population - len(set_bot_ids))
            penguins = [x for x in penguins if x]
            self.server.logger.info(f'{len(penguins)} bot accounts created')
            penguin_bots += penguins
        
        self.bots = [PenguinBot(x.id, self).load_data(x) for x in penguin_bots]
        for bot in self.bots:
            await bot.init()
            bot.begin_activity()
        await self.server.redis.hset('houdini.population', self.server.config.id, len(self.server.penguins_by_id))
        self.server.logger.info(f'Server {self.server.config.id} population: {len(self.server.penguins_by_id)}')
        
        if self.plugin_config.get('bot_rotation', True):
            asyncio.create_task(self.bot_rotation())
            
    async def create_penguin_bots(self, population: int):
        random_names = await self._get_random_names()
        password = self.plugin_config.get('bot_penguin_default_password') or secrets.token_urlsafe(32)
        hashed_password = self._hash_password(password)
        return await asyncio.gather(*(self.create_penguin_bot(
            random.choice(random_names), hashed_password) for _ in range(population)))
    
    async def create_penguin_bot(self, username: str, hashed_password: str) -> Penguin:
        email = f'{username.lower()}@{self.plugin_config.get("bot_penguin_email_domain", "email.com")}'
        
        async with self.server.db.transaction():
            color = random.randrange(2, 14)
            try:
                penguin = await Penguin.create(username=username.lower()[:12], nickname=username,
                                        password=hashed_password, email=email,
                                        color=int(color),
                                        approval_en=True,
                                        approval_pt=True,
                                        approval_fr=True,
                                        approval_es=True,
                                        approval_de=True,
                                        approval_ru=True,
                                        active=True)
            except Exception as e:
                self.server.logger.warn(f'Skipping creation of {username}: {e}')
                return

            await PenguinAttribute.create(penguin_id=penguin.id, name="bot", value="true")
            await PenguinItem.create(penguin_id=penguin.id, item_id=int(color))
            
            if self.plugin_config.get('bot_penguin_default_inventory', True):
                await penguin.update(**{
                    'head': int(random.choice(self.items_by_type[ITEM_TYPE.HEAD]).id),
                    'face': int(random.choice(self.items_by_type[ITEM_TYPE.FACE]).id),
                    'neck': int(random.choice(self.items_by_type[ITEM_TYPE.NECK]).id),
                    'body': int(random.choice(self.items_by_type[ITEM_TYPE.BODY]).id),
                    'hand': int(random.choice(self.items_by_type[ITEM_TYPE.HAND]).id),
                    'feet': int(random.choice(self.items_by_type[ITEM_TYPE.FEET]).id),
                    'flag': int(random.choice(self.items_by_type[ITEM_TYPE.FLAG]).id),
                    'photo': int(random.choice(self.items_by_type[ITEM_TYPE.PHOTO]).id)
                }).apply()
        
        return penguin
    
    def _hash_password(self, password: str) -> str:
        password = Crypto.hash(password).upper()
        password = Crypto.get_login_hash(password, rndk=self.plugin_config.get('dash_static_key', 'houdini'))
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt(12)).decode('utf-8')
    
    async def _get_random_names(self) -> list[str]:
        names_url = "https://www.cs.cmu.edu/Groups/AI/areas/nlp/corpora/names/other/names.txt"
        url = urllib.parse.urlsplit(names_url)
        self.server.logger.debug("Downloading random names...")
        reader, writer = await asyncio.open_connection(url.hostname, 443, ssl=True)
        query = (
            f"GET {url.path or '/'} HTTP/1.1\r\n"
            f"Host: {url.hostname}\r\n"
            f"\r\n"
        )
        
        response = []
        writer.write(query.encode())
        while True:
            line = await reader.readline()
            if not line:
                break
            response.append(line.decode().strip())
        writer.close()
        await writer.wait_closed()
        
        return response
        
    async def bot_rotation(self):
        while True:
            await asyncio.sleep(random.choice(self.bot_rotation_range))
            incoming_bot = random.choice([x for x in self.existing_penguin_bots if x.id not in self.server.penguins_by_id])
            incoming_bot = PenguinBot(incoming_bot.id, self).load_data(incoming_bot)
            rotated_bot = random.choice(self.bots)
            self.bots = [x for x in self.bots if x.id != rotated_bot.id]
            await rotated_bot.disconnect()
            await incoming_bot.init()
            incoming_bot.begin_activity()
            self.bots.append(incoming_bot)
    
    @handlers.handler(XTPacket('j', 'jr'))
    async def handle_join_room(self, p, room: Room, *_):
        await asyncio.gather(*(bot.handle_join_room(p, room) for bot in self.bots))

    @handlers.handler(XTPacket('u', 'sb'))
    async def handle_snowball(self, p, x: int, y: int):
        await asyncio.gather(*(bot.handle_snowball(p, x, y) for bot in self.bots))
        
    @handlers.handler(XTPacket('u', 'ss'))
    async def handle_safe_message(self, p, message_id: int):
        await asyncio.gather(*(bot.handle_safe_message(p, message_id) for bot in self.bots))
