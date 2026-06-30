"""Tests for drivedeploy.publish.archive."""

from __future__ import annotations

import pytest

from drivedeploy.errors import ArtifactNotFoundError
from drivedeploy.publish import archive


def test_zip_and_extract_round_trip(tmp_path):
    src = tmp_path / "bundle"
    (src / "sub").mkdir(parents=True)
    (src / "mytool.exe").write_bytes(b"exe")
    (src / "sub" / "data.bin").write_bytes(b"data")

    zipped = archive.zip_bundle(src, tmp_path / "out.zip")
    assert zipped.is_file()

    out = archive.extract_bundle(zipped, tmp_path / "extracted")
    assert (out / "mytool.exe").read_bytes() == b"exe"
    assert (out / "sub" / "data.bin").read_bytes() == b"data"


def test_zip_missing_dir_raises(tmp_path):
    with pytest.raises(ArtifactNotFoundError):
        archive.zip_bundle(tmp_path / "absent", tmp_path / "out.zip")


def test_extract_missing_zip_raises(tmp_path):
    with pytest.raises(ArtifactNotFoundError):
        archive.extract_bundle(tmp_path / "absent.zip", tmp_path / "out")
