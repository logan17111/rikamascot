import base64
import io
import json
import os
import random
import re
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

import keyboard
import psutil
import win32api
import win32con
import win32gui
import win32process
from PIL import ImageGrab
from PyQt6.QtCore import QPoint, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QCursor, QFont, QIcon, QMovie, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

# --- CONFIGURATION À PERSONNALISER ---
USER_NAME = "Utilisateur"  # Ton prénom ou pseudo
MODEL = "vertex/gemini-2.5-flash@europe-west1"
API_URL = "https://router.requesty.ai/v1/chat/completions"

MIN_COOLDOWN = 7 * 60
MAX_COOLDOWN = 15 * 60

# --- CHEMINS ---
PROJECT_DIR = Path(__file__).resolve().parent
BASE_DIR = PROJECT_DIR.parent
MASCOT_DIR = BASE_DIR / "images" / "mascot"
MEMORY_FILE = PROJECT_DIR / "kira_memory.json"
LAST_CTX_FILE = Path(tempfile.gettempdir()) / "kira_last_context.json"
PREVIEW_FILE = Path(tempfile.gettempdir()) / "kira_view.jpg"


def load_api_key() -> str:
    token_file = PROJECT_DIR / "token"
    if token_file.exists():
        return token_file.read_text(encoding="utf-8").strip()
    return os.environ.get("REQUESTY_API_KEY", "")


API_KEY = load_api_key()

BLACKLIST_KEYWORDS = ["bitwarden", "keepass", "1password", "navigation privée", "private browsing", "banque"]

THEMES_INTERETS = [
    "Apprentissage du japonais : présente un Kanji cool ou un mot d'argot japonais (avec écriture, lecture en rômaji et sens littéral)",
    "Apprentissage du japonais : explique une petite tournure de phrase ou expression idiomatique japonaise qu'on entend souvent dans les animes/mangas",
    "Astuce ou anecdote technique Linux, Windows, Sysadmin ou terminal",
    "Anecdote ou astuce DevOps / Sysadmin (Docker, Ansible, Terraform, réseau ou self-hosting)",
    "Anecdote geek sur la culture Manga / Anime ou le jeu vidéo (JRPG)"
]

# Recensement des sprites disponibles
SPRITE_MAP = {}
for f in MASCOT_DIR.glob("inir-mascot-*"):
    if f.suffix.lower() in (".png", ".gif") and "expression-sheet" not in f.name:
        pose_name = f.stem.removeprefix("inir-mascot-")
        if pose_name not in SPRITE_MAP or f.suffix.lower() == ".gif":
            SPRITE_MAP[pose_name] = f

POSES = sorted(SPRITE_MAP.keys()) or ["smug-hand-raised", "tired-dev", "reading", "thinking-pose"]


