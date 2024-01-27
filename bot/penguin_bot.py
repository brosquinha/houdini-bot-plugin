import asyncio
import random
from inspect import signature

import houdini.data.penguin
from houdini.data.room import Room
from houdini.penguin import Penguin
from houdini.plugins.bot.fake_writer import FakeWriter


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
        await self.randomize_clothes()
        self.randomize_position()
        
    def begin_activity(self):
        asyncio.create_task(self.activity_loop())
        
    async def activity_loop(self):
        while True:
            await asyncio.sleep(random.choice(range(5, 16)))
            await self.random_frame()
            await asyncio.sleep(random.choice(range(5, 16)))
            await self.random_move()
            
    async def random_frame(self):
        self.frame = random.choice(range(18, 26))
        await self.room.send_xt('sf', self.id, self.frame)
            
    async def random_move(self):
        self.randomize_position()
        await self.room.send_xt('sp', self.id, self.x, self.y)
            
    async def handle_join_room(self, p, room: Room):
        if self.following_penguin and p.id == self.following_penguin.id:
            await self.join_room(room)
        elif room.id == self.room.id:
            await self.salute()
    
    async def salute(self):
        await asyncio.sleep(3)
        await self.room.send_xt('ss', self.id, 101)
        await asyncio.sleep(3)
        await self.room.send_xt('ss', self.id, 151)
            
    async def handle_snowball(self, p, x: int, y: int):
        if (x in range(self.x - self.snowball_margin, self.x + self.snowball_margin) and
            y in range(self.y - self.snowball_margin, self.y + self.snowball_margin)):
            await asyncio.sleep(1)
            if random.random() > 0.5:
                return await self.lament_snowball()
            await self.throw_snowball_back(p)
            
    async def lament_snowball(self):
        await self.room.send_xt('se', self.id, 4)
        
    async def throw_snowball_back(self, p):
        await self.room.send_xt('sb', self.id, p.x, p.y)
            
    async def handle_safe_message(self, p, message_id: int):
        if not (p.room and p.room.id == self.room.id):
            return
        message_handlers = {
            310: self.follow_penguin,
            802: self.stop_following_penguin,
            354: self.randomize_clothes,
            410: self.random_move
        }
        handler = message_handlers.get(message_id)
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
        await self.join_room(self.server.rooms[random.choice(self.room_ids)])
    
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
