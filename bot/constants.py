from collections import defaultdict
from dataclasses import dataclass

@dataclass(frozen=True)
class SafeMessages:
    OK = 22
    HI_THERE = 101
    HOW_U_DOING = 151
    SEE_U_LATER = 212
    FOLLOW_ME = 310
    U_ARE_SILLY = 354
    WHERE = 410
    GO_AWAY = 802
    
@dataclass(frozen=True)
class ItemType:
    COLOR = 1
    HEAD = 2
    FACE = 3
    NECK = 4
    BODY = 5
    HAND = 6
    FEET = 7
    FLAG = 8
    PHOTO = 9
    AWARD = 10
    
ROOM_AREAS = defaultdict(lambda: [(190, 300), (530, 300), (530, 450), (190, 450)])
ROOM_AREAS[100] = [(135, 340), (165, 280), (306, 203), (457, 210), (573, 283), (635, 360), (605, 405), (180, 410)]

SAFE_MESSAGES = SafeMessages()
ITEM_TYPE = ItemType()
