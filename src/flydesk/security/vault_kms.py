# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""HashiCorp Vault Transit secrets engine provider."""

from __future__ import annotations

import base64
import logging

logger = logging.getLogger(__name__)


class VaultKMSProvider:
    """Encrypt/decrypt using HashiCorp Vault Transit secrets engine.

    Requires ``hvac`` (install with ``pip install flydesk[vault]``).
    """

    def __init__(
        self,
        url: str,
        token: str,
        transit_key: str = "flydesk",
        mount_point: str = "transit",
    ) -> None:
        import hvac

        self._client = hvac.Client(url=url, token=token)
        self._key = transit_key
        self._mount = mount_point

    def encrypt(self, plaintext: str) -> str:
        b64 = base64.b64encode(plaintext.encode("utf-8")).decode("ascii")
        result = self._client.secrets.transit.encrypt_data(
            name=self._key,
            plaintext=b64,
            mount_point=self._mount,
        )
        return result["data"]["ciphertext"]

    def decrypt(self, ciphertext: str) -> str:
        result = self._client.secrets.transit.decrypt_data(
            name=self._key,
            ciphertext=ciphertext,
            mount_point=self._mount,
        )
        return base64.b64decode(result["data"]["plaintext"]).decode("utf-8")
