"""
============================================================
  FORGE MASTER — Moteur de simulation de combat
  Combat 1v1 déterministe au tick près avec skills,
  buffs, crits, lifesteal, blocage, double attaque, etc.

  IMPORTANT : duree_max est un paramètre de simuler() — plus
  de monkey-patch sur une globale. Permet à plusieurs threads
  de simuler en parallèle avec des timeouts différents.
============================================================
"""

import random
from typing import Dict, List, Optional, Tuple

from .constants import (
    AVANCE_DISTANCE,
    DEFAULT_DUREE_MAX,
    N_SIMULATIONS,
    TICK,
    VITESSE_BASE,
)


class SkillInstance:
    DELAI_INITIAL = 3.8

    def __init__(self, data: Dict, skill_damage_pct: float, skill_cooldown_pct: float):
        self.data          = data
        self.nom           = data["name"]
        self.type_skill    = data["type"]
        self.hits          = int(data.get("hits", 1))
        self.cooldown_base = float(data.get("cooldown", 10.0))
        self.buff_dur      = float(data.get("buff_duration", 0.0))
        self.buff_atq      = float(data.get("buff_atq", 0.0))
        self.buff_hp       = float(data.get("buff_hp", 0.0))

        sd = skill_damage_pct / 100.0
        sc = skill_cooldown_pct / 100.0
        dmg_base          = float(data.get("damage", 0.0))
        self.dmg_par_hit  = dmg_base * (1 + sd)
        self.cooldown     = max(0.1, self.cooldown_base * (1 + sc))

        self.timer         = -self.DELAI_INITIAL
        self.hit_interval  = self.cooldown / self.hits if self.hits > 1 else 0.0
        self.hit_timer     = 0.0
        self.hits_restants = 0
        self.buff_actif    = False
        self.buff_timer    = 0.0
        self.atq_bonus     = 0.0
        self.hp_bonus      = 0.0

    def tick(self, dt: float, porteur: "Combattant", cible: "Combattant") -> None:
        self.timer += dt
        if self.type_skill == "damage":
            self._tick_damage(dt, cible)
        elif self.type_skill == "buff":
            self._tick_buff(dt, porteur)

    def _tick_damage(self, dt: float, cible: "Combattant") -> None:
        if self.hits_restants > 0:
            self.hit_timer += dt
            if self.hit_timer >= self.hit_interval or self.hits == 1:
                if cible.vivant():
                    cible.hp -= self.dmg_par_hit
                self.hits_restants -= 1
                self.hit_timer = 0.0
        elif self.timer >= self.cooldown:
            self.timer = 0.0
            self.hits_restants = self.hits - 1
            self.hit_timer = 0.0
            if cible.vivant():
                cible.hp -= self.dmg_par_hit

    def _tick_buff(self, dt: float, porteur: "Combattant") -> None:
        if self.buff_actif:
            self.buff_timer += dt
            if self.buff_timer >= self.buff_dur:
                porteur.attaque -= self.atq_bonus
                self.atq_bonus   = 0.0
                self.hp_bonus    = 0.0
                self.buff_actif  = False
                self.buff_timer  = 0.0
        elif self.timer >= self.cooldown:
            self.timer      = 0.0
            self.buff_actif = True
            self.buff_timer = 0.0
            self.atq_bonus  = self.buff_atq
            self.hp_bonus   = self.buff_hp
            porteur.attaque += self.atq_bonus
            porteur.hp      += self.hp_bonus


