# === DRAMA (Tragödie/Komödie) – Sprecher stabil, {Titel}, Stufenlayout a/b/c/d (kumulative Einrückung) ===
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from pathlib import Path
from shared.fonts_and_styles import register_dejavu
register_dejavu(Path(__file__).resolve().parent / "shared" / "fonts")
# Versmaß-Funktionalität
from shared.versmass import has_meter_markers, extract_meter

from reportlab.lib.pagesizes import A4
from reportlab.lib.units    import mm as RL_MM
from reportlab.lib.styles   import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums    import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.pdfbase      import pdfmetrics
from reportlab.platypus     import SimpleDocTemplate, Paragraph, Spacer, KeepTogether, Table, TableStyle, Flowable
from reportlab.lib          import colors
import re, os, html, unicodedata, json, argparse

# Import für Preprocessing
try:
    from shared import preprocess
except ImportError:
    # Fallback für direkten Aufruf
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from shared import preprocess

# ========= Optik / Einheiten =========
MM = RL_MM

# Globaler Flag für lateinische Texte (keine Versmaß-Marker-Entfernung)
CURRENT_IS_LATIN = False

# Hilfsfunktion für String-Breite
def _sw(text: str, font_name: str, font_size: float) -> float:
    """Berechnet die Breite eines Textes in Punkten."""
    try:
        return pdfmetrics.stringWidth(text, font_name, font_size)
    except:
        return len(text) * font_size * 0.6  # Fallback
GR_SIZE = 8.4
DE_SIZE = 7.0
SECTION_SIZE = 12.0

# Titel (geschweifte Klammern)
TITLE_BRACE_SIZE   = 18.0
TITLE_SPACE_AFTER  = 6.0   # mm

# Überschriften (eckige Klammern / Gleichheitszeichen)
SECTION_SIZE       = 11.0  # kleiner als vorher (war 12.0)
SECTION_SPACE_BEFORE_MM = 4.0  # kleinerer Abstand vor Überschrift
SECTION_SPACE_AFTER_MM  = 3.0  # kleinerer Abstand nach Überschrift

# Gleichheitszeichen-Überschriften (wie in Prosa)
# WICHTIG: Größen-Staffelung: ==== (größte) > === > == (kleinste)
H1_EQ_SIZE = 24.0              # Größe der H1-Überschriften (==== Text ====) - verkleinert
H1_SPACE_AFTER_MM = 4          # Abstand nach H1-Überschriften
H2_EQ_SIZE = 18.0              # Größe der H2-Überschriften (=== Text ===) - verkleinert
H2_SPACE_AFTER_MM = 3          # Abstand nach H2-Überschriften
H3_EQ_SIZE = 15.3              # Größe der H3-Überschriften (== Text ==)
H3_SPACE_AFTER_MM = 2          # Abstand nach H3-Überschriften

# ========= ABSTÄNDE-REGLER (POESIE) =========
# Diese Regler steuern alle Abstände in den Poesie-PDFs

# 1. ABSTÄNDE ZWISCHEN VERSPAAREN (Abstand von einem Verspaar zum nächsten)
INTER_PAIR_GAP_MM_VERSMASS = 0.0    # Abstand zwischen Verspaaren bei Versmaß-PDFs
INTER_PAIR_GAP_MM_NORMAL_TAG = 2.0      # Abstand zwischen Verspaaren bei Tag PDFs (KOMPAKTER als vorher!)
INTER_PAIR_GAP_MM_NORMAL_NOTAG = 1.0    # Abstand zwischen Verspaaren bei NoTag PDFs (MAXIMAL ENG: 1.0mm)

# 2. ABSTÄNDE INNERHALB EINES VERSPAARS
# 2a. Abstand zwischen antiker Zeile und erster Übersetzungszeile
INTRA_PAIR_ANCIENT_TO_MODERN_TAG = 0.7      # Mit Tags (KOMPAKTER: 0.7mm statt 1.5mm)
INTRA_PAIR_ANCIENT_TO_MODERN_NOTAG = 0.2    # Ohne Tags (MAXIMAL ENG: 0.2mm wie Prosa)

# 2b. Abstand zwischen den 2 Übersetzungszeilen (nur bei 3-sprachigen PDFs)
INTRA_PAIR_DE_TO_EN = -1.5          # Negativ = sehr eng, 0 = normal, positiv = mehr Abstand

# Fallback für Kompatibilität (wird dynamisch gesetzt)
INTER_PAIR_GAP_MM = 4.5

# Sprecher-Laterne (links)
SPEAKER_COL_MIN_MM = 0.0   # breitere Laterne
SPEAKER_GAP_MM     = 0.0    # größerer fester Abstand zwischen Laterne und Text
NUM_GAP_MM         = 1.0
SPEAKER_EXTRA_PAD_PT = 4.0   # zusätzlicher Puffer in Punkten, verhindert Zeilenumbruch von ":" etc.

CELL_PAD_LR_PT      = 0.0
SAFE_EPS_PT         = 0.5
CURRENT_IS_NOTAGS = False   # wird in create_pdf() anhand des Ziel-Dateinamens gesetzt
METER_ADJUST_LEFT_PT  = 1.6  # Schieberegler für Silben LINKS von |
METER_ADJUST_RIGHT_PT = 1.6  # Schieberegler für Silben RECHTS von |

WJ = '\u2060'  # Word Joiner für unsichtbare Verbindungen
def nobreak_chars(s: str) -> str: return WJ.join(list(s))

# Präzise Zentrierung eines Wortes in einer vorgegebenen Spaltenbreite
def center_word_in_width(word_html: str, word_width_pt: float, total_width_pt: float,
                         font_name: str, font_size: float) -> str:
    if word_width_pt >= total_width_pt or not word_html:
        return word_html
    padding_width_needed = total_width_pt - word_width_pt
    nbsp = '\u00A0'
    nbsp_width = pdfmetrics.stringWidth(nbsp, font_name, font_size)
    if nbsp_width <= 0:
        return word_html
    total_nbsp_needed = round(padding_width_needed / nbsp_width)
    left_nbsp = total_nbsp_needed // 2
    right_nbsp = total_nbsp_needed - left_nbsp
    return f'{nbsp * left_nbsp}{word_html}{nbsp * right_nbsp}'

# ------- EINSTELLUNGEN (gemeinsames CFG wie im Epos-Code) -------
CFG = {
    'TAG_WIDTH_FACTOR_TAGGED': 0.8,    # vorher effektiv ~1.30 → etwas enger
    'TOKEN_PAD_PT_VERSMASS_TAG': 2.0,    # Regler für Abstand zwischen Wörtern bei _Versmaß+Tag PDFs
    'TOKEN_PAD_PT_VERSMASS_NOTAG': 4,  # Regler für Abstand zwischen Wörtern bei _Versmaß+NoTag PDFs
    'TOKEN_PAD_PT_NORMAL_TAG': 2.5,      # Regler für Abstand zwischen Wörtern bei Normal+Tag PDFs (REDUZIERT für Kompaktheit)
    'TOKEN_PAD_PT_NORMAL_NOTAG': 2.0,    # Regler für Abstand zwischen Wörtern bei Normal+NoTag PDFs
    'NUM_COLOR': colors.black,
    'NUM_SIZE_FACTOR': 0.84,
    # Versmaß (wie im Epos-Code)
    'TOPLINE_Y_FACTOR': 2.5,
    'LONG_THICK_PT': 0.9,
    'BREVE_HEIGHT_PT': 3.8,
    'BAR_THICK_PT': 0.8,
    'TAG_WIDTH_FACTOR': 0.80,  # wie im Epos-Code
    'TOKEN_BASE_PAD_PT_TAGS': 1.0,     # Grundpuffer bei getaggten Tokens (klein)
    'TOKEN_BASE_PAD_PT_NOTAGS': 1.3,   # Grundpuffer bei ungetaggten Tokens (sichtbar)
}

# ========= Tags/Regex =========
# Standard-Tag-Definitionen (können durch Tag-Config überschrieben werden)
DEFAULT_SUP_TAGS = {'N','D','G','A','V','Du','Adj','Pt','Prp','Adv','Kon','Art','≈','Kmp','ij','Sup','Abl'}  # NEU: Abl für Latein
DEFAULT_SUB_TAGS = {'Prä','Imp','Aor','Per','Plq','Fu','Inf','Imv','Akt','Med','Pas','Knj','Op','Pr','AorS','M/P','Gdv','Ger','Spn','Fu1','Fu2'}  # NEU: Gdv, Ger, Spn, Fu1, Fu2 für Latein

# Dynamische Tag-Konfiguration (wird zur Laufzeit gesetzt)
SUP_TAGS = DEFAULT_SUP_TAGS.copy()
SUB_TAGS = DEFAULT_SUB_TAGS.copy()

# ======= Dynamische Hoch/Tief-Overrides aus dem Preprocess/UI =======
# Mapping: Tag -> "sup" | "sub" | "off"
# - "sup": Tag wird als <sup> gesetzt (egal ob bisher SUP oder SUB)
# - "sub": Tag wird als <sub> gesetzt
# - "off": Tag wird unterdrückt (gar nicht angezeigt/mitsummiert)
PLACEMENT_OVERRIDES: dict[str, str] = {}

def load_tag_config(config_file: str = None) -> None:
    """Lädt Tag-Konfiguration aus JSON-Datei"""
    global SUP_TAGS, SUB_TAGS, PLACEMENT_OVERRIDES
    
    if not config_file or not os.path.exists(config_file):
        return
    
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # Aktualisiere SUP_TAGS
        if 'sup_tags' in config:
            SUP_TAGS = set(config['sup_tags'])
        
        # Aktualisiere SUB_TAGS
        if 'sub_tags' in config:
            SUB_TAGS = set(config['sub_tags'])
        
        # Aktualisiere PLACEMENT_OVERRIDES
        if 'placement_overrides' in config:
            PLACEMENT_OVERRIDES = config['placement_overrides']
        
        print(f"Tag-Konfiguration geladen: {len(SUP_TAGS)} SUP, {len(SUB_TAGS)} SUB")
        
    except Exception as e:
        print(f"Fehler beim Laden der Tag-Konfiguration: {e}")

def _normalize_tag_case(tag: str) -> str:
    """
    Normalisiert Tag-Groß-/Kleinschreibung für Kompatibilität.
    Konvertiert Ij -> ij für Rückwärtskompatibilität.
    """
    if tag == 'Ij':
        return 'ij'
    return tag

def _classify_tag_with_overrides(tag: str) -> str:
    """
    Rückgabe: "sup" | "sub" | "rest" | "off"
    - Overrides haben Vorrang.
    - Ohne Override: Klassifikation nach SUP_TAGS/SUB_TAGS; sonst "rest".
    """
    # Normalisiere Tag für Kompatibilität
    normalized_tag = _normalize_tag_case(tag)
    
    v = PLACEMENT_OVERRIDES.get(normalized_tag)
    if v in ("sup", "sub", "off"):
        return v

    # ZUERST: Prüfe ob das gesamte Tag direkt in den Listen enthalten ist
    if normalized_tag in SUP_TAGS:
        return "sup"
    if normalized_tag in SUB_TAGS:
        return "sub"
    
    # Fallback: zusammengesetzte Tags "A/B" zulassen (aber nur wenn alle Teile in den Listen sind)
    parts = [p for p in normalized_tag.split('/') if p]
    if parts and all(p in SUP_TAGS for p in parts):
        return "sup"
    if parts and all(p in SUB_TAGS for p in parts):
        return "sub"
    return "rest"

def _partition_tags_for_display(tags: list[str]) -> tuple[list[str], list[str], list[str]]:
    """Teile in (sups, subs, rest) auf und wende Overrides an; 'off' wird entfernt."""
    sups, subs, rest = [], [], []
    for t in tags:
        cls = _classify_tag_with_overrides(t)
        normalized_tag = _normalize_tag_case(t)  # Normalisiere für Rückgabe
        if cls == "sup":
            sups.append(normalized_tag)
        elif cls == "sub":
            subs.append(normalized_tag)
        elif cls == "rest":
            rest.append(normalized_tag)
        # "off" -> ignorieren
    return sups, subs, rest


RE_INLINE_MARK  = re.compile(r'^\(\s*(?:[0-9]+[a-z]*|[a-z])\s*\)$', re.IGNORECASE)
RE_TAG       = re.compile(r'\(\s*([A-Za-z/≈äöüßÄÖÜ]+)\s*\)')
RE_TAG_NAKED = re.compile(r'\(\s*[A-Za-z0-9/≈äöüßÄÖÜ]+\s*\)')
RE_GREEK_CHARS = re.compile(r'[\u0370-\u03FF\u1F00-\u1FFF]')
RE_TAG_FINDALL = re.compile(r'\(\s*([A-Za-z0-9/≈äöüßÄÖÜ]+)\s*\)')  # NEU: 0-9 für Fu1, Fu2
RE_TAG_STRIP   = re.compile(r'\(\s*[A-Za-z0-9/≈äöüßÄÖÜ]+\s*\)')  # NEU: 0-9 für Fu1, Fu2
RE_LEADING_BAR_COLOR = re.compile(r'^\|\s*([+\-#§$])')  # |+ |# |- am Tokenanfang

# ----------------------- Defensive token-helpers -----------------------
def _strip_tags_from_token(tok: str) -> str:
    """Entfernt alle '(TAG)'-Stücke aus einem Token (defensiv)."""
    if not tok:
        return tok
    return RE_TAG_STRIP.sub('', tok)

def _token_display_text_from_token(tok: str) -> str:
    """
    Baut die endgültige Textdarstellung für ein Token (ohne Tags).
    Falls Token Farbmarker enthält (|+ oder führende #), belassen wir sie oder entfernen sie je Policy.
    Für defensive Entfernung: entferne Tags und gebe HTML-escaped Text zurück.
    """
    cleaned = _strip_tags_from_token(tok)
    # HTML-escape für sichere Darstellung
    return html.escape(cleaned)

# Sprecher-Tokens: [Χορ:] bzw. Λυσ:
RE_SPK_BRACKET = re.compile(r'^\[[^\]]*:\]$')                         # [Χορ:]
RE_SPEAKER_GR  = re.compile(r'^[\u0370-\u03FF\u1F00-\u1FFF]+:$')      # Λυσ:

RE_SECTION         = re.compile(r'^\s*\[\[\s*(.+?)\s*\]\]\s*$')
RE_SECTION_SINGLE  = re.compile(r'^\s*\[\s*(.+?)\s*\]\s*$')
RE_BRACE_TITLE     = re.compile(r'^\s*\{\s*(.+?)\s*\}\s*$')           # {Titel}
RE_ZEILE_LOST      = re.compile(r'^\s*(\(\d+[a-z]*\))?\s*(\[[^\]]*:\])?\s*\[\[Zeile\s+Lost\]\]\s*$', re.IGNORECASE)  # [[Zeile Lost]] mit optionaler Zeilennummer und Sprecher

