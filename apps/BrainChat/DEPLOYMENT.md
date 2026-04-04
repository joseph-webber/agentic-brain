# 🚀 BrainChat Deployment & Release Pipeline

Complete deployment and release pipeline for **BrainChat** macOS application.

## Quick Start

### Install BrainChat

```bash
brew install --cask brainchat
```

### Update BrainChat

```bash
brew upgrade --cask brainchat
```

---

## Release Architecture

### Release Pipeline (`release.yml`)

Triggered on git tag push (e.g., `git tag v1.2.0`):

1. **validate** - Verify SemVer and extract version
2. **qa** - Run smoke tests  
3. **build** - Build Python packages
4. **release-brainchat** - Build and sign macOS app
   - Build Swift application
   - Code sign with Apple certificate
   - Create DMG installer
   - Apple notarization
   - Upload to GitHub Releases
5. **github-release** - Create GitHub release with all artifacts

### Continuous Deployment (`cd.yml`)

On push to `main`:

1. **build-and-push** - Docker image to GHCR
2. **security-scan** - Trivy vulnerability scan
3. **deploy-brainchat** - Build BrainChat for continuous updates
   - Build Swift application
   - Create DMG installer
   - Generate Sparkle appcast
   - Update Homebrew tap (optional)

---

## Installation Methods

### Method 1: Homebrew (Recommended)

```bash
# Install
brew install --cask brainchat

# Check version
brainchat --version

# Uninstall
brew uninstall --cask brainchat
```

Formula: `apps/BrainChat/Formula/brainchat.rb`

### Method 2: Download from GitHub

Visit: https://github.com/getagentic/brain/releases

1. Download DMG installer
2. Double-click to mount
3. Drag "Brain Chat.app" to Applications
4. Eject DMG

### Method 3: Manual Build

```bash
cd apps/BrainChat
bash build.sh --install --run
```

---

## Sparkle Auto-Updates

BrainChat supports automatic updates via Sparkle framework.

### Enable Updates

Add to `Info.plist`:

```xml
<key>SUFeedURL</key>
<string>https://raw.githubusercontent.com/getagentic/brain/main/apps/BrainChat/appcast.xml</string>
<key>SUShowReleaseNotes</key>
<true/>
<key>SUAutomaticallyUpdate</key>
<true/>
```

### Appcast Location

`apps/BrainChat/appcast.xml` - Sparkle RSS 2.0 feed

### Auto-Generate Appcast

```bash
cd apps/BrainChat
bash scripts/generate-appcast.sh getagentic brain appcast.xml
```

---

## Creating a Release

### 1. Update Version

Edit `apps/BrainChat/Info.plist`:
```xml
<key>CFBundleVersion</key>
<string>1.2.1</string>
<key>CFBundleShortVersionString</key>
<string>1.2.1</string>
```

### 2. Update Changelog

Edit `apps/BrainChat/CHANGELOG.md`:
```markdown
## [1.2.1] - 2025-01-20

### New Features
- Feature X

### Fixes
- Fix Y
```

### 3. Create Tag and Push

```bash
git add apps/BrainChat/Info.plist apps/BrainChat/CHANGELOG.md
git commit -m "Release BrainChat 1.2.1"
git tag v1.2.1
git push origin main
git push origin v1.2.1
```

### 4. Monitor Workflow

Check progress: https://github.com/getagentic/brain/actions/workflows/release.yml

The workflow will:
- Build and sign the app
- Create DMG installer
- Notarize with Apple (optional)
- Upload to GitHub Releases
- Create release notes

---

## Build Scripts

### `build.sh`

Builds BrainChat.app executable:

```bash
cd apps/BrainChat

# Build only
bash build.sh

# Build and install to /Applications
bash build.sh --install

# Build, install, and run
bash build.sh --run

# Clean previous build
bash build.sh --clean
```

### `scripts/create-dmg.sh`

Creates DMG installer with drag-to-install layout:

```bash
cd apps/BrainChat
bash scripts/create-dmg.sh
```

Output: `BrainChat-1.2.1.dmg`

