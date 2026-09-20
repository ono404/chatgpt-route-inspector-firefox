"""Minimal TCP peer that speaks just enough Marionette to be connected to.

Purpose: let a *real* probe process run against a connection this test controls,
so the assertions are made on the commands that actually crossed the socket -
not on an in-process stub's bookkeeping.

It answers anything it receives so the probe can never hang, and records every
command. Answering is deliberately permissive: the point is to observe what the
probe sends, not to imitate Firefox.
"""
import json
import socket
import sys
import threading

sys.dont_write_bytecode = True

GREETING = {"applicationType": "gecko", "marionetteProtocol": 3}


class FakePeer:
    def __init__(self, capabilities):
        self.capabilities = dict(capabilities)
        self.commands = []
        self.connected = 0
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._sock = socket.socket()
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind(("127.0.0.1", 0))
        self._sock.listen(4)
        self._sock.settimeout(0.2)
        self.port = self._sock.getsockname()[1]
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    # -- wire helpers --------------------------------------------------------
    @staticmethod
    def _send(conn, payload):
        data = json.dumps(payload).encode()
        conn.sendall(str(len(data)).encode() + b":" + data)

    @staticmethod
    def _read_frame(conn, buf):
        while b":" not in buf[0]:
            chunk = conn.recv(65536)
            if not chunk:
                raise ConnectionError("eof")
            buf[0] += chunk
        length, rest = buf[0].split(b":", 1)
        size = int(length)
        while len(rest) < size:
            chunk = conn.recv(65536)
            if not chunk:
                raise ConnectionError("eof")
            rest += chunk
        buf[0] = rest[size:]
        return json.loads(rest[:size].decode())

    def _handle(self, conn):
        buf = [b""]
        self._send(conn, GREETING)
        while not self._stop.is_set():
            try:
                message = self._read_frame(conn, buf)
            except Exception:
                return
            if not isinstance(message, list) or len(message) != 4:
                continue
            _channel, msgid, method, params = message
            with self._lock:
                self.commands.append((method, params))
            if method == "WebDriver:NewSession":
                result = {"sessionId": "peer-session", "capabilities": dict(self.capabilities)}
            else:
                result = {"value": None}
            try:
                self._send(conn, [1, msgid, None, result])
            except Exception:
                return

    def _serve(self):
        while not self._stop.is_set():
            try:
                conn, _addr = self._sock.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            with self._lock:
                self.connected += 1
            try:
                self._handle(conn)
            finally:
                try:
                    conn.close()
                except Exception:
                    pass

    # -- inspection ----------------------------------------------------------
    def methods(self):
        with self._lock:
            return [method for method, _params in self.commands]

    def close(self):
        self._stop.set()
        try:
            self._sock.close()
        except Exception:
            pass
