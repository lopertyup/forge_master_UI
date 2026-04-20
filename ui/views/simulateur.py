"""
============================================================
  FORGE MASTER UI — Simulateur de combat
  N_SIMULATIONS simulations avec affichage graphique.
  Callbacks thread-safe (via controller.set_tk_root → after()).
============================================================
"""

from typing import Dict

import customtkinter as ctk

from backend.constants import N_SIMULATIONS
from backend.parser import parser_texte
from backend.stats import finaliser_bases, stats_combat

from ui.theme import (
    C,
    FONT_BIG,
    FONT_BODY,
    FONT_SMALL,
    FONT_SUB,
    FONT_TITLE,
    fmt_nombre,
    rarity_color,
)
from ui.widgets import (
    big_counter,
    build_header,
    skill_icon_grid,
)


class SimulateurView(ctk.CTkFrame):

    def __init__(self, parent, controller, app):
        super().__init__(parent, fg_color=C["bg"], corner_radius=0)
        self.controller  = controller
        self.app         = app
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._adv_profil = None
        self._adv_skills = []
        self._build()

    def _build(self) -> None:
        build_header(self, "Simulateur de combat")

        body = ctk.CTkFrame(self, fg_color=C["bg"], corner_radius=0)
        body.grid(row=1, column=0, sticky="nsew", padx=16, pady=16)
        body.grid_columnconfigure((0, 1), weight=1)
        body.grid_rowconfigure(1, weight=1)

        joueur_card = ctk.CTkFrame(body, fg_color=C["card"], corner_radius=12)
        joueur_card.grid(row=0, column=0, padx=(0, 8), pady=(0, 8), sticky="nsew")
        self._build_joueur_panel(joueur_card)

        adv_outer = ctk.CTkFrame(body, fg_color=C["card"], corner_radius=12)
        adv_outer.grid(row=0, column=1, padx=(8, 0), pady=(0, 8), sticky="nsew")
        adv_outer.grid_rowconfigure(0, weight=1)
        adv_outer.grid_rowconfigure(1, weight=0)
        adv_outer.grid_columnconfigure(0, weight=1)
        self._build_adversaire_panel(adv_outer)

        self.result_frame = ctk.CTkFrame(body, fg_color=C["card"], corner_radius=12)
        self.result_frame.grid(row=1, column=0, columnspan=2,
                               padx=0, pady=(0, 0), sticky="nsew")
        self._build_result_panel(self.result_frame)

    # ── Panneau joueur ────────────────────────────────────────

    def _build_joueur_panel(self, parent: ctk.CTkFrame) -> None:
        ctk.CTkLabel(parent, text="⚔  Votre personnage",
                     font=FONT_SUB, text_color=C["text"]).pack(
            padx=16, pady=(14, 6), anchor="w")

        profil = self.controller.get_profil()
        if not profil:
            ctk.CTkLabel(parent,
                         text="Aucun profil chargé.\nAllez dans Dashboard\npour importer vos stats.",
                         font=FONT_BODY, text_color=C["muted"],
                         justify="center").pack(pady=20)
            return

        stats_f = ctk.CTkFrame(parent, fg_color=C["card_alt"], corner_radius=8)
        stats_f.pack(padx=12, pady=(0, 8), fill="x")
        for label, key in (("HP", "hp_total"), ("ATQ", "attaque_total")):
            row = ctk.CTkFrame(stats_f, fg_color="transparent")
            row.pack(fill="x", padx=12, pady=2)
            ctk.CTkLabel(row, text=label, font=FONT_SMALL,
                         text_color=C["muted"], width=40,
                         anchor="w").pack(side="left")
            ctk.CTkLabel(row, text=fmt_nombre(profil.get(key, 0)),
                         font=FONT_SUB, text_color=C["text"]).pack(
                side="left", padx=8)

        type_atq = profil.get("type_attaque", "?")
        ctk.CTkLabel(stats_f,
                     text=f"Type : {'🏹 Distance' if type_atq == 'distance' else '⚔ Corps à Corps'}",
                     font=FONT_SMALL, text_color=C["muted"]).pack(
            padx=12, pady=(0, 8), anchor="w")

        skills = self.controller.get_skills_actifs()
        if skills:
            sk_f = ctk.CTkFrame(parent, fg_color=C["card_alt"], corner_radius=8)
            sk_f.pack(padx=12, pady=(0, 12), fill="x")
            ctk.CTkLabel(sk_f, text="Skills :", font=FONT_SMALL,
                         text_color=C["muted"]).pack(padx=12, pady=(8, 2),
                                                      anchor="w")
            for code, data in skills:
                color = rarity_color(data.get("rarity", "common"))
                ctk.CTkLabel(sk_f,
                             text=f"  [{code.upper()}] {data.get('name', '?')}",
                             font=FONT_SMALL, text_color=color).pack(
                    padx=12, anchor="w")
            ctk.CTkFrame(sk_f, fg_color="transparent", height=8).pack()

    # ── Panneau adversaire ────────────────────────────────────

    def _build_adversaire_panel(self, parent: ctk.CTkFrame) -> None:
        scroll = ctk.CTkScrollableFrame(parent, fg_color="transparent",
                                         corner_radius=0)
        scroll.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        scroll.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(scroll, text="🎯  Adversaire",
                     font=FONT_SUB, text_color=C["text"]).pack(
            padx=16, pady=(14, 6), anchor="w")

        ctk.CTkLabel(scroll, text="Stats de l'adversaire :",
                     font=FONT_SMALL, text_color=C["muted"]).pack(
            padx=16, anchor="w")

        self.adv_textbox = ctk.CTkTextbox(
            scroll, height=120, font=("Consolas", 11),
            fg_color=C["bg"], text_color=C["text"],
            border_color=C["border"], border_width=1,
        )
        self.adv_textbox.pack(padx=12, pady=(4, 8), fill="x")

        type_f = ctk.CTkFrame(scroll, fg_color="transparent")
        type_f.pack(padx=12, fill="x")
        ctk.CTkLabel(type_f, text="Type :", font=FONT_SMALL,
                     text_color=C["muted"]).pack(side="left")
        self.adv_type = ctk.StringVar(value="distance")
        ctk.CTkRadioButton(type_f, text="🏹 Distance",
                           variable=self.adv_type, value="distance",
                           text_color=C["text"], font=FONT_SMALL).pack(
            side="left", padx=10)
        ctk.CTkRadioButton(type_f, text="⚔ C-à-C",
                           variable=self.adv_type, value="corps_a_corps",
                           text_color=C["text"], font=FONT_SMALL).pack(
            side="left", padx=4)

        ctk.CTkLabel(scroll, text="Skills adversaire :",
                     font=FONT_SMALL, text_color=C["muted"]).pack(
            padx=16, pady=(8, 2), anchor="w")

        tous = self.controller.get_tous_skills()
        self._adv_skill_vars: Dict[str, ctk.BooleanVar] = {
            code: ctk.BooleanVar(value=False) for code in tous
        }

        grid, _btns = skill_icon_grid(
            scroll, tous, self._adv_skill_vars,
            on_toggle=self._toggle_adv_skill,
        )
        grid.pack(padx=12, pady=(0, 4), fill="x")

        self._adv_limit_lbl = ctk.CTkLabel(
            scroll, text="", font=FONT_SMALL, text_color=C["lose"])
        self._adv_limit_lbl.pack(pady=(2, 4))

        ctk.CTkFrame(scroll, fg_color=C["border"], height=1).pack(
            fill="x", padx=12, pady=(0, 4))

        # Bouton fixe hors du scroll
        btn_frame = ctk.CTkFrame(parent, fg_color=C["card"], corner_radius=0)
        btn_frame.grid(row=1, column=0, sticky="ew", padx=0, pady=0)
        btn_frame.grid_columnconfigure(0, weight=1)

        self._lbl_status_adv = ctk.CTkLabel(
            btn_frame, text="", font=FONT_SMALL, text_color=C["lose"])
        self._lbl_status_adv.grid(row=0, column=0, padx=12, pady=(6, 0))

        ctk.CTkButton(
            btn_frame, text=f"▶  Lancer {N_SIMULATIONS} simulations",
            font=FONT_SUB, height=40, corner_radius=8,
            fg_color=C["accent"], hover_color=C["accent_hv"],
            command=self._lancer,
        ).grid(row=1, column=0, padx=12, pady=(4, 12), sticky="ew")

    def _toggle_adv_skill(self, code: str) -> None:
        """Toggle du skill adversaire avec limite à 3."""
        var      = self._adv_skill_vars[code]
        selected = [c for c, v in self._adv_skill_vars.items() if v.get()]
        if not var.get():
            if len(selected) >= 3:
                self._adv_limit_lbl.configure(text="⚠ Maximum 3 skills")
                return
            var.set(True)
        else:
            var.set(False)
        self._adv_limit_lbl.configure(text="")

    # ── Panneau résultats ─────────────────────────────────────

    def _build_result_panel(self, parent: ctk.CTkFrame) -> None:
        parent.grid_columnconfigure((0, 1, 2), weight=1)

        self._lbl_status = ctk.CTkLabel(
            parent,
            text="Remplissez les stats adversaire et lancez la simulation.",
            font=FONT_BODY, text_color=C["muted"],
        )
        self._lbl_status.grid(row=0, column=0, columnspan=3, pady=20)

        total_txt = f"/ {N_SIMULATIONS}"
        self._lbl_win  = big_counter(parent, "WIN",  C["win"],  total_text=total_txt)
        self._lbl_lose = big_counter(parent, "LOSE", C["lose"], total_text=total_txt)
        self._lbl_draw = big_counter(parent, "DRAW", C["draw"], total_text=total_txt)
        self._lbl_win._counter_frame.grid(row=1, column=0, padx=12, pady=8, sticky="ew")
        self._lbl_lose._counter_frame.grid(row=1, column=1, padx=12, pady=8, sticky="ew")
        self._lbl_draw._counter_frame.grid(row=1, column=2, padx=12, pady=8, sticky="ew")

        self._progress = ctk.CTkProgressBar(parent, height=12, corner_radius=6,
                                             progress_color=C["win"])
        self._progress.grid(row=2, column=0, columnspan=3,
                            padx=24, pady=(8, 0), sticky="ew")
        self._progress.set(0)

        self._lbl_verdict = ctk.CTkLabel(
            parent, text="", font=FONT_SUB, text_color=C["text"])
        self._lbl_verdict.grid(row=3, column=0, columnspan=3, pady=(8, 16))

    # ── Logique ───────────────────────────────────────────────

    def _lancer(self) -> None:
        if not self.controller.has_profil():
            self._lbl_status_adv.configure(
                text="⚠ Aucun profil joueur. Allez dans Dashboard.")
            return

        texte = self.adv_textbox.get("1.0", "end").strip()
        if not texte:
            self._lbl_status_adv.configure(text="⚠ Collez les stats de l'adversaire.")
            return

        adv_selected = [c for c, v in self._adv_skill_vars.items() if v.get()]
        if len(adv_selected) > 3:
            self._lbl_status_adv.configure(text="⚠ Maximum 3 skills pour l'adversaire.")
            return

        self._lbl_status_adv.configure(text="")

        adv_stats = parser_texte(texte)
        adv_stats["type_attaque"] = self.adv_type.get()
        adv_stats = finaliser_bases(adv_stats)
        adv_combat = stats_combat(adv_stats)
        adv_skills = self.controller.get_skills_from_codes(adv_selected)

        self._lbl_status.configure(text="⏳ Simulation en cours…",
                                    text_color=C["muted"])
        self._lbl_win.configure(text="…")
        self._lbl_lose.configure(text="…")
        self._lbl_draw.configure(text="…")
        self._progress.set(0)
        self._lbl_verdict.configure(text="")
        self.update_idletasks()

        # Le controller dispatch déjà sur le thread Tk ; pas besoin de after()
        self.controller.simuler(adv_combat, adv_skills, self._afficher_resultats)

    def _afficher_resultats(self, wins: int, loses: int, draws: int) -> None:
        self._lbl_win.configure(text=str(wins))
        self._lbl_lose.configure(text=str(loses))
        self._lbl_draw.configure(text=str(draws))
        win_rate = wins / N_SIMULATIONS if N_SIMULATIONS else 0.0
        self._progress.set(win_rate)
        self._progress.configure(
            progress_color=C["win"] if win_rate >= 0.5 else C["lose"])

        pct = 100.0 / N_SIMULATIONS if N_SIMULATIONS else 0.0
        if wins > loses:
            verdict = f"✅  Vous gagnez {wins * pct:.1f}% du temps"
            color   = C["win"]
        elif loses > wins:
            verdict = f"❌  Vous perdez {loses * pct:.1f}% du temps"
            color   = C["lose"]
        else:
            verdict = f"🤝  Égalité parfaite ({draws * pct:.1f}% draws)"
            color   = C["draw"]

        self._lbl_verdict.configure(text=verdict, text_color=color)
        self._lbl_status.configure(text="Simulation terminée.",
                                    text_color=C["muted"])
