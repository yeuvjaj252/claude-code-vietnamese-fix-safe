# Claude Code Vietnamese IME Fix - Safe Edition

Fix lỗi gõ tiếng Việt trong Claude Code CLI với các bộ gõ OpenKey, EVKey, PHTV, Unikey...
Hỗ trợ macOS, Linux và Windows (npm).

**Safe Edition** với các tính năng bảo mật:
- ✅ Dry-run mode (test không áp dụng)
- ✅ Backup với checksum verification
- ✅ Auto rollback khi lỗi
- ✅ Giới hạn số backup (max 5)
- ✅ SHA256 verification

## Vấn đề

Các bộ gõ tiếng Việt gửi chuỗi: backspace (ký tự DEL `\x7f`) + ký tự mới.
Claude Code CLI chỉ xử lý backspace nhưng **không insert** ký tự thay thế,
dẫn đến ký tự bị "nuốt".

## Cài đặt nhanh

### macOS / Linux
```bash
curl -fsSL https://raw.githubusercontent.com/manhit96/claude-code-vietnamese-fix/main/install.sh | bash
```

### Windows (PowerShell)
```powershell
irm https://raw.githubusercontent.com/manhit96/claude-code-vietnamese-fix/main/install.ps1 | iex
```

> Lần đầu chạy sẽ tự động patch luôn.

## Sử dụng

```bash
# Kiểm tra thông tin CLI (không thay đổi gì)
python3 patcher.py --info

# Chạy thử không áp dụng thay đổi (safe)
python3 patcher.py --dry-run

# Auto-detect và patch thật
python3 patcher.py

# Khôi phục từ backup mới nhất
python3 patcher.py --restore

# Patch file cụ thể
python3 patcher.py --path /path/to/cli.js

# Hướng dẫn
python3 patcher.py --help
```

## Sau khi update Claude Code

Nếu bạn update Claude Code, hãy chạy lại patch:

```bash
python3 ~/.claude-vn-fix/patcher.py
```

Windows:
```powershell
python $env:USERPROFILE\.claude-vn-fix\patcher.py
```

## Cách hoạt động

1. Tự động tìm `cli.js` của npm `@anthropic-ai/claude-code`
2. Tính SHA256 checksum file gốc
3. Tìm bug pattern `.includes("\x7f")`
4. Trích xuất tên biến động (obfuscated)
5. Backup file gốc với checksum verification
6. Thay block lỗi bằng code fix: backspace + insert ký tự thay thế
7. Verify patch marker đã được thêm
8. Dọn backup cũ (giữ max 5)

## Các lệnh tiện dụng

| Lệnh | Mô tả |
|------|-------|
| `--info` | Kiểm tra CLI path, status (patched/not) |
| `--dry-run` | Chạy thử, xem variables, không thay đổi |
| (không flag) | Auto-detect và patch |
| `--restore` | Khôi phục từ backup mới nhất |
| `--path FILE` | Chỉ định file cụ thể |

```bash
# Workflow an toàn:
python3 patcher.py --info      # 1. Kiểm tra
python3 patcher.py --dry-run   # 2. Test trước
python3 patcher.py             # 3. Patch thật
```

## Troubleshooting

### Không tìm thấy Claude Code npm
```bash
npm install -g @anthropic-ai/claude-code
```

### Permission denied
```bash
# Linux/macOS
sudo python3 patcher.py

# Windows: chạy PowerShell as Administrator
```

### Đã patch trước đó
Tool sẽ báo và không patch lại (idempotent).

### Muốn xem trước khi patch?
```bash
python3 patcher.py --dry-run
```

### Khôi phục file gốc?
```bash
python3 patcher.py --restore
```

### Nhiều backup quá?
Tool tự động giữ max 5 backup mới nhất.

## Uninstall / Rollback

```bash
# 1. Khôi phục cli.js
python3 ~/.claude-vn-fix/patcher.py --restore

# 2. Xóa folder tool
rm -rf ~/.claude-vn-fix
```

## Safety Features

| Feature | Mô tả |
|---------|-------|
| SHA256 Checksum | Verify backup integrity |
| Dry-run mode | Test không thay đổi file |
| Auto rollback | Tự khôi phục khi lỗi |
| Max backups | Giữ tối đa 5 backup |
| Idempotent | Patch 1 lần duy nhất |
| Info mode | Xem status không thay đổi |

## Credits

Tham khảo và cải tiến từ [manhit96/claude-code-vietnamese-fix](https://github.com/manhit96/claude-code-vietnamese-fix).

## License

MIT
