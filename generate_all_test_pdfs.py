#!/usr/bin/env python3
"""
Generiert alle 24 Test-PDFs (3 Dateien × 8 Varianten) im pdf_drafts/unknown Verzeichnis
"""

import os
import sys
import Prosa_Code

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

# Alle 8 Varianten  
variants = [
    ('TAGS', 'COLOR', 'NORMAL'),         # Normal_Colour_Tag
    ('NO_TAGS', 'COLOR', 'NORMAL'),      # Normal_Colour_NoTags
    ('TAGS', 'BLACK_WHITE', 'NORMAL'),   # Normal_BlackWhite_Tag
    ('NO_TAGS', 'BLACK_WHITE', 'NORMAL'),# Normal_BlackWhite_NoTags
    ('TAGS', 'COLOR', 'BOLD_GR'),        # GR_Fett_Colour_Tag
    ('NO_TAGS', 'COLOR', 'BOLD_GR'),     # GR_Fett_Colour_NoTags
    ('TAGS', 'BLACK_WHITE', 'BOLD_GR'),  # GR_Fett_BlackWhite_Tag
    ('NO_TAGS', 'BLACK_WHITE', 'BOLD_GR'),# GR_Fett_BlackWhite_NoTags
]

def main():
    output_dir = '/media/tobias/New Volume/birkenbihl-site/pdf_drafts/unknown/prosa/Unsortiert/Unbenannt'
    os.makedirs(output_dir, exist_ok=True)
    
    total_pdfs = len(test_files) * len(variants)
    current = 0
    
    print(f"\n{'='*70}")
    print(f"Generiere {total_pdfs} PDFs (7 Dateien × 8 Varianten)")
    print(f"Output-Verzeichnis: {output_dir}")
    print(f"{'='*70}\n")
    
    for test_file in test_files:
        if not os.path.exists(test_file):
            print(f"⚠️  Datei nicht gefunden: {test_file}")
            continue
        
        base_name = test_file.replace('.txt', '').replace('testdokument', 'test').replace('_SESSION_', '_S_')
        print(f"\n📄 {test_file}")
        print(f"   {'─'*60}")
        
        for tag_mode, color_mode, strength in variants:
            current += 1
            
            # Bestimme Varianten-Name
            bold = "GR_Fett" if strength == "BOLD_GR" else "Normal"
            color = "Colour" if color_mode == "COLOR" else "BlackWhite"
            tags = "Tag" if tag_mode == "TAGS" else "NoTags"
            variant_name = f"{bold}_{color}_{tags}"
            
            # PDF-Name
            pdf_name = f"{base_name}_{variant_name}.pdf"
            pdf_path = os.path.join(output_dir, pdf_name)
            
            print(f"   [{current:2d}/{total_pdfs}] {variant_name:<35} ", end='', flush=True)
            
            try:
                # Lade und verarbeite Text
                blocks = Prosa_Code.process_input_file(test_file)
                
                # Erstelle PDF
                Prosa_Code.create_pdf(
                    blocks=blocks,
                    pdf_name=pdf_path,
                    tag_mode=tag_mode,
                    color_mode=color_mode,
                    strength=strength,
                    hide_pipes=True,
                    tag_config=None
                )
                
                # Prüfe Größe
                if os.path.exists(pdf_path):
                    size_kb = os.path.getsize(pdf_path) / 1024
                    print(f"✅ {size_kb:6.1f} KB")
                else:
                    print(f"❌ Datei nicht erstellt")
                    
            except Exception as e:
                print(f"❌ Fehler: {str(e)[:50]}")
    
    print(f"\n{'='*70}")
    print(f"✅ Generierung abgeschlossen!")
    print(f"{'='*70}\n")

if __name__ == '__main__':
    main()
