# ======================= PROSA/PLATON – vereinheitlicht =======================
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from pathlib import Path
from shared.fonts_and_styles import register_dejavu, make_gr_de_styles
register_dejavu(Path(__file__).resolve().parent / "shared" / "fonts")

# Import für Preprocessing
try:
    from shared import preprocess
    from shared.preprocess import remove_tags_from_token, remove_all_tags_from_token
except ImportError:
    # Fallback für direkten Aufruf
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from shared import preprocess
    from shared.preprocess import remove_tags_from_token, remove_all_tags_from_token

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
INTRA_PAIR_GAP_MM_TAGS = 0.7      # Abstand bei PDFs MIT Tags (KOMPAKT wie Poesie: 0.7mm)
INTRA_PAIR_GAP_MM_NO_TAGS = 0.3   # Abstand bei PDFs OHNE Tags (ETWAS KLEINERER ABSTAND ALS WIE BEI Tags: 0.3mm)

# Vertikale Abstände ZWISCHEN Tabellenzeilen (Inter-Pair)
# Jede Tabellenzeile enthält mehrere Verspaare (griechisch-deutsch Paare)
# Dieser Abstand ist ZWISCHEN den Tabellenzeilen (die die Verspaare enthalten)
CONT_PAIR_GAP_MM_TAGS = 2.0     # Abstand ZWISCHEN Tabellenzeilen bei PDFs MIT Tags (KOMPAKT wie Poesie: 2.0mm)
CONT_PAIR_GAP_MM_NO_TAGS = 1.0  # Abstand ZWISCHEN Tabellenzeilen bei PDFs OHNE Tags (MAXIMAL ENG)

# Sonstige Abstände (werden durch tag_mode-spezifische Werte überschrieben)
# CONT_PAIR_GAP_MM wird in create_pdf basierend auf tag_mode gesetzt
BLANK_MARKER_GAP_MM = 4.0         # Abstand bei Leerzeilen-Marker

# ----------------------- HORIZONTALE ABSTÄNDE (Wort zu Wort) -----------------------
# Sicherheitspuffer zwischen Wörtern (links-rechts), abhängig von Tag-Sichtbarkeit

# VEREINHEITLICHUNG: NUR diese zwei Werte entscheiden über horizontalen Abstand!
# Egal ob: Sprecher, §, HideTags, tag_config, oder NO_TAGS PDF
TOKEN_SPACING_WITH_TAGS_PT = 1.0    # Wort hat sichtbare Tags → kleinerer Abstand (Tags trennen optisch) - REDUZIERT von 1.2
TOKEN_SPACING_NO_TAGS_PT = 2.0      # Wort hat keine Tags → größerer Abstand (klare Trennung nötig)

# ----------------------- TABELLEN-KONFIGURATION -----------------------
# Einstellungen für Tabellen-Layout

PARA_COL_MIN_MM = 5.0      # Mindestbreite für Paragraphen-Spalte (stark reduziert)
PARA_GAP_MM = 1.2          # Abstand neben Paragraphen-Spalte (weiter reduziert für maximale Textbreite)
# Normalize spacing constants so speaker texts behave like §/no-speaker texts
SPEAKER_COL_MIN_MM = 3.0   # Mindestbreite für Sprecher-Spalte
SPEAKER_GAP_MM = 1.5       # Erhöht von 1.2 auf 1.5mm für minimalen Puffer zwischen Sprecher und Text

CELL_PAD_LR_PT = 0.6       # Innenabstand links/rechts in Zellen (stark reduziert für kompaktere TAG-PDFs)
SAFE_EPS_PT = 1.7          # Sicherheitsabstand für Messungen (erhöht von 1.6 auf 1.7 für beste Lesbarkeit bei Sprecher-Texten)

# ----------------------- TAG-KONFIGURATION -----------------------
# Einstellungen für Tag-Darstellung

TAG_WIDTH_FACTOR = 1.0      # EINZIGE Definition: Skalierungsfaktor für Tag-Breite (minimal)
TAG_MAX_WIDTH_PT = 55.0     # EINZIGE Definition: Maximale Breite für alle Tags zusammen (minimal)

# ----------------------- ÜBERSCHRIFTEN-KONFIGURATION -----------------------
# Einstellungen für verschiedene Überschrift-Typen

TITLE_BRACE_SIZE = 18.0        # Größe der Titel-Klammern
TITLE_SPACE_AFTER_MM = 6       # Abstand nach Titeln

H1_EQ_SIZE = 24.0              # Größe der H1-Überschriften (==== ====) - verkleinert
H1_SPACE_AFTER_MM = 4          # Abstand nach H1-Überschriften

H2_EQ_SIZE = 18.0              # Größe der H2-Überschriften (=== ===) - verkleinert
H2_SPACE_AFTER_MM = 3          # Abstand nach H2-Überschriften

H3_EQ_SIZE = 15.3              # Größe der H3-Überschriften (== ==)
H3_SPACE_AFTER_MM = 2          # Abstand nach H3-Überschriften

# ----------------------- QUELLEN-KONFIGURATION -----------------------
# Einstellungen für Quellenangaben

SOURCE_RIGHT_INDENT_MM = 10.0  # Einzug für Quellen von rechts
INLINE_EXTRA_PT = 3.0          # Zusätzlicher Platz für Inline-Elemente
INLINE_COLOR_HEX = "#777"      # Farbe für Inline-Elemente
INLINE_SCALE = 0.84            # Skalierung für Inline-Elemente (korrigiert)
NUM_COLOR_HEX = "#000000"          # Farbe für Zahlen

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
PARA_COL_MIN_MM = 3.0   # Dynamische Berechnung basierend auf tatsächlicher Breite (reduziert für kompaktere Darstellung)
SPEAKER_COL_MIN_MM = 3.0
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
DEFAULT_SUP_TAGS = {'N','D','G','A','V','Du','Adj','Pt','Prp','Adv','Kon','Art','≈','Kmp','ij','Sup','Abl'}  # NEU: Abl für Latein
DEFAULT_SUB_TAGS = {'Prä','Imp','Aor','Per','Plq','Fu','Inf','Imv','Akt','Med','Pas','Knj','Op','Pr','AorS','M/P','Gdv','Ger','Spn','Fu1','Fu2'}  # NEU: Gdv, Ger, Spn, Fu1, Fu2 für Latein

# Dynamische Tag-Konfiguration (wird zur Laufzeit gesetzt)
SUP_TAGS = DEFAULT_SUP_TAGS.copy()
SUB_TAGS = DEFAULT_SUB_TAGS.copy()

RE_TAG       = re.compile(r'\(([A-Za-z0-9/≈äöüßÄÖÜ]+)\)')
RE_TAG_NAKED = re.compile(r'\([A-Za-z0-9/≈äöüßÄÖÜ]+\)')
RE_TAG_STRIP = re.compile(r'\(\s*[A-Za-z0-9/≈äöüßÄÖÜ]+\s*\)')

# ----------------------- Defensive token-helpers -----------------------
def _strip_tags_from_token(tok: str, block: dict = None, tok_idx: int = None, tag_mode: str = "TAGS") -> str:
    """
    Entfernt Tags aus einem Token basierend auf tag_mode und token_meta.
    - Wenn tag_mode == "NO_TAGS": entferne alle Tags
    - Sonst: entferne nur Tags, die in token_meta[i]['removed_tags'] markiert sind
    """
    # DEBUG: Print if token contains color symbols
    if any(sym in tok for sym in ['$', '+', '-']) if tok else False:
        print(f"DEBUG _strip_tags_from_token: INPUT tok='{tok}', tag_mode='{tag_mode}'", flush=True)
    
    if not tok:
        return tok
    
    # If NO_TAGS - remove everything, but preserve color symbols
    if tag_mode == "NO_TAGS":
        # WICHTIG: Hole Farbsymbol aus token_meta (hat Priorität)
        color_sym = None
        if block is not None and tok_idx is not None:
            token_meta = block.get('token_meta', [])
            meta = token_meta[tok_idx] if tok_idx < len(token_meta) else {}
            color_sym = meta.get('color_symbol')
        if not color_sym:
            for sym in ['#', '+', '-', '§', '$']:
                if sym in tok:
                    color_sym = sym
                    break
        cleaned = remove_all_tags_from_token(tok)
        # Re-add color symbol if it was removed
        if color_sym and color_sym not in cleaned:
            if cleaned and cleaned[0] == '|':
                cleaned = '|' + color_sym + cleaned[1:]
            else:
                cleaned = color_sym + cleaned
        
        # DEBUG: Print result
        if any(sym in tok for sym in ['$', '+', '-']):
            print(f"DEBUG _strip_tags_from_token: NO_TAGS OUTPUT cleaned='{cleaned}', color_sym='{color_sym}'", flush=True)
        
        return cleaned
    
    # Otherwise remove only tags that were recorded as removed by apply_tag_visibility
    if block is not None and tok_idx is not None:
        token_meta = block.get('token_meta', [])
        meta = token_meta[tok_idx] if tok_idx < len(token_meta) else {}
        removed_tags = set(meta.get('removed_tags', []))
        if removed_tags:
            # WICHTIG: Hole Farbsymbol aus token_meta (hat Priorität)
            color_sym = meta.get('color_symbol')
            if not color_sym:
                for sym in ['#', '+', '-', '§', '$']:
                    if sym in tok:
                        color_sym = sym
                        break
            cleaned = remove_tags_from_token(tok, removed_tags)
            # Re-add color symbol if it was removed
            if color_sym and color_sym not in cleaned:
                if cleaned and cleaned[0] == '|':
                    cleaned = '|' + color_sym + cleaned[1:]
                else:
                    cleaned = color_sym + cleaned
            
            # DEBUG: Print result
            if any(sym in tok for sym in ['$', '+', '-']):
                print(f"DEBUG _strip_tags_from_token: TAGS+removed OUTPUT cleaned='{cleaned}', color_sym='{color_sym}', removed_tags={removed_tags}", flush=True)
            
            return cleaned
    
    # nothing to remove for this token, keep as-is
    # DEBUG: Print result
    if any(sym in tok for sym in ['$', '+', '-']) if tok else False:
        print(f"DEBUG _strip_tags_from_token: TAGS+no-remove OUTPUT tok='{tok}' (unchanged)", flush=True)
    
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

def _normalize_tag_case(tag: str) -> str:
    """
    Normalisiert Tag-Groß-/Kleinschreibung für Kompatibilität.
    Konvertiert Ij -> ij für Rückwärtskompatibilität.
    """
    if tag == 'Ij':
        return 'ij'
    return tag

def _partition_tags_for_display(tags: list[str], *, is_greek_row: bool) -> tuple[list[str], list[str], list[str]]:
    """
    Teilt tags in (sups, subs, rest) gemäß:
      - Standard (SUP_TAGS/SUB_TAGS)
      - DE-Zeile: nur '≈' im Sup sichtbar (wie gehabt)
      - Overrides: _PLACEMENT_OVERRIDES hat Vorrang: 'sup'/'sub'/'off'
    """
    if not tags:
        return [], [], []

    # Normalisiere Tags für Kompatibilität
    normalized_tags = [_normalize_tag_case(tag) for tag in tags]

    if not is_greek_row:
        # DE-Zeile: nur '≈' bleibt (wie bisher)
        return (['≈'] if '≈' in normalized_tags else []), [], []

    # GR-Zeile: Standard-Verteilung mit normalisierten Tags
    sups = [t for t in normalized_tags if t in SUP_TAGS]
    subs = [t for t in normalized_tags if t in SUB_TAGS]
    rest = [t for t in normalized_tags if (t not in SUP_TAGS and t not in SUB_TAGS)]

    # Overrides anwenden (mit normalisierten Tags)
    if _PLACEMENT_OVERRIDES:
        keep_sup, keep_sub, keep_off = [], [], []
        for t in normalized_tags:
            mode = _PLACEMENT_OVERRIDES.get(t)
            if mode == 'sup':
                keep_sup.append(t)
            elif mode == 'sub':
                keep_sub.append(t)
            elif mode == 'off':
                keep_off.append(t)

        if keep_sup or keep_sub or keep_off:
            vis = [t for t in normalized_tags if t not in keep_off]
            # Rest, der weder explizit sup noch sub ist, bleibt nach Default-Verteilung sichtbar
            default_sup = [t for t in sups if t in vis and t not in keep_sup and t not in keep_sub]
            default_sub = [t for t in subs if t in vis and t not in keep_sup and t not in keep_sub]
            default_rest = [t for t in rest if t in vis and t not in keep_sup and t not in keep_sub]
            sups = keep_sup + default_sup
            subs = keep_sub + default_sub
            rest = default_rest

    return sups, subs, rest

RE_INLINE_MARK = re.compile(r'^\(\s*(?:[0-9]+[a-z]*|[a-z])\s*\)$', re.IGNORECASE)

RE_EQ_H1 = re.compile(r'^\s*={4}\s*(.+?)\s*={4}\s*$')                 # ==== Text ====
RE_EQ_H2 = re.compile(r'^\s*={3}\s*(.+?)\s*={3}\s*$')                 # === Text ===
RE_EQ_H3 = re.compile(r'^\s*={2}\s*(.+?)\s*={2}\s*$')                 # == Text ==
RE_EQ_PARA = re.compile(r'^\s*=\s*§\s*([0-9IVXLCDM]+)\s*=\s*$', re.IGNORECASE)
RE_BRACE_TITLE = re.compile(r'^\s*\{\s*(.+?)\s*\}\s*$')

RE_QUOTE_START   = re.compile(r'^\s*(\([^)]+\))?\s*\[Zitat\s*Anfang\]\s*$',  re.IGNORECASE)
RE_QUOTE_END     = re.compile(r'^\s*(\([^)]+\))?\s*\[Zitat\s*Ende\]\s*$',    re.IGNORECASE)
RE_SOURCE_START  = re.compile(r'^\s*(\([^)]+\))?\s*\[Quelle\s*Anfang\]\s*$', re.IGNORECASE)
RE_SOURCE_END    = re.compile(r'^\s*(\([^)]+\))?\s*\[Quelle\s*Ende\]\s*$',   re.IGNORECASE)
RE_SOURCE_INLINE = re.compile(r'^\s*(\([^)]+\))?\s*\[Quelle\s*Anfang\]\s*(.*?)\s*\[Quelle\s*Ende\]\s*$', re.IGNORECASE)

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

def _remove_speaker_from_line(line: str) -> str:
    """
    Entfernt Sprecher-Präfixe aus einer Zeile komplett.
    Wichtig: Behält Zeilennummer bei, entfernt nur den Sprecher.
    Beispiel: "(123) [Σωκράτης:] text" → "(123) text"
    """
    s = (line or '').strip()
    # Extrahiere Zeilennummer (falls vorhanden)
    line_num_match = re.match(r'^(\(\d+[a-z]*\))\s*(.*)$', s)
    if line_num_match:
        line_num = line_num_match.group(1)
        rest = line_num_match.group(2)
        # Entferne Sprecher aus dem Rest
        # [Sprecher:] <Rest>
        m = re.match(r'^\[[^\]]*:\]\s*(.*)$', rest)
        if m:
            return f"{line_num} {m.group(1)}"
        # ΓΡΑΦΗ: <Rest>
        m2 = re.match(r'^[\u0370-\u03FF\u1F00-\u1FFF]+:\s*(.*)$', rest)
        if m2:
            return f"{line_num} {m2.group(1)}"
        return s
    else:
        # Keine Zeilennummer, entferne nur Sprecher
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
    m_range = re.match(r'^\((\d+)-(\d+)([a-z]?)\)\s*(.*)$', s, re.IGNORECASE)
    if m_range:
        start = m_range.group(1)
        end = m_range.group(2)
        suffix = m_range.group(3)
        rest = m_range.group(4)
        return (f"{start}-{end}{suffix}", rest)
    
    # Regex für Zeilennummer: (Zahl[optionaler Buchstabe oder k/i])
    # k = Kommentar, i = Insertion
    # Beispiele: (123), (123a), (123k), (123i), (50k), (300i)
    m = re.match(r'^\((\d+[a-z]?)\)\s*(.*)$', s, re.IGNORECASE)
    if m:
        line_num = m.group(1)
        return (line_num, m.group(2))
    return (None, s)

def is_comment_line(line_num: str | None) -> bool:
    """Prüft, ob eine Zeilennummer ein Kommentar ist (endet mit 'k')."""
    if not line_num:
        return False
    return line_num.lower().endswith('k')

def is_insertion_line(line_num: str | None) -> bool:
    """Prüft, ob eine Zeilennummer eine Insertion ist (endet mit 'i')."""
    if not line_num:
        return False
    return line_num.lower().endswith('i')

def detect_language_count_from_context(lines: list, current_idx: int) -> int:
    """
    Erkennt, ob der Text 2-sprachig oder 3-sprachig ist, indem die umgebenden Zeilen analysiert werden.
    
    Sucht nach normalen Zeilen (ohne 'i' oder 'k' Suffix) und zählt, wie viele Zeilen mit
    der gleichen Basisnummer aufeinanderfolgen.
    
    Returns:
        2 oder 3 (Anzahl der Sprachen im Text)
    """
    # Suche rückwärts nach der letzten normalen Zeile (keine k, i Suffixe)
    search_range = 50  # Suche max. 50 Zeilen vor/nach
    
    for offset in range(1, min(search_range, current_idx + 1)):
        check_idx = current_idx - offset
        if check_idx < 0:
            break
            
        check_line = (lines[check_idx] or '').strip()
        if not check_line:
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
        while j < len(lines) and len(lines_with_same_num) < 5:  # Max 5 Zeilen prüfen
            test_line = (lines[j] or '').strip()
            if not test_line:
                j += 1
                continue
                
            test_num, _ = extract_line_number(test_line)
            if test_num == line_num:
                lines_with_same_num.append(test_line)
                j += 1
            else:
                break
        
        # Wenn wir 2 oder 3 Zeilen gefunden haben, geben wir das zurück
        count = len(lines_with_same_num)
        if count >= 2:
            return min(count, 3)  # Max 3 (2 oder 3 Sprachen)
    
    # Fallback: Suche vorwärts
    for offset in range(1, min(search_range, len(lines) - current_idx)):
        check_idx = current_idx + offset
        if check_idx >= len(lines):
            break
            
        check_line = (lines[check_idx] or '').strip()
        if not check_line:
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
        while j < len(lines) and len(lines_with_same_num) < 5:
            test_line = (lines[j] or '').strip()
            if not test_line:
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
            return min(count, 3)
    
    # Default: 2-sprachig
    return 2

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
    (0.95, 0.75, 0.8),    # Sanftes, liebliches helles Erdbeerrot (RGB)
    (0.35, 0.55, 0.85),   # Mittleres blau - mittelmäßig verbläuert
    (0.5, 0.85, 0.5),     # Leicht grün - sehr wenig vergrünt (war schon ok)
]

def get_comment_color(comment_index: int) -> tuple[float, float, float]:
    """Gibt die Farbe für einen Kommentar basierend auf dem Index zurück (Rotation: rot → blau → grün)."""
    return COMMENT_COLORS[comment_index % len(COMMENT_COLORS)]

def _remove_line_number_from_line(line: str) -> str:
    """
    Entfernt die Zeilennummer am Anfang einer Zeile.
    Wird nur für Prosa verwendet - in Poesie bleiben Zeilennummern erhalten.
    
    Format: (123) oder (123a) oder (123b) etc.
    
    Returns:
        str: Zeile ohne Zeilennummer
    """
    if not line:
        return line
    
    _, rest = extract_line_number(line)
    return rest

def is_greek_line(s:str) -> bool:
    """DEPRECATED: Alte Methode basierend auf griechischen Buchstaben."""
    return bool(RE_HAS_GREEK.search(s or ''))

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
    # punct_alt = r'(?:,|\.|;|:|!|\?|%|…|\u00B7|\u0387|\u037E)'
    # s = re.sub(rf'\s+{punct_alt}', lambda m: m.group(0).lstrip(), s)
    # s = re.sub(r'([\(\[\{\«"‹'])\s+', r'\1', s)
    # s = re.sub(r'\s+([\)\]\}\»"›'])', r'\1', s)
    # s = re.sub(r'\(([#\+\-])', r'\1(', s)
    # s = re.sub(r'\[([#\+\-])', r'\1[', s)
    # s = re.sub(r'\{([#\+\-])', r'\1{', s)
    # # Dagger/Winkel-Hack (Altregel)
    # s = re.sub(r'†\#', '#†', s); s = re.sub(r'†\+', '+†', s); s = re.sub(r'†\-', '-†', s)
    # s = re.sub(r'<\#', '#<', s); s = re.sub(r'<\+', '+<', s); s = re.sub(r'<\-', '-<', s)
    # # Anführungszeichen + Farbcodes
    # quote_class = r'["\'""„«»‚''‹›]+'
    # return re.sub(rf'(^|(?<=\s))({quote_class})([#\+\-])', r'\1\3\2', s)
    return s

def tokenize(line:str):
    # WICHTIG: Entferne Zitat/Quelle-Marker aus der Zeile ZUERST
    # Diese Marker sind nur für das Parsing gedacht und sollen nicht im PDF erscheinen
    # Entferne die Marker BEVOR normalize_spaces aufgerufen wird
    # Entferne Zitat/Quelle-Marker aus der Zeile
    line = re.sub(r'\[Zitat\s*Anfang\]', '', line, flags=re.IGNORECASE)
    line = re.sub(r'\[Zitat\s*Ende\]', '', line, flags=re.IGNORECASE)
    line = re.sub(r'\[Quelle\s*Anfang\]', '', line, flags=re.IGNORECASE)
    line = re.sub(r'\[Quelle\s*Ende\]', '', line, flags=re.IGNORECASE)
    
    # Entferne auch Zeilennummern, die nur Marker enthalten (z.B. "(491) " wenn danach nichts kommt)
    # Dies verhindert, dass leere Zeilen mit nur Zeilennummern im PDF erscheinen
    line = re.sub(r'^\s*\(\d+[a-z]?\)\s*$', '', line)
    
    # LATEINISCH: (N)(Abl) → (Abl) Transformation
    # Entferne (N) vor Ablativ-Tags, da Nomen mit Ablativ implizit sind
    if is_latin_line(line):
        line = re.sub(r'\(N\)\(Abl\)', '(Abl)', line)
    
    line = normalize_spaces(pre_substitutions(line))
    return [tok for tok in line.split(' ') if tok.strip()]

def _measure_string(text:str, font:str, size:float) -> float:
    return pdfmetrics.stringWidth(text, font, size)

def _token_extra_buffer(token_has_visible_tags:bool):
    """
    VEREINHEITLICHTER horizontaler Sicherheitsabstand zwischen Wörtern.
    
    EINZIGER Entscheidungsfaktor: Hat das Wort im FINALEN PDF sichtbare Tags?
    - JA (Tags sichtbar): Kleinerer Abstand (Tags trennen optisch)
    - NEIN (keine Tags): Größerer Abstand (klare Trennung nötig)
    
    EGAL ob: Sprecher, §, HideTags, tag_config, oder NO_TAGS PDF!
    """
    if token_has_visible_tags:
        return TOKEN_SPACING_WITH_TAGS_PT
    else:
        return TOKEN_SPACING_NO_TAGS_PT

def _calculate_dynamic_token_spacing(gr_token: str, de_token: str, en_token: str, 
                                     tag_mode: str, tag_config: dict = None,
                                     hide_pipes: bool = False,
                                     font_gr: str = 'DejaVu', size_gr: float = 11.0,
                                     font_de: str = 'DejaVu', size_de: float = 10.0) -> float:
    """
    INTELLIGENTE Abstandsberechnung basierend auf tatsächlicher Wortlänge!
    
    Logik:
    1. Hat GR-Wort sichtbare Tags? → Prüfe weiter
    2. Ist GR-Wort (mit Tags) länger als ALLE Übersetzungen? 
       → JA: Reduzierter Abstand (0.5pt) - Tags trennen optisch
       → NEIN: Normaler Abstand (1.0pt) - Übersetzung ist länger
    3. Hat GR-Wort keine Tags? → Normaler Abstand wie NoTags (2.0pt)
    
    Berücksichtigt:
    - hide_pipes: Pipes werden zu Leerzeichen (macht Übersetzungen länger!)
    - tag_mode: NO_TAGS = keine Tags sichtbar
    - tag_config: Individuelle Tag-Versteckung
    """
    # 1. Hat GR-Wort sichtbare Tags?
    has_tags = _token_has_visible_tags(gr_token, tag_mode, tag_config)
    
    if not has_tags:
        # Keine Tags → Normaler NoTags-Abstand
        return TOKEN_SPACING_NO_TAGS_PT
    
    # 2. Berechne tatsächliche Pixel-Breiten
    # GR-Wort MIT Tags (nach Tag-Filterung, aber MIT verbleibenden Tags)
    gr_display = gr_token  # Token wie er angezeigt wird (mit sichtbaren Tags)
    gr_width = _measure_string(gr_display, font_gr, size_gr)
    
    # Übersetzungen: Berücksichtige hide_pipes!
    de_display = de_token.replace('|', ' ') if hide_pipes and de_token else de_token
    en_display = en_token.replace('|', ' ') if hide_pipes and en_token else en_token
    
    de_width = _measure_string(de_display or '', font_de, size_de)
    en_width = _measure_string(en_display or '', font_de, size_de)
    
    # Maximale Übersetzungsbreite
    max_translation_width = max(de_width, en_width)
    
    # 3. Ist GR länger als ALLE Übersetzungen?
    if gr_width > max_translation_width:
        # JA: GR mit Tags ist länger → Reduzierter Abstand (Tags trennen optisch)
        return 0.5
    else:
        # NEIN: Übersetzung ist länger → Normaler Tag-Abstand
        return TOKEN_SPACING_WITH_TAGS_PT

