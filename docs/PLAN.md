# Vietnamese Fix Tool - Plan

## Summary

Tool "claude-code-vietnamese-fix" được thiết kế để fix lỗi gõ tiếng Việt trong Claude Code CLI. Tool tự động phát hiện file `cli.js` của npm package, backup và patch trực tiếp để hỗ trợ các bộ gõ tiếng Việt (OpenKey, EVKey, PHTV, Unikey). Support cross-platform: macOS, Linux, Windows với cài đặt 1-click.

## Technical Analysis

### Problem

**Bug kỹ thuật:**
- Claude Code CLI xử lý ký tự DEL (`\x7f` / chr(127)) do các bộ gõ tiếng Việt tạo ra
- Khi gõ "a" → "á", IME gửi: backspace (ký tự DEL) + ký tự mới "á"
- Claude Code chỉ xử lý backspace, **không insert** ký tự thay thế
- Kết quả: ký tự bị "nuốt", text hiển thị sai

**Pattern bug trong cli.js:**
```javascript
if(input.includes("\x7f")) {
    let COUNT = (input.match(/\x7f/g)||[]).length;
    STATE = CURSTATE;
    // ... chỉ handle backspace, không insert replacement
}
```

### Solution

**Cách tiếp cận:**
1. Auto-detect vị trí `cli.js` trong npm cache
2. Tìm bug pattern `.includes("\x7f")`
3. Trích xuất variable names (dynamic, obfuscated)
4. Generate fix code với đúng variable names
5. Backup file gốc trước khi patch
6. Replace bug block bằng fix code

**Fix logic:**
```javascript
/* Vietnamese IME fix */
if(input.includes("\x7f")) {
    let _n = (input.match(/\x7f/g)||[]).length;
    let _vn = input.replace(/\x7f/g, "");
    state = cur_state;
    for(let _i = 0; _i < _n; _i++) state = state.backspace();
    for(const _c of _vn) state = state.insert(_c);
    if(!cur_state.equals(state)) {
        if(cur_state.text !== state.text)
            update_text(state.text);
        update_offset(state.offset)
    }
    return;
}
```

## Implementation Plan

### Phase 1: Setup
- [x] **Task 1.1**: Khảo sát reference repository
  - Phân tích `patcher.py` logic
  - Hiểu install.sh/install.ps1 workflow
  - Document variable extraction pattern
- [ ] **Task 1.2**: Tạo folder structure
  ```
  /claudetv/vietnamese-fix/
  ├── patcher.py
  ├── install.sh
  ├── install.ps1
  ├── README.md
  └── test.py (optional)
  ```
- [ ] **Task 1.3**: Kiểm tra dependencies
  - Python 3.x (standard library only)
  - Git (cho install scripts)
  - Không cần external packages

### Phase 2: Core Implementation
- [ ] **Task 2.1**: Port `patcher.py` từ reference
  - Giữ nguyên logic `find_cli_js()` - auto-detect
  - Giữ nguyên `find_bug_block()` - tìm pattern
  - Giữ nguyên `extract_variables()` - regex extraction
  - Giữ nguyên `generate_fix()` - code generation
  - Backup/restore functionality
  - Error handling & rollback

- [ ] **Task 2.2**: Cải tiến (optional)
  - Thêm logging chi tiết hơn
  - Thêm version check cho cli.js
  - Support multiple CLI locations
  - Better error messages (tiếng Việt)

- [ ] **Task 2.3**: Test local patching
  - Test auto-detection
  - Test backup creation
  - Test patch application
  - Test restore functionality
  - Test error cases (file not found, already patched)

### Phase 3: Installers
- [ ] **Task 3.1**: Port `install.sh` (macOS/Linux)
  - Check git & python availability
  - Clone repo vào `~/.claude-vn-fix`
  - Auto-run patcher sau install
  - Handle update (git pull)

- [ ] **Task 3.2**: Port `install.ps1` (Windows)
  - PowerShell compatible
  - Check dependencies
  - Clone & auto-patch
  - Handle Windows paths

