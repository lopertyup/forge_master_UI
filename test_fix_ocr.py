"""Unit test for fix_ocr: runs every N→O pair from Exemple OCR.txt
through fix_ocr() and feeds the result into the real parser, asserting
the parser extracts the exact same stats as from the hand-typed O text.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.fix_ocr import fix_ocr
from backend.parser import (
    parse_equipment, parse_profile_text,
    parse_companion, parse_companion_meta,
    parse_skill_meta,
)


# ═══════════════════════════════════════════════════════════
#  Test pairs — each (N_raw, O_reference, kind)
# ═══════════════════════════════════════════════════════════

EQUIPMENT_PAIRS = [
    # --- Necklace swap ---
    ("""Equipped
[Quantum]HiggsCollar
210kDamage
LV.92
+33.3%AttackSpeed
+25.7%DoubleChance
[Quantum]VoidNecklace
223kDamage
LV.98
+1.84%BlockChance
NEW!
+13.4%Health
Sell
Equip""",
     """Equipped

Lv.92

[Quantum] Higgs Collar
210k Damage
+33.3% Attack Speed
+25.7% Double Chance

Lv. 98

NEW!

[Quantum] Void Necklace
223k Damage
+1.84% Block Chance
+13.4% Health

Sell

Equip"""),

    # --- Belt swap ---
    ("""Equipped
[Quantum]NeutrinoBelt
1.84mHealth
LV.101
+5.13%HealthRegen
+9.54%Damage
[Quantum]NeutrinoBelt
1.86mHealth
LV.102
+8.73%AttackSpeed
NEW!
+25.9%MeleeDamage
Sell
Equip""",
     """Equipped

Lv. 101

[Quantum] Neutrino Belt
1.84m Health
+5.13% Health Regen
+9.54% Damage

4

Lv. 102

NEW!

[Quantum] Neutrino Belt
1.86m Health
+8.73% Attack Speed
+25.9% Melee Damage

Sell

Equip"""),

    # --- Black belt ---
    ("""Equipped
[Quantum]NeutrinoBelt
1.84mHealth
LV.101
+5.13%HealthRegen
+9.54%Damage
[Quantum]BlackBelt
1.88mHealth
LV.103
+11.4%SkillDamage
NEW!
+4.1%HealthRegen
Sell
Equip""",
     """Equipped

Lv. 101

[Quantum] Neutrino Belt
1.84m Health
+5.13% Health Regen
+9.54% Damage

4

Lv. 103

NEW!

[Quantum] Black Belt
1.88m Health
+11.4% Skill Damage
+4.1% Health Regen

Sell

Equip"""),

    # --- Single-substat new (RoboFeet) ---
    ("""Equipped
[Quantum]AntimatterFeet
1.8mHealth
66:07
+10.2%CriticalChance
+11.4%RangedDamage
[interstellar]RoboFeet
117kHealth
LO.103
+1.2%HealthRegen
NEW!
Sell
Equip""",
     """Equipped

Lv.99

[Quantum] Antimatter Feet
1.8m Health
+10.2% Critical Chance
+11.4% Ranged Damage

Lv. 103

NEW!

[Interstellar] Robo Feet
117k Health
+1.2% Health Regen

Sell

Equip"""),

    # --- Both single-substat (RoboFeet → HydraulicFeet) ---
    ("""Equipped
[interstellar]RoboFeet
117kHealth
LO.103
+1.2%HealthRegen
[interstellar]HydraulicFeet
116kHealth
LV.102
+44.2%MeleeDamage
NEW!
Sell
Equip""",
     """Equipped

LV. 103

[Interstellar] Robo Feet
117k Health
+1.2% Health Regen

Lv. 102

NEW!

[Interstellar] Hydraulic Feet
116k Health
+44.2% Melee Damage

Sell

Equip"""),

    # --- Weapon (ranged) ---
    ("""Equipped
[Quantum]BlackGun
210kDamage(ranged)
LV.92
+14.3%Lifesteal
+10.6%Damage
[Quantum]BlackStaff
223kDamage(ranged)
LV.98
+24.2%SkillDamage
NEW!
+1.17%Lifesteal
Sell
Equip""",
     """Equipped

Lv. 92

[Quantum] Black Gun
210k Damage (ranged)
+14.3% Lifesteal
+10.6% Damage

Lv. 98

NEW!

[Quantum] Black Staff
223k Damage (ranged)
+24.2% Skill Damage
+1.17% Lifesteal

Sell

Equip"""),

    # --- Single-substat equipped, two-substat new ---
    ("""Equipped