# Gleichheitszeichen-Überschriften (wie in Prosa)
# WICHTIG: Reihenfolge der Prüfung: ==== zuerst, dann ===, dann ==
RE_EQ_H1 = re.compile(r'^\s*={4}\s*(.+?)\s*={4}\s*$')                 # ==== Text ====
RE_EQ_H2 = re.compile(r'^\s*={3}\s*(.+?)\s*={3}\s*$')                 # === Text ===
RE_EQ_H3 = re.compile(r'^\s*={2}\s*(.+?)\s*={2}\s*$')                 # == Text ==

# Label-Token wie [12], [12a], (12), (12a) – optional mit Punkt
RE_LABEL_TOKEN     = re.compile(r'^[\[\(]\s*(-?\d+)([a-z])?\s*[\]\)]\.?$', re.IGNORECASE)
RE_LABEL_STRIP     = re.compile(r'^(?:\[\s*-?\d+[a-z]?\s*\]\.?\s*|\(\s*-?\d+[a-z]?\s*\)\.?\s*)', re.IGNORECASE)

# ========= Utils =========
def _leading_for(size: float) -> float: return round(size * 1.30 + 0.6, 1)
def xml_escape(text:str) -> str:        return html.escape(text or '', quote=False)

def is_empty_or_sep(line:str) -> bool:
    t = (line or '').strip()
    return (not t) or t.upper() in {'[FREIE ZEILE]', '[ENTERZEICHEN]'} or t.startswith('---')

def normalize_spaces(s:str) -> str:
    return re.sub(r'\s+', ' ', (s or '').strip())

def pre_substitutions(s:str) -> str:
    """
    DEAKTIVIERT: Input-Texte gelten als "gesäubert", keine automatischen Umstellungen mehr.
    Die Funktion gibt den String unverändert zurück.
    """
    if not s: return s
    # Alte Regeln deaktiviert - Input-Texte sind bereits korrekt formatiert
    # punct = r'(?:,|\.|;|:|!|\?|%|…|\u00B7|\u0387|\u037E)'
    # s = re.sub(rf'\s+{punct}', lambda m: m.group(0).lstrip(), s)
    # s = re.sub(r'([\(\[\{\«"‹''])\s+', r'\1', s)
    # s = re.sub(r'\s+([\)\]\}\»"›''])', r'\1', s)
    # s = re.sub(r'[\u200B\u200C\u200D\uFEFF\u00A0]', '', s)
    # s = re.sub(r'\(([#\+\-])', r'\1(', s)
    # s = re.sub(r'\[([#\+\-])', r'\1[', s)
    # s = re.sub(r'\{([#\+\-])', r'\1{', s)
    return s

def _sw(text:str, font:str, size:float) -> float:
    return pdfmetrics.stringWidth(text, font, size)

# === Klassifikation: führendes Label & Sprecher nur für Klassifikation entfernen ===
def _strip_speaker_prefix_for_classify(line: str) -> str:
    s = (line or '').strip()
    s = RE_LABEL_STRIP.sub('', s, count=1)
    m = re.match(r'^\[[^\]]*:\]\s*(.*)$', s)  # [Χορ:]
    if m: return m.group(1)
    m2 = re.match(r'^[\u0370-\u03FF\u1F00-\u1FFF]+:\s*(.*)$', s)  # Χορ:
    if m2: return m2.group(1)
    return s

def extract_line_number(s: str) -> tuple[str | None, str]:
    """
    Extrahiert die Zeilennummer am Anfang einer Zeile.
    Format: (123) oder (123a) oder (123b) etc.
    NEU: Auch (123k) für Kommentare und (123i) für Insertionszeilen.
    NEU: Auch (220-222k) für Bereichs-Kommentare.
    
    Returns:
        (line_number, rest_of_line) oder (None, original_line)
    
    Beispiele:
        "(1) Text hier" → ("1", "Text hier")
        "(100a) Text" → ("100a", "Text")
        "(50k) Kommentar hier" → ("50k", "Kommentar hier")
        "(300i) Insertion hier" → ("300i", "Insertion hier")
        "(220-222k) Kommentar zu Zeilen 220-222" → ("220-222k", "Kommentar zu Zeilen 220-222")
        "Text ohne Nummer" → (None, "Text ohne Nummer")
    """
    s = (s or '').strip()
    # NEU: Regex für Bereichs-Kommentare: (zahl-zahl+k/i)
    m_range = re.match(r'^\((-?\d+)-(-?\d+)([a-z]?)\)\s*(.*)$', s, re.IGNORECASE)
    if m_range:
        start = m_range.group(1)
        end = m_range.group(2)
        suffix = m_range.group(3)
        rest = m_range.group(4)
        return (f"{start}-{end}{suffix}", rest)
    
    # Regex für Zeilennummer: (Zahl[optionaler Buchstabe oder k/i]) - auch negative Zahlen!
    # k = Kommentar, i = Insertion
    m = re.match(r'^\((-?\d+[a-z]?)\)\s*(.*)$', s, re.IGNORECASE)
    if m:
        return (m.group(1), m.group(2))
    return (None, s)

def is_comment_line(line_num: str | None) -> bool:
    """Prüft, ob eine Zeilennummer ein Kommentar ist (endet mit 'k')."""
    if not line_num:
        return False
    return line_num.lower().endswith('k')

def extract_line_range(line_num: str | None) -> tuple[int | None, int | None]:
    """
    Extrahiert den Zeilenbereich aus einer Zeilennummer wie "220-222k".
    
    Returns:
        (start_line, end_line) oder (None, None) wenn kein Bereich
        Bei einzelnen Zeilen: (line_num, line_num)
    
    Beispiele:
        "220-222k" → (220, 222)
        "50k" → (50, 50)
        "100" → (100, 100)
        None → (None, None)
    """
    if not line_num:
        return (None, None)
    
    # Prüfe auf Bereichs-Format: "220-222k"
    range_match = re.match(r'^(-?\d+)-(-?\d+)', line_num)
    if range_match:
        try:
            start = int(range_match.group(1))
            end = int(range_match.group(2))
            return (start, end)
        except ValueError:
            return (None, None)
    
    # Einzelne Zeile: Extrahiere die Zahl
    num_match = re.match(r'^(-?\d+)', line_num)
    if num_match:
        try:
            num = int(num_match.group(1))
            return (num, num)
        except ValueError:
            return (None, None)
    
    return (None, None)

# Farben für Kommentare (Rotation: rot → blau → grün → rot)
COMMENT_COLORS = [
    (0.95, 0.9, 0.9),   # Sanft rot (RGB)
    (0.9, 0.95, 1.0),   # Sanft blau
    (0.9, 1.0, 0.9),    # Sanft grün
]

def get_comment_color(comment_index: int) -> tuple[float, float, float]:
    """Gibt die Farbe für einen Kommentar basierend auf dem Index zurück (Rotation: rot → blau → grün)."""
    return COMMENT_COLORS[comment_index % len(COMMENT_COLORS)]

def is_insertion_line(line_num: str | None) -> bool:
    """Prüft, ob eine Zeilennummer eine Insertion ist (endet mit 'i')."""
    if not line_num:
        return False
    return line_num.lower().endswith('i')

def is_greek_line(line: str) -> bool:
    """
    DEPRECATED: Alte Methode basierend auf griechischen Buchstaben.
    Robustere Erkennung griechischer Zeilen.
    Zählt nur griechische Buchstaben (keine Satzzeichen) und verlangt
    mindestens 2 griechische Buchstaben für eine valide griechische Zeile.
    """
    if not line:
        return False

    # Zähle griechische Buchstaben (nur Letters, keine Satzzeichen)
    greek_letters = 0
    for ch in line:
        if unicodedata.category(ch).startswith('L'):  # Letter category
            cp = ord(ch)
            if (0x0370 <= cp <= 0x03FF) or (0x1F00 <= cp <= 0x1FFF):
                greek_letters += 1

    # Mindestens 2 griechische Buchstaben für eine griechische Zeile
    return greek_letters >= 2

def is_latin_line(s:str) -> bool:
    """
    Erkennt lateinische Zeilen anhand lateinischer Buchstaben.
    Lateinisch = normale ASCII-Buchstaben, aber keine deutschen Umlaute.
    """
    if not s:
        return False
    s = s.strip()
    # Entferne Zeilennummer, Sprecher, Tags etc. für die Analyse
    s_clean = re.sub(r'^\(\d+[a-z]*\)', '', s)  # Zeilennummer
    s_clean = re.sub(r'^\[[^\]]*:\]', '', s_clean)  # Sprecher
    s_clean = re.sub(r'\([^)]*\)', '', s_clean)  # Tags
    
    # Zähle lateinische Buchstaben (a-z, A-Z, aber keine Umlaute)
    latin_count = sum(1 for ch in s_clean if ch.isalpha() and ord(ch) < 128)
    # Zähle deutsche Umlaute
    german_count = sum(1 for ch in s_clean if ch in 'äöüÄÖÜß')
    
    # Wenn mehr lateinische als deutsche Buchstaben → lateinisch
    return latin_count > german_count and latin_count >= 2

def _color_from_marker(ch):
    if ch == '+': return '#1E90FF'
    if ch == '-': return '#228B22'
    if ch == '#': return '#FF0000'
    if ch == '§': return '#9370DB'  # Sanftes Violett (wie Blumen) - Pendant zum sanften Blau
    if ch == '$': return '#FFA500'  # Orange
    return None

def _strip_leading_bar_color(core: str):
    m = RE_LEADING_BAR_COLOR.match(core)
    if not m:
        return core, None, False
    color = _color_from_marker(m.group(1))
    # Rekonstruiere den String, indem nur der Farbmarker aus dem Match entfernt wird
    new_core = m.group(0).replace(m.group(1), '') + core[m.end():]
    return new_core, color, True


def _end_has_bar(tok: str) -> bool:
    if not tok: return False
    t = RE_TAG_STRIP.sub('', tok)
    return bool(re.search(r'\|+\s*$', t))

def _has_leading_bar(tok: str) -> bool:
    if not tok: return False
    t = RE_TAG_STRIP.sub('', tok)
    return bool(RE_LEADING_BAR_COLOR.match(t) or t.startswith('|'))

def same_foot(current_token: str, next_token: str) -> bool:
    if _end_has_bar(current_token): return False
    if _has_leading_bar(next_token): return False
    return True

def _make_core_html_with_invisible_bars(core_text:str, *, make_bars_invisible:bool, remove_bars_instead:bool = False) -> str:
    out_parts = []
    for ch in core_text:
        if ch == '|':
            if make_bars_invisible:
                out_parts.append('<font color="#FFFFFF">|</font>')
            elif remove_bars_instead:
                # Bei Nicht-Versmaß: komplett entfernen
                continue
            else:
                out_parts.append(xml_escape(ch))
        else:
            out_parts.append(xml_escape(ch))
    return ''.join(out_parts)

def _is_greek_letter(ch: str) -> bool:
    if not ch: return False
    if not unicodedata.category(ch).startswith('L'): return False
    cp = ord(ch)
    return (0x0370 <= cp <= 0x03FF) or (0x1F00 <= cp <= 0x1FFF)

# METER_CFG entfernt - wird jetzt aus dem gemeinsamen CFG genommen

