# ======================= PROSA/PLATON – vereinheitlicht =======================
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from pathlib import Path
from shared.fonts_and_styles import register_dejavu, make_gr_de_styles
register_dejavu(Path(__file__).resolve().parent / "shared" / "fonts")

# Import für Preprocessing
try:
    from shared import preprocess
except ImportError:
    # Fallback für direkten Aufruf
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from shared import preprocess

from reportlab.lib.pagesizes import A4
from reportlab.lib.units    import mm
from reportlab.lib.styles   import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums    import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.pdfbase      import pdfmetrics
from reportlab.platypus     import SimpleDocTemplate, Paragraph, Spacer, KeepTogether, Table, TableStyle
from reportlab.lib          import colors

import re, os, html, json, argparse

# =============================================================================
# PROSA-KONFIGURATION: Klare, separate Einstellungen für alle Parameter
# =============================================================================

# ----------------------- TEXTGRÖßEN-KONFIGURATION -----------------------
# Separate Einstellungen für Griechisch/Deutsch in verschiedenen Modi

# NORMAL-Modus (keine Fettschrift)
NORMAL_GR_SIZE = 9.0    # Griechische Textgröße im Normal-Modus
NORMAL_DE_SIZE = 8.0    # Deutsche Textgröße im Normal-Modus

# GR_FETT-Modus (nur Griechisch fett)
REVERSE_GR_SIZE = 8.5   # Griechische Textgröße im GR_FETT-Modus
REVERSE_DE_SIZE = 7.8   # Deutsche Textgröße im GR_FETT-Modus

# DE_FETT-Modus (nur Deutsch fett)
DE_FETT_GR_SIZE = 9.0   # Griechische Textgröße im DE_FETT-Modus
DE_FETT_DE_SIZE = 8.2   # Deutsche Textgröße im DE_FETT-Modus

# ----------------------- ABSTANDS-KONFIGURATION -----------------------
# Separate Einstellungen für verschiedene Abstände

# Vertikale Abstände INNERHALB eines Verspaars (Intra-Pair)
# Abstand zwischen griechischer und deutscher Zeile
INTRA_PAIR_GAP_MM_TAGS = 1.5      # Abstand bei PDFs MIT Tags (Originalwert für Stabilität)
INTRA_PAIR_GAP_MM_NO_TAGS = 1.0   # Abstand bei PDFs OHNE Tags (mehr Übersichtlichkeit)

# Vertikale Abstände ZWISCHEN Tabellenzeilen (Inter-Pair)
# Jede Tabellenzeile enthält mehrere Verspaare (griechisch-deutsch Paare)
# Dieser Abstand ist ZWISCHEN den Tabellenzeilen (die die Verspaare enthalten)
CONT_PAIR_GAP_MM_TAGS = 4.0     # Abstand ZWISCHEN Tabellenzeilen bei PDFs MIT Tags (minimal)
CONT_PAIR_GAP_MM_NO_TAGS = 4.0  # Abstand ZWISCHEN Tabellenzeilen bei PDFs OHNE Tags (minimal)

# Sonstige Abstände (werden durch tag_mode-spezifische Werte überschrieben)
# CONT_PAIR_GAP_MM wird in create_pdf basierend auf tag_mode gesetzt
BLANK_MARKER_GAP_MM = 4.0         # Abstand bei Leerzeilen-Marker

# ----------------------- TABELLEN-KONFIGURATION -----------------------
# Einstellungen für Tabellen-Layout

PARA_COL_MIN_MM = 5.0      # Mindestbreite für Paragraphen-Spalte (stark reduziert)
PARA_GAP_MM = 2.5          # Abstand neben Paragraphen-Spalte (minimal)
SPEAKER_COL_MIN_MM = 3.0   # Mindestbreite für Sprecher-Spalte (reduziert)
SPEAKER_GAP_MM = 1.0       # Abstand neben Sprecher-Spalte (minimal)

CELL_PAD_LR_PT = 1.1       # Innenabstand links/rechts in Zellen (minimal)
SAFE_EPS_PT = 0.5          # Sicherheitsabstand für Messungen (minimal)

# ----------------------- TAG-KONFIGURATION -----------------------
# Einstellungen für Tag-Darstellung

TAG_WIDTH_FACTOR = 1.0      # EINZIGE Definition: Skalierungsfaktor für Tag-Breite (minimal)
TAG_MAX_WIDTH_PT = 55.0     # EINZIGE Definition: Maximale Breite für alle Tags zusammen (minimal)

# ----------------------- ÜBERSCHRIFTEN-KONFIGURATION -----------------------
# Einstellungen für verschiedene Überschrift-Typen

TITLE_BRACE_SIZE = 18.0        # Größe der Titel-Klammern
TITLE_SPACE_AFTER_MM = 6       # Abstand nach Titeln

H1_EQ_SIZE = 14.0              # Größe der H1-Überschriften
H1_SPACE_AFTER_MM = 4          # Abstand nach H1-Überschriften

H2_EQ_SIZE = 10.0              # Größe der H2-Überschriften
H2_SPACE_AFTER_MM = 3          # Abstand nach H2-Überschriften

H3_EQ_SIZE = 8.0               # Größe der H3-Überschriften
H3_SPACE_AFTER_MM = 2          # Abstand nach H3-Überschriften

# ----------------------- QUELLEN-KONFIGURATION -----------------------
# Einstellungen für Quellenangaben

SOURCE_RIGHT_INDENT_MM = 10.0  # Einzug für Quellen von rechts
INLINE_EXTRA_PT = 3.0          # Zusätzlicher Platz für Inline-Elemente
INLINE_COLOR_HEX = "#777"      # Farbe für Inline-Elemente
INLINE_SCALE = 0.84            # Skalierung für Inline-Elemente (korrigiert)
NUM_COLOR_HEX = "#777"          # Farbe für Zahlen

# ----------------------- KONFIGURATIONS-FUNKTION -----------------------
# Zentrale Funktion zur Erstellung der kompletten Konfiguration

