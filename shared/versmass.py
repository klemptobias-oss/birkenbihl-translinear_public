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

def has_meter_markers(tokens: List[str]) -> bool:
    """
    True, wenn nach dem Wrapper-Strip irgendwo i/L/| im Token-Core vorkommt.
    """
    if not tokens:
        return False
    for t in tokens:
        core = strip_wrappers(t)
        if any(ch in ('i', 'L', '|') for ch in core):
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

