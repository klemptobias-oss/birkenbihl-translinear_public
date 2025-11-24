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

# ======= Konstanten (müssen mit dem Renderer-Stand zusammenpassen) =======
SUP_TAGS = {'N','D','G','A','V','Du','Adj','Pt','Prp','Adv','Kon','Art','≈','Kmp','Sup','ij','Abl'}  # NEU: Abl für Latein
SUB_TAGS = {'Prä','Imp','Aor','Per','Plq','Fu','Inf','Imv','Akt','Med','Pas','Knj','Op','Pr','AorS','M/P','Gdv','Ger','Spn','Fu1','Fu2'}  # NEU: Gdv, Ger, Spn, Fu1, Fu2 für Latein

# ======= Regexe =======
RE_PAREN_TAG     = re.compile(r'\(([A-Za-z0-9/≈äöüßÄÖÜ]+)\)')
RE_LEAD_BAR_COLOR= re.compile(r'^\|\s*([+\-#§$])')  # |+ |# |- |§ |$ (Farbcode NACH leitender '|')
RE_WORD_START = re.compile(r'([(\[|]*)([\w\u0370-\u03FF\u1F00-\u1FFF\u1F00-\u1FFF]+)') # Findet den Anfang eines Wortes, auch mit Präfixen wie (, [ oder |
RE_STEPHANUS = re.compile(r'\[(\d+[a-e])\]')  # Stephanus-Paginierungen: [543b], [546b] etc.

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
                # Direktes Match: prüfe ob Tag in sup_keep
                if tag_normalized in sup_keep:
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
                if tag_normalized in sub_keep:
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


