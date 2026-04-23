"""
============================================================
  FORGE MASTER — OCR text fixer (extraction-based)

  Philosophy: DO NOT filter noise — extract signal.

  The input is raw OCR output (RapidOCR / PaddleOCR on
  BlueStacks captures). We walk the text line by line,
  recognise ONLY the known tokens (level badges, rarity
  names, flat stats, substats, keywords), normalise each
  one, and rebuild the output in the form the parser expects.
  Everything that matches no pattern is silently dropped.

  Benefits vs the old blacklist approach:
    - No _DROP_PATTERNS to maintain.
    - Immune by default to every new OCR artefact.
    - Double-scan de-duplication comes for free.
    - Canonical stat ordering comes for free.

  Public API:

      fix_ocr(text: str, context: Optional[str] = None) -> str

  Context values: "profile", "opponent", "item", "pet",
  "mount", "skill", or None (generic passthrough).
============================================================
"""

from __future__ import annotations

import re
from typing import Dict, List, NamedTuple, Optional


# ── Known stats (closed list) ────────────────────────────────
_KNOWN_STATS = (
    "Critical Chance", "Critical Damage",
    "Block Chance", "Health Regen",
    "Lifesteal", "Double Chance",
    "Melee Damage", "Ranged Damage",
    "Attack Speed", "Skill Damage", "Skill Cooldown",
    # 1-word names last (shortest match loses to longer prefix).
    "Damage", "Health",
)

# Canonical display order (matches the in-game stat sheet).
_STAT_ORDER = (
    "Critical Chance",
    "Critical Damage",
    "Block Chance",
    "Health Regen",
    "Lifesteal",
    "Double Chance",
    "Damage",
    "Melee Damage",
    "Ranged Damage",
    "Attack Speed",
    "Skill Damage",
    "Skill Cooldown",
    "Health",
)
_STAT_RANK: Dict[str, int] = {name: i for i, name in enumerate(_STAT_ORDER)}

# Longest-first so "Health Regen" wins over "Health" on prefix match.
_KNOWN_STATS_SORTED = tuple(sorted(_KNOWN_STATS, key=lambda s: -len(s)))

# CamelCase → spaced canonical. Applied BEFORE the generic
# "([a-z])([A-Z])" split so 1-word names survive intact.
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

# OCR typos that survive every other normalisation step.
_OCR_TYPOS = {
    "LiFesteal":  "Lifesteal",
    "Lifeste al": "Lifesteal",
    "LifeSteal":  "Lifesteal",
}


# ════════════════════════════════════════════════════════════
#  Step 1 — Low-level normalisation
# ════════════════════════════════════════════════════════════

def _normalize_line(line: str) -> str:
    # Typos
    for wrong, right in _OCR_TYPOS.items():
        line = line.replace(wrong, right)

    # 1. LO / L0 → Lv.
    line = re.sub(r"\b[Ll][O0]\.?\s*(\d)", r"Lv. \1", line)

    # 2. Level prefix variants → "Lv. NN".
    line = re.sub(r"\b[Ll][Vv][.:\']?\s*(\d+)", r"Lv. \1", line)

    # 3. Rarity bracket casing: [interstellar] → [Interstellar].
    line = re.sub(
        r"\[([a-z])([A-Za-z]*)\]",
        lambda m: "[" + m.group(1).upper() + m.group(2) + "]",
        line,
    )

    # 4. Space after bracket glued to a word: "]Higgs" → "] Higgs".
    line = re.sub(r"\](\w)", r"] \1", line)

    # 5. Space between digit+unit and following letter:
    #    "210kDamage" → "210k Damage".
    line = re.sub(r"(\d[kmbKMB])([A-Za-z])", r"\1 \2", line)

    # 6. Space after % glued to a letter.
    line = re.sub(r"(%)([A-Za-z])", r"\1 \2", line)

    # 6bis. Space between digit and following letter (not k/m/b units).
    line = re.sub(r"(\d)([ac-jln-zAC-JLN-Z])", r"\1 \2", line)
    # And between lowercase letter and following digit.
    line = re.sub(r"([a-z])(\d)", r"\1 \2", line)

    # 6ter. Space after comma glued to next word.
    line = re.sub(r",([A-Za-z])", r", \1", line)

    # 7. Space before '(' glued to a word.
    line = re.sub(r"(\w)\(", r"\1 (", line)

    # 8. CamelCase whitelist (before generic split).
    for joined, spaced in _STAT_CAMEL_MAP.items():
        line = re.sub(r"\b" + joined + r"\b", spaced, line)

    # 9. Split passives glued by "+": "Damage+347k" → "Damage +347k".
    line = re.sub(r"([A-Za-z])\+", r"\1 +", line)

    # 10. Generic CamelCase split for item / skill names.
    line = re.sub(r"([a-z])([A-Z])", r"\1 \2", line)

    # 11. Strip trailing punctuation on stat lines.
    if re.match(r"^\s*[+\-]?\s*[\d.]+\s*%", line):
        line = re.sub(r"[\*\.,;:]+\s*$", "", line)

    # 12. Collapse whitespace and strip.
    line = re.sub(r"[ \t]+", " ", line).strip()
    return line


