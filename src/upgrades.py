from dataclasses import dataclass
from typing import Callable
from constants import DASH_CD, DASH_DAMAGE

@dataclass
class Upgrade:
    name: str
    desc: str
    color: tuple
    apply: Callable
    rarity: str = "common"

def upgrade_flare(p):
    p.orbit_count += 1

def upgrade_twin_stars(p):
    p.orbit_count += 2

def upgrade_wildfire(p):
    p.orbit_speed *= 1.4

def upgrade_inferno(p):
    p.orbit_damage += 15

def upgrade_expansion(p):
    p.orbit_radius += 25

def upgrade_magnitude(p):
    p.orbit_size += 3

def upgrade_magnetism(p):
    p.pickup_radius += 40
    p._update_pickup_surf()

def upgrade_celerity(p):
    p.speed *= 1.15

def upgrade_soul_mend(p):
    p.hp = min(p.max_hp, p.hp + 30)

def upgrade_vitality(p):
    p.max_hp += 20
    p.hp = p.max_hp

def upgrade_phase_shift(p):
    p.dash_cd = max(0.1, p.dash_cd - 0.3)

def upgrade_dash_combustion(p):
    p.dash_damage = getattr(p, 'dash_damage', 0) + DASH_DAMAGE

def upgrade_vampirism(p):
    p.lifesteal += 2

def upgrade_thorns(p):
    p.thorns += 20

def upgrade_critical(p):
    p.crit_chance += 0.15

UPGRADES = [
    Upgrade("Flare", "+1 Orbiting Orb", (255, 200, 80), upgrade_flare),
    Upgrade("Wildfire", "+40% Orbit Speed", (255, 100, 50), upgrade_wildfire),
    Upgrade("Inferno", "+15 Orbit Damage", (255, 50, 50), upgrade_inferno),
    Upgrade("Expansion", "+25 Orbit Radius", (100, 200, 255), upgrade_expansion),
    Upgrade("Magnitude", "+3 Orb Size", (255, 150, 200), upgrade_magnitude),
    Upgrade("Magnetism", "+40 Pickup Range", (100, 255, 200), upgrade_magnetism),
    Upgrade("Celerity", "+15% Move Speed", (200, 255, 100), upgrade_celerity),
    Upgrade("Soul Mend", "Heal 30 HP", (100, 255, 100), upgrade_soul_mend),
    Upgrade("Vitality", "+20 Max HP & Full Heal", (255, 100, 100), upgrade_vitality),
    Upgrade("Phase Shift", "-0.3s Dash CD", (150, 200, 255), upgrade_phase_shift),
    Upgrade("Combustion", "Dash Deals Damage", (255, 120, 0), upgrade_dash_combustion, "rare"),
    Upgrade("Vampirism", "Heal 2 HP per Kill", (200, 50, 50), upgrade_vampirism, "rare"),
    Upgrade("Thorns", "Reflect 20 Dmg on Hit", (150, 50, 200), upgrade_thorns, "rare"),
    Upgrade("Critical", "+15% Crit Chance (2x Dmg)", (255, 255, 100), upgrade_critical, "rare"),
    Upgrade("Twin Stars", "+2 Orbiting Orbs", (255, 150, 255), upgrade_twin_stars, "legendary"),
]