def _token_has_visible_tags(token: str, tag_mode: str, tag_config: dict = None) -> bool:
    """
    VEREINFACHTE Prüfung: Hat das Token im FINALEN PDF sichtbare Tags?
    
    Berücksichtigt:
    - tag_mode == "NO_TAGS": Keine Tags sichtbar
    - tag_config: Individuelle Tag-Versteckung
    - HideTags: Tags wurden entfernt
    
    Returns:
        True wenn Token sichtbare Tags hat, sonst False
    """
    if not token:
        return False
    
    # Bei NO_TAGS sind ALLE Tags unsichtbar
    if tag_mode == "NO_TAGS":
        return False
    
    # Extrahiere Tags aus Token
    tags = RE_TAG.findall(token)
    if not tags:
        return False
    
    # Wenn tag_config vorhanden, prüfe ob Tags sichtbar sind
    if tag_config:
        from shared.preprocess import RULE_TAG_MAP
        
        for tag in tags:
            tag_lower = tag.lower()
            is_visible = True
            
            # Prüfe ob Tag direkt versteckt ist
            if tag_config.get(tag_lower, {}).get('hide', False):
                is_visible = False
            else:
                # Prüfe ob Gruppe versteckt ist
                for group_id, group_tags in RULE_TAG_MAP.items():
                    if tag in group_tags:
                        if tag_config.get(group_id, {}).get('hide', False):
                            is_visible = False
                            break
            
            # Wenn mindestens EIN Tag sichtbar ist, return True
            if is_visible:
                return True
        
        # ALLE Tags sind versteckt
        return False
    
    # Keine tag_config: Tags sind sichtbar
    return True

# ----------------------- Sprecher-Handling -----------------------
def pop_leading_speaker(tokens):
    """
    Entfernt führenden Sprecher (Λυσ:, [Χορ:]) und liefert (name, rest_tokens).
    Berücksichtigt auch Sprecher, die nach einer Zeilennummer (z.B. "(2)") kommen.
    """
    if not tokens: return '', tokens
    
    # Prüfe erstes Token
    t0 = tokens[0]
    if RE_SPK_BRACKET.match(t0):
        inner = t0[1:-1]
        if inner.endswith(':'): inner = inner[:-1]
        return inner.strip(), tokens[1:]
    if RE_SPEAKER_GR.match(t0):
        return t0.rstrip(':'), tokens[1:]
    
    # Prüfe zweites Token (falls erstes Token eine Zeilennummer ist)
    if len(tokens) >= 2:
        t1 = tokens[1]
        # Prüfe ob t0 eine Zeilennummer ist (z.B. "(2)" oder "(123a)")
        if re.match(r'^\(\d+[a-z]*\)$', t0):
            if RE_SPK_BRACKET.match(t1):
                inner = t1[1:-1]
                if inner.endswith(':'): inner = inner[:-1]
                # Entferne Sprecher, behalte Zeilennummer
                return inner.strip(), [t0] + tokens[2:]
            if RE_SPEAKER_GR.match(t1):
                # Entferne Sprecher, behalte Zeilennummer
                return t1.rstrip(':'), [t0] + tokens[2:]
    
    return '', tokens

# ----------------------- Markup & Messen -----------------------
def _inline_badge(text_inside:str, base_font_size:float) -> str:
    small = max(4.0, base_font_size * INLINE_SCALE)
    return f'<font name="DejaVu" color="{INLINE_COLOR_HEX}" size="{small:.2f}">[{xml_escape(text_inside)}]</font>'

def format_token_markup(token:str, *, reverse_mode:bool=False, is_greek_row:bool, base_font_size:float, color_mode:str="COLOR") -> str:
    # DEBUG: Print incoming token if it contains color symbols
    if any(sym in token for sym in ['$', '+', '-']):
        print(f"DEBUG format_token_markup: INPUT token='{token}', color_mode={color_mode}", flush=True)
    
    raw = (token or '').strip()
    if not raw: return ''
    # Inline-Marken wie "(1)" → kleines graues Badge (nur in GR-Zeile sichtbar)
    if RE_INLINE_MARK.match(raw):
        inner = re.sub(r'^\(|\)$', '', raw).replace(' ', '')
        return _inline_badge(inner, base_font_size) if is_greek_row else ''

    # Farbcodes - finde den ersten Farbcode im Token
    # WICHTIG: Händisch gesetzte Farbsymbole werden IMMER in bunten Farben dargestellt,
    # auch in BlackWhite-PDFs! (Die automatischen Farben werden in BlackWhite entfernt,
    # aber händisch gesetzte Symbole bleiben farbig für Hervorhebungen)
    color = None
    color_pos = -1
    
    # IMMER bunte Farben für händisch gesetzte Symbole (auch in BLACK_WHITE!):
    if '#' in raw:
        color_pos = raw.find('#'); color = '#FF0000'  # Rot
    elif '+' in raw:
        color_pos = raw.find('+'); color = '#1E90FF'  # Blau
    elif '-' in raw:
        color_pos = raw.find('-'); color = '#228B22'  # Grün
    elif '§' in raw:
        color_pos = raw.find('§'); color = '#9370DB'  # Violett
    elif '$' in raw:
        color_pos = raw.find('$'); color = '#FFA500'  # Orange

    # DEBUG: Print color detection
    if any(sym in token for sym in ['$', '+', '-']):
        print(f"DEBUG format_token_markup: color={color}, color_pos={color_pos}, raw='{raw}'", flush=True)

    # Entferne den Farbcode aus dem raw-Text
    if color_pos >= 0:
        raw = raw[:color_pos] + raw[color_pos+1:]
        # DEBUG: Print after removal
        if any(sym in token for sym in ['$', '+', '-']):
            print(f"DEBUG format_token_markup: After removal raw='{raw}'", flush=True)

    # Stärke/Tags
    strong = '~' in raw; raw = raw.replace('~','')
    tags = RE_TAG.findall(raw)
    core = RE_TAG_NAKED.sub('', raw).strip()

    aorS_present = 'AorS' in tags
    if aorS_present: strong = True

    is_bold = False; star_visible = False
    # DEAKTIVIERT: Sternchen (*) sollen NICHT mehr automatisch entfernt/hinzugefügt werden!
    # User will * Symbole im translinear.txt direkt verwenden können.
    # if '*' in core:
    #     if strong and not aorS_present:  # Bei AorS keine Sternchen anzeigen
    #         star_visible = True
    #     else:
    #         if reverse_mode and not is_greek_row: star_visible = True
    #         else: is_bold = True
    #     core = core.replace('*','')
    # if strong and not star_visible and not aorS_present:  # Bei AorS keine Sternchen hinzufügen
    #     core += '*'
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
    
    result = ''.join(parts)
    
    # DEBUG: Print final output
    if any(sym in token for sym in ['$', '+', '-']):
        print(f"DEBUG format_token_markup: OUTPUT result='{result}'", flush=True)
    
    return result

def visible_measure_token(token:str, *, font:str, size:float, is_greek_row:bool=True, reverse_mode:bool=False) -> float:
    t = (token or '').strip()
    if not t: return 0.0
    if RE_INLINE_MARK.match(t):
        inner = re.sub(r'^\(|\)$', '', t).replace(' ', '')
        w = _measure_string(f'[{inner}]', font, size)
        return w + SAFE_EPS_PT + INLINE_EXTRA_PT + 2*CELL_PAD_LR_PT

    # Entferne ALLE Farbcodes (#, +, -, §, $) aus dem Token
    for color_char in ['#', '+', '-', '§', '$']:
        t = t.replace(color_char, '')
    strong = '~' in t; t = t.replace('~','')

    tags = RE_TAG.findall(t)
    core = RE_TAG_NAKED.sub('', t).strip()

    star_visible = False
    aorS_present = 'AorS' in tags
    if aorS_present: strong = True
    # DEAKTIVIERT: Sternchen (*) sollen NICHT mehr automatisch entfernt/hinzugefügt werden!
    # User will * Symbole im translinear.txt direkt verwenden können.
    # if '*' in core:
    #     if strong and not aorS_present:  # Bei AorS keine Sternchen anzeigen
    #         star_visible = True
    #     core = core.replace('*','')
    # if strong and not star_visible and not aorS_present:  # Bei AorS keine Sternchen hinzufügen
    #     core += '*'

    w = _measure_string(core.replace('-', '|'), font, size)

    # NEU: gleiche Partition wie in der Darstellung
    sups, subs, rest = _partition_tags_for_display(tags, is_greek_row=is_greek_row)

    # Breite der sichtbaren Tags addieren (beschränkt)
    kept = sups + subs + rest
    if kept:
        tag_width = TAG_WIDTH_FACTOR * _measure_string(''.join(kept), font, size)
        max_tag_width = min(tag_width, TAG_MAX_WIDTH_PT)
        w += max_tag_width

    # Reduzierter Sicherheitspuffer für Tags (für kompaktere TAG-PDFs)
    # Stark reduziert für dichteren Text ohne Überlappungen
    tag_safety = 0.8  # Zusätzlicher Puffer für Tags (stark reduziert)
    if kept:
        tag_safety += 0.4  # Weniger zusätzlicher Puffer, wenn Tags sichtbar sind
    safe_eps = max(SAFE_EPS_PT, tag_safety)
    return w + safe_eps + 2*CELL_PAD_LR_PT
    
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
            
            # KRITISCH: Prüfe ob `/` überhaupt AUSSERHALB von Klammern () vorkommt!
            # `/` innerhalb von Tags wie (M/P) soll NICHT splitten!
            import re
            
            # Extrahiere alles außerhalb von Klammern
            outside_parens = re.sub(r'\([^)]*\)', '', token)
            
            # Hat das Token `/` AUSSERHALB von Klammern?
            if '/' not in outside_parens:
                # Kein echtes Straußlogik-Token → nur in ERSTE Zeile, sonst leer!
                if alt_idx == 0:
                    new_line.append(token)
                else:
                    new_line.append('')  # Alternative Zeilen: leer für Tokens ohne `/`
                continue
            
            # Echtes Straußlogik-Token: Extrahiere Tags/Marker VOR dem Splitten
            prefix_tags = ''
            core_token = token
            
            # Extrahiere Tag-Prefix (z.B. "nomen#", "verb$", "nomenD#")
            tag_match = re.match(r'^([a-zA-Z_]+[#\$§+\-])', core_token)
            if tag_match:
                prefix_tags = tag_match.group(1)
                core_token = core_token[len(prefix_tags):]
            
            # Extrahiere Suffix-Tags (alles in Klammern am Ende)
            suffix_tags = ''
            tag_suffix_match = re.search(r'(\([^)]*\))+$', core_token)
            if tag_suffix_match:
                suffix_tags = tag_suffix_match.group(0)
                core_token = core_token[:tag_suffix_match.start()]
            
            # Splitte Core-Token (ohne Tags) an `/`
            alternatives = core_token.split('/')
            
            # Wähle die entsprechende Alternative und füge Tags wieder hinzu
            if alt_idx < len(alternatives):
                chosen_alt = alternatives[alt_idx]
                # WICHTIG: Füge Prefix UND Suffix wieder hinzu!
                final_token = prefix_tags + chosen_alt + suffix_tags if chosen_alt else ''
                new_line.append(final_token)
            else:
                # Kein weiteres `/` in diesem Token - verwende leeren String
                new_line.append('')
        
        result.append(new_line)
    
    return result

def expand_line_with_slashes(line: str) -> list[str]:
    """
    Expandiert eine einzelne Zeile mit `/` in mehrere Zeilen für STRAUßLOGIK.
    
    Input:  "(4) das/TEST/TEST Wort Seiendes/being ..."
    Output: ["(4) das Wort Seiendes ...",
             "(4) TEST  being ...",
             "(4) TEST  ..."
            ]
    
    Wichtig: Tokens OHNE `/` bleiben nur in der ersten Zeile!
    """
    import re
    
    # Extrahiere Zeilennummer
    match = re.match(r'^(\s*\(\d+[a-z]?\)\s*)(.*)', line)
    if not match:
        return [line]
    
    prefix = match.group(1)  # "(4) "
    content = match.group(2)  # "das/TEST Wort ..."
    
    # Tokenisiere die Zeile (einfach: split by space)
    tokens = content.split()
    
    # Expandiere jeden Token
    token_alternatives = []
    max_alts = 1
    
    for token in tokens:
        # Prüfe ob `/` außerhalb von Klammern existiert
        outside_parens = re.sub(r'\([^)]*\)', '', token)
        
        if '/' not in outside_parens:
            # Kein `/` → nur in erster Zeile
            token_alternatives.append([token])
        else:
            # Hat `/` → expandiere
            # Extrahiere Prefix-Tags/Symbole (z.B. "nomen#" oder "#" oder "+" oder "$")
            # WICHTIG: Symbole (#, +, -, §, $) können ALLEINE stehen (ohne Buchstaben davor)!
            prefix_tag = ''
            core = token
            
            # Prüfe zuerst auf Farbsymbole ALLEINE am Anfang
            if core and core[0] in ['#', '+', '-', '§', '$']:
                prefix_tag = core[0]
                core = core[1:]
            else:
                # Prüfe auf Buchstaben + Symbol (z.B. "nomen#")
                tag_match = re.match(r'^([a-zA-Z_]+[#\$§+\-])', core)
                if tag_match:
                    prefix_tag = tag_match.group(1)
                    core = core[len(prefix_tag):]
            
            # Extrahiere Suffix-Tags (z.B. "(Art)(N)")
            suffix_tag = ''
            suffix_match = re.search(r'(\([^)]*\))+$', core)
            if suffix_match:
                suffix_tag = suffix_match.group(0)
                core = core[:suffix_match.start()]
            
            # Splitte an `/`
            parts = core.split('/')
            
            # DEBUG: Print if token contains test symbols
            if any(test in token for test in ['TestEinzeiler', 'Zweizeiler', 'testonly']):
                print(f"DEBUG expand_line_with_slashes: token='{token}', prefix_tag='{prefix_tag}', suffix_tag='{suffix_tag}', parts={parts}", flush=True)
            
            # KRITISCHER FIX: Jedes part kann sein EIGENES Farbsymbol haben!
            # Beispiel: #der/+der/-der → ['der', '+der', '-der']
            # Das erste part bekommt prefix_tag (#), die anderen haben ihre eigenen Symbole!
            alts = []
            for idx, part in enumerate(parts):
                if not part:
                    alts.append('')
                    continue
                
                # Prüfe ob dieses part sein EIGENES Farbsymbol hat
                if part and part[0] in ['#', '+', '-', '§', '$']:
                    # Part hat eigenes Symbol → verwende ES (nicht prefix_tag!)
                    # KRITISCH: Entferne MEHRFACHE Farbsymbole (z.B. "$#Zweizeiler" → "$Zweizeiler")
                    # Dies kann passieren wenn Preprocess Wortart-Symbole hinzufügt NACH dem Alternativ-Symbol
                    first_symbol = part[0]
                    rest = part[1:]
                    
                    # DEBUG: Print before cleanup
                    if any(test in part for test in ['TestEinzeiler', 'Zweizeiler', '+Test', '$Zwei']):
                        print(f"DEBUG expand CLEANUP: part='{part}', first_symbol='{first_symbol}', rest='{rest}'", flush=True)
                    
                    # Entferne alle weiteren Farbsymbole am Anfang
                    while rest and rest[0] in ['#', '+', '-', '§', '$']:
                        rest = rest[1:]
                    
                    # DEBUG: Print after cleanup
                    if any(test in part for test in ['TestEinzeiler', 'Zweizeiler', '+Test', '$Zwei']):
                        print(f"DEBUG expand CLEANUP: after rest='{rest}', final='{first_symbol + rest + suffix_tag}'", flush=True)
                    
                    alts.append(first_symbol + rest + suffix_tag)
                elif idx == 0:
                    # Erstes part → verwende prefix_tag vom ursprünglichen Token
                    alts.append(prefix_tag + part + suffix_tag)
                else:
                    # Weitere parts OHNE eigenes Symbol → kein prefix_tag!
                    alts.append(part + suffix_tag)
            
            token_alternatives.append(alts)
            max_alts = max(max_alts, len(alts))
            
            # DEBUG: Print results
            if any(test in token for test in ['TestEinzeiler', 'Zweizeiler', 'testonly']):
                print(f"DEBUG expand_line_with_slashes: alts={alts}, max_alts={max_alts}", flush=True)
    
    # Erstelle die Zeilen
    result_lines = []
    for alt_idx in range(max_alts):
        alt_tokens = []
        for tok_alts in token_alternatives:
            if alt_idx < len(tok_alts):
                token = tok_alts[alt_idx]
                # Wenn Token leer ist, verwende Platzhalter (wird später entfernt)
                alt_tokens.append(token if token else '∅')  # ∅ = leerer Platzhalter
            else:
                alt_tokens.append('∅')  # Platzhalter für leere Position
        
        # Erstelle Zeile
        line_content = ' '.join(alt_tokens)
        result_lines.append(prefix + line_content)
    
    return result_lines

def expand_triple_with_slashes(gr_line: str, de_line: str, en_line: str) -> tuple[list[str], list[str], list[str]]:
    """
    STRAUßLOGIK: Expandiert eine Gruppe von 3 Zeilen (GR, DE, EN) ZUSAMMEN!
    
    WICHTIG: Alle 3 Zeilen werden auf die MAXIMALE Anzahl Alternativen expandiert!
    
    KRITISCH: Alternative-Gruppen bekommen Suffixe (a, b, c, ...) damit sie als
    SEPARATE pair-Blöcke verarbeitet werden und NICHT zu einem Flow zusammengefasst!
    
    Input:
        gr_line: "(4) griechisch..."
        de_line: "(4) das/TEST Wort..."    <- 2 Alternativen
        en_line: "(4) the word..."          <- 1 Alternative
    
    Output:
        gr_lines: ["(4) griechisch...", "(4a) griechisch..."]  <- 2x wiederholt, zweite mit Suffix!
        de_lines: ["(4) das Wort...", "(4a) TEST ..."]          <- 2 Alternativen
        en_lines: ["(4) the word...", "(4a) ..."]               <- 1 Alternative + Leerzeile
    
    → Ergebnis: 2 SEPARATE pair-Blöcke (wegen unterschiedlicher Nummern)!
    """
    import re
    
    # KRITISCHER FIX: Extrahiere Sprecher VOR der Expansion!
    # Der Sprecher [Χρεμύλος:] würde sonst in erste Zeile bleiben, aber in Alternativen zu ∅ werden
    # → Führt zu falscher Spalten-Alignierung in Tabelle!
    speaker_prefix = ''
    
    # Funktion zum Entfernen des Sprechers aus einer Zeile
    def remove_speaker(line):
        if not line:
            return line, ''
        # Suche nach Sprecher-Pattern: [Name:] oder Name: nach Zeilennummer
        # Beispiel: "(17) [Χρεμύλος:] τῶν μὲν..."
        # WICHTIG: [Name:] - der Doppelpunkt ist INNERHALB der eckigen Klammern!
        speaker_match = re.match(r'^(\s*\(\d+[a-z]?\)\s*)(\[.+?:\]\s*|([^\s:]+):\s*)(.*)', line)
        if speaker_match:
            line_prefix = speaker_match.group(1)  # "(17) "
            speaker_part = speaker_match.group(2)  # "[Χρεμύλος:] " oder "Name: "
            rest = speaker_match.group(4)  # Rest der Zeile
            
            line_without_speaker = line_prefix + rest
            return line_without_speaker, speaker_part
        return line, ''
    
    # Entferne Sprecher aus ALLEN Zeilen (GR, DE, EN)
    gr_line, gr_speaker = remove_speaker(gr_line)
    de_line, de_speaker = remove_speaker(de_line)
    en_line, en_speaker = remove_speaker(en_line)
    
    # Verwende den ersten nicht-leeren Sprecher
    speaker_prefix = gr_speaker or de_speaker or en_speaker
    
    # Expandiere alle 3 Zeilen einzeln (ohne Sprecher!)
    gr_expanded = expand_line_with_slashes(gr_line) if gr_line else ['']
    de_expanded = expand_line_with_slashes(de_line) if de_line else ['']
    en_expanded = expand_line_with_slashes(en_line) if en_line else ['']
    
    # WICHTIG: Sprecher wird NICHT wieder zu den Token-Listen hinzugefügt!
    # Er wird separat über flow_block['speaker'] behandelt und in einer eigenen Spalte gerendert.
    # Wenn wir ihn hier wieder hinzufügen würden, hätten wir eine Verschiebung der Spalten!
    
    # Finde maximale Anzahl Alternativen
    max_alts = max(len(gr_expanded), len(de_expanded), len(en_expanded))
    
    # KRITISCH: Bei 2-sprachigen Zeilen (GR ohne Slashes, nur DE mit Slashes):
    # GR-Zeile muss auf max_alts expandiert werden, mit ∅ Platzhaltern!
    # Nicht nur leere Zeilen "(3) ", sondern "(3) ∅ ∅ ∅ ..."!
    
    if len(gr_expanded) == 1 and max_alts > 1 and gr_line:
        # GR hat nur 1 Zeile, aber max_alts > 1 → expandiere GR mit ∅
        # Extrahiere Tokens aus der ersten GR-Zeile
        import re
        match = re.match(r'^(\s*\(\d+[a-z]?\)\s*)(.*)', gr_expanded[0])
        if match:
            prefix = match.group(1)
            content = match.group(2)
            tokens = content.split()
            num_tokens = len(tokens)
            
            
            # Erstelle Alternative-Zeilen mit ∅
            # KRITISCH: Füge ein griechisches Zeichen hinzu, damit der Parser es als GR erkennt!
            # Verwende ͺ (Greek Ano Teleia) - fast unsichtbar, aber griechisch!
            for _ in range(max_alts - 1):
                alt_line = prefix + 'ͺ ' + ' '.join(['∅'] * num_tokens)  # ͺ markiert als griechisch
                gr_expanded.append(alt_line)
    
    # Erweitere alle Listen auf max_alts (mit Leerzeilen als Fallback)
    def pad_to_max(lines_list, max_count, line_prefix):
        """Erweitert Liste auf max_count Zeilen (mit leeren Zeilen)"""
        if not lines_list:
            lines_list = ['']
        
        # Extrahiere Zeilennummer aus erster Zeile
        if lines_list[0]:
            match = re.match(r'^(\s*\(\d+[a-z]?\)\s*)', lines_list[0])
            prefix = match.group(1) if match else ''
        else:
            prefix = line_prefix if line_prefix else ''
        
        while len(lines_list) < max_count:
            # Füge leere Zeile hinzu (nur Zeilennummer, kein Inhalt)
            lines_list.append(prefix)
        
        return lines_list
    
    # Extrahiere Zeilennummer-Prefix (für Padding)
    line_prefix = ''
    for line in [gr_line, de_line, en_line]:
        if line:
            match = re.match(r'^(\s*\(\d+[a-z]?\)\s*)', line)
            if match:
                line_prefix = match.group(1)
                break
    
    gr_lines = pad_to_max(gr_expanded, max_alts, line_prefix)
    de_lines = pad_to_max(de_expanded, max_alts, line_prefix)
    en_lines = pad_to_max(en_expanded, max_alts, line_prefix)
    
    # FIX: Füge den Sprecher wieder zur ERSTEN GR-Zeile hinzu!
    # Der Sprecher soll NUR in der ersten Zeile erscheinen (wie im Original)
    # Wichtig: Füge ihn NACH der Zeilennummer, aber VOR den Tokens ein!
    if speaker_prefix and gr_lines:
        # Extrahiere Zeilennummer und Rest aus der ersten GR-Zeile
        first_gr = gr_lines[0]
        match = re.match(r'^(\s*\(\d+[a-z]?\)\s*)(.*)', first_gr)
        if match:
            line_num_prefix = match.group(1)  # "(3) "
            rest_of_line = match.group(2)      # "εἶεν(Prä)..."
            # Setze die Zeile mit Sprecher zusammen
            gr_lines[0] = f"{line_num_prefix}{speaker_prefix}{rest_of_line}"
    
    # FLIEßTEXT + STRAUßLOGIK: KEINE Suffixe mehr!
    # Alle Alternativen behalten die GLEICHE Zeilennummer → werden zu EINEM pair-Block!
    # Später erkennen wir die Multi-Row Struktur anhand der Anzahl der GR/DE/EN Zeilen!
    
    return gr_lines, de_lines, en_lines