# --- FENÊTRE ACTIVE, MULTI-ÉCRANS & SMART CAPTURE WINDOWS ---
def get_active_screen_geometry():
    try:
        hwnd = win32gui.GetForegroundWindow()
        if hwnd:
            l, t, r, b = win32gui.GetWindowRect(hwnd)
            scr = QApplication.screenAt(QPoint((l + r) // 2, (t + b) // 2))
            if scr:
                return scr.availableGeometry()
    except Exception:
        pass
    scr = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
    return scr.availableGeometry()


def get_active_window() -> dict:
    try:
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return {"app_id": "bureau", "title": "Bureau Windows"}
        title = win32gui.GetWindowText(hwnd) or "Bureau Windows"
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        app_id = psutil.Process(pid).name().removesuffix(".exe").lower()
        return {"app_id": app_id, "title": title}
    except Exception:
        return {"app_id": "inconnu", "title": "Bureau Windows"}


def get_smart_crop_b64(app_id: str, title: str) -> str:
    try:
        hwnd = win32gui.GetForegroundWindow()
        if hwnd:
            monitor = win32api.MonitorFromWindow(hwnd, win32con.MONITOR_DEFAULTTONEAREST)
            mon_rect = win32api.GetMonitorInfo(monitor)["Monitor"]
            img = ImageGrab.grab(bbox=mon_rect, all_screens=True)
        else:
            img = ImageGrab.grab()

        w, h = img.size
        ctx = f"{app_id} {title}".lower()

        if any(k in ctx for k in ["code", "vscodium", "nvim", "powershell", "terminal", "wt", "cmd"]):
            box = (int(w * 0.10), int(h * 0.08), int(w * 0.85), int(h * 0.88))
        elif any(k in ctx for k in ["discord", "slack", "teams", "webcord"]):
            box = (int(w * 0.22), int(h * 0.10), int(w * 0.82), int(h * 0.90))
        elif any(k in ctx for k in ["twitter", " / x", "reddit", "mangadex", "komga", "wiki"]):
            box = (int(w * 0.20), int(h * 0.08), int(w * 0.80), int(h * 0.92))
        else:
            box = (int(w * 0.12), int(h * 0.08), int(w * 0.88), int(h * 0.90))

        cropped = img.crop(box).convert("RGB")
        cropped.thumbnail((1280, 1280))
        cropped.save(PREVIEW_FILE, format="JPEG", quality=80)

        buf = io.BytesIO()
        cropped.save(buf, format="JPEG", quality=80)
        return base64.b64encode(buf.getvalue()).decode("utf-8")
    except Exception as e:
        print(f"[Erreur Capture] {e}")
        return ""


# --- MÉMOIRE ---
def load_memories() -> list[dict]:
    if not MEMORY_FILE.exists():
        return []
    try:
        return json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def save_memory_entry(keywords: list[str], note: str, is_global: bool = False):
    memories = load_memories()
    clean_kw = [k.strip().lower() for k in keywords if k.strip()]
    for mem in memories:
        if set(mem.get("keywords", [])) == set(clean_kw) and mem.get("global", False) == is_global:
            mem["note"] = note
            mem["updated_at"] = time.strftime("%Y-%m-%d %H:%M")
            MEMORY_FILE.write_text(json.dumps(memories, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            return
    memories.append({
        "keywords": clean_kw,
        "note": note,
        "global": is_global,
        "added_at": time.strftime("%Y-%m-%d %H:%M")
    })
    MEMORY_FILE.write_text(json.dumps(memories, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def get_relevant_memories(app_id: str, title: str) -> list[str]:
    combined = f"{app_id} {title}".lower()
    relevant = []
    for mem in load_memories():
        if mem.get("global", False):
            relevant.append(f"- [Info générale] {mem['note']}")
        elif any(kw in combined for kw in mem.get("keywords", [])):
            relevant.append(f"- [Contexte connu ({', '.join(mem['keywords'])})] {mem['note']}")
    return relevant


def save_last_context(app_id: str, title: str, line: str):
    try:
        LAST_CTX_FILE.write_text(json.dumps({
            "timestamp": time.time(),
            "app_id": app_id,
            "title": title,
            "last_line": line
        }, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def load_last_context() -> dict:
    if LAST_CTX_FILE.exists():
        try:
            data = json.loads(LAST_CTX_FILE.read_text(encoding="utf-8"))
            if time.time() - data.get("timestamp", 0) < 600:
                return data
        except Exception:
            pass
    win = get_active_window()
    return {
        "timestamp": time.time(),
        "app_id": win.get("app_id", "inconnu"),
        "title": win.get("title", "Bureau"),
        "last_line": f"(Aucune remarque récente, {USER_NAME} te parle spontanément)"
    }


# --- APPEL API ---
def call_llm(sys_prompt: str, user_content: list | str, max_tokens: int = 280) -> dict:
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_content}
        ],
        "temperature": 0.7,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"}
    }
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY}",
            "User-Agent": "KiraCompanionWin/3.0"
        },
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        raw_reply = data["choices"][0]["message"]["content"].strip()
        if raw_reply.startswith("```"):
            raw_reply = raw_reply.strip("`").removeprefix("json").strip()
        try:
            return json.loads(raw_reply)
        except json.JSONDecodeError:
            fixed = re.sub(
                r'("line"\s*:\s*")(.*?)("\s*[,}])',
                lambda m: m.group(1) + m.group(2).replace('"', "« ") + m.group(3),
                raw_reply,
                flags=re.DOTALL
            )
            return json.loads(fixed)


# --- CHATBOX DE RÉPONSE PERSONNALISÉE ---
class ReplyDialog(QDialog):
    def __init__(self, last_line: str, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Dialog
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        container = QWidget(self)
        container.setObjectName("box")
        container.setFixedWidth(420)

        vbox = QVBoxLayout(container)
        vbox.setContentsMargins(16, 14, 16, 14)
        vbox.setSpacing(10)

        quote = QLabel(f"Rika : « {last_line} »")
        quote.setWordWrap(True)
        quote.setFont(QFont("Consolas", 9))
        quote.setStyleSheet("color: #a6adc8; border: none; background: transparent;")

        self.input = QLineEdit()
        self.input.setPlaceholderText("Ta réponse à Rika... (Entrée = envoyer, Échap = fermer)")
        self.input.setFont(QFont("Consolas", 10))
        self.input.returnPressed.connect(self.accept)

        vbox.addWidget(quote)
        vbox.addWidget(self.input)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(container)

        self.setStyleSheet("""
            QWidget#box {
                background-color: rgba(24, 24, 30, 245);
                border: 1px solid #45475a;
                border-radius: 12px;
            }
            QLineEdit {
                background-color: rgba(17, 17, 23, 230);
                color: #f2f2f7;
                border: 1px solid #585b70;
                border-radius: 8px;
                padding: 8px 10px;
                selection-background-color: #f9e2af;
                selection-color: #11111b;
            }
            QLineEdit:focus {
                border: 1px solid #f9e2af;
            }
        """)

    def showEvent(self, event):
        super().showEvent(event)
        self.adjustSize()
        screen = get_active_screen_geometry()
        x = screen.right() - self.width() - 25
        y = screen.bottom() - self.height() - 190
        self.move(x, y)
        self.activateWindow()
        self.input.setFocus()


# --- INTERFACE GRAPHIQUE PYQT6 (MASCOTTE) ---
class MascotOverlay(QWidget):
    show_signal = pyqtSignal(str, str, str)
    prompt_reply_signal = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        self.bubble = QLabel()
        self.bubble.setWordWrap(True)
        self.bubble.setFixedWidth(320)
        self.bubble.setFont(QFont("Consolas", 10))
        self.bubble.setStyleSheet("""
            QLabel {
                background-color: rgba(24, 24, 30, 240);
                color: #f2f2f7;
                border: 1px solid #45475a;
                border-radius: 12px;
                padding: 14px;
            }
        """)

        self.sprite_label = QLabel()
        self.sprite_label.setAlignment(Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignCenter)
        self.movie = None

        layout.addWidget(self.bubble, alignment=Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self.sprite_label, alignment=Qt.AlignmentFlag.AlignBottom)

        self.hide_timer = QTimer(self)
        self.hide_timer.timeout.connect(self._on_timeout)

        self.show_signal.connect(self.display_mascot)
        self.prompt_reply_signal.connect(self.open_reply_dialog)

    def _on_timeout(self):
        if self.underMouse() or self.geometry().contains(QCursor.pos()):
            self.hide_timer.start(1500)
            return
        self.hide()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.open_reply_dialog()
        elif event.button() == Qt.MouseButton.RightButton:
            self.hide_timer.stop()
            self.hide()

    def display_mascot(self, pose: str, edge: str, line: str):
        if self.isVisible():
            self.hide()

        sprite_path = SPRITE_MAP.get(pose) or next(iter(SPRITE_MAP.values()), None)
        if self.movie:
            self.movie.stop()
            self.movie = None

        if sprite_path:
            if sprite_path.suffix.lower() == ".gif":
                self.movie = QMovie(str(sprite_path))
                self.movie.setScaledSize(QSize(150, 150))
                self.sprite_label.setMovie(self.movie)
                self.movie.start()
            else:
                pix = QPixmap(str(sprite_path)).scaled(
                    150, 150,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                self.sprite_label.setPixmap(pix)

        self.bubble.setText(line)
        self.bubble.adjustSize()
        self.adjustSize()

        screen = get_active_screen_geometry()
        x = screen.right() - self.width() - 20
        y = screen.bottom() - self.height() - 10
        if edge == "left":
            x = screen.left() + 20
        elif edge == "top":
            y = screen.top() + 20

        self.move(x, y)
        self.show()

        duration = max(12000, len(line) * 130)
        self.hide_timer.start(duration)

    def open_reply_dialog(self):
        if self.isVisible():
            self.hide_timer.start(60000)

        last_ctx = load_last_context()
        dlg = ReplyDialog(last_ctx.get("last_line", ""))
        if dlg.exec() == QDialog.DialogCode.Accepted:
            text = dlg.input.text().strip()
            if text:
                threading.Thread(target=process_reply, args=(text, self), daemon=True).start()


# --- LOGIQUE CERVEAU ---
def build_system_prompt(force_fact: bool, random_theme: str, memories: list[str]) -> str:
    fallback_rule = (
        f'Si l\'écran est banal ou répétitif, NE TE TAIS PAS : mets "should_speak": true et lance une remarque spontanée sur ce thème : « {random_theme} ».'
        if force_fact else
        'Si l\'écran est banal, vide ou n\'a rien de nouveau à commenter, mets "should_speak": false.'
    )
    memory_block = ""
    if memories:
        memory_block = f"\n## Ce que tu sais déjà (appris lors de tes échanges passés avec {USER_NAME}) :\n" + "\n".join(memories) + "\nUtilise naturellement ce contexte si tu parles de sa fenêtre active !\n"

    return f"""Tu es Rika (Kira), la mascotte pixel-art qui vit sur le bureau de {USER_NAME}.
Tu observes sa fenêtre active et sa capture d'écran.
{memory_block}
## Tes 3 modes de réaction (par ordre de priorité) :
1. **Texte japonais détecté à l'écran (Twitter/X, Manga, Anime, Web) :**
   - Choisis UN SEUL kanji, mot de vocabulaire ou tournure grammaticale visible à l'écran et fais un mini-point d'apprentissage rapide (mot en japonais, lecture kana/rômaji et sens).
2. **Activité intéressante à l'écran (Code, DevOps, Jeu, Site connu dans ta mémoire, Vidéo, Erreur) :**
   - Fais une remarque pertinente, complice ou taquine sur ce qu'il fait exactement.
3. **Écran banal / Rien de spécial :**
   - {fallback_rule}

## Règles de format :
- Tutoiement obligatoire, ton naturel, vif et familier.
- Longueur : 15 à 40 mots maximum. Pas de backticks (`) ni de guillemets doubles à l'intérieur de ta phrase.

Réponds UNIQUEMENT en JSON brut :
{{
  "should_speak": true,
  "pose": "choisie parmi : {', '.join(POSES)}",
  "edge": "bottom, right, left ou top",
  "line": "Ta réplique ici"
}}"""


def trigger_once(overlay: MascotOverlay, force: bool = False):
    if not force and overlay.isVisible():
        return

    win = get_active_window()
    title = win.get("title", "Bureau")
    app_id = win.get("app_id", "inconnu")

    combined = f"{title} {app_id}".lower()
    is_sensitive = any(kw in combined for kw in BLACKLIST_KEYWORDS)

    img_b64 = "" if is_sensitive else get_smart_crop_b64(app_id, title)
    force_fact = True if force else random.choice([True, False])
    memories = get_relevant_memories(app_id, title)

    context = (
        f"Heure : {time.strftime('%H:%M')}\n"
        f"Application active : {app_id}\n"
        f"Titre de la fenêtre : {title}"
    )

    try:
        sys_prompt = build_system_prompt(force_fact, random.choice(THEMES_INTERETS), memories)
        user_content = [{"type": "text", "text": context}]
        if img_b64:
            user_content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}
            })

        decision = call_llm(sys_prompt, user_content)
        print(f"[Debug IA | Force={force} | Mem={len(memories)}] {decision}")
        if decision.get("should_speak", False) or force:
            line = decision.get("line", "...")
            save_last_context(app_id, title, line)
            overlay.show_signal.emit(
                decision.get("pose", "smug-hand-raised"),
                decision.get("edge", "bottom"),
                line
            )
    except Exception as e:
        print(f"[Erreur IA] {e}")


def process_reply(user_msg: str, overlay: MascotOverlay):
    last_ctx = load_last_context()
    app_id = last_ctx.get("app_id", "inconnu")
    title = last_ctx.get("title", "Bureau")
    last_line = last_ctx.get("last_line", "")

    sys_prompt = f"""Tu es Rika (Kira), la mascotte pixel-art sur le PC de {USER_NAME}.
{USER_NAME} vient de te répondre suite à ta dernière apparition.

Ta mission :
1. Lui répondre directement avec ton caractère vif, complice et familier (15 à 35 mots max, tutoiement, sans guillemets doubles internes).
2. Déterminer si son message contient une explication utile à retenir pour le futur (site, jeu comme Wiki Master, manga, projet, préférence).
   - Si OUI : mets "should_memorize": true, rédige une "memory_note" concise, et extrais 1 à 3 "keywords" en minuscules (SANS ".com"/".fr" et SANS le nom générique du navigateur ou plateforme comme firefox, chrome, mangadex, youtube si la note porte sur une oeuvre précise). Si c'est une info générale sur {USER_NAME}, mets "is_global": true et "keywords": [].
   - Si NON (simple blague/compliment) : mets "should_memorize": false.

Réponds UNIQUEMENT en JSON brut :
{{
  "pose": "choisie parmi : {', '.join(POSES)}",
  "edge": "bottom",
  "line": "Ta réponse immédiate à {USER_NAME}",
  "should_memorize": true,
  "is_global": false,
  "keywords": ["mot-cle"],
  "memory_note": "Résumé à retenir"
}}"""

    user_prompt = (
        f"Fenêtre concernée : {app_id} | Titre : {title}\n"
        f"Ce que tu venais de lui dire : « {last_line} »\n"
        f"Réponse de {USER_NAME} : « {user_msg} »"
    )

    try:
        res = call_llm(sys_prompt, user_prompt, max_tokens=350)
        print(f"[Debug Reply] {res}")
        if res.get("should_memorize") and res.get("memory_note"):
            save_memory_entry(res.get("keywords", []), res["memory_note"], res.get("is_global", False))
        reply_line = res.get("line", "C'est noté !")
        save_last_context(app_id, title, reply_line)
        overlay.show_signal.emit(res.get("pose", "thinking-pose"), res.get("edge", "bottom"), reply_line)
    except Exception as e:
        print(f"[Erreur Reply] {e}")


def daemon_loop(overlay: MascotOverlay):
    while True:
        wait_time = random.randint(MIN_COOLDOWN, MAX_COOLDOWN)
        print(f"[Timer] Prochaine apparition dans {wait_time // 60}m{wait_time % 60:02d}s")
        time.sleep(wait_time)
        trigger_once(overlay, force=False)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    overlay = MascotOverlay()

    tray = QSystemTrayIcon()
    default_icon = SPRITE_MAP.get("smug-hand-raised") or next(iter(SPRITE_MAP.values()), None)
    if default_icon:
        tray.setIcon(QIcon(str(default_icon)))
    tray.setToolTip("Rika / Kira Companion")

    def open_memory_viewer():
        viewer = BASE_DIR / "Memory_viewer" / "memory_viewer.py"
        if not viewer.exists():
            viewer = PROJECT_DIR / "Memory_viewer" / "memory_viewer.py"
        subprocess.Popen([sys.executable, str(viewer)])

    menu = QMenu()
    act_poke = QAction("Appeler Rika (Ctrl+Alt+K)", menu)
    act_poke.triggered.connect(lambda: threading.Thread(target=trigger_once, args=(overlay, True), daemon=True).start())
    act_reply = QAction("Répondre à Rika (Ctrl+Alt+R)", menu)
    act_reply.triggered.connect(overlay.prompt_reply_signal.emit)
    act_mem = QAction("🧠 Gérer la mémoire", menu)
    act_mem.triggered.connect(open_memory_viewer)
    act_quit = QAction("Quitter", menu)
    act_quit.triggered.connect(app.quit)

    menu.addAction(act_poke)
    menu.addAction(act_reply)
    menu.addAction(act_mem)
    menu.addSeparator()
    menu.addAction(act_quit)
    tray.setContextMenu(menu)
    tray.show()

    keyboard.add_hotkey("ctrl+alt+k", lambda: threading.Thread(target=trigger_once, args=(overlay, True), daemon=True).start())
    keyboard.add_hotkey("ctrl+alt+r", lambda: overlay.prompt_reply_signal.emit())
    try:
        keyboard.add_hotkey("left windows+shift+f23", lambda: threading.Thread(target=trigger_once, args=(overlay, True), daemon=True).start())
        keyboard.add_hotkey("ctrl+left windows+shift+f23", lambda: overlay.prompt_reply_signal.emit())
    except Exception:
        pass

    threading.Thread(target=daemon_loop, args=(overlay,), daemon=True).start()
    print("Démon Rika Windows démarré ! (Ctrl+Alt+K : Appeler | Ctrl+Alt+R ou Clic gauche sur Rika : Répondre)")
    sys.exit(app.exec())