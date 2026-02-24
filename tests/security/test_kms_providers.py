# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Tests for cloud KMS providers and the create_kms_provider factory."""

from __future__ import annotations

import base64
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from flydesk.security.kms import (
    FernetKMSProvider,
    KMSProvider,
    NoOpKMSProvider,
    create_kms_provider,
)


# ---------------------------------------------------------------------------
# Protocol conformance (with mocked SDK imports)
# ---------------------------------------------------------------------------


class TestCloudProviderProtocolConformance:
    """Verify every cloud provider satisfies the KMSProvider protocol."""

    def test_aws_satisfies_protocol(self):
        with patch.dict("sys.modules", {"boto3": MagicMock()}):
            from flydesk.security.aws_kms import AWSKMSProvider

            provider = AWSKMSProvider.__new__(AWSKMSProvider)
            provider._client = MagicMock()
            provider._key_arn = "arn:aws:kms:us-east-1:000:key/abc"
            assert isinstance(provider, KMSProvider)

    def test_gcp_satisfies_protocol(self):
        mock_kms = MagicMock()
        with patch.dict("sys.modules", {"google": MagicMock(), "google.cloud": MagicMock(), "google.cloud.kms": mock_kms}):
            from flydesk.security.gcp_kms import GCPKMSProvider

            provider = GCPKMSProvider.__new__(GCPKMSProvider)
            provider._client = MagicMock()
            provider._key_name = "projects/p/locations/l/keyRings/kr/cryptoKeys/ck"
            assert isinstance(provider, KMSProvider)

    def test_azure_satisfies_protocol(self):
        mock_modules = {
            "azure": MagicMock(),
            "azure.identity": MagicMock(),
            "azure.keyvault": MagicMock(),
            "azure.keyvault.keys": MagicMock(),
            "azure.keyvault.keys.crypto": MagicMock(),
        }
        with patch.dict("sys.modules", mock_modules):
            from flydesk.security.azure_kv import AzureKeyVaultProvider

            provider = AzureKeyVaultProvider.__new__(AzureKeyVaultProvider)
            provider._crypto = MagicMock()
            provider._algorithm = "RSA-OAEP-256"
            assert isinstance(provider, KMSProvider)

    def test_vault_satisfies_protocol(self):
        with patch.dict("sys.modules", {"hvac": MagicMock()}):
            from flydesk.security.vault_kms import VaultKMSProvider

            provider = VaultKMSProvider.__new__(VaultKMSProvider)
            provider._client = MagicMock()
            provider._key = "flydesk"
            provider._mount = "transit"
            assert isinstance(provider, KMSProvider)


# ---------------------------------------------------------------------------
# AWS KMS encrypt/decrypt roundtrip
# ---------------------------------------------------------------------------


class TestAWSKMSProvider:
    def test_encrypt_decrypt_roundtrip(self):
        mock_boto3 = MagicMock()
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client

        plaintext = "my-secret"
        encrypted_blob = b"encrypted-bytes"

        mock_client.encrypt.return_value = {"CiphertextBlob": encrypted_blob}
        mock_client.decrypt.return_value = {"Plaintext": plaintext.encode("utf-8")}

        with patch.dict("sys.modules", {"boto3": mock_boto3}):
            from flydesk.security.aws_kms import AWSKMSProvider

            provider = AWSKMSProvider(key_arn="arn:aws:kms:us-east-1:000:key/abc", region="us-east-1")

            ciphertext = provider.encrypt(plaintext)
            assert ciphertext == base64.b64encode(encrypted_blob).decode("ascii")

            mock_client.encrypt.assert_called_once_with(
                KeyId="arn:aws:kms:us-east-1:000:key/abc",
                Plaintext=plaintext.encode("utf-8"),
            )

            result = provider.decrypt(ciphertext)
            assert result == plaintext

            mock_client.decrypt.assert_called_once_with(
                CiphertextBlob=base64.b64decode(ciphertext),
            )

    def test_region_kwarg_passed(self):
        mock_boto3 = MagicMock()
        with patch.dict("sys.modules", {"boto3": mock_boto3}):
            from flydesk.security.aws_kms import AWSKMSProvider

            AWSKMSProvider(key_arn="arn:test", region="eu-west-1")
            mock_boto3.client.assert_called_once_with("kms", region_name="eu-west-1")

    def test_no_region(self):
        mock_boto3 = MagicMock()
        with patch.dict("sys.modules", {"boto3": mock_boto3}):
            from flydesk.security.aws_kms import AWSKMSProvider

            AWSKMSProvider(key_arn="arn:test", region="")
            mock_boto3.client.assert_called_once_with("kms")


