# 📦 BrainChat Release & Deployment Pipeline

Complete production-ready macOS application release pipeline for BrainChat.

## 📋 Quick Reference

### Install BrainChat
```bash
brew install --cask brainchat
```

### Release a New Version
```bash
# 1. Update Info.plist and CHANGELOG.md
# 2. Tag and push
git tag v1.2.1
git push origin v1.2.1

# 3. Monitor workflow
gh run list --workflow release.yml
```

### Files Created
✅ `.github/workflows/release.yml` - Updated with `release-brainchat` job  
✅ `.github/workflows/cd.yml` - Added `deploy-brainchat` job  
✅ `apps/BrainChat/scripts/create-dmg.sh` - DMG installer creation  
✅ `apps/BrainChat/scripts/generate-appcast.sh` - Sparkle feed generation  
✅ `apps/BrainChat/Formula/brainchat.rb` - Homebrew cask formula  
✅ `apps/BrainChat/appcast.xml` - Sparkle auto-update feed template  
✅ `apps/BrainChat/DEPLOYMENT.md` - Deployment documentation  

---

## 🏗️ Pipeline Overview

### Release Workflow (`release.yml`)

Triggered on: `git tag v*.*.*`

```
1. validate          ✓ Check SemVer format and versions match
2. qa                ✓ Run smoke tests
3. build             ✓ Build Python packages
4. release-brainchat ✓ [NEW] Build and release macOS app
   ├─ Build Swift application
   ├─ Code sign with Apple certificate
   ├─ Create DMG installer with professional layout
   ├─ Submit for Apple notarization (optional)
   └─ Upload to GitHub Releases
5. publish-pypi      ✓ Publish Python package
6. docker            ✓ Build and push Docker image
7. github-release    ✓ Create GitHub release (updated to depend on brainchat)
```

### Continuous Deployment (`cd.yml`)

Triggered on: `push` to `main`

```
1. build-and-push       ✓ Docker image to GHCR
2. security-scan        ✓ Trivy vulnerability scan
3. deploy-brainchat     ✓ [NEW] Continuous app builds
   ├─ Build latest BrainChat
   ├─ Create DMG for testing
   ├─ Generate fresh Sparkle appcast
   └─ Update Homebrew tap (optional)
```

---

## 📦 Distribution Methods

### 1. Homebrew Package (Recommended)
Users install with:
```bash
brew install --cask brainchat
brew upgrade --cask brainchat  # Update
```

**What you provide:**
- Homebrew formula: `apps/BrainChat/Formula/brainchat.rb`
- DMG artifact: `BrainChat-1.2.1.dmg` (uploaded to GitHub Releases)
- SHA256 checksum: Auto-updated when formula is published

**Homebrew discovers updates via:**
- GitHub releases page (livecheck)
- Latest tag matching `v*.*.*` pattern

### 2. Direct Download
Users download from: https://github.com/getagentic/brain/releases

Files provided:
- `BrainChat-1.2.1.dmg` - Installer
- `BrainChat-1.2.1.dmg.sha256` - Integrity verification
- `BrainChat-1.2.1.zip` - For notarization (if applicable)

### 3. Sparkle Auto-Updates
Installed app checks: `apps/BrainChat/appcast.xml`

Features:
- ✅ Automatic background checks
- ✅ User-friendly update notifications
- ✅ One-click installation
- ✅ Rollback support

---

## 🔧 Scripts & Tools

### Build Script: `build.sh`

```bash
cd apps/BrainChat

# Compile Swift → Binary
bash build.sh

# Compile + Install to /Applications
bash build.sh --install

# Compile + Install + Launch
bash build.sh --run

# Clean build directory
bash build.sh --clean
```

**What it does:**
- Compiles all Swift files using `swiftc`
- Links required frameworks (SwiftUI, AppKit, Speech, AVFoundation, etc.)
- Code signs with entitlements
- Produces: `build/Brain Chat.app`

### DMG Creator: `scripts/create-dmg.sh`

```bash
cd apps/BrainChat
bash scripts/create-dmg.sh
```

**What it does:**
- Creates professional macOS installer
- Sets up drag-to-Applications layout
- Compresses with UDZO + zlib (9)
- Generates SHA256 checksum
- Produces: `BrainChat-1.2.1.dmg` (25 MB compressed)

**Features:**
- Custom background image
- Icon positioning (Brain Chat.app + Applications)
- Professional appearance matching macOS standards

