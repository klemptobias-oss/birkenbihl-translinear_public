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
GR_SIZE = 8.4
DE_SIZE = 7.8
SECTION_SIZE = 12.0

# Titel (geschweifte Klammern)
TITLE_BRACE_SIZE   = 18.0
TITLE_SPACE_AFTER  = 6.0   # mm

# Überschriften (eckige Klammern / Gleichheitszeichen)
SECTION_SIZE       = 11.0  # kleiner als vorher (war 12.0)
SECTION_SPACE_BEFORE_MM = 4.0  # kleinerer Abstand vor Überschrift
SECTION_SPACE_AFTER_MM  = 3.0  # kleinerer Abstand nach Überschrift

INTER_PAIR_GAP_MM = 12.0
INTRA_PAIR_GAP_MM = 1

# Sprecher-Laterne (links)
SPEAKER_COL_MIN_MM = .0   # breitere Laterne
SPEAKER_GAP_MM     = 3.0    # größerer fester Abstand zwischen Laterne und Text
NUM_GAP_MM         = 1.5
SPEAKER_EXTRA_PAD_PT = 5.0   # zusätzlicher Puffer in Punkten, verhindert Zeilenumbruch von ":" etc.

CELL_PAD_LR_PT      = 2.1
SAFE_EPS_PT         = 5.5
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
    'TAG_WIDTH_FACTOR_TAGGED': 0.9,    # vorher effektiv ~1.30 → etwas enger
    'TOKEN_BASE_PAD_PT_TAGS': 1.0,     # Grundpuffer bei getaggten Tokens (klein)
    'TOKEN_BASE_PAD_PT_NOTAGS': 1.3,   # Grundpuffer bei ungetaggten Tokens (sichtbar)
    'NUM_COLOR': colors.HexColor('#777'),
    'NUM_SIZE_FACTOR': 0.84,
    # Versmaß (wie im Epos-Code)
    'TOPLINE_Y_FACTOR': 2.5,
    'LONG_THICK_PT': 1.4,
    'BREVE_HEIGHT_PT': 3.8,
    'BAR_THICK_PT': 0.9,
    'TAG_WIDTH_FACTOR': 0.85,  # wie im Epos-Code
}

# ========= Tags/Regex =========
# Standard-Tag-Definitionen (können durch Tag-Config überschrieben werden)
DEFAULT_SUP_TAGS = {'N','D','G','A','V','Adj','Pt','Prp','Adv','Kon','Art','≈','Kmp','ij','Sup'}
DEFAULT_SUB_TAGS = {'Prä','Imp','Aor','Per','Plq','Fu','Inf','Imv','Akt','Med','Pas','Knj','Op','Pr','AorS','M/P'}

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
RE_TAG_NAKED = re.compile(r'\(\s*[A-Za-z/≈äöüßÄÖÜ]+\s*\)')
RE_GREEK_CHARS = re.compile(r'[\u0370-\u03FF\u1F00-\u1FFF]')
RE_TAG_FINDALL = re.compile(r'\(\s*([A-Za-z/≈äöüßÄÖÜ]+)\s*\)')
RE_TAG_STRIP   = re.compile(r'\(\s*[A-Za-z/≈äöüßÄÖÜ]+\s*\)')
RE_LEADING_BAR_COLOR = re.compile(r'^\|\s*([+\-#§$])')  # |+ |# |- am Tokenanfang

# Sprecher-Tokens: [Χορ:] bzw. Λυσ:
RE_SPK_BRACKET = re.compile(r'^\[[^\]]*:\]$')                         # [Χορ:]
RE_SPEAKER_GR  = re.compile(r'^[\u0370-\u03FF\u1F00-\u1FFF]+:$')      # Λυσ:

RE_SECTION         = re.compile(r'^\s*\[\[\s*(.+?)\s*\]\]\s*$')
RE_SECTION_SINGLE  = re.compile(r'^\s*\[\s*(.+?)\s*\]\s*$')
RE_BRACE_TITLE     = re.compile(r'^\s*\{\s*(.+?)\s*\}\s*$')           # {Titel}

