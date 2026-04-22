"""
============================================================
  FORGE MASTER — Persistence (file read / write)
  Read and write profile.txt, pets.txt, mount.txt, skills.txt.
============================================================
"""

import logging
import os
from typing import Dict, List, Optional, Tuple

from .constants import (
    COMPANION_STATS_KEYS,
    MOUNT_FILE,
    MOUNT_LIBRARY_FILE,
    PETS_FILE,
    PETS_LIBRARY_FILE,
    PROFILE_FILE,
    SKILL_NUMERIC_KEYS,
    SKILLS_FILE,
    SKILLS_LIBRARY_FILE,
    STATS_KEYS,
)

log = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════
#  PROFILE + ACTIVE SKILLS
# ════════════════════════════════════════════════════════════
#
#  NOTE: equipped skills are NOT stored inline in profile.txt anymore.
#  They live in their own file (skills.txt, 3 slots) — same pattern as
#  pets.txt and mount.txt. Old profiles with a `skills =` line are
#  silently tolerated (the line is ignored).
# ════════════════════════════════════════════════════════════

def save_profile(player: Dict, skills: Optional[List[Tuple[str, Dict]]] = None) -> None:
    """
    `skills` is accepted for back-compat but no longer written: equipped
    skills are persisted by save_skills() into skills.txt.
    """
    with open(PROFILE_FILE, "w", encoding="utf-8") as f:
        f.write("# ============================================================\n")
        f.write("# FORGE MASTER — Player profile (editable by hand)\n")
        f.write("# ============================================================\n\n")
        f.write("[PLAYER]\n")
        for k in STATS_KEYS:
            f.write(f"{k:20s} = {player.get(k, 0.0)}\n")
        f.write(f"{'attack_type':20s} = {player.get('attack_type', 'melee')}\n\n")


def _read_section(lines: List[str], start: int) -> Optional[Dict]:
    """
    Read a key=value section until the next [...] header or end of file.
    `start` must point to the first line AFTER the [SECTION] header.
    """
    stats: Dict = {}
    for line in lines[start:]:
        line = line.strip()
        if line.startswith("["):
            break
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key, val = key.strip(), val.strip()
        if key == "attack_type":
            stats[key] = val
        elif key == "skills":
            # Legacy field — silently ignored. Equipped skills now live
            # in skills.txt and are loaded by load_skills().
            continue
        else:
            try:
                stats[key] = float(val)
            except ValueError:
                log.warning("profile.txt: invalid value for %s = %r", key, val)
    return stats if stats else None


