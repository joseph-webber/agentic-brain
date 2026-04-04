# BrainChat Security Model - Quick Reference

## 🔐 Security Tiers at a Glance

| Feature | FULL_ADMIN | SAFE_ADMIN | USER | GUEST |
|---------|------------|------------|------|-------|
| **Icon** | 🔓 Red | 🛡️ Green | 👤 Orange | 👋 Blue |
| **YOLO Mode** | ✅ No confirm | ✅ With confirm | ❌ | ❌ |
| **Filesystem** | ✅ Full | ✅ Full* | ❌ | ❌ |
| **Code Execution** | ✅ | ✅* | ❌ | ❌ |
| **API Access** | ✅ All | ✅ All | ✅ Limited | ❌ |
| **Rate Limits** | None | None | Yes | N/A |

*With confirmation dialogs for dangerous operations

## 🎯 Use Cases

### FULL_ADMIN (Joseph)
```swift
// Default for Joseph - unrestricted access
SecurityManager.shared.switchRole(to: .fullAdmin)
```
**When to use:** Joseph's daily work, full automation needed

### SAFE_ADMIN (Developers)
```swift
// Developers with guardrails
SecurityManager.shared.switchRole(to: .safeAdmin)
```
**When to use:** Development/testing with safety confirmations

### USER (Customers)
```swift
// Customer access - API only
SecurityManager.shared.switchRole(to: .user)
```
**When to use:** Customer portal access, LLM features only

### GUEST (Anonymous)
```swift
// Public access - help only
SecurityManager.shared.switchRole(to: .guest)
```
**When to use:** Public demos, FAQ, help content

## ⚠️ Dangerous Operations (SAFE_ADMIN Confirmations)

The following operations require confirmation in SAFE_ADMIN mode:

### File Operations
- File deletions
- Editing system files (`/etc/`, `/System/`, `/Library/`)
- Modifying configuration files (`.plist`, `package.json`, `requirements.txt`)

### Shell Commands
- `rm -rf` or `delete`
- `sudo` commands
- `chmod` or `chown`
- `git push`
- `git reset --hard`

### System Operations
- Network operations
- System-level changes

## 📝 Code Examples

### Checking Permissions
```swift
// Check YOLO access
if SecurityManager.shared.canUseYolo() {
    // YOLO mode available
}

// Check filesystem access
if SecurityManager.shared.canWriteFiles() {
    // Can write files
}

// Check API access
if SecurityManager.shared.canUseProvider(.claude) {
    // Can use Claude API
}
```

### Implementing Confirmations
```swift
// In SAFE_ADMIN mode, dangerous operations trigger confirmation
let confirmed = await confirmationHandler("Delete file: important.txt")
if confirmed {
    // Proceed with operation
}
```

## 🧪 Testing

Run security tests:
```bash
swift test --filter Security
```

All tests:
```bash
swift test
```

Build:
```bash
swift build
```

## 🔄 Migration

Legacy roles are automatically upgraded:
- `admin` → `fullAdmin` (FULL_ADMIN)
- `user` → `user` (USER with new restrictions)
- `guest` → `guest` (GUEST with help-only access)

## 🎨 UI Integration

The SecurityModeView automatically displays all 4 modes with:
- Color-coded indicators
- VoiceOver accessibility
- Keyboard navigation
- Confirmation dialogs for downgrades

## 📊 Permission Matrix

| Permission | Full Admin | Safe Admin | User | Guest |
|------------|-----------|-----------|------|-------|
| Read files | ✅ | ✅ | ❌ | ❌ |
| Write files | ✅ | ✅* | ❌ | ❌ |
| Delete files | ✅ | ✅* | ❌ | ❌ |
| Execute code | ✅ | ✅* | ❌ | ❌ |
| Shell commands | ✅ | ✅* | ❌ | ❌ |
| Git operations | ✅ | ✅* | ❌ | ❌ |
| LLM APIs | ✅ | ✅ | ✅** | ❌ |

*Requires confirmation for dangerous operations
**With rate limits

## 🚀 Quick Start

1. **For Joseph (Default):**
   - Automatically set to FULL_ADMIN
   - No confirmations needed
   - Full unrestricted access

2. **For Developers:**
   - Switch to SAFE_ADMIN in Settings
   - Dangerous operations will prompt for confirmation
   - Test code safely

3. **For Customers:**
   - Set to USER role
   - API access only, no code execution
   - Rate limits apply

4. **For Public Demo:**
   - Set to GUEST role
   - Help content only
   - No external access

## 📚 Related Files

- `Sources/BrainChat/Security/SecurityRole.swift` - Role definitions
- `Sources/BrainChat/Security/SecurityManager.swift` - Permission manager
- `Sources/BrainChat/Security/PermissionChecker.swift` - Permission logic
- `YoloExecutor.swift` - YOLO execution with confirmations
- `Sources/BrainChat/Security/SecurityModeView.swift` - UI components
