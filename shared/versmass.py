#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
shared/versmass.py
------------------
Einfache, robuste Versmaß-Erkennung pro Token.

Grundsätze:
- Es gibt KEINE automatische Elisions- oder Cross-Token-Logik.
- Marker:
    'i'  = kurz
    'L'  = lang
    '|'  = Fuß-Trenner
- Wrapper/Tags in Klammern "(...)" sowie führende Steuerzeichen '#', '+', '-'
  werden entfernt, der Rest bleibt unangetastet.

API:
- has_meter_markers(tokens: list[str]) -> bool
- extract_meter(tokens: list[str]) -> dict | None
  Rückgabe:
    {
      "tokens": [ {"i":[...], "L":[...], "|":[...]}, ... ],
      "counts": {"i": N_i, "L": N_L, "|": N_bar}
    }
"""

from typing import List, Dict, Any, Optional
import re

# Typografisches Apostroph (Durchleitung; keine Logik hier)
APOST = '’'

# Entfernt Tags in (...), z. B. (Pt), (Aj), (Pr) usw.
RE_PARENS = re.compile(r'\([^)]*\)')

def strip_wrappers(token: str) -> str:
    """
    Entfernt führende Steuerzeichen (#, +, -, §, $) und alle (...)-Tags.
    WICHTIG: '_' bleibt erhalten. Ebenso bleiben i, L, |, ' unangetastet.
    """
    if not token:
        return ''
    s = token
    # Führendes Steuerzeichen abwerfen (inkl. neue Farbmarker § und $)
    if s and s[0] in '#+-§$':
        s = s[1:]
    # Alle (...)-Tags entfernen
    s = RE_PARENS.sub('', s)
    # KEIN Entfernen/Ersetzen von '_'!
    return s

def _iter_markers(core: str):
    """Erzeugt (index, zeichen) für jedes Markerzeichen in core."""
    for i, ch in enumerate(core):
        if ch in ('i', 'L', '|'):
            yield i, ch

def has_meter_markers(tokens: List[str], min_markers_per_line: int = 3, min_total: int = 10) -> bool:
    """
    Prüft, ob die Token-Liste signifikante Versmaß-Marker enthält.
    
    Rückgabe True wenn EINE der folgenden Bedingungen erfüllt ist:
    1. Mindestens 10 Marker (i/L/|) insgesamt in der Token-Liste ODER
    2. Es gibt mindestens 3 Marker in dieser einzelnen Zeile
    
    Dies verhindert, dass zufällige einzelne 'i' oder 'L' Buchstaben im Text
    fälschlicherweise als Versmaß-Marker erkannt werden.
    
    Args:
        tokens: Liste von Token-Strings (eine Zeile)
        min_markers_per_line: Mindestanzahl Marker pro Zeile für Versmaß-Erkennung (default: 3)
        min_total: Mindestanzahl Marker insgesamt für sichere Erkennung (default: 10)
    
    Returns:
        True wenn signifikante Versmaß-Marker gefunden wurden
    """
    if not tokens:
        return False
    
    # Zähle alle Marker in dieser Token-Liste
    marker_count = 0
    for t in tokens:
        core = strip_wrappers(t)
        marker_count += sum(1 for ch in core if ch in ('i', 'L', '|'))
    
    # Bedingung 1: Mindestens min_total Marker insgesamt (sehr sicher)
    if marker_count >= min_total:
        return True
    
    # Bedingung 2: Mindestens min_markers_per_line Marker in dieser Zeile
    if marker_count >= min_markers_per_line:
        return True
    
    return False

def extract_meter(tokens: List[str]) -> Optional[Dict[str, Any]]:
    """
    Liefert Markerpositionen je Token (ohne automatische Elision).
    Sichtbarer Join-Marker '_' bleibt im Core und beeinflusst die Indizes.
    """
    if not tokens:
        return None

    per_token: List[Dict[str, List[int]]] = []
    ci = cl = cp = 0
    any_marker = False

    for t in tokens:
        core = strip_wrappers(t)
        pos_i: List[int] = []
        pos_L: List[int] = []
        pos_p: List[int] = []

        for idx, ch in _iter_markers(core):
            any_marker = True
            if ch == 'i':
                pos_i.append(idx); ci += 1
            elif ch == 'L':
                pos_L.append(idx); cl += 1
            else:
                pos_p.append(idx); cp += 1

        per_token.append({"i": pos_i, "L": pos_L, "|": pos_p})

    if not any_marker:
        return None

    return {
        "tokens": per_token,
        "counts": {"i": ci, "L": cl, "|": cp},
    }


def document_has_meter_markers(blocks: List[Dict[str, Any]], 
                               min_lines_with_markers: int = 3,
                               min_markers_per_line: int = 3) -> bool:
    """
    Prüft, ob ein ganzes Dokument (Liste von Blöcken) signifikante Versmaß-Marker enthält.
    
    Rückgabe True wenn EINE der folgenden Bedingungen erfüllt ist:
    1. Mindestens min_lines_with_markers verschiedene Zeilen haben je mindestens 
       min_markers_per_line Marker ODER
    2. Mindestens eine Zeile hat 10 oder mehr Marker
    
    Dies ist robuster als die einzelne has_meter_markers Funktion, da sie über
    mehrere Zeilen hinweg prüft und nicht durch zufällige 'i' oder 'L' getäuscht wird.
    
    Args:
        blocks: Liste von Block-Dictionaries (type='pair' mit 'gr_tokens')
        min_lines_with_markers: Mindestanzahl Zeilen mit Markern (default: 3)
        min_markers_per_line: Mindestanzahl Marker pro Zeile (default: 3)
    
    Returns:
        True wenn das Dokument signifikante Versmaß-Marker enthält
    """
    if not blocks:
        return False
    
    lines_with_sufficient_markers = 0
    
    for block in blocks:
        if block.get('type') == 'pair':
            tokens = block.get('gr_tokens', [])
            if not tokens:
                continue
            
            # Zähle Marker in dieser Zeile
            marker_count = 0
            for t in tokens:
                core = strip_wrappers(t)
                marker_count += sum(1 for ch in core if ch in ('i', 'L', '|'))
            
            # Bedingung 1: Eine Zeile mit sehr vielen Markern (>=10) → sofort True
            if marker_count >= 10:
                return True
            
            # Bedingung 2: Zeile hat mindestens min_markers_per_line Marker → zähle sie
            if marker_count >= min_markers_per_line:
                lines_with_sufficient_markers += 1
                
                # Wenn wir genug Zeilen mit Markern haben → True
                if lines_with_sufficient_markers >= min_lines_with_markers:
                    return True
    
    return False
