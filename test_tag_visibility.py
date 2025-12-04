#!/usr/bin/env python3
"""
Test für die Tag-Visibility-Logik.
Prüft ob Gruppenanführer MIT eigenem Tag (Adj, Art, Pr) nur ihr eigenes Tag ausblenden,
nicht aber die Subtags (N, G, D, A, etc.).
"""

import sys
sys.path.insert(0, '/media/tobias/New Volume/birkenbihl-site')

from shared.preprocess import apply_tag_visibility

# Test-Daten: Zeile aus Andria (-5) und (0)
# (-5) suus(Adj)(N) - "sein"
# (0) aliam(Adj)(A) - "eine andere"
# (-10) Sorōrem(Adj)(A) falsō(Adj)(N) crēditam(Adj)(Abl)

test_blocks = [
    {
        'type': 'pair',
        'gr_tokens': [
            'Sorōrem(Adj)(A)',
            'falsō(Adj)(N)', 
            'crēditam(Adj)(Abl)',
        ],
        'de_tokens': ['Schwester', 'irrtümlich', 'geglaubt'],
        'token_meta': [{}, {}, {}],
    }
]

print("=" * 70)
print("TEST 1: Adj-Gruppenanführer auf 'Tags ausblenden'")
print("=" * 70)
print("ERWARTET: Nur (Adj) ausgeblendet, NICHT (A), (N), (Abl)")
print()

# Tag-Config: "adj" auf "hide" setzen (nicht "hide_tags"!)
tag_config_adj_hidden = {
    'adj': {  # Gruppenanführer
        'hide': True,  # ← KORRIGIERT: 'hide' statt 'hide_tags'
        'show_text': True,
        'color_mode': 'COLOR',
    }
}

result = apply_tag_visibility(test_blocks, tag_config_adj_hidden)

print("ERGEBNIS:")
for i, token in enumerate(result[0]['gr_tokens']):
    original = test_blocks[0]['gr_tokens'][i]
    print(f"  Original: {original:30s} → Result: {token}")

print()
print("ANALYSE:")
print(f"  Token 0: Sollte sein: 'Sorōrem(A)'     Ist: {result[0]['gr_tokens'][0]}")
print(f"  Token 1: Sollte sein: 'falsō(N)'       Ist: {result[0]['gr_tokens'][1]}")
print(f"  Token 2: Sollte sein: 'crēditam(Abl)'  Ist: {result[0]['gr_tokens'][2]}")

success_0 = result[0]['gr_tokens'][0] == 'Sorōrem(A)'
success_1 = result[0]['gr_tokens'][1] == 'falsō(N)'
success_2 = result[0]['gr_tokens'][2] == 'crēditam(Abl)'

if success_0 and success_1 and success_2:
    print("\n✅ TEST BESTANDEN: Adj-Tag entfernt, Kasus-Tags bleiben!")
else:
    print("\n❌ TEST FEHLGESCHLAGEN!")
    if not success_0:
        print("   → Token 0: (Adj) und (A) sollten getrennt behandelt werden")
    if not success_1:
        print("   → Token 1: (Adj) und (N) sollten getrennt behandelt werden")
    if not success_2:
        print("   → Token 2: (Adj) und (Abl) sollten getrennt behandelt werden")

print("\n" + "=" * 70)
print("TEST 2: Adj + spezifischer Kasus (Adj_A) beide auf 'Tags ausblenden'")
print("=" * 70)
print("ERWARTET: Sowohl (Adj) als auch (A) ausgeblendet → 'Sorōrem'")
print()

tag_config_adj_and_A_hidden = {
    'adj': {  # Gruppenanführer
        'hide': True,  # ← KORRIGIERT
    },
    'adj_A': {  # Spezifischer Akkusativ
        'hide': True,  # ← KORRIGIERT
    }
}

print(f"DEBUG: tag_config_adj_and_A_hidden = {tag_config_adj_and_A_hidden}")


test_blocks_2 = [
    {
        'type': 'pair',
        'gr_tokens': ['Sorōrem(Adj)(A)'],
        'de_tokens': ['Schwester'],
        'token_meta': [{}],
    }
]

result2 = apply_tag_visibility(test_blocks_2, tag_config_adj_and_A_hidden)

print("ERGEBNIS:")
print(f"  Original: 'Sorōrem(Adj)(A)' → Result: '{result2[0]['gr_tokens'][0]}'")

if result2[0]['gr_tokens'][0] == 'Sorōrem':
    print("\n✅ TEST BESTANDEN: Beide Tags entfernt!")
else:
    print(f"\n❌ TEST FEHLGESCHLAGEN! Erwartet: 'Sorōrem', Erhalten: '{result2[0]['gr_tokens'][0]}'")

print("\n" + "=" * 70)
print("TEST 3: Nur Adj_N ausgeblendet, Adj-Gruppenanführer NICHT")
print("=" * 70)
print("ERWARTET: Nur (N) ausgeblendet → 'falsō(Adj)'")
print()

tag_config_only_N_hidden = {
    'adj_N': {
        'hide': True,  # ← KORRIGIERT
    }
}

test_blocks_3 = [
    {
        'type': 'pair',
        'gr_tokens': ['falsō(Adj)(N)'],
        'de_tokens': ['irrtümlich'],
        'token_meta': [{}],
    }
]

result3 = apply_tag_visibility(test_blocks_3, tag_config_only_N_hidden)

print("ERGEBNIS:")
print(f"  Original: 'falsō(Adj)(N)' → Result: '{result3[0]['gr_tokens'][0]}'")

if result3[0]['gr_tokens'][0] == 'falsō(Adj)':
    print("\n✅ TEST BESTANDEN: Nur (N) entfernt, (Adj) bleibt!")
else:
    print(f"\n❌ TEST FEHLGESCHLAGEN! Erwartet: 'falsō(Adj)', Erhalten: '{result3[0]['gr_tokens'][0]}'")

print("\n" + "=" * 70)
print("ZUSAMMENFASSUNG")
print("=" * 70)
all_tests = [
    ("Test 1: Adj → (Adj) weg, Kasus bleiben", success_0 and success_1 and success_2),
    ("Test 2: Adj + Adj_A → beide weg", result2[0]['gr_tokens'][0] == 'Sorōrem'),
    ("Test 3: Nur Adj_N → nur (N) weg", result3[0]['gr_tokens'][0] == 'falsō(Adj)'),
]

for test_name, passed in all_tests:
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"  {status}: {test_name}")

if all(p for _, p in all_tests):
    print("\n🎉 ALLE TESTS BESTANDEN! 🎉")
else:
    print("\n⚠️  EINIGE TESTS FEHLGESCHLAGEN")
