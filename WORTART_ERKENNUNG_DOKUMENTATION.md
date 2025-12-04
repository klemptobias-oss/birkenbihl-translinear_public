# WORTART-ERKENNUNGS-LOGIK - Vollständige Dokumentation

## Übersicht

Die Funktion `_get_wortart_and_relevant_tags()` in `shared/preprocess.py` (Zeilen 595-665) analysiert die Tags eines Tokens und bestimmt eindeutig die Wortart.

---

## 📋 TAG-DEFINITIONEN (Zeilen 66-82)

### Kasus-Tags (für Deklination):

```python
KASUS_TAGS = {'N', 'G', 'D', 'A', 'V', 'Abl'}
```

- **N** = Nominativ
- **G** = Genitiv
- **D** = Dativ
- **A** = Akkusativ
- **V** = Vokativ
- **Abl** = Ablativ (nur Latein)

### Tempus-Tags (für Verben):

```python
TEMPUS_TAGS = {'Aor', 'Prä', 'Imp', 'AorS', 'Per', 'Plq', 'Fu', 'Fu1', 'Fu2'}
```

- **Prä** = Präsens
- **Imp** = Imperfekt
- **Aor** = Aorist
- **AorS** = Aorist Strong
- **Per** = Perfekt
- **Plq** = Plusquamperfekt
- **Fu** = Futur
- **Fu1/Fu2** = Futur 1/2 (Latein)

### Diathese-Tags (Genus Verbi):

```python
DIATHESE_TAGS = {'Med', 'Pas', 'Akt', 'M/P'}
```

- **Akt** = Aktiv
- **Med** = Medium
- **Pas** = Passiv
- **M/P** = Medium/Passiv

### Modus-Tags:

```python
MODUS_TAGS = {'Inf', 'Op', 'Imv', 'Knj'}
```

- **Inf** = Infinitiv
- **Op** = Optativ
- **Imv** = Imperativ
- **Knj** = Konjunktiv

### Lateinische Verbformen:

```python
LATEINISCHE_VERBFORMEN = {'Ger', 'Gdv', 'Spn'}
```

- **Ger** = Gerundium
- **Gdv** = Gerundivum
- **Spn** = Supinum

---

## 🎯 WORTART-IDENTIFIER-TAGS (Zeilen 70-79)

Diese Tags identifizieren eine Wortart **eindeutig**:

```python
WORTART_IDENTIFIER_TAGS = {
    'Adj': 'adjektiv',     # Adjektiv-Tag
    'Adv': 'adverb',       # Adverb-Tag
    'Pr': 'pronomen',      # Pronomen-Tag
    'Art': 'artikel',      # Artikel-Tag
    'Prp': 'prp',          # Präposition
    'Kon': 'kon',          # Konjunktion
    'Pt': 'pt',            # Partikel
    'ij': 'ij'             # Interjektion
}
```

**WICHTIG:** `Kon`, `Pt` und `Prp` werden **nur** als Wortart erkannt, wenn sie das **EINZIGE** Tag sind!

- ❌ `tribuendoque(Abl)(Kon)(Ger)` → Verb (Ger + Abl)
- ✅ `καί(Kon)` → Konjunktion
- ❌ `ἐν(Prp)(D)` → Nomen (D bleibt, Prp ignoriert)
- ✅ `ἐν(Prp)` → Präposition

---

## 🔍 ERKENNUNGS-ALGORITHMUS (3 Stufen)

### **Stufe 1: Eindeutige Identifier prüfen** (Zeilen 606-622)

```python
# Spezialfall: Kon, Pt und Prp nur wenn alleine
if has_ignorable and len(token_tags) > 1:
    # Prüfe andere Tags (ohne Kon/Pt/Prp)
    for tag, wortart in WORTART_IDENTIFIER_TAGS.items():
        if tag not in ignorable_tags and tag in token_tags:
            return wortart, token_tags
```

**Beispiele:**

- `falsō(Adj)(N)` → **'adjektiv'** (wegen Adj-Tag)
- `αὐτός(Pr)(N)` → **'pronomen'** (wegen Pr-Tag)
- `ὁ(Art)(N)` → **'artikel'** (wegen Art-Tag)
- `καλῶς(Adv)` → **'adverb'** (wegen Adv-Tag)

---

### **Stufe 2: Komplexe Fälle (Nomen, Verb, Partizip)** (Zeilen 624-650)

**2.1) PARTIZIP erkennen:**

```python
if hat_kasus and hat_tempus:
    return 'partizip', token_tags
```

**Regel:** Kasus-Tag **UND** Tempus-Tag → **PARTIZIP**

**Beispiele:**

