#!/usr/bin/env python3
import json
import shutil
import sys
import time
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

# --- CONFIGURATION & DÉTECTION DU FICHIER ---
SCRIPT_DIR = Path(__file__).resolve().parent

CANDIDATE_PATHS = [
    SCRIPT_DIR.parent / "kira_memory.json",
    SCRIPT_DIR.parent / "MascotInir" / "kira_memory.json",
    SCRIPT_DIR / "kira_memory.json",
]

MEMORY_FILE = CANDIDATE_PATHS[0]
for p in CANDIDATE_PATHS:
    if p.exists():
        MEMORY_FILE = p
        break

BACKUP_FILE = MEMORY_FILE.with_suffix(".json.bak")

# Mots-clés trop génériques qui risquent de déclencher un souvenir sur toutes les pages
WARN_KEYWORDS = {
    "firefox", "chrome", "msedge", "edge", "brave", "zen", "opera", "vivaldi",
    "mangadex", "youtube", "twitch", "discord", "reddit", "komga", "twitter",
    "code", "vscode", "vscodium", "nvim", "neovim", "powershell", "terminal",
    "wt", "cmd", "explorer", "steam", "spotify", "holodex", "wikipedia", "google"
}


# --- GESTIONNAIRE DE DONNÉES ---
class MemoryManager:
    def __init__(self, filepath: Path):
        self.filepath = filepath
        self.backup_path = filepath.with_suffix(".json.bak")
        self.memories: list[dict] = []
        self.load()

    def load(self):
        if not self.filepath.exists():
            self.memories = []
            return
        try:
            data = json.loads(self.filepath.read_text(encoding="utf-8"))
            self.memories = data if isinstance(data, list) else []
        except Exception as e:
            print(f"[Erreur lecture JSON] {e}", file=sys.stderr)
            self.memories = []

    def save(self, make_backup: bool = True):
        self.filepath.parent.mkdir(parents=True, exist_ok=True)
        if make_backup and self.filepath.exists():
            shutil.copy2(self.filepath, self.backup_path)
        self.filepath.write_text(
            json.dumps(self.memories, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8"
        )

    def undo(self) -> bool:
        if not self.backup_path.exists():
            return False
        shutil.copy2(self.backup_path, self.filepath)
        self.load()
        return True

    def add_entry(self, keywords: list[str], note: str, is_global: bool):
        clean_kw = [] if is_global else [k.strip().lower() for k in keywords if k.strip()]
        self.memories.append({
            "keywords": clean_kw,
            "note": note.strip(),
            "global": is_global,
            "added_at": time.strftime("%Y-%m-%d %H:%M")
        })
        self.save()

    def update_entry(self, index: int, keywords: list[str], note: str, is_global: bool):
        if 0 <= index < len(self.memories):
            clean_kw = [] if is_global else [k.strip().lower() for k in keywords if k.strip()]
            self.memories[index]["keywords"] = clean_kw
            self.memories[index]["note"] = note.strip()
            self.memories[index]["global"] = is_global
            self.memories[index]["updated_at"] = time.strftime("%Y-%m-%d %H:%M")
            self.save()

    def delete_entry(self, index: int):
        if 0 <= index < len(self.memories):
            self.memories.pop(index)
            self.save()

    def remove_keyword(self, index: int, kw_to_remove: str):
        if 0 <= index < len(self.memories):
            kws = self.memories[index].get("keywords", [])
            if kw_to_remove in kws:
                kws.remove(kw_to_remove)
                self.memories[index]["keywords"] = kws
                self.memories[index]["updated_at"] = time.strftime("%Y-%m-%d %H:%M")
                self.save()

    def add_keyword(self, index: int, new_kw: str):
        clean = new_kw.strip().lower()
        if clean and 0 <= index < len(self.memories):
            kws = self.memories[index].get("keywords", [])
            if clean not in kws:
                kws.append(clean)
                self.memories[index]["keywords"] = kws
                self.memories[index]["global"] = False
                self.memories[index]["updated_at"] = time.strftime("%Y-%m-%d %H:%M")
                self.save()

    def merge_entries(self, indices: list[int]):
        valid = sorted([i for i in indices if 0 <= i < len(self.memories)])
        if len(valid) < 2:
            return
        combined_kw = []
        notes = []
        is_global = False
        for i in valid:
            m = self.memories[i]
            if m.get("global", False):
                is_global = True
            for k in m.get("keywords", []):
                if k not in combined_kw:
                    combined_kw.append(k)
            if m.get("note"):
                notes.append(m["note"].strip())

        merged_entry = {
            "keywords": [] if is_global else combined_kw,
            "note": " / ".join(notes),
            "global": is_global,
            "added_at": self.memories[valid[0]].get("added_at", time.strftime("%Y-%m-%d %H:%M")),
            "updated_at": time.strftime("%Y-%m-%d %H:%M")
        }

        for i in reversed(valid[1:]):
            self.memories.pop(i)
        self.memories[valid[0]] = merged_entry
        self.save()


# --- BOÎTE DE DIALOGUE AJOUT / ÉDITION ---
class EntryDialog(QDialog):
    def __init__(self, parent=None, entry: dict | None = None):
        super().__init__(parent)
        self.setWindowTitle("Éditer le souvenir" if entry else "Nouveau souvenir pour Rika")
        self.setMinimumWidth(520)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(18, 18, 18, 18)

        self.global_cb = QCheckBox("🌍 Mémoire globale (toujours envoyée à Rika, peu importe la fenêtre)")
        self.global_cb.toggled.connect(self._on_global_toggled)
        layout.addWidget(self.global_cb)

        kw_label = QLabel("Mots-clés déclencheurs (séparés par des virgules) :")
        layout.addWidget(kw_label)

        self.kw_input = QLineEdit()
        self.kw_input.setPlaceholderText("Ex: wiki master, one piece, mon-projet")
        self.kw_input.textChanged.connect(self._check_warnings)
        layout.addWidget(self.kw_input)

        self.warn_label = QLabel("")
        self.warn_label.setWordWrap(True)
        self.warn_label.setStyleSheet("color: #fab387; font-size: 11px;")
        self.warn_label.hide()
        layout.addWidget(self.warn_label)

        note_label = QLabel("Note / Contexte à retenir par Rika :")
        layout.addWidget(note_label)

        self.note_input = QTextEdit()
        self.note_input.setPlaceholderText("Ex: L'utilisateur lit actuellement l'arc Egghead de One Piece...")
        self.note_input.setFixedHeight(100)
        layout.addWidget(self.note_input)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("Annuler")
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton("Enregistrer")
        save_btn.setObjectName("primaryBtn")
        save_btn.clicked.connect(self._validate_and_accept)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

        if entry:
            self.global_cb.setChecked(entry.get("global", False))
            self.kw_input.setText(", ".join(entry.get("keywords", [])))
            self.note_input.setPlainText(entry.get("note", ""))

        self._on_global_toggled(self.global_cb.isChecked())
        self._check_warnings()

    def _on_global_toggled(self, checked: bool):
        self.kw_input.setEnabled(not checked)
        if checked:
            self.warn_label.hide()
        else:
            self._check_warnings()

    def _check_warnings(self):
        if self.global_cb.isChecked():
            self.warn_label.hide()
            return
        kws = [k.strip().lower() for k in self.kw_input.text().split(",") if k.strip()]
        bad = [k for k in kws if k in WARN_KEYWORDS]
        if bad:
            self.warn_label.setText(
                f"⚠️ Attention : {', '.join(bad)} est un mot-clé très générique. "
                f"Cette note risque d'être envoyée à Rika sur toutes tes pages liées à cette plateforme !"
            )
            self.warn_label.show()
        else:
            self.warn_label.hide()

    def _validate_and_accept(self):
        note = self.note_input.toPlainText().strip()
        is_global = self.global_cb.isChecked()
        kws = [k.strip().lower() for k in self.kw_input.text().split(",") if k.strip()]
        if not note:
            QMessageBox.warning(self, "Champ manquant", "La note ne peut pas être vide.")
            return
        if not is_global and not kws:
            QMessageBox.warning(
                self,
                "Mots-clés manquants",
                "Ajoute au moins un mot-clé ou coche « Mémoire globale »."
            )
            return
        self.accept()

    def get_data(self) -> tuple[list[str], str, bool]:
        kws = [k.strip().lower() for k in self.kw_input.text().split(",") if k.strip()]
        return kws, self.note_input.toPlainText().strip(), self.global_cb.isChecked()


# --- CARTE D'UN SOUVENIR ---
class MemoryCard(QFrame):
    def __init__(
        self,
        index: int,
        entry: dict,
        sim_active: bool,
        matched_kws: list[str],
        main_win: "MemoryViewerWindow"
    ):
        super().__init__()
        self.index = index
        self.entry = entry
        self.main_win = main_win

        is_global = entry.get("global", False)
        keywords = entry.get("keywords", [])
        has_warning = any(k in WARN_KEYWORDS for k in keywords)

        if sim_active and (is_global or matched_kws):
            self.setObjectName("cardMatched")
        elif has_warning:
            self.setObjectName("cardWarning")
        else:
            self.setObjectName("cardNormal")

        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(14, 12, 14, 12)
        vbox.setSpacing(8)

        # Ligne du haut : Checkbox + Badge portée + Alerte/Match + Date + Boutons
        top_row = QHBoxLayout()
        top_row.setSpacing(8)

        self.select_cb = QCheckBox()
        self.select_cb.setToolTip("Sélectionner pour fusionner ou supprimer")
        self.select_cb.toggled.connect(self.main_win.update_selection_count)
        top_row.addWidget(self.select_cb)

        scope_badge = QLabel("🌍 GLOBAL" if is_global else "🪟 FENÊTRE")
        scope_badge.setObjectName("badgeGlobal" if is_global else "badgeWindow")
        top_row.addWidget(scope_badge)

        if sim_active and (is_global or matched_kws):
            reason = "Toujours actif (Global)" if is_global else f"Match : {', '.join(matched_kws)}"
            sim_badge = QLabel(f"✅ INJECTÉ ({reason})")
            sim_badge.setObjectName("badgeMatched")
            top_row.addWidget(sim_badge)

        if has_warning:
            warn_badge = QLabel("⚠️ Mot-clé trop large")
            warn_badge.setObjectName("badgeWarn")
            top_row.addWidget(warn_badge)

        date_str = entry.get("updated_at") or entry.get("added_at", "Date inconnue")
        date_lbl = QLabel(f"🕓 {date_str}")
        date_lbl.setStyleSheet("color: #6c7086; font-size: 11px;")
        top_row.addWidget(date_lbl)

        top_row.addStretch()

        edit_btn = QPushButton("✏️ Éditer")
        edit_btn.setObjectName("smallBtn")
        edit_btn.clicked.connect(lambda: self.main_win.edit_entry(self.index))
        top_row.addWidget(edit_btn)

        del_btn = QPushButton("🗑️ Supprimer")
        del_btn.setObjectName("dangerBtn")
        del_btn.clicked.connect(lambda: self.main_win.delete_entry(self.index))
        top_row.addWidget(del_btn)

        vbox.addLayout(top_row)

        # Texte de la note
        note_lbl = QLabel(entry.get("note", ""))
        note_lbl.setWordWrap(True)
        note_lbl.setFont(QFont("Segoe UI", 11))
        note_lbl.setStyleSheet("color: #f2f2f7; padding: 2px 0;")
        vbox.addWidget(note_lbl)

        # Ligne des mots-clés
        if not is_global:
            kw_row = QHBoxLayout()
            kw_row.setSpacing(6)

            kw_title = QLabel("Tags :")
            kw_title.setStyleSheet("color: #a6adc8; font-size: 11px;")
            kw_row.addWidget(kw_title)

            for kw in keywords:
                is_bad = kw in WARN_KEYWORDS
                is_hit = sim_active and (kw in matched_kws)
                prefix = "⚠️ " if is_bad else ("🎯 " if is_hit else "")
                tag_btn = QPushButton(f"{prefix}{kw}  ×")
                if is_bad:
                    tag_btn.setObjectName("tagWarn")
                    tag_btn.setToolTip(
                        f"« {kw} » est un nom générique ! Clique pour retirer ce mot-clé."
                    )
                elif is_hit:
                    tag_btn.setObjectName("tagHit")
                    tag_btn.setToolTip("Ce mot-clé matche la simulation actuelle. Clique pour le supprimer.")
                else:
                    tag_btn.setObjectName("tagNormal")
                    tag_btn.setToolTip(f"Cliquer pour retirer le mot-clé « {kw} »")
                tag_btn.clicked.connect(lambda _, k=kw: self.main_win.remove_keyword(self.index, k))
                kw_row.addWidget(tag_btn)

            add_kw_btn = QPushButton("+ tag")
            add_kw_btn.setObjectName("tagAdd")
            add_kw_btn.setToolTip("Ajouter un mot-clé à cette note")
            add_kw_btn.clicked.connect(lambda: self.main_win.add_keyword_prompt(self.index))
            kw_row.addWidget(add_kw_btn)

            kw_row.addStretch()
            vbox.addLayout(kw_row)


# --- FENÊTRE PRINCIPALE ---
class MemoryViewerWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Rika — Memory Viewer & Moderator")
        self.resize(980, 760)

        self.manager = MemoryManager(MEMORY_FILE)
        self.cards: list[MemoryCard] = []
        self.active_tag_filter: str | None = None

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(18, 16, 18, 16)
        main_layout.setSpacing(12)

        # 1. En-tête
        header_row = QHBoxLayout()
        title_lbl = QLabel("🧠 Mémoire de Rika (Kira)")
        title_lbl.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        header_row.addWidget(title_lbl)

        self.path_lbl = QLabel(f"Fichier : {self.manager.filepath}")
        self.path_lbl.setStyleSheet("color: #6c7086; font-size: 11px;")
        header_row.addStretch()
        header_row.addWidget(self.path_lbl)
        main_layout.addLayout(header_row)

        # 2. Barre de recherche, filtres et actions
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Rechercher dans les notes ou les mots-clés...")
        self.search_input.textChanged.connect(self.refresh_ui)
        toolbar.addWidget(self.search_input, stretch=2)

        self.filter_combo = QComboBox()
        self.filter_combo.addItems([
            "Tous les souvenirs",
            "🪟 Fenêtres spécifiques",
            "🌍 Globaux uniquement",
            "⚠️ Avec mots-clés polluants",
            "✅ Actifs dans le simulateur"
        ])
        self.filter_combo.currentIndexChanged.connect(self.refresh_ui)
        toolbar.addWidget(self.filter_combo)

        add_btn = QPushButton("➕ Ajouter")
        add_btn.setObjectName("primaryBtn")
        add_btn.clicked.connect(self.add_entry)
        toolbar.addWidget(add_btn)

        self.merge_btn = QPushButton("🔗 Fusionner (0)")
        self.merge_btn.setEnabled(False)
        self.merge_btn.clicked.connect(self.merge_selected)
        toolbar.addWidget(self.merge_btn)

        self.undo_btn = QPushButton("↩️ Annuler")
        self.undo_btn.setToolTip("Restaurer la sauvegarde .bak de la dernière modification")
        self.undo_btn.clicked.connect(self.undo_last)
        toolbar.addWidget(self.undo_btn)

        reload_btn = QPushButton("🔄")
        reload_btn.setToolTip("Recharger le fichier depuis le disque")
        reload_btn.clicked.connect(self.reload_from_disk)
        toolbar.addWidget(reload_btn)

        main_layout.addLayout(toolbar)

        # 3. Panneau Simulateur de Fenêtre
        sim_frame = QFrame()
        sim_frame.setObjectName("simBox")
        sim_layout = QVBoxLayout(sim_frame)
        sim_layout.setContentsMargins(14, 10, 14, 10)
        sim_layout.setSpacing(8)

        sim_top = QHBoxLayout()
        sim_title = QLabel("🎯 Simulateur de déclenchement (Teste ce que Rika reçoit selon ta fenêtre active) :")
        sim_title.setStyleSheet("color: #f9e2af; font-weight: bold;")
        sim_top.addWidget(sim_title)
        sim_top.addStretch()

        clear_sim_btn = QPushButton("Effacer test")
        clear_sim_btn.setObjectName("smallBtn")
        clear_sim_btn.clicked.connect(self.clear_simulator)
        sim_top.addWidget(clear_sim_btn)
        sim_layout.addLayout(sim_top)

        sim_inputs = QHBoxLayout()
        self.sim_app = QLineEdit()
        self.sim_app.setPlaceholderText("App ID (ex: firefox, code, discord)")
        self.sim_app.setMaximumWidth(220)
        self.sim_app.textChanged.connect(self.refresh_ui)

        self.sim_title = QLineEdit()
        self.sim_title.setPlaceholderText(
            "Titre de la fenêtre (ex: Chapitre 1120 - One Piece - MangaDex — Mozilla Firefox)"
        )
        self.sim_title.textChanged.connect(self.refresh_ui)

        sim_inputs.addWidget(QLabel("App :"))
        sim_inputs.addWidget(self.sim_app)
        sim_inputs.addWidget(QLabel("Titre :"))
        sim_inputs.addWidget(self.sim_title, stretch=1)
        sim_layout.addLayout(sim_inputs)

        self.sim_result_lbl = QLabel(
            "Tape un titre de fenêtre ci-dessus pour illuminer en vert les souvenirs qui seront injectés dans le prompt."
        )
        self.sim_result_lbl.setWordWrap(True)
        self.sim_result_lbl.setStyleSheet("color: #a6adc8; font-size: 11px;")
        sim_layout.addWidget(self.sim_result_lbl)

        main_layout.addWidget(sim_frame)

        # 4. Compteur de statistiques
        self.stats_lbl = QLabel("")
        self.stats_lbl.setStyleSheet("color: #a6adc8; font-size: 12px;")
        main_layout.addWidget(self.stats_lbl)

        # 5. Zone de défilement des cartes
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)

        self.cards_container = QWidget()
        self.cards_layout = QVBoxLayout(self.cards_container)
        self.cards_layout.setContentsMargins(0, 0, 6, 0)
        self.cards_layout.setSpacing(10)
        self.scroll.setWidget(self.cards_container)

        main_layout.addWidget(self.scroll, stretch=1)

        self._apply_stylesheet()
        self.refresh_ui()

    def _apply_stylesheet(self):
        self.setStyleSheet("""
            QMainWindow, QDialog {
                background-color: #18181e;
                color: #f2f2f7;
            }
            QLabel {
                color: #f2f2f7;
            }
            QLineEdit, QTextEdit, QComboBox {
                background-color: #11111b;
                color: #f2f2f7;
                border: 1px solid #45475a;
                border-radius: 8px;
                padding: 7px 10px;
                font-size: 12px;
            }
            QLineEdit:focus, QTextEdit:focus, QComboBox:focus {
                border: 1px solid #f9e2af;
            }
            QComboBox QAbstractItemView {
                background-color: #18181e;
                color: #f2f2f7;
                selection-background-color: #313244;
            }
            QPushButton {
                background-color: #313244;
                color: #f2f2f7;
                border: 1px solid #45475a;
                border-radius: 8px;
                padding: 7px 13px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #45475a;
            }
            QPushButton:disabled {
                background-color: #1e1e28;
                color: #585b70;
                border-color: #313244;
            }
            QPushButton#primaryBtn {
                background-color: #f9e2af;
                color: #11111b;
                border: none;
            }
            QPushButton#primaryBtn:hover {
                background-color: #f5e0dc;
            }
            QPushButton#smallBtn {
                padding: 4px 10px;
                font-size: 11px;
            }
            QPushButton#dangerBtn {
                background-color: rgba(243, 139, 168, 0.15);
                color: #f38ba8;
                border: 1px solid rgba(243, 139, 168, 0.4);
                padding: 4px 10px;
                font-size: 11px;
            }
            QPushButton#dangerBtn:hover {
                background-color: rgba(243, 139, 168, 0.3);
            }
            QFrame#simBox {
                background-color: #1e1e28;
                border: 1px solid #45475a;
                border-radius: 10px;
            }
            QFrame#cardNormal {
                background-color: #21212b;
                border: 1px solid #313244;
                border-radius: 10px;
            }
            QFrame#cardWarning {
                background-color: #262126;
                border: 1px solid #fab387;
                border-radius: 10px;
            }
            QFrame#cardMatched {
                background-color: #1d2b24;
                border: 2px solid #a6e3a1;
                border-radius: 10px;
            }
            QLabel#badgeGlobal {
                background-color: rgba(137, 180, 250, 0.2);
                color: #89b4fa;
                border-radius: 5px;
                padding: 2px 7px;
                font-size: 10px;
                font-weight: bold;
            }
            QLabel#badgeWindow {
                background-color: rgba(203, 166, 247, 0.2);
                color: #cba6f7;
                border-radius: 5px;
                padding: 2px 7px;
                font-size: 10px;
                font-weight: bold;
            }
            QLabel#badgeMatched {
                background-color: rgba(166, 227, 161, 0.25);
                color: #a6e3a1;
                border-radius: 5px;
                padding: 2px 7px;
                font-size: 10px;
                font-weight: bold;
            }
            QLabel#badgeWarn {
                background-color: rgba(250, 179, 135, 0.25);
                color: #fab387;
                border-radius: 5px;
                padding: 2px 7px;
                font-size: 10px;
                font-weight: bold;
            }
            QPushButton#tagNormal {
                background-color: #11111b;
                color: #cdd6f4;
                border: 1px solid #45475a;
                border-radius: 11px;
                padding: 3px 9px;
                font-size: 11px;
            }
            QPushButton#tagNormal:hover {
                border-color: #f38ba8;
                color: #f38ba8;
            }
            QPushButton#tagWarn {
                background-color: rgba(250, 179, 135, 0.2);
                color: #fab387;
                border: 1px solid #fab387;
                border-radius: 11px;
                padding: 3px 9px;
                font-size: 11px;
            }
            QPushButton#tagWarn:hover {
                background-color: rgba(243, 139, 168, 0.3);
                border-color: #f38ba8;
                color: #f38ba8;
            }
            QPushButton#tagHit {
                background-color: rgba(166, 227, 161, 0.25);
                color: #a6e3a1;
                border: 1px solid #a6e3a1;
                border-radius: 11px;
                padding: 3px 9px;
                font-size: 11px;
            }
            QPushButton#tagAdd {
                background-color: transparent;
                color: #89b4fa;
                border: 1px dashed #45475a;
                border-radius: 11px;
                padding: 3px 8px;
                font-size: 11px;
            }
            QPushButton#tagAdd:hover {
                border-color: #89b4fa;
            }
            QScrollArea {
                background-color: transparent;
            }
            QWidget {
                background-color: transparent;
            }
        """)

    def clear_simulator(self):
        self.sim_app.clear()
        self.sim_title.clear()

    def refresh_ui(self):
        # Nettoyage des cartes existantes
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.cards.clear()

        query = self.search_input.text().strip().lower()
        mode = self.filter_combo.currentIndex()

        sim_app_txt = self.sim_app.text().strip().lower()
        sim_title_txt = self.sim_title.text().strip().lower()
        sim_combined = f"{sim_app_txt} {sim_title_txt}".strip()
        sim_active = bool(sim_combined)

        matched_count = 0
        warn_total = 0
        shown_count = 0

        for idx, mem in enumerate(self.manager.memories):
            is_global = mem.get("global", False)
            kws = mem.get("keywords", [])
            note = mem.get("note", "")

            has_warn = any(k in WARN_KEYWORDS for k in kws)
            if has_warn:
                warn_total += 1

            matched_kws = [k for k in kws if k in sim_combined] if sim_active else []
            is_sim_match = sim_active and (is_global or bool(matched_kws))
            if is_sim_match:
                matched_count += 1

            # Filtrage par texte de recherche
            if query:
                in_note = query in note.lower()
                in_kw = any(query in k.lower() for k in kws)
                if not (in_note or in_kw):
                    continue

            # Filtrage par menu déroulant
            if mode == 1 and is_global:
                continue
            elif mode == 2 and not is_global:
                continue
            elif mode == 3 and not has_warn:
                continue
            elif mode == 4 and not is_sim_match:
                continue

            card = MemoryCard(idx, mem, sim_active, matched_kws, self)
            self.cards.append(card)
            self.cards_layout.addWidget(card)
            shown_count += 1

        self.cards_layout.addStretch()

        # Mise à jour du résumé du simulateur
        if sim_active:
            self.sim_result_lbl.setText(
                f"⚡ Résultat pour « {sim_combined} » : {matched_count} souvenir(s) envoyé(s) dans le prompt de Rika."
            )
            self.sim_result_lbl.setStyleSheet("color: #a6e3a1; font-weight: bold; font-size: 12px;")
        else:
            self.sim_result_lbl.setText(
                "Tape un titre de fenêtre ci-dessus pour illuminer en vert les souvenirs qui seront injectés dans le prompt."
            )
            self.sim_result_lbl.setStyleSheet("color: #a6adc8; font-size: 11px;")

        total = len(self.manager.memories)
        self.stats_lbl.setText(
            f"Affichés : {shown_count} / {total} souvenir(s)   •   "
            f"⚠️ Entrées avec mot-clé trop large : {warn_total}"
        )
        self.undo_btn.setEnabled(self.manager.backup_path.exists())
        self.update_selection_count()

    def update_selection_count(self):
        selected = [c.index for c in self.cards if c.select_cb.isChecked()]
        self.merge_btn.setText(f"🔗 Fusionner ({len(selected)})")
        self.merge_btn.setEnabled(len(selected) >= 2)

    def add_entry(self):
        dlg = EntryDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            kws, note, is_global = dlg.get_data()
            self.manager.add_entry(kws, note, is_global)
            self.refresh_ui()

    def edit_entry(self, index: int):
        entry = self.manager.memories[index]
        dlg = EntryDialog(self, entry)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            kws, note, is_global = dlg.get_data()
            self.manager.update_entry(index, kws, note, is_global)
            self.refresh_ui()

    def delete_entry(self, index: int):
        self.manager.delete_entry(index)
        self.refresh_ui()

    def remove_keyword(self, index: int, kw: str):
        self.manager.remove_keyword(index, kw)
        self.refresh_ui()

    def add_keyword_prompt(self, index: int):
        text, ok = QInputDialog.getText(self, "Ajouter un tag", "Nouveau mot-clé (en minuscules) :")
        if ok and text.strip():
            self.manager.add_keyword(index, text.strip())
            self.refresh_ui()

    def merge_selected(self):
        selected = [c.index for c in self.cards if c.select_cb.isChecked()]
        if len(selected) >= 2:
            self.manager.merge_entries(selected)
            self.refresh_ui()

    def undo_last(self):
        if self.manager.undo():
            self.refresh_ui()

    def reload_from_disk(self):
        self.manager.load()
        self.refresh_ui()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MemoryViewerWindow()
    win.show()
    sys.exit(app.exec())