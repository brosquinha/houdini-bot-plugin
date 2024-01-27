import asyncio
import json
import os

from houdini import handlers
from houdini.data.room import Room
from houdini.handlers import XTPacket
from houdini.houdini import Houdini
from houdini.plugins import IPlugin
from houdini.plugins.bot.penguin_bot import PenguinBot


class BotPlugin(IPlugin):
    author = "brosquinha"
    description = "Bot plugin"
    version = "1.0.0"
    
    config_file = os.path.join(os.path.dirname(__file__), 'config.json')
    default_spawn_room_ids = [100, 110, 111, 120, 121, 122, 130, 300]

    def __init__(self, server: Houdini):
        self.server = server
        self.bots = []
        with open(self.config_file) as f:
            self.plugin_config: dict = json.load(f)
            
    async def ready(self):
        # quick debugging
        # import logging; self.server.logger.setLevel(logging.DEBUG)
        self.server.logger.info("Bot plugin loaded")
        bot_ids = self.plugin_config.get('bot_penguin_ids', [])
        spawn_rooms = self.plugin_config.get('spawn_rooms', self.default_spawn_room_ids)
        
        self.bots = [PenguinBot(x, self.plugin_config, self.server) for x in bot_ids]
        for bot, room_id in zip(self.bots, spawn_rooms):
            room = self.server.rooms[room_id]
            await bot.load()
            await bot.join_room(room)
            bot.begin_activity()
        
    @handlers.handler(XTPacket('j', 'jr'))
    async def handle_join_room(self, p, room: Room, *_):
        await asyncio.gather(*(bot.handle_join_room(p, room) for bot in self.bots))

    @handlers.handler(XTPacket('u', 'sb'))
    async def handle_snowball(self, p, x: int, y: int):
        await asyncio.gather(*(bot.handle_snowball(p, x, y) for bot in self.bots))
        
    @handlers.handler(XTPacket('u', 'ss'))
    async def handle_safe_message(self, p, message_id: int):
        await asyncio.gather(*(bot.handle_safe_message(p, message_id) for bot in self.bots))