class ToplineTokenFlowable(Flowable):
    def __init__(self, token_raw:str, style, cfg, *, gr_bold:bool,
                 had_leading_bar:bool, end_bar_count:int,
                 bridge_to_next:bool, next_has_leading_bar:bool,
                 is_first_in_line:bool=False, next_token_starts_with_bar:bool=False):
        super().__init__()
        self.token_raw = token_raw
        self.style = style
        self.cfg = cfg
        self.gr_bold = gr_bold
        self._para = None
        self._w = 0.0
        self._h = 0.0
        self._segments = []
        self._tags = []
        self._had_leading_bar = had_leading_bar
        self._end_bar_count = end_bar_count
        self._bridge_to_next = bridge_to_next
        self._next_has_leading_bar = next_has_leading_bar
        self.is_first_in_line = is_first_in_line
        self.next_token_starts_with_bar = next_token_starts_with_bar

    def _strip_prefix(self, s:str) -> str:
        # WICHTIG: Auch neue Farbmarker § (lila) und $ (orange) entfernen!
        return s[1:] if s and s[0] in '#+-§$' else s

    def _extract_tags(self, s_raw:str):
        body = self._strip_prefix(s_raw)
        found = RE_TAG_FINDALL.findall(body)
        self._tags = found
        return self._tags

    def _tag_visual_width(self, font:str, size:float) -> float:
        if not self._tags: return 0.0
        add = ''.join(self._tags)
        return self.cfg['TAG_WIDTH_FACTOR'] * pdfmetrics.stringWidth(add, font, size)

    def _core_with_markers(self) -> str:
        s = self._strip_prefix(self.token_raw)
        s = RE_TAG_STRIP.sub('', s)
        s = re.sub(r'\|+\s*$', '', s)
        s, _c, _had_leading = _strip_leading_bar_color(s)
        return s

    def _core_visible_text(self) -> str:
        s = self._core_with_markers()
        # DEAKTIVIERT für lateinische Texte: i, r, L sind normale Buchstaben, keine Versmaß-Marker
        if not CURRENT_IS_LATIN:
            s = re.sub(r'[Lir]+', '', s).replace('-', '|')
        return s.strip()

    def _parse_segments(self):
        s = self._core_with_markers()
        greek_idx, seg_start = 0, 1
        self._segments = []
        for ch in s:
            if _is_greek_letter(ch):
                greek_idx += 1; continue
            if ch in ('L', 'i', 'r'):
                if greek_idx >= seg_start:
                    self._segments.append((seg_start, greek_idx, ch))
                seg_start = greek_idx + 1

    def _letter_positions(self, text_visible:str, font:str, size:float):
        acc = 0.0
        pos = [0.0]
        for ch in text_visible:
            w = pdfmetrics.stringWidth(ch, font, size)
            acc += w
            if _is_greek_letter(ch):
                pos.append(acc)
        return pos

    def _bar_x_positions(self, font:str, size:float):
        t = self.token_raw.strip()
        if t and t[0] in '#+-§$': t_work = t[1:]
        else: t_work = t
        t_no_tags = RE_TAG_STRIP.sub('', t_work)

        lead_m = RE_LEADING_BAR_COLOR.match(t_no_tags)
        had_leading = bool(lead_m)
        if had_leading:
            t_core = t_no_tags[lead_m.end():]
        else:
            t_core = t_no_tags

        m = re.search(r'\|+\s*$', t_core)
        if m:
            core_part = t_core[:m.start()]
            trailing_bars = t_core[m.start():]
        else:
            core_part = t_core
            trailing_bars = ''

        bar_w = pdfmetrics.stringWidth('|', font, size)
        eps   = max(0.15, bar_w * 0.2)
        xs = []
        acc = 0.0

        if had_leading:
            xs.append(0.5*bar_w)
            acc += bar_w

        for ch in core_part:
            if ch in ('L','i','r'): continue
            if ch == '-':
                acc += bar_w
            elif ch == '|':
                xs.append(acc + 0.5*bar_w); acc += bar_w
            else:
                acc += pdfmetrics.stringWidth(ch, font, size)

        acc += self._tag_visual_width(font, size)

        for ch in trailing_bars:
            if ch == '|':
                xs.append(acc + 0.5*bar_w); acc += bar_w
            else:
                acc += pdfmetrics.stringWidth(ch, font, size)

        xs.sort()
        dedup = []
        for x in xs:
            if not dedup or abs(x - dedup[-1]) > eps:
                dedup.append(x)
        return dedup

    def wrap(self, availWidth, availHeight):
        self._extract_tags(self.token_raw)
        vis_markup = format_token_markup(self.token_raw, is_greek_row=True, gr_bold=self.gr_bold, remove_bars_instead=False)
        self._para = Paragraph(vis_markup, self.style)
        w, h = self._para.wrap(availWidth, availHeight)
        self._w, self._h = w, h
        self._parse_segments()
        return w, h + (self.style.fontSize * self.cfg['TOPLINE_Y_FACTOR'])

    def draw(self):
        c = self.canv
        if not self._para:
            self.wrap(self.width, self.height)
            if not self._para: return
        
        self._para.drawOn(c, 0, 0)
        font = self.style.fontName
        size = self.style.fontSize
        y = (self.style.fontSize * self.cfg['TOPLINE_Y_FACTOR'])
        text_vis = self._core_visible_text()
        letter_pos = self._letter_positions(text_vis, font, size)
        total_greek = len(letter_pos) - 1
        tag_w = self._tag_visual_width(font, size)
        bar_xs = self._bar_x_positions(font, size)

        # Semantische Analyse für Schieberegler
        starts_after_bar_indices = set()
        ends_before_bar_indices = set()
        core_text = self._core_with_markers()
        
        # Intra-Token-Analyse
        greek_idx = 0
        is_after_bar = self._had_leading_bar
        for ch in core_text:
            if _is_greek_letter(ch):
                greek_idx += 1
                if is_after_bar:
                    starts_after_bar_indices.add(greek_idx)
                    # "Spiegelung": Die vorherige Silbe endet vor der aktuellen Antenne
                    if (greek_idx - 1) > 0:
                         ends_before_bar_indices.add(greek_idx - 1)
                    is_after_bar = False
            elif ch == '|':
                is_after_bar = True
                # Die vorherige Silbe endet vor dieser Antenne
                if greek_idx > 0:
                    ends_before_bar_indices.add(greek_idx)
        
        # Inter-Token-Analyse
        if self.next_token_starts_with_bar and total_greek > 0:
            ends_before_bar_indices.add(total_greek)

        c.saveState()
        c.setLineWidth(self.cfg['LONG_THICK_PT'])
        if self._segments:
            num_segments = len(self._segments)
            for idx, (st, en, kind) in enumerate(self._segments):
                if st <= 0 or en > total_greek: continue
                
                x0_base = letter_pos[st - 1]
                x1_base = letter_pos[en]
                x0_draw, x1_draw = x0_base, x1_base

                # Brücke zum nächsten Token (Epos-Stil)
                if idx == num_segments - 1:
                    # Hier wird die unkorrigierte x1_base für die Brückenberechnung verwendet
                    x1_final = x1_base + tag_w
                    if self._bridge_to_next:
                        # Für die Brücke wird der bereits korrigierte x1_draw Wert genutzt
                        x1_draw = max(x1_draw, self._w)
                    else:
                        x_anchor = None
                        if bar_xs:
                            for bx in bar_xs:
                                if bx >= x1_final - 0.05:
                                    x_anchor = bx; break
                        if x_anchor is not None:
                            x1_draw = x_anchor
                        elif self._next_has_leading_bar:
                             x1_draw = self._w
                        else:
                             x1_draw = x1_final

                # Wende Schieberegler basierend auf semantischer Analyse an (NACH Epos-Logik)
                if st in starts_after_bar_indices:
                    x0_draw += METER_ADJUST_RIGHT_PT
                if en in ends_before_bar_indices:
                    x1_draw += METER_ADJUST_LEFT_PT
                
                # Zeichne Linie oder Kurve
                if kind == 'L':
                    c.line(x0_draw, y, x1_draw, y)
                elif kind == 'i':
                    h = self.cfg['BREVE_HEIGHT_PT']
                    xm = (x0_draw + x1_draw) / 2.0
                    c.bezier(x0_draw, y, x0_draw, y - h, xm, y - h, xm, y)
                    c.bezier(xm, y, xm, y - h, x1_draw, y - h, x1_draw, y)
                elif kind == 'r':
                    c.saveState()
                    c.setStrokeColor(colors.red)
                    h = self.cfg['BREVE_HEIGHT_PT']
                    xm = (x0_draw + x1_draw) / 2.0
                    c.bezier(x0_draw, y, x0_draw, y + h, xm, y + h, xm, y)
                    c.bezier(xm, y, xm, y + h, x1_draw, y + h, x1_draw, y)
                    c.restoreState()

        c.restoreState()

        if bar_xs:
            c.saveState()
            c.setLineWidth(self.cfg['BAR_THICK_PT'])
            for xb in bar_xs:
                c.line(xb, 0.0, xb, y)
            c.restoreState()


# ========= Tokenizer / Label / Sprecher =========
def tokenize(line:str):
    # LATEINISCH: (N)(Abl) → (Abl) Transformation
    # Entferne (N) vor Ablativ-Tags, da Nomen mit Ablativ implizit sind
    if line and '(N)(Abl)' in line:
        # Prüfe ob es eine lateinische Zeile ist (enthält lateinische Buchstaben)
        if not RE_GREEK_CHARS.search(line):
            line = re.sub(r'\(N\)\(Abl\)', '(Abl)', line)
    
    line = normalize_spaces(pre_substitutions(line or ''))
    if not line: return []
    raw = line.split(' ')
    out, buf = [], []
    for tok in raw:
        if not tok: continue
        if buf:
            buf.append(tok)
            if tok.endswith(']'): 
                # NUR zusammenfassen wenn es ein Sprecher ist (endet mit `:]`)
                combined = ' '.join(buf)
                if combined.endswith(':]'):
                    out.append(combined)
                else:
                    # Philologische Marker - NICHT zusammenfassen!
                    out.extend(buf)
                buf = []
            continue
        if tok.startswith('[') and not tok.endswith(']'):
            # Start eines mehrteiligen Tokens - sammle erstmal
            buf = [tok]
            continue
        out.append(tok)
    if buf: 
        # Falls noch was im Buffer ist - als separate Tokens hinzufügen
        out.extend(buf)
    return out

def _is_label_token(t: str):
    return bool(RE_LABEL_TOKEN.match(t or ''))

def _is_staggered_label(label: str) -> bool:
    """
    Prüft, ob ein Label ein gültiges Suffix für gestaffelte Zeilen hat.
    Nur Suffixe a-g sind erlaubt (h, i, j, etc. sind für andere Zwecke wie Insertions).
    """
    if not label:
        return False
    # Extrahiere Suffix (letzter Buchstabe)
    suffix = label[-1].lower() if label[-1].isalpha() else ''
    # Nur a-g sind gültig für gestaffelte Zeilen
    return suffix in 'abcdefg'

def _pop_label(toks):
    if toks and _is_label_token(toks[0]):
        m = RE_LABEL_TOKEN.match(toks[0])
        label = f"{int(m.group(1))}{m.group(2) or ''}"
        base  = int(m.group(1))
        return label, base, toks[1:]
    return None, None, toks

def _is_speaker_token(t: str):
    return bool(RE_SPK_BRACKET.match(t or '')) or bool(RE_SPEAKER_GR.match(t or ''))

def _pop_speaker(toks):
    if not toks: return '', toks
    t0 = toks[0]
    if RE_SPK_BRACKET.match(t0):
        inner = t0[1:-1]
        if inner.endswith(':'): inner = inner[:-1]
        return inner.strip(), toks[1:]
    if RE_SPEAKER_GR.match(t0):
        return t0.rstrip(':'), toks[1:]
    return '', toks

def split_leading_label_and_speaker(tokens):
    """Entfernt am Anfang Label und Sprecher – in BELIEBIGER Reihenfolge. → (label:str|None, base:int|None, speaker:str, rest_tokens)"""
    toks = tokens[:]
    label, base, toks = _pop_label(toks)
    speaker, toks = _pop_speaker(toks)
    if label is None:
        speaker2, toks2 = _pop_speaker(tokens[:])
        if speaker2:
            label2, base2, toks3 = _pop_label(toks2)
            if label2 is not None:
                return label2, base2, speaker2, toks3
    return label, base, speaker, toks

# ------- Elisions-Übertragung (aus Epos übernommen) -------
APOSTS = (
    '\u02BC',  # ʼ MODIFIER LETTER APOSTROPHE (primär, das schönste!)
    '\u2019',  # ' RIGHT SINGLE QUOTATION MARK
    '\u1FBD',  # ᾽ GREEK KORONIS (in Kallimachos etc.)
)

def propagate_elision_markers(gr_tokens):
    out = gr_tokens[:]
    n = len(out)
    for i in range(n - 1):
        t = out[i]; u = out[i+1]
        idx_t = t.find('(')
        head_t = t if idx_t == -1 else t[:idx_t]
        tail_t = '' if idx_t == -1 else t[idx_t:]

        # wie rfind, aber für beide Apostrophe
        pos = max((head_t.rfind(a) for a in APOSTS), default=-1)
        if pos == -1:
            continue

        prev = head_t[pos-1] if pos > 0 else ''
        if prev in ('i', 'L', '|', 'r'):
            continue

        idx_u = u.find('(')
        head_u = u if idx_u == -1 else u[:idx_u]
        ch_m = next((ch for ch in head_u if ch in ('i','L','|','r')), None)
        if not ch_m:
            continue

        new_head_t = head_t[:pos] + ch_m + head_t[pos:]
        out[i] = new_head_t + tail_t

    return out  # <— siehe Fix B


# ========= Markup & Messung =========
def visible_measure_token(token:str, *, font:str, size:float, cfg, is_greek_row:bool) -> float:
    t = (token or '').strip()
    if not t: return 0.0

    if RE_INLINE_MARK.match(t):
        vis = t.replace(' ', '')
        w = _sw(nobreak_chars(vis), font, size)
        return w + cfg.get('SAFE_EPS_PT', 3.0) + 2 * cfg.get('CELL_PAD_LR_PT', 0.0)

    for color_char in ['#', '+', '-', '§', '$']:
        t = t.replace(color_char, '')
    t = t.replace('~', '')

    m_endbars = re.search(r'\|+\s*$', t)
    end_bar_count = len(m_endbars.group(0).strip()) if m_endbars else 0

    core_all = RE_TAG_STRIP.sub('', t).strip()
    core_no_end = re.sub(r'\|+\s*$', '', core_all)

    core_no_end, _color2, had_leading_bar = _strip_leading_bar_color(core_no_end)

    if is_greek_row and not CURRENT_IS_LATIN:
        # DEAKTIVIERT für lateinische Texte: i, r, L sind normale Buchstaben, keine Versmaß-Marker
        core_meas = re.sub(r'[Lir]+', '', core_no_end).replace('-', '|')
    else:
        core_meas = core_no_end

    tags = RE_TAG_FINDALL.findall(t)

    # Nur Tags mitzählen, die tatsächlich angezeigt werden (Overrides beachten)
    if is_greek_row and tags:
        sups, subs, rest = _partition_tags_for_display(tags)
        shown = sups + subs + rest  # "off" ist bereits entfernt
    else:
        shown = []

    w = _sw(core_meas, font, size)
    if is_greek_row and had_leading_bar:
        w += _sw('|', font, size)
    if is_greek_row and shown:
        w += cfg['TAG_WIDTH_FACTOR'] * _sw(''.join(shown), font, size)
    if is_greek_row and end_bar_count:
        w += end_bar_count * _sw('|', font, size)

    safe_eps = cfg.get('SAFE_EPS_PT', 3.0)
    cell_pad = cfg.get('CELL_PAD_LR_PT', 0.0)
    return w + safe_eps + 2 * cell_pad
    
def format_token_markup(token:str, *, is_greek_row:bool, gr_bold:bool, remove_bars_instead:bool = False) -> str:
    raw = (token or '').strip()
    if not raw: return ''

    color = None; color_pos = -1
    if '#' in raw: color_pos = raw.find('#'); color = '#FF0000'
    elif '+' in raw: color_pos = raw.find('+'); color = '#1E90FF'
    elif '-' in raw: color_pos = raw.find('-'); color = '#228B22'
    elif '§' in raw: color_pos = raw.find('§'); color = '#9370DB'  # Sanftes Violett (wie Blumen) - Pendant zum sanften Blau
    elif '$' in raw: color_pos = raw.find('$'); color = '#FFA500'  # Orange
    if color_pos >= 0: raw = raw[:color_pos] + raw[color_pos+1:]
    raw = raw.replace('~','')

    m_endbars = re.search(r'\|+\s*$', raw)
    end_bar_count = len(m_endbars.group(0).strip()) if m_endbars else 0

    tags = RE_TAG_FINDALL.findall(raw)
    core_all = RE_TAG_STRIP.sub('', raw).strip()
    core_no_end = re.sub(r'\|+\s*$', '', core_all)

    core_no_end, color2, had_leading_bar = _strip_leading_bar_color(core_no_end)
    if color2: color = color2 or color

    is_bold = gr_bold if is_greek_row else False
    if '*' in core_no_end:
        core_no_end = core_no_end.replace('*','')
        is_bold = True

    if is_greek_row and not CURRENT_IS_LATIN:
        # DEAKTIVIERT für lateinische Texte: i, r, L sind normale Buchstaben, keine Versmaß-Marker
        core_for_width = re.sub(r'[Lir]+', '', core_no_end).replace('-', '|')
        core_html_main = _make_core_html_with_invisible_bars(
            core_for_width,
            make_bars_invisible=(not remove_bars_instead),
            remove_bars_instead=remove_bars_instead
        )
        core_html = core_html_main
    else:
        core_html = xml_escape(core_no_end)

    if is_greek_row:
        # Partitioniere Tags nach Overrides
        sups, subs, rest = _partition_tags_for_display(tags)
    else:
        # DE-Zeile: nur ≈ als Sup (wie gehabt)
        sups, subs, rest = (['≈'] if '≈' in tags else []), [], []


    parts = []
    if is_bold: parts.append('<b>')
    if color:   parts.append(f'<font color="{color}">')
    parts.append(core_html)

    if is_greek_row and (sups or subs or rest): parts.append(WJ)
    for t in sups: parts.append(f'<sup>{xml_escape(t)}</sup>{WJ}')
    for t in subs: parts.append(f'<sub>{xml_escape(t)}</sub>{WJ}')
    for t in rest: parts.append(f'({xml_escape(t)}){WJ}')

    if is_greek_row and end_bar_count > 0 and not remove_bars_instead:
        parts.append('<font color="#FFFFFF">' + ('|' * end_bar_count) + '</font>')

    if color:   parts.append('</font>')
    if is_bold: parts.append('</b>')
    return ''.join(parts)

