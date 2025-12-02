#!/usr/bin/env python3
"""
Test-Skript für die Einrückungs-Logik bei gestaffelten Zeilen.
Simuliert die cum_width_by_base Berechnung.
"""

def _is_staggered_label(label_str):
    """Prüft, ob ein Label ein gestaffeltes Suffix hat (a-g)."""
    if not label_str or len(label_str) < 3:
        return False
    if not (label_str.startswith("(") and label_str.endswith(")")):
        return False
    char_before_closing = label_str[-2]
    return char_before_closing in "abcdefg"

def test_staggered_logic():
    """Simuliert die Zeilen-Verarbeitung."""
    
    # Simulierte Zeilen mit Labels
    lines = [
        {"label": "(17)", "speaker": "AJAX", "token_width": 100.0, "speaker_width": 20.0},
        {"label": "(18)", "speaker": "ODYSSEUS", "token_width": 120.0, "speaker_width": 25.0},
        {"label": "(18a)", "speaker": "", "token_width": 80.0, "speaker_width": 0.0},
        {"label": "(18b)", "speaker": "", "token_width": 90.0, "speaker_width": 0.0},
        {"label": "(19)", "speaker": "AJAX", "token_width": 110.0, "speaker_width": 20.0},
    ]
    
    cum_width_by_base = {}
    
    print("=" * 80)
    print("SIMULATION: Gestaffelte Zeilen - Einrückungs-Logik")
    print("=" * 80)
    
    for i, line in enumerate(lines):
        label = line["label"]
        speaker = line["speaker"]
        token_width = line["token_width"]
        speaker_width = line["speaker_width"]
        
        # Basis-Nummer extrahieren
        if label.startswith("(") and label.endswith(")"):
            inner = label[1:-1]
            # Entferne Suffix (a-g) falls vorhanden
            if inner and inner[-1] in "abcdefg":
                base_num = inner[:-1]
            else:
                base_num = inner
        else:
            base_num = None
        
        # Prüfe ob gestaffelt
        is_staggered = _is_staggered_label(label)
        
        # Berechne Einrückung (nur für gestaffelte Zeilen)
        indent_pt = 0.0
        if is_staggered and base_num:
            indent_pt = cum_width_by_base.get(base_num, 0.0)
        
        print(f"\n[Zeile {i+1}] Label: {label:8s} | Basis: {base_num:4s} | Gestaffelt: {is_staggered}")
        print(f"  Sprecher: {speaker:15s} | Speaker-Breite: {speaker_width:6.1f}")
        print(f"  Token-Breite: {token_width:6.1f}")
        print(f"  Einrückung: {indent_pt:6.1f} (gelesen aus cum_width_by_base[{base_num}])")
        
        # UPDATE cum_width_by_base (NEUE LOGIK: immer für die NÄCHSTE Zeile)
        # Dies passiert am ENDE der Verarbeitung dieser Zeile
        if base_num:
            # NEUE Logik: IMMER updaten (nicht nur für gestaffelte Zeilen!)
            total_width = token_width + speaker_width
            cum_width_by_base[base_num] = cum_width_by_base.get(base_num, 0.0) + total_width
            print(f"  → UPDATE cum_width_by_base[{base_num}] = {cum_width_by_base[base_num]:.1f}")
        
        print(f"  Aktueller Stand cum_width_by_base: {dict(cum_width_by_base)}")

if __name__ == "__main__":
    test_staggered_logic()
