## 📂 Structure du projet

```text
MascotRika/
├── images/
│   └── mascot/                 # Sprites et animations (.png / .gif) de la mascotte
├── MascotInir/
│   ├── Memory_viewer/
│   │   └── memory_viewer.py    # Interface graphique (PyQt6) de modération de la mémoire
│   ├── kira_brain.py           # Démon principal pour Linux (Niri + iNiR)
│   ├── smart_capture.py        # Découpage intelligent des captures d'écran (Linux)
│   ├── rika_windows.py         # Application complète autonome pour Windows (PyQt6)
│   ├── kira_memory.json        # Base de connaissances locale (ignorée par Git)
│   └── token                   # Clé API personnelle (ignorée par Git)
├── .gitignore
└── README.md

```

---

## 🚀 1. S'approprier le projet (Installation commune)

### A. Cloner le dépôt

```bash
git clone [https://github.com/TON_PSEUDO/MascotRika.git](https://github.com/TON_PSEUDO/MascotRika.git)
cd MascotRika

```

### B. Configurer la clé API (`token`)

Pour des raisons de sécurité, aucune clé API n'est présente dans le code.

1. Crée un fichier nommé `token` (sans extension) dans le dossier `MascotInir/` :
```bash
echo "ta-cle-api-ici" > MascotInir/token

```


2. *(Alternative)* Tu peux aussi définir la variable d'environnement `REQUESTY_API_KEY` sur ton système.

### C. Variables personnalisables dans le code

En haut des fichiers `MascotInir/kira_brain.py` (Linux) et `MascotInir/rika_windows.py` (Windows), tu peux adapter le comportement de Rika :

