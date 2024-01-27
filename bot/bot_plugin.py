import asyncio
import logging

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
    
    spawn_room_ids = [100, 110, 111, 120, 121, 122, 130, 300]
    bots = None

    def __init__(self, server: Houdini):
        self.server = server

    async def add_to_room(self, player):
        self.server.logger.info('Adding bot to room')
        await player.send_xt("ap", self.bot_string)

    async def remove_from_room(self, player):
        await player.send_xt("rp", self.id)

    async def ready(self):
        # quick debugging
        # self.server.logger.setLevel(logging.DEBUG)
        self.server.logger.info("Bot plugin loaded")
        self.bots = [PenguinBot(x, self.server) for x in [104, 105]]
        for bot, room_id in zip(self.bots, self.spawn_room_ids):
            room = self.server.rooms[room_id]
            await bot.load()
            await bot.join_room(room)
            bot.begin_activity()
        
    @handlers.handler(XTPacket('j', 'jr'))
    async def salute(self, p, room: Room, *_):
        await asyncio.gather(*(bot.handle_join_room(p, room) for bot in self.bots))

    @handlers.handler(XTPacket('u', 'sb'))
    async def lament_snowball(self, p, x: int, y: int):
        await asyncio.gather(*(bot.handle_snowball(p, x, y) for bot in self.bots))
        
    @handlers.handler(XTPacket('u', 'ss'))
    async def handle_safe_message(self, p, message_id: int):
        await asyncio.gather(*(bot.handle_safe_message(p, message_id) for bot in self.bots))
