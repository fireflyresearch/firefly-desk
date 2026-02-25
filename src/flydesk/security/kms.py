# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Key Management Service abstraction for encrypting and decrypting secrets.

Provides a :class:`KMSProvider` protocol and several implementations:

* :class:`FernetKMSProvider` -- local Fernet encryption (default)
* :class:`NoOpKMSProvider` -- passthrough for dev/testing
* :class:`~flydesk.security.aws_kms.AWSKMSProvider` -- AWS KMS
* :class:`~flydesk.security.gcp_kms.GCPKMSProvider` -- Google Cloud KMS
* :class:`~flydesk.security.azure_kv.AzureKeyVaultProvider` -- Azure Key Vault
* :class:`~flydesk.security.vault_kms.VaultKMSProvider` -- HashiCorp Vault Transit

Use :func:`create_kms_provider` to instantiate the appropriate provider based
on application configuration.
"""

from __future__ import annotations

import base64 as _b64
import logging
from typing import Any, Protocol, runtime_checkable

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


def create_kms_provider(config: Any) -> KMSProvider:
    """Create the appropriate KMS provider based on configuration.

    Reads ``config.kms_provider`` and returns the matching implementation.
    Falls back to :class:`FernetKMSProvider` for unknown values.
    """
    provider_type = getattr(config, "kms_provider", "fernet")

    if provider_type == "noop":
        return NoOpKMSProvider()

    if provider_type == "aws":
        if not getattr(config, "aws_kms_key_arn", ""):
            raise ValueError("FLYDESK_AWS_KMS_KEY_ARN must be set when kms_provider=aws")
        try:
            from flydesk.security.aws_kms import AWSKMSProvider
        except ImportError as exc:
            raise ImportError(
                "AWS KMS provider requires boto3. Install with: pip install flydesk[aws-kms]"
            ) from exc
        return AWSKMSProvider(
            key_arn=config.aws_kms_key_arn,
            region=getattr(config, "aws_kms_region", ""),
        )

    if provider_type == "gcp":
        if not getattr(config, "gcp_kms_key_name", ""):
            raise ValueError("FLYDESK_GCP_KMS_KEY_NAME must be set when kms_provider=gcp")
        try:
            from flydesk.security.gcp_kms import GCPKMSProvider
        except ImportError as exc:
            raise ImportError(
                "GCP KMS provider requires google-cloud-kms. "
                "Install with: pip install flydesk[gcp-kms]"
            ) from exc
        return GCPKMSProvider(key_name=config.gcp_kms_key_name)

    if provider_type == "azure":
        if not getattr(config, "azure_vault_url", "") or not getattr(config, "azure_key_name", ""):
            raise ValueError(
                "FLYDESK_AZURE_VAULT_URL and FLYDESK_AZURE_KEY_NAME must be set "
                "when kms_provider=azure"
            )
        try:
            from flydesk.security.azure_kv import AzureKeyVaultProvider
        except ImportError as exc:
            raise ImportError(
                "Azure KMS provider requires azure-keyvault-keys and azure-identity. "
                "Install with: pip install flydesk[azure-kms]"
            ) from exc
        return AzureKeyVaultProvider(
            vault_url=config.azure_vault_url,
            key_name=config.azure_key_name,
        )

    if provider_type == "vault":
        if not getattr(config, "vault_url", "") or not getattr(config, "vault_token", ""):
            raise ValueError(
                "FLYDESK_VAULT_URL and FLYDESK_VAULT_TOKEN must be set "
                "when kms_provider=vault"
            )
        try:
            from flydesk.security.vault_kms import VaultKMSProvider
        except ImportError as exc:
            raise ImportError(
                "Vault KMS provider requires hvac. Install with: pip install flydesk[vault]"
            ) from exc
        return VaultKMSProvider(
            url=config.vault_url,
            token=config.vault_token,
            transit_key=getattr(config, "vault_transit_key", "flydesk"),
            mount_point=getattr(config, "vault_mount_point", "transit"),
        )

    # Default: Fernet
    if provider_type != "fernet":
        logger.warning("Unknown kms_provider=%r; falling back to Fernet.", provider_type)
    return FernetKMSProvider(config.credential_encryption_key)
