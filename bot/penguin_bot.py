import asyncio
import itertools
import math
import random
from inspect import signature
from typing import List, Tuple, TYPE_CHECKING

import houdini.data.penguin
from houdini.data.room import Room, RoomWaddle
from houdini.penguin import Penguin
from houdini.plugins.bot.fake_writer import FakeWriter
from houdini.plugins.bot.constants import ITEM_TYPE, ROOM_AREAS, ROOM_SPOTS, SAFE_MESSAGES, RoomSpot, RoomSpotsController
from houdini.plugins.bot.games import SledRacing
if TYPE_CHECKING:
    from houdini.plugins.bot.bot_plugin import BotPlugin


class PenguinBot(Penguin):
    
    snowball_margin = 25
    movement_speed = 75
    default_greeting_messages = [SAFE_MESSAGES.HI_THERE, SAFE_MESSAGES.HOW_U_DOING]
    default_interaction_distance = 100
    default_spot_distance = 10
    default_max_spot_prob = 0.75
    valid_frames = range(18, 27)
    activity_cycle_range = range(10, 30)
    activity_sleep_range = range(5, 16)
    spot_sleep_range = range(30, 120)
    
    def __init__(self, penguin_id: str, bot_plugin: 'BotPlugin'):
        self.penguin_id = penguin_id
        self.bot_plugin = bot_plugin
        self.plugin_config = bot_plugin.plugin_config
        self.server = bot_plugin.server
        self.penguin_data = None
        self.following_penguin = None
        
        self.frame = 18
        self._activity_task = None
        
        super().__init__(self.server, None, FakeWriter())
        
    def load_data(self, data: houdini.data.penguin.Penguin) -> 'PenguinBot':
        self.update(**data.to_dict())
        return self
        
    async def init(self):
        self.server.penguins_by_id[self.id] = self
        self.server.penguins_by_username[self.username] = self

        if self.character is not None:
            self.server.penguins_by_character_id[self.character] = self
        
        await self.move_to_random_room()
        self.randomize_position()
        if self.plugin_config.get('random_clothing_on_startup', True):
            await self.randomize_clothes()
        elif self.plugin_config.get('no_clothing', False):
            self.reset_clothes()
        
    def begin_activity(self):
        self._activity_task = asyncio.create_task(self.activity_loop())
        
    async def activity_loop(self):
        while True:
            for _ in range(random.choice(self.activity_cycle_range)):
                if self.plugin_config.get('enable_room_spots', True):
                    await self.move_to_spot()
                if self.plugin_config.get('enable_random_frame', True):
                    await asyncio.sleep(random.choice(self.activity_sleep_range))
                    await self.random_frame()
                if self.plugin_config.get('enable_random_movement', True):
                    await asyncio.sleep(random.choice(self.activity_sleep_range))
                    await self.random_move()
            if self.plugin_config.get('enable_random_room_movement', True) and self.following_penguin is None:
                await asyncio.sleep(random.choice(self.activity_sleep_range))
                await self.move_to_random_room()  
            
    async def move_to_spot(self):
        spots_controller = ROOM_SPOTS[self.room.id]
        max_spot_prob = self.plugin_config.get("spot_max_probability", self.default_max_spot_prob)
        if random.random() > min(spots_controller.len_spots() / 3, max_spot_prob):
            return
        with PenguinBotRoomSpots(spots_controller, self) as spot:
            position_already_taken = False
            for penguin in self.room.penguins_by_id.values():
                spot_distance = self.plugin_config.get('spot_distance', self.default_spot_distance)
                penguin_distance = math.dist(spot.position, (penguin.x, penguin.y))
                if not isinstance(penguin, self.__class__) and penguin_distance <= spot_distance:
                    position_already_taken = True
                    break
            
            if not position_already_taken:
                distance = math.dist((self.x, self.y), spot.position)
                self.x, self.y = spot.position
                self.frame = spot.frame
                await self.room.send_xt('sp', self.id, self.x, self.y)
                if spot.clothes:
                    self.head = spot.clothes.get(ITEM_TYPE.HEAD, 0)
                    self.face = spot.clothes.get(ITEM_TYPE.FACE, 0)
                    self.neck = spot.clothes.get(ITEM_TYPE.NECK, 0)
                    self.body = spot.clothes.get(ITEM_TYPE.BODY, 0)
                    self.hand = spot.clothes.get(ITEM_TYPE.HAND, 0)
                    self.feet = spot.clothes.get(ITEM_TYPE.FEET, 0)
                    await self.sync_clothes()
                await asyncio.sleep(distance / self.movement_speed + 2)
                await self.room.send_xt('sf', self.id, self.frame)
                
            await asyncio.sleep(random.choice(self.spot_sleep_range))
            
        await self.random_move()
        await self.sync_clothes()
    
    async def random_frame(self):
        self.frame = random.choice(self.valid_frames)
        await self.room.send_xt('sf', self.id, self.frame)
            
    async def random_move(self):
        self.randomize_position()
        await self.room.send_xt('sp', self.id, self.x, self.y)
            
    async def handle_join_room(self, p, room: Room):
        if self.following_penguin and p.id == self.following_penguin.id:
            await self.join_room(room)
        elif room.id == self.room.id and len(self.room.penguins_by_id) < 4 and self.plugin_config.get('enable_greeting', True):
            await self.greet()
    
    async def greet(self):
        for message in self.plugin_config.get('greeting_messages', self.default_greeting_messages):
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
        if not (p.room and p.room.id == self.room.id and self.is_player_close(p)):
            return
        message_handlers = {
            SAFE_MESSAGES.FOLLOW_ME: (self.follow_penguin, self.plugin_config.get('enable_follow_mode', True)),
            SAFE_MESSAGES.GO_AWAY: (self.stop_following_penguin, self.plugin_config.get('enable_follow_mode', True)),
            SAFE_MESSAGES.U_ARE_SILLY: (self.randomize_clothes, self.plugin_config.get('enable_random_clothing', True)),
            SAFE_MESSAGES.WHERE: (self.random_move, self.plugin_config.get('enable_random_movement_on_demand', True))
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
        await self.room.send_xt('ss', self.id, SAFE_MESSAGES.OK)
    
    async def stop_following_penguin(self):
        if self.following_penguin is None:
            return
        self.following_penguin = None
        await self.room.send_xt('ss', self.id, SAFE_MESSAGES.SEE_U_LATER)
        await asyncio.sleep(2)
        await self.move_to_random_room()
        
    async def disconnect(self):
        del self.server.penguins_by_id[self.id]
        del self.server.penguins_by_username[self.username]

        if self.character in self.server.penguins_by_character_id:
            del self.server.penguins_by_character_id[self.character]
            
        await self.room.remove_penguin(self)
        self._activity_task.cancel()
        self.server.logger.info(f'{self.username} disconnected')
    
    def is_player_close(self, p) -> bool:
        return math.dist((self.x, self.y), (p.x, p.y)) < self.plugin_config.get(
            'interaction_distance', self.default_interaction_distance)
    
    async def randomize_clothes(self):
        self.color = random.choice(self.bot_plugin.items_by_type[ITEM_TYPE.COLOR]).id
        self.head = random.choice(self.bot_plugin.items_by_type[ITEM_TYPE.HEAD]).id
        self.face = random.choice(self.bot_plugin.items_by_type[ITEM_TYPE.FACE]).id
        self.neck = random.choice(self.bot_plugin.items_by_type[ITEM_TYPE.NECK]).id
        self.body = random.choice(self.bot_plugin.items_by_type[ITEM_TYPE.BODY]).id
        self.hand = random.choice(self.bot_plugin.items_by_type[ITEM_TYPE.HAND]).id
        self.feet = random.choice(self.bot_plugin.items_by_type[ITEM_TYPE.FEET]).id
        self.flag = random.choice(self.bot_plugin.items_by_type[ITEM_TYPE.FLAG]).id
        self.photo = random.choice(self.bot_plugin.items_by_type[ITEM_TYPE.PHOTO]).id
        await self.sync_clothes()
            
    async def sync_clothes(self):
        if not self.room:
            return
        await self.room.send_xt('upc', self.id, self.color)
        await self.room.send_xt('uph', self.id, self.head)
        await self.room.send_xt('upf', self.id, self.face)
        await self.room.send_xt('upn', self.id, self.neck)
        await self.room.send_xt('upb', self.id, self.body)
        await self.room.send_xt('upa', self.id, self.hand)
        await self.room.send_xt('upe', self.id, self.feet)
        await self.room.send_xt('upl', self.id, self.flag)
        await self.room.send_xt('upp', self.id, self.photo)
            
    def reset_clothes(self):
        self.head = None
        self.face = None
        self.neck = None
        self.body = None
        self.hand = None
        self.feet = None
        self.flag = None
        self.photo = None
        
    def randomize_position(self):
        self.random_position_in_room(ROOM_AREAS[self.room.id])
        
    def random_position_in_room(self, points: List[Tuple[int, int]]):
        triangles = [(points[0], a, b) for a, b in itertools.pairwise(points[1:])]
        triangles_areas = [0.5 * abs(x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2)) for (x1, y1), (x2, y2), (x3, y3) in triangles]
        (x1, y1), (x2, y2), (x3, y3) = random.choices(triangles, weights=triangles_areas)[0]
        
        r1 = random.random()
        r2 = random.random()
        s1 = math.sqrt(r1)
        
        self.x = int(x1 * (1.0 - s1) + x2 * (1.0 - r2) * s1 + x3 * r2 * s1)
        self.y = int(y1 * (1.0 - s1) + y2 * (1.0 - r2) * s1 + y3 * r2 * s1)
        
    async def move_to_random_room(self):
        bot_rooms = self.plugin_config.get('bot_rooms', self.bot_plugin.default_room_ids)
        available_rooms = [x for x in bot_rooms if self.room is None or x != self.room.id]
        set_room_weights = self.plugin_config.get('room_weights', {})
        room_weights = [set_room_weights.get(str(x), 1) for x in available_rooms]
        await self.join_room(
            self.bot_plugin.server.rooms[random.choices(available_rooms, weights=room_weights)[0]])
        
    async def join_game(self, target_penguin: Penguin, waddle: RoomWaddle):
        if waddle.id in self.plugin_config.get('bot_waddles', self.bot_plugin.default_waddle_ids):
            asyncio.create_task(self.play_game(target_penguin, waddle))
        
    async def play_game(self, target_penguin: Penguin, waddle: RoomWaddle):
        self.server.logger.info(f'{self.username} scheduled to join waddle {waddle.id}')
        await asyncio.sleep(self.plugin_config.get('waddle_join_delay', self.bot_plugin.default_waddle_join_delay))
        
        if target_penguin.waddle != waddle:
            self.server.logger.info(f"Penguin {target_penguin.username} no longer on waddle room, aborting...")
            return
        
        previous_room = self.room
        await waddle.add_penguin(self)
        
        if waddle.game == 'sled':
            game = SledRacing(self)
            await game.play(waddle.id, random.choice(list(game.waddles[waddle.id].keys())))
            
        if previous_room:
            await self.join_room(previous_room)


