#!/usr/bin/env python3
"""
Test für die DEFENSIVE Übersetzungs-Ausblendungs-Logik.

REGEL: Übersetzung wird NUR ausgeblendet wenn ALLE Tags des Tokens auf "hideTranslation" stehen.
Solange mindestens EIN Tag noch sichtbar sein will → Übersetzung bleibt!
"""

import sys
sys.path.insert(0, '/media/tobias/New Volume/birkenbihl-site')

from shared.preprocess import apply_tag_visibility

# Test-Daten
test_blocks = [
    {
        'type': 'pair',
        'gr_tokens': [
            'Sorōrem(Adj)(A)',      # Token mit 2 Tags
            'falsō(Adj)(N)',        # Token mit 2 Tags
            'meretrīculae(Adj)(G)', # Token mit 2 Tags
            'Pamphilus(N)',         # Token mit nur 1 Tag
        ],
        'de_tokens': ['Schwester', 'irrtümlich', 'Prostituierte', 'Pamphilus'],
        'en_tokens': ['sister', 'falsely', 'prostitute', 'Pamphilus'],
        'token_meta': [{}, {}, {}, {}],
    }
]

print("=" * 80)
print("TEST 1: Nur Adj-Gruppenanführer auf 'hideTranslation'")
print("=" * 80)
print("Token: Sorōrem(Adj)(A), falsō(Adj)(N), meretrīculae(Adj)(G)")
print("Config: 'adj' auf hideTranslation")
print("ERWARTET: Übersetzungen bleiben, weil (A), (N), (G) noch sichtbar sein wollen!")
print()

tag_config_1 = {
    'adj': {
        'hideTranslation': True,
    }
}

import copy
test_1 = copy.deepcopy(test_blocks)
result_1 = apply_tag_visibility(test_1, tag_config_1)

print("ERGEBNIS:")
for i, (de, en) in enumerate(zip(result_1[0]['de_tokens'], result_1[0]['en_tokens'])):
    orig_de = test_blocks[0]['de_tokens'][i]
    orig_en = test_blocks[0]['en_tokens'][i]
    status = "✅ BLEIBT" if de == orig_de else "❌ GELÖSCHT"
    print(f"  Token {i}: DE='{de}' EN='{en}' {status}")

all_kept = all(
    result_1[0]['de_tokens'][i] == test_blocks[0]['de_tokens'][i] 
    for i in range(len(test_blocks[0]['de_tokens']))
)

if all_kept:
    print("\n✅ TEST 1 BESTANDEN: Alle Übersetzungen bleiben!")
else:
    print("\n❌ TEST 1 FEHLGESCHLAGEN: Übersetzungen wurden gelöscht!")

print("\n" + "=" * 80)
print("TEST 2: Adj-Gruppenanführer UND alle Kasus-Tags auf 'hideTranslation'")
print("=" * 80)
print("Token: Sorōrem(Adj)(A), falsō(Adj)(N), meretrīculae(Adj)(G)")
print("Config: 'adj', 'adj_A', 'adj_N', 'adj_G' ALLE auf hideTranslation")
print("ERWARTET: Übersetzungen werden gelöscht, weil ALLE Tags ausgeblendet!")
print()

tag_config_2 = {
    'adj': {'hideTranslation': True},
    'adj_A': {'hideTranslation': True},
    'adj_N': {'hideTranslation': True},
    'adj_G': {'hideTranslation': True},
}

test_2 = copy.deepcopy(test_blocks)
result_2 = apply_tag_visibility(test_2, tag_config_2)

print("ERGEBNIS:")
for i in range(3):  # Nur die ersten 3 (mit Adj)
    de = result_2[0]['de_tokens'][i]
    en = result_2[0]['en_tokens'][i]
    status = "✅ GELÖSCHT" if de == '' else "❌ BLEIBT"
    print(f"  Token {i}: DE='{de}' EN='{en}' {status}")

all_hidden = all(
    result_2[0]['de_tokens'][i] == '' and result_2[0]['en_tokens'][i] == ''
    for i in range(3)
)

if all_hidden:
    print("\n✅ TEST 2 BESTANDEN: Alle Übersetzungen gelöscht (alle Tags ausgeblendet)!")
else:
    print("\n❌ TEST 2 FEHLGESCHLAGEN: Übersetzungen sollten gelöscht sein!")

