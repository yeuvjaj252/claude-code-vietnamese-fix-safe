# Claude Code Vietnamese IME Fix (Safe Edition)

Tool fix lỗi gõ tiếng Việt trong **Claude Code CLI** (npm) cho các bộ gõ OpenKey/EVKey/Unikey…
Safe edition bổ sung **dry-run, checksum, rollback, giới hạn backup (max 5)**.

## Quick Start (5 phút)
```bash
# Clone
git clone https://github.com/yeuvjaj252/claude-code-vietnamese-fix-safe.git
cd claude-code-vietnamese-fix-safe/vietnamese-fix

# Kiểm tra & patch
python3 patcher.py --info    # xem cli.js target
python3 patcher.py --dry-run # thử, không đổi file
python3 patcher.py           # patch thật
```

## Features
- Auto-detect `cli.js` (npm global, nvm, system paths)
- Patch bug IME `\x7f` (DEL) → backspace + insert ký tự thay thế
- Backup với SHA256 checksum, rollback khi lỗi
- Giữ tối đa 5 backup gần nhất
- Dry-run & info mode (an toàn trước khi patch)
- Restore từ backup mới nhất
- Cross-platform: macOS / Linux / Windows (PowerShell)

## Installation

### macOS / Linux
```bash
curl -fsSL https://raw.githubusercontent.com/yeuvjaj252/claude-code-vietnamese-fix-safe/master/vietnamese-fix/install.sh | bash
```

### Windows (PowerShell)
```powershell
irm https://raw.githubusercontent.com/yeuvjaj252/claude-code-vietnamese-fix-safe/master/vietnamese-fix/install.ps1 | iex
```

### Thủ công
```bash
git clone https://github.com/yeuvjaj252/claude-code-vietnamese-fix-safe.git
cd claude-code-vietnamese-fix-safe/vietnamese-fix
python3 patcher.py --info
python3 patcher.py --dry-run
python3 patcher.py
```

## Usage
```bash
python3 patcher.py --info       # Xem cli.js, trạng thái patched
python3 patcher.py --dry-run    # Thử, không ghi file
python3 patcher.py              # Patch thật (auto-detect)
python3 patcher.py --path FILE  # Patch file cụ thể
python3 patcher.py --restore    # Khôi phục backup mới nhất
python3 patcher.py --help       # Trợ giúp
```

## Configuration
- Không cần ENV. Các flag CLI:
  - `--info`, `--dry-run`, `--path FILE`, `--restore`, `--auto` (alias), `--help`
- Backup giữ tối đa 5 bản, kèm checksum.

## Troubleshooting
- **Không tìm thấy Claude Code**: `npm install -g @anthropic-ai/claude-code`
- **Permission denied**: Linux/macOS `sudo python3 patcher.py`; Windows chạy PowerShell as Admin
- **Đã patch trước đó**: Tool báo và thoát 0
- **Cần xem trước**: `--dry-run`
- **Rollback**: `--restore`
- **Nhiều node versions (nvm)**: Mỗi version có `cli.js` riêng → chạy patcher sau khi switch node

## Contributing
1) Fork repo
2) Tạo branch: `git checkout -b feat/your-feature`
3) Chạy tests nhẹ: `python3 vietnamese-fix/test.py`
4) Gửi PR

## License
MIT
