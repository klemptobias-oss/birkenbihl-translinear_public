#!/usr/bin/env python3
"""
Hilfsskript zur automatischen PDF-Generierung für Entwürfe
Führt die entsprechenden Adapter-Skripte für alle neuen Entwürfe aus
"""

import os
import sys
from pathlib import Path
import subprocess

def find_new_drafts():
    """Finde alle neuen Entwürfe in texte_drafts/"""
    root = Path(__file__).parent
    drafts = []
    
    # Suche in poesie_drafts
    poesie_dir = root / "texte_drafts" / "poesie"
    if poesie_dir.exists():
        for author_dir in poesie_dir.iterdir():
            if author_dir.is_dir():
                for work_dir in author_dir.iterdir():
                    if work_dir.is_dir():
                        for txt_file in work_dir.glob("*.txt"):
                            if "DRAFT" in txt_file.name:
                                drafts.append(("poesie", txt_file))
    
    # Suche in prosa_drafts
    prosa_dir = root / "texte_drafts" / "prosa"
    if prosa_dir.exists():
        for author_dir in prosa_dir.iterdir():
            if author_dir.is_dir():
                for work_dir in author_dir.iterdir():
                    if work_dir.is_dir():
                        for txt_file in work_dir.glob("*.txt"):
                            if "DRAFT" in txt_file.name:
                                drafts.append(("prosa", txt_file))
    
    return drafts

def generate_pdfs_for_draft(kind, draft_file):
    """Generiere PDFs für einen spezifischen Entwurf"""
    root = Path(__file__).parent
    adapter_script = root / f"build_{kind}_drafts_adapter.py"
    
    if not adapter_script.exists():
        print(f"⚠ Adapter-Skript nicht gefunden: {adapter_script}")
        return False
    
    print(f"→ Generiere PDFs für {kind}: {draft_file.name}")
    
    try:
        result = subprocess.run([
            sys.executable, 
            str(adapter_script), 
            str(draft_file)
        ], cwd=str(root), capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"✓ PDFs erfolgreich generiert für {draft_file.name}")
            print(result.stdout)
            return True
        else:
            print(f"✗ Fehler bei PDF-Generierung für {draft_file.name}")
            print(result.stderr)
            return False
            
    except Exception as e:
        print(f"✗ Ausnahmefehler bei {draft_file.name}: {e}")
        return False

def main():
    """Hauptfunktion"""
    print("🔍 Suche nach neuen Entwürfen...")
    
    drafts = find_new_drafts()
    
    if not drafts:
        print("ℹ Keine neuen Entwürfe gefunden.")
        return
    
    print(f"📄 {len(drafts)} Entwürfe gefunden:")
    for kind, draft_file in drafts:
        print(f"  - {kind}: {draft_file}")
    
    print("\n🚀 Starte PDF-Generierung...")
    
    success_count = 0
    for kind, draft_file in drafts:
        if generate_pdfs_for_draft(kind, draft_file):
            success_count += 1
        print()  # Leerzeile zwischen den Entwürfen
    
    print(f"✅ Fertig! {success_count}/{len(drafts)} Entwürfe erfolgreich verarbeitet.")

if __name__ == "__main__":
    main()
