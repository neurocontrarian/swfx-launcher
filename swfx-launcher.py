#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
swfx-launcher — a launcher for SyndWarsFX (Syndicate Wars Fan Expansion)

Edits config.ini and conf/rules.ini, and starts the game with the right
command line options. Bilingual interface (French / English).

Findings this launcher is built on, all verified by testing:

  * Screen modes. In fullscreen the port asks the graphics card for a real
    display mode. A mode the driver does not expose makes startup fail with
    "resolution not available", so the resolution list is built from xrandr.

  * Aspect ratio. Because the card really switches mode, it is the monitor
    that stretches the signal across a non-4:3 panel. The fix belongs to the
    video output, not to the game: setting the output's "scaling mode"
    property to "Full aspect" keeps the proportions. The launcher applies it
    before starting the game and restores the previous value afterwards.

  * Mission view limits. The renderer is bound by HEIGHT, not by pixel
    count: 2560x1080 runs fine while 3440x1440 kills the process when a
    level loads.

  * Menus. The port draws menu elements at a fixed pixel size without
    scaling them, so raising ResMenu gains no sharpness and pushes captions
    out of the frame. It is kept at 640x480.

  * Windowed mode. Only the -W option works. The "w" suffix accepted by
    config.ini is overridden at startup, when the game forces the windowed
    flag on every registered mode.

  * The -S option is not offered: it asks for a real 320x200 display mode,
    which modern screens do not expose, and freezes the game.

  * Zoom. ZoomMin and ZoomMax generate the 28 zoom levels the game picks
    from according to the equipped weapon's range.

Requirements: python3-gi, gir1.2-gtk-4.0
    sudo apt install python3-gi gir1.2-gtk-4.0

Run with:
    python3 swfx-launcher.py
