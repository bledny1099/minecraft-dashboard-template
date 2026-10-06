"""Lightweight, pure-Python Minecraft RCON client using standard library sockets."""
import socket
import struct


class RconError(Exception):
    pass


class RconAuthError(RconError):
    pass


def send_rcon_command(host: str, port: int, password: str, cmd: str, timeout: float = 6.0) -> str:
    """Execute a single RCON command synchronously and return server text response."""
    def recv_exact(s: socket.socket, n: int) -> bytes:
        buf = bytearray()
        while len(buf) < n:
            chunk = s.recv(n - len(buf))
            if not chunk:
                raise RconError("RCON connection closed unexpectedly by remote server")
            buf.extend(chunk)
        return bytes(buf)

    def send_pkt(s: socket.socket, pid: int, ptype: int, body: str):
        payload = body.encode("utf-8")
        pkt = struct.pack("<ii", pid, ptype) + payload + b"\x00\x00"
        s.sendall(struct.pack("<i", len(pkt)) + pkt)

    def read_pkt(s: socket.socket):
        raw_len = recv_exact(s, 4)
        (length,) = struct.unpack("<i", raw_len)
        data = recv_exact(s, length)
        pid, ptype = struct.unpack("<ii", data[:8])
        return pid, ptype, data[8:-2].decode("utf-8", errors="replace")

    with socket.create_connection((host, int(port)), timeout=timeout) as sock:
        sock.settimeout(timeout)
        # Type 3: SERVERDATA_AUTH
        send_pkt(sock, 1, 3, password)
        pid, ptype, _ = read_pkt(sock)
        if pid == -1:
            raise RconAuthError("Invalid RCON password")
        
        # Type 2: SERVERDATA_EXECCOMMAND
        send_pkt(sock, 2, 2, cmd)
        _, _, out = read_pkt(sock)
        return out