def _split_glued_stats(line: str) -> List[str]:
    """Split on internal '<space>+<digit>' to separate glued stat pairs
    like '+43.4k Base Damage +347k Base Health' into two sub-lines."""
    if not line:
        return []
    parts = re.split(r"\s+(?=\+\d)", line)
    return [p.strip() for p in parts if p.strip()]


# ════════════════════════════════════════════════════════════
#  Step 2 — Pattern extraction
# ════════════════════════════════════════════════════════════

class Token(NamedTuple):
    kind: str
    text: str
    meta: dict


_RE_LV_FORGE  = re.compile(r"^Lv\.\s*(\d+)\s+Forge\s*$", re.IGNORECASE)
_RE_LV        = re.compile(r"^Lv\.\s*(\d+)\s*$", re.IGNORECASE)
_RE_RARITY    = re.compile(r"^\[\s*([A-Z][a-zA-Z]*)\s*\]\s+(.+?)\s*$")
_RE_TOTAL_DMG = re.compile(r"^([\d.]+)\s*([kmb]?)\s+Total\s+Damage\s*$", re.IGNORECASE)
_RE_TOTAL_HP  = re.compile(r"^([\d.]+)\s*([kmb]?)\s+Total\s+Health\s*$", re.IGNORECASE)
_RE_FLAT_DMG  = re.compile(
    r"^([\d.]+)\s*([kmb]?)\s+Damage(?:\s*\(\s*([A-Za-z]+)\s*\))?\s*(?:\d+\s*)?$",
    re.IGNORECASE,
)
_RE_FLAT_HP   = re.compile(r"^([\d.]+)\s*([kmb]?)\s+Health\s*(?:\d+\s*)?$", re.IGNORECASE)
_RE_DEALING   = re.compile(r"^dealing\s+([\d.]+)\s*([kmb]?)\s+Damage\s*(?:to\b.*)?$", re.IGNORECASE)
_RE_BASE_DMG  = re.compile(r"^\+\s*([\d.]+)\s*([kmb]?)\s+Base\s+Damage\s*$", re.IGNORECASE)
_RE_BASE_HP   = re.compile(r"^\+\s*([\d.]+)\s*([kmb]?)\s+Base\s+Health\s*$", re.IGNORECASE)
_RE_SLASH     = re.compile(r"^(\d+)\s*/\s*(\d+)\s*$")
_RE_SUBSTAT   = re.compile(r"^\+\s*([\d.]+)\s*%\s*(.+?)\s*$")
_RE_PASSIVE   = re.compile(r"^Passive\s*:\s*$", re.IGNORECASE)
_RE_NEW       = re.compile(r"^NEW\s*!\s*$", re.IGNORECASE)

# Keywords that are always dropped regardless of context.
_ALWAYS_DROP = {"equipped", "upgrade", "remove", "sell", "equip"}

# Noise patterns that disqualify a line from being kept as skill_text.
_RE_NOISE_SKILL = (
    re.compile(r"^\d+$"),
    re.compile(r"^[A-Za-z]$"),
    re.compile(r"^\d+\s*:\s*\d+$"),
)


def _fmt_unit(num: str, unit: str) -> str:
    return f"{num}{unit.lower()}" if unit else num


def _match_known_stat(tail: str) -> Optional[str]:
    tail_lower = tail.lower().strip().rstrip(" .,;:*")
    for stat in _KNOWN_STATS_SORTED:
        stat_lower = stat.lower()
        if tail_lower == stat_lower or tail_lower.startswith(stat_lower + " "):
            return stat
    return None


