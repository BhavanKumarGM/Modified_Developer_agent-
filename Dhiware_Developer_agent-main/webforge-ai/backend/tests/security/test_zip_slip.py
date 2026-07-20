"""Regression test for the Zip Slip vulnerability in zip_service.extract_zip.

Before the fix, a ZIP entry named "../../evil.txt" would be extracted using
`target_dir.joinpath(*parts)`, which happily walks outside target_dir. The
fix routes every member through `resolve_safe` and skips anything that
escapes.
"""
import zipfile
from pathlib import Path

from app.services.zip_service import extract_zip


def _build_malicious_zip(zip_path: Path) -> None:
    with zipfile.ZipFile(zip_path, "w") as zf:
        # Legitimate file, inside a common single-root folder.
        zf.writestr("myproject/src/App.tsx", "export default function App() {}")
        # Zip Slip payloads: escape the extraction root once the common
        # "myproject/" prefix is stripped. Kept under the same top-level
        # prefix so the archive still looks single-rooted (the realistic case).
        zf.writestr("myproject/../../evil.txt", "pwned")
        zf.writestr("myproject/../../../also_evil.txt", "pwned2")


def test_zip_slip_entries_are_skipped_not_extracted(tmp_path: Path):
    zip_path = tmp_path / "malicious.zip"
    _build_malicious_zip(zip_path)

    target_dir = tmp_path / "extracted"
    extract_zip(zip_path, target_dir)

    # The legitimate file lands inside target_dir.
    assert (target_dir / "src" / "App.tsx").exists()

    # Nothing was written anywhere outside target_dir.
    for suspicious in [
        tmp_path / "evil.txt",
        tmp_path.parent / "evil.txt",
        tmp_path / "also_evil.txt",
    ]:
        assert not suspicious.exists(), f"Zip Slip escaped to {suspicious}"

    # And nothing named evil.txt / also_evil.txt exists anywhere under target_dir either
    # (they should have been skipped, not silently relocated inside).
    escaped_names = {p.name for p in target_dir.rglob("*evil*")}
    assert escaped_names == set(), f"Unexpected escaped-looking files: {escaped_names}"
