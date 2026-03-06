#!/usr/bin/env python3
"""
Claude Code Vietnamese IME Fix - Safe Edition

Fixes Vietnamese input bug in Claude Code CLI by patching
the backspace handling logic to also insert replacement text.

Supports:
- npm install -g @anthropic-ai/claude-code
- curl -fsSL https://claude.ai/install.sh | bash (official installer)
- claude.ai versioned installer (~/.local/share/claude/versions/*)

Safety features:
- Dry-run mode (no changes)
- Backup with checksum verification
- Restore from backup
- Rollback on error
- Multiple backup retention (max 5)

Usage:
  python3 patcher.py              Auto-detect and fix
  python3 patcher.py --dry-run    Test run without changes
  python3 patcher.py --restore    Restore from backup
  python3 patcher.py --path FILE  Fix specific file
  python3 patcher.py --info       Show CLI info
  python3 patcher.py --help       Show help

Repository: https://github.com/yeuvjaj252/claude-code-vietnamese-fix-safe
License: MIT
"""

import glob
import hashlib
import os
import re
import shutil
import subprocess
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


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def sha256_file(filepath: str) -> str:
    """Calculate SHA256 checksum of a file."""
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def check_path_exists(path: Path) -> bool:
    """Check if a path exists, handling symlinks."""
    try:
        return path.exists() or path.resolve().exists()
    except (OSError, RuntimeError):
        return False


def get_resolved_path(path: Path):
    """Get resolved path, handling symlinks."""
    try:
        return path.resolve()
    except (OSError, RuntimeError):
        return path


def search_js_files_in_dir(base_dir: Path, max_depth: int = 4) -> list[str]:
    """Search for potential cli.js files in a directory tree."""
    found = []
    try:
        for root, dirs, files in os.walk(base_dir, topdown=True):
            # Limit depth
            depth = len(Path(root).relative_to(base_dir).parts)
            if depth > max_depth:
                dirs[:] = []  # Don't recurse further
                continue
            
            for f in files:
                if f == "cli.js" or "claude" in f.lower():
                    full_path = os.path.join(root, f)
                    found.append(full_path)
    except (PermissionError, OSError):
        pass
    return found