# ---------------------------------------------------------------------------
# GCP KMS encrypt/decrypt roundtrip
# ---------------------------------------------------------------------------


class TestGCPKMSProvider:
    def test_encrypt_decrypt_roundtrip(self):
        plaintext = "my-gcp-secret"
        ciphertext_bytes = b"gcp-encrypted-bytes"
        key_name = "projects/p/locations/l/keyRings/kr/cryptoKeys/ck"

        mock_client = MagicMock()

        encrypt_resp = MagicMock()
        encrypt_resp.ciphertext = ciphertext_bytes
        mock_client.encrypt.return_value = encrypt_resp

        decrypt_resp = MagicMock()
        decrypt_resp.plaintext = plaintext.encode("utf-8")
        mock_client.decrypt.return_value = decrypt_resp

        # Build the provider manually to avoid module-caching issues with
        # the lazy ``from google.cloud import kms`` inside __init__.
        from flydesk.security.gcp_kms import GCPKMSProvider

        provider = GCPKMSProvider.__new__(GCPKMSProvider)
        provider._client = mock_client
        provider._key_name = key_name

        ct = provider.encrypt(plaintext)
        assert ct == base64.b64encode(ciphertext_bytes).decode("ascii")

        mock_client.encrypt.assert_called_once_with(
            request={"name": key_name, "plaintext": plaintext.encode("utf-8")},
        )

        result = provider.decrypt(ct)
        assert result == plaintext

        mock_client.decrypt.assert_called_once_with(
            request={"name": key_name, "ciphertext": base64.b64decode(ct)},
        )


# ---------------------------------------------------------------------------
# Azure Key Vault encrypt/decrypt roundtrip
# ---------------------------------------------------------------------------


class TestAzureKeyVaultProvider:
    def test_encrypt_decrypt_roundtrip(self):
        plaintext = "my-azure-secret"
        ciphertext_bytes = b"azure-encrypted-bytes"

        mock_credential = MagicMock()
        mock_key_client_cls = MagicMock()
        mock_key = MagicMock()
        mock_key_client_cls.return_value.get_key.return_value = mock_key

        mock_crypto_client_cls = MagicMock()
        mock_crypto = MagicMock()
        mock_crypto_client_cls.return_value = mock_crypto

        mock_encryption_algorithm = MagicMock()
        mock_encryption_algorithm.rsa_oaep_256 = "RSA-OAEP-256"

        encrypt_result = MagicMock()
        encrypt_result.ciphertext = ciphertext_bytes
        mock_crypto.encrypt.return_value = encrypt_result

        decrypt_result = MagicMock()
        decrypt_result.plaintext = plaintext.encode("utf-8")
        mock_crypto.decrypt.return_value = decrypt_result

        mock_identity = MagicMock()
        mock_identity.DefaultAzureCredential.return_value = mock_credential

        mock_kv_keys = MagicMock()
        mock_kv_keys.KeyClient = mock_key_client_cls

        mock_kv_crypto = MagicMock()
        mock_kv_crypto.CryptographyClient = mock_crypto_client_cls
        mock_kv_crypto.EncryptionAlgorithm = mock_encryption_algorithm

        mock_modules = {
            "azure": MagicMock(),
            "azure.identity": mock_identity,
            "azure.keyvault": MagicMock(),
            "azure.keyvault.keys": mock_kv_keys,
            "azure.keyvault.keys.crypto": mock_kv_crypto,
        }

        with patch.dict("sys.modules", mock_modules):
            from flydesk.security.azure_kv import AzureKeyVaultProvider

            provider = AzureKeyVaultProvider(
                vault_url="https://myvault.vault.azure.net",
                key_name="my-key",
            )

            ct = provider.encrypt(plaintext)
            assert ct == base64.b64encode(ciphertext_bytes).decode("ascii")

            result = provider.decrypt(ct)
            assert result == plaintext


