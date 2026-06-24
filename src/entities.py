import pygame
import math
import random
from typing import List, Tuple
from constants import (PLAYER_SPEED, DASH_SPEED, DASH_DURATION, DASH_CD, 
                       IFRAME_DURATION, PROJECTILE_LIFE, PICKUP_PULL, DASH_DAMAGE, 
                       MAP_W, MAP_H, BOSS_HP_BASE)

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
        
        # Evolution & Scaling Stats
        self.tier = 1
        self.lifesteal = 0
        self.thorns = 0
        self.crit_chance = 0.0
        
        self._update_pickup_surf()

    def _update_pickup_surf(self):
        self._pickup_surf = pygame.Surface((self.pickup_radius*2, self.pickup_radius*2), pygame.SRCALPHA)
        pygame.draw.circle(self._pickup_surf, (100, 255, 200, 15), (self.pickup_radius, self.pickup_radius), self.pickup_radius)

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

        # Map Boundary Clamping
        self.x = max(self.radius, min(MAP_W - self.radius, self.x))
        self.y = max(self.radius, min(MAP_H - self.radius, self.y))

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

    def take_damage(self, dmg, fx, shake, attacker=None):
        if self.iframes > 0: return
        self.hp -= dmg; self.iframes = IFRAME_DURATION
        fx.burst(self.x, self.y, 12, (255, 50, 80), spd=(2, 5)); shake.trigger(8, 0.2)
        
        # Thorns damage
        if attacker and self.thorns > 0 and attacker.hp > 0:
            attacker.take_damage(self.thorns)
            fx.popup(attacker.x, attacker.y - 20, f"{self.thorns}", (255, 100, 100))

    def add_xp(self, amount, fx):
        self.xp += amount
        return self.xp >= self.xp_to_next

    def get_orb_positions(self):
        return [(self.x + math.cos(self.orbit_angle + (i / self.orbit_count) * math.tau) * self.orbit_radius,
                 self.y + math.sin(self.orbit_angle + (i / self.orbit_count) * math.tau) * self.orbit_radius)
                for i in range(self.orbit_count)]

    def draw(self, surf, cam_x, cam_y):
        surf.blit(self._pickup_surf, (self.x - self.pickup_radius - cam_x, self.y - self.pickup_radius - cam_y))

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
        self.base_radius = {'grunt': 12, 'fast': 8, 'tank': 22,
                            'charger': 13, 'teleporter': 10, 'shooter': 11, 
                            'bomber': 14, 'splitter': 16, 'boss': 40}.get(kind, 12)
        self.radius = self.base_radius
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
            'bomber':     (1.8,  40,  40, 3), # High dmg, low hp
            'splitter':   (1.0,  80,  15, 4), # Med hp, splits
            'boss':       (0.7,  BOSS_HP_BASE,  30, 20),
        }
        c = cfg.get(kind, cfg['grunt'])
        self.speed, self.hp, self.dmg, self.xp_val = c
        self.hp = int(self.hp * hp_mult)
        self.max_hp = self.hp

        self.charge_cd = random.uniform(2, 4)
        self.charge_t = 0.0
        self.charge_vx = 0.0; self.charge_vy = 0.0
        self.charge_speed = 7.0

        self.teleport_cd = random.uniform(3, 5)
        self.shoot_cd = random.uniform(1.5, 2.5)
        self.pending_projectiles: List[Tuple] = []  
        self.pending_spawns: List[Tuple] = []

        self.boss_phase = 0
        self.boss_action_cd = 1.5
        self.boss_spin = 0.0
        
        # Bomber state
        self.detonating = False
        self.detonate_t = 0.0

    @property
    def is_spawning(self):
        return self.spawn_t > 0

    @property
    def is_dead(self):
        return self.hp <= 0 and not self.detonating

    def update(self, dt, player):
        # If detonating, stand still and tick down
        if self.detonating:
            self.detonate_t -= dt
            self.pulse_t += dt * 30  # Flash extremely fast
            if self.detonate_t <= 0:
                self.hp = 0
                self.detonating = False
            return

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
                self.radius = int(self.base_radius * 1.2)
            else:
                self.radius = self.base_radius
                self.x += (dx/d) * self.speed * dt * 60
                self.y += (dy/d) * self.speed * dt * 60
                if self.charge_cd <= 0:
                    self.charge_vx, self.charge_vy = (dx/d) * self.charge_speed, (dy/d) * self.charge_speed
                    self.charge_t = 0.35
                    self.charge_cd = random.uniform(2.5, 4.0)

        elif self.kind == 'teleporter':
            self.teleport_cd -= dt
            self.x += (dx/d) * self.speed * dt * 60
            self.y += (dy/d) * self.speed * dt * 60
            if self.teleport_cd <= 0:
                angle = random.uniform(0, math.tau)
                dist = random.uniform(120, 220)
                self.x = player.x + math.cos(angle) * dist
                self.y = player.y + math.sin(angle) * dist
                self.teleport_cd = random.uniform(2.5, 4.5)

        elif self.kind == 'shooter':
            target_dist = 220
            if d > target_dist + 20:
                self.x += (dx/d) * self.speed * dt * 60
                self.y += (dy/d) * self.speed * dt * 60
            elif d < target_dist - 20:
                self.x -= (dx/d) * self.speed * dt * 60
                self.y -= (dy/d) * self.speed * dt * 60
            else:
                self.x += (-dy/d) * self.speed * 0.8 * dt * 60
                self.y += (dx/d) * self.speed * 0.8 * dt * 60

            self.shoot_cd -= dt
            if self.shoot_cd <= 0:
                for spread in [-0.2, 0, 0.2]:
                    angle = math.atan2(dy, dx) + spread
                    spd = 3.2
                    self.pending_projectiles.append((self.x, self.y, math.cos(angle) * spd, math.sin(angle) * spd, 15))
                self.shoot_cd = random.uniform(1.8, 2.8)
                
        elif self.kind == 'bomber':
            # Rushes player, triggers detonation on proximity
            self.x += (dx/d) * self.speed * dt * 60
            self.y += (dy/d) * self.speed * dt * 60
            self.pulse_t += dt * 10
            if d < player.radius + self.radius + 20:
                self.detonating = True
                self.detonate_t = 0.4
                self.hp = 1  # Prevent normal death trigger while detonating

        elif self.kind == 'splitter':
            self.x += (dx/d) * self.speed * dt * 60
            self.y += (dy/d) * self.speed * dt * 60

        elif self.kind == 'boss':
            self.boss_spin += dt * 1.5
            self.boss_action_cd -= dt
            self.x += (dx/d) * self.speed * dt * 60
            self.y += (dy/d) * self.speed * dt * 60
            
            if self.hp < self.max_hp * 0.66: self.boss_phase = 1
            if self.hp < self.max_hp * 0.33: self.boss_phase = 2

            if self.boss_action_cd <= 0:
                spd = 3.5 + self.boss_phase * 0.8
                dmg = 15 + self.boss_phase * 5
                if self.boss_phase == 0:
                    for i in range(8):
                        a = i * math.tau / 8
                        self.pending_projectiles.append((self.x, self.y, math.cos(a)*spd, math.sin(a)*spd, dmg))
                elif self.boss_phase == 1:
                    for spread in [-0.35, 0, 0.35]:
                        a = math.atan2(dy, dx) + spread
                        self.pending_projectiles.append((self.x, self.y, math.cos(a)*spd, math.sin(a)*spd, dmg))
                else:
                    for i in range(12):
                        a = self.boss_spin + i * math.tau / 12
                        self.pending_projectiles.append((self.x, self.y, math.cos(a)*spd, math.sin(a)*spd, dmg))
                self.boss_action_cd = max(0.6, 1.5 - self.boss_phase * 0.3)
        else:
            self.x += (dx/d) * self.speed * dt * 60
            self.y += (dy/d) * self.speed * dt * 60

    def take_damage(self, dmg):
        if self.detonating: return  # Invulnerable while detonating
        
        self.hp -= dmg
        if self.kind == 'bomber' and self.hp <= 0:
            self.hp = 1
            self.detonating = True
            self.detonate_t = 0.6  # Longer fuse if killed from afar
        else:
            self.flash_t = 0.08

    def draw(self, surf, cam_x, cam_y, sprite_cache):
        scale = 1.0 + math.sin(self.pulse_t) * 0.08
        if self.kind == 'charger' and self.charge_t > 0:
            scale = 1.2
        if self.kind == 'boss':
            scale = 1.0 + math.sin(self.pulse_t) * 0.04
        if self.kind == 'bomber' and self.detonating:
            scale = 1.0 + abs(math.sin(self.pulse_t)) * 0.4  # Throb violently
        elif self.kind == 'bomber':
            scale = 1.0 + abs(math.sin(self.pulse_t)) * 0.15

        w, h = self.sprite.get_size()
        target_size = max(1, int(w * scale))
        spr = sprite_cache.get_scaled(self.sprite, target_size)
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

        if self.hp < self.max_hp and self.kind != 'boss':
            bw = rect.width
            bx = rect.x
            by = rect.y - 10
            pygame.draw.rect(surf, (40, 10, 40), (bx, by, bw, 3))
            pygame.draw.rect(surf, (255, 50, 80), (bx, by, int(bw*(self.hp/self.max_hp)), 3))


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
        d = math.hypot(dx, dy) or 1
        if self.attracted or d < player.pickup_radius:
            self.attracted = True
            self.x += (dx/d) * PICKUP_PULL * dt * 60
            self.y += (dy/d) * PICKUP_PULL * dt * 60

    def draw(self, surf, cam_x, cam_y):
        rect = self.sprite.get_rect(center=(int(self.x - cam_x), int(self.y - cam_y)))
        surf.blit(self.sprite, rect)

class Projectile:
    def __init__(self, x, y, vx, vy, dmg, sprite):
        self.x, self.y = x, y
        self.vx, self.vy = vx, vy
        self.dmg = dmg
        self.sprite = sprite
        self.radius = 5
        self.life = PROJECTILE_LIFE

    def update(self, dt):
        self.x += self.vx * dt * 60
        self.y += self.vy * dt * 60
        self.life -= dt

    @property
    def alive(self): return self.life > 0

    def draw(self, surf, cam_x, cam_y):
        rect = self.sprite.get_rect(center=(int(self.x - cam_x), int(self.y - cam_y)))
        surf.blit(self.sprite, rect)