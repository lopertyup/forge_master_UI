"""
============================================================
  FORGE MASTER — Optimiseur génétique v3
  - hp_base / atk_base / type_attaque fixes par config
  - 24 slots % uniquement (avec remise, additifs)
  - Melee ignoré si distance, Ranged ignoré si corps_a_corps
  - Skill Cooldown négatif (réduit le cooldown)
  - Skills fixes : u1, u2, u3

  Placer dans : forge_master_UI/forge_optimizer.py
============================================================
"""

import random
import itertools
from collections import defaultdict

# ════════════════════════════════════════════════════════════
#  CONFIGURATION — à ajuster selon ton personnage
# ════════════════════════════════════════════════════════════

POPULATION_SIZE  = 32
TOP_K            = 8
NUM_GENERATIONS  = 10
MAX_SUBSTATS     = 24   # nombre de slots (avec remise)

# ── Profil de base fixe ──────────────────────────────────────
# Modifie ces valeurs selon ton personnage
HP_BASE          = 14_882_381.0
ATK_BASE         = 3_146_578.0
TYPE_ATTAQUE     = "distance"   # "distance" ou "corps_a_corps"

# ── Skills fixes ─────────────────────────────────────────────
# Codes définis dans skills.txt
SKILLS_CODES     = ["u1", "u2", "u3"]

# ── Pool de substats % ───────────────────────────────────────
# Format : clé_interne → (min_par_slot, max_par_slot)
# Le Skill Cooldown est en négatif : chaque slot donne entre -7% et 0%
# (une valeur plus négative = meilleur cooldown)

SUBSTATS_POOL = {
    "taux_crit":       (0.0,  12.0),
    "degat_crit":      (0.0, 100.0),
    "vitesse_attaque": (0.0,  40.0),
    "double_chance":   (0.0,  40.0),
    "damage_pct":      (0.0,  15.0),
    "skill_damage":    (0.0,  30.0),
    "ranged_pct":      (0.0,  15.0),   # ignoré si corps_a_corps
    "melee_pct":       (0.0,  50.0),   # ignoré si distance
    "chance_blocage":  (0.0,   5.0),
    "lifesteal":       (0.0,  20.0),
    "health_regen":    (0.0,   6.0),
    "skill_cooldown":  (-7.0,  0.0),   # négatif = réduit le cooldown
    "health_pct":      (0.0,  15.0),
}

# Max théorique absolu par stat (tous les slots sur la même stat)
SUBSTATS_MAX_ABS = {
    "taux_crit":       12.0  * MAX_SUBSTATS,
    "degat_crit":      100.0 * MAX_SUBSTATS,
    "vitesse_attaque": 40.0  * MAX_SUBSTATS,
    "double_chance":   40.0  * MAX_SUBSTATS,
    "damage_pct":      15.0  * MAX_SUBSTATS,
    "skill_damage":    30.0  * MAX_SUBSTATS,
    "ranged_pct":      15.0  * MAX_SUBSTATS,
    "melee_pct":       50.0  * MAX_SUBSTATS,
    "chance_blocage":  5.0   * MAX_SUBSTATS,
    "lifesteal":       20.0  * MAX_SUBSTATS,
    "health_regen":    6.0   * MAX_SUBSTATS,
    "skill_cooldown":  7.0   * MAX_SUBSTATS,   # on compare en valeur absolue
    "health_pct":      15.0  * MAX_SUBSTATS,
}

# Noms affichables
SUBSTATS_LABELS = {
    "taux_crit":       "Crit Chance",
    "degat_crit":      "Crit Damage",
    "vitesse_attaque": "Attack Speed",
    "double_chance":   "Double Chance",
    "damage_pct":      "Damage %",
    "skill_damage":    "Skill Damage",
    "ranged_pct":      "Ranged Damage",
    "melee_pct":       "Melee Damage",
    "chance_blocage":  "Block Chance",
    "lifesteal":       "Lifesteal",
    "health_regen":    "Health Regen",
    "skill_cooldown":  "Skill Cooldown",
    "health_pct":      "Health %",
}


# ════════════════════════════════════════════════════════════
#  CHARGEMENT DES SKILLS
# ════════════════════════════════════════════════════════════

_skills_cache = None

def charger_skills_fixes():
    """Charge u1, u2, u3 depuis le backend une seule fois."""
    global _skills_cache
    if _skills_cache is not None:
        return _skills_cache
    from backend.forge_master import charger_skills
    tous = charger_skills()
    _skills_cache = []
    for code in SKILLS_CODES:
        if code in tous:
            _skills_cache.append((code, tous[code]))
    return _skills_cache


# ════════════════════════════════════════════════════════════
#  GÉNÉRATION D'UN BUILD
# ════════════════════════════════════════════════════════════

def _pool_actif():
    """
    Retourne le pool de stats pertinent selon le type d'attaque :
    - distance  → exclut melee_pct
    - corps_a_corps → exclut ranged_pct
    """
    exclus = "melee_pct" if TYPE_ATTAQUE == "distance" else "ranged_pct"
    return {k: v for k, v in SUBSTATS_POOL.items() if k != exclus}


