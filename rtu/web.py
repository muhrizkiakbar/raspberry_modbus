from http.server import HTTPServer, BaseHTTPRequestHandler
import ssl
import json
import logging
from auth import AuthenticationSystem


class SecureRequestHandler(BaseHTTPRequestHandler):
    def __init__(self, config, db, auth_system, *args):
        self.config = config
        self.db = db
        self.auth_system = auth_system
        super().__init__(*args)

    def do_GET(self):
        if not self._authenticate():
            self._require_auth()
            return

        if self.path == "/data":
            self._send_data()
        elif self.path == "/alarms":
            self._send_alarms()
        else:
            self._send_home()

    def _authenticate(self):
        auth_header = self.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return False

        token = auth_header[7:]
        return bool(self.auth_system.verify_token(token))

    def _require_auth(self):
        self.send_response(401)
        self.send_header("WWW-Authenticate", 'Bearer realm="RTU System"')
        self.end_headers()

    def _send_data(self):
        try:
            data = self.db.get_recent_data(100)
            self._send_json({"status": "success", "data": data})
        except Exception as e:
            self._send_error(str(e))

    def _send_alarms(self):
        try:
            # Implement alarm retrieval
            self._send_json({"alarms": []})
        except Exception as e:
            self._send_error(str(e))

    def _send_home(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(b"<h1>Secure RTU System</h1>")

    def _send_json(self, data):
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def _send_error(self, message):
        self.send_response(500)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"status": "error", "message": message}).encode())


class WebServer:
    def __init__(self, config, db, auth_system):
        self.config = config
        self.db = db
        self.auth_system = auth_system
        self.server = None

    def start(self):
        handler = lambda *args: SecureRequestHandler(
            self.config, self.db, self.auth_system, *args
        )

        self.server = HTTPServer(("", self.config["http_server"]["port"]), handler)

        # if self.config["http_server"]["ssl"]["enabled"]:
        #    self.server.socket = ssl.wrap_socket(
        #        self.server.socket,
        #        keyfile=self.config["http_server"]["ssl"]["keyfile"],
        #        certfile=self.config["http_server"]["ssl"]["certfile"],
        #        server_side=True,
        #    )

        logging.info(
            f"Starting secure web server on port {self.config['http_server']['port']}"
        )
        self.server.serve_forever()