def _extract_tokens(lines: List[str], context: Optional[str]) -> List[Token]:
    tokens: List[Token] = []
    seen_rarity  = False
    seen_passive = False
    is_skill     = context == "skill"

    for line in lines:
        if not line:
            continue

        low = line.lower().strip()

        # Always-drop keywords (Equipped, Upgrade, Remove, Sell, Equip).
        if low in _ALWAYS_DROP:
            continue

        # NEW! — dropped everywhere (second item detected by second rarity).
        if _RE_NEW.match(line):
            continue

        # Passive: — skill context only.
        if _RE_PASSIVE.match(line):
            if is_skill:
                tokens.append(Token("passive", "Passive:", {}))
                seen_passive = True
            continue

        # Priority 1: "Lv. NN Forge" — dropped everywhere.
        m = _RE_LV_FORGE.match(line)
        if m:
            continue

        # Priority 2: "Lv. NN" — kept only in pet, mount, skill.
        m = _RE_LV.match(line)
        if m:
            if context in ("pet", "mount", "skill"):
                tokens.append(Token("lv", f"Lv. {m.group(1)}", {"level": int(m.group(1))}))
            continue

        # Priority 3: "[Rarity] Name".
        m = _RE_RARITY.match(line)
        if m:
            rarity = m.group(1).strip()
            name   = m.group(2).strip()
            tokens.append(Token("rarity_name", f"[{rarity}] {name}",
                                {"rarity": rarity, "name": name}))
            seen_rarity = True
            continue

        # Priority 4: "NN.N[kmb] Total Damage".
        m = _RE_TOTAL_DMG.match(line)
        if m:
            tokens.append(Token("total_dmg",
                                f"{_fmt_unit(m.group(1), m.group(2))} Total Damage", {}))
            continue

        # Priority 5: "NN.N[kmb] Total Health".
        m = _RE_TOTAL_HP.match(line)
        if m:
            tokens.append(Token("total_hp",
                                f"{_fmt_unit(m.group(1), m.group(2))} Total Health", {}))
            continue

        # Priority 11: "dealing NN.N[kmb] Damage" (before flat_dmg to avoid clash).
        m = _RE_DEALING.match(line)
        if m:
            tokens.append(Token("dealing",
                                f"dealing {_fmt_unit(m.group(1), m.group(2))} Damage", {}))
            continue

        # Priority 6: "NN.N[kmb] Damage [(ranged)]".
        m = _RE_FLAT_DMG.match(line)
        if m:
            base      = f"{_fmt_unit(m.group(1), m.group(2))} Damage"
            qualifier = m.group(3) or ""
            text      = f"{base} ({qualifier.lower()})" if qualifier else base
            tokens.append(Token("flat_dmg", text,
                                {"attack_type": qualifier.lower() or None}))
            continue

        # Priority 7: "NN.N[kmb] Health".
        m = _RE_FLAT_HP.match(line)
        if m:
            tokens.append(Token("flat_hp",
                                f"{_fmt_unit(m.group(1), m.group(2))} Health", {}))
            continue

        # Priority 9: "+NN.N[kmb] Base Damage".
        m = _RE_BASE_DMG.match(line)
        if m:
            tokens.append(Token("base_dmg",
                                f"+{_fmt_unit(m.group(1), m.group(2))} Base Damage", {}))
            continue

        # Priority 10: "+NN.N[kmb] Base Health".
        m = _RE_BASE_HP.match(line)
        if m:
            tokens.append(Token("base_hp",
                                f"+{_fmt_unit(m.group(1), m.group(2))} Base Health", {}))
            continue

        # Priority 12: "NN/NN" — dropped everywhere.
        m = _RE_SLASH.match(line)
        if m:
            continue

        # Priority 8: "+NN.N% <known stat>".
        m = _RE_SUBSTAT.match(line)
        if m:
            stat = _match_known_stat(m.group(2))
            if stat:
                tokens.append(Token("substat", f"+{m.group(1)}% {stat}",
                                    {"stat": stat, "value": m.group(1)}))
            continue  # unknown stat tail → dropped silently

        # Priority 16: free skill text (skill context, before Passive:).
        if is_skill and seen_rarity and not seen_passive:
            if not any(p.match(line) for p in _RE_NOISE_SKILL):
                tokens.append(Token("skill_text", line, {}))

        # Anything else: silently dropped.

    return tokens


# ════════════════════════════════════════════════════════════
#  Step 3 — Context-specific post-processing
# ════════════════════════════════════════════════════════════

def _dedupe(tokens: List[Token]) -> List[Token]:
    seen: set = set()
    out: List[Token] = []
    for t in tokens:
        if t.text in seen:
            continue
        seen.add(t.text)
        out.append(t)
    return out


# -- profile / opponent -------------------------------------------------

def _post_profile(tokens: List[Token]) -> List[str]:
    kept = [t for t in tokens if t.kind in ("total_dmg", "total_hp", "substat")]
    kept = _dedupe(kept)
    totals   = [t for t in kept if t.kind in ("total_dmg", "total_hp")]
    substats = [t for t in kept if t.kind == "substat"]
    substats.sort(key=lambda t: _STAT_RANK.get(t.meta.get("stat", ""), 99))
    return [t.text for t in totals + substats]


# -- item ---------------------------------------------------------------

