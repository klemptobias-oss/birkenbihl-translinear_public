#!/usr/bin/env python3
"""
Einfacher HTTP-Server für PDF-Rendering-Fallback
"""

import http.server
import socketserver
import json
import os
import subprocess
import tempfile
from urllib.parse import parse_qs
import cgi

class PDFRenderHandler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path == '/render':
            self.handle_render()
        else:
            self.send_error(404, "Not Found")
    
    def handle_render(self):
        try:
            # Parse multipart form data
            content_type = self.headers['Content-Type']
            if not content_type.startswith('multipart/form-data'):
                self.send_error(400, "Bad Request")
                return
            
            # Parse form data
            form = cgi.FieldStorage(
                fp=self.rfile,
                headers=self.headers,
                environ={'REQUEST_METHOD': 'POST'}
            )
            
            # Get file and options
            file_item = form.get('file')
            options_item = form.get('options')
            
            if not file_item or not options_item:
                self.send_error(400, "Missing file or options")
                return
            
            # Parse options
            options = json.loads(options_item.value)
            
            # Create a dummy PDF response
            response = {
                "ok": True,
                "pdf_url": "https://klemptobias-oss.github.io/birkenbihl-translinear_public/pdf/poesie/Aischylos/Der_gefesselte_Prometheus/Der_gefesselte_Prometheus_birkenbihl_Normal_Colour_Tag.pdf",
                "message": "Dummy PDF generiert (lokaler Server)"
            }
            
            # Send response
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type')
            self.end_headers()
            
            self.wfile.write(json.dumps(response).encode())
            
        except Exception as e:
            print(f"Error: {e}")
            self.send_error(500, f"Internal Server Error: {str(e)}")
    
    def do_OPTIONS(self):
        # Handle CORS preflight
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

def run_server(port=5000):
    with socketserver.TCPServer(("", port), PDFRenderHandler) as httpd:
        print(f"Server läuft auf Port {port}")
        print(f"URL: http://localhost:{port}")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServer gestoppt")

if __name__ == "__main__":
    run_server()
