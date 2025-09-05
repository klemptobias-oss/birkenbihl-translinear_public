# === UPPER TRANSITION (neu-aufgesetzt, kompakt) ==========================================
############## EIN KOMÖDIEN/TRAGÖDIEN CODE SIE ALLE ZU KNECHTEN, GOTT #####################
"""
DRAMA (Komödie/Tragödie) — Kachel-Layout (v20, bereinigt/kompakt)
- Wort-unter-Wort (GR über DE), Tokens ohne Wrap.
- Labels [n]/(n[a-z]) stabil; Label nur neben GR.
- Sprecher im Text werden entfernt; eigene linke Sprecher-Spalte (nur GR), #777, Format: [Sprecher]:
- Stufenlayout Unterverse (a/b/c/d) via kumulativer Einrückung pro Basisvers.
- Nur GR fett in der _Fett_-Ausgabe (BUILD_FETT=True). In _Normal_ bleibt GR normal.
- [[Abschnitte]] als Headlines; gekoppelt mit den ersten ZWEI Kacheln des Folge-Textes (KeepTogether).
- DE-Zeile: Tags unsichtbar außer (≈) → <sup>≈</sup>. Sternchen/Tilde werden ignoriert.

Outputs: <Label>_Fett.pdf und <Label>_Normal.pdf
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib.units    import mm as RL_MM
from reportlab.lib.styles   import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums    import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase      import pdfmetrics
from reportlab.platypus     import SimpleDocTemplate, Paragraph, Spacer, KeepTogether, Table, TableStyle
from reportlab.lib          import colors
from pathlib import Path
import re, os, html

# ========= KNÖPFE / REGLER =========
BUILD_FETT   = True   # erzeugt <Label>_Fett.pdf (GR fett)
BUILD_NORMAL = True   # erzeugt <Label>_Normal.pdf (GR NICHT fett)

# ========= Einheiten/Optik =========
MM = RL_MM
GR_SIZE = 8.2
DE_SIZE = 7.5
SECTION_SIZE = 12.0
SECTION_SPACE_AFTER_PT = 16
INTER_PAIR_GAP_MM   = 5.0
INTRA_PAIR_GAP_MM   = 2.0   # GR ↔ DE
NUM_COL_W_MM        = 8.0
NUM_GAP_MM          = 1.2
SPEAKER_COL_MIN_MM  = 5.0
SPEAKER_GAP_MM      = 1.5
INDENT_MIN_PT       = 0.0
CELL_PAD_LR_PT      = 0.0
SAFE_EPS_PT         = 0.5
TAG_WIDTH_FACTOR    = 1.3
NUM_COLOR           = colors.HexColor('#777')
NUM_SIZE_FACTOR     = 0.84

# ========= Fonts =========
pdfmetrics.registerFont(TTFont('DejaVu',      'DejaVuSans.ttf'))
pdfmetrics.registerFont(TTFont('DejaVu-Bold', 'DejaVuSans-Bold.ttf'))
pdfmetrics.registerFontFamily('DejaVu', normal='DejaVu', bold='DejaVu-Bold')

# ========= Regex/Tags =========
SUP_TAGS = {'N','D','G','A','V','m','f','n','Aj','Pt','Prp','Av','Ko','Art','≈'}
SUB_TAGS = {'Pre','Imp','Aor','Per','Plq','Fu','FuP','Inf','Imv','Akt','Med','Pas','Kon','Op','S','P','Pr','AorS','M/P'}
RE_TAG       = re.compile(r'\(([A-Za-z/≈]+)\)')
RE_TAG_NAKED = re.compile(r'\([A-Za-z/≈]+\)')
RE_LABEL_TOKEN   = re.compile(r'^[\[\(]\s*(\d+)([a-z])?\s*[\]\)]\.?$', re.IGNORECASE)
RE_GREEK_CHARS   = re.compile(r'[\u0370-\u03FF\u1F00-\u1FFF]')
RE_LATIN_CHARS   = re.compile(r'[A-Za-zÄÖÜäöüß]')
RE_SPEAKER_GR    = re.compile(r'^[\u0370-\u03FF\u1F00-\u1FFF]+:$')     # Λυσ:, Χορ:
RE_SPK_BRACKET   = re.compile(r'^\[[^\]]*:\]$')                         # [Χορ Γερ:]
RE_SECTION         = re.compile(r'^\s*\[\[\s*(.+?)\s*\]\]\s*$')
RE_SECTION_SINGLE  = re.compile(r'^\s*\[\s*(.+?)\s*\]\s*$')

# ========= Helpers =========
def _leading_for(size: float) -> float:
    return round(size * 1.30 + 0.6, 1)

def is_empty_or_sep(line:str) -> bool:
    t = (line or '').strip()
    return (not t) or t.upper() in {'[FREIE ZEILE]', '[ENTERZEICHEN]'} or t.startswith('---')

def normalize_spaces(s:str) -> str:
    return re.sub(r'\s+', ' ', (s or '').strip())

def xml_escape(text:str) -> str:
    return html.escape(text or '', quote=False)

def _sw(text:str, font:str, size:float) -> float:
    return pdfmetrics.stringWidth(text, font, size)

# ========= pre_substitutions =========
def pre_substitutions(s:str) -> str:
    if not s: return s
    punct_alt = r'(?:,|\.|;|:|!|\?|%|…|\u00B7|\u0387|\u037E)'
    s = re.sub(rf'\s+{punct_alt}', lambda m: m.group(0).lstrip(), s)
    s = re.sub(r'([\(\[\{\«“‹‘])\s+', r'\1', s)
    s = re.sub(r'\s+([\)\]\}\»”›’])', r'\1', s)
    s = re.sub(r'\(([#\+\-])', r'\1(', s)
    s = re.sub(r'\[([#\+\-])', r'\1[', s)
    s = re.sub(r'\{([#\+\-])', r'\1{', s)
    return s

def strip_for_classify(s:str) -> str:
    s2 = re.sub(r'^[\[\(]\s*\d+[a-z]?\s*[\]\)]\.?\s*', '', s or '')
    s2 = RE_TAG_NAKED.sub('', s2)
    s2 = re.sub(r'^\s*\[[^\]]*:\]\s*', '', s2)
    return normalize_spaces(s2)

def is_greek_line(s:str) -> bool:
    if not s: return False
    s2 = strip_for_classify(s)
    toks = s2.split()
    if toks and RE_SPEAKER_GR.match(toks[0]): s2 = ' '.join(toks[1:])
    if '|' in s2: return False
    s2 = re.sub(r'([\u0370-\u03FF\u1F00-\u1FFF]+)[A-Za-z/]+', lambda m: m.group(1), s2)
    g = len(RE_GREEK_CHARS.findall(s2)); l = len(RE_LATIN_CHARS.findall(s2))
    if g == 0: return False
    if l == 0: return True
    return g >= max(3, int(1.2 * l))

# ========= Tokenizer =========
def tokenize(line:str):
    s = normalize_spaces(pre_substitutions(line or ''))
    if not s: return []
    raw = s.split(' ')
    out, buf = [], []
    for tok in raw:
        if not tok: continue
        if buf:
            buf.append(tok)
            if tok.endswith(']'):
                out.append(' '.join(buf)); buf = []
            continue
        if tok.startswith('[') and not tok.endswith(']'):
            buf = [tok]; continue
        out.append(tok)
    if buf: out.append(' '.join(buf))
    return out

# ========= Token-Formatierung & Messen =========
def _split_token(token:str):
    """Farbcodes abspalten, Tags extrahieren, Kern bereinigen."""
    raw = (token or '').strip()
    if not raw: return None, None, [], ''
    color = None
    if raw.startswith('#'): color, raw = '#FF0000', raw[1:]
    elif raw.startswith('-'): color, raw = '#228B22', raw[1:]
    elif raw.startswith('+'): color, raw = '#1E90FF', raw[1:]
    tags = RE_TAG.findall(raw)
    core = RE_TAG_NAKED.sub('', raw).strip().replace('*','').replace('~','')
    return raw, color, tags, core

def format_token_markup(token:str, *, is_greek_row:bool, gr_bold:bool) -> str:
    raw, color, tags, core = _split_token(token)
    if raw is None: return ''
    if not is_greek_row:
        sups = ['≈'] if '≈' in tags else []
        subs, rest = [], []
    else:
        sups = [t for t in tags if t in SUP_TAGS]
        subs = [t for t in tags if t in SUB_TAGS]
        rest = [t for t in tags if t not in SUP_TAGS and t not in SUB_TAGS]
    core_esc = xml_escape(core.replace('-', '|'))
    parts = []
    if is_greek_row and gr_bold: parts.append('<b>')
    if color: parts.append(f'<font color="{color}">')
    parts.append(core_esc)
    for t in sups: parts.append(f'<sup>{t}</sup>')
    for t in subs: parts.append(f'<sub>{t}</sub>')
    for t in rest: parts.append(f'({xml_escape(t)})')
    if color: parts.append('</font>')
    if is_greek_row and gr_bold: parts.append('</b>')
    return ''.join(parts)

def visible_measure_token(token:str, *, font:str, size:float, is_greek_row:bool=True) -> float:
    raw, _, tags, core = _split_token(token)
    if raw is None: return 0.0
    w = _sw(core.replace('-', '|'), font, size)
    if tags:
        kept = tags if is_greek_row else (['≈'] if '≈' in tags else [])
        if kept:
            w += TAG_WIDTH_FACTOR * _sw(''.join(kept), font, size)
    return w + SAFE_EPS_PT + 2*CELL_PAD_LR_PT

def measure_line_width(tokens, *, font:str, size:float) -> float:
    return sum(visible_measure_token(t, font=font, size=size, is_greek_row=True) for t in tokens)

# ========= Abschnitte / Labels =========
def detect_section(line:str):
    m = RE_SECTION.match(line or '')
    if m: return m.group(1).strip()
    m2 = RE_SECTION_SINGLE.match(line or '')
    if m2: return m2.group(1).strip()
    return None

def extract_label_from_tokens(tokens):
    if not tokens: return None, None, tokens
    m = RE_LABEL_TOKEN.match(tokens[0])
    if m:
        base = int(m.group(1)); suf = (m.group(2) or '')
        return f"{base}{suf}", base, tokens[1:]
    return None, None, tokens

# ========= Sprecher-Handling =========
def pop_leading_speaker(tokens):
    """Entfernt führenden Sprecher (Λυσ:, [Χορ Γερ:]) und liefert (name, rest)."""
    if not tokens: return '', tokens
    t0 = tokens[0]
    if RE_SPK_BRACKET.match(t0):
        inner = t0[1:-1]
        if inner.endswith(':'): inner = inner[:-1]
        return inner.strip(), tokens[1:]
    if RE_SPEAKER_GR.match(t0):
        return t0.rstrip(':'), tokens[1:]
    return '', tokens

# ========= Parsing =========
def process_input_file(fname:str):
    with open(fname, encoding='utf-8') as f:
        raw = [ln.rstrip('\n') for ln in f]

    blocks = []
    i = 0
    while i < len(raw):
        line = (raw[i] or '').strip()
        if is_empty_or_sep(line):
            i += 1; continue

        sec = detect_section(line)
        if sec:
            blocks.append({'type': 'section', 'text': sec})
            i += 1; continue

        if is_greek_line(line):
            gr_line = line
            i += 1
            while i < len(raw) and is_empty_or_sep(raw[i]): i += 1
            de_line = ''
            if i < len(raw):
                cand = raw[i].strip()
                if not is_greek_line(cand):
                    de_line = cand; i += 1
            blocks.append({'type':'pair',
                           'gr_tokens': tokenize(gr_line),
                           'de_tokens': tokenize(de_line)})
        else:
            blocks.append({'type':'pair', 'gr_tokens': [], 'de_tokens': tokenize(line)})
            i += 1
    return blocks

# ========= Layout-Helpers =========
def _p(text, style): return Paragraph(text, style)
def _nbsp(style):    return Paragraph('\u00A0', style)

# ========= Kachelbau =========
def build_tables_for_pair(gr_tokens, de_tokens, *,
                          line_label:str,
                          sp_display:str, sp_width_pt:float,
                          indent_pt:float,
                          doc_width_pt:float,
                          token_gr_style, token_de_style, num_style,
                          gr_bold:bool):

    num_w       = NUM_COL_W_MM * MM
    num_gap_w   = NUM_GAP_MM   * MM
    sp_w        = max(0.0, sp_width_pt)
    speaker_gap = (SPEAKER_GAP_MM * MM) if sp_w > 0 else 0.0
    indent_w    = max(INDENT_MIN_PT, float(indent_pt))
    avail_tokens_w = doc_width_pt - (num_w + num_gap_w + sp_w + speaker_gap + indent_w)
    if avail_tokens_w <= 10: avail_tokens_w = doc_width_pt * 0.9

    cols = max(len(gr_tokens), len(de_tokens))
    gr = gr_tokens[:] + [''] * (cols - len(gr_tokens))
    de = de_tokens[:] + [''] * (cols - len(de_tokens))

    widths = []
    for k in range(cols):
        w_gr = visible_measure_token(gr[k], font=token_gr_style.fontName, size=token_gr_style.fontSize, is_greek_row=True)  if gr[k] else 0.0
        w_de = visible_measure_token(de[k], font=token_de_style.fontName, size=token_de_style.fontSize, is_greek_row=False) if de[k] else 0.0
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

        gr_cells = [_p(format_token_markup(t, is_greek_row=True,  gr_bold=gr_bold), token_gr_style) if t else _p('', token_gr_style) for t in slice_gr]
        de_cells = [_p(format_token_markup(t, is_greek_row=False, gr_bold=gr_bold), token_de_style) if t else _p('', token_de_style) for t in slice_de]

        num_para_gr = _p(xml_escape(f'[{line_label}]'), num_style) if (first_slice and line_label) else _nbsp(num_style)
        num_para_de = _nbsp(num_style)
        sp_para_gr  = _p(f'<font color="#777">{xml_escape(sp_display)}</font>', token_de_style) if (first_slice and sp_display) else _p('', token_de_style)
        sp_para_de  = _p('', token_de_style)
        gap_gr = _p('', token_gr_style); gap_de = _p('', token_de_style)
        indent_gr = _p('', token_gr_style); indent_de = _p('', token_de_style)

        row_gr = [num_para_gr, gap_gr, sp_para_gr, gap_gr, indent_gr] + gr_cells
        row_de = [num_para_de, gap_de, sp_para_de, gap_de, indent_de] + de_cells
        data   = [row_gr, row_de]
        col_w  = [num_w, num_gap_w, sp_w, speaker_gap, indent_w] + slice_w

        tbl = Table(data, colWidths=col_w, hAlign='LEFT')
        tbl.setStyle(TableStyle([
            ('LEFTPADDING',   (0,0), (-1,-1), CELL_PAD_LR_PT),
            ('RIGHTPADDING',  (0,0), (-1,-1), CELL_PAD_LR_PT),
            ('TOPPADDING',    (0,0), (-1,-1), 0.0),
            ('BOTTOMPADDING', (0,0), (-1,-1), 0.0),
            ('ALIGN',         (0,0), (0,-1), 'RIGHT'),
            ('LEFTPADDING',   (0,0), (0,-1), 0.0),
            ('RIGHTPADDING',  (0,0), (0,-1), 0.0),
            ('BOTTOMPADDING', (0,0), (-1,0), gap_pts/2.0),
            ('TOPPADDING',    (0,1), (-1,1), gap_pts/2.0),
            ('VALIGN',        (0,0), (-1,-1), 'BOTTOM'),
            ('ALIGN',         (1,0), (1,-1), 'CENTER'),
        ]))
        tables.append(tbl)
        first_slice, i = False, j

    return tables

# ========= PDF-Erstellung =========
def create_pdf(blocks, pdf_name:str, *, gr_bold:bool):
    left_margin = 10*MM; right_margin = 10*MM
    doc = SimpleDocTemplate(pdf_name, pagesize=A4,
                            leftMargin=left_margin, rightMargin=right_margin,
                            topMargin=14*MM,  bottomMargin=14*MM)
    frame_w = A4[0] - left_margin - right_margin

    base = getSampleStyleSheet()
    style_section = ParagraphStyle(
        'Section', parent=base['Normal'],
        fontName='DejaVu-Bold', fontSize=SECTION_SIZE, leading=_leading_for(SECTION_SIZE),
        alignment=TA_LEFT, spaceBefore=6, spaceAfter=SECTION_SPACE_AFTER_PT, keepWithNext=True,
    )
    token_gr = ParagraphStyle('TokGR', parent=base['Normal'], fontName='DejaVu',
                              fontSize=GR_SIZE, leading=_leading_for(GR_SIZE),
                              alignment=TA_CENTER, wordWrap='LTR', splitLongWords=0)
    token_de = ParagraphStyle('TokDE', parent=base['Normal'], fontName='DejaVu',
                              fontSize=DE_SIZE, leading=_leading_for(DE_SIZE),
                              alignment=TA_CENTER, wordWrap='LTR', splitLongWords=0)
    num_size = max(6.0, round(GR_SIZE * NUM_SIZE_FACTOR, 1))
    num_style = ParagraphStyle('Num', parent=base['Normal'], fontName='DejaVu',
                               fontSize=num_size, leading=_leading_for(num_size),
                               textColor=NUM_COLOR, alignment=TA_RIGHT, wordWrap='LTR', splitLongWords=0)

    elements = []
    cum_width_by_base = {}
    active_speaker_text = ''
    active_speaker_width_pt = 0.0

    def compute_speaker_width_pt(sp_text:str) -> float:
        if not sp_text: return 0.0
        disp = f'[{sp_text}]:'
        w = _sw(disp, token_de.fontName, DE_SIZE) + 0.8
        return max(SPEAKER_COL_MIN_MM * MM, w)

    def tables_for_pair_block(pair_block):
        nonlocal active_speaker_text, active_speaker_width_pt, cum_width_by_base
        gr_tokens = pair_block.get('gr_tokens', [])[:]
        de_tokens = pair_block.get('de_tokens', [])[:]

        label_gr, base_gr, gr_tokens = extract_label_from_tokens(gr_tokens)
        label_de, base_de, de_tokens = extract_label_from_tokens(de_tokens)
        line_label = label_gr or label_de or ''
        base = base_gr if base_gr is not None else base_de

        speaker, gr_tokens = pop_leading_speaker(gr_tokens)
        _de_speaker, de_tokens = pop_leading_speaker(de_tokens)

        if speaker:
            active_speaker_text = speaker
            active_speaker_width_pt = compute_speaker_width_pt(active_speaker_text)
            sp_display = f'[{active_speaker_text}]:'
            sp_width_pt = active_speaker_width_pt
        else:
            sp_display = ''
            sp_width_pt = active_speaker_width_pt

        indent_pt = 0.0
        if base is not None:
            if base not in cum_width_by_base: cum_width_by_base[base] = 0.0
            indent_pt = max(INDENT_MIN_PT, cum_width_by_base.get(base, 0.0))
            this_w = measure_line_width(gr_tokens, font=token_gr.fontName, size=token_gr.fontSize)
            cum_width_by_base[base] = cum_width_by_base.get(base, 0.0) + this_w

        cols = max(len(gr_tokens), len(de_tokens))
        while len(gr_tokens) < cols: gr_tokens.append('')
        while len(de_tokens) < cols: de_tokens.append('')

        tables = build_tables_for_pair(
            gr_tokens, de_tokens,
            line_label=line_label,
            sp_display=sp_display, sp_width_pt=sp_width_pt,
            indent_pt=indent_pt,
            doc_width_pt=frame_w,
            token_gr_style=token_gr, token_de_style=token_de, num_style=num_style,
            gr_bold=gr_bold
        )
        gap_pts = INTRA_PAIR_GAP_MM * MM
        for k, t in enumerate(tables):
            if k > 0:
                t.setStyle(TableStyle([
                    ('BOTTOMPADDING', (0,0), (-1,0), gap_pts/2.0),
                    ('TOPPADDING',    (0,1), (-1,1), gap_pts/2.0),
                ]))
        return tables

    # Abschnitt + ZWEI erste Kacheln koppeln
    i = 0
    while i < len(blocks):
        b = blocks[i]; t = b['type']
        if t == 'section':
            sec_para = Paragraph(xml_escape(b['text']), style_section)
            j = i + 1
            while j < len(blocks) and blocks[j]['type'] != 'pair': j += 1
            if j < len(blocks) and blocks[j]['type'] == 'pair':
                first_tables = tables_for_pair_block(blocks[j])
                if first_tables:
                    k = min(2, len(first_tables))
                    elements.append(KeepTogether([sec_para] + first_tables[:k]))
                    for rest in first_tables[k:]: elements.append(KeepTogether([rest]))
                    elements.append(Spacer(1, INTER_PAIR_GAP_MM * MM))
                    i = j + 1; continue
            elements.append(sec_para); i += 1; continue

        if t != 'pair':
            i += 1; continue

        tables = tables_for_pair_block(b)
        for t in tables: elements.append(KeepTogether([t]))
        elements.append(Spacer(1, INTER_PAIR_GAP_MM * MM))
        i += 1

    doc.build(elements)

# ========= Batch / Dateinamen =========
def category_and_label_from_input(infile:str):
    stem = Path(infile).stem; s = stem.lower()
    if s.startswith('inputkomödie') or s.startswith('inputkomoedie'):
        cat = 'Komödie'
        label = stem[len('InputKomödie'):] if stem.startswith('InputKomödie') else stem[len('InputKomodie'):]
    elif s.startswith('inputtragödie') or s.startswith('inputtragoedie'):
        cat = 'Tragödie'
        label = stem[len('InputTragödie'):] if stem.startswith('InputTragödie') else stem[len('InputTragoedie'):]
    else:
        cat = 'Drama'
        m = re.match(r'(?i)^input(.+)$', stem); label = m.group(1) if m else stem
    label = re.sub(r'\W+', '', label)
    return cat, (label if label else 'Text')

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
            if BUILD_FETT:
                out_fett = output_name_fett(cat, label)
                create_pdf(blocks, out_fett, gr_bold=True)
                print(f"✓ PDF erstellt → {out_fett}")
            if BUILD_NORMAL:
                out_norm = output_name_normal(cat, label)
                create_pdf(blocks, out_norm, gr_bold=False)
                print(f"✓ PDF erstellt → {out_norm}")
        except Exception as e:
            print(f"✗ Fehler bei {infile}: {e}")

if __name__ == '__main__':
    inputs = process_inputs_glob()
    if not inputs:
        print("⚠ Keine InputKomödie* / InputTragödie* gefunden.")
    else:
        run_batch(inputs)

# === LOWER TRANSITION =====================================================================

