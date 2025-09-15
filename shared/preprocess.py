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
from typing import List, Dict, Any, Iterable, Optional

# ======= Tag-Definitionen für die Farbsymbol-Logik =======
KASUS_TAGS = {'N', 'G', 'D', 'A', 'V'}
MODUS_TAGS = {'Inf', 'Op', 'Imv', 'Kon'}
TEMPUS_TAGS = {'Aor', 'Prä', 'Imp', 'AorS', 'Per', 'Plq', 'Fu'}
DIATHESE_TAGS = {'Med', 'Pas', 'Akt', 'M/P'}
ADJEKTIV_TAGS = {'Adj'}

# ======= Konstanten (müssen mit dem Renderer-Stand zusammenpassen) =======
SUP_TAGS = {'N','D','G','A','V','Adj','Pt','Prp','Adv','Kon','Art','≈','Kmp','Sup','ij'}
SUB_TAGS = {'Prä','Imp','Aor','Per','Plq','Fu','Inf','Imv','Akt','Med','Pas','Knj','Op','Pr','AorS','M/P'}

# COLOR_POS_WHITELIST entfernt - Farben werden jetzt direkt in tag_colors definiert

# ======= Regexe =======
RE_PAREN_TAG     = re.compile(r'\(([A-Za-z0-9/≈äöüßÄÖÜ]+)\)')
RE_LEAD_BAR_COLOR= re.compile(r'^\|\s*([+\-#§$])')  # |+ |# |- |§ |$ (Farbcode NACH leitender '|')
RE_WORD_START = re.compile(r'([(\[|]*)([\w\u0370-\u03FF\u1F00-\u1FFF\u1F00-\u1FFF]+)') # Findet den Anfang eines Wortes, auch mit Präfixen wie (, [ oder |

COLOR_SYMBOLS = {'#', '+', '-', '§', '$'}
COLOR_MAP = {
    'red': '#',
    'blue': '+',
    'green': '-',
    'magenta': '§',
    'orange': '$',
}

# ======= Typen =======
ColorMode   = str  # "COLOR" | "BLACK_WHITE"
TagMode     = str  # "TAGS"  | "NO_TAGS"
VersmassMode= str  # "NORMAL" | "REMOVE_MARKERS" | "KEEP_MARKERS"

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
        
        # ZUERST: Prüfe ob das gesamte Tag direkt in den Listen enthalten ist
        is_sup_direct = tag in SUP_TAGS
        is_sub_direct = tag in SUB_TAGS
        
        if is_sup_direct or is_sub_direct:
            # Direktes Match gefunden
            is_sup = is_sup_direct
            is_sub = is_sub_direct
        else:
            # Fallback: Zerlege evtl. 'A/B' in Einzeltags (für zusammengesetzte Tags)
            parts = [p for p in tag.split('/') if p]
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
                # Direktes Match: prüfe ob Tag in sup_keep
                if tag in sup_keep:
                    return m.group(0)  # behalten
                return ''  # raus
            else:
                # Zusammengesetztes Tag: prüfe alle Teile
                if all(p in sup_keep for p in parts):
                    return m.group(0)  # behalten
                return ''  # raus
        if is_sub and sub_keep is not None:
            if is_sub_direct:
                # Direktes Match: prüfe ob Tag in sub_keep
                if tag in sub_keep:
                    return m.group(0)
                return ''
            else:
                # Zusammengesetztes Tag: prüfe alle Teile
                if all(p in sub_keep for p in parts):
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


def _apply_colors_from_config(blocks: List[Dict[str, Any]], tag_colors: Dict[str, str]) -> List[Dict[str, Any]]:
    """
    Fügt Farbsymbole basierend auf einer `tag_colors`-Konfiguration hinzu und überträgt sie.
    """
    if not tag_colors:
        return blocks

    new_blocks = []
    for block in blocks:
        if isinstance(block, dict) and block.get('type') in ('pair', 'flow'):
            new_block = block.copy()
            gr_tokens = new_block.get('gr_tokens', [])
            de_tokens = new_block.get('de_tokens', [])
            
            new_gr_tokens = list(gr_tokens)
            new_de_tokens = list(de_tokens)

            for i, token in enumerate(gr_tokens):
                if not token or any(c in token for c in COLOR_SYMBOLS):
                    continue

                token_tags = _extract_tags(token)
                color_to_apply = None
                
                for tag in token_tags:
                    if tag in tag_colors:
                        color_to_apply = tag_colors[tag]
                        break # Erster gefundener Tag bestimmt die Farbe
                
                if color_to_apply and color_to_apply in COLOR_MAP:
                    symbol = COLOR_MAP[color_to_apply]
                    
                    # Symbol im griechischen Token einfügen
                    match = RE_WORD_START.search(token)
                    if match:
                        new_gr_tokens[i] = token[:match.start(2)] + symbol + token[match.start(2):]

                        # Symbol auf deutsches Token übertragen, falls vorhanden und farblos
                        if i < len(de_tokens):
                            de_tok = de_tokens[i]
                            if de_tok and not any(c in de_tok for c in COLOR_SYMBOLS):
                                de_match = RE_WORD_START.search(de_tok)
                                if de_match:
                                    new_de_tokens[i] = de_tok[:de_match.start(2)] + symbol + de_tok[de_match.start(2):]
                                else:
                                    new_de_tokens[i] = symbol + de_tok

            new_block['gr_tokens'] = new_gr_tokens
            new_block['de_tokens'] = new_de_tokens
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