def measure_line_width(gr_tokens, de_tokens=None, *, font:str, size:float, font_de:str=None, size_de:float=None, cfg=None) -> float:
    """Summiert die sichtbaren Tokenbreiten beider Zeilen und nimmt das Maximum."""
    if de_tokens is None:
        de_tokens = []
    if cfg is None:
        cfg = CFG

    # Berechne Breite der griechischen Zeile
    gr_width = sum(visible_measure_token(t, font=font, size=size, cfg=cfg, is_greek_row=True) for t in gr_tokens)

    # Berechne Breite der deutschen Zeile (falls vorhanden)
    if de_tokens and (font_de and size_de):
        de_width = sum(visible_measure_token(t, font=font_de, size=size_de, cfg=cfg, is_greek_row=False) for t in de_tokens)
    else:
        de_width = 0.0

    # Nimm die breitere Zeile als Basisbreite
    return max(gr_width, de_width)

def measure_rendered_line_width(gr_tokens, de_tokens, *, gr_bold:bool, is_notags:bool, remove_bars_instead:bool = False) -> float:
    """
    Berechnet die tatsächliche gerenderte Breite einer Zeile unter Berücksichtigung
    aller Formatierungsoptionen (Tags, Fettdruck, Versmaß-Marker, etc.)
    """
    if not gr_tokens:
        gr_tokens = []
    if not de_tokens:
        de_tokens = []

    # Verwende die gleichen Fonts wie in create_pdf
    GR_SIZE = 8.4
    DE_SIZE = 7.8
    gr_font = 'DejaVu-Bold' if gr_bold else 'DejaVu'
    de_font = 'DejaVu'

    # Temporär CURRENT_IS_NOTAGS setzen für korrekte Messung
    global CURRENT_IS_NOTAGS
    original_notags = CURRENT_IS_NOTAGS
    CURRENT_IS_NOTAGS = is_notags

    try:
        # Berechne griechische Breite mit voller Formatierung
        gr_width = 0.0
        for token in gr_tokens:
            # Verwende format_token_markup um die tatsächliche Formatierung zu bekommen
            formatted = format_token_markup(token, is_greek_row=True, gr_bold=gr_bold, remove_bars_instead=remove_bars_instead)
            # Entferne HTML-Tags für Breitenberechnung
            plain_text = re.sub(r'<[^>]+>', '', formatted)
            if plain_text.strip():
                gr_width += _sw(plain_text, gr_font, GR_SIZE)

        # Berechne deutsche Breite
        de_width = 0.0
        for token in de_tokens:
            formatted = format_token_markup(token, is_greek_row=False, gr_bold=gr_bold, remove_bars_instead=remove_bars_instead)
            plain_text = re.sub(r'<[^>]+>', '', formatted)
            if plain_text.strip():
                de_width += _sw(plain_text, de_font, DE_SIZE)

        return max(gr_width, de_width)

    finally:
        # Stelle ursprünglichen Wert wieder her
        CURRENT_IS_NOTAGS = original_notags

def measure_full_layout_width(gr_tokens, de_tokens, speaker, line_label, *,
                             token_gr_style, token_de_style, num_style, style_speaker,
                             global_speaker_width_pt, gr_bold:bool = False, is_notags:bool = False) -> float:
    """Berechnet die Gesamtbreite einer Zeile inklusive aller Layout-Elemente."""
    # Token-Breite (robuste Berechnung)
    token_width = measure_rendered_line_width(
        gr_tokens, de_tokens,
        gr_bold=gr_bold, is_notags=is_notags,
        remove_bars_instead=False
    )

    # Layout-Elemente Breite
    layout_width = 0.0

    # Nummernspalte
    num_w = max(6.0*MM, _sw('[999]', num_style.fontName, num_style.fontSize) + 2.0)
    layout_width += num_w + NUM_GAP_MM * MM

    # Sprecher-Laterne (falls vorhanden oder reserviert)
    if speaker or global_speaker_width_pt > 0:
        sp_w = max(global_speaker_width_pt, SPEAKER_COL_MIN_MM * MM)
        layout_width += sp_w + SPEAKER_GAP_MM * MM

    # Gesamtbreite = Layout-Elemente + Token-Breite
    return layout_width + token_width

# ========= Abschnitte / Titel =========
def detect_section(line:str):
    m = RE_SECTION.match(line or '')
    if m: return m.group(1).strip()
    m2 = RE_SECTION_SINGLE.match(line or '')
    if m2: return m2.group(1).strip()
    return None

def detect_eq_heading(line:str):
    """Erkennt Gleichheitszeichen-Überschriften wie ==== Text ==== oder === Text ==="""
    s = (line or '').strip()
    m = RE_EQ_H1.match(s)
    if m: return ('h1_eq', m.group(1).strip())
    m = RE_EQ_H2.match(s)
    if m: return ('h2_eq', m.group(1).strip())
    m = RE_EQ_H3.match(s)
    if m: return ('h3_eq', m.group(1).strip())
    return (None, None)

# ========= Parser =========
def process_input_file(fname:str):
    with open(fname, encoding='utf-8') as f:
        raw = [ln.rstrip('\n') for ln in f]
    
    # LATEINISCH: (N)(Abl) → (Abl) Transformation für ALLE Zeilen
    # Prüfe ob es ein lateinischer Text ist (keine griechischen Zeichen)
    is_latin_text = False
    for line in raw:
        if line.strip() and not is_empty_or_sep(line.strip()):
            is_latin_text = not RE_GREEK_CHARS.search(line)
            break
    
    if is_latin_text:
        raw = [re.sub(r'\(N\)\(Abl\)', '(Abl)', ln) for ln in raw]

    blocks = []
    i = 0
    while i < len(raw):
        line = (raw[i] or '').strip()
        if is_empty_or_sep(line):
            i += 1; continue

        # {Titel}
        m = RE_BRACE_TITLE.match(line)
        if m:
            blocks.append({'type':'title_brace', 'text': m.group(1).strip()})
            i += 1; continue

        # ==== Überschrift ==== / === Überschrift === / == Überschrift ==
        # WICHTIG: Entferne Zeilennummer vor der Prüfung, falls vorhanden
        line_num_temp, line_without_num = extract_line_number(line)
        htyp, htxt = detect_eq_heading(line_without_num if line_num_temp else line)
        if htyp:
            blocks.append({'type': htyp, 'text': htxt})
            i += 1; continue

        # [[Zeile Lost]] - Sonderfall: keine Übersetzung, keine Versmaß-Marker-Entfernung
        if RE_ZEILE_LOST.match(line):
            blocks.append({'type':'zeile_lost', 'text': line})
            i += 1; continue

        # [[Abschnitt]] / [Abschnitt]
        sec = detect_section(line)
        if sec:
            blocks.append({'type':'section', 'text':sec})
            i += 1; continue

        # NEUE LOGIK: Zeilennummern-basierte Paarbildung
        # Extrahiere Zeilennummer der aktuellen Zeile
        line_num, line_content = extract_line_number(line)
        
        # NEU: Kommentarzeilen erkennen (k) und als Kommentar-Blocks speichern
        if line_num is not None and is_comment_line(line_num):
            # Kommentar-Zeile: Extrahiere Zeilenbereich und speichere als Kommentar-Block
            start_line, end_line = extract_line_range(line_num)
            blocks.append({
                'type': 'comment',
                'line_num': line_num,
                'content': line_content,
                'start_line': start_line,
                'end_line': end_line,
                'original_line': line
            })
            i += 1
            continue
        
        if line_num is not None:
            # WICHTIG: Prüfe nochmal, ob die aktuelle Zeile ein Kommentar ist
            # (kann passieren, wenn extract_line_number() die Zeilennummer extrahiert hat, aber is_comment_line() noch nicht geprüft wurde)
            if is_comment_line(line_num):
                # Kommentar-Zeile: Extrahiere Zeilenbereich und speichere als Kommentar-Block
                start_line, end_line = extract_line_range(line_num)
                blocks.append({
                    'type': 'comment',
                    'line_num': line_num,
                    'content': line_content,
                    'start_line': start_line,
                    'end_line': end_line,
                    'original_line': line
                })
                i += 1
                continue
            
            # Wir haben eine Zeilennummer gefunden
            # Schaue voraus, um zu prüfen, ob die nächste(n) Zeile(n) dieselbe Nummer haben
            lines_with_same_num = [line]
            j = i + 1
            
            # Sammle alle aufeinanderfolgenden Zeilen mit derselben Nummer
            # (überspringe leere Zeilen dazwischen)
            # NEU: Überspringe auch Kommentar-Zeilen, damit sie nicht als Teil eines Paares behandelt werden
            while j < len(raw):
                next_line = (raw[j] or '').strip()
                if is_empty_or_sep(next_line):
                    j += 1
                    continue
                
                # Prüfe, ob die nächste Zeile ein Kommentar ist - überspringe sie dann
                next_num_temp, _ = extract_line_number(next_line)
                if next_num_temp is not None and is_comment_line(next_num_temp):
                    j += 1
                    continue  # Überspringe Kommentar-Zeilen
                
                next_num, _ = extract_line_number(next_line)
                if next_num == line_num:
                    lines_with_same_num.append(next_line)
                    j += 1
                else:
                    break
            
            # Jetzt haben wir alle Zeilen mit derselber Nummer
            # WICHTIG: Prüfe, ob die ERSTE Zeile selbst ein Kommentar ist (sollte nicht passieren, aber sicherheitshalber)
            first_line_num, _ = extract_line_number(lines_with_same_num[0])
            if first_line_num is not None and is_comment_line(first_line_num):
                # Die erste Zeile ist ein Kommentar - das sollte bereits oben erkannt worden sein!
                # Aber sicherheitshalber überspringen wir sie hier auch
                i = j
                continue
            
            num_lines = len(lines_with_same_num)
            
            if num_lines >= 2:
                # WICHTIG: Prüfe, ob eine der Zeilen ein Kommentar ist, BEVOR wir sie verarbeiten
                # Kommentare sollten bereits vorher erkannt und übersprungen worden sein, aber sicherheitshalber nochmal prüfen
                comment_found = False
                for idx, test_line in enumerate(lines_with_same_num):
                    test_num, _ = extract_line_number(test_line)
                    if test_num is not None and is_comment_line(test_num):
                        # Kommentar in lines_with_same_num gefunden - überspringe diese Zeilen
                        i = j
                        comment_found = True
                        break
                
                if comment_found:
                    continue  # Kommentar gefunden - überspringe Tokenisierung
                
                # Kein Kommentar gefunden - verarbeite normal
                # Zweisprachig (2) oder Dreisprachig (3+): gr/lat_de oder gr/lat_de_en
                # WICHTIG: Erste Zeile = IMMER antike Sprache, zweite = IMMER Übersetzung
                # UNABHÄNGIG von Sprechern oder Buchstaben!
                gr_line = lines_with_same_num[0]
                de_line = lines_with_same_num[1]
                en_line = lines_with_same_num[2] if num_lines >= 3 else None
                
                # WICHTIG: Prüfe nochmal, ob eine der Zeilen ein Kommentar ist, BEVOR wir tokenisieren
                gr_num, _ = extract_line_number(gr_line)
                de_num, _ = extract_line_number(de_line)
                if (gr_num and is_comment_line(gr_num)) or (de_num and is_comment_line(de_num)):
                    # Kommentar gefunden - überspringe diese Zeilen
                    i = j
                    continue
                
                # Tokenisieren & führende Label/Sprecher abwerfen
                gr_tokens = tokenize(gr_line)
                de_tokens = tokenize(de_line)

                lbl_gr, base_gr, sp_gr, gr_tokens = split_leading_label_and_speaker(gr_tokens)
                lbl_de, base_de, sp_de, de_tokens = split_leading_label_and_speaker(de_tokens)

                line_label = lbl_gr or lbl_de or ''
                base_num   = base_gr if base_gr is not None else base_de
                speaker    = sp_gr or ''

                # WICHTIG: Elisions-Übertragung direkt nach dem Tokenizing anwenden
                gr_tokens = propagate_elision_markers(gr_tokens)

                # Für 3-sprachige Texte: Englische Zeile verarbeiten
                en_tokens = []
                if en_line:
                    en_tokens = tokenize(en_line)
                    # Entferne Zeilennummer und Sprecher aus englischer Zeile
                    lbl_en, base_en, sp_en, en_tokens = split_leading_label_and_speaker(en_tokens)

                blocks.append({
                    'type':'pair',
                    'speaker': speaker,
                    'label': line_label,
                    'base':  base_num,
                    'gr_tokens': gr_tokens,
                    'de_tokens': de_tokens,
                    'en_tokens': en_tokens  # NEU: Englische Tokens für 3-sprachige Texte
                })
                i = j
                continue
            else:
                # Nur eine Zeile mit dieser Nummer - könnte Strukturzeile oder Fehler sein
                # Als Fallback: Prüfe Sprachinhalt (OHNE Sprecher zu berücksichtigen!)
                line_without_speaker = _strip_speaker_prefix_for_classify(line_content)
                if is_greek_line(line_without_speaker) or is_latin_line(line_without_speaker):
                    # Antike Sprache ohne Übersetzung
                    gr_tokens = tokenize(line)
                    lbl_gr, base_gr, sp_gr, gr_tokens = split_leading_label_and_speaker(gr_tokens)
                    gr_tokens = propagate_elision_markers(gr_tokens)
                    
                    blocks.append({
                        'type':'pair',
                        'speaker': sp_gr or '',
                        'label': lbl_gr or '',
                        'base': base_gr,
                        'gr_tokens': gr_tokens,
                        'de_tokens': []
                    })
                else:
                    # Deutsche Zeile ohne antike Sprache
                    de_tokens = tokenize(line)
                    lbl_de, base_de, _sp_de, de_tokens = split_leading_label_and_speaker(de_tokens)
                    blocks.append({
                        'type':'pair',
                        'speaker':'',
                        'label': lbl_de or '',
                        'base': base_de,
                        'gr_tokens': [],
                        'de_tokens': de_tokens
                    })
                i = j
                continue
        else:
            # Keine Zeilennummer gefunden - Fallback auf alte Logik
            # NEU: Prüfe auch hier, ob es ein Kommentar ist (für den Fall, dass extract_line_number None zurückgibt, aber die Zeile trotzdem (zahl-zahlk) enthält)
            line_num_fallback, _ = extract_line_number(line)
            if line_num_fallback is not None and is_comment_line(line_num_fallback):
                # Kommentar-Zeile: Extrahiere Zeilenbereich und speichere als Kommentar-Block
                start_line, end_line = extract_line_range(line_num_fallback)
                blocks.append({
                    'type': 'comment',
                    'line_num': line_num_fallback,
                    'content': line_content if 'line_content' in locals() else line,
                    'start_line': start_line,
                    'end_line': end_line,
                    'original_line': line
                })
                i += 1
                continue
            
            line_cls = _strip_speaker_prefix_for_classify(line)
            if is_greek_line(line_cls) or is_latin_line(line_cls):
                gr_line = line
                i += 1
                while i < len(raw) and is_empty_or_sep(raw[i]): i += 1

                de_line = ''
                if i < len(raw):
                    cand = (raw[i] or '').strip()
                    # NEU: Prüfe, ob die Kandidaten-Zeile ein Kommentar ist - überspringe sie dann
                    cand_num, _ = extract_line_number(cand)
                    if cand_num is not None and is_comment_line(cand_num):
                        # Kommentar-Zeile überspringen
                        i += 1
                        while i < len(raw) and is_empty_or_sep(raw[i]): i += 1
                        if i < len(raw):
                            cand = (raw[i] or '').strip()
                            cand_num, _ = extract_line_number(cand)
                            if cand_num is not None and is_comment_line(cand_num):
                                # Noch ein Kommentar - überspringe auch diesen
                                i += 1
                                continue
                    
                    cand_cls = _strip_speaker_prefix_for_classify(cand)
                    if not (is_greek_line(cand_cls) or is_latin_line(cand_cls)):
                        de_line = cand
                        i += 1

                # Tokenisieren & führende Label/Sprecher abwerfen
                gr_tokens = tokenize(gr_line)
                de_tokens = tokenize(de_line)

                lbl_gr, base_gr, sp_gr, gr_tokens = split_leading_label_and_speaker(gr_tokens)
                lbl_de, base_de, sp_de, de_tokens = split_leading_label_and_speaker(de_tokens)

                line_label = lbl_gr or lbl_de or ''
                base_num   = base_gr if base_gr is not None else base_de
                speaker    = sp_gr or ''

                # WICHTIG: Elisions-Übertragung direkt nach dem Tokenizing anwenden
                gr_tokens = propagate_elision_markers(gr_tokens)

                blocks.append({
                    'type':'pair',
                    'speaker': speaker,
                    'label': line_label,
                    'base':  base_num,
                    'gr_tokens': gr_tokens,
                    'de_tokens': de_tokens
                })
                continue

            # reine DE-Zeile – Label & Sprecher raus, Sprecher nicht anzeigen
            de_tokens = tokenize(line)
            lbl_de, base_de, _sp_de, de_tokens = split_leading_label_and_speaker(de_tokens)
            blocks.append({'type':'pair', 'speaker':'', 'label': (lbl_de or ''), 'base': base_de,
                           'gr_tokens': [], 'de_tokens': de_tokens})
            i += 1

    return blocks

