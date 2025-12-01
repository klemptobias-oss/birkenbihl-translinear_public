# 🚨 HideTrans funktioniert nicht in Poesie - TO-DO

## Problem

`(HideTrans)` Tag wird in **Poesie-PDFs nicht erkannt**, funktioniert aber in **Prosa-PDFs**.

## Ursache

**Poesie_Code.py Zeile 1863**:
```python
should_hide_trans = '(HideTrans)' in gr_token or '(hidetrans)' in gr_token.lower()
```

❌ **PROBLEM**: `gr_token` wurde bereits von `preprocess.py` "gereinigt" - der `(HideTrans)` Tag wurde entfernt!

**preprocess.py Zeile 845**:
```python
cleaned_token = cleaned_token.replace('(HideTrans)', '')
```

→ Der Tag existiert **nicht mehr** im Token-String, wenn Poesie_Code.py ihn sieht!

## Warum funktioniert es in Prosa?

**Prosa_Code.py Zeile 2472-2473**:
```python
if hasattr(preprocess, '_token_should_hide_translation'):
    if preprocess._token_should_hide_translation(gr_token, translation_rules):
```

✅ **RICHTIG**: Prosa verwendet `preprocess._token_should_hide_translation()`, die:
1. Tags aus dem Token **extrahiert** (auch wenn String schon cleaned ist)
2. `TRANSLATION_HIDE_TAG` in den **extrahierten** Tags prüft
3. Mit `translation_rules` arbeitet (user-definierte Versteck-Regeln)

## Lösung

### Option 1: Poesie wie Prosa (BESTE Lösung) ✅

**Implementiere `translation_rules` Support in Poesie_Code.py:**

1. **Zeile 1608**: `build_tables_for_pair()` Parameter erweitern:
   ```python
   def build_tables_for_pair(gr_tokens: list[str], de_tokens: list[str] = None,
                             ...
                             translation_rules: dict = None):  # ← NEU
   ```

2. **Zeile 1863**: Ersetze naive String-Prüfung durch preprocess-Funktion:
   ```python
   # ALT (funktioniert nicht):
   should_hide_trans = '(HideTrans)' in gr_token or '(hidetrans)' in gr_token.lower()
   
   # NEU (funktioniert wie Prosa):
   should_hide_trans = False
   if hasattr(preprocess, '_token_should_hide_translation'):
       should_hide_trans = preprocess._token_should_hide_translation(gr_token, translation_rules)
   ```

3. **Zeile 1889**: Gleiches für englische Übersetzungen

4. **Alle Aufrufe von `build_tables_for_pair()`**: `translation_rules` Parameter übergeben

### Option 2: Marker-System (HACK, nicht empfohlen) ⚠️

preprocess.py könnte einen unsichtbaren Marker hinzufügen:
```python
cleaned_token += '__HIDETRANS__'  # Unsichtbar im PDF
```

Dann Poesie:
```python
should_hide_trans = '__HIDETRANS__' in gr_token
```

❌ Problem: Hacky, könnte in PDFs sichtbar werden, unclean

### Option 3: Separate Flags-Liste (KOMPLEX) 🔧

Poesie könnte zusätzlich zur `gr_tokens` Liste eine `hide_trans_flags` Liste bekommen:
```python
gr_tokens = ['πρῶτον', 'μῦθον', ...]
hide_trans_flags = [True, False, ...]  # Parallel-Array
```

❌ Problem: Große Umstrukturierung, viele Funktionen anpassen

## Warum Option 1 die beste ist

- ✅ **Konsistent**: Gleicher Mechanismus wie Prosa
- ✅ **Robust**: Nutzt preprocess.py Infrastructure
- ✅ **Erweiterbar**: `translation_rules` ermöglicht user-definierte Versteck-Regeln
- ✅ **Getestet**: Funktioniert bereits in Prosa
- ✅ **Sauber**: Keine Hacks, keine String-Manipulation

## Implementierungs-Schritte

### 1. Import erweitern (Zeile 26)
```python
from shared.preprocess import (
    remove_tags_from_token, 
    remove_all_tags_from_token, 
    RE_WORD_START,
    _token_should_hide_translation  # ← NEU
)
```

### 2. `build_tables_for_pair()` Signatur (Zeile 1608)
```python
def build_tables_for_pair(
    gr_tokens: list[str], 
    de_tokens: list[str] = None,
    indent_pt: float = 0.0,
    ...
    hide_pipes: bool = False,
    block: dict = None,
    translation_rules: dict = None  # ← NEU
):
```

### 3. HideTrans-Check ersetzen (Zeile 1863, 1889)
```python
# Für DE-Übersetzungen:
for idx, t in enumerate(slice_de):
    gr_token = slice_gr[idx] if idx < len(slice_gr) else ''
    
    # NEU: Verwende preprocess-Funktion
    should_hide_trans = _token_should_hide_translation(gr_token, translation_rules) if translation_rules else False
    
    # DEBUG entfernen (nicht mehr nötig)
    # if should_hide_trans and gr_token:
    #     print(f"🚫 HideTrans erkannt: {gr_token[:50]}")
    
    if not t or should_hide_trans:
        de_cells.append(Paragraph('', token_de_style))
    else:
        # ... normale Verarbeitung
```

### 4. Alle Aufrufe anpassen

Suche nach `build_tables_for_pair(` und füge `translation_rules=translation_rules` hinzu.

**Beispiel (Zeile ~2500)**:
```python
tbl = build_tables_for_pair(
    gr_tokens=b.get('gr_tokens', [])[  :],
    de_tokens=b.get('de_tokens', []),
    ...
    translation_rules=translation_rules  # ← NEU
)
```

### 5. `translation_rules` von oben durchreichen

Die Haupt-Funktion (die `build_tables_for_pair` aufruft) muss `translation_rules` als Parameter haben und durchreichen.

## Testing

Nach der Implementierung:

1. Upload `Demonstration_Poesie_Euripides_Kyklops_gr_de_Entwurf_translinear.txt`
2. Generiere PDF
3. Prüfe Zeilen 3-6: Übersetzungen sollten **leer** sein (HideTrans-Tokens)
4. Prüfe Zeilen 1-2: Übersetzungen sollten **sichtbar** sein (nur HideTags)

## Zeitaufwand

**Geschätzt: 30-45 Minuten**
- Import + Signatur: 5 min
- HideTrans-Check ersetzen: 10 min
- Alle Aufrufe finden und anpassen: 20-30 min
- Testing: 10 min

## Priorität

🔴 **HOCH** - Feature funktioniert nicht, User erwarten konsistentes Verhalten zwischen Poesie und Prosa

## Status

📝 **Dokumentiert** - Bereit für Implementierung

---

**Notizen**:
- Debug-Logs können entfernt werden nach Fix
- preprocess.py ist bereits vollständig - keine Änderungen nötig dort
- Prosa_Code.py ist das Vorbild - Code von dort kopieren!