def get_prosa_cfg_for_tag_mode(tag_mode: str = "TAGS"):
    """
    Erstellt die komplette Prosa-Konfiguration basierend auf dem Tag-Modus.

    Parameter:
    tag_mode (str): "TAGS" für PDFs mit Tags, "NO_TAGS" für PDFs ohne Tags

    Rückgabe:
    dict: Vollständige Konfiguration mit allen Parametern
    """

    # Grundkonfiguration (unabhängig vom Tag-Modus)
    cfg = {
        # Textgrößen (bleiben immer gleich)
        'NORMAL_GR_SIZE': NORMAL_GR_SIZE,
        'NORMAL_DE_SIZE': NORMAL_DE_SIZE,
        'REVERSE_GR_SIZE': REVERSE_GR_SIZE,
        'REVERSE_DE_SIZE': REVERSE_DE_SIZE,
        'DE_FETT_GR_SIZE': DE_FETT_GR_SIZE,
        'DE_FETT_DE_SIZE': DE_FETT_DE_SIZE,

        # Tabellen-Parameter (bleiben immer gleich)
        'PARA_COL_MIN_MM': PARA_COL_MIN_MM,
        'PARA_GAP_MM': PARA_GAP_MM,
        'SPEAKER_COL_MIN_MM': SPEAKER_COL_MIN_MM,
        'SPEAKER_GAP_MM': SPEAKER_GAP_MM,
        'CELL_PAD_LR_PT': CELL_PAD_LR_PT,
        'SAFE_EPS_PT': SAFE_EPS_PT,
        'INLINE_EXTRA_PT': INLINE_EXTRA_PT,

        # Tag-Parameter (bleiben immer gleich)
        'TAG_WIDTH_FACTOR': TAG_WIDTH_FACTOR,
        'TAG_MAX_WIDTH_PT': TAG_MAX_WIDTH_PT,

        # Überschriften (bleiben immer gleich)
        'TITLE_BRACE_SIZE': TITLE_BRACE_SIZE,
        'TITLE_SPACE_AFTER_MM': TITLE_SPACE_AFTER_MM,
        'H1_EQ_SIZE': H1_EQ_SIZE,
        'H1_SPACE_AFTER_MM': H1_SPACE_AFTER_MM,
        'H2_EQ_SIZE': H2_EQ_SIZE,
        'H2_SPACE_AFTER_MM': H2_SPACE_AFTER_MM,
        'H3_EQ_SIZE': H3_EQ_SIZE,
        'H3_SPACE_AFTER_MM': H3_SPACE_AFTER_MM,

        # Quellen (bleiben immer gleich)
        'SOURCE_RIGHT_INDENT_MM': SOURCE_RIGHT_INDENT_MM,
        'INLINE_COLOR_HEX': INLINE_COLOR_HEX,
        'INLINE_SCALE': INLINE_SCALE,
        'NUM_COLOR_HEX': NUM_COLOR_HEX,

        # Andere Parameter (bleiben immer gleich)
        'BLANK_MARKER_GAP_MM': BLANK_MARKER_GAP_MM,
    }

    # Tag-abhängige Parameter
    if tag_mode == "TAGS":
        # Konfiguration für PDFs MIT Tags (kompaktere Darstellung)
        cfg.update({
            'INTRA_PAIR_GAP_MM': INTRA_PAIR_GAP_MM_TAGS,    # Kompakter Abstand INNERHALB Verspaaren
            'CONT_PAIR_GAP_MM': CONT_PAIR_GAP_MM_TAGS,      # Kompakter Abstand ZWISCHEN Tabellenzeilen
        })
    else:
        # Konfiguration für PDFs OHNE Tags (mehr Übersichtlichkeit)
        cfg.update({
            'INTRA_PAIR_GAP_MM': INTRA_PAIR_GAP_MM_NO_TAGS, # Größerer Abstand INNERHALB Verspaaren
            'CONT_PAIR_GAP_MM': CONT_PAIR_GAP_MM_NO_TAGS,   # Größerer Abstand ZWISCHEN Tabellenzeilen
        })

    return cfg

# ----------------------- ABWÄRTSKOMPATIBILITÄT -----------------------
# Globale Konstanten - werden in create_pdf basierend auf tag_mode gesetzt

# Basis-Konstanten (werden von allen Modi verwendet)
PARA_COL_MIN_MM = 8.0
SPEAKER_COL_MIN_MM = 5.0
SOURCE_RIGHT_INDENT_MM = 10.0
# Diese Parameter werden oben definiert (keine doppelten Definitionen)
# CELL_PAD_LR_PT = 5.0 (oben definiert)
# SAFE_EPS_PT = 2.0 (oben definiert)
# INLINE_EXTRA_PT = 3.0 (oben definiert)
# INLINE_COLOR_HEX = "#777" (oben definiert)
# INLINE_SCALE = 0.84 (oben definiert)
# NUM_COLOR_HEX = "#777" (oben definiert)
# TAG_WIDTH_FACTOR wird oben definiert (keine doppelte Definition)
# PARA_GAP_MM = 2.0 (oben definiert)
# SPEAKER_GAP_MM = 3.0 (oben definiert)
# CONT_PAIR_GAP_MM wird dynamisch in create_pdf gesetzt
BLANK_MARKER_GAP_MM = 4.0

# Textgrößen (bleiben gleich für alle Modi)
NORMAL_GR_SIZE = 9.0
NORMAL_DE_SIZE = 8.0
REVERSE_GR_SIZE = 8.5
REVERSE_DE_SIZE = 7.8

# Standardwerte (werden in create_pdf überschrieben)
CONT_PAIR_GAP_MM = CONT_PAIR_GAP_MM_TAGS   # 10.0 (korrekter Abstand zwischen Tabellenzeilen)
INTRA_PAIR_GAP_MM = INTRA_PAIR_GAP_MM_TAGS  # 1.5
# SPEAKER_GAP_MM wird oben definiert

# Alte INTER_PAIR_GAP_MM Definitionen für Abwärtskompatibilität
INTER_PAIR_GAP_MM_TAGS = CONT_PAIR_GAP_MM_TAGS
INTER_PAIR_GAP_MM_NO_TAGS = CONT_PAIR_GAP_MM_NO_TAGS
INTER_PAIR_GAP_MM = CONT_PAIR_GAP_MM

# ----------------------- Tags & Regex -----------------------
# Standard-Tag-Definitionen (können durch Tag-Config überschrieben werden)
DEFAULT_SUP_TAGS = {'N','D','G','A','V','Aj','Pt','Prp','Av','Ko','Art','≈','Kmp','Ij','Sup'}
DEFAULT_SUB_TAGS = {'Pre','Imp','Aor','Per','Plq','Fu','Inf','Imv','Akt','Med','Pas','Kon','Op','Pr','AorS','M/P'}

# Dynamische Tag-Konfiguration (wird zur Laufzeit gesetzt)
SUP_TAGS = DEFAULT_SUP_TAGS.copy()
SUB_TAGS = DEFAULT_SUB_TAGS.copy()

RE_TAG       = re.compile(r'\(([A-Za-z0-9/≈]+)\)')
RE_TAG_NAKED = re.compile(r'\([A-Za-z0-9/≈]+\)')

# ----------------------- Tag-Placement Overrides (hoch/tief/aus) -----------------------
# Globale Laufzeit-Overrides, z. B. {"Pt":"off","Aor":"sub","≈":"sup"}
_PLACEMENT_OVERRIDES: dict[str, str] = {}

def load_tag_config(config_file: str = None) -> None:
    """Lädt Tag-Konfiguration aus JSON-Datei"""
    global SUP_TAGS, SUB_TAGS, _PLACEMENT_OVERRIDES
    
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
            _PLACEMENT_OVERRIDES = config['placement_overrides']
        
        print(f"Tag-Konfiguration geladen: {len(SUP_TAGS)} SUP, {len(SUB_TAGS)} SUB")
        
    except Exception as e:
        print(f"Fehler beim Laden der Tag-Konfiguration: {e}")

def set_tag_placement_overrides(overrides: dict | None):
    """Von außen (unified_api) einstellbar. Werte: "sup" | "sub" | "off"."""
    global _PLACEMENT_OVERRIDES
    _PLACEMENT_OVERRIDES = {}
    if overrides:
        # nur gültige Werte übernehmen, Keys als plain Strings
        for k, v in overrides.items():
            v2 = (v or '').strip().lower()
            if v2 in ('sup', 'sub', 'off'):
                _PLACEMENT_OVERRIDES[str(k)] = v2

