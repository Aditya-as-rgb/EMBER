#!/usr/bin/env python3
"""
EMBER: Infinite Edition — A juicy survival auto-battler for Linux.
Dependencies: pygame, numpy
"""

import pygame
import math
import random
import sys
import os
from dataclasses import dataclass
from enum import Enum, auto
from typing import List, Tuple

# Try importing numpy for procedural audio
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

# ============================================================
# CONFIG & CONSTANTS
# ============================================================
SCREEN_W, SCREEN_H = 1024, 768
FPS = 60

C_BG          = (12, 8, 20)
C_GRID        = (22, 15, 35)
C_TEXT        = (220, 210, 255)
C_TEXT_DIM    = (110, 100, 140)
C_ACCENT      = (255, 200, 80)
C_DANGER      = (255, 50, 80)
C_GEM         = (100, 255, 200)

PLAYER_SPEED = 3.5
DASH_SPEED = 12.0
DASH_DURATION = 0.15
DASH_CD = 1.5


# ============================================================
# STATE MACHINE
# ============================================================
class State(Enum):
    MENU = auto()
    PLAYING = auto()
    LEVEL_UP = auto()
    PAUSED = auto()
    GAME_OVER = auto()


# ============================================================
# PROCEDURAL AUDIO
# ============================================================
class Audio:
    def __init__(self):
        self.enabled = True
        self.muted = False
        self.sfx = {}
        self.pickup_idx = 0
        
        if not HAS_NUMPY:
            self.enabled = False
            return
            
        try:
            pygame.mixer.pre_init(44100, -16, 2, 256)
            pygame.mixer.init()
            self._build()
        except Exception:
            self.enabled = False

    def _make(self, samples):
        samples = np.clip(samples, -1, 1)
        stereo = np.column_stack([samples, samples])
        arr = (stereo * 32767).astype(np.int16)
        return pygame.sndarray.make_sound(arr)

    def _build(self):
        sr = 44100
        
        # Dash: quick sweep down
        d = 0.15; t = np.linspace(0, d, int(sr * d), endpoint=False)
        env = np.exp(-t * 15)
        freq = 600 - 400 * (t / d)
        self.sfx['dash'] = self._make(0.3 * env * np.sin(2 * np.pi * freq * t))
        
        # Hit: short blip
        d = 0.05; t = np.linspace(0, d, int(sr * d), endpoint=False)
        env = np.exp(-t * 40)
        self.sfx['hit'] = self._make(0.25 * env * np.sin(2 * np.pi * 800 * t))
        
        # Explode: noise + low sine
        d = 0.3; t = np.linspace(0, d, int(sr * d), endpoint=False)
        env = np.exp(-t * 8)
        noise = np.random.uniform(-1, 1, len(t))
        self.sfx['explode'] = self._make(0.3 * env * noise + 0.2 * env * np.sin(2 * np.pi * 60 * t))
        
        # Level up: rising sweep
        d = 0.5; t = np.linspace(0, d, int(sr * d), endpoint=False)
        env = np.exp(-t * 3) * (1 - np.exp(-t * 50))
        freq = 400 + 800 * (t / d)
        self.sfx['levelup'] = self._make(0.3 * env * np.sin(2 * np.pi * freq * t))
        
        # Pickups: array of 5 ascending notes
        self.sfx['pickup'] = []
        for i in range(5):
            f = 800 + i * 150
            d = 0.08; t = np.linspace(0, d, int(sr * d), endpoint=False)
            env = np.exp(-t * 25)
            self.sfx['pickup'].append(self._make(0.15 * env * np.sin(2 * np.pi * f * t)))

    def play(self, name, vol=1.0):
        if self.enabled and not self.muted and name in self.sfx:
            s = self.sfx[name]
            if isinstance(s, list):
                s = s[self.pickup_idx]
                self.pickup_idx = (self.pickup_idx + 1) % len(self.sfx[name])  # use original list
            s.set_volume(vol)
            s.play()

    def toggle_mute(self):
        self.muted = not self.muted


# ============================================================
# PROCEDURAL TEXTURES (Fallbacks)
# ============================================================
def create_radial_glow(radius: int, color: Tuple[int, int, int], intensity: int = 255) -> pygame.Surface:
    size = radius * 2
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    for r in range(radius, 0, -1):
        alpha = int(intensity * (r / radius) ** 2)
        pygame.draw.circle(surf, (*color, alpha), (radius, radius), r)
    return surf

