# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""AWS KMS provider for encrypting/decrypting secrets via AWS Key Management Service."""

from __future__ import annotations

import base64
import logging

logger = logging.getLogger(__name__)


class AWSKMSProvider:
    """Encrypt/decrypt using AWS KMS.

    Requires ``boto3`` (install with ``pip install flydesk[aws-kms]``).
    """

    def __init__(self, key_arn: str, region: str = "") -> None:
        import boto3

        kwargs: dict = {}
        if region:
            kwargs["region_name"] = region
        self._client = boto3.client("kms", **kwargs)
        self._key_arn = key_arn

    def encrypt(self, plaintext: str) -> str:
        resp = self._client.encrypt(
            KeyId=self._key_arn,
            Plaintext=plaintext.encode("utf-8"),
        )
        return base64.b64encode(resp["CiphertextBlob"]).decode("ascii")

    def decrypt(self, ciphertext: str) -> str:
        resp = self._client.decrypt(
            CiphertextBlob=base64.b64decode(ciphertext),
        )
        return resp["Plaintext"].decode("utf-8")
