#!/usr/bin/env python3
"""
EMBER — A survival auto-battler for Linux.
Dependencies: pygame
"""

import pygame
import math
import random
import sys
from dataclasses import dataclass
from enum import Enum, auto
from typing import List, Tuple

# ============================================================
# CONFIG & CONSTANTS
# ============================================================
SCREEN_W, SCREEN_H = 1024, 768
FPS = 60

# Colors (Dark Fantasy / Neon)
C_BG          = (12, 8, 20)
C_GRID        = (22, 15, 35)
C_PLAYER      = (255, 180, 80)
C_PLAYER_GLOW = (255, 120, 30)
C_ORB         = (255, 220, 100)
C_ENEMY       = (180, 50, 200)
C_ENEMY_FAST  = (50, 200, 255)
C_ENEMY_TANK  = (255, 80, 80)
C_GEM         = (100, 255, 200)
C_TEXT        = (220, 210, 255)
C_TEXT_DIM    = (110, 100, 140)
C_ACCENT      = (255, 200, 80)
C_DANGER      = (255, 50, 80)

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
# PARTICLES & FLOATING TEXT
# ============================================================
@dataclass
class Particle:
    x: float; y: float; vx: float; vy: float
    life: float; max_life: float
    color: Tuple[int, int, int]; size: float

    def update(self, dt):
        self.x += self.vx * dt * 60
        self.y += self.vy * dt * 60
        self.vx *= 0.94; self.vy *= 0.94
        self.life -= dt

    @property
    def alive(self): return self.life > 0

    def draw(self, surf):
        a = max(0, self.life / self.max_life)
        r = max(1, int(self.size * a))
        col = (*self.color, int(255 * a))
        s = pygame.Surface((r * 4, r * 4), pygame.SRCALPHA)
        pygame.draw.circle(s, col, (r * 2, r * 2), r * 2)
        surf.blit(s, (self.x - r * 2, self.y - r * 2), special_flags=pygame.BLEND_ADD)