def _partition_tags_for_display(tags: list[str], *, is_greek_row: bool) -> tuple[list[str], list[str], list[str]]:
    """
    Teilt tags in (sups, subs, rest) gemäß:
      - Standard (SUP_TAGS/SUB_TAGS)
      - DE-Zeile: nur '≈' im Sup sichtbar (wie gehabt)
      - Overrides: _PLACEMENT_OVERRIDES hat Vorrang: 'sup'/'sub'/'off'
    """
    if not tags:
        return [], [], []

    if not is_greek_row:
        # DE-Zeile: nur '≈' bleibt (wie bisher)
        return (['≈'] if '≈' in tags else []), [], []

    # GR-Zeile: Standard-Verteilung
    sups = [t for t in tags if t in SUP_TAGS]
    subs = [t for t in tags if t in SUB_TAGS]
    rest = [t for t in tags if (t not in SUP_TAGS and t not in SUB_TAGS)]

    # Overrides anwenden
    if _PLACEMENT_OVERRIDES:
        keep_sup, keep_sub, keep_off = [], [], []
        for t in tags:
            mode = _PLACEMENT_OVERRIDES.get(t)
            if mode == 'sup':
                keep_sup.append(t)
            elif mode == 'sub':
                keep_sub.append(t)
            elif mode == 'off':
                keep_off.append(t)

        if keep_sup or keep_sub or keep_off:
            vis = [t for t in tags if t not in keep_off]
            # Rest, der weder explizit sup noch sub ist, bleibt nach Default-Verteilung sichtbar
            default_sup = [t for t in sups if t in vis and t not in keep_sup and t not in keep_sub]
            default_sub = [t for t in subs if t in vis and t not in keep_sup and t not in keep_sub]
            default_rest = [t for t in rest if t in vis and t not in keep_sup and t not in keep_sub]
            sups = keep_sup + default_sup
            subs = keep_sub + default_sub
            rest = default_rest

    return sups, subs, rest

RE_INLINE_MARK = re.compile(r'^\(\s*(?:[0-9]+[a-z]*|[a-z])\s*\)$', re.IGNORECASE)

RE_EQ_H1 = re.compile(r'^\s*={4}\s*(.+?)\s*={4}\s*$')
RE_EQ_H2 = re.compile(r'^\s*={2}\s*(.+?)\s*={2}\s*$')
RE_EQ_H3 = re.compile(r'^\s*=\s*(.+?)\s*=\s*$')
RE_EQ_PARA = re.compile(r'^\s*=\s*§\s*([0-9IVXLCDM]+)\s*=\s*$', re.IGNORECASE)
RE_BRACE_TITLE = re.compile(r'^\s*\{\s*(.+?)\s*\}\s*$')

RE_QUOTE_START   = re.compile(r'^\s*\[ZitatAnfang\]\s*$',  re.IGNORECASE)
RE_QUOTE_END     = re.compile(r'^\s*\[ZitatEnde\]\s*$',    re.IGNORECASE)
RE_SOURCE_START  = re.compile(r'^\s*\[QuelleAnfang\]\s*$', re.IGNORECASE)
RE_SOURCE_END    = re.compile(r'^\s*\[QuelleEnde\]\s*$',   re.IGNORECASE)
RE_SOURCE_INLINE = re.compile(r'^\s*\[QuelleAnfang\]\s*(.*?)\s*\[QuelleEnde\]\s*$', re.IGNORECASE)

RE_HAS_GREEK = re.compile(r'[\u0370-\u03FF\u1F00-\u1FFF]')

# Sprecher (griechisch + Klammerform)
RE_SPEAKER_GR    = re.compile(r'^[\u0370-\u03FF\u1F00-\u1FFF]+:$')     # Λυσ:, Σωκ:
RE_SPK_BRACKET   = re.compile(r'^\[[^\]]*:\]$')                         # [ΣΩΚ:]

# ----------------------- Utils -----------------------
def _strip_speaker_prefix_for_classify(line: str) -> str:
    """Entfernt NUR für die Klassifikation einen führenden Sprecher-Präfix."""
    s = (line or '').strip()
    # [Sprecher:] <Rest>
    m = re.match(r'^\[[^\]]*:\]\s*(.*)$', s)
    if m:
        return m.group(1)
    # ΓΡΑΦΗ: <Rest>
    m2 = re.match(r'^[\u0370-\u03FF\u1F00-\u1FFF]+:\s*(.*)$', s)
    if m2:
        return m2.group(1)
    return s

def _leading_for(size: float) -> float:
    return round(size * 1.30 + 0.6, 1)

def xml_escape(text:str) -> str:
    return html.escape(text or '', quote=False)

def is_greek_line(s:str) -> bool:
    return bool(RE_HAS_GREEK.search(s or ''))

def is_empty_or_sep(line:str) -> bool:
    t = (line or '').strip()
    return (not t) or t.upper() in {'[FREIE ZEILE]', '[ENTERZEICHEN]'} or t.startswith('---')

def normalize_spaces(s:str) -> str:
    return re.sub(r'\s+', ' ', (s or '').strip())

def pre_substitutions(s:str) -> str:
    if not s: return s
    punct_alt = r'(?:,|\.|;|:|!|\?|%|…|\u00B7|\u0387|\u037E)'
    s = re.sub(rf'\s+{punct_alt}', lambda m: m.group(0).lstrip(), s)
    s = re.sub(r'([\(\[\{\«“‹‘])\s+', r'\1', s)
    s = re.sub(r'\s+([\)\]\}\»”›’])', r'\1', s)
    s = re.sub(r'\(([#\+\-])', r'\1(', s)
    s = re.sub(r'\[([#\+\-])', r'\1[', s)
    s = re.sub(r'\{([#\+\-])', r'\1{', s)
    # Dagger/Winkel-Hack (Altregel)
    s = re.sub(r'†\#', '#†', s); s = re.sub(r'†\+', '+†', s); s = re.sub(r'†\-', '-†', s)
    s = re.sub(r'<\#', '#<', s); s = re.sub(r'<\+', '+<', s); s = re.sub(r'<\-', '-<', s)
    # Anführungszeichen + Farbcodes
    quote_class = r'["\'“”„«»‚‘’‹›]+'
    return re.sub(rf'(^|(?<=\s))({quote_class})([#\+\-])', r'\1\3\2', s)

def tokenize(line:str):
    line = normalize_spaces(pre_substitutions(line))
    return [tok for tok in line.split(' ') if tok.strip()]

def _measure_string(text:str, font:str, size:float) -> float:
    return pdfmetrics.stringWidth(text, font, size)

# ----------------------- Sprecher-Handling -----------------------
def pop_leading_speaker(tokens):
    """Entfernt führenden Sprecher (Λυσ:, [Χορ:]) und liefert (name, rest_tokens)."""
    if not tokens: return '', tokens
    t0 = tokens[0]
    if RE_SPK_BRACKET.match(t0):
        inner = t0[1:-1]
        if inner.endswith(':'): inner = inner[:-1]
        return inner.strip(), tokens[1:]
    if RE_SPEAKER_GR.match(t0):
        return t0.rstrip(':'), tokens[1:]
    return '', tokens