def process_input_file(fname:str):
    """
    Vereinheitlichte Parser-Phase:
    - Unterstützt Prosa-Features (Titel {}, =-Überschriften, §, Zitate/Quellen).
    - Erkennt Sprecher in GR/DE und erzeugt später (bei Bedarf) eine Sprecher-Spalte.
    - GR/DE-Paare werden wie gehabt gebildet; reflow zu Streams in group_pairs_into_flows().
    """
    with open(fname, encoding='utf-8') as f:
        raw = [ln.rstrip('\n') for ln in f]
    
    # ═══════════════════════════════════════════════════════════════════
    # STRAUßLOGIK: Expandiere GRUPPEN von 3 Zeilen (GR, DE, EN) zusammen!
    # ═══════════════════════════════════════════════════════════════════
    # WICHTIG: Dies passiert VOR allem anderen Parsing!
    # Wenn alle 3 Zeilen die gleiche Nummer haben, expandieren wir sie ZUSAMMEN
    # auf die MAXIMALE Anzahl Alternativen!
    
    expanded_raw = []
    i = 0
    while i < len(raw):
        line = raw[i]
        
        # Prüfe ob dies eine nummerierte Zeile ist
        line_match = re.match(r'^\s*\(\d+[a-z]?\)', line)
        if not line_match:
            # Keine Zeilennummer → einfach übernehmen
            expanded_raw.append(line)
            i += 1
            continue
        
        # Extrahiere Zeilennummer
        line_num_match = re.match(r'^\s*\((\d+[a-z]?)\)', line)
        if not line_num_match:
            expanded_raw.append(line)
            i += 1
            continue
        
        line_num = line_num_match.group(1)
        
        # Prüfe ob die nächsten 2 Zeilen die GLEICHE Nummer haben
        next1 = raw[i+1] if i+1 < len(raw) else ''
        next2 = raw[i+2] if i+2 < len(raw) else ''
        
        next1_match = re.match(r'^\s*\((\d+[a-z]?)\)', next1) if next1 else None
        next2_match = re.match(r'^\s*\((\d+[a-z]?)\)', next2) if next2 else None
        
        # WICHTIG: Überspringe Kommentare! Kommentare enden mit 'k' wie (8k) oder (125-129k)
        # Sie sollen NICHT für Slash-Expansion verwendet werden!
        is_comment = line_num.endswith('k') or line_num.endswith('K')
        next1_is_comment = next1_match and (next1_match.group(1).endswith('k') or next1_match.group(1).endswith('K')) if next1_match else False
        next2_is_comment = next2_match and (next2_match.group(1).endswith('k') or next2_match.group(1).endswith('K')) if next2_match else False
        
        # Wenn IRGENDEINE Zeile ein Kommentar ist → KEINE Expansion!
        if is_comment or next1_is_comment or next2_is_comment:
            expanded_raw.append(line)
            i += 1
            continue
        
        # Prüfe ob mindestens EINE der 3 Zeilen `/` enthält
        has_slash = '/' in line or (next1 and '/' in next1) or (next2 and '/' in next2)
        
        # FALL 1: Alle 3 Zeilen haben gleiche Nummer UND mindestens eine hat `/`
        if (next1_match and next1_match.group(1) == line_num and
            next2_match and next2_match.group(1) == line_num and
            has_slash):
            # Expandiere alle 3 zusammen!
            gr_lines, de_lines, en_lines = expand_triple_with_slashes(line, next1, next2)
            
            # FLIEßTEXT + STRAUßLOGIK: Füge ALLE Zeilen OHNE Marker hinzu!
            # Sie werden automatisch zum gleichen Flow zusammengefügt!
            # Keine {STRAUSS_ALT} Marker mehr → alles fließt zusammen!
            
            # Füge alle Zeilen hinzu (interleaved: GR1, DE1, EN1, GR2, DE2, EN2, ...)
            for j in range(len(gr_lines)):
                # ALLE Gruppen OHNE Marker → fließen zusammen!
                expanded_raw.append(gr_lines[j])
                expanded_raw.append(de_lines[j])
                expanded_raw.append(en_lines[j])
            
            print(f"STRAUßLOGIK + FLIEßTEXT: Expandierte 3 Zeilen ({line_num}) → {len(gr_lines)} Gruppen (fließen zusammen!)", flush=True)
            i += 3  # Überspringe alle 3 Zeilen
            continue
        
        # FALL 2: Nur 2 Zeilen mit gleicher Nummer (GR + DE, kein EN)
        if next1_match and next1_match.group(1) == line_num and has_slash:
            # Expandiere GR + DE zusammen (EN ist leer)
            gr_lines, de_lines, en_lines = expand_triple_with_slashes(line, next1, '')
            
            # FLIEßTEXT + STRAUßLOGIK: Füge ALLE Zeilen OHNE Marker hinzu!
            # Sie werden automatisch zum gleichen Flow zusammengefügt!
            # Keine {STRAUSS_ALT} Marker mehr → alles fließt zusammen!
            
            # Füge alle Zeilen hinzu (interleaved: GR1, DE1, EN1, GR2, DE2, EN2, ...)
            # Bei 2-sprachig ist EN immer leer ('')
            # WICHTIG: Füge ein Leerzeichen zu leeren EN-Zeilen hinzu, damit sie nicht übersprungen werden!
            for j in range(len(gr_lines)):
                expanded_raw.append(gr_lines[j])
                expanded_raw.append(de_lines[j])
                # KRITISCH: Wenn EN leer ist, füge die Zeilennummer mit einem Leerzeichen hinzu!
                # Sonst wird die Zeile beim Parsing als leer übersprungen!
                en_line = en_lines[j]
                if not en_line or en_line.strip() == '' or en_line.strip() == line_num or en_line.strip() == f'({line_num})':
                    # EN ist leer → füge Zeilennummer + Leerzeichen hinzu
                    en_line = f'({line_num}) '
                expanded_raw.append(en_line)
            
            print(f"STRAUßLOGIK + FLIEßTEXT: Expandierte 2 Zeilen ({line_num}) → {len(gr_lines)} Gruppen (fließen zusammen!)", flush=True)
            i += 2
            continue
        
        # FALL 3: Einzelne Zeile mit `/`
        if has_slash:
            # Expandiere nur diese eine Zeile
            expanded_lines = expand_line_with_slashes(line)
            expanded_raw.extend(expanded_lines)
            print(f"STRAUßLOGIK: Expandierte 1 Zeile ({line_num}) → {len(expanded_lines)} Zeilen", flush=True)
            i += 1
            continue
        
        # FALL 4: Keine Expansion nötig
        expanded_raw.append(line)
        i += 1
    
    raw = expanded_raw
    
    # LATEINISCH: (N)(Abl) → (Abl) Transformation für ALLE Zeilen
    # Prüfe ob es ein lateinischer Text ist (erste nicht-leere Zeile)
    is_latin_text = False
    for line in raw:
        if line.strip() and not is_empty_or_sep(line.strip()):
            is_latin_text = is_latin_line(line)
            break
    
    if is_latin_text:
        raw = [re.sub(r'\(N\)\(Abl\)', '(Abl)', ln) for ln in raw]

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
            # Group 1 ist die optionale Zeilennummer, Group 2 ist der Quelltext
            source_text = m.group(2).strip() if m.lastindex >= 2 else m.group(1).strip()
            blocks += [{'type':'blank'}, {'type':'source', 'text': source_text}, {'type':'blank'}]
            i += 1; continue

        if RE_QUOTE_START.match(line):
            # [Zitat Anfang] Marker - nicht im PDF anzeigen, nur für Parsing
            blocks.append({'type':'blank'}); i += 1
            qlines = []
            while i < len(raw) and not RE_QUOTE_END.match((raw[i] or '').strip()):
                qlines.append(raw[i].rstrip('\n')); i += 1
            blocks.append({'type':'quote', 'lines': qlines})
            if i < len(raw) and RE_QUOTE_END.match((raw[i] or '').strip()):
                # [Zitat Ende] Marker - nicht im PDF anzeigen
                blocks.append({'type':'blank'}); i += 1
            continue

        if RE_SOURCE_START.match(line):
            # [Quelle Anfang] Marker - nicht im PDF anzeigen, nur für Parsing
            blocks.append({'type':'blank'}); i += 1
            slines = []
            while i < len(raw) and not RE_SOURCE_END.match((raw[i] or '').strip()):
                slines.append((raw[i] or '').strip()); i += 1
            blocks.append({'type':'source', 'text': ' '.join([s for s in slines if s])})
            if i < len(raw) and RE_SOURCE_END.match((raw[i] or '').strip()):
                # [Quelle Ende] Marker - nicht im PDF anzeigen
                blocks.append({'type':'blank'}); i += 1
            continue

        # NEUE LOGIK: Zeilennummern-basierte Paarbildung
        # FLIEßTEXT: KEINE Marker mehr! Alle Zeilen mit gleicher Nummer werden zusammengefügt!
        
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
        
        # WICHTIG: Prüfe ob der Inhalt (nach Entfernen der Zeilennummer) ein Marker ist
        # Wenn ja, behandle ihn als Marker, nicht als normale Zeile
        if line_num is not None and line_content:
            # Prüfe ob line_content ein Zitat/Quelle-Marker ist
            if RE_QUOTE_START.match(line_content):
                # [Zitat Anfang] Marker
                blocks.append({'type':'blank'}); i += 1
                qlines = []
                while i < len(raw) and not RE_QUOTE_END.match((raw[i] or '').strip()):
                    qlines.append(raw[i].rstrip('\n')); i += 1
                blocks.append({'type':'quote', 'lines': qlines})
                if i < len(raw) and RE_QUOTE_END.match((raw[i] or '').strip()):
                    blocks.append({'type':'blank'}); i += 1
                continue
            elif RE_SOURCE_START.match(line_content):
                # [Quelle Anfang] Marker
                blocks.append({'type':'blank'}); i += 1
                slines = []
                while i < len(raw) and not RE_SOURCE_END.match((raw[i] or '').strip()):
                    slines.append((raw[i] or '').strip()); i += 1
                blocks.append({'type':'source', 'text': ' '.join([s for s in slines if s])})
                if i < len(raw) and RE_SOURCE_END.match((raw[i] or '').strip()):
                    blocks.append({'type':'blank'}); i += 1
                continue
            elif RE_QUOTE_END.match(line_content) or RE_SOURCE_END.match(line_content):
                # [Zitat Ende] oder [Quelle Ende] Marker - überspringen
                i += 1
                continue
        
        if line_num is not None:
            # Wir haben eine Zeilennummer gefunden
            # FLIEßTEXT: Sammle ALLE Zeilen mit gleicher Nummer (STRAUßLOGIK fließt zusammen!)
            lines_with_same_num = [line]
            j = i + 1
            
            while j < len(raw):
                next_line = (raw[j] or '').strip()
                if is_empty_or_sep(next_line):
                    j += 1
                    continue
                
                # Prüfe Zeilennummer
                next_num, _ = extract_line_number(next_line)
                if next_num == line_num:
                    lines_with_same_num.append(next_line)
                    j += 1
                else:
                    break
            
            # Jetzt haben wir alle Zeilen mit derselber Nummer
            num_lines = len(lines_with_same_num)
            
            # DEBUG: Zeige die erste Zeile dieser Gruppe
            if line_num == "3":  # Nur für Zeile 3 (Σωκράτης)
                print(f"DEBUG process_input_file: line_num={line_num}, num_lines={num_lines}", flush=True)
                print(f"DEBUG process_input_file: lines_with_same_num[0]='{lines_with_same_num[0][:120]}'", flush=True)
            
            # NEU: Spezielle Behandlung für Insertionszeilen (i)
            # Bei konsekutiven (i)-Zeilen müssen wir sie in Gruppen aufteilen
            if is_insertion_line(line_num):
                # Erkenne, ob der Text 2-sprachig oder 3-sprachig ist
                expected_lines_per_insertion = detect_language_count_from_context(raw, i)
                
                print(f"DEBUG Prosa: Insertionszeile erkannt: {line_num}, {num_lines} Zeilen gefunden, erwarte {expected_lines_per_insertion} Zeilen pro Insertion")
                
                # Gruppiere die Zeilen in Blöcke von expected_lines_per_insertion
                insertion_idx = 0
                while insertion_idx < num_lines:
                    # Hole die nächsten expected_lines_per_insertion Zeilen
                    insertion_group = lines_with_same_num[insertion_idx:insertion_idx + expected_lines_per_insertion]
                    
                    if len(insertion_group) < expected_lines_per_insertion:
                        # Nicht genug Zeilen für eine vollständige Insertion - überspringe
                        print(f"WARNING Prosa: Unvollständige Insertionsgruppe: {len(insertion_group)} Zeilen, erwartet {expected_lines_per_insertion}")
                        break
                    
                    # Verarbeite diese Insertionsgruppe
                    gr_line = _remove_line_number_from_line(insertion_group[0])
                    de_line = _remove_line_number_from_line(_remove_speaker_from_line(insertion_group[1]))
                    en_line = ''
                    if expected_lines_per_insertion >= 3 and len(insertion_group) >= 3:
                        en_line = _remove_line_number_from_line(_remove_speaker_from_line(insertion_group[2]))
                    
                    # Speichere die ursprüngliche Zeilennummer
                    base_num = int(re.match(r'^(\d+)', line_num).group(1)) if re.match(r'^(\d+)', line_num) else None
                    blocks.append({'type':'pair', 'gr': gr_line, 'de': de_line, 'en': en_line, 'base': base_num})
                    
                    insertion_idx += expected_lines_per_insertion
                
                i = j
                continue
            
            if num_lines == 2:
                # Zweisprachig: gr/lat_de oder gr/lat_en
                # WICHTIG: Erste Zeile = IMMER antike Sprache, zweite = IMMER Übersetzung
                # UNABHÄNGIG von Sprechern oder Buchstaben!
                # WICHTIG: Sprecher nur in der antiken Zeile behalten, aus Übersetzung entfernen
                # NEU: Zeilennummern aus allen Zeilen entfernen (nur für Prosa)
                gr_line = _remove_line_number_from_line(lines_with_same_num[0])
                
                # DEBUG: Zeige gr_line nach _remove_line_number_from_line
                if line_num == "3":
                    print(f"DEBUG process_input_file: AFTER _remove_line_number_from_line: gr_line='{gr_line[:120]}'", flush=True)
                
                de_line = _remove_line_number_from_line(_remove_speaker_from_line(lines_with_same_num[1]))
                # NEU: Speichere die ursprüngliche Zeilennummer für Hinterlegung (ohne sie im PDF anzuzeigen)
                base_num = int(re.match(r'^(\d+)', line_num).group(1)) if re.match(r'^(\d+)', line_num) else None
                pair_block = {'type':'pair', 'gr': gr_line, 'de': de_line, 'en': '', 'base': base_num}
                blocks.append(pair_block)
                i = j
                continue
            elif num_lines >= 3:
                # STRAUßLOGIK + FLIEßTEXT: Wenn wir MEHR als 3 Zeilen haben, sind das ALTERNATIVEN!
                # Teile sie in Gruppen von 3 auf und erstelle MEHRERE pair-Blöcke!
                # Diese werden später zu Multi-Row-Struktur zusammengefügt!
                
                # Anzahl der Gruppen: num_lines / 3 (aufgerundet)
                num_groups = (num_lines + 2) // 3  # Ganzzahl-Division mit Aufrunden
                
                # NEU: Speichere die ursprüngliche Zeilennummer für Hinterlegung
                base_num = int(re.match(r'^(\d+)', line_num).group(1)) if re.match(r'^(\d+)', line_num) else None
                
                # Erstelle für jede Gruppe einen pair-Block
                for group_idx in range(num_groups):
                    start_idx = group_idx * 3
                    
                    # Extrahiere GR, DE, EN für diese Gruppe
                    gr_line = _remove_line_number_from_line(lines_with_same_num[start_idx]) if start_idx < num_lines else ''
                    de_line = _remove_line_number_from_line(_remove_speaker_from_line(lines_with_same_num[start_idx + 1])) if start_idx + 1 < num_lines else ''
                    en_line = _remove_line_number_from_line(_remove_speaker_from_line(lines_with_same_num[start_idx + 2])) if start_idx + 2 < num_lines else ''
                    
                    pair_block = {'type':'pair', 'gr': gr_line, 'de': de_line, 'en': en_line, 'base': base_num}
                    
                    # Markiere Alternativen (alle außer erste Gruppe)
                    if group_idx > 0:
                        pair_block['_is_strauss_alt'] = True
                    
                    blocks.append(pair_block)
                
                i = j
                continue
            elif num_lines == 1:
                # Nur eine Zeile mit dieser Nummer - könnte Strukturzeile oder Fehler sein
                # Als Fallback: Prüfe Sprachinhalt (OHNE Sprecher zu berücksichtigen!)
                line_without_speaker = _strip_speaker_prefix_for_classify(line_content)
                # NEU: Speichere die ursprüngliche Zeilennummer für Hinterlegung
                base_num = int(re.match(r'^(\d+)', line_num).group(1)) if re.match(r'^(\d+)', line_num) else None
                if is_greek_line(line_without_speaker) or is_latin_line(line_without_speaker):
                    # Antike Sprache ohne Übersetzung
                    pair_block = {'type':'pair', 'gr': line, 'de': '', 'en': '', 'base': base_num}
                else:
                    # Deutsche Zeile ohne antike Sprache (ungewöhnlich)
                    pair_block = {'type':'pair', 'gr': '', 'de': line, 'en': '', 'base': base_num}
                # NEU: Einzelne Zeilen sind NIEMALS Alternativen (nur bei num_lines >= 3)
                # if is_strauss_alternative: <- Diese Variable existiert hier nicht!
                #     pair_block['_is_strauss_alt'] = True
                blocks.append(pair_block)
                i = j
                continue
        else:
            # Keine Zeilennummer gefunden - Strukturzeile oder Überschrift
            # Fallback auf alte Logik (nur für Zeilen OHNE Zeilennummer)
            line_cls = _strip_speaker_prefix_for_classify(line)
            if is_greek_line(line_cls) or is_latin_line(line_cls):
                gr = line; i += 1
                while i < len(raw) and is_empty_or_sep(raw[i]): i += 1
                de_line = ''
                if i < len(raw):
                    cand = (raw[i] or '').strip()
                    cand_cls = _strip_speaker_prefix_for_classify(cand)
                    if not (is_greek_line(cand_cls) or is_latin_line(cand_cls)):
                        de_line = cand
                        i += 1
                blocks.append({'type':'pair', 'gr': gr, 'de': de_line, 'en': ''})
                continue
            
            blocks.append({'type':'pair', 'gr': '', 'de': line, 'en': ''}); i += 1

    # WICHTIG: Filtere pair-Blöcke heraus, die nur Zitat/Quelle-Marker enthalten
    # Diese Zeilen sollen nicht im PDF erscheinen
    filtered_blocks = []
    marker_pattern = re.compile(r'\[(?:Zitat|Quelle)\s*(?:Anfang|Ende)\]', re.IGNORECASE)
    skipped_count = 0
    
    for b in blocks:
        if b['type'] == 'pair':
            gr = (b.get('gr') or '').strip()
            de = (b.get('de') or '').strip()
            en = (b.get('en') or '').strip()
            
            # Entferne Zeilennummer aus gr und de
            gr_no_num = re.sub(r'^\s*\(\d+[a-z]?\)\s*', '', gr).strip()
            de_no_num = re.sub(r'^\s*\(\d+[a-z]?\)\s*', '', de).strip()
            
            # Prüfe ob die Zeile NUR Marker enthält (nichts anderes außer Marker)
            gr_no_marker = marker_pattern.sub('', gr_no_num).strip()
            de_no_marker = marker_pattern.sub('', de_no_num).strip()
            
            # Wenn nach Entfernung von Zeilennummer UND Markern nichts übrig bleibt, überspringe
            if not gr_no_marker and not de_no_marker and not en:
                skipped_count += 1
                continue
        
        filtered_blocks.append(b)
    
    # Debug-Ausgabe entfernt - Filterung funktioniert korrekt
    
    return filtered_blocks

def group_pairs_into_flows(blocks):
    """
    Reflow zu „Flows" (fortlaufender Tokenstrom) mit optionaler
    - Sprecher-Info (falls im GR-Teil erkennbar)
    - §-Absatzlabel (para_label)
    Schnittpunkte: neuer Sprecher oder para_set / Strukturblöcke.
    
    SPEZIAL: Lyrik-Modus für Boethius "De consolatione philosophiae"
    - Bei === Lyrik === wird die Zeilenstruktur bewahrt (wie bei Zitaten)
    - Keine § Paragraphen-Marker im Lyrik-Bereich
    
    FLIEßTEXT-LOGIK: Aufeinanderfolgende STRAUßLOGIK-Blöcke haben kein § zwischen sich.
    """
    print(f"DEBUG group_pairs_into_flows: Called with {len(blocks)} blocks", flush=True)
    flows = []
    buf_gr, buf_de, buf_en = [], [], []
    current_para_label = None
    active_speaker = ''
    any_speaker_seen = False
    in_lyrik_mode = False  # NEU: Lyrik-Modus für Boethius
    current_base_num = None  # NEU: Zeilennummer für Hinterlegung
    accumulated_comments = []  # NEU: Sammle Kommentare von pair-Blöcken für flow-Block
    after_comment = False  # NEU: Track ob wir gerade nach einem Kommentar sind
    
    # STRAUßLOGIK + FLIEßTEXT: Speichere Token-Zeilen separat für Multi-Row!
    strauss_gr_rows = []  # Liste von Token-Listen: [[tok1, tok2, ...], [alt1, alt2, ...], ...]
    strauss_de_rows = []
    strauss_en_rows = []
    
    # FLIEßTEXT: Merke, ob wir schon einen flow-Block im aktuellen § Absatz hatten
    is_first_flow_in_para = True

    def flush():
        nonlocal buf_gr, buf_de, buf_en, active_speaker, current_base_num, accumulated_comments, after_comment
        nonlocal strauss_gr_rows, strauss_de_rows, strauss_en_rows, is_first_flow_in_para
        
        if buf_gr or buf_de or buf_en:
            flow_block = {'type':'flow','gr_tokens':buf_gr,'de_tokens':buf_de,'en_tokens':buf_en,
                          'para_label': current_para_label, 'speaker': active_speaker,
                          'base': current_base_num}
            
            # WICHTIG: Übertrage Kommentare vom letzten pair-Block zum flow-Block
            if accumulated_comments:
                flow_block['comments'] = list(accumulated_comments)
                accumulated_comments = []  # Reset nach Übertragung
            
            # STRAUßLOGIK: Wenn wir Multi-Row-Daten haben, übertrage sie!
            current_has_strauss = bool(strauss_gr_rows)
            if current_has_strauss:
                flow_block['_has_strauss'] = True
                flow_block['_gr_rows'] = [buf_gr] + strauss_gr_rows  # Erste Zeile + Alternativen
                flow_block['_de_rows'] = [buf_de] + strauss_de_rows
                flow_block['_en_rows'] = [buf_en] + strauss_en_rows
                
                strauss_gr_rows, strauss_de_rows, strauss_en_rows = [], [], []  # Reset
            
            # FLIEßTEXT: Wenn NICHT der erste Block im § → kein § Symbol!
            # (Nur der allererste Block im Absatz bekommt das § Symbol)
            if not is_first_flow_in_para and current_para_label:
                flow_block['para_label'] = ''  # Unterdrücke § Symbol für FLIEßTEXT
                print(f"FLIEßTEXT: Suppressing § symbol for continuation in same paragraph", flush=True)
            
            # Ab jetzt sind wir nicht mehr der erste Block
            is_first_flow_in_para = False
            
            flows.append(flow_block)
            buf_gr, buf_de, buf_en = [], [], []
            current_base_num = None  # Reset für nächsten Block
            after_comment = False  # Nach flush() sind wir nicht mehr "nach Kommentar"



    for b in blocks:
        t = b['type']
        
        # NEU: Lyrik-Modus für Boethius - Erkenne === Lyrik === Überschrift
        if t == 'h2_eq':
            flush()
            heading_text = b.get('text', '').lower()
            # DEBUG: print(f"  [DEBUG] h2_eq gefunden: '{heading_text}'")
            if 'lyrik' in heading_text:
                in_lyrik_mode = True
                print("  → Lyrik-Modus AKTIVIERT (Zeilenstruktur wird bewahrt, keine § Marker)")
            elif in_lyrik_mode:
                # Andere h2_eq Überschrift nach Lyrik → Lyrik-Modus beenden
                in_lyrik_mode = False
                print("  → Lyrik-Modus BEENDET")
            flows.append(b)
            continue
        
        # Bei anderen Überschriften (h1_eq, h3_eq, section, title) Lyrik-Modus beenden
        if t in ('h1_eq', 'h3_eq', 'section', 'title'):
            flush()
            if in_lyrik_mode:
                in_lyrik_mode = False
                print("  → Lyrik-Modus beendet")
            flows.append(b)
            continue
        
        if t == 'pair':
            # FLIEßTEXT: ALLE pair-Blöcke fließen zusammen (keine Sonderbehandlung mehr!)
            
            # Normale pair-Verarbeitung
            # Tokenisiere falls nötig
            if 'gr_tokens' in b:
                gt = list(b['gr_tokens']) if b.get('gr_tokens') else []
                # DEBUG: Zeige ORIGINAL gr_tokens aus dem Block (VOR pop_leading_speaker)
                if gt:
                    print(f"DEBUG: Original gr_tokens from block: {gt[:5]}", flush=True)
            else:
                gr_text = b.get('gr', '')
                # DEBUG: Zeige GR-Text VOR tokenize
                if gr_text:
                    print(f"DEBUG: GR text before tokenize: '{gr_text[:80]}'", flush=True)
                gt = tokenize(gr_text) if gr_text else []
            
            if 'de_tokens' in b:
                dt = list(b['de_tokens']) if b.get('de_tokens') else []
            else:
                dt = tokenize(b['de']) if b.get('de') else []
            
            if 'en_tokens' in b:
                et = list(b['en_tokens']) if b.get('en_tokens') else []
            else:
                et = tokenize(b['en']) if b.get('en') else []
            
            # WICHTIG: Sammle Kommentare vom pair-Block für späteren flow-Block
            pair_comments = b.get('comments', [])
            if pair_comments:
                accumulated_comments.extend(pair_comments)
            
            # NEU: base_num für Hinterlegung speichern (erstes base_num wird verwendet)
            if current_base_num is None:
                current_base_num = b.get('base')

            # DE: Inline-Marken unsichtbar machen
            dt = ['' if RE_INLINE_MARK.match(x or '') else (x or '') for x in dt]
            # EN: Inline-Marken unsichtbar machen
            et = ['' if RE_INLINE_MARK.match(x or '') else (x or '') for x in et]

            # Sprecher nur aus der antiken Zeile (GR) entfernen
            # DE und EN Zeilen haben bereits keine Sprecher mehr (wurden beim Parsing entfernt)
            # DEBUG: Zeige erste 3 Tokens BEVOR pop_leading_speaker()
            print(f"DEBUG: Before pop_leading_speaker: gt[:3]={gt[:3]}", flush=True)
            sp_gr, gt = pop_leading_speaker(gt)
            print(f"DEBUG: Extracted speaker='{sp_gr}', remaining tokens={len(gt)}", flush=True)
            if sp_gr:
                any_speaker_seen = True
                print(f"DEBUG: any_speaker_seen set to True! active_speaker={active_speaker}", flush=True)
                if sp_gr != active_speaker:
                    flush()
                    active_speaker = sp_gr
                after_comment = False  # Neuer Sprecher gefunden → nicht mehr "nach Kommentar"
            else:
                # KEIN Sprecher extrahiert
                # UNTERSCHEIDE 2 Fälle:
                # 1. Nach Kommentar → Sprecher zurücksetzen (sonst erscheint alter Sprecher nach Kommentar)
                # 2. Mitten im FLIEßTEXT → Sprecher beibehalten (mehrere Zeilen gehören zum selben Sprecher)
                if after_comment and active_speaker is not None:
                    # Nach Kommentar + alter Sprecher noch aktiv → zurücksetzen
                    flush()
                    active_speaker = None
                    after_comment = False
                # Sonst: FLIEßTEXT → active_speaker bleibt wie er ist!

            # Breitenangleich: Jetzt mit 3 Zeilen
            max_len = max(len(gt), len(dt), len(et))
            if len(gt) < max_len: gt += [''] * (max_len - len(gt))
            if len(dt) < max_len: dt += [''] * (max_len - len(dt))
            if len(et) < max_len: et += [''] * (max_len - len(et))

            # NEU: Lyrik-Modus → Zeilenstruktur bewahren (isolierte pair-blocks)
            if in_lyrik_mode:
                # WICHTIG: Flush vorherigen Flow
                flush()
                
                # Erstelle isolierten pair-Block für Lyrik-Zeile
                base_num = b.get('base')
                pair_block = {
                    'type': 'pair',
                    'gr_tokens': gt,
                    'de_tokens': dt,
                    'en_tokens': et,
                    'para_label': '',  # Kein § bei Lyrik
                    'speaker': active_speaker,
                    'base': base_num,
                    '_is_lyrik': True
                }
                flows.append(pair_block)
                continue
            
            # Normale Zeile: Prüfe auf para/speaker
            has_para_or_speaker = ('para' in b or 'speaker' in b)
            
            # STRAUßLOGIK: base_num_changed für separate Blöcke (Alternativen-Positionierung!)
            # WICHTIG: Wir MÜSSEN pro Zeile flushen, damit Alternativen korrekt zugeordnet werden!
            base_num = b.get('base')
            base_num_changed = (current_base_num is not None and base_num is not None and base_num != current_base_num)
            
            if has_para_or_speaker or base_num_changed:
                # Neue Zeile mit para/speaker ODER neue Zeilennummer → vorherige Gruppe abschließen
                if buf_gr or buf_de or buf_en:
                    flush()
            
            # Aktualisiere current_base_num
            if current_base_num is None and base_num is not None:
                current_base_num = base_num
            
            # STRAUßLOGIK + FLIEßTEXT: Wenn Alternative, speichere als separate Zeile!
            is_strauss_alt = b.get('_is_strauss_alt', False)
            if is_strauss_alt:
                # Alternative → Speichere als separate Zeile (NICHT zum Hauptbuffer)
                # WICHTIG: Bei 2-sprachigen Alternativen (GR leer, nur DE hat Slashes):
                # Fülle GR mit ∅ Platzhaltern, damit die Spalten aligniert sind!
                
                # KRITISCH: Prüfe ob gt leer ist ODER nur leere Strings enthält!
                if (not gt or all(not token for token in gt)) and dt:
                    # GR ist leer oder nur leere Strings, aber DE hat Tokens → Fülle GR mit ∅
                    gt = ['∅'] * len(dt)
                if (not gt or all(not token for token in gt)) and et:
                    # GR ist leer oder nur leere Strings, aber EN hat Tokens → Fülle GR mit ∅
                    gt = ['∅'] * len(et)
                
                strauss_gr_rows.append(list(gt))
                strauss_de_rows.append(list(dt))
                strauss_en_rows.append(list(et))
            else:
                # Normale Zeile → Zum Hauptbuffer hinzufügen
                buf_gr.extend(gt)
                buf_de.extend(dt)
                buf_en.extend(et)
            
            continue

        if t == 'para_set':
            flush()
            # Speichere para_label immer, aber im Lyrik-Modus nicht verwenden
            current_para_label = b['label']
            # FLIEßTEXT: Neuer § Absatz → nächster Block ist wieder der erste
            is_first_flow_in_para = True
            continue

        # NEU: Kommentare → Flush nur bei Sprecherwechsel, nicht bei JEDEM Kommentar!
        # KRITISCHER FIX: Kommentare müssen gerendert werden, aber active_speaker darf
        # nicht verloren gehen (Sprecher steht nur in der ersten Zeile, nicht in jeder!)
        if t == 'comment':
            # WICHTIG: Nur flushen wenn bereits Tokens gesammelt wurden
            # Dadurch erscheint der Kommentar NACH dem zugehörigen Text
            if buf_gr or buf_de or buf_en:
                flush()
            # Kommentar als separaten Block hinzufügen (OHNE active_speaker zu ändern!)
            flows.append(b)
            # WICHTIG: Markiere dass wir gerade nach einem Kommentar sind
            # Dies erlaubt uns den Sprecher zurückzusetzen wenn die nächste Zeile keinen hat
            after_comment = True
            # active_speaker bleibt erhalten → wird erst beim nächsten pair-Block geprüft!
            continue

        # Strukturelle Blöcke → vorher flushen
        flush(); flows.append(b)

    flush()
    # Meta: merken, ob überhaupt Sprecher existieren
    print(f"DEBUG: Flushing flows. any_speaker_seen={any_speaker_seen}", flush=True)
    flows.append({'type':'_meta', 'any_speaker': any_speaker_seen})
    return flows

