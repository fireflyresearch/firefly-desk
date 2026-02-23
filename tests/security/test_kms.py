# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Tests for the KMS abstraction layer."""

from __future__ import annotations

import base64

import pytest

from flydesk.security.kms import (
    FernetKMSProvider,
    KMSProvider,
    NoOpKMSProvider,
)


# ---------------------------------------------------------------------------
# KMSProvider protocol conformance
# ---------------------------------------------------------------------------


class TestKMSProtocol:
    def test_fernet_satisfies_protocol(self):
        assert isinstance(FernetKMSProvider(), KMSProvider)

    def test_noop_satisfies_protocol(self):
        assert isinstance(NoOpKMSProvider(), KMSProvider)


# ---------------------------------------------------------------------------
# FernetKMSProvider
# ---------------------------------------------------------------------------


def _valid_fernet_key() -> str:
    """Generate a valid Fernet key (URL-safe base64, 32 bytes)."""
    return base64.urlsafe_b64encode(b"0" * 32).decode()


class TestFernetKMSProvider:
    def test_encrypt_decrypt_roundtrip(self):
        kms = FernetKMSProvider(_valid_fernet_key())
        plaintext = "my-secret-api-key-12345"
        ciphertext = kms.encrypt(plaintext)

        assert ciphertext != plaintext
        assert kms.decrypt(ciphertext) == plaintext

    def test_ciphertext_differs_each_time(self):
        kms = FernetKMSProvider(_valid_fernet_key())
        c1 = kms.encrypt("same-value")
        c2 = kms.encrypt("same-value")
        assert c1 != c2  # Fernet uses random IV

    def test_dev_key_fallback_when_empty(self):
        kms = FernetKMSProvider("")
        assert kms.is_dev_key is True
        # Should still encrypt/decrypt
        ct = kms.encrypt("secret")
        assert kms.decrypt(ct) == "secret"

    def test_dev_key_fallback_on_invalid_key(self):
        kms = FernetKMSProvider("not-a-valid-fernet-key")
        assert kms.is_dev_key is True

    def test_valid_key_not_dev(self):
        kms = FernetKMSProvider(_valid_fernet_key())
        assert kms.is_dev_key is False

    def test_decrypt_wrong_key_raises(self):
        kms1 = FernetKMSProvider(_valid_fernet_key())
        key2 = base64.urlsafe_b64encode(b"1" * 32).decode()
        kms2 = FernetKMSProvider(key2)

        ciphertext = kms1.encrypt("secret")
        with pytest.raises(ValueError, match="Decryption failed"):
            kms2.decrypt(ciphertext)

    def test_decrypt_garbage_raises(self):
        kms = FernetKMSProvider(_valid_fernet_key())
        with pytest.raises(ValueError, match="Decryption failed"):
            kms.decrypt("not-valid-ciphertext")

    def test_encrypt_empty_string(self):
        kms = FernetKMSProvider(_valid_fernet_key())
        ct = kms.encrypt("")
        assert kms.decrypt(ct) == ""

    def test_encrypt_unicode(self):
        kms = FernetKMSProvider(_valid_fernet_key())
        plaintext = "mot de passe: caf\u00e9\u2615"
        ct = kms.encrypt(plaintext)
        assert kms.decrypt(ct) == plaintext


# ---------------------------------------------------------------------------
# NoOpKMSProvider
# ---------------------------------------------------------------------------


class TestNoOpKMSProvider:
    def test_encrypt_passthrough(self):
        kms = NoOpKMSProvider()
        assert kms.encrypt("secret") == "secret"

    def test_decrypt_passthrough(self):
        kms = NoOpKMSProvider()
        assert kms.decrypt("secret") == "secret"

    def test_roundtrip(self):
        kms = NoOpKMSProvider()
        value = "my-api-key"
        assert kms.decrypt(kms.encrypt(value)) == value
