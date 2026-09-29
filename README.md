```
Message perso avant le blabla bien IA : Ouai c'est bien vibecode a la mort, 
J'ai mis une partie sur les crédits des sprite mais ils sont de base généré par IA
Donc bon, c'est juste histoire de faire genre.
Bonne journée.

PS: Rika ou Kira je sais toujours pas, c'est pour ça qu'il ya des fichiers au deux noms,
    un jour je me déciderais
```

# 🦊 MascotRika (Kira Companion)

Compagnon de bureau IA multimodal (Vision + Mémoire contextuelle persistante) capable d'observer la fenêtre active, de réagir à ce que tu fais (code, lecture de manga, apprentissage du japonais sur le web, jeux) et de retenir tes préférences au fil de vos discussions.

Le projet fonctionne sur **Linux (Wayland / Niri)** via l'interface native d'**iNiR**, ainsi que sur **Windows** grâce à une réimplémentation graphique autonome en **PyQt6** (compatible multi-écrans).

### 🎲 Fonctionnement des apparitions & Logique du « 50/50 »
À intervalle régulier (toutes les 7 à 15 minutes par défaut), Rika analyse le titre de ta fenêtre active et prend une capture d'écran recadrée :
1. **S'il se passe quelque chose d'intéressant** (texte japonais détecté à l'écran, code, jeu, erreur, site connu dans sa mémoire), elle apparaît pour réagir directement dessus ou t'expliquer un mot de vocabulaire japonais visible sur ta page.
2. **Si l'écran est banal, vide ou répétitif :** Pour éviter d'être trop envahissante, le script tire à **pile ou face (1 chance sur 2)** :
   * **50 % de chance qu'elle se taise :** Elle met `"should_speak": false` et n'apparaît pas du tout sur ce cycle.
   * **50 % de chance qu'elle lance un sujet spontané :** Elle apparaît avec une anecdote, une astuce technique ou un point de japonais pioché aléatoirement dans ta liste `THEMES_INTERETS`.
   *(Note : si tu l'appelles manuellement via son raccourci clavier, ce tirage est ignoré et elle te répond à 100 %).*

### 💬 Système de réponse & Tri intelligent de la mémoire
Tu peux répondre directement à Rika (via raccourci clavier ou en cliquant sur elle) suite à sa dernière réplique ou pour lui expliquer ce qu'il y a sur ton écran. À chaque message envoyé, elle te répond à la volée et décide toute seule comment classer l'information dans `kira_memory.json` :

* **🪟 Mémoire liée à une fenêtre (`is_global: false`) :** Si tu lui expliques ce qu'est un site précis, un jeu, l'avancement d'un manga ou un projet en cours, elle résume l'info et génère **1 à 3 mots-clés déclencheurs** (`keywords`). Ce souvenir ne sera injecté dans son prompt que lorsque tu auras une fenêtre active contenant l'un de ces mots-clés dans son titre.
* **🌍 Mémoire globale (`is_global: true`) :** Si tu lui confies une information générale sur toi ou tes goûts qui n'est pas liée à une application particulière, elle l'enregistre sans mot-clé (`keywords: []`). Cette note sera **toujours** envoyée à Rika, peu importe ta fenêtre active.
* **🗑️ Information ignorée (`should_memorize: false`) :** Si ton message est une simple blague, un salut ou une remarque qui n'a pas d'intérêt à être retenue pour le futur, elle te répondra naturellement mais **n'enregistrera rien** dans le fichier JSON pour ne pas polluer sa mémoire.

---

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
│   ├── kira_memory.json        # Base de connaissances locale (créée auto, ignorée par Git)
│   └── token                   # Clé API personnelle (à créer, ignorée par Git)
├── .gitignore
└── README.md
```

> 💡 **Note sur `kira_memory.json` :** Tu n'as pas besoin de créer ce fichier manuellement après avoir cloné le projet. Il sera **généré automatiquement** dès que Rika mémorisera une première information (ou dès ton premier ajout via le *Memory Viewer*).

---

## 🚀 1. S'approprier le projet (Installation commune)

### A. Cloner le dépôt

```bash
git clone [https://github.com/logan17111/rikamascot.git](https://github.com/logan17111/rikamascot.git)
cd rikamascot
```

### B. Configurer la clé API (`token`)

Pour des raisons de sécurité, aucune clé API n'est présente dans le code.

1. **Méthode recommandée :** Crée un fichier nommé `token` (sans extension) dans le dossier `MascotInir/` et colle directement ta clé API dedans :
   ```bash
   echo "ta-cle-api-ici" > MascotInir/token
   ```
2. **Alternative (Variable d'environnement) :** Si le fichier `token` n'existe pas, le script cherche la variable d'environnement `REQUESTY_API_KEY` sur ton système. Elle porte ce nom car j'utilise personnellement Requesty, mais si tu as la motivation, tu peux tout à fait la renommer partout dans le code (`kira_brain.py` et `rika_windows.py`).

### C. Variables personnalisables & Adaptation des prompts

En haut des fichiers `MascotInir/kira_brain.py` (Linux) et `MascotInir/rika_windows.py` (Windows), tu peux adapter la configuration à ton setup :

| Variable | Description | Valeur par défaut |
| :--- | :--- | :--- |
| `USER_NAME` | Ton prénom ou pseudo (utilisé par Rika pour s'adresser à toi et mémoriser des notes) | `"Utilisateur"` |
| `API_URL` | J'utilise **Requesty** par défaut, mais n'importe quel autre routeur ou endpoint compatible OpenAI (OpenRouter, LiteLLM, Ollama local, etc.) fonctionne normalement sans problème | `"https://router.requesty.ai/v1/chat/completions"` |
| `MODEL` | Modèle multimodal (avec support vision) à interroger | `"vertex/gemini-2.5-flash@europe-west1"` |
| `MIN_COOLDOWN` / `MAX_COOLDOWN` | Intervalle aléatoire (en secondes) entre deux apparitions spontanées | `420` (7 min) / `900` (15 min) |
| `THEMES_INTERETS` | Liste des sujets spontanés (japonais, Linux, DevOps, manga/JRPG) quand l'écran est banal | Liste de chaînes Python |
| `BLACKLIST_KEYWORDS` | Mots-clés dans le titre de fenêtre qui **bloquent la capture d'écran** par confidentialité | `["bitwarden", "keepass", "1password", "navigation privée", "banque", ...]` |

* **Personnalisation des prompts IA :** Les consignes qui définissent le caractère de Rika, sa façon de parler et ses priorités d'analyse (apprentissage du japonais, réaction aux écrans, règles de mémorisation) se trouvent dans les fonctions `build_system_prompt()` et `handle_reply()` / `process_reply()`. Elles sont 100 % adaptables à chacun : n'hésite pas à modifier le texte du prompt dans le code pour changer sa personnalité ou ses centres d'intérêt.

---

## 🐧 2. Utilisation sur Linux (Wayland / Niri)

> ⚠️ **Prérequis obligatoire — Projet iNiR :**
> Sur Linux, ce script n'embarque pas sa propre fenêtre graphique : il pilote directement le module mascotte du projet **[iNiR](https://github.com/snowarch/iNiR)** (environnement **Quickshell** conçu pour le compositeur Wayland **Niri**).
> **Sans Niri et iNiR installés et actifs (`inir mascot ...` et `niri msg ...`), `kira_brain.py` ne pourra pas fonctionner.**

### Dépendances Linux

* **Niri** (compositeur Wayland) + **[iNiR](https://github.com/snowarch/iNiR)** (Quickshell)
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

### Ajouter les raccourcis clavier dans la config Niri / iNiR

Pour appeler Rika ou lui répondre à la volée sous Linux, ajoute ces raccourcis dans ta configuration Niri (par exemple dans `~/.config/niri/config.kdl` ou dans le fichier de raccourcis personnalisés d'iNiR comme `~/.config/niri/config.d/90-user-extra.kdl`) en adaptant le chemin vers ton dossier :

```kdl
binds {
    // Appeler Rika manuellement (Ctrl + Alt + K)
    Ctrl+Alt+K { spawn "python3" "/home/TON_USER/Documents/MascotRika/MascotInir/kira_brain.py" "--once"; }

    // Ouvrir la boîte de réponse pour parler à Rika (Ctrl + Alt + R)
    Ctrl+Alt+R { spawn "python3" "/home/TON_USER/Documents/MascotRika/MascotInir/kira_brain.py" "--reply"; }
}
```
*(Si ton clavier possède une touche Copilot qui envoie `Super+Shift+F23`, tu peux aussi remplacer `Ctrl+Alt+K` par `Mod+Shift+F23` et `Ctrl+Alt+R` par `Ctrl+Mod+Shift+F23`).*

### Lancer en tâche de fond sur Linux (`systemd`)

Crée un service utilisateur `~/.config/systemd/user/kira-brain.service` (en adaptant le chemin `ExecStart` si besoin) :

```ini
[Unit]
Description=Démon Rika/Kira Companion pour iNiR
After=graphical-session.target

[Service]
ExecStart=/usr/bin/python3 %h/Documents/MascotRika/MascotInir/kira_brain.py
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

Pour exécuter Rika sans fenêtre de console (`pythonw.exe`) et créer un raccourci dans le démarrage automatique de Windows (`shell:startup`), lance dans PowerShell (en adaptant le chemin vers ton `pythonw.exe` si nécessaire) :

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
  L'intégralité des illustrations, sprites et animations composant la mascotte (`inir-mascot-*`) ainsi que le concept d'intégration originale sous Wayland proviennent du projet **[iNiR](https://github.com/snowarch/iNiR)**.
* **Clause de non-affiliation :**
  Ce dépôt est un projet personnel et communautaire ajoutant une couche d'intelligence artificielle (LLM + Vision + Mémoire) et un portage PyQt6 pour Windows. Je ne revendique aucun droit d'auteur sur les œuvres graphiques de la mascotte.
* **Usage :**
  Le code Python de ce dépôt est partagé à titre éducatif et personnel (open-source). Les images et ressources graphiques associées restent soumises aux droits et à la licence de leurs créateurs respectifs au sein du projet **[iNiR](https://github.com/snowarch/iNiR)**. Si vous êtes l'auteur original des visuels et souhaitez leur retrait de ce dépôt au profit d'un script de téléchargement externe, n'hésitez pas à ouvrir une *Issue*.