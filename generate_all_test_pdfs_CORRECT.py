#!/usr/bin/env python3
"""
Generiert alle Test-PDFs mit dem KORREKTEN build_prosa_drafts_adapter.py Workflow!
"""

import os
import subprocess
import sys

# Test-Dateien
test_files = [
    'testdokument1_apologiartiger_text.txt',
    'testdokument2_2_sprachig_menon.txt',
    'testdokument3_politeia-3-sprachig.txt',
    'testdokument4_politeia3_sprachig_und_2_srpachig.txt',
    'testdokument5_Caesar_Commentarii_de_bello_civil_2_lat_en_translinear_SESSION_5b7b69c4fe719bc5_DRAFT_20251212_194333.txt',
    'testdokument6_Cicero_De_re_publica_3_lat_de_translinear_SESSION_42ba80182c9f69a7_DRAFT_20251212_194423.txt',
    'testdokument7_Platon_Gorgias_gr_de_en_translinear_SESSION_5df245b99388dca5_DRAFT_20251212_195725.txt'
]

def main():
    total_pdfs = len(test_files) * 8  # 8 Varianten pro Datei
    current = 0
    
    print(f"\n{'='*70}")
    print(f"Generiere {total_pdfs} PDFs (7 Dateien × 8 Varianten)")
    print(f"Verwende build_prosa_drafts_adapter.py für korrektes Preprocessing!")
    print(f"{'='*70}\n")
    
    for test_file in test_files:
        if not os.path.exists(test_file):
            print(f"⚠️  Datei nicht gefunden: {test_file}")
            continue
        
        print(f"\n📄 {test_file}")
        print(f"   {'─'*60}")
        
        # Rufe build_prosa_drafts_adapter.py auf
        # Dieser generiert automatisch alle 8 Varianten
        try:
            result = subprocess.run(
                ['python', 'build_prosa_drafts_adapter.py', test_file],
                cwd='/media/tobias/New Volume/birkenbihl-site',
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if result.returncode == 0:
                # Zähle erfolgreich erstellte PDFs
                lines = result.stdout.split('\n')
                pdf_count = sum(1 for line in lines if '✓ PDF →' in line)
                current += pdf_count
                print(f"   ✅ {pdf_count} PDFs erstellt")
            else:
                print(f"   ❌ Fehler: {result.stderr[:100]}")
                
        except subprocess.TimeoutExpired:
            print(f"   ❌ Timeout nach 5 Minuten")
        except Exception as e:
            print(f"   ❌ Fehler: {str(e)}")
    
    print(f"\n{'='*70}")
    print(f"✅ Generierung abgeschlossen! {current} PDFs erstellt.")
    print(f"{'='*70}\n")

if __name__ == '__main__':
    main()