# ========= Tabellenbau – NUM → Sprecher → Einrückung → Tokens =========

def get_visible_tags_poesie(token: str, tag_config: dict = None) -> list:
    """Gibt die Liste der sichtbaren Tags für ein Token zurück (basierend auf tag_config) - Poesie-Version."""
    if not tag_config or not token:
        tags = RE_TAG_FINDALL.findall(token)
        return tags
    
    tags = RE_TAG_FINDALL.findall(token)
    if not tags:
        return []
    
    visible_tags = []
    from shared.preprocess import RULE_TAG_MAP
    
    for tag in tags:
        tag_lower = tag.lower()
        is_hidden = False
        
        # Prüfe, ob der Tag direkt versteckt ist (z.B. "nomen_N")
        if tag_config.get(tag_lower, {}).get('hide', False):
            is_hidden = True
        else:
            # Prüfe, ob die Gruppe versteckt ist (z.B. "nomen")
            for group_id, group_tags in RULE_TAG_MAP.items():
                if tag in group_tags:
                    if tag_config.get(group_id, {}).get('hide', False):
                        is_hidden = True
                    break
        
        if not is_hidden:
            visible_tags.append(tag)
    
    return visible_tags

def measure_token_width_with_visibility_poesie(token: str, font: str, size: float, cfg: dict,
                                               is_greek_row: bool = False, 
                                               tag_config: dict = None) -> float:
    """
    Berechnet die Breite eines Tokens - Poesie-Version.
    WICHTIG: Diese Funktion erhält das Token NACH der Vorverarbeitung (apply_tag_visibility).
    Die Tags, die im Token noch vorhanden sind, sind bereits die sichtbaren Tags!
    Wir müssen nicht mehr prüfen, welche Tags versteckt sind - sie sind bereits entfernt.
    """
    if not token:
        return 0.0
    
    # Berechne Breite direkt mit dem Token, wie es ist (Tags wurden bereits entfernt)
    # Das Token enthält bereits nur noch die sichtbaren Tags!
    w_with_remaining_tags = visible_measure_token(token, font=font, size=size, cfg=cfg, is_greek_row=is_greek_row)
    
    # WICHTIG: Das Token wurde bereits in apply_tag_visibility verarbeitet.
    # Die Tags, die noch im Token vorhanden sind, sind die sichtbaren Tags!
    # Wir müssen einfach nur die Breite des aktuellen Tokens messen.
    
    tags_in_token = RE_TAG_FINDALL.findall(token)
    if tags_in_token:
        # Tags vorhanden → Tag-PDF, verwende gemessene Breite mit angemessenem Puffer
        return w_with_remaining_tags + max(size * 0.03, 0.8)  # Puffer für Tag-PDFs
    else:
        # Keine Tags vorhanden → NoTag-PDF, verwende gemessene Breite mit größerem Puffer
        return w_with_remaining_tags + max(size * 0.15, 2.5)  # Größerer Puffer für NoTag NoTrans

