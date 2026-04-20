"""
============================================================
  FORGE MASTER UI — Gestion du Mount
  Un seul mount, fonctionne comme les pets.
  Placer dans : forge_master_UI/ui/views/mount_view.py
============================================================
"""

import customtkinter as ctk

C = {
    "bg":      "#0D0F14",
    "surface": "#151820",
    "card":    "#1C2030",
    "border":  "#2A2F45",
    "accent":  "#E8593C",
    "text":    "#E8E6DF",
    "muted":   "#7A7F96",
    "win":     "#2ECC71",
    "lose":    "#E74C3C",
    "draw":    "#F39C12",
}

FONT_TITLE = ("Segoe UI", 20, "bold")
FONT_SUB   = ("Segoe UI", 13, "bold")
FONT_BODY  = ("Segoe UI", 13)
FONT_SMALL = ("Segoe UI", 11)
FONT_MONO  = ("Consolas", 12)

STAT_LABELS = {
    "hp_flat":         "❤  HP",
    "damage_flat":     "⚔  Damage",
    "health_pct":      "❤  Health %",
    "damage_pct":      "⚔  Damage %",
    "melee_pct":       "⚔  Melee %",
    "ranged_pct":      "⚔  Ranged %",
    "taux_crit":       "🎯 Crit Chance",
    "degat_crit":      "💥 Crit Damage",
    "health_regen":    "♻  Health Regen",
    "lifesteal":       "🩸 Lifesteal",
    "double_chance":   "✌  Double Chance",
    "vitesse_attaque": "⚡ Attack Speed",
    "skill_damage":    "✨ Skill Damage",
    "skill_cooldown":  "⏱  Skill CD",
    "chance_blocage":  "🛡  Block Chance",
}

MOUNT_STATS_KEYS = [
    "hp_flat", "damage_flat", "health_pct", "damage_pct",
    "melee_pct", "ranged_pct", "taux_crit", "degat_crit",
    "health_regen", "lifesteal", "double_chance", "vitesse_attaque",
    "skill_damage", "skill_cooldown", "chance_blocage"
]