def merge_strauss_alternatives(flows):
    """
    STRAUßLOGIK + FLIEßTEXT: Diese Funktion macht jetzt NICHTS mehr!
    
    Die Multi-Row-Struktur wird bereits in group_pairs_into_flows() erstellt!
    - Normale Zeilen → Hauptbuffer (fließen zusammen)
    - Alternativen → Separate Zeilen (strauss_XX_rows)
    - Beim flush() → Multi-Row-Struktur (_has_strauss, _de_rows, _en_rows)
    
    Diese Funktion existiert nur noch aus Kompatibilitätsgründen.
    """
    print(f"STRAUßLOGIK + FLIEßTEXT: Multi-Row-Struktur wurde bereits in group_pairs_into_flows() erstellt!", flush=True)
    return flows

# ----------------------- Tabellenbau -----------------------
def build_tables_for_alternatives(gr_tokens_alternatives, de_tokens_alternatives, en_tokens_alternatives, *,
                                  doc_width_pt, token_gr_style, token_de_style,
                                  para_display, para_width_pt, style_para,
                                  speaker_display, speaker_width_pt, style_speaker,
                                  table_halign='LEFT',
                                  hide_pipes=False, tag_config=None, tag_mode="TAGS", color_mode="COLOR"):
    """
    STRAUßLOGIK mit SLICE-LOGIC für Fließtext-Umbrüche!
    
    KRITISCH: Wenn die Zeile zu breit ist, wird sie in MEHRERE Tabellen aufgeteilt (Slices)!
    Jede Slice-Tabelle hat dann wieder mehrere Zeilen (GR + DE-Alternativen + EN-Alternativen).
    
    GENAU WIE BEI NORMALEM FLOW!
    """
    from reportlab.platypus import Table, TableStyle, Paragraph
    from reportlab.lib import colors
    from reportlab.pdfbase.pdfmetrics import stringWidth
    from reportlab.lib.styles import ParagraphStyle
    
    # WICHTIG: Leading (Zeilenabstand) für Alternativen mit <br/> Tags!
    # Verwende fontSize * 1.1 - OPTIMAL für konsistente, enge Abstände
    # (1.0 zu eng → Überlappung, 1.1 → PERFEKT, 1.2+ → zu viel Abstand)
    token_gr_style_tight = ParagraphStyle('TokGR_Tight', parent=token_gr_style,
        leading=token_gr_style.fontSize * 1.1,  # 1.1× = OPTIMAL ENGER ABSTAND
        spaceBefore=0, spaceAfter=0)
    token_de_style_tight = ParagraphStyle('TokDE_Tight', parent=token_de_style,
        leading=token_de_style.fontSize * 1.1,  # 1.1× = OPTIMAL ENGER ABSTAND
        spaceBefore=0, spaceAfter=0)
    
    # Handle None inputs
    if gr_tokens_alternatives is None:
        gr_tokens_alternatives = [[]]
    if de_tokens_alternatives is None:
        de_tokens_alternatives = [[]]
    if en_tokens_alternatives is None:
        en_tokens_alternatives = [[]]
    
    # Bestimme maximale Anzahl Alternativen und Spalten
    max_alts_gr = len(gr_tokens_alternatives)
    max_alts_de = len(de_tokens_alternatives)
    max_alts_en = len(en_tokens_alternatives)
    
    # Berechne maximale Spaltenanzahl über ALLE Alternativen
    cols = 0
    for gr_alt in gr_tokens_alternatives:
        cols = max(cols, len(gr_alt))
    for de_alt in de_tokens_alternatives:
        cols = max(cols, len(de_alt))
    for en_alt in en_tokens_alternatives:
        cols = max(cols, len(en_alt))
    
    if cols == 0:
        return []
    
    # Angleiche alle Alternativen auf gleiche Länge
    gr_lines = [alt + [''] * (cols - len(alt)) for alt in gr_tokens_alternatives]
    de_lines = [alt + [''] * (cols - len(alt)) for alt in de_tokens_alternatives]
    en_lines = [alt + [''] * (cols - len(alt)) for alt in en_tokens_alternatives]
    
    # ═══════════════════════════════════════════════════════════════════
    # SPALTENBREITEN-BERECHNUNG (per-column, widest token)
    # ═══════════════════════════════════════════════════════════════════
    gr_font = token_gr_style.fontName
    gr_size = token_gr_style.fontSize
    de_font = token_de_style.fontName
    de_size = token_de_style.fontSize
    
    token_widths = []
    for k in range(cols):
        # Finde breitestes Token in Spalte k über alle Alternativen
        gr_token = ''
        for gr_line in gr_lines:
            if k < len(gr_line) and gr_line[k]:
                if len(gr_line[k]) > len(gr_token):
                    gr_token = gr_line[k]
        
        de_token = ''
        for de_line in de_lines:
            if k < len(de_line) and de_line[k]:
                display_tok = de_line[k].replace('|', ' ') if hide_pipes else de_line[k]
                if len(display_tok) > len(de_token):
                    de_token = display_tok
        
        en_token = ''
        for en_line in en_lines:
            if k < len(en_line) and en_line[k]:
                display_tok = en_line[k].replace('|', ' ') if hide_pipes else en_line[k]
                if len(display_tok) > len(en_token):
                    en_token = display_tok
        
        # Messe Breiten
        try:
            gr_width = visible_measure_token(gr_token, font=gr_font, size=gr_size, 
                                            is_greek_row=True) if gr_token else 0.0
        except:
            gr_width = stringWidth(gr_token, gr_font, gr_size) if gr_token else 0.0
        
        try:
            de_width = visible_measure_token(de_token, font=de_font, size=de_size,
                                            is_greek_row=False) if de_token else 0.0
        except:
            de_width = stringWidth(de_token, de_font, de_size) if de_token else 0.0
        
        try:
            en_width = visible_measure_token(en_token, font=de_font, size=de_size,
                                            is_greek_row=False) if en_token else 0.0
        except:
            en_width = stringWidth(en_token, de_font, de_size) if en_token else 0.0
        
        max_width = max(gr_width, de_width, en_width)
        padding = 2.5 if tag_mode == "TAGS" else 2.0
        token_widths.append(max_width + padding)
    
    # ═══════════════════════════════════════════════════════════════════
    # SLICE-LOGIK: Teile Tokens in Slices (wie in normalem Flow!)
    # ═══════════════════════════════════════════════════════════════════
    avail_w = doc_width_pt
    if speaker_display and speaker_width_pt > 0:
        avail_w -= (speaker_width_pt + 2.0)  # SPEAKER_GAP_MM
    if para_display and para_width_pt > 0:
        avail_w -= (para_width_pt + 2.0)  # PARA_GAP_MM
    
    tables = []
    i = 0
    first_slice = True
    
    while i < cols:
        # Pack-Phase: Füge Spalten hinzu bis avail_w überschritten
        acc, j = 0.0, i
        while j < cols:
            w = token_widths[j]
            if acc + w > avail_w and j > i:
                break
            acc += w
            j += 1
        
        # Slice: i bis j (exklusiv)
        slice_gr_lines = [line[i:j] for line in gr_lines]
        slice_de_lines = [line[i:j] for line in de_lines]
        slice_en_lines = [line[i:j] for line in en_lines]
        slice_widths = token_widths[i:j]
        
        # ═══════════════════════════════════════════════════════════════════
        # FILTER: Entferne Spalten, die NUR ∅ enthalten (leere Platzhalter)
        # ═══════════════════════════════════════════════════════════════════
        num_cols = len(slice_gr_lines[0]) if slice_gr_lines else 0
        cols_to_keep = []
        
        for col_idx in range(num_cols):
            # Prüfe ob diese Spalte irgendein nicht-leeres Token hat
            has_content = False
            
            # Prüfe GR-Zeilen
            for gr_line in slice_gr_lines:
                if col_idx < len(gr_line):
                    tok = gr_line[col_idx]
                    # WICHTIG: ∅ auch mit Farbsymbolen erkennen
                    is_placeholder = (tok == '∅' or tok in ('#∅', '$∅', '+∅', '-∅', '§∅'))
                    if tok and not is_placeholder:
                        has_content = True
                        break
            
            # Prüfe DE-Zeilen
            if not has_content:
                for de_line in slice_de_lines:
                    if col_idx < len(de_line):
                        tok = de_line[col_idx]
                        is_placeholder = (tok == '∅' or tok in ('#∅', '$∅', '+∅', '-∅', '§∅'))
                        if tok and not is_placeholder:
                            has_content = True
                            break
            
            # Prüfe EN-Zeilen
            if not has_content:
                for en_line in slice_en_lines:
                    if col_idx < len(en_line):
                        tok = en_line[col_idx]
                        is_placeholder = (tok == '∅' or tok in ('#∅', '$∅', '+∅', '-∅', '§∅'))
                        if tok and not is_placeholder:
                            has_content = True
                            break
            
            if has_content:
                cols_to_keep.append(col_idx)
        
        # Filtere Spalten: Behalte nur nicht-leere
        if cols_to_keep:
            slice_gr_lines = [[line[c] for c in cols_to_keep if c < len(line)] for line in slice_gr_lines]
            slice_de_lines = [[line[c] for c in cols_to_keep if c < len(line)] for line in slice_de_lines]
            slice_en_lines = [[line[c] for c in cols_to_keep if c < len(line)] for line in slice_en_lines]
            slice_widths = [slice_widths[c] for c in cols_to_keep if c < len(slice_widths)]
        
        # ═══════════════════════════════════════════════════════════════════
        # FARB-EXTRAKTION für diesen Slice
        # ═══════════════════════════════════════════════════════════════════
        def extract_color_from_html(html: str) -> str:
            """Extrahiert Farbcode aus HTML-String"""
            if not html:
                return None
            # Suche nach <font color="...">
            import re
            match = re.search(r'<font\s+color="([^"]+)"', html, re.IGNORECASE)
            if match:
                return match.group(1)
            return None
        
        # WICHTIG: Formatiere GR-Tokens und extrahiere Farben aus dem HTML!
        # Das ist kritisch, weil format_token_markup() die Tag-Farben hinzufügt
        # STRAUßLOGIK: Sammle Farben aus ALLEN GR-Zeilen (nicht nur erste!)
        gr_formatted_tokens = []
        gr_colors = []
        
        # Bestimme Anzahl Spalten
        num_cols = max(len(line) for line in slice_gr_lines) if slice_gr_lines else 0
        
        if slice_gr_lines and len(slice_gr_lines) > 0:
            # Für jede Spalte: Sammle Farbe aus ALLEN GR-Zeilen (erste nicht-leere gewinnt)
            for col_idx in range(num_cols):
                color = None
                formatted_first = ''
                
                # Durchsuche ALLE GR-Zeilen nach Farbe für diese Spalte
                for row_idx, gr_line in enumerate(slice_gr_lines):
                    if col_idx < len(gr_line):
                        tok = gr_line[col_idx]
                        # WICHTIG: ∅ auch mit Farbsymbolen erkennen
                        is_placeholder = (tok == '∅' or tok in ('#∅', '$∅', '+∅', '-∅', '§∅'))
                        if tok and not is_placeholder:
                            formatted = format_token_markup(tok, is_greek_row=True, base_font_size=token_gr_style.fontSize, color_mode=color_mode)
                            if not formatted_first:  # Erste nicht-leere für Display speichern
                                formatted_first = formatted
                            # Extrahiere Farbe
                            tok_color = extract_color_from_html(formatted)
                            if tok_color and not color:  # Erste Farbe gewinnt
                                color = tok_color
                
                gr_formatted_tokens.append(formatted_first)
                gr_colors.append(color)
        
        # ═══════════════════════════════════════════════════════════════════
        # TABELLEN-ZEILEN für diesen Slice
        # ═══════════════════════════════════════════════════════════════════
        rows = []
        
        # ============================================================
        # NEUE STRAUßLOGIK: Alternativen IN DERSELBEN ZELLE statt separate Rows!
        # ============================================================
        
        # 1. GR-Zeile: Kombiniere ALLE Alternativen in EINER Zeile
        gr_row = []
        
        # Para-Spalte (nur first_slice)
        if para_display:
            if first_slice:
                gr_row.append(Paragraph(para_display, style_para))
            else:
                gr_row.append('')
        
        # Speaker-Spalte (nur first_slice)
        if speaker_display:
            if first_slice:
                gr_row.append(Paragraph(speaker_display, style_speaker))
            else:
                gr_row.append('')
        
        # GR Tokens: Da alle GR-Zeilen IDENTISCH sind (Wiederholungen), zeige nur die ERSTE!
        num_cols = len(slice_gr_lines[0]) if slice_gr_lines else 0
        for col_idx in range(num_cols):
            # Nehme nur die ERSTE GR-Zeile (alle anderen sind Duplikate)
            if slice_gr_lines and len(slice_gr_lines) > 0:
                gr_line = slice_gr_lines[0]  # NUR die erste Zeile!
                if col_idx < len(gr_line):
                    tok = gr_line[col_idx]
                    # WICHTIG: Filtere ∅ auch mit Farbsymbolen (#∅, $∅, +∅, -∅, §∅)
                    is_placeholder = (tok == '∅' or tok in ('#∅', '$∅', '+∅', '-∅', '§∅'))
                    if tok and not is_placeholder:
                        # Formatiere Token MIT Farben (format_token_markup entfernt # + - § $ automatisch!)
                        formatted = format_token_markup(tok, is_greek_row=True, base_font_size=token_gr_style.fontSize, color_mode=color_mode)
                        gr_row.append(Paragraph(formatted, token_gr_style_tight))
                    else:
                        gr_row.append('')
                else:
                    gr_row.append('')
            else:
                gr_row.append('')
        
        rows.append(gr_row)
        
        # 2. DE+EN-Zeile: KOLLABIERE DE und EN Alternativen (entferne Leerräume!)
        # Für jede Spalte: Sammle ALLE DE und EN Alternativen, entferne ∅, stapel DICHT!
        de_en_row = []
        if para_display:
            de_en_row.append('')
        if speaker_display:
            de_en_row.append('')
        
        for col_idx in range(num_cols):
            # Sammle ALLE Übersetzungen (DE + EN) für diese Spalte
            all_translations = []
            
            # WICHTIG: Extrahiere Farbe vom griechischen Token für diese Spalte!
            gr_color = gr_colors[col_idx] if col_idx < len(gr_colors) else None
            
            # 1. Sammle DE-Alternativen
            for de_idx, de_line in enumerate(slice_de_lines):
                if col_idx < len(de_line):
                    tok = de_line[col_idx]
                    # WICHTIG: Filtere ∅ auch mit Farbsymbolen (#∅, $∅, +∅, -∅, §∅)
                    is_placeholder = (tok == '∅' or tok in ('#∅', '$∅', '+∅', '-∅', '§∅'))
                    if tok and not is_placeholder:
                        display_tok = tok.replace('|', ' ') if hide_pipes else tok
                        
                        # KRITISCHER FIX: Entferne MEHRFACHE Farbsymbole vom Preprocess
                        # Der Preprocess kann Wortart-Symbole hinzufügen NACHDEM bereits ein Alternativ-Symbol da ist
                        # Beispiel: '+TestEinzeiler' → Preprocess fügt '#' hinzu → '+#TestEinzeiler'
                        # Wir wollen nur das ERSTE Symbol behalten (das Alternativ-Symbol!)
                        if display_tok and display_tok[0] in ['#', '+', '-', '§', '$']:
                            first_symbol = display_tok[0]
                            rest = display_tok[1:]
                            # Entferne alle weiteren Farbsymbole am Anfang
                            while rest and rest[0] in ['#', '+', '-', '§', '$']:
                                rest = rest[1:]
                            display_tok = first_symbol + rest
                        
                        # DEBUG: Print token before formatting
                        if any(sym in tok for sym in ['$', '+', '-']):
                            print(f"DEBUG DE alt: tok='{tok}', display_tok='{display_tok}'", flush=True)
                        
                        formatted = format_token_markup(display_tok, is_greek_row=False, base_font_size=token_de_style.fontSize, color_mode=color_mode)
                        
                        # DEBUG: Print after formatting
                        if any(sym in tok for sym in ['$', '+', '-']):
                            print(f"DEBUG DE alt: formatted='{formatted}'", flush=True)
                        
                        # KRITISCH: Nur GR-Farbe übertragen, wenn Token KEINE eigene Farbe hat!
                        # Prüfe ob Token eigene Farbsymbole (#, +, -, §, $) hat
                        has_own_color = any(sym in tok for sym in ['#', '+', '-', '§', '$'])
                        if gr_color and not has_own_color:
                            formatted = f'<font color="{gr_color}">{formatted}</font>'
                        
                        # DEBUG: Print final
                        if any(sym in tok for sym in ['$', '+', '-']):
                            print(f"DEBUG DE alt: final='{formatted}', has_own_color={has_own_color}, gr_color={gr_color}", flush=True)
                        
                        all_translations.append(formatted)
            
            # 2. Sammle EN-Alternativen
            for en_idx, en_line in enumerate(slice_en_lines):
                if col_idx < len(en_line):
                    tok = en_line[col_idx]
                    # WICHTIG: Filtere ∅ auch mit Farbsymbolen (#∅, $∅, +∅, -∅, §∅)
                    is_placeholder = (tok == '∅' or tok in ('#∅', '$∅', '+∅', '-∅', '§∅'))
                    if tok and not is_placeholder:
                        display_tok = tok.replace('|', ' ') if hide_pipes else tok
                        
                        # KRITISCHER FIX: Entferne MEHRFACHE Farbsymbole vom Preprocess (gleich wie bei DE)
                        if display_tok and display_tok[0] in ['#', '+', '-', '§', '$']:
                            first_symbol = display_tok[0]
                            rest = display_tok[1:]
                            while rest and rest[0] in ['#', '+', '-', '§', '$']:
                                rest = rest[1:]
                            display_tok = first_symbol + rest
                        
                        # DEBUG: Print token before formatting
                        if any(sym in tok for sym in ['$', '+', '-']):
                            print(f"DEBUG EN alt: tok='{tok}', display_tok='{display_tok}'", flush=True)
                        
                        formatted = format_token_markup(display_tok, is_greek_row=False, base_font_size=token_de_style.fontSize, color_mode=color_mode)
                        
                        # DEBUG: Print after formatting
                        if any(sym in tok for sym in ['$', '+', '-']):
                            print(f"DEBUG EN alt: formatted='{formatted}'", flush=True)
                        
                        # KRITISCH: Nur GR-Farbe übertragen, wenn Token KEINE eigene Farbe hat!
                        # Prüfe ob Token eigene Farbsymbole (#, +, -, §, $) hat
                        has_own_color = any(sym in tok for sym in ['#', '+', '-', '§', '$'])
                        if gr_color and not has_own_color:
                            formatted = f'<font color="{gr_color}">{formatted}</font>'
                        
                        # DEBUG: Print final
                        if any(sym in tok for sym in ['$', '+', '-']):
                            print(f"DEBUG EN alt: final='{formatted}', has_own_color={has_own_color}, gr_color={gr_color}", flush=True)
                        
                        all_translations.append(formatted)
            
            # KRITISCHER FIX: Erstelle SEPARATE Paragraphs für jede Alternative!
            # <br/> führt zu inkonsistenten Abständen bei vielen Alternativen (πολλὰ Problem)
            # Mit separaten Paragraphs in nested Table: KONSISTENTE, ENGE Abstände!
            if all_translations:
                # Erstelle Paragraph für jede Alternative
                translation_paragraphs = []
                for trans in all_translations:
                    translation_paragraphs.append([Paragraph(trans, token_de_style_tight)])
                
                # Erstelle nested Table mit ALLEN Alternativen als separate Zeilen
                nested_table = Table(translation_paragraphs, colWidths=[None])
                
                # SANFTE Abstände zwischen Alternativen (nicht zu eng für Z/g, aber eng genug)
                # -0.5pt = KOMPROMISS: Vermeidet Z/g Overlaps, bleibt aber schön dicht
                nested_style = TableStyle([
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ('LEFTPADDING', (0, 0), (-1, -1), 0),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), -0.5),  # -0.5pt zwischen Zeilen
                    ('TOPPADDING', (0, 0), (-1, -1), -0.5),     # -0.5pt Standard
                ])
                
                # KRITISCH: Erste Zeile der nested_table darf KEIN negatives TOPPADDING haben!
                # Sonst "zieht" sie sich zur GR-Zeile hoch und überlappt!
                # Die erste Alternative braucht 0pt TOPPADDING, damit gap_pts wirken kann
                if len(translation_paragraphs) > 0:
                    nested_style.add('TOPPADDING', (0, 0), (-1, 0), 0)  # Erste Zeile: 0pt!
                
                nested_table.setStyle(nested_style)
                
                de_en_row.append(nested_table)
            else:
                de_en_row.append('')
        
        rows.append(de_en_row)

        
        if not rows:
            i = j
            first_slice = False
            continue
        
        # Erstelle Spaltenbreiten für diesen Slice
        col_widths = []
        if para_display:
            col_widths.append(para_width_pt)
        if speaker_display:
            col_widths.append(speaker_width_pt)
        col_widths.extend(slice_widths)
        
        # Erstelle Tabelle
        table = Table(rows, colWidths=col_widths, hAlign=table_halign)
        
        # VEREINHEITLICHUNG: Verwende GLEICHEN SPACING-ANSATZ wie build_tables_for_stream!
        # gap_pts sorgt für konsistenten Abstand GR → DE/EN (Tag-abhängig)
        gap_pts = INTRA_PAIR_GAP_MM * mm
        
        table_style_commands = [
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0.5),    # Minimal
            ('RIGHTPADDING', (0, 0), (-1, -1), 0.5),   # Minimal
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),    # Standard: 0
            ('TOPPADDING', (0, 0), (-1, -1), 0),       # Standard: 0
        ]
        
        # KRITISCH: Erste Zeile (GR) bekommt BOTTOMPADDING = gap_pts!
        # Dies sorgt für Abstand zwischen GR und DE/EN Alternativen
        if len(rows) > 0:
            table_style_commands.append(('BOTTOMPADDING', (0, 0), (-1, 0), gap_pts))  # GR → Alternativen
            table_style_commands.append(('TOPPADDING', (0, 0), (-1, 0), 1))  # Abstand zur vorherigen Table
        
        table.setStyle(TableStyle(table_style_commands))
        tables.append(table)
        
        i = j
        first_slice = False
    
    return tables

