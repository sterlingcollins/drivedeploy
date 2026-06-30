"""Tests for drivedeploy.core.hashing."""

from __future__ import annotations

import hashlib
from pathlib import Path

from drivedeploy.core import hashing

# echo -n "" | sha256sum
EMPTY_SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def test_sha256_bytes_known_vector():
    assert hashing.sha256_bytes(b"") == EMPTY_SHA256


def test_sha256_file_matches_hashlib(tmp_path: Path):
    payload = b"drivedeploy round-trip payload" * 1000
    target = tmp_path / "blob.bin"
    target.write_bytes(payload)
    assert hashing.sha256_file(target) == hashlib.sha256(payload).hexdigest()


def test_sha256_file_empty(tmp_path: Path):
    target = tmp_path / "empty.bin"
    target.write_bytes(b"")
    assert hashing.sha256_file(target) == EMPTY_SHA256
