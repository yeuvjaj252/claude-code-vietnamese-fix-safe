#!/usr/bin/env python3
"""Basic tests for Vietnamese IME patcher (Safe Edition).

Note: These are lightweight functional tests that operate on in-memory strings
and temporary files to validate core behaviors (regex extraction, patch generation,
backup/restore logic). They don't require Claude Code installed.

To run:
    python3 test.py
"""

import hashlib
import tempfile
from pathlib import Path

import patcher


def mock_cli_js():
    """Mock cli.js content with bug pattern."""
    return (
        "function demo(input,state,cur){"  # opening
        'if(input.includes("\x7f")){'  # bug block start
        "let c=(input.match(/\x7f/g)||[]).length,s=cur;"
        "state=s;"
        "state=state.backspace();"
        "state=state.insert('a');"
        "if(cur.text!==s.text)uText(s.text);uOffset(s.offset)}"
        "return s;}"
    )


def test_extract_variables():
    """Test variable extraction from bug block."""
    block = mock_cli_js()
    vars_map = patcher.extract_variables(block)
    assert set(vars_map.keys()) == {
        "input",
        "state",
        "cur_state",
        "update_text",
        "update_offset",
    }
    print("✓ test_extract_variables")


def test_generate_fix_contains_marker():
    """Test fix code generation."""
    block = mock_cli_js()
    vars_map = patcher.extract_variables(block)
    fix = patcher.generate_fix(vars_map)
    assert patcher.PATCH_MARKER in fix
    assert "backspace" in fix
    assert "insert" in fix
    print("✓ test_generate_fix_contains_marker")


def test_backup_and_restore():
    """Test backup creation and restore."""
    tmp_path = Path(tempfile.mkdtemp())
    file_path = tmp_path / "cli.js"
    file_path.write_text(mock_cli_js(), encoding="utf-8")

    # Get original checksum
    original_checksum = hashlib.sha256(file_path.read_bytes()).hexdigest()

    # Patch
    rc = patcher.patch(str(file_path))
    assert rc == 0
    assert patcher.PATCH_MARKER in file_path.read_text(encoding="utf-8")

    # Restore
    rc_restore = patcher.restore(str(file_path))
    assert rc_restore == 0
    restored_content = file_path.read_text(encoding="utf-8")
    assert patcher.PATCH_MARKER not in restored_content

    # Verify checksum after restore
    restored_checksum = hashlib.sha256(file_path.read_bytes()).hexdigest()
    assert original_checksum == restored_checksum, "Checksum mismatch after restore!"

    print("✓ test_backup_and_restore")


def test_dry_run():
    """Test dry-run mode doesn't modify file."""
    tmp_path = Path(tempfile.mkdtemp())
    file_path = tmp_path / "cli.js"
    original_content = mock_cli_js()
    file_path.write_text(original_content, encoding="utf-8")

    # Dry run
    rc = patcher.patch(str(file_path), dry_run=True)
    assert rc == 0

    # File should NOT be modified
    assert file_path.read_text(encoding="utf-8") == original_content
    assert patcher.PATCH_MARKER not in file_path.read_text(encoding="utf-8")

    print("✓ test_dry_run")


def test_sha256_file():
    """Test SHA256 checksum calculation."""
    tmp_path = Path(tempfile.mkdtemp())
    file_path = tmp_path / "test.txt"
    file_path.write_text("test content", encoding="utf-8")

    checksum = patcher.sha256_file(str(file_path))
    assert len(checksum) == 64  # SHA256 hex length
    assert checksum == hashlib.sha256(b"test content").hexdigest()

    print("✓ test_sha256_file")


def test_already_patched():
    """Test idempotency - already patched file returns 0."""
    tmp_path = Path(tempfile.mkdtemp())
    file_path = tmp_path / "cli.js"
    content = mock_cli_js() + patcher.PATCH_MARKER
    file_path.write_text(content, encoding="utf-8")

    rc = patcher.patch(str(file_path))
    assert rc == 0  # Should return 0 without error

    print("✓ test_already_patched")


if __name__ == "__main__":
    print("Running lightweight tests...\n")
    test_extract_variables()
    test_generate_fix_contains_marker()
    test_backup_and_restore()
    test_dry_run()
    test_sha256_file()
    test_already_patched()
    print("\n✅ All tests passed (lightweight).")
