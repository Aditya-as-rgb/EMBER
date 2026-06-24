import pygame

# Screen & Timing
SCREEN_W, SCREEN_H = 1024, 768
FPS = 60

# Map Dimensions (Finite but large)
MAP_W, MAP_H = 3200, 3200

# Colors
C_BG          = (12, 8, 20)
C_GRID        = (22, 15, 35)
C_BOUNDARY    = (255, 50, 50, 100)
C_TEXT        = (220, 210, 255)
C_TEXT_DIM    = (110, 100, 140)
C_ACCENT      = (255, 200, 80)
C_DANGER      = (255, 50, 80)
C_GEM         = (100, 255, 200)

# Player Stats
PLAYER_SPEED = 3.5
DASH_SPEED = 12.0
DASH_DURATION = 0.15
DASH_CD = 1.5
DASH_DAMAGE = 50
IFRAME_DURATION = 0.8

# Mechanics
PROJECTILE_LIFE = 4.0
PICKUP_PULL = 8.0

# Boss Config
BOSS_HP_BASE = 1500
BOSS_LEVEL_INTERVAL = 5

# Boss Phases
PHASE_COLORS = [(255, 50, 50), (200, 0, 255), (255, 150, 0)]