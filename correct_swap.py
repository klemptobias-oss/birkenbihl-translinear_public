#!/usr/bin/env python3
"""
Korrektes Vertauschen der Panes:
- Entwurf-Pane muss ZUERST kommen (links)
- PDF-Pane muss DANACH kommen (rechts)
"""

def correct_swap():
    with open('work.html.backup', 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Finde die Start- und End-Zeilen der beiden Panes
    # Suche nach "<!-- PDF" und "<!-- Entwurf"
    
    pdf_start = None
    pdf_end = None
    entwurf_start = None
    entwurf_end = None
    
    pane_depth = 0
    in_pdf = False
    in_entwurf = False
    
    for i, line in enumerate(lines):
        # Finde PDF-Pane Start
        if '<!-- PDF (oben' in line:
            pdf_start = i
            in_pdf = True
            pane_depth = 0
            continue
        
        # Finde Entwurf-Pane Start
        if '<!-- Entwurf' in line and 'PDF' in line:
            entwurf_start = i
            in_entwurf = True
            pane_depth = 0
            continue
        
        # Zähle Pane-Tiefe
        if in_pdf or in_entwurf:
            if '<div class="pane' in line:
                pane_depth += 1
            if '</div>' in line and 'pane' not in line:
                # Prüfe ob es das schließende div des Panes ist
                # Wir suchen nach dem zweiten </div> nach dem pane-body
                pass
        
        # Finde PDF-Pane Ende (nach </div></div> nach pane-body)
        if in_pdf and pdf_start is not None:
            if i > pdf_start + 130 and '</div>' in line and i < pdf_start + 145:
                # Das sollte das schließende </div> des PDF-Panes sein
                if pdf_end is None:
                    pdf_end = i + 1
                    in_pdf = False
        
        # Finde Entwurf-Pane Ende
        if in_entwurf and entwurf_start is not None:
            if i > entwurf_start + 60 and '</div>' in line and i < entwurf_start + 70:
                # Das sollte das schließende </div> des Entwurf-Panes sein
                if entwurf_end is None:
                    entwurf_end = i + 1
                    in_entwurf = False
    
    print(f"PDF-Pane: Zeilen {pdf_start}-{pdf_end}")
    print(f"Entwurf-Pane: Zeilen {entwurf_start}-{entwurf_end}")
    
    if not all([pdf_start, pdf_end, entwurf_start, entwurf_end]):
        print("❌ Konnte nicht alle Panes finden!")
        return
    
    # Extrahiere die Blöcke
    before_pdf = lines[:pdf_start]
    pdf_block = lines[pdf_start:pdf_end]
    between = lines[pdf_end:entwurf_start]
    entwurf_block = lines[entwurf_start:entwurf_end]
    after_entwurf = lines[entwurf_end:]
    
    # Neue Reihenfolge: before + Entwurf + between + PDF + after
    new_lines = before_pdf + entwurf_block + between + pdf_block + after_entwurf
    
    with open('work.html', 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    
    print("✅ Panes korrekt vertauscht!")
    print("   Position 1 (links): Entwurf → PDF")
    print("   Position 2 (rechts): PDF-Ansicht")

if __name__ == '__main__':
    correct_swap()

