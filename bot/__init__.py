import asyncio
import logging
import random

import houdini.data.penguin
from houdini import handlers
from houdini.data.room import Room
from houdini.handlers import XTPacket
from houdini.houdini import Houdini
from houdini.penguin import Penguin
from houdini.plugins import IPlugin

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
        await asyncio.gather(*(bot.salute(p, room) for bot in self.bots))

    @handlers.handler(XTPacket('u', 'sb'))
    async def lament_snowball(self, p, x: int, y: int):
        await asyncio.gather(*(bot.lament_snowball(p, x, y) for bot in self.bots))
        
    @handlers.handler(XTPacket('u', 'ss'))
    async def handle_safe_message(self, p, message_id: int):
        await asyncio.gather(*(bot.handle_safe_message(p, message_id) for bot in self.bots))


class PenguinBot(Penguin):
    
    snowball_margin = 25
    room_ids = [
        100, 110, 111, 120, 121, 130, 300, 310, 320, 330, 340, 200, 220,
        230, 801, 802, 800, 400, 410, 411, 809, 805, 810, 806, 808, 807
    ]
    
    def __init__(self, penguin_id: str, server):
        self.penguin_id = penguin_id
        self.server = server
        self.penguin_data = None
        self.following_penguin = None
        
        self.frame = 18
        
        all_items = [self.server.items[x] for x in self.server.items]

        """
        This is intentionally placed outside of the if statement to allow randomization (via the command)
        even if the bot wasn't initially created randomly.
        """
        # TODO: Exclude bait items probably (LAZY)
        self._head_ids = [item.id for item in all_items if item.is_head()]
        self._face_ids = [item.id for item in all_items if item.is_face()]
        self._neck_ids = [item.id for item in all_items if item.is_neck()]
        self._body_ids = [item.id for item in all_items if item.is_body()]
        self._hand_ids = [item.id for item in all_items if item.is_hand()]
        self._feet_ids = [item.id for item in all_items if item.is_feet()]
        self._flag_ids = [item.id for item in all_items if item.is_flag()]
        self._photo_ids = [item.id for item in all_items if item.is_photo()]
        
        super().__init__(self.server, None, FakeWriter())
        
    async def load(self):
        self.penguin_data = await houdini.data.penguin.Penguin.get(self.penguin_id)
        self.update(**self.penguin_data.to_dict())
        self.randomize_clothes()
        self.randomize_position()
        
    def begin_activity(self):
        asyncio.create_task(self.activity_loop())
        
    async def activity_loop(self):
        while True:
            await asyncio.sleep(5)
            self.frame = max(self.frame + 1, 18) if self.frame < 26 else 18
            await self.room.send_xt('sf', self.id, self.frame)
            await asyncio.sleep(5)
            self.x = random.choice(range(190, 530))
            self.y = random.choice(range(300, 450))
            await self.room.send_xt('sp', self.id, self.x, self.y)
            
    async def salute(self, p, room: Room):
        if self.following_penguin and p.id == self.following_penguin.id:
            await self.join_room(room)
        elif room.id == self.room.id:
            await asyncio.sleep(3)
            await self.room.send_xt('ss', self.id, 101)
            await asyncio.sleep(3)
            await self.room.send_xt('ss', self.id, 151)
            
    async def lament_snowball(self, p, x: int, y: int):
        if (x in range(self.x - self.snowball_margin, self.x + self.snowball_margin) and
            y in range(self.y - self.snowball_margin, self.y + self.snowball_margin)):
            await asyncio.sleep(1)
            await self.room.send_xt('se', self.id, 4)
            
    async def handle_safe_message(self, p, message_id: int):
        if not (p.room and p.room.id == self.room.id):
            return
        if message_id == 310 and self.following_penguin is None:
            self.following_penguin = p
            await self.room.send_xt('ss', self.id, 22)
        if message_id == 802 and self.following_penguin is not None:
            self.following_penguin = None
            await self.room.send_xt('ss', self.id, 212)
            await asyncio.sleep(2)
            await self.join_room(self.server.rooms[random.choice(self.room_ids)])
    
    def randomize_clothes(self):
        self.color = random.randrange(2, 14)
        self.head = random.choice(self._head_ids)
        self.face = random.choice(self._face_ids)
        self.neck = random.choice(self._neck_ids)
        self.body = random.choice(self._body_ids)
        self.hand = random.choice(self._hand_ids)
        self.feet = random.choice(self._feet_ids)
        self.flag = random.choice(self._flag_ids)
        self.photo = random.choice(self._photo_ids)
        
    def randomize_position(self):
        self.x = random.choice(range(190, 530))
        self.y = random.choice(range(300, 450))


class FakeWriter:
    def get_extra_info(self, _):
        return str(random.randbytes(10))
    
    def is_closing(self):
        return False
    
    def write(self, *args, **kwargs):
        pass

