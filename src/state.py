from enum import Enum, auto

class State(Enum):
    MENU = auto()
    PLAYING = auto()
    LEVEL_UP = auto()
    PAUSED = auto()
    GAME_OVER = auto()
