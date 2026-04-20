"""
============================================================
  FORGE MASTER — Math de stats (pure, sans I/O)
  Transformations sur les dictionnaires de profil :
  application d'équipements, de companions, finalisation, etc.
============================================================
"""

from typing import Dict

from .constants import PERCENT_STATS_KEYS


def finaliser_bases(profil: Dict) -> Dict:
    """
    Calcule attaque_base à partir de attaque_total et des pourcentages.
    Mute et retourne le profil.
    """
    type_atq   = profil.get("type_attaque", "corps_a_corps")
    damage_pct = profil.get("damage_pct", 0.0)
    melee_pct  = profil.get("melee_pct", 0.0)
    ranged_pct = profil.get("ranged_pct", 0.0)

    bonus = damage_pct + (ranged_pct if type_atq == "distance" else melee_pct)
    total = profil.get("attaque_total", 0.0)
    profil["attaque_base"] = total / (1 + bonus / 100) if bonus else total
    return profil


def stats_combat(profil: Dict) -> Dict:
    """Extrait les stats nécessaires à la simulation de combat."""
    return {
        "hp":              profil["hp_total"],
        "attaque":         profil["attaque_total"],
        "taux_crit":       profil["taux_crit"],
        "degat_crit":      profil["degat_crit"],
        "health_regen":    profil["health_regen"],
        "lifesteal":       profil["lifesteal"],
        "double_chance":   profil["double_chance"],
        "vitesse_attaque": profil["vitesse_attaque"],
        "skill_damage":    profil["skill_damage"],
        "skill_cooldown":  profil["skill_cooldown"],
        "chance_blocage":  profil["chance_blocage"],
        "type_attaque":    profil["type_attaque"],
    }


def _recalculer_totaux(profil: Dict) -> None:
    """Recalcule hp_total et attaque_total depuis les bases et pourcentages."""
    profil["hp_total"] = profil["hp_base"] * (1 + profil["health_pct"] / 100)

    type_atq = profil.get("type_attaque", "corps_a_corps")
    bonus = profil["damage_pct"] + (
        profil["ranged_pct"] if type_atq == "distance" else profil["melee_pct"])
    profil["attaque_total"] = profil["attaque_base"] * (1 + bonus / 100)


def appliquer_changement(profil: Dict, eq_ancien: Dict, eq_nouveau: Dict) -> Dict:
    """Remplace un équipement par un autre. Retourne un nouveau dict."""
    nouveau = dict(profil)

    for k in PERCENT_STATS_KEYS:
        nouveau[k] = round(
            profil.get(k, 0.0) - eq_ancien.get(k, 0.0) + eq_nouveau.get(k, 0.0), 6)

    if eq_nouveau.get("type_attaque") is not None:
        nouveau["type_attaque"] = eq_nouveau["type_attaque"]

    nouveau["hp_base"]      = profil["hp_base"]      - eq_ancien.get("hp_flat",     0) + eq_nouveau.get("hp_flat",     0)
    nouveau["attaque_base"] = profil["attaque_base"] - eq_ancien.get("damage_flat", 0) + eq_nouveau.get("damage_flat", 0)

    _recalculer_totaux(nouveau)
    return nouveau


def appliquer_companion(profil: Dict, ancien: Dict, nouveau_c: Dict) -> Dict:
    """Remplace un pet ou un mount par un autre. Retourne un nouveau dict."""
    nouveau = dict(profil)

    for k in PERCENT_STATS_KEYS:
        nouveau[k] = round(
            profil.get(k, 0.0) - ancien.get(k, 0.0) + nouveau_c.get(k, 0.0), 6)

    nouveau["hp_base"]      = profil["hp_base"]      - ancien.get("hp_flat",     0) + nouveau_c.get("hp_flat",     0)
    nouveau["attaque_base"] = profil["attaque_base"] - ancien.get("damage_flat", 0) + nouveau_c.get("damage_flat", 0)

    _recalculer_totaux(nouveau)
    return nouveau


# Alias rétrocompatibles
appliquer_pet   = appliquer_companion
appliquer_mount = appliquer_companion
