"""
============================================================
  FORGE MASTER UI — Comparateur d'équipements
  Disposition : texte à gauche | ancien/nouveau empilés à droite
  Simulation auto (debounce 600 ms) dès détection de « NEW! ».
============================================================
"""

from typing import Dict

import customtkinter as ctk

from backend.constants import N_SIMULATIONS
from backend.stats import stats_combat

from ui.theme import (
    C,
    FONT_BIG,
    FONT_BODY,
    FONT_MONO,
    FONT_MONO_S,
    FONT_SMALL,
    FONT_SUB,
    fmt_nombre,
)
from ui.widgets import build_header, confirmer


# Stats affichables sur un équipement (ordre d'affichage)
_STAT_ROWS = [
    ("hp_flat",         "Health (flat)",  True),
    ("damage_flat",     "Damage (flat)",  True),
    ("health_pct",      "Health %",       False),
    ("damage_pct",      "Damage %",       False),
    ("melee_pct",       "Melee %",        False),
    ("ranged_pct",      "Ranged %",       False),
    ("taux_crit",       "Crit Chance",    False),
    ("degat_crit",      "Crit Damage",    False),
    ("health_regen",    "Health Regen",   False),
    ("lifesteal",       "Lifesteal",      False),
    ("double_chance",   "Double Chance",  False),
    ("vitesse_attaque", "Attack Speed",   False),
    ("skill_damage",    "Skill Damage",   False),
    ("skill_cooldown",  "Skill Cooldown", False),
    ("chance_blocage",  "Block Chance",   False),
]


