"""
============================================================
  FORGE MASTER — Optimiseur génétique v6
  Sélection par win rate + mutation locale contrainte
  Population : 32 builds
  Adversaire : profil actuel du joueur (fixe)
============================================================
"""

import math
import random
from typing import Callable, Dict, List, Optional, Tuple

from .simulation import simuler_100
from .stats import stats_combat

# ════════════════════════════════════════════════════════════
#  CONFIGURATION
# ════════════════════════════════════════════════════════════

N_BUILDS      = 32
N_SUBSTATS    = 24      # points à distribuer par build
SELECTION_PCT = 0.30    # garder top 30%
N_SURVIVORS   = max(2, round(N_BUILDS * SELECTION_PCT))  # ≈ 10

# Plages par point (valeur ajoutée à chaque tirage)
SUBSTATS_POOL: Dict[str, Tuple[float, float]] = {
    "taux_crit":       (0.0,  12.0),
    "degat_crit":      (0.0, 100.0),
    "vitesse_attaque": (0.0,  40.0),
    "double_chance":   (0.0,  40.0),
    "damage_pct":      (0.0,  15.0),
    "skill_damage":    (0.0,  30.0),
    "ranged_pct":      (0.0,  15.0),
    "melee_pct":       (0.0,  50.0),
    "chance_blocage":  (0.0,   5.0),
    "lifesteal":       (0.0,  20.0),
    "health_regen":    (0.0,   6.0),
    "skill_cooldown":  (-7.0,  0.0),
    "health_pct":      (0.0,  15.0),
}

SUBSTATS_LABELS = {
    "taux_crit":       "Crit Chance",
    "degat_crit":      "Crit Damage",
    "vitesse_attaque": "Attack Speed",
    "double_chance":   "Double Chance",
    "damage_pct":      "Damage %",
    "skill_damage":    "Skill Damage",
    "ranged_pct":      "Ranged Dmg",
    "melee_pct":       "Melee Dmg",
    "chance_blocage":  "Block Chance",
    "lifesteal":       "Lifesteal",
    "health_regen":    "Health Regen",
    "skill_cooldown":  "Skill Cooldown",
    "health_pct":      "Health %",
}

SUBSTATS_MOY_PAR_TIRAGE = {
    k: abs(lo + hi) / 2 if (lo + hi) != 0 else 1.0
    for k, (lo, hi) in SUBSTATS_POOL.items()
}

SUBSTATS_MAX_THEORIQUE = {
    k: N_SUBSTATS * SUBSTATS_MOY_PAR_TIRAGE[k]
    for k in SUBSTATS_POOL
}


# ════════════════════════════════════════════════════════════
#  GÉNÉRATION D'UN BUILD
# ════════════════════════════════════════════════════════════

def _build_depuis_substats(substats: Dict, hp_base: float, atk_base: float,
                            type_attaque: str) -> Dict:
    hp_total  = hp_base * (1 + substats["health_pct"] / 100)
    bonus_atq = substats["damage_pct"] + (
        substats["ranged_pct"] if type_attaque == "distance" else substats["melee_pct"])
    atk_total = atk_base * (1 + bonus_atq / 100)

    return {
        **substats,
        "hp_total":      hp_total,
        "attaque_total": atk_total,
        "hp_base":       hp_base,
        "attaque_base":  atk_base,
        "type_attaque":  type_attaque,
    }


def _substats_vides() -> Dict[str, float]:
    return {k: 0.0 for k in SUBSTATS_POOL}


def _distribuer_points(pool_actif: Dict[str, Tuple[float, float]]) -> Dict[str, float]:
    """Distribue N_SUBSTATS points uniformément sur le pool actif."""
    substats = _substats_vides()
    keys = list(pool_actif.keys())
    for _ in range(N_SUBSTATS):
        k = random.choice(keys)
        lo, hi = pool_actif[k]
        substats[k] += round(random.uniform(lo, hi), 2)
    return substats


def build_aleatoire(hp_base: float, atk_base: float, type_attaque: str) -> Dict:
    exclus   = "melee_pct" if type_attaque == "distance" else "ranged_pct"
    pool     = {k: v for k, v in SUBSTATS_POOL.items() if k != exclus}
    substats = _distribuer_points(pool)
    return _build_depuis_substats(substats, hp_base, atk_base, type_attaque)


# ════════════════════════════════════════════════════════════
#  MUTATION LOCALE
# ════════════════════════════════════════════════════════════