def load_profile() -> Tuple[Optional[Dict], List[Tuple[str, Dict]]]:
    """
    Returns (profile, equipped_skills).
    `equipped_skills` is loaded from skills.txt (the new 3-slot format).
    """
    if not os.path.isfile(PROFILE_FILE):
        return None, []

    with open(PROFILE_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()

    profile: Optional[Dict] = None
    for i, line in enumerate(lines):
        if line.strip() == "[PLAYER]":
            profile = _read_section(lines, i + 1)
            break

    if profile is None:
        return None, []

    return profile, load_skills()


# ════════════════════════════════════════════════════════════
#  SKILLS — 3 equipped slots (S1 / S2 / S3)
# ════════════════════════════════════════════════════════════
#
#  skills.txt holds the CURRENT-LEVEL stats of the equipped skills,
#  in the same spirit as pets.txt and mount.txt.
#
#  Lv.1 reference values for swap simulations live in skills_library.txt
#  (see the LIBRARIES section below).
#
#  Returned format (back-compat with the simulator):
#      [(slot_label, data_dict), ...]
#  where data_dict has the keys expected by SkillInstance:
#      name, type, damage, hits, cooldown,
#      buff_duration, buff_atk, buff_hp,
#      passive_damage, passive_hp,
#      __name__, __rarity__, __level__
# ════════════════════════════════════════════════════════════

SKILL_SLOTS = ("S1", "S2", "S3")


def empty_skill() -> Dict:
    """Build an empty skill slot (all-zero stats, no identity)."""
    out: Dict = {k: 0.0 for k in SKILL_NUMERIC_KEYS}
    out["type"] = ""
    out["name"] = ""
    return out


def _is_empty_skill(slot: Dict) -> bool:
    return not slot.get("__name__")


def load_skills() -> List[Tuple[str, Dict]]:
    """
    Load the 3 equipped skill slots from skills.txt.

    Returns a list of (slot_label, data_dict) for slots that actually
    hold a skill (empty slots are skipped). Order follows S1, S2, S3.
    """
    slots: Dict[str, Dict] = {s: empty_skill() for s in SKILL_SLOTS}
    if not os.path.isfile(SKILLS_FILE):
        return []

    current: Optional[str] = None
    with open(SKILLS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("[") and line.endswith("]"):
                tag = line[1:-1].strip()
                current = tag if tag in SKILL_SLOTS else None
                continue
            if current is None or "=" not in line:
                continue
            key, val = line.split("=", 1)
            key, val = key.strip(), val.strip()
            if key in ("__name__", "__rarity__", "type"):
                slots[current][key] = val
            elif key == "__level__":
                try:
                    slots[current][key] = int(val)
                except ValueError:
                    log.warning("skills.txt: invalid level for %s = %r",
                                current, val)
            else:
                try:
                    slots[current][key] = float(val)
                except ValueError:
                    log.warning("skills.txt: invalid value for %s.%s = %r",
                                current, key, val)

    # Mirror __name__ into "name" so the simulator's SkillInstance keeps
    # working without changes.
    for slot in slots.values():
        if slot.get("__name__"):
            slot["name"] = slot["__name__"]

    return [(s, slots[s]) for s in SKILL_SLOTS if not _is_empty_skill(slots[s])]


def load_skill_slots() -> Dict[str, Dict]:
    """Like load_skills() but returns the raw {slot: dict} mapping
    including empty slots — used by the UI."""
    slots: Dict[str, Dict] = {s: empty_skill() for s in SKILL_SLOTS}
    if not os.path.isfile(SKILLS_FILE):
        return slots
    for label, data in load_skills():
        slots[label] = data
    return slots


def save_skills(skills_by_slot: Dict[str, Dict]) -> None:
    """Persist the 3 skill slots to skills.txt."""
    with open(SKILLS_FILE, "w", encoding="utf-8") as f:
        f.write("# ============================================================\n")
        f.write("# FORGE MASTER — Active skills (3 slots, editable by hand)\n")
        f.write("# ============================================================\n\n")
        for slot in SKILL_SLOTS:
            data = skills_by_slot.get(slot) or empty_skill()
            f.write(f"[{slot}]\n")
            if data.get("__name__"):
                f.write(f"{'__name__':14s} = {data['__name__']}\n")
            if data.get("__rarity__"):
                f.write(f"{'__rarity__':14s} = {data['__rarity__']}\n")
            if data.get("__level__"):
                f.write(f"{'__level__':14s} = {int(data['__level__'])}\n")
            if data.get("type"):
                f.write(f"{'type':14s} = {data['type']}\n")
            for k in SKILL_NUMERIC_KEYS:
                f.write(f"{k:14s} = {data.get(k, 0.0)}\n")
            f.write("\n")


# ════════════════════════════════════════════════════════════
#  PETS
# ════════════════════════════════════════════════════════════

def empty_companion() -> Dict[str, float]:
    return {k: 0.0 for k in COMPANION_STATS_KEYS}


# Back-compat aliases
pet_vide   = empty_companion
mount_vide = empty_companion


def load_pets() -> Dict[str, Dict[str, float]]:
    pets = {name: empty_companion() for name in ("PET1", "PET2", "PET3")}
    if not os.path.isfile(PETS_FILE):
        return pets

    with open(PETS_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()

    current: Optional[str] = None
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line in ("[PET1]", "[PET2]", "[PET3]"):
            current = line[1:-1]
        elif current and "=" in line:
            key, val = line.split("=", 1)
            key, val = key.strip(), val.strip()
            if key in ("__name__", "__rarity__"):
                pets[current][key] = val
            elif key == "__level__":
                try:
                    pets[current][key] = int(val)
                except ValueError:
                    log.warning("pets.txt: invalid level for %s = %r", current, val)
            else:
                try:
                    pets[current][key] = float(val)
                except ValueError:
                    log.warning("pets.txt: invalid value for %s.%s = %r", current, key, val)
    return pets


def save_pets(pets: Dict[str, Dict[str, float]]) -> None:
    with open(PETS_FILE, "w", encoding="utf-8") as f:
        f.write("# ============================================================\n")
        f.write("# FORGE MASTER — Active pets (editable by hand)\n")
        f.write("# ============================================================\n\n")
        for name in ("PET1", "PET2", "PET3"):
            pet = pets.get(name, empty_companion())
            f.write(f"[{name}]\n")
            # Identity (name/rarity) at the top of the section if set
            if pet.get("__name__"):
                f.write(f"{'__name__':20s} = {pet['__name__']}\n")
            if pet.get("__rarity__"):
                f.write(f"{'__rarity__':20s} = {pet['__rarity__']}\n")
            if pet.get("__level__"):
                f.write(f"{'__level__':20s} = {int(pet['__level__'])}\n")
            for k in COMPANION_STATS_KEYS:
                f.write(f"{k:20s} = {pet.get(k, 0.0)}\n")
            f.write("\n")


# ════════════════════════════════════════════════════════════
#  MOUNT
# ════════════════════════════════════════════════════════════

def load_mount() -> Dict[str, float]:
    mount = empty_companion()
    if not os.path.isfile(MOUNT_FILE):
        return mount

    with open(MOUNT_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()

    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("["):
            continue
        if "=" in line:
            key, val = line.split("=", 1)
            key, val = key.strip(), val.strip()
            if key in ("__name__", "__rarity__"):
                mount[key] = val
            elif key == "__level__":
                try:
                    mount[key] = int(val)
                except ValueError:
                    log.warning("mount.txt: invalid level = %r", val)
            else:
                try:
                    mount[key] = float(val)
                except ValueError:
                    log.warning("mount.txt: invalid value for %s = %r", key, val)
    return mount


def save_mount(mount: Dict[str, float]) -> None:
    with open(MOUNT_FILE, "w", encoding="utf-8") as f:
        f.write("# ============================================================\n")
        f.write("# FORGE MASTER — Active mount (editable by hand)\n")
        f.write("# ============================================================\n\n")
        f.write("[MOUNT]\n")
        if mount.get("__name__"):
            f.write(f"{'__name__':20s} = {mount['__name__']}\n")
        if mount.get("__rarity__"):
            f.write(f"{'__rarity__':20s} = {mount['__rarity__']}\n")
        if mount.get("__level__"):
            f.write(f"{'__level__':20s} = {int(mount['__level__'])}\n")
        for k in COMPANION_STATS_KEYS:
            f.write(f"{k:20s} = {mount.get(k, 0.0)}\n")


# ════════════════════════════════════════════════════════════
#  LIBRARIES (pets + mount at level 1)
# ════════════════════════════════════════════════════════════
#
#  Identical format for both files:
#
#      # comment
#      [Treant]
#      rarity      = ultimate
#      hp_flat     = 10200000.0
#      damage_flat = 427000.0
#
#      [Phoenix]
#      rarity      = legendary
#      hp_flat     = 8500000.0
#      damage_flat = 380000.0
#
#  The index key (e.g. "Treant") is case-sensitive on disk
#  but compared case-insensitively by the controller.
# ════════════════════════════════════════════════════════════

_LIBRARY_KEYS = ("rarity", "hp_flat", "damage_flat")


def _load_library(path: str) -> Dict[str, Dict]:
    if not os.path.isfile(path):
        return {}

    library: Dict[str, Dict] = {}
    current_name: Optional[str] = None
    current: Dict = {}

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("[") and line.endswith("]"):
                if current_name:
                    library[current_name] = current
                current_name = line[1:-1].strip()
                current = {"rarity": "common", "hp_flat": 0.0, "damage_flat": 0.0}
            elif current_name and "=" in line:
                key, val = line.split("=", 1)
                key, val = key.strip(), val.strip()
                if key == "rarity":
                    current[key] = val.lower()
                elif key in ("hp_flat", "damage_flat"):
                    try:
                        current[key] = float(val)
                    except ValueError:
                        log.warning("%s: invalid value for [%s].%s = %r",
                                    path, current_name, key, val)
        if current_name:
            library[current_name] = current
    return library


def _save_library(path: str, library: Dict[str, Dict], title: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write("# ============================================================\n")
        f.write(f"# FORGE MASTER — {title}\n")
        f.write("# Reference stats at level 1, indexed by name.\n")
        f.write("# ============================================================\n\n")
        for name in sorted(library.keys(), key=str.lower):
            entry = library[name]
            f.write(f"[{name}]\n")
            f.write(f"{'rarity':12s} = {entry.get('rarity', 'common')}\n")
            f.write(f"{'hp_flat':12s} = {entry.get('hp_flat', 0.0)}\n")
            f.write(f"{'damage_flat':12s} = {entry.get('damage_flat', 0.0)}\n\n")


def load_pets_library() -> Dict[str, Dict]:
    return _load_library(PETS_LIBRARY_FILE)


def save_pets_library(library: Dict[str, Dict]) -> None:
    _save_library(PETS_LIBRARY_FILE, library, "Pets library (level 1)")


def load_mount_library() -> Dict[str, Dict]:
    return _load_library(MOUNT_LIBRARY_FILE)


def save_mount_library(library: Dict[str, Dict]) -> None:
    _save_library(MOUNT_LIBRARY_FILE, library, "Mounts library (level 1)")


# ════════════════════════════════════════════════════════════
#  SKILLS LIBRARY (level 1 reference, identical pattern as pets/mount)
# ════════════════════════════════════════════════════════════

_SKILL_LIB_STRING_KEYS = ("rarity", "type")


def load_skills_library() -> Dict[str, Dict]:
    """Load skills_library.txt — Lv.1 reference for each known skill."""
    if not os.path.isfile(SKILLS_LIBRARY_FILE):
        return {}

    library: Dict[str, Dict] = {}
    current_name: Optional[str] = None
    current: Dict = {}

    def _empty_entry() -> Dict:
        entry = {k: 0.0 for k in SKILL_NUMERIC_KEYS}
        entry["rarity"] = "common"
        entry["type"]   = "damage"
        return entry

    with open(SKILLS_LIBRARY_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("[") and line.endswith("]"):
                if current_name:
                    library[current_name] = current
                current_name = line[1:-1].strip()
                current = _empty_entry()
            elif current_name and "=" in line:
                key, val = line.split("=", 1)
                key, val = key.strip(), val.strip()
                if key in _SKILL_LIB_STRING_KEYS:
                    current[key] = val.lower()
                elif key in SKILL_NUMERIC_KEYS:
                    try:
                        current[key] = float(val)
                    except ValueError:
                        log.warning("skills_library.txt: invalid value for [%s].%s = %r",
                                    current_name, key, val)
        if current_name:
            library[current_name] = current
    return library


def save_skills_library(library: Dict[str, Dict]) -> None:
    """Persist skills_library.txt, sorted alphabetically (case-insensitive)."""
    with open(SKILLS_LIBRARY_FILE, "w", encoding="utf-8") as f:
        f.write("# ============================================================\n")
        f.write("# FORGE MASTER — Skills library (level 1)\n")
        f.write("# Reference stats at level 1, indexed by name.\n")
        f.write("# ============================================================\n\n")
        for name in sorted(library.keys(), key=str.lower):
            entry = library[name]
            f.write(f"[{name}]\n")
            f.write(f"{'rarity':14s} = {entry.get('rarity', 'common')}\n")
            f.write(f"{'type':14s} = {entry.get('type', 'damage')}\n")
            for k in SKILL_NUMERIC_KEYS:
                f.write(f"{k:14s} = {entry.get(k, 0.0)}\n")
            f.write("\n")
