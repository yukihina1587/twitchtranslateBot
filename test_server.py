from http.server import SimpleHTTPRequestHandler
import socketserver

PORT = 8787

with socketserver.TCPServer(("localhost", PORT), SimpleHTTPRequestHandler) as httpd:
    print(f"Serving at port {PORT}")
    httpd.serve_forever()