[interstellar]RoboFeet
117kHealth
LO.103
+1.2%HealthRegen
[Quantum]AntigravityBoots
1.77mHealth
LV.97
+7.58%SkillDamage
NEW!
+3.91%RangedDamage
Sell
Equip""",
     """Equipped

Lv. 103

[Interstellar] Robo Feet
117k Health
+1.2% Health Regen

Lv. 97

NEW!

[Quantum] Antigravity Boots
1.77m Health 4
+7.58% Skill Damage
+3.91% Ranged Damage

Sell

Equip"""),
]


PROFILE_PAIRS = [
    ("""lopertyup y
[-FR-]
Lv. 23 Forge
X,227m
5.51mTotalDamage
31.7mTotalHealth
LV.103
V.-103
54
LV.78
LV.92
LV.97
LV.102
LV.3
LV.15
LV.3
LV.8
+10.6%CriticalChance
+95.2%CriticalDamage
+10.5% Health Regen
+82.1%Lifesteal
+64.4%DoubleChance
+10.6%Damage
+161%Moloonamano

lopertyupoy
[-FR-]
Lv. 23 Forge
Y.227m
5.51mTotalDamage
31.7mTotalHealth
LV.103
LV.54
LV.103
LV.78
LV.92
LV.97
LV.102
LV.+7
LV.3
LV.153
LV.3
LV.8
+64.4%DoubleChance
+10.6%Damage
+16.1%MeleeDamage
+21.6%RangedDamage
+164%AttackSpeed
+7.58%SkillDamage*""",
     """Lv. 23 Forge
5.51m Total Damage
31.7m Total Health
+10.6% Critical Chance
+95.2% Critical Damage
+10.5% Health Regen
+82.1% Lifesteal
+64.4% Double Chance
+10.6% Damage
+16.1% Melee Damage
+21.6% Ranged Damage
+164% Attack Speed
+7.58% Skill Damage"""),
]


OPPONENT_PAIRS = [
    ("""ScgEric o
[SHAKS]
Lv.24Forge
X410m
10mTotalDamage
56.3mTotalHealth
LV.106
LV.106
LV.108
104
66:7
LV.108
LV.101
Lv.32
V.4
LV.4
LV.4
LV23
L0.22
LV.25
+5.39%CriticalChance
+178%CriticalDamage
+43.1%HealthRegen
+8.32%Lifesteal
+45.8%DoubleChance
+30.6%Damage
+757%Moloonamano

SegEric o
[SHAKS]
Lv.24 Forge
X410m
10mTotalDamage
56.3mTotalHealth
LV.106
104
LV.106
LV.108
6607
LV.108
LV.101
Lv.32
LV.4
L0.23
L.22
Lv.25
+8.32%Lifesteal
+45.8%DoubleChance
+30.6%Damage
+75.7%MeleeDamage
+24.9%SkillDamage
+14.1%Health""",
     """Lv. 24 Forge
10m Total Damage
56.3m Total Health
+5.39% Critical Chance
+178% Critical Damage
+43.1% Health Regen
+8.32% Lifesteal
+45.8% Double Chance
+30.6% Damage
+75.7% Melee Damage
+24.9% Skill Damage
+14.1% Health"""),
]


PET_PAIRS = [
    ("""[Ultimate] Electry
Equipped
1.47mDamage
3.93mHealth
LV15
+33.5%AttackSpeed
+19.7%LiFesteal
Upgrade
Remove""",
     """Equipped

LV. 15

[Ultimate] Electry
1.47m Damage
3.93m Health
+33.5% Attack Speed
+19.7% Lifesteal

Upgrade

Remove"""),

    ("""[Epic] Tiger
12.1kDamage
32.3kHealth
LV6
+5.06%Health""",
     """Lv.6

[Epic] Tiger
12.1k Damage
32.3k Health
+5.06% Health"""),
]


MOUNT_PAIRS = [
    ("""[Rare] Crab
Equipped
10.4kDamage
83.2kHealth
+10.6%CriticalChance
Upgrade
Remove""",
     """Equipped

LV.1

[Rare] Crab
10.4k Damage
83.2k Health
+10.6% Critical Chance

Upgrade

Remove"""),

    ("""[Ultimate]MiniDragon
LV.52
238mDamage
1.9bHealth
+36.9%DoubleChance
+25.8%AttackSpeed""",
     """Lv.52

[Ultimate] Mini Dragon
238m Damage
1.9b Health
+36.9% Double Chance
+25.8% Attack Speed"""),
]


SKILL_PAIRS = [
    ("""[Ultimate]Stampede
Equipped
CallonaBull stampede,each
LV.3
dealing2.45mDamage
0/2
Passive:
+43.4kBaseDamage+347kBaseHealth
Upgrade
Remove""",
     """Equipped

