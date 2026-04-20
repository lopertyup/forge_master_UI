"""
============================================================
  FORGE MASTER — GameController (bridge UI <-> backend)

  Point d'entrée unique pour toute l'UI. Toutes les vues
  appellent des méthodes de GameController ; la controller
  orchestre backend + threading + dispatch thread-safe vers
  Tkinter via `after()`.

  Les opérations lourdes (simuler_100, tests pet/mount) sont
  déportées dans des threads daemon ; les callbacks sont
  rappelés sur le thread Tk via `_dispatch`.
============================================================
"""

import logging
import re
import threading
from typing import Callable, Dict, List, Optional, Tuple

from backend.constants import (
    COMPANION_DUREE_MAX,
    COMPANION_STATS_KEYS,
    N_SIMULATIONS,
    PETS_STATS_KEYS,
)
from backend.parser import (
    parser_equipement,
    parser_mount,
    parser_pet,
    parser_texte,
)
from backend.persistence import (
    charger_mount,
    charger_pets,
    charger_profil,
    charger_skills,
    sauvegarder_mount,
    sauvegarder_pets,
    sauvegarder_profil,
)
from backend.simulation import simuler_100
from backend.stats import (
    appliquer_changement,
    appliquer_mount,
    appliquer_pet,
    finaliser_bases,
    stats_combat,
)

log = logging.getLogger(__name__)