# ---------------------------------------------------------------------------
# Vault Transit encrypt/decrypt roundtrip
# ---------------------------------------------------------------------------


class TestVaultKMSProvider:
    def test_encrypt_decrypt_roundtrip(self):
        plaintext = "my-vault-secret"
        b64_plaintext = base64.b64encode(plaintext.encode("utf-8")).decode("ascii")
        vault_ciphertext = "vault:v1:someciphertext"

        mock_hvac = MagicMock()
        mock_client = MagicMock()
        mock_hvac.Client.return_value = mock_client

        mock_client.secrets.transit.encrypt_data.return_value = {
            "data": {"ciphertext": vault_ciphertext},
        }
        mock_client.secrets.transit.decrypt_data.return_value = {
            "data": {"plaintext": b64_plaintext},
        }

        with patch.dict("sys.modules", {"hvac": mock_hvac}):
            from flydesk.security.vault_kms import VaultKMSProvider

            provider = VaultKMSProvider(
                url="http://vault:8200",
                token="s.mytoken",
                transit_key="flydesk",
                mount_point="transit",
            )

            ct = provider.encrypt(plaintext)
            assert ct == vault_ciphertext

            mock_client.secrets.transit.encrypt_data.assert_called_once_with(
                name="flydesk",
                plaintext=b64_plaintext,
                mount_point="transit",
            )

            result = provider.decrypt(ct)
            assert result == plaintext

            mock_client.secrets.transit.decrypt_data.assert_called_once_with(
                name="flydesk",
                ciphertext=vault_ciphertext,
                mount_point="transit",
            )


# ---------------------------------------------------------------------------
# create_kms_provider factory tests
# ---------------------------------------------------------------------------


