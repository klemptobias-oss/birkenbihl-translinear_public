# Entwurfs-System Anleitung

## 🎯 Überblick

Das System funktioniert in 3 Schritten:

1. **Frontend** → **Worker**: Text wird in `texte_drafts/` gespeichert
2. **Python-Codes**: Generieren PDFs aus `texte_drafts/` → `pdf_drafts/`
3. **Frontend**: Zeigt PDFs aus `pdf_drafts/` an

## 🚀 Setup

### 1. Worker konfigurieren

```bash
# GitHub Token setzen (einmalig)
wrangler secret put GITHUB_TOKEN

# Worker deployen
wrangler deploy
```

### 2. Python-Abhängigkeiten installieren

```bash
pip install reportlab
```

## 📝 Workflow

### Schritt 1: Text speichern

- Gehe zu einer Werkseite (z.B. Aischylos - Der gefesselte Prometheus)
- Wähle "Entwurf" als Quelle
- Klicke "Entwurf jetzt rendern" → "PDFs rendern"
- Text wird automatisch in `texte_drafts/` gespeichert

### Schritt 2: PDFs generieren

Führe einen der folgenden Befehle aus:

```bash
# Für alle neuen Entwürfe (empfohlen)
python generate_draft_pdfs.py

# Für einen spezifischen Entwurf
python build_poesie_drafts_adapter.py texte_drafts/poesie/Aischylos/Der_gefesselte_Prometheus/datei.txt
python build_prosa_drafts_adapter.py texte_drafts/prosa/Platon/Menon/datei.txt
```

### Schritt 3: PDFs anzeigen

- Gehe zurück zur Werkseite
- Wähle "Entwurf" als Quelle
- PDFs werden automatisch aus `pdf_drafts/` geladen

## 📁 Ordnerstruktur

```
texte_drafts/
├── poesie/
│   └── Aischylos/
│       └── Der_gefesselte_Prometheus/
│           └── Der_gefesselte_Prometheus_birkenbihl_DRAFT_20250113_143335.txt
└── prosa/
    └── Platon/
        └── Menon/
            └── Menon_birkenbihl_DRAFT_20250113_143335.txt

pdf_drafts/
├── poesie_drafts/
│   └── Aischylos/
│       └── Der_gefesselte_Prometheus/
│           ├── Der_gefesselte_Prometheus_birkenbihl_Normal_Colour_Tag.pdf
│           ├── Der_gefesselte_Prometheus_birkenbihl_Normal_BlackWhite_Tag.pdf
│           └── ... (12 Varianten)
└── prosa_drafts/
    └── Platon/
        └── Menon/
            ├── Menon_birkenbihl_Normal_Colour_Tag.pdf
            ├── Menon_birkenbihl_Normal_BlackWhite_Tag.pdf
            └── ... (12 Varianten)
```

## 🔧 Fehlerbehebung

### Worker 500-Fehler

- Prüfe: `wrangler secret list` → GITHUB_TOKEN gesetzt?
- Prüfe: GitHub Repository-Zugriff

### PDFs werden nicht generiert

- Prüfe: Python-Abhängigkeiten installiert?
- Prüfe: Dateipfade korrekt?
- Prüfe: `texte_drafts/` Ordner existiert?

### PDFs werden nicht angezeigt

- Prüfe: `pdf_drafts/` Ordner existiert?
- Prüfe: PDF-Dateien wurden generiert?
- Prüfe: Browser-Cache leeren

## 🎨 Tag-Konfiguration

Das System unterstützt erweiterte Tag-Konfigurationen:

- **Hoch-/Tiefstellung**: Tags können hoch- oder tiefgestellt werden
- **Farben**: Rot, Blau, Grün für verschiedene Tag-Typen
- **Verstecken**: Tags können komplett ausgeblendet werden
- **Quick Controls**: Schnelle Einstellungen für Partizipe (blau), Verben (grün), Nomen (rot)

## 📞 Support

Bei Problemen:

1. Prüfe die Browser-Konsole (F12)
2. Prüfe die Python-Ausgabe
3. Prüfe die Worker-Logs: `wrangler tail`
