# Ordnerstruktur der Webseite GODLIKE

## Neue Hierarchie (ab November 2025)

Die Ordnerstruktur wurde umorganisiert, um eine zusätzliche Gliederungsebene zwischen Poesie/Prosa und Autoren einzufügen.

### Struktur

```
texte/pdf
├── Sprache (griechisch / latein)
│   ├── Gattung (poesie / prosa)
│   │   ├── KATEGORIE (neu!)
│   │   │   ├── Autor
│   │   │   │   ├── Werk
│   │   │   │   │   └── birkenbihl.txt / PDFs
```

### Kategorien

#### Poesie-Kategorien

1. **Epos** - Epische Dichtung
   - Homer (Ilias, Odyssee, Homerische Hymnen)
   - Hesiod (Theogonie, Werke und Tage)
   - Vergil (Aeneis, Georgica)
   - Apollonios von Rhodos (Argonautika)
   - Lucretius (De rerum natura)

2. **Drama** - Tragödie und Komödie
   - **Griechische Tragödie**: Aischylos, Sophokles, Euripides
   - **Griechische Komödie**: Aristophanes
   - **Römische Komödie**: Plautus, Terentius
   - **Römische Tragödie**: Seneca

3. **Lyrik** - Gefühl, Form, Moment
   - Pindar (Oden)
   - Horaz (Oden, Carmina, Ars poetica)
   - Kallimachos (Hymnen)
   - Theokrit (Idyllen)
   - Ovid (Amores, Metamorphosen)
   - Juvenal (Satiren)

#### Prosa-Kategorien

1. **Philosophie_Rhetorik** - Philosophische und rhetorische Werke
   - Platon (Dialoge, Politeia, Nomoi)
   - Aristoteles (Metaphysik, Ethik, Politik, Rhetorik, Poetik)
   - Cicero (De officiis, De oratore, De re publica)
   - Seneca (Epistulae morales ad Lucilium)
   - Lukian (Vera Historia)
   - Lysias (Gerichtsreden)

2. **Historie** - Geschichtsschreibung und Biographien
   - Herodot (Historien)
   - Thukydides (Der peloponnesische Krieg)
   - Caesar (De bello Gallico, De bello civili)
   - Livius (Ab urbe condita)
   - Tacitus (Historiae, Germania)
   - Demosthenes (Über die Krone)
   - Plutarch (Biographien: Caesar, Cicero, Alexander, etc.)
   - Xenophon (Anabasis, Kyrupaideia, Memorabilien)

### Besonderheiten

- **Seneca** erscheint zweimal:
  - In `poesie/Drama/Seneca` für seine Tragödien
  - In `prosa/Philosophie_Rhetorik/Seneca` für seine philosophischen Briefe

### Spiegelung

Die Ordnerstruktur ist **spiegelidentisch** in folgenden Verzeichnissen:

1. `texte/` - Eingabedateien (birkenbihl.txt)
2. `pdf/` - Ausgabe-PDFs
3. `texte_drafts/` - Entwürfe für Texte
4. `pdf_drafts/` - Entwürfe für PDFs

### PDF-Builder

Die vier PDF-Builder wurden angepasst, um die neue Struktur zu unterstützen:

- `lat_build_poesie_adapter.py` - Lateinische Poesie
- `gr_build_poesie_adapter.py` - Griechische Poesie
- `lat_build_prosa_adapter.py` - Lateinische Prosa
- `gr_build_prosa_adapter.py` - Griechische Prosa

Alle Builder extrahieren automatisch:
- Kategorie (z.B. "Epos", "Drama", "Lyrik", "Philosophie_Rhetorik", "Historie")
- Autor
- Werk

Und erstellen die entsprechenden Ordner in `pdf/`, `texte_drafts/` und `pdf_drafts/`.

## Migration

Die Migration wurde am 11. November 2025 durchgeführt mit dem Skript `restructure_folders.py`.

Alle Texte und PDFs wurden erfolgreich in die neue Struktur verschoben, ohne Datenverlust.

