"""
============================================================
  FORGE MASTER UI — Gestion du Mount
  Un seul slot ; nouveau_moi (avec mount) vs ancien_moi.
============================================================
"""

from typing import Dict

import customtkinter as ctk

from ui.theme import C, FONT_SUB, FONT_BODY, MOUNT_ICON
from ui.widgets import (
    build_header,
    build_import_zone,
    build_wld_bars,
    confirmer,
    stats_card,
)
from backend.constants import N_SIMULATIONS


class MountView(ctk.CTkFrame):

    def __init__(self, parent, controller, app):
        super().__init__(parent, fg_color=C["bg"], corner_radius=0)
        self.controller = controller
        self.app        = app
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._build()

    # ── Construction ─────────────────────────────────────────

    def _build(self) -> None:
        build_header(self, f"{MOUNT_ICON}  Gestion du Mount")

        self._scroll = ctk.CTkScrollableFrame(self, fg_color=C["bg"],
                                               corner_radius=0)
        self._scroll.grid(row=1, column=0, sticky="nsew")
        self._scroll.grid_columnconfigure(0, weight=1)

        self._build_mount_card()
        self._build_import()
        self._build_result_zone()

    def _build_mount_card(self) -> None:
        mount = self.controller.get_mount()
        card = stats_card(self._scroll,
                          title=f"{MOUNT_ICON}  Mount actuel",
                          stats=mount,
                          empty_text="(aucun mount enregistré)")
        card.grid(row=0, column=0, padx=16, pady=16, sticky="ew")

    def _build_import(self) -> None:
        card, self._textbox, self._lbl_status = build_import_zone(
            self._scroll,
            title="Tester un nouveau mount",
            hint="Collez les stats du mount depuis le jeu.",
            primary_label="🔬  Simuler le remplacement",
            primary_cmd=self._tester_mount,
            secondary_label="💾  Enregistrer directement",
            secondary_cmd=self._enregistrer_direct,
        )
        card.grid(row=1, column=0, padx=16, pady=(0, 8), sticky="ew")

    def _build_result_zone(self) -> None:
        self._result_outer = ctk.CTkFrame(self._scroll, fg_color="transparent")
        self._result_outer.grid(row=2, column=0, padx=16, pady=(0, 16),
                                sticky="ew")
        self._result_outer.grid_columnconfigure(0, weight=1)

    # ── Actions ──────────────────────────────────────────────

    def _tester_mount(self) -> None:
        if not self.controller.has_profil():
            self._lbl_status.configure(
                text="⚠ Aucun profil joueur. Allez dans Dashboard d'abord.",
                text_color=C["lose"])
            return

        texte = self._textbox.get("1.0", "end").strip()
        if not texte:
            self._lbl_status.configure(text="⚠ Collez les stats du mount.",
                                        text_color=C["lose"])
            return

        nouveau = self.controller.importer_texte_mount(texte)
        for w in self._result_outer.winfo_children():
            w.destroy()

        self._lbl_status.configure(text="⏳ Simulation en cours…",
                                    text_color=C["muted"])
        self.update_idletasks()

        def on_result(w: int, l: int, d: int) -> None:
            self._lbl_status.configure(text="", text_color=C["muted"])
            self._afficher_resultats(w, l, d, nouveau)

        self.controller.tester_mount(nouveau, on_result)

    def _afficher_resultats(self, wins: int, loses: int, draws: int,
                             nouveau_mount: Dict) -> None:
        for w in self._result_outer.winfo_children():
            w.destroy()

        card = ctk.CTkFrame(self._result_outer, fg_color=C["card"],
                             corner_radius=12)
        card.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(card, text="Résultat — Nouveau mount vs Ancien mount",
                     font=FONT_SUB, text_color=C["text"]).pack(
            padx=20, pady=(16, 4), anchor="w")
        ctk.CTkLabel(card,
                     text="Nouveau moi (avec ce mount) vs Ancien moi (avec l'ancien mount).",
                     font=("Segoe UI", 11), text_color=C["muted"]).pack(
            padx=20, pady=(0, 12), anchor="w")

        bars = build_wld_bars(card, wins, loses, draws, total=N_SIMULATIONS)
        bars.pack(fill="x", padx=20, pady=(0, 8))

        if wins > loses:
            verdict_txt = f"✅  Ce mount est meilleur — {100 * wins / N_SIMULATIONS:.0f}% de victoires."
            verdict_col = C["win"]
            show_btn    = True
        elif loses > wins:
            verdict_txt = "❌  Ce mount est moins bon. Gardez l'actuel."
            verdict_col = C["lose"]
            show_btn    = False
        else:
            verdict_txt = "🤝  Égalité — les deux mounts se valent."
            verdict_col = C["draw"]
            show_btn    = False

        ctk.CTkLabel(card, text=verdict_txt, font=FONT_SUB,
                     text_color=verdict_col).pack(
            padx=20, pady=(8, 8 if show_btn else 16))

        if show_btn:
            ctk.CTkButton(
                card, text="💾  Appliquer ce mount",
                font=FONT_BODY, height=36, corner_radius=8,
                fg_color=C["win"], hover_color=C["win_hv"],
                text_color=C["bg"],
                command=lambda m=nouveau_mount: self._appliquer_mount(m),
            ).pack(padx=20, pady=(0, 16), fill="x")

    def _appliquer_mount(self, mount: Dict) -> None:
        if not confirmer(
            self.app, "Confirmer le remplacement",
            "Remplacer le mount actuel par ce nouveau mount ?",
            ok_label="Remplacer", danger=False,
        ):
            return
        self.controller.set_mount(mount)
        self._lbl_status.configure(text="✅ Mount mis à jour !",
                                    text_color=C["win"])
        self.app.refresh_current()

    def _enregistrer_direct(self) -> None:
        texte = self._textbox.get("1.0", "end").strip()
        if not texte:
            self._lbl_status.configure(
                text="⚠ Collez d'abord les stats du mount.",
                text_color=C["lose"])
            return
        if not confirmer(
            self.app, "Enregistrer sans simuler",
            "Enregistrer ce mount sans tester s'il est meilleur que l'actuel ?",
            ok_label="Enregistrer", danger=False,
        ):
            return
        mount = self.controller.importer_texte_mount(texte)
        self.controller.set_mount(mount)
        self._lbl_status.configure(text="✅ Mount enregistré !",
                                    text_color=C["win"])
        self.app.refresh_current()
