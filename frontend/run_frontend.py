import http.server
import socketserver

PORT = 5501
DIRECTORY = "."

class NoCacheHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

with socketserver.TCPServer(("", PORT), NoCacheHTTPRequestHandler) as httpd:
    print(f"Serving at http://localhost:{PORT} with NO-CACHE headers")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