Lv.3
0/2

[Ultimate] Stampede
Call on a Bull stampede, each
dealing 2.45m Damage

Passive:
+43.4k Base Damage +347k Base Health

Upgrade

Remove"""),
]


# ═══════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════

def _stats_subset(d: dict, keys) -> dict:
    return {k: d.get(k) for k in keys}

def _fmt(d: dict) -> str:
    return ", ".join(f"{k}={v}" for k, v in d.items())


def _assert_equal(context: str, fixed_result: dict, ref_result: dict,
                  keys: list) -> bool:
    ok = True
    for k in keys:
        a = fixed_result.get(k)
        b = ref_result.get(k)
        # Soft compare: ignore tiny float noise and None vs 0.0
        if isinstance(a, float) and isinstance(b, float):
            if abs(a - b) > 1e-3:
                ok = False
        elif a != b:
            # None vs 0.0 — treat as equal
            if (a in (None, 0.0) and b in (None, 0.0)):
                continue
            ok = False
    if not ok:
        print(f"  ✗ MISMATCH [{context}]")
        print(f"    fixed → {_fmt(_stats_subset(fixed_result, keys))}")
        print(f"    ref   → {_fmt(_stats_subset(ref_result, keys))}")
    return ok


# ═══════════════════════════════════════════════════════════
#  Runners
# ═══════════════════════════════════════════════════════════

EQ_KEYS = ["hp_flat", "damage_flat", "crit_chance", "crit_damage",
           "health_regen", "lifesteal", "double_chance", "attack_speed",
           "skill_damage", "skill_cooldown", "block_chance",
           "health_pct", "damage_pct", "melee_pct", "ranged_pct",
           "attack_type"]

PROFILE_KEYS = ["hp_total", "attack_total", "crit_chance", "crit_damage",
                "health_regen", "lifesteal", "double_chance", "attack_speed",
                "skill_damage", "skill_cooldown", "block_chance",
                "health_pct", "damage_pct", "melee_pct", "ranged_pct"]

COMP_KEYS = ["hp_flat", "damage_flat", "crit_chance", "crit_damage",
             "health_regen", "lifesteal", "double_chance", "attack_speed",
             "skill_damage", "skill_cooldown", "block_chance",
             "health_pct", "damage_pct", "melee_pct", "ranged_pct"]


def run_equipment():
    print("=" * 60)
    print("EQUIPMENT")
    print("=" * 60)
    passed = 0
    for i, (n, o) in enumerate(EQUIPMENT_PAIRS, 1):
        fixed = fix_ocr(n)
        # Split both on NEW! as the real pipeline does.
        import re as _re
        f_parts = _re.split(r"NEW\s*!", fixed, flags=_re.IGNORECASE)
        o_parts = _re.split(r"NEW\s*!", o,     flags=_re.IGNORECASE)
        if len(f_parts) < 2 or len(o_parts) < 2:
            print(f"  ✗ case {i}: NEW! split failed (fixed={len(f_parts)} / ref={len(o_parts)})")
            print("--- fixed ---"); print(fixed); print("---")
            continue
        f_old = parse_equipment(f_parts[0])
        f_new = parse_equipment(f_parts[1])
        o_old = parse_equipment(o_parts[0])
        o_new = parse_equipment(o_parts[1])
        ok = True
        ok &= _assert_equal(f"case {i} OLD", f_old, o_old, EQ_KEYS)
        ok &= _assert_equal(f"case {i} NEW", f_new, o_new, EQ_KEYS)
        if ok:
            print(f"  ✓ case {i}")
            passed += 1
    print(f"  {passed}/{len(EQUIPMENT_PAIRS)} passed")
    return passed, len(EQUIPMENT_PAIRS)


def run_profile():
    print("=" * 60)
    print("PROFILE")
    print("=" * 60)
    passed = 0
    for i, (n, o) in enumerate(PROFILE_PAIRS, 1):
        fixed = fix_ocr(n)
        f_res = parse_profile_text(fixed)
        o_res = parse_profile_text(o)
        if _assert_equal(f"case {i}", f_res, o_res, PROFILE_KEYS):
            print(f"  ✓ case {i}")
            passed += 1
        else:
            print("--- fixed ---"); print(fixed); print("---")
    print(f"  {passed}/{len(PROFILE_PAIRS)} passed")
    return passed, len(PROFILE_PAIRS)


def run_opponent():
    print("=" * 60)
    print("OPPONENT (parsed via profile_text)")
    print("=" * 60)
    passed = 0
    for i, (n, o) in enumerate(OPPONENT_PAIRS, 1):
        fixed = fix_ocr(n)
        f_res = parse_profile_text(fixed)
        o_res = parse_profile_text(o)
        if _assert_equal(f"case {i}", f_res, o_res, PROFILE_KEYS):
            print(f"  ✓ case {i}")
            passed += 1
        else:
            print("--- fixed ---"); print(fixed); print("---")
    print(f"  {passed}/{len(OPPONENT_PAIRS)} passed")
    return passed, len(OPPONENT_PAIRS)


def run_pet():
    print("=" * 60)
    print("PET")
    print("=" * 60)
    passed = 0
    for i, (n, o) in enumerate(PET_PAIRS, 1):
        fixed = fix_ocr(n)
        f_meta = parse_companion_meta(fixed)
        o_meta = parse_companion_meta(o)
        # Compare stats + level + name + rarity
        ok = True
        if f_meta["level"] != o_meta["level"]:
            ok = False; print(f"  ✗ case {i} level: fixed={f_meta['level']} ref={o_meta['level']}")
        if f_meta["name"] != o_meta["name"]:
            ok = False; print(f"  ✗ case {i} name: fixed={f_meta['name']!r} ref={o_meta['name']!r}")
        if f_meta["rarity"] != o_meta["rarity"]:
            ok = False; print(f"  ✗ case {i} rarity: fixed={f_meta['rarity']!r} ref={o_meta['rarity']!r}")
        ok &= _assert_equal(f"case {i} stats", f_meta["stats"], o_meta["stats"], COMP_KEYS)
        if ok:
            print(f"  ✓ case {i}")
            passed += 1
        else:
            print("--- fixed ---"); print(fixed); print("---")
    print(f"  {passed}/{len(PET_PAIRS)} passed")
    return passed, len(PET_PAIRS)


def run_mount():
    print("=" * 60)
    print("MOUNT")
    print("=" * 60)
    passed = 0
    for i, (n, o) in enumerate(MOUNT_PAIRS, 1):
        fixed = fix_ocr(n)
        f_meta = parse_companion_meta(fixed)
        o_meta = parse_companion_meta(o)
        ok = True
        if f_meta["level"] != o_meta["level"]:
            ok = False; print(f"  ✗ case {i} level: fixed={f_meta['level']} ref={o_meta['level']}")
        if f_meta["name"] != o_meta["name"]:
            ok = False; print(f"  ✗ case {i} name: fixed={f_meta['name']!r} ref={o_meta['name']!r}")
        if f_meta["rarity"] != o_meta["rarity"]:
            ok = False; print(f"  ✗ case {i} rarity: fixed={f_meta['rarity']!r} ref={o_meta['rarity']!r}")
        ok &= _assert_equal(f"case {i} stats", f_meta["stats"], o_meta["stats"], COMP_KEYS)
        if ok:
            print(f"  ✓ case {i}")
            passed += 1
        else:
            print("--- fixed ---"); print(fixed); print("---")
    print(f"  {passed}/{len(MOUNT_PAIRS)} passed")
    return passed, len(MOUNT_PAIRS)


def run_skill():
    print("=" * 60)
    print("SKILL")
    print("=" * 60)
    passed = 0
    for i, (n, o) in enumerate(SKILL_PAIRS, 1):
        fixed = fix_ocr(n)
        f_meta = parse_skill_meta(fixed)
        o_meta = parse_skill_meta(o)
        ok = True
        for k in ["name", "rarity", "level", "total_damage", "passive_damage", "passive_hp"]:
            a, b = f_meta[k], o_meta[k]
            if isinstance(a, float) and isinstance(b, float):
                if abs(a - b) > 1e-3:
                    ok = False; print(f"  ✗ case {i} {k}: fixed={a} ref={b}")
            elif a != b:
                ok = False; print(f"  ✗ case {i} {k}: fixed={a!r} ref={b!r}")
        if ok:
            print(f"  ✓ case {i}")
            passed += 1
        else:
            print("--- fixed ---"); print(fixed); print("---")
    print(f"  {passed}/{len(SKILL_PAIRS)} passed")
    return passed, len(SKILL_PAIRS)


if __name__ == "__main__":
    results = [
        run_equipment(),
        run_profile(),
        run_opponent(),
        run_pet(),
        run_mount(),
        run_skill(),
    ]
    total_passed = sum(p for p, _ in results)
    total_cases  = sum(t for _, t in results)
    print()
    print("=" * 60)
    print(f"TOTAL: {total_passed}/{total_cases}")
    print("=" * 60)
    sys.exit(0 if total_passed == total_cases else 1)