# Label-Token wie [12], [12a], (12), (12a) – optional mit Punkt
RE_LABEL_TOKEN     = re.compile(r'^[\[\(]\s*(\d+)([a-z])?\s*[\]\)]\.?$', re.IGNORECASE)
RE_LABEL_STRIP     = re.compile(r'^(?:\[\s*\d+[a-z]?\s*\]\.?\s*|\(\s*\d+[a-z]?\s*\)\.?\s*)', re.IGNORECASE)

# ========= Utils =========
def _leading_for(size: float) -> float: return round(size * 1.30 + 0.6, 1)
def xml_escape(text:str) -> str:        return html.escape(text or '', quote=False)

def is_empty_or_sep(line:str) -> bool:
    t = (line or '').strip()
    return (not t) or t.upper() in {'[FREIE ZEILE]', '[ENTERZEICHEN]'} or t.startswith('---')

def normalize_spaces(s:str) -> str:
    return re.sub(r'\s+', ' ', (s or '').strip())

def pre_substitutions(s:str) -> str:
    if not s: return s
    punct = r'(?:,|\.|;|:|!|\?|%|…|\u00B7|\u0387|\u037E)'
    s = re.sub(rf'\s+{punct}', lambda m: m.group(0).lstrip(), s)
    s = re.sub(r'([\(\[\{\«"‹''])\s+', r'\1', s)
    s = re.sub(r'\s+([\)\]\}\»"›''])', r'\1', s)
    s = re.sub(r'[\u200B\u200C\u200D\uFEFF\u00A0]', '', s)
    s = re.sub(r'\(([#\+\-])', r'\1(', s)
    s = re.sub(r'\[([#\+\-])', r'\1[', s)
    s = re.sub(r'\{([#\+\-])', r'\1{', s)
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

