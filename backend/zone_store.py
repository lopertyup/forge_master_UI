"""
============================================================
  FORGE MASTER — Zone store (OCR capture regions)

  Thin business-logic layer around zones.json:

    - load()                 → full dict {zone_key: {captures, bboxes}}
    - get_zone(key)          → single entry (or defaults)
    - set_zone_bboxes(k, bb) → update in-memory + persist to disk
    - reset_zone(key)        → zero out all bboxes for this zone
    - is_zone_configured(..) → True if at least one bbox has non-zero size
    - empty_bbox()           → canonical zero bbox ([0,0,0,0])

  Raw file I/O stays in persistence.py; this module is the
  single point the UI and GameController should touch.
============================================================
"""

from __future__ import annotations

import logging
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .constants import ZONE_DEFAULTS
from .persistence import load_zones, save_zones

log = logging.getLogger(__name__)

# Canonical bbox type: (x1, y1, x2, y2) — screen-absolute pixels.
Bbox = Tuple[int, int, int, int]


def empty_bbox() -> List[int]:
    """Return a fresh zero bbox ([0, 0, 0, 0])."""
    return [0, 0, 0, 0]


def is_bbox_valid(bbox: Sequence[int]) -> bool:
    """A bbox is 'valid' (i.e. actually configured) when it has non-zero area."""
    if not bbox or len(bbox) < 4:
        return False
    x1, y1, x2, y2 = (int(bbox[0]), int(bbox[1]),
                      int(bbox[2]), int(bbox[3]))
    return (x2 > x1) and (y2 > y1)


def _normalize_bbox(bbox: Sequence[int]) -> List[int]:
    """Reorder corners so (x1,y1) is top-left and (x2,y2) bottom-right."""
    if not bbox or len(bbox) < 4:
        return empty_bbox()
    x1, y1, x2, y2 = (int(bbox[0]), int(bbox[1]),
                      int(bbox[2]), int(bbox[3]))
    return [min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)]


def default_captures(zone_key: str) -> int:
    """Number of screen grabs this zone requires (from ZONE_DEFAULTS)."""
    entry = ZONE_DEFAULTS.get(zone_key) or {}
    return max(1, int(entry.get("captures", 1)))


def load() -> Dict[str, Dict]:
    """Alias for persistence.load_zones — single import point for callers."""
    return load_zones()


def get_zone(zone_key: str,
             zones: Optional[Dict[str, Dict]] = None) -> Dict:
    """Return the entry for `zone_key`, falling back to defaults."""
    if zones is None:
        zones = load()
    entry = zones.get(zone_key)
    if not isinstance(entry, dict):
        # Build from defaults if the file was missing this key.
        default = ZONE_DEFAULTS.get(zone_key) or {
            "captures": 1, "bboxes": [empty_bbox()]}
        return {
            "captures": int(default["captures"]),
            "bboxes":   [list(b) for b in default["bboxes"]],
        }
    return {
        "captures": int(entry.get("captures", default_captures(zone_key))),
        "bboxes":   [list(b) for b in (entry.get("bboxes") or [])],
    }


def set_zone_bboxes(zone_key: str,
                    bboxes: Iterable[Sequence[int]],
                    zones: Optional[Dict[str, Dict]] = None) -> Dict[str, Dict]:
    """
    Update the bboxes for `zone_key` and persist to zones.json.

    `captures` is kept in sync with the number of bboxes supplied (padded
    or trimmed if mismatched). Returns the updated full zones dict.
    """
    if zones is None:
        zones = load()

    norm = [_normalize_bbox(b) for b in bboxes]
    if not norm:
        norm = [empty_bbox()]

    default_n = default_captures(zone_key)
    # Honour the schema's expected capture count: pad with empties if the
    # caller sent fewer, trim excess if they sent more.
    if len(norm) < default_n:
        norm = norm + [empty_bbox()] * (default_n - len(norm))
    elif len(norm) > default_n:
        norm = norm[:default_n]

    zones[zone_key] = {"captures": default_n, "bboxes": norm}
    save_zones(zones)
    log.info("zone_store: %s set to %s", zone_key, norm)
    return zones


def reset_zone(zone_key: str,
               zones: Optional[Dict[str, Dict]] = None) -> Dict[str, Dict]:
    """Zero out every bbox for this zone (keeps the capture count)."""
    n = default_captures(zone_key)
    return set_zone_bboxes(zone_key, [empty_bbox() for _ in range(n)],
                           zones=zones)


def is_zone_configured(zone_key: str,
                       zones: Optional[Dict[str, Dict]] = None) -> bool:
    """True iff ALL bboxes for this zone have non-zero area."""
    entry = get_zone(zone_key, zones=zones)
    bboxes = entry.get("bboxes") or []
    if not bboxes:
        return False
    return all(is_bbox_valid(b) for b in bboxes)