@dataclass
class TextPopup:
    x: float; y: float; text: str
    life: float; max_life: float
    color: Tuple[int, int, int]

    def update(self, dt):
        self.y -= 40 * dt
        self.life -= dt

    @property
    def alive(self): return self.life > 0

    def draw(self, surf, font):
        a = max(0, self.life / self.max_life)
        ts = font.render(self.text, True, self.color)
        ts.set_alpha(int(255 * a))
        surf.blit(ts, (self.x - ts.get_width()//2, self.y))


class FX:
    def __init__(self):
        self.particles: List[Particle] = []
        self.popups: List[TextPopup] = []

    def burst(self, x, y, n, color, spd=(1, 5), life=(0.3, 0.7), size=(2, 5)):
        for _ in range(n):
            a = random.uniform(0, math.tau)
            s = random.uniform(*spd)
            l = random.uniform(*life)
            self.particles.append(Particle(x, y, math.cos(a)*s, math.sin(a)*s, l, l, color, random.uniform(*size)))

    def popup(self, x, y, text, color):
        self.popups.append(TextPopup(x, y, text, 0.8, 0.8, color))

    def update(self, dt):
        for p in self.particles: p.update(dt)
        for p in self.popups: p.update(dt)
        self.particles = [p for p in self.particles if p.alive]
        self.popups = [p for p in self.popups if p.alive]

    def draw(self, surf, font):
        for p in self.particles: p.draw(surf)
        for p in self.popups: p.draw(surf, font)

    def clear(self):
        self.particles.clear()
        self.popups.clear()


# ============================================================
# SCREEN SHAKE
# ============================================================
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


# ============================================================
# ENTITIES
# ============================================================
class Player:
    def __init__(self, x, y):
        self.x, self.y = x, y
        self.radius = 14
        self.hp = 100; self.max_hp = 100
        self.xp = 0; self.xp_to_next = 5; self.level = 1
        
        # Upgradable stats
        self.speed = PLAYER_SPEED
        self.orbit_count = 3
        self.orbit_radius = 70
        self.orbit_speed = 2.5  # radians/sec
        self.orbit_damage = 25
        self.orbit_size = 8
        self.pickup_radius = 80
        
        # Internal state
        self.orbit_angle = 0
        self.dash_cd = 0
        self.dash_t = 0
        self.dash_dir = (0, 0)
        self.iframes = 0

    def update(self, dt, keys, fx):
        dx, dy = 0, 0
        if keys[pygame.K_w] or keys[pygame.K_UP]: dy -= 1
        if keys[pygame.K_s] or keys[pygame.K_DOWN]: dy += 1
        if keys[pygame.K_a] or keys[pygame.K_LEFT]: dx -= 1
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]: dx += 1
        
        if dx != 0 or dy != 0:
            mag = math.hypot(dx, dy)
            dx, dy = dx/mag, dy/mag
            
        if self.dash_t > 0:
            self.dash_t -= dt
            self.x += self.dash_dir[0] * DASH_SPEED * dt * 60
            self.y += self.dash_dir[1] * DASH_SPEED * dt * 60
            fx.burst(self.x, self.y, 2, (255, 200, 100), spd=(0, 1), life=(0.1, 0.2), size=(2, 4))
        else:
            self.x += dx * self.speed * dt * 60
            self.y += dy * self.speed * dt * 60

        # Keep in bounds
        self.x = max(self.radius, min(SCREEN_W - self.radius, self.x))
        self.y = max(self.radius, min(SCREEN_H - self.radius, self.y))

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
                mag = math.hypot(dx, dy)
                self.dash_dir = (dx/mag, dy/mag)
                self.dash_t = DASH_DURATION
                self.dash_cd = DASH_CD
                self.iframes = DASH_DURATION + 0.1
                fx.burst(self.x, self.y, 15, (255, 220, 100), spd=(2, 6), life=(0.2, 0.4))

    def take_damage(self, dmg, fx, shake):
        if self.iframes > 0: return
        self.hp -= dmg
        self.iframes = 0.8
        fx.burst(self.x, self.y, 12, C_DANGER, spd=(2, 5))
        shake.trigger(8, 0.2)

    def add_xp(self, amount, fx):
        self.xp += amount
        if self.xp >= self.xp_to_next:
            return True
        return False

    def get_orb_positions(self):
        positions = []
        for i in range(self.orbit_count):
            angle = self.orbit_angle + (i / self.orbit_count) * math.tau
            ox = self.x + math.cos(angle) * self.orbit_radius
            oy = self.y + math.sin(angle) * self.orbit_radius
            positions.append((ox, oy))
        return positions

    def draw(self, surf):
        # Pickup radius (faint)
        s = pygame.Surface((self.pickup_radius*2, self.pickup_radius*2), pygame.SRCALPHA)
        pygame.draw.circle(s, (100, 255, 200, 15), (self.pickup_radius, self.pickup_radius), self.pickup_radius)
        surf.blit(s, (self.x - self.pickup_radius, self.y - self.pickup_radius))

        # Dash CD indicator
        if self.dash_cd > 0:
            p = 1 - (self.dash_cd / DASH_CD)
            pygame.draw.arc(surf, (50, 50, 80), 
                           (self.x-20, self.y-20, 40, 40), 
                           -math.pi/2, -math.pi/2 + p * math.tau, 2)

        # Glow
        g = pygame.Surface((self.radius*4, self.radius*4), pygame.SRCALPHA)
        pygame.draw.circle(g, (*C_PLAYER_GLOW, 40), (self.radius*2, self.radius*2), self.radius+6)
        pygame.draw.circle(g, (*C_PLAYER_GLOW, 80), (self.radius*2, self.radius*2), self.radius+2)
        surf.blit(g, (self.x - self.radius*2, self.y - self.radius*2), special_flags=pygame.BLEND_ADD)

        # Core
        if self.iframes > 0 and int(self.iframes * 20) % 2 == 0:
            pass # Flicker
        else:
            pygame.draw.circle(surf, C_PLAYER, (int(self.x), int(self.y)), self.radius)

class Enemy:
    def __init__(self, x, y, kind='grunt'):
        self.x, self.y = x, y
        self.kind = kind
        self.spawn_t = 0.4
        
        cfg = {
            'grunt': (C_ENEMY,      1.4, 30, 10, 12, 1),
            'fast':  (C_ENEMY_FAST, 2.8, 15, 5,  8,  2),
            'tank':  (C_ENEMY_TANK, 0.8, 150,25, 22, 5),
        }
        c = cfg.get(kind, cfg['grunt'])
        self.color, self.speed, self.hp, self.dmg, self.radius, self.xp_val = c
        self.max_hp = self.hp

    def update(self, dt, player):
        if self.spawn_t > 0:
            self.spawn_t -= dt
            return
        
        dx, dy = player.x - self.x, player.y - self.y
        d = math.hypot(dx, dy)
        if d > 0:
            self.x += (dx/d) * self.speed * dt * 60
            self.y += (dy/d) * self.speed * dt * 60

    def draw(self, surf):
        if self.spawn_t > 0:
            prog = 1 - self.spawn_t / 0.4
            r = int(30 * (1 - prog) + self.radius * prog)
            s = pygame.Surface((r*4, r*4), pygame.SRCALPHA)
            pygame.draw.circle(s, (*self.color, int(255*prog)), (r*2, r*2), r, 2)
            surf.blit(s, (self.x-r*2, self.y-r*2), special_flags=pygame.BLEND_ADD)
            return

        # Glow
        g = pygame.Surface((self.radius*4, self.radius*4), pygame.SRCALPHA)
        pygame.draw.circle(g, (*self.color, 30), (self.radius*2, self.radius*2), self.radius+6)
        pygame.draw.circle(g, (*self.color, 60), (self.radius*2, self.radius*2), self.radius+2)
        surf.blit(g, (self.x-self.radius*2, self.y-self.radius*2), special_flags=pygame.BLEND_ADD)

        pygame.draw.circle(surf, self.color, (int(self.x), int(self.y)), self.radius)
        
        # HP Bar
        if self.hp < self.max_hp:
            bw = self.radius * 2
            pygame.draw.rect(surf, (40, 10, 40), (self.x-bw/2, self.y-self.radius-8, bw, 3))
            pygame.draw.rect(surf, C_DANGER, (self.x-bw/2, self.y-self.radius-8, bw*(self.hp/self.max_hp), 3))

class Gem:
    def __init__(self, x, y):
        self.x, self.y = x, y
        self.vx = random.uniform(-2, 2)
        self.vy = random.uniform(-2, 2)
        self.radius = 5
        self.attracted = False

    def update(self, dt, player):
        # Initial scatter
        self.x += self.vx * dt * 60; self.y += self.vy * dt * 60
        self.vx *= 0.9; self.vy *= 0.9

        dx, dy = player.x - self.x, player.y - self.y
        d = math.hypot(dx, dy)

        if self.attracted or d < player.pickup_radius:
            self.attracted = True
            pull = 8.0
            self.x += (dx/d) * pull * dt * 60
            self.y += (dy/d) * pull * dt * 60

    def draw(self, surf):
        s = pygame.Surface((self.radius*4, self.radius*4), pygame.SRCALPHA)
        pygame.draw.circle(s, (*C_GEM, 60), (self.radius*2, self.radius*2), self.radius+3)
        pygame.draw.circle(s, (*C_GEM, 150), (self.radius*2, self.radius*2), self.radius+1)
        surf.blit(s, (self.x-self.radius*2, self.y-self.radius*2), special_flags=pygame.BLEND_ADD)
        pygame.draw.circle(surf, (200, 255, 220), (int(self.x), int(self.y)), 3)


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
        pygame.display.set_caption("EMBER")
        self.clock = pygame.time.Clock()
        
        self.font_l = pygame.font.SysFont("monospace", 54, bold=True)
        self.font_m = pygame.font.SysFont("monospace", 24, bold=True)
        self.font_s = pygame.font.SysFont("monospace", 18)
        self.font_xs = pygame.font.SysFont("monospace", 14)
        
        self.state = State.MENU
        self.fx = FX()
        self.shake = Shake()
        self.menu_t = 0
        self.high_score = 0
        self.reset()

    def reset(self):
        self.player = Player(SCREEN_W//2, SCREEN_H//2)
        self.enemies: List[Enemy] = []
        self.gems: List[Gem] = []
        self.fx.clear()
        self.shake = Shake()
        self.game_time = 0
        self.spawn_timer = 0
        self.kill_count = 0
        self.upgrade_choices = []

    def spawn_enemy(self):
        edge = random.randint(0, 3)
        if edge == 0:   x, y = random.randint(0, SCREEN_W), -30
        elif edge == 1: x, y = SCREEN_W + 30, random.randint(0, SCREEN_H)
        elif edge == 2: x, y = random.randint(0, SCREEN_W), SCREEN_H + 30
        else:           x, y = -30, random.randint(0, SCREEN_H)

        # Difficulty scaling
        t = self.game_time
        kinds = ['grunt']
        if t > 20: kinds.append('grunt')
        if t > 45: kinds.append('fast')
        if t > 75: kinds.append('fast', 'grunt')
        if t > 100: kinds.append('tank')
        if t > 140: kinds.append('tank', 'fast')
        
        self.enemies.append(Enemy(x, y, random.choice(kinds)))

    def handle_events(self) -> bool:
        for e in pygame.event.get():
            if e.type == pygame.QUIT: return False
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    if self.state == State.PLAYING: self.state = State.PAUSED
                    elif self.state == State.PAUSED: self.state = State.PLAYING
                    elif self.state == State.MENU: return False
                    elif self.state == State.GAME_OVER: self.state = State.MENU
                if e.key in (pygame.K_RETURN, pygame.K_SPACE):
                    if self.state == State.MENU:
                        self.reset(); self.state = State.PLAYING
                    elif self.state == State.GAME_OVER:
                        self.reset(); self.state = State.PLAYING
                    elif self.state == State.PLAYING:
                        self.player.try_dash(pygame.key.get_pressed(), self.fx)
                if e.key == pygame.K_1 and self.state == State.LEVEL_UP: self.pick_upgrade(0)
                if e.key == pygame.K_2 and self.state == State.LEVEL_UP: self.pick_upgrade(1)
                if e.key == pygame.K_3 and self.state == State.LEVEL_UP: self.pick_upgrade(2)

            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                if self.state == State.LEVEL_UP:
                    mx, my = e.pos
                    for i, rect in enumerate(self.upgrade_rects):
                        if rect.collidepoint(mx, my):
                            self.pick_upgrade(i)
                            break

        keys = pygame.key.get_pressed()
        if keys[pygame.K_SPACE] and self.state == State.PLAYING:
            self.player.try_dash(keys, self.fx) # Hold to dash when off CD
        return True

    def pick_upgrade(self, idx):
        if idx < len(self.upgrade_choices):
            upgrade = self.upgrade_choices[idx]
            upgrade["apply"](self.player)
            self.fx.popup(self.player.x, self.player.y - 30, upgrade["name"], upgrade["color"])
            self.state = State.PLAYING

    def update(self, dt):
        self.menu_t += dt
        if self.state in (State.PAUSED, State.LEVEL_UP, State.GAME_OVER):
            return

        # PLAYING
        self.game_time += dt
        keys = pygame.key.get_pressed()
        self.player.update(dt, keys, self.fx)

        # Spawning
        self.spawn_timer -= dt
        if self.spawn_timer <= 0:
            self.spawn_enemy()
            self.spawn_timer = max(0.2, 1.2 - self.game_time * 0.01)

        # Update Entities
        for en in self.enemies: en.update(dt, self.player)
        for g in self.gems: g.update(dt, self.player)

        # Orbital Collisions
        orb_positions = self.player.get_orb_positions()
        for ox, oy in orb_positions:
            for en in self.enemies[:]:
                if math.hypot(ox - en.x, oy - en.y) < en.radius + self.player.orbit_size:
                    en.hp -= self.player.orbit_damage
                    self.fx.burst(ox, oy, 4, C_ORB, spd=(1, 3), life=(0.1, 0.2), size=(1, 3))
                    if en.hp <= 0:
                        self.enemies.remove(en)
                        self.kill_count += 1
                        self.fx.burst(en.x, en.y, 15, en.color, spd=(2, 6), life=(0.3, 0.6))
                        self.shake.trigger(4, 0.15)
                        for _ in range(en.xp_val):
                            self.gems.append(Gem(en.x, en.y))

        # Player Collisions
        for en in self.enemies:
            if en.spawn_t > 0: continue
            if math.hypot(self.player.x - en.x, self.player.y - en.y) < en.radius + self.player.radius:
                self.player.take_damage(en.dmg, self.fx, self.shake)
                # Knockback enemy
                dx, dy = en.x - self.player.x, en.y - self.player.y
                d = math.hypot(dx, dy)
                if d > 0:
                    en.x += (dx/d) * 15; en.y += (dy/d) * 15

        for g in self.gems[:]:
            if math.hypot(self.player.x - g.x, self.player.y - g.y) < self.player.radius + g.radius:
                leveled_up = self.player.add_xp(1, self.fx)
                self.gems.remove(g)
                if leveled_up:
                    self.player.xp -= self.player.xp_to_next
                    self.player.level += 1
                    self.player.xp_to_next = int(self.player.xp_to_next * 1.35)
                    self.state = State.LEVEL_UP
                    self.upgrade_choices = random.sample(UPGRADES, 3)
                    self.upgrade_rects = []
                    break # Break loop since state changed

        if self.player.hp <= 0:
            self.state = State.GAME_OVER
            self.high_score = max(self.high_score, self.kill_count)
            self.fx.burst(self.player.x, self.player.y, 40, C_PLAYER, spd=(3, 10), life=(0.5, 1.0))
            self.shake.trigger(15, 0.5)

        self.fx.update(dt)
        self.shake.update(dt)

    def draw(self):
        world = pygame.Surface((SCREEN_W, SCREEN_H))
        world.fill(C_BG)
        
        # Grid
        sp = 48
        for x in range(0, SCREEN_W, sp): pygame.draw.line(world, C_GRID, (x, 0), (x, SCREEN_H))
        for y in range(0, SCREEN_H, sp): pygame.draw.line(world, C_GRID, (0, y), (SCREEN_W, y))

        if self.state in (State.PLAYING, State.PAUSED, State.LEVEL_UP, State.GAME_OVER):
            for g in self.gems: g.draw(world)
            for en in self.enemies: en.draw(world)
            
            # Draw Orbs
            for ox, oy in self.player.get_orb_positions():
                g = pygame.Surface((self.player.orbit_size*4, self.player.orbit_size*4), pygame.SRCALPHA)
                pygame.draw.circle(g, (*C_ORB, 40), (self.player.orbit_size*2, self.player.orbit_size*2), self.player.orbit_size+6)
                pygame.draw.circle(g, (*C_ORB, 80), (self.player.orbit_size*2, self.player.orbit_size*2), self.player.orbit_size+2)
                world.blit(g, (ox-self.player.orbit_size*2, oy-self.player.orbit_size*2), special_flags=pygame.BLEND_ADD)
                pygame.draw.circle(world, C_ORB, (int(ox), int(oy)), self.player.orbit_size)

            if self.player.hp > 0: self.player.draw(world)
            self.fx.draw(world, self.font_xs)

        ox, oy = self.shake.offset
        self.screen.fill(C_BG)
        self.screen.blit(world, (ox, oy))

        # UI
        if self.state == State.MENU: self.draw_menu()
        elif self.state == State.PLAYING: self.draw_hud()
        elif self.state == State.LEVEL_UP: self.draw_hud(); self.draw_level_up()
        elif self.state == State.PAUSED: self.draw_hud(); self.draw_paused()
        elif self.state == State.GAME_OVER: self.draw_hud(); self.draw_game_over()

        pygame.display.flip()

    def draw_hud(self):
        p = self.player
        # HP Bar
        pygame.draw.rect(self.screen, (40, 10, 10), (20, 20, 240, 22))
        pygame.draw.rect(self.screen, C_DANGER, (20, 20, int(240 * (p.hp/p.max_hp)), 22))
        pygame.draw.rect(self.screen, C_TEXT, (20, 20, 240, 22), 2)
        t = self.font_s.render(f"{int(p.hp)} / {p.max_hp}", True, C_TEXT)
        self.screen.blit(t, (30, 22))

        # XP Bar
        pygame.draw.rect(self.screen, (10, 30, 25), (20, 50, 240, 12))
        pygame.draw.rect(self.screen, C_GEM, (20, 50, int(240 * (p.xp/p.xp_to_next)), 12))

        # Stats
        t = self.font_m.render(f"Lvl {p.level}", True, C_ACCENT)
        self.screen.blit(t, (SCREEN_W - t.get_width() - 20, 15))
        t = self.font_s.render(f"Kills: {self.kill_count}", True, C_TEXT)
        self.screen.blit(t, (SCREEN_W - t.get_width() - 20, 45))
        t = self.font_s.render(f"Time: {int(self.game_time)}s", True, C_TEXT_DIM)
        self.screen.blit(t, (SCREEN_W - t.get_width() - 20, 65))

    def draw_menu(self):
        ov = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 140)); self.screen.blit(ov, (0, 0))

        title = self.font_l.render("EMBER", True, C_ACCENT)
        tr = title.get_rect(center=(SCREEN_W//2, SCREEN_H//2 - 80))
        # Glow
        for i in range(8, 0, -1):
            g = self.font_l.render("EMBER", True, C_ACCENT)
            g.set_alpha(20)
            for dx, dy in [(i,0), (-i,0), (0,i), (0,-i)]: self.screen.blit(g, (tr.x+dx, tr.y+dy))
        self.screen.blit(title, tr)

        a = int(140 + 115 * math.sin(self.menu_t * 3))
        sub = self.font_m.render("PRESS ENTER TO IGNITE", True, C_TEXT)
        sub.set_alpha(a)
        self.screen.blit(sub, sub.get_rect(center=(SCREEN_W//2, SCREEN_H//2)))

        lines = [
            "WASD / ARROWS  —  Move",
            "SPACE  —  Dash (Invincibility frames)",
            "Survive, collect souls, and upgrade your flame.",
        ]
        for i, ln in enumerate(lines):
            t = self.font_s.render(ln, True, C_TEXT_DIM)
            self.screen.blit(t, t.get_rect(center=(SCREEN_W//2, SCREEN_H//2 + 50 + i*26)))

    def draw_level_up(self):
        ov = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 180)); self.screen.blit(ov, (0, 0))
        
        t = self.font_l.render("LEVEL UP", True, C_ACCENT)
        self.screen.blit(t, t.get_rect(center=(SCREEN_W//2, 150)))

        self.upgrade_rects = []
        card_w, card_h = 220, 300
        gap = 30
        total_w = card_w * 3 + gap * 2
        start_x = (SCREEN_W - total_w) // 2

        for i, up in enumerate(self.upgrade_choices):
            x = start_x + i * (card_w + gap)
            y = SCREEN_H//2 - card_h//2 + 20
            rect = pygame.Rect(x, y, card_w, card_h)
            self.upgrade_rects.append(rect)

            # Card BG
            s = pygame.Surface((card_w, card_h), pygame.SRCALPHA)
            s.fill((20, 15, 35, 220))
            self.screen.blit(s, rect)
            pygame.draw.rect(self.screen, up["color"], rect, 3, border_radius=8)

            # Number
            num = self.font_l.render(str(i+1), True, up["color"])
            self.screen.blit(num, (x + 15, y + 10))

            # Name
            nm = self.font_m.render(up["name"], True, up["color"])
            self.screen.blit(nm, nm.get_rect(center=(x + card_w//2, y + 100)))

            # Desc
            words = up["desc"].split()
            lines = []
            curr = ""
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
        h = self.font_s.render("ESC to resume", True, C_TEXT_DIM)
        self.screen.blit(h, h.get_rect(center=(SCREEN_W//2, SCREEN_H//2 + 30)))

    def draw_game_over(self):
        ov = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        ov.fill((20, 0, 0, 180)); self.screen.blit(ov, (0, 0))
        t = self.font_l.render("EXTINGUISHED", True, C_DANGER)
        self.screen.blit(t, t.get_rect(center=(SCREEN_W//2, SCREEN_H//2 - 60)))
        s = self.font_m.render(f"Survived {int(self.game_time)}s", True, C_TEXT)
        self.screen.blit(s, s.get_rect(center=(SCREEN_W//2, SCREEN_H//2)))
        s = self.font_m.render(f"{self.kill_count} Kills", True, C_TEXT)
        self.screen.blit(s, s.get_rect(center=(SCREEN_W//2, SCREEN_H//2 + 35)))
        h = self.font_s.render("ENTER to reignite  |  ESC for menu", True, C_TEXT_DIM)
        self.screen.blit(h, h.get_rect(center=(SCREEN_W//2, SCREEN_H - 60)))

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
