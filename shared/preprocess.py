#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
shared/preprocess.py
--------------------
Vorverarbeitung der Blockstruktur vor dem Rendern.

Kompatibilität:
- Bestehende Aufrufe bleiben gültig: apply(blocks, color_mode=..., tag_mode=..., versmass_mode=...)
- NEU: optionale Feineinstellungen:
    - color_pos_keep: Iterable[str] | None
        → PoS-Liste, für die Farbcodes (#/+/−) beibehalten werden (nur wenn color_mode="COLOR").
          Alle anderen Tokens werden entfärbt. Mögliche PoS: {"Adj","Pt","Prp","Adv","Kon","Art","Pr","ij"}
    - sup_keep: Iterable[str] | None
        → SUP-Tags, die beibehalten werden (alle anderen werden entfernt).
    - sub_keep: Iterable[str] | None
        → SUB-Tags, die beibehalten werden (alle anderen werden entfernt).

Hinweis „Hoch/Tief je Tag“:
- Der Renderer (z. B. Poesie_Code.format_token_markup) entscheidet anhand seiner statischen
  SUP_TAGS / SUB_TAGS über <sup>/<sub>. Dieses Modul kann selektiv entfernen,
  aber kein Tag von SUP→SUB „umhängen“, solange der Renderer unverändert ist.
- Für freie Zuweisung liefere ich in einem Folge-Patch ein kleines Mapping in Poesie_Code.py nach.

Datenannahme:
- Blöcke haben typischerweise 'pair'-Einträge mit 'gr_tokens' / 'de_tokens' (Listen von Tokens).
- Tokens sind Strings mit optionalen:
    * Farbcodes: '#', '+', '-' (ggf. auch als '|#', '|+', '|-' nach führendem '|')
    * Grammatik-Tags: '(TAG)' – mehrere pro Token möglich.
    * Versmaß-Marker: 'i', 'L', '|' (nur griechische Zeile)

Effekte:
- color_mode = "BLACK_WHITE": Farbcodes vollständig entfernen.
- color_mode = "COLOR":
    * Wenn color_pos_keep angegeben ist, dann Farbcodes nur bei Tokens beibehalten,
      deren PoS in color_pos_keep vorkommt (sonst Farbcodes entfernen).
- tag_mode = "NO_TAGS": alle bekannten Tags (SUP/SUB) entfernen.
- tag_mode = "TAGS": nur die in sup_keep/sub_keep enthaltenen Tags behalten; andere entfernen.
- versmass_mode:
    * "NORMAL": Marker bleiben stehen; Renderer macht später „Bars unsichtbar“.
    * "KEEP_MARKERS": Marker bleiben stehen (für Versmaßdarstellung).
    * "REMOVE_MARKERS": 'i', 'L', '|' werden entfernt (nur griechische Zeile).

"""

from __future__ import annotations
import re
from typing import List, Dict, Any, Iterable, Optional, Set

# ======= Tag-Definitionen für die Erkennungslogik =======
KASUS_TAGS = {'N', 'G', 'D', 'A', 'V', 'Abl'}  # NEU: Abl für Latein
TEMPUS_TAGS = {'Aor', 'Prä', 'Imp', 'AorS', 'Per', 'Plq', 'Fu', 'Fu1', 'Fu2'}  # NEU: Fu1, Fu2 für Latein
DIATHESE_TAGS = {'Med', 'Pas', 'Akt', 'M/P'}
MODUS_TAGS = {'Inf', 'Op', 'Imv', 'Knj'}
STEIGERUNG_TAGS = {'Kmp', 'Sup'}
LATEINISCHE_VERBFORMEN = {'Ger', 'Gdv', 'Spn'}  # NEU: Spezielle lateinische Verbformen

# Alle Tags, die eine Wortart eindeutig identifizieren
WORTART_IDENTIFIER_TAGS = {
    'Adj': 'adjektiv',
    'Adv': 'adverb',
    'Pr': 'pronomen',
    'Art': 'artikel',
    'Prp': 'prp',
    'Kon': 'kon',
    'Pt': 'pt',
    'ij': 'ij'
}

# Reihenfolge für Hierarchie-Überschreibung innerhalb der Gruppen
HIERARCHIE = {
    'verb': ['Prä', 'Imp', 'Aor', 'AorS', 'Per', 'Plq', 'Fu', 'Fu1', 'Fu2', 'Akt', 'Med', 'Pas', 'M/P', 'Inf', 'Op', 'Knj', 'Imv'],  # NEU: Fu1, Fu2
    'partizip': ['Prä', 'Imp', 'Aor', 'AorS', 'Per', 'Plq', 'Fu', 'Fu1', 'Fu2', 'N', 'G', 'D', 'A', 'V', 'Akt', 'Med', 'Pas', 'M/P'],  # NEU: Fu1, Fu2
    'adjektiv': ['N', 'G', 'D', 'A', 'V', 'Kmp', 'Sup'],
    'adverb': ['Kmp', 'Sup'],
    'pronomen': ['N', 'G', 'D', 'A'],
    'artikel': ['N', 'G', 'D', 'A'],
    'nomen': ['N', 'G', 'D', 'A', 'V', 'Abl'],  # NEU: Abl für Latein
}

RULE_TAG_MAP = {
    'nomen': HIERARCHIE['nomen'],
    'verb': HIERARCHIE['verb'],
    'partizip': HIERARCHIE['partizip'],
    'adjektiv': ['Adj', *HIERARCHIE['adjektiv']],
    'adverb': ['Adv', *HIERARCHIE['adverb']],
    'pronomen': ['Pr', *HIERARCHIE['pronomen']],
    'artikel': ['Art', *HIERARCHIE['artikel']],
    'gerundium': ['Ger', 'G', 'D', 'A', 'Abl'],
    'gerundivum': ['Gdv', 'N', 'G', 'D', 'A', 'Abl', 'V'],
    'supinum': ['Spn', 'A', 'Abl'],
    'prp': ['Prp'],
    'kon': ['Kon'],
    'pt': ['Pt'],
    'ij': ['ij'],
}

# Tag für manuelle Übersetzungs-Ausblendung
TRANSLATION_HIDE_TAG = "HideTrans"
TRANSLATION_HIDE_GLOBAL = "_global"
# Tag für manuelle Tag-Ausblendung (Tags werden entfernt, aber Farben bleiben erhalten)
TAG_HIDE_TAGS = "HideTags"

# ======= Konstanten (müssen mit dem Renderer-Stand zusammenpassen) =======
SUP_TAGS = {'N','D','G','A','V','Du','Adj','Pt','Prp','Adv','Kon','Art','≈','Kmp','Sup','ij','Abl'}  # NEU: Abl für Latein
SUB_TAGS = {'Prä','Imp','Aor','Per','Plq','Fu','Inf','Imv','Akt','Med','Pas','Knj','Op','Pr','AorS','M/P','Gdv','Ger','Spn','Fu1','Fu2'}  # NEU: Gdv, Ger, Spn, Fu1, Fu2 für Latein

# ======= Regexe =======
RE_PAREN_TAG     = re.compile(r'\(([A-Za-z0-9/≈äöüßÄÖÜ]+)\)')
RE_LEAD_BAR_COLOR= re.compile(r'^\|\s*([+\-#§$])')  # |+ |# |- |§ |$ (Farbcode NACH leitender '|')
RE_WORD_START = re.compile(r'([(\[|]*)([\w\u0370-\u03FF\u1F00-\u1FFF\u1F00-\u1FFF]+)') # Findet den Anfang eines Wortes, auch mit Präfixen wie (, [ oder |
RE_STEPHANUS = re.compile(r'\[(\d+[a-e])\]')  # Stephanus-Paginierungen: [543b], [546b] etc.

def is_trivial_translation(text: str) -> bool:
    """
    True, wenn text nur aus Interpunktionszeichen oder Stephanus-Paginierungen besteht.
    - z.B. ".", "?", "]", "[", ":" oder "[543b]" oder Kombinationen wie ". . ."
    Used to *drop* such translation lines when hide-translation is requested.
    WICHTIG: Sprecher zählen NICHT als "Wort" - sie werden ignoriert.
    """
    if not text:
        return True
    t = text.strip()
    
    # Entferne Sprecher-Marker (z.B. "[Sokrates:]", "[Φύλαξ:]") - diese zählen nicht als "Wort"
    # Sprecher-Marker sind typischerweise am Anfang: [Name:] oder [Name]
    t_no_speaker = re.sub(r'^\s*\[[^\]]+:\]\s*', '', t)  # [Name:]
    t_no_speaker = re.sub(r'^\s*\[[^\]]+\]\s*', '', t_no_speaker)  # [Name] (ohne Doppelpunkt)
    
    # Wenn nach Entfernen des Sprechers nichts mehr übrig ist -> trivial
    if not t_no_speaker.strip():
        return True
    
    # Prüfe auf Stephanus-Paginierungen: [123a] pattern
    if RE_STEPHANUS.search(t_no_speaker):
        # Entferne alle Stephanus-Marker und prüfe, ob noch Text übrig ist
        without_steps = RE_STEPHANUS.sub('', t_no_speaker).strip()
        if not without_steps:
            return True
    
    # Wenn nur Interpunktion und Leerzeichen übrig bleiben
    if re.fullmatch(r'^[\s\.\,\;\:\?\!\-\(\)\[\]\"\'\/\\\|…·•]+$', t_no_speaker):
        return True
    
    return False

COLOR_SYMBOLS = {'#', '+', '-', '§', '$'}
COLOR_MAP = {
    'red': '#',
    'blue': '+',
    'green': '-',
    'magenta': '§',
    'purple': '§',  # purple = magenta (sanftes Violett)
    'violett': '§',
    'orange': '$',
}

# ======= Typen =======
ColorMode   = str  # "COLOR" | "BLACK_WHITE"
TagMode     = str  # "TAGS"  | "NO_TAGS"
VersmassMode= str  # "NORMAL" | "REMOVE_MARKERS" | "KEEP_MARKERS"

# ======= Hilfen: Kommentar-Masken =======
def create_comment_token_mask_for_block(block: Dict[str, Any], all_blocks: Optional[List[Dict[str,Any]]] = None) -> List[bool]:
    """
    Erzeugt eine Maskenliste (len == len(block['gr_tokens'])) mit True für Tokens,
    die zu Kommentarbereichen gehören. Erwartet kommentare mit token_start/token_end
    oder flow_blocks mit type=='comment' und token ranges.
    """
    tokens = block.get('gr_tokens', []) or []
    mask = [False] * len(tokens)
    
    # 1) direkte comments
    for c in block.get('comments', []) if isinstance(block.get('comments', []), list) else []:
        s = c.get('token_start')
        e = c.get('token_end')
        if s is None or e is None:
            continue
        s = max(0, int(s))
        e = min(len(mask)-1, int(e))
        for i in range(s, e+1):
            mask[i] = True
    
    # 2) flow_blocks
    for fb in block.get('flow_blocks', []) if isinstance(block.get('flow_blocks', []), list) else []:
        if not isinstance(fb, dict):
            continue
        if fb.get('type') == 'comment':
            s = fb.get('token_start')
            e = fb.get('token_end')
            if s is None or e is None:
                continue
            s = max(0, int(s))
            e = min(len(mask)-1, int(e))
            for i in range(s, e+1):
                mask[i] = True
    
    # fallback: if no structured ranges present, leave mask all False
    return mask

# ======= COMMENT EXTRACTION & MASKING HELPERS =======
# Regex für Inline-Kommentare: "(2-4k) text..." oder "(5121k) text..."
_RE_INLINE_COMMENT = re.compile(r'^\s*\(?\s*(\d+)(?:-(\d+))?\s*k\)\s*(.*)', flags=re.I)

def extract_inline_comments_from_blocks(blocks: List[Dict[str,Any]]) -> List[Dict[str,Any]]:
    """
    Scans blocks for inline comment lines of the form "(2-4k) text..." or "(5121k) text..."
    Returns a list of dicts: {'start_pair': int, 'end_pair': int, 'text': str, 'origin_block_index': i}
    Also removes the comment-line text from the block's 'gr' (so it doesn't render as normal text).
    Prüft auch in gr_tokens (erster Token) und in separaten comment-Blocks.
    """
    comments = []
    for i, block in enumerate(blocks):
        if not isinstance(block, dict):
            continue
        
        # 1. Prüfe block['gr'] (string)
        gr = block.get('gr') or ""
        m = _RE_INLINE_COMMENT.match(gr.strip())
        if m:
            s = int(m.group(1))
            e = int(m.group(2) or m.group(1))
            text = m.group(3).strip()
            comments.append({'start_pair': s, 'end_pair': e, 'text': text, 'origin_block_index': i})
            # remove the comment line from the block's gr
            remainder = _RE_INLINE_COMMENT.sub('', gr, count=1).strip()
            block['gr'] = remainder
            # also clear gr_tokens if they correspond to the comment line
            if block.get('gr_tokens') and len(block.get('gr_tokens')) <= 3:
                block['gr_tokens'] = []
            continue
        
        # 2. Prüfe ersten gr_token (falls vorhanden)
        gr_tokens = block.get('gr_tokens', [])
        if gr_tokens and len(gr_tokens) > 0:
            first_token = gr_tokens[0] if isinstance(gr_tokens[0], str) else str(gr_tokens[0])
            m = _RE_INLINE_COMMENT.match(first_token.strip())
            if m:
                s = int(m.group(1))
                e = int(m.group(2) or m.group(1))
                text = m.group(3).strip()
                comments.append({'start_pair': s, 'end_pair': e, 'text': text, 'origin_block_index': i})
                # Entferne den Kommentar-Token
                block['gr_tokens'] = gr_tokens[1:] if len(gr_tokens) > 1 else []
                continue
        
        # 3. Prüfe ob Block selbst ein comment-Block ist
        if block.get('type') == 'comment':
            # Kommentar-Block bereits vorhanden - nicht nochmal extrahieren
            pass
    return comments

def assign_comment_ranges_to_blocks(blocks: List[Dict[str,Any]], inline_comments: List[Dict[str,Any]]) -> None:
    """
    Given inline_comments with pair numbers, map them to the actual pair blocks.
    For each comment, we attach it to the *last* block in the covered range (so it appears after the range).
    Also we set/merge comment_token_mask for every block in the range.
    """
    # First assign pair_index to each pair/flow block (1-based sequential)
    pair_index = 1
    for b in blocks:
        if not isinstance(b, dict):
            continue
        if b.get('type') in ('pair', 'flow'):
            b['_pair_index'] = pair_index
            pair_index += 1
    
    # Ensure blocks have gr_tokens lists (auch für flow-Blöcke!)
    for b in blocks:
        if not isinstance(b, dict):
            continue
        if b.get('type') in ('pair', 'flow'):
            if 'gr_tokens' not in b:
                b['gr_tokens'] = []
            # init mask if absent
            if 'comment_token_mask' not in b:
                b['comment_token_mask'] = [False] * max(1, len(b.get('gr_tokens', [])))
    
    # For each extracted inline comment, attach to appropriate block
    for cm in inline_comments:
        s = cm['start_pair']
        e = cm['end_pair']
        txt = cm['text']
        # find block with pair_index == e (last block in range). fallback: nearest lower index
        target = None
        for b in blocks:
            if isinstance(b, dict) and b.get('_pair_index') == e:
                target = b
                break
        if target is None:
            # fallback: find last block with pair_index <= e
            for b in reversed(blocks):
                if isinstance(b, dict) and isinstance(b.get('_pair_index'), int) and b.get('_pair_index') <= e:
                    target = b
                    break
        if target is None:
            # give up for this comment
            continue
        
        comment_obj = {
            'text': txt,
            'pair_range': (s, e),
            # we will later set token_start/token_end for the target block; default mark whole block
            'token_start': 0,
            'token_end': max(0, len(target.get('gr_tokens', [])) - 1)
        }
        target.setdefault('comments', []).append(comment_obj)
        
        # Now set mask for all blocks in s..e
        for b in blocks:
            pi = b.get('_pair_index')
            if isinstance(pi, int) and s <= pi <= e:
                # ensure mask length equals token count
                toklen = len(b.get('gr_tokens', []))
                if toklen == 0:
                    b['comment_token_mask'] = []
                    continue
                old = b.get('comment_token_mask') or [False] * toklen
                if len(old) != toklen:
                    # resize preserving old flags
                    new_mask = [False] * toklen
                    for i in range(min(len(old), toklen)):
                        new_mask[i] = old[i]
                    old = new_mask
                # mark entire token range as True (comment)
                for i in range(toklen):
                    old[i] = True
                b['comment_token_mask'] = old

def discover_and_attach_comments(blocks: List[Dict[str,Any]]) -> None:
    """
    Robustere Kommentar-Erkennung und -Zuordnung.
    - erkennt Zeilen wie "(2-4k) Kommentartext ..." (Range-kommentare)
    - erkennt "(5121k) Kommentar..." (Einzelkommentar)
    - erkennt inline "(2-4k) Kommentar" innerhalb einer gr-Zeile
    - hängt Kommentare an block['comments'] an (Liste von dicts: {'start','end','text'})
    - entfernt Kommentartext aus block['gr'] (damit er nicht als normaler Text weiter gerendert bzw. als comment bg markiert wird)
    - legt für jeden Block block['comment_token_mask'] an (bool list mit len(gr_tokens))
    """
    import re

    comment_full_re = re.compile(r'^\s*\((\d+(?:-\d+)?)k\)\s*(.+)$', re.UNICODE)
    comment_inline_re = re.compile(r'\((\d+(?:-\d+)?)k\)\s*([^()]+)', re.UNICODE)

    # 1) build pair_index -> block index mapping for pair/flow blocks
    # Build pair_index for pair/flow blocks if not present
    pair_to_block = {}
    pair_index = 1
    for bi, b in enumerate(blocks):
        if b.get('type') in ('pair', 'flow'):
            # preserve existing if present
            if not b.get('pair_index') and not b.get('_pair_index'):
                b['pair_index'] = pair_index
                b['_pair_index'] = pair_index
            elif b.get('pair_index'):
                b['_pair_index'] = b['pair_index']
            elif b.get('_pair_index'):
                b['pair_index'] = b['_pair_index']
            pair_index_val = b.get('pair_index') or b.get('_pair_index') or pair_index
            pair_to_block[pair_index_val] = bi
            if not b.get('pair_index'):
                b['pair_index'] = pair_index_val
            pair_index += 1

    comments_found = 0

    # 2) scan each block for full-line or inline comment markers
    for bi, b in enumerate(blocks):
        gr = b.get('gr')
        if not gr or not isinstance(gr, str):
            continue

        lines = gr.splitlines()
        new_lines = []
        block_comments = b.setdefault('comments', [])

        for line in lines:
            line_strip = line.strip()
            m = comment_full_re.match(line_strip)
            if m:
                # full-line comment "(2-4k) text..."
                range_str = m.group(1)
                text = m.group(2).strip()
                if '-' in range_str:
                    s, e = range_str.split('-', 1)
                    start, end = int(s), int(e)
                else:
                    start = end = int(range_str)
                # attach comment to blocks whose pair_index is in [start..end]
                # Helper function to attach comment to range
                for target_idx, target_block in enumerate(blocks):
                    if target_block.get('type') in ('pair', 'flow'):
                        target_pi = target_block.get('pair_index') or target_block.get('_pair_index')
                        if target_pi is not None and start <= target_pi <= end:
                            # ensure comments list exists
                            c = target_block.setdefault('comments', [])
                            # token_start/ token_end set to whole block by default
                            token_start = 0
                            token_end = max(0, len(target_block.get('gr_tokens', [])) - 1)
                            c.append({
                                'start': start, 'end': end, 'text': text, 'kind': 'range',
                                'pair_range': (start, end),
                                'token_start': token_start,
                                'token_end': token_end
                            })
                comments_found += 1
                # do not keep this line in the original block -> remove
                continue

            # inline comment(s) in this line?
            inline_matches = list(comment_inline_re.finditer(line))
            if inline_matches:
                cleaned_line = line
                for im in inline_matches:
                    range_str = im.group(1)
                    text = im.group(2).strip()
                    if '-' in range_str:
                        s, e = range_str.split('-', 1)
                        start, end = int(s), int(e)
                    else:
                        start = end = int(range_str)
                    # attach to blocks whose pair_index is in [start..end]
                    for target_idx, target_block in enumerate(blocks):
                        if target_block.get('type') in ('pair', 'flow'):
                            target_pi = target_block.get('pair_index') or target_block.get('_pair_index')
                            if target_pi is not None and start <= target_pi <= end:
                                c = target_block.setdefault('comments', [])
                                token_start = 0
                                token_end = max(0, len(target_block.get('gr_tokens', [])) - 1)
                                c.append({
                                    'start': start, 'end': end, 'text': text, 'kind': 'inline',
                                    'pair_range': (start, end),
                                    'token_start': token_start,
                                    'token_end': token_end
                                })
                    comments_found += 1
                    # remove the inline comment chunk from the line
                    cleaned_line = cleaned_line.replace(im.group(0), '')
                cleaned_line = cleaned_line.strip()
                if cleaned_line:
                    new_lines.append(cleaned_line)
                # if cleaned_line is empty we drop the line
                continue

            # no comment detected: keep original line
            new_lines.append(line)

        # write back the cleaned block text (without detected comment lines)
        if new_lines:
            b['gr'] = '\n'.join(new_lines)
        else:
            b['gr'] = ''
        
        # Also remove comment tokens from gr_tokens if they exist
        gr_tokens = b.get('gr_tokens', [])
        if gr_tokens:
            # Filter out tokens that look like comment markers
            filtered_tokens = []
            for tok in gr_tokens:
                if not isinstance(tok, str):
                    filtered_tokens.append(tok)
                    continue
                tok_strip = tok.strip()
                # Skip tokens that are just comment markers like "(2-4k)" or "(123k)"
                if comment_full_re.match(tok_strip) or comment_inline_re.search(tok):
                    continue
                filtered_tokens.append(tok)
            b['gr_tokens'] = filtered_tokens

    # 3) Build per-block comment_token_mask (True for tokens that are inside a comment range)
    for b in blocks:
        if b.get("type") not in ("pair", "flow"):
            continue
        toks = b.get('gr_tokens') or []
        mask = [False] * len(toks) if toks else []
        # For each comment attached to this block, mark tokens in the range
        for c in b.get("comments", []):
            start = c.get("token_start", 0)
            end = c.get("token_end", -1)
            # If token_end is -1, mark all tokens in the block
            if end < 0:
                end = len(toks) - 1
            # Ensure end is within bounds
            end = min(end, len(toks) - 1) if toks else -1
            # Mark all tokens in the range
            for i in range(max(0, start), max(end + 1, start)):
                if 0 <= i < len(mask):
                    mask[i] = True
        b['comment_token_mask'] = mask

    # debug summary
    sample_comments = blocks[0].get('comments') if blocks else None
    sample_mask = blocks[0].get('comment_token_mask') if blocks else None
    print(f"DEBUG discover_and_attach_comments: comments found={comments_found} sample: {sample_comments[:3] if sample_comments else []} mask-sample: {sample_mask[:40] if sample_mask else None}")
    
    # WICHTIG: Stelle sicher, dass Kommentare auch wirklich an Block angehängt wurden
    total_comments_attached = sum(len(b.get('comments', [])) for b in blocks)
    if total_comments_attached > 0:
        print(f"DEBUG discover_and_attach_comments: total comments attached to blocks: {total_comments_attached}")

# ======= Hilfen: Token-Verarbeitung =======
def _join_tokens_to_line(tokens: list[str]) -> str:
    """
    Einfacher Zusammenbau: Tokens werden durch ein Leerzeichen verbunden.
    Wir vermeiden komplexe Heuristiken; Renderer erwartet i.d.R. Token-Listen
    oder Strings mit Leerzeichen.
    """
    if not tokens:
        return ""
    return " ".join(tokens)

def _remove_tags_from_token(token: str,
                           sup_keep: Optional[set[str]],
                           sub_keep: Optional[set[str]],
                           remove_all: bool) -> str:
    """
    Wrapper, benutzt die bereits vorhandene _remove_selected_tags-Funktion
    und stellt sicher, dass bei zusammengesetzten Tags (A/B) die Normalisierung sauber läuft.
    """
    return _remove_selected_tags(token, sup_keep=sup_keep, sub_keep=sub_keep, remove_all=remove_all)

# ======= Hilfen: Farbentfernung (ohne '|' zu zerstören) =======
def _strip_leading_bar_color_only(token: str) -> str:
    """
    Entfernt NUR den Farbcode nach einem führenden '|' (|+ |# |-),
    belässt aber das '|' selbst.
    """
    if not token:
        return token
    m = RE_LEAD_BAR_COLOR.match(token)
    if not m:
        return token
    # Entferne genau EIN Mal die Sequenz '|{color}'
    color_char = m.group(1)
    return token.replace('|' + color_char, '|', 1)

def _strip_all_colors(token: str) -> str:
    """
    Entfernt ALLE Farbcodes ('#','+','-') aus dem Token,
    inklusive der Variante nach führender '|'.
    """
    if not token:
        return token
    # Erst Spezialfall '|<color>' behandeln
    t = _strip_leading_bar_color_only(token)
    # Jetzt alle übrigen Farbcodes tilgen
    for ch in COLOR_SYMBOLS:
        t = t.replace(ch, '')
    return t

# ======= Hilfen: Tag-Listen am Token =======
def _extract_tags(token: str) -> List[str]:
    if not token:
        return []
    return RE_PAREN_TAG.findall(token)

# ======= Helper: Token-Tag-Parsing =======
def parse_token_tags(token: str):
    """
    Return (base_token, tags_list).
    Example: '+ἐτείας(Adj)(G)...' -> ('+ἐτείας...', ['Adj','G'])
    """
    if not token:
        return '', []
    tags = RE_PAREN_TAG.findall(token)
    base = RE_PAREN_TAG.sub('', token)
    return base, tags

def remove_tags_from_token(token: str, tags_to_remove: set):
    """
    Remove only the (...) occurrences whose tag is in tags_to_remove.
    """
    if not token or not tags_to_remove:
        return token
    
    def repl(m):
        tag = m.group(1)
        return '' if tag in tags_to_remove else m.group(0)
    
    return RE_PAREN_TAG.sub(repl, token)

def remove_all_tags_from_token(token: str):
    """Strip all parenthesized tags from token."""
    if not token:
        return token
    return RE_PAREN_TAG.sub('', token)

def _get_wortart_and_relevant_tags(token_tags: Set[str]) -> (Optional[str], Set[str]):
    """
    Analysiert die Tags eines Tokens und bestimmt die Wortart und die für die
    Konfiguration relevanten Tags.
    """
    # 1. Eindeutige Identifier prüfen (Adj, Adv, Pr, Art, etc.)
    # ABER: Kon und Pt werden NUR als Wortart erkannt, wenn sie das EINZIGE Tag sind
    # (z.B. tribuendoqueAblKonGer soll als Verb erkannt werden, nicht als Kon)
    # (z.B. obtinendineGPtGer soll als Verb erkannt werden, nicht als Pt)
    # (z.B. MīlesneNPt soll als Nomen erkannt werden, nicht als Pt)
    
    # Spezialfall: Wenn Kon oder Pt vorhanden ist UND andere Tags, ignoriere sie komplett
    ignorable_tags = {'Kon', 'Pt'}  # Tags, die nur als Wortart gelten, wenn sie alleine stehen
    has_ignorable = bool(token_tags.intersection(ignorable_tags))
    
    if has_ignorable and len(token_tags) > 1:
        # Prüfe andere Tags (ohne Kon/Pt) in WORTART_IDENTIFIER_TAGS
        for tag, wortart in WORTART_IDENTIFIER_TAGS.items():
            if tag not in ignorable_tags and tag in token_tags:
                return wortart, token_tags
        # Kein anderer Identifier gefunden, fahre mit komplexer Logik fort
        # (z.B. obtinendineGPtGer hat G+Ger, die nicht in WORTART_IDENTIFIER_TAGS sind)
    elif not has_ignorable:
        # Normale Prüfung (weder Kon noch Pt vorhanden)
        for tag, wortart in WORTART_IDENTIFIER_TAGS.items():
            if tag in token_tags:
                return wortart, token_tags
    # Wenn Kon oder Pt das EINZIGE Tag ist, wird es als 'kon' oder 'pt' erkannt

    # 2. Komplexe Fälle: Nomen, Verb, Partizip
    hat_kasus = bool(token_tags.intersection(KASUS_TAGS))
    hat_tempus = bool(token_tags.intersection(TEMPUS_TAGS))
    hat_modus = bool(token_tags.intersection(MODUS_TAGS))  # NEU: Inf, Op, Imv, Knj
    hat_lat_verbform = bool(token_tags.intersection(LATEINISCHE_VERBFORMEN))  # NEU: Ger, Gdv, Spn

    if hat_kasus and hat_tempus:
        return 'partizip', token_tags
    if hat_tempus and not hat_kasus:
        return 'verb', token_tags
    # NEU: Modus (Inf, Op, Imv, Knj) als Verben behandeln (z.B. morīInfAkt)
    if hat_modus and not hat_kasus:
        return 'verb', token_tags
    # NEU: Lateinische Verbformen (Ger, Gdv, Spn) als Verben behandeln
    # AUCH wenn zusätzlich Kon/Pt vorhanden ist (z.B. cogitandiqueGKonGer, obtinendineGPtGer)
    if hat_lat_verbform:
        return 'verb', token_tags
    if hat_kasus and not hat_tempus:
        # Nomen: nur Kasus-Tag(s), AUCH mit Kon/Pt/Du erlaubt (z.B. sollertiaqueAblKon, MīlesneNPt, ἵππωDuN)
        # Entferne Kon, Pt und Du aus der Prüfung (Du = Dual, optional bei Nomen)
        tags_ohne_ignorable = token_tags - {'Kon', 'Pt', 'Du'}
        if tags_ohne_ignorable and all(t in KASUS_TAGS for t in tags_ohne_ignorable):
             return 'nomen', token_tags

    # 3. Standalone-Wortarten: Kon, Pt, Prp, ij
    # WICHTIG: Diese werden erkannt, wenn keine andere Wortart gefunden wurde
    # Auch wenn sie mit anderen Tags kombiniert sind (z.B. καί(Kon) oder δέ(Pt))
    if 'Kon' in token_tags:
        return 'kon', token_tags
    if 'Pt' in token_tags:
        return 'pt', token_tags
    if 'Prp' in token_tags:
        return 'prp', token_tags
    if 'ij' in token_tags:
        return 'ij', token_tags

    return None, set()

def _is_known_sup(tag: str) -> bool:
    # ZUERST: Prüfe ob das gesamte Tag direkt in den Listen enthalten ist
    if tag in SUP_TAGS:
        return True
    # Fallback: zusammengesetzte Tags (A/B/C) - aber nur wenn alle Teile in SUP_TAGS sind
    parts = [p for p in tag.split('/') if p]
    return all(p in SUP_TAGS for p in parts)

def _is_known_sub(tag: str) -> bool:
    # ZUERST: Prüfe ob das gesamte Tag direkt in den Listen enthalten ist
    if tag in SUB_TAGS:
        return True
    # Fallback: zusammengesetzte Tags (A/B/C) - aber nur wenn alle Teile in SUB_TAGS sind
    parts = [p for p in tag.split('/') if p]
    return all(p in SUB_TAGS for p in parts)

def _remove_selected_tags(token: str,
                          *,
                          sup_keep: Optional[set[str]],
                          sub_keep: Optional[set[str]],
                          remove_all: bool) -> str:
    """
    Entfernt (TAG)-Vorkommen gemäß:
      - remove_all=True  → alle bekannten SUP/SUB-Tags weg
      - sonst: entferne alle bekannten SUP/SUB-Tags, die NICHT in sup_keep/sub_keep enthalten sind.
    Unbekannte Tags (weder SUP noch SUB) bleiben unangetastet.
    """
    if not token:
        return token

    def repl(m):
        tag = m.group(1)
        
        # NEU: Normalisiere Umlaute für den Vergleich
        tag_normalized = tag.replace('Prä', 'Prä')
        # Zusätzliche Normalisierung für konsistenten Vergleich
        tag_normalized = _normalize_tag_name(tag_normalized)

        # ZUERST: Prüfe ob das gesamte Tag direkt in den Listen enthalten ist
        is_sup_direct = tag_normalized in SUP_TAGS
        is_sub_direct = tag_normalized in SUB_TAGS
        
        if tag_normalized == TRANSLATION_HIDE_TAG:
            return ''
        
        if is_sup_direct or is_sub_direct:
            # Direktes Match gefunden
            is_sup = is_sup_direct
            is_sub = is_sub_direct
        else:
            # Fallback: Zerlege evtl. 'A/B' in Einzeltags (für zusammengesetzte Tags)
            parts = [p for p in tag_normalized.split('/') if p]
            is_sup = all(p in SUP_TAGS for p in parts)
            is_sub = all(p in SUB_TAGS for p in parts)

        if not (is_sup or is_sub):
            # fremde/sonstige Tags bleiben stehen
            return m.group(0)

        if remove_all:
            return ''  # sämtliche bekannten SUP/SUB entfernen

        # Filtermodus: nur die gewünschten behalten
        if is_sup and sup_keep is not None:
            if is_sup_direct:
                # Direktes Match: prüfe ob Tag in sup_keep (auch normalisiert prüfen)
                if tag_normalized in sup_keep or tag in sup_keep:
                    return m.group(0)  # behalten
                # DEBUG: Nur noch zusammenfassend, nicht pro Tag
                return ''  # raus
            else:
                # Zusammengesetztes Tag: prüfe alle Teile
                if all((p in sup_keep or _normalize_tag_name(p) in sup_keep) for p in parts):
                    return m.group(0)  # behalten
                return ''  # raus
        if is_sub and sub_keep is not None:
            if is_sub_direct:
                # Direktes Match: prüfe ob Tag in sub_keep (auch normalisiert prüfen)
                if tag_normalized in sub_keep or tag in sub_keep:
                    return m.group(0)
                # DEBUG: Tag wird entfernt
                print(f"DEBUG _remove_selected_tags: Entferne SUB-Tag '{tag}' (normalisiert: '{tag_normalized}') - tag in sub_keep: {tag in sub_keep}, normalized in sub_keep: {tag_normalized in sub_keep}, sub_keep={sorted(list(sub_keep))[:10]}...")
                return ''
            else:
                # Zusammengesetztes Tag: prüfe alle Teile
                if all((p in sub_keep or _normalize_tag_name(p) in sub_keep) for p in parts):
                    return m.group(0)
                return ''
        # Falls keine Keep-Liste für die Kategorie übergeben wurde:
        # Standard: behalten
        return m.group(0)

    return RE_PAREN_TAG.sub(repl, token)

# ======= Hilfen: PoS-Ermittlung für Farbregel =======
def _has_any_pos(token: str, pos_whitelist: set[str]) -> bool:
    """
    Prüft, ob das Token mind. einen (TAG) aus der pos_whitelist trägt.
    Die Prüfung erfolgt auf SUP+SUB-Tags (da PoS bei dir als SUP-Tags geführt werden).
    """
    tags = _extract_tags(token)
    for t in tags:
        parts = [p for p in t.split('/') if p]
        for p in parts:
            if p in pos_whitelist:
                return True
    return False


def _apply_colors_and_placements(blocks: List[Dict[str, Any]], config: Dict[str, Any], disable_comment_bg: bool = False) -> List[Dict[str, Any]]:
    """
    Fügt Farbsymbole und (zukünftig) Platzierungen basierend auf der vollen Konfiguration hinzu.
    
    WICHTIG: Wenn disable_comment_bg=True, werden Hintergrundfarben in Kommentarbereichen unterdrückt.
    Die Wort-/Tag-Farben (Symbole) bleiben jedoch erhalten.
    
    IMPORTANT: Store original tags per token into block['token_meta'][i]['orig_tags'] so later stages
    can use the original tags (for deciding which tags to remove) while colors remain
    computed from original tags.
    """
    if not config:
        return blocks
        
    new_blocks = []
    for block in blocks:
        if isinstance(block, dict) and block.get('type') in ('pair', 'flow'):
            new_block = block.copy()
            gr_tokens = new_block.get('gr_tokens', [])
            de_tokens = new_block.get('de_tokens', [])
            en_tokens = new_block.get('en_tokens', [])  # NEU: Englische Tokens für 3-sprachige Texte
            
            new_gr_tokens = list(gr_tokens)
            new_de_tokens = list(de_tokens)
            new_en_tokens = list(en_tokens) if en_tokens else []  # NEU: Englische Tokens kopieren

            # Initialize token_meta for storing original tags
            token_meta = new_block.setdefault("token_meta", [{} for _ in gr_tokens])
            # Create comment mask default (may be set elsewhere)
            if "comment_token_mask" not in new_block:
                new_block["comment_token_mask"] = [False] * len(gr_tokens)
            
            for i, token in enumerate(gr_tokens):
                if not token:
                    continue
                
                # Extract original tags and store them so later removal uses original tag set
                orig_tags = set(_extract_tags(token))
                # Speichere die Original-Tags, falls noch nicht vorhanden (wichtig für apply_tag_visibility)
                if i < len(token_meta):
                    if 'orig_tags' not in token_meta[i] or not token_meta[i].get('orig_tags'):
                        token_meta[i]['orig_tags'] = list(orig_tags)
                else:
                    # sollte nicht passieren, aber sicherstellen
                    token_meta.append({'orig_tags': list(orig_tags)})
                
                # If disable_comment_bg and this token belongs to comment → skip bg coloring
                if disable_comment_bg and new_block.get("comment_token_mask", [False])[i]:
                    # Still keep other color metadata (e.g. token color), but skip background fill
                    # We still may set token_meta[i]['color'] etc. if needed
                    continue
                
                if any(c in token for c in COLOR_SYMBOLS):
                    continue

                token_tags = orig_tags
                
                if not token_tags:
                    continue
                
                # Bestimme Wortart und relevante Tags
                wortart, relevant_tags = _get_wortart_and_relevant_tags(token_tags)
                if not wortart:
                    continue
                
                # Finde die relevanteste Regel basierend auf der Prioritäts-Hierarchie
                best_rule_config = None
                highest_priority = -1

                # 1. Prüfe Gruppenanführer-Regel zuerst (niedrigste Priorität)
                group_leader_id = f"{wortart}"
                group_leader_config = config.get(group_leader_id)
                if group_leader_config and 'color' in group_leader_config:
                    best_rule_config = group_leader_config
                    highest_priority = 0

                # 2. Prüfe alle spezifischen Tags (höhere Priorität = weiter unten in der Tabelle)
                for tag in relevant_tags:
                    rule_id = f"{wortart}_{tag}"
                    # Versuche auch normalisierte Versionen für Draft-Kompatibilität
                    normalized_rule_id = _normalize_rule_id(rule_id)
                    
                    rule_config = config.get(rule_id) or config.get(normalized_rule_id)
                    if rule_config and 'color' in rule_config:
                        # Bestimme Priorität basierend auf Position in der HIERARCHIE
                        priority = 0
                        if wortart in HIERARCHIE and tag in HIERARCHIE[wortart]:
                            # Höhere Priorität = weiter unten in der Liste
                            priority = HIERARCHIE[wortart].index(tag) + 1
                        else:
                            # Fallback: Tags ohne Hierarchie bekommen Standard-Priorität
                            priority = 100
                        
                        if priority > highest_priority:
                            highest_priority = priority
                            best_rule_config = rule_config
                
                # Regel anwenden (aktuell nur Farbe)
                if best_rule_config and 'color' in best_rule_config:
                    color = best_rule_config['color']
                    if color in COLOR_MAP:
                        symbol = COLOR_MAP[color]
                        
                        # Symbol im griechischen Token einfügen
                        match = RE_WORD_START.search(token)
                        if match:
                            new_gr_tokens[i] = token[:match.start(2)] + symbol + token[match.start(2):]

                            # Symbol auf deutsches Token übertragen
                            if i < len(de_tokens):
                                de_tok = de_tokens[i]
                                if de_tok and not any(c in de_tok for c in COLOR_SYMBOLS):
                                    de_match = RE_WORD_START.search(de_tok)
                                    if de_match:
                                        new_de_tokens[i] = de_tok[:de_match.start(2)] + symbol + de_tok[de_match.start(2):]
                                    else:
                                        new_de_tokens[i] = symbol + de_tok
                            
                            # NEU: Symbol auch auf englisches Token übertragen (für 3-sprachige Texte)
                            if i < len(new_en_tokens):
                                en_tok = en_tokens[i]
                                if en_tok and not any(c in en_tok for c in COLOR_SYMBOLS):
                                    en_match = RE_WORD_START.search(en_tok)
                                    if en_match:
                                        new_en_tokens[i] = en_tok[:en_match.start(2)] + symbol + en_tok[en_match.start(2):]
                                    else:
                                        new_en_tokens[i] = symbol + en_tok
            
            new_block['gr_tokens'] = new_gr_tokens
            new_block['de_tokens'] = new_de_tokens
            if new_en_tokens:  # NEU: Englische Tokens nur setzen, wenn vorhanden
                new_block['en_tokens'] = new_en_tokens
            new_blocks.append(new_block)
        else:
            new_blocks.append(block)
    
    return new_blocks


# ======= Token-Prozessor =======
def _process_token(token: str,
                   *,
                   color_mode: ColorMode,
                   tag_mode: TagMode,
                   versmass_mode: VersmassMode,
                   color_pos_keep: Optional[set[str]],
                   sup_keep: Optional[set[str]],
                   sub_keep: Optional[set[str]],
                   is_greek_line: bool) -> str:
    t = token or ''

    # 1) Farben
    if color_mode == "BLACK_WHITE":
        t = _strip_all_colors(t)
    else:  # "COLOR"
        if color_pos_keep is not None:
            # Farbcodes nur dort beibehalten, wo PoS in color_pos_keep
            if _has_any_pos(t, color_pos_keep):
                # nix – Farben bleiben
                pass
            else:
                t = _strip_all_colors(t)

    # 2) Tags
    if tag_mode == "NO_TAGS":
        t = _remove_selected_tags(t, sup_keep=None, sub_keep=None, remove_all=True)
    else:  # "TAGS"
        t = _remove_selected_tags(t,
                                  sup_keep=sup_keep,
                                  sub_keep=sub_keep,
                                  remove_all=False)

    # 3) Versmaß
    #   - nur griechische Zeile hat Marker; deutsche Tokens bleiben stets markerfrei
    if is_greek_line:
        if versmass_mode == "REMOVE_MARKERS":
            t = re.sub(r'[iL|]', '', t)
        elif versmass_mode == "KEEP_MARKERS":
            pass  # nichts tun
        else:
            # "NORMAL": Marker bleiben stehen; Renderer macht ggf. „Bars unsichtbar“
            pass

    return t

# ======= Block-Prozessor =======
def _process_pair_block(block: Dict[str, Any],
                        *,
                        color_mode: ColorMode,
                        tag_mode: TagMode,
                        versmass_mode: VersmassMode,
                        color_pos_keep: Optional[set[str]],
                        sup_keep: Optional[set[str]],
                        sub_keep: Optional[set[str]]) -> Dict[str, Any]:
    """
    Erwartet einen 'pair'-Block mit 'gr_tokens' / 'de_tokens' ODER 'gr' / 'de'.
    Gibt einen NEUEN Block zurück (Original bleibt unangetastet).
    """

    def proc_tokens(seq: Iterable[str], *, is_greek_line: bool) -> List[str]:
        return [
            _process_token(tok,
                           color_mode=color_mode,
                           tag_mode=tag_mode,
                           versmass_mode=versmass_mode if is_greek_line else "NORMAL",
                           color_pos_keep=color_pos_keep,
                           sup_keep=sup_keep,
                           sub_keep=sub_keep,
                           is_greek_line=is_greek_line)
            for tok in (seq or [])
        ]

    if 'gr_tokens' in block or 'de_tokens' in block:
        gr = block.get('gr_tokens', [])
        de = block.get('de_tokens', [])
        return {
            **block,
            'gr_tokens': proc_tokens(gr, is_greek_line=True),
            'de_tokens': proc_tokens(de, is_greek_line=False),
        }

    # Fallback: Stringzeilen (selten in deinen Pipelines)
    gr_s = block.get('gr', '')
    de_s = block.get('de', '')

    def _split(s: str) -> list:
        return [p for p in (s or '').split() if p]

    def _join(xs: list) -> str:
        return ' '.join(xs)

    gr_t = proc_tokens(_split(gr_s), is_greek_line=True)
    de_t = proc_tokens(_split(de_s), is_greek_line=False)
    return {**block, 'gr': _join(gr_t), 'de': _join(de_t)}

# ======= Hilfsfunktionen =======

def _normalize_tag_name(tag: str) -> str:
    """
    Normalisiert Tag-Namen für Kompatibilität mit Draft-Dateien.
    """
    # Normalisiere Umlaute
    tag = tag.replace('Pra', 'Prä')
    
    # Normalisiere Wortart-Präfixe
    if tag.startswith('adverb'):
        tag = tag.replace('adverb', 'adv')
    if tag.startswith('pronomen'):
        tag = tag.replace('pronomen', 'pr')
    if tag.startswith('artikel'):
        tag = tag.replace('artikel', 'art')
    if tag.startswith('adjektiv'):
        tag = tag.replace('adjektiv', 'adj')
    
    # Normalisiere Standalone-Tags zu den korrekten Tag-Namen
    if tag == 'pr':
        return 'Pr'
    elif tag == 'adj':
        return 'Adj'
    elif tag == 'kon':
        return 'Kon'
    elif tag == 'pt':
        return 'Pt'
    elif tag == 'art':
        return 'Art'
    elif tag == 'prp':
        return 'Prp'
    elif tag == 'adv':
        return 'Adv'
    elif tag == 'ij':
        return 'ij'
    elif tag == 'MP':
        return 'M/P'
    
    return tag

def _resolve_tags_for_rule(normalized_rule_id: str) -> List[str]:
    if '_' in normalized_rule_id:
        tag = normalized_rule_id.split('_', 1)[1]
        return [tag]
    return RULE_TAG_MAP.get(normalized_rule_id, [normalized_rule_id])

def _token_should_hide_translation(token: str, translation_rules: Optional[Dict[str, Dict[str, Any]]]) -> bool:
    if not token or not translation_rules:
        return False

    tags = _extract_tags(token)
    # Prüfe zuerst auf HideTrans-Tag
    if TRANSLATION_HIDE_TAG in tags:
        return True
    
    # WICHTIG: Verwende ORIGINALE Tags (nicht normalisiert) für Wortart-Erkennung
    original_tags = set(tags)
    wortart, _ = _get_wortart_and_relevant_tags(original_tags)
    
    if wortart:
        wortart_key = wortart.lower()
        entry = translation_rules.get(wortart_key)
        if entry:
            if entry.get("all"):
                return True
            # Prüfe auf Tags in entry["tags"]
            entry_tags = entry.get("tags", set())
            if entry_tags:
                # Normalisiere beide Sets für Vergleich
                normalized_entry_tags = {_normalize_tag_name(t) for t in entry_tags}
                # Für jedes originale Tag: normalisiere es und prüfe
                for orig_tag in original_tags:
                    parts = [p for p in orig_tag.split('/') if p]
                    for part in parts:
                        normalized_part = _normalize_tag_name(part)
                        if normalized_part in normalized_entry_tags:
                            return True

    global_entry = translation_rules.get(TRANSLATION_HIDE_GLOBAL)
    if global_entry:
        if global_entry.get("all"):
            return True
        entry_tags = global_entry.get("tags", set())
        if entry_tags:
            normalized_entry_tags = {_normalize_tag_name(t) for t in entry_tags}
            for orig_tag in original_tags:
                parts = [p for p in orig_tag.split('/') if p]
                for part in parts:
                    normalized_part = _normalize_tag_name(part)
                    if normalized_part in normalized_entry_tags:
                        return True

    return False

def _normalize_rule_id(rule_id: str) -> str:
    """
    Normalisiert Regel-IDs für Kompatibilität mit Draft-Dateien.
    """
    if '_' not in rule_id:
        # Für Standalone-Tags (ohne Unterstrich)
        return _normalize_tag_name(rule_id)
    
    parts = rule_id.split('_')
    if len(parts) >= 2:
        wortart = parts[0]
        tag = '_'.join(parts[1:])  # In case there are multiple underscores
        
        # Spezielle Behandlung für Sonderzeichen in Regel-IDs
        if tag == 'M/P':
            return f"{wortart}_MP"
        elif tag == 'Prä':
            return f"{wortart}_Pra"
        
        normalized_tag = _normalize_tag_name(tag)
        return f"{wortart}_{normalized_tag}"
    
    return rule_id

def _register_translation_rule(rules: Dict[str, Dict[str, Any]], normalized_rule_id: str) -> None:
    if not normalized_rule_id:
        return
    if '_' in normalized_rule_id:
        wordart, tag = normalized_rule_id.split('_', 1)
    else:
        wordart, tag = normalized_rule_id, None

    normalized_wordart = wordart.lower()

    if normalized_wordart not in RULE_TAG_MAP:
        normalized_tag = _normalize_tag_name(normalized_rule_id)
        entry = rules.setdefault(TRANSLATION_HIDE_GLOBAL, {"all": False, "tags": set()})
        if normalized_tag:
            entry["tags"].add(normalized_tag)
        return

    entry = rules.setdefault(normalized_wordart, {"all": False, "tags": set()})
    if tag:
        entry["tags"].add(_normalize_tag_name(tag))
    else:
        entry["all"] = True

def _should_hide_translation(conf: Dict[str, Any]) -> bool:
    return bool(conf.get('hideTranslation'))

def _maybe_register_translation_rule(rules: Dict[str, Dict[str, Any]], normalized_rule_id: str, conf: Dict[str, Any]) -> None:
    if _should_hide_translation(conf):
        _register_translation_rule(rules, normalized_rule_id)

# ======= Öffentliche, granulare API =======

def apply_colors(blocks: List[Dict[str, Any]], tag_config: Dict[str, Any], disable_comment_bg: bool = False) -> List[Dict[str, Any]]:
    """
    Fügt Farbsymbole (#, +, §, $) basierend auf der tag_config hinzu.
    Gibt eine NEUE, tief kopierte Blockliste zurück.
    Die Original-Tags bleiben vollständig erhalten.
    
    WICHTIG: Versteckt auch Übersetzungen für (HideTrans) Tags NACH dem Hinzufügen der Farben.
    NEU: Entfernt auch Stephanus-Paginierungen aus Übersetzungszeilen, wenn Übersetzungen ausgeblendet sind.
    
    disable_comment_bg: Wenn True, werden Hintergrundfarben in Kommentarbereichen unterdrückt.
    """
    import copy
    blocks_copy = copy.deepcopy(blocks)
    
    # Schritt 1: Füge Farben hinzu (ZUERST, damit Farben nicht verloren gehen)
    blocks_with_colors = _apply_colors_and_placements(blocks_copy, tag_config)
    
    # Schritt 2: Erstelle translation_rules aus tag_config
    translation_rules: Dict[str, Dict[str, Any]] = {}
    if tag_config:
        for rule_id, conf in tag_config.items():
            normalized_rule_id = _normalize_rule_id(rule_id)
            _maybe_register_translation_rule(translation_rules, normalized_rule_id, conf)
    
    # Schritt 3: Verstecke Übersetzungen für (HideTrans) Tags und entferne Stephanus-Paginierungen (DANACH)
    blocks_with_hidden_trans = []
    for block in blocks_with_colors:
        if isinstance(block, dict) and block.get('type') in ('pair', 'flow'):
            # Verstecke manuelle Übersetzungen (HideTrans)
            block = _hide_manual_translations_in_block(block)
            # Entferne Stephanus-Paginierungen aus Übersetzungszeilen
            block = _hide_stephanus_in_translations(block, translation_rules if translation_rules else None)
            blocks_with_hidden_trans.append(block)
        else:
            blocks_with_hidden_trans.append(block)
    
    return blocks_with_hidden_trans

def apply_tag_visibility(blocks: List[Dict[str, Any]], tag_config: Optional[Dict[str, Any]], hidden_tags_by_wortart: Optional[Dict[str, Set[str]]] = None) -> List[Dict[str, Any]]:
    """
    WICHTIG: Tags werden nur bei der entsprechenden Wortart entfernt!
    Wenn "nomen" ausgeblendet wird, werden Kasus-Tags nur bei Nomen entfernt, nicht bei Partizipien.
    
    Robust: expandiert Gruppen-Regeln in konkrete hidden_tags pro Wortart, berechnet sup_keep/sub_keep pro Token,
    entfernt die nicht gewünschten Tags aus ALLEN token-Feldern und schreibt gr/de strings zurück.
    """
    # helper: is this translation-only (punctuation / Stephanus) so it can be deduped?
    import re
    _re_only_punct = re.compile(r'^[\s\.\,\:\;\?\!\-\–\—\"\'\[\]\(\)\/\\]+$')
    _re_stephanus = re.compile(r'^\s*\[\s*\d+\s*[a-z]?\s*\]\s*$', re.I)
    
    def is_translation_empty_or_punct(txt: str) -> bool:
        if not txt or not txt.strip():
            return True
        s = txt.strip()
        if _re_only_punct.match(s):
            return True
        if _re_stephanus.match(s):
            return True
        return False
    
    import copy
    blocks_copy = copy.deepcopy(blocks)
    
    # Struktur: {wortart: {tags_to_hide}} - Tags werden nur bei der richtigen Wortart entfernt
    # Wenn hidden_tags_by_wortart bereits übergeben wurde, verwende es, sonst baue es aus tag_config
    if hidden_tags_by_wortart is None:
        hidden_tags_by_wortart = {}
    else:
        hidden_tags_by_wortart = {k.lower(): set(v) for k, v in hidden_tags_by_wortart.items()}
    
    # -- ensure we detect "quote" blocks indicated by markers like '[Zitat Anfang]' / '[Zitat Ende]'
    in_quote = False
    for b in blocks_copy:
        txt = b.get('gr', '')
        if isinstance(txt, str) and 'Zitat Anfang' in txt:
            in_quote = True
            b['_in_quote_marker'] = True
        elif isinstance(txt, str) and 'Zitat Ende' in txt:
            # mark the end block and set flag on it too
            b['_in_quote_marker'] = True
            in_quote = False
        # mark blocks inside quotes
        b['_in_quote'] = in_quote or b.get('_in_quote_marker', False)
    
    translation_rules: Dict[str, Dict[str, Any]] = {}
    
    if tag_config and not hidden_tags_by_wortart:
        # If adapter already provided hidden_tags array, use it (globale hidden tags)
        global_hidden_tags = set()
        if isinstance(tag_config.get('hidden_tags'), (list, tuple, set)):
            for t in tag_config.get('hidden_tags', []):
                if isinstance(t, str) and t:
                    global_hidden_tags.add(t)
        
        # Collect from rules with hide=true
        for rule_id, conf in (tag_config.items() if isinstance(tag_config, dict) else []):
            if not isinstance(conf, dict):
                continue
            
            # Register translation rules
            normalized_rule_id = _normalize_rule_id(rule_id)
            _maybe_register_translation_rule(translation_rules, normalized_rule_id, conf)
            
            hide_val = conf.get('hide')
            if hide_val in (True, 'true', 'True', 'hide', 'Hide'):
                rid = rule_id.strip()
                
                # Bestimme Wortart und Tags
                if '_' in rid:
                    # Spezifische Regel: z.B. 'nomen_N' -> wortart='nomen', tag='N'
                    parts = rid.split('_', 1)
                    wortart_key = parts[0].lower()
                    tag = parts[1]
                    
                    # Normalisiere wortart_key
                    if wortart_key in RULE_TAG_MAP:
                        wortart = wortart_key
                    elif wortart_key in HIERARCHIE:
                        wortart = wortart_key
                    else:
                        continue
                    
                    if tag in SUP_TAGS or tag in SUB_TAGS:
                        # Verwende wortart_key (lowercase) für konsistente Keys
                        if wortart_key not in hidden_tags_by_wortart:
                            hidden_tags_by_wortart[wortart_key] = set()
                        hidden_tags_by_wortart[wortart_key].add(tag)
                else:
                    # Gruppen-Regel: z.B. 'nomen' -> alle Kasus-Tags für Nomen
                    key = rid.lower()
                    mapped = RULE_TAG_MAP.get(key) or HIERARCHIE.get(key)
                    if mapped:
                        if key not in hidden_tags_by_wortart:
                            hidden_tags_by_wortart[key] = set()
                        for t in mapped:
                            hidden_tags_by_wortart[key].add(t)
                    else:
                        # Vielleicht ein konkretes Tag direkt
                        if rid in SUP_TAGS or rid in SUB_TAGS:
                            global_hidden_tags.add(rid)
        
        # Füge globale hidden tags zu allen Wortarten hinzu (falls nötig)
        if global_hidden_tags:
            for wortart in hidden_tags_by_wortart:
                hidden_tags_by_wortart[wortart].update(global_hidden_tags)
    
    # Normalisiere alle Keys zu lowercase für konsistente Lookups (falls noch nicht normalisiert)
    if hidden_tags_by_wortart and not any(k != k.lower() for k in hidden_tags_by_wortart.keys()):
        # Bereits normalisiert, nichts zu tun
        pass
    elif hidden_tags_by_wortart:
        hidden_tags_by_wortart = {k.lower(): v for k, v in hidden_tags_by_wortart.items()}
    
    # ---- Helper: Entferne nur die angegebenen Tags aus einem Token-String ----
    def remove_tags_from_token_local(tok: str, tags_to_remove: Set[str] = None, remove_all: bool = False) -> str:
        """
        Entferne nur die Parenthesen-Tags (z.B. '(N)', '(G)') aus tok, die in tags_to_remove stehen.
        Bewahrt Prefixe wie '$', '+', '-', '§' und alle anderen Teile des Tokens.
        Wenn remove_all=True, entfernt ALLE Tag-Gruppen (alle (...) Klammern), behält aber andere Zeichen.
        """
        if remove_all:
            # Remove all parenthesis tag-groups (keeps punctuation / leading markers)
            cleaned = RE_PAREN_TAG.sub('', tok)
            return cleaned
        if not tags_to_remove:
            return tok
        # callback für jede Klammergruppe
        def repl(m):
            tag = m.group(1).strip()
            # falls Gruppe aus mehreren Subtags besteht (sollte selten sein), check jedes Einzelne:
            # Wir behandeln einzelne rohe Tags (z.B. 'N', 'G', 'Adj'), remove wenn eines matcht.
            if tag in tags_to_remove:
                return ''
            return '(' + tag + ')'
        # ersetze jede (TAG) Gruppe einzeln
        result = RE_PAREN_TAG.sub(repl, tok)
        # Trim überflüssige Doppelpunkte/Kommas etc. nicht verändern — wir geben result zurück
        return result
    
    if hidden_tags_by_wortart:
        # Normalisiere alle Keys zu lowercase für konsistente Lookups
        hidden_tags_by_wortart_normalized = {k.lower(): v for k, v in hidden_tags_by_wortart.items()}
        hidden_tags_by_wortart = hidden_tags_by_wortart_normalized
        print(f"DEBUG apply_tag_visibility: hidden_tags_by_wortart: {dict((k, sorted(list(v))[:10]) for k, v in hidden_tags_by_wortart.items())}")
    else:
        print("DEBUG apply_tag_visibility: hidden_tags_by_wortart ist leer - keine Tags werden entfernt")
    
    # iterate blocks
    changed_total = 0
    for bi, block in enumerate(blocks_copy):
        if not isinstance(block, dict):
            continue
        gr_tokens = block.get('gr_tokens', [])
        # token_meta sollte von apply_colors gesetzt worden sein; wenn nicht, erzeuge Platzhalter
        token_meta = block.setdefault("token_meta", [{} for _ in gr_tokens])
        
        # if block seems to be a quote-block, treat it the same as normal blocks when removing tags.
        block_in_quote = bool(block.get('_in_quote', False))
        
        # Only process pair/flow blocks (quote blocks are already marked with _in_quote, so they will be processed too)
        if block.get('type') not in ('pair','flow') and not block_in_quote:
            continue
        
        # WICHTIG: Übersetzungs-Ausblendung ZUERST (bevor Tags entfernt werden)
        # Verwende ORIGINAL-Tokens (mit allen Tags) für die Erkennung
        if translation_rules:
            gr_tokens_original = block.get('gr_tokens', [])
            de_tokens = block.get('de_tokens', [])
            en_tokens = block.get('en_tokens', [])
            
            for idx, gr_token in enumerate(gr_tokens_original):
                if _token_should_hide_translation(gr_token, translation_rules):
                    # Entferne Übersetzung, aber prüfe auch ob sie trivial ist (nur Interpunktion/Stephanus)
                    # WICHTIG: Wenn Übersetzung trivial ist, entferne sie auch wenn hide_translation nicht aktiv ist
                    if idx < len(de_tokens):
                        de_text = de_tokens[idx].strip() if isinstance(de_tokens[idx], str) else ''
                        # Wenn Übersetzung trivial ist (nur Interpunktion/Stephanus), entferne sie komplett
                        if is_trivial_translation(de_text):
                            de_tokens[idx] = ''
                        # Ansonsten: entferne nur wenn hide_translation aktiv ist (was hier der Fall ist, da wir in diesem if-Block sind)
                        else:
                            de_tokens[idx] = ''
                    
                    if idx < len(en_tokens):
                        en_text = en_tokens[idx].strip() if isinstance(en_tokens[idx], str) else ''
                        if is_trivial_translation(en_text):
                            en_tokens[idx] = ''
                        else:
                            en_tokens[idx] = ''
            
            # Aktualisiere die Token-Listen im Block
            block['de_tokens'] = de_tokens
            block['en_tokens'] = en_tokens
        
        # DANACH: Tag-Entfernung (wortart-spezifisch)
        # neue, sichere Logik: benutze orig_tags (falls vorhanden), bestimme wortart davon,
        # entferne nur die Tags, die in hidden_tags_by_wortart[w] stehen UND tatsächlich auf dem Token vorhanden sind.
        new_tokens_for_block: List[str] = []
        changed = 0
        
        for i, tok in enumerate(gr_tokens):
            if not tok:
                new_tokens_for_block.append(tok)
                continue
            
            # Ursprungstags: falls apply_colors token_meta['orig_tags'] gesetzt hat -> benutzen,
            # sonst aus dem Token extrahieren
            original_tags = set()
            if i < len(token_meta):
                original_tags = set(token_meta[i].get('orig_tags', []))
            if not original_tags:
                original_tags = set(_extract_tags(tok))
            orig_tags = original_tags
            
            # normalize for detection (case-insensitive)
            original_tags_normalized = set(t.lower() for t in orig_tags)
            
            # If token contains the HideTags flag, remove all tags from its printable form
            # WICHTIG: Farben bleiben erhalten, weil sie bereits von apply_colors gesetzt wurden!
            if TAG_HIDE_TAGS.lower() in original_tags_normalized:
                # Remove all tag groups like '(Adj)(G)' etc. but keep punctuation and color
                cleaned = remove_tags_from_token_local(tok, remove_all=True)
                # Debug output
                if bi < 2 and i < 5:
                    print(f"DEBUG apply_tag_visibility: Block {bi} Token {i}: HideTags detected, removed all tags, orig_tags={sorted(list(orig_tags))[:8]}")
                new_tokens_for_block.append(cleaned)
                if cleaned != tok:
                    changed += 1
                # Mark that we removed all tags due to HideTags
                if i < len(token_meta):
                    token_meta[i]['removed_tags'] = list(orig_tags)  # All tags were removed
                    token_meta[i]['hide_tags_flag'] = True
                else:
                    # fallback - erweitern
                    while len(token_meta) <= i:
                        token_meta.append({})
                    token_meta[i]['removed_tags'] = list(orig_tags)
                    token_meta[i]['hide_tags_flag'] = True
                continue
            
            # Bestimme Wortart für dieses Token anhand der ORIGINAL-Tags (hilfsfunktion wird verwendet)
            try:
                wortart, _ = _get_wortart_and_relevant_tags(orig_tags)
            except Exception:
                wortart = None
            
            tags_to_hide = set()
            if hidden_tags_by_wortart and wortart:
                tags_to_hide = set(hidden_tags_by_wortart.get(wortart.lower(), []))
            
            # compute intersection: remove only tags actually present on token (orig tags)
            # If block is a quote and we shouldn't treat it specially, still apply rules (user expects same behaviour)
            # Remove only the tags that both are in tags_to_hide and present in original_tags
            tags_to_remove = tags_to_hide & orig_tags if tags_to_hide else set()
            if tags_to_remove:
                sup_keep_for_token = set(SUP_TAGS) - (tags_to_remove & set(SUP_TAGS))
                sub_keep_for_token = set(SUB_TAGS) - (tags_to_remove & set(SUB_TAGS))
                cleaned = remove_tags_from_token_local(tok, tags_to_remove)
                # Debug: only print for first blocks / tokens (limit output)
                if bi < 2 and i < 5:
                    print(f"DEBUG apply_tag_visibility: Block {bi} Token {i}: wortart='{wortart}', tags_removed={sorted(list(tags_to_remove))}, orig_tags={sorted(list(orig_tags))[:8]}")
                if cleaned != tok:
                    changed += 1
                new_tokens_for_block.append(cleaned)
            else:
                cleaned = tok
                new_tokens_for_block.append(cleaned)
            
            # --- Dedupe translations that are only punctuation/Stephanus
            # token_meta may contain translation text in token_meta[i]['translation']
            if i < len(token_meta):
                # Check de_tokens and en_tokens in the block
                de_tokens = block.get('de_tokens', [])
                en_tokens = block.get('en_tokens', [])
                
                if i < len(de_tokens):
                    de_text = de_tokens[i] if isinstance(de_tokens[i], str) else ''
                    if is_translation_empty_or_punct(de_text):
                        # remove translation so renderer won't output an empty punct-only translation cell
                        if i < len(block.get('de_tokens', [])):
                            block['de_tokens'][i] = ''
                
                if i < len(en_tokens):
                    en_text = en_tokens[i] if isinstance(en_tokens[i], str) else ''
                    if is_translation_empty_or_punct(en_text):
                        if i < len(block.get('en_tokens', [])):
                            block['en_tokens'][i] = ''
                # SICHERN: welche Tags wir für dieses token tatsächlich entfernt haben
                actually_removed = list((set(orig_tags) & set(tags_to_remove)))
                # Stelle sicher, dass token_meta existiert
                if i < len(token_meta):
                    token_meta[i]['removed_tags'] = actually_removed
                else:
                    # fallback - erweitern
                    while len(token_meta) <= i:
                        token_meta.append({})
                    token_meta[i]['removed_tags'] = actually_removed
            else:
                new_tokens_for_block.append(tok)
                # kein Entfernen — entfernte Tags leer setzen
                if i < len(token_meta) and 'removed_tags' not in token_meta[i]:
                    token_meta[i].setdefault('removed_tags', [])
        
        # End for tokens in block
        block['gr_tokens'] = new_tokens_for_block
        if changed:
            changed_total += changed
        
        # Rebuild string fields if renderer may use them
        if 'gr_tokens' in block:
            block['gr'] = _join_tokens_to_line(block.get('gr_tokens', []))
        if 'de_tokens' in block:
            block['de'] = _join_tokens_to_line(block.get('de_tokens', []))
        if 'en_tokens' in block:
            block['en'] = _join_tokens_to_line(block.get('en_tokens', []))
    
    # Final debug output after processing all blocks
    if changed_total > 0:
        print(f"DEBUG apply_tag_visibility: {changed_total} token(s) changed total")
    elif hidden_tags_by_wortart:
        print(f"DEBUG apply_tag_visibility: Tag-Entfernung abgeschlossen (hidden_tags_by_wortart: {list(hidden_tags_by_wortart.keys()) if hidden_tags_by_wortart else '{}'})")
    
    return blocks_copy

def remove_all_tags(blocks: List[Dict[str, Any]],
                    tag_config: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """
    Entfernt ALLE bekannten Grammatik-Tags (SUP und SUB).
    Gibt eine NEUE, tief kopierte Blockliste zurück.
    """
    import copy
    blocks_copy = copy.deepcopy(blocks)
    processed_blocks = []
    translation_rules: Dict[str, Dict[str, Any]] = {}
    if tag_config:
        for rule_id, conf in tag_config.items():
            normalized_rule_id = _normalize_rule_id(rule_id)
            _maybe_register_translation_rule(translation_rules, normalized_rule_id, conf)

    for b in blocks_copy:
        if isinstance(b, dict) and b.get('type') in ('pair', 'flow'):
            processed_blocks.append(_process_pair_block_for_tags(
                b,
                sup_keep=set(),
                sub_keep=set(),
                remove_all=True,
                translation_rules=translation_rules if translation_rules else None,
            ))
        else:
            # Kommentare und andere Block-Typen durchreichen
            processed_blocks.append(b)
    return processed_blocks

def remove_all_color_symbols(blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Entfernt ALLE Farbsymbole (#, +, §, $) aus allen Tokens.
    Gibt eine NEUE, tief kopierte Blockliste zurück.
    """
    import copy
    blocks_copy = copy.deepcopy(blocks)
    processed_blocks = []
    for b in blocks_copy:
        if isinstance(b, dict) and b.get('type') in ('pair', 'flow'):
            processed_blocks.append(_strip_colors_from_block(b))
        else:
            processed_blocks.append(b)
    return processed_blocks


# ======= Hilfen: PoS-Ermittlung für Farbregel =======
def _has_any_pos(token: str, pos_whitelist: set[str]) -> bool:
    """
    Prüft, ob das Token mind. einen (TAG) aus der pos_whitelist trägt.
    Die Prüfung erfolgt auf SUP+SUB-Tags (da PoS bei dir als SUP-Tags geführt werden).
    """
    tags = _extract_tags(token)
    for t in tags:
        parts = [p for p in t.split('/') if p]
        for p in parts:
            if p in pos_whitelist:
                return True
    return False


# ======= Veraltete Öffentliche API (wird schrittweise entfernt) =======
def apply(blocks: List[Dict[str, Any]],
          *,
          color_mode: ColorMode,
          tag_mode: TagMode,
          versmass_mode: VersmassMode = "NORMAL",
          # NEU (optional):
          tag_config: Optional[Dict[str, Any]] = None,
          disable_comment_bg: bool = False) -> List[Dict[str, Any]]:
    """
    Vorverarbeitung der Blockliste. Gibt eine NEUE Liste zurück.
    - tag_config: Das neue, detaillierte Konfigurationsobjekt vom Frontend.
    - disable_comment_bg: Wenn True, werden Hintergrundfarben in Kommentarbereichen unterdrückt.
    """
    
    # 0. Erstelle Kommentar-Masken für alle pair-Blöcke (VOR dem Hinzufügen der Farben)
    if disable_comment_bg:
        for block in blocks:
            if isinstance(block, dict) and block.get('type') in ('pair', 'flow'):
                mask = create_comment_token_mask_for_block(block, blocks)
                block['comment_token_mask'] = mask
    
    # 1. Farben anwenden (wenn color_mode="COLOR")
    # Dieser Schritt fügt die Farbsymbole (#, +, §, $) basierend auf der tag_config hinzu.
    # Die Original-Tags bleiben für den nächsten Schritt erhalten.
    blocks_with_colors = blocks
    if color_mode == "COLOR" and tag_config:
        blocks_with_colors = _apply_colors_and_placements(blocks, tag_config, disable_comment_bg=disable_comment_bg)

    # 2. Tags filtern/entfernen (je nach tag_mode)
    # Dieser Schritt wird NACH dem Hinzufügen der Farben ausgeführt.
    sup_keep, sub_keep = None, None
    remove_all_tags_flag = (tag_mode == "NO_TAGS")
    translation_rules: Dict[str, Dict[str, Any]] = {}

    if tag_config:
        for rule_id, conf in tag_config.items():
            normalized_rule_id = _normalize_rule_id(rule_id)
            _maybe_register_translation_rule(translation_rules, normalized_rule_id, conf)

    if tag_mode == "TAGS" and tag_config:
        # WICHTIG: Starte mit ALLEN Tags, dann entferne die, die hide=true haben
        sup_keep = SUP_TAGS.copy()
        sub_keep = SUB_TAGS.copy()
        
        # Sortiere Regeln: Gruppen-Regeln zuerst, dann spezifische Regeln
        group_rules = []
        specific_rules = []
        
        for rule_id, conf in tag_config.items():
            normalized_rule_id = _normalize_rule_id(rule_id)
            if '_' in normalized_rule_id and normalized_rule_id.split('_', 1)[1]:
                specific_rules.append((rule_id, conf, normalized_rule_id))
            else:
                group_rules.append((rule_id, conf, normalized_rule_id))
        
        # Verarbeite zuerst Gruppen-Regeln, dann spezifische Regeln
        forbidden_tags_sup = set()
        forbidden_tags_sub = set()
        
        for rule_id, conf, normalized_rule_id in group_rules + specific_rules:
            tags_for_rule = _resolve_tags_for_rule(normalized_rule_id)
            if not tags_for_rule:
                continue
            
            is_specific_rule = (rule_id, conf, normalized_rule_id) in specific_rules
            
            # ROBUST: Prüfe hide (akzeptiere sowohl True als auch String "hide" für Kompatibilität)
            hide_value = conf.get('hide')
            should_hide = hide_value == True or hide_value == "hide" or hide_value == "true"
            
            if should_hide:
                # Entferne Tags aus sup_keep/sub_keep
                for tag in tags_for_rule:
                    normalized_tag = _normalize_tag_name(tag)
                    if tag in sup_keep:
                        sup_keep.discard(tag)
                        if not is_specific_rule:
                            forbidden_tags_sup.add(tag)
                            forbidden_tags_sup.add(normalized_tag)
                    if normalized_tag in sup_keep and normalized_tag != tag:
                        sup_keep.discard(normalized_tag)
                        if not is_specific_rule:
                            forbidden_tags_sup.add(normalized_tag)
                    if tag in sub_keep:
                        sub_keep.discard(tag)
                        if not is_specific_rule:
                            forbidden_tags_sub.add(tag)
                            forbidden_tags_sub.add(normalized_tag)
                    if normalized_tag in sub_keep and normalized_tag != tag:
                        sub_keep.discard(normalized_tag)
                        if not is_specific_rule:
                            forbidden_tags_sub.add(normalized_tag)
            else:
                # Tags hinzufügen, wenn hide=false (nur wenn nicht verboten)
                placement = conf.get('placement')
                if placement == 'sup':
                    for tag in tags_for_rule:
                        normalized_tag = _normalize_tag_name(tag)
                        if is_specific_rule or (tag not in forbidden_tags_sup and normalized_tag not in forbidden_tags_sup):
                            if tag in SUP_TAGS:
                                sup_keep.add(tag)
                            if tag in SUB_TAGS:
                                sub_keep.discard(tag)
                elif placement == 'sub':
                    for tag in tags_for_rule:
                        normalized_tag = _normalize_tag_name(tag)
                        if is_specific_rule or (tag not in forbidden_tags_sub and normalized_tag not in forbidden_tags_sub):
                            if tag in SUB_TAGS:
                                sub_keep.add(tag)
                            if tag in SUP_TAGS:
                                sup_keep.discard(tag)
                else:
                    for tag in tags_for_rule:
                        normalized_tag = _normalize_tag_name(tag)
                        if is_specific_rule or (tag not in forbidden_tags_sup and normalized_tag not in forbidden_tags_sup):
                            if tag in SUP_TAGS:
                                sup_keep.add(tag)
                        if is_specific_rule or (tag not in forbidden_tags_sub and normalized_tag not in forbidden_tags_sub):
                            if tag in SUB_TAGS:
                                sub_keep.add(tag)
        
        print(f"DEBUG apply (in apply()): Finale sup_keep={sorted(list(sup_keep))}, sub_keep={sorted(list(sub_keep))}")
    else:
        # Wenn tag_mode == "NO_TAGS" oder keine tag_config, alle Tags entfernen
        sup_keep = set()
        sub_keep = set()

    translation_rules_arg = translation_rules if translation_rules else None
    out: List[Dict[str, Any]] = []
    for b in blocks_with_colors:
        if isinstance(b, dict) and b.get('type') in ('pair', 'flow'):
            processed_block = _process_pair_block_for_tags(
                b,
                sup_keep=sup_keep,
                sub_keep=sub_keep,
                remove_all=remove_all_tags_flag,
                translation_rules=translation_rules_arg,
            )
            # NEU: Entferne Stephanus-Paginierungen aus Übersetzungszeilen, wenn Übersetzungen ausgeblendet sind
            processed_block = _hide_stephanus_in_translations(processed_block, translation_rules_arg)
            out.append(processed_block)
        else:
            out.append(b)

    # 3. Farbcodes für BLACK_WHITE-Modus entfernen
    # Dieser Schritt ist der letzte, um sicherzustellen, dass die Farben
    # auch dann korrekt hinzugefügt wurden, wenn die Tags danach entfernt werden.
    if color_mode == "BLACK_WHITE":
        final_blocks = []
        for b in out:
            if isinstance(b, dict) and b.get('type') in ('pair', 'flow'):
                final_blocks.append(_strip_colors_from_block(b))
            else:
                final_blocks.append(b)
        return final_blocks
        
    return out

# Hilfsfunktion zum Entfernen von Tags in einem Block
def _process_pair_block_for_tags(block: Dict[str, Any], *,
                                 sup_keep: Optional[set[str]],
                                 sub_keep: Optional[set[str]],
                                 remove_all: bool,
                                 translation_rules: Optional[Dict[str, Dict[str, Any]]] = None) -> Dict[str, Any]:
    source_tokens = block.get('gr_tokens', [])

    if translation_rules:
        hide_translation_flags = [
            _token_should_hide_translation(token, translation_rules)
            for token in source_tokens
        ]
    else:
        hide_translation_flags = [False] * len(source_tokens)
    def proc_tokens(seq: Iterable[str]) -> List[str]:
        result = []
        for tok in (seq or []):
            if tok:
                original = tok
                processed = _remove_selected_tags(tok, sup_keep=sup_keep, sub_keep=sub_keep, remove_all=remove_all)
                # DEBUG: Zeige, wenn ein Tag entfernt wurde
                if original != processed and ('(' in original or ')' in original):
                    print(f"DEBUG _process_pair_block_for_tags: Tag entfernt aus Token: '{original[:60]}...' → '{processed[:60]}...'")
                result.append(processed)
            else:
                result.append(tok)
        return result
    
    if 'gr_tokens' in block or 'de_tokens' in block:
        new_gr_tokens = proc_tokens(block.get('gr_tokens', []))
        new_de_tokens = proc_tokens(block.get('de_tokens', []))
        
        result = {
            **block,
            'gr_tokens': new_gr_tokens,
            'de_tokens': new_de_tokens,
        }
        if 'en_tokens' in block:
            result['en_tokens'] = proc_tokens(block.get('en_tokens', []))

        if translation_rules:
            for idx, should_hide in enumerate(hide_translation_flags):
                if not should_hide:
                    continue
                if idx < len(result['de_tokens']):
                    result['de_tokens'][idx] = ''
                if 'en_tokens' in result and idx < len(result['en_tokens']):
                    result['en_tokens'][idx] = ''
        
        # WICHTIG: Aktualisiere auch block['gr'] und block['de'], damit Renderer die bereinigten Strings verwenden
        # Rekonstruiere die Linerpräsentation, die Renderer ggf. benutzen:
        result['gr'] = _join_tokens_to_line(new_gr_tokens)
        result['de'] = _join_tokens_to_line(new_de_tokens)
        if 'en_tokens' in result:
            result['en'] = _join_tokens_to_line(result.get('en_tokens', []))
        
        return result
    return block

# Hilfsfunktion zum Entfernen von Stephanus-Paginierungen aus Tokens
def _remove_stephanus_from_token(token: str) -> str:
    """
    Entfernt Stephanus-Paginierungen (z.B. [543b], [546b]) aus einem Token.
    """
    if not token:
        return token
    # Entferne Stephanus-Paginierungen: [543b], [546b] etc.
    return RE_STEPHANUS.sub('', token).strip()

# Regex für Satzzeichen-Token (nur Satzzeichen, keine Wörter)
RE_PUNCTUATION_ONLY = re.compile(r'^[.,;:!?·…\s]+$')

def _is_punctuation_only_token(token: str) -> bool:
    """
    Prüft, ob ein Token nur aus Satzzeichen oder Stephanus-Paginierungen besteht.
    Beispiele: ".", "?", "!", "...", ". . .", "·", "[581b]", "[1251a]", "[5c]", "[25e]", etc.
    """
    if not token:
        return False
    token_stripped = token.strip()
    
    # Prüfe auf Stephanus-Paginierung wie [581b], [1251a], [5c], [25e]
    if RE_STEPHANUS.fullmatch(token_stripped):
        return True
    
    # Entferne Leerzeichen und prüfe, ob nur Satzzeichen übrig bleiben
    no_spaces = token_stripped.replace(' ', '').replace('\t', '').replace('\n', '').replace('\r', '')
    # Prüfe, ob nur Satzzeichen vorhanden sind (inkl. Ellipsis, Gedankenstrich, etc.)
    punct_chars = '.,;:!?·…–—()[]{}"\'"„«»‚''‹›'
    return bool(no_spaces) and all(c in punct_chars for c in no_spaces)

# Hilfsfunktion zum Verstecken von Übersetzungen basierend auf (HideTrans) Tag
def _hide_manual_translations_in_block(block: Dict[str, Any]) -> Dict[str, Any]:
    """
    Versteckt Übersetzungen für Tokens, die den (HideTrans) Tag haben.
    Dies ist unabhängig von der tag_config und funktioniert für manuelle Tags im Text.
    """
    if 'gr_tokens' not in block:
        return block
    
    source_tokens = block.get('gr_tokens', [])
    hide_flags = []
    
    for token in source_tokens:
        tags = _extract_tags(token)
        # Prüfe auf HideTrans (case-insensitive, da Nutzer verschiedene Schreibweisen verwenden könnten)
        should_hide = any(tag.lower() == TRANSLATION_HIDE_TAG.lower() for tag in tags)
        hide_flags.append(should_hide)
    
    result = {**block}
    
    # Verstecke Übersetzungen für markierte Tokens
    for idx, should_hide in enumerate(hide_flags):
        if not should_hide:
            continue
        if 'de_tokens' in result and idx < len(result['de_tokens']):
            result['de_tokens'][idx] = ''
        if 'en_tokens' in result and idx < len(result['en_tokens']):
            result['en_tokens'][idx] = ''
    
    return result

# NEU: Funktion zum Entfernen von Stephanus-Paginierungen aus Übersetzungszeilen
def _hide_stephanus_in_translations(block: Dict[str, Any], translation_rules: Optional[Dict[str, Dict[str, Any]]] = None) -> Dict[str, Any]:
    """
    Entfernt Stephanus-Paginierungen aus Übersetzungszeilen (DE, EN), wenn Übersetzungen ausgeblendet sind.
    Entfernt ALLE Stephanus-Paginierungen aus Übersetzungszeilen, wenn die entsprechenden Übersetzungen ausgeblendet sind.
    """
    if 'gr_tokens' not in block:
        return block
    
    source_tokens = block.get('gr_tokens', [])
    result = {**block}
    
    # Prüfe, ob ALLE Übersetzungen in diesem Block ausgeblendet sind (NoTrans PDF)
    # Nur dann sollen Stephanus-Paginierungen entfernt werden
    has_all_translations_hidden = True
    if translation_rules and source_tokens:
        for idx, gr_token in enumerate(source_tokens):
            if not _token_should_hide_translation(gr_token, translation_rules):
                has_all_translations_hidden = False
                break
    else:
        has_all_translations_hidden = False
    
    # Entferne Stephanus-Paginierungen aus DE-Tokens
    # ROBUST: Entferne ALLE Stephanus-Paginierungen aus Übersetzungszeilen, wenn irgendwelche Übersetzungen ausgeblendet sind
    if 'de_tokens' in result:
        de_tokens = result['de_tokens']
        for idx, token in enumerate(de_tokens):
            if not token:
                continue
            
            # Prüfe, ob die Übersetzung für dieses Token ausgeblendet ist
            should_hide_translation = False
            if translation_rules and idx < len(source_tokens):
                should_hide_translation = _token_should_hide_translation(source_tokens[idx], translation_rules)
            
            # Prüfe, ob Token eine Stephanus-Paginierung enthält ODER nur Satzzeichen ist
            token_stripped = token.strip()
            
            # WICHTIG: Entferne Interpunktion/Stephanus auch wenn nur EINE Übersetzung ausgeblendet ist
            # (nicht nur wenn ALLE ausgeblendet sind)
            # AUCH: Entferne trivial translations (nur Interpunktion/Stephanus) IMMER, auch wenn hide_translation nicht aktiv ist
            if should_hide_translation or has_all_translations_hidden:
                # Prüfe ob Übersetzung trivial ist (nur Interpunktion/Stephanus) - das ist die robusteste Methode
                if is_trivial_translation(token_stripped):
                    result['de_tokens'][idx] = ''
                    continue
                
                # Entferne Tokens, die nur aus Satzzeichen bestehen
                if _is_punctuation_only_token(token_stripped):
                    result['de_tokens'][idx] = ''
                    continue
                
                # Entferne Stephanus-Paginierungen
                if RE_STEPHANUS.search(token_stripped):
                    if RE_STEPHANUS.fullmatch(token_stripped):
                        # Token ist nur eine Stephanus-Paginierung → komplett entfernen
                        result['de_tokens'][idx] = ''
                    else:
                        # Token enthält Stephanus-Paginierung + anderen Text → nur Paginierung entfernen
                        cleaned = _remove_stephanus_from_token(token)
                        if not cleaned.strip() or is_trivial_translation(cleaned.strip()):
                            result['de_tokens'][idx] = ''
                        else:
                            result['de_tokens'][idx] = cleaned
            # AUCH wenn hide_translation NICHT aktiv ist: entferne trivial translations
            elif is_trivial_translation(token_stripped):
                result['de_tokens'][idx] = ''
                continue
    
    # Entferne Stephanus-Paginierungen aus EN-Tokens
    # ROBUST: Entferne ALLE Stephanus-Paginierungen aus Übersetzungszeilen, wenn irgendwelche Übersetzungen ausgeblendet sind
    if 'en_tokens' in result:
        en_tokens = result['en_tokens']
        for idx, token in enumerate(en_tokens):
            if not token:
                continue
            
            # Prüfe, ob die Übersetzung für dieses Token ausgeblendet ist
            should_hide_translation = False
            if translation_rules and idx < len(source_tokens):
                should_hide_translation = _token_should_hide_translation(source_tokens[idx], translation_rules)
            
            # Prüfe, ob Token eine Stephanus-Paginierung enthält ODER nur Satzzeichen ist
            token_stripped = token.strip()
            
            # WICHTIG: Entferne Interpunktion/Stephanus auch wenn nur EINE Übersetzung ausgeblendet ist
            # (nicht nur wenn ALLE ausgeblendet sind)
            # AUCH: Entferne trivial translations (nur Interpunktion/Stephanus) IMMER, auch wenn hide_translation nicht aktiv ist
            if should_hide_translation or has_all_translations_hidden:
                # Prüfe ob Übersetzung trivial ist (nur Interpunktion/Stephanus)
                if is_trivial_translation(token_stripped):
                    result['en_tokens'][idx] = ''
                    continue
                
                # Entferne Tokens, die nur aus Satzzeichen bestehen
                if _is_punctuation_only_token(token_stripped):
                    result['en_tokens'][idx] = ''
                    continue
                
                # Entferne Stephanus-Paginierungen
                if RE_STEPHANUS.search(token_stripped):
                    if RE_STEPHANUS.fullmatch(token_stripped):
                        # Token ist nur eine Stephanus-Paginierung → komplett entfernen
                        result['en_tokens'][idx] = ''
                    else:
                        # Token enthält Stephanus-Paginierung + anderen Text → nur Paginierung entfernen
                        cleaned = _remove_stephanus_from_token(token)
                        if not cleaned.strip() or _is_punctuation_only_token(cleaned.strip()):
                            result['en_tokens'][idx] = ''
                        else:
                            result['en_tokens'][idx] = cleaned
            # AUCH wenn hide_translation NICHT aktiv ist: entferne trivial translations
            elif is_trivial_translation(token_stripped):
                result['en_tokens'][idx] = ''
                continue
    
    return result

def _all_translations_hidden(block: Dict[str, Any]) -> bool:
    """
    Prüft, ob ALLE Übersetzungen in einem Block leer/versteckt sind.
    Gibt True zurück, wenn alle de_tokens (und en_tokens, falls vorhanden) leer sind.
    """
    if 'de_tokens' not in block:
        return False
    
    de_tokens = block.get('de_tokens', [])
    en_tokens = block.get('en_tokens', [])
    
    # Prüfe, ob alle deutschen Übersetzungen leer sind
    de_all_empty = all(not tok or tok.strip() == '' for tok in de_tokens)
    
    # Wenn en_tokens vorhanden, müssen auch diese leer sein
    if en_tokens:
        en_all_empty = all(not tok or tok.strip() == '' for tok in en_tokens)
        return de_all_empty and en_all_empty
    
    return de_all_empty

def remove_empty_translation_lines(blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Entfernt die Übersetzungszeilen aus Blöcken, wo ALLE Übersetzungen versteckt sind.
    Dies verhindert leere Zeilen im PDF, wenn der Nutzer alle Übersetzungen ausblendet.
    
    WICHTIG: Dies funktioniert nur für 'pair' und 'flow' Blöcke mit Tokens.
    WICHTIG: Wir setzen de_tokens/en_tokens auf leere Listen, statt sie zu entfernen,
             damit der Rendering-Code nicht abstürzt.
    """
    result = []
    for block in blocks:
        if isinstance(block, dict) and block.get('type') in ('pair', 'flow'):
            if _all_translations_hidden(block):
                # Setze Übersetzungszeilen auf leere Listen (nicht entfernen!)
                new_block = {**block}
                if 'de_tokens' in new_block:
                    new_block['de_tokens'] = []
                if 'en_tokens' in new_block:
                    new_block['en_tokens'] = []
                if 'de' in new_block:
                    new_block['de'] = ''
                if 'en' in new_block:
                    new_block['en'] = ''
                result.append(new_block)
            else:
                result.append(block)
        else:
            result.append(block)
    
    return result

def all_blocks_have_no_translations(blocks: List[Dict[str, Any]]) -> bool:
    """
    Prüft, ob ALLE Blöcke keine Übersetzungen haben.
    Gibt True zurück, wenn alle pair/flow Blöcke leere de_tokens/en_tokens haben.
    Dies wird verwendet, um den _NoTrans Tag zum Dateinamen hinzuzufügen.
    """
    for block in blocks:
        if isinstance(block, dict) and block.get('type') in ('pair', 'flow'):
            # Prüfe, ob dieser Block Übersetzungen hat
            de_tokens = block.get('de_tokens', [])
            en_tokens = block.get('en_tokens', [])
            
            # Wenn irgendein Token nicht leer ist, haben wir Übersetzungen
            if any(tok and tok.strip() for tok in de_tokens):
                return False
            if any(tok and tok.strip() for tok in en_tokens):
                return False
    
    # Alle Blöcke haben keine Übersetzungen
    return True

# Hilfsfunktion zum Entfernen von Farben in einem Block
def _strip_colors_from_block(block: Dict[str, Any]) -> Dict[str, Any]:
    def proc_tokens(seq: Iterable[str]) -> List[str]:
        return [_strip_all_colors(tok) for tok in (seq or [])]

    if 'gr_tokens' in block or 'de_tokens' in block:
        result = {
            **block,
            'gr_tokens': proc_tokens(block.get('gr_tokens', [])),
            'de_tokens': proc_tokens(block.get('de_tokens', [])),
        }
        # NEU: Auch en_tokens entfärben, falls vorhanden
        if 'en_tokens' in block:
            result['en_tokens'] = proc_tokens(block.get('en_tokens', []))
        return result
    return block

# ======= Komfort: Payload aus UI (Hidden JSON) verarbeiten =======
def apply_from_payload(blocks: List[Dict[str, Any]], payload: Dict[str, Any], *,
                       default_versmass_mode: VersmassMode = "NORMAL") -> List[Dict[str, Any]]:
    """
    Verarbeitet die Konfiguration aus dem Frontend.
    """
    tag_config = payload.get("tag_config", {})
    
    # 1. Farbmodus bestimmen
    color_mode = "BLACK_WHITE" if payload.get("color_mode") == "BlackWhite" else "COLOR"

    # 2. Tag-Modus bestimmen (vereinfacht)
    # Wenn alle Tags auf "hide" stehen, ist es NO_TAGS, ansonsten TAGS
    # Die Detail-Logik, welche Tags gezeigt werden, steckt jetzt in `apply`
    all_hidden = True
    if not tag_config:
        all_hidden = False
    else:
        # ROBUST: Prüfe hide (akzeptiere sowohl True als auch String "hide" für Kompatibilität)
        for conf in tag_config.values():
            hide_value = conf.get('hide')
            should_hide = hide_value == True or hide_value == "hide" or hide_value == "true"
            if not should_hide:
                all_hidden = False
                break
        
    tag_mode = "NO_TAGS" if all_hidden else "TAGS"
    
    # 3. Versmaß-Modus
    versmass_mode  = payload.get("versmass", default_versmass_mode)

    return apply(
        blocks,
        color_mode=color_mode,
        tag_mode=tag_mode,
        versmass_mode=versmass_mode,
        tag_config=tag_config,
    )