class PenguinBotRoomSpots:
    spot: RoomSpot
    bot: 'PenguinBot'
    
    def __init__(self, spots_controller: RoomSpotsController, penguin_bot: 'PenguinBot') -> None:
        self.controller = spots_controller
        self.bot = penguin_bot
        self.clothes = {}
        
    def __enter__(self):
        self.spot = next(x.pop(0) for x in self.controller.spots if x)
        self.clothes = {
            ITEM_TYPE.HEAD: self.bot.head,
            ITEM_TYPE.FACE: self.bot.face,
            ITEM_TYPE.NECK: self.bot.neck,
            ITEM_TYPE.BODY: self.bot.body,
            ITEM_TYPE.HAND: self.bot.hand,
            ITEM_TYPE.FEET: self.bot.feet,
        }
        return self.spot
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.bot.head = self.clothes[ITEM_TYPE.HEAD]
        self.bot.face = self.clothes[ITEM_TYPE.FACE]
        self.bot.neck = self.clothes[ITEM_TYPE.NECK]
        self.bot.body = self.clothes[ITEM_TYPE.BODY]
        self.bot.hand = self.clothes[ITEM_TYPE.HAND]
        self.bot.feet = self.clothes[ITEM_TYPE.FEET]
        self.controller.spots[self.spot.priority - 1].append(self.spot)