# ----------------------- Markup & Messen -----------------------
def _inline_badge(text_inside:str, base_font_size:float) -> str:
    small = max(4.0, base_font_size * INLINE_SCALE)
    return f'<font name="DejaVu" color="{INLINE_COLOR_HEX}" size="{small:.2f}">[{xml_escape(text_inside)}]</font>'

def format_token_markup(token:str, *, reverse_mode:bool=False, is_greek_row:bool, base_font_size:float) -> str:
    raw = (token or '').strip()
    if not raw: return ''
    # Inline-Marken wie "(1)" → kleines graues Badge (nur in GR-Zeile sichtbar)
    if RE_INLINE_MARK.match(raw):
        inner = re.sub(r'^\(|\)$', '', raw).replace(' ', '')
        return _inline_badge(inner, base_font_size) if is_greek_row else ''

    # Farbcodes - finde den ersten Farbcode im Token
    color = None
    color_pos = -1
    if '#' in raw:
        color_pos = raw.find('#'); color = '#FF0000'
    elif '+' in raw:
        color_pos = raw.find('+'); color = '#1E90FF'
    elif '-' in raw:
        color_pos = raw.find('-'); color = '#228B22'

    # Entferne den Farbcode aus dem raw-Text
    if color_pos >= 0:
        raw = raw[:color_pos] + raw[color_pos+1:]

    # Stärke/Tags
    strong = '~' in raw; raw = raw.replace('~','')
    tags = RE_TAG.findall(raw)
    core = RE_TAG_NAKED.sub('', raw).strip()

    aorS_present = 'AorS' in tags
    if aorS_present: strong = True

    is_bold = False; star_visible = False
    if '*' in core:
        if strong and not aorS_present:  # Bei AorS keine Sternchen anzeigen
            star_visible = True
        else:
            if reverse_mode and not is_greek_row: star_visible = True
            else: is_bold = True
        core = core.replace('*','')
    if strong and not star_visible and not aorS_present:  # Bei AorS keine Sternchen hinzufügen
        core += '*'
    if reverse_mode and is_greek_row: is_bold = True

    # NEU: Partition via Overrides
    if is_greek_row:
        sups, subs, rest = _partition_tags_for_display(tags, is_greek_row=True)
    else:
        sups, subs, rest = _partition_tags_for_display(tags, is_greek_row=False)

    core = xml_escape(core.replace('-', '|'))
    parts = []
    if is_bold: parts.append('<b>')
    if color:   parts.append(f'<font color="{color}">')
    parts.append(core)
    for t in sups: parts.append(f'<sup>{t}</sup>')
    for t in subs: parts.append(f'<sub>{t}</sub>')
    for t in rest: parts.append(f'({xml_escape(t)})')
    if color:   parts.append('</font>')
    if is_bold: parts.append('</b>')
    return ''.join(parts)

def visible_measure_token(token:str, *, font:str, size:float, is_greek_row:bool=True, reverse_mode:bool=False) -> float:
    t = (token or '').strip()
    if not t: return 0.0
    if RE_INLINE_MARK.match(t):
        inner = re.sub(r'^\(|\)$', '', t).replace(' ', '')
        w = _measure_string(f'[{inner}]', font, size)
        return w + SAFE_EPS_PT + INLINE_EXTRA_PT + 2*CELL_PAD_LR_PT

    # Entferne ALLE Farbcodes (#, +, -) aus dem Token
    for color_char in ['#', '+', '-']:
        t = t.replace(color_char, '')
    strong = '~' in t; t = t.replace('~','')

    tags = RE_TAG.findall(t)
    core = RE_TAG_NAKED.sub('', t).strip()

    star_visible = False
    aorS_present = 'AorS' in tags
    if aorS_present: strong = True
    if '*' in core:
        if strong and not aorS_present:  # Bei AorS keine Sternchen anzeigen
            star_visible = True
        core = core.replace('*','')
    if strong and not star_visible and not aorS_present:  # Bei AorS keine Sternchen hinzufügen
        core += '*'

    w = _measure_string(core.replace('-', '|'), font, size)

    # NEU: gleiche Partition wie in der Darstellung
    sups, subs, rest = _partition_tags_for_display(tags, is_greek_row=is_greek_row)

    # Breite der sichtbaren Tags addieren (beschränkt)
    kept = sups + subs + rest
    if kept:
        tag_width = TAG_WIDTH_FACTOR * _measure_string(''.join(kept), font, size)
        max_tag_width = min(tag_width, TAG_MAX_WIDTH_PT)
        w += max_tag_width

    return w + SAFE_EPS_PT + 2*CELL_PAD_LR_PT
    
# ----------------------- Parsing (Prosa + Dialog) -----------------------
def detect_eq_heading(line:str):
    s = (line or '').strip()
    m = RE_EQ_H1.match(s)
    if m: return ('h1_eq', m.group(1).strip())
    m = RE_EQ_H2.match(s)
    if m: return ('h2_eq', m.group(1).strip())
    m = RE_EQ_H3.match(s)
    if m: return ('h3_eq', m.group(1).strip())
    return (None, None)

def process_input_file(fname:str):
    """
    Vereinheitlichte Parser-Phase:
    - Unterstützt Prosa-Features (Titel {}, =-Überschriften, §, Zitate/Quellen).
    - Erkennt Sprecher in GR/DE und erzeugt später (bei Bedarf) eine Sprecher-Spalte.
    - GR/DE-Paare werden wie gehabt gebildet; reflow zu Streams in group_pairs_into_flows().
    """
    with open(fname, encoding='utf-8') as f:
        raw = [ln.rstrip('\n') for ln in f]

    blocks = []; i = 0
    while i < len(raw):
        line = (raw[i] or '').strip()
        if is_empty_or_sep(line): i += 1; continue

        m = RE_BRACE_TITLE.match(line)
        if m:
            blocks.append({'type':'title_brace', 'text': m.group(1).strip()}); i += 1; continue

        m = RE_EQ_PARA.match(line)
        if m:
            blocks.append({'type':'para_set', 'label': f'§ {m.group(1)}'}); i += 1; continue

        htyp, htxt = detect_eq_heading(line)
        if htyp:
            blocks.append({'type': htyp, 'text': htxt}); i += 1; continue

        m = RE_SOURCE_INLINE.match(line)
        if m:
            blocks += [{'type':'blank'}, {'type':'source', 'text': m.group(1).strip()}, {'type':'blank'}]
            i += 1; continue

        if RE_QUOTE_START.match(line):
            blocks.append({'type':'blank'}); i += 1
            qlines = []
            while i < len(raw) and not RE_QUOTE_END.match((raw[i] or '').strip()):
                qlines.append(raw[i].rstrip('\n')); i += 1
            blocks.append({'type':'quote', 'lines': qlines})
            if i < len(raw) and RE_QUOTE_END.match((raw[i] or '').strip()):
                blocks.append({'type':'blank'}); i += 1
            continue

        if RE_SOURCE_START.match(line):
            blocks.append({'type':'blank'}); i += 1
            slines = []
            while i < len(raw) and not RE_SOURCE_END.match((raw[i] or '').strip()):
                slines.append((raw[i] or '').strip()); i += 1
            blocks.append({'type':'source', 'text': ' '.join([s for s in slines if s])})
            if i < len(raw) and RE_SOURCE_END.match((raw[i] or '').strip()):
                blocks.append({'type':'blank'}); i += 1
            continue

        # Normale Paarbildung
        if is_greek_line(line):
            gr = line; i += 1
            while i < len(raw) and is_empty_or_sep(raw[i]): i += 1
            de_line = ''
            if i < len(raw):
                cand = (raw[i] or '').strip()
                cand_cls = _strip_speaker_prefix_for_classify(cand)
                if not is_greek_line(cand_cls):
                    de_line = cand
                    i += 1

            blocks.append({'type':'pair', 'gr': gr, 'de': de_line})
            continue

        blocks.append({'type':'pair', 'gr': '', 'de': line}); i += 1

    return blocks