"""

import json
import math
import os
import re
import shutil
import subprocess
import sys
import threading

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gio, Gdk, GLib

APP_ID = "org.swfans.SwfxLauncher"
SETTINGS_PATH = os.path.expanduser("~/.config/swfx-launcher.json")
DEFAULT_GAME_DIR = os.path.expanduser("~/games/syndwarsfx")

# Mission view limits (3D renderer).
MAX_GAME_HEIGHT = 1080
MAX_GAME_WIDTH = 2560

# Above this height, video element placement degrades.
MAX_VIDEO_HEIGHT = 960

MENU_MODE = "640x480x8"
LOWRES_MODE = "320x200x8"
FMV_HI_DEFAULT = "640x480x8"
FMV_LO_DEFAULT = "320x200x8"
BPP = 8

SCALING_PROPERTY = "scaling mode"
SCALING_ASPECT = "Full aspect"

FALLBACK_MODES = ["640x480", "800x600", "1024x768",
                  "1280x960", "1280x1024", "1920x1080"]

WINDOW_SIZES = ["800x600", "1024x768", "1280x800", "1280x960",
                "1440x900", "1440x1080", "1920x1080", "2560x1080"]

# Internal keys kept stable for saved settings.
VIDEO_KEYS = ["upscaled", "fixed43"]

ZOOM_SCALE = {
    1: (40, 80),
    2: (50, 100),
    3: (60, 125),
    4: (70, 150),
    5: (85, 175),
    6: (100, 200),
    7: (110, 225),
    8: (120, 245),
    9: (127, 260),
    10: (132, 264),
}
ZOOM_DEFAULT_STEP = 9

ADVANCED_KEYS = ["-L", "-w"]

MODE_RE = re.compile(r'^\s*(\d+)\s*x\s*(\d+)\s*([xw])\s*(\d+)\s*$', re.I)
SIZE_RE = re.compile(r'^\s*(\d+)\s*[xX]\s*(\d+)\s*$')
XRANDR_MODE_RE = re.compile(r'^\s+(\d+)x(\d+)\s')
XRANDR_OUTPUT_RE = re.compile(r'^(\S+)\s+connected')


# --------------------------------------------------------------------------
# Translations
# --------------------------------------------------------------------------

LANGUAGES = [("fr", "Francais"), ("en", "English")]

STRINGS = {
    "window_title": {
        "fr": "SyndWarsFX — Lanceur",
        "en": "SyndWarsFX Launcher"},
    "game_folder": {
        "fr": "Dossier du jeu…",
        "en": "Game folder…"},
    "folder_dialog": {
        "fr": "Dossier d'installation de SyndWarsFX",
        "en": "SyndWarsFX installation folder"},

    "tab_display": {"fr": "Affichage", "en": "Display"},
    "tab_game": {"fr": "Jeu", "en": "Game"},
    "tab_launch": {"fr": "Lancement", "en": "Launch"},

    "sec_mission_view": {"fr": "Vue de mission", "en": "Mission view"},
    "windowed": {"fr": "Mode fenetre", "en": "Windowed mode"},
    "resolution": {"fr": "Resolution", "en": "Resolution"},
    "res_note_windowed": {
        "fr": "En fenetre, la taille est libre : le jeu cree une fenetre au "
              "lieu de demander un mode d'affichage.",
        "en": "In a window any size works: the game creates a window instead "
              "of requesting a display mode."},
    "res_note_fullscreen": {
        "fr": "En plein ecran, seuls les modes reellement disponibles sur "
              "votre ecran fonctionnent.",
        "en": "In fullscreen, only modes your screen actually provides will "
              "work."},
    "res_limit": {
        "fr": "Le moteur ne supporte pas plus de %d pixels de hauteur : "
              "au-dela, le jeu se ferme au chargement de la mission. La "
              "largeur peut depasser 1920 — %dx%d fonctionne.",
        "en": "The renderer does not support more than %d pixels of height: "
              "beyond that the game exits when a mission loads. Width may go "
              "past 1920 — %dx%d works."},

    "sec_aspect": {"fr": "Proportions a l'ecran", "en": "On-screen aspect"},
    "keep_aspect": {
        "fr": "Preserver les proportions (bandes noires)",
        "en": "Keep the aspect ratio (black bars)"},
    "aspect_on": {
        "fr": "La sortie video sera reglee pour preserver les proportions "
              "avant le lancement, puis remise dans son etat precedent a la "
              "fermeture du jeu.",
        "en": "The video output will be set to keep proportions before the "
              "game starts, then restored to its previous state when the "
              "game exits."},
    "aspect_off": {
        "fr": "En plein ecran, le jeu fait changer de mode votre carte "
              "graphique. C'est ensuite le moniteur qui etale ce signal sur "
              "toute la largeur, ce qui deforme le texte et les menus sur un "
              "ecran panoramique.",
        "en": "In fullscreen the game makes your graphics card switch mode. "
              "The monitor then spreads that signal across the full width, "
              "which distorts text and menus on a widescreen display."},
    "aspect_unavailable": {
        "fr": "Votre pilote graphique n'expose pas ce reglage : les "
              "proportions dependent alors du menu de votre moniteur.",
        "en": "Your graphics driver does not expose this setting: "
              "proportions then depend on your monitor's own menu."},

    "sec_videos": {
        "fr": "Videos (intro et fins de mission)",
        "en": "Videos (intro and mission endings)"},
    "video_upscaled": {
        "fr": "Agrandies a l'ecran",
        "en": "Enlarged to fit the screen"},
    "video_upscaled_desc": {
        "fr": "Les videos gardent leurs modes d'origine et occupent tout "
              "l'ecran. Avec « Preserver les proportions », elles ne sont "
              "pas deformees.",
        "en": "Videos keep their original modes and fill the screen. With "
              "\"Keep the aspect ratio\" enabled they are not distorted."},
    "video_fixed43": {
        "fr": "Dans un mode 4:3 dedie",
        "en": "In a dedicated 4:3 mode"},
    "video_fixed43_desc": {
        "fr": "Force un mode d'ecran 4:3 pour les videos. L'image est plus "
              "petite et centree.",
        "en": "Forces a 4:3 screen mode for videos. The picture is smaller "
              "and centred."},
    "video_target": {
        "fr": "Videos affichees en %dx%d.",
        "en": "Videos shown at %dx%d."},
    "video_no_43": {
        "fr": "Aucune taille 4:3 utilisable dans ce mode.",
        "en": "No usable 4:3 size in this mode."},

    "menu_info": {
        "fr": "<b>Menus :</b> fixes a 640x480. Le jeu dessine leurs elements "
              "a taille fixe sans mise a l'echelle, donc une valeur plus "
              "elevee ne gagne aucune nettete et fait sortir les inscriptions "
              "du cadre.",
        "en": "<b>Menus:</b> fixed at 640x480. The game draws their elements "
              "at a fixed size without scaling, so a higher value gains no "
              "sharpness and pushes captions out of the frame."},

    "monitor_none": {"fr": "Moniteur non detecte.", "en": "No monitor found."},
    "monitor_info": {
        "fr": "Moniteur : %dx%d (%s). Plus grand mode 4:3 utilisable : %dx%d.",
        "en": "Monitor: %dx%d (%s). Largest usable 4:3 mode: %dx%d."},
    "monitor_info_short": {
        "fr": "Moniteur : %dx%d (%s).",
        "en": "Monitor: %dx%d (%s)."},

    "sec_view_range": {"fr": "Champ de vision", "en": "Field of view"},
    "view_wide": {"fr": "Vue large", "en": "Wide view"},
    "view_original": {"fr": "Vue d'origine", "en": "Original view"},
    "zoom_position": {
        "fr": "Position %d sur 10 — ZoomMin %d, ZoomMax %d%s.",
        "en": "Position %d of 10 — ZoomMin %d, ZoomMax %d%s."},
    "zoom_closest": {
        "fr": " — au plus proche du jeu de 1996",
        "en": " — closest to the 1996 game"},
    "zoom_default": {
        "fr": " — valeurs par defaut du port",
        "en": " — the port's default values"},
    "zoom_warning": {
        "fr": "Le zoom depend aussi de l'arme equipee : ces valeurs servent a "
              "generer les niveaux dans lesquels le jeu pioche. Aux vues tres "
              "larges, le moteur d'origine montre ses limites — encadres de "
              "selection disparaissant pres des bords, horizon qui se replie.",
        "en": "Zoom also depends on the equipped weapon: these values "
              "generate the levels the game picks from. At very wide views "
              "the original engine shows its limits — selection outlines "
              "vanishing near the edges, horizon folding over itself."},
    "target_health": {
        "fr": "Afficher la sante des cibles visees",
        "en": "Show health of targeted enemies"},
    "target_health_desc": {
        "fr": "Fonctionnalite prevue par le jeu d'origine mais cassee a "
              "l'epoque, reparee par le port.",
        "en": "Intended by the original game but broken back then, repaired "
              "by the port."},

    "skip_intro": {
        "fr": "Sauter la video d'intro",
        "en": "Skip the intro video"},
    "sec_direct_mission": {
        "fr": "Lancer directement une mission",
        "en": "Start a specific mission"},
    "enable": {"fr": "Activer", "en": "Enable"},
    "campaign": {"fr": "Campagne", "en": "Campaign"},
    "mission": {"fr": "Mission", "en": "Mission"},
    "mission_note": {
        "fr": "Permet de rejouer une mission precise, y compris les niveaux "
              "pre-alpha et ceux de la version PlayStation livres avec le "
              "jeu.",
        "en": "Replay a specific mission, including the pre-alpha levels and "
              "the PlayStation ones shipped with the game."},
    "advanced": {"fr": "Reglages avances", "en": "Advanced settings"},
    "flag_L": {
        "fr": "Corrections approfondies des niveaux",
        "en": "Deeper level fixes"},
    "flag_L_desc": {
        "fr": "Applique des reparations supplementaires aux niveaux charges. "
              "Peut corriger certains defauts mais aussi en introduire "
              "d'autres. Les corrections sans risque sont deja appliquees "
              "sans cette option.",
        "en": "Applies extra repairs to loaded levels. May fix some glitches "
              "but can also introduce others. Non-damaging fixes are already "
              "applied without this option."},
    "flag_w": {
        "fr": "Reduire l'usage memoire",
        "en": "Lower memory use"},
    "flag_w_desc": {
        "fr": "Diminue la taille des tableaux internes du moteur. Destine aux "
              "machines a faible memoire ; inutile sur un ordinateur recent.",
        "en": "Shrinks the engine's internal arrays. Meant for low-memory "
              "machines; pointless on a recent computer."},
    "command": {"fr": "Commande : ", "en": "Command: "},

    "view_log": {"fr": "Voir error.log", "en": "View error.log"},
    "restore_bak": {"fr": "Restaurer les .bak", "en": "Restore .bak files"},
    "save": {"fr": "Enregistrer", "en": "Save"},
    "play": {"fr": "Jouer", "en": "Play"},

    "folder_is": {"fr": "Dossier : %s", "en": "Folder: %s"},
    "exe_missing": {
        "fr": "Executable introuvable dans %s",
        "en": "Executable not found in %s"},
    "saved": {
        "fr": "Reglages enregistres (anciens fichiers en .bak).",
        "en": "Settings saved (previous files kept as .bak)."},
    "save_failed": {
        "fr": "Echec de l'enregistrement : %s",
        "en": "Could not save: %s"},
    "no_resolution": {
        "fr": "Aucune resolution selectionnee.",
        "en": "No resolution selected."},
    "too_tall": {
        "fr": "Hauteur %d trop grande : le jeu se ferme au chargement de la "
              "mission au-dela de %d pixels de haut.",
        "en": "Height %d is too large: the game exits when a mission loads "
              "beyond %d pixels of height."},
    "too_wide": {
        "fr": "Largeur %d non validee : %d est la plus grande largeur testee "
              "comme fonctionnelle.",
        "en": "Width %d is untested: %d is the largest width known to work."},
    "not_a_mode": {
        "fr": "%dx%d n'est pas un mode de votre ecran : cochez « Mode "
              "fenetre » ou choisissez une autre resolution.",
        "en": "%dx%d is not a mode your screen provides: tick \"Windowed "
              "mode\" or pick another resolution."},
    "launched": {"fr": "Jeu lance.", "en": "Game started."},
    "launched_aspect": {
        "fr": "Proportions preservees ; jeu lance.",
        "en": "Aspect ratio preserved; game started."},
    "aspect_refused": {
        "fr": "Reglage des proportions refuse par le pilote ; jeu lance quand "
              "meme.",
        "en": "The driver refused the aspect setting; game started anyway."},
    "launch_failed": {
        "fr": "Echec du lancement : %s",
        "en": "Could not start the game: %s"},
    "restored_screen": {
        "fr": "Jeu ferme ; reglage d'ecran restaure.",
        "en": "Game closed; screen setting restored."},
    "no_log": {
        "fr": "Aucun error.log dans %s",
        "en": "No error.log in %s"},
    "read_failed": {
        "fr": "Lecture impossible : %s",
        "en": "Could not read: %s"},
    "restore_failed": {
        "fr": "Restauration impossible : %s",
        "en": "Could not restore: %s"},
    "no_backup": {
        "fr": "Aucune sauvegarde .bak trouvee.",
        "en": "No .bak backup found."},
    "restored": {"fr": "Restaure : %s", "en": "Restored: %s"},
    "settings_failed": {
        "fr": "Reglages du lanceur non sauvegardes : %s",
        "en": "Launcher settings not saved: %s"},
}


# --------------------------------------------------------------------------
# Screen modes
# --------------------------------------------------------------------------

def parse_mode(text):
    m = MODE_RE.match(text or "")
    if not m:
        return None
    return (int(m.group(1)), int(m.group(2)),
            int(m.group(4)), m.group(3).lower() == "w")


def size_of(text):
    m = SIZE_RE.match(text or "")
    if m:
        return (int(m.group(1)), int(m.group(2)))
    parsed = parse_mode(text)
    return (parsed[0], parsed[1]) if parsed else None


def format_mode(width, height):
    """Always written with 'x': the 'w' suffix is overridden at startup."""
    return "%dx%dx%d" % (width, height, BPP)


def aspect_label(w, h):
    if h == 0:
        return "?"
    g = math.gcd(w, h)
    return "%d:%d" % (w // g, h // g)


def run_xrandr(args, capture=True):
    try:
        return subprocess.run(["xrandr"] + args, capture_output=capture,
                              text=True, timeout=5)
    except Exception:
        return None


def xrandr_sizes():
    result = run_xrandr([])
    if result is None:
        return []
    found = set()
    for line in result.stdout.splitlines():
        m = XRANDR_MODE_RE.match(line)
        if m:
            found.add((int(m.group(1)), int(m.group(2))))
    return sorted(found, key=lambda wh: (-wh[0] * wh[1], -wh[0]))


def primary_output():
    """Name of the connected video output, for xrandr --output."""
    result = run_xrandr([])
    if result is None:
        return None
    fallback = None
    for line in result.stdout.splitlines():
        m = XRANDR_OUTPUT_RE.match(line)
        if not m:
            continue
        if " primary " in line:
            return m.group(1)
        if fallback is None:
            fallback = m.group(1)
    return fallback


def scaling_mode_supported():
    result = run_xrandr(["--prop"])
    if result is None:
        return False
    return SCALING_PROPERTY in result.stdout and SCALING_ASPECT in result.stdout


def current_scaling_mode(output):
    result = run_xrandr(["--prop"])
    if result is None or not output:
        return None
    in_output = False
    for line in result.stdout.splitlines():
        m = XRANDR_OUTPUT_RE.match(line)
        if m:
            in_output = (m.group(1) == output)
            continue
        if in_output and SCALING_PROPERTY in line.lower():
            parts = line.split(":", 1)
            if len(parts) == 2:
                return parts[1].strip()
    return None


def set_scaling_mode(output, value):
    if not output or not value:
        return False
    result = run_xrandr(["--output", output, "--set", SCALING_PROPERTY, value])
    return bool(result) and result.returncode == 0


def game_modes(all_sizes):
    usable = [(w, h) for (w, h) in all_sizes
              if h <= MAX_GAME_HEIGHT and w <= MAX_GAME_WIDTH]
    if not usable:
        return list(FALLBACK_MODES)
    return ["%dx%d" % (w, h) for w, h in usable]


def four_three_sizes(all_sizes, max_height):
    result = [(w, h) for (w, h) in all_sizes
              if h <= max_height and abs(w / h - 4 / 3) <= 0.01]
    result.sort(key=lambda wh: -wh[0] * wh[1])
    return result


def detect_monitor():
    try:
        display = Gdk.Display.get_default()
        if display is None:
            return None
        monitors = display.get_monitors()
        if monitors.get_n_items() == 0:
            return None
        geo = monitors.get_item(0).get_geometry()
        return (geo.width, geo.height)
    except Exception:
        return None


def nearest_zoom_step(zoom_max):
    best_step, best_gap = ZOOM_DEFAULT_STEP, None
    for step, (_lo, hi) in ZOOM_SCALE.items():
        gap = abs(hi - zoom_max)
        if best_gap is None or gap < best_gap:
            best_step, best_gap = step, gap
    return best_step


# --------------------------------------------------------------------------
# Ini files
# --------------------------------------------------------------------------

class IniFile:
    """Keeps order, comments and unknown lines untouched."""

    LINE_RE = re.compile(r'^(\s*)([A-Za-z_][A-Za-z0-9_]*)(\s*=\s*)(.*?)(\s*)$')

    def __init__(self, path):
        self.path = path
        self.lines = []
        self.load()

    def load(self):
        self.lines = []
        if not os.path.exists(self.path):
            return
        with open(self.path, "r", encoding="utf-8", errors="replace") as fh:
            self.lines = fh.read().splitlines()

    def _is_key(self, line, key):
        m = self.LINE_RE.match(line)
        return bool(m) and m.group(2).lower() == key.lower()

    def get(self, key, default=""):
        for line in self.lines:
            if self._is_key(line, key):
                return self.LINE_RE.match(line).group(4).strip().strip('"')
        return default

    def remove(self, key):
        self.lines = [ln for ln in self.lines if not self._is_key(ln, key)]

    def format_value(self, value):
        return str(value)

    def set(self, key, value):
        """Writes the first occurrence and drops duplicates: the game reads
        the file top to bottom, so a duplicate would win over the new value.
        """
        found = False
        kept = []
        for line in self.lines:
            if self._is_key(line, key):
                if found:
                    continue
                m = self.LINE_RE.match(line)
                kept.append("%s%s%s%s" % (m.group(1), m.group(2), m.group(3),
                                          self.format_value(value)))
                found = True
            else:
                kept.append(line)
        self.lines = kept
        if not found:
            self.lines.append("%s=%s" % (key, self.format_value(value)))

    def save(self):
        if os.path.exists(self.path):
            shutil.copy2(self.path, self.path + ".bak")
        parent = os.path.dirname(self.path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(self.lines).rstrip("\n") + "\n")


class ConfigIni(IniFile):
    def format_value(self, value):
        return '"%s"' % value


class RulesIni(IniFile):
    pass


# --------------------------------------------------------------------------
# Main window
# --------------------------------------------------------------------------

class LauncherWindow(Gtk.ApplicationWindow):

    def __init__(self, app):
        super().__init__(application=app)
        self.set_default_size(720, 700)

        self.settings = self.load_settings()
        self.lang = self.settings.get("lang", "fr")
        self.game_dir = self.settings.get("game_dir", DEFAULT_GAME_DIR)

        self.all_sizes = xrandr_sizes()
        self.fullscreen_modes = game_modes(self.all_sizes)
        self.window_sizes = self.build_window_sizes()
        self.output = primary_output()
        self.scaling_available = scaling_mode_supported()

        self.config = ConfigIni(self.config_path())
        self.rules = RulesIni(self.rules_path())

        self.root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_child(self.root)
        self.build_ui()

    # -- translation -------------------------------------------------------

    def tr(self, key):
        entry = STRINGS.get(key)
        if not entry:
            return key
        return entry.get(self.lang, entry.get("en", key))

    # -- paths and settings ------------------------------------------------

    def config_path(self):
        return os.path.join(self.game_dir, "config.ini")

    def rules_path(self):
        return os.path.join(self.game_dir, "conf", "rules.ini")

    def build_window_sizes(self):
        sizes = []
        for text in WINDOW_SIZES:
            size = size_of(text)
            if size and size[1] <= MAX_GAME_HEIGHT \
                    and size[0] <= MAX_GAME_WIDTH:
                sizes.append(text)
        geo = detect_monitor()
        if geo is not None:
            width = min(geo[0], MAX_GAME_WIDTH)
            candidate = "%dx%d" % (width, MAX_GAME_HEIGHT)
            if candidate not in sizes:
                sizes.insert(0, candidate)
        return sizes

    def load_settings(self):
        try:
            with open(SETTINGS_PATH, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except Exception:
            return {}

    def save_settings(self):
        self.settings["lang"] = self.lang
        self.settings["game_dir"] = self.game_dir
        self.settings["windowed"] = self.windowed_check.get_active()
        self.settings["keep_aspect"] = self.aspect_check.get_active()
        self.settings["video_mode"] = self.current_video_mode()
        self.settings["skip_intro"] = self.skip_intro.get_active()
        self.settings["advanced"] = [f for f, sw
                                     in self.advanced_switches.items()
                                     if sw.get_active()]
        os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
        try:
            with open(SETTINGS_PATH, "w", encoding="utf-8") as fh:
                json.dump(self.settings, fh, indent=2)
        except Exception as exc:
            self.set_status(self.tr("settings_failed") % exc)

    # -- interface ---------------------------------------------------------

    def build_ui(self):
        """Builds every widget. Called again when the language changes."""
        child = self.root.get_first_child()
        while child is not None:
            nxt = child.get_next_sibling()
            self.root.remove(child)
            child = nxt

        self.advanced_switches = {}
        self.video_buttons = {}
        self._items = []
        self._loading = False

        self.set_title(self.tr("window_title"))

        header = Gtk.HeaderBar()
        self.set_titlebar(header)

        btn_dir = Gtk.Button(label=self.tr("game_folder"))
        btn_dir.connect("clicked", self.on_pick_dir)
        header.pack_start(btn_dir)

        lang_drop = Gtk.DropDown.new_from_strings(
            [name for _code, name in LANGUAGES])
        codes = [code for code, _name in LANGUAGES]
        lang_drop.set_selected(codes.index(self.lang)
                               if self.lang in codes else 0)
        lang_drop.connect("notify::selected", self.on_language_changed)
        header.pack_end(lang_drop)

        notebook = Gtk.Notebook()
        for side in ("top", "start", "end"):
            getattr(notebook, "set_margin_" + side)(12)
        notebook.set_margin_bottom(6)
        notebook.set_vexpand(True)
        self.root.append(notebook)

        notebook.append_page(self.build_display_tab(),
                             Gtk.Label(label=self.tr("tab_display")))
        notebook.append_page(self.build_game_tab(),
                             Gtk.Label(label=self.tr("tab_game")))
        notebook.append_page(self.build_launch_tab(),
                             Gtk.Label(label=self.tr("tab_launch")))

        self.root.append(self.build_action_bar())

        self.status = Gtk.Label(xalign=0, wrap=True)
        self.status.set_margin_start(14)
        self.status.set_margin_end(14)
        self.status.set_margin_bottom(10)
        self.status.add_css_class("dim-label")
        self.root.append(self.status)

        self.reload_all()

    def on_language_changed(self, drop, _param):
        index = drop.get_selected()
        if index < 0 or index >= len(LANGUAGES):
            return
        code = LANGUAGES[index][0]
        if code == self.lang:
            return
        self.lang = code
        self.settings["lang"] = code
        self.build_ui()

    def small_label(self, text, indent=0):
        lbl = Gtk.Label(xalign=0, wrap=True)
        lbl.set_markup("<small>%s</small>" % text)
        lbl.add_css_class("dim-label")
        if indent:
            lbl.set_margin_start(indent)
        return lbl

    def section_label(self, text):
        lbl = Gtk.Label(xalign=0)
        lbl.set_markup("<b>%s</b>" % GLib.markup_escape_text(text))
        return lbl

    def build_display_tab(self):
        scroller = Gtk.ScrolledWindow()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        for side in ("top", "bottom", "start", "end"):
            getattr(box, "set_margin_" + side)(16)
        scroller.set_child(box)

        box.append(self.section_label(self.tr("sec_mission_view")))

        self.windowed_check = Gtk.CheckButton(label=self.tr("windowed"))
        self.windowed_check.connect("toggled",
                                    lambda *_: self.on_mode_switch())
        box.append(self.windowed_check)

        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        row.append(Gtk.Label(label=self.tr("resolution"), xalign=0))
        self.res_drop = Gtk.DropDown.new_from_strings(self.fullscreen_modes)
        self.res_drop.connect("notify::selected", lambda *_: self.on_changed())
        row.append(self.res_drop)
        box.append(row)

        self.res_note = Gtk.Label(xalign=0, wrap=True)
        self.res_note.add_css_class("dim-label")
        box.append(self.res_note)

        box.append(self.small_label(GLib.markup_escape_text(
            self.tr("res_limit") % (MAX_GAME_HEIGHT, MAX_GAME_WIDTH,
                                    MAX_GAME_HEIGHT))))

        box.append(Gtk.Separator())
        box.append(self.section_label(self.tr("sec_aspect")))

        self.aspect_check = Gtk.CheckButton(label=self.tr("keep_aspect"))
        self.aspect_check.set_sensitive(self.scaling_available)
        self.aspect_check.connect("toggled", lambda *_: self.on_changed())
        box.append(self.aspect_check)

        self.aspect_note = Gtk.Label(xalign=0, wrap=True)
        self.aspect_note.add_css_class("dim-label")
        self.aspect_note.set_margin_start(28)
        box.append(self.aspect_note)

        box.append(Gtk.Separator())
        box.append(self.section_label(self.tr("sec_videos")))

        first = None
        for key in VIDEO_KEYS:
            btn = Gtk.CheckButton(label=self.tr("video_" + key))
            if first is None:
                first = btn
            else:
                btn.set_group(first)
            btn.connect("toggled", lambda *_: self.on_changed())
            box.append(btn)
            box.append(self.small_label(
                GLib.markup_escape_text(self.tr("video_%s_desc" % key)), 28))
            self.video_buttons[key] = btn

        self.video_note = Gtk.Label(xalign=0, wrap=True)
        self.video_note.add_css_class("dim-label")
        box.append(self.video_note)

        box.append(Gtk.Separator())
        box.append(self.small_label(self.tr("menu_info")))

        self.monitor_label = Gtk.Label(xalign=0, wrap=True)
        self.monitor_label.add_css_class("dim-label")
        box.append(self.monitor_label)

        self.update_monitor_info()
        return scroller

    def build_game_tab(self):
        scroller = Gtk.ScrolledWindow()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        for side in ("top", "bottom", "start", "end"):
            getattr(box, "set_margin_" + side)(16)
        scroller.set_child(box)

        box.append(self.section_label(self.tr("sec_view_range")))

        adjustment = Gtk.Adjustment(value=ZOOM_DEFAULT_STEP, lower=1, upper=10,
                                    step_increment=1, page_increment=1)
        self.zoom_scale = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL,
                                    adjustment=adjustment)
        self.zoom_scale.set_draw_value(False)
        self.zoom_scale.set_digits(0)
        self.zoom_scale.set_round_digits(0)
        self.zoom_scale.set_hexpand(True)
        for step in range(1, 11):
            self.zoom_scale.add_mark(step, Gtk.PositionType.BOTTOM, None)
        self.zoom_scale.connect("value-changed",
                                lambda *_: self.on_zoom_moved())
        box.append(self.zoom_scale)

        ends = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        left = Gtk.Label(label=self.tr("view_wide"), xalign=0)
        left.set_hexpand(True)
        left.add_css_class("dim-label")
        ends.append(left)
        right = Gtk.Label(label=self.tr("view_original"), xalign=1)
        right.add_css_class("dim-label")
        ends.append(right)
        box.append(ends)

        self.zoom_note = Gtk.Label(xalign=0, wrap=True)
        self.zoom_note.add_css_class("dim-label")
        box.append(self.zoom_note)

        box.append(self.small_label(
            GLib.markup_escape_text(self.tr("zoom_warning"))))

        box.append(Gtk.Separator())

        self.target_health = Gtk.CheckButton(label=self.tr("target_health"))
        box.append(self.target_health)
        box.append(self.small_label(
            GLib.markup_escape_text(self.tr("target_health_desc")), 28))

        return scroller

    def build_launch_tab(self):
        scroller = Gtk.ScrolledWindow()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        for side in ("top", "bottom", "start", "end"):
            getattr(box, "set_margin_" + side)(16)
        scroller.set_child(box)

        self.skip_intro = Gtk.CheckButton(label=self.tr("skip_intro"))
        self.skip_intro.set_active(self.settings.get("skip_intro", False))
        self.skip_intro.connect("toggled", lambda *_: self.on_changed())
        box.append(self.skip_intro)

        box.append(Gtk.Separator())
        box.append(self.section_label(self.tr("sec_direct_mission")))

        mrow = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.mission_enable = Gtk.CheckButton(label=self.tr("enable"))
        self.mission_enable.connect("toggled", lambda *_: self.on_changed())
        mrow.append(self.mission_enable)
        mrow.append(Gtk.Label(label=self.tr("campaign"), xalign=0))
        self.campaign_spin = Gtk.SpinButton.new_with_range(0, 99, 1)
        self.campaign_spin.connect("value-changed",
                                   lambda *_: self.on_changed())
        mrow.append(self.campaign_spin)
        mrow.append(Gtk.Label(label=self.tr("mission"), xalign=0))
        self.mission_spin = Gtk.SpinButton.new_with_range(0, 999, 1)
        self.mission_spin.connect("value-changed", lambda *_: self.on_changed())
        mrow.append(self.mission_spin)
        box.append(mrow)

        box.append(self.small_label(
            GLib.markup_escape_text(self.tr("mission_note"))))

        box.append(Gtk.Separator())

        expander = Gtk.Expander(label=self.tr("advanced"))
        adv = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        adv.set_margin_top(10)
        adv.set_margin_start(12)

        saved = set(self.settings.get("advanced", []))
        for flag in ADVANCED_KEYS:
            name = flag.lstrip("-")
            sw_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            sw = Gtk.Switch()
            sw.set_active(flag in saved)
            sw.set_valign(Gtk.Align.START)
            sw.connect("notify::active", lambda *_: self.on_changed())
            sw_row.append(sw)

            texts = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            texts.append(Gtk.Label(
                label="%s  (%s)" % (self.tr("flag_" + name), flag), xalign=0))
            texts.append(self.small_label(GLib.markup_escape_text(
                self.tr("flag_%s_desc" % name))))
            texts.set_hexpand(True)
            sw_row.append(texts)

            adv.append(sw_row)
            self.advanced_switches[flag] = sw

        expander.set_child(adv)
        box.append(expander)

        self.cmd_preview = Gtk.Label(xalign=0, wrap=True, selectable=True)
        self.cmd_preview.add_css_class("dim-label")
        box.append(self.cmd_preview)

        return scroller

    def build_action_bar(self):
        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        bar.set_margin_start(14)
        bar.set_margin_end(14)
        bar.set_margin_bottom(6)

        btn_log = Gtk.Button(label=self.tr("view_log"))
        btn_log.connect("clicked", self.on_show_log)
        bar.append(btn_log)

        btn_restore = Gtk.Button(label=self.tr("restore_bak"))
        btn_restore.connect("clicked", self.on_restore_backup)
        bar.append(btn_restore)

        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        bar.append(spacer)

        btn_save = Gtk.Button(label=self.tr("save"))
        btn_save.connect("clicked", self.on_save)
        bar.append(btn_save)

        btn_play = Gtk.Button(label=self.tr("play"))
        btn_play.add_css_class("suggested-action")
        btn_play.connect("clicked", self.on_play)
        bar.append(btn_play)
        return bar

    # -- resolution lists --------------------------------------------------

    def current_list(self):
        return (self.window_sizes if self.windowed_check.get_active()
                else self.fullscreen_modes)

    def refill_resolutions(self, keep=""):
        items = list(self.current_list())
        if keep and keep not in items:
            items.insert(0, keep)
        self.res_drop.set_model(Gtk.StringList.new(items))
        self.res_drop.set_selected(items.index(keep) if keep in items else 0)
        self._items = items

    def selected_size(self):
        index = self.res_drop.get_selected()
        if index < 0 or index >= len(self._items):
            return None
        return size_of(self._items[index])

    def on_mode_switch(self):
        if self._loading:
            return
        size = self.selected_size()
        self.refill_resolutions("%dx%d" % size if size else "")
        self.on_changed()

    # -- loading -----------------------------------------------------------

    def reload_all(self):
        self._loading = True
        self.config = ConfigIni(self.config_path())
        self.rules = RulesIni(self.rules_path())

        self.windowed_check.set_active(self.settings.get("windowed", False))
        self.aspect_check.set_active(
            self.scaling_available and self.settings.get("keep_aspect", False))

        size = size_of(self.config.get("ResGameHi", ""))
        self.refill_resolutions("%dx%d" % size if size else "1280x960")

        video_size = size_of(self.config.get("ResFMVidLo", ""))
        mode = "fixed43" if (video_size and video_size != (320, 200)) \
            else "upscaled"
        self.video_buttons[mode].set_active(True)

        try:
            zoom_max = int(self.rules.get("ZoomMax", "260"))
        except ValueError:
            zoom_max = 260
        self.zoom_scale.set_value(nearest_zoom_step(zoom_max))

        self.target_health.set_active(
            self.rules.get("ShowTargetHealth", "False").strip().lower()
            in ("true", "1", "yes"))

        self._loading = False
        self.on_zoom_moved()
        self.on_changed()

        if not os.path.exists(os.path.join(self.game_dir, "syndwarsfx")):
            self.set_status(self.tr("exe_missing") % self.game_dir)
        else:
            self.set_status(self.tr("folder_is") % self.game_dir)

    # -- reactions ---------------------------------------------------------

    def current_video_mode(self):
        for key, btn in self.video_buttons.items():
            if btn.get_active():
                return key
        return "upscaled"

    def video_target(self):
        """4:3 size used when videos get their own screen mode."""
        if self.windowed_check.get_active():
            size = self.selected_size()
            if size is None:
                return (1280, 960)
            width, height = size
            height = min(height, MAX_VIDEO_HEIGHT)
            new_width = int(round(height * 4 / 3))
            new_width -= new_width % 2
            if new_width > width:
                new_height = int(round(width * 3 / 4))
                new_height -= new_height % 2
                return (width, new_height)
            return (new_width, height)
        options = four_three_sizes(self.all_sizes, MAX_VIDEO_HEIGHT)
        return options[0] if options else None

    def on_changed(self):
        if self._loading:
            return
        self.update_preview()

        self.res_note.set_text(
            self.tr("res_note_windowed") if self.windowed_check.get_active()
            else self.tr("res_note_fullscreen"))

        if not self.scaling_available:
            self.aspect_note.set_text(self.tr("aspect_unavailable"))
        elif self.aspect_check.get_active():
            self.aspect_note.set_text(self.tr("aspect_on"))
        else:
            self.aspect_note.set_text(self.tr("aspect_off"))

        if self.current_video_mode() == "fixed43":
            target = self.video_target()
            self.video_note.set_text(
                self.tr("video_target") % target if target
                else self.tr("video_no_43"))
        else:
            self.video_note.set_text("")

    def on_zoom_moved(self):
        step = int(round(self.zoom_scale.get_value()))
        step = max(1, min(10, step))
        lo, hi = ZOOM_SCALE[step]
        if step == 10:
            suffix = self.tr("zoom_closest")
        elif step == ZOOM_DEFAULT_STEP:
            suffix = self.tr("zoom_default")
        else:
            suffix = ""
        self.zoom_note.set_text(
            self.tr("zoom_position") % (step, lo, hi, suffix))

    def update_monitor_info(self):
        geo = detect_monitor()
        if geo is None:
            self.monitor_label.set_text(self.tr("monitor_none"))
            return
        w, h = geo
        options = four_three_sizes(self.all_sizes, MAX_VIDEO_HEIGHT)
        if options:
            self.monitor_label.set_text(
                self.tr("monitor_info")
                % (w, h, aspect_label(w, h), options[0][0], options[0][1]))
        else:
            self.monitor_label.set_text(
                self.tr("monitor_info_short") % (w, h, aspect_label(w, h)))

    def build_command(self):
        cmd = [os.path.join(self.game_dir, "syndwarsfx"), "-g"]
        if self.windowed_check.get_active():
            cmd.append("-W")
        if self.skip_intro.get_active():
            cmd.append("-q")
        for flag in ADVANCED_KEYS:
            if self.advanced_switches[flag].get_active():
                cmd.append(flag)
        if self.mission_enable.get_active():
            cmd.append("-m")
            cmd.append("%d,%d" % (int(self.campaign_spin.get_value()),
                                  int(self.mission_spin.get_value())))
        return cmd

    def update_preview(self):
        self.cmd_preview.set_text(self.tr("command")
                                  + " ".join(self.build_command()))

    # -- saving ------------------------------------------------------------

    def on_save(self, _btn=None):
        size = self.selected_size()
        if size is None:
            self.set_status(self.tr("no_resolution"))
            return
        width, height = size
        windowed = self.windowed_check.get_active()

        if height > MAX_GAME_HEIGHT:
            self.set_status(self.tr("too_tall") % (height, MAX_GAME_HEIGHT))
            return
        if width > MAX_GAME_WIDTH:
            self.set_status(self.tr("too_wide") % (width, MAX_GAME_WIDTH))
            return
        if not windowed and ("%dx%d" % (width, height)) \
                not in self.fullscreen_modes:
            self.set_status(self.tr("not_a_mode") % (width, height))
            return

        self.config.set("ResGameHi", format_mode(width, height))
        self.config.set("ResGameLo", LOWRES_MODE)
        self.config.set("ResMenu", MENU_MODE)

        if self.current_video_mode() == "fixed43":
            target = self.video_target()
            if target is None:
                self.set_status(self.tr("video_no_43"))
                return
            value = format_mode(*target)
            self.config.set("ResFMVVidHi", value)
            self.config.set("ResFMVidLo", value)
        else:
            self.config.set("ResFMVVidHi", FMV_HI_DEFAULT)
            self.config.set("ResFMVidLo", FMV_LO_DEFAULT)

        step = int(round(self.zoom_scale.get_value()))
        step = max(1, min(10, step))
        lo, hi = ZOOM_SCALE[step]
        self.rules.set("ZoomMin", lo)
        self.rules.set("ZoomMax", hi)
        self.rules.set("ShowTargetHealth",
                       "True" if self.target_health.get_active() else "False")

        try:
            self.config.save()
            if os.path.exists(self.rules_path()):
                self.rules.save()
            self.save_settings()
            self.set_status(self.tr("saved"))
        except Exception as exc:
            self.set_status(self.tr("save_failed") % exc)

    def on_restore_backup(self, _btn):
        restored = []
        for path in (self.config_path(), self.rules_path()):
            backup = path + ".bak"
            if os.path.exists(backup):
                try:
                    shutil.copy2(backup, path)
                    restored.append(os.path.basename(path))
                except Exception as exc:
                    self.set_status(self.tr("restore_failed") % exc)
                    return
        if not restored:
            self.set_status(self.tr("no_backup"))
            return
        self.reload_all()
        self.set_status(self.tr("restored") % ", ".join(restored))

    # -- launching ---------------------------------------------------------

    def on_play(self, _btn):
        self.on_save()
        cmd = self.build_command()
        if not os.path.exists(cmd[0]):
            self.set_status(self.tr("exe_missing") % self.game_dir)
            return

        previous_scaling = None
        if self.aspect_check.get_active() and self.scaling_available:
            previous_scaling = current_scaling_mode(self.output)
            if set_scaling_mode(self.output, SCALING_ASPECT):
                self.set_status(self.tr("launched_aspect"))
            else:
                previous_scaling = None
                self.set_status(self.tr("aspect_refused"))
        else:
            self.set_status(self.tr("launched"))

        try:
            process = subprocess.Popen(cmd, cwd=self.game_dir)
        except Exception as exc:
            if previous_scaling:
                set_scaling_mode(self.output, previous_scaling)
            self.set_status(self.tr("launch_failed") % exc)
            return

        if previous_scaling:
            self.watch_process(process, previous_scaling)

    def watch_process(self, process, previous_scaling):
        """Waits for the game in a background thread, so the screen setting
        goes back to what it was without freezing the interface."""
        output = self.output

        def waiter():
            try:
                process.wait()
            except Exception:
                pass
            set_scaling_mode(output, previous_scaling)
            GLib.idle_add(self.set_status, self.tr("restored_screen"))

        threading.Thread(target=waiter, daemon=True).start()

    def on_show_log(self, _btn):
        path = os.path.join(self.game_dir, "error.log")
        if not os.path.exists(path):
            self.set_status(self.tr("no_log") % self.game_dir)
            return
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                content = fh.read()[-20000:]
        except Exception as exc:
            self.set_status(self.tr("read_failed") % exc)
            return

        win = Gtk.Window(title="error.log", transient_for=self, modal=True)
        win.set_default_size(800, 560)
        view = Gtk.TextView()
        view.set_editable(False)
        view.set_monospace(True)
        view.get_buffer().set_text(content)
        scroller = Gtk.ScrolledWindow()
        scroller.set_child(view)
        win.set_child(scroller)
        win.present()

    def on_pick_dir(self, _btn):
        dialog = Gtk.FileDialog()
        dialog.set_title(self.tr("folder_dialog"))
        dialog.set_initial_folder(Gio.File.new_for_path(self.game_dir))

        def done(dlg, result):
            try:
                folder = dlg.select_folder_finish(result)
            except GLib.Error:
                return
            if folder is not None:
                self.game_dir = folder.get_path()
                self.save_settings()
                self.reload_all()

        dialog.select_folder(self, None, done)

    def set_status(self, text):
        self.status.set_text(text)
        return False


class LauncherApp(Gtk.Application):

    def __init__(self):
        super().__init__(application_id=APP_ID,
                         flags=Gio.ApplicationFlags.FLAGS_NONE)

    def do_activate(self):
        win = self.props.active_window
        if not win:
            win = LauncherWindow(self)
        win.present()


if __name__ == "__main__":
    sys.exit(LauncherApp().run(sys.argv))