def _apply_colors_and_placements(blocks: List[Dict[str, Any]], config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Fügt Farbsymbole und (zukünftig) Platzierungen basierend auf der vollen Konfiguration hinzu.
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

            for i, token in enumerate(gr_tokens):
                if not token or any(c in token for c in COLOR_SYMBOLS):
                    continue

                token_tags = set(_extract_tags(token))
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
    normalized_tags: Set[str] = set()
    for tag in tags:
        # Debug: Prüfe ob HideTrans erkannt wird
        if tag == TRANSLATION_HIDE_TAG:
            # print(f"DEBUG: HideTrans gefunden in Token: {token}")
            return True
        parts = [p for p in tag.split('/') if p]
        for part in parts:
            normalized_tags.add(_normalize_tag_name(part))

    wortart, _ = _get_wortart_and_relevant_tags(normalized_tags)
    if wortart:
        entry = translation_rules.get(wortart.lower())
        if entry:
            if entry.get("all"):
                return True
            if entry.get("tags") and any(tag in entry["tags"] for tag in normalized_tags):
                return True

    global_entry = translation_rules.get(TRANSLATION_HIDE_GLOBAL)
    if global_entry:
        if global_entry.get("all"):
            return True
        if global_entry.get("tags") and any(tag in global_entry["tags"] for tag in normalized_tags):
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

def apply_colors(blocks: List[Dict[str, Any]], tag_config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Fügt Farbsymbole (#, +, §, $) basierend auf der tag_config hinzu.
    Gibt eine NEUE, tief kopierte Blockliste zurück.
    Die Original-Tags bleiben vollständig erhalten.
    
    WICHTIG: Versteckt auch Übersetzungen für (HideTrans) Tags NACH dem Hinzufügen der Farben.
    NEU: Entfernt auch Stephanus-Paginierungen aus Übersetzungszeilen, wenn Übersetzungen ausgeblendet sind.
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

def apply_tag_visibility(blocks: List[Dict[str, Any]], tag_config: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Filtert Tags basierend auf den 'hide' und 'placement' Regeln in tag_config.
    Wenn tag_config=None ist, bleiben alle Tags erhalten.
    Gibt eine NEUE, tief kopierte Blockliste zurück.
    """
    import copy
    blocks_copy = copy.deepcopy(blocks)
    
    sup_keep, sub_keep = set(), set()
    translation_rules: Dict[str, Dict[str, Any]] = {}
    if tag_config:
        # Starte mit allen bekannten Tags
        sup_keep = SUP_TAGS.copy()
        sub_keep = SUB_TAGS.copy()
        
        # Sortiere Regeln: Gruppen-Regeln zuerst, dann spezifische Regeln
        # Damit spezifische Regeln die Gruppen-Regeln überschreiben können
        group_rules = []
        specific_rules = []
        
        for rule_id, conf in tag_config.items():
            normalized_rule_id = _normalize_rule_id(rule_id)
            # Gruppen-Regel = keine Unterstriche nach dem Hauptteil (z.B. "verb", "nomen")
            # Spezifische Regel = mit Unterstrich (z.B. "verb_Pra", "nomen_N")
            if '_' in normalized_rule_id and normalized_rule_id.split('_', 1)[1]:
                specific_rules.append((rule_id, conf))
            else:
                group_rules.append((rule_id, conf))
        
        # Verarbeite zuerst Gruppen-Regeln, dann spezifische Regeln
        for rule_id, conf in group_rules + specific_rules:
            normalized_rule_id = _normalize_rule_id(rule_id)
            tags_for_rule = _resolve_tags_for_rule(normalized_rule_id)

            if not tags_for_rule:
                continue

            _maybe_register_translation_rule(translation_rules, normalized_rule_id, conf)

            if conf.get('hide'):
                # DEBUG: Zeige, welche Tags entfernt werden
                print(f"DEBUG apply_tag_visibility: Regel '{rule_id}' (normalisiert: '{normalized_rule_id}') hat hide=true, entferne Tags: {tags_for_rule}")
                for tag in tags_for_rule:
                    # Normalisiere Tag-Namen für robusten Vergleich
                    normalized_tag = _normalize_tag_name(tag)
                    sup_keep.discard(tag)
                    sup_keep.discard(normalized_tag)
                    sub_keep.discard(tag)
                    sub_keep.discard(normalized_tag)
                print(f"DEBUG: Nach Entfernung - sup_keep hat noch {len(sup_keep)} Tags, sub_keep hat noch {len(sub_keep)} Tags")
            else:
                placement = conf.get('placement')
                if placement == 'sup':
                    for tag in tags_for_rule:
                        sub_keep.discard(tag)
                        if tag in SUP_TAGS:
                            sup_keep.add(tag)
                elif placement == 'sub':
                    for tag in tags_for_rule:
                        sup_keep.discard(tag)
                        if tag in SUB_TAGS:
                            sub_keep.add(tag)

    else:
        # Wenn keine Config da ist, alle bekannten Tags behalten
        sup_keep = SUP_TAGS
        sub_keep = SUB_TAGS

    processed_blocks = []
    for b in blocks_copy:
        if isinstance(b, dict) and b.get('type') in ('pair', 'flow'):
            processed_blocks.append(_process_pair_block_for_tags(
                b,
                sup_keep=sup_keep,
                sub_keep=sub_keep,
                remove_all=False,
                translation_rules=translation_rules if translation_rules else None,
            ))
        else:
            # Kommentare und andere Block-Typen durchreichen
            processed_blocks.append(b)
    return processed_blocks

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
          tag_config: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """
    Vorverarbeitung der Blockliste. Gibt eine NEUE Liste zurück.
    - tag_config: Das neue, detaillierte Konfigurationsobjekt vom Frontend.
    """
    
    # 1. Farben anwenden (wenn color_mode="COLOR")
    # Dieser Schritt fügt die Farbsymbole (#, +, §, $) basierend auf der tag_config hinzu.
    # Die Original-Tags bleiben für den nächsten Schritt erhalten.
    blocks_with_colors = blocks
    if color_mode == "COLOR" and tag_config:
        blocks_with_colors = _apply_colors_and_placements(blocks, tag_config)

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
        sup_keep = set()
        sub_keep = set()
        for rule_id, conf in tag_config.items():
            normalized_rule_id = _normalize_rule_id(rule_id)
            tags_for_rule = _resolve_tags_for_rule(normalized_rule_id)
            if not tags_for_rule:
                continue

            if conf.get('hide'):
                for tag in tags_for_rule:
                    if tag in SUP_TAGS:
                        sup_keep.discard(tag)
                    if tag in SUB_TAGS:
                        sub_keep.discard(tag)
            else:
                placement = conf.get('placement')
                if placement == 'sup':
                    for tag in tags_for_rule:
                        if tag in SUP_TAGS:
                            sup_keep.add(tag)
                        if tag in SUB_TAGS:
                            sub_keep.discard(tag)
                elif placement == 'sub':
                    for tag in tags_for_rule:
                        if tag in SUB_TAGS:
                            sub_keep.add(tag)
                        if tag in SUP_TAGS:
                            sup_keep.discard(tag)
                else:
                    for tag in tags_for_rule:
                        if tag in SUP_TAGS:
                            sup_keep.add(tag)
                        if tag in SUB_TAGS:
                            sub_keep.add(tag)

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
        return [
            _remove_selected_tags(tok, sup_keep=sup_keep, sub_keep=sub_keep, remove_all=remove_all)
            for tok in (seq or [])
        ]
    
    if 'gr_tokens' in block or 'de_tokens' in block:
        result = {
            **block,
            'gr_tokens': proc_tokens(block.get('gr_tokens', [])),
            'de_tokens': proc_tokens(block.get('de_tokens', [])),
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
    Prüft, ob ein Token nur aus Satzzeichen besteht (mit optionalen Leerzeichen).
    Beispiele: ".", "?", "!", "...", ". . .", "·", etc.
    """
    if not token:
        return False
    token_stripped = token.strip()
    # Entferne Leerzeichen und prüfe, ob nur Satzzeichen übrig bleiben
    no_spaces = token_stripped.replace(' ', '')
    # Prüfe, ob nur Satzzeichen vorhanden sind
    return bool(no_spaces) and all(c in '.,;:!?·…' for c in no_spaces)

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
            
            # Entferne Tokens, die nur aus Satzzeichen bestehen (nur wenn ALLE Übersetzungen ausgeblendet sind = NoTrans PDF)
            if has_all_translations_hidden and _is_punctuation_only_token(token_stripped):
                result['de_tokens'][idx] = ''
                continue
            
            # Entferne Stephanus-Paginierungen NUR wenn ALLE Übersetzungen ausgeblendet sind (NoTrans PDF)
            if RE_STEPHANUS.search(token_stripped):
                if has_all_translations_hidden:
                    if RE_STEPHANUS.fullmatch(token_stripped):
                        # Token ist nur eine Stephanus-Paginierung → komplett entfernen
                        result['de_tokens'][idx] = ''
                    else:
                        # Token enthält Stephanus-Paginierung + anderen Text → nur Paginierung entfernen
                        cleaned = _remove_stephanus_from_token(token)
                        if not cleaned.strip():
                            result['de_tokens'][idx] = ''
                        else:
                            result['de_tokens'][idx] = cleaned
    
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
            
            # Entferne Tokens, die nur aus Satzzeichen bestehen (nur wenn ALLE Übersetzungen ausgeblendet sind = NoTrans PDF)
            if has_all_translations_hidden and _is_punctuation_only_token(token_stripped):
                result['en_tokens'][idx] = ''
                continue
            
            # Entferne Stephanus-Paginierungen NUR wenn ALLE Übersetzungen ausgeblendet sind (NoTrans PDF)
            if RE_STEPHANUS.search(token_stripped):
                if has_all_translations_hidden:
                    if RE_STEPHANUS.fullmatch(token_stripped):
                        # Token ist nur eine Stephanus-Paginierung → komplett entfernen
                        result['en_tokens'][idx] = ''
                    else:
                        # Token enthält Stephanus-Paginierung + anderen Text → nur Paginierung entfernen
                        cleaned = _remove_stephanus_from_token(token)
                        if not cleaned.strip():
                            result['en_tokens'][idx] = ''
                        else:
                            result['en_tokens'][idx] = cleaned
    
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
    if not tag_config or not all(conf.get('hide', False) for conf in tag_config.values()):
        all_hidden = False
        
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