def muter(build: Dict, hp_base: float, atk_base: float, type_attaque: str,
          force: Optional[int] = None) -> Dict:
    """
    Déplace 1 à 3 points d'une stat vers une autre.
    Contrainte : la somme des points reste N_SUBSTATS.
    """
    exclus   = "melee_pct" if type_attaque == "distance" else "ranged_pct"
    pool     = {k: v for k, v in SUBSTATS_POOL.items() if k != exclus}
    keys     = list(pool.keys())
    substats = {k: build.get(k, 0.0) for k in SUBSTATS_POOL}

    if force is None:
        force = 3 if random.random() < 0.10 else random.randint(1, 2)

    for _ in range(force):
        sources = [k for k in keys if substats[k] != 0.0]
        if not sources:
            break
        src = random.choice(sources)
        lo_src, hi_src = pool[src]
        retire = round(random.uniform(lo_src, hi_src), 2)
        if lo_src >= 0:
            substats[src] = max(0.0, substats[src] - retire)
        else:
            substats[src] = min(0.0, substats[src] + abs(retire))

        cibles = [k for k in keys if k != src]
        dst    = random.choice(cibles)
        lo_dst, hi_dst = pool[dst]
        ajoute = round(random.uniform(lo_dst, hi_dst), 2)
        substats[dst] += ajoute

    return _build_depuis_substats(substats, hp_base, atk_base, type_attaque)


# ════════════════════════════════════════════════════════════
#  ÉVALUATION
# ════════════════════════════════════════════════════════════

def evaluer(build: Dict, adversaire: Dict, skills: List, n_sims: int) -> float:
    wins, loses, draws = simuler_100(build, adversaire, skills, skills, n=n_sims)
    total = wins + loses + draws
    return wins / total if total > 0 else 0.0


# ════════════════════════════════════════════════════════════
#  ANALYSE : MOYENNE + VARIANCE
# ════════════════════════════════════════════════════════════

def analyser(builds: List[Dict], scores: List[float]) -> List[Tuple]:
    """
    Pour chaque substat, calcule dans le top 30% :
      - pts_moy  : nombre de points investis en moyenne
      - pts_var  : écart-type du nombre de points
      - moyenne  : valeur brute moyenne
      - variance : écart-type brut

    Retourne [(pts_moy, pts_var, moyenne, variance, key, label), ...]
    trié par pts_moy desc.
    """
    n       = len(builds)
    n_top   = max(1, round(n * SELECTION_PCT))
    classes = sorted(range(n), key=lambda i: scores[i], reverse=True)
    top     = [builds[i] for i in classes[:n_top]]

    resultats = []
    for k in SUBSTATS_POOL:
        moy_tirage = SUBSTATS_MOY_PAR_TIRAGE[k]
        vals       = [abs(b.get(k, 0.0)) for b in top]
        moyenne    = sum(vals) / len(vals)
        variance   = math.sqrt(
            sum((v - moyenne) ** 2 for v in vals) / len(vals)
        ) if len(vals) > 1 else 0.0

        pts_moy = moyenne  / moy_tirage if moy_tirage else 0.0
        pts_var = variance / moy_tirage if moy_tirage else 0.0

        resultats.append((pts_moy, pts_var, moyenne, variance, k, SUBSTATS_LABELS.get(k, k)))

    return sorted(resultats, key=lambda x: x[0], reverse=True)


# ════════════════════════════════════════════════════════════
#  BOUCLE PRINCIPALE
# ════════════════════════════════════════════════════════════

def optimiser(
    profil: Dict,
    skills: List,
    n_generations: int = 8,
    n_sims: int = 100,
    generation_cb: Optional[Callable] = None,
    progress_cb: Optional[Callable] = None,
    stop_flag=None,
) -> Tuple[List[Dict], List[Tuple]]:
    hp_base      = profil["hp_base"]
    atk_base     = profil["attaque_base"]
    type_attaque = profil.get("type_attaque", "corps_a_corps")

    adversaire = stats_combat(profil)

    builds = [build_aleatoire(hp_base, atk_base, type_attaque)
              for _ in range(N_BUILDS)]

    top_builds: List[Dict] = []
    analyse: List[Tuple]   = []

    for gen in range(1, n_generations + 1):
        if stop_flag and stop_flag.is_set():
            break

        scores: List[float] = []
        for i, b in enumerate(builds):
            if stop_flag and stop_flag.is_set():
                break
            scores.append(evaluer(b, adversaire, skills, n_sims))
            if progress_cb:
                progress_cb(i + 1, len(builds), gen)

        if not scores:
            break

        analyse    = analyser(builds, scores)
        classes    = sorted(zip(scores, builds), key=lambda x: x[0], reverse=True)
        top_scores = [s for s, _ in classes[:N_SURVIVORS]]
        top_builds = [b for _, b in classes[:N_SURVIVORS]]
        wr_moyen   = sum(top_scores) / len(top_scores)

        if generation_cb:
            meilleur = top_builds[0]
            generation_cb(gen, top_builds, analyse, top_scores, wr_moyen, meilleur)

        nouveaux = list(top_builds)
        while len(nouveaux) < N_BUILDS:
            parent = random.choice(top_builds)
            nouveaux.append(muter(parent, hp_base, atk_base, type_attaque))
        builds = nouveaux

    return top_builds, analyse
