#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
"""
shared/preprocess.py
--------------------
Vorverarbeitung der Blockstruktur vor dem Rendern.
"""
import re
import os
import string
import logging
from typing import List, Dict, Any, Iterable, Optional, Set, Tuple

# Reduce noisy DEBUG output from lower-level modules by default
logging.getLogger().setLevel(logging.INFO)

# Limit very noisy per-token debug lines
_TOKEN_DEBUG_LIMIT = 5

"""

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
STEHPANUS_RE = re.compile(r'^\s*(\[[0-9a-zA-Z]+\]|[0-9]+[a-z]?)\s*$')  # simple stephanus-like bracket forms

def is_only_punctuation_or_stephanus(s: str) -> bool:
    """
    Return True if the string s contains only punctuation characters
    (.,;:!?()[]-quotes etc.) or a stephanus-like pagination token.
    Used to hide translation lines that would be visually empty.
    """
    if s is None:
        return False
    t = s.strip()
    if not t:
        return True
    # stephanus page forms like [581b] or [5c]
    if STEHPANUS_RE.match(t):
        return True
    # if every char is punctuation or whitespace
    return all(ch in string.punctuation or ch.isspace() for ch in t)

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
    
    # Erweiterte Liste von Interpunktionszeichen und Sonderzeichen:
    # . , ; : ? ! - ( ) [ ] " ' / \ | … · • — – ‒ ― * + = < > « » ' ' " " „ " ‹ › ‐ ‑ ‧
    # Wenn nur diese Zeichen und Leerzeichen übrig bleiben -> trivial
    if re.fullmatch(r'^[\s\.\,\;\:\?\!\-\(\)\[\]\"\'\/\\\|…·•—–‒―\*\+=<>«»''""„"‹›‐‑‧]+$', t_no_speaker):
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

def discover_and_attach_comments(blocks: List[Dict[str,Any]]) -> List[Dict[str,Any]]:
    """
    Robustere Kommentar-Erkennung und -Zuordnung.
    WICHTIG: Diese Funktion DARF NICHT in eine Endlosschleife geraten!
    """
    import re
    import time
    
    # Log START mit Timeout-Protection
    logger = logging.getLogger(__name__)
    start_time = time.time()
    MAX_PROCESSING_TIME = 60  # Maximum 60 Sekunden für Kommentar-Verarbeitung
    
    logger.info("discover_and_attach_comments: START processing %d blocks", len(blocks))
    
    # KRITISCH: Defensive Prüfung - blocks MUSS eine Liste sein
    if not isinstance(blocks, list):
        logger.error("discover_and_attach_comments: blocks is not a list (type=%s), returning empty list", type(blocks))
        return []
    
    # KRITISCH: Leere oder sehr große Listen abfangen
    if len(blocks) == 0:
        logger.info("discover_and_attach_comments: empty blocks list, returning []")
        return []
    
    if len(blocks) > 50000:
        logger.warning("discover_and_attach_comments: HUGE blocks list (%d blocks), may be slow!", len(blocks))
    
    comment_full_re = re.compile(r'^\s*\((\d+(?:-\d+)?)k\)\s*(.+)$', re.UNICODE)
    comment_inline_re = re.compile(r'\((\d+(?:-\d+)?)k\)\s*([^()]+)', re.UNICODE)

    # Schritt 1: Erstelle ein Mapping von Zeilennummern zu Block-Indices
    pair_to_block = {}
    
    for idx, block in enumerate(blocks):
        # Timeout-Check alle 1000 Blöcke
        if idx > 0 and idx % 1000 == 0:
            elapsed = time.time() - start_time
            if elapsed > MAX_PROCESSING_TIME:
                logger.error("discover_and_attach_comments: TIMEOUT after %.1f seconds at block %d/%d", elapsed, idx, len(blocks))
                return blocks  # Gebe unveränderte Blöcke zurück
            
            if idx % 5000 == 0:
                logger.debug("discover_and_attach_comments: processed %d/%d blocks (%.1fs elapsed)", idx, len(blocks), elapsed)
        
        if not isinstance(block, dict):
            continue
        
        block_type = block.get('type')
        if block_type not in ('pair', 'flow'):
            continue
        
        # Versuche Zeilennummer zu extrahieren
        line_num = block.get('line_num') or block.get('label')
        if not line_num:
            continue
        
        # Normalisiere Zeilennummer (entferne Buchstaben wie "a", "b")
        base_num = re.sub(r'[a-z]', '', str(line_num).lower())
        try:
            base_num = int(base_num)
            pair_to_block[base_num] = idx
        except (ValueError, TypeError):
            continue
    
    logger.debug("discover_and_attach_comments: built pair_to_block mapping with %d entries", len(pair_to_block))
    
    comments_found = 0
    result_blocks = []
    
    # Schritt 2: Durchlaufe alle Blöcke und extrahiere Kommentare
    for idx, block in enumerate(blocks):
        # Timeout-Check alle 1000 Blöcke
        if idx > 0 and idx % 1000 == 0:
            elapsed = time.time() - start_time
            if elapsed > MAX_PROCESSING_TIME:
                logger.error("discover_and_attach_comments: TIMEOUT after %.1f seconds at block %d/%d", elapsed, idx, len(blocks))
                return blocks  # Gebe unveränderte Blöcke zurück
        
        if not isinstance(block, dict):
            result_blocks.append(block)
            continue
        
        block_type = block.get('type')
        
        # Kommentare in pair/flow Blöcken extrahieren
        if block_type in ('pair', 'flow'):
            # Sammle Kommentare aus diesem Block
            inline_comments = []
            
            # Prüfe gr_tokens auf Kommentare
            gr_tokens = block.get('gr_tokens', [])
            if isinstance(gr_tokens, list):
                for token in gr_tokens:
                    if not token or not isinstance(token, str):
                        continue
                    
                    # Inline-Kommentare: "(123k) Text" innerhalb eines Tokens
                    match = comment_inline_re.search(token)
                    if match:
                        line_ref = match.group(1)
                        comment_text = match.group(2).strip()
                        
                        if comment_text:
                            # Erstelle einen neuen Kommentar-Block
                            comment_block = {
                                'type': 'comment',
                                'line_num': line_ref,
                                'content': comment_text,
                                'original_line': f"({line_ref}k) {comment_text}"
                            }
                            inline_comments.append(comment_block)
                            comments_found += 1
            
            # KRITISCH: Füge pair/flow-Block ZUERST hinzu, DANN die Kommentare!
            result_blocks.append(block)
            
            # Füge gesammelte Inline-Kommentare NACH dem Block hinzu
            if inline_comments:
                result_blocks.extend(inline_comments)
        
        # Vollständige Kommentar-Zeilen: "(123k) Text"
        elif block_type == 'comment':
            original_line = block.get('original_line', '')
            if original_line:
                match = comment_full_re.match(original_line)
                if match:
                    line_ref = match.group(1)
                    comment_text = match.group(2).strip()
                    
                    # Aktualisiere den Block mit extrahierten Daten
                    block['line_num'] = line_ref
                    block['content'] = comment_text
                    comments_found += 1
            
            result_blocks.append(block)
        
        else:
            result_blocks.append(block)
    
    # Log ENDE mit Statistiken
    elapsed = time.time() - start_time
    logger.info("discover_and_attach_comments: END - found=%d comment blocks, total_blocks=%d (%.1fs)", 
                comments_found, len(result_blocks), elapsed)
    
    return result_blocks

# ======= Hilfen: Token-Processing =======
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
    # ABER: Kon, Pt und Prp werden NUR als Wortart erkannt, wenn sie das EINZIGE Tag sind
    # (z.B. tribuendoqueAblKonGer soll als Verb erkannt werden, nicht als Kon)
    # (z.B. obtinendineGPtGer soll als Verb erkannt werden, nicht als Pt)
    # (z.B. MīlesneNPt soll als Nomen erkannt werden, nicht als Pt)
    # (z.B. ἐν(Prp)(D) soll als Präposition erkannt werden, nicht als Nomen)
    
    # Spezialfall: Wenn Kon, Pt oder Prp vorhanden ist UND andere Tags, ignoriere sie komplett
    ignorable_tags = {'Kon', 'Pt', 'Prp'}  # Tags, die nur als Wortart gelten, wenn sie alleine stehen
    has_ignorable = bool(token_tags.intersection(ignorable_tags))
    
    if has_ignorable and len(token_tags) > 1:
        # Prüfe andere Tags (ohne Kon/Pt/Prp) in WORTART_IDENTIFIER_TAGS
        for tag, wortart in WORTART_IDENTIFIER_TAGS.items():
            if tag not in ignorable_tags and tag in token_tags:
                return wortart, token_tags
        # Kein anderer Identifier gefunden, fahre mit komplexer Logik fort
        # (z.B. obtinendineGPtGer hat G+Ger, die nicht in WORTART_IDENTIFIER_TAGS sind)
    elif not has_ignorable:
        # Normale Prüfung (weder Kon noch Pt noch Prp vorhanden)
        for tag, wortart in WORTART_IDENTIFIER_TAGS.items():
            if tag in token_tags:
                return wortart, token_tags
    # Wenn Kon, Pt oder Prp das EINZIGE Tag ist, wird es als 'kon', 'pt' oder 'prp' erkannt

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
        # Nomen: nur Kasus-Tag(s), AUCH mit Kon/Pt/Du/Prp erlaubt (z.B. sollertiaqueAblKon, MīlesneNPt, ἵππωDuN)
        # Entferne Kon, Pt, Du und Prp aus der Prüfung (Du = Dual, optional bei Nomen)
        tags_ohne_ignorable = token_tags - {'Kon', 'Pt', 'Du', 'Prp'}
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
                # DEBUG: Reduziert - nur bei ersten 5 Tags ausgeben
                # print(f"DEBUG _remove_selected_tags: Entferne SUB-Tag '{tag}' (normalisiert: '{tag_normalized}') - tag in sub_keep: {tag in sub_keep}, normalized in sub_keep: {tag_normalized in sub_keep}, sub_keep={sorted(list(sub_keep))[:10]}...")
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

def is_translation_empty_or_punct(text: str) -> bool:
    """
    Prüft, ob eine Übersetzung leer ist oder nur Satzzeichen enthält.
    Wird verwendet, um zu entscheiden, ob Übersetzungen ausgeblendet werden sollen.
    """
    if not text or not text.strip():
        return True
    # Entferne Whitespace und alle Satzzeichen / Sonderzeichen
    cleaned = text.strip()
    # Erweiterte Liste von Satzzeichen und Sonderzeichen, die als "leer" gelten
    punct_chars = ['.', ',', ';', ':', '!', '?', '…', '·', '‧', '—', '–', '‒', '―', '-', 
                   '*', '+', '=', '<', '>', '(', ')', '[', ']', '{', '}', '"', "'", 
                   '«', '»', ''', ''', '"', '"', '„', '"', '‹', '›', '/', '\\', '|', '‐', '‑']
    for char in punct_chars:
        cleaned = cleaned.replace(char, '')
    return not cleaned

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
        # WICHTIG: Kommentar-Blöcke und andere nicht-pair/flow Blöcke unverändert weitergeben
        if not isinstance(block, dict) or block.get('type') not in ('pair', 'flow'):
            new_blocks.append(block)
            continue
        
        # WICHTIG: pair/flow Blöcke verarbeiten
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
            
            # WICHTIG: Erkenne HideTags/HideTrans Flags direkt im Token-String (vor Tag-Extraktion)
            # Prüfe sowohl im Token-String als auch in extrahierten Tags
            hide_tags_flag = (TAG_HIDE_TAGS in token or '(HideTags)' in token or '(hidetags)' in token) or (TAG_HIDE_TAGS in orig_tags or 'hidetags' in (t.lower() for t in orig_tags))
            hide_trans_flag = (TRANSLATION_HIDE_TAG in token or '(HideTrans)' in token or '(hidetrans)' in token) or (TRANSLATION_HIDE_TAG in orig_tags or 'hidetrans' in (t.lower() for t in orig_tags))
            
            # Entferne HideTags/HideTrans Marker aus dem Token-String, damit sie nicht im PDF erscheinen
            cleaned_token = token
            if hide_tags_flag:
                cleaned_token = cleaned_token.replace(f'({TAG_HIDE_TAGS})', '')
                cleaned_token = cleaned_token.replace('(HideTags)', '')
                cleaned_token = cleaned_token.replace('(hidetags)', '')
            if hide_trans_flag:
                cleaned_token = cleaned_token.replace(f'({TRANSLATION_HIDE_TAG})', '')
                cleaned_token = cleaned_token.replace('(HideTrans)', '')
                cleaned_token = cleaned_token.replace('(hidetrans)', '')
            # Aktualisiere token in der Liste
            new_gr_tokens[i] = cleaned_token
            
            # Aktualisiere orig_tags nach Entfernung der Hide-Marker
            orig_tags_clean = orig_tags - {TAG_HIDE_TAGS, TRANSLATION_HIDE_TAG}
            orig_tags_clean = orig_tags_clean - {t for t in orig_tags if t.lower() in ('hidetags', 'hidetrans')}
            
            # Speichere die Original-Tags (ohne Hide-Marker) und Flags in token_meta
            if i < len(token_meta):
                token_meta[i]['orig_tags'] = list(orig_tags_clean)
                token_meta[i].setdefault('flags', {})
                token_meta[i]['flags']['hide_tags'] = hide_tags_flag
                token_meta[i]['flags']['hide_trans'] = hide_trans_flag
            else:
                # sollte nicht passieren, aber sicherstellen
                token_meta.append({
                    'orig_tags': list(orig_tags_clean),
                    'flags': {
                        'hide_tags': hide_tags_flag,
                        'hide_trans': hide_trans_flag
                    }
                })
            
            # Verwende cleaned_token für weitere Verarbeitung
            token = cleaned_token
            
            # If disable_comment_bg and this token belongs to comment → skip bg coloring
            if disable_comment_bg and new_block.get("comment_token_mask", [False])[i]:
                # Still keep other color metadata (e.g. token color), but skip background fill
                # We still may set token_meta[i]['color'] etc. if needed
                continue
            
            # WICHTIG: Manuelle Farbsymbole im griechischen Token extrahieren
            # Diese sollen ALLE Übersetzungen färben UND in BlackWhite-PDFs sichtbar sein!
            manual_color_symbol = None
            for sym in COLOR_SYMBOLS:
                if sym in token:
                    manual_color_symbol = sym
                    break
            
            # Wenn manuelles Symbol gefunden: Zu allen Übersetzungen hinzufügen und in token_meta speichern
            if manual_color_symbol:
                # Symbol zu deutschem Token hinzufügen (wenn noch nicht vorhanden)
                if i < len(de_tokens):
                    de_tok = de_tokens[i]
                    if de_tok and not any(c in de_tok for c in COLOR_SYMBOLS):
                        de_match = RE_WORD_START.search(de_tok)
                        if de_match:
                            new_de_tokens[i] = de_tok[:de_match.start(2)] + manual_color_symbol + de_tok[de_match.start(2):]
                        else:
                            new_de_tokens[i] = manual_color_symbol + de_tok
                
                # Symbol zu englischem Token hinzufügen (wenn noch nicht vorhanden)
                if i < len(new_en_tokens):
                    en_tok = en_tokens[i]
                    if en_tok and not any(c in en_tok for c in COLOR_SYMBOLS):
                        en_match = RE_WORD_START.search(en_tok)
                        if en_match:
                            new_en_tokens[i] = en_tok[:en_match.start(2)] + manual_color_symbol + en_tok[en_match.start(2):]
                        else:
                            new_en_tokens[i] = manual_color_symbol + en_tok
                
                # WICHTIG: Symbol in token_meta speichern mit FORCE_COLOR Flag!
                # Dies signalisiert, dass diese Farbe AUCH in BlackWhite-PDFs gezeigt werden soll!
                if i < len(token_meta):
                    token_meta[i]['color_symbol'] = manual_color_symbol
                    token_meta[i]['force_color'] = True  # Manuelle Farbe überschreibt BlackWhite-Modus!
                else:
                    while len(token_meta) <= i:
                        token_meta.append({})
                    token_meta[i]['color_symbol'] = manual_color_symbol
                    token_meta[i]['force_color'] = True
                
                # Fahre mit nächstem Token fort (keine automatische Farbzuweisung mehr nötig)
                continue

            # WICHTIG: Für Farbberechnung HideTags/HideTrans entfernen, damit sie die Farbzuordnung nicht beeinflussen
            tags_for_color = orig_tags - {TAG_HIDE_TAGS, TRANSLATION_HIDE_TAG}
            tags_for_color = tags_for_color - {t for t in orig_tags if t.lower() in ('hidetags', 'hidetrans')}
            token_tags = tags_for_color
            
            if not token_tags:
                continue
            
            # Bestimme Wortart und relevante Tags BASIEREND AUF TAGS OHNE HideTags/HideTrans
            wortart, relevant_tags = _get_wortart_and_relevant_tags(token_tags)
            if not wortart:
                continue
            
            # Speichere Wortart in token_meta für spätere Verwendung
            if i < len(token_meta):
                token_meta[i]['wortart'] = wortart
            
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
            computed_color = None
            computed_symbol = None
            if best_rule_config and 'color' in best_rule_config:
                color = best_rule_config['color']
                computed_color = color  # Speichere die berechnete Farbe
                if color in COLOR_MAP:
                    symbol = COLOR_MAP[color]
                    computed_symbol = symbol
                    
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
            
            # WICHTIG: Speichere computed_color und computed_symbol in token_meta, damit Renderer sie auch nach Tag-Entfernung verwenden kann
            # preserve color chosen by apply_colors so later tag removal does not wipe it
            if i < len(token_meta):
                if computed_color:
                    token_meta[i]['computed_color'] = computed_color
                    token_meta[i]['color'] = computed_color  # Also store as 'color' for compatibility
                if computed_symbol:
                    token_meta[i]['color_symbol'] = computed_symbol
            else:
                # fallback - erweitern
                while len(token_meta) <= i:
                    token_meta.append({})
                if computed_color:
                    token_meta[i]['computed_color'] = computed_color
                    token_meta[i]['color'] = computed_color  # Also store as 'color' for compatibility
                if computed_symbol:
                    token_meta[i]['color_symbol'] = computed_symbol
        
        new_block['gr_tokens'] = new_gr_tokens
        new_block['de_tokens'] = new_de_tokens
        if new_en_tokens:  # NEU: Englische Tokens nur setzen, wenn vorhanden
            new_block['en_tokens'] = new_en_tokens
        new_blocks.append(new_block)
    
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
    """
    DEFENSIVE LOGIK (konsistent mit Tag-Ausblendung):
    Übersetzung wird NUR ausgeblendet wenn ALLE Tags des Tokens auf "hideTranslation" stehen.
    Solange mindestens EIN Tag noch sichtbar sein will → Übersetzung bleibt!
    
    Beispiel:
      Token: Sorōrem(Adj)(A)
      Config: 'adj' auf hideTranslation, 'adj_A' NICHT
      → Übersetzung bleibt, weil (A) noch sichtbar sein will!
    """
    if not token or not translation_rules:
        return False

    tags = _extract_tags(token)
    # Prüfe zuerst auf HideTrans-Tag (explizites Flag im Token selbst)
    if TRANSLATION_HIDE_TAG in tags:
        return True
    
    # Keine Tags? → Übersetzung zeigen
    if not tags:
        return False
    
    # WICHTIG: Verwende ORIGINALE Tags (nicht normalisiert) für Wortart-Erkennung
    original_tags = set(tags)
    wortart, _ = _get_wortart_and_relevant_tags(original_tags)
    
    # Sammle ALLE Tags die auf "hideTranslation" stehen
    tags_that_want_to_hide = set()
    
    # 1. Prüfe wortart-spezifische Regeln (z.B. 'adjektiv', 'nomen')
    if wortart:
        wortart_key = wortart.lower()
        entry = translation_rules.get(wortart_key)
        if entry:
            # Wenn "all" gesetzt ist: ALLE Tags dieser Wortart wollen ausblenden
            if entry.get("all"):
                # Füge alle originalen Tags hinzu (normalisiert)
                for orig_tag in original_tags:
                    parts = [p for p in orig_tag.split('/') if p]
                    for part in parts:
                        tags_that_want_to_hide.add(_normalize_tag_name(part))
            else:
                # Nur spezifische Tags dieser Wortart wollen ausblenden
                entry_tags = entry.get("tags", set())
                if entry_tags:
                    normalized_entry_tags = {_normalize_tag_name(t) for t in entry_tags}
                    tags_that_want_to_hide.update(normalized_entry_tags)
    
    # 2. Prüfe globale Regeln (z.B. '_global')
    global_entry = translation_rules.get(TRANSLATION_HIDE_GLOBAL)
    if global_entry:
        if global_entry.get("all"):
            # Alle Tags wollen ausblenden
            for orig_tag in original_tags:
                parts = [p for p in orig_tag.split('/') if p]
                for part in parts:
                    tags_that_want_to_hide.add(_normalize_tag_name(part))
        else:
            entry_tags = global_entry.get("tags", set())
            if entry_tags:
                normalized_entry_tags = {_normalize_tag_name(t) for t in entry_tags}
                tags_that_want_to_hide.update(normalized_entry_tags)
    
    # 3. DEFENSIVE PRÜFUNG: Gibt es mindestens EIN Tag das NICHT ausgeblendet werden will?
    for orig_tag in original_tags:
        parts = [p for p in orig_tag.split('/') if p]
        for part in parts:
            normalized_part = _normalize_tag_name(part)
            # Wenn dieses Tag NICHT in der "hide"-Liste ist → Übersetzung bleibt!
            if normalized_part not in tags_that_want_to_hide:
                return False  # Mindestens ein Tag will sichtbar bleiben → Übersetzung zeigen!
    
    # Alle Tags wollen ausblenden → Übersetzung ausblenden
    return True

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
    """
    Registriert eine Regel für Übersetzungs-Ausblendung.
    
    WICHTIG: Konsistent mit Tag-Visibility-Logik:
    - Gruppenanführer MIT eigenem Tag (Adj, Art, Pr): Nur das Tag selbst registrieren
    - Gruppenanführer OHNE eigenem Tag (Nomen, Verb): Nichts (Subtags via spezifische Regeln)
    """
    if not normalized_rule_id:
        return
    
    if '_' in normalized_rule_id:
        # Spezifische Regel: z.B. 'adj_A' -> wortart='adj', tag='A'
        wordart, tag = normalized_rule_id.split('_', 1)
    else:
        # Gruppen-Regel: z.B. 'adj' -> wortart='adj', tag=None
        wordart, tag = normalized_rule_id, None

    normalized_wordart = wordart.lower()
    
    # WICHTIG: Normalisiere Wortart-Key zu voller Form (wie bei Tag-Visibility)
    # 'adj' → 'adjektiv', 'art' → 'artikel', 'pr' → 'pronomen', etc.
    wordart_capitalized = wordart.capitalize()
    if wordart_capitalized in WORTART_IDENTIFIER_TAGS:
        # Map z.B. 'adj' → 'adjektiv'
        normalized_wordart = WORTART_IDENTIFIER_TAGS[wordart_capitalized]
    
    # Prüfe ob normalisierte Wortart bekannt ist
    if normalized_wordart not in RULE_TAG_MAP and normalized_wordart not in HIERARCHIE:
        # Unbekannte Wortart → global
        normalized_tag = _normalize_tag_name(normalized_rule_id)
        entry = rules.setdefault(TRANSLATION_HIDE_GLOBAL, {"all": False, "tags": set()})
        if normalized_tag:
            entry["tags"].add(normalized_tag)
        return

    entry = rules.setdefault(normalized_wordart, {"all": False, "tags": set()})
    
    if tag:
        # Spezifische Regel (z.B. 'adj_A') -> füge nur dieses Tag hinzu
        entry["tags"].add(_normalize_tag_name(tag))
    else:
        # Gruppen-Regel (z.B. 'adj') - DEFENSIVE LOGIK:
        # Prüfe ob wordart ein Tag ist (Adj, Art, Pr) oder nur organizational (Nomen, Verb)
        rid_upper = wordart if wordart in SUP_TAGS or wordart in SUB_TAGS else wordart.capitalize()
        is_tag_itself = rid_upper in SUP_TAGS or rid_upper in SUB_TAGS
        
        if is_tag_itself:
            # Gruppenanführer MIT eigenem Tag (z.B. "Adj", "Art", "Pr")
            # → Nur dieses Tag registrieren, NICHT alle Subtags
            entry["tags"].add(rid_upper)
        else:
            # Gruppenanführer OHNE eigenem Tag (z.B. "nomen", "verb")
            # → Setze "all" flag (bedeutet: alle Subtags dieser Wortart)
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

def apply_tag_visibility(blocks: List[Dict[str, Any]], tag_config: Optional[Dict[str, Any]], 
                        hidden_tags_by_wortart: Optional[Dict[str, Set[str]]] = None) -> List[Dict[str, Any]]:
    """
    Filtert Tags basierend auf den 'hide' und 'placement' Regeln in tag_config.
    WICHTIG: Markiert auch, welche Tags entfernt wurden, damit Poesie_Code.py die Breite korrekt berechnen kann.
    """
    import copy
    blocks_copy = copy.deepcopy(blocks)
    
    # Schritt 1: Bestimme globale und wortart-spezifische sup_keep / sub_keep
    global_sup_keep = set(SUP_TAGS)
    global_sub_keep = set(SUB_TAGS)
    
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
                    # Spezifische Regel: z.B. 'nomen_N' oder 'adj_A'
                    parts = rid.split('_', 1)
                    wortart_key = parts[0].lower()
                    tag = parts[1]
                    
                    # Normalisiere wortart_key zur vollen Form BEVOR wir prüfen
                    # 'adj' → 'adjektiv', 'art' → 'artikel', etc.
                    wortart_key_capitalized = wortart_key.capitalize()
                    if wortart_key_capitalized in WORTART_IDENTIFIER_TAGS:
                        # Map z.B. 'adj' → 'adjektiv'
                        normalized_wortart_key = WORTART_IDENTIFIER_TAGS[wortart_key_capitalized]
                    else:
                        # Keine Abkürzung, nutze direkt (z.B. 'nomen', 'verb', 'partizip')
                        normalized_wortart_key = wortart_key
                    
                    # Jetzt prüfen ob diese Wortart bekannt ist
                    if normalized_wortart_key not in RULE_TAG_MAP and normalized_wortart_key not in HIERARCHIE:
                        # Unbekannte Wortart, überspringe diese Regel
                        continue
                    
                    if tag in SUP_TAGS or tag in SUB_TAGS:
                        # Füge das Tag zur normalisierten Wortart hinzu
                        if normalized_wortart_key not in hidden_tags_by_wortart:
                            hidden_tags_by_wortart[normalized_wortart_key] = set()
                        hidden_tags_by_wortart[normalized_wortart_key].add(tag)
                else:
                    # Gruppen-Regel: z.B. 'adj', 'adjektiv', 'nomen', 'verb', 'artikel', etc.
                    # WICHTIG: Unterscheidung zwischen zwei Arten von Gruppenanführern:
                    #   1) MIT eigenem Tag (Adj, Art, Pr, Adv) → nur das Tag selbst ausblenden
                    #   2) OHNE eigenem Tag (Nomen, Verb, Partizip) → nichts (Subtags via spezifische Regeln)
                    
                    # WICHTIG: UI schickt volle Wortart-Namen (z.B. "adjektiv", "pronomen")
                    # Wir müssen daraus das Tag-Kürzel extrahieren (z.B. "Adj", "Pr")
                    # Reverse-Lookup in WORTART_IDENTIFIER_TAGS: 'Adj' -> 'adjektiv'
                    tag_code_for_rid = None
                    rid_lower = rid.lower()
                    for tag, wortart_name in WORTART_IDENTIFIER_TAGS.items():
                        if wortart_name == rid_lower:
                            tag_code_for_rid = tag
                            break
                    
                    # Fallback: Prüfe ob rid selbst ein Tag ist (z.B. "Adj", "Art", "Pr")
                    if not tag_code_for_rid:
                        rid_upper = rid if rid in SUP_TAGS or rid in SUB_TAGS else rid.capitalize()
                        if rid_upper in SUP_TAGS or rid_upper in SUB_TAGS:
                            tag_code_for_rid = rid_upper
                    
                    is_tag_itself = tag_code_for_rid is not None
                    
                    if is_tag_itself:
                        # Gruppenanführer MIT eigenem Tag (z.B. "Adj", "Art", "Pr")
                        # → Nur das Gruppen-Tag selbst ausblenden, NICHT die Subtags (N, G, D, A)
                        # Der User kann jeden Subtag individuell steuern (adj_N, adj_G, etc.)
                        
                        # WICHTIG: Normalisiere den Key zur vollen Wortart-Form, damit Lookup funktioniert
                        # 'adj' → 'adjektiv', 'art' → 'artikel', 'pr' → 'pronomen', etc.
                        # Die Wortart-Funktion gibt 'adjektiv' zurück, nicht 'adj'!
                        wortart_key = WORTART_IDENTIFIER_TAGS.get(tag_code_for_rid)
                        if not wortart_key:
                            # Fallback: nutze rid.lower() direkt (z.B. 'prp', 'kon', 'pt', 'ij')
                            wortart_key = rid_lower
                        
                        if wortart_key not in hidden_tags_by_wortart:
                            hidden_tags_by_wortart[wortart_key] = set()
                        hidden_tags_by_wortart[wortart_key].add(tag_code_for_rid)
                    else:
                        # Gruppenanführer OHNE eigenem Tag (z.B. "nomen", "verb", "partizip")
                        # → Nichts hinzufügen! Diese sind nur UI-Convenience zum schnellen Markieren
                        # Die einzelnen Subtags (nomen_N, nomen_G, etc.) werden über spezifische Regeln behandelt
                        pass
        
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
        # WICHTIG: Verwende setdefault nur wenn token_meta nicht existiert, sonst behalte die bestehende token_meta
        # Dies stellt sicher, dass color_symbol von apply_colors erhalten bleibt
        if "token_meta" not in block:
            block["token_meta"] = [{} for _ in gr_tokens]
        token_meta = block["token_meta"]
        # Stelle sicher, dass token_meta die richtige Länge hat
        while len(token_meta) < len(gr_tokens):
            token_meta.append({})
        
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
                # WICHTIG: Prüfe per-token HideTrans Flag in token_meta (für einzelne Tokens ohne Gruppenanführer)
                hide_trans_from_flag = False
                if idx < len(token_meta):
                    hide_trans_from_flag = bool(token_meta[idx].get('flags', {}).get('hide_trans'))
                
                # WICHTIG: ERGÄNZENDE Logik - beide Bedingungen werden geprüft (OR)
                # Wenn EINE der beiden Bedingungen erfüllt ist, wird die Übersetzung ausgeblendet
                hide_trans_from_table = _token_should_hide_translation(gr_token, translation_rules)
                
                # Entweder Flag ODER Tabellen-Regel -> beide wirksam
                if hide_trans_from_flag or hide_trans_from_table:
                    # Entferne Übersetzung, aber prüfe auch ob sie trivial ist (nur Interpunktion/Stephanus)
                    # WICHTIG: Wenn Übersetzung trivial ist, entferne sie auch wenn hide_translation nicht aktiv ist
                    if idx < len(de_tokens):
                        de_text = de_tokens[idx].strip() if isinstance(de_tokens[idx], str) else ''
                        # Wenn Übersetzung trivial ist (nur Interpunktion/Stephanus), entferne sie komplett
                        if is_trivial_translation(de_text):
                            de_tokens[idx] = ''
                        else:
                            # Ansonsten: entferne nur wenn hide_translation aktiv ist (was hier der Fall ist, da wir in diesem if-Block sind)
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
            # Prüfe auch Flags in token_meta
            hide_tags_flag = False
            if i < len(token_meta):
                hide_tags_flag = bool(token_meta[i].get('flags', {}).get('hide_tags'))
            
            if TAG_HIDE_TAGS.lower() in original_tags_normalized or hide_tags_flag:
                # Remove all tag groups like '(Adj)(G)' etc. but keep punctuation and COLOR SYMBOLS
                # WICHTIG: COLOR_SYMBOLS (#, +, -, §, $) müssen erhalten bleiben!
                cleaned = tok
                # Entferne alle Tag-Klammern (Parenthesen-Gruppen), aber behalte Farbcodes
                cleaned = RE_PAREN_TAG.sub('', cleaned)
                # Entferne auch HideTags/HideTrans selbst aus dem Token
                cleaned = cleaned.replace(f'({TAG_HIDE_TAGS})', '').replace(f'({TRANSLATION_HIDE_TAG})', '')
                cleaned = re.sub(r'\([Hh]ide[Tt]ags\)', '', cleaned)
                cleaned = re.sub(r'\([Hh]ide[Tt]rans\)', '', cleaned)
                # Debug output
                if bi < 2 and i < 5:
                    print(f"DEBUG apply_tag_visibility: Block {bi} Token {i}: HideTags detected, removed all tags, orig_tags={sorted(list(orig_tags))[:8]}, computed_color={token_meta[i].get('computed_color') if i < len(token_meta) else None}")
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
            
            # WICHTIG: ERGÄNZENDE Logik - Tabellen-Einstellungen werden mit HideTags-Flag kombiniert
            # Wenn HideTags Flag gesetzt ist, werden alle Tags entfernt (schon oben behandelt)
            # Hier behandeln wir nur die wortart-spezifischen Tag-Einstellungen aus der Tabelle
            tags_to_hide_from_table = set()
            if hidden_tags_by_wortart and wortart:
                tags_to_hide_from_table = set(hidden_tags_by_wortart.get(wortart.lower(), []))
            
            # compute intersection: remove only tags actually present on token (orig tags)
            # WICHTIG: Nur Tags entfernen, die tatsächlich auf dem Token vorhanden sind
            # NEU: Normalisiere auch die Gruppenanführer-Tags (Adj -> adjektiv, Pr -> pronomen, Art -> artikel)
            # damit sie korrekt gefunden und entfernt werden können
            tags_to_remove = set()
            if tags_to_hide_from_table:
                for tag_to_hide in tags_to_hide_from_table:
                    # Prüfe ob das Tag direkt vorhanden ist (z.B. 'N', 'G', 'Adj')
                    if tag_to_hide in orig_tags:
                        tags_to_remove.add(tag_to_hide)
                    
                    # ZUSÄTZLICH: Prüfe auch alle orig_tags einzeln
                    # (für Gruppenanführer wie Adj, Art, Pr die in tags_to_hide_from_table sein können)
                    # WICHTIG: Dies fängt Fälle ab wo tag_to_hide z.B. 'Adj' ist und orig_tags {'Adj', 'N'} hat
                    # → 'Adj' soll entfernt werden!
                    if tag_to_hide in {'Adj', 'Art', 'Pr', 'Adv', 'Prp', 'Kon', 'Pt', 'ij'}:
                        # Gruppenanführer-Tag: entferne es wenn es in orig_tags ist
                        if tag_to_hide in orig_tags:
                            tags_to_remove.add(tag_to_hide)
            
            # NEU: Enklitische Tags-Logik
            # Wenn bei einer Wortart ALLE Tags entfernt werden sollen (z.B. bei Nomen alle Kasus),
            # sollen auch enklitische Partikel (Pt), Konjunktionen (Kon) und Präpositionen (Prp) entfernt werden
            enclitic_tags = {'Pt', 'Kon', 'Prp'}
            wortart_is_completely_tagfree = False
            
            if wortart and tags_to_hide_from_table:
                # Prüfe ob alle möglichen Tags dieser Wortart entfernt werden sollen
                if wortart.lower() in ['nomen', 'adjektiv', 'partizip']:
                    # Bei Nomen/Adjektiv/Partizip: wenn alle Kasus entfernt werden
                    all_kasus = set(KASUS_TAGS)
                    if all_kasus.issubset(tags_to_hide_from_table):
                        wortart_is_completely_tagfree = True
                elif wortart.lower() == 'verb':
                    # Bei Verben: wenn alle Tempora/Modi entfernt werden
                    all_verb_tags = set(TEMPUS_TAGS) | set(MODUS_TAGS) | set(LATEINISCHE_VERBFORMEN)
                    # Prüfe ob mindestens alle Haupt-Tags (Präsens, Imperfekt, etc.) entfernt werden
                    main_tempus = {'Prä', 'Imp', 'Aor', 'Fu', 'Pf', 'Plpf'}
                    if main_tempus.issubset(tags_to_hide_from_table) or len(all_verb_tags & tags_to_hide_from_table) >= 8:
                        wortart_is_completely_tagfree = True
                elif wortart.lower() == 'adjektiv':
                    # Bei Adjektiven: wenn Adj-Tag und alle Kasus entfernt werden
                    if 'Adj' in tags_to_hide_from_table and set(KASUS_TAGS).issubset(tags_to_hide_from_table):
                        wortart_is_completely_tagfree = True
            
            # Wenn Wortart komplett tagfrei werden soll, entferne auch enklitische Tags
            if wortart_is_completely_tagfree:
                tags_to_remove = tags_to_remove | (orig_tags & enclitic_tags)
            
            # ZUSÄTZLICH: Wenn ein enklitisches Tag (Pt, Kon, Prp) global ausgeschaltet ist,
            # entferne es überall, auch wenn es enklitisch an anderen Wortarten hängt
            for enclitic in enclitic_tags:
                # Prüfe ob dieses enklitische Tag in irgendeiner Wortart ausgeschaltet ist
                # ODER ob es als standalone (z.B. 'pt', 'kon', 'prp') ausgeschaltet ist
                if hidden_tags_by_wortart:
                    for wort_key, hidden_set in hidden_tags_by_wortart.items():
                        if enclitic in hidden_set:
                            # Dieses enklitische Tag ist global ausgeschaltet
                            if enclitic in orig_tags:
                                tags_to_remove.add(enclitic)
                            break
            
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
                # Stelle sicher, dass token_meta existiert
                if i < len(token_meta):
                    # WICHTIG: tags_to_remove ist das Set der entfernten Tags (nicht actually_removed!)
                    token_meta[i]['removed_tags'] = list(tags_to_remove) if tags_to_remove else []
                else:
                    # fallback - erweitern
                    while len(token_meta) <= i:
                        token_meta.append({})
                    token_meta[i]['removed_tags'] = list(tags_to_remove) if tags_to_remove else []
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
            # WICHTIG: Verwende _process_pair_block statt der nicht-existierenden _process_pair_block_for_tags
            processed_blocks.append(_process_pair_block(
                b,
                color_mode="COLOR",  # Farben bleiben erhalten
                tag_mode="NO_TAGS",  # Alle Tags entfernen
                versmass_mode="NORMAL",
                color_pos_keep=None,
                sup_keep=set(),  # Keine SUP-Tags behalten
                sub_keep=set(),  # Keine SUB-Tags behalten
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

def _strip_colors_from_block(block: dict, tag_config: dict = None) -> dict:
    """
    Entfernt Farbsymbole (#, +, -, §, $) aus einem Block.
    Wird für BLACK_WHITE PDFs verwendet.
    
    WICHTIG: Manuelle Farbsymbole (mit force_color=True) werden BEIBEHALTEN!
    Dies ermöglicht es, einzelne Wörter auch in BlackWhite-PDFs zu färben.
    """
    if not isinstance(block, dict):
        return block
    
    # Prüfe welche Tokens manuelle Farben haben (force_color=True)
    force_color_indices = set()
    if 'token_meta' in block and isinstance(block['token_meta'], list):
        for i, meta in enumerate(block['token_meta']):
            if isinstance(meta, dict) and meta.get('force_color') == True:
                force_color_indices.add(i)
    
    # Entferne Farbsymbole aus gr_tokens (NUR wenn NICHT force_color!)
    if 'gr_tokens' in block and isinstance(block['gr_tokens'], list):
        block['gr_tokens'] = [
            t if (i in force_color_indices or not t) else remove_color_symbols_from_token(t)
            for i, t in enumerate(block['gr_tokens'])
        ]
    
    # Entferne Farbsymbole aus de_tokens (NUR wenn NICHT force_color!)
    if 'de_tokens' in block and isinstance(block['de_tokens'], list):
        block['de_tokens'] = [
            t if (i in force_color_indices or not t) else remove_color_symbols_from_token(t)
            for i, t in enumerate(block['de_tokens'])
        ]
    
    # Entferne Farbsymbole aus en_tokens (NUR wenn NICHT force_color!)
    if 'en_tokens' in block and isinstance(block['en_tokens'], list):
        block['en_tokens'] = [
            t if (i in force_color_indices or not t) else remove_color_symbols_from_token(t)
            for i, t in enumerate(block['en_tokens'])
        ]
    
    # Entferne color_symbol aus token_meta (NUR wenn NICHT force_color!)
    if 'token_meta' in block and isinstance(block['token_meta'], list):
        for meta in block['token_meta']:
            if isinstance(meta, dict) and 'color_symbol' in meta:
                # Behalte Symbol wenn force_color=True
                if not meta.get('force_color'):
                    del meta['color_symbol']
    
    return block

def remove_color_symbols_from_token(token: str) -> str:
    """Entfernt alle Farbsymbole (#, +, -, §, $) aus einem einzelnen Token."""
    if not token:
        return token
    
    # Entferne alle Farbsymbole
    for sym in ['#', '+', '-', '§', '$']:
        token = token.replace(sym, '')
    
    return token

def remove_empty_translation_lines(blocks: list) -> list:
    """
    Entfernt Zeilen, bei denen ALLE Übersetzungen leer sind (de_tokens UND en_tokens).
    WICHTIG: Behält aber die antiken Tokens (gr_tokens)!
    """
    result = []
    for block in blocks:
        if not isinstance(block, dict):
            result.append(block)
            continue
        
        # Behalte ALLE Nicht-pair/flow Blöcke (Überschriften, Kommentare, etc.)
        if block.get('type') not in ('pair', 'flow'):
            result.append(block)
            continue
        
        # Prüfe ob ALLE Übersetzungen leer sind
        de_tokens = block.get('de_tokens', [])
        en_tokens = block.get('en_tokens', [])
        
        has_any_translation = any(de_tokens) or any(en_tokens)
        
        if has_any_translation:
            # Mindestens eine Übersetzung vorhanden → Block behalten
            result.append(block)
        else:
            # KEINE Übersetzungen → Prüfe ob antike Tokens vorhanden sind
            gr_tokens = block.get('gr_tokens', [])
            if any(gr_tokens):
                # Antike Tokens vorhanden → Block behalten (nur ohne Übersetzungen)
                result.append(block)
            # Sonst: Block komplett leer → entfernen (nicht zu result hinzufügen)
    
    return result

def _hide_manual_translations_in_block(block: Dict[str, Any]) -> Dict[str, Any]:
    """
    Versteckt Übersetzungen für Tokens mit (HideTrans) Tag.
    
    WICHTIG: Diese Funktion wird von apply_colors() aufgerufen!
    """
    if not isinstance(block, dict) or block.get('type') not in ('pair', 'flow'):
        return block
    
    gr_tokens = block.get('gr_tokens', [])
    de_tokens = block.get('de_tokens', [])
    en_tokens = block.get('en_tokens', [])
    
    TRANSLATION_HIDE_TAG = '(HideTrans)'
    
    for idx, gr_token in enumerate(gr_tokens):
        if not gr_token:
            continue
        
        # Prüfe auf (HideTrans) Tag
        if TRANSLATION_HIDE_TAG in gr_token or '(hidetrans)' in gr_token.lower():
            # Verstecke deutsche Übersetzung
            if idx < len(de_tokens):
                de_tokens[idx] = ''
            # Verstecke englische Übersetzung
            if idx < len(en_tokens):
                en_tokens[idx] = ''
    
    block['de_tokens'] = de_tokens
    block['en_tokens'] = en_tokens
    return block

def _hide_stephanus_in_translations(block: Dict[str, Any], translation_rules: Optional[Dict[str, Dict[str, Any]]]) -> Dict[str, Any]:
    """
    Entfernt Stephanus-Paginierungen aus Übersetzungszeilen, wenn Übersetzungen ausgeblendet sind.
    
    WICHTIG: Diese Funktion wird von apply_colors() aufgerufen!
    """
    if not isinstance(block, dict) or block.get('type') not in ('pair', 'flow'):
        return block
    
    # TODO: Implementiere Stephanus-Entfernung basierend auf translation_rules
    return block

def all_blocks_have_no_translations(blocks: List[Dict[str, Any]]) -> bool:
    """
    Prüft, ob ALLE pair/flow Blöcke keine Übersetzungen haben.
    Wird für _NoTrans Suffix verwendet.
    
    WICHTIG: Diese Funktion wird von prosa_pdf.py und poesie_pdf.py aufgerufen!
    """
    if not blocks:
        return True
    
    for block in blocks:
        if not isinstance(block, dict):
            continue
        if block.get('type') not in ('pair', 'flow'):
            continue
        
        de_tokens = block.get('de_tokens', [])
        en_tokens = block.get('en_tokens', [])
        
        # Wenn irgendein Token eine nicht-leere Übersetzung hat
        if any(de_tokens) or any(en_tokens):
            return False
    
    return True