def create_player_sprite() -> pygame.Surface:
    r = 14; size = r * 4; surf = pygame.Surface((size, size), pygame.SRCALPHA)
    cx, cy = size // 2, size // 2
    surf.blit(create_radial_glow(r * 2, (255, 100, 30), 100), (0, 0))
    surf.blit(create_radial_glow(r + 4, (255, 200, 80), 200), (cx - (r+4), cy - (r+4)))
    pygame.draw.circle(surf, (255, 220, 150), (cx, cy), r)
    pygame.draw.circle(surf, (255, 255, 220), (cx, cy), r // 2)
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
        points = []
        for i in range(10):
            angle = i * (math.tau / 10); rad = r if i % 2 == 0 else r * 0.6
            points.append((cx + math.cos(angle) * rad, cy + math.sin(angle) * rad))
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
    return pygame.Surface((16, 16), pygame.SRCALPHA)

def create_gem_sprite() -> pygame.Surface:
    r = 6; size = r * 4; surf = pygame.Surface((size, size), pygame.SRCALPHA)
    cx, cy = size // 2, size // 2
    surf.blit(create_radial_glow(r * 2, C_GEM, 120), (0, 0))
    points = [(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)]
    pygame.draw.polygon(surf, C_GEM, points); pygame.draw.polygon(surf, (255, 255, 255), points, 1)
    return surf

def create_enemy_sprite_charger() -> pygame.Surface:
    r = 13; color = (255, 140, 0); size = r * 4; surf = pygame.Surface((size, size), pygame.SRCALPHA)
    cx, cy = size // 2, size // 2
    surf.blit(create_radial_glow(r * 2, color, 90), (0, 0))
    # Arrow/wedge shape pointing right
    pts = [(cx + r, cy), (cx - r, cy - r + 3), (cx - r + 6, cy), (cx - r, cy + r - 3)]
    pygame.draw.polygon(surf, color, pts)
    pygame.draw.polygon(surf, (255, 220, 100), pts, 2)
    pygame.draw.circle(surf, (255, 255, 200), (cx - 2, cy), 4)
    return surf

def create_enemy_sprite_teleporter() -> pygame.Surface:
    r = 10; color = (0, 255, 180); size = r * 4; surf = pygame.Surface((size, size), pygame.SRCALPHA)
    cx, cy = size // 2, size // 2
    surf.blit(create_radial_glow(r * 2, color, 100), (0, 0))
    # Hexagon
    pts = [(cx + math.cos(i * math.pi / 3) * r, cy + math.sin(i * math.pi / 3) * r) for i in range(6)]
    pygame.draw.polygon(surf, (0, 80, 60), pts)
    pygame.draw.polygon(surf, color, pts, 2)
    # Inner symbol
    pygame.draw.line(surf, color, (cx, cy - 6), (cx, cy + 6), 2)
    pygame.draw.line(surf, color, (cx - 5, cy - 3), (cx + 5, cy - 3), 2)
    return surf

def create_enemy_sprite_shooter() -> pygame.Surface:
    r = 11; color = (255, 80, 180); size = r * 4; surf = pygame.Surface((size, size), pygame.SRCALPHA)
    cx, cy = size // 2, size // 2
    surf.blit(create_radial_glow(r * 2, color, 80), (0, 0))
    pygame.draw.circle(surf, (100, 20, 60), (cx, cy), r)
    pygame.draw.circle(surf, color, (cx, cy), r, 2)
    # Cannon barrels
    for angle in [0, math.pi/2, math.pi, 3*math.pi/2]:
        ex, ey = cx + math.cos(angle) * r, cy + math.sin(angle) * r
        pygame.draw.line(surf, color, (cx, cy), (int(ex), int(ey)), 3)
        pygame.draw.circle(surf, (255, 200, 230), (int(ex), int(ey)), 3)
    return surf

def create_boss_sprite(phase: int) -> pygame.Surface:
    size = 128; surf = pygame.Surface((size, size), pygame.SRCALPHA)
    cx, cy = size // 2, size // 2
    color = [(255, 50, 50), (200, 0, 255), (255, 150, 0)][phase % 3]
    # Outer glow
    surf.blit(create_radial_glow(56, color, 60), (cx - 56, cy - 56))
    # Outer ring
    pts = [(cx + math.cos(i * math.tau / 8) * 44, cy + math.sin(i * math.tau / 8) * 44) for i in range(8)]
    pygame.draw.polygon(surf, tuple(c // 2 for c in color), pts)
    pygame.draw.polygon(surf, color, pts, 3)
    # Inner core
    pygame.draw.circle(surf, tuple(c // 3 for c in color), (cx, cy), 22)
    pygame.draw.circle(surf, color, (cx, cy), 22, 3)
    pygame.draw.circle(surf, (255, 255, 255), (cx, cy), 8)
    # Spikes
    for i in range(8):
        angle = i * math.tau / 8
        x1 = cx + math.cos(angle) * 22; y1 = cy + math.sin(angle) * 22
        x2 = cx + math.cos(angle) * 44; y2 = cy + math.sin(angle) * 44
        pygame.draw.line(surf, color, (int(x1), int(y1)), (int(x2), int(y2)), 3)
    return surf

def create_projectile_sprite() -> pygame.Surface:
    size = 16; surf = pygame.Surface((size, size), pygame.SRCALPHA)
    cx, cy = size // 2, size // 2
    pygame.draw.circle(surf, (255, 80, 180, 200), (cx, cy), 5)
    pygame.draw.circle(surf, (255, 200, 240), (cx, cy), 2)
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


# ============================================================
# FX (Particles, Popups, Shake)
# ============================================================
@dataclass
class Particle:
    x: float; y: float; vx: float; vy: float
    life: float; max_life: float
    color: Tuple[int, int, int]; size: float
    def update(self, dt):
        self.x += self.vx * dt * 60; self.y += self.vy * dt * 60
        self.vx *= 0.94; self.vy *= 0.94; self.life -= dt
    @property
    def alive(self): return self.life > 0
    def draw(self, surf, cam_x, cam_y):
        a = max(0, self.life / self.max_life); r = max(1, int(self.size * a))
        col = (*self.color, int(255 * a)); s = pygame.Surface((r * 4, r * 4), pygame.SRCALPHA)
        pygame.draw.circle(s, col, (r * 2, r * 2), r * 2)
        surf.blit(s, (self.x - r * 2 - cam_x, self.y - r * 2 - cam_y), special_flags=pygame.BLEND_ADD)

@dataclass
class TextPopup:
    x: float; y: float; text: str
    life: float; max_life: float
    color: Tuple[int, int, int]
    def update(self, dt):
        self.y -= 40 * dt; self.life -= dt
    @property
    def alive(self): return self.life > 0
    def draw(self, surf, font, cam_x, cam_y):
        a = max(0, self.life / self.max_life)
        ts = font.render(self.text, True, self.color); ts.set_alpha(int(255 * a))
        surf.blit(ts, (self.x - ts.get_width()//2 - cam_x, self.y - cam_y))

class FX:
    def __init__(self):
        self.particles: List[Particle] = []
        self.popups: List[TextPopup] = []
    def burst(self, x, y, n, color, spd=(1, 5), life=(0.3, 0.7), size=(2, 5)):
        for _ in range(n):
            a = random.uniform(0, math.tau); s = random.uniform(*spd); l = random.uniform(*life)
            self.particles.append(Particle(x, y, math.cos(a)*s, math.sin(a)*s, l, l, color, random.uniform(*size)))
    def popup(self, x, y, text, color):
        self.popups.append(TextPopup(x, y, text, 0.8, 0.8, color))
    def update(self, dt):
        for p in self.particles: p.update(dt)
        for p in self.popups: p.update(dt)
        self.particles = [p for p in self.particles if p.alive]
        self.popups = [p for p in self.popups if p.alive]
    def draw(self, surf, font, cam_x, cam_y):
        for p in self.particles: p.draw(surf, cam_x, cam_y)
        for p in self.popups: p.draw(surf, font, cam_x, cam_y)
    def clear(self):
        self.particles.clear(); self.popups.clear()

class Shake:
    def __init__(self):
        self.intensity = 0; self.timer = 0; self.max_timer = 0; self.offset = (0, 0)
    def trigger(self, i, d=0.3):
        if i > self.intensity * (self.timer / max(self.max_timer, 0.001)):
            self.intensity = i; self.timer = d; self.max_timer = d
    def update(self, dt):
        if self.timer > 0:
            self.timer -= dt
            m = self.intensity * max(0, self.timer / max(self.max_timer, 0.001))
            self.offset = (random.uniform(-m, m), random.uniform(-m, m))
        else:
            self.intensity = 0; self.offset = (0, 0)

class Camera:
    def __init__(self):
        self.x = 0; self.y = 0
    def update(self, dt, target_x, target_y):
        tx = target_x - SCREEN_W / 2
        ty = target_y - SCREEN_H / 2
        # Smooth follow
        self.x += (tx - self.x) * min(1, dt * 8)
        self.y += (ty - self.y) * min(1, dt * 8)


# ============================================================
# ENTITIES
# ============================================================
class Player:
    def __init__(self, x, y, sprite, audio):
        self.x, self.y = x, y
        self.sprite = sprite; self.audio = audio
        self.radius = 14
        self.hp = 100; self.max_hp = 100
        self.xp = 0; self.xp_to_next = 5; self.level = 1
        
        self.speed = PLAYER_SPEED
        self.orbit_count = 3; self.orbit_radius = 70; self.orbit_speed = 2.5
        self.orbit_damage = 25; self.orbit_size = 8; self.pickup_radius = 80
        
        self.orbit_angle = 0; self.dash_cd = 0; self.dash_t = 0
        self.dash_dir = (0, 0); self.iframes = 0

    def update(self, dt, keys, fx):
        dx, dy = 0, 0
        if keys[pygame.K_w] or keys[pygame.K_UP]: dy -= 1
        if keys[pygame.K_s] or keys[pygame.K_DOWN]: dy += 1
        if keys[pygame.K_a] or keys[pygame.K_LEFT]: dx -= 1
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]: dx += 1
        
        if dx != 0 or dy != 0:
            mag = math.hypot(dx, dy); dx, dy = dx/mag, dy/mag
            
        if self.dash_t > 0:
            self.dash_t -= dt
            self.x += self.dash_dir[0] * DASH_SPEED * dt * 60
            self.y += self.dash_dir[1] * DASH_SPEED * dt * 60
            fx.burst(self.x, self.y, 2, (255, 200, 100), spd=(0, 1), life=(0.1, 0.2), size=(2, 4))
        else:
            self.x += dx * self.speed * dt * 60
            self.y += dy * self.speed * dt * 60

        self.orbit_angle += self.orbit_speed * dt
        if self.dash_cd > 0: self.dash_cd -= dt
        if self.iframes > 0: self.iframes -= dt

    def try_dash(self, keys, fx):
        if self.dash_cd <= 0:
            dx, dy = 0, 0
            if keys[pygame.K_w] or keys[pygame.K_UP]: dy -= 1
            if keys[pygame.K_s] or keys[pygame.K_DOWN]: dy += 1
            if keys[pygame.K_a] or keys[pygame.K_LEFT]: dx -= 1
            if keys[pygame.K_d] or keys[pygame.K_RIGHT]: dx += 1
            if dx != 0 or dy != 0:
                mag = math.hypot(dx, dy); self.dash_dir = (dx/mag, dy/mag)
                self.dash_t = DASH_DURATION; self.dash_cd = DASH_CD
                self.iframes = DASH_DURATION + 0.1
                fx.burst(self.x, self.y, 15, (255, 220, 100), spd=(2, 6), life=(0.2, 0.4))
                self.audio.play('dash', 0.3)

    def take_damage(self, dmg, fx, shake):
        if self.iframes > 0: return
        self.hp -= dmg; self.iframes = 0.8
        fx.burst(self.x, self.y, 12, C_DANGER, spd=(2, 5)); shake.trigger(8, 0.2)

    def add_xp(self, amount, fx):
        self.xp += amount
        return self.xp >= self.xp_to_next

    def get_orb_positions(self):
        return [(self.x + math.cos(self.orbit_angle + (i / self.orbit_count) * math.tau) * self.orbit_radius,
                 self.y + math.sin(self.orbit_angle + (i / self.orbit_count) * math.tau) * self.orbit_radius)
                for i in range(self.orbit_count)]

    def draw(self, surf, cam_x, cam_y):
        # Pickup radius visual
        s = pygame.Surface((self.pickup_radius*2, self.pickup_radius*2), pygame.SRCALPHA)
        pygame.draw.circle(s, (100, 255, 200, 15), (self.pickup_radius, self.pickup_radius), self.pickup_radius)
        surf.blit(s, (self.x - self.pickup_radius - cam_x, self.y - self.pickup_radius - cam_y))

        if self.dash_cd > 0:
            p = 1 - (self.dash_cd / DASH_CD)
            pygame.draw.arc(surf, (50, 50, 80), 
                           (self.x-20 - cam_x, self.y-20 - cam_y, 40, 40), 
                           -math.pi/2, -math.pi/2 + p * math.tau, 2)

        if not (self.iframes > 0 and int(self.iframes * 20) % 2 == 0):
            rect = self.sprite.get_rect(center=(int(self.x - cam_x), int(self.y - cam_y)))
            surf.blit(self.sprite, rect)

class Enemy:
    def __init__(self, x, y, kind, sprite, audio, hp_mult=1.0):
        self.x, self.y = x, y; self.kind = kind; self.sprite = sprite; self.audio = audio
        self.radius = {'grunt': 12, 'fast': 8, 'tank': 22,
                       'charger': 13, 'teleporter': 10, 'shooter': 11, 'boss': 40}.get(kind, 12)
        self.spawn_t = 0.4
        self.pulse_t = random.uniform(0, math.tau)
        self.flash_t = 0.0

        cfg = {
            'grunt':      (1.4,  30,  10, 1),
            'fast':       (2.8,  15,   5, 2),
            'tank':       (0.8, 150,  25, 5),
            'charger':    (1.0,  60,  20, 3),
            'teleporter': (1.2,  45,  15, 3),
            'shooter':    (0.9,  50,  12, 3),
            'boss':       (0.7, 800,  30, 20),
        }
        c = cfg.get(kind, cfg['grunt'])
        self.speed, self.hp, self.dmg, self.xp_val = c
        self.hp = int(self.hp * hp_mult)
        self.max_hp = self.hp

        # Charger state
        self.charge_cd = random.uniform(2, 4)
        self.charge_t = 0.0
        self.charge_vx = 0.0; self.charge_vy = 0.0
        self.charge_speed = 7.0

        # Teleporter state
        self.teleport_cd = random.uniform(3, 5)

        # Shooter state
        self.shoot_cd = random.uniform(1.5, 2.5)
        self.pending_projectiles: List = []   # filled by update, consumed by Game

        # Boss state
        self.boss_phase = 0
        self.boss_action_cd = 1.5
        self.boss_spin = 0.0

    def update(self, dt, player):
        self.pulse_t += dt * 4
        if self.flash_t > 0: self.flash_t -= dt
        if self.spawn_t > 0:
            self.spawn_t -= dt; return

        dx, dy = player.x - self.x, player.y - self.y
        d = math.hypot(dx, dy) or 1

        if self.kind == 'charger':
            self.charge_cd -= dt
            if self.charge_t > 0:
                self.charge_t -= dt
                self.x += self.charge_vx * dt * 60
                self.y += self.charge_vy * dt * 60
            else:
                self.x += (dx/d) * self.speed * dt * 60
                self.y += (dy/d) * self.speed * dt * 60
                if self.charge_cd <= 0:
                    # Lock on and lunge
                    self.charge_vx, self.charge_vy = (dx/d) * self.charge_speed, (dy/d) * self.charge_speed
                    self.charge_t = 0.35
                    self.charge_cd = random.uniform(2.5, 4.0)

        elif self.kind == 'teleporter':
            self.teleport_cd -= dt
            self.x += (dx/d) * self.speed * dt * 60
            self.y += (dy/d) * self.speed * dt * 60
            if self.teleport_cd <= 0:
                # Blink to a random spot near the player
                angle = random.uniform(0, math.tau)
                dist = random.uniform(120, 220)
                self.x = player.x + math.cos(angle) * dist
                self.y = player.y + math.sin(angle) * dist
                self.teleport_cd = random.uniform(2.5, 4.5)

        elif self.kind == 'shooter':
            # Keep distance, orbit slowly
            target_dist = 220
            if d > target_dist + 20:
                self.x += (dx/d) * self.speed * dt * 60
                self.y += (dy/d) * self.speed * dt * 60
            elif d < target_dist - 20:
                self.x -= (dx/d) * self.speed * dt * 60
                self.y -= (dy/d) * self.speed * dt * 60
            else:
                # Strafe
                self.x += (-dy/d) * self.speed * 0.8 * dt * 60
                self.y += (dx/d) * self.speed * 0.8 * dt * 60

            self.shoot_cd -= dt
            if self.shoot_cd <= 0:
                # Fire 3 spread shots toward player
                for spread in [-0.2, 0, 0.2]:
                    angle = math.atan2(dy, dx) + spread
                    spd = 3.2
                    self.pending_projectiles.append((
                        self.x, self.y,
                        math.cos(angle) * spd, math.sin(angle) * spd
                    ))
                self.shoot_cd = random.uniform(1.8, 2.8)

        elif self.kind == 'boss':
            self.boss_spin += dt * 1.5
            self.boss_action_cd -= dt
            # Slowly drift toward player
            self.x += (dx/d) * self.speed * dt * 60
            self.y += (dy/d) * self.speed * dt * 60
            # Update phase by HP
            if self.hp < self.max_hp * 0.66: self.boss_phase = 1
            if self.hp < self.max_hp * 0.33: self.boss_phase = 2

            if self.boss_action_cd <= 0:
                spd = 3.5 + self.boss_phase * 0.8
                if self.boss_phase == 0:
                    # Fire ring of 8
                    for i in range(8):
                        a = i * math.tau / 8
                        self.pending_projectiles.append((self.x, self.y, math.cos(a)*spd, math.sin(a)*spd))
                elif self.boss_phase == 1:
                    # Fire toward player + 2 flanking
                    for spread in [-0.35, 0, 0.35]:
                        a = math.atan2(dy, dx) + spread
                        self.pending_projectiles.append((self.x, self.y, math.cos(a)*spd, math.sin(a)*spd))
                else:
                    # Spiral burst
                    for i in range(12):
                        a = self.boss_spin + i * math.tau / 12
                        self.pending_projectiles.append((self.x, self.y, math.cos(a)*spd, math.sin(a)*spd))
                self.boss_action_cd = max(0.6, 1.5 - self.boss_phase * 0.3)
        else:
            self.x += (dx/d) * self.speed * dt * 60
            self.y += (dy/d) * self.speed * dt * 60

    def take_damage(self, dmg):
        self.hp -= dmg
        self.flash_t = 0.08

    def draw(self, surf, cam_x, cam_y):
        scale = 1.0 + math.sin(self.pulse_t) * 0.08
        # Charger glows orange when charging
        spr = self.sprite
        if self.kind == 'charger' and self.charge_t > 0:
            scale = 1.2
        if self.kind == 'boss':
            scale = 1.0 + math.sin(self.pulse_t) * 0.04

        w, h = spr.get_size()
        new_w, new_h = max(1, int(w * scale)), max(1, int(h * scale))
        spr = pygame.transform.smoothscale(spr, (new_w, new_h))
        rect = spr.get_rect(center=(int(self.x - cam_x), int(self.y - cam_y)))

        if self.spawn_t > 0:
            prog = 1 - self.spawn_t / 0.4
            r = int(30 * (1 - prog) + self.radius * prog)
            s = pygame.Surface((r*4, r*4), pygame.SRCALPHA)
            pygame.draw.circle(s, (255, 255, 255, int(255*prog)), (r*2, r*2), r, 2)
            surf.blit(s, (self.x-r*2 - cam_x, self.y-r*2 - cam_y), special_flags=pygame.BLEND_ADD)
            return

        if self.flash_t > 0:
            flash_spr = spr.copy()
            flash_spr.fill((255, 255, 255, 255), special_flags=pygame.BLEND_RGB_MULT)
            surf.blit(flash_spr, rect)
        else:
            surf.blit(spr, rect)

        # Boss warning ring
        if self.kind == 'boss':
            r = int(self.radius * 1.3)
            phase_colors = [(255, 50, 50), (200, 0, 255), (255, 150, 0)]
            ring = pygame.Surface((r*2+4, r*2+4), pygame.SRCALPHA)
            pygame.draw.circle(ring, (*phase_colors[self.boss_phase], 80), (r+2, r+2), r, 3)
            surf.blit(ring, (self.x - r - 2 - cam_x, self.y - r - 2 - cam_y), special_flags=pygame.BLEND_ADD)

        # HP bar — bigger for boss
        if self.hp < self.max_hp:
            bw = rect.width if self.kind != 'boss' else 120
            bx = rect.x if self.kind != 'boss' else int(self.x - cam_x) - 60
            by = rect.y - 10 if self.kind != 'boss' else int(self.y - cam_y) - 55
            bh = 3 if self.kind != 'boss' else 8
            pygame.draw.rect(surf, (40, 10, 40), (bx, by, bw, bh))
            hp_color = C_DANGER if self.kind != 'boss' else phase_colors[self.boss_phase] if self.kind == 'boss' else C_DANGER
            if self.kind == 'boss': hp_color = [(255, 50, 50), (200, 0, 255), (255, 150, 0)][self.boss_phase]
            pygame.draw.rect(surf, hp_color, (bx, by, int(bw*(self.hp/self.max_hp)), bh))
            if self.kind == 'boss':
                pygame.draw.rect(surf, (200, 200, 200), (bx, by, bw, bh), 1)
                label = pygame.font.SysFont("monospace", 13, bold=True).render(
                    f"BOSS  {int(self.hp)}/{self.max_hp}", True, hp_color)
                surf.blit(label, (bx, by - 16))

class Gem:
    def __init__(self, x, y, sprite):
        self.x, self.y = x, y; self.sprite = sprite
        self.radius = 6
        self.vx = random.uniform(-2, 2); self.vy = random.uniform(-2, 2)
        self.attracted = False

    def update(self, dt, player):
        self.x += self.vx * dt * 60; self.y += self.vy * dt * 60
        self.vx *= 0.9; self.vy *= 0.9
        dx, dy = player.x - self.x, player.y - self.y
        d = math.hypot(dx, dy)
        if self.attracted or d < player.pickup_radius:
            self.attracted = True; pull = 8.0
            self.x += (dx/d) * pull * dt * 60; self.y += (dy/d) * pull * dt * 60

    def draw(self, surf, cam_x, cam_y):
        rect = self.sprite.get_rect(center=(int(self.x - cam_x), int(self.y - cam_y)))
        surf.blit(self.sprite, rect)


class Projectile:
    def __init__(self, x, y, vx, vy, sprite):
        self.x, self.y = x, y
        self.vx, self.vy = vx, vy
        self.sprite = sprite
        self.radius = 5
        self.life = 4.0  # seconds before despawn

    def update(self, dt):
        self.x += self.vx * dt * 60
        self.y += self.vy * dt * 60
        self.life -= dt

    @property
    def alive(self): return self.life > 0

    def draw(self, surf, cam_x, cam_y):
        rect = self.sprite.get_rect(center=(int(self.x - cam_x), int(self.y - cam_y)))
        surf.blit(self.sprite, rect)
        # Trail
        trail = pygame.Surface((8, 8), pygame.SRCALPHA)
        pygame.draw.circle(trail, (255, 80, 180, 80), (4, 4), 4)
        surf.blit(trail, (int(self.x - self.vx * 2 - cam_x) - 4, int(self.y - self.vy * 2 - cam_y) - 4),
                  special_flags=pygame.BLEND_ADD)


# ============================================================
# UPGRADES
# ============================================================
UPGRADES = [
    {"name": "Flare",       "desc": "+1 Orbiting Orb",          "color": (255, 200, 80),  "apply": lambda p: setattr(p, 'orbit_count', p.orbit_count + 1)},
    {"name": "Wildfire",    "desc": "+40% Orbit Speed",         "color": (255, 100, 50),  "apply": lambda p: setattr(p, 'orbit_speed', p.orbit_speed * 1.4)},
    {"name": "Inferno",     "desc": "+15 Orbit Damage",         "color": (255, 50, 50),   "apply": lambda p: setattr(p, 'orbit_damage', p.orbit_damage + 15)},
    {"name": "Expansion",   "desc": "+25 Orbit Radius",         "color": (100, 200, 255), "apply": lambda p: setattr(p, 'orbit_radius', p.orbit_radius + 25)},
    {"name": "Magnitude",   "desc": "+3 Orb Size",              "color": (255, 150, 200), "apply": lambda p: setattr(p, 'orbit_size', p.orbit_size + 3)},
    {"name": "Magnetism",   "desc": "+40 Pickup Range",         "color": (100, 255, 200), "apply": lambda p: setattr(p, 'pickup_radius', p.pickup_radius + 40)},
    {"name": "Celerity",    "desc": "+15% Move Speed",          "color": (200, 255, 100), "apply": lambda p: setattr(p, 'speed', p.speed * 1.15)},
    {"name": "Soul Mend",   "desc": "Heal 30 HP",               "color": (100, 255, 100), "apply": lambda p: setattr(p, 'hp', min(p.max_hp, p.hp + 30))},
    {"name": "Vitality",    "desc": "+20 Max HP & Full Heal",   "color": (255, 100, 100), "apply": lambda p: (setattr(p, 'max_hp', p.max_hp + 20), setattr(p, 'hp', p.max_hp))},
]


# ============================================================
# GAME CONTROLLER
# ============================================================
class Game:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
        pygame.display.set_caption("EMBER: Infinite Edition")
        self.clock = pygame.time.Clock()
        
        self.font_l = pygame.font.SysFont("monospace", 54, bold=True)
        self.font_m = pygame.font.SysFont("monospace", 24, bold=True)
        self.font_s = pygame.font.SysFont("monospace", 18)
        self.font_xs = pygame.font.SysFont("monospace", 14)
        
        self.audio = Audio()
        self.state = State.MENU
        self.fx = FX(); self.shake = Shake(); self.camera = Camera()
        self.menu_t = 0; self.high_score = 0

        bg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ember_bg2.jpg")
        if os.path.exists(bg_path):
            raw = pygame.image.load(bg_path).convert()
            self.bg_texture = pygame.transform.scale(raw, (SCREEN_W, SCREEN_H))
            # Darken it so sprites stay readable
            dark = pygame.Surface((SCREEN_W, SCREEN_H))
            dark.fill((0, 0, 0))
            dark.set_alpha(120)  # 0=no effect, 255=fully black — tune this
            self.bg_texture.blit(dark, (0, 0))
        else:
            self.bg_texture = create_background()

        self.spr_player = load_sprite("player.png", create_player_sprite)
        self.spr_orb = load_sprite("orb.png", create_orb_sprite)
        self.spr_gem = load_sprite("gem.png", create_gem_sprite)
        self.spr_enemies = {
            'grunt':       load_sprite("enemy_grunt.png", lambda: create_enemy_sprite('grunt')),
            'fast':        load_sprite("enemy_fast.png",  lambda: create_enemy_sprite('fast')),
            'tank':        load_sprite("enemy_tank.png",  lambda: create_enemy_sprite('tank')),
            'charger':     load_sprite("enemy_charger.png",     create_enemy_sprite_charger),
            'teleporter':  load_sprite("enemy_teleporter.png",  create_enemy_sprite_teleporter),
            'shooter':     load_sprite("enemy_shooter.png",     create_enemy_sprite_shooter),
            'boss':        load_sprite("enemy_boss.png",  lambda: create_boss_sprite(0)),
        }
        self.spr_boss_phases = [create_boss_sprite(i) for i in range(3)]
        self.spr_projectile = load_sprite("projectile.png", create_projectile_sprite)

        self.reset()

    def reset(self):
        self.player = Player(0, 0, self.spr_player, self.audio)
        self.enemies: List[Enemy] = []
        self.gems: List[Gem] = []
        self.projectiles: List[Projectile] = []
        self.fx.clear(); self.shake = Shake()
        self.camera = Camera()
        self.game_time = 0; self.spawn_timer = 0; self.kill_count = 0
        self.upgrade_choices = []
        self.next_boss_time = 60.0
        self.boss_alive = False
        self.boss_warning_t = 0.0

    def spawn_enemy(self, kind_override=None):
        cx, cy = self.camera.x + SCREEN_W / 2, self.camera.y + SCREEN_H / 2
        edge = random.randint(0, 3)
        offset = 50
        if edge == 0:   x, y = cx + random.randint(-SCREEN_W//2, SCREEN_W//2), cy - SCREEN_H//2 - offset
        elif edge == 1: x, y = cx + SCREEN_W//2 + offset, cy + random.randint(-SCREEN_H//2, SCREEN_H//2)
        elif edge == 2: x, y = cx + random.randint(-SCREEN_W//2, SCREEN_W//2), cy + SCREEN_H//2 + offset
        else:           x, y = cx - SCREEN_W//2 - offset, cy + random.randint(-SCREEN_H//2, SCREEN_H//2)

        # HP scales with time
        hp_mult = 1.0 + self.game_time / 60.0

        t = self.game_time; kinds = ['grunt']
        if t > 20:  kinds.append('grunt')
        if t > 40:  kinds.append('charger')
        if t > 45:  kinds.append('fast')
        if t > 70:  kinds.append('shooter')
        if t > 75:  kinds.extend(['fast', 'grunt'])
        if t > 100: kinds.append('tank')
        if t > 110: kinds.append('teleporter')
        if t > 140: kinds.extend(['tank', 'fast', 'charger'])
        if t > 180: kinds.extend(['shooter', 'teleporter'])

        kind = kind_override if kind_override else random.choice(kinds)
        spr = self.spr_enemies.get(kind, self.spr_enemies['grunt'])
        # Use phase sprite for boss
        if kind == 'boss':
            spr = self.spr_boss_phases[0]
        self.enemies.append(Enemy(x, y, kind, spr, self.audio, hp_mult=hp_mult))

    def handle_events(self) -> bool:
        for e in pygame.event.get():
            if e.type == pygame.QUIT: return False
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    if self.state == State.PLAYING: self.state = State.PAUSED
                    elif self.state == State.PAUSED: self.state = State.PLAYING
                    elif self.state == State.MENU: return False
                    elif self.state == State.GAME_OVER: self.state = State.MENU
                if e.key == pygame.K_m:
                    self.audio.toggle_mute()
                if e.key in (pygame.K_RETURN, pygame.K_SPACE):
                    if self.state == State.MENU: self.reset(); self.state = State.PLAYING
                    elif self.state == State.GAME_OVER: self.reset(); self.state = State.PLAYING
                    elif self.state == State.PLAYING: self.player.try_dash(pygame.key.get_pressed(), self.fx)
                    elif self.state == State.LEVEL_UP: 
                        # Allow Space/Enter to skip level up if clicked outside
                        pass 
                if e.key == pygame.K_1 and self.state == State.LEVEL_UP: self.pick_upgrade(0)
                if e.key == pygame.K_2 and self.state == State.LEVEL_UP: self.pick_upgrade(1)
                if e.key == pygame.K_3 and self.state == State.LEVEL_UP: self.pick_upgrade(2)
            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                if self.state == State.LEVEL_UP:
                    for i, rect in enumerate(self.upgrade_rects):
                        if rect.collidepoint(e.pos): self.pick_upgrade(i); break

        keys = pygame.key.get_pressed()
        if keys[pygame.K_SPACE] and self.state == State.PLAYING:
            self.player.try_dash(keys, self.fx)
        return True

    def pick_upgrade(self, idx):
        if idx < len(self.upgrade_choices):
            up = self.upgrade_choices[idx]
            up["apply"](self.player)
            self.fx.popup(self.player.x, self.player.y - 30, up["name"], up["color"])
            self.state = State.PLAYING

    def update(self, dt):
        self.menu_t += dt
        if self.state in (State.PAUSED, State.LEVEL_UP, State.GAME_OVER): return

        self.game_time += dt
        keys = pygame.key.get_pressed()
        self.player.update(dt, keys, self.fx)
        self.camera.update(dt, self.player.x, self.player.y)

        # Boss warning countdown
        if self.boss_warning_t > 0:
            self.boss_warning_t -= dt

        # Boss spawn trigger
        if not self.boss_alive and self.game_time >= self.next_boss_time:
            if self.boss_warning_t <= 0 and self.game_time < self.next_boss_time + 3:
                self.boss_warning_t = 3.0
            if self.game_time >= self.next_boss_time + 3:
                self.spawn_enemy(kind_override='boss')
                self.boss_alive = True
                self.next_boss_time += 60.0
                self.shake.trigger(10, 0.4)

        self.spawn_timer -= dt
        if self.spawn_timer <= 0:
            self.spawn_enemy()
            self.spawn_timer = max(0.2, 1.2 - self.game_time * 0.008)

        for en in self.enemies:
            en.update(dt, self.player)
            # Update boss sprite by phase
            if en.kind == 'boss':
                en.sprite = self.spr_boss_phases[en.boss_phase]
            # Collect projectiles fired by enemies
            for proj_data in en.pending_projectiles:
                self.projectiles.append(Projectile(*proj_data, self.spr_projectile))
            en.pending_projectiles.clear()

        for g in self.gems: g.update(dt, self.player)

        # Update projectiles
        for p in self.projectiles: p.update(dt)
        self.projectiles = [p for p in self.projectiles if p.alive]

        # Projectile vs player collision
        for p in self.projectiles[:]:
            if math.hypot(self.player.x - p.x, self.player.y - p.y) < self.player.radius + p.radius:
                self.player.take_damage(15, self.fx, self.shake)
                self.projectiles.remove(p)

        # Orbital Collisions
        for ox, oy in self.player.get_orb_positions():
            for en in self.enemies[:]:
                if math.hypot(ox - en.x, oy - en.y) < en.radius + self.player.orbit_size:
                    en.take_damage(self.player.orbit_damage)
                    self.audio.play('hit', 0.15)
                    self.fx.burst(ox, oy, 4, (255, 220, 100), spd=(1, 3), life=(0.1, 0.2), size=(1, 3))
                    if en.hp <= 0:
                        if en.kind == 'boss': self.boss_alive = False
                        self.enemies.remove(en); self.kill_count += 1
                        self.audio.play('explode', 0.3)
                        self.fx.burst(en.x, en.y, 15, (255, 100, 50), spd=(2, 6), life=(0.3, 0.6))
                        self.shake.trigger(4 if en.kind != 'boss' else 20, 0.15)
                        gems_n = en.xp_val if en.kind != 'boss' else en.xp_val // 2
                        for _ in range(gems_n): self.gems.append(Gem(en.x, en.y, self.spr_gem))
                        if en.kind == 'boss':
                            self.fx.burst(en.x, en.y, 60, (255, 150, 50), spd=(3, 10), life=(0.5, 1.2))
                            self.fx.popup(en.x, en.y - 60, "BOSS SLAIN!", C_ACCENT)

        # Player Collisions
        for en in self.enemies:
            if en.spawn_t > 0: continue
            if math.hypot(self.player.x - en.x, self.player.y - en.y) < en.radius + self.player.radius:
                self.player.take_damage(en.dmg, self.fx, self.shake)
                dx, dy = en.x - self.player.x, en.y - self.player.y
                d = math.hypot(dx, dy)
                if d > 0: en.x += (dx/d) * 15; en.y += (dy/d) * 15

        for g in self.gems[:]:
            if math.hypot(self.player.x - g.x, self.player.y - g.y) < self.player.radius + g.radius:
                leveled_up = self.player.add_xp(1, self.fx)
                self.gems.remove(g)
                self.audio.play('pickup', 0.4)
                if leveled_up:
                    self.player.xp -= self.player.xp_to_next
                    self.player.level += 1
                    self.player.xp_to_next = int(self.player.xp_to_next * 1.4)
                    self.state = State.LEVEL_UP
                    self.audio.play('levelup', 0.5)
                    self.upgrade_choices = random.sample(UPGRADES, 3)
                    self.upgrade_rects = []
                    break

        if self.player.hp <= 0:
            self.state = State.GAME_OVER
            self.high_score = max(self.high_score, self.kill_count)
            self.fx.burst(self.player.x, self.player.y, 40, (255, 100, 30), spd=(3, 10), life=(0.5, 1.0))
            self.shake.trigger(15, 0.5)

        self.fx.update(dt); self.shake.update(dt)

    def draw(self):
        # Infinite Background Tiling
        bg_x = -int(self.camera.x) % SCREEN_W - SCREEN_W
        bg_y = -int(self.camera.y) % SCREEN_H - SCREEN_H
        for x in range(bg_x, SCREEN_W, SCREEN_W):
            for y in range(bg_y, SCREEN_H, SCREEN_H):
                self.screen.blit(self.bg_texture, (x, y))

        cam_x, cam_y = self.camera.x, self.camera.y
        
        if self.state in (State.PLAYING, State.PAUSED, State.LEVEL_UP, State.GAME_OVER):
            for g in self.gems: g.draw(self.screen, cam_x, cam_y)
            for en in self.enemies: en.draw(self.screen, cam_x, cam_y)
            
            # Draw Orbs
            scaled_orb_size = self.player.orbit_size * 2
            scaled_orb = pygame.transform.smoothscale(self.spr_orb, (scaled_orb_size*4, scaled_orb_size*4))
            for ox, oy in self.player.get_orb_positions():
                rect = scaled_orb.get_rect(center=(int(ox - cam_x), int(oy - cam_y)))
                self.screen.blit(scaled_orb, rect)

            if self.player.hp > 0: self.player.draw(self.screen, cam_x, cam_y)
            for p in self.projectiles: p.draw(self.screen, cam_x, cam_y)
            self.fx.draw(self.screen, self.font_xs, cam_x, cam_y)

        ox, oy = self.shake.offset
        if ox != 0 or oy != 0:
            # Re-blit everything with offset if shaking (simple shake implementation)
            temp_surf = self.screen.copy()
            self.screen.fill(C_BG)
            self.screen.blit(temp_surf, (ox, oy))

        # UI (Not affected by camera)
        if self.state == State.MENU: self.draw_menu()
        elif self.state == State.PLAYING: self.draw_hud()
        elif self.state == State.LEVEL_UP: self.draw_hud(); self.draw_level_up()
        elif self.state == State.PAUSED: self.draw_hud(); self.draw_paused()
        elif self.state == State.GAME_OVER: self.draw_hud(); self.draw_game_over()

        pygame.display.flip()

    def draw_hud(self):
        p = self.player
        pygame.draw.rect(self.screen, (40, 10, 10), (20, 20, 240, 22))
        pygame.draw.rect(self.screen, C_DANGER, (20, 20, int(240 * (p.hp/p.max_hp)), 22))
        pygame.draw.rect(self.screen, C_TEXT, (20, 20, 240, 22), 2)
        self.screen.blit(self.font_s.render(f"{int(p.hp)} / {p.max_hp}", True, C_TEXT), (30, 22))

        pygame.draw.rect(self.screen, (10, 30, 25), (20, 50, 240, 12))
        pygame.draw.rect(self.screen, C_GEM, (20, 50, int(240 * (p.xp/p.xp_to_next)), 12))

        t = self.font_m.render(f"Lvl {p.level}", True, C_ACCENT)
        self.screen.blit(t, (SCREEN_W - t.get_width() - 20, 15))
        t = self.font_s.render(f"Kills: {self.kill_count}", True, C_TEXT)
        self.screen.blit(t, (SCREEN_W - t.get_width() - 20, 45))
        t = self.font_s.render(f"Time: {int(self.game_time)}s", True, C_TEXT_DIM)
        self.screen.blit(t, (SCREEN_W - t.get_width() - 20, 65))
        
        if self.audio.muted:
            mt = self.font_s.render("[MUTED]", True, C_TEXT_DIM)
            self.screen.blit(mt, (20, SCREEN_H - 30))

        # Boss incoming warning
        if self.boss_warning_t > 0:
            pulse = abs(math.sin(self.menu_t * 8))
            col = (255, int(50 + 100 * pulse), int(50 * pulse))
            warn = self.font_m.render("⚠  BOSS INCOMING  ⚠", True, col)
            warn.set_alpha(int(180 + 75 * pulse))
            self.screen.blit(warn, warn.get_rect(center=(SCREEN_W // 2, SCREEN_H - 50)))

    def draw_menu(self):
        ov = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 140)); self.screen.blit(ov, (0, 0))
        title = self.font_l.render("EMBER", True, C_ACCENT)
        tr = title.get_rect(center=(SCREEN_W//2, SCREEN_H//2 - 80))
        for i in range(8, 0, -1):
            g = self.font_l.render("EMBER", True, C_ACCENT); g.set_alpha(20)
            for dx, dy in [(i,0), (-i,0), (0,i), (0,-i)]: self.screen.blit(g, (tr.x+dx, tr.y+dy))
        self.screen.blit(title, tr)
        a = int(140 + 115 * math.sin(self.menu_t * 3))
        sub = self.font_m.render("PRESS ENTER TO IGNITE", True, C_TEXT); sub.set_alpha(a)
        self.screen.blit(sub, sub.get_rect(center=(SCREEN_W//2, SCREEN_H//2)))
        lines = ["WASD / ARROWS  —  Move", "SPACE  —  Dash", "M  —  Mute Audio"]
        for i, ln in enumerate(lines):
            t = self.font_s.render(ln, True, C_TEXT_DIM)
            self.screen.blit(t, t.get_rect(center=(SCREEN_W//2, SCREEN_H//2 + 50 + i*26)))

    def draw_level_up(self):
        ov = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 180)); self.screen.blit(ov, (0, 0))
        t = self.font_l.render("LEVEL UP", True, C_ACCENT)
        self.screen.blit(t, t.get_rect(center=(SCREEN_W//2, 150)))
        self.upgrade_rects = []
        card_w, card_h = 220, 300; gap = 30
        start_x = (SCREEN_W - (card_w * 3 + gap * 2)) // 2
        for i, up in enumerate(self.upgrade_choices):
            x = start_x + i * (card_w + gap); y = SCREEN_H//2 - card_h//2 + 20
            rect = pygame.Rect(x, y, card_w, card_h); self.upgrade_rects.append(rect)
            s = pygame.Surface((card_w, card_h), pygame.SRCALPHA); s.fill((20, 15, 35, 220))
            self.screen.blit(s, rect); pygame.draw.rect(self.screen, up["color"], rect, 3, border_radius=8)
            num = self.font_l.render(str(i+1), True, up["color"]); self.screen.blit(num, (x + 15, y + 10))
            nm = self.font_m.render(up["name"], True, up["color"]); self.screen.blit(nm, nm.get_rect(center=(x + card_w//2, y + 100)))
            words = up["desc"].split(); lines = []; curr = ""
            for w in words:
                test = curr + " " + w if curr else w
                if self.font_s.size(test)[0] < card_w - 20: curr = test
                else: lines.append(curr); curr = w
            if curr: lines.append(curr)
            for j, line in enumerate(lines):
                dt = self.font_s.render(line, True, C_TEXT)
                self.screen.blit(dt, dt.get_rect(center=(x + card_w//2, y + 160 + j*25)))

    def draw_paused(self):
        ov = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 150)); self.screen.blit(ov, (0, 0))
        t = self.font_l.render("PAUSED", True, C_TEXT)
        self.screen.blit(t, t.get_rect(center=(SCREEN_W//2, SCREEN_H//2 - 20)))

    def draw_game_over(self):
        ov = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        ov.fill((20, 0, 0, 180)); self.screen.blit(ov, (0, 0))
        t = self.font_l.render("EXTINGUISHED", True, C_DANGER)
        self.screen.blit(t, t.get_rect(center=(SCREEN_W//2, SCREEN_H//2 - 60)))
        s = self.font_m.render(f"Survived {int(self.game_time)}s", True, C_TEXT)
        self.screen.blit(s, s.get_rect(center=(SCREEN_W//2, SCREEN_H//2)))
        s = self.font_m.render(f"{self.kill_count} Kills", True, C_TEXT)
        self.screen.blit(s, s.get_rect(center=(SCREEN_W//2, SCREEN_H//2 + 35)))

    def run(self):
        running = True
        while running:
            dt = min(self.clock.tick(FPS) / 1000.0, 1/30)
            running = self.handle_events()
            self.update(dt)
            self.draw()
        pygame.quit()
        sys.exit()

if __name__ == "__main__":
    Game().run()