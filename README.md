# swfx-launcher

Un lanceur graphique GTK4 pour **SyndWarsFX**, le portage libre de
*Syndicate Wars* (Bullfrog, 1996).
A GTK4 launcher for **SyndWarsFX**, the open source port of Bullfrog's
*Syndicate Wars* (1996).

**→ [English version](#english)**

---

## Français

### Remerciements

Ce projet n'existerait pas sans le travail du portage lui-même :
[swfans/syndwarsfx](https://github.com/swfans/syndwarsfx), lui-même
continuation du portage original créé par **Unavowed** et **Gynvael
Coldwind**. Merci à **mefistotelis**, **Moburma**, **geist22** et à tous les
contributeurs pour un travail de rétro-ingénierie considérable, ainsi que
pour la documentation du wiki et les discussions dans les tickets, dont
plusieurs ont directement guidé ce lanceur.

Ce lanceur est un projet indépendant, sans lien avec Electronic Arts.

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

#### Paquet Debian / Ubuntu / Mint

```bash
git clone https://github.com/neurocontrarian/swfx-launcher.git
cd swfx-launcher
./build-deb.sh
sudo apt install ./dist/swfx-launcher_0.1.0_all.deb
```

`apt` installe les dépendances tout seul et ajoute l'entrée dans le menu des
applications. Le lanceur se démarre ensuite par la commande `swfx-launcher`
ou depuis le menu. Pour le retirer : `sudo apt remove swfx-launcher`.

La construction du paquet ne demande que `dpkg-deb` et `gzip`, présents
partout sur ces distributions.

#### Depuis les sources

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

Pour un raccourci dans le menu des applications — inutile si vous avez
installé le paquet — créez
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

### Découvertes techniques

Cette section documente ce que des essais successifs ont établi sur le
comportement du port. Elle existe pour éviter que quiconque — humain ou
assistant de code — refasse ce chemin.

#### 1. Le plein écran exige un vrai mode d'affichage

En plein écran, le port demande à la carte graphique un mode réel. Un mode
absent de la liste du pilote fait échouer le démarrage avec, dans
`error.log` :

```
LbScreenSetupAnyMode: full screen resolution 1440x1080 (mode 29) not available
```

**Piège** : calculer une résolution « idéale » (par exemple 1440×1080 pour un
pillarbox 4:3 sur un écran 1440 de haut) sans vérifier qu'elle existe. Le
lanceur construit donc ses listes depuis `xrandr`.

#### 2. La déformation vient du moniteur, pas du jeu

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

#### 3. La limite de résolution porte sur la hauteur

Le wiki indique que rien ne fonctionne au-delà de 1080p. La mesure est plus
précise : **c'est la hauteur qui compte, pas le nombre de pixels**.

| Résolution | Résultat |
|---|---|
| 1920×1080 | fonctionne |
| 2560×1080 | fonctionne — plus de pixels, même hauteur |
| 3440×1440 | intro et menus passent, le processus est tué au chargement du niveau |

Le plantage ne laisse aucune trace dans `error.log`.

#### 4. Les menus ne sont pas mis à l'échelle

`ResMenu` peut recevoir une valeur plus haute que son défaut de 640×480, mais
le port dessine les éléments à taille fixe. Résultat : aucun gain de netteté,
du texte plus petit à l'écran, et au-delà de 1280×960 les inscriptions
sortent du cadre. Le lanceur laisse donc `ResMenu` à 640×480.

Vérifié par comparaison de captures : les caractères ont exactement la même
taille en pixels dans les deux cas.

#### 5. Le mode fenêtré ne passe que par `-W`

La bibliothèque accepte une syntaxe de mode fenêtré dans `config.ini`, avec un
`w` à la place du second `x` — par exemple `1280x960w8`. Elle est inopérante :
au démarrage, `display_set_full_screen()` parcourt tous les modes enregistrés
et force l'indicateur selon un unique réglage global.

#### 6. L'option `-S` fige le jeu en plein écran

`-S` désactive l'agrandissement du 320×200. Le port réclame alors un mode
d'affichage 320×200 réel, que les écrans modernes n'exposent pas, et se fige.
L'image non déformée s'obtient autrement : par un mode 4:3, ou par le réglage
de la sortie vidéo décrit au point 2.

#### 7. `ResGameLo` n'est pas une résolution concurrente

`ResGameHi` et `ResGameLo` désignent deux jeux de sprites d'interface, entre
lesquels on bascule **en jeu avec F8**. `ResGameLo` reste à 320×200 : y
écrire une haute résolution place des sprites basse définition dans une
grande surface.

Le mode d'écran se change aussi depuis l'écran d'options « Visual Depth ».

#### 8. `config.ini` est lu de haut en bas

Une clé présente en double fait gagner la **dernière** valeur. Une écriture
naïve qui remplace la première occurrence sans supprimer les autres produit
donc des réglages fantômes. Le lanceur déduplique à chaque écriture.

#### 9. Le zoom dépend de l'arme équipée

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

#### 10. Le nombre d'images par seconde n'est pas réglable

Découpler la vitesse du jeu du rendu fait l'objet du ticket
[#164](https://github.com/swfans/syndwarsfx/issues/164), ouvert et non
implémenté. Rien à exposer côté lanceur.

### Notes de compilation du port

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

### Licence

GPL v3, cohérente avec le portage sur lequel ce lanceur s'appuie. Voir
[LICENSE](LICENSE).

---

## English

### Credits

This launcher owes everything to the port itself:
[swfans/syndwarsfx](https://github.com/swfans/syndwarsfx), a continuation of
the original port by **Unavowed** and **Gynvael Coldwind**. Thanks to
**mefistotelis**, **Moburma**, **geist22** and every contributor for an
enormous reverse-engineering effort, and for the wiki and issue discussions
that directly informed several decisions here.

This launcher is an independent project, not affiliated with Electronic Arts.

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

On Fedora:

```bash
sudo dnf install python3-gobject gtk4 xrandr
```

### Installation

#### Debian / Ubuntu / Mint package

```bash
git clone https://github.com/neurocontrarian/swfx-launcher.git
cd swfx-launcher
./build-deb.sh
sudo apt install ./dist/swfx-launcher_0.1.0_all.deb
```

`apt` pulls the dependencies in and adds the application menu entry. The
launcher then starts with the `swfx-launcher` command or from the menu. To
remove it: `sudo apt remove swfx-launcher`.

Building the package needs only `dpkg-deb` and `gzip`, both present
everywhere on these distributions.

#### From source

```bash
git clone https://github.com/neurocontrarian/swfx-launcher.git
cd swfx-launcher
chmod +x swfx-launcher.py
python3 swfx-launcher.py
```

On first run the launcher looks for the game in `~/games/syndwarsfx`. Use the
**Game folder…** button in the title bar if yours lives elsewhere. The path is
remembered in `~/.config/swfx-launcher.json`.

To add a shortcut to the application menu — not needed if you installed the
package — create `~/.local/share/applications/swfx-launcher.desktop`:

```ini
[Desktop Entry]
Type=Application
Name=SyndWarsFX Launcher
Exec=python3 /path/to/swfx-launcher.py
Icon=/path/to/syndwarsfx/syndwarsfx_icon.png
Categories=Game;
Terminal=false
```

### Technical findings

This section records what repeated testing established about the port's
behaviour. It exists so that nobody — human or coding assistant — has to
rediscover any of it.

#### 1. Fullscreen requires a real display mode

In fullscreen, the port asks the graphics card for a real display mode. A
mode absent from the driver's list makes startup fail, with this in
`error.log`:

```
LbScreenSetupAnyMode: full screen resolution 1440x1080 (mode 29) not available
```

**Trap**: computing an "ideal" resolution (for example 1440×1080 for a 4:3
pillarbox on a 1440-tall screen) without checking that it actually exists.
The launcher therefore builds its lists from `xrandr`.

#### 2. The distortion comes from the monitor, not the game

Since the card really does switch mode, it is the monitor that stretches the
signal across a non-4:3 panel. This can be checked by starting the game,
then from another terminal running `xrandr | grep '\*'`: the active
resolution really is the game's.

The fix belongs to the video output:

```bash
xrandr --output <output> --set "scaling mode" "Full aspect"
```

**Trap**: looking for the fix in the game's code. A fix was attempted in
`LbScreenSwap()`, which calls `LbI_SDL_BlitScaled()` with two `NULL`s — the
whole source to the whole destination. It changed nothing, for a logical
reason: both surfaces already share the same ratio, so the stretching
happens afterwards, in the display chain.

#### 3. The resolution limit is on height

The wiki states that nothing works above 1080p. The actual measurement is
more precise: **it's the height that matters, not the pixel count**.

| Resolution | Result |
|---|---|
| 1920×1080 | works |
| 2560×1080 | works — more pixels, same height |
| 3440×1440 | intro and menus pass, the process is killed when a level loads |

The crash leaves no trace in `error.log`.

#### 4. Menus are not scaled

`ResMenu` can be set higher than its 640×480 default, but the port draws
menu elements at a fixed size. Result: no gain in sharpness, smaller-looking
text on screen, and past 1280×960 captions run off the frame. The launcher
therefore keeps `ResMenu` at 640×480.

Verified by comparing screenshots: characters are exactly the same pixel
size in both cases.

#### 5. Windowed mode only works via `-W`

The library accepts a windowed-mode syntax in `config.ini`, with a `w` in
place of the second `x` — for example `1280x960w8`. It has no effect: at
startup, `display_set_full_screen()` walks every registered mode and forces
the flag from a single global setting.

#### 6. The `-S` option freezes the game in fullscreen

`-S` disables upscaling of the 320×200 image. The port then asks for a real
320×200 display mode, which modern screens do not expose, and freezes. An
undistorted picture is obtained another way: through a 4:3 mode, or through
the video output setting described in point 2.

#### 7. `ResGameLo` is not a competing resolution

`ResGameHi` and `ResGameLo` name two HUD sprite sets, switched **in game
with F8**. `ResGameLo` stays at 320×200: writing a high resolution there
just places low-definition sprites on a large surface.

The screen mode can also be changed from the "Visual Depth" options screen.

#### 8. `config.ini` is read top to bottom

A duplicate key means the **last** value wins. A naive write that replaces
the first occurrence without removing the others therefore produces phantom
settings. The launcher deduplicates on every write.

#### 9. Zoom depends on the equipped weapon

`ZoomMin` and `ZoomMax` do not set the view directly: they generate 28
levels that the game picks from according to the range of the weapon in
hand. It is `ZoomMax` that determines what is actually seen in practice —
changing `ZoomMin` alone barely changes anything.

Based on measurements from ticket [#40](https://github.com/swfans/syndwarsfx/issues/40),
`ZoomMax=264` reproduces the 1996 game most closely.

**Worth knowing**: at very wide views, the original engine shows its
limits. Selection boxes and agent numbers can disappear near the edges, for
lack of room in the rendering tables — see ticket
[#255](https://github.com/swfans/syndwarsfx/issues/255) — and the horizon
can fold over itself. These are not bugs in the launcher.

#### 10. Frame rate is not adjustable

Decoupling game speed from rendering is the subject of ticket
[#164](https://github.com/swfans/syndwarsfx/issues/164), open and not
implemented. Nothing for the launcher to expose.

### Building the port

Not directly related to the launcher, but useful to anyone building
SyndWarsFX from source on a recent distribution:

- The port only builds **32-bit** (`-m32`); the disassembly-derived code
  assumes 4-byte pointers.
- On Ubuntu 24.04 bases, **do not install `libsdl1.2-dev`**: it tries to
  remove vital system components. Use SDL2 instead.
- Pass `--with-data-path` to `configure`, otherwise the data path is
  hardcoded to an unusable value and the game finds no files.
- On a distribution that builds **PIE by default**, the `ebx` register —
  the base of position-independent code — gets clobbered on return from
  certain assembly wrappers, corrupting the addressing of global variables.
  Build with `-fno-pie` and link with `-no-pie`.

### License

GPL v3, consistent with the port this launcher builds upon. See
[LICENSE](LICENSE).
