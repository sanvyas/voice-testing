"""Encryption for credentials stored in the database (provider API keys).

Key sources, in order:
  1. LAB_SECRET_KEY (any string of 32+ characters; recommended for containers/Postgres).
  2. A key file `secret.key` created next to a SQLite database file (0600), so a persistent data volume keeps both together.
With neither, saving credentials through the UI is refused; keys can still come from environment variables.
"""
from __future__ import annotations

import base64
import hashlib
import logging
import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger("ai_therapy.lab.secrets")


class SecretBox:
    def __init__(self, fernet_key: bytes, source: str):
        self._fernet = Fernet(fernet_key)
        self.source = source

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, token: str) -> str | None:
        """Return the plaintext, or None if it cannot be decrypted (key changed/lost)."""
        try:
            return self._fernet.decrypt(token.encode()).decode()
        except InvalidToken:
            return None


def _from_passphrase(secret: str) -> bytes:
    return base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest())


def load_box(secret_key: str | None, database_url: str) -> SecretBox | None:
    if secret_key:
        return SecretBox(_from_passphrase(secret_key), "LAB_SECRET_KEY")
    if database_url.startswith("sqlite") and ":memory:" not in database_url:
        db_path = Path(database_url.split("sqlite:///", 1)[-1])
        key_file = db_path.parent / "secret.key"
        key_file.parent.mkdir(parents=True, exist_ok=True)
        if key_file.exists():
            return SecretBox(key_file.read_bytes().strip(), f"file {key_file}")
        key = Fernet.generate_key()
        fd = os.open(key_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as fh:
            fh.write(key)
        logger.info("Created encryption key file %s", key_file)
        return SecretBox(key, f"file {key_file}")
    return None
