#!/usr/bin/env python3
import json
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from smart_capture import get_smart_crop_b64

os.environ["PATH"] += os.pathsep + os.path.expanduser("~/.local/bin")

# --- CONFIGURATION À PERSONNALISER ---
USER_NAME = "Utilisateur"  # Ton prénom ou pseudo
MODEL = "vertex/gemini-2.5-flash@europe-west1"
API_URL = "https://router.requesty.ai/v1/chat/completions"

MIN_COOLDOWN = 7 * 60   # 7 minutes
MAX_COOLDOWN = 15 * 60  # 15 minutes

# --- CHEMINS ---
PROJECT_DIR = Path(__file__).resolve().parent
MEMORY_FILE = PROJECT_DIR / "kira_memory.json"
LAST_CTX_FILE = Path(tempfile.gettempdir()) / "kira_last_context.json"
LOG_FILE = Path(tempfile.gettempdir()) / "kira.log"


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
    "Astuce ou anecdote technique Linux, Wayland ou terminal",
    "Anecdote ou astuce DevOps / Sysadmin (Docker, Ansible, Terraform, réseau ou self-hosting)",
    "Anecdote geek sur la culture Manga / Anime ou le jeu vidéo (JRPG)"
]

MASCOT_DIR = PROJECT_DIR.parent / "images" / "mascot"
if not MASCOT_DIR.exists():
    MASCOT_DIR = Path.home() / ".config/quickshell/inir/assets/images/mascot"

POSES = sorted({
    f.stem.removeprefix("inir-mascot-")
    for f in MASCOT_DIR.glob("inir-mascot-*")
    if f.suffix in (".png", ".gif") and "expression-sheet" not in f.name
}) or ["smug-hand-raised", "tired-dev", "reading", "thinking-pose"]


# --- GESTION DE LA MÉMOIRE ---
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
            relevant.append(f"- [Contexte connu sur cette fenêtre ({', '.join(mem['keywords'])})] {mem['note']}")
    return relevant


def save_last_context(app_id: str, title: str, line: str):
    data = {
        "timestamp": time.time(),
        "app_id": app_id,
        "title": title,
        "last_line": line
    }
    try:
        LAST_CTX_FILE.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
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


# --- OUTILS SYSTÈME & API ---
def run_cmd(cmd: list[str]) -> str:
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
        return res.stdout.strip() if res.returncode == 0 else ""
    except Exception:
        return ""


def get_active_window() -> dict:
    raw = run_cmd(["niri", "msg", "-j", "focused-window"])
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except Exception:
        return {}


def is_mascot_busy_or_locked() -> bool:
    raw = run_cmd(["inir", "mascot", "status"])
    if not raw:
        return True
    try:
        st = json.loads(raw)
        return (
            st.get("showing", False)
            or st.get("suppressed", False)
            or st.get("screenTime", {}).get("userIdle", False)
        )
    except Exception:
        return False


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
            "User-Agent": "KiraCompanion/3.0"
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


def show_mascot(pose: str, edge: str, line: str):
    if pose not in POSES:
        pose = "smug-hand-raised"
    if edge not in ("right", "left", "top", "bottom"):
        edge = "bottom"
    clean_line = line.replace("`", "").strip()
    subprocess.run(["inir", "mascot", "appearWithLine", pose, edge, clean_line])