- `λέγων(Prä)(Akt)(N)` → **'partizip'** (Prä = Tempus, N = Kasus)
- `λελυκώς(Per)(Akt)(N)` → **'partizip'** (Per = Tempus, N = Kasus)

---

**2.2) VERB erkennen:**

```python
if hat_tempus and not hat_kasus:
    return 'verb', token_tags

if hat_modus and not hat_kasus:
    return 'verb', token_tags

if hat_lat_verbform:
    return 'verb', token_tags
```

**Regel 1:** Tempus-Tag **OHNE** Kasus → **VERB**

- `λέγει(Prä)(Akt)` → **'verb'** (Prä, aber kein Kasus)

**Regel 2:** Modus-Tag **OHNE** Kasus → **VERB**

- `λέγειν(Inf)(Akt)` → **'verb'** (Inf = Modus)
- `λέγε(Imv)(Akt)` → **'verb'** (Imv = Modus)

**Regel 3:** Lateinische Verbform (Ger/Gdv/Spn) → **VERB**

- `amandi(Ger)(G)` → **'verb'** (Ger = Gerundium)
- `amandus(Gdv)(N)` → **'verb'** (Gdv = Gerundivum)
- `cogitandiqueGKonGer` → **'verb'** (Ger vorhanden)

---

**2.3) NOMEN erkennen:**

```python
if hat_kasus and not hat_tempus:
    tags_ohne_ignorable = token_tags - {'Kon', 'Pt', 'Du', 'Prp'}
    if tags_ohne_ignorable and all(t in KASUS_TAGS for t in tags_ohne_ignorable):
        return 'nomen', token_tags
```

**Regel:** Kasus-Tag **OHNE** Tempus, **und ALLE** verbleibenden Tags sind Kasus → **NOMEN**

**Beispiele:**

- `ἄνθρωπος(N)` → **'nomen'** (nur Kasus-Tag)
- `ἀνθρώπου(G)` → **'nomen'** (nur Kasus-Tag)
- `MīlesneNPt` → **'nomen'** (N bleibt nach Entfernung von Pt)
- `sollertiaqueAblKon` → **'nomen'** (Abl bleibt nach Entfernung von Kon)
- `domoPrpAbl` → **'nomen'** (Abl bleibt nach Entfernung von Prp)

**WICHTIG:** Kon, Pt, Du und Prp werden ignoriert! Sie verhindern **nicht** die Nomen-Erkennung.

---

### **Stufe 3: Standalone-Wortarten** (Zeilen 652-661)

Falls keine Wortart in Stufe 1 oder 2 gefunden wurde:

```python
if 'Kon' in token_tags:
    return 'kon', token_tags
if 'Pt' in token_tags:
    return 'pt', token_tags
if 'Prp' in token_tags:
    return 'prp', token_tags
if 'ij' in token_tags:
    return 'ij', token_tags
```

**Beispiele:**

- `καί(Kon)` → **'kon'** (nur Kon-Tag)
- `δέ(Pt)` → **'pt'** (nur Pt-Tag)
- `ἐν(Prp)` → **'prp'** (nur Prp-Tag)

---

## 📊 ENTSCHEIDUNGSBAUM

```
Token mit Tags: z.B. "λέγων(Prä)(Akt)(N)"
    ↓
1. Hat eindeutiges Identifier-Tag? (Adj, Adv, Pr, Art, Prp, ij)
   ├─ JA → Wortart gefunden!
   └─ NEIN → weiter zu 2
    ↓
2. Komplexe Prüfung:
   ├─ hat_kasus AND hat_tempus → PARTIZIP ✓
   ├─ hat_tempus AND NOT hat_kasus → VERB
   ├─ hat_modus AND NOT hat_kasus → VERB
   ├─ hat_lat_verbform → VERB
   └─ hat_kasus AND NOT hat_tempus AND alle_tags_sind_kasus → NOMEN
    ↓
3. Standalone-Prüfung (Kon, Pt, Prp, ij)
   └─ Falls vorhanden → entsprechende Wortart
    ↓
4. Keine Wortart gefunden → None
```

---

## 🔎 PRAKTISCHE BEISPIELE

### Partizipien:

```
λέγων(Prä)(Akt)(N)         → partizip (Prä + N)
λελυκώς(Per)(Akt)(N)       → partizip (Per + N)
λεγόμενος(Prä)(Pas)(N)     → partizip (Prä + N)
amatus(Per)(Pas)(N)        → partizip (Per + N)
```

### Verben:

