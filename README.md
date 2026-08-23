# swfx-launcher

Un lanceur graphique GTK4 pour **SyndWarsFX**, le portage libre de
*Syndicate Wars* (Bullfrog, 1996).
A GTK4 launcher for **SyndWarsFX**, the open source port of Bullfrog's
*Syndicate Wars* (1996).

---

## Remerciements / Credits

Ce projet n'existerait pas sans le travail du portage lui-même :
[swfans/syndwarsfx](https://github.com/swfans/syndwarsfx), lui-même
continuation du portage original créé par **Unavowed** et **Gynvael
Coldwind**. Merci à **mefistotelis**, **Moburma**, **geist22** et à tous les
contributeurs pour un travail de rétro-ingénierie considérable, ainsi que
pour la documentation du wiki et les discussions dans les tickets, dont
plusieurs ont directement guidé ce lanceur.

This launcher owes everything to the port itself:
[swfans/syndwarsfx](https://github.com/swfans/syndwarsfx), a continuation of
the original port by **Unavowed** and **Gynvael Coldwind**. Thanks to
**mefistotelis**, **Moburma**, **geist22** and every contributor for an
enormous reverse-engineering effort, and for the wiki and issue discussions
that directly informed several decisions here.

Ce lanceur est un projet indépendant, sans lien avec Electronic Arts.

---

## Français

### À quoi ça sert

SyndWarsFX se configure par deux fichiers texte, `config.ini` et
`conf/rules.ini`, plus une poignée d'options de ligne de commande. Ces
réglages sont puissants mais peu pardonnants : une résolution que votre
écran n'expose pas empêche le démarrage, une valeur trop haute ferme le jeu
au chargement d'une mission, et certaines options se contredisent
silencieusement.

Le lanceur expose seulement ce qui fonctionne réellement, en refusant les
combinaisons qui échouent, et explique chaque choix directement dans
l'interface.

### Fonctionnalités

- Résolution de la vue de mission, plein écran ou fenêtré
- Liste des résolutions construite depuis `xrandr` : impossible de choisir un
  mode que votre écran n'expose pas
- Préservation des proportions sur les écrans panoramiques, appliquée avant
  le lancement et restaurée automatiquement à la fermeture du jeu
- Traitement des vidéos : agrandies à l'écran, ou dans un mode 4:3 dédié
- Champ de vision sur une échelle de 1 à 10, écrite dans `rules.ini`
- Affichage de la santé des cibles
- Saut de l'intro, lancement direct d'une mission, options avancées
- Sauvegarde automatique en `.bak` avant chaque écriture, et bouton de
  restauration
- Consultation de `error.log` depuis l'interface
- Interface en français et en anglais

### Prérequis

- Linux avec X11 (le réglage des proportions passe par `xrandr`)
- Python 3.8 ou plus récent
- GTK 4 et ses liaisons Python
- SyndWarsFX déjà installé et fonctionnel

```bash
sudo apt install python3-gi gir1.2-gtk-4.0 x11-xserver-utils
```

Sur Fedora :

```bash
sudo dnf install python3-gobject gtk4 xrandr
```

### Installation

```bash
git clone https://github.com/neurocontrarian/swfx-launcher.git
cd swfx-launcher
chmod +x swfx-launcher.py
python3 swfx-launcher.py
```

Au premier démarrage, le lanceur cherche le jeu dans `~/games/syndwarsfx`.
Si votre installation est ailleurs, utilisez le bouton **Dossier du jeu…**
dans la barre de titre. Le chemin est mémorisé dans
`~/.config/swfx-launcher.json`.

Pour un raccourci dans le menu des applications, créez
`~/.local/share/applications/swfx-launcher.desktop` :

```ini
[Desktop Entry]
Type=Application
Name=SyndWarsFX Launcher
Exec=python3 /chemin/vers/swfx-launcher.py
Icon=/chemin/vers/syndwarsfx/syndwarsfx_icon.png
Categories=Game;
Terminal=false
```

---

## English

### What it does

SyndWarsFX is configured through two text files, `config.ini` and
`conf/rules.ini`, plus a handful of command line options. Those settings are
powerful but unforgiving: a resolution your screen does not expose prevents
startup, a value that is too tall closes the game when a mission loads, and
some options silently contradict each other.

This launcher exposes only what actually works, refuses combinations that
fail, and explains each choice inside the interface.

### Features

- Mission view resolution, fullscreen or windowed
- Resolution list built from `xrandr`, so an unsupported mode cannot be picked
- Aspect ratio preservation on widescreen displays, applied before launch and
  restored automatically when the game exits
- Video handling: enlarged to fit the screen, or in a dedicated 4:3 mode
- Field of view on a 1 to 10 scale, written to `rules.ini`
- Target health display
- Skip intro, start a specific mission, advanced options
- Automatic `.bak` backup before every write, with a restore button
- `error.log` viewer built in
- French and English interface

### Requirements

- Linux with X11 (aspect handling relies on `xrandr`)
- Python 3.8 or newer
- GTK 4 with Python bindings
- A working SyndWarsFX installation

```bash
sudo apt install python3-gi gir1.2-gtk-4.0 x11-xserver-utils
```

### Installation

```bash
git clone https://github.com/neurocontrarian/swfx-launcher.git
cd swfx-launcher
chmod +x swfx-launcher.py
python3 swfx-launcher.py
```

On first run the launcher looks for the game in `~/games/syndwarsfx`. Use the
**Game folder…** button in the title bar if yours lives elsewhere. The path is
remembered in `~/.config/swfx-launcher.json`.

---

## Découvertes techniques / Technical findings

Cette section documente ce que des essais successifs ont établi sur le
comportement du port. Elle existe pour éviter que quiconque — humain ou
assistant de code — refasse ce chemin.

This section records what repeated testing established about the port's
behaviour. It exists so that nobody — human or coding assistant — has to
rediscover any of it.

### 1. Le plein écran exige un vrai mode d'affichage

En plein écran, le port demande à la carte graphique un mode réel. Un mode
absent de la liste du pilote fait échouer le démarrage avec, dans
`error.log` :

```
LbScreenSetupAnyMode: full screen resolution 1440x1080 (mode 29) not available
```

**Piège** : calculer une résolution « idéale » (par exemple 1440×1080 pour un
pillarbox 4:3 sur un écran 1440 de haut) sans vérifier qu'elle existe. Le
lanceur construit donc ses listes depuis `xrandr`.

*Fullscreen requires a real display mode; modes absent from the driver's list
make startup fail. Always validate against `xrandr`.*

### 2. La déformation vient du moniteur, pas du jeu

Puisque la carte change réellement de mode, c'est le moniteur qui étale le
signal sur une dalle non 4:3. Vérifiable en lançant le jeu puis, depuis un
autre terminal, `xrandr | grep '\*'` : la résolution active est bien celle du
jeu.

Le correctif appartient à la sortie vidéo :

```bash
xrandr --output <sortie> --set "scaling mode" "Full aspect"
```

**Piège** : chercher la solution dans le code du jeu. Un correctif a été
tenté dans `LbScreenSwap()`, qui appelle `LbI_SDL_BlitScaled()` avec deux
`NULL` — toute la source vers toute la destination. Il n'a rien changé, pour
une raison logique : les deux surfaces ont le même ratio, l'étirement se
produit après, dans la chaîne d'affichage.

*The distortion happens in the display chain, not in the game. Fix it on the
video output.*

### 3. La limite de résolution porte sur la hauteur

Le wiki indique que rien ne fonctionne au-delà de 1080p. La mesure est plus
précise : **c'est la hauteur qui compte, pas le nombre de pixels**.

| Résolution | Résultat |
|---|---|
| 1920×1080 | fonctionne |
| 2560×1080 | fonctionne — plus de pixels, même hauteur |
| 3440×1440 | intro et menus passent, le processus est tué au chargement du niveau |

Le plantage ne laisse aucune trace dans `error.log`.

*The renderer is bound by height, not pixel count. 2560×1080 works; 3440×1440
kills the process when a level loads, silently.*

### 4. Les menus ne sont pas mis à l'échelle

`ResMenu` peut recevoir une valeur plus haute que son défaut de 640×480, mais
le port dessine les éléments à taille fixe. Résultat : aucun gain de netteté,
du texte plus petit à l'écran, et au-delà de 1280×960 les inscriptions
sortent du cadre. Le lanceur laisse donc `ResMenu` à 640×480.

Vérifié par comparaison de captures : les caractères ont exactement la même
taille en pixels dans les deux cas.

*Menu elements are drawn at a fixed pixel size. Raising `ResMenu` gains
nothing and breaks past 1280×960.*

### 5. Le mode fenêtré ne passe que par `-W`

La bibliothèque accepte une syntaxe de mode fenêtré dans `config.ini`, avec un
`w` à la place du second `x` — par exemple `1280x960w8`. Elle est inopérante :
au démarrage, `display_set_full_screen()` parcourt tous les modes enregistrés
et force l'indicateur selon un unique réglage global.

*The `w` suffix in `config.ini` is overridden at startup. Only `-W` works.*

### 6. L'option `-S` fige le jeu en plein écran

`-S` désactive l'agrandissement du 320×200. Le port réclame alors un mode
d'affichage 320×200 réel, que les écrans modernes n'exposent pas, et se fige.
L'image non déformée s'obtient autrement : par un mode 4:3, ou par le réglage
de la sortie vidéo décrit au point 2.

*`-S` asks for a real 320×200 display mode and freezes. Do not offer it.*

### 7. `ResGameLo` n'est pas une résolution concurrente

`ResGameHi` et `ResGameLo` désignent deux jeux de sprites d'interface, entre
lesquels on bascule **en jeu avec F8**. `ResGameLo` reste à 320×200 : y
écrire une haute résolution place des sprites basse définition dans une
grande surface.

Le mode d'écran se change aussi depuis l'écran d'options « Visual Depth ».

*They are two HUD sprite sets, switched in game with F8 — not two competing
resolutions.*

### 8. `config.ini` est lu de haut en bas

Une clé présente en double fait gagner la **dernière** valeur. Une écriture
naïve qui remplace la première occurrence sans supprimer les autres produit
donc des réglages fantômes. Le lanceur déduplique à chaque écriture.

*Duplicate keys mean the last value wins. Deduplicate when writing.*

### 9. Le zoom dépend de l'arme équipée

`ZoomMin` et `ZoomMax` ne fixent pas la vue : ils génèrent 28 niveaux dans
lesquels le jeu pioche selon la portée de l'arme en main. C'est `ZoomMax` qui
détermine ce que l'on voit en pratique — modifier `ZoomMin` seul ne change
presque rien.

D'après les mesures du ticket [#40](https://github.com/swfans/syndwarsfx/issues/40),
`ZoomMax=264` reproduit au plus près le jeu de 1996.

**À savoir** : aux vues très larges, le moteur d'origine montre ses limites.
Les encadrés de sélection et les numéros d'agents peuvent disparaître près des
bords, faute de place dans les tableaux de rendu — voir le ticket
[#255](https://github.com/swfans/syndwarsfx/issues/255) — et l'horizon peut se
replier sur lui-même. Ce ne sont pas des bugs du lanceur.

*Zoom values generate 28 levels indexed by weapon range. `ZoomMax` is what
matters. Very wide views expose known engine limits.*

### 10. Le nombre d'images par seconde n'est pas réglable

Découpler la vitesse du jeu du rendu fait l'objet du ticket
[#164](https://github.com/swfans/syndwarsfx/issues/164), ouvert et non
implémenté. Rien à exposer côté lanceur.

*Not configurable; tracked upstream in issue #164.*

---

## Notes de compilation du port / Building the port

Sans rapport direct avec le lanceur, mais utile à qui compile SyndWarsFX
depuis les sources sur une distribution récente :

- Le port se compile en **32 bits uniquement** (`-m32`), le code issu du
  désassemblage supposant des pointeurs de 4 octets.
- Sur les bases Ubuntu 24.04, **ne pas installer `libsdl1.2-dev`** : il tente
  de retirer des composants vitaux du système. Utiliser SDL2.
- Passer `--with-data-path` à `configure`, sinon le chemin des données est
  compilé en dur à une valeur inutilisable et le jeu ne trouve aucun fichier.
- Sur une distribution qui compile en **PIE par défaut**, le registre `ebx`
  — base du code indépendant de la position — est écrasé au retour de
  certaines enveloppes assembleur, ce qui corrompt l'adressage des variables
  globales. Compiler avec `-fno-pie` et lier avec `-no-pie`.

*The port builds 32-bit only; avoid `libsdl1.2-dev` on Ubuntu 24.04; always
pass `--with-data-path`; and build with `-fno-pie` / `-no-pie` on
PIE-by-default distributions.*

---

## Licence / License

GPL v3, cohérente avec le portage sur lequel ce lanceur s'appuie. Voir
[LICENSE](LICENSE).

*GPL v3, consistent with the port this launcher builds upon. See
[LICENSE](LICENSE).*