class MountView(ctk.CTkFrame):

    def __init__(self, parent, controller, app):
        super().__init__(parent, fg_color=C["bg"], corner_radius=0)
        self.controller = controller
        self.app        = app
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._build()

    # ── Construction principale ───────────────────────────────

    def _build(self):
        header = ctk.CTkFrame(self, fg_color=C["surface"], corner_radius=0, height=64)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_propagate(False)
        ctk.CTkLabel(header, text="🐴  Gestion du Mount",
                     font=FONT_TITLE, text_color=C["text"]).pack(
            side="left", padx=24, pady=16)

        scroll = ctk.CTkScrollableFrame(self, fg_color=C["bg"], corner_radius=0)
        scroll.grid(row=1, column=0, sticky="nsew")
        scroll.grid_columnconfigure(0, weight=1)
        self._scroll = scroll

        self._build_mount_card()
        self._build_import_zone()
        self._build_result_zone()

    def _build_mount_card(self):
        """Affiche la carte du mount actuel."""
        mount = self.controller.get_mount()

        card = ctk.CTkFrame(self._scroll, fg_color=C["card"], corner_radius=12)
        card.grid(row=0, column=0, padx=16, pady=16, sticky="ew")

        ctk.CTkLabel(card, text="🐴  Mount actuel",
                     font=FONT_SUB, text_color=C["text"]).pack(
            padx=16, pady=(14, 6), anchor="w")

        stats_non_nuls = [(k, v) for k, v in mount.items() if v != 0.0]

        if not stats_non_nuls:
            ctk.CTkLabel(card, text="(aucun mount enregistré)",
                         font=FONT_BODY, text_color=C["muted"]).pack(
                padx=16, pady=20)
        else:
            inner = ctk.CTkFrame(card, fg_color="transparent")
            inner.pack(fill="x", padx=10, pady=(0, 10))
            inner.grid_columnconfigure(1, weight=1)

            for i, (k, v) in enumerate(stats_non_nuls):
                row_f = ctk.CTkFrame(inner,
                                     fg_color="#232840" if i % 2 == 0 else C["card"],
                                     corner_radius=4)
                row_f.grid(row=i, column=0, columnspan=2, padx=0, pady=1, sticky="ew")
                inner.grid_columnconfigure(0, weight=1)

                label = STAT_LABELS.get(k, k)
                ctk.CTkLabel(row_f, text=label, font=FONT_SMALL,
                             text_color=C["muted"], anchor="w").pack(
                    side="left", padx=10, pady=4)

                unit    = "" if k in ("hp_flat", "damage_flat") else "%"
                val_txt = (self.controller.fmt_nombre(v)
                           if k in ("hp_flat", "damage_flat")
                           else f"+{v}{unit}")
                ctk.CTkLabel(row_f, text=val_txt, font=FONT_MONO,
                             text_color=C["text"], anchor="e").pack(
                    side="right", padx=10, pady=4)

        ctk.CTkFrame(card, fg_color="transparent", height=6).pack()

    def _build_import_zone(self):
        """Zone de saisie du nouveau mount."""
        card = ctk.CTkFrame(self._scroll, fg_color=C["card"], corner_radius=12)
        card.grid(row=1, column=0, padx=16, pady=(0, 8), sticky="ew")
        card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(card, text="Tester un nouveau mount",
                     font=FONT_SUB, text_color=C["text"]).grid(
            row=0, column=0, padx=20, pady=(16, 4), sticky="w")
        ctk.CTkLabel(card, text="Collez les stats du mount depuis le jeu.",
                     font=FONT_SMALL, text_color=C["muted"]).grid(
            row=1, column=0, padx=20, pady=(0, 8), sticky="w")

        self._textbox = ctk.CTkTextbox(
            card, height=130, font=("Consolas", 11),
            fg_color="#0D0F14", text_color=C["text"],
            border_color=C["border"], border_width=1)
        self._textbox.grid(row=2, column=0, padx=16, pady=(0, 8), sticky="ew")

        btn_f = ctk.CTkFrame(card, fg_color="transparent")
        btn_f.grid(row=3, column=0, padx=16, pady=(0, 8), sticky="w")

        ctk.CTkButton(btn_f, text="🔬  Simuler le remplacement",
                      font=FONT_BODY, height=38, corner_radius=8,
                      fg_color=C["accent"], hover_color="#c94828",
                      command=self._tester_mount).pack(side="left", padx=(0, 8))

        ctk.CTkButton(btn_f, text="💾  Enregistrer directement",
                      font=FONT_BODY, height=38, corner_radius=8,
                      fg_color="#2A2F45", hover_color="#3A3F55",
                      command=self._enregistrer_direct).pack(side="left")

        self._lbl_status = ctk.CTkLabel(card, text="",
                                         font=FONT_SMALL, text_color=C["muted"])
        self._lbl_status.grid(row=4, column=0, padx=20, pady=(0, 12))

    def _build_result_zone(self):
        self._result_outer = ctk.CTkFrame(self._scroll, fg_color="transparent")
        self._result_outer.grid(row=2, column=0, padx=16, pady=(0, 16), sticky="ew")
        self._result_outer.grid_columnconfigure(0, weight=1)

    # ── Logique simulation ────────────────────────────────────

    def _tester_mount(self):
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

        nouveau_mount = self.controller.importer_texte_mount(texte)

        for w in self._result_outer.winfo_children():
            w.destroy()

        self._lbl_status.configure(text="⏳ Simulation en cours…",
                                    text_color=C["muted"])
        self.update()

        def on_result(wins, loses, draws):
            self._lbl_status.configure(text="", text_color=C["muted"])
            self._afficher_resultats(wins, loses, draws, nouveau_mount)

        self.controller.tester_mount(nouveau_mount, on_result)

    def _afficher_resultats(self, wins, loses, draws, nouveau_mount):
        for w in self._result_outer.winfo_children():
            w.destroy()

        card = ctk.CTkFrame(self._result_outer, fg_color=C["card"], corner_radius=12)
        card.pack(fill="x", pady=(0, 8))

        # Titre
        ctk.CTkLabel(card, text="Résultat — Nouveau mount vs Ancien mount",
                     font=FONT_SUB, text_color=C["text"]).pack(
            padx=20, pady=(16, 4), anchor="w")
        ctk.CTkLabel(card,
                     text="Nouveau moi (avec ce mount) vs Ancien moi (avec l'ancien mount).",
                     font=FONT_SMALL, text_color=C["muted"]).pack(
            padx=20, pady=(0, 12), anchor="w")

        # Barres WIN / LOSE / DRAW
        bars_f = ctk.CTkFrame(card, fg_color="transparent")
        bars_f.pack(fill="x", padx=20, pady=(0, 8))

        for label, val, color in [
            ("WIN",  wins,  C["win"]),
            ("LOSE", loses, C["lose"]),
            ("DRAW", draws, C["draw"]),
        ]:
            row_f = ctk.CTkFrame(bars_f, fg_color="transparent")
            row_f.pack(fill="x", pady=3)
            ctk.CTkLabel(row_f, text=label, font=FONT_SMALL,
                         text_color=color, width=40).pack(side="left")
            bar = ctk.CTkProgressBar(row_f, height=10, corner_radius=4,
                                      progress_color=color)
            bar.pack(side="left", fill="x", expand=True, padx=8)
            bar.set(val / 1000)
            ctk.CTkLabel(row_f, text=f"{val / 10:.0f}%",
                         font=FONT_SMALL, text_color=C["muted"],
                         width=40).pack(side="right")

        # Verdict + bouton
        if wins > loses:
            verdict_txt = f"✅  Ce mount est meilleur — {wins / 10:.0f}% de victoires."
            verdict_col = C["win"]
            show_btn    = True
        elif loses > wins:
            verdict_txt = f"❌  Ce mount est moins bon. Gardez l'actuel."
            verdict_col = C["lose"]
            show_btn    = False
        else:
            verdict_txt = "🤝  Égalité — les deux mounts se valent."
            verdict_col = C["draw"]
            show_btn    = False

        ctk.CTkLabel(card, text=verdict_txt,
                     font=FONT_SUB, text_color=verdict_col).pack(
            padx=20, pady=(8, 8 if show_btn else 16))

        if show_btn:
            ctk.CTkButton(
                card,
                text="💾  Appliquer ce mount",
                font=FONT_BODY, height=36, corner_radius=8,
                fg_color=C["win"], hover_color="#27ae60",
                text_color="#0D0F14",
                command=lambda m=nouveau_mount: self._appliquer_mount(m),
            ).pack(padx=20, pady=(0, 16), fill="x")

    # ── Actions ───────────────────────────────────────────────

    def _appliquer_mount(self, mount):
        self.controller.set_mount(mount)
        self._lbl_status.configure(
            text="✅ Mount mis à jour !", text_color=C["win"])
        self.app.refresh_current()

    def _enregistrer_direct(self):
        texte = self._textbox.get("1.0", "end").strip()
        if not texte:
            self._lbl_status.configure(
                text="⚠ Collez d'abord les stats du mount.",
                text_color=C["lose"])
            return
        mount = self.controller.importer_texte_mount(texte)
        self.controller.set_mount(mount)
        self._lbl_status.configure(
            text="✅ Mount enregistré !", text_color=C["win"])
        self.app.refresh_current()