# --- MODE OBSERVATION (TIMER & COPILOT+K) ---
def build_system_prompt(force_fact: bool, random_theme: str, memories: list[str]) -> str:
    fallback_rule = (
        f'Si l\'écran est banal ou répétitif, NE TE TAIS PAS : mets "should_speak": true et lance une remarque spontanée sur ce thème : « {random_theme} ».'
        if force_fact else
        'Si l\'écran est banal, vide ou n\'a rien de nouveau à commenter, mets "should_speak": false.'
    )

    memory_block = ""
    if memories:
        memory_block = f"\n## Ce que tu sais déjà (appris lors de tes échanges passés avec {USER_NAME}) :\n" + "\n".join(memories) + "\nUtilise naturellement ce contexte si tu parles de sa fenêtre active !\n"

    return f"""Tu es Rika (Kira), la mascotte pixel-art qui vit sur le bureau Linux (Fedora/Niri) de {USER_NAME}.
Tu observes sa fenêtre active, son média et sa capture d'écran recadrée sur la zone clé.
{memory_block}
## Tes 3 modes de réaction (par ordre de priorité) :
1. **Texte japonais détecté à l'écran (Twitter/X, Manga, Anime, Web) :**
   - Lis attentivement les kanjis/phrases sur l'image.
   - Ne traduis JAMAIS tout le tweet ou toute la page.
   - Choisis UN SEUL kanji, mot de vocabulaire ou tournure grammaticale visible à l'écran et fais un mini-point d'apprentissage rapide : donne le mot en japonais, sa lecture (kana/rômaji) et sa signification ou nuance.
2. **Activité intéressante à l'écran (Code, DevOps, Jeu, Site connu dans ta mémoire, Vidéo, Erreur) :**
   - Fais une remarque pertinente, complice ou un peu taquine sur ce qu'il fait exactement (tu peux glisser un petit mot en japonais de temps en temps).
3. **Écran banal / Rien de spécial :**
   - {fallback_rule}

## Règles de format :
- Tutoiement obligatoire, ton naturel, vif et familier.
- Longueur : 15 à 40 mots maximum. Pas de balises Markdown ni de backticks (`).
- Pour "edge" : utilise "bottom" pour les poses debout/assises (street-*, chibi-*) et "right", "left" ou "top" pour les poses qui dépassent d'un bord.

Réponds UNIQUEMENT avec un objet JSON brut (sans ```json) :
{{
  "should_speak": true,
  "pose": "choisie parmi : {', '.join(POSES)}",
  "edge": "bottom, right, left ou top",
  "line": "Ta réplique ici"
}}"""


