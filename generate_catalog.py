import json
from pathlib import Path

from flachmacher import decide_bucket

# Definiere das Wurzelverzeichnis des Projekts
ROOT = Path(__file__).parent.resolve()
PDF_ROOT = ROOT / "pdf"
TEXTE_ROOT = ROOT / "texte" # NEU: Pfad zum Texte-Verzeichnis
CATALOG_PATH = ROOT / "catalog.json"

LANG_MAP = {
    "griechisch": "GR",
    "latein": "LAT",
}


def sanitize_component(value: str | None) -> str | None:
    if not value:
        return None
    return value.strip().replace(" ", "")


def bucket_to_release_tag(bucket: str | None) -> str:
    if not bucket:
        return "misc-v1"
    base = bucket.lower().replace("__", "_").replace("_", "-")
    return f"{base}-v1"

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

            # Ebene 3: Kategorien (z.B. Epos, Drama, Lyrik, Philosophie_Rhetorik, Historie)
            for category_dir in [p for p in kind_dir.iterdir() if p.is_dir()]:
                category = category_dir.name
                catalog["Sprachen"][language][kind][category] = {}
                print(f"      - Kategorie: {category}")

                # Ebene 4: Autoren
                for author_dir in [p for p in category_dir.iterdir() if p.is_dir()]:
                    author = author_dir.name
                    catalog["Sprachen"][language][kind][category][author] = {}
                    print(f"        - Autor: {author}")

                    # Ebene 5: Werke
                    for work_dir in [p for p in author_dir.iterdir() if p.is_dir()]:
                        work = work_dir.name
                        print(f"          - Werk: {work}")

                        # Finde den Basis-Dateinamen im entsprechenden 'texte'-Verzeichnis
                        # WICHTIG: Wir suchen ZUERST nach der NORMALEN Datei (ohne _Versmaß)
                        base_filename = work # Fallback
                        text_work_dir = TEXTE_ROOT / language / kind / category / author / work
                        if text_work_dir.is_dir():
                            # Suche nach allen birkenbihl.txt Dateien
                            birkenbihl_files = list(text_work_dir.glob("*_birkenbihl.txt"))
                            
                            # Filtere zuerst die OHNE _Versmaß
                            normal_files = [f for f in birkenbihl_files if "_Versmaß" not in f.name]
                            
                            if normal_files:
                                # Nehme die erste normale Datei als Basis
                                base_filename = normal_files[0].name.replace("_birkenbihl.txt", "")
                                print(f"            ✓ Basis-Dateiname gefunden: {base_filename}")
                            elif birkenbihl_files:
                                # Falls nur Versmaß-Dateien existieren, entferne _Versmaß vom Namen
                                base_filename = birkenbihl_files[0].name.replace("_Versmaß_birkenbihl.txt", "").replace("_birkenbihl.txt", "")
                                print(f"            ✓ Basis-Dateiname gefunden (aus Versmaß): {base_filename}")
                            else:
                                print(f"            ⚠ Kein '_birkenbihl.txt' in {text_work_dir} gefunden, verwende Ordnernamen als Fallback.")
                        else:
                            print(f"            ⚠ Text-Verzeichnis {text_work_dir} nicht gefunden.")

                        # Prüfe auf Versmaß-Fähigkeit im 'pdf'-Verzeichnis
                        has_versmass = False
                        pdf_files = list(work_dir.glob("*.pdf"))
                        if not pdf_files:
                            print(f"            ⚠ Kein PDF in {work_dir} gefunden, wird übersprungen.")
                            continue # Nur Werke mit PDFs aufnehmen

                        for pdf_file in pdf_files:
                            if "_Versmaß" in pdf_file.name:
                                has_versmass = True
                                print("            ✓ Versmaß-PDF gefunden.")
                                break

                        # Zusätzliche Metadaten für Releases bestimmen
                        lang_tag = LANG_MAP.get(language.lower(), language.upper())
                        main_genre_s = sanitize_component(kind)
                        subgenre_s = sanitize_component(category)
                        author_s = sanitize_component(author)
                        work_s = sanitize_component(work)
                        orig_stem = pdf_files[0].stem if pdf_files else None

                        bucket = decide_bucket(
                            lang_tag=lang_tag,
                            main_genre=main_genre_s,
                            subgenre=subgenre_s,
                            author=author_s,
                            work=work_s,
                            orig_stem=orig_stem,
                        )

                        meta_parts = [lang_tag]
                        if main_genre_s:
                            meta_parts.append(main_genre_s)
                        if subgenre_s:
                            meta_parts.append(subgenre_s)
                        if author_s:
                            meta_parts.append(author_s)
                        if work_s:
                            meta_parts.append(work_s)
                        meta_prefix = "_".join(filter(None, meta_parts))
                        release_tag = bucket_to_release_tag(bucket)
                        
                        # Erstelle den relativen Pfad für die work.html
                        # Format: Sprache/Gattung/Kategorie/Autor/Werk
                        work_path = f"{language}/{kind}/{category}/{author}/{work}"
                        
                        # Formatiere Autor und Werk für die Anzeige
                        author_display = author.replace("_", " ")
                        work_title = work.replace("_", " ")
                        
                        catalog["Sprachen"][language][kind][category][author][work] = {
                            "path": work_path,
                            "versmass": has_versmass,
                            "filename_base": base_filename, # NEU: Der exakte Dateiname
                            "title": work_title, # NEU: Werk-Titel für Anzeige
                            "author_display": author_display, # NEU: Autor-Name für Anzeige
                            "bucket": bucket,
                            "meta_prefix": meta_prefix,
                            "release_tag": release_tag,
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
