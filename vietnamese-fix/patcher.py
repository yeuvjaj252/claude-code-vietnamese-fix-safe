#!/usr/bin/env python3
"""
Claude Code Vietnamese IME Fix - Safe Edition

Fixes Vietnamese input bug in Claude Code CLI (npm) by patching
the backspace handling logic to also insert replacement text.

Safety features:
- Dry-run mode (no changes)
- Backup with checksum verification
- Restore from backup
- Version info logging
- Rollback on error
- Multiple backup retention

Usage:
  python3 patcher.py              Auto-detect and fix
  python3 patcher.py --dry-run    Test run without changes
  python3 patcher.py --restore    Restore from backup
  python3 patcher.py --path FILE  Fix specific file
  python3 patcher.py --info       Show CLI info
  python3 patcher.py --help       Show help

Repository: https://github.com/manhit96/claude-code-vietnamese-fix
License: MIT
"""

import hashlib
import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

try:
    import platform
except ImportError:
    platform = None

PATCH_MARKER = "/* Vietnamese IME fix */"
DEL_CHAR = chr(127)  # 0x7F - character used by Vietnamese IME for backspace
MAX_BACKUPS = 5  # Keep max 5 backups


def sha256_file(filepath: str) -> str:
    """Calculate SHA256 checksum of a file."""
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def find_cli_js():
    """Auto-detect Claude Code npm cli.js location."""
    home = Path.home()
    is_windows = (platform.system() == "Windows") if platform else False

    if is_windows:
        search_dirs = [
            Path(os.environ.get("LOCALAPPDATA", "")) / "npm-cache" / "_npx",
            Path(os.environ.get("APPDATA", "")) / "npm" / "node_modules",
        ]
    else:
        search_dirs = [
            home / ".npm" / "_npx",
            home / ".nvm" / "versions" / "node",
            Path("/usr/local/lib/node_modules"),
            Path("/opt/homebrew/lib/node_modules"),
            Path("/usr/lib/node_modules"),
        ]

    found_paths = []
    for directory in search_dirs:
        if directory.exists():
            for cli_js in directory.rglob("*/@anthropic-ai/claude-code/cli.js"):
                found_paths.append(str(cli_js))

    if not found_paths:
        raise FileNotFoundError(
            "Không tìm thấy Claude Code npm.\n"
            "Cài đặt trước: npm install -g @anthropic-ai/claude-code"
        )

    # Return the most recently modified one
    found_paths.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    return found_paths[0]


def find_bug_block(content: str):
    """Find the if-block containing the Vietnamese IME bug pattern."""
    pattern = f'.includes("{DEL_CHAR}")'
    idx = content.find(pattern)

    if idx == -1:
        raise RuntimeError(
            'Không tìm thấy bug pattern .includes("\\x7f").\n'
            "Claude Code có thể đã được Anthropic fix."
        )

    # Find the containing if(
    block_start = content.rfind("if(", max(0, idx - 150), idx)
    if block_start == -1:
        raise RuntimeError("Không tìm thấy block if chứa pattern")

    # Find matching closing brace
    depth = 0
    block_end = idx
    for i, c in enumerate(content[block_start:block_start + 800]):
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                block_end = block_start + i + 1
                break

    if depth != 0:
        raise RuntimeError("Không tìm thấy closing brace của block if")

    return block_start, block_end, content[block_start:block_end]


def extract_variables(block: str):
    """Extract dynamic variable names from the bug block."""
    normalized = block.replace(DEL_CHAR, "\\x7f")

    # Match: let COUNT=(INPUT.match(/\x7f/g)||[]).length,STATE=CURSTATE;
    match = re.search(
        r"let ([\w$]+)=\(\w+\.match\(/\\x7f/g\)\|\|\[\]\)\.length[,;]([\w$]+)=([\w$]+)[;,]",
        normalized,
    )
    if not match:
        raise RuntimeError("Không trích xuất được biến count/state")

    state, cur_state = match.group(2), match.group(3)

    # Match: UPDATETEXT(STATE.text);UPDATEOFFSET(STATE.offset)
    match_update = re.search(
        rf"([\w$]+)\({re.escape(state)}\.text\);([\w$]+)\({re.escape(state)}\.offset\)",
        block,
    )
    if not match_update:
        raise RuntimeError("Không trích xuất được update functions")

    # Match: INPUT.includes("
    match_input = re.search(r"([\w$]+)\.includes\(\"", block)
    if not match_input:
        raise RuntimeError("Không trích xuất được input variable")

    return {
        "input": match_input.group(1),
        "state": state,
        "cur_state": cur_state,
        "update_text": match_update.group(1),
        "update_offset": match_update.group(2),
    }