| Variable | Description | Valeur par défaut |
| --- | --- | --- |
| `USER_NAME` | Ton prénom ou pseudo (utilisé par Rika pour s'adresser à toi et mémoriser des notes) | `"Utilisateur"` |
| `API_URL` | URL de l'endpoint compatible OpenAI (Requesty, OpenRouter, Ollama, etc.) | `"https://router.requesty.ai/v1/chat/completions"` |
| `MODEL` | Modèle multimodal (avec support vision) à interroger | `"vertex/gemini-2.5-flash@europe-west1"` |
| `MIN_COOLDOWN` / `MAX_COOLDOWN` | Intervalle aléatoire (en secondes) entre deux apparitions spontanées | `420` (7 min) / `900` (15 min) |
| `THEMES_INTERETS` | Liste des sujets spontanés (japonais, Linux, DevOps, manga/JRPG) quand l'écran est banal | Liste de chaînes Python |
| `BLACKLIST_KEYWORDS` | Mots-clés dans le titre de fenêtre qui **bloquent la capture d'écran** par confidentialité | `["bitwarden", "keepass", "1password", "navigation privée", "banque", ...]` |

---

## 🐧 2. Utilisation sur Linux (Wayland / Niri)

> ⚠️ **Prérequis obligatoire — Projet iNiR :**
> Sur Linux, ce script n'embarque pas sa propre fenêtre graphique : il pilote directement le module mascotte du projet **[iNiR](https://www.google.com/search?q=https://github.com/snowarch/inir)** (environnement **Quickshell** conçu pour le compositeur Wayland **Niri**).
> **Sans Niri et iNiR installés et actifs (`inir mascot ...` et `niri msg ...`), `kira_brain.py` ne pourra pas fonctionner.**

### Dépendances Linux

* **Niri** (compositeur Wayland) + **iNiR** (Quickshell)
* Paquets système : `grim` (capture d'écran Wayland), `playerctl` (détection du média en cours), `zenity` (ou `fuzzel` / `rofi` / `wofi` pour la boîte de réponse)
* Python : `Pillow` (`pip install Pillow` ou `sudo dnf install python3-pillow`)

### Commandes de test (Linux)

* **Forcer une apparition immédiate (test) :**
```bash
python3 MascotInir/kira_brain.py --once

```


* **Ouvrir la boîte de dialogue pour répondre à Rika ou lui apprendre quelque chose :**
```bash
python3 MascotInir/kira_brain.py --reply

```


* **Lancer la boucle principale dans le terminal (avec logs) :**
```bash
python3 MascotInir/kira_brain.py

```



### Lancer en tâche de fond sur Linux (`systemd`)

Crée un service utilisateur `~/.config/systemd/user/kira-brain.service` :

```ini
[Unit]
Description=Démon Rika/Kira Companion pour iNiR
After=graphical-session.target

[Service]
ExecStart=/usr/bin/python3 %h/Documents/Projet/MascotRika/MascotInir/kira_brain.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target

```

Puis active-le :

```bash
systemctl --user daemon-reload
systemctl --user enable --now kira-brain.service

```

---

## 🪟 3. Utilisation sur Windows (Version autonome)

Sur Windows, `rika_windows.py` remplace Quickshell et Niri par une superposition **PyQt6** transparente sans bordure, compatible **multi-écrans** (Rika capture et apparaît automatiquement sur l'écran où se trouve ta fenêtre active).

### Dépendances Windows

Dans PowerShell :

```powershell
pip install PyQt6 Pillow pywin32 psutil keyboard

```

### Commandes de test & Contrôles (Windows)

Pour tester le script avec la console visible et suivre les retours de l'IA (`[Timer]`, `[Debug IA]`, `[Debug Reply]`) :

```powershell
python .\MascotInir\rika_windows.py

```

* **Appeler Rika manuellement :** `Ctrl + Alt + K` (ou touche `Copilot`)
* **Répondre à Rika (Chatbox sombre) :** `Ctrl + Alt + R` ou **Clic gauche directement sur Rika**
* **Fermer la bulle immédiatement :** **Clic droit** sur Rika
* **Mettre en pause la disparition :** Laisse le curseur de la souris sur la bulle ou le sprite
* **Menu System Tray :** Clic droit sur l'icône de Rika près de l'horloge Windows (`Appeler`, `Répondre`, `🧠 Gérer la mémoire`, `Quitter`).

### Lancer en tâche de fond et au démarrage de Windows

Pour exécuter Rika sans fenêtre de console (`pythonw.exe`) et créer un raccourci dans le démarrage automatique de Windows (`shell:startup`), lance dans PowerShell (en adaptant le chemin vers ton `pythonw.exe` et ton dossier) :

```powershell
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\RikaCompanion.lnk")
$Shortcut.TargetPath = "pythonw.exe"
$Shortcut.Arguments = '"' + (Resolve-Path ".\MascotInir\rika_windows.py").Path + '"'
$Shortcut.WorkingDirectory = (Resolve-Path ".\MascotInir").Path
$Shortcut.Save()

Start-Process "pythonw.exe" -ArgumentList ('"' + (Resolve-Path ".\MascotInir\rika_windows.py").Path + '"')

```

Pour arrêter ou relancer proprement le processus en tâche de fond :

```powershell
Stop-Process -Name "pythonw" -ErrorAction SilentlyContinue

```

---

## 🧠 4. Memory Viewer & Moderator (`memory_viewer.py`)

Le sous-projet `MascotInir/Memory_viewer/memory_viewer.py` est une interface graphique Desktop en **PyQt6** permettant d'administrer facilement le fichier `kira_memory.json` :

* **Recherche et filtrage instantanés** par mots-clés, texte de note ou portée (`Global` vs `Fenêtre spécifique`).
* **Détecteur de mots-clés polluants (⚠️) :** Signale en orange les tags trop génériques (`firefox`, `chrome`, `youtube`, `discord`, `mangadex`, etc.) qui déclencheraient un souvenir sur toutes les pages.
* **Simulateur de déclenchement en temps réel :** Permet de taper un faux titre de fenêtre pour voir immédiatement (en vert) quels souvenirs seront injectés dans le prompt de Rika.
* **Outils d'édition :** Ajout/suppression de tags en un clic, fusion de plusieurs notes sélectionnées et bouton **Annuler (Undo)** via sauvegarde `.json.bak`.

**Lancement direct :**

```bash
python MascotInir/Memory_viewer/memory_viewer.py

```

---

## ⚖️ Crédits, Attribution & Mentions Légales

* **Propriété des assets graphiques (`images/mascot/`) :**
L'intégralité des illustrations, sprites et animations composant la mascotte (`inir-mascot-*`) ainsi que le concept d'intégration originale sous Wayland proviennent du projet **[iNiR](https://www.google.com/search?q=https://github.com/snowarch/inir)**.
* **Clause de non-affiliation :**
Ce dépôt (`MascotRika`) est un projet personnel et communautaire ajoutant une couche d'intelligence artificielle (LLM + Vision + Mémoire) et un portage PyQt6 pour Windows. Je ne revendique aucun droit d'auteur sur les œuvres graphiques de la mascotte.
* **Usage :**
Le code Python de ce dépôt est partagé à titre éducatif et personnel (open-source). Les images et ressources graphiques associées restent soumises aux droits et à la licence de leurs créateurs respectifs au sein du projet **iNiR**. Si vous êtes l'auteur original des visuels et souhaitez leur retrait de ce dépôt au profit d'un script de téléchargement externe, n'hésitez pas à ouvrir une *Issue*.

```

```