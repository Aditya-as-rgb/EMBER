import pygame
import random
import math
from dataclasses import dataclass
from typing import List, Tuple
from constants import SCREEN_W, SCREEN_H

@dataclass(slots=True)
class Particle:
    x: float; y: float; vx: float; vy: float
    life: float; max_life: float
    color: Tuple[int, int, int]; size: float
    def update(self, dt):
        self.x += self.vx * dt * 60; self.y += self.vy * dt * 60
        self.vx *= 0.94; self.vy *= 0.94; self.life -= dt
    @property
    def alive(self): return self.life > 0

@dataclass(slots=True)
class TextPopup:
    x: float; y: float; text: str
    life: float; max_life: float
    color: Tuple[int, int, int]
    def update(self, dt):
        self.y -= 40 * dt; self.life -= dt
    @property
    def alive(self): return self.life > 0

class FX:
    def __init__(self):
        self.particles: List[Particle] = []
        self.popups: List[TextPopup] = []
        self.particle_surf = pygame.Surface((40, 40), pygame.SRCALPHA)
        
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
        self.particle_surf.fill((0, 0, 0, 0))
        for p in self.particles:
            a = max(0, p.life / p.max_life); r = max(1, int(p.size * a))
            col = (*p.color, int(255 * a))
            pygame.draw.circle(self.particle_surf, col, (20, 20), r)
            surf.blit(self.particle_surf, (p.x - 20 - cam_x, p.y - 20 - cam_y), special_flags=pygame.BLEND_ADD)
            
        for p in self.popups:
            a = max(0, p.life / p.max_life)
            ts = font.render(p.text, True, p.color); ts.set_alpha(int(255 * a))
            surf.blit(ts, (p.x - ts.get_width()//2 - cam_x, p.y - cam_y))
            
    def clear(self):
        self.particles.clear(); self.popups.clear()

class Shake:
    def __init__(self):
        self.intensity = 0; self.timer = 0; self.max_timer = 0; self.offset = (0, 0)
    def trigger(self, i, d=0.3):
        current_intensity = self.intensity * (self.timer / self.max_timer if self.max_timer > 0 else 0)
        if i > current_intensity:
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
    def update(self, dt, target_x, target_y, map_w, map_h):
        tx = target_x - SCREEN_W / 2
        ty = target_y - SCREEN_H / 2
        # Clamp camera to map boundaries
        tx = max(0, min(map_w - SCREEN_W, tx))
        ty = max(0, min(map_h - SCREEN_H, ty))
        self.x += (tx - self.x) * min(1, dt * 8)
        self.y += (ty - self.y) * min(1, dt * 8)