class TestCreateKmsProvider:
    def test_noop_provider(self):
        config = SimpleNamespace(kms_provider="noop")
        kms = create_kms_provider(config)
        assert isinstance(kms, NoOpKMSProvider)

    def test_fernet_provider(self):
        config = SimpleNamespace(kms_provider="fernet", credential_encryption_key="")
        kms = create_kms_provider(config)
        assert isinstance(kms, FernetKMSProvider)

    def test_fernet_default_when_missing_attr(self):
        config = SimpleNamespace(credential_encryption_key="")
        kms = create_kms_provider(config)
        assert isinstance(kms, FernetKMSProvider)

    def test_fernet_fallback_for_unknown_value(self):
        config = SimpleNamespace(kms_provider="unknown-provider", credential_encryption_key="")
        kms = create_kms_provider(config)
        assert isinstance(kms, FernetKMSProvider)

    def test_aws_provider(self):
        mock_boto3 = MagicMock()
        with patch.dict("sys.modules", {"boto3": mock_boto3}):
            config = SimpleNamespace(
                kms_provider="aws",
                aws_kms_key_arn="arn:aws:kms:us-east-1:000:key/abc",
                aws_kms_region="us-east-1",
            )
            kms = create_kms_provider(config)
            from flydesk.security.aws_kms import AWSKMSProvider

            assert isinstance(kms, AWSKMSProvider)

    def test_gcp_provider(self):
        mock_kms_module = MagicMock()
        mock_modules = {
            "google": MagicMock(),
            "google.cloud": MagicMock(),
            "google.cloud.kms": mock_kms_module,
        }
        with patch.dict("sys.modules", mock_modules):
            config = SimpleNamespace(
                kms_provider="gcp",
                gcp_kms_key_name="projects/p/locations/l/keyRings/kr/cryptoKeys/ck",
            )
            kms = create_kms_provider(config)
            from flydesk.security.gcp_kms import GCPKMSProvider

            assert isinstance(kms, GCPKMSProvider)

    def test_azure_provider(self):
        mock_modules = {
            "azure": MagicMock(),
            "azure.identity": MagicMock(),
            "azure.keyvault": MagicMock(),
            "azure.keyvault.keys": MagicMock(),
            "azure.keyvault.keys.crypto": MagicMock(),
        }
        with patch.dict("sys.modules", mock_modules):
            config = SimpleNamespace(
                kms_provider="azure",
                azure_vault_url="https://myvault.vault.azure.net",
                azure_key_name="my-key",
            )
            kms = create_kms_provider(config)
            from flydesk.security.azure_kv import AzureKeyVaultProvider

            assert isinstance(kms, AzureKeyVaultProvider)

    def test_vault_provider(self):
        mock_hvac = MagicMock()
        with patch.dict("sys.modules", {"hvac": mock_hvac}):
            config = SimpleNamespace(
                kms_provider="vault",
                vault_url="http://vault:8200",
                vault_token="s.mytoken",
                vault_transit_key="flydesk",
                vault_mount_point="transit",
            )
            kms = create_kms_provider(config)
            from flydesk.security.vault_kms import VaultKMSProvider

            assert isinstance(kms, VaultKMSProvider)

    def test_unknown_provider_logs_warning(self):
        config = SimpleNamespace(kms_provider="unknown-xyz", credential_encryption_key="")
        with patch("flydesk.security.kms.logger") as mock_logger:
            kms = create_kms_provider(config)
            assert isinstance(kms, FernetKMSProvider)
            mock_logger.warning.assert_called_once_with(
                "Unknown kms_provider=%r; falling back to Fernet.", "unknown-xyz"
            )


# ---------------------------------------------------------------------------
# Error handling: SDK errors wrapped as ValueError
# ---------------------------------------------------------------------------