def group_pairs_into_flows(blocks):
    """
    Reflow zu „Flows“ (fortlaufender Tokenstrom) mit optionaler
    - Sprecher-Info (falls im GR-Teil erkennbar)
    - §-Absatzlabel (para_label)
    Schnittpunkte: neuer Sprecher oder para_set / Strukturblöcke.
    """
    flows = []; buf_gr, buf_de = [], []
    current_para_label = None
    active_speaker = ''
    any_speaker_seen = False

    def flush():
        nonlocal buf_gr, buf_de, active_speaker
        if buf_gr or buf_de:
            flows.append({'type':'flow','gr_tokens':buf_gr,'de_tokens':buf_de,
                          'para_label': current_para_label, 'speaker': active_speaker})
            buf_gr, buf_de = [], []

    for b in blocks:
        t = b['type']
        if t == 'pair':
            gt = tokenize(b['gr']) if b['gr'] else []
            dt = tokenize(b['de']) if b['de'] else []

            # DE: Inline-Marken unsichtbar machen
            dt = ['' if RE_INLINE_MARK.match(x or '') else (x or '') for x in dt]

            # Sprecher entfernen + Wechsel erkennen
            _sp_de, dt = pop_leading_speaker(dt)
            sp_gr, gt = pop_leading_speaker(gt)
            if sp_gr:
                any_speaker_seen = True
                if sp_gr != active_speaker:
                    flush()
                    active_speaker = sp_gr

            # Breitenangleich
            if len(gt) > len(dt):   dt += [''] * (len(gt) - len(dt))
            elif len(dt) > len(gt): gt += [''] * (len(dt) - len(gt))

            buf_gr.extend(gt); buf_de.extend(dt); continue

        if t == 'para_set':
            flush(); current_para_label = b['label']; continue

        # Strukturelle Blöcke → vorher flushen
        flush(); flows.append(b)

    flush()
    # Meta: merken, ob überhaupt Sprecher existieren
    flows.append({'type':'_meta', 'any_speaker': any_speaker_seen})
    return flows

# ----------------------- Tabellenbau -----------------------
def build_tables_for_stream(gr_tokens, de_tokens, *,
                            doc_width_pt,
                            reverse_mode:bool=False,  # Deprecated, kept for compatibility
                            token_gr_style, token_de_style,
                            para_display:str, para_width_pt:float, style_para,
                            speaker_display:str, speaker_width_pt:float, style_speaker,
                            table_halign='LEFT', italic=False):
    cols = max(len(gr_tokens), len(de_tokens))
    gr = gr_tokens[:] + [''] * (cols - len(gr_tokens))
    de = de_tokens[:] + [''] * (cols - len(de_tokens))
    de = ['' if RE_INLINE_MARK.match(t or '') else (t or '') for t in de]

    def col_width(k:int) -> float:
        w_gr = visible_measure_token(gr[k], font=token_gr_style.fontName, size=token_gr_style.fontSize, is_greek_row=True, reverse_mode=False) if gr[k] else 0.0
        w_de = visible_measure_token(de[k], font=token_de_style.fontName, size=token_de_style.fontSize, is_greek_row=False, reverse_mode=False) if de[k] else 0.0
        return max(w_gr, w_de)

    widths = [col_width(k) for k in range(cols)]
    tables, i, first_slice = [], 0, True
    while i < cols:
        acc, j = 0.0, i

        # verfügbare Breite abzüglich optionaler Spalten
        avail_w = doc_width_pt
        if speaker_width_pt > 0:
            avail_w -= (speaker_width_pt + SPEAKER_GAP_MM*mm)
        if para_width_pt > 0:
            avail_w -= (para_width_pt + PARA_GAP_MM*mm)

        # Hilfen: prüfe, ob in de[i:j] irgendein sichtbarer Inhalt steckt
        def _has_de_content(i_start: int, i_end_excl: int) -> bool:
            if i_start >= i_end_excl:
                return False
            for k in range(i_start, i_end_excl):
                if (de[k] or '').strip():
                    return True
            return False

        # finde nächstes Index >= cur, das DE-Inhalt hat
        def _next_de_index(from_idx: int) -> int:
            p = from_idx
            while p < cols and not (de[p] or '').strip():
                p += 1
            return p  # kann == cols sein

        # Normale Pack-Phase
        while j < cols:
            w = widths[j]
            if acc + w > avail_w and j > i:
                break
            acc += w
            j += 1

        # --- SPEZIALFALL: erstes Slice eines Sprecher-Blocks ohne DE-Inhalt
        if first_slice and not _has_de_content(i, j):
            k = _next_de_index(j)  # erster Index mit DE-Inhalt rechts vom Slice
            if k < cols:
                # (1) Versuche, alle Spalten bis inkl. k zusätzlich unterzubringen
                extra = 0.0
                for t in range(j, k+1):
                    extra += widths[t]
                if acc + extra <= avail_w:
                    acc += extra
                    j = k + 1
                else:
                    # (2) Notfalls tausche letzte Spalte des Slices gegen Spalte k aus,
                    #     damit wenigstens ein DE-Token im ersten Slice auftaucht.
                    if j > i:
                        last_w = widths[j-1]
                        if acc - last_w + widths[k] <= avail_w:
                            acc = acc - last_w + widths[k]
                            j = j  # gleicher Endindex, aber wir merken uns später die Spaltenrange i..j und tauschen die Inhalte
                            # Wir vertauschen die Breitenliste nicht; der Table nimmt die Zelleninhalte.
                            # Um die Spalte k in das Slice zu bekommen, schieben wir einen "Swap" in die Slicedaten:
                            gr[i:j][-1], gr[k] = gr[k], gr[i:j][-1]
                            de[i:j][-1], de[k] = de[k], de[i:j][-1]
                        # Wenn auch das nicht passt, lassen wir es beim bisherigen Slice (optisch wie vorher),
                        # damit das Layout nicht überläuft.

        slice_gr, slice_de, slice_w = gr[i:j], de[i:j], widths[i:j]

        # linke Zusatzspalten
        sp_cell_gr = Paragraph(f'<font color="#777">{xml_escape(speaker_display)}</font>', style_speaker) if (first_slice and speaker_width_pt>0 and speaker_display) else Paragraph('', style_speaker)
        sp_cell_de = Paragraph('', style_speaker)
        sp_gap_gr  = Paragraph('', token_gr_style); sp_gap_de = Paragraph('', token_de_style)

        para_cell_gr = Paragraph(xml_escape(para_display), style_para) if (para_width_pt>0 and first_slice and para_display) else Paragraph('', style_para)
        para_cell_de = Paragraph('', style_para)
        para_gap_gr  = Paragraph('', token_gr_style); para_gap_de = Paragraph('', token_de_style)

        def cell_markup(t, is_gr):
            mk = format_token_markup(t, reverse_mode=False, is_greek_row=is_gr,
                                     base_font_size=(token_gr_style.fontSize if is_gr else token_de_style.fontSize))
            return f'<i>{mk}</i>' if italic and mk else mk

        gr_cells = [Paragraph(cell_markup(t, True),  token_gr_style) if t else Paragraph('', token_gr_style) for t in slice_gr]
        de_cells = [Paragraph(cell_markup(t, False), token_de_style) if t else Paragraph('', token_de_style) for t in slice_de]

        row_gr, row_de, colWidths = [], [], []
        if speaker_width_pt > 0:
            row_gr += [sp_cell_gr, sp_gap_gr]; row_de += [sp_cell_de, sp_gap_de]
            colWidths += [speaker_width_pt, SPEAKER_GAP_MM*mm]
        if para_width_pt > 0:
            row_gr += [para_cell_gr, para_gap_gr]; row_de += [para_cell_de, para_gap_de]
            colWidths += [para_width_pt, PARA_GAP_MM*mm]

        row_gr += gr_cells; row_de += de_cells

        # Blocksatz-ähnliche Verteilung der Spaltenbreiten
        # Berechne die tatsächlich verfügbare Breite für die Token-Spalten
        token_avail_w = avail_w
        if speaker_width_pt > 0:
            token_avail_w -= (speaker_width_pt + SPEAKER_GAP_MM*mm)
        if para_width_pt > 0:
            token_avail_w -= (para_width_pt + PARA_GAP_MM*mm)

        # Verfügbare Breite für Token-Spalten
        token_slice_w = slice_w
        total_slice_w = sum(token_slice_w)

        # Blocksatz vorübergehend deaktiviert für maximale Stabilität
        # Die intelligente Blocksatz-Logik kann Layout-Probleme verursachen
        token_slice_w = slice_w  # Immer Originalbreiten verwenden

        colWidths += token_slice_w

        tbl = Table([row_gr, row_de], colWidths=colWidths, hAlign=table_halign)
        gap_pts = INTRA_PAIR_GAP_MM * mm
        tbl.setStyle(TableStyle([
            ('LEFTPADDING',   (0,0), (-1,-1), CELL_PAD_LR_PT),
            ('RIGHTPADDING',  (0,0), (-1,-1), CELL_PAD_LR_PT),
            ('TOPPADDING',    (0,0), (-1,-1), 0.0),
            ('BOTTOMPADDING', (0,0), (-1,-1), 0.0),
            ('BOTTOMPADDING', (0,0), (-1,0),  gap_pts),
            ('VALIGN',        (0,0), (-1,-1), 'BOTTOM'),
            ('ALIGN',         (0,0), (-1,-1), 'CENTER'),
        ]))
        tables.append(tbl)
        first_slice, i = False, j
    return tables