def find_cli_js():
    """
    Auto-detect Claude Code cli.js location.

    Supports:
    1. npm install -g @anthropic-ai/claude-code
    2. Official claude.ai installer
    3. Claude.ai versioned installer (~/.local/share/claude/versions/*)
    4. User-specific installations in /home/*/
    """
    home = Path.home()
    is_windows = (platform.system() == "Windows") if platform else False

    found_paths: list[str] = []

    # ==================== EXPLICIT PATHS (highest priority) ====================
    explicit_paths = [
        Path("/usr/lib/node_modules/@anthropic-ai/claude-code/cli.js"),
        Path("/usr/local/lib/node_modules/@anthropic-ai/claude-code/cli.js"),
        Path("/opt/homebrew/lib/node_modules/@anthropic-ai/claude-code/cli.js"),
    ]

    for p in explicit_paths:
        if check_path_exists(p):
            found_paths.append(str(get_resolved_path(p)))

    # ==================== CLAUDE.AI VERSIONED INSTALLER ====================
    # Check ~/.local/share/claude/versions/*/ for cli.js
    claude_versions_dir = home / ".local" / "share" / "claude" / "versions"
    if claude_versions_dir.exists():
        # Find all version directories
        for version_dir in claude_versions_dir.iterdir():
            if version_dir.is_dir():
                # Search for cli.js in version directory
                for pattern in ["cli.js", "bin/claude", "resources/cli.js"]:
                    candidate = version_dir / pattern
                    if candidate.exists():
                        found_paths.append(str(candidate))
                # Deep search
                for js_file in search_js_files_in_dir(version_dir):
                    if "cli" in js_file.lower():
                        found_paths.append(js_file)

    # ==================== CLAUDE LOCAL BIN ====================
    # Check ~/.local/bin/claude and resolve
    claude_local_bin = home / ".local" / "bin" / "claude"
    if claude_local_bin.exists():
        try:
            resolved = os.path.realpath(str(claude_local_bin))
            if os.path.exists(resolved):
                # Check if it's a directory with cli.js
                if os.path.isdir(resolved):
                    for js_file in search_js_files_in_dir(Path(resolved)):
                        if "cli" in js_file.lower():
                            found_paths.append(js_file)
                elif "cli.js" in resolved:
                    found_paths.append(resolved)
        except (OSError, RuntimeError):
            pass

    # ==================== WINDOWS ====================
    if is_windows:
        search_dirs = [
            Path(os.environ.get("LOCALAPPDATA", "")) / "npm-cache" / "_npx",
            Path(os.environ.get("APPDATA", "")) / "npm" / "node_modules",
            Path(os.environ.get("LOCALAPPDATA", "")) / "claude-cli",
            Path(os.environ.get("PROGRAMFILES", "")) / "claude-cli",
        ]
    # ==================== LINUX / MACOS ====================
    else:
        search_dirs = [
            # User home directories
            home / ".npm" / "_npx",
            home / ".nvm" / "versions" / "node",
            home / ".local" / "lib" / "node_modules",
            home / ".claude-cli",
            # System directories
            Path("/usr/lib/node_modules"),
            Path("/usr/local/lib/node_modules"),
            Path("/opt/homebrew/lib/node_modules"),
            # Official installers
            Path("/opt/claude-cli"),
            Path("/usr/local/claude-cli"),
            Path("/opt/homebrew/opt/claude-cli"),
            Path("/usr/local/opt/claude-cli"),
            # Claude Code Router (if installed)
            home / ".claude-code-router",
        ]

        # Add all /home/*/ directories for multi-user VPS
        for home_dir in Path("/home").glob("*"):
            if home_dir.is_dir():
                search_dirs.append(home_dir / ".npm" / "_npx")
                search_dirs.append(home_dir / ".nvm" / "versions" / "node")
                search_dirs.append(home_dir / ".local" / "lib" / "node_modules")
                search_dirs.append(home_dir / ".claude-cli")

    # ==================== SEARCH IN DIRECTORIES ====================
    for directory in search_dirs:
        if not directory.exists():
            continue

        # Direct cli.js
        direct_cli = directory / "cli.js"
        if direct_cli.exists():
            found_paths.append(str(direct_cli))

        # Scoped package path
        scoped_cli = directory / "@anthropic-ai" / "claude-code" / "cli.js"
        if scoped_cli.exists():
            found_paths.append(str(scoped_cli))

        # lib/cli.js pattern (common in claude.ai installer)
        lib_cli = directory / "lib" / "cli.js"
        if lib_cli.exists():
            found_paths.append(str(lib_cli))

        # Recursive search for scoped package
        try:
            for cli_js in directory.rglob("@anthropic-ai/claude-code/cli.js"):
                found_paths.append(str(cli_js))
        except (PermissionError, OSError):
            pass

    # ==================== FALLBACK: Use 'which claude' ====================
    try:
        result = subprocess.run(
            ["which", "claude"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            claude_bin = result.stdout.strip()
            # Resolve symlink to get actual path
            resolved = os.path.realpath(claude_bin)
            
            if os.path.isdir(resolved):
                # It's a directory, search for cli.js inside
                for js_file in search_js_files_in_dir(Path(resolved)):
                    if "cli" in js_file.lower():
                        found_paths.append(js_file)
            elif "cli.js" in resolved or "claude-code" in resolved:
                found_paths.append(resolved)
            else:
                # Check parent directory for cli.js
                parent_dir = Path(resolved).parent
                for js_file in search_js_files_in_dir(parent_dir):
                    if "cli" in js_file.lower():
                        found_paths.append(js_file)
    except Exception:
        pass

    # ==================== ERROR ====================
    if not found_paths:
        if is_windows:
            hint_paths = ["%LOCALAPPDATA%\\claude-cli", "%PROGRAMFILES%\\claude-cli"]
        else:
            hint_paths = [
                "~/.local/share/claude/versions/",
                "/usr/lib/node_modules/@anthropic-ai/claude-code/cli.js",
                "/usr/local/lib/node_modules/@anthropic-ai/claude-code/cli.js",
                "/opt/claude-cli",
                "/usr/local/claude-cli",
                "~/.claude-cli",
            ]
        raise FileNotFoundError(
            "Không tìm thấy Claude Code installation.\n\n"
            "Cài đặt bằng một trong các cách:\n"
            "  1. npm: npm install -g @anthropic-ai/claude-code\n"
            "  2. Official: curl -fsSL https://claude.ai/install.sh | bash\n\n"
            f"Kiểm tra các đường dẫn: {', '.join(hint_paths)}\n\n"
            "Hoặc dùng: python3 patcher.py --path /path/to/cli.js"
        )

    # Return the most recently modified one
    found_paths = list(dict.fromkeys(found_paths))  # Remove duplicates, preserve order
    found_paths.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    return found_paths[0]


# ---------------------------------------------------------------------------
# Patch logic
# ---------------------------------------------------------------------------

def find_bug_block(content: str):
    pattern = f'.includes("{DEL_CHAR}")'
    idx = content.find(pattern)

    if idx == -1:
        raise RuntimeError(
            'Không tìm thấy bug pattern .includes("\\x7f").\n'
            "Claude Code có thể đã được Anthropic fix."
        )

    block_start = content.rfind("if(", max(0, idx - 150), idx)
    if block_start == -1:
        raise RuntimeError("Không tìm thấy block if chứa pattern")

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
    normalized = block.replace(DEL_CHAR, "\\x7f")

    match = re.search(
        r"let ([\w$]+)=\(\w+\.match\(/\\x7f/g\)\|\|\[\]\)\.length[,;]([\w$]+)=([\w$]+)[;,]",
        normalized,
    )
    if not match:
        raise RuntimeError("Không trích xuất được biến count/state")

    state, cur_state = match.group(2), match.group(3)

    match_update = re.search(
        rf"([\w$]+)\({re.escape(state)}\.text\);([\w$]+)\({re.escape(state)}\.offset\)",
        block,
    )
    if not match_update:
        raise RuntimeError("Không trích xuất được update functions")

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
    backups = find_backups(file_path)
    return backups[0] if backups else None


def cleanup_old_backups(file_path: str):
    backups = find_backups(file_path)
    for old_backup in backups[MAX_BACKUPS:]:
        try:
            os.remove(old_backup)
        except OSError:
            pass


def patch(file_path: str, dry_run: bool = False):
    print(f"-> File: {file_path}")

    if not os.path.exists(file_path):
        print(f"Lỗi: File không tồn tại: {file_path}", file=sys.stderr)
        return 1

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
        block_start, block_end, block = find_bug_block(content)
        variables = extract_variables(block)
        print(
            "   Vars: input={input}, state={state}, cur={cur}".format(
                input=variables["input"], state=variables["state"], cur=variables["cur_state"]
            )
        )

        fix_code = generate_fix(variables)
        patched = content[:block_start] + fix_code + content[block_end:]

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(patched)

        with open(file_path, "r", encoding="utf-8") as f:
            new_content = f.read()
            if PATCH_MARKER not in new_content:
                raise RuntimeError("Verify failed: patch marker not found after write")

        new_checksum = hashlib.sha256(new_content.encode("utf-8")).hexdigest()
        print(f"   New SHA256: {new_checksum[:16]}...")

        cleanup_old_backups(file_path)

        print("\n   Patch thành công! Khởi động lại Claude Code.\n")
        return 0

    except Exception as exc:  # noqa: BLE001
        print(f"\nLỗi: {exc}", file=sys.stderr)
        print(
            "Báo lỗi tại: https://github.com/yeuvjaj252/claude-code-vietnamese-fix-safe/issues",
            file=sys.stderr,
        )
        if os.path.exists(backup_path):
            shutil.copy2(backup_path, file_path)
            os.remove(backup_path)
            print("Đã rollback về bản gốc.", file=sys.stderr)
        return 1


def restore(file_path: str):
    backup = find_latest_backup(file_path)
    if not backup:
        print(f"Không tìm thấy backup cho {file_path}", file=sys.stderr)
        return 1

    backup_checksum = sha256_file(backup)
    print(f"Backup SHA256: {backup_checksum[:16]}...")

    shutil.copy2(backup, file_path)
    print(f"Đã khôi phục từ: {backup}")
    print("Khởi động lại Claude Code.")
    return 0


def show_info():
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
    print("https://github.com/yeuvjaj252/claude-code-vietnamese-fix-safe")


def main():
    args = sys.argv[1:]

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
