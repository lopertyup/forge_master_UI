"""
============================================================
  FORGE MASTER UI — Gestion des Pets
  3 slots (PET1, PET2, PET3). Teste le nouveau pet contre
  chaque ancien pour trouver le meilleur slot à remplacer.
============================================================
"""

from typing import Dict, Tuple

import customtkinter as ctk

from ui.theme import (
    C,
    FONT_BODY,
    FONT_SMALL,
    FONT_SUB,
    FONT_TINY,
    PET_ICONS,
)
from ui.widgets import (
    build_header,
    build_import_zone,
    build_wld_bars,
    confirmer,
    stats_card,
)
from backend.constants import N_SIMULATIONS

_SLOTS = ("PET1", "PET2", "PET3")


class PetsView(ctk.CTkFrame):

    def __init__(self, parent, controller, app):
        super().__init__(parent, fg_color=C["bg"], corner_radius=0)
        self.controller = controller
        self.app        = app
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._build()

    # ── Construction ─────────────────────────────────────────

    def _build(self) -> None:
        build_header(self, "Gestion des Pets")

        self._scroll = ctk.CTkScrollableFrame(self, fg_color=C["bg"],
                                               corner_radius=0)
        self._scroll.grid(row=1, column=0, sticky="nsew")
        self._scroll.grid_columnconfigure(0, weight=1)

        self._build_pets_cards()
        self._build_import()
        self._build_result_zone()

    def _build_pets_cards(self) -> None:
        pets_frame = ctk.CTkFrame(self._scroll, fg_color="transparent")
        pets_frame.grid(row=0, column=0, padx=16, pady=16, sticky="ew")
        pets_frame.grid_columnconfigure((0, 1, 2), weight=1)

        pets = self.controller.get_pets()
        for col, nom in enumerate(_SLOTS):
            icon = PET_ICONS.get(nom, "🐾")
            card = stats_card(pets_frame,
                              title=f"{icon}  {nom}",
                              stats=pets.get(nom, {}))
            card.grid(row=0, column=col, padx=6, pady=0, sticky="nsew")

    def _build_import(self) -> None:
        card, self._textbox, self._lbl_status = build_import_zone(
            self._scroll,
            title="Tester un nouveau pet",
            hint="Collez les stats du pet depuis le jeu.",
            primary_label="🔬  Simuler le remplacement",
            primary_cmd=self._tester_pet,
            secondary_label="✏  Modifier directement un slot",
            secondary_cmd=self._modifier_direct,
        )
        card.grid(row=1, column=0, padx=16, pady=(0, 8), sticky="ew")

    def _build_result_zone(self) -> None:
        self._result_outer = ctk.CTkFrame(self._scroll, fg_color="transparent")
        self._result_outer.grid(row=2, column=0, padx=16, pady=(0, 16),
                                sticky="ew")
        self._result_outer.grid_columnconfigure(0, weight=1)

    # ── Actions ──────────────────────────────────────────────

    def _tester_pet(self) -> None:
        if not self.controller.has_profil():
            self._lbl_status.configure(
                text="⚠ Aucun profil joueur. Allez dans Dashboard d'abord.",
                text_color=C["lose"])
            return

        texte = self._textbox.get("1.0", "end").strip()
        if not texte:
            self._lbl_status.configure(text="⚠ Collez les stats du pet.",
                                        text_color=C["lose"])
            return

        nouveau_pet = self.controller.importer_texte_pet(texte)
        for w in self._result_outer.winfo_children():
            w.destroy()

        self._lbl_status.configure(text="⏳ Simulation en cours…",
                                    text_color=C["muted"])
        self.update_idletasks()

        def on_result(resultats: Dict[str, Tuple[int, int, int]]) -> None:
            self._lbl_status.configure(text="", text_color=C["muted"])
            self._afficher_resultats(resultats, nouveau_pet)

        self.controller.tester_pet(nouveau_pet, on_result)

    def _afficher_resultats(self, resultats: Dict[str, Tuple[int, int, int]],
                             nouveau_pet: Dict) -> None:
        for w in self._result_outer.winfo_children():
            w.destroy()

        if not resultats:
            return

        titre = ctk.CTkFrame(self._result_outer, fg_color=C["card"],
                              corner_radius=12)
        titre.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(titre, text="Résultats — quel slot remplacer ?",
                     font=FONT_SUB, text_color=C["text"]).pack(
            padx=20, pady=(14, 4), anchor="w")
        ctk.CTkLabel(titre,
                     text="Nouveau moi (avec ce pet) vs Ancien moi (avec l'ancien pet dans ce slot).",
                     font=FONT_SMALL, text_color=C["muted"]).pack(
            padx=20, pady=(0, 12), anchor="w")

        meilleur = max(resultats, key=lambda k: resultats[k][0])
        wins_max, loses_max, _ = resultats[meilleur]

        cards = ctk.CTkFrame(self._result_outer, fg_color="transparent")
        cards.pack(fill="x", pady=(0, 8))
        cards.grid_columnconfigure((0, 1, 2), weight=1)

        for col, nom in enumerate(_SLOTS):
            wins, loses, draws = resultats[nom]
            is_best = (nom == meilleur and wins > loses)

            card = ctk.CTkFrame(
                cards,
                fg_color=C["selected"] if is_best else C["card"],
                corner_radius=12,
                border_width=2 if is_best else 0,
                border_color=C["win"] if is_best else C["card"],
            )
            card.grid(row=0, column=col, padx=6, pady=0, sticky="nsew")

            icon = PET_ICONS.get(nom, "🐾")
            ctk.CTkLabel(card, text=f"{icon} Remplacer {nom}",
                         font=FONT_SUB,
                         text_color=C["win"] if is_best else C["text"]).pack(
                padx=16, pady=(14, 2))

            if is_best:
                ctk.CTkLabel(card, text="★ MEILLEURE OPTION",
                             font=FONT_TINY, text_color=C["win"]).pack()

            bars = build_wld_bars(card, wins, loses, draws,
                                   total=N_SIMULATIONS, compact=True,
                                   bar_height=8)
            bars.pack(fill="x", padx=12, pady=(4, 2))

            if wins > loses:
                v_txt = f"✅ +{100 * wins / N_SIMULATIONS:.0f}% WIN"
                v_col = C["win"]
            elif loses > wins:
                v_txt = f"❌ {100 * loses / N_SIMULATIONS:.0f}% LOSE"
                v_col = C["lose"]
            else:
                v_txt = "🤝 Égal"
                v_col = C["draw"]
            ctk.CTkLabel(card, text=v_txt, font=FONT_SMALL,
                         text_color=v_col).pack(pady=(4, 4))

            ctk.CTkButton(
                card, text=f"Remplacer {nom}",
                font=FONT_SMALL, height=32, corner_radius=6,
                fg_color=C["win"] if is_best else C["border"],
                hover_color=C["win_hv"] if is_best else C["border_hl"],
                text_color=C["bg"] if is_best else C["text"],
                command=lambda n=nom, p=nouveau_pet: self._remplacer_pet(n, p),
            ).pack(padx=12, pady=(0, 14), fill="x")

        reco = ctk.CTkFrame(self._result_outer, fg_color=C["card"],
                             corner_radius=12)
        reco.pack(fill="x", pady=(0, 8))

        if wins_max > loses_max:
            reco_txt = f"✅  Remplacez {meilleur} — {100 * wins_max / N_SIMULATIONS:.0f}% de victoires avec ce pet."
            reco_col = C["win"]
            show_btn = True
        else:
            reco_txt = "❌  Aucun remplacement n'est bénéfique. Gardez vos pets actuels."
            reco_col = C["lose"]
            show_btn = False

        ctk.CTkLabel(reco, text=reco_txt, font=FONT_SUB,
                     text_color=reco_col).pack(
            padx=20, pady=(16, 8 if show_btn else 16))

        if show_btn:
            ctk.CTkButton(
                reco, text=f"💾  Appliquer — remplacer {meilleur}",
                font=FONT_BODY, height=36, corner_radius=8,
                fg_color=C["win"], hover_color=C["win_hv"],
                text_color=C["bg"],
                command=lambda n=meilleur, p=nouveau_pet: self._remplacer_pet(n, p),
            ).pack(padx=20, pady=(0, 16), fill="x")

    def _remplacer_pet(self, nom: str, nouveau_pet: Dict) -> None:
        if not confirmer(
            self.app, f"Remplacer {nom}",
            f"Remplacer le pet du slot {nom} ?",
            ok_label="Remplacer", danger=False,
        ):
            return
        self.controller.set_pet(nom, nouveau_pet)
        self._lbl_status.configure(text=f"✅ {nom} mis à jour !",
                                    text_color=C["win"])
        self.app.refresh_current()

    def _modifier_direct(self) -> None:
        texte = self._textbox.get("1.0", "end").strip()
        if not texte:
            self._lbl_status.configure(
                text="⚠ Collez d'abord les stats du pet.",
                text_color=C["lose"])
            return
        ModifyPetDialog(self, self.controller, self.app, texte)