# ----------------------- PDF-Erstellung -----------------------
def create_pdf(blocks, pdf_name:str, *, strength:str="NORMAL",
               gr_size:float=9.0, de_size:float=8.0,
               color_mode:str="COLOR", tag_mode:str="TAGS",
               placement_overrides: dict | None = None,
               tag_config: dict | None = None):

    # Tag-Placement-Overrides (hoch/tief/aus) anwenden
    set_tag_placement_overrides(placement_overrides)

    # Preprocessing mit Tag-Konfiguration anwenden
    if tag_config:
        try:
            from shared.preprocess import apply_from_payload
            # Konvertiere tag_config zu preprocess payload
            payload = {
                "show_colors": color_mode == "COLOR",
                "show_tags": tag_mode == "TAGS",
                "sup_keep": tag_config.get('sup_tags', []),
                "sub_keep": tag_config.get('sub_tags', []),
                "versmass": "NORMAL"
            }
            blocks = apply_from_payload(blocks, payload)
            print(f"Preprocessing angewendet: {len(tag_config.get('sup_tags', []))} SUP, {len(tag_config.get('sub_tags', []))} SUB")
        except Exception as e:
            print(f"Fehler beim Preprocessing: {e}")

    # Setze kritische Konstanten basierend auf tag_mode
    global INTRA_PAIR_GAP_MM, CONT_PAIR_GAP_MM, SPEAKER_GAP_MM

    if tag_mode == "TAGS":
        INTRA_PAIR_GAP_MM = INTRA_PAIR_GAP_MM_TAGS  # 1.5mm
        CONT_PAIR_GAP_MM = CONT_PAIR_GAP_MM_TAGS   # 3.0mm (minimal für Stabilität)
        SPEAKER_GAP_MM = 1.0  # 1.0mm (minimal)
    else:  # NO_TAGS
        INTRA_PAIR_GAP_MM = INTRA_PAIR_GAP_MM_NO_TAGS  # 1.0mm
        CONT_PAIR_GAP_MM = CONT_PAIR_GAP_MM_NO_TAGS    # 6.0mm (minimal)
        SPEAKER_GAP_MM = 1.0  # 1.0mm (minimal)

    # Debug-Ausgabe für Testzwecke
    # print(f"DEBUG: tag_mode={tag_mode}, CONT_PAIR_GAP_MM={CONT_PAIR_GAP_MM}, INTRA_PAIR_GAP_MM={INTRA_PAIR_GAP_MM}")

    doc = SimpleDocTemplate(pdf_name, pagesize=A4,
                            leftMargin=10*mm, rightMargin=25*mm,  # Mehr Platz rechts (1.5cm statt 1cm)
                            topMargin=14*mm,  bottomMargin=14*mm)
    frame_w = A4[0] - doc.leftMargin - doc.rightMargin
    base = getSampleStyleSheet()

    # Überschriften / Titel
    style_eq_h1 = ParagraphStyle('EqH1', parent=base['Normal'],
        fontName='DejaVu-Bold', fontSize=H1_EQ_SIZE, leading=_leading_for(H1_EQ_SIZE),
        alignment=TA_LEFT, spaceAfter=H1_SPACE_AFTER_MM*mm, keepWithNext=True)
    style_eq_h2 = ParagraphStyle('EqH2', parent=base['Normal'],
        fontName='DejaVu-Bold', fontSize=H2_EQ_SIZE, leading=_leading_for(H2_EQ_SIZE),
        alignment=TA_LEFT, spaceAfter=H2_SPACE_AFTER_MM*mm, keepWithNext=True)
    style_eq_h3 = ParagraphStyle('EqH3', parent=base['Normal'],
        fontName='DejaVu-Bold', fontSize=H3_EQ_SIZE, leading=_leading_for(H3_EQ_SIZE),
        alignment=TA_LEFT, spaceAfter=H3_SPACE_AFTER_MM*mm, keepWithNext=True)
    style_title = ParagraphStyle('TitleBrace', parent=base['Normal'],
        fontName='DejaVu-Bold', fontSize=TITLE_BRACE_SIZE, leading=_leading_for(TITLE_BRACE_SIZE),
        alignment=TA_CENTER, spaceAfter=TITLE_SPACE_AFTER_MM*mm, keepWithNext=True)

    # Tokenstile
    gr_bold = (strength == "GR_FETT")
    de_bold = (strength == "DE_FETT")

    token_gr = ParagraphStyle('TokGR', parent=base['Normal'],
        fontName='DejaVu-Bold' if gr_bold else 'DejaVu',
        fontSize=gr_size, leading=_leading_for(gr_size),
        alignment=TA_CENTER, spaceAfter=0, spaceBefore=0, wordWrap='LTR', splitLongWords=0)
    token_de = ParagraphStyle('TokDE', parent=base['Normal'],
        fontName='DejaVu-Bold' if de_bold else 'DejaVu',
        fontSize=de_size, leading=_leading_for(de_size),
        alignment=TA_CENTER, spaceAfter=0, spaceBefore=0, wordWrap='LTR', splitLongWords=0)

    # §-Label / Quelle / Sprecher
    style_para = ParagraphStyle('ParaLabel', parent=base['Normal'],
        fontName='DejaVu', fontSize=max(de_size, 9.0), leading=_leading_for(max(de_size, 9.0)),
        alignment=TA_JUSTIFY, spaceAfter=0, spaceBefore=0, wordWrap='LTR', splitLongWords=0)
    style_quote_line = ParagraphStyle('QuoteLine', parent=base['Normal'],
        fontName='DejaVu-Bold' if gr_bold else 'DejaVu', fontSize=gr_size, leading=_leading_for(gr_size),
        alignment=TA_JUSTIFY, spaceAfter=0, spaceBefore=0, wordWrap='LTR', splitLongWords=0)
    style_source = ParagraphStyle('SourceLine', parent=base['Normal'],
        fontName='DejaVu', fontSize=gr_size, leading=_leading_for(gr_size),
        alignment=TA_RIGHT, rightIndent=SOURCE_RIGHT_INDENT_MM*mm,
        spaceAfter=0, spaceBefore=0, wordWrap='LTR', splitLongWords=0)
    style_speaker = ParagraphStyle('Speaker', parent=base['Normal'],
        fontName='DejaVu', fontSize=de_size, leading=_leading_for(de_size),
        alignment=TA_JUSTIFY, spaceAfter=0, spaceBefore=0, wordWrap='LTR', splitLongWords=0, textColor=colors.HexColor('#777'))

    # Reflow
    flow_blocks = group_pairs_into_flows(blocks)
    # Meta-Flag: ob irgendwo Sprecher auftraten
    any_speaker = False
    if flow_blocks and flow_blocks[-1].get('type') == '_meta':
        any_speaker = bool(flow_blocks[-1].get('any_speaker'))
        flow_blocks = flow_blocks[:-1]

    def para_width_pt(text:str) -> float:
        if not text: return 0.0
        w = pdfmetrics.stringWidth(text, style_para.fontName, style_para.fontSize) + 1.0
        return max(PARA_COL_MIN_MM * mm, w)

    def speaker_width_pt(text:str) -> float:
        if not text: return 0.0
        disp = f'[{text}]:'
        w = pdfmetrics.stringWidth(disp, style_speaker.fontName, style_speaker.fontSize) + 0.8
        return max(SPEAKER_COL_MIN_MM * mm, w)

    def build_flow_tables(flow_block):
        gr_tokens, de_tokens = flow_block['gr_tokens'], flow_block['de_tokens']
        pdisp = flow_block.get('para_label') or ''
        sdisp = flow_block.get('speaker') or ''
        pwidth = para_width_pt(pdisp)
        swidth = speaker_width_pt(sdisp) if any_speaker else 0.0

        tables = build_tables_for_stream(
            gr_tokens, de_tokens,
            doc_width_pt=frame_w,
            reverse_mode=False,  # Nicht mehr verwendet
            token_gr_style=token_gr, token_de_style=token_de,
            para_display=pdisp, para_width_pt=pwidth, style_para=style_para,
            speaker_display=(f'[{sdisp}]:' if sdisp else ''), speaker_width_pt=swidth, style_speaker=style_speaker,
            table_halign='LEFT', italic=False
        )
        for idx, t in enumerate(tables):
            if idx > 0: t.setStyle(TableStyle([('TOPPADDING', (0,0), (-1,0), CONT_PAIR_GAP_MM * mm)]))
        return tables

    elements, idx = [], 0
    while idx < len(flow_blocks):
        b, t = flow_blocks[idx], flow_blocks[idx]['type']

        if t == 'blank':
            elements.append(Spacer(1, BLANK_MARKER_GAP_MM * mm)); idx += 1; continue
        if t == 'title_brace':
            elements.append(Paragraph(xml_escape(b['text']), style_title)); idx += 1; continue

        if t in ('h1_eq', 'h2_eq'):
            header = []
            if t == 'h1_eq':
                header.append(Paragraph(xml_escape(b['text']), style_eq_h1)); idx += 1
                while idx < len(flow_blocks) and flow_blocks[idx]['type'] == 'blank': idx += 1
                if idx < len(flow_blocks) and flow_blocks[idx]['type'] == 'h2_eq':
                    header.append(Paragraph(xml_escape(flow_blocks[idx]['text']), style_eq_h2)); idx += 1
                while idx < len(flow_blocks) and flow_blocks[idx]['type'] == 'h3_eq':
                    header.append(Paragraph(xml_escape(flow_blocks[idx]['text']), style_eq_h3)); idx += 1
            else:
                header.append(Paragraph(xml_escape(b['text']), style_eq_h2)); idx += 1
                while idx < len(flow_blocks) and flow_blocks[idx]['type'] == 'h3_eq':
                    header.append(Paragraph(xml_escape(flow_blocks[idx]['text']), style_eq_h3)); idx += 1

            scan = idx
            while scan < len(flow_blocks) and flow_blocks[scan]['type'] == 'blank': scan += 1
            if scan < len(flow_blocks) and flow_blocks[scan]['type'] == 'flow':
                flow_tables = build_flow_tables(flow_blocks[scan])
                if flow_tables:
                    k = min(2, len(flow_tables))
                    elements.append(KeepTogether(header + flow_tables[:k]))
                    for rest in flow_tables[k:]: elements.append(KeepTogether([rest]))
                    elements.append(Spacer(1, CONT_PAIR_GAP_MM * mm))
                else:
                    elements.append(KeepTogether(header))
                idx = scan + 1; continue
            else:
                elements.append(KeepTogether(header)); continue

        if t == 'h3_eq':
            elements.append(Paragraph(xml_escape(b['text']), style_eq_h3)); idx += 1; continue

        if t == 'quote':
            q_pairs, j, lines = [], 0, b.get('lines', [])
            while j < len(lines):
                ln = (lines[j] or '').strip()
                if ln:
                    if is_greek_line(ln):
                        gr, de = ln, ''
                        if j+1 < len(lines):
                            cand = (lines[j+1] or '').strip()
                            if cand and not is_greek_line(cand): de, j = cand, j+1
                        q_pairs.append((gr, de))
                    else:
                        q_pairs.append(('', ln))
                j += 1

            # Erstelle temporäre pair-Blöcke für Preprocessing
            temp_quote_blocks = []
            for gr, de in q_pairs:
                if gr or de:
                    gt = tokenize(gr) if gr else []
                    dt = tokenize(de) if de else []
                    dt = ['' if RE_INLINE_MARK.match(x or '') else (x or '') for x in dt]
                    if len(gt) > len(dt):   dt += [''] * (len(gt) - len(dt))
                    elif len(dt) > len(gt): gt += [''] * (len(dt) - len(gt))
                    temp_quote_blocks.append({
                        'type': 'pair',
                        'gr_tokens': gt,
                        'de_tokens': dt
                    })

            # Wende Preprocessing auf Zitat-Blöcke an
            processed_quote_blocks = preprocess.apply(temp_quote_blocks, color_mode=color_mode, tag_mode=tag_mode)

            # Sammle die verarbeiteten Tokens
            q_gr, q_de = [], []
            for block in processed_quote_blocks:
                if block['type'] == 'pair':
                    q_gr.extend(block.get('gr_tokens', []))
                    q_de.extend(block.get('de_tokens', []))

            # Für Zitate verwenden wir den gleichen Stil wie normale Tokens
            quote_de_style = ParagraphStyle('QuoteDE', parent=base['Normal'],
                fontName='DejaVu-Bold' if de_bold else 'DejaVu', fontSize=gr_size, leading=_leading_for(gr_size),
                alignment=TA_CENTER, spaceAfter=0, spaceBefore=0, wordWrap='LTR', splitLongWords=0)

            q_tables = build_tables_for_stream(
                q_gr, q_de,
                doc_width_pt=frame_w,
                reverse_mode=False,  # Nicht mehr verwendet
                token_gr_style=style_quote_line, token_de_style=quote_de_style,
                para_display='', para_width_pt=0.0, style_para=style_para,
                speaker_display='', speaker_width_pt=0.0, style_speaker=style_speaker,
                table_halign='CENTER', italic=True
            )
            for k, tquote in enumerate(q_tables):
                if k > 0: tquote.setStyle(TableStyle([('TOPPADDING', (0,0), (-1,0), CONT_PAIR_GAP_MM * mm)]))

            kidx, src_text = idx + 1, ''
            while kidx < len(flow_blocks) and flow_blocks[kidx]['type'] == 'blank': kidx += 1
            if kidx < len(flow_blocks) and flow_blocks[kidx]['type'] == 'source':
                src_text = (flow_blocks[kidx].get('text') or '').strip()

            block = list(q_tables)
            if src_text:
                block += [Spacer(1, BLANK_MARKER_GAP_MM * mm), Paragraph('<i>'+xml_escape(src_text)+'</i>', style_source)]
            elements.append(KeepTogether(block))
            elements.append(Spacer(1, CONT_PAIR_GAP_MM * mm))
            idx = (kidx + 1) if src_text else (idx + 1)
            if idx < len(flow_blocks) and flow_blocks[idx]['type'] == 'blank': idx += 1
            continue

        if t == 'source':
            text = (b.get('text') or '').strip()
            if text:
                elements.append(KeepTogether([Paragraph('<i>'+xml_escape(text)+'</i>', style_source)]))
                elements.append(Spacer(1, CONT_PAIR_GAP_MM * mm))
            idx += 1; continue

        if t == 'flow':
            for tbl in build_flow_tables(b): elements.append(KeepTogether([tbl]))
            elements.append(Spacer(1, CONT_PAIR_GAP_MM * mm))
            idx += 1; continue

        idx += 1

    doc.build(elements)

