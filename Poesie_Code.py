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
from reportlab.platypus     import SimpleDocTemplate, Paragraph, Spacer, KeepTogether, Table, TableStyle, Flowable, CondPageBreak
from reportlab.lib          import colors
import re, os, html, unicodedata, json, argparse

# WICHTIG: Füge typing Imports hinzu für Type Hints
from typing import List, Dict, Any, Optional, Tuple

# Import für Preprocessing
try:
    from shared import preprocess
    from shared.preprocess import remove_tags_from_token, remove_all_tags_from_token, RE_WORD_START
except ImportError:
    # Fallback für direkten Aufruf
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from shared import preprocess
    from shared.preprocess import remove_tags_from_token, remove_all_tags_from_token, RE_WORD_START

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
def _strip_tags_from_token(tok: str, block: dict = None, tok_idx: int = None, tag_mode: str = "TAGS") -> str:
    """
    Entfernt Tags aus einem Token basierend auf tag_mode und token_meta.
    - Wenn tag_mode == "NO_TAGS": entferne alle Tags
    - Sonst: entferne nur Tags, die in token_meta[i]['removed_tags'] markiert sind
    WICHTIG: Farbsymbole (#, +, -, §, $) bleiben IMMER erhalten!
    """
    if not tok:
        return tok
    
    # WICHTIG: Hole Farbsymbol aus token_meta, falls vorhanden (von apply_colors gesetzt)
    color_symbol_from_meta = None
    if block is not None and tok_idx is not None:
        token_meta = block.get('token_meta', [])
        if tok_idx < len(token_meta):
            meta = token_meta[tok_idx]
            color_symbol_from_meta = meta.get('color_symbol')
    
    # WICHTIG: Speichere Farbsymbole vor der Tag-Entfernung (aus Token UND token_meta)
    color_symbols = []
    
    # ZUERST: Hole Farbsymbol aus token_meta (wird von apply_colors gesetzt)
    if color_symbol_from_meta:
        color_symbols = [color_symbol_from_meta]
    else:
        # FALLBACK: Prüfe Token nur wenn kein Farbsymbol in token_meta vorhanden ist
        for sym in ['#', '+', '-', '§', '$']:
            if sym in tok:
                color_symbols.append(sym)
                break
    
    # If NO_TAGS - remove everything
    if tag_mode == "NO_TAGS":
        cleaned = remove_all_tags_from_token(tok)
        # WICHTIG: Stelle sicher, dass Farbsymbole erhalten bleiben
        for sym in color_symbols:
            if sym not in cleaned:
                # Füge Farbsymbol am Anfang des Wortes hinzu (nach führenden Markern)
                match = RE_WORD_START.search(cleaned)
                if match:
                    cleaned = cleaned[:match.start(2)] + sym + cleaned[match.start(2):]
                else:
                    cleaned = sym + cleaned
        return cleaned
    
    # Otherwise remove only tags that were recorded as removed by apply_tag_visibility
    if block is not None and tok_idx is not None:
        token_meta = block.get('token_meta', [])
        if tok_idx < len(token_meta):
            meta = token_meta[tok_idx]
            removed_tags = set(meta.get('removed_tags', []))
            if removed_tags:
                cleaned = remove_tags_from_token(tok, removed_tags)
                # WICHTIG: Stelle sicher, dass Farbsymbole erhalten bleiben
                for sym in color_symbols:
                    if sym not in cleaned:
                        match = RE_WORD_START.search(cleaned)
                        if match:
                            cleaned = cleaned[:match.start(2)] + sym + cleaned[match.start(2):]
                        else:
                            cleaned = sym + cleaned
                return cleaned
    
    # nothing to remove for this token, keep as-is
    return tok

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
    """
    s = (s or '').strip()
    # NEU: Regex für Bereichs-Kommentare: (zahl-zahl+k/i) - MUSS ZUERST GEPRÜFT WERDEN!
    m_range = re.match(r'^\((-?\d+)-(-?\d+)([a-z]?)\)\s*(.*)$', s, re.IGNORECASE)
    if m_range:
        start = m_range.group(1)
        end = m_range.group(2)
        suffix = m_range.group(3)
        rest = m_range.group(4)
        line_num = f"{start}-{end}{suffix}"  # z.B. "2-4k"
        print(f"DEBUG extract_line_number: Bereichs-Kommentar erkannt: line_num={line_num}, rest={rest[:50] if rest else 'None'}")
        return (line_num, rest)
    
    # Regex für Zeilennummer: (Zahl[optionaler Buchstabe oder k/i]) - auch negative Zahlen!
    m = re.match(r'^\((-?\d+)([a-z]?)\)\s*(.*)$', s, re.IGNORECASE)
    if m:
        num = m.group(1)
        suffix = m.group(2)
        rest = m.group(3)
        line_num = f"{num}{suffix}"
        if suffix and suffix.lower() in ['k', 'i']:
            print(f"DEBUG extract_line_number: Einzelner Kommentar/Insertion erkannt: line_num={line_num}, rest={rest[:50] if rest else 'None'}")
        return (line_num, rest)
    
    return (None, s)

def is_comment_line(line_num: str | None) -> bool:
    """Prüft, ob eine Zeilennummer ein Kommentar ist (endet mit 'k')."""
    if not line_num:
        return False
    # WICHTIG: Normalisiere line_num (entferne Leerzeichen, Kleinbuchstaben)
    line_num_clean = line_num.strip().lower()
    # Prüfe ob es mit 'k' endet (für einfache Kommentare wie "9k")
    # ODER ob es das Format "zahl-zahlk" hat (für Bereichs-Kommentare wie "2-4k")
    return line_num_clean.endswith('k') or '-' in line_num_clean and line_num_clean.split('-')[-1].endswith('k')

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

def expand_slash_alternatives(tokens: list[str]) -> list[list[str]]:
    """
    ═══════════════════════════════════════════════════════════════════════════════════════
    BEDEUTUNGS-STRAUß: Expandiert Token-Listen mit `/`-Alternativen in mehrere Zeilen
    ═══════════════════════════════════════════════════════════════════════════════════════
    
    ZWECK:
        Implementiert das "BEDEUTUNGS-STRAUß"-Feature nach Vera F. Birkenbihl.
        Erlaubt mehrere Übersetzungsalternativen für ein Wort, die eng untereinander
        als "gekoppelte Doppel-/Dreifachzeile" dargestellt werden (wie DE/EN in 3-sprachigen PDFs).
    
    WARUM FUNKTIONIERT DAS SO GUT?
        1. FRÜHE TRANSFORMATION: Diese Funktion wird GANZ AM ANFANG aufgerufen (in process_input_file),
           VOR allen anderen Verarbeitungsschritten (Tagging, Farben, Meter-Marker, etc.)
        2. SAUBERE DATENSTRUKTUR: Erzeugt `*_tokens_alternatives` Listen, die durch ALLE
           nachfolgenden Schritte transparent durchgereicht werden
        3. POSITION PRESERVATION: Leere Strings an Positionen ohne `/` erhalten die Token-Ausrichtung
        4. KEINE DUPLIKATE: Griechische Zeile wird NICHT dupliziert (nur Übersetzungen expandiert)
    
    BEISPIEL:
        Input:  ['den|Mann/über|den|Mann', 'mir', 'sage,/verrate,', 'Muse,/Göttin,']
        Output: [
            ['den|Mann',         'mir', 'sage,',    'Muse,'],      # Alternative 0
            ['über|den|Mann',    '',    'verrate,', 'Göttin,']     # Alternative 1
        ]
        
        WICHTIG: Leerer String ('') bei 'mir' in Alternative 1, weil 'mir' kein `/` hat!
                 Dies erhält die Token-Positionen und Spaltenausrichtung im PDF.
    
    INTEGRATION MIT REST DES SYSTEMS:
        - Tags (nomen, verb, etc.) werden VOR dieser Funktion extrahiert → bleiben erhalten
        - Farben (#, +, -, §) sind bereits in Tokens → werden mitkopiert
        - Meter-Marker (´ˆˉ) sind bereits in Tokens → werden mitkopiert
        - HideTrans-Flags werden parallel gespeichert → funktionieren weiterhin
    
    Args:
        tokens: Liste von Tokens, möglicherweise mit `/`-Trennzeichen
        
    Returns:
        Liste von Token-Listen (eine pro Alternative)
        Wenn keine `/` vorhanden, wird eine einzige Zeile zurückgegeben
        Max. 4 Alternativen (bei 3 `/` pro Token)
    """
    # Zähle maximale Anzahl von Alternativen über alle Tokens
    max_alternatives = 1
    for token in tokens:
        if token:
            # Zähle `/` im Token (jedes `/` fügt eine Alternative hinzu)
            slash_count = token.count('/')
            alternatives_in_token = slash_count + 1
            max_alternatives = max(max_alternatives, alternatives_in_token)
    
    # Begrenze auf max. 4 Alternativen (3 `/` pro Token)
    max_alternatives = min(max_alternatives, 4)
    
    # Erstelle die erweiterten Zeilen
    result = []
    for alt_idx in range(max_alternatives):
        new_line = []
        for token in tokens:
            if not token:
                new_line.append('')
                continue
            
            # Splitte Token an `/`
            alternatives = token.split('/')
            
            # Wähle die entsprechende Alternative (oder letzte, falls Index zu groß)
            if alt_idx < len(alternatives):
                new_line.append(alternatives[alt_idx])
            else:
                # Kein weiteres `/` in diesem Token - verwende leeren String
                new_line.append('')
        
        result.append(new_line)
    
    return result

def detect_language_count_from_context(lines: list, current_idx: int) -> int:
    """
    Erkennt, ob der Text 2-, 3- oder 4-zeilig ist (1 antike + 1-3 Übersetzungen),
    indem die umgebenden Zeilen analysiert werden.
    
    Sucht nach normalen Zeilen (ohne 'i' oder 'k' Suffix) und zählt, wie viele Zeilen mit
    der gleichen Basisnummer aufeinanderfolgen.
    
    Returns:
        2, 3 oder 4 (Anzahl der Zeilen pro Block: 1 antike + 1-3 Übersetzungen)
    """
    # Suche rückwärts nach der letzten normalen Zeile (keine k, i Suffixe)
    search_range = 50  # Suche max. 50 Zeilen vor/nach
    
    for offset in range(1, min(search_range, current_idx + 1)):
        check_idx = current_idx - offset
        if check_idx < 0:
            break
            
        check_line = (lines[check_idx] or '').strip()
        if is_empty_or_sep(check_line):
            continue
            
        line_num, _ = extract_line_number(check_line)
        if line_num is None:
            continue
            
        # Ignoriere Kommentare und Insertionen
        if is_comment_line(line_num) or is_insertion_line(line_num):
            continue
        
        # Wir haben eine normale Zeile gefunden - zähle wie viele Zeilen mit dieser Nummer existieren
        lines_with_same_num = []
        j = check_idx
        while j < len(lines) and len(lines_with_same_num) < 6:  # Max 6 Zeilen prüfen (um 5 zu finden)
            test_line = (lines[j] or '').strip()
            if is_empty_or_sep(test_line):
                j += 1
                continue
                
            test_num, _ = extract_line_number(test_line)
            if test_num == line_num:
                lines_with_same_num.append(test_line)
                j += 1
            else:
                break
        
        # Wenn wir 2, 3, 4 oder 5 Zeilen gefunden haben, geben wir das zurück
        count = len(lines_with_same_num)
        if count >= 2:
            return min(count, 5)  # NEU: Max 5 (1 antike + bis zu 4 Übersetzungen)
    
    # Fallback: Suche vorwärts
    for offset in range(1, min(search_range, len(lines) - current_idx)):
        check_idx = current_idx + offset
        if check_idx >= len(lines):
            break
            
        check_line = (lines[check_idx] or '').strip()
        if is_empty_or_sep(check_line):
            continue
            
        line_num, _ = extract_line_number(check_line)
        if line_num is None:
            continue
            
        # Ignoriere Kommentare und Insertionen
        if is_comment_line(line_num) or is_insertion_line(line_num):
            continue
        
        # Zähle Zeilen mit dieser Nummer
        lines_with_same_num = []
        j = check_idx
        while j < len(lines) and len(lines_with_same_num) < 6:  # Max 6 Zeilen prüfen (um 5 zu finden)
            test_line = (lines[j] or '').strip()
            if is_empty_or_sep(test_line):
                j += 1
                continue
                
            test_num, _ = extract_line_number(test_line)
            if test_num == line_num:
                lines_with_same_num.append(test_line)
                j += 1
            else:
                break
        
        count = len(lines_with_same_num)
        if count >= 2:
            return min(count, 5)  # NEU: Max 5 (1 antike + bis zu 4 Übersetzungen)
    
    # Default: 2-sprachig
    return 2

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
                
                # ═══════════════════════════════════════════════════════════════════
                # FIX: Lücke bei führendem | im nächsten Token schließen
                # ═══════════════════════════════════════════════════════════════════
                # PROBLEM: Wenn nächstes Token mit | beginnt, endet aktuelle Silbe
                #          vor diesem | → Topline connected nicht perfekt zur Antenne
                # LÖSUNG: Verlängere x1_draw um kleinen Wert nach rechts
                # WANN: Nur für LETZTE Silbe (idx == num_segments - 1) UND
                #       wenn nächstes Token mit | beginnt
                if idx == num_segments - 1 and self.next_token_starts_with_bar:
                    # Kleine Verlängerung um Lücke zur Antenne zu schließen
                    x1_draw += 0.8  # pt - genug um Lücke zu schließen, nicht zu viel
                
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
def extract_hide_trans_flags(gr_tokens):
    """
    Extrahiert HideTrans-Flags aus griechischen Tokens BEVOR preprocess.py sie entfernt.
    
    WICHTIG: Diese Funktion muss VOR dem Preprocessing aufgerufen werden!
    preprocess.py entfernt '(HideTrans)' aus dem Token-String (Zeile 845).
    
    Returns:
        List[bool]: Parallel-Liste zu gr_tokens, True wenn Token (HideTrans) hat
    """
    flags = []
    for token in gr_tokens:
        # Prüfe auf HideTrans-Tag (case-insensitive)
        has_hide_trans = (
            '(HideTrans)' in token or 
            '(hidetrans)' in token or 
            '(HIDETRANS)' in token
        )
        flags.append(has_hide_trans)
    return flags

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
            # Start eines mehrteiliger Tokens - sammle erstmal
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
    
    Beispiele:
    - "18" -> False (keine Suffix)
    - "18b" -> True (Suffix 'b')
    - "18c" -> True (Suffix 'c')
    - "9i" -> False (Suffix 'i' ist für Insertions)
    - "(18b)" -> True (mit Klammern - backward compatibility)
    """
    if not label or len(label) < 2:
        return False
    
    # Entferne Klammern falls vorhanden (für backward compatibility)
    if label.startswith('(') and label.endswith(')'):
        label = label[1:-1]
    
    # Prüfe ob letztes Zeichen ein Buchstabe ist
    if label and label[-1].isalpha():
        suffix_char = label[-1].lower()
        return suffix_char in 'abcdefg'
    
    return False

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

    # ═══════════════════════════════════════════════════════════════════
    # FARBSYMBOL-ERKENNUNG: Nur das ERSTE Symbol bestimmt die Farbe!
    # ═══════════════════════════════════════════════════════════════════
    # WICHTIG: Nach dieser Erkennung werden ALLE Symbole entfernt!
    #
    # WARUM NUR ERSTES?
    #   - Token sollte normalerweise nur EIN Symbol haben
    #   - Falls mehrere (Bug): Nur erstes zählt (konsistent)
    #
    # BEISPIELE:
    #   "#der"    → Rot,  entferne #  → "der"
    #   "+ist"    → Blau, entferne +  → "ist"
    #   "#-der"   → Rot,  entferne #- → "der"  (Bug-Fall, beide entfernen!)
    
    color = None
    if '#' in raw:   color = '#FF0000'  # Rot
    elif '+' in raw: color = '#1E90FF'  # Blau
    elif '-' in raw: color = '#228B22'  # Grün
    elif '§' in raw: color = '#9370DB'  # Violett
    elif '$' in raw: color = '#FFA500'  # Orange
    
    # KRITISCH: Entferne ALLE Farbsymbole (nicht nur das erste!)
    # WARUM? Nach Tetris-Kollabieren können mehrere Symbole vorhanden sein
    # Beispiel: Token "-der" + token_meta "#" → "#-der" → beide entfernen!
    # WICHTIG: ~ und * NICHT entfernen (werden später separat behandelt)
    for symbol in ['#', '+', '-', '§', '$']:
        raw = raw.replace(symbol, '')
    
    # ~ entfernen (kein Farbsymbol, nur Marker)
    raw = raw.replace('~', '')

    m_endbars = re.search(r'\|+\s*$', raw)
    end_bar_count = len(m_endbars.group(0).strip()) if m_endbars else 0

    tags = RE_TAG_FINDALL.findall(raw)
    core_all = RE_TAG_STRIP.sub('', raw).strip()
    core_no_end = re.sub(r'\|+\s*$', '', core_all)

    core_no_end, color2, had_leading = _strip_leading_bar_color(core_no_end)
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

def measure_rendered_line_width(gr_tokens, de_tokens, *, gr_bold:bool, is_notags:bool, remove_bars_instead:bool = False, tag_config:dict = None, hide_trans_flags:list = None) -> float:
    """
    Berechnet die tatsächliche gerenderte Breite einer Zeile.
    WICHTIG: Verwendet die GLEICHEN Mechanismen wie build_tables_for_pair() für genaue Messung!
    
    NEU: Berücksichtigt SAFE_EPS_PT, Extra-Puffer, Tag-Config für akkurate Breiten-Berechnung
    von gestaffelten Zeilen (23a, 23b, etc.)
    
    hide_trans_flags: Optional[List[bool]]
        Parallel-Liste zu gr_tokens. True wenn Token (HideTrans) hatte.
        Bei True wird DE-Übersetzung NICHT in Breiten-Berechnung einbezogen!
    """
    if not gr_tokens:
        gr_tokens = []
    if not de_tokens:
        de_tokens = []
    
    # Fallback: Wenn keine Flags übergeben wurden, erstelle leere Liste
    if hide_trans_flags is None:
        hide_trans_flags = [False] * len(gr_tokens)

    # Verwende die gleichen Parameter wie in build_tables_for_pair
    GR_SIZE = 8.4
    DE_SIZE = 7.8
    gr_font = 'DejaVu-Bold' if gr_bold else 'DejaVu'
    de_font = 'DejaVu'
    
    # WICHTIG: cfg mit SAFE_EPS_PT basierend auf is_notags
    cfg = dict(CFG)
    if is_notags:
        cfg['SAFE_EPS_PT'] = 3.5  # NoTag-PDFs (wie in build_tables_for_pair)
    else:
        cfg['SAFE_EPS_PT'] = 4.0  # Tag-PDFs (wie in build_tables_for_pair)
    
    tag_mode = "NO_TAGS" if is_notags else "TAGS"
    
    # KRITISCH: Berechne Breiten PER TOKEN (wie in build_tables_for_pair)!
    # build_tables_for_pair macht: widths.append(max(w_gr, w_de, w_en))
    # Wir müssen also für JEDEN Token das Maximum nehmen und dann summieren!
    
    total_width = 0.0
    
    # Iteriere über alle Tokens (verwende längere Liste als Basis)
    max_tokens = max(len(gr_tokens), len(de_tokens))
    
    for i in range(max_tokens):
        gr_token = gr_tokens[i] if i < len(gr_tokens) else ''
        de_token = de_tokens[i] if i < len(de_tokens) else ''
        
        # WICHTIG: Prüfe HideTrans-Flag für diesen Token
        should_hide_trans = hide_trans_flags[i] if i < len(hide_trans_flags) else False
        
        # GRIECHISCHES TOKEN
        if gr_token:
            tags_in_token = RE_TAG.findall(gr_token)
            
            if tag_mode == "NO_TAGS" and tags_in_token:
                # FALL 1: NoTag-PDF + Token hat Tags → Tags entfernen
                core_text = RE_TAG_STRIP.sub('', gr_token).strip()
                for color_char in ['#', '+', '-', '§', '$', '~', '*']:
                    core_text = core_text.replace(color_char, '')
                core_text = core_text.replace('|', '')
                
                w_gr = visible_measure_token(core_text, font=gr_font, size=GR_SIZE, cfg=cfg, is_greek_row=True)
                w_gr += max(GR_SIZE * 0.03, 0.8)  # Extra-Puffer (wie in build_tables_for_pair)
                
            elif tags_in_token and tag_mode == "TAGS":
                # FALL 2: Tag-PDF + Token hat Tags → measure_token_width_with_visibility_poesie
                w_gr = measure_token_width_with_visibility_poesie(
                    gr_token, font=gr_font, size=GR_SIZE, cfg=cfg,
                    is_greek_row=True, tag_config=tag_config, tag_mode=tag_mode
                )
            else:
                # FALL 3: Keine Tags
                w_gr = visible_measure_token(gr_token, font=gr_font, size=GR_SIZE, cfg=cfg, is_greek_row=True)
                w_gr += max(GR_SIZE * 0.03, 0.8)  # Extra-Puffer (wie in build_tables_for_pair)
        else:
            w_gr = 0.0
        
        # DEUTSCHES TOKEN
        # KRITISCH: Wenn HideTrans aktiv ist, wird DE-Übersetzung NICHT gerendert!
        # Daher darf sie NICHT in die Breiten-Berechnung einfließen!
        if de_token and not should_hide_trans:
            w_de = visible_measure_token(de_token, font=de_font, size=DE_SIZE, cfg=cfg, is_greek_row=False)
        else:
            w_de = 0.0
        
        # WICHTIG: Nehme Maximum PER TOKEN (wie build_tables_for_pair: widths.append(max(w_gr, w_de, w_en)))
        total_width += max(w_gr, w_de)
    
    return total_width

def measure_full_layout_width(gr_tokens, de_tokens, speaker, line_label, *,
                             token_gr_style, token_de_style, num_style, style_speaker,
                             global_speaker_width_pt, gr_bold:bool = False, is_notags:bool = False, tag_config:dict = None) -> float:
    """Berechnet die Gesamtbreite einer Zeile inklusive aller Layout-Elemente."""
    # Token-Breite (robuste Berechnung)
    token_width = measure_rendered_line_width(
        gr_tokens, de_tokens,
        gr_bold=gr_bold, is_notags=is_notags,
        remove_bars_instead=False,
        tag_config=tag_config  # NEU: Tag-Config übergeben
    )

    # Layout-Elemente Breite
    layout_width = 0.0

    # Nummernspalte
    num_w = max(6.0*MM, _sw('[999]', num_style.fontName, num_style.fontSize) + 2.0)
    layout_width += num_w + NUM_GAP_MM * MM

    # Sprecher-Laterne (falls vorhanden oder reserviert)
    sp_w = max(global_speaker_width_pt, SPEAKER_COL_MIN_MM * MM)
    sp_gap = SPEAKER_GAP_MM * MM

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
def process_input_file(infile: str) -> List[Dict[str, Any]]:
    """Parst Input-Datei in Blöcke."""
    import logging
    logger = logging.getLogger(__name__)
    
    # NEU: Debug-Logging am Anfang
    logger.info("Poesie_Code.process_input_file: START reading %s", infile)
    
    with open(infile, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # NEU: Log Zeilenanzahl
    logger.info("Poesie_Code.process_input_file: read %d lines", len(lines))
    
    blocks = []
    i = 0
    while i < len(lines):
        line = (lines[i] or '').strip()
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
        # WICHTIG: Prüfe ZUERST, ob es ein Kommentar ist, BEVOR wir andere Verarbeitung machen
        if line_num is not None and is_comment_line(line_num):
            # Kommentar-Zeile: Extrahiere Zeilenbereich und speichere als Kommentar-Block
            start_line, end_line = extract_line_range(line_num)
            comment_block = {
                'type': 'comment',
                'line_num': line_num,
                'content': line_content,
                'start_line': start_line,
                'end_line': end_line,
                'original_line': line
            }
            # WICHTIG: Debug-Ausgabe um zu sehen, ob Kommentare erkannt werden
            print(f"DEBUG Poesie_Code.process_input_file: Kommentar erkannt: line_num={line_num}, content={line_content[:50] if line_content else 'None'}, start={start_line}, end={end_line}")
            blocks.append(comment_block)  # ← HIER WAR DAS PROBLEM: Das wurde NICHT erreicht!
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
            # NEU: Sammle auch Kommentare, aber füge sie NICHT sofort ein!
            comments_to_insert = []  # Liste: (insert_after_index, comment_block)
            while j < len(lines):
                next_line = (lines[j] or '').strip()
                if is_empty_or_sep(next_line):
                    j += 1
                    continue
                
                # Prüfe, ob die nächste Zeile ein Kommentar ist
                next_num_temp, next_content_temp = extract_line_number(next_line)
                if next_num_temp is not None and is_comment_line(next_num_temp):
                    # WICHTIG: Kommentar NICHT sofort einfügen, sondern merken!
                    start_line, end_line = extract_line_range(next_num_temp)
                    comment_block = {
                        'type': 'comment',
                        'line_num': next_num_temp,
                        'content': next_content_temp,
                        'start_line': start_line,
                        'end_line': end_line,
                        'original_line': next_line
                    }
                    # Merke: Dieser Kommentar soll NACH dem aktuellen pair-Block eingefügt werden
                    comments_to_insert.append(comment_block)
                    j += 1
                    continue  # Überspringe Kommentar-Zeilen
                
                next_num, _ = extract_line_number(next_line)
                if next_num == line_num:
                    lines_with_same_num.append(next_line)
                    j += 1
                else:
                    break
            
            # Jetzt haben wir alle Zeilen mit derselber Nummer
            # WICHTIG: Prüfe die ERSTE Zeile selbst ein Kommentar ist (sollte nicht passieren, aber sicherheitshalber)
            first_line_num, _ = extract_line_number(lines_with_same_num[0])
            if first_line_num is not None and is_comment_line(first_line_num):
                # Die erste Zeile ist ein Kommentar - das sollte bereits oben erkannt worden sein!
                # WICHTIG: i auf j setzen, um Endlosschleife zu vermeiden
                i = j
            
            num_lines = len(lines_with_same_num)
            
            # NEU: Spezielle Behandlung für Insertionszeilen (i)
            # Bei konsekutiven (i)-Zeilen müssen wir sie in Gruppen aufteilen
            if first_line_num is not None and is_insertion_line(first_line_num):
                # FÜR INSERTIONEN: Verwende die tatsächliche Anzahl der aufeinanderfolgenden Zeilen
                # mit derselben Insertionsnummer, NICHT den Kontext drumherum!
                # Wenn 4 Zeilen mit (777i) existieren → sie gehören ALLE zusammen
                # (1. Zeile = Griechisch, 2.-4. Zeile = Deutsche Übersetzungen)
                expected_lines_per_insertion = num_lines
                
                print(f"DEBUG: Insertionszeile erkannt: {first_line_num}, {num_lines} Zeilen gefunden, behandle als EINE zusammenhängende Gruppe")
                
                # Gruppiere die Zeilen in Blöcke von expected_lines_per_insertion
                insertion_idx = 0
                while insertion_idx < num_lines:
                    # Hole die nächsten expected_lines_per_insertion Zeilen
                    insertion_group = lines_with_same_num[insertion_idx:insertion_idx + expected_lines_per_insertion]
                    
                    if len(insertion_group) < expected_lines_per_insertion:
                        # Nicht genug Zeilen für eine vollständige Insertion - überspringe
                        print(f"WARNING: Unvollständige Insertionsgruppe: {len(insertion_group)} Zeilen, erwartet {expected_lines_per_insertion}")
                        break
                    
                    # Verarbeite diese Insertionsgruppe wie einen normalen Zeilenblock
                    gr_line = insertion_group[0]
                    de_line = insertion_group[1]
                    en_line = insertion_group[2] if expected_lines_per_insertion >= 3 and len(insertion_group) >= 3 else None
                    
                    # NEU: Optionale 4. Zeile (dritte Übersetzung) bei Insertionszeilen
                    trans3_line = insertion_group[3] if expected_lines_per_insertion >= 4 and len(insertion_group) >= 4 else None
                    
                    # Tokenisieren & führende Label/Sprecher abwerfen
                    gr_tokens = tokenize(gr_line)
                    de_tokens = tokenize(de_line)

                    lbl_gr, base_gr, sp_gr, gr_tokens = split_leading_label_and_speaker(gr_tokens)
                    lbl_de, base_de, sp_de, de_tokens = split_leading_label_and_speaker(de_tokens)

                    line_label = lbl_gr or lbl_de or ''
                    base_num   = base_gr if base_gr is not None else base_de
                    speaker    = sp_gr or ''

                    # Extrahiere HideTrans-Flags
                    hide_trans_flags = extract_hide_trans_flags(gr_tokens)

                    # Elisions-Übertragung
                    gr_tokens = propagate_elision_markers(gr_tokens)

                    # Für 3-sprachige Texte: Englische Zeile verarbeiten
                    en_tokens = []
                    if en_line:
                        en_tokens = tokenize(en_line)
                        lbl_en, base_en, sp_en, en_tokens = split_leading_label_and_speaker(en_tokens)
                    
                    # NEU: Für 4-zeilige Blöcke: Dritte Übersetzung verarbeiten
                    trans3_tokens = []
                    if trans3_line:
                        trans3_tokens = tokenize(trans3_line)
                        lbl_trans3, base_trans3, sp_trans3, trans3_tokens = split_leading_label_and_speaker(trans3_tokens)

                    # ═══════════════════════════════════════════════════════════════════════════
                    # NEU: BEDEUTUNGS-STRAUß - Expandiere `/`-Alternativen (auch bei Insertionen!)
                    # ═══════════════════════════════════════════════════════════════════════════
                    # WARUM HIER?
                    #   - NACH Tokenisierung: Tokens sind bereits aufgespalten
                    #   - NACH Label/Speaker-Extraktion: Strukturinformationen sind erhalten
                    #   - NACH HideTrans-Extraktion: Flags sind bereits gesichert
                    #   - NACH Elisions-Übertragung: Marker sind bereits propagiert
                    #   - VOR Block-Erstellung: Datenstruktur kann sauber aufgebaut werden
                    #
                    # FUNKTIONSWEISE:
                    #   1. Prüfe ob IRGENDEINE Übersetzung `/` enthält
                    #   2. Expandiere ALLE Übersetzungen (auch die ohne `/`)
                    #   3. Gleiche Anzahl Alternativen an (fülle mit leeren Zeilen auf)
                    #   4. Speichere als *_tokens_alternatives Listen im Block
                    #
                    # RESULTAT:
                    #   Block enthält EINE griechische Zeile + MEHRERE Übersetzungsalternativen
                    #   Die Rendering-Funktion (build_tables_for_pair) erhält ALLE Alternativen
                    #   und rendert sie als EINE gekoppelte Tabelle (nicht mehrere separate!)
                    
                    has_slash_in_de = any('/' in token for token in de_tokens if token)
                    has_slash_in_en = any('/' in token for token in en_tokens if token)
                    has_slash_in_trans3 = any('/' in token for token in trans3_tokens if token)
                    
                    if has_slash_in_de or has_slash_in_en or has_slash_in_trans3:
                        # Es gibt `/`-Alternativen! Expandiere die Übersetzungen
                        de_lines = expand_slash_alternatives(de_tokens)
                        en_lines = expand_slash_alternatives(en_tokens) if en_tokens else [[]]
                        trans3_lines = expand_slash_alternatives(trans3_tokens) if trans3_tokens else [[]]
                        
                        # WICHTIG: Alle Zeilen müssen gleich viele Alternativen haben
                        max_alternatives = max(len(de_lines), len(en_lines), len(trans3_lines))
                        
                        while len(de_lines) < max_alternatives:
                            de_lines.append([''] * len(de_tokens))
                        while len(en_lines) < max_alternatives:
                            en_lines.append([''] * len(en_tokens))
                        while len(trans3_lines) < max_alternatives:
                            trans3_lines.append([''] * len(trans3_tokens))
                        
                        # ═══════════════════════════════════════════════════════════════════
                        # KRITISCH: Block-Struktur mit Alternativen
                        # ═══════════════════════════════════════════════════════════════════
                        # WARUM FUNKTIONIERT DAS SO GUT?
                        #
                        # 1. EINE GRIECHISCHE ZEILE: `gr_tokens` wird nur EINMAL gespeichert
                        #    → Im PDF erscheint Griechisch nur einmal (kein Duplikat!)
                        #
                        # 2. MEHRERE ÜBERSETZUNGEN: `*_tokens_alternatives` sind LISTEN von Listen
                        #    → Jede Alternative ist eine separate Token-Liste
                        #    → Alle haben gleiche Länge (aufgefüllt mit leeren Strings)
                        #
                        # 3. KOMPATIBILITÄT: Normale Blöcke (ohne `/`) funktionieren weiterhin
                        #    → Rendering-Code prüft ob `*_tokens_alternatives` existiert
                        #    → Falls nicht: Erstellt automatisch `[[de_tokens]]` (eine Alternative)
                        #
                        # 4. DURCHGÄNGIGKEIT: Alle nachfolgenden Schritte arbeiten mit dieser Struktur
                        #    → Kommentare: Block wird durchgereicht
                        #    → Farben: In token_meta gespeichert, bleibt erhalten
                        #    → Tags: Bereits extrahiert, funktioniert parallel
                        #    → Hide-Trans: Flags parallel gespeichert, funktioniert weiterhin
                        #
                        # 5. RENDERING: build_tables_for_pair() erhält ALLE Alternativen gleichzeitig
                        #    → Baut EINE Tabelle mit mehreren DE-Zeilen (nicht separate Tabellen!)
                        #    → Minimales Padding zwischen Alternativen (gap_de_to_en)
                        #    → Sieht aus wie EN unter DE in 3-sprachigen PDFs
                        
                        # NEU: Erstelle EINEN Block mit MEHREREN Übersetzungsvarianten
                        # Die griechische Zeile erscheint nur EINMAL, aber mit mehreren Übersetzungen darunter
                        blocks.append({
                            'type':'pair',
                            'speaker': speaker,
                            'label': line_label,
                            'base':  base_num,
                            'gr_tokens': gr_tokens,  # Griechisch NUR EINMAL!
                            'de_tokens_alternatives': de_lines,  # NEU: Liste von Alternativen
                            'en_tokens_alternatives': en_lines if en_tokens else None,  # NEU: Liste von Alternativen
                            'trans3_tokens_alternatives': trans3_lines if trans3_tokens else None,  # NEU: Liste von Alternativen
                            'hide_trans_flags': hide_trans_flags
                        })
                    else:
                        # Keine `/`-Alternativen - normaler Block
                        blocks.append({
                            'type':'pair',
                            'speaker': speaker,
                            'label': line_label,
                            'base':  base_num,
                            'gr_tokens': gr_tokens,
                            'de_tokens': de_tokens,
                            'en_tokens': en_tokens,
                            'trans3_tokens': trans3_tokens,  # NEU: Dritte Übersetzung
                            'hide_trans_flags': hide_trans_flags
                        })
                    
                    insertion_idx += expected_lines_per_insertion
                
                # Füge gesammelte Kommentare ein
                for comment_block in comments_to_insert:
                    blocks.append(comment_block)
                
                i = j
                continue
            
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
                
                # NEUE FLEXIBILITÄT: Unterstütze 2-4 Zeilen pro Block (1 antike + 1-3 Übersetzungen)
                # Bei 5+ Zeilen: Verarbeite die ersten 4, rest wird beim nächsten Durchlauf verarbeitet
                
                # WICHTIG: Wenn >= 5 Zeilen mit gleicher Nummer existieren, verarbeite nur die ersten 4
                # und lasse die restlichen für den nächsten Block-Durchlauf übrig
                if num_lines >= 5:
                    # Verarbeite nur die ersten 4 Zeilen als einen Block
                    lines_to_process = lines_with_same_num[:4]
                    # WICHTIG: Setze j so, dass beim nächsten Durchlauf die 5. Zeile verarbeitet wird
                    # j zeigt bereits auf die erste Zeile NACH allen gesammelten Zeilen
                    # Wir müssen j um (num_lines - 4) zurücksetzen, damit die restlichen Zeilen verarbeitet werden
                    j = i + 4  # Starte nächsten Block bei Zeile 5
                else:
                    lines_to_process = lines_with_same_num
                
                # WICHTIG: Erste Zeile = IMMER antike Sprache, weitere = Übersetzungen
                # UNABHÄNGIG von Sprechern oder Buchstaben!
                gr_line = lines_to_process[0]
                de_line = lines_to_process[1] if len(lines_to_process) >= 2 else None
                en_line = lines_to_process[2] if len(lines_to_process) >= 3 else None
                
                # NEU: Optionale 4. Zeile (dritte Übersetzung)
                trans3_line = lines_to_process[3] if len(lines_to_process) >= 4 else None
                
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

                # WICHTIG: Extrahiere HideTrans-Flags BEVOR Elisions-Marker angewendet werden
                # (Elisions können Tokens ändern, aber HideTrans-Flags bleiben parallel)
                hide_trans_flags = extract_hide_trans_flags(gr_tokens)

                # WICHTIG: Elisions-Übertragung direkt nach dem Tokenizing anwenden
                gr_tokens = propagate_elision_markers(gr_tokens)

                # Für 3-sprachige Texte: Englische Zeile verarbeiten
                en_tokens = []
                if en_line:
                    en_tokens = tokenize(en_line)
                    # Entferne Zeilennummer und Sprecher aus englischer Zeile
                    lbl_en, base_en, sp_en, en_tokens = split_leading_label_and_speaker(en_tokens)
                
                # NEU: Für 4-zeilige Blöcke: Dritte Übersetzung verarbeiten
                trans3_tokens = []
                if trans3_line:
                    trans3_tokens = tokenize(trans3_line)
                    # Entferne Zeilennummer und Sprecher aus dritter Übersetzungszeile
                    lbl_trans3, base_trans3, sp_trans3, trans3_tokens = split_leading_label_and_speaker(trans3_tokens)

                # ═══════════════════════════════════════════════════════════════════════════
                # NEU: BEDEUTUNGS-STRAUß - Expandiere `/`-Alternativen in Übersetzungen
                # ═══════════════════════════════════════════════════════════════════════════
                # Prüfe ob IRGENDEINE Übersetzungszeile `/` enthält
                has_slash_in_de = any('/' in token for token in de_tokens if token)
                has_slash_in_en = any('/' in token for token in en_tokens if token)
                has_slash_in_trans3 = any('/' in token for token in trans3_tokens if token)
                
                if has_slash_in_de or has_slash_in_en or has_slash_in_trans3:
                    # Es gibt `/`-Alternativen! Expandiere die Übersetzungen
                    de_lines = expand_slash_alternatives(de_tokens)
                    en_lines = expand_slash_alternatives(en_tokens) if en_tokens else [[]]
                    trans3_lines = expand_slash_alternatives(trans3_tokens) if trans3_tokens else [[]]
                    
                    # WICHTIG: Alle Zeilen müssen gleich viele Alternativen haben
                    # Fülle kürzere Listen mit leeren Zeilen auf
                    max_alternatives = max(len(de_lines), len(en_lines), len(trans3_lines))
                    
                    while len(de_lines) < max_alternatives:
                        de_lines.append([''] * len(de_tokens))
                    while len(en_lines) < max_alternatives:
                        en_lines.append([''] * len(en_tokens))
                    while len(trans3_lines) < max_alternatives:
                        trans3_lines.append([''] * len(trans3_tokens))
                    
                    # NEU: Erstelle EINEN Block mit MEHREREN Übersetzungsvarianten
                    # Die griechische Zeile erscheint nur EINMAL, aber mit mehreren Übersetzungen darunter
                    blocks.append({
                        'type':'pair',
                        'speaker': speaker,
                        'label': line_label,
                        'base':  base_num,
                        'gr_tokens': gr_tokens,  # Griechisch NUR EINMAL!
                        'de_tokens_alternatives': de_lines,  # NEU: Liste von Alternativen
                        'en_tokens_alternatives': en_lines if en_tokens else None,  # NEU: Liste von Alternativen
                        'trans3_tokens_alternatives': trans3_lines if trans3_tokens else None,  # NEU: Liste von Alternativen
                        'hide_trans_flags': hide_trans_flags
                    })
                else:
                    # Keine `/`-Alternativen - normaler Block
                    blocks.append({
                        'type':'pair',
                        'speaker': speaker,
                        'label': line_label,
                        'base':  base_num,
                        'gr_tokens': gr_tokens,
                        'de_tokens': de_tokens,
                        'en_tokens': en_tokens,  # NEU: Englische Tokens für 3-sprachige Texte
                        'trans3_tokens': trans3_tokens,  # NEU: Dritte Übersetzung für 4-zeilige Blöcke
                        'hide_trans_flags': hide_trans_flags  # NEU: HideTrans-Flags für jeden Token
                    })
                
                # JETZT die gesammelten Kommentare einfügen (NACH dem pair-Block!)
                for comment_block in comments_to_insert:
                    blocks.append(comment_block)
                
                # ← KRITISCH: Hier fehlte die Aktualisierung von i!
                i = j  # ← FIX: Setze i auf j, um zur nächsten unverarbeiteten Zeile zu springen
                continue  # ← WICHTIG: continue, um die äußere while-Schleife fortzusetzen
            
            else:
                # Nur eine Zeile mit dieser Nummer - könnte Strukturzeile oder Fehler sein
                # Als Fallback: Prüfe Sprachinhalt (OHNE Sprecher zu berücksichtigen!)
                line_without_speaker = _strip_speaker_prefix_for_classify(line_content)
                if is_greek_line(line_without_speaker) or is_latin_line(line_without_speaker):
                    # Antike Sprache ohne Übersetzung
                    gr_tokens = tokenize(line)
                    lbl_gr, base_gr, sp_gr, gr_tokens = split_leading_label_and_speaker(gr_tokens)
                    
                    # Extrahiere HideTrans-Flags (wichtig für konsistentes Verhalten)
                    hide_trans_flags = extract_hide_trans_flags(gr_tokens)
                    
                    gr_tokens = propagate_elision_markers(gr_tokens)
                    
                    blocks.append({
                        'type':'pair',
                        'speaker': sp_gr or '',
                        'label': lbl_gr or '',
                        'base': base_gr,
                        'gr_tokens': gr_tokens,
                        'de_tokens': [],
                        'hide_trans_flags': hide_trans_flags
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
                        'de_tokens': de_tokens,
                        'hide_trans_flags': []  # Keine gr_tokens, also keine Flags
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
                while i < len(lines) and is_empty_or_sep(lines[i]): i += 1

                de_line = ''
                if i < len(lines):
                    cand = (lines[i] or '').strip()
                    # NEU: Prüfe, ob die Kandidaten-Zeile ein Kommentar ist - überspringe sie dann
                    cand_num, _ = extract_line_number(cand)
                    if cand_num is not None and is_comment_line(cand_num):
                        # Kommentar-Zeile überspringen
                        i += 1
                        while i < len(lines) and is_empty_or_sep(lines[i]): i += 1
                        if i < len(lines):
                            cand = (lines[i] or '').strip()
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
                           'gr_tokens': [], 'de_tokens': de_tokens, 'hide_trans_flags': []})
            i += 1

    # NEU: Log am Ende
    logger.info("Poesie_Code.process_input_file: END - parsed %d blocks", len(blocks))
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
                                               tag_config: dict = None,
                                               tag_mode: str = "TAGS") -> float:
    """
    Berechnet die Breite eines Tokens - Poesie-Version.
    WICHTIG: Diese Funktion erhält das Token NACH der Vorverarbeitung (apply_tag_visibility).
    Die Tags, die im Token noch vorhanden sind, sind bereits die sichtbaren Tags!
    
    KRITISCH: tag_mode bestimmt den Puffer, NICHT die Tag-Präsenz im Token!
    In Tag-PDFs haben manche Wörter keine Tags (hideTags/Config) → trotzdem Tag-Puffer verwenden!
    """
    if not token:
        return 0.0

    # Berechne Breite mit dem Token, wie es ist
    w_with_remaining_tags = visible_measure_token(token, font=font, size=size, cfg=cfg, is_greek_row=is_greek_row)
    
    # NEUE STRATEGIE (nach User-Feedback): NoTag-PDFs sind jetzt das Vorbild für Wörter ohne Tags!
    # Tag-PDFs: Wörter MIT Tags = 0.8pt, Wörter OHNE Tags = 0.8pt (erhöht von 0.3pt!)
    # NoTag-PDFs: ALLE Wörter = 0.8pt (unverändert, perfekt!)
    
    tags_in_token = RE_TAG.findall(token)
    
    if tag_mode == "TAGS":
        # Tag-PDF → Wörter mit UND ohne Tags bekommen jetzt gleichen Puffer!
        # Grund: NoTag-PDFs sind jetzt das Vorbild für Wörter ohne Tags!
        if tags_in_token:
            base_padding = max(size * 0.03, 0.8)  # MIT Tags → Puffer
        else:
            base_padding = max(size * 0.03, 0.8)  # OHNE Tags → ERHÖHT von 0.3pt auf 0.8pt!
    else:
        # NoTag-PDF → ALLE Wörter bekommen gleichen Puffer (unverändert, perfekt!)
        base_padding = max(size * 0.03, 0.8)
    
    return w_with_remaining_tags + base_padding

def _calculate_column_widths(tokens: list, tag_mode: str) -> list:
    """
    Berechnet die Spaltenbreiten für eine Token-Liste.
    WICHTIG: tag_mode bestimmt, ob Tags in der Breiten-Berechnung berücksichtigt werden!
    
    tag_mode='TAGS' → Breite MIT Tags
    tag_mode='NO_TAGS' → Breite OHNE Tags (schmaler!)
    """
    widths = []
    for token in tokens:
        if tag_mode == 'NO_TAGS':
            # Entferne Tags aus Token für Breiten-Berechnung
            token_display = remove_all_tags_from_token(token)
        else:
            token_display = token
        # Berechne Breite basierend auf Zeichen-Länge
        width = len(token_display) * CHAR_WIDTH  # CHAR_WIDTH ist eine Konstante
        widths.append(width)
    return widths

def build_tables_for_pair(gr_tokens: list[str], de_tokens: list[str] = None, 
                          indent_pt: float = 0.0,
                          global_speaker_width_pt: float = None,
                          meter_on: bool = False,
                          tag_mode: str = "TAGS",
                          speaker: str = "",
                          line_label: str = "",
                          doc_width_pt: float = 595.0,
                          token_gr_style: ParagraphStyle = None,
                          token_de_style: ParagraphStyle = None,
                          num_style: ParagraphStyle = None,
                          style_speaker: ParagraphStyle = None,
                          gr_bold: bool = False,
                          reserve_speaker_col: bool = False,
                          en_tokens: list[str] = None,
                          trans3_tokens: list[str] = None,  # NEU: Dritte Übersetzung
                          tag_config: dict = None,
                          base_line_num: int = None,
                          line_comment_colors: dict = None,
                          hide_pipes: bool = False,
                          block: dict = None,
                          hide_trans_flags: list[bool] = None,  # NEU: HideTrans-Flags
                          de_tokens_alternatives: list[list[str]] = None,  # NEU: Alternative Übersetzungen
                          en_tokens_alternatives: list[list[str]] = None,
                          trans3_tokens_alternatives: list[list[str]] = None):
    """
    ═══════════════════════════════════════════════════════════════════════════════════════
    HAUPTFUNKTION: Erstellt ReportLab-Tabellen für ein griechisch-deutsches Verspaar
    ═══════════════════════════════════════════════════════════════════════════════════════
    
    KERNFUNKTIONALITÄT:
        Baut Tabellen mit Token-Spalten für:
        - Griechische Zeile (einmal)
        - Deutsche Übersetzung(en) (mehrere möglich durch `/`-Alternativen)
        - Englische Übersetzung(en) (optional)
        - Dritte Übersetzung(en) (optional)
    
    BEDEUTUNGS-STRAUß INTEGRATION:
        Diese Funktion wurde erweitert um MEHRERE Übersetzungsalternativen zu unterstützen.
        
        ALTE ARCHITEKTUR (vor `/`-Feature):
            - Ein Aufruf = Eine Tabelle mit [GR, DE, EN?, trans3?] Zeilen
            - Für Alternativen: Multiple Aufrufe → Multiple separate Tabellen → Große Abstände
        
        NEUE ARCHITEKTUR (mit `/`-Feature):
            - Ein Aufruf = Eine Tabelle mit [GR, DE-alt0, DE-alt1, DE-alt2, EN?, trans3?] Zeilen
            - ALLE Alternativen in EINER Tabelle → Minimale Abstände zwischen Alternativen
            - Sieht aus wie DE/EN in 3-sprachigen PDFs (eng gekoppelt)
    
    WARUM FUNKTIONIERT DAS SO GUT?
        1. PARAMETER-DESIGN: Akzeptiert sowohl alte (de_tokens) als auch neue Parameter
           (*_tokens_alternatives), dadurch 100% rückwärtskompatibel
        
        2. AUTOMATISCHE KONVERTIERUNG: Wenn alte Parameter übergeben werden, wandelt
           Funktion automatisch in neue Struktur um (Zeile 2069-2093)
        
        3. EINHEITLICHE VERARBEITUNG: Ab Zeile 2094 arbeitet Code nur noch mit
           *_lines Listen, egal ob Alternativen vorhanden oder nicht
        
        4. SPALTENBREITEN: Berechnet maximale Breite über ALLE Alternativen (Zeile 2119-2136)
           → Alle Alternativen-Zeilen haben gleiche Spaltenbreiten
           → Token bleiben vertikal ausgerichtet
        
        5. ZEILEN-BAU: Schleife baut zusätzliche DE-Zeilen für Alternativen (Zeile 2559-2601)
           → Verwendet gleiche Zell-Erstellung wie Haupt-DE-Zeile
           → Keine Zeilennummer/Sprecher bei Alternativen (leere Strings)
        
        6. PADDING-LOGIK: Dynamische Style-Regeln basierend auf Anzahl Alternativen
           (Zeile 2668-2683 für meter_on, Zeile 2715-2730 für normale PDFs)
           → GR-zu-DE: Normaler Abstand (gap_ancient_to_modern)
           → DE-zu-DE-alt: Minimaler Abstand (gap_de_to_en, wie DE-zu-EN!)
           → Alternativen bilden "gekoppelte Mehrfachzeile"
    
    KOMPATIBILITÄT MIT ANDEREN FEATURES:
        - Tags (nomen, verb): Funktioniert! Token-Meta parallel durchgereicht
        - Farben (#+-§): Funktioniert! In Tokens enthalten, werden mitkopiert
        - HideTrans: Funktioniert! Flags parallel gespeichert, gelten für alle Alternativen
        - Meter (Versmaß): Funktioniert! Gilt nur für GR-Zeile (die nur einmal erscheint)
        - Kommentare: Funktioniert! Block wird durchgereicht mit allen Infos
        - Sprecher: Funktioniert! Nur bei erster Alternative angezeigt
        - Gestaffelte Zeilen: Funktioniert! Indent gilt für gesamten Block
    
    WICHTIG: Spaltenbreiten müssen NACH dem Tag-Entfernen berechnet werden!
    
    hide_trans_flags: Optional[List[bool]]
        Parallel-Liste zu gr_tokens. True wenn Token (HideTrans) hatte.
        Diese Flags werden VOR dem Preprocessing extrahiert, damit sie verfügbar sind.
    
    de_tokens_alternatives, en_tokens_alternatives, trans3_tokens_alternatives: Optional[List[List[str]]]
        NEU: Alternative Übersetzungen (BEDEUTUNGS-STRAUß durch `/` erzeugt).
        Wenn angegeben, werden ALLE Alternativen in EINER Tabelle gerendert (eng untereinander).
        de_tokens/en_tokens/trans3_tokens werden dann ignoriert!
    """
    
    # Standardwerte setzen falls nicht übergeben
    if doc_width_pt is None:
        doc_width_pt = A4[0] - 40*MM
    
    # ═══════════════════════════════════════════════════════════════════
    # NEU: BEDEUTUNGS-STRAUß - Alternative Übersetzungen verarbeiten
    # ═══════════════════════════════════════════════════════════════════
    # ZWECK: Konvertiere alte API (de_tokens) zu neuer API (*_tokens_alternatives)
    #        Dies macht die Funktion 100% rückwärtskompatibel!
    #
    # FUNKTIONSWEISE:
    #   - Wenn *_tokens_alternatives angegeben: Verwende diese (neuer Code-Pfad)
    #   - Wenn NICHT angegeben: Konvertiere de_tokens zu [[de_tokens]] (alter Code-Pfad)
    #   - Ab diesem Punkt arbeitet ALLES mit *_lines Listen
    #
    # WARUM SO?
    #   - Alter Code (ohne `/`) muss weiterhin funktionieren
    #   - Neuer Code (mit `/`) verwendet bereits die neue Struktur
    #   - Diese Konvertierung macht beide Fälle identisch für Rest der Funktion
    
    # Wenn *_tokens_alternatives angegeben sind, verwende diese statt einzelner Tokens
    # Konvertiere sie in Listen von Alternativen für die spätere Verarbeitung
    if de_tokens_alternatives is not None:
        # Verwende Alternativen - ignoriere de_tokens
        pass
    else:
        # Keine Alternativen - verwende normale de_tokens als einzige Alternative
        if de_tokens is None:
            de_tokens_alternatives = [[]]
        else:
            de_tokens_alternatives = [de_tokens]
    
    if en_tokens_alternatives is not None:
        pass
    else:
        if en_tokens is None:
            en_tokens_alternatives = [[]]
        else:
            en_tokens_alternatives = [en_tokens]
    
    if trans3_tokens_alternatives is not None:
        pass
    else:
        if trans3_tokens is None:
            trans3_tokens_alternatives = [[]]
        else:
            trans3_tokens_alternatives = [trans3_tokens]
    
    # Effektive cfg abhängig von meter_on (Versmaß an/aus) und tag_mode
    eff_cfg = dict(CFG)
    if meter_on:
        eff_cfg['CELL_PAD_LR_PT'] = 0.0
        if tag_mode == "TAGS":
            # Tag-PDFs (Versmaß): Basis-Padding + Meter-Adjust-Kompensation
            # WARUM? ToplineTokenFlowable verschiebt Linien um METER_ADJUST_RIGHT_PT
            # → Diese Verschiebung "stiehlt" Platz zwischen Tokens
            # → Füge METER_ADJUST zum Padding hinzu um Überlappung zu vermeiden
            base_padding = eff_cfg.get('TOKEN_PAD_PT_VERSMASS_TAG', 2.0)
            eff_cfg['SAFE_EPS_PT'] = base_padding + METER_ADJUST_RIGHT_PT
        else:
            # NoTag-PDFs (Versmaß): Basis-Padding + Meter-Adjust-Kompensation
            # WICHTIG: NoTag braucht mehr Padding als Tag (4pt vs 2pt)
            # PLUS die Meter-Adjust-Kompensation für korrekte Abstände
            base_padding = eff_cfg.get('TOKEN_PAD_PT_VERSMASS_NOTAG', 4.0)
            eff_cfg['SAFE_EPS_PT'] = base_padding + METER_ADJUST_RIGHT_PT
        eff_cfg['INTER_PAIR_GAP_MM'] = INTER_PAIR_GAP_MM_VERSMASS
    else:
        eff_cfg['CELL_PAD_LR_PT'] = 0.5
        if tag_mode == "TAGS":
            eff_cfg['SAFE_EPS_PT'] = eff_cfg.get('TOKEN_PAD_PT_NORMAL_TAG', 4.0)
            eff_cfg['INTER_PAIR_GAP_MM'] = INTER_PAIR_GAP_MM_NORMAL_TAG
        else:
            # NoTag-PDFs (Normal): Erhöht von 0.5 auf 3.5 (näher an Tag-PDFs 4.0!)
            # Dies gibt den "Grund-Abstand" den Tag-PDFs haben!
            eff_cfg['SAFE_EPS_PT'] = 3.5  # ERHÖHT von 0.5 (war zu eng!)
            eff_cfg['INTER_PAIR_GAP_MM'] = INTER_PAIR_GAP_MM_NORMAL_NOTAG

    # WICHTIG: Spaltenlängen angleichen (zeilengetreu) - MUSS VOR der widths-Berechnung kommen!
    # ═══════════════════════════════════════════════════════════════════
    # BEDEUTUNGS-STRAUß: Berechne maximale Spaltenanzahl über ALLE Alternativen
    # ═══════════════════════════════════════════════════════════════════
    # WARUM?
    #   - Verschiedene Alternativen können unterschiedlich viele Tokens haben
    #   - Beispiel: Alt 0 = 5 Tokens, Alt 1 = 7 Tokens → Tabelle braucht 7 Spalten
    #   - Alle kürzeren Alternativen werden mit leeren Strings aufgefüllt
    #
    # FUNKTIONSWEISE:
    #   1. Iteriere über ALLE Alternativen in de_lines, en_lines, trans3_lines
    #   2. Finde maximale Länge
    #   3. Fülle alle kürzeren Listen mit leeren Strings auf
    #   4. Ergebnis: Alle de_lines[i] haben gleiche Länge (=cols)
    
    # Bei Alternativen: Berechne maximale Spaltenanzahl über ALLE Alternativen
    gr = gr_tokens[:]
    
    # Konvertiere Alternativen zu einheitlicher Liste
    cols = len(gr)
    for de_alt in de_tokens_alternatives:
        cols = max(cols, len(de_alt))
    for en_alt in en_tokens_alternatives:
        cols = max(cols, len(en_alt))
    for trans3_alt in trans3_tokens_alternatives:
        cols = max(cols, len(trans3_alt))
    
    if cols == 0:
        # Komplett leerer Block - rendere nichts
        return []
    
    # Passe GR-Zeile an Spaltenlänge an
    gr = gr_tokens[:] + [''] * (cols - len(gr_tokens))
    
    # Passe ALLE Alternativen an Spaltenlänge an
    de_lines = [alt[:] + [''] * (cols - len(alt)) for alt in de_tokens_alternatives]
    en_lines = [alt[:] + [''] * (cols - len(alt)) for alt in en_tokens_alternatives]
    trans3_lines = [alt[:] + [''] * (cols - len(alt)) for alt in trans3_tokens_alternatives]
    
    # ═══════════════════════════════════════════════════════════════════
    # NEU: "TETRIS-KOLLABIEREN" - ALLE Übersetzungszeilen gemeinsam kollabieren
    # ═══════════════════════════════════════════════════════════════════
    # ZWECK: Tokens aus ALLEN Übersetzungszeilen (DE-Alternativen, EN, trans3)
    #        sollen nach oben rutschen in leere Spalten
    #
    # KRITISCH: Wir müssen DE + EN + trans3 als EINE GRUPPE behandeln!
    #
    # BEISPIEL (3-sprachiger Text mit / Alternativen):
    #   VORHER:
    #     de_lines[0] = ["vieles", "", "er", ...]        ← Lücke Spalte 1
    #     de_lines[1] = ["ERGÄNZUNG", "", "", ...]       ← Lücke Spalte 1  
    #     en_lines[0] = ["many|things", "but", "", ...]  ← Hat "but" in Spalte 1!
    #
    #   NACHHER:
    #     de_lines[0] = ["vieles", "but", "er", ...]        ← "but" hochgezogen!
    #     de_lines[1] = ["ERGÄNZUNG", "", "", ...]          ← Lücke bleibt
    #     en_lines[0] = ["many|things", "", "", ...]        ← "but" entfernt
    #
    # ALGORITHMUS:
    #   1. Kombiniere ALLE Übersetzungszeilen in eine Liste (de_lines + en_lines + trans3_lines)
    #   2. Für jede Spalte k:
    #        Für jede Zeile row_idx (von 0 bis N-2):
    #          Wenn all_lines[row_idx][k] leer:
    #            Suche in all_lines[row_idx+1...N] nach nicht-leerem Token
    #            Ziehe Token hoch, entferne von Quelle
    #   3. Trenne wieder in de_lines, en_lines, trans3_lines
    
    # Kombiniere ALLE Übersetzungszeilen
    all_translation_lines = de_lines + en_lines + trans3_lines
    
    if len(all_translation_lines) >= 2:
        num_rows = len(all_translation_lines)
        num_cols = len(all_translation_lines[0]) if all_translation_lines else 0
        
        # Für jede Spalte
        for k in range(num_cols):
            # Für jede Zeile (von oben nach unten, außer letzte)
            for row_idx in range(num_rows - 1):
                # Prüfe ob diese Zeile in Spalte k leer ist
                if not all_translation_lines[row_idx][k]:
                    # Suche nach nicht-leerem Token in tieferen Zeilen
                    for source_row in range(row_idx + 1, num_rows):
                        source_token = all_translation_lines[source_row][k]
                        if source_token:
                            # GEFUNDEN! Ziehe Token hoch (TETRIS!)
                            all_translation_lines[row_idx][k] = source_token
                            all_translation_lines[source_row][k] = ''  # Entferne von Quelle
                            break  # Nur EINEN Token hochziehen pro Lücke
        
        # Trenne wieder in de_lines, en_lines, trans3_lines
        num_de = len(de_lines)
        num_en = len(en_lines)
        num_trans3 = len(trans3_lines)
        
        de_lines = all_translation_lines[0:num_de]
        en_lines = all_translation_lines[num_de:num_de + num_en]
        trans3_lines = all_translation_lines[num_de + num_en:num_de + num_en + num_trans3]
    
    # Für Kompatibilität: Verwende erste Alternative als de/en/trans3
    # (wird für Breitenberechnung benötigt)
    de = de_lines[0] if de_lines else []
    en = en_lines[0] if en_lines else []
    trans3 = trans3_lines[0] if trans3_lines else []

    # ═══════════════════════════════════════════════════════════════════
    # Spaltenbreiten berechnen - KRITISCH: Bei NO_TAGS muss Breite OHNE Tags berechnet werden!
    # ═══════════════════════════════════════════════════════════════════
    # BEDEUTUNGS-STRAUß: Berechne maximale Breite über ALLE Alternativen
    # ═══════════════════════════════════════════════════════════════════
    # WARUM?
    #   - Verschiedene Alternativen können unterschiedlich breite Tokens haben
    #   - Beispiel: Alt 0 = "sage,", Alt 1 = "verrate," → Spalte braucht Breite für "verrate,"
    #   - Alle Alternativen nutzen dann diese maximale Breite
    #   - Resultat: Token bleiben vertikal ausgerichtet über alle Alternativen hinweg
    #
    # FUNKTIONSWEISE:
    #   1. Iteriere über jede Spalte (0 bis cols-1)
    #   2. Für jede Spalte: Finde längstes Token über ALLE Alternativen
    #   3. Berechne Breite für dieses längste Token
    #   4. Diese Breite gilt für die Spalte in ALLEN Alternativen
    
    widths = []
    for k in range(cols):
        gr_token = gr[k] if (k < len(gr) and gr[k]) else ''
        
        # Berechne maximale Breite über ALLE Alternativen für diese Spalte
        de_token = ''
        for de_line in de_lines:
            if k < len(de_line) and de_line[k]:
                if len(de_line[k]) > len(de_token):
                    de_token = de_line[k]
        
        en_token = ''
        for en_line in en_lines:
            if k < len(en_line) and en_line[k]:
                if len(en_line[k]) > len(en_token):
                    en_token = en_line[k]
        
        trans3_token = ''
        for trans3_line in trans3_lines:
            if k < len(trans3_line) and trans3_line[k]:
                if len(trans3_line[k]) > len(trans3_token):
                    trans3_token = trans3_line[k]
        
        if gr_token:
            # KRITISCH: Prüfe ob dieses Token Tags HAT (die bei NO_TAGS entfernt werden)
            # Bei NO_TAGS muss die Breite OHNE Tags berechnet werden!
            tags_in_token = RE_TAG.findall(gr_token)
            
            # ENTSCHEIDUNG: Basierend auf tag_mode UND Vorhandensein von Tags
            if tag_mode == "NO_TAGS" and tags_in_token:
                # FALL 1: NoTag-PDF UND Token HAT Tags → Tags werden entfernt → Breite ohne Tags!
                # Entferne ALLE Tags und Markup-Zeichen für Breitenberechnung
                core_text = RE_TAG_STRIP.sub('', gr_token).strip()
                for color_char in ['#', '+', '-', '§', '$', '~', '*']:
                    core_text = core_text.replace(color_char, '')
                core_text = core_text.replace('|', '')  # Pipes auch entfernen
                
                # Berechne Breite ohne Tags
                w_gr = visible_measure_token(core_text, font=token_gr_style.fontName, 
                                             size=token_gr_style.fontSize, cfg=eff_cfg, 
                                             is_greek_row=True)
                # WICHTIG: Verwende GLEICHEN Puffer wie Tag-PDFs (0.8pt) für konsistente Abstände!
                # Dies macht NoTag-PDFs lesbar wie Tag-PDFs (mit versteckten Tags)
                w_gr += max(token_gr_style.fontSize * 0.03, 0.8)  # REDUZIERT von 0.13/1.6 auf 0.03/0.8 (wie Tag-PDFs!)
                
            elif tags_in_token and tag_mode == "TAGS":
                # FALL 2: Tag-PDF UND Token HAT Tags → Tags werden angezeigt → normale Breite
                w_gr = measure_token_width_with_visibility_poesie(
                    gr_token, 
                    font=token_gr_style.fontName, 
                    size=token_gr_style.fontSize, 
                    cfg=eff_cfg,
                    is_greek_row=True,
                    tag_config=tag_config,
                    tag_mode=tag_mode  # WICHTIG: tag_mode übergeben für korrekte Puffer-Berechnung!
                )
                
            else:
                # FALL 3: Token HAT KEINE Tags (in beiden PDF-Typen möglich!)
                # Tag-PDF: Wörter ohne Tags (z.B. HideTags) → erhöhter Puffer wie NoTag-PDFs!
                # NoTag-PDF: Normale Wörter ohne Tags → erhöhter Puffer (bessere Lesbarkeit!)
                w_gr = visible_measure_token(gr_token, font=token_gr_style.fontName, 
                                             size=token_gr_style.fontSize, cfg=eff_cfg, 
                                             is_greek_row=True)
                
                # NEUE LOGIK: BEIDE PDF-Typen bekommen gleichen Puffer für Wörter ohne Tags!
                # NoTag-PDFs sind jetzt das Vorbild für Wörter ohne Tags!
                w_gr += max(token_gr_style.fontSize * 0.03, 0.8)  # ERHÖHT von 0.3pt auf 0.8pt für Tag-PDFs!
            
            # ═══════════════════════════════════════════════════════════════════
            # FIX: Extra-Padding bei Versmaß für Tokens mit Bars
            # ═══════════════════════════════════════════════════════════════════
            # PROBLEM: Bei Versmaß sind | unsichtbar (weiß), nehmen aber Platz ein
            #          Tokens mit | kleben an benachbarten Tokens (z.B. |ἀλλοδα|ποῖσι)
            # URSACHE: visible_measure_token() addiert nur leading/trailing | zur Breite
            #          Aber visuell sind ALLE | unsichtbar → kein sichtbarer Abstand
            # LÖSUNG: Bei Versmaß: Füge extra Padding für JEDEN Token mit ≥1 Bar hinzu
            #         Mehr Bars → mehr Padding (kompensiert unsichtbare Bars)
            # 
            # BEISPIELE:
            # - |ἀλλοδα|ποῖσι (bar_count=2) → Wort "eingeklammert"
            # - Πειρεσι|ὰς (bar_count=1) → Bar in der Mitte
            # - ὄρε|ος (bar_count=1) → Bar in der Mitte
            # 
            # Bei 2-Wort-Versen (z.B. "Πειρεσι|ὰς ὄρε|ος") kommen die Wörter
            # sich sehr nahe, weil beide Tokens je 1 Bar haben und diese
            # unsichtbar sind. Lösung: Auch bei bar_count=1 Extra-Padding!
            if meter_on:
                bar_count = gr_token.count('|')
                if bar_count >= 1:  # GEÄNDERT von ≥2 zu ≥1
                    # Berechne Bar-Breite für diesen Font/Size
                    bar_width = _sw('|', token_gr_style.fontName, token_gr_style.fontSize)
                    # Füge proportionales Extra-Padding hinzu
                    # Faktor 0.8: 80% der Bar-Breite pro Bar als visueller Abstand
                    w_gr += bar_count * bar_width * 0.8  # ERHÖHT von 0.6 auf 0.8
        else:
            w_gr = 0.0
        
        # Breite für deutsches Token
        if hide_pipes:
            de_text = de_token.replace('|', ' ') if de_token else ''
            en_text = en_token.replace('|', ' ') if en_token else ''
            trans3_text = trans3_token.replace('|', ' ') if trans3_token else ''  # NEU
            de_pipe_count = de_token.count('|') if de_token else 0
            en_pipe_count = en_token.count('|') if en_token else 0
            trans3_pipe_count = trans3_token.count('|') if trans3_token else 0  # NEU
            space_vs_pipe_diff = token_de_style.fontSize * 0.25
            de_pipe_extra = de_pipe_count * space_vs_pipe_diff
            en_pipe_extra = en_pipe_count * space_vs_pipe_diff
            trans3_pipe_extra = trans3_pipe_count * space_vs_pipe_diff  # NEU
        else:
            de_text = de_token
            en_text = en_token
            trans3_text = trans3_token  # NEU
            de_pipe_extra = 0.0
            en_pipe_extra = 0.0
            trans3_pipe_extra = 0.0  # NEU
        
        w_de = visible_measure_token(de_text, font=token_de_style.fontName, 
                                     size=token_de_style.fontSize, cfg=eff_cfg, 
                                     is_greek_row=False) if de_text else 0.0
        w_en = visible_measure_token(en_text, font=token_de_style.fontName, 
                                     size=token_de_style.fontSize, cfg=eff_cfg, 
                                     is_greek_row=False) if en_text else 0.0
        w_trans3 = visible_measure_token(trans3_text, font=token_de_style.fontName,  # NEU
                                     size=token_de_style.fontSize, cfg=eff_cfg, 
                                     is_greek_row=False) if trans3_text else 0.0
        
        w_de += de_pipe_extra
        w_en += en_pipe_extra
        w_trans3 += trans3_pipe_extra  # NEU
        
        widths.append(max(w_gr, w_de, w_en, w_trans3))  # NEU: Include trans3

    # JETZT kommt der Rest der Funktion (Layout-Berechnung, Tabellen-Erstellung, etc.)
    # Die restlichen 800+ Zeilen der Funktion bleiben UNVERÄNDERT...
    
    # Layout-Spalten berechnen
    num_w = max(6.0*MM, _sw('[999]', num_style.fontName, num_style.fontSize) + 2.0)
    num_gap = NUM_GAP_MM * MM
    
    # KRITISCHER FIX: Bei gestaffelten Zeilen (b/c/d) steht der Sprecher bereits in der num-Spalte!
    # WICHTIG: Gestaffelte Zeilen (18a, 18b) haben AUCH eine Sprecher-Spalte!
    # Die Spalte ist nur LEER/UNSICHTBAR, aber sie nimmt Platz ein!
    # Der Unterschied: Bei gestaffelten Zeilen wird der Sprecher NICHT angezeigt,
    # aber die Spalten-Breite bleibt gleich (reserve_speaker_col erzwingt das).
    is_staggered = _is_staggered_label(line_label) if line_label else False
    
    # Sprecher-Spalten-Breite: IMMER reservieren wenn reserve_speaker_col=True
    # (auch bei gestaffelten Zeilen - die Spalte ist nur unsichtbar!)
    sp_w = max(global_speaker_width_pt, SPEAKER_COL_MIN_MM * MM) if (reserve_speaker_col or speaker) else 0.0
    
    sp_gap = SPEAKER_GAP_MM * MM if sp_w > 0 else 0.0
    indent_w = indent_pt
    avail_tokens_w = doc_width_pt - (num_w + num_gap + sp_w + sp_gap + indent_w)

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
        slice_trans3 = trans3[i:j]  # NEU: Für 4-zeilige Blöcke

        # Zellen
        def _p(text, st): return Paragraph(text, st)
        def _end_has_bar_local(s: str) -> bool: return _end_has_bar(s)
        def _has_leading_bar_local(s: str) -> bool: return _has_leading_bar(s)

        def cell(is_gr, tok, idx_in_slice, global_idx=None):
            if not tok:
                return Paragraph('', token_gr_style if is_gr else token_de_style)

            if is_gr and meter_on:
                # WICHTIG: Entferne Tags basierend auf tag_mode und token_meta, BEVOR ToplineTokenFlowable verwendet wird
                # Dies stellt sicher, dass Farbsymbole erhalten bleiben, auch wenn Tags entfernt werden
                tok_cleaned = _strip_tags_from_token(tok, block=block, tok_idx=global_idx, tag_mode=tag_mode)
                
                had_lead = _has_leading_bar_local(tok_cleaned)
                endbars_match = re.search(r'\|+\s*$', RE_TAG_STRIP.sub('', tok_cleaned))
                endbars = len(endbars_match.group(0).strip()) if endbars_match else 0
                br_to_next = False
                next_has_lead = False
                
                # Kontext-Übergabe für Schieberegler
                next_tok_starts_with_bar = False  # FIX: Variable muss korrekt heißen!
                if idx_in_slice is not None and idx_in_slice < (len(slice_gr) - 1):
                    nxt = slice_gr[idx_in_slice + 1]
                    # WICHTIG: Auch für next_token die Tags entfernen
                    nxt_cleaned = _strip_tags_from_token(nxt, block=block, tok_idx=global_idx+1 if global_idx is not None else None, tag_mode=tag_mode)
                    br_to_next = same_foot(tok_cleaned, nxt_cleaned)
                    next_has_lead = _has_leading_bar_local(nxt_cleaned)
                    next_tok_starts_with_bar = next_has_lead

                return ToplineTokenFlowable(
                    tok_cleaned, token_gr_style, eff_cfg,
                    gr_bold=(gr_bold if is_gr else False),
                    had_leading_bar=had_lead,
                    end_bar_count=endbars,
                    bridge_to_next=br_to_next,
                    next_has_leading_bar=next_has_lead,
                    is_first_in_line=(idx_in_slice == 0),
                    next_token_starts_with_bar=next_tok_starts_with_bar  # FIX: Typo korrigiert
                )

            # NICHT-Versmaß: Bars entfernen + pro Spaltenbreite weich zentrieren (Epos-Logik)
            # WICHTIG: Entferne Tags basierend auf tag_mode und token_meta
            tok_cleaned = _strip_tags_from_token(tok, block=block, tok_idx=global_idx, tag_mode=tag_mode)
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

        # ═══════════════════════════════════════════════════════════════════
        # HILFSFUNKTION: Farbverarbeitung für Übersetzungs-Tokens
        # ═══════════════════════════════════════════════════════════════════
        # ZWECK: Entscheide ob manuelles oder automatisches Farbsymbol verwendet wird
        #
        # REGEL: Manuell gesetzte Symbole (#+-§$) haben VORRANG vor token_meta!
        #
        # WARUM?
        #   - Nach Tetris-Kollabieren kann Token eigenes Symbol + token_meta haben
        #   - Beispiel: Token "-der" + token_meta "#" → KONFLIKT!
        #   - Lösung: Wenn Token manuelles Symbol hat, ignoriere token_meta
        #   - Sonst: Füge token_meta-Symbol hinzu (automatische Färbung)
        #
        # RETURN: Token mit korrekt gesetztem Farbsymbol (genau EINS!)
        
        def apply_color_symbol(token_text: str, token_index: int, block: dict) -> str:
            """
            Wendet Farbsymbol auf Token an: Manuell hat Vorrang vor automatisch.
            
            Args:
                token_text: Der Token-Text (möglicherweise mit manuellem Symbol)
                token_index: Index des Tokens in der Zeile (für token_meta Lookup)
                block: Der Block-Dict (enthält token_meta)
            
            Returns:
                Token mit genau EINEM Farbsymbol (oder ohne wenn keine Färbung)
            """
            # Prüfe ob Token MANUELLES Symbol hat (#+-§$~*)
            has_manual_color = any(sym in token_text for sym in ['#', '+', '-', '§', '$', '~', '*'])
            
            if has_manual_color:
                # MANUELL gefärbt → nutze Token as-is (Symbol bereits vorhanden)
                return token_text
            else:
                # NICHT manuell gefärbt → prüfe token_meta für automatische Färbung
                token_meta = block.get('token_meta', [])
                if token_index < len(token_meta):
                    meta = token_meta[token_index]
                    color_symbol = meta.get('color_symbol')
                    if color_symbol:
                        # Füge automatisches Symbol hinzu
                        return color_symbol + token_text
                
                # Kein Symbol (weder manuell noch automatisch)
                return token_text

        gr_cells = [cell(True,  t, k, global_idx=i+k) for k, t in enumerate(slice_gr)]

        # DE-Zellen mit gleicher Zentrierung wie im Epos
        # NEU: Pipe-Ersetzung für hide_pipes
        def process_translation_token_poesie(token: str) -> str:
            """Ersetzt | durch Leerzeichen in Übersetzungen, wenn hide_pipes aktiviert ist"""
            if not token or not hide_pipes:
                return token
            return token.replace('|', ' ')
        
        # Stelle sicher, dass hide_trans_flags existiert (Fallback für alte Blocks ohne Flags)
        if hide_trans_flags is None:
            hide_trans_flags = [False] * len(slice_gr)
        
        de_cells = []
        for idx, t in enumerate(slice_de):
            # WICHTIG: Verwende hide_trans_flags (wurde VOR Preprocessing extrahiert!)
            should_hide_trans = hide_trans_flags[idx] if idx < len(hide_trans_flags) else False
            
            if not t or should_hide_trans:
                # Leeres Token ODER HideTrans → keine Übersetzung anzeigen
                # WICHTIG: Paragraph muss trotzdem die korrekte Breite haben (aus slice_w)!
                de_cells.append(Paragraph('', token_de_style))
                # KEIN continue! Wir müssen slice_w[idx] korrekt zuordnen
            else:
                # NEU: Pipes durch Leerzeichen ersetzen, wenn hide_pipes aktiviert ist
                t_processed = process_translation_token_poesie(t)
                
                # Wende Farbsymbol an (manuell hat Vorrang!)
                global_idx = i + idx
                t_with_color = apply_color_symbol(t_processed, global_idx, block)
                
                # format_token_markup entfernt das Symbol und gibt farbigen HTML zurück
                de_html = format_token_markup(t_with_color, is_greek_row=False, gr_bold=False, remove_bars_instead=True)
                
                # KRITISCH: Breite OHNE Farbsymbol messen! (Symbol wurde von format_token_markup entfernt)
                # Verwende t_processed (OHNE Symbol) für Breitenmessung!
                de_meas  = visible_measure_token(t_processed, font=token_de_style.fontName, size=token_de_style.fontSize, cfg=eff_cfg, is_greek_row=False)
                de_width = slice_w[idx]
                de_html_centered = center_word_in_width(de_html, de_meas, de_width, token_de_style.fontName, token_de_style.fontSize)
                de_cells.append(Paragraph(de_html_centered, token_de_style))

        # EN-Zellen (für 3-sprachige Texte)
        en_cells = []
        has_en = any(slice_en)
        if has_en:
            for idx, t in enumerate(slice_en):
                # WICHTIG: Verwende hide_trans_flags (wurde VOR Preprocessing extrahiert!)
                should_hide_trans = hide_trans_flags[idx] if idx < len(hide_trans_flags) else False
                
                if not t or should_hide_trans:
                    # Leeres Token ODER HideTrans → keine Übersetzung anzeigen
                    # WICHTIG: Paragraph muss trotzdem die korrekte Breite haben (aus slice_w)!
                    en_cells.append(Paragraph('', token_de_style))
                    # KEIN continue! Wir müssen slice_w[idx] korrekt zuordnen
                else:
                    # NEU: Pipes durch Leerzeichen ersetzen, wenn hide_pipes aktiviert ist
                    t_processed = process_translation_token_poesie(t)
                    
                    # Wende Farbsymbol an (manuell hat Vorrang!)
                    global_idx = i + idx
                    t_with_color = apply_color_symbol(t_processed, global_idx, block)
                    
                    # format_token_markup entfernt das Symbol und gibt farbigen HTML zurück
                    en_html = format_token_markup(t_with_color, is_greek_row=False, gr_bold=False, remove_bars_instead=True)
                    
                    # KRITISCH: Breite OHNE Farbsymbol messen! (Symbol wurde von format_token_markup entfernt)
                    en_meas  = visible_measure_token(t_processed, font=token_de_style.fontName, size=token_de_style.fontSize, cfg=eff_cfg, is_greek_row=False)
                    en_width = slice_w[idx]
                    en_html_centered = center_word_in_width(en_html, en_meas, en_width, token_de_style.fontName, token_de_style.fontSize)
                    en_cells.append(Paragraph(en_html_centered, token_de_style))

        # NEU: TRANS3-Zellen (für 4-zeilige Blöcke / dritte Übersetzung)
        trans3_cells = []
        has_trans3 = any(slice_trans3)
        if has_trans3:
            for idx, t in enumerate(slice_trans3):
                # WICHTIG: Verwende hide_trans_flags (wurde VOR Preprocessing extrahiert!)
                should_hide_trans = hide_trans_flags[idx] if idx < len(hide_trans_flags) else False
                
                if not t or should_hide_trans:
                    # Leeres Token ODER HideTrans → keine Übersetzung anzeigen
                    trans3_cells.append(Paragraph('', token_de_style))
                else:
                    # NEU: Pipes durch Leerzeichen ersetzen, wenn hide_pipes aktiviert ist
                    t_processed = process_translation_token_poesie(t)
                    
                    # Wende Farbsymbol an (manuell hat Vorrang!)
                    global_idx = i + idx
                    t_with_color = apply_color_symbol(t_processed, global_idx, block)
                    
                    # format_token_markup entfernt das Symbol und gibt farbigen HTML zurück
                    trans3_html = format_token_markup(t_with_color, is_greek_row=False, gr_bold=False, remove_bars_instead=True)
                    
                    # Breite OHNE Farbsymbol messen
                    trans3_meas = visible_measure_token(t_processed, font=token_de_style.fontName, size=token_de_style.fontSize, cfg=eff_cfg, is_greek_row=False)
                    trans3_width = slice_w[idx]
                    trans3_html_centered = center_word_in_width(trans3_html, trans3_meas, trans3_width, token_de_style.fontName, token_de_style.fontSize)
                    trans3_cells.append(Paragraph(trans3_html_centered, token_de_style))

        # Linke Spalten: NUM → Gap → SPRECHER → Gap → INDENT → Tokens
        # WICHTIG: Zeilennummer in <font> Tag wrappen, damit "-" nicht als Farbmarker interpretiert wird
        if first_slice and line_label:
            num_text = f'<font color="black">[{xml_escape(line_label)}]</font>'
        else:
            num_text = '\u00A0'
        num_para_gr = _p(num_text, num_style)
        num_para_de = _p('\u00A0', num_style)
        num_para_en = _p('\u00A0', num_style) if has_en else None
        num_para_trans3 = _p('\u00A0', num_style) if has_trans3 else None  # NEU
        num_gap_gr  = _p('', token_gr_style); num_gap_de = _p('', token_de_style)
        num_gap_en  = _p('', token_de_style) if has_en else None
        num_gap_trans3 = _p('', token_de_style) if has_trans3 else None  # NEU

        # KRITISCHER FIX: Bei gestaffelten Zeilen sp_w=0, aber Sprecher trotzdem anzeigen!
        # Bedingung: (sp_w>0 OR is_staggered) AND speaker
        sp_para_gr  = _p(xml_escape(f"[{speaker}]:"), style_speaker) if (first_slice and (sp_w>0 or is_staggered) and speaker) else _p('', style_speaker)
        sp_para_de  = _p('', style_speaker)
        sp_para_en  = _p('', style_speaker) if has_en else None
        sp_para_trans3 = _p('', style_speaker) if has_trans3 else None  # NEU
        sp_gap_gr   = _p('', token_gr_style); sp_gap_de = _p('', token_de_style)
        sp_gap_en   = _p('', token_de_style) if has_en else None
        sp_gap_trans3 = _p('', token_de_style) if has_trans3 else None  # NEU

        indent_gr   = _p('', token_gr_style)
        indent_de   = _p('', token_de_style)
        indent_en   = _p('', token_de_style) if has_en else None
        indent_trans3 = _p('', token_de_style) if has_trans3 else None  # NEU

        row_gr = [num_para_gr, num_gap_gr, sp_para_gr, sp_gap_gr, indent_gr] + gr_cells
        row_de = [num_para_de, num_gap_de, sp_para_de, sp_gap_de, indent_de] + de_cells
        col_w  = [num_w, num_gap, sp_w,        sp_gap,   indent_w] + slice_w

        # KRITISCHER FIX: Prüfe ob TATSÄCHLICH sichtbare Übersetzungen vorhanden sind
        # NICHT nur ob de/en-Listen existieren, sondern ob irgendein Token NICHT HideTrans hat!
        # Wenn ALLE Tokens (HideTrans) haben → de_cells sind alle leer → Zeile soll kollabieren!
        has_visible_de = any(de[i] and not (hide_trans_flags[i] if i < len(hide_trans_flags) else False) for i in range(len(de)))
        has_visible_en = has_en and any(en[i] and not (hide_trans_flags[i] if i < len(hide_trans_flags) else False) for i in range(len(en)))
        has_visible_trans3 = has_trans3 and any(trans3[i] and not (hide_trans_flags[i] if i < len(hide_trans_flags) else False) for i in range(len(trans3)))  # NEU

        # NEU: Für 4-zeilige Blöcke: dritte Übersetzung hinzufügen
        # Build table rows dynamically based on which translations are visible
        table_rows = [row_gr]  # Ancient line always included
        
        if has_visible_de:
            table_rows.append(row_de)
        
        # ═══════════════════════════════════════════════════════════════════
        # NEU: BEDEUTUNGS-STRAUß - Zusätzliche Übersetzungsalternativen
        # ═══════════════════════════════════════════════════════════════════
        # ZWECK: Füge zusätzliche DE-Zeilen hinzu für Alternativen 1, 2, 3, ...
        #        Diese werden ENG unter der ersten DE-Zeile platziert (wie EN unter DE)
        #
        # WARUM HIER?
        #   - Nach row_de (erste DE-Zeile ist bereits gebaut)
        #   - Vor row_en (EN-Zeile kommt nach ALLEN DE-Alternativen)
        #   - Innerhalb der Slice-Schleife (i:j) → Zeilenlänge automatisch korrekt
        #
        # FUNKTIONSWEISE:
        #   1. Prüfe ob mehr als eine Alternative (len(de_lines) > 1)
        #   2. Iteriere über Alternativen 1, 2, 3... (Index 0 ist bereits als row_de gebaut)
        #   3. Für jede Alternative: Baue Zellen GENAU WIE für row_de
        #   4. Wichtig: KEINE Zeilennummer, KEIN Sprecher (leere Paragraphs)
        #   5. Füge Zeile zu table_rows hinzu
        #
        # RESULTAT:
        #   table_rows = [row_gr, row_de_alt0, row_de_alt1, row_de_alt2, row_en?, row_trans3?]
        #   Alle DE-Alternativen stehen zwischen GR und EN
        #   Padding-Logik (weiter unten) macht sie "gekoppelt"
        
        if len(de_lines) > 1:
            # Es gibt Alternativen! Rendere sie alle
            for alt_idx in range(1, len(de_lines)):
                de_alt = de_lines[alt_idx]
                slice_de_alt = de_alt[i:j]
                
                # ═══════════════════════════════════════════════════════════════
                # Baue Zellen für diese Alternative - GENAU WIE für row_de!
                # ═══════════════════════════════════════════════════════════════
                # WICHTIG: Gleiche Logik wie bei de_cells (Zeile 2493-2536)
                #   - HideTrans-Prüfung: Gleich
                #   - Pipe-Ersetzung: Gleich (hide_pipes wird angewendet)
                #   - Farbsymbole: Gleich (aus token_meta)
                #   - Zentrierung: Gleich (center_word_in_width)
                #
                # WARUM DUPLIZIERUNG?
                #   - Code muss identisch sein zu de_cells für Konsistenz
                #   - Könnte in Funktion extrahiert werden, aber dann schlechter lesbar
                #   - Duplizierung ist akzeptabel für diese ~20 Zeilen
                
                de_alt_cells = []
                for idx, t in enumerate(slice_de_alt):
                    should_hide_trans = hide_trans_flags[idx] if idx < len(hide_trans_flags) else False
                    
                    if not t or should_hide_trans:
                        de_alt_cells.append(Paragraph('', token_de_style))
                    else:
                        t_processed = process_translation_token_poesie(t)
                        
                        # Wende Farbsymbol an (manuell hat Vorrang!)
                        global_idx = i + idx
                        t_with_color = apply_color_symbol(t_processed, global_idx, block)
                        
                        de_html = format_token_markup(t_with_color, is_greek_row=False, gr_bold=False, remove_bars_instead=True)
                        de_meas = visible_measure_token(t_processed, font=token_de_style.fontName, size=token_de_style.fontSize, cfg=eff_cfg, is_greek_row=False)
                        de_width = slice_w[idx]
                        de_html_centered = center_word_in_width(de_html, de_meas, de_width, token_de_style.fontName, token_de_style.fontSize)
                        de_alt_cells.append(Paragraph(de_html_centered, token_de_style))
                
                # Baue Zeile für diese Alternative (ohne Zeilennummer/Sprecher)
                num_para_de_alt = _p('\u00A0', num_style)
                num_gap_de_alt = _p('', token_de_style)
                sp_para_de_alt = _p('', style_speaker)
                sp_gap_de_alt = _p('', token_de_style)
                indent_de_alt = _p('', token_de_style)
                
                row_de_alt = [num_para_de_alt, num_gap_de_alt, sp_para_de_alt, sp_gap_de_alt, indent_de_alt] + de_alt_cells
                table_rows.append(row_de_alt)
        
        if has_visible_en:
            row_en = [num_para_en, num_gap_en, sp_para_en, sp_gap_en, indent_en] + en_cells
            table_rows.append(row_en)
        
        if has_visible_trans3:
            row_trans3 = [num_para_trans3, num_gap_trans3, sp_para_trans3, sp_gap_trans3, indent_trans3] + trans3_cells
            table_rows.append(row_trans3)
        
        # Create table with all visible rows
        tbl = Table(table_rows, colWidths=col_w, hAlign='LEFT')

        # NEU: Prüfe, ob diese Zeile von einem Kommentar referenziert wird
        # WICHTIG: Wenn comment_token_mask vorhanden ist und nicht leer, unterdrücke Hintergrundfarbe
        comment_color = None
        comment_token_mask = block.get('comment_token_mask', []) if block else []
        has_comment_mask = comment_token_mask and any(comment_token_mask)
        
        # DEAKTIVIERT: Farbliche Hinterlegung für Kommentar-referenzierte Zeilen
        # (Code bleibt erhalten für spätere Reaktivierung)
        # if base_line_num is not None and line_comment_colors and base_line_num in line_comment_colors and not has_comment_mask:
        #     comment_color = line_comment_colors[base_line_num]

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
            # NEU: Hinterlegung DEAKTIVIERT (Code bleibt erhalten)
            # if comment_color:
            #     bg_color = colors.Color(comment_color[0], comment_color[1], comment_color[2], alpha=0.35)
            #     style_list.append(('BACKGROUND', (0,0), (-1,-1), bg_color))
            # Nur Padding für Sprecher-Spalte hinzufügen, wenn sie existiert (sp_w > 0)
            if sp_w > 0:
                style_list.append(('RIGHTPADDING',  (2,0), (2,-1), 2.0))
            # Nur Padding zwischen Zeilen hinzufügen, wenn Übersetzungen vorhanden sind
            if has_visible_de or has_visible_en:
                style_list.append(('BOTTOMPADDING', (0,0), (-1,0), gap_ancient_to_modern/2.0))
                style_list.append(('TOPPADDING',    (0,1), (-1,1), gap_ancient_to_modern/2.0))
            
            # ═══════════════════════════════════════════════════════════════════
            # NEU: BEDEUTUNGS-STRAUß - Padding zwischen Übersetzungsalternativen (METER_ON)
            # ═══════════════════════════════════════════════════════════════════
            # ZWECK: Alternativen sollen ENG untereinander stehen (wie EN unter DE in 3-sprachigen PDFs)
            #        Dies ist das HERZSTÜCK der "gekoppelten Doppel-/Dreifachzeile"!
            #
            # WARUM FUNKTIONIERT DAS?
            #   1. DYNAMISCHE ZEILEN-INDIZES: Berechne Position jeder Alternative in table_rows
            #   2. MINIMALES PADDING: Verwende gap_de_to_en (gleich wie DE→EN, z.B. 0.2-0.7mm)
            #   3. UNTERSCHIED ZU NORMALEM ABSTAND: gap_ancient_to_modern ist VIEL größer (1-2mm)
            #   4. VISUELLER EFFEKT: Alternativen "kleben zusammen", Blöcke sind getrennt
            #
            # ZEILEN-STRUKTUR IN table_rows:
            #   Index 0: row_gr              (Griechische Zeile)
            #   Index 1: row_de (Alternative 0)   ← Erste DE-Zeile
            #   Index 2: row_de_alt1              ← Zweite DE-Zeile (wenn vorhanden)
            #   Index 3: row_de_alt2              ← Dritte DE-Zeile (wenn vorhanden)
            #   Index 4: row_en (wenn vorhanden)  ← EN-Zeile
            #   Index 5: row_trans3 (wenn vorhanden)
            #
            # PADDING-REGELN:
            #   - Zeile 0→1: gap_ancient_to_modern (normal, GR zu erster DE)
            #   - Zeile 1→2: gap_de_to_en (MINIMAL, erste zu zweiter DE-Alternative)
            #   - Zeile 2→3: gap_de_to_en (MINIMAL, zweite zu dritter DE-Alternative)
            #   - Zeile N→EN: gap_de_to_en (MINIMAL, letzte DE-Alternative zu EN)
            #
            # BEISPIEL (3 Alternativen):
            #   table_rows hat Indizes: [0:GR, 1:DE0, 2:DE1, 3:DE2, 4:EN]
            #   num_de_alternatives = 3
            #   Schleife: alt_idx = 1, 2
            #     alt_idx=1: row_idx=2 → Padding zwischen Index 1↔2 (DE0↔DE1)
            #     alt_idx=2: row_idx=3 → Padding zwischen Index 2↔3 (DE1↔DE2)
            #   en_row_idx = 1+3 = 4 → Padding zwischen Index 3↔4 (DE2↔EN)
            
            num_de_alternatives = len(de_lines)
            if num_de_alternatives > 1:
                # Erste DE-Zeile ist an Index 1, weitere Alternativen folgen
                for alt_idx in range(1, num_de_alternatives):
                    row_idx = 1 + alt_idx  # Index der Alternative in table_rows
                    # MINIMALES Padding zwischen DE-Alternativen (wie DE zu EN)
                    style_list.append(('BOTTOMPADDING', (0,row_idx-1), (-1,row_idx-1), gap_de_to_en))
                    style_list.append(('TOPPADDING',    (0,row_idx), (-1,row_idx), gap_de_to_en))
            
            # NEU: Für 3-sprachige Texte: Padding zwischen Zeilen
            # Berechne Index von EN-Zeile (kommt nach allen DE-Alternativen)
            en_row_idx = 1 + num_de_alternatives if has_visible_en else None
            if has_visible_en and en_row_idx:
                # Abstand zwischen letzter DE-Alternative und EN
                style_list.append(('BOTTOMPADDING', (0,en_row_idx-1), (-1,en_row_idx-1), gap_de_to_en))
                style_list.append(('TOPPADDING',    (0,en_row_idx), (-1,en_row_idx), gap_de_to_en))
            
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
            if has_visible_de or has_visible_en:
                style_list.append(('BOTTOMPADDING', (0,0), (-1,0), gap_ancient_to_modern/2.0))
                style_list.append(('TOPPADDING',    (0,1), (-1,1), gap_ancient_to_modern/2.0))
            
            # ═══════════════════════════════════════════════════════════════════
            # NEU: BEDEUTUNGS-STRAUß - Padding zwischen Übersetzungsalternativen
            # Alternativen sollen ENG untereinander stehen (wie EN unter DE)
            # ═══════════════════════════════════════════════════════════════════
            num_de_alternatives = len(de_lines)
            if num_de_alternatives > 1:
                # Erste DE-Zeile ist an Index 1, weitere Alternativen folgen
                for alt_idx in range(1, num_de_alternatives):
                    row_idx = 1 + alt_idx  # Index der Alternative in table_rows
                    # MINIMALES Padding zwischen DE-Alternativen (wie DE zu EN)
                    style_list.append(('BOTTOMPADDING', (0,row_idx-1), (-1,row_idx-1), gap_de_to_en))
                    style_list.append(('TOPPADDING',    (0,row_idx), (-1,row_idx), gap_de_to_en))
            
            # NEU: Für 3-sprachige Texte: Padding zwischen Zeilen
            # Berechne Index von EN-Zeile (kommt nach allen DE-Alternativen)
            en_row_idx = 1 + num_de_alternatives if has_visible_en else None
            if has_visible_en and en_row_idx:
                # Abstand zwischen letzter DE-Alternative und EN
                style_list.append(('BOTTOMPADDING', (0,en_row_idx-1), (-1,en_row_idx-1), gap_de_to_en))
                style_list.append(('TOPPADDING',    (0,en_row_idx), (-1,en_row_idx), gap_de_to_en))
            
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

    # NoTags-Schalter global setzen basierend auf tag_mode (nicht nur Dateiname!)
    global CURRENT_IS_NOTAGS
    CURRENT_IS_NOTAGS = (tag_mode == "NO_TAGS") or pdf_name.lower().endswith("_notags.pdf")
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
            
            # WICHTIG: text_clean MUSS initialisiert werden, bevor es verwendet wird!
            text_clean = content if content else ''
            
            # Fallback: Wenn content leer ist, extrahiere aus original_line
            if not text_clean and original_line:
                # Entferne Zeilennummer-Marker
                text_clean = re.sub(r'^\(\d+-\d+k\)\s*', '', original_line)
                text_clean = re.sub(r'^\(\d+k\)\s*', '', text_clean)
                text_clean = text_clean.strip()
            
            # Wenn text_clean immer noch leer ist, überspringe
            if not text_clean:
                i += 1
                continue
            
            # WICHTIG: Zeilennummer VOR dem Kommentartext anzeigen in [ECKIGEN KLAMMERN]!
            if line_num:
                # Entferne "k" Suffix und verwende eckige Klammern
                line_num_clean = line_num.rstrip('kK')
                text_clean = f"[{line_num_clean}] {text_clean}"
            
            # Sanitize - KEINE Kürzung mehr!
            text_clean = " ".join(text_clean.split())
            # Längere Kommentare sind erlaubt (kein Abschneiden)
            
            # WICHTIG: backColor im ParagraphStyle verhindert Seitenumbrüche!
            # Daher: Verwende Table mit grauem Hintergrund für ALLE Kommentare
            comment_style_simple = ParagraphStyle('CommentSimple', parent=base['Normal'],
                fontName='DejaVu', fontSize=7.5,  # Erhöht von 7 auf 7.5 (+0.5pt)
                leading=9,  # Proportional angepasst (war 8.5)
                alignment=TA_LEFT, 
                leftIndent=0, rightIndent=0,  # Kein Indent im Style (wird in Table gemacht)
                spaceBefore=0, spaceAfter=0,
                textColor=colors.Color(0.25, 0.25, 0.25),
                splitLongWords=True,  # KRITISCH: Erlaube Wortumbrüche
                wordWrap='LTR')  # WICHTIG: Aktiviere Word-Wrapping
            
            # Grau hinterlegte Box: Table mit Hintergrundfarbe
            from reportlab.platypus import Table, TableStyle
            try:
                from Poesie_Code import doc  # Versuche doc zu finden
                available_width = doc.pagesize[0] - doc.leftMargin - doc.rightMargin - 12*MM  # -12MM für Padding
            except:
                available_width = 170*MM - 12*MM  # Fallback mit Padding
            
            # Prüfe ob Kommentar lang ist (>175 Wörter) für Page-Breaking
            word_count = len(text_clean.split())
            
            # KRITISCH: Verwende Table mit grauem Hintergrund für ALLE Kommentare
            # Table kann über Seiten umbrechen, wenn kein KeepTogether verwendet wird!
            p = Paragraph(html.escape(text_clean), comment_style_simple)
            
            # WICHTIG: Kommentar-Box-Breite soll bis zum Ende des Translinear-Texts reichen
            # In Poesie: Verwende pagesize - margins (volle Textbreite)
            try:
                from Poesie_Code import doc
                available_width = doc.pagesize[0] - doc.leftMargin - doc.rightMargin
            except:
                available_width = 170*MM  # Fallback
            
            # Padding: 0.3cm = 3mm oben/unten, 0.6cm = 6mm links/rechts
            comment_table = Table([[p]], colWidths=[available_width])
            comment_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.Color(0.92, 0.92, 0.92)),  # Grauer Hintergrund
                ('LEFTPADDING', (0, 0), (-1, -1), 6*MM),  # 0.6cm links
                ('RIGHTPADDING', (0, 0), (-1, -1), 6*MM),  # 0.6cm rechts
                ('TOPPADDING', (0, 0), (-1, -1), 3*MM),  # 0.3cm oben
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3*MM),  # 0.3cm unten
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ]))
            
            if word_count > 175:
                # Langer Kommentar: Direkt hinzufügen (KEIN KeepTogether!)
                # Table kann über Seiten umbrechen
                elements.append(Spacer(1, 2*MM))
                elements.append(comment_table)
                elements.append(Spacer(1, 2*MM))
            else:
                # Kurzer Kommentar: Mit KeepTogether (bleibt auf einer Seite)
                elements.append(Spacer(1, 2*MM))
                elements.append(KeepTogether([comment_table]))
                elements.append(Spacer(1, 2*MM))
            i += 1
            continue

        # Gleichheitszeichen-Überschriften (wie in Prosa)
        # WICHTIG: Alle aufeinanderfolgenden Überschriften sammeln und mit erster Textzeile koppeln
        # WICHTIG: Überschriften mit "Gedicht" markieren den Beginn eines neuen Gedichts
        # → Kumulative Einrückung zurücksetzen (nur bei "Gedicht"-Überschriften)
        if t in ['h1_eq', 'h2_eq', 'h3_eq', 'section']:
            # Bei Überschriften, die "Gedicht" enthalten, kumulative Breite zurücksetzen
            # Dies verhindert, dass Zeilen aus verschiedenen Gedichten kumulativ eingerückt werden
            heading_text = b.get('text', '').lower()
            if t in ['h1_eq', 'h2_eq', 'h3_eq'] and 'gedicht' in heading_text:
                cum_width_by_base = {}
            
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
                    # ═══════════════════════════════════════════════════════════════════
                    # NEU: BEDEUTUNGS-STRAUß - Prüfe ob es Alternativen gibt (wie im Haupt-Pfad)
                    # ═══════════════════════════════════════════════════════════════════
                    next_de_tokens_alternatives = pair_b.get('de_tokens_alternatives')
                    next_en_tokens_alternatives = pair_b.get('en_tokens_alternatives')
                    next_trans3_tokens_alternatives = pair_b.get('trans3_tokens_alternatives')
                    
                    # Falls KEINE Alternativen vorhanden sind, verwende die normale Struktur
                    if next_de_tokens_alternatives is None:
                        next_de_tokens_alternatives = [pair_b.get('de_tokens', [])]
                    if next_en_tokens_alternatives is None:
                        next_en_tokens_alternatives = [pair_b.get('en_tokens', [])]
                    if next_trans3_tokens_alternatives is None:
                        next_trans3_tokens_alternatives = [pair_b.get('trans3_tokens', [])]
                    
                    next_gr_tokens = pair_b.get('gr_tokens', [])[:]
                    next_speaker = pair_b.get('speaker') or ''
                    next_line_label = pair_b.get('label') or ''
                    next_base_num = pair_b.get('base')

                    next_gr_tokens = propagate_elision_markers(next_gr_tokens)
                    
                    # ═══════════════════════════════════════════════════════════════════
                    # KRITISCH: Sprecher-Breite MUSS VOR Indent-Berechnung erfolgen!
                    # (Siehe ausführliche Dokumentation im WITHOUT-headings Pfad ~Zeile 2810)
                    # ═══════════════════════════════════════════════════════════════════
                    next_current_speaker_width_pt = _speaker_col_width(next_speaker) if next_speaker else 0.0
                    
                    # ═══════════════════════════════════════════════════════════════════
                    # GESTAFFELTE ZEILEN: Indent-Berechnung (siehe ~Zeile 2810)
                    # Formel: indent = cum_width - current_speaker_width
                    # ═══════════════════════════════════════════════════════════════════
                    next_indent_pt = 0.0
                    if next_base_num is not None and next_line_label and _is_staggered_label(next_line_label):
                        cum_width = cum_width_by_base.get(next_base_num, 0.0)
                        next_indent_pt = max(0.0, cum_width - next_current_speaker_width_pt)

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
                    
                    # Sprecher-Breite wurde bereits oben berechnet (für Indent-Berechnung)

                    # ═══════════════════════════════════════════════════════════════════
                    # NEU: Rendere ALLE Alternativen (durch `/` erzeugt) in EINER Tabelle
                    # Übergebe *_tokens_alternatives Listen, nicht einzelne Alternativen!
                    # ═══════════════════════════════════════════════════════════════════
                    next_tables = build_tables_for_pair(
                        next_gr_tokens,  # GR-Zeile nur einmal
                        de_tokens=None,  # Verwende Alternativen!
                        speaker=next_display_speaker,  # Sprecher nur bei erster Alternative!
                        line_label=next_line_label,  # Zeilennummer nur bei erster Alternative!
                        doc_width_pt=frame_w,
                        token_gr_style=token_gr, token_de_style=token_de,
                        num_style=num_style, style_speaker=style_speaker,
                        gr_bold=gr_bold,
                        reserve_speaker_col=reserve_all_speakers,
                        indent_pt=next_indent_pt,
                        global_speaker_width_pt=next_current_speaker_width_pt,
                        meter_on=versmass_display and next_has_versmass,
                        tag_mode=tag_mode,
                        en_tokens=None,  # Verwende Alternativen!
                        trans3_tokens=None,  # Verwende Alternativen!
                        de_tokens_alternatives=next_de_tokens_alternatives,  # NEU!
                        en_tokens_alternatives=next_en_tokens_alternatives,  # NEU!
                        trans3_tokens_alternatives=next_trans3_tokens_alternatives,  # NEU!
                        tag_config=tag_config,
                        base_line_num=next_base_num,
                        line_comment_colors=line_comment_colors,
                        hide_pipes=hide_pipes,
                        block=pair_b,
                        hide_trans_flags=pair_b.get('hide_trans_flags', [])
                    )

                    # Sammle die Zeilen
                    rendered_lines.append(KeepTogether(next_tables))

                    # ═══════════════════════════════════════════════════════════════════
                    # KUMULATIVE BREITEN-SPEICHERUNG (siehe ~Zeile 3040 für Details)
                    # Verwende ERSTE Alternative für Breitenberechnung
                    # ═══════════════════════════════════════════════════════════════════
                    next_de_tokens = next_de_tokens_alternatives[0] if next_de_tokens_alternatives else []
                    
                    if next_base_num is not None and next_line_label:
                        next_token_w = measure_rendered_line_width(
                            next_gr_tokens, next_de_tokens,
                            gr_bold=gr_bold, is_notags=CURRENT_IS_NOTAGS,
                            remove_bars_instead=True,
                            tag_config=tag_config,
                            hide_trans_flags=pair_b.get('hide_trans_flags', [])
                        )
                        
                        next_is_staggered = _is_staggered_label(next_line_label) if next_line_label else False
                        
                        if not next_is_staggered:
                            # BASIS: Sprecher + Text
                            cum_width_by_base[next_base_num] = next_current_speaker_width_pt + next_token_w
                        else:
                            # Gestaffelt: Nur Text addieren
                            cum_width_by_base[next_base_num] = cum_width_by_base.get(next_base_num, 0.0) + next_token_w
                
                # OPTIMIERTE LÖSUNG gegen weiße Flächen:
                # Problem: Große KeepTogether-Blöcke erzwingen zu früh Seitenumbrüche
                # Lösung: Kleinere Blöcke + keepWithNext=True
                
                # NEU: Abstand VOR der ersten Überschrift (nur wenn Text davor existiert!)
                # Dies verhindert, dass Überschriften direkt am vorherigen Text kleben
                if i > 0:  # Nur wenn nicht am Anfang des Dokuments
                    elements.append(Spacer(1, 4*MM))  # 4mm Sicherheitsabstand vor Überschriften
                
                # WICHTIG: Verhindere Orphan Headlines (Überschrift ohne nachfolgenden Text am Seitenende)
                # CondPageBreak prüft, ob genug Platz für Überschrift + mindestens 1 Zeile Text
                # REDUZIERT von 80mm auf 30mm (≈ Überschrift + 2 Zeilen, nicht 15 Zeilen!)
                elements.append(CondPageBreak(30*MM))
                
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
            
            # ═══════════════════════════════════════════════════════════════════════════
            # NEU: BEDEUTUNGS-STRAUß - Prüfe ob es Alternativen gibt (durch `/` erzeugt)
            # ═══════════════════════════════════════════════════════════════════════════
            de_tokens_alternatives = b.get('de_tokens_alternatives')  # Liste von Token-Arrays
            en_tokens_alternatives = b.get('en_tokens_alternatives')  # Liste von Token-Arrays
            trans3_tokens_alternatives = b.get('trans3_tokens_alternatives')  # Liste von Token-Arrays
            
            # Falls KEINE Alternativen vorhanden sind, verwende die normale Struktur
            if de_tokens_alternatives is None:
                de_tokens_alternatives = [b.get('de_tokens', [])]
            if en_tokens_alternatives is None:
                en_tokens_alternatives = [b.get('en_tokens', [])]
            if trans3_tokens_alternatives is None:
                trans3_tokens_alternatives = [b.get('trans3_tokens', [])]
            
            speaker   = b.get('speaker') or ''
            line_label= b.get('label') or ''
            base_num  = b.get('base')  # None oder int

            # >>> NEU: Elisions-Übertragung wie im Epos
            gr_tokens = propagate_elision_markers(gr_tokens)
            # <<<

            # ═══════════════════════════════════════════════════════════════════════════
            # KRITISCH: Sprecher-Breite MUSS VOR Indent-Berechnung erfolgen!
            # ═══════════════════════════════════════════════════════════════════════════
            # Warum? Weil das Indent die Sprecher-Breite abziehen muss (siehe unten)!
            # Dies ist die TATSÄCHLICHE Breite, die im Layout verwendet wird.
            current_speaker_width_pt = _speaker_col_width(speaker) if speaker else 0.0

            # ═══════════════════════════════════════════════════════════════════════════
            # GESTAFFELTE ZEILEN: Indent-Berechnung für "Treppenstufen-Effekt"
            # ═══════════════════════════════════════════════════════════════════════════
            # 
            # PROBLEM: Gestaffelte Zeilen (18b, 18c, 18d) sollen wie eine Treppe aussehen.
            # Jede Zeile soll GENAU dort beginnen, wo die vorherige Zeile endet.
            # 
            # BEISPIEL:
            #   [18]  [Χρεμύλος] ἔρωτος          ← BASIS-Zeile
            #   [18b] [Κα]      ἄρτων            ← Text startet wo "ἔρωτος" endet
            #   [18c] [Χρεμύλος] μουσικῆς        ← Text startet wo "ἄρτων" endet
            #   [18d] [Κα]      τραγημάτων       ← Text startet wo "μουσικῆς" endet
            # 
            # HERAUSFORDERUNG: Jede Zeile hat einen UNTERSCHIEDLICH LANGEN Sprecher!
            #   - Zeile 18:  Sprecher = 58.4pt (lang)
            #   - Zeile 18b: Sprecher = 21.0pt (kurz)
            #   - Zeile 18c: Sprecher = 58.4pt (lang)
            #   - Zeile 18d: Sprecher = 21.0pt (kurz)
            # 
            # LAYOUT-STRUKTUR (wichtig für Verständnis!):
            #   [Nummer] [gap] [Sprecher-Spalte] [gap] [Indent] [Token1] [Token2]...
            #                   ↑ sp_w              ↑ 0   ↑ indent_pt
            # 
            # Die POSITION des Textes ist: Sprecher-Spalte + Indent
            # 
            # KUMULATIVE BREITE speichert: sp_w(BASIS) + Tokens(18) + Tokens(18b) + ...
            # Dies ist die ABSOLUTE Position (von Zeilennummer aus gemessen).
            # 
            # BEISPIEL-RECHNUNG:
            #   Zeile 18:  cum_width[18] = 58.4pt + 42.0pt = 100.5pt
            #   Zeile 18b: Text soll bei 100.5pt starten (wo 18 endet)
            #              ABER: Zeile 18b hat sp_w = 21.0pt (eigene Sprecher-Spalte)
            #              ALSO: indent = 100.5pt - 21.0pt = 79.4pt
            #              → Position = 21.0pt + 79.4pt = 100.5pt ✅ PERFEKT!
            # 
            # WARUM minus current_speaker_width_pt?
            #   Weil cum_width die ABSOLUTE Position ist (von Zeilennummer aus),
            #   aber die Sprecher-Spalte den Text schon nach rechts verschiebt!
            #   
            #   WENN wir nicht abziehen würden:
            #     Position = 21.0pt + 100.5pt = 121.5pt ❌ ZU WEIT RECHTS! (Lücke!)
            #   
            #   RICHTIG mit Abzug:
            #     Position = 21.0pt + (100.5pt - 21.0pt) = 100.5pt ✅ PERFEKT!
            # 
            # WICHTIG: Diese Berechnung funktioniert NUR, weil:
            #   1. Wir current_speaker_width_pt VORHER berechnen (nicht nochmal aufrufen!)
            #   2. Dies ist EXAKT der Wert, der an build_tables_for_pair() übergeben wird
            #   3. build_tables_for_pair() verwendet: sp_w = max(current_speaker_width_pt, MIN)
            #   4. Wir verwenden beim Speichern die GLEICHE Breite (siehe unten ~Zeile 3000)
            # ═══════════════════════════════════════════════════════════════════════════
            indent_pt = 0.0
            if base_num is not None and line_label and _is_staggered_label(line_label):
                cum_width = cum_width_by_base.get(base_num, 0.0)
                indent_pt = max(0.0, cum_width - current_speaker_width_pt)

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
            
            # Sprecher-Breite wurde bereits oben berechnet (für Indent-Berechnung)

            # ═══════════════════════════════════════════════════════════════════════════
            # NEU: Rendere ALLE Alternativen (durch `/` erzeugt) in EINER Tabelle
            # Übergebe *_tokens_alternatives Listen, nicht einzelne Alternativen!
            # ═══════════════════════════════════════════════════════════════════════════
            tables = build_tables_for_pair(
                gr_tokens,  # GR-Zeile nur einmal
                de_tokens=None,  # Verwende Alternativen!
                indent_pt=indent_pt,
                global_speaker_width_pt=current_speaker_width_pt,
                meter_on=(versmass_display and has_versmass),
                tag_mode=tag_mode,
                speaker=display_speaker,
                line_label=line_label,
                doc_width_pt=frame_w,
                token_gr_style=token_gr, token_de_style=token_de,
                num_style=num_style, style_speaker=style_speaker,
                gr_bold=gr_bold,
                reserve_speaker_col=reserve_all_speakers,
                en_tokens=None,  # Verwende Alternativen!
                trans3_tokens=None,  # Verwende Alternativen!
                de_tokens_alternatives=de_tokens_alternatives,  # NEU!
                en_tokens_alternatives=en_tokens_alternatives,  # NEU!
                trans3_tokens_alternatives=trans3_tokens_alternatives,  # NEU!
                tag_config=tag_config,
                base_line_num=base_num,
                line_comment_colors=line_comment_colors,
                hide_pipes=hide_pipes,
                block=b,
                hide_trans_flags=b.get('hide_trans_flags', [])
            )
            # KRITISCH: KeepTogether() verhindert Seitenumbruch zwischen GR und DE!
            # OHNE KeepTogether: GR kann am Seitenende, DE am Seitenanfang landen
            # MIT KeepTogether: Gesamter Block (GR + alle DE-Alternativen) bleibt zusammen
            elements.append(KeepTogether(tables))
            
            # Verwende de_tokens von der ERSTEN Alternative für kumulative Breitenberechnung
            de_tokens = de_tokens_alternatives[0] if de_tokens_alternatives else []
            
            # NEU: Kommentare aus block['comments'] rendern (nach dem pair-Block) - dedupliziert + limitiert
            comments = b.get('comments') or []
            if comments:
                # Prüfe disable_comment_bg Flag (falls verfügbar)
                disable_comment_bg = False
                try:
                    disable_comment_bg = tag_config.get('disable_comment_bg', False) if tag_config else False
                except Exception:
                    pass
                
                MAX_COMMENTS_PER_BLOCK = 10  # Erhöht auf 10
                MAX_COMMENT_WORDS = 175  # Wortgrenze für automatischen Umbruch
                added_keys = set()
                added_count = 0
                truncated = False
                
                for cm in comments:
                    if added_count >= MAX_COMMENTS_PER_BLOCK:
                        truncated = True
                        break
                    
                    # Unterstütze verschiedene Formate: dict mit 'text', 'comment', 'body' oder direkt String
                    if isinstance(cm, dict):
                        txt = cm.get('text') or cm.get('comment') or cm.get('body') or ""
                        key = (cm.get('line_num'), len(txt))
                    else:
                        txt = str(cm) if cm else ""
                        key = ("txt", hash(txt))
                    
                    if not txt or not txt.strip():
                        continue
                    
                    # Deduplizierung: überspringe identische Kommentare
                    if key in added_keys:
                        continue
                    added_keys.add(key)
                    
                    # Optional: Zeige den Bereich in [ECKIGEN KLAMMERN] (z.B. [2-4])
                    rng = cm.get('pair_range') if isinstance(cm, dict) else None
                    if rng:
                        display = f"[{rng[0]}-{rng[1]}] {txt}"
                    elif isinstance(cm, dict) and cm.get('start') and cm.get('end'):
                        display = f"[{cm.get('start')}-{cm.get('end')}] {txt}"
                    else:
                        display = txt.strip()
                    
                    # Sanitize - KEINE Kürzung mehr!
                    text_clean = " ".join(display.split())
                    # Längere Kommentare sind erlaubt (kein Abschneiden)
                    
                    # Kommentar-Style: klein, grau, kursiv, GRAU HINTERLEGT
                    comment_style_simple = ParagraphStyle('CommentSimple', parent=base['Normal'],
                        fontName='DejaVu', fontSize=7.5,  # Erhöht von 7 auf 7.5 (+0.5pt)
                        leading=9,  # Proportional angepasst (war 8.5)
                        alignment=TA_LEFT, 
                        leftIndent=4*MM, rightIndent=4*MM,
                        spaceBefore=2, spaceAfter=2,
                        textColor=colors.Color(0.25, 0.25, 0.25),
                        backColor=colors.Color(0.92, 0.92, 0.92))
                    # Grau hinterlegte Box: Table mit Hintergrundfarbe
                    from reportlab.platypus import Table, TableStyle
                    try:
                        from Poesie_Code import doc  # Versuche doc zu finden
                        available_width = doc.pagesize[0] - doc.leftMargin - doc.rightMargin - 8*MM
                    except:
                        available_width = 170*MM  # Fallback
                    
                    # Prüfe ob Kommentar lang ist (>175 Wörter) für Page-Breaking
                    word_count = len(text_clean.split())
                    
                    comment_table = Table([[Paragraph(html.escape(text_clean), comment_style_simple)]], 
                                         colWidths=[available_width])
                    comment_table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, -1), colors.Color(0.92, 0.92, 0.92)),  # Grauer Hintergrund
                        ('LEFTPADDING', (0, 0), (-1, -1), 4*MM),
                        ('RIGHTPADDING', (0, 0), (-1, -1), 4*MM),
                        ('TOPPADDING', (0, 0), (-1, -1), 3*MM),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 3*MM),
                    ]))
                    
                    # Bei langen Kommentaren (>175 Wörter): Tables brechen automatisch
                            
                    elements.append(Spacer(1, 2*MM))
                    elements.append(comment_table)
                    elements.append(Spacer(1, 2*MM))
                    added_count += 1
                
                # Compact debug log instead of per-comment verbose logging
                if added_count > 0:
                    block_id = b.get("block_index") or b.get("index") or "?"
                    import logging
                    logging.getLogger(__name__).debug(
                        "poesie_pdf: Added %d comment paragraphs for block idx=%s (total_comments=%d, truncated=%s)",
                        added_count, block_id, len(comments), truncated
                    )

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

            # Nach dem Rendern: JEDE Zeile fügt ihre Breite zur kumulative Breite hinzu
            # Logik: 18 → 18b startet bei (Sprecher_von_18 + Text_von_18)
            #        18b → 18c startet bei (Sprecher_von_18 + Text_von_18 + Text_von_18b)
            # WICHTIG: Wir speichern die ABSOLUTE Position, wo der Text endet!
            if base_num is not None and line_label:
                # KRITISCH: Berechne Token-Breite
                this_token_w = measure_rendered_line_width(
                    gr_tokens, de_tokens,
                    gr_bold=gr_bold, is_notags=CURRENT_IS_NOTAGS,
                    remove_bars_instead=True,
                    tag_config=tag_config,
                    hide_trans_flags=b.get('hide_trans_flags', [])  # NEU: HideTrans-Flags für korrekte Breitenberechnung!
                )
                
                # ═══════════════════════════════════════════════════════════════════════════
                # KUMULATIVE BREITEN-SPEICHERUNG: Das Herzstück der Treppenstufen-Logik
                # ═══════════════════════════════════════════════════════════════════════════
                # 
                # ZWEI FÄLLE:
                # 
                # 1) BASIS-ZEILE (z.B. "18"): Setze kumulative Breite = Sprecher + Text
                #    Dies ist die STARTPOSITION für die erste gestaffelte Zeile.
                #    
                #    BEISPIEL:
                #      Zeile 18: [Χρεμύλος] ἔρωτος
                #      speaker_width = 58.4pt, token_width = 42.0pt
                #      cum_width[18] = 58.4 + 42.0 = 100.5pt
                #    
                #    Diese 100.5pt ist die ABSOLUTE Position, wo der Text "ἔρωτος" endet
                #    (gemessen von der Zeilennummer aus).
                # 
                # 2) GESTAFFELTE ZEILE (z.B. "18b"): Addiere NUR Token-Breite
                #    Die Sprecher-Breite wird NICHT addiert, weil jede gestaffelte Zeile
                #    ihren EIGENEN Sprecher hat (mit unterschiedlicher Länge)!
                #    
                #    BEISPIEL:
                #      Zeile 18b: [Κα] ἄρτων
                #      old_cum = 100.5pt (von Zeile 18)
                #      token_width = 40.8pt
                #      cum_width[18] = 100.5 + 40.8 = 141.2pt
                #    
                #    Diese 141.2pt ist die ABSOLUTE Position, wo der Text "ἄρτων" endet.
                #    Die nächste gestaffelte Zeile (18c) startet dann bei 141.2pt.
                # 
                # WARUM funktioniert das?
                #   - Die kumulative Breite speichert die ABSOLUTE Position (vom Nullpunkt)
                #   - Das Indent oben (Zeile ~2820) zieht die aktuelle Sprecher-Breite ab
                #   - Dadurch kompensieren sich die unterschiedlichen Sprecher-Längen
                #   - Ergebnis: Perfekte Treppe, unabhängig von Sprecher-Längen!
                # 
                # WICHTIG: Verwende current_speaker_width_pt (berechnet VOR dem Rendering)!
                #   Dies ist die GLEICHE Breite, die in build_tables_for_pair() verwendet wurde.
                #   Wenn wir hier _speaker_col_width() nochmal aufrufen würden, könnten wir
                #   einen ANDEREN Wert bekommen (z.B. durch SPEAKER_COL_MIN_MM) → BUG!
                # ═══════════════════════════════════════════════════════════════════════════
                
                is_staggered_line = _is_staggered_label(line_label) if line_label else False
                
                if not is_staggered_line:
                    # BASIS-Zeile: Setze kumulative Breite = Sprecher + Text
                    cum_width_by_base[base_num] = current_speaker_width_pt + this_token_w
                else:
                    # Gestaffelte Zeile: Addiere nur Token-Breite (Sprecher ist unterschiedlich!)
                    cum_width_by_base[base_num] = cum_width_by_base.get(base_num, 0.0) + this_token_w

            i += 1; continue

    # PDF erzeugen
    doc.build(elements)
