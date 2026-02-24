# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""GCP Cloud KMS provider for encrypting/decrypting secrets."""

from __future__ import annotations

import base64
import logging

logger = logging.getLogger(__name__)


class GCPKMSProvider:
    """Encrypt/decrypt using Google Cloud KMS.

    Requires ``google-cloud-kms`` (install with ``pip install flydesk[gcp-kms]``).
    """

    def __init__(self, key_name: str) -> None:
        from google.cloud import kms

        self._client = kms.KeyManagementServiceClient()
        self._key_name = key_name

    def encrypt(self, plaintext: str) -> str:
        response = self._client.encrypt(
            request={"name": self._key_name, "plaintext": plaintext.encode("utf-8")},
        )
        return base64.b64encode(response.ciphertext).decode("ascii")

    def decrypt(self, ciphertext: str) -> str:
        response = self._client.decrypt(
            request={"name": self._key_name, "ciphertext": base64.b64decode(ciphertext)},
        )
        return response.plaintext.decode("utf-8")
