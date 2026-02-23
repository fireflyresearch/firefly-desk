# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Key Management Service abstraction for encrypting and decrypting secrets.

Provides a :class:`KMSProvider` protocol and two implementations:

* :class:`FernetKMSProvider` -- local Fernet encryption (default)
* :class:`NoOpKMSProvider` -- passthrough for dev/testing
"""

from __future__ import annotations

import base64 as _b64
import logging
from typing import Protocol, runtime_checkable

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)

# A deterministic 32-byte key used only in development when no key is configured.
_DEV_FERNET_KEY = _b64.urlsafe_b64encode(b"flydesk-dev-encryption-key-32b!!")


@runtime_checkable
class KMSProvider(Protocol):
    """Key Management Service provider for encrypting/decrypting secrets."""

    def encrypt(self, plaintext: str) -> str:
        """Encrypt *plaintext* and return ciphertext."""
        ...

    def decrypt(self, ciphertext: str) -> str:
        """Decrypt *ciphertext* and return plaintext.

        Raises :class:`ValueError` if decryption fails.
        """
        ...


class FernetKMSProvider:
    """Local Fernet-based KMS implementation.

    Uses the ``cryptography`` library's :class:`~cryptography.fernet.Fernet`
    symmetric encryption.  When no valid key is provided, falls back to a
    static dev-only key (NOT suitable for production).
    """

    def __init__(self, encryption_key: str = "") -> None:
        if encryption_key:
            try:
                self._fernet = Fernet(encryption_key.encode())
                self._is_dev = False
                return
            except (ValueError, Exception):
                logger.warning("Invalid Fernet key; falling back to dev key.")

        self._fernet = Fernet(_DEV_FERNET_KEY)
        self._is_dev = True

    @property
    def is_dev_key(self) -> bool:
        """True if using the static dev key (not suitable for production)."""
        return self._is_dev

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        try:
            return self._fernet.decrypt(ciphertext.encode()).decode()
        except InvalidToken as exc:
            raise ValueError("Decryption failed -- invalid key or corrupted data") from exc


class NoOpKMSProvider:
    """Passthrough KMS that performs no encryption.

    Useful for tests or backward-compatible migration of unencrypted data.
    """

    def encrypt(self, plaintext: str) -> str:
        return plaintext

    def decrypt(self, ciphertext: str) -> str:
        return ciphertext
