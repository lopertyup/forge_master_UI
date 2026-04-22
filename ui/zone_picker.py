"""
============================================================
  FORGE MASTER UI — Zone picker
  Fullscreen transparent overlay that lets the user drag a
  rectangle on top of BlueStacks (or any other window). The
  result is returned as (x1, y1, x2, y2) screen-absolute
  pixels via a callback.

  Usage:
      ZonePicker(parent=root, hint="Trace the profile zone",
                 on_done=lambda bbox: print(bbox))

  Callback receives None if the user pressed Escape (cancel)
  or released without dragging a valid rectangle.
============================================================
"""

from __future__ import annotations

import logging
from typing import Callable, Optional, Tuple

import tkinter as tk

log = logging.getLogger(__name__)

Bbox    = Tuple[int, int, int, int]
DoneCb  = Callable[[Optional[Bbox]], None]

# Visual settings
_OVERLAY_ALPHA       = 0.30    # 0 = fully transparent, 1 = opaque
_OVERLAY_BG          = "#000000"
_RECT_OUTLINE        = "#FF3B3B"
_RECT_OUTLINE_WIDTH  = 2
_RECT_FILL_STIPPLE   = "gray25"  # semi-transparent red fill
_RECT_FILL_COLOR     = "#FF3B3B"
_HINT_FONT           = ("Segoe UI", 18, "bold")
_HINT_BG             = "#0B0F17"
_HINT_FG             = "#F2F2F7"
_HINT_PADX           = 20
_HINT_PADY           = 10
_MIN_SIZE            = 8  # a drag smaller than this is treated as "cancel"


class ZonePicker(tk.Toplevel):
    """Transparent overlay for rectangular region selection.

    By default the overlay covers the entire screen, but passing
    `region=(x, y, w, h)` restricts it to a specific rectangle
    (useful to overlay only BlueStacks while keeping Forge Master
    visible alongside). Coordinates returned via `on_done` are
    always SCREEN-absolute regardless of the overlay's origin.
    """

    def __init__(self, parent: tk.Misc,
                 hint: str = "Click-drag to select a zone (Esc to cancel)",
                 on_done: Optional[DoneCb] = None,
                 region: Optional[Tuple[int, int, int, int]] = None) -> None:
        super().__init__(parent)
        self._on_done = on_done
        self._done_called = False

        # Borderless, always on top, semi-transparent.
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        try:
            self.attributes("-alpha", _OVERLAY_ALPHA)
        except tk.TclError:
            pass  # Alpha is not supported on every WM — not fatal.

        # Region (x, y, w, h). Defaults to fullscreen if not provided.
        if region is None:
            x = 0
            y = 0
            w = self.winfo_screenwidth()
            h = self.winfo_screenheight()
        else:
            x, y, w, h = region
        self._origin = (int(x), int(y))
        self.geometry(f"{int(w)}x{int(h)}+{int(x)}+{int(y)}")
        self.configure(bg=_OVERLAY_BG)

        # Canvas fills the whole overlay.
        self.canvas = tk.Canvas(
            self, bg=_OVERLAY_BG, highlightthickness=0, cursor="crosshair",
        )
        self.canvas.pack(fill="both", expand=True)

        # Hint banner at the top of the overlay (centered on the overlay,
        # not the screen — overlay may not span full width).
        self._hint_id = self.canvas.create_text(
            int(w) // 2, 40,
            text=hint, font=_HINT_FONT, fill=_HINT_FG,
        )
        # Hint background rectangle (drawn behind the text).
        bbox = self.canvas.bbox(self._hint_id)
        if bbox:
            x1, y1, x2, y2 = bbox
            self.canvas.create_rectangle(
                x1 - _HINT_PADX, y1 - _HINT_PADY,
                x2 + _HINT_PADX, y2 + _HINT_PADY,
                fill=_HINT_BG, outline=_HINT_FG, width=1,
            )
            # Redraw the text on top of the background.
            self.canvas.tag_raise(self._hint_id)

        # Event state
        self._start_x: Optional[int] = None
        self._start_y: Optional[int] = None
        self._rect_id: Optional[int] = None
        self._size_id: Optional[int] = None

        # Bindings
        self.canvas.bind("<ButtonPress-1>",   self._on_press)
        self.canvas.bind("<B1-Motion>",       self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Escape>",                 self._on_cancel)
        self.bind("<KeyPress-q>",             self._on_cancel)

        # Grab focus so key bindings work.
        self.focus_force()
        try:
            self.grab_set()
        except tk.TclError:
            pass

    # ── Event handlers ───────────────────────────────────────

    def _on_press(self, ev: tk.Event) -> None:
        self._start_x = ev.x_root
        self._start_y = ev.y_root
        # Draw initial 0×0 rectangle in canvas-local coords (which match
        # screen coords since the overlay is at +0+0 fullscreen).
        if self._rect_id is not None:
            self.canvas.delete(self._rect_id)
        self._rect_id = self.canvas.create_rectangle(
            ev.x, ev.y, ev.x, ev.y,
            outline=_RECT_OUTLINE, width=_RECT_OUTLINE_WIDTH,
            fill=_RECT_FILL_COLOR, stipple=_RECT_FILL_STIPPLE,
        )

    def _on_drag(self, ev: tk.Event) -> None:
        if self._start_x is None or self._rect_id is None:
            return
        # Update rectangle (canvas-local coords).
        x0 = self._start_x - self.winfo_rootx()
        y0 = self._start_y - self.winfo_rooty()
        self.canvas.coords(self._rect_id, x0, y0, ev.x, ev.y)
        # Live size indicator near the cursor.
        w = abs(ev.x_root - self._start_x)
        h = abs(ev.y_root - self._start_y)
        text = f"{w} × {h}"
        if self._size_id is None:
            self._size_id = self.canvas.create_text(
                ev.x + 12, ev.y + 12, text=text,
                font=("Segoe UI", 12, "bold"), fill=_HINT_FG, anchor="nw",
            )
        else:
            self.canvas.coords(self._size_id, ev.x + 12, ev.y + 12)
            self.canvas.itemconfigure(self._size_id, text=text)

    def _on_release(self, ev: tk.Event) -> None:
        if self._start_x is None or self._start_y is None:
            return self._finish(None)
        x1 = min(self._start_x, ev.x_root)
        y1 = min(self._start_y, ev.y_root)
        x2 = max(self._start_x, ev.x_root)
        y2 = max(self._start_y, ev.y_root)
        if (x2 - x1) < _MIN_SIZE or (y2 - y1) < _MIN_SIZE:
            # Treat a click-without-drag as a cancel so the user can retry.
            return self._finish(None)
        self._finish((int(x1), int(y1), int(x2), int(y2)))

    def _on_cancel(self, _ev: Optional[tk.Event] = None) -> None:
        self._finish(None)

    def _finish(self, bbox: Optional[Bbox]) -> None:
        if self._done_called:
            return
        self._done_called = True
        try:
            self.grab_release()
        except tk.TclError:
            pass
        try:
            self.destroy()
        except tk.TclError:
            pass
        if self._on_done is not None:
            try:
                self._on_done(bbox)
            except Exception:
                log.exception("ZonePicker on_done callback raised")