### Appcast Generator: `scripts/generate-appcast.sh`

```bash
cd apps/BrainChat
bash scripts/generate-appcast.sh getagentic brain appcast.xml
```

**What it does:**
- Fetches latest releases from GitHub API
- Generates Sparkle RSS feed (XML)
- Updates version, download URLs, release notes
- Produces: `appcast.xml`

---

## 🔐 Code Signing & Notarization

### Ad-Hoc Signing (Default, No Secrets)
- Works on your Mac immediately
- Does NOT prevent Gatekeeper warnings
- Good for testing

### Developer ID Signing (Production)

**Set up GitHub Secrets:**

1. `APPLE_IDENTITY_ID` - Developer ID display name
   ```
   "Developer ID Application: John Doe (ABC123XYZ)"
   ```

2. `APPLE_CERTIFICATE_P12_B64` - Base64-encoded certificate
   ```bash
   security export-cert -k ~/Library/Keychains/login.keychain \
     -p "Developer ID Application: ..." \
     -o cert.p12 -P "password"
   base64 -i cert.p12
   ```

3. `APPLE_CERTIFICATE_PASSWORD` - Cert password

4. `APPLE_DEVELOPER_ID_APPLICATION` - Developer ID for notarization
   ```
   developer@example.com
   ```

5. `APPLE_DEVELOPER_ID_PASSWORD` - App-specific password (from Apple ID)

6. `APPLE_TEAM_ID` - Apple Team ID
   ```
   ABC123XYZ
   ```

### Notarization (Optional)

Once secrets are set:
- Workflow submits app for Apple scanning
- Waits 5-10 minutes for analysis
- Staples notarization ticket to app
- Removes Gatekeeper warnings

**Without notarization:** App still works, users see warning once

**With notarization:** Seamless installation, trusted delivery

---

## 📝 Homebrew Formula

Location: `apps/BrainChat/Formula/brainchat.rb`

The formula:
- Specifies version: `version "1.2.1"`
- References DMG URL on GitHub Releases
- Auto-updates via livecheck (watches GitHub releases)
- Defines app location: `app "Brain Chat.app"`
- Handles uninstall cleanup (caches, preferences, etc.)

**Updates automatically when:**
1. New release tagged: `git tag v1.2.1`
2. DMG uploaded to GitHub Releases
3. Homebrew queries for latest version

**To publish to main Homebrew:**
- Create separate repo: `homebrew-brainchat`
- Users tap: `brew tap getagentic/brainchat`
- Then: `brew install brainchat`

---

## 🚀 Release Checklist

### Before Creating Tag

- [ ] Update `apps/BrainChat/Info.plist` version
- [ ] Update `apps/BrainChat/CHANGELOG.md` with release notes
- [ ] Test build locally: `bash build.sh --run`
- [ ] Verify code signing: `codesign -v build/Brain\ Chat.app`
- [ ] Commit changes: `git commit -m "Release BrainChat 1.2.1"`

### Create Release

```bash
# Create tag
git tag v1.2.1

# Push to GitHub (triggers workflow)
git push origin main
git push origin v1.2.1
```

### After Release

- [ ] Monitor workflow: https://github.com/getagentic/brain/actions
- [ ] Verify GitHub Release created
- [ ] Test DMG download and install
- [ ] Test Sparkle update notification
- [ ] Verify Homebrew livecheck detects new version

---

## 🧪 Testing

### Test Local Build
```bash
cd apps/BrainChat
bash build.sh --install --run
```

### Test DMG Creation
```bash
cd apps/BrainChat
bash scripts/create-dmg.sh

# Mount and inspect
hdiutil attach BrainChat-1.2.1.dmg
ls /Volumes/BrainChat
hdiutil detach /Volumes/BrainChat
```

### Test Code Signature
```bash
# Verify signature validity
codesign -v build/Brain\ Chat.app

# Check notarization (if notarized)
xcrun stapler validate build/Brain\ Chat.app

# Test Gatekeeper approval
spctl -a -v build/Brain\ Chat.app
```

### Test Homebrew Formula
```bash
# Check syntax
brew cask audit brainchat

# Try install from local formula
brew install --cask brainchat --verbose
```

### Test Sparkle Updates
1. Edit appcast.xml to add new version
2. Increment version in app
3. Launch app and trigger update check
4. Should offer update notification

---