def generate_fix(vars_map: dict) -> str:
    """Generate the fix code that does backspace + insert replacement text."""
    return (
        f"{PATCH_MARKER}"
        f"if({vars_map['input']}.includes(\"\\x7f\")){{"
        f"let _n=({vars_map['input']}.match(/\\x7f/g)||[]).length,"
        f"_vn={vars_map['input']}.replace(/\\x7f/g,\"\"),"
        f"{vars_map['state']}={vars_map['cur_state']};"
        f"for(let _i=0;_i<_n;_i++){{{vars_map['state']}={vars_map['state']}.backspace();}}"
        f"for(const _c of _vn){{{vars_map['state']}={vars_map['state']}.insert(_c);}}"
        f"if(!{vars_map['cur_state']}.equals({vars_map['state']})){{"
        f"if({vars_map['cur_state']}.text!=={vars_map['state']}.text)"
        f"{vars_map['update_text']}({vars_map['state']}.text);"
        f"{vars_map['update_offset']}({vars_map['state']}.offset)"
        f"}}return;}}"
    )


def find_backups(file_path: str):
    """Find all backup files for a given file."""
    dir_path = os.path.dirname(file_path) or "."
    filename = os.path.basename(file_path)
    backups = [
        os.path.join(dir_path, f)
        for f in os.listdir(dir_path)
        if f.startswith(f"{filename}.backup-")
    ]
    backups.sort(key=os.path.getmtime, reverse=True)
    return backups


def find_latest_backup(file_path: str):
    """Find the most recent backup file."""
    backups = find_backups(file_path)
    return backups[0] if backups else None


def cleanup_old_backups(file_path: str):
    """Keep only MAX_BACKUPS most recent backups."""
    backups = find_backups(file_path)
    for old_backup in backups[MAX_BACKUPS:]:
        try:
            os.remove(old_backup)
        except OSError:
            pass


def patch(file_path: str, dry_run: bool = False):
    """Apply Vietnamese IME fix to cli.js."""
    print(f"-> File: {file_path}")

    if not os.path.exists(file_path):
        print(f"Lỗi: File không tồn tại: {file_path}", file=sys.stderr)
        return 1

    # Checksum before
    original_checksum = sha256_file(file_path)
    print(f"   SHA256: {original_checksum[:16]}...")

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    if PATCH_MARKER in content:
        print("Đã patch trước đó.")
        return 0

    if dry_run:
        print("\n[DRY RUN] Would patch but skipping (no changes made)")
        try:
            block_start, block_end, block = find_bug_block(content)
            variables = extract_variables(block)
            print(f"   Vars: input={variables['input']}, state={variables['state']}, cur={variables['cur_state']}")
        except Exception as e:
            print(f"   Warning: {e}")
        return 0

    # Backup with checksum
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = f"{file_path}.backup-{timestamp}"
    shutil.copy2(file_path, backup_path)
    backup_checksum = sha256_file(backup_path)
    print(f"   Backup: {backup_path}")
    print(f"   Backup SHA256: {backup_checksum[:16]}...")

    if original_checksum != backup_checksum:
        print("Lỗi: Backup checksum không khớp!", file=sys.stderr)
        return 1

    try:
        # Find bug block
        block_start, block_end, block = find_bug_block(content)

        # Extract variables
        variables = extract_variables(block)
        print(
            "   Vars: input={input}, state={state}, cur={cur}".format(
                input=variables["input"], state=variables["state"], cur=variables["cur_state"]
            )
        )

        # Generate fix and replace
        fix_code = generate_fix(variables)
        patched = content[:block_start] + fix_code + content[block_end:]

        # Write
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(patched)

        # Verify
        with open(file_path, "r", encoding="utf-8") as f:
            new_content = f.read()
            if PATCH_MARKER not in new_content:
                raise RuntimeError("Verify failed: patch marker not found after write")

        new_checksum = hashlib.sha256(new_content.encode("utf-8")).hexdigest()
        print(f"   New SHA256: {new_checksum[:16]}...")

        # Cleanup old backups
        cleanup_old_backups(file_path)

        print("\n   Patch thành công! Khởi động lại Claude Code.\n")
        return 0

    except Exception as exc:  # noqa: BLE001
        print(f"\nLỗi: {exc}", file=sys.stderr)
        print(
            "Báo lỗi tại: https://github.com/manhit96/claude-code-vietnamese-fix/issues",
            file=sys.stderr,
        )
        # Rollback
        if os.path.exists(backup_path):
            shutil.copy2(backup_path, file_path)
            os.remove(backup_path)
            print("Đã rollback về bản gốc.", file=sys.stderr)
        return 1