- [ ] **Task 3.3**: Test installers
  - Test fresh install (no existing folder)
  - Test update (folder exists)
  - Test dependency checks
  - Test auto-patch workflow

### Phase 4: Testing & Documentation
- [ ] **Task 4.1**: Tạo `test.py`
  - Test variable extraction regex
  - Test fix code generation
  - Mock cli.js với bug pattern
  - Verify patch correctness

- [ ] **Task 4.2**: Documentation `README.md`
  - Tiếng Việt, dễ hiểu
  - Installation instructions (3 platforms)
  - Usage guide (fix, restore, update)
  - Troubleshooting section
  - Credits

- [ ] **Task 4.3**: Final testing
  - End-to-end test trên mỗi platform
  - Test với Claude Code CLI thật
  - Verify tiếng Việt gõ đúng

## File Structure

```
/claudetv/
├── .opencode/                    # Existing OpenCode config
│   ├── commands/
│   ├── agents/
│   └── skills/
├── package.json                  # Existing (Bun)
└── vietnamese-fix/               # NEW: Tool folder
    ├── patcher.py                # Main Python script (~250 lines)
    ├── install.sh                # macOS/Linux installer (~50 lines)
    ├── install.ps1               # Windows installer (~50 lines)
    ├── README.md                 # Documentation (Vietnamese)
    └── test.py                   # Test script (optional, ~100 lines)
```

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| **cli.js location changes** | Medium | High | Update `find_cli_js()` với new paths; user can use `--path` flag |
| **Anthropic fixes bug upstream** | Low | Medium | Tool detects & reports; no patch needed |
| **Variable names change** | Low | High | Regex patterns need update; test.py catches this |
| **Permission issues** | Medium | Medium | Document running as admin/sudo when needed |
| **Backup disk space** | Low | Low | Backups are small (~1MB each); can add cleanup |
| **Python version compatibility** | Low | Low | Use Python 3.6+ features only; test on multiple versions |
| **Windows path encoding** | Medium | Medium | Use `pathlib` for cross-platform; test on Windows |

## Testing Strategy

### Unit Tests (`test.py`)
```python
# Test cases:
1. test_find_bug_block() - valid pattern detection
2. test_extract_variables() - regex matching
3. test_generate_fix() - correct code output
4. test_backup_restore() - file operations
5. test_already_patched() - idempotency
```

### Integration Tests
```bash
# Manual test workflow:
1. Install Claude Code CLI: npm install -g @anthropic-ai/claude-code
2. Run patcher: python3 patcher.py
3. Verify backup created
4. Verify patch marker in cli.js
5. Test Vietnamese input in Claude Code
6. Test restore: python3 patcher.py --restore
```

### Platform-Specific Tests
| Platform | Test |
|----------|------|
| macOS | `install.sh`, Homebrew node, OpenKey |
| Linux | `install.sh`, nvm node, IBus/Bamboo |
| Windows | `install.ps1`, npm node, Unikey |

## Estimated Effort

| Phase | Tasks | Time Estimate |
|-------|-------|---------------|
| **Phase 1: Setup** | 3 tasks | 1-2 hours |
| **Phase 2: Core** | 3 tasks | 3-4 hours |
| **Phase 3: Installers** | 3 tasks | 2-3 hours |
| **Phase 4: Testing** | 3 tasks | 2-3 hours |
| **Total** | 12 tasks | **8-12 hours** |

## Dependencies

### Required
- Python 3.6+ (standard library only)
- Git (for install scripts)
- Claude Code CLI installed via npm

### Optional
- Node.js (for testing with actual CLI)

## Next Steps

1. **Approval**: Review plan với user
2. **Implementation**: Begin Phase 1
3. **Testing**: Comprehensive testing trên 3 platforms
4. **Deployment**: Publish GitHub repo
5. **Distribution**: 1-click install scripts

---

**Ghi chú**: Plan này giữ nguyên 100% logic từ reference repository, chỉ different ở folder location (`/claudetv/vietnamese-fix/` thay vì standalone repo). Có thể improve documentation và error messages.
