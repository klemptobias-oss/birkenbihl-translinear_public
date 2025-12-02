#!/usr/bin/env python3
"""
Test _is_staggered_label Funktion.
"""

def _is_staggered_label(label: str) -> bool:
    """
    Prüft, ob ein Label ein gültiges Suffix für gestaffelte Zeilen hat.
    Nur Suffixe a-g sind erlaubt (h, i, j, etc. sind für andere Zwecke wie Insertions).
    
    Beispiele:
    - "18" -> False (keine Suffix)
    - "18b" -> True (Suffix 'b')
    - "18c" -> True (Suffix 'c')
    - "9i" -> False (Suffix 'i' ist für Insertions)
    - "(18b)" -> True (mit Klammern - backward compatibility)
    """
    if not label or len(label) < 2:
        return False
    
    # Entferne Klammern falls vorhanden (für backward compatibility)
    if label.startswith('(') and label.endswith(')'):
        label = label[1:-1]
    
    # Prüfe ob letztes Zeichen ein Buchstabe ist
    if label and label[-1].isalpha():
        suffix_char = label[-1].lower()
        return suffix_char in 'abcdefg'
    
    return False

# Teste mit verschiedenen Labels
test_labels = ['18', '18b', '18c', '9i', '(18)', '(18b)', '(18c)', '(9i)', '35b', '41a', '90c', '100b']
print('🧪 Test _is_staggered_label:')
for label in test_labels:
    result = _is_staggered_label(label)
    symbol = '✅' if result else '❌'
    print(f'  {symbol} {label:8s} -> {result}')
