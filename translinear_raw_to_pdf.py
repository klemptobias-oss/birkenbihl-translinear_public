#!/usr/bin/env python3
"""
Translinear Raw Text to PDF Converter
=====================================
Einfacher Builder, der .txt Dateien 1:1 als PDF ausgibt.
Keine Formatierung, keine Translinear-Logik - nur roher Text wie im Editor.

Usage:
    python translinear_raw_to_pdf.py input.txt [output.pdf]
"""

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import sys
import os

def create_raw_pdf(input_txt: str, output_pdf: str = None):
    """
    Konvertiert eine .txt Datei 1:1 zu PDF.
    
    Args:
        input_txt: Pfad zur Input .txt Datei
        output_pdf: Pfad zur Output .pdf Datei (optional)
    """
    # Output-Pfad generieren falls nicht angegeben
    if output_pdf is None:
        output_pdf = input_txt.replace('.txt', '_RAW.pdf')
    
    # Text-Datei einlesen
    try:
        with open(input_txt, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except FileNotFoundError:
        print(f"❌ Fehler: Datei '{input_txt}' nicht gefunden!")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Fehler beim Lesen der Datei: {e}")
        sys.exit(1)
    
    # PDF erstellen
    c = canvas.Canvas(output_pdf, pagesize=A4)
    width, height = A4
    
    # Schriftart: Courier (monospaced, gut für Code/Text)
    font_name = "Courier"
    font_size = 9
    line_height = font_size + 2
    
    # Ränder
    margin_left = 40
    margin_right = 40
    margin_top = 40
    margin_bottom = 40
    
    # Start-Position (oben links)
    y = height - margin_top
    page_num = 1
    
    # Maximale Zeichen pro Zeile (für Courier 9pt auf A4)
    max_chars_per_line = int((width - margin_left - margin_right) / (font_size * 0.6))
    
    def add_page_number():
        """Fügt Seitenzahl hinzu"""
        c.setFont(font_name, 8)
        c.drawString(width / 2 - 10, margin_bottom - 15, f"– {page_num} –")
        c.setFont(font_name, font_size)
    
    def new_page():
        """Erstellt neue Seite"""
        nonlocal y, page_num
        add_page_number()
        c.showPage()
        page_num += 1
        y = height - margin_top
        c.setFont(font_name, font_size)
    
    # PDF-Metadaten
    c.setTitle(f"Raw Text: {os.path.basename(input_txt)}")
    c.setAuthor("Translinear Raw Builder")
    c.setSubject("Raw Text Export")
    
    # Font setzen
    c.setFont(font_name, font_size)
    
    print(f"📄 Erstelle Raw-PDF: {output_pdf}")
    print(f"   Eingabe: {input_txt}")
    print(f"   Zeilen: {len(lines)}")
    print(f"   Schrift: {font_name} {font_size}pt")
    print(f"   Max. Zeichen/Zeile: {max_chars_per_line}")
    
    # Zeilen verarbeiten
    for line_num, line in enumerate(lines, 1):
        # Newline entfernen (wird manuell behandelt)
        line = line.rstrip('\n\r')
        
        # Lange Zeilen umbrechen
        if len(line) > max_chars_per_line:
            # Zeile in Chunks aufteilen
            chunks = [line[i:i+max_chars_per_line] for i in range(0, len(line), max_chars_per_line)]
            for chunk in chunks:
                # Neue Seite wenn nötig
                if y < margin_bottom + 20:
                    new_page()
                
                c.drawString(margin_left, y, chunk)
                y -= line_height
        else:
            # Normale Zeile
            # Neue Seite wenn nötig
            if y < margin_bottom + 20:
                new_page()
            
            c.drawString(margin_left, y, line)
            y -= line_height
    
    # Letzte Seite abschließen
    add_page_number()
    c.save()
    
    print(f"✅ PDF erfolgreich erstellt!")
    print(f"   Output: {output_pdf}")
    print(f"   Seiten: {page_num}")
    return output_pdf


def main():
    """Hauptfunktion"""
    if len(sys.argv) < 2:
        print("❌ Fehler: Keine Input-Datei angegeben!")
        print()
        print("Usage:")
        print("  python translinear_raw_to_pdf.py input.txt [output.pdf]")
        print()
        print("Beispiel:")
        print("  python translinear_raw_to_pdf.py demo.txt")
        print("  python translinear_raw_to_pdf.py demo.txt output.pdf")
        sys.exit(1)
    
    input_txt = sys.argv[1]
    output_pdf = sys.argv[2] if len(sys.argv) > 2 else None
    
    try:
        create_raw_pdf(input_txt, output_pdf)
    except Exception as e:
        print(f"❌ Fehler beim Erstellen des PDFs: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
