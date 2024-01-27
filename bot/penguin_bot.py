import asyncio
import random
from inspect import signature

import houdini.data.penguin
from houdini.data.room import Room
from houdini.penguin import Penguin
from houdini.plugins.bot.fake_writer import FakeWriter


class PenguinBot(Penguin):
    
    snowball_margin = 25
    default_room_ids = [
        100, 110, 111, 120, 121, 130, 300, 310, 320, 330, 340, 200, 220,
        230, 801, 802, 800, 400, 410, 411, 809, 805, 810, 806, 808, 807
    ]
    default_salute_messages = [101, 151]
    valid_frames = range(18, 26)
    activity_sleep_range = range(5, 16)
    
    def __init__(self, penguin_id: str, plugin_config: dict, server):
        self.penguin_id = penguin_id
        self.plugin_config = plugin_config
        self.server = server
        self.penguin_data = None
        self.following_penguin = None
        
        self.frame = 18
        
        all_items = [self.server.items[x] for x in self.server.items]

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
        self.randomize_position()
        if self.plugin_config.get('enable_random_clothing', True):
            await self.randomize_clothes()
        
    def begin_activity(self):
        asyncio.create_task(self.activity_loop())
        
    async def activity_loop(self):
        while True:
            if self.plugin_config.get('enable_random_frame', True):
                await asyncio.sleep(random.choice(self.activity_sleep_range))
                await self.random_frame()
            if self.plugin_config.get('enable_random_movement', True):
                await asyncio.sleep(random.choice(self.activity_sleep_range))
                await self.random_move()
            
    async def random_frame(self):
        self.frame = random.choice(self.valid_frames)
        await self.room.send_xt('sf', self.id, self.frame)
            
    async def random_move(self):
        self.randomize_position()
        await self.room.send_xt('sp', self.id, self.x, self.y)
            
    async def handle_join_room(self, p, room: Room):
        if self.following_penguin and p.id == self.following_penguin.id:
            await self.join_room(room)
        elif room.id == self.room.id and self.plugin_config.get('enable_salute', True):
            await self.salute()
    
    async def salute(self):
        for message in self.plugin_config.get('salute_messages', self.default_salute_messages):
            await asyncio.sleep(3)
            await self.room.send_xt('ss', self.id, message)
            
    async def handle_snowball(self, p, x: int, y: int):
        if (x in range(self.x - self.snowball_margin, self.x + self.snowball_margin) and
            y in range(self.y - self.snowball_margin, self.y + self.snowball_margin)):
            await asyncio.sleep(1)
            snowball_reactions = [
                (self.lament_snowball, self.plugin_config.get('enable_snowball_lament', True)),
                (self.throw_snowball_back, self.plugin_config.get('enable_snowball_throwback', True))
            ]
            enabled_reactions = [f for f, e in snowball_reactions if e]
            if enabled_reactions:
                await random.choice(enabled_reactions)(p)
            
    async def lament_snowball(self, _):
        await self.room.send_xt('se', self.id, 4)
        
    async def throw_snowball_back(self, p):
        await self.room.send_xt('sb', self.id, p.x, p.y)
            
    async def handle_safe_message(self, p, message_id: int):
        if not (p.room and p.room.id == self.room.id):
            return
        message_handlers = {
            310: (self.follow_penguin, self.plugin_config.get('enable_follow_mode', True)),
            802: (self.stop_following_penguin, self.plugin_config.get('enable_follow_mode', True)),
            354: (self.randomize_clothes, self.plugin_config.get('enable_random_clothing', True)),
            410: (self.random_move, self.plugin_config.get('enable_random_movement_on_demand', True))
        }
        enabled_handlers = {k: f for k, (f, e) in message_handlers.items() if e}
        handler = enabled_handlers.get(message_id)
        if handler:
            if len(signature(handler).parameters) > 0:
                return await handler(p)
            await handler()
            
    async def follow_penguin(self, p):
        if self.following_penguin is not None:
            return
        self.following_penguin = p
        await self.room.send_xt('ss', self.id, 22)
    
    async def stop_following_penguin(self):
        if self.following_penguin is None:
            return
        self.following_penguin = None
        await self.room.send_xt('ss', self.id, 212)
        await asyncio.sleep(2)
        await self.join_room(
            self.server.rooms[random.choice(self.plugin_config.get('bot_rooms', self.default_room_ids))])
    
    async def randomize_clothes(self):
        self.color = random.randrange(2, 14)
        self.head = random.choice(self._head_ids)
        self.face = random.choice(self._face_ids)
        self.neck = random.choice(self._neck_ids)
        self.body = random.choice(self._body_ids)
        self.hand = random.choice(self._hand_ids)
        self.feet = random.choice(self._feet_ids)
        self.flag = random.choice(self._flag_ids)
        self.photo = random.choice(self._photo_ids)
        if self.room:
            await self.room.send_xt('upc', self.id, self.color)
            await self.room.send_xt('uph', self.id, self.head)
            await self.room.send_xt('upf', self.id, self.face)
            await self.room.send_xt('upn', self.id, self.neck)
            await self.room.send_xt('upb', self.id, self.body)
            await self.room.send_xt('upa', self.id, self.hand)
            await self.room.send_xt('upe', self.id, self.feet)
            await self.room.send_xt('upl', self.id, self.flag)
            await self.room.send_xt('upp', self.id, self.photo)
        
    def randomize_position(self):
        self.x = random.choice(range(190, 530))
        self.y = random.choice(range(300, 450))