def build_tables_for_stream(gr_tokens, de_tokens=None, *,
                            doc_width_pt,
                            reverse_mode:bool=False,  # Deprecated, kept for compatibility
                            token_gr_style, token_de_style,
                            para_display:str, para_width_pt:float, style_para,
                            speaker_display:str, speaker_width_pt:float, style_speaker,
                            table_halign='LEFT', italic=False,
                            en_tokens=None,  # NEU: Englische Tokens
                            hide_pipes:bool=False,  # NEU: Pipes (|) in Übersetzungen verstecken
                            tag_config:dict=None,  # NEU: Tag-Konfiguration für individuelle Breitenberechnung
                            base_num:int=None,  # NEU: Zeilennummer für Hinterlegung
                            line_comment_colors:dict=None,  # NEU: Map von Zeilennummern zu Kommentar-Farben
                            block:dict=None,  # NEU: Block-Objekt für comment_token_mask
                            tag_mode:str="TAGS",  # NEU: Tag-Modus (TAGS oder NO_TAGS)
                            color_mode:str="COLOR",  # NEU: Farb-Modus (COLOR oder BLACK_WHITE)
                            gr_tokens_alternatives=None,  # NEU: STRAUßLOGIK - GR Alternativen (Liste von Token-Listen)
                            de_tokens_alternatives=None,  # NEU: STRAUßLOGIK - DE Alternativen (Liste von Token-Listen)
                            en_tokens_alternatives=None,  # NEU: STRAUßLOGIK - EN Alternativen (Liste von Token-Listen)
                            is_quote=False):  # NEU: Ist dies ein Zitat? (für größeres Padding in nested tables)
    if en_tokens is None:
        en_tokens = []
    if de_tokens is None:
        de_tokens = []
    
    # NEU: STRAUßLOGIK - Konvertiere zu Alternativen-Format
    # Wenn *_tokens_alternatives angegeben sind, verwende diese statt einzelner Tokens
    if gr_tokens_alternatives is not None:
        # Verwende GR Alternativen
        print(f"Prosa_Code: build_tables_for_stream() - Using GR alternatives ({len(gr_tokens_alternatives)} lines)", flush=True)
    else:
        # Keine Alternativen - verwende normale gr_tokens als einzige Alternative
        gr_tokens_alternatives = [gr_tokens]
    
    if de_tokens_alternatives is not None:
        # Verwende DE Alternativen
        print(f"Prosa_Code: build_tables_for_stream() - Using DE alternatives ({len(de_tokens_alternatives)} lines)", flush=True)
    else:
        # Keine Alternativen - verwende normale de_tokens als einzige Alternative
        de_tokens_alternatives = [de_tokens]
    
    if en_tokens_alternatives is not None:
        # Verwende EN Alternativen
        pass
    else:
        # Keine Alternativen - verwende normale en_tokens als einzige Alternative
        en_tokens_alternatives = [en_tokens]
    
    # NEU: STRAUßLOGIK - Wenn Alternativen vorhanden, verwende separate Rendering-Funktion
    if (gr_tokens_alternatives and len(gr_tokens_alternatives) > 1) or \
       (de_tokens_alternatives and len(de_tokens_alternatives) > 1) or \
       (en_tokens_alternatives and len(en_tokens_alternatives) > 1):
        # Rufe spezielle Alternativ-Rendering-Funktion auf
        return build_tables_for_alternatives(
            gr_tokens_alternatives=gr_tokens_alternatives,
            de_tokens_alternatives=de_tokens_alternatives,
            en_tokens_alternatives=en_tokens_alternatives,
            doc_width_pt=doc_width_pt,
            token_gr_style=token_gr_style, token_de_style=token_de_style,
            para_display=para_display, para_width_pt=para_width_pt, style_para=style_para,
            speaker_display=speaker_display, speaker_width_pt=speaker_width_pt, style_speaker=style_speaker,
            table_halign=table_halign,
            hide_pipes=hide_pipes,
            tag_config=tag_config,
            tag_mode=tag_mode,
            color_mode=color_mode
        )
    
    # Normaler Fall: KEINE Alternativen (oder nur eine)
    # Verwende erste Alternative als primäre Tokens
    gr_tokens = gr_tokens_alternatives[0] if gr_tokens_alternatives else []
    de_tokens = de_tokens_alternatives[0] if de_tokens_alternatives else []
    en_tokens = en_tokens_alternatives[0] if en_tokens_alternatives else []
    
    # KRITISCH: Erstelle token_de_style_tight für nested tables (multi-row Übersetzungen)
    # WICHTIG: Verwende das Leading vom übergebenen token_de_style!
    # - Für normalen Text: token_de_style hat 1.1× leading (eng, kompakt)
    # - Für Zitate: quote_de_style hat _leading_for() = 1.3× (normal, damit Tags nicht überlappen)
    # Indem wir das Leading vom parent übernehmen, respektieren wir die Intention des Aufrufers!
    token_de_style_tight = ParagraphStyle('TokDE_Tight', parent=token_de_style,
        leading=token_de_style.leading,  # Übernehme Leading vom übergebenen Style!
        spaceBefore=0, spaceAfter=0)
    
    def is_only_symbols_or_stephanus(token: str) -> bool:
        """
        Prüft ob ein Token NUR aus Stephanus-Paginierungen, Interpunktion oder Symbolen besteht.
        Returns True wenn das Token unsichtbar gemacht werden soll (nur Symbole, keine echten Wörter).
        
        Beispiele die True zurückgeben:
        - [535b], [100c], [5125e] (Stephanus-Paginierungen)
        - ?, !, ., ,, :, ;, —, ", ', ..., ?, ?., ?"
        - Kombinationen: [535b],  oder  ?.
        """
        if not token or not token.strip():
            return True
        
        # Entferne alle Whitespace
        cleaned = token.strip()
        
        # Regex: NUR Stephanus-Paginierungen, Interpunktion, Symbole, Klammern, Whitespace
        # Stephanus: [123a], [123b], [123c], [123d], [123e]
        # Symbole: . , ; : ! ? … — " ' * † ‡ § ( ) [ ] 
        only_symbols_pattern = r'^[\[\]\(\).,;:!?…—"\'*†‡§\s]+$'
        
        # Prüfe ob es NUR aus diesen Zeichen besteht
        if re.match(only_symbols_pattern, cleaned):
            return True
        
        # Spezielle Prüfung für Stephanus-Paginierungen: [123a-e]
        stephanus_pattern = r'^\[?\d+[a-e]?\]?$'
        if re.match(stephanus_pattern, cleaned):
            return True
        
        return False
    
    # Wenn KEINE Übersetzungen vorhanden sind (alle ausgeblendet), zeige nur die griechische Zeile
    # WICHTIG: Prüfe mit any() ob irgendein Token nicht-leer ist (nicht nur ob Liste leer ist!)
    if not any(de_tokens) and not any(en_tokens):
        cols = len(gr_tokens)
        gr = gr_tokens[:]
        de = []
        en = []
    else:
        cols = max(len(gr_tokens), len(de_tokens), len(en_tokens))
        gr = gr_tokens[:] + [''] * (cols - len(gr_tokens))
        de = de_tokens[:] + [''] * (cols - len(de_tokens))
        en = en_tokens[:] + [''] * (cols - len(en_tokens))
        
        # Filtere Inline-Marker UND Stephanus/Symbole
        de = ['' if (RE_INLINE_MARK.match(t or '') or is_only_symbols_or_stephanus(t or '')) else (t or '') for t in de]
        en = ['' if (RE_INLINE_MARK.match(t or '') or is_only_symbols_or_stephanus(t or '')) else (t or '') for t in en]

    def get_visible_tags(token: str, tag_config: dict = None) -> list:
        """Gibt die Liste der sichtbaren Tags für ein Token zurück (basierend auf tag_config)."""
        if not tag_config or not token:
            tags = RE_TAG.findall(token)
            return tags
        
        tags = RE_TAG.findall(token)
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
    
    def measure_token_width_with_visibility(token: str, font: str, size: float, 
                                            is_greek_row: bool = False, 
                                            tag_config: dict = None) -> float:
        """
        Berechnet die Breite eines Tokens.
        WICHTIG: Diese Funktion erhält das Token NACH der Vorverarbeitung (apply_tag_visibility).
        Die Tags, die im Token noch vorhanden sind, sind bereits die sichtbaren Tags!
        Wir müssen nicht mehr prüfen, welche Tags versteckt sind - sie sind bereits entfernt.
        """
        if not token:
            return 0.0
        
        # Berechne Breite direkt mit dem Token, wie es ist (Tags wurden bereits entfernt)
        # Das Token enthält bereits nur noch die sichtbaren Tags!
        w_with_remaining_tags = visible_measure_token(token, font=font, size=size, 
                                                      is_greek_row=is_greek_row, reverse_mode=False)
        
        # WICHTIG: Das Token wurde bereits in apply_tag_visibility verarbeitet.
        # Die Tags, die noch im Token vorhanden sind, sind die sichtbaren Tags!
        # Wir müssen einfach nur die Breite des aktuellen Tokens messen.
        
        tags_in_token = RE_TAG.findall(token)
        if tags_in_token:
            # Tags vorhanden → Tag-PDF, verwende gemessene Breite mit angemessenem Puffer
            return w_with_remaining_tags + max(size * 0.03, 0.8)  # Puffer für Tag-PDFs
        else:
            # Keine Tags vorhanden → NoTag-PDF, verwende gemessene Breite mit größerem Puffer
            # ERHÖHT: Besonders wichtig bei Wörtern, wo Tags mit (HideTags) versteckt wurden
            return w_with_remaining_tags + max(size * 0.20, 3.0)  # Erhöht von 0.18/2.8 auf 0.20/3.0
    
    def col_width(k:int) -> float:
        """
        Berechnet die optimale Spaltenbreite für Spalte k.
        
        Die Breitenberechnung berücksichtigt:
        1. Tag-Sichtbarkeit (basierend auf tag_config)
        2. Übersetzungs-Sichtbarkeit (ob DE/EN ausgeblendet sind)
        3. Pipe-Ersetzung (wenn hide_pipes aktiviert ist)
        4. Konsistente Sicherheitspuffer zur Vermeidung von Überlappungen
        
        Returns:
            Die optimale Spaltenbreite in Punkten (pt)
        """
        # Basis-Breite für griechisches Wort (berücksichtigt Tag-Sichtbarkeit)
        gr_token = gr[k] if (k < len(gr) and gr[k]) else ''
        w_gr = measure_token_width_with_visibility(
            gr_token, 
            font=token_gr_style.fontName, 
            size=token_gr_style.fontSize, 
            is_greek_row=True,
            tag_config=tag_config
        ) if gr_token else 0.0
        
        # Berechne DE- und EN-Text (mit/ohne Pipe-Ersetzung)
        de_token_raw = de[k] if (k < len(de) and de[k]) else ''
        en_token_raw = en[k] if (k < len(en) and en[k]) else ''
        
        # Prüfe, ob Übersetzungen tatsächlich sichtbar sind (nicht leer und nicht nur Whitespace)
        de_visible = bool(de_token_raw and de_token_raw.strip())
        en_visible = bool(en_token_raw and en_token_raw.strip())
        translations_visible = de_visible or en_visible
        
        # Bereite DE/EN-Text für Breitenberechnung vor
        if hide_pipes:
            de_text = de_token_raw.replace('|', ' ') if de_token_raw else ''
            en_text = en_token_raw.replace('|', ' ') if en_token_raw else ''
        else:
            de_text = de_token_raw
            en_text = en_token_raw
        
        # Berechne DE- und EN-Breiten
        w_de = 0.0
        w_en = 0.0
        
        if de_visible and de_text:
            w_de = visible_measure_token(de_text, font=token_de_style.fontName, 
                                        size=token_de_style.fontSize, 
                                        is_greek_row=False, reverse_mode=False)
            
            # Zusätzlicher Puffer für Pipe-Ersetzung (wenn hide_pipes aktiviert)
            if hide_pipes and de_token_raw:
                pipe_count = de_token_raw.count('|')
                if pipe_count > 0:
                    # Leerzeichen sind breiter als Pipes: ~0.3x Font-Size Differenz pro Pipe
                    space_vs_pipe_diff = token_de_style.fontSize * 0.3
                    w_de += pipe_count * space_vs_pipe_diff
                    # Zusätzlicher Sicherheitspuffer (10% der Breite) für Pipe-Split-Umbrüche
                    w_de += w_de * 0.10
        
        if en_visible and en_text:
            w_en = visible_measure_token(en_text, font=token_de_style.fontName, 
                                        size=token_de_style.fontSize, 
                                        is_greek_row=False, reverse_mode=False)
            
            # Zusätzlicher Puffer für Pipe-Ersetzung (wenn hide_pipes aktiviert)
            if hide_pipes and en_token_raw:
                pipe_count = en_token_raw.count('|')
                if pipe_count > 0:
                    # Leerzeichen sind breiter als Pipes: ~0.3x Font-Size Differenz pro Pipe
                    space_vs_pipe_diff = token_de_style.fontSize * 0.3
                    w_en += pipe_count * space_vs_pipe_diff
                    # Zusätzlicher Sicherheitspuffer (10% der Breite) für Pipe-Split-Umbrüche
                    w_en += w_en * 0.10
        
        # ROBUSTE BREITENBERECHNUNG BASIEREND AUF SICHTBARKEIT
        
        # Basis-Sicherheitspuffer: Konsistent für alle Wörter (verhindert Überlappungen)
        # WICHTIG: Erhöht auf 8% um alle Wort-Überlappungen zu verhindern (1.2% → 3% → 5% → 8%)
        # Grund: "Blocksatzartige" Darstellung führt zu ungleichen Abständen (manche eng, manche frei)
        # Der MINDEST-Abstand muss hoch genug sein für die engsten Fälle!
        # Bei 10pt Font → 0.8pt Mindestabstand, bei 11pt → 0.88pt
        base_safety = max(token_gr_style.fontSize * 0.08, 0.8)  # 8% der Font-Size oder mindestens 0.8pt
        
        # Wenn Übersetzungen ausgeblendet sind: Nur GR-Breite mit angepasstem Puffer
        if not translations_visible:
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                
            # Nur griechische Zeile sichtbar
            # Prüfe, ob es eine NoTag-Version ist (keine Tags sichtbar durch measure_token_width_with_visibility)
            is_notag = False
            if tag_config is None:
                # Wenn tag_config None ist, wurden alle Tags entfernt (NoTag)
                tags_in_token = RE_TAG.findall(gr_token) if gr_token else []
                is_notag = len(tags_in_token) > 0
            else:
                # Prüfe, ob alle Tags versteckt sind
                visible_tags = get_visible_tags(gr_token, tag_config) if gr_token else []
                all_tags = RE_TAG.findall(gr_token) if gr_token else []
                is_notag = len(all_tags) > 0 and len(visible_tags) == 0
            
            if w_gr > 0:
                # INTELLIGENTE ABSTANDSBERECHNUNG: Berücksichtige tatsächliche Wortlängen!
                # Wenn GR-Wort mit Tags länger als Übersetzungen → reduzierter Abstand (0.5pt)
                # Sonst → normaler Abstand basierend auf Tag-Sichtbarkeit
                extra_buffer = _calculate_dynamic_token_spacing(
                    gr_token=gr_token,
                    de_token=de_token_raw,
                    en_token=en_token_raw,
                    tag_mode=tag_mode,
                    tag_config=tag_config,
                    hide_pipes=hide_pipes,
                    font_gr=token_gr_style.fontName,
                    size_gr=token_gr_style.fontSize,
                    font_de=token_de_style.fontName,
                    size_de=token_de_style.fontSize
                )
                return w_gr + base_safety + extra_buffer
            else:
                return base_safety
        
        # Wenn Übersetzungen sichtbar sind: Maximum von GR, DE, EN
        # Die Spaltenbreite muss alle sichtbaren Zeilen aufnehmen
        max_width = max(w_gr, w_de, w_en)
        
        if max_width > 0:
            # INTELLIGENTE ABSTANDSBERECHNUNG auch mit Übersetzungen!
            # Verwende dynamische Token-Spacing-Logik (wie bei NoTrans)
            extra_buffer = _calculate_dynamic_token_spacing(
                gr_token=gr_token,
                de_token=de_token_raw,
                en_token=en_token_raw,
                tag_mode=tag_mode,
                tag_config=tag_config,
                hide_pipes=hide_pipes,
                font_gr=token_gr_style.fontName,
                size_gr=token_gr_style.fontSize,
                font_de=token_de_style.fontName,
                size_de=token_de_style.fontSize
            )
            return max_width + base_safety + extra_buffer
        else:
            # Fallback: Minimaler Puffer
            return base_safety

    widths = [col_width(k) for k in range(cols)]
    
    # DEFENSIVE: Filtere ungültige Breiten heraus (None, 0, negativ)
    # Dies kann passieren wenn ALLE Übersetzungen versteckt sind
    widths = [max(w or 0.1, 0.1) for w in widths]  # Mindestens 0.1pt pro Spalte
    
    tables, i, first_slice = [], 0, True
    while i < cols:
        acc, j = 0.0, i

        # verfügbare Breite abzüglich optionaler Spalten
        # WICHTIG: IMMER reduzieren, damit alle Zeilen am gleichen Ort beginnen
        # Para/Speaker-Spalten werden nur beim ersten Slice angezeigt, aber der Platz wird immer reserviert
        # für konsistente Ausrichtung aller Zeilen im gleichen Block
        # WICHTIG: SPEAKER_GAP_MM ist jetzt gleich PARA_GAP_MM für konsistente Formatierung
        avail_w = doc_width_pt
        has_speaker = bool(speaker_display) or (block and block.get('speaker'))
        if has_speaker and speaker_width_pt > 0:
            # Diese Zeile HAT einen Sprecher → verwende minimale Spaltenbreite
            effective_speaker_width = min(speaker_width_pt, SPEAKER_COL_MIN_MM*mm)
            effective_speaker_gap = SPEAKER_GAP_MM*mm
            avail_w -= (effective_speaker_width + effective_speaker_gap)
        elif speaker_width_pt > 0:
            # Sprecher-Spalte existiert, aber diese Zeile hat KEINEN Sprecher
            # WICHTIG: Verwende auch hier NUR minimale Breite (3mm), nicht die volle speaker_width_pt!
            # Sonst werden Zeilen ohne Sprecher zu stark gequetscht!
            effective_speaker_width = SPEAKER_COL_MIN_MM*mm
            effective_speaker_gap = SPEAKER_GAP_MM*mm
            avail_w -= (effective_speaker_width + effective_speaker_gap)
        if para_width_pt > 0:
            avail_w -= (para_width_pt + PARA_GAP_MM*mm)

        # Hilfen: prüfe, ob in de[i:j] irgendein sichtbarer Inhalt steckt
        def _has_de_content(i_start: int, i_end_excl: int) -> bool:
            if i_start >= i_end_excl or not de:
                return False
            for k in range(i_start, i_end_excl):
                if k < len(de) and (de[k] or '').strip():
                    return True
            return False

        # finde nächstes Index >= cur, das DE-Inhalt hat
        def _next_de_index(from_idx: int) -> int:
            if not de:
                return cols  # Keine DE-Inhalte vorhanden
            p = from_idx
            while p < cols and p < len(de) and not (de[p] or '').strip():
                p += 1
            return p  # kann == cols sein

        # Normale Pack-Phase
        while j < cols:
            w = widths[j]
            if acc + w > avail_w and j > i:
                break
            acc += w
            j += 1

        # --- SPEZIALFALL: erstes Slice eines Sprecher-Blocks ohne DE-Content
        # Nur ausführen, wenn DE-Übersetzungen vorhanden sind
        if first_slice and de and not _has_de_content(i, j):
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
                        # WICHTIG: Verhindere Swap von wichtigen Tokens wie Fragezeichen, Kommas, etc.
                        if j > i:
                            last_w = widths[j-1]
                            if acc - last_w + widths[k] <= avail_w:
                                # Prüfe, ob das letzte Token im Slice ein wichtiges Satzzeichen ist
                                last_token = gr[j-1] if j-1 < len(gr) else ''
                                is_punctuation = last_token and last_token.strip() in ['.', ',', ';', ':', '?', '!', '·']
                                
                                if not is_punctuation:  # Nur tauschen, wenn es kein Satzzeichen ist
                                    acc = acc - last_w + widths[k]
                                    j = j  # gleicher Endindex, aber wir merken uns später die Spaltenrange i..j und tauschen die Inhalte
                                    # Wir vertauschen die Breitenliste nicht; der Table nimmt die Zelleninhalte.
                                    # Um die Spalte k in das Slice zu bekommen, schieben wir einen "Swap" in die Slicedaten:
                                    if len(gr[i:j]) > 0 and k < len(gr):
                                        gr[i:j][-1], gr[k] = gr[k], gr[i:j][-1]
                                    if len(de[i:j]) > 0 and k < len(de):
                                        de[i:j][-1], de[k] = de[k], de[i:j][-1]
                                    if len(en[i:j]) > 0 and k < len(en):
                                        en[i:j][-1], en[k] = en[k], en[i:j][-1]
                        # Wenn auch das nicht passt, lassen wir es beim bisherigen Slice (optisch wie vorher),
                        # damit das Layout nicht überläuft.

        slice_gr, slice_de, slice_w = gr[i:j], de[i:j], widths[i:j]
        slice_en = en[i:j]  # NEU: Englische Zeile
        slice_start = i  # NEU: Start-Index für tok_idx-Berechnung

        # KRITISCH: Content-Check MUSS NACH Stephanus-Filterung kommen!
        # Die Filterung passiert in Paragraph-Erstellung unten, aber wir müssen hier schon prüfen
        # ob nach Filterung noch Content übrig bleibt

        # linke Zusatzspalten
        # DEFENSIV: Verwende Leerzeichen statt leere Strings für leere Paragraphen (verhindert ReportLab-Crashes)
        sp_cell_gr = Paragraph(xml_escape(speaker_display), style_speaker) if (first_slice and speaker_width_pt>0 and speaker_display) else Paragraph(' ', style_speaker)
        sp_cell_de = Paragraph(' ', style_speaker)
        sp_cell_en = Paragraph(' ', style_speaker)  # NEU: Englische Zeile
        sp_gap_gr  = Paragraph(' ', token_gr_style); sp_gap_de = Paragraph(' ', token_de_style)
        sp_gap_en  = Paragraph(' ', token_de_style)  # NEU: Englische Zeile

        para_cell_gr = Paragraph(xml_escape(para_display), style_para) if (para_width_pt>0 and first_slice and para_display) else Paragraph(' ', style_para)
        para_cell_de = Paragraph(' ', style_para)
        para_cell_en = Paragraph(' ', style_para)  # NEU: Englische Zeile
        para_gap_gr  = Paragraph(' ', token_gr_style); para_gap_de = Paragraph(' ', token_de_style)
        para_gap_en  = Paragraph(' ', token_de_style)  # NEU: Englische Zeile

        def cell_markup(t, is_gr, tok_idx=None):
            # DEFENSIV: Entferne Tags aus Token, falls sie noch vorhanden sind
            # WICHTIG: Übergebe tag_mode und block, damit _strip_tags_from_token korrekt arbeitet
            t_cleaned = _strip_tags_from_token(t, block=block, tok_idx=tok_idx, tag_mode=tag_mode) if t else t
            mk = format_token_markup(t_cleaned, reverse_mode=False, is_greek_row=is_gr,
                                     base_font_size=(token_gr_style.fontSize if is_gr else token_de_style.fontSize),
                                     color_mode=color_mode)
            return f'<i>{mk}</i>' if italic and mk else mk
        
        def replace_pipes_with_spaces(text):
            """Ersetzt | durch Leerzeichen in Übersetzungen für bessere Lesbarkeit"""
            if not text:
                return text
            return text.replace('|', ' ')
        
        def process_translation_token(t):
            """Verarbeitet Übersetzungstoken: Ersetzt | durch Leerzeichen, wenn hide_pipes aktiviert ist"""
            if not t:
                return t
            return replace_pipes_with_spaces(t) if hide_pipes else t

        # KRITISCH: Content-Check VOR Paragraph-Erstellung!
        # Prüfe ob alle Slices nach Stephanus-Filterung + Tag-Stripping leer sind
        # Dies verhindert ReportLab-Crashes durch leere Tabellen
        
        def is_only_symbols_or_stephanus_local(token: str) -> bool:
            """Lokale Kopie der Stephanus-Filter-Funktion"""
            if not token or not token.strip():
                return True
            cleaned = token.strip()
            # Nur Symbole/Interpunktion
            only_symbols_pattern = r'^[\[\]\(\).,;:!?…—"\'*†‡§\s]+$'
            if re.match(only_symbols_pattern, cleaned):
                return True
            # Stephanus-Paginierungen: [123a-e]
            stephanus_pattern = r'^\[?\d+[a-e]?\]?$'
            if re.match(stephanus_pattern, cleaned):
                return True
            return False
        
        def has_visible_content(token, is_translation=False):
            """Prüft ob Token nach ALLEN Filterungen sichtbaren Content hat"""
            if not token or not token.strip():
                return False
            
            # Für Übersetzungen (DE/EN): Prüfe zuerst Stephanus-Filter
            if is_translation:
                if RE_INLINE_MARK.match(token or ''):
                    return False
                if is_only_symbols_or_stephanus_local(token or ''):
                    return False
            
            # Dann Tag-Stripping (für alle Zeilen)
            cleaned = _strip_tags_from_token(token, block=block, tok_idx=None, tag_mode=tag_mode) if token else token
            
            # Nach allen Filterungen, prüfe ob noch sichtbarer Text übrig ist
            if cleaned and cleaned.strip() and cleaned.strip() not in ['', '<i></i>', '<b></b>']:
                return True
            return False
        
        has_gr_visible = any(has_visible_content(t, is_translation=False) for t in slice_gr)
        has_de_visible = any(has_visible_content(process_translation_token(t), is_translation=True) for t in slice_de)
        has_en_visible = any(has_visible_content(process_translation_token(t), is_translation=True) for t in slice_en)
        
        if not has_gr_visible and not has_de_visible and not has_en_visible:
            # Alle Zeilen leer nach Filterung - überspringe dieses Slice komplett
            i = j
            first_slice = False
            continue

        # JETZT erst die Paragraphs erstellen (nachdem wir wissen, dass Content vorhanden ist)
        # WICHTIG: Übergebe tok_idx an cell_markup, damit _strip_tags_from_token korrekt arbeitet
        # DEFENSIV: Wenn cell_markup() leer zurückgibt, verwende ' ' (Leerzeichen) statt '' (verhindert ReportLab-Crashes)
        gr_cells = []
        for idx, t in enumerate(slice_gr):
            if t:
                markup = cell_markup(t, True, tok_idx=slice_start + idx)
                # KRITISCH: ReportLab crasht manchmal bei komplett leeren Paragraphen - verwende Leerzeichen als Fallback
                gr_cells.append(Paragraph(markup if markup else ' ', token_gr_style))
            else:
                gr_cells.append(Paragraph(' ', token_gr_style))  # Leerzeichen statt '' für Stabilität
        
        # KRITISCHER FIX: DE und EN in NESTED TABLES kombinieren (wie STRAUßLOGIK!)
        # WICHTIG: Nur VORHANDENE Übersetzungen hinzufügen (nicht immer 2 Zeilen!)
        # Damit bei gemischten 2/3-zeiligen Wörtern die Übersetzungen OBEN bleiben!
        de_en_combined_cells = []
        # KRITISCH: Iteriere über slice_gr Länge, nicht über DE/EN!
        # Die Anzahl der Zellen MUSS mit GR-Zellen übereinstimmen!
        max_len = len(slice_gr)  # ANZAHL DER GR-TOKENS bestimmt Anzahl der Spalten!
        for idx in range(max_len):
            tok_de = slice_de[idx] if idx < len(slice_de) else ''
            tok_en = slice_en[idx] if idx < len(slice_en) else ''
            
            # Sammle NUR vorhandene Übersetzungen (wie STRAUßLOGIK!)
            all_translations = []
            
            if tok_de and tok_de.strip():
                formatted_de = cell_markup(process_translation_token(tok_de), False, tok_idx=None)
                all_translations.append(formatted_de)
            
            if tok_en and tok_en.strip():
                formatted_en = cell_markup(process_translation_token(tok_en), False, tok_idx=None)
                all_translations.append(formatted_en)
            
            # Erstelle nested table NUR für vorhandene Übersetzungen
            if all_translations:
                # Erstelle Paragraph für jede Übersetzung
                translation_paragraphs = []
                for trans in all_translations:
                    translation_paragraphs.append([Paragraph(trans, token_de_style_tight)])
                
                # Erstelle nested Table mit ALLEN Übersetzungen als separate Zeilen
                nested_table = Table(translation_paragraphs, colWidths=[None])
                
                # KRITISCHER FIX: Normale Paddings (0pt) für korrekte Abstände!
                # Negatives Padding zieht Zeilen zu eng zusammen (Tags ragen in vorherige Zeile)
                # FÜR ZITATE: Verwende das GLEICHE Padding wie normale Zeilen (0pt)!
                # Der Abstand zwischen Zitat-Blöcken wird durch TOPPADDING auf der äußeren Tabelle kontrolliert.
                padding_value = 0  # Immer 0pt - Abstand wird auf Table-Ebene kontrolliert!
                nested_style = TableStyle([
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ('LEFTPADDING', (0, 0), (-1, -1), 0),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), padding_value),
                    ('TOPPADDING', (0, 0), (-1, -1), padding_value),
                ])
                
                # KRITISCH: Erste Zeile braucht KEIN extra Padding (bleibt bei 0pt)
                nested_table.setStyle(nested_style)
                de_en_combined_cells.append(nested_table)
            else:
                # Kein Übersetzung vorhanden - leere Zelle (Leerzeichen statt '' für Stabilität)
                de_en_combined_cells.append(Paragraph(' ', token_de_style))

        # VEREINHEITLICHUNG: Nur 2 Rows (wie STRAUßLOGIK)!
        # Row 0: GR-Zeile
        # Row 1: DE+EN combined (nested tables)
        row_gr, row_de_en, colWidths = [], [], []
        
        # Speaker-Spalte (nur in GR-Row sichtbar, in DE/EN-Row leer)
        if speaker_width_pt > 0:
            row_gr.append(sp_cell_gr)
            row_gr.append(sp_gap_gr)
            row_de_en.append(Paragraph(' ', token_de_style))  # Leer in DE/EN-Row (Leerzeichen statt '')
            row_de_en.append(Paragraph(' ', token_de_style))  # Leer für Gap (Leerzeichen statt '')
            colWidths += [speaker_width_pt, SPEAKER_GAP_MM*mm]
            
        # Para-Spalte (nur in GR-Row sichtbar, in DE/EN-Row leer)
        if para_width_pt > 0:
            row_gr.append(para_cell_gr)
            row_gr.append(para_gap_gr)
            row_de_en.append(Paragraph(' ', token_de_style))  # Leer in DE/EN-Row (Leerzeichen statt '')
            row_de_en.append(Paragraph(' ', token_de_style))  # Leer für Gap (Leerzeichen statt '')
            colWidths += [para_width_pt, PARA_GAP_MM*mm]

        # Token-Spalten
        row_gr += gr_cells
        row_de_en += de_en_combined_cells

        # WICHTIG: Die verfügbare Breite wurde bereits oben berechnet (avail_w)
        # und berücksichtigt bereits speaker_width_pt und para_width_pt!
        # Daher dürfen wir diese NICHT NOCHMAL abziehen!
        token_avail_w = avail_w  # Bereits korrekt berechnet in Zeile 1485-1492

        # Verfügbare Breite für Token-Spalten
        token_slice_w = slice_w
        total_slice_w = sum(token_slice_w)

        # Blocksatz vorübergehend deaktiviert für maximale Stabilität
        # Die intelligente Blocksatz-Logik kann Layout-Probleme verursachen
        token_slice_w = slice_w  # Immer Originalbreiten verwenden

        colWidths += token_slice_w

        # DEFENSIVE: Prüfe auf None-Werte in colWidths
        colWidths = [max(w or 0.1, 0.1) for w in colWidths]

        # SICHERHEIT: Prüfe, ob die Table-Breite größer ist als die verfügbare Breite
        # Wenn ja, skaliere die colWidths, um negative Breiten zu vermeiden
        total_table_width = sum(colWidths)
        # Berücksichtige Padding: 2 * CELL_PAD_LR_PT pro Spalte
        padding_overhead = len(colWidths) * 2 * CELL_PAD_LR_PT
        max_available_width = avail_w - padding_overhead
        
        if total_table_width > max_available_width and max_available_width > 0:
            # Skaliere alle colWidths proportional
            scale_factor = max_available_width / total_table_width
            colWidths = [w * scale_factor for w in colWidths]
            # Warnung unterdrückt: Skalierung erfolgt automatisch, keine Log-Flut nötig
            # (Table-Breite wird automatisch angepasst, daher ist diese Warnung redundant)

        # VEREINHEITLICHT: Erstelle Tabelle mit NUR 2 Rows (wie STRAUßLOGIK)!
        # Row 0: GR
        # Row 1: DE+EN combined (nested tables)
        tbl = Table([row_gr, row_de_en], colWidths=colWidths, hAlign=table_halign)
        
        # Prüfe ob Übersetzungen vorhanden sind (für Padding-Logik)
        has_de = any(slice_de)
        has_en = any(slice_en)
        
        gap_pts = INTRA_PAIR_GAP_MM * mm
        style_list = [
            ('LEFTPADDING',   (0,0), (-1,-1), 0.5),    # Minimal (wie STRAUßLOGIK)
            ('RIGHTPADDING',  (0,0), (-1,-1), 0.5),    # Minimal (wie STRAUßLOGIK)
            ('TOPPADDING',    (0,0), (-1,-1), 0.0),
            ('BOTTOMPADDING', (0,0), (-1,-1), 0.0),
            ('VALIGN',        (0,0), (-1,-1), 'BOTTOM'),
            ('ALIGN',         (0,0), (-1,-1), 'CENTER'),  # Zentriere Zellen-Inhalte
        ]
        
        # NEU: Hinterlegung für Kommentar-Referenzen
        # Prüfe, ob base_num in line_comment_colors enthalten ist
        # WICHTIG: Wenn comment_token_mask vorhanden ist und nicht leer, unterdrücke Hintergrundfarbe
        # (wird in der Vorverarbeitung gesetzt, wenn disable_comment_bg=True)
        comment_token_mask = block.get('comment_token_mask', []) if block else []
        has_comment_mask = comment_token_mask and any(comment_token_mask)
        
        # Prüfe auch, ob disable_comment_bg in tag_config gesetzt ist
        disable_comment_bg_flag = False
        if tag_config and isinstance(tag_config, dict):
            disable_comment_bg_flag = bool(tag_config.get('disable_comment_bg', False))
        
        # WICHTIG: Hinterlegung KOMPLETT DEAKTIVIERT (User-Request)
        # Keine Hinterlegung mehr für kommentierte Bereiche
        
        # Padding nur hinzufügen, wenn Übersetzungen vorhanden sind
        if has_de or has_en:
            style_list.append(('BOTTOMPADDING', (0,0), (-1,0), gap_pts))  # GR → Übersetzungen
            style_list.append(('TOPPADDING', (0,0), (-1,0), 1))  # Abstand zur vorherigen Table (wie STRAUßLOGIK)
        
        # VEREINHEITLICHUNG: Entferne NEGATIVE PADDINGS!
        # Diese verursachten unterschiedliche Abstände zwischen 2-sprachig und 3-sprachig.
        # Verwende stattdessen EINHEITLICH gap_pts für GR → erste Übersetzung.
        # Zwischen DE und EN: KEIN zusätzlicher Abstand (0pt)!
        # KRITISCH: Auch bei § Texten soll der Abstand zwischen DE und EN minimal sein (0mm)!
        if has_en and has_de:
            # DE und EN vorhanden: KEIN zusätzliches Padding zwischen ihnen!
            # Die Zeilen liegen DIREKT aufeinander (nur Leading-Abstand innerhalb Paragraph)
            pass  # Kein BOTTOMPADDING/TOPPADDING zwischen DE und EN!
        elif has_en and not has_de:
            # Nur griechisch und englisch (keine deutsche Zeile)
            # gap_pts wird bereits oben angewendet
            pass
        
        tbl.setStyle(TableStyle(style_list))
        tables.append(tbl)
        first_slice, i = False, j
    return tables

