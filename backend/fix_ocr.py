"""
============================================================
  FORGE MASTER — OCR text fixer
  Turn raw OCR output (RapidOCR / PaddleOCR on BlueStacks
  captures) into text the parser can handle.

  Input example (N — from OCR):
      Equipped
      [Quantum]HiggsCollar
      210kDamage
      LV.92
      +33.3%AttackSpeed
      +25.7%DoubleChance

  Output (O — parser-ready):
      Equipped
      [Quantum] Higgs Collar
      210k Damage
      Lv. 92
      +33.3% Attack Speed
      +25.7% Double Chance

  Public API:

      fix_ocr(text: str) -> str
============================================================
"""

from __future__ import annotations

import re
from typing import List, Optional

# ── Canonical stat ordering (matches the in-game display) ───
# Used to reorder the substats in profile/opponent output so
# the textbox looks like the game's sheet. The parser's regex
# lookups are order-independent, so reordering is safe.
_STAT_ORDER = (
    "critical chance",
    "block chance",
    "health regen",
    "critical damage",
    "lifesteal",
    "double chance",
    "damage",
    "melee damage",
    "ranged damage",
    "attack speed",
    "skill damage",
    "skill cooldown",
    "health",
)

# ── Known stat names (lowercase) ────────────────────────────
# Used to tell a real "+NN% <stat>" line apart from OCR garbage
# like "+161% Moloonamano". Matching is lenient: we accept any
# known stat, optionally followed by extra words we ignore.
_KNOWN_PCT_STATS = (
    "critical chance", "critical damage",
    "attack speed", "double chance", "block chance",
    "health regen", "lifesteal", "skill damage", "skill cooldown",
    "melee damage", "ranged damage",
    "health", "damage",
)

# Explicit CamelCase map for stat names. Applied BEFORE generic
# CamelCase splitting so we never mangle one-word names (e.g.
# "Lifesteal" must not become "Life steal").
_STAT_CAMEL_MAP = {
    "AttackSpeed":    "Attack Speed",
    "DoubleChance":   "Double Chance",
    "BlockChance":    "Block Chance",
    "HealthRegen":    "Health Regen",
    "MeleeDamage":    "Melee Damage",
    "RangedDamage":   "Ranged Damage",
    "SkillDamage":    "Skill Damage",
    "SkillCooldown":  "Skill Cooldown",
    "CriticalChance": "Critical Chance",
    "CriticalDamage": "Critical Damage",
    "BaseDamage":     "Base Damage",
    "BaseHealth":     "Base Health",
    "TotalDamage":    "Total Damage",
    "TotalHealth":    "Total Health",
}

# OCR typos that would otherwise survive every normalization step.
_OCR_TYPOS = {
    "LiFesteal": "Lifesteal",
    "Lifeste al": "Lifesteal",
    "LifeSteal": "Lifesteal",
}

# Lines whose lowercased content is EXACTLY one of these are kept
# verbatim (after trim + canonical casing).
_KEYWORDS_PASSTHROUGH = {
    "equipped": "Equipped",
    "upgrade":  "Upgrade",
    "remove":   "Remove",
    "sell":     "Sell",
    "equip":    "Equip",
    "new!":     "NEW!",
    "new !":    "NEW!",
    "passive:": "Passive:",
    "passive :": "Passive:",
}

# Lines matching any of these get dropped (empty strings, single
# characters, lone digits, OCR artifacts unique to the game UI).
_DROP_PATTERNS = [
    re.compile(r"^\s*$"),                                # empty
    re.compile(r"^\s*[A-Za-z]\s*$"),                     # single letter
    re.compile(r"^\s*\d{1,6}\s*$"),                      # lone digits: 4, 54, 6607
    re.compile(r"^\s*\d+\s*:\s*\d+\s*$"),                # timer: 66:07
    re.compile(r"^\s*[XYxy]\s*[.,]\s*\d"),               # X,227m / Y.227m
    re.compile(r"^\s*[XY]\d"),                           # X410m
    re.compile(r"^\s*V\.?\s*[-+]?\s*\d"),                # V.-103, V.4
    re.compile(r"^\s*[Ll][Vv]\.?\s*[+\-]\s*\d"),         # LV.+7, Lv.-3 (OCR corrupt level)
    re.compile(r"^\s*\[\s*-.*-\s*\]\s*$"),               # [-FR-]
    re.compile(r"^\s*\[[A-Z]{3,}\]\s*$"),                # [SHAKS] all-caps tag
    re.compile(r"^\s*[A-Za-z][A-Za-z]*\s+[a-z]\s*$"),    # "lopertyup y" trailing-letter noise
    re.compile(r"^\s*(?:[A-Za-z]+\s+){1,3}[a-z]\s*$"),   # "Scg Eric o" — N words + trailing letter
    re.compile(r"^\s*lopertyup\w*\s*$", re.IGNORECASE),  # "lopertyupoy" player-name blob
    re.compile(r"^\s*Sc[gq]\s*Eric\s*\w?\s*$", re.IGNORECASE),  # "Scg Eric o" / "Seg Eric"
]


# ── Per-line normalization ──────────────────────────────────

