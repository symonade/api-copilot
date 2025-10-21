import base64
import hashlib
import hmac
import json
import zlib
from typing import List, Dict


def _b64u_encode(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode("ascii").rstrip("=")


def _b64u_decode(s: str) -> bytes:
    pad = '=' * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def pack(transcript: List[Dict], secret: str) -> str:
    data = json.dumps(transcript, separators=(",", ":")).encode("utf-8")
    comp = zlib.compress(data)
    part = _b64u_encode(comp)
    msg = ("v1." + part).encode("utf-8")
    sig = hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).digest()
    return "v1." + part + "." + _b64u_encode(sig)


def unpack(token: str, secret: str) -> List[Dict]:
    if not token.startswith("v1."):
        raise ValueError("unsupported token version")
    try:
        _, data_b64, sig_b64 = token.split(".", 2)
    except ValueError:
        raise ValueError("invalid token format")
    msg = ("v1." + data_b64).encode("utf-8")
    expected = hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).digest()
    got = _b64u_decode(sig_b64)
    if not hmac.compare_digest(expected, got):
        raise ValueError("bad signature")
    raw = _b64u_decode(data_b64)
    data = zlib.decompress(raw)
    transcript = json.loads(data.decode("utf-8"))
    if not isinstance(transcript, list):
        raise ValueError("invalid payload")
    return transcript

