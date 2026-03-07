# PLAN: Binary Patch Support for Vietnamese IME Fix

## Bối cảnh

Script `patcher.py` hiện tại chỉ hỗ trợ patch file `cli.js` (cài qua npm). Khi Claude Code được cài dạng **binary** (ví dụ qua `curl -fsSL https://claude.ai/install.sh | bash`), file thực thi là một Bun-compiled binary, không có `cli.js` riêng.

### Phát hiện từ repo tham khảo (0x0a0d/fix-vietnamese-claude-code)

Repo này đã giải quyết vấn đề bằng cách:

1. **Binary Bun chứa JS source bên trong** - Bun compiler nhúng toàn bộ JS source vào binary, có thể tìm thấy cùng pattern `.includes("\x7f")` trong nội dung binary.
2. **Patch trực tiếp binary** - Áp dụng cùng regex replacement như với `.js` file, nhưng đọc/ghi bằng encoding `latin1`.
3. **Giữ cấu trúc binary** - Sau khi patch (nội dung dài hơn), cần tìm marker `\x00// @bun` trong binary, rồi xóa bớt bytes thừa (bằng đúng số bytes chênh lệch) tại vị trí `\n//` sau marker đó để binary không bị lệch size.

## Kế hoạch triển khai

### Phase 1: Cập nhật detection logic

**File:** `vietnamese-fix/patcher.py`

**Tasks:**
- [ ] Thêm detection cho binary file (không chỉ `cli.js`)
  - Tìm `~/.local/bin/claude` (binary thường ở đây)
  - Tìm `~/.local/share/claude/versions/*/claude` (versioned binary)
  - Check xem file tìm được là JS hay binary (kiểm tra có phải text file không)
- [ ] Hàm `is_binary_file(path)` - kiểm tra file có phải binary không (đọc vài bytes đầu, check null bytes)

### Phase 2: Binary patching logic

**File:** `vietnamese-fix/patcher.py`

**Tasks:**
- [ ] Hàm `find_bug_block_binary(content: bytes)` - tìm pattern trong binary content
  - Đọc file bằng encoding `latin1` (giữ nguyên bytes)
  - Tìm cùng pattern `.includes("\x7f")` trong binary string
- [ ] Hàm `patch_binary(file_path, dry_run)`:
  1. Đọc file binary bằng `latin1` encoding
  2. Áp dụng cùng regex replacement logic như `patchContentJs` của 0x0a0d
  3. Tính offset delta (new_length - old_length)
  4. Tìm marker `\x00// @bun` trong content
  5. Tìm `\n//` sau marker
  6. Xóa đúng `delta` bytes tại vị trí đó để giữ binary size alignment
  7. Ghi file bằng `latin1` encoding
- [ ] Backup và rollback giữ nguyên logic hiện tại

### Phase 3: Cập nhật flow chính

**File:** `vietnamese-fix/patcher.py`

**Tasks:**
- [ ] Cập nhật `find_cli_js()` → rename thành `find_claude_file()`, trả về cả binary paths
- [ ] Cập nhật `patch()` function:
  - Detect file type (JS vs binary)
  - Gọi `patch_binary()` nếu là binary
  - Gọi logic hiện tại nếu là JS
- [ ] Cập nhật `--info` để hiển thị loại file (JS/binary)

### Phase 4: Testing

- [ ] Test với binary installation thực tế
- [ ] Test dry-run mode với binary
- [ ] Test backup/restore với binary
- [ ] Test rollback khi patch fail

## Chi tiết kỹ thuật quan trọng

### Binary size alignment

Khi patch binary Bun, nội dung replacement thường **dài hơn** original. Bun binary có metadata/offset tables nên **phải giữ nguyên tổng file size**. Cách làm:

```
delta = len(new_content) - len(original_content)  # bytes thêm vào

# Tìm vùng comment có thể cắt bớt
bun_marker = content.find('\x00// @bun')
comment_area = content.find('\n//', bun_marker)  # vùng comment sau marker

# Xóa đúng delta bytes tại comment_area
patched = content[:comment_area] + content[comment_area + delta:]
```

### Encoding

- Binary files: đọc/ghi bằng `latin1` (1 byte = 1 char, không mất data)
- JS files: giữ nguyên `utf-8` như hiện tại

### Detection priority

1. Nếu user chỉ định `--path` → dùng file đó, auto-detect type
2. Tìm `cli.js` (npm) → ưu tiên nếu có
3. Tìm binary `claude` → fallback

## Agent assignments

| Task | Agent |
|------|-------|
| Phase 1-3: Implementation | backend-specialist |
| Phase 4: Testing | test-engineer |

## Verification checklist

- [ ] Patch hoạt động với npm installation (regression test)
- [ ] Patch hoạt động với binary installation
- [ ] `--dry-run` hiển thị đúng thông tin cho cả 2 loại
- [ ] `--restore` hoạt động cho cả 2 loại
- [ ] `--info` hiển thị đúng loại file
- [ ] Binary sau khi patch vẫn chạy được (không bị corrupt)
- [ ] Rollback hoạt động khi patch fail