class GameController:
    """Bridge entre les vues CTk et le backend (stats, persistence, sim)."""

    # ── Init / chargement ───────────────────────────────────

    def __init__(self) -> None:
        self._profil: Optional[Dict]      = None
        self._skills: List                 = []
        self._pets:   Dict[str, Dict]      = {}
        self._mount:  Dict                 = {}
        self._tous_skills: Dict[str, Dict] = {}
        self._tk_root                      = None  # pour after() thread-safe
        self.reload()

    def set_tk_root(self, root) -> None:
        """Enregistre la racine Tk pour dispatcher les callbacks sur le thread UI."""
        self._tk_root = root

    def reload(self) -> None:
        """Recharge profil + pets + mount + skills depuis le disque."""
        self._profil, self._skills = charger_profil()
        self._pets                 = charger_pets()
        self._mount                = charger_mount()
        self._tous_skills          = charger_skills()
        log.info("GameController.reload : profil=%s, pets=%d, skills=%d",
                 "OK" if self._profil else "-",
                 len(self._pets), len(self._tous_skills))

    # ── Profil ──────────────────────────────────────────────

    def has_profil(self) -> bool:
        return self._profil is not None

    def get_profil(self) -> Dict:
        return dict(self._profil) if self._profil else {}

    def get_skills_actifs(self) -> List:
        return list(self._skills)

    def get_tous_skills(self) -> Dict[str, Dict]:
        return dict(self._tous_skills)

    def importer_texte_profil(self, texte: str, type_attaque: str) -> Dict:
        stats = parser_texte(texte)
        stats["type_attaque"] = type_attaque
        return finaliser_bases(stats)

    def set_profil(self, profil: Dict, skills: List) -> None:
        self._profil = profil
        self._skills = skills
        sauvegarder_profil(profil, skills)

    def get_skills_from_codes(self, codes: List[str]) -> List[Tuple[str, Dict]]:
        """Convertit une liste de codes (ex: ['cgs','uss','beb']) en [(code, data), ...]."""
        result: List[Tuple[str, Dict]] = []
        for code in codes[:3]:
            code = code.strip().lower()
            if code in self._tous_skills:
                result.append((code, self._tous_skills[code]))
        return result

    # ── Helpers thread-safe ─────────────────────────────────

    def _dispatch(self, callback: Callable, *args) -> None:
        """Appelle callback(*args) sur le thread Tk principal (via after)."""
        if self._tk_root is not None:
            self._tk_root.after(0, lambda: callback(*args))
        else:
            callback(*args)

    # ── Simulation principale (adversaire = build passé) ────

    def simuler(
        self,
        stats_adversaire: Dict,
        skills_adversaire: List,
        callback: Callable[[int, int, int], None],
        profil_override: Optional[Dict] = None,
        skills_override: Optional[List] = None,
    ) -> None:
        """Lance N_SIMULATIONS combats dans un thread secondaire."""
        profil = profil_override if profil_override else self._profil
        skills = skills_override if skills_override else self._skills

        if profil is None:
            self._dispatch(callback, 0, 0, 0)
            return

        sj = stats_combat(profil)
        se = stats_adversaire

        def _run() -> None:
            try:
                w, l, d = simuler_100(sj, se, skills, skills_adversaire,
                                      n=N_SIMULATIONS)
            except Exception:
                log.exception("simuler() a levé une exception")
                w, l, d = 0, 0, 0
            self._dispatch(callback, w, l, d)

        threading.Thread(target=_run, daemon=True).start()

    # ── Équipements ─────────────────────────────────────────

    def comparer_equipement(
        self, texte_comparaison: str
    ) -> Optional[Tuple[Dict, Dict, Dict]]:
        """Parse 'ANCIEN ... NEW! ... NOUVEAU' et renvoie (ancien, nouveau, profil_nv)."""
        if not re.search(r'NEW\s*!', texte_comparaison, re.IGNORECASE):
            return None

        parties       = re.split(r'NEW\s*!', texte_comparaison, flags=re.IGNORECASE)
        texte_ancien  = parties[0]
        texte_nouveau = parties[1] if len(parties) > 1 else ""

        eq_ancien  = parser_equipement(texte_ancien)
        eq_nouveau = parser_equipement(texte_nouveau)

        if self._profil is None:
            return None

        profil_nouveau = appliquer_changement(self._profil, eq_ancien, eq_nouveau)
        return eq_ancien, eq_nouveau, profil_nouveau

    def appliquer_equipement(self, profil_nouveau: Dict) -> None:
        self._profil = profil_nouveau
        sauvegarder_profil(profil_nouveau, self._skills)

    # ── Pets ────────────────────────────────────────────────

    def get_pets(self) -> Dict[str, Dict]:
        return {k: dict(v) for k, v in self._pets.items()}

    def get_pet(self, nom: str) -> Dict:
        return dict(self._pets.get(nom, {}))

    def importer_texte_pet(self, texte: str) -> Dict:
        return parser_pet(texte)

    def set_pet(self, nom: str, pet: Dict) -> None:
        self._pets[nom] = pet
        sauvegarder_pets(self._pets)

    def tester_pet(
        self,
        nouveau_pet: Dict,
        callback: Callable[[Dict[str, Tuple[int, int, int]]], None],
    ) -> None:
        """
        Pour chaque slot PET1/PET2/PET3 :
          NOUVEAU_MOI (avec nouveau pet) vs ANCIEN_MOI (avec ancien pet à ce slot).
        Appelle callback({nom_slot: (w, l, d)}).
        """
        if self._profil is None:
            self._dispatch(callback, {})
            return

        profil_actuel = dict(self._profil)
        pets_actuels  = {k: dict(v) for k, v in self._pets.items()}
        skills        = list(self._skills)

        def _run() -> None:
            resultats: Dict[str, Tuple[int, int, int]] = {}
            try:
                for nom in ("PET1", "PET2", "PET3"):
                    pet_ancien = pets_actuels.get(
                        nom, {k: 0.0 for k in PETS_STATS_KEYS})
                    resultats[nom] = self._compare_profil_vs_profil(
                        profil_nouveau=appliquer_pet(
                            profil_actuel, pet_ancien, nouveau_pet),
                        profil_ancien=profil_actuel,
                        skills=skills,
                    )
            except Exception:
                log.exception("tester_pet() a levé une exception")
            self._dispatch(callback, resultats)

        threading.Thread(target=_run, daemon=True).start()

    # ── Mount ───────────────────────────────────────────────

    def get_mount(self) -> Dict:
        return dict(self._mount)

    def importer_texte_mount(self, texte: str) -> Dict:
        return parser_mount(texte)

    def set_mount(self, mount: Dict) -> None:
        self._mount = mount
        sauvegarder_mount(mount)

    def tester_mount(
        self,
        nouveau_mount: Dict,
        callback: Callable[[int, int, int], None],
    ) -> None:
        """NOUVEAU_MOI (avec nouveau mount) vs ANCIEN_MOI (avec mount actuel)."""
        if self._profil is None:
            self._dispatch(callback, 0, 0, 0)
            return

        profil_actuel = dict(self._profil)
        mount_actuel  = dict(self._mount) if self._mount else {
            k: 0.0 for k in COMPANION_STATS_KEYS}
        skills        = list(self._skills)

        def _run() -> None:
            try:
                w, l, d = self._compare_profil_vs_profil(
                    profil_nouveau=appliquer_mount(
                        profil_actuel, mount_actuel, nouveau_mount),
                    profil_ancien=profil_actuel,
                    skills=skills,
                )
            except Exception:
                log.exception("tester_mount() a levé une exception")
                w, l, d = 0, 0, 0
            self._dispatch(callback, w, l, d)

        threading.Thread(target=_run, daemon=True).start()

    # ── Helper interne : NOUVEAU_MOI vs ANCIEN_MOI ───────────

    @staticmethod
    def _compare_profil_vs_profil(
        profil_nouveau: Dict,
        profil_ancien: Dict,
        skills: List,
    ) -> Tuple[int, int, int]:
        """
        Lance N_SIMULATIONS combats profil_nouveau vs profil_ancien avec
        la durée-max 'companion' (plus courte pour éviter les matchs nuls
        entre deux versions quasi identiques).
        """
        sj = stats_combat(profil_nouveau)
        se = stats_combat(profil_ancien)
        return simuler_100(sj, se, skills, skills,
                           n=N_SIMULATIONS,
                           duree_max=COMPANION_DUREE_MAX)

    # ── Helpers UI (compat — nouvelles vues utilisent ui.theme) ─

    @staticmethod
    def fmt_nombre(n: float) -> str:
        from ui.theme import fmt_nombre
        return fmt_nombre(n)

    @staticmethod
    def rarity_color(rarity: str) -> str:
        from ui.theme import rarity_color
        return rarity_color(rarity)

    @staticmethod
    def stats_display_list() -> List[Tuple[str, str, bool]]:
        """Liste (clé, label, is_flat) pour l'affichage détaillé d'un profil."""
        return [
            ("hp_total",        "❤  HP Total",         True),
            ("attaque_total",   "⚔  ATQ Total",         True),
            ("hp_base",         "   HP Base",           True),
            ("attaque_base",    "   ATQ Base",          True),
            ("health_pct",      "❤  Health %",          False),
            ("damage_pct",      "⚔  Damage %",          False),
            ("melee_pct",       "⚔  Melee %",           False),
            ("ranged_pct",      "⚔  Ranged %",          False),
            ("taux_crit",       "🎯 Crit Chance",        False),
            ("degat_crit",      "💥 Crit Damage",        False),
            ("health_regen",    "♻  Health Regen",      False),
            ("lifesteal",       "🩸 Lifesteal",          False),
            ("double_chance",   "✌  Double Chance",     False),
            ("vitesse_attaque", "⚡ Attack Speed",       False),
            ("skill_damage",    "✨ Skill Damage",       False),
            ("skill_cooldown",  "⏱  Skill Cooldown",    False),
            ("chance_blocage",  "🛡  Block Chance",      False),
        ]