# ----------------------- Batch / Dateinamen (Legacy-Einzellauf) -----------------------
def label_from_input_name(infile:str) -> str:
    stem = Path(infile).stem
    m = re.match(r'(?i)^input(.+)$', stem)
    label = m.group(1) if m else stem
    return re.sub(r'\W+', '', label) or 'Text'

def output_name_for_label(label:str, *, reverse:bool=False) -> str:
    return f'{label}{"_Reverse" if reverse else ""}.pdf'

def run_batch(input_files):
    for infile in input_files:
        if not os.path.isfile(infile):
            print(f"⚠ Datei nicht gefunden, übersprungen: {infile}"); continue
        try:
            print(f"→ Verarbeite: {infile}")
            blocks = process_input_file(infile)
            label  = label_from_input_name(infile)

            out_normal = output_name_for_label(label, reverse=False)
            create_pdf(blocks, out_normal, strength="NORMAL",
                       gr_size=NORMAL_GR_SIZE, de_size=NORMAL_DE_SIZE)
            print(f"✓ PDF erstellt → {out_normal}")

            out_fett = output_name_for_label(label, reverse=False) + "_Fett"
            create_pdf(blocks, out_fett, strength="GR_FETT",
                       gr_size=REVERSE_GR_SIZE, de_size=REVERSE_DE_SIZE)
            print(f"✓ PDF erstellt → {out_fett}")

            out_rev = output_name_for_label(label, reverse=True)
            create_pdf(blocks, out_rev, strength="GR_FETT",
                       gr_size=REVERSE_GR_SIZE, de_size=REVERSE_DE_SIZE)
            print(f"✓ PDF erstellt → {out_rev}")
        except Exception as e:
            print(f"✗ Fehler bei {infile}: {e}")

