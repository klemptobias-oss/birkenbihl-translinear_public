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
          Alle anderen Tokens werden entfärbt. Mögliche PoS: {"Aj","Pt","Prp","Av","Ko","Art","Pr","Ij"}
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

# ======= Konstanten (müssen mit dem Renderer-Stand zusammenpassen) =======
SUP_TAGS = {'N','D','G','A','V','Aj','Pt','Prp','Av','Ko','Art','≈','Kmp','Sup','Ij'}
SUB_TAGS = {'Pre','Imp','Aor','Per','Plq','Fu','Inf','Imv','Akt','Med','Pas','Kon','Op','Pr','AorS','M/P'}

# PoS-Kandidaten für Farbsteuerung (bewusst keine Kasus!)
COLOR_POS_WHITELIST = {'Aj','Pt','Prp','Av','Ko','Art','Pr','Ij'}

# ======= Regexe =======
RE_PAREN_TAG     = re.compile(r'\(([A-Za-z0-9/≈]+)\)')
RE_LEAD_BAR_COLOR= re.compile(r'^\|\s*([+\-#])')  # |+ |# |- (Farbcode NACH leitender '|')

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
    for ch in ['#', '+', '-']:
        t = t.replace(ch, '')
    return t

# ======= Hilfen: Tag-Listen am Token =======
def _extract_tags(token: str) -> List[str]:
    if not token:
        return []
    return RE_PAREN_TAG.findall(token)

def _is_known_sup(tag: str) -> bool:
    if tag in SUP_TAGS:
        return True
    # zusammengesetzte Tags (M/P) oder A/B/C
    parts = [p for p in tag.split('/') if p]
    return all(p in SUP_TAGS for p in parts)

def _is_known_sub(tag: str) -> bool:
    if tag in SUB_TAGS:
        return True
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
        # Zerlege evtl. 'A/B' in Einzeltags (wir entscheiden „bekannt“/„unbekannt“ auf Basis aller Teile)
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
            if all(p in sup_keep for p in parts):
                return m.group(0)  # behalten
            return ''  # raus
        if is_sub and sub_keep is not None:
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
          color_pos_keep: Optional[Iterable[str]] = None,
          sup_keep: Optional[Iterable[str]] = None,
          sub_keep: Optional[Iterable[str]] = None) -> List[Dict[str, Any]]:
    """
    Vorverarbeitung der Blockliste. Gibt eine NEUE Liste zurück.
    - color_pos_keep: Iterable PoS-Tags (aus COLOR_POS_WHITELIST), für die Farbcodes erhalten bleiben.
                      None → keine Einschränkung (Farben bleiben überall erhalten, sofern color_mode="COLOR").
    - sup_keep / sub_keep: Iterable Tag-Kürzel, die behalten werden (alle übrigen bekannten SUP/SUB werden entfernt).
                           None → keine Einschränkung (alle bekannten Tag-Typen bleiben erhalten).
    """
    # Defensive Normalisierung der optionalen Parameter
    cpos = None
    if color_pos_keep is not None:
        cpos = {p for p in color_pos_keep if p in COLOR_POS_WHITELIST}
    keep_sup = None
    if sup_keep is not None:
        keep_sup = {t for t in sup_keep if t in SUP_TAGS}
    keep_sub = None
    if sub_keep is not None:
        keep_sub = {t for t in sub_keep if t in SUB_TAGS}

    out: List[Dict[str, Any]] = []
    for b in blocks:
        if isinstance(b, dict) and b.get('type') == 'pair':
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
                       default_color_mode: ColorMode = "COLOR",
                       default_tag_mode: TagMode = "TAGS",
                       default_versmass_mode: VersmassMode = "NORMAL") -> List[Dict[str, Any]]:
    """
    Payload:
      {
        "show_colors": bool,
        "show_tags":   bool,
        "color_pos":   [ "Aj","Pt",... ],     # PoS für Farbe
        "sup_keep":    [ "N","D","G","A","V","Aj",... ],
        "sub_keep":    [ "Pre","Imp","Aor","AorS","Per",... ],
        "versmass":    "NORMAL" | "KEEP_MARKERS" | "REMOVE_MARKERS"
      }
    """
    show_colors = bool(payload.get("show_colors", True))
    show_tags   = bool(payload.get("show_tags",   True))

    color_pos_keep = payload.get("color_pos") or []
    sup_keep       = payload.get("sup_keep")   or []
    sub_keep       = payload.get("sub_keep")   or []
    versmass_mode  = payload.get("versmass", default_versmass_mode)

    # --- Normalisierung auf Extremfälle (wichtig für Suffixe/Namen) ---
    # Farben: Wenn global aus ODER Liste leer → BLACK_WHITE
    if (not show_colors) or (len(color_pos_keep) == 0):
        color_mode = "BLACK_WHITE"
        color_pos_arg = None
    else:
        color_mode = "COLOR"
        color_pos_arg = color_pos_keep

    # Tags: Wenn global aus ODER beide Listen leer → NO_TAGS
    if (not show_tags) or (len(sup_keep) == 0 and len(sub_keep) == 0):
        tag_mode = "NO_TAGS"
        sup_arg = None
        sub_arg = None
    else:
        tag_mode = "TAGS"
        sup_arg = sup_keep
        sub_arg = sub_keep

    return apply(
        blocks,
        color_mode=color_mode,
        tag_mode=tag_mode,
        versmass_mode=versmass_mode,
        color_pos_keep=color_pos_arg,
        sup_keep=sup_arg,
        sub_keep=sub_arg,
    )

