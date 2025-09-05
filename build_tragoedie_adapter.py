from pathlib import Path
import shutil, subprocess, sys

ROOT = Path(__file__).parent.resolve()
TEXTE = ROOT / "texte"
PDF_DIR = ROOT / "pdf"
PDF_DIR.mkdir(exist_ok=True)

# Mapping: Quelle -> Zielname für deinen Code
MAP = {
    "Aias_birkenbihl.txt":        "InputTragödieAias.txt",
    "Trachiniae_birkenbihl.txt":  "InputTragödieTrachiniae.txt",
    "Agamemnon_birkenbihl.txt":   "InputTragödieAgamemnon.txt",
}

# 1) Input-Dateien bereitstellen (Kopie ins Repo-Root)
prepared = []
for src_name, dst_name in MAP.items():
    src = TEXTE / src_name
    dst = ROOT / dst_name
    if not src.exists():
        print(f"⚠ Quelle fehlt (übersprungen): {src}")
        continue
    shutil.copyfile(src, dst)
    prepared.append(dst_name)
    print(f"→ bereitgestellt: {dst_name}")

if not prepared:
    print("✗ Keine Eingaben gefunden – Abbruch.")
    sys.exit(1)

# 2) Deinen Tragödien-Satz ausführen
print("→ Starte Satz (tragoedie_pdf.py)…")
subprocess.check_call([sys.executable, "tragoedie_pdf.py"])

# 3) erzeugte PDFs einsammeln und nach /pdf verschieben
for pdf in ROOT.glob("*.pdf"):
    target = PDF_DIR / pdf.name
    shutil.move(str(pdf), target)
    print(f"✓ PDF → {target}")

print("✓ Fertig.")