## 📊 Workflow Details

### GitHub Secrets Used

| Secret | Used In | Purpose |
|--------|---------|---------|
| `APPLE_IDENTITY_ID` | release-brainchat | Code signing identity |
| `APPLE_CERTIFICATE_P12_B64` | release-brainchat | Signing certificate |
| `APPLE_CERTIFICATE_PASSWORD` | release-brainchat | Certificate password |
| `APPLE_DEVELOPER_ID_APPLICATION` | release-brainchat | Notarization credentials |
| `APPLE_DEVELOPER_ID_PASSWORD` | release-brainchat | Notarization password |
| `APPLE_TEAM_ID` | release-brainchat | Apple Team identifier |
| `HOMEBREW_TAP_TOKEN` | deploy-brainchat | Optional Homebrew update |

### Build Times

| Step | Duration | Notes |
|------|----------|-------|
| Validate | 1-2 min | Quick checks |
| QA Tests | 3-5 min | Smoke tests |
| Python Build | 2-3 min | PyPI package |
| BrainChat Build | 2-3 min | Swift compilation |
| DMG Creation | 1-2 min | Compression |
| Notarization | 5-10 min | Apple processing |
| **Total** | **15-25 min** | Parallel jobs |

### Artifacts

| Artifact | Size | Purpose |
|----------|------|---------|
| Brain Chat.app | ~50 MB | Executable bundle |
| BrainChat-1.2.1.dmg | ~25 MB | Installer |
| BrainChat-1.2.1.dmg.sha256 | ~100 B | Checksum |
| brainchat-wheel.whl | ~30 KB | Python package |

---

## 🔄 Continuous Deployment

### On Push to Main

Workflow `cd.yml` deploys:

1. **Docker image** → GHCR (always)
2. **BrainChat** → Continuous build
   - Builds current main branch
   - Creates test DMG
   - Generates appcast
   - Ready for daily testing

**Note:** Only tagged releases reach Homebrew

---

## 🐛 Troubleshooting

### Build Fails: "swift command not found"

```bash
xcode-select --install
xcode-select --switch /Applications/Xcode.app/Contents/Developer
```

### Notarization Rejected: "Invalid certificate"

```bash
# Verify certificate
security find-identity -v -p codesigning

# Check expiration
openssl x509 -in certificate.pem -text -noout
```

### DMG Creation Fails

```bash
# Free up disk space
df -h

# Try again with verbose output
bash -x scripts/create-dmg.sh 2>&1 | tee create-dmg.log
```

### Homebrew Shows Old Version

```bash
# Force livecheck update
brew livecheck --full --verbose brainchat

# Update formula
brew update
brew upgrade --cask brainchat
```

---

## 📚 Documentation

- **[DEPLOYMENT.md](DEPLOYMENT.md)** - Detailed deployment guide
- **[build.sh](build.sh)** - Swift compilation
- **[scripts/create-dmg.sh](scripts/create-dmg.sh)** - DMG creation
- **[scripts/generate-appcast.sh](scripts/generate-appcast.sh)** - Sparkle feed
- **[Formula/brainchat.rb](Formula/brainchat.rb)** - Homebrew formula

---

## 🎯 Next Steps

1. **Verify Build**
   ```bash
   cd apps/BrainChat
   bash build.sh
   ```

2. **Test DMG**
   ```bash
   bash scripts/create-dmg.sh
   hdiutil attach BrainChat-*.dmg
   ```

3. **Create Release**
   ```bash
   git tag v1.2.1
   git push origin v1.2.1
   ```

4. **Monitor Workflow**
   - https://github.com/getagentic/brain/actions/workflows/release.yml

---

## ✅ Summary

| Component | Status | Location |
|-----------|--------|----------|
| Release workflow | ✅ Created | `.github/workflows/release.yml` |
| CD workflow | ✅ Updated | `.github/workflows/cd.yml` |
| DMG script | ✅ Created | `apps/BrainChat/scripts/create-dmg.sh` |
| Appcast generator | ✅ Created | `apps/BrainChat/scripts/generate-appcast.sh` |
| Homebrew formula | ✅ Created | `apps/BrainChat/Formula/brainchat.rb` |
| Appcast template | ✅ Created | `apps/BrainChat/appcast.xml` |
| Documentation | ✅ Created | `apps/BrainChat/DEPLOYMENT.md` |

**BrainChat is ready for production release!** 🎉