def build_tables_for_pair(gr_tokens: list[str], de_tokens: list[str] = None, 
                          indent_pt: float = 0.0,
                          global_speaker_width_pt: float = None,
                          meter_on: bool = False,
                          tag_mode: str = "TAGS",
                          speaker: str = "",
                          reserve_speaker_col: bool = False,
                          line_label: str = "",
                          doc_width_pt: float = None,
                          token_gr_style = None,
                          token_de_style = None,
                          num_style = None,
                          style_speaker = None,
                          gr_bold: bool = False,
                          en_tokens: list[str] = None,
                          tag_config: dict = None,  # NEU: Tag-Konfiguration für individuelle Breitenberechnung
                          base_line_num: int = None,  # NEU: Basis-Zeilennummer für Kommentar-Hinterlegung
                          line_comment_colors: dict = None,  # NEU: Map von Zeilennummern zu Kommentar-Farben
                          hide_pipes: bool = False,  # NEU: Pipes (|) in Übersetzungen verstecken
                          block: dict = None):  # NEU: Block-Objekt für comment_token_mask
    # Standardwerte setzen falls nicht übergeben
    if doc_width_pt is None:
        doc_width_pt = A4[0] - 40*MM  # A4-Breite minus Ränder
    if num_style is None:
        num_style = ParagraphStyle('Default', fontName='DejaVu', fontSize=8)
    if global_speaker_width_pt is None:
        global_speaker_width_pt = 0.0
    
    # linke Spaltenbreiten
    # Nummernspalte
    num_w   = max(6.0*MM, _sw('[999]', num_style.fontName, num_style.fontSize) + 2.0)
    num_gap = NUM_GAP_MM * MM

    # Sprecher-Laterne (immer reservieren, falls irgendwo ein Sprecher vorkam)
    sp_w   = 0.0
    sp_gap = 0.0
    if speaker:
        # Nutze mindestens die global ermittelte Breite (inkl. Puffer)
        sp_w  = max(global_speaker_width_pt, SPEAKER_COL_MIN_MM * MM)
        sp_gap= SPEAKER_GAP_MM*MM
    elif reserve_speaker_col:
        # Kein Sprecher in diesem Pair – aber Spalte bleibt als "Laterne" reserviert, mit globaler Breite
        sp_w  = max(global_speaker_width_pt, SPEAKER_COL_MIN_MM * MM)
        sp_gap= SPEAKER_GAP_MM*MM

    indent_w = max(0.0, float(indent_pt))  # Kachel-Einrückung (Stufenlayout)

    avail_tokens_w = doc_width_pt - (num_w + num_gap + sp_w + sp_gap + indent_w)
    if avail_tokens_w < 60: avail_tokens_w = doc_width_pt * 0.9

    # Spaltenlängen angleichen (zeilengetreu)
    # Für 3-sprachige Texte: englische Zeile einbeziehen
    if en_tokens is None:
        en_tokens = []
    if de_tokens is None:
        de_tokens = []
    
    # Wenn KEINE Übersetzungen vorhanden sind (alle ausgeblendet), zeige nur die griechische Zeile
    if not de_tokens and not en_tokens:
        cols = len(gr_tokens)
        gr = gr_tokens[:]
        de = []
        en = []
    else:
        cols = max(len(gr_tokens), len(de_tokens), len(en_tokens))
        gr = gr_tokens[:] + [''] * (cols - len(gr_tokens))
        de = de_tokens[:] + [''] * (cols - len(de_tokens))
        en = en_tokens[:] + [''] * (cols - len(en_tokens))

    # Effektive cfg abhängig von meter_on (Versmaß an/aus) und tag_mode
    eff_cfg = dict(CFG)
    if meter_on:
        eff_cfg['CELL_PAD_LR_PT'] = 0.0   # MUSS 0 SEIN für lückenlose Topline
        if tag_mode == "TAGS":
            eff_cfg['SAFE_EPS_PT'] = eff_cfg.get('TOKEN_PAD_PT_VERSMASS_TAG', 1.0)
        else:
            eff_cfg['SAFE_EPS_PT'] = eff_cfg.get('TOKEN_PAD_PT_VERSMASS_NOTAG', 0.5)
        # Versmaß-spezifische Gaps (INTER_PAIR wird global gesetzt, INTRA wird direkt berechnet)
        eff_cfg['INTER_PAIR_GAP_MM'] = INTER_PAIR_GAP_MM_VERSMASS
    else:
        # Für normale PDFs ist ein kleiner Zell-Innenabstand gut, der Hauptabstand kommt vom Token-Pad.
        eff_cfg['CELL_PAD_LR_PT'] = 0.5
        if tag_mode == "TAGS":
            eff_cfg['SAFE_EPS_PT'] = eff_cfg.get('TOKEN_PAD_PT_NORMAL_TAG', 4.0)
            eff_cfg['INTER_PAIR_GAP_MM'] = INTER_PAIR_GAP_MM_NORMAL_TAG
        else:
            eff_cfg['SAFE_EPS_PT'] = eff_cfg.get('TOKEN_PAD_PT_NORMAL_NOTAG', 3.0)
            eff_cfg['INTER_PAIR_GAP_MM'] = INTER_PAIR_GAP_MM_NORMAL_NOTAG

    # Breiten: Berücksichtige auch englische Zeile
    # Verwende die neue Funktion, die Tag-Sichtbarkeit berücksichtigt
    widths = []
    for k in range(cols):
        # Verwende die neue Funktion, die Tag-Sichtbarkeit berücksichtigt (nur für griechische Tokens)
        w_gr = measure_token_width_with_visibility_poesie(
            gr[k] if (k < len(gr) and gr[k]) else '', 
            font=token_gr_style.fontName, 
            size=token_gr_style.fontSize, 
            cfg=eff_cfg,
            is_greek_row=True,
            tag_config=tag_config
        ) if (k < len(gr) and gr[k]) else 0.0
        # DE- und EN-Tokens haben normalerweise keine Tags, daher verwenden wir die Standard-Breitenberechnung
        # NEU: Berücksichtige Pipe-Ersetzung bei der Breitenberechnung
        if hide_pipes:
            de_text = de[k].replace('|', ' ') if (k < len(de) and de[k]) else ''
            en_text = en[k].replace('|', ' ') if (k < len(en) and en[k]) else ''
            # Berechne die Anzahl der Pipes, die ersetzt werden (für zusätzlichen Platz)
            de_pipe_count = (de[k].count('|') if (k < len(de) and de[k]) else 0)
            en_pipe_count = (en[k].count('|') if (k < len(en) and en[k]) else 0)
            # Leerzeichen sind breiter als Pipes - füge zusätzlichen Platz hinzu
            space_vs_pipe_diff = token_de_style.fontSize * 0.25
            de_pipe_extra = de_pipe_count * space_vs_pipe_diff
            en_pipe_extra = en_pipe_count * space_vs_pipe_diff
        else:
            de_text = de[k] if (k < len(de) and de[k]) else ''
            en_text = en[k] if (k < len(en) and en[k]) else ''
            de_pipe_extra = 0.0
            en_pipe_extra = 0.0
        
        w_de = visible_measure_token(de_text, font=token_de_style.fontName, size=token_de_style.fontSize, cfg=eff_cfg, is_greek_row=False) if de_text else 0.0
        w_en = visible_measure_token(en_text, font=token_de_style.fontName, size=token_de_style.fontSize, cfg=eff_cfg, is_greek_row=False) if en_text else 0.0
        
        # Addiere zusätzlichen Platz für ersetzte Pipes
        w_de += de_pipe_extra
        w_en += en_pipe_extra
        
        widths.append(max(w_gr, w_de, w_en))

    tables, i, first_slice = [], 0, True
    
    # Dynamischer Abstand zwischen antiker und moderner Zeile
    # Abhängig von Tag/NoTag
    if CURRENT_IS_NOTAGS:
        gap_ancient_to_modern = INTRA_PAIR_ANCIENT_TO_MODERN_NOTAG * MM
    else:
        gap_ancient_to_modern = INTRA_PAIR_ANCIENT_TO_MODERN_TAG * MM
    
    # Abstand zwischen DE und EN (nur bei 3-sprachigen PDFs)
    gap_de_to_en = INTRA_PAIR_DE_TO_EN  # in Punkten, nicht MM!

    while i < cols:
        acc, j = 0.0, i
        while j < cols:
            w = widths[j]
            if acc + w > avail_tokens_w and j > i: break
            acc += w; j += 1

        slice_gr, slice_de, slice_w = gr[i:j], de[i:j], widths[i:j]
        slice_en = en[i:j]  # Für 3-sprachige Texte

        # Zellen
        def _p(text, st): return Paragraph(text, st)
        def _end_has_bar_local(s: str) -> bool: return _end_has_bar(s)
        def _has_leading_bar_local(s: str) -> bool: return _has_leading_bar(s)

        def cell(is_gr, tok, idx_in_slice):
            if not tok:
                return Paragraph('', token_gr_style if is_gr else token_de_style)

            if is_gr and meter_on:
                had_lead = _has_leading_bar_local(tok)
                endbars_match = re.search(r'\|+\s*$', RE_TAG_STRIP.sub('', tok))
                endbars = len(endbars_match.group(0).strip()) if endbars_match else 0
                br_to_next = False
                next_has_lead = False
                
                # Kontext-Übergabe für Schieberegler
                next_tok_starts_bar = False
                if idx_in_slice is not None and idx_in_slice < (len(slice_gr) - 1):
                    nxt = slice_gr[idx_in_slice + 1]
                    br_to_next = same_foot(tok, nxt)
                    next_has_lead = _has_leading_bar_local(nxt)
                    next_tok_starts_bar = next_has_lead

                return ToplineTokenFlowable(
                    tok, token_gr_style, eff_cfg,
                    gr_bold=(gr_bold if is_gr else False),
                    had_leading_bar=had_lead,
                    end_bar_count=endbars,
                    bridge_to_next=br_to_next,
                    next_has_leading_bar=next_has_lead,
                    is_first_in_line=(idx_in_slice == 0),
                    next_token_starts_with_bar=next_tok_starts_bar
                )

            # NICHT-Versmaß: Bars entfernen + pro Spaltenbreite weich zentrieren (Epos-Logik)
            # DEFENSIV: Entferne Tags aus Token, falls sie noch vorhanden sind
            tok_cleaned = _strip_tags_from_token(tok)
            html_ = format_token_markup(tok_cleaned, is_greek_row=is_gr, gr_bold=(gr_bold if is_gr else False), remove_bars_instead=True)
            # Spaltenbreite dieser Zelle
            if is_gr and idx_in_slice is not None:
                this_w = slice_w[idx_in_slice]
                # Verwende bereinigten Token für Breitenmessung
                measured = visible_measure_token(tok_cleaned, font=token_gr_style.fontName, size=token_gr_style.fontSize, cfg=eff_cfg, is_greek_row=True)
                html_centered = center_word_in_width(html_, measured, this_w, token_gr_style.fontName, token_gr_style.fontSize)
                return Paragraph(html_centered, token_gr_style)
            else:
                # DE-Zeile: ebenfalls zentrieren
                # idx_in_slice ist bei DE nicht gesetzt; nutze parallelen Index über enumerate weiter unten
                return html_  # wird später im de_cells-Block zentriert

        gr_cells = [cell(True,  t, k) for k, t in enumerate(slice_gr)]

        # DE-Zellen mit gleicher Zentrierung wie im Epos
        # NEU: Pipe-Ersetzung für hide_pipes
        def process_translation_token_poesie(token: str) -> str:
            """Ersetzt | durch Leerzeichen in Übersetzungen, wenn hide_pipes aktiviert ist"""
            if not token or not hide_pipes:
                return token
            return token.replace('|', ' ')
        
        de_cells = []
        for idx, t in enumerate(slice_de):
            if not t:
                de_cells.append(Paragraph('', token_de_style))
                continue
            # NEU: Pipes durch Leerzeichen ersetzen, wenn hide_pipes aktiviert ist
            t_processed = process_translation_token_poesie(t)
            de_html = format_token_markup(t_processed, is_greek_row=False, gr_bold=False, remove_bars_instead=True)
            # WICHTIG: Breite mit verarbeitetem Token messen (Pipes bereits ersetzt)
            de_meas  = visible_measure_token(t_processed, font=token_de_style.fontName, size=token_de_style.fontSize, cfg=eff_cfg, is_greek_row=False)
            de_width = slice_w[idx]
            de_html_centered = center_word_in_width(de_html, de_meas, de_width, token_de_style.fontName, token_de_style.fontSize)
            de_cells.append(Paragraph(de_html_centered, token_de_style))

        # EN-Zellen (für 3-sprachige Texte)
        en_cells = []
        has_en = any(slice_en)
        if has_en:
            for idx, t in enumerate(slice_en):
                if not t:
                    en_cells.append(Paragraph('', token_de_style))
                    continue
                # NEU: Pipes durch Leerzeichen ersetzen, wenn hide_pipes aktiviert ist
                t_processed = process_translation_token_poesie(t)
                en_html = format_token_markup(t_processed, is_greek_row=False, gr_bold=False, remove_bars_instead=True)
                # WICHTIG: Breite mit verarbeitetem Token messen (Pipes bereits ersetzt)
                en_meas  = visible_measure_token(t_processed, font=token_de_style.fontName, size=token_de_style.fontSize, cfg=eff_cfg, is_greek_row=False)
                en_width = slice_w[idx]
                en_html_centered = center_word_in_width(en_html, en_meas, en_width, token_de_style.fontName, token_de_style.fontSize)
                en_cells.append(Paragraph(en_html_centered, token_de_style))

        # Linke Spalten: NUM → Gap → SPRECHER → Gap → INDENT → Tokens
        # WICHTIG: Zeilennummer in <font> Tag wrappen, damit "-" nicht als Farbmarker interpretiert wird
        if first_slice and line_label:
            num_text = f'<font color="black">[{xml_escape(line_label)}]</font>'
        else:
            num_text = '\u00A0'
        num_para_gr = _p(num_text, num_style)
        num_para_de = _p('\u00A0', num_style)
        num_para_en = _p('\u00A0', num_style) if has_en else None
        num_gap_gr  = _p('', token_gr_style); num_gap_de = _p('', token_de_style)
        num_gap_en  = _p('', token_de_style) if has_en else None

        sp_para_gr  = _p(xml_escape(f"[{speaker}]:"), style_speaker) if (first_slice and sp_w>0 and speaker) else _p('', style_speaker)
        sp_para_de  = _p('', style_speaker)
        sp_para_en  = _p('', style_speaker) if has_en else None
        sp_gap_gr   = _p('', token_gr_style); sp_gap_de = _p('', token_de_style)
        sp_gap_en   = _p('', token_de_style) if has_en else None

        indent_gr   = _p('', token_gr_style)
        indent_de   = _p('', token_de_style)
        indent_en   = _p('', token_de_style) if has_en else None

        row_gr = [num_para_gr, num_gap_gr, sp_para_gr, sp_gap_gr, indent_gr] + gr_cells
        row_de = [num_para_de, num_gap_de, sp_para_de, sp_gap_de, indent_de] + de_cells
        col_w  = [num_w, num_gap, sp_w,        sp_gap,   indent_w] + slice_w

        # Prüfe, ob Übersetzungen vorhanden sind
        has_de = any(de)
        
        # Für 3-sprachige Texte: englische Zeile hinzufügen
        if has_en:
            row_en = [num_para_en, num_gap_en, sp_para_en, sp_gap_en, indent_en] + en_cells
            if has_de:
                tbl = Table([row_gr, row_de, row_en], colWidths=col_w, hAlign='LEFT')
            else:
                # Keine deutschen Übersetzungen, nur griechisch und englisch
                tbl = Table([row_gr, row_en], colWidths=col_w, hAlign='LEFT')
        elif has_de:
            # Nur griechisch und deutsch (Standard 2-sprachig)
            tbl = Table([row_gr, row_de], colWidths=col_w, hAlign='LEFT')
        else:
            # Keine Übersetzungen, nur griechische Zeile
            tbl = Table([row_gr], colWidths=col_w, hAlign='LEFT')

        # NEU: Prüfe, ob diese Zeile von einem Kommentar referenziert wird
        # WICHTIG: Wenn comment_token_mask vorhanden ist und nicht leer, unterdrücke Hintergrundfarbe
        comment_color = None
        comment_token_mask = block.get('comment_token_mask', []) if block else []
        has_comment_mask = comment_token_mask and any(comment_token_mask)
        
        if base_line_num is not None and line_comment_colors and base_line_num in line_comment_colors and not has_comment_mask:
            comment_color = line_comment_colors[base_line_num]
        
        if meter_on:
            # Versmaß: KEIN Innenabstand, sonst entstehen Lücken zwischen Flowables
            style_list = [
                ('LEFTPADDING',   (0,0), (-1,-1), 0.0),
                ('RIGHTPADDING',  (0,0), (-1,-1), 0.0),
                ('TOPPADDING',    (0,0), (-1,-1), 0.0),
                ('BOTTOMPADDING', (0,0), (-1,-1), 0.0),
                ('VALIGN',        (0,0), (-1,-1), 'BOTTOM'),
                ('ALIGN',         (0,0), (0,-1), 'RIGHT'),  # Nummern rechts
                ('ALIGN',         (1,0), (-1,-1), 'LEFT'),  # Rest links (wie im Epos)
            ]
            # NEU: Hinterlegung für Kommentar-referenzierte Zeilen
            if comment_color:
                bg_color = colors.Color(comment_color[0], comment_color[1], comment_color[2], alpha=0.35)  # Flächige Hinterlegung (wie Prosa)
                style_list.append(('BACKGROUND', (0,0), (-1,-1), bg_color))
            # Nur Padding für Sprecher-Spalte hinzufügen, wenn sie existiert (sp_w > 0)
            if sp_w > 0:
                style_list.append(('RIGHTPADDING',  (2,0), (2,-1), 2.0))
            # Nur Padding zwischen Zeilen hinzufügen, wenn Übersetzungen vorhanden sind
            if has_de or has_en:
                style_list.append(('BOTTOMPADDING', (0,0), (-1,0), gap_ancient_to_modern/2.0))
                style_list.append(('TOPPADDING',    (0,1), (-1,1), gap_ancient_to_modern/2.0))
            # NEU: Für 3-sprachige Texte: Padding zwischen Zeilen
            # Zeile 1 (GR) und Zeile 2 (DE): normaler Abstand (siehe oben)
            # Zeile 2 (DE) und Zeile 3 (EN): SEHR MINIMAL, fast direkt untereinander
            if has_en:
                style_list.append(('BOTTOMPADDING', (0,1), (-1,1), gap_de_to_en))
                style_list.append(('TOPPADDING',    (0,2), (-1,2), gap_de_to_en))
            tbl.setStyle(TableStyle(style_list))
        else:
            # Nicht-Versmaß: bisheriges Padding-Verhalten
            style_list = [
                ('LEFTPADDING',   (0,0), (-1,-1), CELL_PAD_LR_PT),
                ('RIGHTPADDING',  (0,0), (-1,-1), CELL_PAD_LR_PT),
                ('TOPPADDING',    (0,0), (-1,-1), 0.0),
                ('BOTTOMPADDING', (0,0), (-1,-1), 0.0),
                ('VALIGN',        (0,0), (-1,-1), 'BOTTOM'),
                ('ALIGN',         (0,0), (0,-1), 'RIGHT'),
                ('ALIGN',         (1,0), (-1,-1), 'LEFT'),
            ]
            # NEU: Hinterlegung für Kommentar-referenzierte Zeilen
            if comment_color:
                bg_color = colors.Color(comment_color[0], comment_color[1], comment_color[2], alpha=0.35)  # Flächige Hinterlegung (wie Prosa)
                style_list.append(('BACKGROUND', (0,0), (-1,-1), bg_color))
            # Nur Padding für Sprecher-Spalte hinzufügen, wenn sie existiert (sp_w > 0)
            if sp_w > 0:
                style_list.append(('RIGHTPADDING',  (2,0), (2,-1), 2.0))
            # Nur Padding zwischen Zeilen hinzufügen, wenn Übersetzungen vorhanden sind
            if has_de or has_en:
                style_list.append(('BOTTOMPADDING', (0,0), (-1,0), gap_ancient_to_modern/2.0))
                style_list.append(('TOPPADDING',    (0,1), (-1,1), gap_ancient_to_modern/2.0))
            # NEU: Für 3-sprachige Texte: Padding zwischen Zeilen
            # Zeile 1 (GR) und Zeile 2 (DE): normaler Abstand (siehe oben)
            # Zeile 2 (DE) und Zeile 3 (EN): SEHR MINIMAL, fast direkt untereinander
            if has_en:
                style_list.append(('BOTTOMPADDING', (0,1), (-1,1), gap_de_to_en))
                style_list.append(('TOPPADDING',    (0,2), (-1,2), gap_de_to_en))
            tbl.setStyle(TableStyle(style_list))
        tables.append(tbl)
        first_slice, i = False, j

    return tables

# ========= PDF-Erzeugung =========
def process_comments_for_coloring(blocks):
    """
    Verarbeitet Kommentare in den Blöcken und weist ihnen Farben zu.
    Gibt ein Dictionary zurück: {comment_index: {'color': (r, g, b), 'start_line': int, 'end_line': int, 'block_index': int}}
    """
    comments = []
    comment_index = 0
    
    # Sammle alle Kommentar-Blocks
    for i, block in enumerate(blocks):
        if block.get('type') == 'comment':
            start_line = block.get('start_line')
            end_line = block.get('end_line')
            if start_line is not None and end_line is not None:
                color = get_comment_color(comment_index)
                comments.append({
                    'comment_index': comment_index,
                    'color': color,
                    'start_line': start_line,
                    'end_line': end_line,
                    'block_index': i
                })
                # Speichere die Farbe direkt im Block für späteres Rendering
                block['comment_color'] = color
                block['comment_index'] = comment_index
                comment_index += 1
    
    return comments