def restore(file_path: str):
    """Restore file from latest backup."""
    backup = find_latest_backup(file_path)
    if not backup:
        print(f"Không tìm thấy backup cho {file_path}", file=sys.stderr)
        return 1

    # Verify backup integrity
    backup_checksum = sha256_file(backup)
    print(f"Backup SHA256: {backup_checksum[:16]}...")

    shutil.copy2(backup, file_path)
    print(f"Đã khôi phục từ: {backup}")
    print("Khởi động lại Claude Code.")
    return 0


def show_info():
    """Show CLI information."""
    print("Claude Code Vietnamese IME Fix - Info\n")
    try:
        cli_path = find_cli_js()
        print(f"CLI Path: {cli_path}")
        if os.path.exists(cli_path):
            size = os.path.getsize(cli_path)
            print(f"File Size: {size:,} bytes")
            with open(cli_path, "r", encoding="utf-8") as f:
                content = f.read()
            if PATCH_MARKER in content:
                print("Status: PATCHED ✓")
            else:
                print("Status: NOT PATCHED")
    except FileNotFoundError as e:
        print(f"Error: {e}")
    except Exception as e:
        print(f"Error: {e}")


def show_help():
    """Hiển thị hướng dẫn sử dụng."""
    print("Claude Code Vietnamese IME Fix - Safe Edition")
    print("")
    print("Sử dụng:")
    print("  python3 patcher.py              Tự động phát hiện và fix")
    print("  python3 patcher.py --dry-run    Chạy thử không áp dụng thay đổi")
    print("  python3 patcher.py --restore    Khôi phục từ backup")
    print("  python3 patcher.py --path FILE  Fix file cụ thể")
    print("  python3 patcher.py --info       Hiển thị thông tin CLI")
    print("  python3 patcher.py --help       Hiển thị hướng dẫn")
    print("")
    print("https://github.com/manhit96/claude-code-vietnamese-fix")


def main():
    args = sys.argv[1:]

    # treat --auto as default behavior
    if "--auto" in args:
        args = [a for a in args if a != "--auto"]

    if "--help" in args or "-h" in args:
        show_help()
        return 0

    if "--info" in args:
        show_info()
        return 0

    if "--restore" in args:
        if "--path" in args:
            idx = args.index("--path")
            try:
                file_path = args[idx + 1]
            except IndexError:
                print("Thiếu giá trị cho --path", file=sys.stderr)
                return 1
        else:
            file_path = find_cli_js()
        return restore(file_path)

    dry_run = "--dry-run" in args
    if dry_run:
        args = [a for a in args if a != "--dry-run"]

    if "--path" in args:
        idx = args.index("--path")
        try:
            file_path = args[idx + 1]
        except IndexError:
            print("Thiếu giá trị cho --path", file=sys.stderr)
            return 1
    else:
        file_path = find_cli_js()

    return patch(file_path, dry_run=dry_run)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
    except FileNotFoundError as err:
        print(f"Lỗi: {err}", file=sys.stderr)
        sys.exit(1)
    except Exception as err:  # noqa: BLE001
        print(f"Lỗi: {err}", file=sys.stderr)
        sys.exit(1)
