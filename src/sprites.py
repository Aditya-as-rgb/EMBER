import pygame
import math
import random
import os
from constants import SCREEN_W, SCREEN_H, C_BG, C_GRID, C_GEM

class SpriteCache:
    def __init__(self):
        self._cache = {}
    def get_scaled(self, surf, size):
        size = max(2, (size // 2) * 2)
        key = (id(surf), size)
        if key not in self._cache:
            self._cache[key] = pygame.transform.smoothscale(surf, (size, size))
        return self._cache[key]

def create_radial_glow(radius: int, color: tuple, intensity: int = 255) -> pygame.Surface:
    size = radius * 2
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    for r in range(radius, 0, -1):
        alpha = int(intensity * (r / radius) ** 2)
        pygame.draw.circle(surf, (*color, alpha), (radius, radius), r)
    return surf

def create_player_sprite(tier: int = 1) -> pygame.Surface:
    r = 14
    if tier == 2: r = 16
    if tier == 3: r = 18
    size = r * 4; surf = pygame.Surface((size, size), pygame.SRCALPHA)
    cx, cy = size // 2, size // 2
    
    if tier == 1:
        surf.blit(create_radial_glow(r * 2, (255, 100, 30), 100), (0, 0))
        surf.blit(create_radial_glow(r + 4, (255, 200, 80), 200), (cx - (r+4), cy - (r+4)))
        pygame.draw.circle(surf, (255, 220, 150), (cx, cy), r)
        pygame.draw.circle(surf, (255, 255, 220), (cx, cy), r // 2)
    elif tier == 2:
        surf.blit(create_radial_glow(r * 2, (100, 200, 255), 120), (0, 0))
        surf.blit(create_radial_glow(r + 6, (200, 240, 255), 220), (cx - (r+6), cy - (r+6)))
        pygame.draw.circle(surf, (150, 220, 255), (cx, cy), r)
        pygame.draw.circle(surf, (255, 255, 255), (cx, cy), r // 2)
        for i in range(3):
            a = i * (math.tau / 3)
            ex, ey = cx + math.cos(a)*r*1.5, cy + math.sin(a)*r*1.5
            pygame.draw.line(surf, (255,255,255), (cx,cy), (ex,ey), 2)
    else: # Tier 3
        surf.blit(create_radial_glow(r * 3, (255, 50, 255), 150), (0, 0))
        surf.blit(create_radial_glow(r + 8, (200, 100, 255), 240), (cx - (r+8), cy - (r+8)))
        pygame.draw.circle(surf, (200, 100, 255), (cx, cy), r)
        pygame.draw.circle(surf, (255, 200, 255), (cx, cy), r // 2)
        pts = [(cx + math.cos(i*math.tau/6)*r*1.8, cy + math.sin(i*math.tau/6)*r*1.8) for i in range(6)]
        pygame.draw.polygon(surf, (255,255,255), pts, 2)
    return surf

def create_orb_sprite() -> pygame.Surface:
    r = 8; size = r * 4; surf = pygame.Surface((size, size), pygame.SRCALPHA)
    cx, cy = size // 2, size // 2
    surf.blit(create_radial_glow(r * 2, (255, 220, 100), 150), (0, 0))
    pygame.draw.circle(surf, (255, 240, 150), (cx, cy), r)
    return surf

def create_enemy_sprite(kind: str) -> pygame.Surface:
    if kind == 'grunt':
        r = 12; color = (180, 50, 200); size = r * 4; surf = pygame.Surface((size, size), pygame.SRCALPHA)
        cx, cy = size // 2, size // 2
        surf.blit(create_radial_glow(r * 2, color, 80), (0, 0))
        points = [(cx + math.cos(i * math.tau / 10) * (r if i % 2 == 0 else r * 0.6), 
                   cy + math.sin(i * math.tau / 10) * (r if i % 2 == 0 else r * 0.6)) for i in range(10)]
        pygame.draw.polygon(surf, color, points); pygame.draw.polygon(surf, (255, 255, 255), points, 2)
        return surf
    elif kind == 'fast':
        r = 8; color = (50, 200, 255); size = r * 4; surf = pygame.Surface((size, size), pygame.SRCALPHA)
        cx, cy = size // 2, size // 2
        surf.blit(create_radial_glow(r * 2, color, 100), (0, 0))
        points = [(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)]
        pygame.draw.polygon(surf, color, points); pygame.draw.polygon(surf, (255, 255, 255), points, 1)
        return surf
    elif kind == 'tank':
        r = 22; color = (255, 80, 80); size = r * 4; surf = pygame.Surface((size, size), pygame.SRCALPHA)
        cx, cy = size // 2, size // 2
        surf.blit(create_radial_glow(r * 2, color, 60), (0, 0))
        points = [(cx + math.cos(i * math.pi / 3) * r, cy + math.sin(i * math.pi / 3) * r) for i in range(6)]
        pygame.draw.polygon(surf, color, points); pygame.draw.polygon(surf, (255, 255, 255), points, 3)
        return surf
    elif kind == 'bomber':
        r = 14; color = (255, 160, 50); size = r * 4; surf = pygame.Surface((size, size), pygame.SRCALPHA)
        cx, cy = size // 2, size // 2
        surf.blit(create_radial_glow(r * 2, color, 100), (0, 0))
        pygame.draw.circle(surf, color, (cx, cy), r)
        pygame.draw.circle(surf, (255, 255, 255), (cx, cy), r, 2)
        # Fuse
        pygame.draw.line(surf, (100, 50, 0), (cx, cy - r), (cx, cy - r - 6), 3)
        pygame.draw.circle(surf, (255, 50, 50), (cx, cy - r - 8), 3)
        return surf
    elif kind == 'splitter':
        r = 16; color = (100, 255, 50); size = r * 4; surf = pygame.Surface((size, size), pygame.SRCALPHA)
        cx, cy = size // 2, size // 2
        surf.blit(create_radial_glow(r * 2, color, 80), (0, 0))
        pygame.draw.circle(surf, color, (cx, cy), r)
        pygame.draw.line(surf, (50, 100, 20), (cx - r, cy), (cx + r, cy), 2)
        pygame.draw.line(surf, (50, 100, 20), (cx, cy - r), (cx, cy + r), 2)
        return surf
    return pygame.Surface((16, 16), pygame.SRCALPHA)

def create_enemy_sprite_charger() -> pygame.Surface:
    r = 13; color = (255, 140, 0); size = r * 4; surf = pygame.Surface((size, size), pygame.SRCALPHA)
    cx, cy = size // 2, size // 2
    surf.blit(create_radial_glow(r * 2, color, 90), (0, 0))
    pts = [(cx + r, cy), (cx - r, cy - r + 3), (cx - r + 6, cy), (cx - r, cy + r - 3)]
    pygame.draw.polygon(surf, color, pts)
    pygame.draw.polygon(surf, (255, 220, 100), pts, 2)
    pygame.draw.circle(surf, (255, 255, 200), (cx - 2, cy), 4)
    return surf

def create_enemy_sprite_teleporter() -> pygame.Surface:
    r = 10; color = (0, 255, 180); size = r * 4; surf = pygame.Surface((size, size), pygame.SRCALPHA)
    cx, cy = size // 2, size // 2
    surf.blit(create_radial_glow(r * 2, color, 100), (0, 0))
    pts = [(cx + math.cos(i * math.pi / 3) * r, cy + math.sin(i * math.pi / 3) * r) for i in range(6)]
    pygame.draw.polygon(surf, (0, 80, 60), pts)
    pygame.draw.polygon(surf, color, pts, 2)
    pygame.draw.line(surf, color, (cx, cy - 6), (cx, cy + 6), 2)
    pygame.draw.line(surf, color, (cx - 5, cy - 3), (cx + 5, cy - 3), 2)
    return surf

def create_enemy_sprite_shooter() -> pygame.Surface:
    r = 11; color = (255, 80, 180); size = r * 4; surf = pygame.Surface((size, size), pygame.SRCALPHA)
    cx, cy = size // 2, size // 2
    surf.blit(create_radial_glow(r * 2, color, 80), (0, 0))
    pygame.draw.circle(surf, (100, 20, 60), (cx, cy), r)
    pygame.draw.circle(surf, color, (cx, cy), r, 2)
    for angle in [0, math.pi/2, math.pi, 3*math.pi/2]:
        ex, ey = cx + math.cos(angle) * r, cy + math.sin(angle) * r
        pygame.draw.line(surf, color, (cx, cy), (int(ex), int(ey)), 3)
        pygame.draw.circle(surf, (255, 200, 230), (int(ex), int(ey)), 3)
    return surf

def create_boss_sprite(phase: int) -> pygame.Surface:
    size = 128; surf = pygame.Surface((size, size), pygame.SRCALPHA)
    cx, cy = size // 2, size // 2
    color = [(255, 50, 50), (200, 0, 255), (255, 150, 0)][phase % 3]
    surf.blit(create_radial_glow(56, color, 60), (cx - 56, cy - 56))
    pts = [(cx + math.cos(i * math.tau / 8) * 44, cy + math.sin(i * math.tau / 8) * 44) for i in range(8)]
    pygame.draw.polygon(surf, tuple(c // 2 for c in color), pts)
    pygame.draw.polygon(surf, color, pts, 3)
    pygame.draw.circle(surf, tuple(c // 3 for c in color), (cx, cy), 22)
    pygame.draw.circle(surf, color, (cx, cy), 22, 3)
    pygame.draw.circle(surf, (255, 255, 255), (cx, cy), 8)
    for i in range(8):
        angle = i * math.tau / 8
        x1, y1 = cx + math.cos(angle) * 22, cy + math.sin(angle) * 22
        x2, y2 = cx + math.cos(angle) * 44, cy + math.sin(angle) * 44
        pygame.draw.line(surf, color, (int(x1), int(y1)), (int(x2), int(y2)), 3)
    return surf

def create_projectile_sprite() -> pygame.Surface:
    size = 16; surf = pygame.Surface((size, size), pygame.SRCALPHA)
    cx, cy = size // 2, size // 2
    pygame.draw.circle(surf, (255, 80, 180, 200), (cx, cy), 5)
    pygame.draw.circle(surf, (255, 200, 240), (cx, cy), 2)
    return surf

def create_gem_sprite() -> pygame.Surface:
    r = 6; size = r * 4; surf = pygame.Surface((size, size), pygame.SRCALPHA)
    cx, cy = size // 2, size // 2
    surf.blit(create_radial_glow(r * 2, C_GEM, 120), (0, 0))
    points = [(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)]
    pygame.draw.polygon(surf, C_GEM, points); pygame.draw.polygon(surf, (255, 255, 255), points, 1)
    return surf

def create_background() -> pygame.Surface:
    surf = pygame.Surface((SCREEN_W, SCREEN_H)); surf.fill(C_BG)
    sp = 48
    for x in range(0, SCREEN_W, sp): pygame.draw.line(surf, C_GRID, (x, 0), (x, SCREEN_H))
    for y in range(0, SCREEN_H, sp): pygame.draw.line(surf, C_GRID, (0, y), (SCREEN_W, y))
    for _ in range(100):
        sx, sy = random.randint(0, SCREEN_W), random.randint(0, SCREEN_H)
        b = random.randint(30, 90); surf.set_at((sx, sy), (b, b, b + 20))
    return surf

def load_sprite(filename: str, fallback_func) -> pygame.Surface:
    filepath = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
    if os.path.exists(filepath):
        try: return pygame.image.load(filepath).convert_alpha()
        except Exception: pass
    return fallback_func()