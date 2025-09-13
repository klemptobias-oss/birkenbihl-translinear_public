#!/usr/bin/env python3
"""
Lokaler Worker-Server für PDF-Rendering
"""

import os
import json
import tempfile
import subprocess
from pathlib import Path
from flask import Flask, request, jsonify, send_file
from werkzeug.utils import secure_filename

app = Flask(__name__)

# Konfiguration
UPLOAD_FOLDER = 'temp_uploads'
ALLOWED_EXTENSIONS = {'txt'}

# Erstelle Upload-Ordner
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/render', methods=['POST'])
def render_pdf():
    try:
        # Prüfe ob Datei vorhanden ist
        if 'file' not in request.files:
            return jsonify({'ok': False, 'error': 'Keine Datei hochgeladen'}), 400
        
        file = request.files['file']
        if file.filename == '' or not allowed_file(file.filename):
            return jsonify({'ok': False, 'error': 'Ungültige Datei'}), 400
        
        # Lade Optionen
        options_str = request.form.get('options', '{}')
        try:
            options = json.loads(options_str)
        except json.JSONDecodeError:
            return jsonify({'ok': False, 'error': 'Ungültige Optionen'}), 400
        
        # Speichere Datei temporär
        filename = secure_filename(file.filename)
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(file_path)
        
        # Extrahiere Parameter
        kind = options.get('kind', 'poesie')
        author = options.get('author', 'Unbekannt')
        work = options.get('work', 'Unbekannt')
        tag_config = options.get('tag_config', {})
        
        # Erstelle Tag-Config-Datei
        tag_config_file = None
        if tag_config:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                json.dump(tag_config, f)
                tag_config_file = f.name
        
        try:
            # Rufe entsprechendes Adapter-Skript auf
            if kind == 'poesie':
                cmd = ['python3', 'build_poesie_drafts_adapter.py', file_path]
            else:
                cmd = ['python3', 'build_prosa_drafts_adapter.py', file_path]
            
            if tag_config_file:
                cmd.extend(['--tag-config', tag_config_file])
            
            # Führe Skript aus
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=os.getcwd())
            
            if result.returncode != 0:
                return jsonify({
                    'ok': False, 
                    'error': f'PDF-Erstellung fehlgeschlagen: {result.stderr}'
                }), 500
            
            # Finde erstellte PDF-Datei
            # Das Adapter-Skript sollte die PDF-Datei im pdf_drafts Ordner erstellen
            pdf_path = f"pdf_drafts/{kind}_drafts/{author}/{work}"
            pdf_files = list(Path(pdf_path).glob("*.pdf"))
            
            if not pdf_files:
                return jsonify({
                    'ok': False, 
                    'error': 'PDF-Datei nicht gefunden'
                }), 500
            
            # Verwende die erste gefundene PDF-Datei
            pdf_file = pdf_files[0]
            
            # Erstelle relative URL für den Browser
            pdf_url = f"/pdf_drafts/{kind}_drafts/{author}/{work}/{pdf_file.name}"
            
            return jsonify({
                'ok': True,
                'pdf_url': pdf_url,
                'message': 'PDF erfolgreich erstellt'
            })
            
        finally:
            # Aufräumen
            if os.path.exists(file_path):
                os.remove(file_path)
            if tag_config_file and os.path.exists(tag_config_file):
                os.remove(tag_config_file)
                
    except Exception as e:
        return jsonify({
            'ok': False, 
            'error': f'Server-Fehler: {str(e)}'
        }), 500

@app.route('/pdf_drafts/<path:filename>')
def serve_pdf(filename):
    """Serviere PDF-Dateien aus dem pdf_drafts Ordner"""
    pdf_path = os.path.join('pdf_drafts', filename)
    if os.path.exists(pdf_path):
        return send_file(pdf_path, as_attachment=False)
    else:
        return jsonify({'error': 'PDF nicht gefunden'}), 404

if __name__ == '__main__':
    print("Starte lokalen Worker-Server auf Port 5000...")
    print("Verfügbare Endpoints:")
    print("  POST /render - PDF-Rendering")
    print("  GET /pdf_drafts/<path> - PDF-Dateien servieren")
    app.run(host='0.0.0.0', port=5000, debug=True)