def build_aleatoire():
    """
    Génère un build aléatoire :
    - hp_base, atk_base, type_attaque fixes (config)
    - 24 slots % tirés avec remise dans le pool actif
    - Les valeurs du même type s'additionnent
    - Calcule hp_total et atk_total avec les bonus %
    """
    pool  = _pool_actif()
    keys  = list(pool.keys())
    stats = {k: 0.0 for k in SUBSTATS_POOL}

    for _ in range(MAX_SUBSTATS):
        k = random.choice(keys)
        lo, hi = pool[k]
        stats[k] += random.uniform(lo, hi)

    # Calcul des totaux
    hp_total = HP_BASE * (1 + stats["health_pct"] / 100)

    if TYPE_ATTAQUE == "distance":
        bonus_atq = stats["damage_pct"] + stats["ranged_pct"]
    else:
        bonus_atq = stats["damage_pct"] + stats["melee_pct"]
    atk_total = ATK_BASE * (1 + bonus_atq / 100)

    stats["hp_total"]      = hp_total
    stats["attaque_total"] = atk_total
    stats["hp_base"]       = HP_BASE
    stats["attaque_base"]  = ATK_BASE
    stats["type_attaque"]  = TYPE_ATTAQUE

    return stats


# ════════════════════════════════════════════════════════════
#  COMBAT
# ════════════════════════════════════════════════════════════

def score_combat(stats_j, stats_e, skills):
    """
    Taux de victoire de j contre e (0.0 → 1.0).
    Les deux combattants ont les mêmes skills.
    """
    from backend.forge_master import simuler_100
    wins, loses, draws = simuler_100(stats_j, stats_e, skills, skills)
    total = wins + loses + draws
    return wins / total if total > 0 else 0.0


# ════════════════════════════════════════════════════════════
#  TOURNOI ROUND-ROBIN
# ════════════════════════════════════════════════════════════

def round_robin(population, skills, progress_callback=None):
    """
    Chaque build affronte tous les autres avec les skills fixes.
    Retourne [(score, build), ...] trié du meilleur au pire.
    """
    n      = len(population)
    scores = [0.0] * n
    paires = list(itertools.combinations(range(n), 2))
    total  = len(paires)

    for idx, (i, j) in enumerate(paires):
        if progress_callback:
            progress_callback(idx, total)

        win_i = score_combat(population[i], population[j], skills)
        scores[i] += win_i
        scores[j] += (1.0 - win_i)

    for i in range(n):
        scores[i] /= (n - 1)

    return sorted(zip(scores, population), key=lambda x: x[0], reverse=True)


# ════════════════════════════════════════════════════════════
#  ALGORITHME PRINCIPAL
# ════════════════════════════════════════════════════════════

def optimiser(
    population_size=POPULATION_SIZE,
    top_k=TOP_K,
    num_generations=NUM_GENERATIONS,
    generation_callback=None,
    progress_callback=None,
    stop_flag=None,
):
    """
    Lance l'optimisation génétique.

    Callbacks :
      generation_callback(gen, top_score, avg_score, classement)
      progress_callback(combat_idx, total_combats, gen)
      stop_flag : threading.Event — si set(), arrête proprement

    Retourne (hall_of_fame, historique).
    """
    skills       = charger_skills_fixes()
    population   = [build_aleatoire() for _ in range(population_size)]
    historique   = []
    hall_of_fame = []

    for gen in range(1, num_generations + 1):
        if stop_flag and stop_flag.is_set():
            break

        def _progress(idx, total, g=gen):
            if progress_callback:
                progress_callback(idx, total, g)

        classement = round_robin(population, skills, progress_callback=_progress)

        top_score = classement[0][0]
        avg_score = sum(s for s, _ in classement[:top_k]) / top_k
        historique.append((gen, top_score, avg_score))

        for score, build in classement[:top_k]:
            hall_of_fame.append((score, gen, build))

        if generation_callback:
            generation_callback(gen, top_score, avg_score, classement)

        survivants = [build for _, build in classement[:top_k]]
        nouveaux   = [build_aleatoire() for _ in range(population_size - top_k)]
        population = survivants + nouveaux

    hall_of_fame.sort(key=lambda x: x[0], reverse=True)
    return hall_of_fame, historique


# ════════════════════════════════════════════════════════════
#  ANALYSE DES RÉSULTATS
# ════════════════════════════════════════════════════════════

def analyser_substats(hall_of_fame):
    """
    Pour chaque substat, calcule la valeur moyenne dans les builds gagnants
    et son taux par rapport au max théorique absolu.

    Pour skill_cooldown (négatif), on compare en valeur absolue.

    Retourne [(taux, clé, label, moyenne, max_abs), ...] trié desc.
    """
    totaux = defaultdict(float)
    nb     = len(hall_of_fame)

    for _, _, build in hall_of_fame:
        for k in SUBSTATS_POOL:
            totaux[k] += build.get(k, 0.0)

    lignes = []
    for k in SUBSTATS_POOL:
        max_abs  = SUBSTATS_MAX_ABS[k]
        moyenne  = totaux[k] / nb if nb > 0 else 0.0
        # Pour cooldown : valeur négative, on compare en absolu
        val_abs  = abs(moyenne)
        taux     = val_abs / max_abs if max_abs > 0 else 0.0
        lignes.append((taux, k, SUBSTATS_LABELS.get(k, k), moyenne, max_abs))

    return sorted(lignes, reverse=True)