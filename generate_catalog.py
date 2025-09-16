import json
from pathlib import Path

# Definiere das Wurzelverzeichnis des Projekts
ROOT = Path(__file__).parent.resolve()
PDF_ROOT = ROOT / "pdf"
TEXTE_ROOT = ROOT / "texte" # NEU: Pfad zum Texte-Verzeichnis
CATALOG_PATH = ROOT / "catalog.json"

def generate_catalog():
    """
    Durchsucht das 'pdf'-Verzeichnis und generiert eine 'catalog.json'
    basierend auf der gefundenen Ordnerstruktur und den Dateinamen.
    """
    if not PDF_ROOT.is_dir():
        print(f"✗ PDF-Verzeichnis nicht gefunden: {PDF_ROOT}")
        return

    catalog = {"Sprachen": {}}
    
    print(f"🔍 Durchsuche Verzeichnis: {PDF_ROOT}")

    # Ebene 1: Sprachen (z.B. griechisch, latein)
    for lang_dir in [p for p in PDF_ROOT.iterdir() if p.is_dir()]:
        language = lang_dir.name
        catalog["Sprachen"][language] = {}
        print(f"  - Sprache: {language}")

        # Ebene 2: Gattungen (z.B. poesie, prosa)
        for kind_dir in [p for p in lang_dir.iterdir() if p.is_dir()]:
            kind = kind_dir.name
            if kind not in ["poesie", "prosa"]:
                continue
            catalog["Sprachen"][language][kind] = {}
            print(f"    - Gattung: {kind}")

            # Ebene 3: Autoren
            for author_dir in [p for p in kind_dir.iterdir() if p.is_dir()]:
                author = author_dir.name
                catalog["Sprachen"][language][kind][author] = {}
                print(f"      - Autor: {author}")

                # Ebene 4: Werke
                for work_dir in [p for p in author_dir.iterdir() if p.is_dir()]:
                    work = work_dir.name
                    print(f"        - Werk: {work}")

                    # Finde den Basis-Dateinamen im entsprechenden 'texte'-Verzeichnis
                    base_filename = work # Fallback
                    text_work_dir = TEXTE_ROOT / language / kind / author / work
                    if text_work_dir.is_dir():
                        birkenbihl_files = list(text_work_dir.glob("*_birkenbihl.txt"))
                        if birkenbihl_files:
                            base_filename = birkenbihl_files[0].name.replace("_birkenbihl.txt", "")
                            print(f"          ✓ Basis-Dateiname gefunden: {base_filename}")
                        else:
                            print(f"          ⚠ Kein '_birkenbihl.txt' in {text_work_dir} gefunden, verwende Ordnernamen als Fallback.")
                    else:
                        print(f"          ⚠ Text-Verzeichnis {text_work_dir} nicht gefunden.")

                    # Prüfe auf Versmaß-Fähigkeit im 'pdf'-Verzeichnis
                    has_versmass = False
                    pdf_files = list(work_dir.glob("*.pdf"))
                    if not pdf_files:
                        print(f"          ⚠ Kein PDF in {work_dir} gefunden, wird übersprungen.")
                        continue # Nur Werke mit PDFs aufnehmen

                    for pdf_file in pdf_files:
                        if "_Versmaß" in pdf_file.name:
                            has_versmass = True
                            print("          ✓ Versmaß-PDF gefunden.")
                            break
                    
                    # Erstelle den relativen Pfad für die work.html
                    # Format: Sprache/Gattung/Autor/Werk
                    work_path = f"{language}/{kind}/{author}/{work}"
                    
                    catalog["Sprachen"][language][kind][author][work] = {
                        "path": work_path,
                        "versmass": has_versmass,
                        "filename_base": base_filename # NEU: Der exakte Dateiname
                    }

    # Schreibe die neue catalog.json
    try:
        with open(CATALOG_PATH, 'w', encoding='utf-8') as f:
            json.dump(catalog, f, ensure_ascii=False, indent=2)
        print(f"\n✓ 'catalog.json' erfolgreich erstellt in: {CATALOG_PATH}")
    except Exception as e:
        print(f"\n✗ Fehler beim Schreiben von 'catalog.json': {e}")


if __name__ == "__main__":
    generate_catalog()