# ----------------------- PDF-Erstellung -----------------------
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

def create_pdf(blocks, pdf_name:str, *, strength:str="NORMAL",
               color_mode:str="COLOR", tag_mode:str="TAGS",
               placement_overrides: dict | None = None,
               tag_config: dict | None = None,
               hide_pipes:bool=False):  # NEU: Pipes (|) in Übersetzungen verstecken

    # DIAGNOSE: Logging am Anfang von create_pdf
    import logging
    import sys
    import os
    logger = logging.getLogger(__name__)
    logger.info("Prosa_Code.create_pdf: ENTRY for %s (blocks=%d, strength=%s, color=%s, tag=%s)", 
                os.path.basename(pdf_name), len(blocks), strength, color_mode, tag_mode)
    print(f"Prosa_Code: create_pdf ENTRY for {os.path.basename(pdf_name)} (blocks={len(blocks)})", flush=True)
    try:
        sys.stdout.flush()
    except Exception:
        pass

    # Verarbeite Kommentare und weise Farben zu
    comments = process_comments_for_coloring(blocks)
    
    # Erstelle eine Map: Zeilennummer → Kommentar-Farbe (für Hinterlegung)
    line_comment_colors = {}  # {line_num: (r, g, b)}
    for comment in comments:
        color = comment['color']
        for line_num in range(comment['start_line'], comment['end_line'] + 1):
            line_comment_colors[line_num] = color
    
    # Speichere line_comment_colors für späteres Rendering
    # (wird in build_tables_for_stream und beim Rendering verwendet)

    # Leite gr_size und de_size aus strength ab, wie in der alten Logik
    if strength == "NORMAL":
        gr_size = NORMAL_GR_SIZE
        de_size = NORMAL_DE_SIZE
    elif strength == "GR_FETT" or strength == "LAT_FETT":
        # LAT_FETT wird wie GR_FETT behandelt (antike Sprache fett)
        gr_size = REVERSE_GR_SIZE
        de_size = REVERSE_DE_SIZE
    elif strength == "DE_FETT":
        gr_size = DE_FETT_GR_SIZE
        de_size = DE_FETT_DE_SIZE
    else:
        gr_size = NORMAL_GR_SIZE
        de_size = NORMAL_DE_SIZE

    # Tag-Placement-Overrides (hoch/tief/aus) anwenden
    set_tag_placement_overrides(placement_overrides)

    # =============================================================================
    # HINWEIS: Die Vorverarbeitung (Färben, Tag-Filterung) wird jetzt ZENTRAL
    # in shared/unified_api.py gehandhabt. Die 'blocks', die hier ankommen,
    # sind bereits fertig vorverarbeitet.
    # =============================================================================

    # Setze kritische Konstanten basierend auf tag_mode
    global INTRA_PAIR_GAP_MM, CONT_PAIR_GAP_MM, SPEAKER_GAP_MM

    if tag_mode == "TAGS":
        INTRA_PAIR_GAP_MM = INTRA_PAIR_GAP_MM_TAGS  # 1.5mm
        CONT_PAIR_GAP_MM = CONT_PAIR_GAP_MM_TAGS   # 3.0mm (minimal für Stabilität)
        SPEAKER_GAP_MM = 1.2  # Gleich wie PARA_GAP_MM für konsistente Formatierung
    else:  # NO_TAGS
        INTRA_PAIR_GAP_MM = INTRA_PAIR_GAP_MM_NO_TAGS  # 1.0mm
        CONT_PAIR_GAP_MM = CONT_PAIR_GAP_MM_NO_TAGS    # 6.0mm (minimal)
        SPEAKER_GAP_MM = 1.2  # Gleich wie PARA_GAP_MM für konsistente Formatierung

    # Debug-Ausgabe für Testzwecke
    # print(f"DEBUG: tag_mode={tag_mode}, CONT_PAIR_GAP_MM={CONT_PAIR_GAP_MM}, INTRA_PAIR_GAP_MM={INTRA_PAIR_GAP_MM}")

    doc = SimpleDocTemplate(pdf_name, pagesize=A4,
                            leftMargin=10*mm, rightMargin=6*mm,  # Minimaler rechter Rand für maximale Textbreite (wie Apologie)
                            topMargin=14*mm,  bottomMargin=14*mm)
    frame_w = A4[0] - doc.leftMargin - doc.rightMargin
    base = getSampleStyleSheet()

    # Überschriften / Titel
    # Gleichheitszeichen-Überschriften: ALLE NICHT FETT (Tinte sparen!)
    # H1 (====): zentriert, H2 (===) und H3 (==): linksbündig
    style_eq_h1 = ParagraphStyle('EqH1', parent=base['Normal'],
        fontName='DejaVu', fontSize=H1_EQ_SIZE, leading=_leading_for(H1_EQ_SIZE),
        alignment=TA_CENTER, spaceAfter=H1_SPACE_AFTER_MM*mm, keepWithNext=True)  # Zentriert
    style_eq_h2 = ParagraphStyle('EqH2', parent=base['Normal'],
        fontName='DejaVu', fontSize=H2_EQ_SIZE, leading=_leading_for(H2_EQ_SIZE),
        alignment=TA_LEFT, spaceAfter=H2_SPACE_AFTER_MM*mm, keepWithNext=True)  # Linksbündig
    style_eq_h3 = ParagraphStyle('EqH3', parent=base['Normal'],
        fontName='DejaVu', fontSize=H3_EQ_SIZE, leading=_leading_for(H3_EQ_SIZE),
        alignment=TA_LEFT, spaceAfter=H3_SPACE_AFTER_MM*mm, keepWithNext=True)  # Linksbündig
    style_title = ParagraphStyle('TitleBrace', parent=base['Normal'],
        fontName='DejaVu', fontSize=TITLE_BRACE_SIZE, leading=_leading_for(TITLE_BRACE_SIZE),
        alignment=TA_CENTER, spaceAfter=TITLE_SPACE_AFTER_MM*mm, keepWithNext=True)

    # Tokenstile
    gr_bold = (strength == "GR_FETT" or strength == "LAT_FETT")  # LAT_FETT auch fett
    de_bold = (strength == "DE_FETT")

    token_gr = ParagraphStyle('TokGR', parent=base['Normal'],
        fontName='DejaVu-Bold' if gr_bold else 'DejaVu',
        fontSize=gr_size, leading=_leading_for(gr_size),
        alignment=TA_CENTER, spaceAfter=0, spaceBefore=0, wordWrap='LTR', splitLongWords=0)
    # KRITISCH: token_de mit 1.1× Leading für ENGEN Abstand in normalen Texten!
    # Zitate verwenden quote_de_style mit normalem 1.3× Leading (_leading_for)
    token_de = ParagraphStyle('TokDE', parent=base['Normal'],
        fontName='DejaVu-Bold' if de_bold else 'DejaVu',
        fontSize=de_size, leading=de_size * 1.1,  # 1.1× = ENGER Abstand für normale Texte!
        alignment=TA_CENTER, spaceAfter=0, spaceBefore=0, wordWrap='LTR', splitLongWords=0)

    # §-Label / Quelle / Sprecher
    style_para = ParagraphStyle('ParaLabel', parent=base['Normal'],
        fontName='DejaVu', fontSize=max(de_size, 9.0), leading=_leading_for(max(de_size, 9.0)),
        alignment=TA_LEFT, spaceAfter=0, spaceBefore=0, wordWrap='LTR', splitLongWords=0)
    style_quote_line = ParagraphStyle('QuoteLine', parent=base['Normal'],
        fontName='DejaVu-Bold' if gr_bold else 'DejaVu', fontSize=gr_size, leading=_leading_for(gr_size),
        alignment=TA_CENTER, spaceAfter=0, spaceBefore=0, wordWrap='LTR', splitLongWords=0)  # CENTER statt JUSTIFY!
    style_source = ParagraphStyle('SourceLine', parent=base['Normal'],
        fontName='DejaVu', fontSize=gr_size, leading=_leading_for(gr_size),
        alignment=TA_RIGHT, rightIndent=SOURCE_RIGHT_INDENT_MM*mm,
        spaceAfter=0, spaceBefore=0, wordWrap='LTR', splitLongWords=0)
    style_speaker = ParagraphStyle('Speaker', parent=base['Normal'],
        fontName='DejaVu', fontSize=de_size, leading=_leading_for(de_size),
        alignment=TA_JUSTIFY, spaceAfter=0, spaceBefore=0, wordWrap='LTR', splitLongWords=0, textColor=colors.black)

    # Die Blöcke kommen jetzt vorverarbeitet und tokenisiert an.
    flow_blocks = blocks

    # DEBUG: Prüfe, ob Kommentare in flow_blocks vorhanden sind
    # Kommentare werden in flow_blocks verarbeitet (DEBUG entfernt für weniger Log-Noise)

    # Meta-Flag: ob irgendwo Sprecher auftraten
    any_speaker = False
    print(f"DEBUG RENDER: Checking for _meta block in {len(flow_blocks)} blocks", flush=True)
    if flow_blocks and flow_blocks[-1].get('type') == '_meta':
        any_speaker = bool(flow_blocks[-1].get('any_speaker'))
        print(f"DEBUG RENDER: Found _meta block! any_speaker={any_speaker}", flush=True)
        flow_blocks = flow_blocks[:-1]
    else:
        print(f"DEBUG RENDER: No _meta block found! Last block type: {flow_blocks[-1].get('type') if flow_blocks else 'NO BLOCKS'}", flush=True)

    def para_width_pt(text:str) -> float:
        # Zeilennummern (123) werden nicht angezeigt, aber Paragraphen-Marker (§ 1) schon
        if not text: return 0.0
        # Prüfe ob es ein Paragraphen-Marker ist (enthält §)
        if '§' in text:
            # Dynamische Berechnung: Verwende die tatsächliche Breite + ausreichender Puffer
            # WICHTIG: Puffer muss groß genug sein, damit "§ 1" nicht umbricht
            w = pdfmetrics.stringWidth(text, style_para.fontName, style_para.fontSize) + 4.0  # Ausreichender Puffer gegen Umbruch
            # Verwende ein angemessenes Minimum, damit auch "§ 1" nicht umbricht
            return max(20.0, w)  # Minimal 20pt um sicherzustellen, dass "§ 1" nicht umbricht
        # Zeilennummern werden nicht angezeigt
        return 0.0

    def speaker_width_pt(text:str) -> float:
        if not text: return 0.0
        disp = f'[{text}]:'
        w = pdfmetrics.stringWidth(disp, style_speaker.fontName, style_speaker.fontSize) + 0.8
        return max(SPEAKER_COL_MIN_MM * mm, w)

    def build_flow_tables(flow_block):
        print(f"Prosa_Code: build_flow_tables() ENTRY (gr_tokens={len(flow_block.get('gr_tokens', []))}, de_tokens={len(flow_block.get('de_tokens', []))})", flush=True)
        try:
            gr_tokens, de_tokens = flow_block['gr_tokens'], flow_block['de_tokens']
            pdisp = flow_block.get('para_label') or ''
            sdisp = flow_block.get('speaker') or ''
            pwidth = para_width_pt(pdisp)
            swidth = speaker_width_pt(sdisp) if any_speaker else 0.0
            base_num = flow_block.get('base')  # NEU: Zeilennummer für Hinterlegung

            en_tokens = flow_block.get('en_tokens', [])  # NEU: Englische Tokens
            
            # STRAUßLOGIK: Prüfe ob Multi-Row-Struktur vorhanden
            has_strauss = flow_block.get('_has_strauss', False)
            
            if has_strauss:
                # Multi-Row-Struktur vorhanden → verwende spezielle Render-Funktion
                gr_rows = flow_block.get('_gr_rows', [gr_tokens])  # GR kann auch mehrfach sein!
                de_rows = flow_block.get('_de_rows', [])
                en_rows = flow_block.get('_en_rows', [])
                
                print(f"STRAUßLOGIK + FLIEßTEXT: Rendering Multi-Row (GR={len(gr_rows)} rows, DE={len(de_rows)} rows, EN={len(de_rows)} rows)", flush=True)
                
                # Verwende build_tables_for_alternatives für Multi-Row-Rendering
                tables = build_tables_for_alternatives(
                    gr_tokens_alternatives=gr_rows,  # GR kann auch Multi-Row sein!
                    de_tokens_alternatives=de_rows,       # DE mehrfach
                    en_tokens_alternatives=en_rows,       # EN mehrfach
                    doc_width_pt=frame_w,
                    token_gr_style=token_gr, token_de_style=token_de,
                    para_display=pdisp, para_width_pt=pwidth, style_para=style_para,
                    speaker_display=(f'[{sdisp}]:' if sdisp else ''), speaker_width_pt=swidth, style_speaker=style_speaker,
                    table_halign='LEFT',
                    hide_pipes=hide_pipes,
                    tag_config=tag_config,
                    tag_mode=tag_mode,
                    color_mode=color_mode)
            else:
                # Normale Zeile ohne STRAUßLOGIK
                tables = build_tables_for_stream(
                    gr_tokens, de_tokens,
                    doc_width_pt=frame_w,
                    reverse_mode=False,  # Nicht mehr verwendet
                    token_gr_style=token_gr, token_de_style=token_de,
                    para_display=pdisp, para_width_pt=pwidth, style_para=style_para,
                    speaker_display=(f'[{sdisp}]:' if sdisp else ''), speaker_width_pt=swidth, style_speaker=style_speaker,
                    table_halign='LEFT', italic=False,
                    en_tokens=en_tokens,  # NEU: Englische Tokens übergeben
                    hide_pipes=hide_pipes,  # NEU: Pipes (|) in Übersetzungen verstecken
                    tag_config=tag_config,  # NEU: Tag-Konfiguration für individuelle Breitenberechnung
                    base_num=base_num,  # NEU: Zeilennummer für Hinterlegung
                    line_comment_colors=line_comment_colors,  # NEU: Map von Zeilennummern zu Kommentar-Farben
                    block=flow_block,  # NEU: Block-Objekt für comment_token_mask
                    tag_mode=tag_mode,  # NEU: Tag-Modus (TAGS oder NO_TAGS)
                    color_mode=color_mode)  # NEU: Farb-Modus (COLOR oder BLACK_WHITE)
            
            # WICHTIG: TableStyle explizit importieren (verhindert Closure-Scope-Problem)
            from reportlab.platypus import TableStyle
            for table_idx, table in enumerate(tables):
                if table_idx > 0:  # WICHTIG: Verwende table_idx statt idx (verhindert Namenskonflikt)
                    table.setStyle(TableStyle([('TOPPADDING', (0,0), (-1,0), CONT_PAIR_GAP_MM * mm)]))
            return tables
        except Exception as e:
            print(f"Prosa_Code: build_flow_tables() ERROR: {e}", flush=True)
            import traceback
            traceback.print_exc()
            raise

    # NEU: Hilfsfunktion zum Rendern von Kommentaren aus block['comments']
    def render_block_comments(block, elements_list, doc=None):
        """Rendert Kommentare aus block['comments'] als Paragraphen (dedupliziert + limitiert)"""
        cms = block.get('comments') or []
        # DEBUG: Prüfe auch, ob der Block selbst ein Kommentar ist
        if not cms and block.get('type') == 'comment':
            # Block ist selbst ein Kommentar - verwende ihn direkt
            cms = [block]
        if not cms:
            return
        # DEBUG: Logge gefundene Kommentare
        print(f"Prosa_Code: render_block_comments() - found {len(cms)} comments in block type={block.get('type')}", flush=True)
        
        # Prüfe disable_comment_bg Flag (falls verfügbar)
        disable_comment_bg = False
        try:
            disable_comment_bg = tag_config.get('disable_comment_bg', False) if tag_config else False
        except Exception:
            disable_comment_bg = block.get('disable_comment_bg', False)
        
        # Deduplicate comments per block and limit count & length to keep PDF generation fast.
        # ERHÖHT: Keine Kürzung mehr, erlaubt längere Kommentare mit Umbruch
        MAX_COMMENTS_PER_BLOCK = 10  # Erhöht auf 10
        MAX_COMMENT_WORDS = 175  # Wortgrenze für automatischen Umbruch (gleich wie Poesie!)
        added_keys = set()
        added_count = 0
        truncated = False
        
        for cm in cms:
            if added_count >= MAX_COMMENTS_PER_BLOCK:
                truncated = True
                break
            
            # Unterstütze verschiedene Formate: dict mit 'text', 'comment', 'body', 'content' oder direkt String
            # KRITISCH: 'content' ist das Feld, das discover_and_attach_comments() verwendet!
            if isinstance(cm, dict):
                txt = cm.get('text') or cm.get('comment') or cm.get('body') or cm.get('content') or ""
                key = (cm.get('start'), cm.get('end'), len(txt))
            else:
                txt = str(cm) if cm else ""
                key = ("txt", hash(txt))
            
            # DEBUG: Zeige gefundenen Kommentartext
            print(f"Prosa_Code: render_block_comments - processing comment: txt='{txt[:50]}...' (type={type(cm).__name__})", flush=True)
            
            if not txt or not txt.strip():
                print(f"Prosa_Code: render_block_comments - SKIPPING empty comment", flush=True)
                continue
            
            # Deduplizierung: überspringe identische Kommentare
            if key in added_keys:
                continue
            added_keys.add(key)
            
            # Optional: Zeige den Bereich in [ECKIGEN KLAMMERN] (z.B. [2-4] oder [8k])
            # Unterstütze verschiedene Formate:
            # 1. pair_range: dict mit start/end
            # 2. line_num: direkt aus dem Kommentar-Block (von discover_and_attach_comments)
            # 3. start/end: explizite Felder
            rng = cm.get('pair_range') if isinstance(cm, dict) else None
            line_num = cm.get('line_num') if isinstance(cm, dict) else None
            
            # WICHTIG: Entferne "k" Suffix von line_num (wie in Poesie)
            # ODER: Wenn kein line_num, aber pair_range vorhanden, verwende das!
            if line_num:
                line_num_clean = str(line_num).rstrip('kK')
                txt = f"[{line_num_clean}] {txt}"
            elif rng:
                # pair_range vorhanden: Zeige als [start-end] oder [start] (wenn gleich)
                if rng[0] == rng[1]:
                    # Einzelne Zeile → zeige nur [start]
                    txt = f"[{rng[0]}] {txt}"
                else:
                    # Bereich → zeige [start-end]
                    txt = f"[{rng[0]}-{rng[1]}] {txt}"
            elif isinstance(cm, dict) and cm.get('start') and cm.get('end'):
                # Fallback: explizite start/end Felder
                start = cm.get('start')
                end = cm.get('end')
                if start == end:
                    txt = f"[{start}] {txt}"
                else:
                    txt = f"[{start}-{end}] {txt}"
            
            # Sanitize - KEINE Kürzung mehr! Längere Kommentare erlaubt
            text_clean = " ".join(txt.split())
            # KEIN Abschneiden mehr! Längere Kommentare erlaubt.
            
            # Kommentar-Style: klein, grau, kursiv, GRAU HINTERLEGT — be defensive
            try:
                # WICHTIG: backColor im ParagraphStyle verhindert Seitenumbrüche!
                # Daher: Verwende Table mit grauem Hintergrund für ALLE Kommentare
                comment_style_simple = ParagraphStyle('CommentSimple', parent=base['Normal'],
                    fontName='DejaVu', fontSize=7.5,  # Gleich wie Poesie
                    leading=9,  # Gleich wie Poesie (war 9.5)
                    alignment=TA_LEFT, 
                    leftIndent=4*mm, rightIndent=4*mm,  # Gleich wie Poesie
                    spaceBefore=2, spaceAfter=2,  # Gleich wie Poesie
                    textColor=colors.Color(0.25, 0.25, 0.25),  # Gleich wie Poesie
                    backColor=colors.Color(0.92, 0.92, 0.92))  # Gleich wie Poesie
                
                # Prüfe ob Kommentar lang ist (>175 Wörter) für Page-Breaking
                word_count = len(text_clean.split())
                
                # Berechne verfügbare Breite (gleich wie Poesie)
                try:
                    from Prosa_Code import doc  # Versuche doc zu finden
                    available_width = doc.pagesize[0] - doc.leftMargin - doc.rightMargin - 8*mm
                except:
                    available_width = 170*mm  # Fallback
                
                # Bei langen Kommentaren (>175 Wörter): Tables brechen automatisch
                comment_table = Table([[Paragraph(html.escape(text_clean), comment_style_simple)]], 
                                     colWidths=[available_width])
                comment_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, -1), colors.Color(0.92, 0.92, 0.92)),  # Grauer Hintergrund
                    ('LEFTPADDING', (0, 0), (-1, -1), 4*mm),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 4*mm),
                    ('TOPPADDING', (0, 0), (-1, -1), 3*mm),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 3*mm),
                ]))
                
                # Füge Kommentar hinzu
                elements_list.append(Spacer(1, 2*mm))
                elements_list.append(comment_table)
                elements_list.append(Spacer(1, 2*mm))
                    
                print(f"Prosa_Code: render_block_comments - ADDED comment paragraph ({word_count} words): '{text_clean[:50]}...'", flush=True)
                added_count += 1
            except Exception as e:
                import logging
                logging.getLogger(__name__).exception("prosa_pdf: rendering comment failed (continuing): %s", str(e))
        
        # Compact debug log instead of per-comment verbose logging
        if added_count > 0:
            block_id = block.get("block_index") or block.get("index") or "?"
            import logging
            logging.getLogger(__name__).debug(
                "prosa_pdf: Added %d comment paragraphs for block idx=%s (total_comments=%d, truncated=%s)",
                added_count, block_id, len(cms), truncated
            )

    # DIAGNOSE: Logging vor Element-Erstellung
    logger.info("Prosa_Code.create_pdf: Starting element creation (flow_blocks=%d)", len(flow_blocks))
    print(f"Prosa_Code: Starting element creation (flow_blocks={len(flow_blocks)})", flush=True)
    try:
        sys.stdout.flush()
    except Exception:
        pass
    
    elements, idx = [], 0
    last_block_type = None  # Speichert den Typ des letzten verarbeiteten Blocks
    processed_flow_indices = set()  # WICHTIG: Verhindere doppelte Verarbeitung von Flow-Blöcken
    processed_h3_indices = set()  # WICHTIG: Verhindere doppelte Verarbeitung von h3_eq Blöcken
    skipped_indices = set()  # WICHTIG: Verfolge übersprungene Indizes, um Endlosschleifen zu vermeiden
    pending_headers = []  # WICHTIG: Speichere Überschriften, die mit nächstem Content zusammen in KeepTogether gepackt werden
    
    print(f"Prosa_Code: Entering element creation loop (flow_blocks={len(flow_blocks)})", flush=True)
    comment_count = sum(1 for b in flow_blocks if isinstance(b, dict) and b.get('type') == 'comment')
    if comment_count > 0:
        print(f"Prosa_Code: Found {comment_count} comment blocks in flow_blocks", flush=True)
    
    iteration_count = 0
    last_idx_seen = -1  # Track last idx to detect backwards jumps
    consecutive_same_idx = 0  # Count consecutive iterations with same idx
    while idx < len(flow_blocks):
        iteration_count += 1
        
        # DIAGNOSE: Detect backwards jumps or stuck idx
        if idx == last_idx_seen:
            consecutive_same_idx += 1
            if consecutive_same_idx >= 2:  # Reduziert von 3 auf 2 für frühere Erkennung
                print(f"Prosa_Code: ERROR - idx stuck at {idx} for {consecutive_same_idx} iterations! Forcing increment to break loop.", flush=True)
                idx += 1  # Force increment to break loop
                if idx >= len(flow_blocks):
                    break
                continue
        elif idx < last_idx_seen:
            print(f"Prosa_Code: ERROR - idx decreased from {last_idx_seen} to {idx}! Forcing increment.", flush=True)
            idx = last_idx_seen + 1  # Force increment
            if idx >= len(flow_blocks):
                break
            continue
        else:
            consecutive_same_idx = 0
        last_idx_seen = idx
        
        # DIAGNOSE: Safety check - prevent infinite loops
        if iteration_count > len(flow_blocks) * 10:  # Max 10x iterations per block
            print(f"Prosa_Code: ERROR - Infinite loop detected! iteration_count={iteration_count}, idx={idx}, len(flow_blocks)={len(flow_blocks)}", flush=True)
            raise RuntimeError(f"Infinite loop detected in element creation: iteration_count={iteration_count}, idx={idx}")
        
        # DIAGNOSE: Logging am Anfang jeder Iteration (für ersten Block)
        if idx == 0:
            print(f"Prosa_Code: Processing first block (idx=0, type={flow_blocks[idx].get('type', 'unknown')})", flush=True)
        elif iteration_count % 50 == 0:  # Logge alle 50 Iterationen
            print(f"Prosa_Code: Still processing... iteration={iteration_count}, idx={idx}, type={flow_blocks[idx].get('type', 'unknown')}", flush=True)
        
        b, t = flow_blocks[idx], flow_blocks[idx].get('type', 'unknown')
        
        # DEBUG: Logge type für Kommentar-Blöcke
        if isinstance(b, dict) and b.get('type') == 'comment':
            print(f"Prosa_Code: DEBUG - Found comment block at idx={idx}, t='{t}', b.type='{b.get('type')}', will check if t=='comment'", flush=True)

        if t == 'blank':
            elements.append(Spacer(1, BLANK_MARKER_GAP_MM * mm)); idx += 1; continue
        if t == 'title_brace':
            # NEU: Kommentare aus block['comments'] rendern (auch bei title_brace)
            render_block_comments(b, elements, doc)
            elements.append(Paragraph(xml_escape(b['text']), style_title))
            last_block_type = t
            idx += 1; continue

        # NEU: Kommentar-Zeilen (zahlk oder zahl-zahlk) - GANZ EINFACH: Text in grauer Box
        if t == 'comment':
            original_line = b.get('original_line', '')
            content = b.get('content', '')
            line_num = b.get('line_num', '')
            
            # WICHTIG: line_num ist bereits OHNE 'k' Suffix (wurde beim Parsen entfernt)!
            # Erstelle Zeilennummer-Präfix direkt aus line_num
            line_num_prefix = ""
            if line_num:
                # line_num kann '500' oder '1-10' sein (OHNE 'k'!)
                line_num_prefix = f"[{line_num}] "
            
            # Falls kein line_num vorhanden, versuche aus original_line zu extrahieren
            if not line_num_prefix and original_line:
                # Extrahiere Zeilennummer-Bereich und entferne (XYZk)-Marker
                line_num_match = re.match(r'^\((\d+(?:-\d+)?)k\)\s*(.*)', original_line)
                if line_num_match:
                    line_num_str = line_num_match.group(1)
                    content = line_num_match.group(2).strip()
                    line_num_prefix = f"[{line_num_str}] "
                else:
                    content = re.sub(r'^\(\d+(?:-\d+)?k\)\s*', '', original_line).strip()
            
            # Fallback: Wenn immer noch kein content, verwende original_line (ohne Zeilennummer)
            if not content:
                if original_line:
                    line_num_match = re.match(r'^\((\d+(?:-\d+)?)k\)\s*(.*)', original_line)
                    if line_num_match:
                        line_num_str = line_num_match.group(1)
                        content = line_num_match.group(2).strip()
                        line_num_prefix = f"[{line_num_str}] "
                    else:
                        content = re.sub(r'^\(\d+(?:-\d+)?k\)\s*', '', original_line).strip()
                else:
                    content = ''
            
            # Wenn content leer ist, überspringe
            if not content:
                print(f"Prosa_Code: Skipping comment block at idx={idx} (content is empty, original_line='{original_line[:50] if original_line else ''}')", flush=True)
                idx += 1
                continue
            
            # Füge Zeilennummer-Präfix hinzu
            full_content = line_num_prefix + content
            
            # GANZ EINFACH: Kommentar in grauer Box rendern
            # Grau hinterlegter Kommentar-Box mit kleiner Schrift
            from reportlab.platypus import Table, TableStyle
            comment_style_simple = ParagraphStyle('CommentSimple', parent=base['Normal'],
                fontName='DejaVu', fontSize=7.5,  # Gleich wie Poesie
                leading=9,  # Gleich wie Poesie
                alignment=TA_LEFT, 
                leftIndent=4*mm, rightIndent=4*mm,  # Gleich wie Poesie
                spaceBefore=2, spaceAfter=2,  # Gleich wie Poesie
                textColor=colors.Color(0.25, 0.25, 0.25),  # Gleich wie Poesie
                backColor=colors.Color(0.92, 0.92, 0.92))  # Gleich wie Poesie
            
            # Berechne verfügbare Breite (gleich wie Poesie)
            try:
                available_width = doc.pagesize[0] - doc.leftMargin - doc.rightMargin - 8*mm
            except:
                available_width = 170*mm  # Fallback
            
            # Prüfe ob Kommentar lang ist (>175 Wörter) für Page-Breaking
            word_count = len(full_content.split())
            
            comment_table = Table([[Paragraph(xml_escape(full_content), comment_style_simple)]], 
                                 colWidths=[available_width])
            comment_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.Color(0.92, 0.92, 0.92)),  # Grauer Hintergrund
                ('LEFTPADDING', (0, 0), (-1, -1), 4*mm),
                ('RIGHTPADDING', (0, 0), (-1, -1), 4*mm),
                ('TOPPADDING', (0, 0), (-1, -1), 3*mm),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3*mm),
            ]))
            
            # Bei langen Kommentaren (>175 Wörter): Erlaube Seitenumbrüche
            # (Keine spezielle Behandlung nötig, Tables brechen automatisch)
                    
            elements.append(Spacer(1, 2*mm))
            elements.append(comment_table)
            elements.append(Spacer(1, 2*mm))
            print(f"Prosa_Code: Rendered comment block ({word_count} words): '{full_content[:50]}...'", flush=True)
            idx += 1
            continue

        if t in ('h1_eq', 'h2_eq'):
            # NEU: Kommentare aus block['comments'] rendern (auch bei Überschriften)
            render_block_comments(b, elements, doc)
            
            # WICHTIG: Füge Abstand VOR Überschriften hinzu, wenn vorher Text war
            # (aber nicht zwischen aufeinanderfolgenden Überschriften)
            if last_block_type in ('flow', 'pair', 'quote'):
                elements.append(Spacer(1, BLANK_MARKER_GAP_MM * mm * 1.2))
            
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

            # ANTI-ORPHAN: Speichere Überschriften für späteren KeepTogether mit Content
            pending_headers.extend(header)
            last_block_type = t
            continue

        if t == 'h3_eq':
            # WICHTIG: Überschriften-Handling MUSS EINFACH bleiben!
            # Das Scannen nach flow-Blöcken führt zu idx-Dekrementen und Endlosschleifen
            processed_h3_indices.add(idx)
            render_block_comments(b, elements, doc)
            print(f"Prosa_Code: Processing h3_eq block at idx={idx}", flush=True)
            
            # ANTI-ORPHAN: Speichere H3 für späteren KeepTogether mit Content
            h3_para = Paragraph(xml_escape(b['text']), style_eq_h3)
            pending_headers.append(h3_para)
            
            # KRITISCH: idx IMMER inkrementieren, NIEMALS scannen!
            idx += 1
            continue

        if t == 'quote':
            # NEU: Kommentare aus block['comments'] rendern (auch bei Zitaten)
            render_block_comments(b, elements, doc)
            
            # KRITISCH: Prüfe ob vorheriger Block (ignoriere BLANKs) ein para_set ist (§ Marker)
            # Wenn ja: Zeige § Marker VOR dem Zitat an!
            # Problem: § Marker wird nur in flow-Blöcken angezeigt, aber Zitate sind separate Blöcke
            # Lösung: Manuell § Marker als Paragraph vor Zitat einfügen
            prev_non_blank_idx = idx - 1
            while prev_non_blank_idx >= 0 and flow_blocks[prev_non_blank_idx].get('type') == 'blank':
                prev_non_blank_idx -= 1
            
            if prev_non_blank_idx >= 0 and flow_blocks[prev_non_blank_idx].get('type') == 'para_set':
                para_label = flow_blocks[prev_non_blank_idx].get('label', '')
                if para_label:
                    # ANTI-ORPHAN: § Marker zu pending_headers hinzufügen (nicht direkt zu elements!)
                    para_paragraph = Paragraph(xml_escape(para_label), style_eq_h3)
                    pending_headers.append(para_paragraph)
                    pending_headers.append(Spacer(1, BLANK_MARKER_GAP_MM * mm))
            
            # WICHTIG: Mehr Abstand vor dem Zitat (1.5x größer als normal)
            # (wird nur hinzugefügt wenn keine pending_headers vorhanden sind)
            if not pending_headers:
                elements.append(Spacer(1, BLANK_MARKER_GAP_MM * mm * 1.5))
            
            # NEU: Parse Zitat-Zeilen mit Zeilennummern-basierter Logik (wie normaler Text)
            # Dies ermöglicht korrekte Erkennung von 2- und 3-sprachigen Zeilen
            lines = b.get('lines', [])
            temp_quote_blocks = []
            j = 0
            
            while j < len(lines):
                ln = (lines[j] or '').strip()
                if not ln or is_empty_or_sep(ln):
                    j += 1
                    continue
                
                # Extrahiere Zeilennummer
                line_num, line_content = extract_line_number(ln)
                
                if line_num is not None:
                    # Sammle alle Zeilen mit derselben Nummer
                    lines_with_same_num = [ln]
                    k = j + 1
                    while k < len(lines):
                        next_line = (lines[k] or '').strip()
                        if is_empty_or_sep(next_line):
                            k += 1
                            continue
                        next_num, _ = extract_line_number(next_line)
                        if next_num == line_num:
                            lines_with_same_num.append(next_line)
                            k += 1
                        else:
                            break
                    
                    # Parse basierend auf Anzahl der Zeilen
                    num_lines = len(lines_with_same_num)
                    
                    # NEU: Spezielle Behandlung für Insertionszeilen (i) in Zitaten
                    if is_insertion_line(line_num):
                        # Erkenne, ob der Text 2-sprachig oder 3-sprachig ist
                        expected_lines_per_insertion = detect_language_count_from_context(lines, j)
                        
                        print(f"DEBUG Prosa Zitat: Insertionszeile erkannt: {line_num}, {num_lines} Zeilen gefunden, erwarte {expected_lines_per_insertion} Zeilen pro Insertion")
                        
                        # Gruppiere die Zeilen in Blöcke von expected_lines_per_insertion
                        insertion_idx = 0
                        while insertion_idx < num_lines:
                            # Hole die nächsten expected_lines_per_insertion Zeilen
                            insertion_group = lines_with_same_num[insertion_idx:insertion_idx + expected_lines_per_insertion]
                            
                            if len(insertion_group) < expected_lines_per_insertion:
                                # Nicht genug Zeilen für eine vollständige Insertion - überspringe
                                print(f"WARNING Prosa Zitat: Unvollständige Insertionsgruppe: {len(insertion_group)} Zeilen, erwartet {expected_lines_per_insertion}")
                                break
                            
                            # Verarbeite diese Insertionsgruppe
                            gr_line = _remove_line_number_from_line(insertion_group[0])
                            de_line = _remove_line_number_from_line(_remove_speaker_from_line(insertion_group[1]))
                            en_line = ''
                            if expected_lines_per_insertion >= 3 and len(insertion_group) >= 3:
                                en_line = _remove_line_number_from_line(_remove_speaker_from_line(insertion_group[2]))
                            
                            gt = tokenize(gr_line) if gr_line else []
                            dt = tokenize(de_line) if de_line else []
                            et = tokenize(en_line) if en_line else []
                            dt = ['' if RE_INLINE_MARK.match(x or '') else (x or '') for x in dt]
                            et = ['' if RE_INLINE_MARK.match(x or '') else (x or '') for x in et]
                            
                            if len(gt) > len(dt):   dt += [''] * (len(gt) - len(dt))
                            elif len(dt) > len(gt): gt += [''] * (len(dt) - len(gt))
                            if len(gt) > len(et):   et += [''] * (len(gt) - len(et))
                            elif len(et) > len(gt): gt += [''] * (len(et) - len(gt))
                            
                            temp_quote_blocks.append({
                                'type': 'pair',
                                'gr_tokens': gt,
                                'de_tokens': dt,
                                'en_tokens': et
                            })
                            
                            insertion_idx += expected_lines_per_insertion
                        
                        j = k
                        continue
                    
                    if num_lines == 2:
                        # 2-sprachig
                        gr_line = _remove_line_number_from_line(lines_with_same_num[0])
                        de_line = _remove_line_number_from_line(_remove_speaker_from_line(lines_with_same_num[1]))
                        gt = tokenize(gr_line) if gr_line else []
                        dt = tokenize(de_line) if de_line else []
                        dt = ['' if RE_INLINE_MARK.match(x or '') else (x or '') for x in dt]
                        if len(gt) > len(dt):   dt += [''] * (len(gt) - len(dt))
                        elif len(dt) > len(gt): gt += [''] * (len(dt) - len(gt))
                        temp_quote_blocks.append({
                            'type': 'pair',
                            'gr_tokens': gt,
                            'de_tokens': dt,
                            'en_tokens': []
                        })
                    elif num_lines >= 3:
                        # 3-sprachig
                        gr_line = _remove_line_number_from_line(lines_with_same_num[0])
                        de_line = _remove_line_number_from_line(_remove_speaker_from_line(lines_with_same_num[1]))
                        en_line = _remove_line_number_from_line(_remove_speaker_from_line(lines_with_same_num[2]))
                        gt = tokenize(gr_line) if gr_line else []
                        dt = tokenize(de_line) if de_line else []
                        et = tokenize(en_line) if en_line else []
                        dt = ['' if RE_INLINE_MARK.match(x or '') else (x or '') for x in dt]
                        et = ['' if RE_INLINE_MARK.match(x or '') else (x or '') for x in et]
                        max_len = max(len(gt), len(dt), len(et))
                        gt += [''] * (max_len - len(gt))
                        dt += [''] * (max_len - len(dt))
                        et += [''] * (max_len - len(et))
                        temp_quote_blocks.append({
                            'type': 'pair',
                            'gr_tokens': gt,
                            'de_tokens': dt,
                            'en_tokens': et
                        })
                    else:
                        # Nur 1 Zeile - als antike Zeile ohne Übersetzung
                        gr_line = _remove_line_number_from_line(lines_with_same_num[0])
                        gt = tokenize(gr_line) if gr_line else []
                        temp_quote_blocks.append({
                            'type': 'pair',
                            'gr_tokens': gt,
                            'de_tokens': [],
                            'en_tokens': []
                        })
                    j = k
                else:
                    # Keine Zeilennummer - als einzelne Zeile behandeln
                    gt = tokenize(ln) if ln else []
                    temp_quote_blocks.append({
                        'type': 'pair',
                        'gr_tokens': gt,
                        'de_tokens': [],
                        'en_tokens': []
                    })
                    j += 1
            
            # WICHTIG: Wende Farben und Tag-Verarbeitung auf Zitate an (wie bei normalem Text)
            # Verwende die gleiche Tag-Config wie für den Rest des Dokuments
            # KRITISCH: Zitate müssen ALLE Tag/Translation-Einstellungen erben!
            import shared.preprocess as preprocess
            
            # KRITISCH: Markiere alle Quote-Blöcke mit _in_quote=True damit apply_tag_visibility() sie verarbeitet!
            # Ohne dieses Flag werden sie in apply_tag_visibility() übersprungen (Zeile 1665)!
            for qb in temp_quote_blocks:
                qb['_in_quote'] = True
            
            # WICHTIG: Die Blöcke wurden bereits in prosa_pdf.py vorverarbeitet!
            # Die Farben und Tags sind bereits korrekt gesetzt.
            # Wir müssen hier NUR noch die Farbsymbole entfernen, wenn BLACK_WHITE aktiv ist.
            # ABER: Wir müssen die Farben ZUERST hinzufügen (falls noch nicht geschehen),
            # dann die Tags verarbeiten, und dann die Farbsymbole entfernen.
            
            # 1) Farben anwenden (IMMER, auch bei BLACK_WHITE - werden später entfernt)
            disable_comment_bg_flag = False
            if tag_config and isinstance(tag_config, dict):
                disable_comment_bg_flag = bool(tag_config.get('disable_comment_bg', False))
            
            # WICHTIG: apply_colors IMMER aufrufen (auch bei BLACK_WHITE),
            # da es die Farbsymbole hinzufügt, die dann bei BLACK_WHITE entfernt werden
            if tag_config:
                temp_quote_blocks = preprocess.apply_colors(temp_quote_blocks, tag_config, disable_comment_bg=disable_comment_bg_flag)
            
            # 2) Tag-Sichtbarkeit anwenden (wie beim normalen Text)
            # WICHTIG: apply_tag_visibility() wendet auch Translation-Hiding an (intern)!
            # Dank _in_quote=True werden Zitate jetzt korrekt behandelt!
            hidden_by_wortart = None
            if tag_config and isinstance(tag_config, dict):
                raw = tag_config.get('hidden_tags_by_wortart') or tag_config.get('hidden_tags_by_wordart') or None
                if raw:
                    hidden_by_wortart = {k.lower(): set(v) for k, v in raw.items()}
            
            if tag_mode == "TAGS" and hidden_by_wortart:
                # WICHTIG: apply_tag_visibility() wendet AUTOMATISCH Translation-Hiding an!
                # Keine separate Logik mehr nötig (entfernt in diesem Fix)!
                temp_quote_blocks = preprocess.apply_tag_visibility(temp_quote_blocks, tag_config, hidden_tags_by_wortart=hidden_by_wortart)
            elif tag_mode == "NO_TAGS":
                # KRITISCHER FIX: apply_tag_visibility() MUSS auch bei NO_TAGS aufgerufen werden!
                # Grund: Translation-Hiding passiert in apply_tag_visibility(), nicht in remove_all_tags()!
                # Ohne diesen Aufruf werden Übersetzungen in Zitaten bei NO_TAGS nicht ausgeblendet!
                temp_quote_blocks = preprocess.apply_tag_visibility(temp_quote_blocks, tag_config, hidden_tags_by_wortart=hidden_by_wortart)
                # DANACH: Entferne alle Tags (aber Übersetzungen wurden bereits ausgeblendet)
                temp_quote_blocks = preprocess.remove_all_tags(temp_quote_blocks, tag_config)
            elif tag_mode == "TAGS" and not hidden_by_wortart:
                # Auch wenn keine Tags ausgeblendet werden, müssen wir Translation-Hiding anwenden!
                # apply_tag_visibility() macht das automatisch (wenn tag_config gesetzt ist)
                temp_quote_blocks = preprocess.apply_tag_visibility(temp_quote_blocks, tag_config)
            
            # 3) Translation-Hiding wurde bereits in apply_tag_visibility() angewendet!
            # ALTE LOGIK wurde ENTFERNT, da apply_tag_visibility() das bereits macht!
            
            # 4) Bei BLACK_WHITE Mode: Entferne Farbsymbole (§, $) aus Zitaten
            if color_mode == "BLACK_WHITE":
                temp_quote_blocks = preprocess.remove_all_color_symbols(temp_quote_blocks)

            # WICHTIG: Bewahre die Zeilenstruktur innerhalb des Zitats!
            # Erstelle SEPARATE Tabellen für jede Zeile, nicht einen Fließtext.
            # Außerdem: Zitate linksbündig mit 10% kleinerer Breite (Einrückung)
            
            # Für Zitate verwenden wir den gleichen Stil wie normale Tokens
            # WICHTIG: Verwende 1.1× leading (wie normale Zeilen) statt 1.3× (_leading_for)!
            # Grund: Zitate sollen den GLEICHEN Abstand haben wie normale 3-zeilige Zeilen!
            quote_de_style = ParagraphStyle('QuoteDE', parent=base['Normal'],
                fontName='DejaVu-Bold' if de_bold else 'DejaVu', fontSize=de_size, leading=de_size * 1.1,  # 1.1× = GLEICH wie normale Zeilen!
                alignment=TA_CENTER, spaceAfter=0, spaceBefore=0, wordWrap='LTR', splitLongWords=0)

            # Reduziere die Breite um 10% für Einrückung
            quote_width_pt = frame_w * 0.9
            
            q_tables = []
            for block in temp_quote_blocks:
                if block['type'] == 'pair':
                    q_gr = block.get('gr_tokens', [])
                    q_de = block.get('de_tokens', [])
                    q_en = block.get('en_tokens', [])  # NEU: Englische Tokens für 3-sprachige Zitate
                    
                    # Erstelle eine separate Tabelle für diese Zeile
                    line_tables = build_tables_for_stream(
                        q_gr, q_de,
                        doc_width_pt=quote_width_pt,  # 10% kleiner
                        reverse_mode=False,
                        token_gr_style=style_quote_line, token_de_style=quote_de_style,
                        para_display='', para_width_pt=0.0, style_para=style_para,
                        speaker_display='', speaker_width_pt=0.0, style_speaker=style_speaker,
                        table_halign='CENTER', italic=True,  # Zentriert für Einrückung von beiden Seiten
                        en_tokens=q_en,  # NEU: Englische Tokens übergeben
                        hide_pipes=hide_pipes,  # NEU: Pipes (|) in Übersetzungen verstecken
                        tag_config=tag_config,  # NEU: Tag-Konfiguration für individuelle Breitenberechnung
                        tag_mode=tag_mode,  # NEU: Tag-Modus übergeben
                        color_mode=color_mode,  # NEU: Farb-Modus übergeben
                        is_quote=True  # KRITISCH: Zitate brauchen mehr Padding in nested tables!
                    )
                    q_tables.extend(line_tables)
            
            # KRITISCH: Setze TOPPADDING für Zitat-Zeilen (außer der ersten)!
            # build_tables_for_stream() setzt das Padding NICHT automatisch!
            # Für Zitate brauchen wir MEHR Abstand als für normalen Text:
            # - Normal: CONT_PAIR_GAP_MM (1-2mm)
            # - Zitate: CONT_PAIR_GAP_MM * 2.5 (2.5-5mm) für bessere Lesbarkeit
            from reportlab.platypus import TableStyle
            for table_idx, table in enumerate(q_tables):
                if table_idx > 0:  # Erste Zeile braucht kein TOPPADDING
                    # 2.5× mehr Abstand für Zitate als für normalen Text!
                    quote_gap = CONT_PAIR_GAP_MM * 2.5 * mm
                    table.setStyle(TableStyle([('TOPPADDING', (0,0), (-1,0), quote_gap)]))
            
            # Die Zeilenabstände werden jetzt durch TOPPADDING kontrolliert, nicht durch Spacer


            kidx, src_text = idx + 1, ''
            while kidx < len(flow_blocks) and flow_blocks[kidx]['type'] == 'blank': kidx += 1
            if kidx < len(flow_blocks) and flow_blocks[kidx]['type'] == 'source':
                src_text = (flow_blocks[kidx].get('text') or '').strip()

            block = list(q_tables)
            
            # ANTI-ORPHAN: Wenn pending_headers vorhanden, mit Zitat-Content zusammenfassen
            if pending_headers:
                block = pending_headers + block
                pending_headers.clear()
            
            if src_text:
                # Quelle vorhanden - füge sie direkt nach dem Zitat hinzu (ohne Abstand dazwischen)
                block += [Spacer(1, BLANK_MARKER_GAP_MM * mm), Paragraph('<i>'+xml_escape(src_text)+'</i>', style_source)]
                elements.append(KeepTogether(block))
                # Abstand nach der Quelle (1.5x größer als normal)
                elements.append(Spacer(1, BLANK_MARKER_GAP_MM * mm * 1.5))
                # KRITISCH: Setze idx auf MAXIMUM(kidx+1, idx+1) um Rücksprünge zu vermeiden!
                idx = max(kidx + 1, idx + 1)
            else:
                # Keine Quelle - füge Abstand direkt nach dem Zitat hinzu
                elements.append(KeepTogether(block))
                elements.append(Spacer(1, BLANK_MARKER_GAP_MM * mm * 1.5))
                # KRITISCH: Inkrementiere idx normal
                idx += 1
            
            # Überspringe trailing blanks
            while idx < len(flow_blocks) and flow_blocks[idx]['type'] == 'blank': 
                idx += 1
            continue

        if t == 'source':
            text = (b.get('text') or '').strip()
            if text:
                elements.append(KeepTogether([Paragraph('<i>'+xml_escape(text)+'</i>', style_source)]))
                elements.append(Spacer(1, CONT_PAIR_GAP_MM * mm))
            idx += 1
            continue

        # KRITISCH: para_set Handler (für § Marker) - WAR KOMPLETT VERGESSEN!
        if t == 'para_set':
            # para_set wird in group_pairs_into_flows() verwendet, um para_label zu setzen
            # Hier müssen wir ihn einfach überspringen (er wird beim nächsten flow-Block verwendet)
            idx += 1
            continue

        # KRITISCH: flow-Handler MUSS VOR pair-Handler stehen!
        if t == 'flow':
            # FLIEßTEXT + STRAUßLOGIK: IMMER alle flow-Blöcke im selben § kombinieren!
            # Dabei Multi-Row-Struktur intelligent zusammenführen!
            
            current_para_label = b.get('para_label', '')
            
            # Sammle ALLE flow-Blöcke im selben § Absatz (mit UND ohne STRAUßLOGIK)
            combined_gr_tokens = []
            combined_de_tokens = []
            combined_en_tokens = []
            flow_blocks_in_para = []
            first_para_label = None  # Merke § Symbol vom ersten Block!
            
            # STRAUßLOGIK: Multi-Row-Struktur für kombinierten Block
            has_any_strauss = False
            combined_gr_rows = []  # Liste der GR-Rows (erste = Hauptzeile)
            combined_de_rows = []
            combined_en_rows = []
            
            temp_idx = idx
            while temp_idx < len(flow_blocks):
                block = flow_blocks[temp_idx]
                
                if block.get('type') == 'blank':
                    temp_idx += 1
                    continue
                
                if block.get('type') != 'flow':
                    break
                
                block_para = block.get('para_label', '')
                
                # Erster Block: Merke § Symbol!
                if first_para_label is None and block_para:
                    first_para_label = block_para
                
                # Prüfe ob noch im selben § Absatz
                if block_para and block_para != first_para_label:
                    break
                
                # Diesen flow-Block hinzufügen
                flow_blocks_in_para.append(block)
                
                # STRAUßLOGIK: Hat dieser Block Multi-Row-Struktur?
                block_has_strauss = block.get('_has_strauss', False)
                
                if block_has_strauss:
                    has_any_strauss = True
                    # Hole Multi-Row-Daten
                    block_gr_rows = block.get('_gr_rows', [])
                    block_de_rows = block.get('_de_rows', [])
                    block_en_rows = block.get('_en_rows', [])
                    
                    # WICHTIG: _gr_rows[0] ist die Hauptzeile (schon in gr_tokens enthalten!)
                    # Wir müssen nur die ALTERNATIVEN (ab Index 1) hinzufügen!
                    if len(combined_gr_rows) == 0:
                        # Erstes Mal: Initialisiere mit aktuellen Tokens
                        combined_gr_rows.append(list(combined_gr_tokens))
                        combined_de_rows.append(list(combined_de_tokens))
                        combined_en_rows.append(list(combined_en_tokens))
                    
                    # Erweitere die Hauptzeile ZUERST mit den Tokens dieses Blocks
                    combined_gr_rows[0].extend(block.get('gr_tokens', []))
                    combined_de_rows[0].extend(block.get('de_tokens', []))
                    combined_en_rows[0].extend(block.get('en_tokens', []))
                    
                    # Füge die ALTERNATIVEN-Rows hinzu (ab Index 1)
                    for alt_idx in range(1, len(block_gr_rows)):
                        # Jede Alternative-Row: Padding bis zur Position dieses Blocks + Alternative
                        current_pos = len(combined_gr_tokens)  # Position VOR dem aktuellen Block
                        
                        # Erstelle neue Alternative-Row
                        gr_alt_row = ([''] * current_pos) + block_gr_rows[alt_idx]
                        de_alt_row = ([''] * current_pos) + block_de_rows[alt_idx]
                        en_alt_row = ([''] * current_pos) + block_en_rows[alt_idx]
                        
                        combined_gr_rows.append(gr_alt_row)
                        combined_de_rows.append(de_alt_row)
                        combined_en_rows.append(en_alt_row)
                    
                else:
                    # Kein STRAUß: Erweitere nur Hauptzeile (wenn vorhanden)
                    if len(combined_gr_rows) > 0:
                        combined_gr_rows[0].extend(block.get('gr_tokens', []))
                        combined_de_rows[0].extend(block.get('de_tokens', []))
                        combined_en_rows[0].extend(block.get('en_tokens', []))
                
                # Erweitere die Token-Listen für den kombinierten Block
                combined_gr_tokens.extend(block.get('gr_tokens', []))
                combined_de_tokens.extend(block.get('de_tokens', []))
                combined_en_tokens.extend(block.get('en_tokens', []))
                
                temp_idx += 1
            
            print(f"FLIEßTEXT + STRAUßLOGIK: Kombiniere {len(flow_blocks_in_para)} flow-Blöcke → {len(combined_gr_tokens)} Tokens (STRAUß={has_any_strauss}, § '{first_para_label}')", flush=True)
            
            # WICHTIG: Sammle ALLE Kommentare aus allen kombinierten flow-Blöcken!
            combined_comments = []
            for block in flow_blocks_in_para:
                if 'comments' in block:
                    combined_comments.extend(block['comments'])
            
            # Erstelle kombinierten Block mit § Symbol vom ersten Block!
            combined_block = {
                'type': 'flow',
                'gr_tokens': combined_gr_tokens,
                'de_tokens': combined_de_tokens,
                'en_tokens': combined_en_tokens,
                'para_label': first_para_label or '',  # WICHTIG: § vom ersten Block!
                'speaker': b.get('speaker', ''),
                'has_en': bool(combined_en_tokens),
            }
            
            # WICHTIG: Füge gesammelte Kommentare hinzu!
            if combined_comments:
                combined_block['comments'] = combined_comments
                print(f"  → {len(combined_comments)} Kommentare übernommen", flush=True)
            
            # STRAUßLOGIK: Füge Multi-Row-Struktur hinzu, wenn vorhanden!
            if has_any_strauss and combined_gr_rows:
                combined_block['_has_strauss'] = True
                combined_block['_gr_rows'] = combined_gr_rows
                combined_block['_de_rows'] = combined_de_rows
                combined_block['_en_rows'] = combined_en_rows
                print(f"  → Multi-Row: GR={len(combined_gr_rows)} rows, DE={len(combined_de_rows)} rows, EN={len(combined_en_rows)} rows", flush=True)
            
            try:
                flow_tables = build_flow_tables(combined_block)
                valid_tables = [t for t in flow_tables if t is not None]
                if valid_tables:
                    # ANTI-ORPHAN: Wenn pending_headers vorhanden, mit Content zusammenfassen
                    if pending_headers:
                        # Kombiniere Überschriften + erste Tabelle in KeepTogether
                        first_table = valid_tables[0]
                        elements.append(KeepTogether([*pending_headers, first_table]))
                        pending_headers.clear()
                        # Rest der Tabellen normal wrappen
                        for table in valid_tables[1:]:
                            elements.append(KeepTogether([table]))
                    else:
                        # KRITISCH: Jede Tabelle (GR+DE+EN Zeilen) in KeepTogether wrappen
                        # Verhindert Page-Breaks zwischen antiker Zeile und ihren Übersetzungen!
                        for table in valid_tables:
                            elements.append(KeepTogether([table]))
                
                elements.append(Spacer(1, CONT_PAIR_GAP_MM * mm))
                # WICHTIG: Übergebe combined_block statt b (enthält alle gesammelten Kommentare!)
                render_block_comments(combined_block, elements, doc)
                
            except Exception as e:
                logger.exception("Prosa_Code: build_flow_tables() ERROR: %s", e)
            
            # Springe zu temp_idx (alle kombiniert verarbeitet)
            idx = temp_idx
            continue

        # NEU: Handler für einzelne Paare (Lyrik-Modus & Zitate mit Straußlogik)
        # Bewahrt die Zeilenstruktur wie bei Zitaten
        if t == 'pair':
            # KRITISCH: pair Blöcke haben ROHE Zeilen in 'gr', 'de', 'en' (mit Markern, Tags, etc.)
            # Diese müssen durch tokenize() verarbeitet werden!
            gr_line = b.get('gr_tokens') or b.get('gr', '')
            de_line = b.get('de_tokens') or b.get('de', '')
            en_line = b.get('en_tokens') or b.get('en', '')
            
            # Tokenisiere die rohen Zeilen (entfernt Marker, normalisiert, etc.)
            if isinstance(gr_line, str):
                gr_tokens = tokenize(gr_line) if gr_line else []
            else:
                gr_tokens = gr_line or []
                
            if isinstance(de_line, str):
                de_tokens = tokenize(de_line) if de_line else []
            else:
                de_tokens = de_line or []
                
            if isinstance(en_line, str):
                en_tokens = tokenize(en_line) if en_line else []
            else:
                en_tokens = en_line or []
            
            para_label = b.get('para_label', '')
            speaker = b.get('speaker', '')
            is_lyrik = b.get('_is_lyrik', False)  # NEU: Prüfe ob Lyrik-Block
            has_alternatives = b.get('_has_alternatives', False)  # NEU: Prüfe ob Straußlogik
            
            # NEU: BEDEUTUNGS-STRAUß - Wenn Alternativen vorhanden, erstelle EINE Tabelle mit mehreren Zeilen
            if has_alternatives:
                gr_alternatives = b.get('_gr_alternatives', [[]])  # NEU: Auch GR Alternativen!
                de_alternatives = b.get('_de_alternatives', [[]])
                en_alternatives = b.get('_en_alternatives', [[]])
                
                # KRITISCH: Rufe build_tables_for_stream DIREKT auf (wie in Poesie)!
                # Übergebe die Alternativen als gr_tokens_alternatives, de_tokens_alternatives, en_tokens_alternatives
                # Dies erstellt EINE Tabelle mit ALLEN Alternativen als separate Zeilen!
                
                # Berechne Spaltenbreiten (wie in normalem Flow)
                pwidth = para_width_pt(para_label) if para_label else 0.0
                swidth = speaker_width_pt(speaker) if speaker and any_speaker else 0.0
                
                # Rufe build_tables_for_stream direkt mit Alternativen auf
                pair_tables = build_tables_for_stream(
                    gr_tokens, de_tokens,  # Primäre Tokens (werden ignoriert wenn alternatives vorhanden)
                    doc_width_pt=frame_w,
                    reverse_mode=False,
                    token_gr_style=token_gr, token_de_style=token_de,
                    para_display=para_label, para_width_pt=pwidth, style_para=style_para,
                    speaker_display=(f'[{speaker}]:' if speaker else ''), speaker_width_pt=swidth, style_speaker=style_speaker,
                    table_halign='LEFT', italic=False,
                    en_tokens=en_tokens,
                    hide_pipes=hide_pipes,
                    tag_config=tag_config,
                    base_num=b.get('base'),
                    line_comment_colors=line_comment_colors,
                    block=b,
                    tag_mode=tag_mode,
                    color_mode=color_mode,  # NEU: Farb-Modus übergeben
                    # NEU: Übergebe Alternativen!
                    gr_tokens_alternatives=gr_alternatives if len(gr_alternatives) > 1 else None,
                    de_tokens_alternatives=de_alternatives if len(de_alternatives) > 1 else None,
                    en_tokens_alternatives=en_alternatives if len(en_alternatives) > 1 else None
                )
                
                if pair_tables:
                    valid_tables = [t for t in pair_tables if t is not None]
                    if valid_tables:
                        # ANTI-ORPHAN: Wenn pending_headers vorhanden, mit Content zusammenfassen
                        if pending_headers:
                            try:
                                elements.append(KeepTogether([*pending_headers, *valid_tables]))
                            except (TypeError, ValueError) as e:
                                logger.warning("Prosa_Code: KeepTogether failed for alternatives with headers: %s", e)
                                elements.extend(pending_headers)
                                elements.extend(valid_tables)
                            pending_headers.clear()
                        else:
                            try:
                                elements.append(KeepTogether(valid_tables))
                            except (TypeError, ValueError) as e:
                                logger.warning("Prosa_Code: KeepTogether failed for alternatives, appending individually: %s", e)
                                elements.extend(valid_tables)
                        
                        # Abstand nach Alternativen - verwende CONT_PAIR_GAP_MM für einheitliche Abstände
                        if is_lyrik:
                            # KORREKTUR: Gleicher Abstand wie normaler Prosa-Text (CONT_PAIR_GAP_MM)
                            elements.append(Spacer(1, CONT_PAIR_GAP_MM * mm))
                        else:
                            elements.append(Spacer(1, CONT_PAIR_GAP_MM * mm))
                
                # Kommentare rendern (nur einmal nach allen Alternativen)
                render_block_comments(b, elements, doc)
                idx += 1
                continue
            
            # Normaler Fall: KEINE Alternativen
            # Erstelle eine Pseudo-Flow-Struktur für eine einzelne Zeile
            pseudo_flow = {
                'type': 'flow',
                'gr_tokens': gr_tokens,
                'de_tokens': de_tokens,
                'en_tokens': en_tokens,
                'para_label': para_label,
                'speaker': speaker,
                'has_en': bool(en_tokens)
            }
            
            # Rendere als einzelne Zeile (behält Zeilenstruktur)
            pair_tables = build_flow_tables(pseudo_flow)
            if pair_tables:
                # DEFENSIVE: Prüfe auf gültige Tables (nicht None/leer)
                valid_tables = [t for t in pair_tables if t is not None]
                if valid_tables:
                    # ANTI-ORPHAN: Wenn pending_headers vorhanden, mit Content zusammenfassen
                    if pending_headers:
                        # Kombiniere Überschriften + alle Tabellen in KeepTogether
                        try:
                            elements.append(KeepTogether([*pending_headers, *valid_tables]))
                        except (TypeError, ValueError) as e:
                            logger.warning("Prosa_Code: KeepTogether failed for pair with headers: %s", e)
                            elements.extend(pending_headers)
                            elements.extend(valid_tables)
                        pending_headers.clear()
                    else:
                        # Keine pending_headers - normale Behandlung
                        try:
                            elements.append(KeepTogether(valid_tables))
                        except (TypeError, ValueError) as e:
                            # Fallback: Einzeln hinzufügen
                            logger.warning("Prosa_Code: KeepTogether failed for pair, appending individually: %s", e)
                            elements.extend(valid_tables)
                    
                    # WICHTIG: Lyrik-Bereiche verwenden GLEICHEN Abstand wie normaler Prosa-Text!
                    # Verwende CONT_PAIR_GAP_MM (der bereits tag_mode berücksichtigt)
                    if is_lyrik:
                        # KORREKTUR: Verwende CONT_PAIR_GAP_MM statt hartcodiertem 3.0mm
                        # Damit haben Lyrik-Bereiche identische Abstände wie § Prosa-Text
                        elements.append(Spacer(1, CONT_PAIR_GAP_MM * mm))
            
            # KRITISCH: Kommentare NACH den Tabellen rendern, damit sie nach dem Text erscheinen!
            render_block_comments(b, elements, doc)
            
            idx += 1
            continue

    # DIAGNOSE: Logging nach Element-Erstellung, vor doc.build()
    logger.info("Prosa_Code.create_pdf: Element creation complete (elements=%d)", len(elements))
    print(f"Prosa_Code: Element creation complete (elements={len(elements)})", flush=True)
    
    # ANTI-ORPHAN: Flush pending_headers am Dokumentende (Edge Case)
    # Falls am Ende noch Überschriften ohne folgenden Content existieren
    if pending_headers:
        logger.warning("Prosa_Code: %d pending headers at document end - adding directly", len(pending_headers))
        elements.extend(pending_headers)
        pending_headers.clear()
    
    try:
        sys.stdout.flush()
    except Exception:
        pass

    # Build PDF with error handling and file verification
    try:
        # Flush stdout before starting (critical for CI visibility)
        try:
            sys.stdout.flush()
            sys.stderr.flush()
        except Exception:
            pass
        
        logger.info("Prosa_Code: starting doc.build() for %s (elements=%d)", pdf_name, len(elements))
        print(f"Prosa_Code: BUILD START for {os.path.basename(pdf_name)} (elements={len(elements)})", flush=True)
        
        # Check if file already exists (for debugging)
        if os.path.exists(pdf_name):
            logger.warning("Prosa_Code: PDF file %s already exists, will be overwritten", pdf_name)
        
        # Actual build - this is the blocking call
        import time
        build_start = time.time()
        doc.build(elements)
        build_duration = time.time() - build_start
        
        # Flush again after build
        try:
            sys.stdout.flush()
            sys.stderr.flush()
        except Exception:
            pass
        
        # Verify PDF was created
        if os.path.exists(pdf_name):
            file_size = os.path.getsize(pdf_name)
            logger.info("Prosa_Code: doc.build() completed for %s (file_size=%d bytes, duration=%.1fs)", pdf_name, file_size, build_duration)
            print(f"Prosa_Code: BUILD SUCCESS for {os.path.basename(pdf_name)} ({file_size} bytes, {build_duration:.1f}s)", flush=True)
        else:
            logger.error("Prosa_Code: doc.build() completed but PDF file %s does NOT exist!", pdf_name)
            print(f"Prosa_Code: BUILD FAILED - file not created: {pdf_name}", flush=True)
            raise FileNotFoundError(f"PDF file {pdf_name} was not created after doc.build()")
    except Exception as e:
        logger.exception("Prosa_Code: doc.build() FAILED for %s: %s", pdf_name, str(e))
        print(f"Prosa_Code: BUILD ERROR for {os.path.basename(pdf_name)}: {e}", flush=True)
        raise

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
                       color_mode="COLOR", tag_mode="TAGS")
            print(f"✓ PDF erstellt → {out_normal}")

            out_fett = output_name_for_label(label, reverse=False) + "_Fett"
            create_pdf(blocks, out_fett, strength="GR_FETT",
                       color_mode="COLOR", tag_mode="TAGS")
            print(f"✓ PDF erstellt → {out_fett}")

            out_rev = output_name_for_label(label, reverse=True)
            create_pdf(blocks, out_rev, strength="GR_FETT",
                       color_mode="COLOR", tag_mode="TAGS")
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
                       color_mode="COLOR", tag_mode="TAGS")
            print(f"✓ PDF erstellt → {out_normal}")
            
            out_fett = output_name_for_label(label, reverse=False) + "_Fett"
            create_pdf(blocks, out_fett, strength="GR_FETT",
                       color_mode="COLOR", tag_mode="TAGS")
            print(f"✓ PDF erstellt → {out_fett}")
            
            out_rev = output_name_for_label(label, reverse=True)
            create_pdf(blocks, out_rev, strength="GR_FETT",
                       color_mode="COLOR", tag_mode="TAGS")
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

