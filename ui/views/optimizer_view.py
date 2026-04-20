"""
============================================================
  FORGE MASTER UI — Optimizer View
  Placer dans : forge_master_UI/ui/views/optimizer_view.py
============================================================
"""

import threading
import sys
import os
import customtkinter as ctk

C = {
    "bg":      "#0D0F14",
    "surface": "#151820",
    "card":    "#1C2030",
    "border":  "#2A2F45",
    "accent":  "#E8593C",
    "accent2": "#F2A623",
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


class OptimizerView(ctk.CTkFrame):

    def __init__(self, parent, controller, app):
        super().__init__(parent, fg_color=C["bg"], corner_radius=0)
        self.controller = controller
        self.app        = app
        self._stop_flag = threading.Event()
        self._running   = False

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._build()

    # ════════════════════════════════════════════════════════
    #  LAYOUT
    # ════════════════════════════════════════════════════════

    def _build(self):
        self._build_header()
        self._build_body()

    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color=C["surface"], corner_radius=0, height=64)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_propagate(False)

        ctk.CTkLabel(
            header, text="🧬  Optimiseur génétique",
            font=FONT_TITLE, text_color=C["text"],
        ).pack(side="left", padx=24, pady=16)

        self._btn_stop = ctk.CTkButton(
            header, text="⏹  Arrêter",
            font=FONT_BODY, height=36, corner_radius=8,
            fg_color="#444", hover_color="#666",
            command=self._stop,
            state="disabled",
        )
        self._btn_stop.pack(side="right", padx=8, pady=14)

        self._btn_start = ctk.CTkButton(
            header, text="▶  Lancer",
            font=FONT_BODY, height=36, corner_radius=8,
            fg_color=C["accent"], hover_color="#c94828",
            command=self._start,
        )
        self._btn_start.pack(side="right", padx=8, pady=14)

    def _build_body(self):
        body = ctk.CTkScrollableFrame(self, fg_color=C["bg"], corner_radius=0)
        body.grid(row=1, column=0, sticky="nsew")
        body.grid_columnconfigure(0, weight=1)
        self._body = body

        # ── Configuration ────────────────────────────────
        cfg = ctk.CTkFrame(body, fg_color=C["card"], corner_radius=10,
                           border_width=1, border_color=C["border"])
        cfg.pack(fill="x", padx=20, pady=(16, 8))
        cfg.grid_columnconfigure((0, 1, 2), weight=1)

        ctk.CTkLabel(cfg, text="Configuration",
                     font=FONT_SUB, text_color=C["accent"]).grid(
            row=0, column=0, columnspan=3, padx=16, pady=(12, 4), sticky="w")

        params = [
            ("Population",        "population_size", 32, 8,  128, 8),
            ("Survivants (top K)", "top_k",           8,  2,  32,  1),
            ("Générations",        "num_gen",          10, 2,  50,  1),
        ]
        self._sliders      = {}
        self._slider_labels = {}

        for col, (label, key, default, lo, hi, step) in enumerate(params):
            fr = ctk.CTkFrame(cfg, fg_color="transparent")
            fr.grid(row=1, column=col, padx=20, pady=(4, 14), sticky="ew")

            ctk.CTkLabel(fr, text=label, font=FONT_SMALL,
                         text_color=C["muted"]).pack(anchor="w")

            val_lbl = ctk.CTkLabel(fr, text=str(default),
                                   font=("Segoe UI", 16, "bold"),
                                   text_color=C["text"])
            val_lbl.pack(anchor="w")
            self._slider_labels[key] = val_lbl

            sl = ctk.CTkSlider(
                fr, from_=lo, to=hi,
                number_of_steps=(hi - lo) // step,
                command=lambda v, k=key: self._on_slider(k, v),
            )
            sl.set(default)
            sl.pack(fill="x")
            self._sliders[key] = sl

        # ── Progression ──────────────────────────────────
        prog_fr = ctk.CTkFrame(body, fg_color=C["card"], corner_radius=10,
                                border_width=1, border_color=C["border"])
        prog_fr.pack(fill="x", padx=20, pady=8)
        prog_fr.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(prog_fr, text="Progression",
                     font=FONT_SUB, text_color=C["accent"]).grid(
            row=0, column=0, padx=16, pady=(12, 4), sticky="w")

        self._lbl_status = ctk.CTkLabel(
            prog_fr, text="En attente…",
            font=FONT_BODY, text_color=C["muted"])
        self._lbl_status.grid(row=1, column=0, padx=16, sticky="w")

        self._progressbar = ctk.CTkProgressBar(prog_fr, height=10, corner_radius=4)
        self._progressbar.set(0)
        self._progressbar.grid(row=2, column=0, padx=16, pady=(6, 6), sticky="ew")

        self._lbl_gen = ctk.CTkLabel(
            prog_fr, text="",
            font=FONT_SMALL, text_color=C["muted"])
        self._lbl_gen.grid(row=3, column=0, padx=16, pady=(0, 14), sticky="w")

        # ── Log des générations ──────────────────────────
        log_fr = ctk.CTkFrame(body, fg_color=C["card"], corner_radius=10,
                               border_width=1, border_color=C["border"])
        log_fr.pack(fill="x", padx=20, pady=8)
        log_fr.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(log_fr, text="Journal des générations",
                     font=FONT_SUB, text_color=C["accent"]).grid(
            row=0, column=0, padx=16, pady=(12, 4), sticky="w")

        self._log_box = ctk.CTkTextbox(
            log_fr, height=160, font=FONT_MONO,
            fg_color=C["surface"], text_color=C["text"],
            state="disabled",
        )
        self._log_box.grid(row=1, column=0, padx=16, pady=(0, 14), sticky="ew")

        # ── Substats des gagnants ────────────────────────
        res_fr = ctk.CTkFrame(body, fg_color=C["card"], corner_radius=10,
                               border_width=1, border_color=C["border"])
        res_fr.pack(fill="x", padx=20, pady=8)
        res_fr.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(res_fr, text="Substats des builds gagnants",
                     font=FONT_SUB, text_color=C["accent"]).grid(
            row=0, column=0, padx=16, pady=(12, 4), sticky="w")
        ctk.CTkLabel(
            res_fr,
            text="Taux moyen dans les tops builds (valeur moyenne / max possible)",
            font=FONT_SMALL, text_color=C["muted"],
        ).grid(row=1, column=0, padx=16, sticky="w")

        self._substats_frame = ctk.CTkFrame(res_fr, fg_color="transparent")
        self._substats_frame.grid(row=2, column=0, padx=16, pady=(8, 14), sticky="ew")
        self._substats_frame.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(self._substats_frame,
                     text="Lance l'optimiseur pour voir les résultats.",
                     font=FONT_SMALL, text_color=C["muted"]).grid(row=0, column=0)

        # ── Classement top builds ────────────────────────
        top_fr = ctk.CTkFrame(body, fg_color=C["card"], corner_radius=10,
                               border_width=1, border_color=C["border"])
        top_fr.pack(fill="x", padx=20, pady=(8, 20))
        top_fr.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(top_fr, text="Classement — Top 10 builds",
                     font=FONT_SUB, text_color=C["accent"]).grid(
            row=0, column=0, padx=16, pady=(12, 4), sticky="w")

        self._classement_frame = ctk.CTkFrame(top_fr, fg_color="transparent")
        self._classement_frame.grid(row=1, column=0, padx=16, pady=(0, 14), sticky="ew")
        ctk.CTkLabel(self._classement_frame,
                     text="Lance l'optimiseur pour voir le classement.",
                     font=FONT_SMALL, text_color=C["muted"]).grid(row=0, column=0)

    # ════════════════════════════════════════════════════════
    #  CONTRÔLES
    # ════════════════════════════════════════════════════════

    def _on_slider(self, key, value):
        self._slider_labels[key].configure(text=str(int(round(value))))

    def _get_params(self):
        return {
            "population_size": int(round(self._sliders["population_size"].get())),
            "top_k":           int(round(self._sliders["top_k"].get())),
            "num_generations": int(round(self._sliders["num_gen"].get())),
        }

    def _start(self):
        if self._running:
            return
        self._running = True
        self._stop_flag.clear()
        self._btn_start.configure(state="disabled")
        self._btn_stop.configure(state="normal")
        self._log_clear()
        self._set_status("Initialisation…", C["muted"])
        self._progressbar.set(0)
        self._lbl_gen.configure(text="")
        self._vider_resultats()
        params = self._get_params()
        threading.Thread(target=self._run_optimizer, kwargs=params, daemon=True).start()

    def _stop(self):
        self._stop_flag.set()
        self._set_status("Arrêt demandé…", C["draw"])

    # ════════════════════════════════════════════════════════
    #  THREAD SECONDAIRE
    # ════════════════════════════════════════════════════════

    def _run_optimizer(self, population_size, top_k, num_generations):
        try:
            # ui/views/optimizer_view.py → remonter 2 fois pour atteindre la racine
            # __file__ = forge_master_UI/ui/views/optimizer_view.py
            # dirname×1 = forge_master_UI/ui/views/
            # dirname×2 = forge_master_UI/ui/
            # dirname×3 = forge_master_UI/   ← racine du projet
            root_dir = os.path.dirname(         # forge_master_UI/
                           os.path.dirname(     # ui/
                               os.path.dirname( # views/
                                   os.path.abspath(__file__))))
            print(f"[Optimizer] root_dir = {root_dir}")
            print(f"[Optimizer] sys.path avant = {sys.path[:3]}")

            if root_dir not in sys.path:
                sys.path.insert(0, root_dir)

            print(f"[Optimizer] Tentative import forge_optimizer depuis {root_dir}")
            from forge_optimizer import optimiser, analyser_substats
            print("[Optimizer] ✅ forge_optimizer importé")

            print("[Optimizer] Tentative import backend")
            from backend.forge_master import simuler_100
            print("[Optimizer] ✅ backend importé")

        except ImportError as e:
            print(f"[Optimizer] ❌ ImportError : {e}")
            self.after(0, lambda err=str(e): self._set_status(
                f"Erreur import : {err}", C["lose"]))
            self.after(0, lambda err=str(e): self._log_append(
                f"ImportError : {err}\nVérifie que forge_optimizer.py est à la racine du projet.\n"))
            self._running = False
            self.after(0, self._on_done)
            return
        except Exception as e:
            print(f"[Optimizer] ❌ Erreur inattendue à l'import : {e}")
            self.after(0, lambda err=str(e): self._set_status(
                f"Erreur : {err}", C["lose"]))
            self._running = False
            self.after(0, self._on_done)
            return

        def on_generation(gen, top_score, avg_score, classement):
            msg = (
                f"Gén. {gen:>2}/{num_generations}  │  "
                f"Top : {top_score*100:5.1f}%  │  "
                f"Moy. top{top_k}: {avg_score*100:5.1f}%\n"
            )
            # Callbacks thread-safe : une lambda = une action
            self.after(0, lambda m=msg: self._log_append(m))
            self.after(0, lambda g=gen: self._lbl_gen.configure(
                text=f"Génération {g} / {num_generations} terminée"))

        def on_progress(idx, total, gen):
            pct   = idx / total if total > 0 else 0.0
            label = (
                f"Gén. {gen}/{num_generations} — "
                f"Combat {idx + 1}/{total}  ({pct * 100:.0f}%)"
            )
            # FIX : deux after() séparés, pas un tuple dans un lambda
            self.after(0, lambda p=pct: self._progressbar.set(p))
            self.after(0, lambda l=label: self._set_status(l, C["muted"]))

        try:
            hall, historique = optimiser(
                population_size=population_size,
                top_k=top_k,
                num_generations=num_generations,
                generation_callback=on_generation,
                progress_callback=on_progress,
                stop_flag=self._stop_flag,
            )
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            self.after(0, lambda err=tb: self._set_status(
                f"Erreur simulation : {e}", C["lose"]))
            self.after(0, lambda err=tb: self._log_append(f"\n--- ERREUR ---\n{err}\n"))
            self._running = False
            self.after(0, self._on_done)
            return

        try:
            analyse = analyser_substats(hall)
        except Exception as e:
            analyse = []

        # Affichage des résultats dans le thread principal
        self.after(0, lambda h=hall, a=analyse: self._afficher_resultats(h, a))
        self._running = False
        self.after(0, self._on_done)

    def _on_done(self):
        self._running = False
        self._btn_start.configure(state="normal")
        self._btn_stop.configure(state="disabled")
        if not self._stop_flag.is_set():
            self._set_status("✅ Terminé !", C["win"])
            self._progressbar.set(1.0)
        else:
            self._set_status("⏹ Arrêté", C["draw"])

    # ════════════════════════════════════════════════════════
    #  AFFICHAGE RÉSULTATS
    # ════════════════════════════════════════════════════════

    def _vider_resultats(self):
        for w in self._substats_frame.winfo_children():
            w.destroy()
        for w in self._classement_frame.winfo_children():
            w.destroy()

    def _afficher_resultats(self, hall, analyse):
        self._vider_resultats()
        if not hall:
            ctk.CTkLabel(self._substats_frame,
                         text="Aucun résultat.",
                         font=FONT_SMALL, text_color=C["lose"]).grid(row=0, column=0)
            return
        self._afficher_substats(analyse)
        self._afficher_classement(hall[:10])

    def _afficher_substats(self, analyse):
        frame = self._substats_frame
        frame.grid_columnconfigure(1, weight=1)

        for row_idx, (taux, key, label, moyenne, max_val) in enumerate(analyse):
            if taux >= 0.7:
                bar_color = C["win"]
            elif taux >= 0.4:
                bar_color = C["accent2"]
            else:
                bar_color = C["muted"]

            # Label stat (colonne 0)
            ctk.CTkLabel(
                frame, text=label,
                font=FONT_SMALL, text_color=C["text"],
                anchor="e", width=130,
            ).grid(row=row_idx, column=0, padx=(0, 10), pady=3, sticky="e")

            # Barre (colonne 1) — canvas simple pour éviter les bugs de .place()
            bar_bg = ctk.CTkCanvas(
                frame, height=16, bg=C["surface"],
                highlightthickness=0,
            )
            bar_bg.grid(row=row_idx, column=1, pady=3, sticky="ew")

            # Dessiner la barre après que le widget soit visible
            def _draw_bar(canvas=bar_bg, t=taux, color=bar_color):
                canvas.update_idletasks()
                w = canvas.winfo_width()
                if w < 2:
                    w = 300
                fill_w = max(4, int(w * t))
                canvas.delete("all")
                canvas.create_rectangle(0, 2, fill_w, 14,
                                        fill=color, outline="")
            bar_bg.bind("<Configure>", lambda e, fn=_draw_bar: fn())
            self.after(50, _draw_bar)

            # Valeur numérique (colonne 2)
            ctk.CTkLabel(
                frame,
                text=f"{taux*100:.0f}%  ({moyenne:.1f} / {max_val:.0f})",
                font=FONT_SMALL, text_color=C["muted"],
                anchor="w", width=130,
            ).grid(row=row_idx, column=2, padx=(10, 0), pady=3, sticky="w")

    def _afficher_classement(self, hall):
        frame = self._classement_frame
        for col in range(6):
            frame.grid_columnconfigure(col, weight=1 if col > 2 else 0)

        headers = ["#", "Winrate", "Gén.", "HP total", "ATK total", "Type"]
        widths   = [32, 72, 48, 120, 120, 130]

        for col, (h, w) in enumerate(zip(headers, widths)):
            ctk.CTkLabel(
                frame, text=h,
                font=("Segoe UI", 11, "bold"),
                text_color=C["muted"], width=w, anchor="w",
            ).grid(row=0, column=col, padx=4, pady=(0, 4), sticky="w")

        sep = ctk.CTkFrame(frame, height=1, fg_color=C["border"])
        sep.grid(row=1, column=0, columnspan=6, sticky="ew", pady=(0, 4))

        rang_colors = [C["accent2"], "#C0C0C0", "#CD7F32"]

        for i, (score, gen, build) in enumerate(hall):
            row = i + 2
            color_rang = rang_colors[i] if i < 3 else C["text"]

            vals = [
                f"#{i + 1}",
                f"{score * 100:.1f}%",
                str(gen),
                f"{build['hp_total']:,.0f}",
                f"{build['attaque_total']:,.0f}",
                build.get("type_attaque", "?"),
            ]
            for col, (v, w) in enumerate(zip(vals, widths)):
                ctk.CTkLabel(
                    frame, text=v,
                    font=FONT_MONO if col >= 3 else FONT_SMALL,
                    text_color=color_rang if col == 0 else C["text"],
                    width=w, anchor="w",
                ).grid(row=row, column=col, padx=4, pady=2, sticky="w")

    # ════════════════════════════════════════════════════════
    #  HELPERS
    # ════════════════════════════════════════════════════════

    def _set_status(self, text, color):
        self._lbl_status.configure(text=text, text_color=color)

    def _log_clear(self):
        self._log_box.configure(state="normal")
        self._log_box.delete("1.0", "end")
        self._log_box.configure(state="disabled")

    def _log_append(self, msg):
        self._log_box.configure(state="normal")
        self._log_box.insert("end", msg)
        self._log_box.see("end")
        self._log_box.configure(state="disabled")