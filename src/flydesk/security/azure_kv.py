# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Azure Key Vault provider for encrypting/decrypting secrets."""

from __future__ import annotations

import base64
import logging

logger = logging.getLogger(__name__)


class AzureKeyVaultProvider:
    """Encrypt/decrypt using Azure Key Vault keys.

    Requires ``azure-keyvault-keys`` and ``azure-identity``
    (install with ``pip install flydesk[azure-kms]``).
    """

    def __init__(self, vault_url: str, key_name: str) -> None:
        from azure.identity import DefaultAzureCredential
        from azure.keyvault.keys import KeyClient
        from azure.keyvault.keys.crypto import CryptographyClient, EncryptionAlgorithm

        credential = DefaultAzureCredential()
        key_client = KeyClient(vault_url=vault_url, credential=credential)
        key = key_client.get_key(key_name)
        self._crypto = CryptographyClient(key, credential=credential)
        self._algorithm = EncryptionAlgorithm.rsa_oaep_256

    def encrypt(self, plaintext: str) -> str:
        try:
            result = self._crypto.encrypt(self._algorithm, plaintext.encode("utf-8"))
            return base64.b64encode(result.ciphertext).decode("ascii")
        except Exception as exc:
            logger.error("Azure Key Vault encryption failed: %s", exc)
            raise ValueError(f"Azure Key Vault encryption failed: {exc}") from exc

    def decrypt(self, ciphertext: str) -> str:
        try:
            result = self._crypto.decrypt(self._algorithm, base64.b64decode(ciphertext))
            return result.plaintext.decode("utf-8")
        except ValueError:
            raise
        except Exception as exc:
            logger.error("Azure Key Vault decryption failed: %s", exc)
            raise ValueError(f"Azure Key Vault decryption failed: {exc}") from exc