def _normalize_line(line: str) -> str:
    # 1. Typos
    for wrong, right in _OCR_TYPOS.items():
        line = line.replace(wrong, right)

    # 2. LO / L0 → Lv (OCR confuses lowercase v with capital O or digit 0).
    line = re.sub(r"\b[Ll][O0]\.?\s*(\d)", r"Lv. \1", line)

    # 3. Level prefix: LV.92 / LV92 / lv.92 / LV 92 → "Lv. 92"
    line = re.sub(r"\b[Ll][Vv]\.?\s*(\d+)", r"Lv. \1", line)

    # 4. Rarity bracket casing: [interstellar] → [Interstellar]
    line = re.sub(
        r"\[([a-z])([A-Za-z]*)\]",
        lambda m: "[" + m.group(1).upper() + m.group(2) + "]",
        line,
    )

    # 5. Space after ']' when glued to a letter: "]Higgs" → "] Higgs"
    line = re.sub(r"\](\w)", r"] \1", line)

    # 6. Space between digit+unit and next word:
    #    "210kDamage" → "210k Damage", "1.84mHealth" → "1.84m Health"
    line = re.sub(r"(\d[kmbKMB])([A-Za-z])", r"\1 \2", line)

    # 7. Space between % and next letter: "+33%AttackSpeed" → "+33% AttackSpeed"
    line = re.sub(r"(%)([A-Za-z])", r"\1 \2", line)

    # 7bis. Space between a number and a following word, EXCEPT when the
    #       letter is a k/m/b unit (rule 6 already handles those).
    #       "Lv. 24Forge" → "Lv. 24 Forge"
    #       "dealing2.45m Damage" → "dealing 2.45m Damage" (lowercase+digit).
    #       Exclusion class covers every letter EXCEPT k, m, b (any case).
    line = re.sub(r"(\d)([ac-jln-zAC-JLN-Z])", r"\1 \2", line)
    line = re.sub(r"([a-z])(\d)", r"\1 \2", line)

    # 7ter. Space after a comma that's glued to the next word:
    #       "stampede,each" → "stampede, each"
    line = re.sub(r",([A-Za-z])", r", \1", line)

    # 8. Whitelist CamelCase → spaced stat names (keeps "Lifesteal" intact).
    for joined, spaced in _STAT_CAMEL_MAP.items():
        line = re.sub(r"\b" + joined + r"\b", spaced, line)

    # 9. Space before parenthetical: "Damage(ranged)" → "Damage (ranged)"
    line = re.sub(r"(\w)\(", r"\1 (", line)

    # 10. Split two passives glued by "+": "Damage+347k" → "Damage +347k"
    line = re.sub(r"([A-Za-z])\+", r"\1 +", line)

    # 11. Generic CamelCase split for item names ("HiggsCollar" → "Higgs Collar").
    #     Applied last so stat whitelist wins on contested cases.
    line = re.sub(r"([a-z])([A-Z])", r"\1 \2", line)

    # 11bis. Strip trailing punctuation noise on stat lines:
    #        "+7.58% Skill Damage*" → "+7.58% Skill Damage"
    if re.match(r"^\s*[+\-]?\s*[\d.]+\s*%", line):
        line = re.sub(r"[\*\.,;:]+\s*$", "", line)

    # 12. Collapse runs of spaces and strip.
    line = re.sub(r"[ \t]+", " ", line).strip()
    return line


# ── Per-line keep/drop decision ─────────────────────────────

def _is_noise_percent(line: str) -> bool:
    """True if `line` is a '+NN% <stat>' line with an unknown stat."""
    m = re.match(r"^[+-]?\s*[\d.]+\s*%\s*(.+)$", line)
    if not m:
        return False
    tail = re.sub(r"\s+", " ", m.group(1)).strip().lower()
    if not tail:
        return True
    # Strip a trailing single punctuation char that OCR sometimes appends
    # (e.g. "Skill Damage*").
    tail = tail.rstrip(" .,;:*")
    for known in _KNOWN_PCT_STATS:
        if tail == known:
            return False
        if tail.startswith(known + " "):
            return False
    return True


def _should_drop(line: str) -> bool:
    if not line:
        return True
    low = line.lower()
    if low in _KEYWORDS_PASSTHROUGH:
        return False
    for pat in _DROP_PATTERNS:
        if pat.match(line):
            return True
    if line.startswith(("+", "-")) or re.match(r"^\s*\d[\d.]*\s*%", line):
        if _is_noise_percent(line):
            return True
    return False


def _canonicalize_keyword(line: str) -> str:
    """If the line is a known keyword (case-insensitive), return its canonical form."""
    return _KEYWORDS_PASSTHROUGH.get(line.lower(), line)


# ── Profile / opponent specific cleanup ─────────────────────

# Any line that is ONLY "Lv. <num>" (no trailing word like "Forge")
# is an equipment/skill-level badge rendered between stats on the
# profile sheet — drop it, it clutters the textbox and the parser
# doesn't use it anyway.
_RE_LEVEL_STANDALONE = re.compile(r"^\s*Lv\.?\s*\d+\s*$", re.IGNORECASE)