class Combattant:
    def __init__(self, s: Dict, skills_actifs: Optional[List[Tuple[str, Dict]]] = None):
        self.hp_max          = s.get("hp_total", s.get("hp", 0.0))
        self.hp              = float(self.hp_max)
        self.health_regen    = s.get("health_regen",   0.0) / 100.0
        self.attaque         = s.get("attaque_total", s.get("attaque", 0.0))
        self.vitesse_attaque = s.get("vitesse_attaque", 0.0) / 100.0
        self.double_chance   = s.get("double_chance",   0.0) / 100.0
        self.lifesteal       = s.get("lifesteal",       0.0) / 100.0
        self.taux_crit       = s.get("taux_crit",       0.0) / 100.0
        self.degat_crit      = s.get("degat_crit",      0.0) / 100.0
        self.chance_blocage  = s.get("chance_blocage",  0.0) / 100.0
        self.type_attaque    = s.get("type_attaque", "corps_a_corps")
        self.freq            = VITESSE_BASE * (1.0 + self.vitesse_attaque)
        self.intervalle      = 1.0 / self.freq
        self.timer           = 0.0

        sd = s.get("skill_damage",  0.0)
        sc = s.get("skill_cooldown", 0.0)
        self.skills = [SkillInstance(data, sd, sc) for _, data in (skills_actifs or [])]

    def vivant(self) -> bool:
        return self.hp > 0

    def regenerer(self, dt: float) -> None:
        if self.hp < self.hp_max:
            self.hp = min(self.hp_max, self.hp + self.hp_max * self.health_regen * dt)

    def frapper(self, cible: "Combattant") -> None:
        coups = 2 if random.random() < self.double_chance else 1
        for _ in range(coups):
            if random.random() < cible.chance_blocage:
                continue
            dmg = self.attaque * (1 + self.degat_crit) if random.random() < self.taux_crit else self.attaque
            cible.hp -= dmg
            self.hp = min(self.hp_max, self.hp + dmg * self.lifesteal)


def simuler(
    sj: Dict,
    se: Dict,
    skills_j: Optional[List[Tuple[str, Dict]]] = None,
    skills_e: Optional[List[Tuple[str, Dict]]] = None,
    duree_max: float = DEFAULT_DUREE_MAX,
) -> str:
    """Lance un combat unique. Retourne 'WIN', 'LOSE' ou 'DRAW'."""
    j = Combattant(sj, skills_j)
    e = Combattant(se, skills_e)

    if j.type_attaque == e.type_attaque:
        j.timer, e.timer = 0.0, 0.0
    elif j.type_attaque == "distance":
        j.timer, e.timer = 0.0, -AVANCE_DISTANCE
    else:
        j.timer, e.timer = -AVANCE_DISTANCE, 0.0

    temps = 0.0
    while temps < duree_max:
        if not j.vivant() or not e.vivant():
            break
        j.regenerer(TICK)
        e.regenerer(TICK)
        for sk in j.skills:
            sk.tick(TICK, j, e)
        for sk in e.skills:
            sk.tick(TICK, e, j)
        j.timer += TICK
        e.timer += TICK
        if j.timer >= j.intervalle:
            j.timer = 0.0
            if e.vivant():
                j.frapper(e)
        if e.timer >= e.intervalle:
            e.timer = 0.0
            if j.vivant():
                e.frapper(j)
        temps += TICK

    if j.vivant() and not e.vivant():
        return "WIN"
    if e.vivant() and not j.vivant():
        return "LOSE"
    if not j.vivant() and not e.vivant():
        return "LOSE"
    return "DRAW"


def simuler_100(
    sj: Dict,
    se: Dict,
    skills_j: Optional[List[Tuple[str, Dict]]] = None,
    skills_e: Optional[List[Tuple[str, Dict]]] = None,
    n: int = N_SIMULATIONS,
    duree_max: float = DEFAULT_DUREE_MAX,
) -> Tuple[int, int, int]:
    """
    Lance N combats. Retourne (wins, loses, draws).
    Le nom 'simuler_100' est historique — N est paramétrable.
    """
    wins = loses = draws = 0
    for _ in range(n):
        r = simuler(sj, se, skills_j, skills_e, duree_max=duree_max)
        if r == "WIN":    wins  += 1
        elif r == "LOSE": loses += 1
        else:             draws += 1
    return wins, loses, draws
