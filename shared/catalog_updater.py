import json
from pathlib import Path
import sys

# Füge das übergeordnete Verzeichnis zum PYTHONPATH hinzu, um 'shared' Module zu finden
# Dies ist notwendig, damit das Skript 'shared.versmass' importieren kann
# wenn es von den Build-Adaptern im Hauptverzeichnis aufgerufen wird.
sys.path.append(str(Path(__file__).parent.parent))

from shared.versmass import has_meter_markers

# Definiere den Pfad zur Katalogdatei
CATALOG_PATH = Path(__file__).parent.parent / "catalog.json"

def update_catalog(
    language: str,
    category: str,  # "Poesie" oder "Prosa"
    author: str,
    work: str,
    input_file: Path
) -> None:
    """
    Aktualisiert die catalog.json Datei mit den Informationen eines neuen oder geänderten Werkes.
    Die Struktur ist: Sprache -> Kategorie -> Autor -> Werk.
    """
    try:
        # Lese den Inhalt der Eingabedatei, um auf Versmaß zu prüfen
        with open(input_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Zerlege den Inhalt in Tokens (einfaches Splitting nach Leerzeichen)
        tokens = content.split()
        
        # Prüfe, ob Versmaß-Marker vorhanden sind
        has_versmass = has_meter_markers(tokens)
        
        # Lade die bestehende catalog.json oder erstelle ein leeres Objekt
        if CATALOG_PATH.exists():
            with open(CATALOG_PATH, 'r', encoding='utf-8') as f:
                catalog = json.load(f)
        else:
            catalog = {"Sprachen": {}}
            
        # Stelle sicher, dass die Hierarchie existiert
        if "Sprachen" not in catalog:
            catalog["Sprachen"] = {}
        if language not in catalog["Sprachen"]:
            catalog["Sprachen"][language] = {}
        if category not in catalog["Sprachen"][language]:
            catalog["Sprachen"][language][category] = {}
        if author not in catalog["Sprachen"][language][category]:
            catalog["Sprachen"][language][category][author] = {}
            
        # Erstelle den korrekten, vollständigen relativen Pfad für das Werk.
        # Format: Sprache/Gattung/Autor/Werk
        work_path_parts = [language, category, author, work]
        # Ersetze Leerzeichen und andere problematische Zeichen für URL-Pfade
        safe_work_path_parts = [part.replace(" ", "_") for part in work_path_parts]
        work_path = "/".join(safe_work_path_parts)

        # Füge den Eintrag für das Werk hinzu oder aktualisiere ihn
        catalog["Sprachen"][language][category][author][work] = {
            "path": work_path,
            "versmass": has_versmass
        }
        
        # Schreibe die aktualisierte catalog.json zurück
        with open(CATALOG_PATH, 'w', encoding='utf-8') as f:
            json.dump(catalog, f, ensure_ascii=False, indent=2)
            
        print(f"✓ Katalog aktualisiert für: {language} -> {category} -> {author} -> {work}")

    except Exception as e:
        print(f"✗ Fehler beim Aktualisieren des Katalogs: {e}")

if __name__ == '__main__':
    # Dies ermöglicht das direkte Testen des Skripts
    # Beispielaufruf:
    # python shared/catalog_updater.py Griechisch Poesie Aischylos "Der gefesselte Prometheus" griechisch/texte/poesie/Aischylos/Der_gefesselte_Prometheus/Der_gefesselte_Prometheus_birkenbihl.txt
    if len(sys.argv) == 6:
        lang, cat, auth, wk, file_path = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5]
        update_catalog(lang, cat, auth, wk, Path(file_path))
    else:
        print("Verwendung: python catalog_updater.py <Sprache> <Kategorie> <Autor> <Werk> <Dateipfad>")
