#!/usr/bin/env python3
import sys
sys.path.insert(0, '/media/tobias/New Volume/birkenbihl-site')

# Direkter Test: Importiere und verarbeite
from Prosa_Code import process_input_file
import shared.preprocess as preprocess
from prosa_pdf import _get_default_tag_config

# Lade die Test-Datei
input_file = "prosa_test1_apologieartig.txt"

print(f"Lade Datei: {input_file}")
blocks = process_input_file(input_file)

print(f"\n=== NACH process_input_file ===")
print(f"Anzahl Blöcke: {len(blocks)}")

# Finde ersten flow-Block
for i, b in enumerate(blocks):
    if b.get('type') == 'flow':
        print(f"\n=== Flow Block {i} (VOR apply_colors) ===")
        gr_tokens = b.get('gr_tokens', [])[:10]
        print(f"GR tokens (first 10): {gr_tokens}")
        print(f"Farbsymbole in Tokens: {[t for t in gr_tokens if any(sym in str(t) for sym in ['#', '+', '-', '§', '$'])]}")
        break

# Jetzt apply_colors anwenden
tag_config = _get_default_tag_config("GR_FETT")
print(f"\n=== Wende apply_colors an ===")
blocks_with_colors = preprocess.apply_colors(blocks, tag_config, disable_comment_bg=False)

# Prüfe wieder
for i, b in enumerate(blocks_with_colors):
    if b.get('type') == 'flow':
        print(f"\n=== Flow Block {i} (NACH apply_colors) ===")
        gr_tokens = b.get('gr_tokens', [])[:10]
        print(f"GR tokens (first 10): {gr_tokens}")
        print(f"Farbsymbole in Tokens: {[t for t in gr_tokens if any(sym in str(t) for sym in ['#', '+', '-', '§', '$'])]}")
        
        # Prüfe token_meta
        if 'token_meta' in b:
            meta = b.get('token_meta', [])[:10]
            print(f"token_meta (first 10):")
            for j, m in enumerate(meta):
                if m:
                    print(f"  [{j}]: {m}")
        break

print("\n=== FERTIG ===")