### `scripts/generate-appcast.sh`

Generates Sparkle appcast from GitHub releases:

```bash
bash scripts/generate-appcast.sh getagentic brain appcast.xml
```

---

## Code Signing & Notarization

### Prerequisites

Set GitHub Secrets for code signing:

```
APPLE_IDENTITY_ID              # "Developer ID Application: Name (ID)"
APPLE_CERTIFICATE_P12_B64      # Base64-encoded .p12 certificate
APPLE_CERTIFICATE_PASSWORD     # Certificate password
APPLE_DEVELOPER_ID_APPLICATION # Developer ID email/ID
APPLE_DEVELOPER_ID_PASSWORD    # App-specific password
APPLE_TEAM_ID                  # Apple Team ID
```

### Generate Certificate

```bash
# Export certificate from Keychain
security export-cert -k ~/Library/Keychains/login.keychain \
  -p "Developer ID Application: Name (ID)" \
  -o certificate.p12 \
  -P "password"

# Encode to base64
base64 -i certificate.p12 -o cert.b64

# Add to GitHub Secrets
```

### Notarization

Apple notarization (optional but recommended):
- Removes "Developer cannot be verified" warning
- Enables automatic quarantine removal
- Improves user trust

---

## Testing

### Test Build

```bash
cd apps/BrainChat
bash build.sh
open build/Brain\ Chat.app
```

### Test DMG

```bash
cd apps/BrainChat
bash scripts/create-dmg.sh
hdiutil attach BrainChat-1.2.1.dmg

# Should show:
# /Volumes/BrainChat
#   ├── Brain Chat.app
#   └── Applications -> /Applications

hdiutil detach /Volumes/BrainChat
```

### Verify Code Signature

```bash
codesign -v build/Brain\ Chat.app
spctl -a -v build/Brain\ Chat.app
```

### Check Notarization Status

```bash
xcrun stapler validate build/Brain\ Chat.app
```

---

## File Structure

```
apps/BrainChat/
├── build.sh                    # Main build script
├── scripts/
│   ├── create-dmg.sh          # DMG creation
│   └── generate-appcast.sh    # Sparkle appcast generator
├── Formula/
│   └── brainchat.rb           # Homebrew formula
├── appcast.xml                # Sparkle auto-update feed
├── Info.plist                 # App metadata
├── BrainChat.entitlements     # Sandbox permissions
├── CHANGELOG.md               # Version history
└── DEPLOYMENT.md              # This file
```

---

## Security

### Code Signing
- Validates app integrity
- Prevents tampering
- Required for Gatekeeper approval

### Notarization
- Apple scans for malware
- Removes security warnings
- Enables automatic quarantine removal

### Appcast Security
- Served over HTTPS
- Can be signed with DSA/Ed25519 keys
- Version checking prevents downgrade attacks

---

## Resources

- [GitHub Actions Release Workflow](../../.github/workflows/release.yml)
- [GitHub Actions CD Workflow](../../.github/workflows/cd.yml)
- [Sparkle Documentation](https://sparkle-project.org/)
- [Apple Notarization Guide](https://developer.apple.com/documentation/security/notarizing_macos_software_before_distribution)
- [Homebrew Cask Docs](https://github.com/Homebrew/homebrew-cask)
- [macOS Code Signing](https://developer.apple.com/library/archive/documentation/Security/Conceptual/CodeSigningGuide/)

---

## FAQ

**Q: How do users get updates?**  
A: Sparkle checks appcast.xml on app launch. Users see a notification and can install updates automatically or manually.

**Q: Can I distribute on Mac App Store?**  
A: With notarization and additional App Store certificates, yes. See Apple's guidelines.

**Q: How do I create a beta release?**  
A: Tag with pre-release version like `v1.2.0-beta.1`. Same workflow, marked as pre-release on GitHub.

**Q: What if I want to host downloads elsewhere?**  
A: Update appcast.xml with different download URLs. Workflow will still build, sign, and notarize locally.

**Q: Can I roll back a release?**  
A: Yes, delete the tag and GitHub release, then create a new release with correct version.