```
λέγει(Prä)(Akt)            → verb (Prä, kein Kasus)
ἔλεγε(Imp)(Akt)            → verb (Imp, kein Kasus)
λέγειν(Inf)(Akt)           → verb (Inf = Modus)
λέγε(Imv)(Akt)             → verb (Imv = Modus)
amandi(Ger)(G)             → verb (Ger = lat. Verbform)
amandus(Gdv)(N)            → verb (Gdv = lat. Verbform)
```

### Nomen:

```
ἄνθρωπος(N)                → nomen (nur Kasus)
ἀνθρώπου(G)                → nomen (nur Kasus)
MīlesneNPt                 → nomen (N bleibt, Pt ignoriert)
sollertiaqueAblKon         → nomen (Abl bleibt, Kon ignoriert)
ἵππωDuN                    → nomen (N + Du, beide Kasus)
```

### Adjektive:

```
καλός(Adj)(N)              → adjektiv (Adj-Tag)
καλοῦ(Adj)(G)              → adjektiv (Adj-Tag)
bonus(Adj)(N)              → adjektiv (Adj-Tag)
```

### Pronomen:

```
αὐτός(Pr)(N)               → pronomen (Pr-Tag)
τις(Pr)(N)                 → pronomen (Pr-Tag)
```

### Artikel:

```
ὁ(Art)(N)                  → artikel (Art-Tag)
τοῦ(Art)(G)                → artikel (Art-Tag)
```

### Konjunktionen/Partikeln/Präpositionen (nur wenn allein):

```
καί(Kon)                   → kon (allein)
δέ(Pt)                     → pt (allein)
ἐν(Prp)                    → prp (allein)
tribuendoque(Abl)(Kon)(Ger) → verb (Ger + Abl, Kon ignoriert)
ἐν(Prp)(D)                 → nomen (D bleibt, Prp ignoriert)
```

---

## 🎨 FÄRBUNG (in Poesie_Code.py)

Die Wortart bestimmt die Färbung im PDF:

```python
COLOR_POS_MAP = {
    'verb': '#0b5',         # Grün
    'partizip': '#a0d',     # Violett
    'nomen': '#d33',        # Rot
    'adjektiv': '#05d',     # Blau
    'gerundium': '#a0d',    # Violett (wie Partizip)
    'gerundivum': '#a0d',   # Violett (wie Partizip)
    'supinum': '#a0d',      # Violett (wie Partizip)
}
```

---

## ⚙️ VERWENDUNG IM CODE

Die Funktion wird in folgenden Kontexten aufgerufen:

1. **Tag-Visibility** (`apply_tag_visibility()`, Zeile 1589):

   ```python
   wortart, _ = _get_wortart_and_relevant_tags(orig_tags)
   ```

   → Bestimmt welche Tags ausgeblendet werden

2. **Translation-Visibility** (`_token_should_hide_translation()`, Zeile 1188):

   ```python
   wortart, _ = _get_wortart_and_relevant_tags(original_tags)
   ```

   → Bestimmt ob Übersetzung ausgeblendet wird

3. **Färbung** (in `Poesie_Code.py` und `Prosa_Code.py`):
   → Bestimmt Hintergrundfarbe des Tokens

---

## 🔧 EDGE CASES

### Gerundium/Gerundivum mit Kon/Pt:

```
cogitandiqueGKonGer   → verb (Ger vorhanden, Kon ignoriert)
obtinendineGPtGer     → verb (Ger vorhanden, Pt ignoriert)
```

### Nomen mit enklitischen Partikeln:

```
MīlesneNPt            → nomen (N bleibt, Pt wird ignoriert)
sollertiaqueAblKon    → nomen (Abl bleibt, Kon wird ignoriert)
domoPrpAbl            → nomen (Abl bleibt, Prp wird ignoriert)
```

### Dual bei Nomen:

```
ἵππωDuN               → nomen (Du wird wie Kasus behandelt)
```

### Fehlerfall (kein Match):

```
unbekannt()           → None (keine Tags)
xyz(ABC)              → None (unbekannte Tags)
```

---

## 📝 ZUSAMMENFASSUNG

**Eindeutige Erkennung durch:**

1. **Identifier-Tags** (Adj, Pr, Art, Adv, Prp, ij) → sofort erkannt
2. **Tag-Kombinationen:**
   - Kasus + Tempus → **Partizip**
   - Tempus ohne Kasus → **Verb**
   - Modus ohne Kasus → **Verb**
   - Lat. Verbform → **Verb**
   - Kasus ohne Tempus → **Nomen**
3. **Standalone** (wenn nichts anderes passt): Kon, Pt, Prp, ij

**Spezialregeln:**

- Kon/Pt/Prp werden bei Mehrfach-Tags ignoriert (außer bei Nomen)
- Du wird wie ein Kasus-Tag behandelt
- Lateinische Verbformen haben Vorrang