class EquipementsView(ctk.CTkFrame):

    def __init__(self, parent, controller, app):
        super().__init__(parent, fg_color=C["bg"], corner_radius=0)
        self.controller        = controller
        self.app               = app
        self._profil_nouveau   = None
        self._after_id         = None  # debounce auto-analyse
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._build()

    # ── Construction ─────────────────────────────────────────

    def _build(self) -> None:
        build_header(self, "Comparateur d'équipements")

        body = ctk.CTkFrame(self, fg_color=C["bg"], corner_radius=0)
        body.grid(row=1, column=0, sticky="nsew", padx=16, pady=12)
        body.grid_columnconfigure(0, weight=2)   # colonne texte
        body.grid_columnconfigure(1, weight=3)   # colonne équipements
        body.grid_rowconfigure(0, weight=1)
        body.grid_rowconfigure(1, weight=0)

        # ── Gauche : saisie ──────────────────────────────────
        left = ctk.CTkFrame(body, fg_color=C["card"], corner_radius=12)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=(0, 8))
        left.grid_columnconfigure(0, weight=1)
        left.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(left, text="Coller le texte ici",
                     font=FONT_SUB, text_color=C["text"]).grid(
            row=0, column=0, padx=16, pady=(14, 4), sticky="w")

        self.text_box = ctk.CTkTextbox(
            left, font=FONT_MONO_S,
            fg_color=C["bg"], text_color=C["text"],
            border_color=C["border"], border_width=1,
        )
        self.text_box.grid(row=1, column=0, padx=12, pady=(0, 8), sticky="nsew")
        self.text_box.bind("<KeyRelease>", self._on_text_change)

        self._lbl_err = ctk.CTkLabel(left, text="", font=FONT_SMALL,
                                      text_color=C["lose"], wraplength=260)
        self._lbl_err.grid(row=2, column=0, padx=12, pady=(0, 4))

        self._lbl_status = ctk.CTkLabel(left, text="En attente du texte…",
                                         font=FONT_SMALL, text_color=C["muted"],
                                         wraplength=260)
        self._lbl_status.grid(row=3, column=0, padx=12, pady=(0, 12))

        # ── Droite : ancien + nouveau ────────────────────────
        right = ctk.CTkFrame(body, fg_color="transparent", corner_radius=0)
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 0), pady=(0, 8))
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure((0, 1), weight=1)

        self.card_ancien = ctk.CTkFrame(right, fg_color=C["card"],
                                         corner_radius=12)
        self.card_ancien.grid(row=0, column=0, sticky="nsew", pady=(0, 6))
        self.card_ancien.grid_columnconfigure(0, weight=1)
        self._lbl_titre_ancien = ctk.CTkLabel(
            self.card_ancien, text="Équipement actuel",
            font=FONT_SUB, text_color=C["muted"])
        self._lbl_titre_ancien.pack(padx=16, pady=(12, 4), anchor="w")
        self._inner_ancien = ctk.CTkScrollableFrame(
            self.card_ancien, fg_color="transparent", height=120)
        self._inner_ancien.pack(fill="both", expand=True, padx=8, pady=(0, 10))

        self.card_nouveau = ctk.CTkFrame(right, fg_color=C["card"],
                                          corner_radius=12)
        self.card_nouveau.grid(row=1, column=0, sticky="nsew", pady=(6, 0))
        self.card_nouveau.grid_columnconfigure(0, weight=1)
        self._lbl_titre_nouveau = ctk.CTkLabel(
            self.card_nouveau, text="Nouvel équipement",
            font=FONT_SUB, text_color=C["accent"])
        self._lbl_titre_nouveau.pack(padx=16, pady=(12, 4), anchor="w")
        self._inner_nouveau = ctk.CTkScrollableFrame(
            self.card_nouveau, fg_color="transparent", height=120)
        self._inner_nouveau.pack(fill="both", expand=True, padx=8, pady=(0, 10))

        # ── Bas : résultats ──────────────────────────────────
        self.bottom = ctk.CTkFrame(body, fg_color=C["card"], corner_radius=12)
        self.bottom.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        self.bottom.grid_columnconfigure((0, 1, 2), weight=1)
        self._build_bottom_empty()

    def _build_bottom_empty(self) -> None:
        for w in self.bottom.winfo_children():
            w.destroy()
        ctk.CTkLabel(self.bottom,
                     text="Les résultats de simulation apparaîtront ici.",
                     font=FONT_SMALL, text_color=C["muted"]).pack(pady=18)

    # ── Auto-analyse (debounce 600 ms) ───────────────────────

    def _on_text_change(self, _event=None) -> None:
        if self._after_id:
            self.after_cancel(self._after_id)
        texte = self.text_box.get("1.0", "end").strip()
        if "NEW!" in texte.upper():
            self._after_id = self.after(600, self._analyser)
        else:
            self._lbl_status.configure(
                text="En attente de « NEW! » dans le texte…")
            self._lbl_err.configure(text="")

    # ── Analyse + simulation ─────────────────────────────────

    def _analyser(self) -> None:
        self._after_id = None

        if not self.controller.has_profil():
            self._lbl_err.configure(
                text="⚠ Aucun profil joueur. Allez dans Dashboard d'abord.")
            return

        texte  = self.text_box.get("1.0", "end").strip()
        result = self.controller.comparer_equipement(texte)
        if result is None:
            self._lbl_err.configure(
                text="⚠ Texte invalide : assurez-vous que « NEW! » est présent.")
            return

        self._lbl_err.configure(text="")
        eq_ancien, eq_nouveau, profil_nouveau = result
        self._profil_nouveau = profil_nouveau

        self._render_eq(self._inner_ancien, eq_ancien)
        self._render_eq(self._inner_nouveau, eq_nouveau)

        lbl_a = "Équipement actuel"
        lbl_n = "Nouvel équipement"
        t_anc = eq_ancien.get("type_attaque")
        t_nv  = eq_nouveau.get("type_attaque")
        if t_anc:
            lbl_a += f"  {'🏹 Distance' if t_anc == 'distance' else '⚔ Mêlée'}"
        if t_nv:
            lbl_n += f"  {'🏹 Distance' if t_nv == 'distance' else '⚔ Mêlée'}"
        self._lbl_titre_ancien.configure(text=lbl_a)
        self._lbl_titre_nouveau.configure(text=lbl_n)

        self._lbl_status.configure(text="⏳ Simulation en cours…")
        self._build_bottom_loading()

        se_ancien = stats_combat(self.controller.get_profil())
        skills    = self.controller.get_skills_actifs()

        self.controller.simuler(
            se_ancien, skills, self._on_sim_done,
            profil_override=profil_nouveau,
            skills_override=skills,
        )

    def _build_bottom_loading(self) -> None:
        for w in self.bottom.winfo_children():
            w.destroy()
        ctk.CTkLabel(
            self.bottom,
            text=f"⏳ Simulation en cours ({N_SIMULATIONS} combats)…",
            font=FONT_BODY, text_color=C["muted"]).pack(pady=18)

    def _on_sim_done(self, wins: int, loses: int, draws: int) -> None:
        self._lbl_status.configure(text="✅ Analyse terminée.")
        self._afficher_resultats(wins, loses, draws)

    # ── Rendu équipement ─────────────────────────────────────

    def _render_eq(self, parent: ctk.CTkScrollableFrame, eq: Dict) -> None:
        for w in parent.winfo_children():
            w.destroy()

        any_shown = False
        for i, (key, label, is_flat) in enumerate(_STAT_ROWS):
            val = eq.get(key, 0.0)
            if not val:
                continue
            any_shown = True
            row_f = ctk.CTkFrame(
                parent,
                fg_color=C["card_alt"] if i % 2 == 0 else C["card"],
                corner_radius=4,
            )
            row_f.pack(padx=4, pady=1, fill="x")
            row_f.grid_columnconfigure(1, weight=1)
            ctk.CTkLabel(row_f, text=label, font=FONT_SMALL,
                         text_color=C["muted"], anchor="w").grid(
                row=0, column=0, padx=10, pady=4, sticky="w")
            val_str = fmt_nombre(val) if is_flat else f"+{val}%"
            ctk.CTkLabel(row_f, text=val_str, font=FONT_MONO,
                         text_color=C["text"], anchor="e").grid(
                row=0, column=1, padx=10, pady=4, sticky="e")

        if not any_shown:
            ctk.CTkLabel(parent, text="Aucune stat détectée",
                         font=FONT_SMALL, text_color=C["muted"]).pack(pady=10)

    # ── Rendu résultats ──────────────────────────────────────

    def _afficher_resultats(self, wins: int, loses: int, draws: int) -> None:
        for w in self.bottom.winfo_children():
            w.destroy()

        total = wins + loses + draws or 1
        pct   = 100.0 / total

        # Compteurs WIN / LOSE / DRAW
        for col, (label, val, color) in enumerate([
            ("WIN",  wins,  C["win"]),
            ("LOSE", loses, C["lose"]),
            ("DRAW", draws, C["draw"]),
        ]):
            f = ctk.CTkFrame(self.bottom, fg_color=C["card_alt"],
                              corner_radius=10)
            f.grid(row=0, column=col, padx=10, pady=(12, 6), sticky="ew")
            ctk.CTkLabel(f, text=label, font=FONT_SMALL,
                         text_color=C["muted"]).pack(pady=(6, 0))
            ctk.CTkLabel(f, text=str(val), font=FONT_BIG,
                         text_color=color).pack()
            ctk.CTkLabel(f, text=f"{val * pct:.1f}%", font=FONT_SMALL,
                         text_color=C["muted"]).pack(pady=(0, 6))

        bar = ctk.CTkProgressBar(
            self.bottom, height=8, corner_radius=4,
            progress_color=C["win"] if wins >= loses else C["lose"])
        bar.grid(row=1, column=0, columnspan=3, padx=16, pady=(0, 6),
                  sticky="ew")
        bar.set(wins / total)

        # Verdict
        amelioration = wins > loses
        if amelioration:
            verdict       = f"✅  Meilleur équipement ! ({wins * pct:.1f}% WIN)"
            verdict_color = C["win"]
        elif loses > wins:
            verdict       = f"❌  Moins bon équipement. ({loses * pct:.1f}% LOSE)"
            verdict_color = C["lose"]
        else:
            verdict       = "🤝  Équivalents."
            verdict_color = C["draw"]

        ctk.CTkLabel(self.bottom, text=verdict, font=FONT_SUB,
                     text_color=verdict_color).grid(
            row=2, column=0, columnspan=3, padx=16, pady=(0, 8))

        # Boutons
        btn_frame = ctk.CTkFrame(self.bottom, fg_color="transparent")
        btn_frame.grid(row=3, column=0, columnspan=3, padx=16, pady=(0, 12),
                        sticky="ew")
        btn_frame.grid_columnconfigure((0, 1), weight=1)

        if amelioration:
            ctk.CTkButton(
                btn_frame, text="💾  Appliquer le nouvel équipement",
                font=FONT_BODY, height=36, corner_radius=8,
                fg_color=C["win"], hover_color=C["win_hv"],
                text_color=C["bg"],
                command=self._appliquer,
            ).grid(row=0, column=0, padx=(0, 6), sticky="ew")

            ctk.CTkButton(
                btn_frame, text="✖  Ne pas appliquer",
                font=FONT_BODY, height=36, corner_radius=8,
                fg_color=C["lose"], hover_color=C["lose_hv"],
                text_color=C["text"],
                command=self._clear,
            ).grid(row=0, column=1, padx=(6, 0), sticky="ew")
        else:
            ctk.CTkButton(
                btn_frame, text="💾  Appliquer quand même",
                font=FONT_BODY, height=36, corner_radius=8,
                fg_color=C["lose"], hover_color=C["lose_hv"],
                text_color=C["text"],
                command=self._appliquer_quand_meme,
            ).grid(row=0, column=0, padx=(0, 6), sticky="ew")

            ctk.CTkButton(
                btn_frame, text="✔  Garder l'équipement actuel",
                font=FONT_BODY, height=36, corner_radius=8,
                fg_color=C["win"], hover_color=C["win_hv"],
                text_color=C["bg"],
                command=self._clear,
            ).grid(row=0, column=1, padx=(6, 0), sticky="ew")

    # ── Actions ──────────────────────────────────────────────

    def _appliquer(self) -> None:
        if self._profil_nouveau:
            self.controller.appliquer_equipement(self._profil_nouveau)
            self.app.refresh_current()
        self._clear()

    def _appliquer_quand_meme(self) -> None:
        """Applique un équipement moins bon — demande confirmation."""
        if not confirmer(
            self.app, "Appliquer un équipement moins bon",
            "Les simulations indiquent que ce nouvel équipement est moins performant.\n\n"
            "Voulez-vous vraiment remplacer votre équipement actuel ?",
            ok_label="Appliquer quand même",
            cancel_label="Annuler",
            danger=True,
        ):
            return
        self._appliquer()

    def _clear(self) -> None:
        self.text_box.delete("1.0", "end")
        self._profil_nouveau = None
        self._lbl_err.configure(text="")
        self._lbl_status.configure(text="En attente du texte…")
        self._render_eq(self._inner_ancien, {})
        self._render_eq(self._inner_nouveau, {})
        self._build_bottom_empty()
