"""
============================================================
  FORGE MASTER — Backend (shim de compatibilité)

  Le backend a été découpé en modules thématiques :
    - backend/constants.py    : toutes les constantes
    - backend/parser.py       : parsers (texte -> dict)
    - backend/stats.py        : math pure sur les dicts de stats
    - backend/persistence.py  : lecture/écriture des .txt
    - backend/simulation.py   : moteur de combat

  Ce fichier re-exporte l'API publique pour conserver la
  rétrocompatibilité avec le code existant. Les nouveaux
  modules devraient importer directement depuis les sous-
  modules ciblés.
============================================================
"""

# Constantes ----------------------------------------------------
from .constants import (  # noqa: F401
    AVANCE_DISTANCE,
    COMPANION_DUREE_MAX,
    COMPANION_STATS_KEYS,
    DEFAULT_DUREE_MAX,
    MOUNT_FILE,
    MOUNT_STATS_KEYS,
    N_SIMULATIONS,
    PERCENT_STATS_KEYS,
    PETS_FILE,
    PETS_STATS_KEYS,
    PROFIL_FILE,
    SKILLS_FILE,
    STATS_KEYS,
    TICK,
    VITESSE_BASE,
)

# Parser --------------------------------------------------------
from .parser import (  # noqa: F401
    extraire,
    extraire_flat,
    parse_flat,
    parser_companion,
    parser_equipement,
    parser_mount,
    parser_pet,
    parser_texte,
)

# Stats math ----------------------------------------------------
from .stats import (  # noqa: F401
    appliquer_changement,
    appliquer_companion,
    appliquer_mount,
    appliquer_pet,
    finaliser_bases,
    stats_combat,
)

# Persistence ---------------------------------------------------
from .persistence import (  # noqa: F401
    charger_mount,
    charger_pets,
    charger_profil,
    charger_skills,
    companion_vide,
    mount_vide,
    pet_vide,
    sauvegarder_mount,
    sauvegarder_pets,
    sauvegarder_profil,
)

# Simulation ----------------------------------------------------
from .simulation import (  # noqa: F401
    Combattant,
    SkillInstance,
    simuler,
    simuler_100,
)

# Compat : certains callers lisaient fm.DUREE_MAX pour le patcher.
# On expose la valeur mais les nouveaux callers doivent passer
# duree_max en argument à simuler() / simuler_100().
DUREE_MAX = DEFAULT_DUREE_MAX
