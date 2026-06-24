import pygame
import math
import random
import json
import os
from typing import List
from constants import (SCREEN_W, SCREEN_H, FPS, C_BG, C_TEXT, C_TEXT_DIM, 
                       C_ACCENT, C_DANGER, C_GEM, PHASE_COLORS, DASH_DAMAGE,
                       MAP_W, MAP_H, BOSS_LEVEL_INTERVAL)
from state import State
from audio import Audio
from sprites import (SpriteCache, create_player_sprite, create_orb_sprite, create_gem_sprite, 
                     create_enemy_sprite, create_enemy_sprite_charger, create_enemy_sprite_teleporter, 
                     create_enemy_sprite_shooter, create_boss_sprite, create_projectile_sprite, 
                     create_background, load_sprite)
from fx import FX, Shake, Camera
from entities import Player, Enemy, Gem, Projectile
from upgrades import UPGRADES

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
        self.font_boss_hp = pygame.font.SysFont("monospace", 13, bold=True)
        
        self.audio = Audio()
        self.state = State.MENU
        self.fx = FX(); self.shake = Shake(); self.camera = Camera()
        self.menu_t = 0; 
        
        # High Score Loading
        self.high_score = 0
        if os.path.exists("ember_hs.json"):
            try:
                with open("ember_hs.json", "r") as f:
                    self.high_score = json.load(f).get("hs", 0)
            except Exception:
                self.high_score = 0

        bg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ember_bg2.jpg")
        if os.path.exists(bg_path):
            raw = pygame.image.load(bg_path).convert()
            self.bg_texture = pygame.transform.scale(raw, (SCREEN_W, SCREEN_H))
            dark = pygame.Surface((SCREEN_W, SCREEN_H))
            dark.fill((0, 0, 0))
            dark.set_alpha(120)
            self.bg_texture.blit(dark, (0, 0))
        else:
            self.bg_texture = create_background()

        # Sprites
        self.spr_player_tiers = [create_player_sprite(1), create_player_sprite(2), create_player_sprite(3)]
        self.spr_orb = load_sprite("orb.png", create_orb_sprite)
        self.spr_gem = load_sprite("gem.png", create_gem_sprite)
        self.spr_enemies = {
            'grunt':       load_sprite("enemy_grunt.png", lambda: create_enemy_sprite('grunt')),
            'fast':        load_sprite("enemy_fast.png",  lambda: create_enemy_sprite('fast')),
            'tank':        load_sprite("enemy_tank.png",  lambda: create_enemy_sprite('tank')),
            'bomber':      load_sprite("enemy_bomber.png", lambda: create_enemy_sprite('bomber')),
            'splitter':    load_sprite("enemy_splitter.png", lambda: create_enemy_sprite('splitter')),
            'charger':     load_sprite("enemy_charger.png",     create_enemy_sprite_charger),
            'teleporter':  load_sprite("enemy_teleporter.png",  create_enemy_sprite_teleporter),
            'shooter':     load_sprite("enemy_shooter.png",     create_enemy_sprite_shooter),
        }
        self.spr_boss_phases = [create_boss_sprite(i) for i in range(3)]
        self.spr_projectile = load_sprite("projectile.png", create_projectile_sprite)
        
        self.sprite_cache = SpriteCache()
        self.upgrade_rects = []
        self.cached_upgrade_surfaces = []
        self.last_upgrade_choices = []
        
        self.boss_state = 'idle'
        self.boss_warning_t = 0.0
        self.hit_stop = 0.0
        self.damage_flash = 0.0

        self.reset()

    def reset(self):
        self.player = Player(MAP_W//2, MAP_H//2, self.spr_player_tiers[0], self.audio)
        self.enemies: List[Enemy] = []
        self.gems: List[Gem] = []
        self.projectiles: List[Projectile] = []
        self.fx.clear(); self.shake = Shake()
        self.camera = Camera()
        self.game_time = 0; self.spawn_timer = 0; self.kill_count = 0
        self.upgrade_choices = []
        self.next_boss_level = BOSS_LEVEL_INTERVAL
        self.boss_alive = False
        self.boss_state = 'idle'
        self.boss_warning_t = 0.0
        self.hit_stop = 0.0
        self.damage_flash = 0.0

    def spawn_enemy(self, kind_override=None):
        # Spawn around the screen viewport, but inside map bounds
        cx, cy = self.camera.x + SCREEN_W / 2, self.camera.y + SCREEN_H / 2
        edge = random.randint(0, 3)
        offset = 50
        if edge == 0:   x, y = cx + random.randint(-SCREEN_W//2, SCREEN_W//2), cy - SCREEN_H//2 - offset
        elif edge == 1: x, y = cx + SCREEN_W//2 + offset, cy + random.randint(-SCREEN_H//2, SCREEN_H//2)
        elif edge == 2: x, y = cx + random.randint(-SCREEN_W//2, SCREEN_W//2), cy + SCREEN_H//2 + offset
        else:           x, y = cx - SCREEN_W//2 - offset, cy + random.randint(-SCREEN_H//2, SCREEN_H//2)

        x = max(50, min(MAP_W - 50, x))
        y = max(50, min(MAP_H - 50, y))

        # HP scales with time
        hp_mult = 1.0 + (self.game_time / 60.0) ** 1.3

        t = self.game_time; kinds = ['grunt']
        if t > 20:  kinds.append('grunt')
        if t > 40:  kinds.append('charger')
        if t > 45:  kinds.append('fast')
        if t > 60:  kinds.append('bomber')
        if t > 70:  kinds.append('shooter')
        if t > 75:  kinds.extend(['fast', 'grunt'])
        if t > 90:  kinds.append('splitter')
        if t > 100: kinds.append('tank')
        if t > 110: kinds.append('teleporter')
        if t > 140: kinds.extend(['tank', 'fast', 'charger'])
        if t > 180: kinds.extend(['shooter', 'teleporter'])

        kind = kind_override if kind_override else random.choice(kinds)
        spr = self.spr_enemies.get(kind, self.spr_enemies['grunt'])
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
                if e.key == pygame.K_q and self.state == State.PAUSED:
                    self.state = State.MENU
                if e.key == pygame.K_r and self.state == State.PAUSED:
                    self.reset(); self.state = State.PLAYING
                if e.key == pygame.K_m:
                    self.audio.toggle_mute()
                if e.key in (pygame.K_RETURN, pygame.K_SPACE):
                    if self.state == State.MENU: self.reset(); self.state = State.PLAYING
                    elif self.state == State.GAME_OVER: self.reset(); self.state = State.PLAYING
                    elif self.state == State.PLAYING: self.player.try_dash(pygame.key.get_pressed(), self.fx)
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
            up.apply(self.player)
            self.fx.popup(self.player.x, self.player.y - 30, up.name, up.color)
            self.check_player_evolution()
            self.check_boss_spawn()
            self.state = State.PLAYING

    def check_player_evolution(self):
        # Evolutions at Level 5 and 10
        if self.player.level >= 5 and self.player.tier == 1:
            self.player.tier = 2
            self.player.sprite = self.spr_player_tiers[1]
            self.player.orbit_damage += 25
            self.player.max_hp += 30
            self.player.hp = self.player.max_hp
            self.fx.popup(self.player.x, self.player.y - 60, "EVOLVED!", (100, 200, 255))
            self.audio.play('levelup', 0.8)
        elif self.player.level >= 10 and self.player.tier == 2:
            self.player.tier = 3
            self.player.sprite = self.spr_player_tiers[2]
            self.player.orbit_count += 2
            self.player.orbit_size += 4
            self.player.max_hp += 50
            self.player.hp = self.player.max_hp
            self.fx.popup(self.player.x, self.player.y - 60, "ASCENDED!", (255, 100, 255))
            self.audio.play('levelup', 1.0)

    def check_boss_spawn(self):
        if self.player.level % BOSS_LEVEL_INTERVAL == 0 and self.player.level > 0:
            if not self.boss_alive and self.boss_state == 'idle':
                self.boss_state = 'warning'
                self.boss_warning_t = 3.0

    def update(self, dt):
        self.menu_t += dt
        if self.state in (State.PAUSED, State.LEVEL_UP, State.GAME_OVER): return

        if self.hit_stop > 0:
            self.hit_stop -= dt
            self.shake.update(dt)
            self.fx.update(dt)
            return

        if self.damage_flash > 0:
            self.damage_flash -= dt

        self.game_time += dt
        keys = pygame.key.get_pressed()
        self.player.update(dt, keys, self.fx)
        self.camera.update(dt, self.player.x, self.player.y, MAP_W, MAP_H)

        # Boss spawning logic state machine
        if self.boss_state == 'warning':
            self.boss_warning_t -= dt
            if self.boss_warning_t <= 0:
                self.spawn_enemy(kind_override='boss')
                self.boss_alive = True
                self.boss_state = 'active'
                self.shake.trigger(10, 0.4)

        self.spawn_timer -= dt
        if self.spawn_timer <= 0:
            self.spawn_enemy()
            self.spawn_timer = max(0.2, 1.2 - self.game_time * 0.008)

        for en in self.enemies:
            en.update(dt, self.player)
            if en.kind == 'boss':
                en.sprite = self.spr_boss_phases[en.boss_phase]
            for proj_data in en.pending_projectiles:
                self.projectiles.append(Projectile(*proj_data, self.spr_projectile))
            en.pending_projectiles.clear()
            
            # Handle Splitter spawns
            for spawn_data in en.pending_spawns:
                sx, sy, skind = spawn_data
                self.enemies.append(Enemy(sx, sy, skind, self.spr_enemies.get(skind, self.spr_enemies['grunt']), self.audio))
            en.pending_spawns.clear()

        for g in self.gems: g.update(dt, self.player)

        for p in self.projectiles: p.update(dt)
        self.projectiles = [p for p in self.projectiles if p.alive]

        # Projectile vs player
        for p in self.projectiles[:]:
            if math.hypot(self.player.x - p.x, self.player.y - p.y) < self.player.radius + p.radius:
                self.player.take_damage(p.dmg, self.fx, self.shake)
                self.damage_flash = 0.2
                self.projectiles.remove(p)

        # Dash damage
        if self.player.dash_t > 0 and getattr(self.player, 'dash_damage', 0) > 0:
            for en in self.enemies[:]:
                if en.is_spawning or en.detonating: continue
                if math.hypot(self.player.x - en.x, self.player.y - en.y) < en.radius + self.player.radius:
                    en.take_damage(self.player.dash_damage)
                    self.fx.burst(en.x, en.y, 8, C_ACCENT, spd=(2, 4))

        # Orbital Collisions
        for ox, oy in self.player.get_orb_positions():
            for en in self.enemies[:]:
                if en.is_spawning or en.detonating: continue
                if math.hypot(ox - en.x, oy - en.y) < en.radius + self.player.orbit_size:
                    # Calculate damage with crit
                    dmg = self.player.orbit_damage
                    is_crit = random.random() < self.player.crit_chance
                    if is_crit: dmg *= 2
                    
                    en.take_damage(dmg)
                    self.audio.play('hit', 0.15)
                    self.fx.burst(ox, oy, 4, (255, 220, 100) if not is_crit else (255, 255, 100), spd=(1, 3), life=(0.1, 0.2), size=(1, 3))
                    if is_crit:
                        self.fx.popup(en.x, en.y - 20, f"{dmg}!", (255, 255, 100))

                    if en.is_dead:
                        if en.kind == 'boss': 
                            self.boss_alive = False
                            self.boss_state = 'idle'
                            self.hit_stop = 0.15
                        else:
                            self.hit_stop = 0.02
                            
                        # Bomber explosion
                        if en.kind == 'bomber':
                            self.fx.burst(en.x, en.y, 40, (255, 160, 50), spd=(4, 8), life=(0.3, 0.5), size=(4, 7))
                            self.shake.trigger(6, 0.2)
                            # Check player proximity for explosion damage
                            if math.hypot(self.player.x - en.x, self.player.y - en.y) < 120:
                                self.player.take_damage(40, self.fx, self.shake)
                                self.damage_flash = 0.3
                            # Destroy other enemies in radius
                            for other in self.enemies[:]:
                                if other is not en and not other.detonating and math.hypot(other.x - en.x, other.y - en.y) < 100:
                                    other.take_damage(60)
                        
                        # Splitter spawn
                        if en.kind == 'splitter':
                            for _ in range(2):
                                en.pending_spawns.append((en.x + random.uniform(-20, 20), en.y + random.uniform(-20, 20), 'fast'))

                        self.enemies.remove(en); self.kill_count += 1
                        
                        # Lifesteal
                        if self.player.lifesteal > 0:
                            self.player.hp = min(self.player.max_hp, self.player.hp + self.player.lifesteal)
                            self.fx.popup(self.player.x, self.player.y - 20, f"+{self.player.lifesteal}", (100, 255, 100))

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
            # Bombers don't deal contact damage, they detonate. Detonating enemies don't deal contact damage.
            if en.is_spawning or en.detonating or en.kind == 'bomber': continue 
            if math.hypot(self.player.x - en.x, self.player.y - en.y) < en.radius + self.player.radius:
                self.player.take_damage(en.dmg, self.fx, self.shake, attacker=en)
                self.damage_flash = 0.2
                dx, dy = en.x - self.player.x, en.y - self.player.y
                d = math.hypot(dx, dy) or 1
                en.x += (dx/d) * 15; en.y += (dy/d) * 15

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
                    # Pick 3 random upgrades, weighting common higher than rare/legendary
                    weighted_pool = []
                    for up in UPGRADES:
                        weight = 10 if up.rarity == "common" else 3 if up.rarity == "rare" else 1
                        weighted_pool.extend([up] * weight)
                    self.upgrade_choices = random.sample(weighted_pool, 3)
                    break

        if self.player.hp <= 0:
            self.state = State.GAME_OVER
            if self.kill_count > self.high_score:
                self.high_score = self.kill_count
                try:
                    with open("ember_hs.json", "w") as f:
                        json.dump({"hs": self.high_score}, f)
                except Exception:
                    pass
            self.fx.burst(self.player.x, self.player.y, 40, (255, 100, 30), spd=(3, 10), life=(0.5, 1.0))
            self.shake.trigger(15, 0.5)

        self.fx.update(dt); self.shake.update(dt)

    def draw(self):
        bg_x = -int(self.camera.x) % SCREEN_W - SCREEN_W
        bg_y = -int(self.camera.y) % SCREEN_H - SCREEN_H
        for x in range(bg_x, SCREEN_W, SCREEN_W):
            for y in range(bg_y, SCREEN_H, SCREEN_H):
                self.screen.blit(self.bg_texture, (x, y))

        cam_x = self.camera.x - self.shake.offset[0]
        cam_y = self.camera.y - self.shake.offset[1]
        
        if self.state in (State.PLAYING, State.PAUSED, State.LEVEL_UP, State.GAME_OVER):
            # Draw Map Boundaries
            boundary_rect = pygame.Rect(-cam_x, -cam_y, MAP_W, MAP_H)
            pygame.draw.rect(self.screen, (255, 50, 50), boundary_rect, 5)
            
            for g in self.gems: g.draw(self.screen, cam_x, cam_y)
            for en in self.enemies: en.draw(self.screen, cam_x, cam_y, self.sprite_cache)
            
            scaled_orb_size = self.player.orbit_size * 4
            scaled_orb = self.sprite_cache.get_scaled(self.spr_orb, scaled_orb_size)
            for ox, oy in self.player.get_orb_positions():
                rect = scaled_orb.get_rect(center=(int(ox - cam_x), int(oy - cam_y)))
                self.screen.blit(scaled_orb, rect)

            if self.player.hp > 0: self.player.draw(self.screen, cam_x, cam_y)
            for p in self.projectiles: p.draw(self.screen, cam_x, cam_y)
            self.fx.draw(self.screen, self.font_xs, cam_x, cam_y)

        if self.state == State.MENU: self.draw_menu()
        elif self.state == State.PLAYING: self.draw_hud()
        elif self.state == State.LEVEL_UP: self.draw_hud(); self.draw_level_up()
        elif self.state == State.PAUSED: self.draw_hud(); self.draw_paused()
        elif self.state == State.GAME_OVER: self.draw_hud(); self.draw_game_over()

        if self.damage_flash > 0:
            flash = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
            flash.fill((255, 50, 50, int(100 * (self.damage_flash / 0.2))))
            self.screen.blit(flash, (0, 0))

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
        t = self.font_s.render(f"High Score: {self.high_score}", True, C_TEXT_DIM)
        self.screen.blit(t, (SCREEN_W - t.get_width() - 20, 85))
        
        # Tier indicator
        t = self.font_s.render(f"Tier: {p.tier}", True, C_ACCENT)
        self.screen.blit(t, (20, 70))
        
        # Extra stats indicators
        stats_y = 90
        if p.lifesteal > 0:
            self.screen.blit(self.font_xs.render(f"Vampirism: +{p.lifesteal}", True, (200, 50, 50)), (20, stats_y)); stats_y += 15
        if p.thorns > 0:
            self.screen.blit(self.font_xs.render(f"Thorns: {p.thorns}", True, (150, 50, 200)), (20, stats_y)); stats_y += 15
        if p.crit_chance > 0:
            self.screen.blit(self.font_xs.render(f"Crit: {int(p.crit_chance*100)}%", True, (255, 255, 100)), (20, stats_y)); stats_y += 15

        if not self.audio.enabled:
            mt = self.font_s.render("[AUDIO DISABLED]", True, C_TEXT_DIM)
            self.screen.blit(mt, (20, SCREEN_H - 30))
        elif self.audio.muted:
            mt = self.font_s.render("[MUTED]", True, C_TEXT_DIM)
            self.screen.blit(mt, (20, SCREEN_H - 30))

        if self.boss_state == 'warning':
            pulse = abs(math.sin(self.menu_t * 8))
            col = (255, int(50 + 100 * pulse), int(50 * pulse))
            warn = self.font_m.render("⚠  BOSS INCOMING  ⚠", True, col)
            warn.set_alpha(int(180 + 75 * pulse))
            self.screen.blit(warn, warn.get_rect(center=(SCREEN_W // 2, SCREEN_H - 50)))

        boss = next((e for e in self.enemies if e.kind == 'boss'), None)
        if boss:
            bw = 600; bh = 20
            bx = (SCREEN_W - bw) // 2; by = 20
            pygame.draw.rect(self.screen, (40, 10, 40), (bx, by, bw, bh))
            hp_color = PHASE_COLORS[boss.boss_phase]
            pygame.draw.rect(self.screen, hp_color, (bx, by, int(bw * (boss.hp / boss.max_hp)), bh))
            pygame.draw.rect(self.screen, C_TEXT, (bx, by, bw, bh), 2)
            label = self.font_boss_hp.render(f"BOSS  {int(boss.hp)}/{boss.max_hp}", True, C_TEXT)
            self.screen.blit(label, label.get_rect(center=(bx + bw // 2, by + bh // 2)))

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
        lines = ["WASD / ARROWS  —  Move", "SPACE  —  Dash", "M  —  Mute Audio", "Q  —  Quit to Menu (Paused)"]
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
            self.screen.blit(s, rect); pygame.draw.rect(self.screen, up.color, rect, 3, border_radius=8)
            num = self.font_l.render(str(i+1), True, up.color); self.screen.blit(num, (x + 15, y + 10))
            nm = self.font_m.render(up.name, True, up.color); self.screen.blit(nm, nm.get_rect(center=(x + card_w//2, y + 100)))
            
            # Display rarity
            if up.rarity != "common":
                rar = self.font_xs.render(f"[{up.rarity.upper()}]", True, C_ACCENT)
                self.screen.blit(rar, rar.get_rect(center=(x + card_w//2, y + 125)))
            
            words = up.desc.split(); lines = []; curr = ""
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
        self.screen.blit(t, t.get_rect(center=(SCREEN_W//2, SCREEN_H//2 - 40)))
        s = self.font_s.render("ESC: Resume  |  R: Restart  |  Q: Quit to Menu", True, C_TEXT_DIM)
        self.screen.blit(s, s.get_rect(center=(SCREEN_W//2, SCREEN_H//2 + 20)))

    def draw_game_over(self):
        ov = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        ov.fill((20, 0, 0, 180)); self.screen.blit(ov, (0, 0))
        t = self.font_l.render("EXTINGUISHED", True, C_DANGER)
        self.screen.blit(t, t.get_rect(center=(SCREEN_W//2, SCREEN_H//2 - 60)))
        s = self.font_m.render(f"Survived {int(self.game_time)}s", True, C_TEXT)
        self.screen.blit(s, s.get_rect(center=(SCREEN_W//2, SCREEN_H//2)))
        s = self.font_m.render(f"{self.kill_count} Kills", True, C_TEXT)
        self.screen.blit(s, s.get_rect(center=(SCREEN_W//2, SCREEN_H//2 + 35)))
        s = self.font_s.render(f"High Score: {self.high_score}", True, C_ACCENT)
        self.screen.blit(s, s.get_rect(center=(SCREEN_W//2, SCREEN_H//2 + 75)))

    def run(self):
        running = True
        while running:
            dt = min(self.clock.tick(FPS) / 1000.0, 1/30)
            running = self.handle_events()
            self.update(dt)
            self.draw()
        pygame.quit()