# ======= Öffentliche API =======
def apply(blocks: List[Dict[str, Any]],
          *,
          color_mode: ColorMode,
          tag_mode: TagMode,
          versmass_mode: VersmassMode = "NORMAL",
          # NEU (optional):
          tag_config: Optional[Dict[str, Any]] = None,
          sup_keep: Optional[Iterable[str]] = None,
          sub_keep: Optional[Iterable[str]] = None) -> List[Dict[str, Any]]:
    """
    Vorverarbeitung der Blockliste. Gibt eine NEUE Liste zurück.
    - tag_config: Das neue Konfigurationsobjekt vom Frontend.
    - sup_keep / sub_keep: Iterable Tag-Kürzel, die behalten werden (alle übrigen bekannten SUP/SUB werden entfernt).
                           None → keine Einschränkung (alle bekannten Tag-Typen bleiben erhalten).
    """
    
    blocks_to_process = blocks
    if tag_config and tag_config.get('tag_colors'):
        blocks_to_process = _apply_colors_from_config(blocks, tag_config.get('tag_colors'))

    # color_pos_keep wird nicht mehr verwendet
    cpos = None
    
    keep_sup = None
    if sup_keep is not None:
        keep_sup = set(sup_keep)
    keep_sub = None
    if sub_keep is not None:
        keep_sub = set(sub_keep)

    out: List[Dict[str, Any]] = []
    for b in blocks_to_process:
        # Erweitert, um sowohl 'pair' (Poesie) als auch 'flow' (Prosa) Blöcke zu verarbeiten.
        if isinstance(b, dict) and b.get('type') in ('pair', 'flow'):
            out.append(_process_pair_block(
                b,
                color_mode=color_mode,
                tag_mode=tag_mode,
                versmass_mode=versmass_mode,
                color_pos_keep=cpos,
                sup_keep=keep_sup,
                sub_keep=keep_sub,
            ))
        else:
            out.append(b)
    return out

# ======= Komfort: Payload aus UI (Hidden JSON) verarbeiten =======
def apply_from_payload(blocks: List[Dict[str, Any]], payload: Dict[str, Any], *,
                       default_versmass_mode: VersmassMode = "NORMAL") -> List[Dict[str, Any]]:
    """
    Verarbeitet die Konfiguration aus dem Frontend.
    Payload-Format (neu):
      {
        "kind": "poesie",
        "author": "...",
        "work": "...",
        "color_mode": "Colour" | "BlackWhite",
        // ... andere Metadaten
        "tag_config": {
          "placement_overrides": { "N": "sup", "Prä": "sub", ... },
          "tag_colors": { "N": "red", ... },
          "hidden_tags": [ "V", "D", ... ]
        }
      }
    """
    tag_config = payload.get("tag_config", {})
    
    # 1. Farbmodus bestimmen
    color_mode = "BLACK_WHITE" if payload.get("color_mode") == "BlackWhite" else "COLOR"

    # 2. Tag-Modus und Keep-Listen bestimmen
    hidden_tags = set(tag_config.get("hidden_tags", []))
    placement = tag_config.get("placement_overrides", {})
    
    all_known_tags = SUP_TAGS.union(SUB_TAGS)
    
    # Wenn alle Tags versteckt sind, ist der Modus NO_TAGS
    if hidden_tags.issuperset(all_known_tags):
        tag_mode = "NO_TAGS"
        sup_arg = None
        sub_arg = None
    else:
        tag_mode = "TAGS"
        sup_arg = {tag for tag, place in placement.items() if place == "sup" and tag not in hidden_tags}
        sub_arg = {tag for tag, place in placement.items() if place == "sub" and tag not in hidden_tags}

    # 3. Versmaß-Modus
    versmass_mode  = payload.get("versmass", default_versmass_mode)

    return apply(
        blocks,
        color_mode=color_mode,
        tag_mode=tag_mode,
        versmass_mode=versmass_mode,
        tag_config=tag_config,
        sup_keep=sup_arg,
        sub_keep=sub_arg,
    )

