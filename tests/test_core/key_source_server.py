"""A loopback HTTP source for the key source tests: synthetic all-zero key files, served on 127.0.0.1 only.

Not a test module (no ``test_`` prefix). Each test chooses its routes; nothing here reaches the network.
"""
import http.server
import threading
from contextlib import contextmanager

# Synthetic bodies in each console's format. Zero bytes only: no key material anywhere.
AES_KEYS = b"slot0x2CKeyX=" + b"0" * 32 + b"\ncommon0=" + b"0" * 32 + b"\n"
BOOT9 = b"\x00" * 65536   # n3ds reads boot9 only at its full size
SEEDDB = b"\x00" * 128
PROD_KEYS = b"header_key = " + b"0" * 64 + b"\n"
KEYS_BIN = b"\x00" * 1024
BODIES = {
    "3DS/aes_keys.txt": AES_KEYS,
    "3DS/boot9.bin": BOOT9,
    "3DS/Citra/sysdata/seeddb.bin": SEEDDB,
    "Switch/prod.keys": PROD_KEYS,
    "Wii/keys.bin": KEYS_BIN,
}


class _Handler(http.server.BaseHTTPRequestHandler):
    routes = {}   # remote path -> bytes (served), int (an HTTP error code), or a float (seconds to stall)

    def log_message(self, *_args):   # keep the test output quiet
        pass

    def do_GET(self):
        route = self.routes.get(self.path.lstrip("/"))
        if isinstance(route, int):
            self.send_error(route)
        elif isinstance(route, float):
            threading.Event().wait(route)
            self.send_error(503)
        elif route is None:
            self.send_error(404)
        else:
            self.send_response(200)
            self.send_header("Content-Length", str(len(route)))
            self.end_headers()
            self.wfile.write(route)


@contextmanager
def serve_loopback():
    """Yields ``(base address, routes dict)``. Fill the routes before the download; the server stops after the block."""
    routes = {}
    _Handler.routes = routes
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}/", routes
    finally:
        server.shutdown()
        server.server_close()


def serve_all(routes):
    routes.update(BODIES)