print("\n" + "=" * 80)
print("TEST 3: Nur spezifischer Kasus (adj_A) auf 'hideTranslation'")
print("=" * 80)
print("Token: Sorōrem(Adj)(A)")
print("Config: 'adj_A' auf hideTranslation, aber NICHT 'adj'")
print("ERWARTET: Übersetzung bleibt, weil (Adj) noch sichtbar sein will!")
print()

tag_config_3 = {
    'adj_A': {'hideTranslation': True},
}

test_3 = copy.deepcopy(test_blocks)
result_3 = apply_tag_visibility(test_3, tag_config_3)

de_0 = result_3[0]['de_tokens'][0]
en_0 = result_3[0]['en_tokens'][0]
status = "✅ BLEIBT" if de_0 == 'Schwester' else "❌ GELÖSCHT"

print(f"ERGEBNIS: Token 0: DE='{de_0}' EN='{en_0}' {status}")

if de_0 == 'Schwester':
    print("\n✅ TEST 3 BESTANDEN: Übersetzung bleibt (Adj-Tag noch sichtbar)!")
else:
    print("\n❌ TEST 3 FEHLGESCHLAGEN: Übersetzung sollte bleiben!")

print("\n" + "=" * 80)
print("TEST 4: Adj UND adj_A beide auf hideTranslation, aber adj_N NICHT")
print("=" * 80)
print("Token: falsō(Adj)(N)")
print("Config: 'adj' und 'adj_A' auf hideTranslation, aber 'adj_N' NICHT")
print("ERWARTET: Übersetzung bleibt, weil (N) noch sichtbar sein will!")
print()

tag_config_4 = {
    'adj': {'hideTranslation': True},
    'adj_A': {'hideTranslation': True},
    # adj_N NICHT auf hideTranslation!
}

test_4 = copy.deepcopy(test_blocks)
result_4 = apply_tag_visibility(test_4, tag_config_4)

de_1 = result_4[0]['de_tokens'][1]  # falsō(Adj)(N)
en_1 = result_4[0]['en_tokens'][1]
status = "✅ BLEIBT" if de_1 == 'irrtümlich' else "❌ GELÖSCHT"

print(f"ERGEBNIS: Token 1: DE='{de_1}' EN='{en_1}' {status}")

if de_1 == 'irrtümlich':
    print("\n✅ TEST 4 BESTANDEN: Übersetzung bleibt (N-Tag nicht auf hide)!")
else:
    print("\n❌ TEST 4 FEHLGESCHLAGEN: Übersetzung sollte bleiben!")

print("\n" + "=" * 80)
print("TEST 5: Token mit nur einem Tag - dieser auf hideTranslation")
print("=" * 80)
print("Token: Pamphilus(N)")
print("Config: 'nomen_N' auf hideTranslation")
print("ERWARTET: Übersetzung wird gelöscht, weil das einzige Tag ausgeblendet!")
print()

tag_config_5 = {
    'nomen_N': {'hideTranslation': True},
}

test_5 = copy.deepcopy(test_blocks)
result_5 = apply_tag_visibility(test_5, tag_config_5)

de_3 = result_5[0]['de_tokens'][3]  # Pamphilus(N)
en_3 = result_5[0]['en_tokens'][3]
status = "✅ GELÖSCHT" if de_3 == '' else "❌ BLEIBT"

print(f"ERGEBNIS: Token 3: DE='{de_3}' EN='{en_3}' {status}")

if de_3 == '':
    print("\n✅ TEST 5 BESTANDEN: Übersetzung gelöscht (einziges Tag ausgeblendet)!")
else:
    print("\n❌ TEST 5 FEHLGESCHLAGEN: Übersetzung sollte gelöscht sein!")

print("\n" + "=" * 80)
print("ZUSAMMENFASSUNG")
print("=" * 80)

all_tests = [
    ("Test 1: Adj hide, Kasus visible → Trans bleibt", all_kept),
    ("Test 2: Alle Tags hide → Trans weg", all_hidden),
    ("Test 3: Nur adj_A hide, Adj visible → Trans bleibt", de_0 == 'Schwester'),
    ("Test 4: Adj+adj_A hide, adj_N visible → Trans bleibt", de_1 == 'irrtümlich'),
    ("Test 5: Einziges Tag hide → Trans weg", de_3 == ''),
]

for test_name, passed in all_tests:
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"  {status}: {test_name}")

if all(p for _, p in all_tests):
    print("\n🎉 ALLE TESTS BESTANDEN! DEFENSIVE LOGIK FUNKTIONIERT! 🎉")
else:
    print("\n⚠️  EINIGE TESTS FEHLGESCHLAGEN")