class TestProviderErrorHandling:
    """Verify SDK exceptions are wrapped in ValueError."""

    def test_aws_encrypt_error_raises_valueerror(self):
        with patch.dict("sys.modules", {"boto3": MagicMock()}):
            from flydesk.security.aws_kms import AWSKMSProvider

            provider = AWSKMSProvider.__new__(AWSKMSProvider)
            provider._client = MagicMock()
            provider._key_arn = "arn:test"
            provider._client.encrypt.side_effect = RuntimeError("AWS SDK error")

            with pytest.raises(ValueError, match="AWS KMS encryption failed"):
                provider.encrypt("secret")

    def test_aws_decrypt_error_raises_valueerror(self):
        with patch.dict("sys.modules", {"boto3": MagicMock()}):
            from flydesk.security.aws_kms import AWSKMSProvider

            provider = AWSKMSProvider.__new__(AWSKMSProvider)
            provider._client = MagicMock()
            provider._key_arn = "arn:test"
            provider._client.decrypt.side_effect = RuntimeError("AWS SDK error")

            with pytest.raises(ValueError, match="AWS KMS decryption failed"):
                provider.decrypt(base64.b64encode(b"data").decode())

    def test_aws_decrypt_reraises_valueerror(self):
        """ValueError from our own wrapping should not be double-wrapped."""
        with patch.dict("sys.modules", {"boto3": MagicMock()}):
            from flydesk.security.aws_kms import AWSKMSProvider

            provider = AWSKMSProvider.__new__(AWSKMSProvider)
            provider._client = MagicMock()
            provider._key_arn = "arn:test"
            provider._client.decrypt.side_effect = ValueError("original error")

            with pytest.raises(ValueError, match="original error"):
                provider.decrypt(base64.b64encode(b"data").decode())

    def test_gcp_encrypt_error_raises_valueerror(self):
        from flydesk.security.gcp_kms import GCPKMSProvider

        provider = GCPKMSProvider.__new__(GCPKMSProvider)
        provider._client = MagicMock()
        provider._key_name = "projects/p/locations/l/keyRings/kr/cryptoKeys/ck"
        provider._client.encrypt.side_effect = RuntimeError("GCP error")

        with pytest.raises(ValueError, match="GCP KMS encryption failed"):
            provider.encrypt("secret")

    def test_gcp_decrypt_error_raises_valueerror(self):
        from flydesk.security.gcp_kms import GCPKMSProvider

        provider = GCPKMSProvider.__new__(GCPKMSProvider)
        provider._client = MagicMock()
        provider._key_name = "projects/p/locations/l/keyRings/kr/cryptoKeys/ck"
        provider._client.decrypt.side_effect = RuntimeError("GCP error")

        with pytest.raises(ValueError, match="GCP KMS decryption failed"):
            provider.decrypt(base64.b64encode(b"data").decode())

    def test_azure_encrypt_error_raises_valueerror(self):
        from flydesk.security.azure_kv import AzureKeyVaultProvider

        provider = AzureKeyVaultProvider.__new__(AzureKeyVaultProvider)
        provider._crypto = MagicMock()
        provider._algorithm = "RSA-OAEP-256"
        provider._crypto.encrypt.side_effect = RuntimeError("Azure error")

        with pytest.raises(ValueError, match="Azure Key Vault encryption failed"):
            provider.encrypt("secret")

    def test_azure_decrypt_error_raises_valueerror(self):
        from flydesk.security.azure_kv import AzureKeyVaultProvider

        provider = AzureKeyVaultProvider.__new__(AzureKeyVaultProvider)
        provider._crypto = MagicMock()
        provider._algorithm = "RSA-OAEP-256"
        provider._crypto.decrypt.side_effect = RuntimeError("Azure error")

        with pytest.raises(ValueError, match="Azure Key Vault decryption failed"):
            provider.decrypt(base64.b64encode(b"data").decode())

    def test_vault_encrypt_error_raises_valueerror(self):
        from flydesk.security.vault_kms import VaultKMSProvider

        provider = VaultKMSProvider.__new__(VaultKMSProvider)
        provider._client = MagicMock()
        provider._key = "flydesk"
        provider._mount = "transit"
        provider._client.secrets.transit.encrypt_data.side_effect = RuntimeError("Vault error")

        with pytest.raises(ValueError, match="Vault Transit encryption failed"):
            provider.encrypt("secret")

    def test_vault_decrypt_error_raises_valueerror(self):
        from flydesk.security.vault_kms import VaultKMSProvider

        provider = VaultKMSProvider.__new__(VaultKMSProvider)
        provider._client = MagicMock()
        provider._key = "flydesk"
        provider._mount = "transit"
        provider._client.secrets.transit.decrypt_data.side_effect = RuntimeError("Vault error")

        with pytest.raises(ValueError, match="Vault Transit decryption failed"):
            provider.decrypt("vault:v1:something")


# ---------------------------------------------------------------------------
# Config validation in create_kms_provider
# ---------------------------------------------------------------------------