def create_pdf(blocks, pdf_name:str, *, gr_bold:bool,
               de_bold:bool = False,
               versmass_display: bool = False,
               tag_mode: str = "TAGS",
               placement_overrides: dict[str, str] | None = None,
               tag_config: dict | None = None,
               hide_pipes:bool=False):  # NEU: Pipes (|) in Übersetzungen verstecken

    # Verarbeite Kommentare und weise Farben zu
    comments = process_comments_for_coloring(blocks)
    
    # Erstelle eine Map: Zeilennummer → Kommentar-Farbe (für Hinterlegung)
    line_comment_colors = {}  # {line_num: (r, g, b)}
    for comment in comments:
        color = comment['color']
        for line_num in range(comment['start_line'], comment['end_line'] + 1):
            line_comment_colors[line_num] = color
    
    # Speichere line_comment_colors für späteres Rendering
    # (wird in build_tables_for_pair verwendet)

    # NoTags-Schalter global setzen, wenn Dateiname auf _NoTags.pdf endet
    global CURRENT_IS_NOTAGS
    CURRENT_IS_NOTAGS = pdf_name.lower().endswith("_notags.pdf")
    # Lateinischer Text? (keine Versmaß-Marker-Entfernung für i, r, L)
    global CURRENT_IS_LATIN
    CURRENT_IS_LATIN = "_LAT_" in pdf_name.upper() or "_lat_" in pdf_name.lower()
    # Optionale Hoch/Tief/Off-Overrides aus Preprocess/UI aktivieren
    global PLACEMENT_OVERRIDES
    PLACEMENT_OVERRIDES = dict(placement_overrides or {})
    
    # Versmaß-spezifische Abstände setzen (abhängig von versmass_display UND tag_mode)
    global INTER_PAIR_GAP_MM
    if versmass_display:
        INTER_PAIR_GAP_MM = INTER_PAIR_GAP_MM_VERSMASS
    else:
        # Normal-PDFs: Unterscheide zwischen TAG und NOTAG
        if CURRENT_IS_NOTAGS:
            INTER_PAIR_GAP_MM = INTER_PAIR_GAP_MM_NORMAL_NOTAG
        else:
            INTER_PAIR_GAP_MM = INTER_PAIR_GAP_MM_NORMAL_TAG
    
    # Intra-Pair Abstand für Debug
    intra_val = INTRA_PAIR_ANCIENT_TO_MODERN_NOTAG if CURRENT_IS_NOTAGS else INTRA_PAIR_ANCIENT_TO_MODERN_TAG
    
    # Debug-Ausgabe
    print(f"DEBUG Poesie: versmass={versmass_display}, tag_mode={'NO_TAGS' if CURRENT_IS_NOTAGS else 'TAGS'}, INTER_PAIR={INTER_PAIR_GAP_MM}mm, INTRA_PAIR={intra_val}mm")
    
    left_margin = 10*MM
    right_margin = 10*MM
    doc = SimpleDocTemplate(
        pdf_name, pagesize=A4,
        leftMargin=left_margin, rightMargin=right_margin,
        topMargin=14*MM, bottomMargin=14*MM
    )

    frame_w = A4[0] - left_margin - right_margin

    base = getSampleStyleSheet()
    token_gr = ParagraphStyle('TokGR', parent=base['Normal'],
        fontName='DejaVu-Bold' if gr_bold else 'DejaVu',
        fontSize=GR_SIZE, leading=_leading_for(GR_SIZE),
        alignment=TA_LEFT, wordWrap='LTR', splitLongWords=0)
    token_de = ParagraphStyle('TokDE', parent=base['Normal'],
        fontName='DejaVu-Bold' if de_bold else 'DejaVu',
        fontSize=DE_SIZE, leading=_leading_for(DE_SIZE),
        alignment=TA_LEFT, wordWrap='LTR', splitLongWords=0)
    num_size = max(6.0, round(GR_SIZE * CFG['NUM_SIZE_FACTOR'], 1))
    num_style = ParagraphStyle('Num', parent=base['Normal'], fontName='DejaVu',
                               fontSize=num_size, leading=_leading_for(num_size),
                               textColor=CFG['NUM_COLOR'], alignment=TA_RIGHT, wordWrap='LTR', splitLongWords=0)
    style_section = ParagraphStyle('Section', parent=base['Normal'],
        fontName='DejaVu', fontSize=SECTION_SIZE, leading=_leading_for(SECTION_SIZE),
        alignment=TA_LEFT, spaceBefore=0,
        spaceAfter=SECTION_SPACE_AFTER_MM*MM, keepWithNext=False)
    style_title = ParagraphStyle('TitleBrace', parent=base['Normal'],
        fontName='DejaVu', fontSize=TITLE_BRACE_SIZE, leading=_leading_for(TITLE_BRACE_SIZE),
        alignment=TA_CENTER, spaceAfter=TITLE_SPACE_AFTER*MM, keepWithNext=False)
    
    # Gleichheitszeichen-Überschriften (wie in Prosa)
    # H1 (====): zentriert, H2/H3 (===, ==): linksbündig, ALLE nicht fett (Tinte sparen!)
    style_eq_h1 = ParagraphStyle('EqH1', parent=base['Normal'],
        fontName='DejaVu', fontSize=H1_EQ_SIZE, leading=_leading_for(H1_EQ_SIZE),
        alignment=TA_CENTER, spaceAfter=H1_SPACE_AFTER_MM*MM, keepWithNext=False)
    style_eq_h2 = ParagraphStyle('EqH2', parent=base['Normal'],
        fontName='DejaVu', fontSize=H2_EQ_SIZE, leading=_leading_for(H2_EQ_SIZE),
        alignment=TA_LEFT, spaceAfter=H2_SPACE_AFTER_MM*MM, keepWithNext=False)
    style_eq_h3 = ParagraphStyle('EqH3', parent=base['Normal'],
        fontName='DejaVu', fontSize=H3_EQ_SIZE, leading=_leading_for(H3_EQ_SIZE),
        alignment=TA_LEFT, spaceAfter=H3_SPACE_AFTER_MM*MM, keepWithNext=False)
    style_speaker = ParagraphStyle('Speaker', parent=base['Normal'],
        fontName='DejaVu', fontSize=DE_SIZE, leading=_leading_for(DE_SIZE),
        alignment=TA_LEFT, textColor=colors.black)
        
             # Globale Sprecher-Spaltenbreite (max über alle Sprecher) mit Puffer
    def _speaker_col_width(text:str) -> float:
        if not text:
            return SPEAKER_COL_MIN_MM * MM
        disp = f'[{text}]:'
        w = _sw(disp, style_speaker.fontName, style_speaker.fontSize)
        return max(SPEAKER_COL_MIN_MM * MM, w + SPEAKER_EXTRA_PAD_PT)

    # KEINE globale Sprecher-Spaltenbreite mehr!
    # Jede Zeile hat ihre eigene Sprecher-Spaltenbreite
    
    elements = []

    # Sprecher-Laterne global reservieren, sobald irgendwo ein Sprecher vorkommt
    reserve_all_speakers = any(b.get('type')=='pair' and (b.get('speaker') or '') for b in blocks)

    # Stufenlayout: kumulative Breite pro Basisvers
    cum_width_by_base = {}  # base:int -> float pt
    
    # Sprecher-Tracking: Nur bei Wechsel oder nach Überschrift anzeigen
    last_speaker = None
    last_was_heading = False  # True wenn der letzte Block eine Überschrift war

    i = 0
    while i < len(blocks):
        b = blocks[i]
        t = b['type']

        # {Titel} Funktion existiert nicht mehr - überspringe diese Blöcke
        if t == 'title_brace':
            i += 1; continue

        # [[Zeile Lost]] - Sonderfall: als normale Zeile formatieren mit eckigen Klammern
        if t == 'zeile_lost':
            raw_text = b['text']
            
            # Parse: (123) [Sprecher:] [[Zeile Lost]]
            # Ziel: [123] [Sprecher:] [[Zeile Lost]]
            match_lost = re.match(r'^\s*\((\d+[a-z]*)\)\s*(\[[^\]]*:\])?\s*\[\[Zeile\s+Lost\]\]\s*$', raw_text, re.IGNORECASE)
            
            if match_lost:
                line_num = match_lost.group(1)
                speaker = match_lost.group(2) if match_lost.group(2) else ''
                
                # Formatiere wie normale Zeilen: [123] [Sprecher:] [[Zeile Lost]]
                formatted_parts = []
                formatted_parts.append(f'<font name="DejaVu" size="{num_style.fontSize}">[{line_num}]</font>')
                if speaker:
                    formatted_parts.append(f'<font name="DejaVu" size="{style_speaker.fontSize}">{xml_escape(speaker)}</font>')
                formatted_parts.append('<font name="DejaVu">[[Zeile Lost]]</font>')
                formatted_text = ' '.join(formatted_parts)
            else:
                # Fallback: Zeige den Text wie er ist
                formatted_text = xml_escape(raw_text)
            
            # Zeige als Paragraph mit normalem Abstand
            zeile_lost_style = ParagraphStyle('ZeileLost', parent=base['Normal'],
                fontName='DejaVu', fontSize=DE_SIZE, leading=_leading_for(DE_SIZE),
                alignment=TA_LEFT)
            elements.append(Paragraph(formatted_text, zeile_lost_style))
            elements.append(Spacer(1, INTER_PAIR_GAP_MM * MM))  # Normaler Abstand wie zwischen Zeilen
            i += 1; continue

        # NEU: Kommentar-Zeilen (zahlk oder zahl-zahlk)
        if t == 'comment':
            line_num = b.get('line_num', '')
            content = b.get('content', '')
            original_line = b.get('original_line', '')
            
            # DEBUG: Kommentar wird verarbeitet (IMMER, auch wenn leer)
            print(f"  → Kommentar verarbeiten (Poesie): type={t}, line_num={line_num}, content={content[:50] if content else '(leer)'}, original_line={original_line[:80] if original_line else '(leer)'}")
            
            # Fallback: Wenn content leer ist, versuche original_line zu verwenden
            if not content and original_line:
                # Extrahiere content aus original_line
                from Poesie_Code import extract_line_number
                _, content = extract_line_number(original_line)

            # Wenn immer noch kein content, verwende original_line direkt (ohne Zeilennummer)
            if not content and original_line:
                # Entferne Zeilennummer am Anfang (z.B. "(3-7k) " oder "(24k) ")
                content = re.sub(r'^\(\d+-\d+k\)\s*', '', original_line)
                content = re.sub(r'^\(\d+k\)\s*', '', content)
                content = content.strip()
            
            # Fallback: Wenn line_num leer ist, extrahiere sie aus original_line
            if not line_num and original_line:
                from Poesie_Code import extract_line_number
                line_num, _ = extract_line_number(original_line)
            
            comment_color = b.get('comment_color', COMMENT_COLORS[0])  # Fallback zu rot
            comment_index = b.get('comment_index', 0)
            
            # ROBUST: Prüfe, ob überhaupt Daten vorhanden sind (line_num, content oder original_line)
            if not line_num and not content and not original_line:
                print(f"  ⚠️ Kommentar komplett leer übersprungen (Poesie)")
                i += 1
                continue
            
            # Formatiere Zeilennummer in der Kommentar-Farbe (rot/blau/grün)
            # Konvertiere RGB-Tupel zu Hex für HTML
            r, g, b = comment_color
            color_hex = f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"
            
            # Kommentar-Text mit kleinerem Font und etwas kursiv/leicht hervorgehoben
            formatted_parts = []
            # Zeilennummer in Kommentar-Farbe (WICHTIG: xml_escape auf line_num anwenden, um "-" zu schützen)
            comment_num_size = num_style.fontSize * 0.85  # Etwas kleiner als normale Zeilennummern
            formatted_parts.append(f'<font name="DejaVu" size="{comment_num_size}" color="{color_hex}"><b>[{xml_escape(line_num)}]</b></font>')
            # Kommentar-Text mit kleinerem Font und Farbe
            comment_size = DE_SIZE * 0.8  # Deutlich kleiner (80% statt 90%)
            # Sicherstellen, dass content vorhanden ist
            if content:
                formatted_parts.append(f'<font name="DejaVu" size="{comment_size}" color="{color_hex}"><i> {xml_escape(content)}</i></font>')
            else:
                # Fallback: Verwende original_line wenn content leer ist
                original_line = b.get('original_line', '')
                if original_line:
                    # Entferne Zeilennummer aus original_line für content
                    _, fallback_content = extract_line_number(original_line)
                    if fallback_content:
                        formatted_parts.append(f'<font name="DejaVu" size="{comment_size}" color="{color_hex}"><i> {xml_escape(fallback_content)}</i></font>')
            formatted_text = ''.join(formatted_parts)
            
            # Style für Kommentar (kompakt, kleiner, dichter)
            comment_style = ParagraphStyle('Comment', parent=base['Normal'],
                fontName='DejaVu', fontSize=comment_size, 
                leading=comment_size * 1.2,  # Dichterer Zeilenabstand (1.2 statt normal)
                alignment=TA_LEFT, leftIndent=5*MM,  # Leicht eingerückt
                spaceBefore=0, spaceAfter=0,  # Keine zusätzlichen Abstände
                backColor=colors.Color(comment_color[0], comment_color[1], comment_color[2], alpha=0.1))  # Sehr leichte Hinterlegung
            
            elements.append(Paragraph(formatted_text, comment_style))
            elements.append(Spacer(1, INTER_PAIR_GAP_MM * 0.5 * MM))  # Kleinerer Abstand
            i += 1; continue

        # Gleichheitszeichen-Überschriften (wie in Prosa)
        # WICHTIG: Alle aufeinanderfolgenden Überschriften sammeln und mit erster Textzeile koppeln
        # WICHTIG: Überschriften mit "Gedicht" markieren den Beginn eines neuen Gedichts
        # → Kumulative Einrückung zurücksetzen (nur bei "Gedicht"-Überschriften)
        if t in ['h1_eq', 'h2_eq', 'h3_eq', 'section']:
            # Bei Überschriften, die "Gedicht" enthalten, kumulative Breite zurücksetzen
            # Dies verhindert, dass Zeilen aus verschiedenen Gedichten kumulativ eingerückt werden
            heading_text = b.get('text', '').lower()
            if t in ['h1_eq', 'h2_eq', 'h3_eq'] and 'gedicht' in heading_text:
                cum_width_by_base = {}  # Reset für neues Gedicht
            
            # Wähle den richtigen Style basierend auf dem Typ
            if t == 'h1_eq':
                para_style = style_eq_h1
            elif t == 'h2_eq':
                para_style = style_eq_h2
            elif t == 'h3_eq':
                para_style = style_eq_h3
            else:  # section
                para_style = style_section
            
            # Sammle aufeinanderfolgende Überschriften
            headers = [Paragraph(xml_escape(b['text']), para_style)]
            temp_i = i + 1
            
            while temp_i < len(blocks):
                next_b = blocks[temp_i]
                next_t = next_b['type']
                
                if next_t in ['h1_eq', 'h2_eq', 'h3_eq', 'section']:
                    # Weitere Überschrift - hinzufügen
                    next_heading_text = next_b.get('text', '').lower()
                    if next_t in ['h1_eq', 'h2_eq', 'h3_eq'] and 'gedicht' in next_heading_text:
                        cum_width_by_base = {}
                    
                    if next_t == 'h1_eq':
                        next_para_style = style_eq_h1
                    elif next_t == 'h2_eq':
                        next_para_style = style_eq_h2
                    elif next_t == 'h3_eq':
                        next_para_style = style_eq_h3
                    else:
                        next_para_style = style_section
                    
                    headers.append(Paragraph(xml_escape(next_b['text']), next_para_style))
                    temp_i += 1
                elif next_t in ['blank', 'title_brace']:
                    temp_i += 1
                else:
                    break
            
            # Suche nach den nächsten 2 pair-Blöcken
            scan = temp_i
            while scan < len(blocks) and blocks[scan]['type'] == 'blank':
                scan += 1
            
            # Sammle die ersten 2 Textzeilen (ohne sie zu rendern)
            pair_blocks_to_couple = []
            temp_scan = scan
            
            while temp_scan < len(blocks) and len(pair_blocks_to_couple) < 2:
                next_b = blocks[temp_scan]
                if next_b['type'] == 'pair':
                    pair_blocks_to_couple.append((temp_scan, next_b))
                    temp_scan += 1
                elif next_b['type'] in ['blank', 'title_brace']:
                    temp_scan += 1
                else:
                    break
            
            if pair_blocks_to_couple:
                # EINFACHSTE UND ROBUSTESTE STRATEGIE:
                # Alle Überschriften + NUR die erste Textzeile in KeepTogether
                # Das ist klein genug und garantiert, dass Überschriften nicht allein stehen
                
                # Rendere die ersten 2 Textzeilen und sammle sie
                rendered_lines = []
                for idx, (block_idx, pair_b) in enumerate(pair_blocks_to_couple):
                    next_gr_tokens = pair_b.get('gr_tokens', [])[:]
                    next_de_tokens = pair_b.get('de_tokens', [])[:]
                    next_en_tokens = pair_b.get('en_tokens', [])
                    next_speaker = pair_b.get('speaker') or ''
                    next_line_label = pair_b.get('label') or ''
                    next_base_num = pair_b.get('base')

                    next_gr_tokens = propagate_elision_markers(next_gr_tokens)
                    
                    # Einrückung: NUR wenn das Label ein gültiges Suffix für gestaffelte Zeilen hat (a-g)
                    next_indent_pt = 0.0
                    if next_base_num is not None and next_line_label and _is_staggered_label(next_line_label):
                        next_indent_pt = max(0.0, cum_width_by_base.get(next_base_num, 0.0))

                    next_has_versmass = has_meter_markers(next_gr_tokens)
                    
                    # Sprecher-Logik für Zeilen nach Überschrift
                    # idx == 0: Erste Zeile nach Überschrift → Sprecher immer anzeigen
                    # idx > 0: Weitere Zeilen → nur bei Sprecherwechsel anzeigen
                    next_display_speaker = next_speaker
                    if next_speaker:
                        if idx == 0 or next_speaker != last_speaker:
                            # Erste Zeile nach Überschrift ODER Sprecherwechsel
                            next_display_speaker = next_speaker
                        else:
                            # Gleicher Sprecher wie vorher - nicht anzeigen
                            next_display_speaker = ''
                        last_speaker = next_speaker
                    
                    next_current_speaker_width_pt = _speaker_col_width(next_speaker) if next_speaker else 0.0

                    next_tables = build_tables_for_pair(
                        next_gr_tokens, next_de_tokens,
                        speaker=next_display_speaker,
                        line_label=next_line_label,
                        doc_width_pt=frame_w,
                        token_gr_style=token_gr, token_de_style=token_de,
                        num_style=num_style, style_speaker=style_speaker,
                        gr_bold=gr_bold,
                        reserve_speaker_col=reserve_all_speakers,
                        indent_pt=next_indent_pt,
                        global_speaker_width_pt=next_current_speaker_width_pt,
                        meter_on=versmass_display and next_has_versmass,
                        en_tokens=next_en_tokens,
                        tag_config=tag_config,  # NEU: Tag-Konfiguration für individuelle Breitenberechnung
                        base_line_num=next_base_num,  # NEU: Basis-Zeilennummer für Kommentar-Hinterlegung
                        line_comment_colors=line_comment_colors,  # NEU: Map von Zeilennummern zu Kommentar-Farben
                        hide_pipes=hide_pipes,  # NEU: Pipes (|) in Übersetzungen verstecken
                        block=pair_b  # NEU: Block-Objekt für comment_token_mask
                    )

                    # Sammle die Zeilen
                    rendered_lines.append(KeepTogether(next_tables))

                    # Breite gutschreiben - NUR wenn das Label ein gültiges Suffix für gestaffelte Zeilen hat (a-g)
                    if next_base_num is not None and next_line_label and _is_staggered_label(next_line_label):
                        next_w = measure_rendered_line_width(
                            next_gr_tokens, next_de_tokens,
                            gr_bold=gr_bold, is_notags=CURRENT_IS_NOTAGS,
                            remove_bars_instead=True
                        )
                        cum_width_by_base[next_base_num] = cum_width_by_base.get(next_base_num, 0.0) + next_w
                
                # OPTIMIERTE LÖSUNG gegen weiße Flächen:
                # Problem: Große KeepTogether-Blöcke erzwingen zu früh Seitenumbrüche
                # Lösung: Kleinere Blöcke + keepWithNext=True
                
                # 1. Alle Überschriften zusammen (mit keepWithNext=True im Style)
                if len(headers) > 0:
                    elements.append(KeepTogether(headers))
                
                # 2. Erste Textzeile (wird durch keepWithNext an Überschriften gekoppelt)
                if len(rendered_lines) > 0:
                    elements.append(rendered_lines[0])
                    elements.append(Spacer(1, INTER_PAIR_GAP_MM * MM))
                
                # 3. Zweite Textzeile einzeln
                if len(rendered_lines) > 1:
                    elements.append(rendered_lines[1])
                    elements.append(Spacer(1, INTER_PAIR_GAP_MM * MM))
                
                # WICHTIG: last_was_heading = False, weil wir gerade Textzeilen verarbeitet haben
                # Die nächsten Zeilen sollen normale Sprecher-Logik verwenden
                last_was_heading = False
                i = temp_scan
            else:
                # Keine Textzeilen gefunden - Header allein
                elements.append(KeepTogether(headers))
                last_was_heading = True
                i = temp_i
            
            continue

        if t == 'pair':
            gr_tokens = b.get('gr_tokens', [])[:]
            de_tokens = b.get('de_tokens', [])[:]
            en_tokens = b.get('en_tokens', [])  # NEU: Englische Tokens für 3-sprachige Texte
            speaker   = b.get('speaker') or ''
            line_label= b.get('label') or ''
            base_num  = b.get('base')  # None oder int

            # >>> NEU: Elisions-Übertragung wie im Epos
            gr_tokens = propagate_elision_markers(gr_tokens)
            # <<<

            # Einrückung: kumulative Breite aller bisherigen Teilverse dieses Basisverses
            # NUR wenn das Label ein gültiges Suffix für gestaffelte Zeilen hat (a-g)
            indent_pt = 0.0
            if base_num is not None and line_label and _is_staggered_label(line_label):
                indent_pt = max(0.0, cum_width_by_base.get(base_num, 0.0))

            # Prüfe auf Versmaß-Marker
            has_versmass = has_meter_markers(gr_tokens)
            
            # NEUE LOGIK: Sprecher nur bei Wechsel oder nach Überschrift anzeigen
            display_speaker = speaker
            if speaker:
                # Sprecher anzeigen wenn:
                # 1. Nach einer Überschrift (last_was_heading)
                # 2. Sprecherwechsel (speaker != last_speaker)
                # 3. Erster Sprecher überhaupt (last_speaker is None)
                if not last_was_heading and speaker == last_speaker:
                    # Gleicher Sprecher wie vorher - NICHT anzeigen
                    display_speaker = ''
                
                # Update tracking
                last_speaker = speaker
                last_was_heading = False
            
            # Berechne Sprecher-Spaltenbreite für DIESE Zeile
            # WICHTIG: Verwende den AKTUELLEN Sprecher für die Breite, auch wenn er nicht angezeigt wird!
            current_speaker_width_pt = _speaker_col_width(speaker) if speaker else 0.0

            tables = build_tables_for_pair(
                gr_tokens, de_tokens,
                speaker=display_speaker,  # Verwende display_speaker statt speaker!
                line_label=line_label,
                doc_width_pt=frame_w,
                token_gr_style=token_gr, token_de_style=token_de, num_style=num_style, style_speaker=style_speaker,
                gr_bold=gr_bold,
                reserve_speaker_col=reserve_all_speakers,
                indent_pt=indent_pt,
                global_speaker_width_pt=current_speaker_width_pt,  # Verwende aktuelle Breite!
                meter_on=versmass_display and has_versmass,
                en_tokens=en_tokens,
                tag_config=tag_config,  # NEU: Tag-Konfiguration für individuelle Breitenberechnung
                base_line_num=base_num,  # NEU: Basis-Zeilennummer für Kommentar-Hinterlegung
                line_comment_colors=line_comment_colors,  # NEU: Map von Zeilennummern zu Kommentar-Farben
                hide_pipes=hide_pipes,  # NEU: Pipes (|) in Übersetzungen verstecken
                block=b  # NEU: Block-Objekt für comment_token_mask
            )
            # WICHTIG: Alle Tabellen eines Paares/Triplikats zusammenhalten
            # (verhindert, dass GR/DE/EN über Seitenumbrüche getrennt werden)
            elements.append(KeepTogether(tables))

            # Abstand nach jedem Textblock hinzufügen
            # Finde den nächsten relevanten Block (überspringe 'blank' und 'title_brace')
            next_relevant_idx = i + 1
            while next_relevant_idx < len(blocks):
                next_block = blocks[next_relevant_idx]
                if next_block['type'] not in ['blank', 'title_brace']:
                    break
                next_relevant_idx += 1

            if next_relevant_idx < len(blocks):
                next_block = blocks[next_relevant_idx]
                if next_block['type'] == 'section':
                    # Weniger Abstand vor Überschriften
                    elements.append(Spacer(1, INTER_PAIR_GAP_MM * MM * 0.5))
                else:
                    elements.append(Spacer(1, INTER_PAIR_GAP_MM * MM))
            else:
                # Letzte Zeile: normaler Abstand
                elements.append(Spacer(1, INTER_PAIR_GAP_MM * MM))

            # Nach dem Rendern: Nur die Token-Breite dem Basisvers gutschreiben
            # NUR wenn das Label ein gültiges Suffix für gestaffelte Zeilen hat (a-g)
            if base_num is not None and line_label and _is_staggered_label(line_label):
                # Nur die eigentliche Textbreite zählt für die Einrückung,
                # Layout-Elemente (Nummern, Sprecher) stehen links und beeinflussen nicht den Textfluss
                this_w = measure_rendered_line_width(
                    gr_tokens, de_tokens,
                    gr_bold=gr_bold, is_notags=CURRENT_IS_NOTAGS,
                    remove_bars_instead=True
                )
                cum_width_by_base[base_num] = cum_width_by_base.get(base_num, 0.0) + this_w

            i += 1; continue

        i += 1

    doc.build(elements)

