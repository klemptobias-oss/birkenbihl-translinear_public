#!/usr/bin/env python3
"""Test build_tables_for_pair mit leeren gr_tokens"""

from Poesie_Code import build_tables_for_pair
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.units import mm as MM

base = getSampleStyleSheet()

token_gr = ParagraphStyle('TokenGR', parent=base['Normal'], fontSize=12, alignment=TA_LEFT)
token_de = ParagraphStyle('TokenDE', parent=base['Normal'], fontSize=10, alignment=TA_LEFT)
num_style = ParagraphStyle('Num', parent=base['Normal'], fontSize=10)
style_speaker = ParagraphStyle('Speaker', parent=base['Normal'], fontSize=9)

print("=== Test 1: Normale Zeile (mit gr_tokens) ===")
result1 = build_tables_for_pair(
    gr_tokens=['ἄνδρα', 'μοι', 'ἔννεπε,'],
    de_tokens=['den|Mann', 'mir', 'sage,'],
    speaker='Test',
    line_label='1',
    doc_width_pt=500,
    token_gr_style=token_gr,
    token_de_style=token_de,
    num_style=num_style,
    style_speaker=style_speaker,
    global_speaker_width_pt=50.0,  # Mock
    block={}  # Mock block
)
print(f"Result 1: {len(result1)} Tabellen")

print("\n=== Test 2: Alternative Zeile (OHNE gr_tokens) ===")
result2 = build_tables_for_pair(
    gr_tokens=[],  # LEER!
    de_tokens=['über|den|Mann', '', 'verrate,'],
    speaker='',  # Kein Sprecher
    line_label='',  # Keine Zeilennummer
    doc_width_pt=500,
    token_gr_style=token_gr,
    token_de_style=token_de,
    num_style=num_style,
    style_speaker=style_speaker,
    global_speaker_width_pt=50.0,  # Mock
    block={}  # Mock block
)
print(f"Result 2: {len(result2)} Tabellen")

if len(result2) == 0:
    print("❌ PROBLEM: build_tables_for_pair gibt LEERE Liste zurück für Alternativen ohne gr_tokens!")
else:
    print("✅ OK: build_tables_for_pair gibt Tabellen zurück auch ohne gr_tokens")