# A percent-looking line that's actually corrupted by the OCR:
#   "+2 i 6% Pannodnamano"  →  digits then SPACE then a non-% char.
# A well-formed stat is "+N.NN% Stat Name" — no whitespace between
# the number and the %.
_RE_CORRUPT_PCT = re.compile(r"^\s*[+\-]\s*[\d.]+\s+[^%\s]")

# Strict percent-stat check: the tail must be one of the known
# substats from _KNOWN_PCT_STATS. Used in profile/opponent mode
# to hard-drop anything that wasn't cleanly recognised — the same
# stat will re-appear on the second capture pass.
def _is_known_pct_stat(line: str) -> bool:
    m = re.match(r"^\s*[+\-]\s*[\d.]+\s*%\s*(.+?)\s*$", line)
    if not m:
        return False
    tail = re.sub(r"\s+", " ", m.group(1)).strip().lower().rstrip(" .,;:*")
    if not tail:
        return False
    for known in _KNOWN_PCT_STATS:
        if tail == known or tail.startswith(known + " "):
            return True
    return False


def _is_profile_noise(line: str) -> bool:
    """Extra drop rules for profile/opponent captures only."""
    # Standalone "Lv. 103" (equipment level badge) → drop.
    if _RE_LEVEL_STANDALONE.match(line):
        return True
    # Corrupted percent line (e.g. "+2 i 6% Pannodnamano") → drop,
    # the stat reappears on the next capture pass.
    if _RE_CORRUPT_PCT.match(line):
        return True
    # Any remaining "+NN% <garbage>" is also dropped (stricter than
    # the default _is_noise_percent which leaves malformed forms in).
    if line.startswith(("+", "-")) and "%" in line:
        if not _is_known_pct_stat(line):
            return True
    return False


def _dedupe_preserve_order(lines: List[str]) -> List[str]:
    """Return `lines` with duplicates removed, keeping first occurrence."""
    seen: set = set()
    out: List[str] = []
    for line in lines:
        key = line.strip()
        if key in seen:
            continue
        seen.add(key)
        out.append(line)
    return out


def _stat_rank(line: str) -> int:
    """Canonical rank for a '+NN% <stat>' line. Non-stats return -1."""
    m = re.match(r"^\s*[+\-]\s*[\d.]+\s*%\s*(.+?)\s*$", line)
    if not m:
        return -1
    tail = re.sub(r"\s+", " ", m.group(1)).strip().lower().rstrip(" .,;:*")
    # Match against _STAT_ORDER — longest-prefix wins so "health regen"
    # doesn't collide with the generic "health".
    best = -1
    best_len = -1
    for idx, name in enumerate(_STAT_ORDER):
        if tail == name or tail.startswith(name + " "):
            if len(name) > best_len:
                best = idx
                best_len = len(name)
    return best


def _reorder_profile_stats(lines: List[str]) -> List[str]:
    """Reorder recognised stat lines into canonical game order.

    Non-stat lines keep their relative position; the block of stat
    lines is moved together, placed where the FIRST stat line was,
    and sorted by _stat_rank.
    """
    stat_lines = [(i, l) for i, l in enumerate(lines) if _stat_rank(l) >= 0]
    if len(stat_lines) < 2:
        return lines
    first_stat_idx = stat_lines[0][0]
    non_stats = [(i, l) for i, l in enumerate(lines) if _stat_rank(l) < 0]
    sorted_stats = sorted((l for _, l in stat_lines), key=_stat_rank)
    out: List[str] = []
    inserted = False
    for i, l in non_stats:
        if not inserted and i > first_stat_idx:
            out.extend(sorted_stats)
            inserted = True
        out.append(l)
    if not inserted:
        out.extend(sorted_stats)
    return out


# ── Public entry point ──────────────────────────────────────

def fix_ocr(text: str, context: Optional[str] = None) -> str:
    """Clean up raw OCR text so the parser regexes match.

    Drops obvious noise (player-name artifacts, resource badges,
    corrupted level readouts, garbage percentage stats) and normalizes
    every remaining line to the "paste-from-screenshot" format the
    parser was originally written for.

    `context` (optional) activates zone-specific cleanup:
      - "profile" / "opponent" : drop standalone "Lv. XX" lines
        (equipment-level badges in the stat sheet), drop corrupt
        percent stats (OCR garbage — they re-appear on the next
        capture anyway), dedupe lines coming from the two
        stacked captures, then reorder substats into the in-game
        canonical order (see _STAT_ORDER).
      - other / None : legacy behaviour, no extra cleanup.

    The transform is idempotent: running `fix_ocr(fix_ocr(x, c), c)`
    yields the same result as `fix_ocr(x, c)`.
    """
    if not text:
        return ""

    profile_mode = context in ("profile", "opponent")

    out: List[str] = []
    for raw in text.splitlines():
        line = _normalize_line(raw)
        if _should_drop(line):
            continue
        if profile_mode and _is_profile_noise(line):
            continue
        out.append(_canonicalize_keyword(line))

    if profile_mode:
        out = _dedupe_preserve_order(out)
        out = _reorder_profile_stats(out)

    return "\n".join(out)