# ----------------------- MAIN -----------------------
if __name__ == '__main__':
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Prosa PDF Generator')
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
            label = label_from_input_name(args.input_file)
            
            out_normal = output_name_for_label(label, reverse=False)
            create_pdf(blocks, out_normal, strength="NORMAL",
                       gr_size=NORMAL_GR_SIZE, de_size=NORMAL_DE_SIZE)
            print(f"✓ PDF erstellt → {out_normal}")
            
            out_fett = output_name_for_label(label, reverse=False) + "_Fett"
            create_pdf(blocks, out_fett, strength="GR_FETT",
                       gr_size=REVERSE_GR_SIZE, de_size=REVERSE_DE_SIZE)
            print(f"✓ PDF erstellt → {out_fett}")
            
            out_rev = output_name_for_label(label, reverse=True)
            create_pdf(blocks, out_rev, strength="GR_FETT",
                       gr_size=REVERSE_GR_SIZE, de_size=REVERSE_DE_SIZE)
            print(f"✓ PDF erstellt → {out_rev}")
        except Exception as e:
            print(f"✗ Fehler bei {args.input_file}: {e}")
    else:
        # Process batch
        inputs = sorted([str(p) for p in Path('.').glob('InputFließtext*.txt')])
        if not inputs:
            print("⚠ Keine Input*.txt gefunden.")
        else:
            run_batch(inputs)