class TestCreateKmsProviderConfigValidation:
    """Verify missing config fields raise ValueError."""

    def test_aws_missing_key_arn(self):
        config = SimpleNamespace(kms_provider="aws", aws_kms_key_arn="")
        with pytest.raises(ValueError, match="FLYDESK_AWS_KMS_KEY_ARN must be set"):
            create_kms_provider(config)

    def test_aws_missing_key_arn_attr(self):
        config = SimpleNamespace(kms_provider="aws")
        with pytest.raises(ValueError, match="FLYDESK_AWS_KMS_KEY_ARN must be set"):
            create_kms_provider(config)

    def test_gcp_missing_key_name(self):
        config = SimpleNamespace(kms_provider="gcp", gcp_kms_key_name="")
        with pytest.raises(ValueError, match="FLYDESK_GCP_KMS_KEY_NAME must be set"):
            create_kms_provider(config)

    def test_azure_missing_vault_url(self):
        config = SimpleNamespace(kms_provider="azure", azure_vault_url="", azure_key_name="key")
        with pytest.raises(ValueError, match="FLYDESK_AZURE_VAULT_URL and FLYDESK_AZURE_KEY_NAME"):
            create_kms_provider(config)

    def test_azure_missing_key_name(self):
        config = SimpleNamespace(
            kms_provider="azure", azure_vault_url="https://vault.azure.net", azure_key_name=""
        )
        with pytest.raises(ValueError, match="FLYDESK_AZURE_VAULT_URL and FLYDESK_AZURE_KEY_NAME"):
            create_kms_provider(config)

    def test_vault_missing_url(self):
        config = SimpleNamespace(kms_provider="vault", vault_url="", vault_token="tok")
        with pytest.raises(ValueError, match="FLYDESK_VAULT_URL and FLYDESK_VAULT_TOKEN"):
            create_kms_provider(config)

    def test_vault_missing_token(self):
        config = SimpleNamespace(kms_provider="vault", vault_url="http://vault:8200", vault_token="")
        with pytest.raises(ValueError, match="FLYDESK_VAULT_URL and FLYDESK_VAULT_TOKEN"):
            create_kms_provider(config)


# ---------------------------------------------------------------------------
# ImportError handling in create_kms_provider
# ---------------------------------------------------------------------------


class TestCreateKmsProviderImportErrors:
    """Verify missing SDK packages raise ImportError with install instructions."""

    def test_aws_missing_sdk(self):
        config = SimpleNamespace(
            kms_provider="aws",
            aws_kms_key_arn="arn:aws:kms:us-east-1:000:key/abc",
            aws_kms_region="us-east-1",
        )
        # Block both the SDK and the provider module so the factory import fails
        with patch.dict(
            "sys.modules",
            {"boto3": None, "flydesk.security.aws_kms": None},
        ):
            with pytest.raises(ImportError, match="pip install flydesk\\[aws-kms\\]"):
                create_kms_provider(config)

    def test_gcp_missing_sdk(self):
        config = SimpleNamespace(
            kms_provider="gcp",
            gcp_kms_key_name="projects/p/locations/l/keyRings/kr/cryptoKeys/ck",
        )
        with patch.dict(
            "sys.modules",
            {
                "google": None,
                "google.cloud": None,
                "google.cloud.kms": None,
                "flydesk.security.gcp_kms": None,
            },
        ):
            with pytest.raises(ImportError, match="pip install flydesk\\[gcp-kms\\]"):
                create_kms_provider(config)

    def test_azure_missing_sdk(self):
        config = SimpleNamespace(
            kms_provider="azure",
            azure_vault_url="https://myvault.vault.azure.net",
            azure_key_name="my-key",
        )
        with patch.dict(
            "sys.modules",
            {
                "azure": None,
                "azure.identity": None,
                "azure.keyvault": None,
                "azure.keyvault.keys": None,
                "azure.keyvault.keys.crypto": None,
                "flydesk.security.azure_kv": None,
            },
        ):
            with pytest.raises(ImportError, match="pip install flydesk\\[azure-kms\\]"):
                create_kms_provider(config)

    def test_vault_missing_sdk(self):
        config = SimpleNamespace(
            kms_provider="vault",
            vault_url="http://vault:8200",
            vault_token="s.mytoken",
            vault_transit_key="flydesk",
            vault_mount_point="transit",
        )
        with patch.dict(
            "sys.modules",
            {"hvac": None, "flydesk.security.vault_kms": None},
        ):
            with pytest.raises(ImportError, match="pip install flydesk\\[vault\\]"):
                create_kms_provider(config)