def trigger_once(force: bool = False):
    if not force and is_mascot_busy_or_locked():
        return

    win = get_active_window()
    title = win.get("title", "Bureau vide")
    app_id = win.get("app_id", "inconnu")

    combined = f"{title} {app_id}".lower()
    is_sensitive = any(kw in combined for kw in BLACKLIST_KEYWORDS)

    media = run_cmd(["playerctl", "metadata", "--format", "{{status}}: {{artist}} - {{title}}"])
    img_b64 = "" if is_sensitive else get_smart_crop_b64(app_id, title)
    force_fact = True if force else random.choice([True, False])
    memories = get_relevant_memories(app_id, title)

    context = (
        f"Heure : {time.strftime('%H:%M')}\n"
        f"Application active : {app_id}\n"
        f"Titre de la fenêtre : {title}\n"
        f"Média en cours : {media or 'Aucun'}"
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
        print(f"[Debug IA | ForceFact={force_fact} | Mem={len(memories)}] {decision}")
        if decision.get("should_speak", False) or force:
            line = decision.get("line", "...")
            save_last_context(app_id, title, line)
            show_mascot(decision.get("pose", "smug-hand-raised"), decision.get("edge", "bottom"), line)
    except Exception as e:
        print(f"[Erreur] {e}", file=sys.stderr)


# --- MODE RÉPONSE & APPRENTISSAGE (COPILOT+R) ---
def ask_user_reply_gui(last_line: str) -> str:
    if shutil.which("zenity"):
        res = subprocess.run(
            [
                "zenity", "--entry",
                "--title=Répondre à Rika",
                f"--text=Rika : « {last_line} »\n\nTa réponse ou explication à mémoriser :",
                "--width=500"
            ],
            capture_output=True, text=True
        )
        return res.stdout.strip() if res.returncode == 0 else ""

    for cmd in (["fuzzel", "--dmenu", "-p", "Rika > "], ["rofi", "-dmenu", "-p", "Rika"], ["wofi", "--dmenu", "-p", "Rika"]):
        if shutil.which(cmd[0]):
            res = subprocess.run(cmd, input="", capture_output=True, text=True)
            return res.stdout.strip() if res.returncode == 0 else ""
    return ""


def handle_reply(user_msg: str = ""):
    last_ctx = load_last_context()
    if not user_msg:
        user_msg = ask_user_reply_gui(last_ctx.get("last_line", ""))
    if not user_msg:
        return

    app_id = last_ctx.get("app_id", "inconnu")
    title = last_ctx.get("title", "Bureau")
    last_line = last_ctx.get("last_line", "")

    sys_prompt = f"""Tu es Rika (Kira), la mascotte pixel-art sur le bureau Linux de {USER_NAME}.
{USER_NAME} vient de te répondre suite à ta dernière apparition (ou pour t'apprendre quelque chose sur sa fenêtre actuelle).

Ta mission est double :
1. Lui répondre directement avec ton caractère vif, complice et familier (15 à 35 mots max, tutoiement, sans backticks).
2. Déterminer si son message contient une explication utile à retenir pour le futur (ex: expliquer ce qu'est un site/jeu comme Wiki Master, un projet, une habitude ou une préférence).
   - Si OUI : mets "should_memorize": true, rédige une "memory_note" claire et concise à la 3e personne, et extrais 1 à 3 "keywords" en minuscules (le nom du site, du jeu ou de l'outil visible dans le titre de la fenêtre ou son message, SANS ".com"/".fr"). Si c'est une info générale sur {USER_NAME} non liée à une fenêtre précise, mets "is_global": true et "keywords": [].
   - Si NON (simple blague ou salut) : mets "should_memorize": false.

Réponds UNIQUEMENT en JSON brut (sans ```json) :
{{
  "pose": "choisie parmi : {', '.join(POSES)}",
  "edge": "bottom, right, left ou top",
  "line": "Ta réponse immédiate à {USER_NAME}",
  "should_memorize": true,
  "is_global": false,
  "keywords": ["mot-cle-1"],
  "memory_note": "Résumé de ce qu'il faut retenir"
}}"""

    user_prompt = (
        f"Fenêtre concernée : {app_id} | Titre : {title}\n"
        f"Ce que tu venais de lui dire : « {last_line} »\n"
        f"Réponse de {USER_NAME} : « {user_msg} »"
    )

    try:
        res = call_llm(sys_prompt, user_prompt, max_tokens=350)
        print(f"[Debug Reply] {res}")
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            print(f"[{time.strftime('%H:%M:%S')}] Reply OK: {res}", file=f)

        if res.get("should_memorize") and res.get("memory_note"):
            save_memory_entry(
                res.get("keywords", []),
                res["memory_note"],
                res.get("is_global", False)
            )
            print(f"[Mémoire enregistrée] {res.get('keywords')} -> {res.get('memory_note')}")

        reply_line = res.get("line", "C'est noté !")
        save_last_context(app_id, title, reply_line)
        show_mascot(res.get("pose", "thinking-pose"), res.get("edge", "bottom"), reply_line)
    except Exception as e:
        print(f"[Erreur Reply] {e}", file=sys.stderr)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            print(f"[{time.strftime('%H:%M:%S')}] Erreur Reply: {e}", file=f)


if __name__ == "__main__":
    if "--reply" in sys.argv:
        idx = sys.argv.index("--reply")
        msg = " ".join(sys.argv[idx + 1:]) if idx + 1 < len(sys.argv) else ""
        handle_reply(msg)
    elif "--once" in sys.argv:
        trigger_once(force=True)
    else:
        print("Démon Rika/Kira v3 (avec mémoire) démarré...")
        while True:
            wait_time = random.randint(MIN_COOLDOWN, MAX_COOLDOWN)
            print(f"[Timer] Prochaine vérification dans {wait_time // 60}m{wait_time % 60:02d}s")
            time.sleep(wait_time)
            trigger_once(force=False)