# ════════════════════════════════════════════════════════════
#  Dialogue de modification directe
# ════════════════════════════════════════════════════════════

class ModifyPetDialog(ctk.CTkToplevel):

    def __init__(self, parent, controller, app, texte: str):
        super().__init__(parent)
        self.controller = controller
        self.app        = app
        self.texte      = texte
        self.title("Modifier un slot pet")
        self.geometry("400x280")
        self.resizable(False, False)
        self.configure(fg_color=C["surface"])
        self.grab_set()
        self.transient(parent)
        self._build()

    def _build(self) -> None:
        ctk.CTkLabel(self, text="Quel slot remplacer ?",
                     font=("Segoe UI", 15, "bold"),
                     text_color=C["text"]).pack(padx=24, pady=(24, 8))
        ctk.CTkLabel(self, text="Le pet sera enregistré sans simulation.",
                     font=FONT_BODY, text_color=C["muted"]).pack(padx=24)

        self.slot_var = ctk.StringVar(value="PET1")
        for nom in _SLOTS:
            icon = PET_ICONS.get(nom, "🐾")
            ctk.CTkRadioButton(
                self, text=f"{icon}  {nom}",
                variable=self.slot_var, value=nom,
                text_color=C["text"], font=FONT_BODY,
            ).pack(padx=40, pady=4, anchor="w")

        btn_f = ctk.CTkFrame(self, fg_color="transparent")
        btn_f.pack(padx=24, pady=20, fill="x")
        ctk.CTkButton(btn_f, text="Annuler", fg_color=C["border"],
                      hover_color=C["border_hl"], font=FONT_BODY, width=100,
                      command=self.destroy).pack(side="right", padx=(8, 0))
        ctk.CTkButton(btn_f, text="✓  Enregistrer",
                      fg_color=C["accent"], hover_color=C["accent_hv"],
                      font=FONT_BODY, width=140,
                      command=self._save).pack(side="right")

    def _save(self) -> None:
        nom     = self.slot_var.get()
        nouveau = self.controller.importer_texte_pet(self.texte)
        self.controller.set_pet(nom, nouveau)
        self.destroy()
        self.app.refresh_current()