def _post_item(tokens: List[Token]) -> List[str]:
    """item layout (per item):
        [Rarity] Name
        flat value(s)
        +substats
    No Lv., no Equipped, no Sell, no Equip, no NEW!
    (all already dropped in _extract_tokens).
    """
    out: List[str] = []
    for t in tokens:
        if t.kind in ("rarity_name", "flat_dmg", "flat_hp", "substat"):
            out.append(t.text)
    return out


# -- pet / mount --------------------------------------------------------

def _post_companion(tokens: List[Token], default_lv: int = 1) -> List[str]:
    """pet/mount: Lv. → [Rarity] Name → flats → substats.
    Synthesises 'Lv. 1' if OCR missed the level badge."""
    out: List[str] = []
    lv     = next((t for t in tokens if t.kind == "lv"), None)
    rarity = next((t for t in tokens if t.kind == "rarity_name"), None)

    if rarity:
        out.append(lv.text if lv else f"Lv. {default_lv}")
        out.append(rarity.text)
    elif lv:
        out.append(lv.text)

    for t in tokens:
        if t.kind in ("flat_dmg", "flat_hp"):
            out.append(t.text)
    for t in tokens:
        if t.kind == "substat":
            out.append(t.text)

    return out


# -- skill --------------------------------------------------------------

def _post_skill(tokens: List[Token]) -> List[str]:
    """skill layout:
        Lv. NN
        [Rarity] Name
        <free description lines>
        dealing NN.N[kmb] Damage
        Passive:
        +Base Damage +Base Health   (combined on one line)
    """
    out: List[str] = []

    lv = next((t for t in tokens if t.kind == "lv"), None)
    if lv:
        out.append(lv.text)

    rarity = next((t for t in tokens if t.kind == "rarity_name"), None)
    if rarity:
        out.append(rarity.text)

    for t in tokens:
        if t.kind == "skill_text":
            out.append(t.text)

    for t in tokens:
        if t.kind == "dealing":
            out.append(t.text)

    passive = next((t for t in tokens if t.kind == "passive"), None)
    if passive:
        out.append(passive.text)

    base_d = next((t for t in tokens if t.kind == "base_dmg"), None)
    base_h = next((t for t in tokens if t.kind == "base_hp"),  None)
    if base_d and base_h:
        out.append(f"{base_d.text} {base_h.text}")
    elif base_d:
        out.append(base_d.text)
    elif base_h:
        out.append(base_h.text)

    return out


# -- default (no context) -----------------------------------------------

def _post_default(tokens: List[Token]) -> List[str]:
    """No reordering — emit tokens in original order.
    Recombines adjacent Base Damage / Base Health onto one line."""
    out: List[str] = []
    i = 0
    while i < len(tokens):
        t = tokens[i]
        if (t.kind == "base_dmg"
                and i + 1 < len(tokens)
                and tokens[i+1].kind == "base_hp"):
            out.append(f"{t.text} {tokens[i+1].text}")
            i += 2
            continue
        out.append(t.text)
        i += 1
    return out


# ════════════════════════════════════════════════════════════
#  Public entry point
# ════════════════════════════════════════════════════════════

def fix_ocr(text: str, context: Optional[str] = None) -> str:
    """Extract known tokens from raw OCR output, reformat per context.

    `context` selects the post-processing strategy:
      - "profile" / "opponent" : keep only Total Damage/Health + known
        substats, dedupe, reorder substats into canonical in-game order.
      - "item"                 : [Rarity] Name → flats → substats,
        repeated for each item. No level, no UI keywords.
      - "pet" / "mount"        : Lv. → [Rarity] Name → flats → substats.
        Synthesises "Lv. 1" if OCR missed the level badge.
      - "skill"                : Lv. → [Rarity] Name → description →
        dealing → Passive: → +Base Damage +Base Health.
      - None / other           : generic passthrough (original order).

    The transform is idempotent on well-formed input.
    """
    if not text:
        return ""

    # Step 1: normalise each raw line, then split glued stat pairs.
    normalised: List[str] = []
    for raw in text.splitlines():
        line = _normalize_line(raw)
        normalised.extend(_split_glued_stats(line))

    # Step 2: extract typed tokens.
    tokens = _extract_tokens(normalised, context)

    # Step 3: context-specific post-processing.
    if context in ("profile", "opponent"):
        out_lines = _post_profile(tokens)
    elif context == "item":
        out_lines = _post_item(tokens)
    elif context in ("pet", "mount"):
        out_lines = _post_companion(tokens, default_lv=1)
    elif context == "skill":
        out_lines = _post_skill(tokens)
    else:
        out_lines = _post_default(tokens)

    return "\n".join(out_lines)