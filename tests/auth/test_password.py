# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Tests for password hashing utilities."""

from __future__ import annotations

from flydesk.auth.password import hash_password, verify_password


class TestPasswordHashing:
    def test_hash_returns_bcrypt_string(self):
        """hash_password() returns a bcrypt hash starting with $2b$."""
        hashed = hash_password("my-secret")
        assert hashed.startswith("$2b$")

    def test_verify_correct_password(self):
        """verify_password() returns True for the correct plaintext."""
        hashed = hash_password("correct-horse-battery-staple")
        assert verify_password("correct-horse-battery-staple", hashed) is True

    def test_verify_wrong_password(self):
        """verify_password() returns False for an incorrect plaintext."""
        hashed = hash_password("correct-horse-battery-staple")
        assert verify_password("wrong-password", hashed) is False

    def test_different_hashes_for_same_password(self):
        """Each call to hash_password() produces a different salt/hash."""
        h1 = hash_password("same-password")
        h2 = hash_password("same-password")
        assert h1 != h2
        # But both still verify correctly
        assert verify_password("same-password", h1) is True
        assert verify_password("same-password", h2) is True

    def test_empty_password(self):
        """An empty string can be hashed and verified."""
        hashed = hash_password("")
        assert verify_password("", hashed) is True
        assert verify_password("not-empty", hashed) is False