# ========= Batch (Legacy) =========
def category_and_label_from_input(infile:str):
    stem = Path(infile).stem; s = stem.lower()
    if s.startswith('inputkomödie') or s.startswith('inputkomoedie'):
        cat = 'Komödie'
        label = stem[len('InputKomödie'):] if stem.startswith('InputKomödie') else stem[len('InputKomodie'):]
    elif s.startswith('inputtragödie') or s.startswith('inputtragoedie'):
        cat = 'Tragödie'
        label = stem[len('InputTragödie'):] if stem.startswith('InputTragödie') else stem[len('InputTragoedie'):]
    else:
        cat = 'Drama'; label = stem
    label = re.sub(r'\W+', '', label) or 'Text'
    return cat, label

def output_name_fett(cat:str, label:str) -> str:   return f'{cat}{label}_Fett.pdf'
def output_name_normal(cat:str, label:str) -> str: return f'{cat}{label}_Normal.pdf'

def process_inputs_glob():
    return sorted(
        [str(p) for p in Path('.').glob('InputKomödie*.txt')] +
        [str(p) for p in Path('.').glob('InputKomodie*.txt')] +
        [str(p) for p in Path('.').glob('InputTragödie*.txt')] +
        [str(p) for p in Path('.').glob('InputTragoedie*.txt')]
    )

def run_batch(input_files):
    for infile in input_files:
        if not os.path.isfile(infile):
            print(f"⚠ Datei nicht gefunden, übersprungen: {infile}"); continue
        try:
            print(f"→ Verarbeite: {infile}")
            blocks = process_input_file(infile)
            cat, label = category_and_label_from_input(infile)
            out_fett = output_name_fett(cat, label)
            create_pdf(blocks, out_fett, gr_bold=True)
            print(f"✓ PDF erstellt → {out_fett}")
            out_norm = output_name_normal(cat, label)
            create_pdf(blocks, out_norm, gr_bold=False)
            print(f"✓ PDF erstellt → {out_norm}")
        except Exception as e:
            print(f"✗ Fehler bei {infile}: {e}")

if __name__ == '__main__':
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Poesie PDF Generator')
    parser.add_argument('input_file', nargs='?', help='Input file to process')
    parser.add_argument('--tag-config', help='JSON file with tag configuration')
    args = parser.parse_args()
    
    # Load tag configuration if provided
    if args.tag_config:
        load_tag_config(args.tag_config)
    
    if args.input_file:
        # Process single file
        if not os.path.isfile(args.input_file):
            print(f"⚠ Datei nicht gefunden: {args.input_file}")
            exit(1)
        try:
            print(f"→ Verarbeite: {args.input_file}")
            blocks = process_input_file(args.input_file)
            cat, label = category_and_label_from_input(args.input_file)
            out_fett = output_name_fett(cat, label)
            create_pdf(blocks, out_fett, gr_bold=True)
            print(f"✓ PDF erstellt → {out_fett}")
            out_norm = output_name_normal(cat, label)
            create_pdf(blocks, out_norm, gr_bold=False)
            print(f"✓ PDF erstellt → {out_norm}")
        except Exception as e:
            print(f"✗ Fehler bei {args.input_file}: {e}")
    else:
        # Process batch
        inputs = process_inputs_glob()
        if not inputs:
            print("⚠ Keine InputKomödie* / InputTragödie* gefunden.")
        else:
            run_batch(inputs)

# ========= PDF-Erstellung mit Versmaß-spezifischen Abständen =========
# Die ursprüngliche create_pdf Funktion wurde bereits oben definiert und 
# enthält bereits die Versmaß-spezifische Logik. Diese doppelte Definition
# wurde entfernt, um Endlosschleifen zu vermeiden.