def is_greek_line(line: str) -> bool:
    """
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

def _color_from_marker(ch):
    if ch == '+': return '#1E90FF'
    if ch == '-': return '#228B22'
    if ch == '#': return '#FF0000'
    if ch == '§': return '#FF00FF'  # Magenta
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
        return s[1:] if s and s[0] in '#+-' else s

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
    line = normalize_spaces(pre_substitutions(line or ''))
    if not line: return []
    raw = line.split(' ')
    out, buf = [], []
    for tok in raw:
        if not tok: continue
        if buf:
            buf.append(tok)
            if tok.endswith(']'): out.append(' '.join(buf)); buf = []
            continue
        if tok.startswith('[') and not tok.endswith(']'):
            buf = [tok]; continue
        out.append(tok)
    if buf: out.append(' '.join(buf))
    return out

def _is_label_token(t: str):
    return bool(RE_LABEL_TOKEN.match(t or ''))

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
APOSTS = ('\u2019', '\u02BC')  # ’ und ʼ

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

    if is_greek_row:
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
    elif '§' in raw: color_pos = raw.find('§'); color = '#FF00FF'  # Magenta
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

    if is_greek_row:
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

# ========= Parser =========
def process_input_file(fname:str):
    with open(fname, encoding='utf-8') as f:
        raw = [ln.rstrip('\n') for ln in f]

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

        # [[Abschnitt]] / [Abschnitt]
        sec = detect_section(line)
        if sec:
            blocks.append({'type':'section', 'text':sec})
            i += 1; continue

        # Klassifikation: Label/Sprecher vorn für Klassifizierung weg
        line_cls = _strip_speaker_prefix_for_classify(line)
        if is_greek_line(line_cls):
            gr_line = line
            i += 1
            while i < len(raw) and is_empty_or_sep(raw[i]): i += 1

            de_line = ''
            if i < len(raw):
                cand = (raw[i] or '').strip()
                cand_cls = _strip_speaker_prefix_for_classify(cand)
                if not is_greek_line(cand_cls):
                    de_line = cand
                    i += 1

            # Tokenisieren & führende Label/Sprecher abwerfen (beide, beliebige Reihenfolge)
            gr_tokens = tokenize(gr_line)
            de_tokens = tokenize(de_line)

            lbl_gr, base_gr, sp_gr, gr_tokens = split_leading_label_and_speaker(gr_tokens)
            lbl_de, base_de, sp_de, de_tokens = split_leading_label_and_speaker(de_tokens)

            line_label = lbl_gr or lbl_de or ''
            base_num   = base_gr if base_gr is not None else base_de
            speaker    = sp_gr or ''   # DE-Sprecher verwerfen

            # WICHTIG: Elisions-Übertragung direkt nach dem Tokenizing anwenden
            gr_tokens = propagate_elision_markers(gr_tokens)

            blocks.append({
                'type':'pair',
                'speaker': speaker,
                'label': line_label,
                'base':  base_num,       # wichtig fürs Stufenlayout
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
def build_tables_for_pair(gr_tokens, de_tokens, *,
                          speaker:str = '',
                          line_label:str = '',
                          doc_width_pt:float = 0.0,
                          token_gr_style=None, token_de_style=None, num_style=None, style_speaker=None,
                          gr_bold:bool = False,
                          reserve_speaker_col: bool = False,
                          indent_pt: float = 0.0,
                          global_speaker_width_pt: float = None,
                          meter_on: bool = False):
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
    cols = max(len(gr_tokens), len(de_tokens))
    gr = gr_tokens[:] + [''] * (cols - len(gr_tokens))
    de = de_tokens[:] + [''] * (cols - len(de_tokens))

    # Effektive cfg abhängig von meter_on (Versmaß an/aus)
    eff_cfg = dict(CFG)
    if meter_on:
        eff_cfg['CELL_PAD_LR_PT'] = 0.0   # MUSS 0 SEIN für lückenlose Topline
        eff_cfg['SAFE_EPS_PT']     = 3.0  # wie im Epos angemessen klein
    else:
        eff_cfg['CELL_PAD_LR_PT'] = 2.1   # bisheriger Standard
        eff_cfg['SAFE_EPS_PT']     = 5.5  # bisheriger Standard

    # Breiten
    widths = []
    for k in range(cols):
        w_gr = visible_measure_token(gr[k], font=token_gr_style.fontName, size=token_gr_style.fontSize, cfg=eff_cfg, is_greek_row=True)  if gr[k] else 0.0
        w_de = visible_measure_token(de[k], font=token_de_style.fontName, size=token_de_style.fontSize, cfg=eff_cfg, is_greek_row=False) if de[k] else 0.0
        widths.append(max(w_gr, w_de))

    tables, i, first_slice = [], 0, True
    gap_pts = INTRA_PAIR_GAP_MM * MM

    while i < cols:
        acc, j = 0.0, i
        while j < cols:
            w = widths[j]
            if acc + w > avail_tokens_w and j > i: break
            acc += w; j += 1

        slice_gr, slice_de, slice_w = gr[i:j], de[i:j], widths[i:j]

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
            html_ = format_token_markup(tok, is_greek_row=is_gr, gr_bold=(gr_bold if is_gr else False), remove_bars_instead=True)
            # Spaltenbreite dieser Zelle
            if is_gr and idx_in_slice is not None:
                this_w = slice_w[idx_in_slice]
                measured = visible_measure_token(tok, font=token_gr_style.fontName, size=token_gr_style.fontSize, cfg=eff_cfg, is_greek_row=True)
                html_centered = center_word_in_width(html_, measured, this_w, token_gr_style.fontName, token_gr_style.fontSize)
                return Paragraph(html_centered, token_gr_style)
            else:
                # DE-Zeile: ebenfalls zentrieren
                # idx_in_slice ist bei DE nicht gesetzt; nutze parallelen Index über enumerate weiter unten
                return html_  # wird später im de_cells-Block zentriert

        gr_cells = [cell(True,  t, k) for k, t in enumerate(slice_gr)]

        # DE-Zellen mit gleicher Zentrierung wie im Epos
        de_cells = []
        for idx, t in enumerate(slice_de):
            if not t:
                de_cells.append(Paragraph('', token_de_style))
                continue
            de_html = format_token_markup(t, is_greek_row=False, gr_bold=False, remove_bars_instead=True)
            de_width = slice_w[idx]
            de_meas  = visible_measure_token(t, font=token_de_style.fontName, size=token_de_style.fontSize, cfg=eff_cfg, is_greek_row=False)
            de_html_centered = center_word_in_width(de_html, de_meas, de_width, token_de_style.fontName, token_de_style.fontSize)
            de_cells.append(Paragraph(de_html_centered, token_de_style))

        # Linke Spalten: NUM → Gap → SPRECHER → Gap → INDENT → Tokens
        num_para_gr = _p(xml_escape(f'[{line_label}]') if (first_slice and line_label) else '\u00A0', num_style)
        num_para_de = _p('\u00A0', num_style)
        num_gap_gr  = _p('', token_gr_style); num_gap_de = _p('', token_de_style)

        sp_para_gr  = _p(f'<font color="#777">{xml_escape(f"[{speaker}]:")}</font>', style_speaker) if (first_slice and sp_w>0 and speaker) else _p('', style_speaker)
        sp_para_de  = _p('', style_speaker)
        sp_gap_gr   = _p('', token_gr_style); sp_gap_de = _p('', token_de_style)

        indent_gr   = _p('', token_gr_style)
        indent_de   = _p('', token_de_style)

        row_gr = [num_para_gr, num_gap_gr, sp_para_gr, sp_gap_gr, indent_gr] + gr_cells
        row_de = [num_para_de, num_gap_de, sp_para_de, sp_gap_de, indent_de] + de_cells
        col_w  = [num_w, num_gap, sp_w,        sp_gap,   indent_w] + slice_w

        tbl = Table([row_gr, row_de], colWidths=col_w, hAlign='LEFT')

        if meter_on:
            # Versmaß: KEIN Innenabstand, sonst entstehen Lücken zwischen Flowables
            tbl.setStyle(TableStyle([
                ('LEFTPADDING',   (0,0), (-1,-1), 0.0),
                ('RIGHTPADDING',  (0,0), (-1,-1), 0.0),
                ('TOPPADDING',    (0,0), (-1,-1), 0.0),
                ('BOTTOMPADDING', (0,0), (-1,-1), 0.0),
                ('VALIGN',        (0,0), (-1,-1), 'BOTTOM'),
                ('ALIGN',         (0,0), (0,-1), 'RIGHT'),  # Nummern rechts
                ('ALIGN',         (1,0), (-1,-1), 'LEFT'),  # Rest links (wie im Epos)
                ('BOTTOMPADDING', (0,0), (-1,0), gap_pts/2.0),
                ('TOPPADDING',    (0,1), (-1,1), gap_pts/2.0),
                ('RIGHTPADDING',  (2,0), (2,-1), 2.0),      # Sprecher-Spalte darf etwas Luft haben
            ]))
        else:
            # Nicht-Versmaß: bisheriges Padding-Verhalten
            tbl.setStyle(TableStyle([
                ('LEFTPADDING',   (0,0), (-1,-1), CELL_PAD_LR_PT),
                ('RIGHTPADDING',  (0,0), (-1,-1), CELL_PAD_LR_PT),
                ('TOPPADDING',    (0,0), (-1,-1), 0.0),
                ('BOTTOMPADDING', (0,0), (-1,-1), 0.0),
                ('VALIGN',        (0,0), (-1,-1), 'BOTTOM'),
                ('ALIGN',         (0,0), (0,-1), 'RIGHT'),
                ('ALIGN',         (1,0), (-1,-1), 'LEFT'),
                ('BOTTOMPADDING', (0,0), (-1,0), gap_pts/2.0),
                ('TOPPADDING',    (0,1), (-1,1), gap_pts/2.0),
                ('RIGHTPADDING',  (2,0), (2,-1), 2.0),
            ]))
        tables.append(tbl)
        first_slice, i = False, j

    return tables

# ========= PDF-Erzeugung =========
def create_pdf(blocks, pdf_name:str, *, gr_bold:bool,
               de_bold:bool = False,
               versmass_display: bool = False,
               tag_mode: str = "TAGS",
               placement_overrides: dict[str, str] | None = None,
               tag_config: dict | None = None):

    # NoTags-Schalter global setzen, wenn Dateiname auf _NoTags.pdf endet
    global CURRENT_IS_NOTAGS
    CURRENT_IS_NOTAGS = pdf_name.lower().endswith("_notags.pdf")
    # Optionale Hoch/Tief/Off-Overrides aus Preprocess/UI aktivieren
    global PLACEMENT_OVERRIDES
    PLACEMENT_OVERRIDES = dict(placement_overrides or {})
    
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
        fontName='DejaVu-Bold', fontSize=SECTION_SIZE, leading=_leading_for(SECTION_SIZE),
        alignment=TA_LEFT, spaceBefore=SECTION_SPACE_BEFORE_MM*MM,
        spaceAfter=SECTION_SPACE_AFTER_MM*MM, keepWithNext=True)
    style_title = ParagraphStyle('TitleBrace', parent=base['Normal'],
        fontName='DejaVu-Bold', fontSize=TITLE_BRACE_SIZE, leading=_leading_for(TITLE_BRACE_SIZE),
        alignment=TA_CENTER, spaceAfter=TITLE_SPACE_AFTER*MM, keepWithNext=True)
    style_speaker = ParagraphStyle('Speaker', parent=base['Normal'],
        fontName='DejaVu', fontSize=DE_SIZE, leading=_leading_for(DE_SIZE),
        alignment=TA_LEFT, textColor=colors.HexColor('#777'))
        
             # Globale Sprecher-Spaltenbreite (max über alle Sprecher) mit Puffer
    def _speaker_col_width(text:str) -> float:
        if not text:
            return SPEAKER_COL_MIN_MM * MM
        disp = f'[{text}]:'
        w = _sw(disp, style_speaker.fontName, style_speaker.fontSize)
        return max(SPEAKER_COL_MIN_MM * MM, w + SPEAKER_EXTRA_PAD_PT)

    all_speakers = [ (b.get('speaker') or '') for b in blocks if b.get('type') == 'pair' and (b.get('speaker') or '') ]
    global_speaker_width_pt = max([_speaker_col_width(s) for s in all_speakers], default=SPEAKER_COL_MIN_MM * MM)

    elements = []

    # Sprecher-Laterne global reservieren, sobald irgendwo ein Sprecher vorkommt
    reserve_all_speakers = any(b.get('type')=='pair' and (b.get('speaker') or '') for b in blocks)

    # Stufenlayout: kumulative Breite pro Basisvers
    cum_width_by_base = {}  # base:int -> float pt

    i = 0
    while i < len(blocks):
        b = blocks[i]
        t = b['type']

        if t == 'title_brace':
            elements.append(Paragraph(xml_escape(b['text']), style_title))
            elements.append(Spacer(1, 2*MM))
            i += 1; continue

        if t == 'section':
            para = Paragraph(xml_escape(b['text']), style_section)

            # Sammle die nächsten 2 Textzeilen für KeepTogether
            next_elements = [para]
            text_lines_found = 0
            temp_i = i + 1

            # Suche nach den nächsten 2 Textzeilen (pairs)
            while temp_i < len(blocks) and text_lines_found < 2:
                next_b = blocks[temp_i]
                if next_b['type'] == 'pair':
                    # Erstelle die Tabellen für diese Zeile
                    next_gr_tokens = next_b.get('gr_tokens', [])[:]
                    next_de_tokens = next_b.get('de_tokens', [])[:]
                    next_speaker = next_b.get('speaker') or ''
                    next_line_label = next_b.get('label') or ''
                    next_base_num = next_b.get('base')

                    next_indent_pt = 0.0
                    if next_base_num is not None:
                        next_indent_pt = max(0.0, cum_width_by_base.get(next_base_num, 0.0))

                    # Prüfe auf Versmaß-Marker für diese temporäre Zeile
                    next_has_versmass = has_meter_markers(next_gr_tokens)

                    next_tables = build_tables_for_pair(
                        next_gr_tokens, next_de_tokens,
                        speaker=next_speaker,
                        line_label=next_line_label,
                        doc_width_pt=frame_w,
                        token_gr_style=token_gr, token_de_style=token_de,
                        num_style=num_style, style_speaker=style_speaker,
                        gr_bold=gr_bold,
                        reserve_speaker_col=reserve_all_speakers,
                        indent_pt=next_indent_pt,
                        global_speaker_width_pt=global_speaker_width_pt,
                        meter_on=versmass_display and next_has_versmass
                    )

                    next_elements.extend(next_tables)
                    text_lines_found += 1
                    # Füge Abstand zwischen den Textzeilen in der KeepTogether-Gruppe hinzu
                    # (außer nach der letzten Zeile)
                    if text_lines_found < 2:  # Noch nicht die letzte Zeile erreicht
                        next_elements.append(Spacer(1, INTER_PAIR_GAP_MM * MM))

                    # Nach dem Rendern: Breite gutschreiben (aber nur für diese temporäre Berechnung)
                    if next_base_num is not None:
                        next_w = measure_rendered_line_width(
                            next_gr_tokens, next_de_tokens,
                            gr_bold=gr_bold, is_notags=CURRENT_IS_NOTAGS,
                            remove_bars_instead=True
                        )
                        # Hier nicht in cum_width_by_base eintragen, da das später nochmal gemacht wird

                elif next_b['type'] == 'section':
                    # Bei weiteren Überschriften stoppen - diese werden separat verarbeitet
                    break
                elif next_b['type'] not in ['blank', 'title_brace']:
                    # Bei anderen Elementen stoppen
                    break

                temp_i += 1

            if text_lines_found > 0:
                # Überschrift mit nächsten Textzeilen verkoppeln
                elements.append(KeepTogether(next_elements))

                # Abstand nach KeepTogether-Gruppe hinzufügen
                # Finde den nächsten relevanten Block nach der Gruppe
                next_relevant_idx = temp_i
                while next_relevant_idx < len(blocks):
                    next_block = blocks[next_relevant_idx]
                    if next_block['type'] not in ['blank', 'title_brace']:
                        break
                    next_relevant_idx += 1

                if next_relevant_idx < len(blocks):
                    next_block = blocks[next_relevant_idx]
                    if next_block['type'] == 'section':
                        # Weniger Abstand vor Überschriften
                        elements.append(Spacer(1, SECTION_SPACE_AFTER_MM * MM * 0.5))
                    else:
                        # Normaler Abstand vor weiteren Textzeilen
                        elements.append(Spacer(1, INTER_PAIR_GAP_MM * MM))
                # Bei letzter Gruppe: keinen zusätzlichen Abstand

                i = temp_i
            else:
                # Keine Textzeilen gefunden, nur Überschrift
                elements.append(para)

                # Abstand nach einzelner Überschrift hinzufügen
                # Finde den nächsten relevanten Block
                next_relevant_idx = temp_i
                while next_relevant_idx < len(blocks):
                    next_block = blocks[next_relevant_idx]
                    if next_block['type'] not in ['blank', 'title_brace']:
                        break
                    next_relevant_idx += 1

                if next_relevant_idx < len(blocks):
                    next_block = blocks[next_relevant_idx]
                    if next_block['type'] == 'section':
                        # Weniger Abstand zwischen aufeinanderfolgenden Überschriften
                        elements.append(Spacer(1, SECTION_SPACE_AFTER_MM * MM * 0.5))
                    else:
                        # Normaler Abstand vor Textzeilen
                        elements.append(Spacer(1, INTER_PAIR_GAP_MM * MM))

                i = temp_i  # Verwende temp_i statt i+1, um keine Überschriften zu überspringen
            continue

        if t == 'pair':
            gr_tokens = b.get('gr_tokens', [])[:]
            de_tokens = b.get('de_tokens', [])[:]
            speaker   = b.get('speaker') or ''
            line_label= b.get('label') or ''
            base_num  = b.get('base')  # None oder int

            # >>> NEU: Elisions-Übertragung wie im Epos
            gr_tokens = propagate_elision_markers(gr_tokens)
            # <<<

            # Einrückung: kumulative Breite aller bisherigen Teilverse dieses Basisverses
            indent_pt = 0.0
            if base_num is not None:
                indent_pt = max(0.0, cum_width_by_base.get(base_num, 0.0))

            # Prüfe auf Versmaß-Marker
            has_versmass = has_meter_markers(gr_tokens)

            tables = build_tables_for_pair(
                gr_tokens, de_tokens,
                speaker=speaker,
                line_label=line_label,                 # <<< WICHTIG: Label übergeben
                doc_width_pt=frame_w,
                token_gr_style=token_gr, token_de_style=token_de, num_style=num_style, style_speaker=style_speaker,
                gr_bold=gr_bold,
                reserve_speaker_col=reserve_all_speakers,
                indent_pt=indent_pt,
                global_speaker_width_pt=global_speaker_width_pt,
                meter_on=versmass_display and has_versmass
            )
            for t2 in tables:
                elements.append(KeepTogether([t2]))

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
            if base_num is not None:
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

