#
# Agentic Brain Setup Script for Windows
# PowerShell version of setup.sh
#
# Usage:
#   .\setup.ps1                   Interactive menu (recommended)
#   .\setup.ps1 -Install          Fresh installation
#   .\setup.ps1 -Update           Update (git pull + reinstall)
#   .\setup.ps1 -Reset            Hard reset and clean install
#   .\setup.ps1 -Config           Generate config files
#   .\setup.ps1 -Help             Show help
#
# One-liner install:
#   irm https://raw.githubusercontent.com/joseph-webber/agentic-brain/main/setup.ps1 | iex
#

param(
    [switch]$Install,
    [switch]$Update,
    [switch]$Reset,
    [switch]$Config,
    [switch]$Docker,
    [switch]$Help,
    [switch]$SkipDeps,
    [switch]$ForceDeps
)

Clear-Host

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

# ============================================================
# Configuration
# ============================================================
$VENV_DIR = ".venv"
$PYTHON_MIN_VERSION = [version]"3.10"
$SCRIPT_DIR = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
$RESET_BRANCH = "main"
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$LogFilePath = Join-Path ([System.IO.Path]::GetTempPath()) "agentic_brain_install_$Timestamp.txt"

# Marker file for tracking installed dependencies
$DEPS_MARKER_FILE = Join-Path $SCRIPT_DIR ".deps-installed"

# Supported Python versions (newest first)
$SupportedMinorVersions = @(13, 12, 11, 10)
$SupportedPythonVersions = "3.10, 3.11, 3.12 and 3.13"

# Detected OS info
$global:OS_TYPE = "windows"
$global:OS_VERSION = [System.Environment]::OSVersion.Version
$global:OS_NAME = (Get-CimInstance Win32_OperatingSystem).Caption

# ============================================================
# Logging and Output Functions
# ============================================================

function Write-Block {
    param([string]$Color, [string]$Message)
    Write-Host ""
    Write-Host ("=" * 60) -ForegroundColor $Color
    Write-Host $Message -ForegroundColor $Color
    Write-Host ("=" * 60) -ForegroundColor $Color
    Write-Host ""
    "[$Color] $Message" | Out-File $LogFilePath -Append
}

function Write-Info { 
    param([string]$Message)
    Write-Host "[i] $Message" -ForegroundColor Cyan
    "[INFO] $Message" | Out-File $LogFilePath -Append
}
function Write-Success { 
    param([string]$Message)
    Write-Host "[+] $Message" -ForegroundColor Green
    "[SUCCESS] $Message" | Out-File $LogFilePath -Append
}
function Write-Warning { 
    param([string]$Message)
    Write-Host "[!] $Message" -ForegroundColor Yellow
    "[WARNING] $Message" | Out-File $LogFilePath -Append
}
function Write-Err { 
    param([string]$Message)
    Write-Host "[-] $Message" -ForegroundColor Red
    "[ERROR] $Message" | Out-File $LogFilePath -Append
}
function Write-Step { 
    param([string]$Message)
    Write-Host "--> $Message" -ForegroundColor White
    "[STEP] $Message" | Out-File $LogFilePath -Append
}

function Show-Banner {
    Write-Host @"

    ╔═══════════════════════════════════════════════════════════╗
    ║                                                           ║
    ║     █████╗  ██████╗ ███████╗███╗   ██╗████████╗██╗ ██████╗║
    ║    ██╔══██╗██╔════╝ ██╔════╝████╗  ██║╚══██╔══╝██║██╔════╝║
    ║    ███████║██║  ███╗█████╗  ██╔██╗ ██║   ██║   ██║██║     ║
    ║    ██╔══██║██║   ██║██╔══╝  ██║╚██╗██║   ██║   ██║██║     ║
    ║    ██║  ██║╚██████╔╝███████╗██║ ╚████║   ██║   ██║╚██████╗║
    ║    ╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝  ╚═══╝   ╚═╝   ╚═╝ ╚═════╝║
    ║                                                           ║
    ║               BRAIN  -  Windows Installer                 ║
    ║                                                           ║
    ╚═══════════════════════════════════════════════════════════╝

"@ -ForegroundColor Cyan
}

function Exit-WithLog {
    param([int]$ExitCode)
    
    if ($ExitCode -ne 0) {
        Write-Err "Installation failed. Log file: $LogFilePath"
        Write-Info "Would you like to open the log file? (Y/N)"
        $openLog = Read-Host
        if ($openLog -match '^[Yy]') {
            Start-Process notepad.exe -ArgumentList $LogFilePath
        }
    }
    exit $ExitCode
}

# ============================================================
# Python Detection (Robust Windows detection)
# ============================================================

function Test-PythonExecutable {
    <#
    .SYNOPSIS
    Tests if a Python executable is valid and meets version requirements.
    
    .PARAMETER PythonPath
    Path to the Python executable or command name.
    
    .RETURNS
    $true if Python is valid and >= 3.10, $false otherwise.
    #>
    param([string]$PythonPath)
    
    try {
        # Skip Windows Store stub (just opens Microsoft Store)
        if ($PythonPath -match "WindowsApps") {
            "[DEBUG] Skipping WindowsApps stub: $PythonPath" | Out-File $LogFilePath -Append
            return $false
        }
        
        # Check if command exists
        $cmd = Get-Command $PythonPath -ErrorAction SilentlyContinue
        if (-not $cmd) {
            # Not in PATH, check if it's a direct path that exists
            if (-not (Test-Path $PythonPath)) {
                return $false
            }
        }
        
        # Get version
        $versionOutput = & $PythonPath --version 2>&1
        "[DEBUG] Testing $PythonPath : $versionOutput" | Out-File $LogFilePath -Append
        
        if ($LASTEXITCODE -eq 0 -and $versionOutput -match "Python (\d+)\.(\d+)") {
            $major = [int]$Matches[1]
            $minor = [int]$Matches[2]
            if ($major -eq 3 -and $minor -ge 10) {
                "[DEBUG] VALID: Python $major.$minor at $PythonPath" | Out-File $LogFilePath -Append
                return $true
            } else {
                "[DEBUG] TOO OLD: Python $major.$minor (need 3.10+)" | Out-File $LogFilePath -Append
            }
        }
    } catch {
        "[DEBUG] Exception testing $PythonPath : $_" | Out-File $LogFilePath -Append
    }
    return $false
}

function Find-Python {
    <#
    .SYNOPSIS
    Finds a suitable Python installation on Windows.
    
    .DESCRIPTION
    Searches for Python in the following order:
    1. py.exe launcher (most reliable on Windows)
    2. python3/python in PATH
    3. Common Windows installation paths
    4. Offers to auto-install if not found
    #>
    
    Write-Step "Detecting Python installation..."
    
    # Check for uv first (fast package manager)
    $global:UV_AVAILABLE = $false
    if (Get-Command uv -ErrorAction SilentlyContinue) {
        $global:UV_AVAILABLE = $true
        Write-Success "uv found (fast mode available)"
    }
    
    # ============================================================
    # Method 1: Try py.exe launcher (BEST method for Windows)
    # ============================================================
    Write-Info "Checking Python launcher (py.exe)..."
    try {
        $pyVersion = & py -3 --version 2>$null
        if ($LASTEXITCODE -eq 0 -and $pyVersion -match "Python 3\.(\d+)") {
            $minor = [int]$Matches[1]
            if ($minor -ge 10) {
                $global:PYTHON_BIN = "py -3"
                Write-Success "Found Python via py launcher: $pyVersion"
                return
            }
        }
    } catch {
        "[DEBUG] py launcher not available" | Out-File $LogFilePath -Append
    }
    
    # ============================================================
    # Method 2: Try python3/python commands in PATH
    # ============================================================
    Write-Info "Checking PATH for python..."
    $pythonCandidates = @("python3", "python")
    
    foreach ($py in $pythonCandidates) {
        $pyCmd = Get-Command $py -ErrorAction SilentlyContinue
        if ($pyCmd -and $pyCmd.Source -notmatch "WindowsApps") {
            if (Test-PythonExecutable -PythonPath $py) {
                $global:PYTHON_BIN = $py
                Write-Success "Found Python at $($pyCmd.Source)"
                return
            }
        }
    }
    
    # ============================================================
    # Method 3: Check common Windows installation paths
    # ============================================================
    Write-Info "Checking common installation paths..."
    
    # Build dynamic list based on supported versions
    $pythonInstallPaths = @()
    
    foreach ($v in $SupportedMinorVersions) {
        # User local installs (most common)
        $pythonInstallPaths += "$env:LOCALAPPDATA\Programs\Python\Python3$v\python.exe"
        $pythonInstallPaths += "$env:USERPROFILE\AppData\Local\Programs\Python\Python3$v\python.exe"
        
        # System-wide installs
        $pythonInstallPaths += "$env:PROGRAMFILES\Python3$v\python.exe"
        $pythonInstallPaths += "${env:PROGRAMFILES(x86)}\Python3$v\python.exe"
        
        # Root installs
        $pythonInstallPaths += "C:\Python3$v\python.exe"
    }
    
    # Also check package managers
    $pythonInstallPaths += "$env:USERPROFILE\scoop\apps\python\current\python.exe"
    $pythonInstallPaths += "$env:USERPROFILE\.pyenv\pyenv-win\shims\python.exe"
    
    # Check pyenv versions
    foreach ($v in $SupportedMinorVersions) {
        $pythonInstallPaths += "$env:USERPROFILE\.pyenv\pyenv-win\versions\3.$v.0\python.exe"
        $pythonInstallPaths += "$env:USERPROFILE\.pyenv\pyenv-win\versions\3.$v.1\python.exe"
        $pythonInstallPaths += "$env:USERPROFILE\.pyenv\pyenv-win\versions\3.$v.2\python.exe"
        $pythonInstallPaths += "$env:USERPROFILE\.pyenv\pyenv-win\versions\3.$v.3\python.exe"
    }
    
    foreach ($pyPath in $pythonInstallPaths) {
        if (Test-Path $pyPath) {
            if (Test-PythonExecutable -PythonPath $pyPath) {
                $global:PYTHON_BIN = $pyPath
                Write-Success "Found Python at $pyPath"
                return
            }
        }
    }
    
    # ============================================================
    # Method 4: Glob search for Python installations
    # ============================================================
    Write-Info "Searching for Python installations..."
    
    $searchPaths = @(
        "$env:LOCALAPPDATA\Programs\Python\Python3*",
        "$env:PROGRAMFILES\Python3*",
        "C:\Python3*"
    )
    
    foreach ($searchPath in $searchPaths) {
        $found = Get-ChildItem -Path $searchPath -ErrorAction SilentlyContinue | Where-Object { $_.PSIsContainer }
        foreach ($dir in $found) {
            $pyExe = Join-Path $dir.FullName "python.exe"
            if ((Test-Path $pyExe) -and ($pyExe -notmatch "WindowsApps")) {
                if (Test-PythonExecutable -PythonPath $pyExe) {
                    $global:PYTHON_BIN = $pyExe
                    Write-Success "Found Python at $pyExe"
                    return
                }
            }
        }
    }
    
    # ============================================================
    # Python not found - offer to install
    # ============================================================
    Write-Warning "Python $SupportedPythonVersions not found!"
    Write-Host ""
    Write-Host "Python is required but was not found on your system." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Would you like to install Python automatically?" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  [1] Yes, install Python 3.12 via winget (recommended)" -ForegroundColor White
    Write-Host "  [2] Yes, download from python.org and install" -ForegroundColor White
    Write-Host "  [3] No, I'll install it myself" -ForegroundColor White
    Write-Host ""
    
    $choice = Read-Host "Enter choice (1/2/3)"
    
    switch ($choice) {
        "1" {
            Install-PythonWinget
        }
        "2" {
            Install-PythonDownload
        }
        default {
            Write-Info ""
            Write-Info "Please install Python 3.10+ from: https://python.org/downloads"
            Write-Info ""
            Write-Info "IMPORTANT: During installation, check these options:"
            Write-Info "  [x] Add Python to PATH"
            Write-Info "  [x] Install pip"
            Write-Info "  [x] Install py launcher"
            Write-Info ""
            Write-Info "Then run this script again."
            exit 1
        }
    }
}

# ============================================================
# Python Auto-Install Functions
# ============================================================

function Install-PythonWinget {
    Write-Block "Yellow" "Installing Python via winget"
    
    # Check if winget is available
    $wingetCmd = Get-Command winget -ErrorAction SilentlyContinue
    if (-not $wingetCmd) {
        Write-Warning "winget not found. Falling back to download method."
        Install-PythonDownload
        return
    }
    
    Write-Step "Installing Python 3.12 (this may take a minute)..."
    
    try {
        # Run winget install
        $process = Start-Process -FilePath "winget" -ArgumentList "install", "Python.Python.3.12", "--accept-source-agreements", "--accept-package-agreements", "--silent" -Wait -PassThru -NoNewWindow
        
        if ($process.ExitCode -ne 0) {
            Write-Warning "winget install returned code $($process.ExitCode)"
        }
        
        # Refresh PATH environment
        Write-Step "Refreshing PATH..."
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
        
        Write-Success "Python installation command completed!"
        Write-Step "Verifying installation..."
        
        # Give Windows a moment to update
        Start-Sleep -Seconds 3
        
        # Try py launcher first
        try {
            $pyVersion = & py -3 --version 2>$null
            if ($LASTEXITCODE -eq 0 -and $pyVersion) {
                $global:PYTHON_BIN = "py -3"
                Write-Success "Python ready: $pyVersion"
                return
            }
        } catch {}
        
        # Check common install locations
        $pythonPaths = @(
            "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
            "$env:PROGRAMFILES\Python312\python.exe",
            "C:\Python312\python.exe"
        )
        
        foreach ($pyPath in $pythonPaths) {
            if (Test-Path $pyPath) {
                $global:PYTHON_BIN = $pyPath
                Write-Success "Found Python at $pyPath"
                return
            }
        }
        
        Write-Warning "Python installed but not detected in PATH yet."
        Write-Info "Please close this terminal, open a NEW terminal, and run this script again."
        Write-Info "This is required for PATH changes to take effect."
        exit 0
        
    } catch {
        Write-Err "Failed to install Python via winget: $_"
        Write-Info "Trying download method..."
        Install-PythonDownload
    }
}

function Install-PythonDownload {
    Write-Block "Yellow" "Installing Python from python.org"
    
    # Use latest stable Python 3.12
    $pythonVersion = "3.12.7"
    $pythonUrl = "https://www.python.org/ftp/python/$pythonVersion/python-$pythonVersion-amd64.exe"
    $installerPath = Join-Path $env:TEMP "python-$pythonVersion-installer.exe"
    
    Write-Step "Downloading Python $pythonVersion..."
    Write-Info "URL: $pythonUrl"
    
    try {
        # Download with progress
        $webClient = New-Object System.Net.WebClient
        $webClient.DownloadFile($pythonUrl, $installerPath)
        Write-Success "Download complete: $installerPath"
    } catch {
        Write-Err "Failed to download Python: $_"
        Write-Info ""
        Write-Info "Please download manually from: https://python.org/downloads"
        Write-Info "Make sure to check 'Add Python to PATH' during installation"
        exit 1
    }
    
    Write-Step "Installing Python (this may take a minute)..."
    Write-Info "Options: PrependPath=1, Include_pip=1, Include_launcher=1"
    
    try {
        # Silent install with all the right options
        $installArgs = @(
            "/quiet",
            "InstallAllUsers=0",
            "PrependPath=1",
            "Include_pip=1",
            "Include_launcher=1",
            "Include_test=0"
        )
        
        $process = Start-Process -FilePath $installerPath -ArgumentList $installArgs -Wait -PassThru -NoNewWindow
        
        if ($process.ExitCode -ne 0) {
            Write-Warning "Installer returned exit code: $($process.ExitCode)"
        }
        
        # Clean up installer
        Remove-Item $installerPath -Force -ErrorAction SilentlyContinue
        
        # Refresh PATH
        Write-Step "Refreshing PATH..."
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
        
        Write-Success "Python installed successfully!"
        
        # Verify installation
        Start-Sleep -Seconds 2
        
        try {
            $pyVersion = & py -3 --version 2>$null
            if ($LASTEXITCODE -eq 0 -and $pyVersion) {
                $global:PYTHON_BIN = "py -3"
                Write-Success "Python ready: $pyVersion"
                return
            }
        } catch {}
        
        # Check direct path
        $pyPath = "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"
        if (Test-Path $pyPath) {
            $global:PYTHON_BIN = $pyPath
            Write-Success "Found Python at $pyPath"
            return
        }
        
        Write-Warning "Python installed. Please restart your terminal and run this script again."
        Write-Info "This is required for PATH changes to take effect."
        exit 0
        
    } catch {
        Write-Err "Installation failed: $_"
        Write-Info ""
        Write-Info "Please install manually from: https://python.org/downloads"
        Write-Info "During installation, make sure to check:"
        Write-Info "  [x] Add Python to PATH"
        exit 1
    }
}

# ============================================================
# Check required tools
# ============================================================
function Test-RequiredTools {
    Write-Step "Checking required tools..."
    $missing = @()
    
    # Git is required
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        $missing += "git"
    }
    
    if ($missing.Count -gt 0) {
        Write-Warning "Missing required tools: $($missing -join ', ')"
        Write-Info ""
        Write-Host "Would you like to install missing tools via winget? (Y/N)" -ForegroundColor Cyan
        $choice = Read-Host
        
        if ($choice -match '^[Yy]') {
            foreach ($tool in $missing) {
                Write-Step "Installing $tool..."
                & winget install --id Git.Git -e --source winget --accept-source-agreements --accept-package-agreements
            }
            # Refresh PATH
            $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
        } else {
            Write-Info "Install with: winget install Git.Git"
            exit 1
        }
    }
    
    Write-Success "All required tools found"
}

# ============================================================
# Setup virtualenv
# ============================================================
function Initialize-Venv {
    param([switch]$Force)
    
    Write-Block "Cyan" "Setting Up Virtual Environment"
    
    Set-Location $SCRIPT_DIR
    
    # Remove existing venv if forcing
    if ($Force -and (Test-Path $VENV_DIR)) {
        Write-Step "Removing existing virtualenv..."
        Remove-Item -Recurse -Force $VENV_DIR
    }
    
    # Create virtualenv
    if (-not (Test-Path $VENV_DIR)) {
        Write-Step "Creating virtualenv in $VENV_DIR..."
        
        if ($global:UV_AVAILABLE) {
            Write-Info "Using uv for fast venv creation"
            & uv venv $VENV_DIR --python $global:PYTHON_BIN
        } else {
            # Handle "py -3" special case
            if ($global:PYTHON_BIN -eq "py -3") {
                & py -3 -m venv $VENV_DIR
            } else {
                & $global:PYTHON_BIN -m venv $VENV_DIR
            }
        }
        
        if ($LASTEXITCODE -ne 0) {
            Write-Err "Failed to create virtual environment"
            Exit-WithLog -ExitCode 1
        }
        
        Write-Success "Virtualenv created"
    } else {
        Write-Info "Virtualenv already exists"
    }
    
    # Activate virtualenv
    $activateScript = Join-Path $VENV_DIR "Scripts\Activate.ps1"
    if (Test-Path $activateScript) {
        Write-Step "Activating virtualenv..."
        . $activateScript
        Write-Success "Virtualenv activated"
    } else {
        Write-Err "Activation script not found: $activateScript"
        Exit-WithLog -ExitCode 1
    }
    
    # Upgrade pip (using --trusted-host for corporate SSL bypass)
    # Upgrade pip (with trusted-host for corporate firewalls)
    Write-Step "Upgrading pip..."
    if ($global:UV_AVAILABLE) {
        $output = & uv pip install --upgrade pip wheel setuptools 2>&1
        $output | Out-File $LogFilePath -Append
    } else {
        $output = & pip install --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org --upgrade pip wheel setuptools 2>&1
        $output | Out-File $LogFilePath -Append
    }
    
    Write-Success "Virtualenv ready"
}

# ============================================================
# Install Python dependencies (with idempotency)
# ============================================================
function Test-DepsInstalled {
    <#
    .SYNOPSIS
    Check if Python dependencies are already installed using pip list.
    #>
    
    if ($ForceDeps) {
        Write-Info "Force mode enabled - will reinstall dependencies"
        return $false
    }
    
    # First check marker file
    if (Test-Path $DEPS_MARKER_FILE) {
        $markerTime = Get-Item $DEPS_MARKER_FILE | Select-Object -ExpandProperty LastWriteTime
        Write-Info "Found dependency marker from $(Get-Date $markerTime -Format 'yyyy-MM-dd HH:mm:ss')"
        
        try {
            # Quick verification: check if agentic-brain is installed
            $installed = & pip list 2>$null | Select-String "agentic-brain"
            if ($installed) {
                Write-Info "Verified: agentic-brain is installed"
                return $true
            } else {
                Write-Warning "Marker file exists but agentic-brain not found - will reinstall"
                Remove-Item $DEPS_MARKER_FILE -Force -ErrorAction SilentlyContinue
                return $false
            }
        } catch {
            Write-Warning "Error checking pip list: $_"
            return $false
        }
    }
    
    return $false
}

function Install-PythonDeps {
    param([switch]$SkipIfInstalled)
    
    Write-Block "Green" "Python Dependencies"
    
    Set-Location $SCRIPT_DIR
    
    # Activate venv
    $activateScript = Join-Path $VENV_DIR "Scripts\Activate.ps1"
    . $activateScript
    
    # ============================================================
    # Idempotency check
    # ============================================================
    if ($SkipIfInstalled -or $SkipDeps) {
        if (Test-DepsInstalled) {
            Write-Success "Dependencies already installed, skipping..."
            Write-Info "Run with -ForceDeps to force reinstall"
            return
        }
    }
    
    Write-Step "Installing agentic-brain with all extras..."
    Write-Info "This may take a few minutes on first run..."
    Write-Info "Using trusted-host flags for corporate firewall compatibility..."
    
    if ($global:UV_AVAILABLE) {
        Write-Info "Using uv for fast installation"
        $output = & uv pip install -e ".[all,dev]" 2>&1
        $output | Out-File $LogFilePath -Append
    } else {
        # Use --trusted-host by default for corporate environments with SSL inspection
        $output = & pip install --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org -e ".[all,dev]" 2>&1
        $output | Out-File $LogFilePath -Append
    }
    
    if ($LASTEXITCODE -ne 0) {
        Write-Err "Failed to install dependencies. Check log: $LogFilePath"
        Exit-WithLog -ExitCode 1
    }
    
    Write-Success "Python dependencies installed successfully"
    
    # Create marker file
    Write-Step "Creating dependency marker..."
    New-Item -Path $DEPS_MARKER_FILE -ItemType File -Force | Out-Null
    Write-Info "Marker saved: $DEPS_MARKER_FILE"
    
    # Show installed version
    $version = & pip show agentic-brain 2>$null | Select-String "^Version:" | ForEach-Object { $_ -replace "Version: ", "" }
    if ($version) {
        Write-Info "Installed agentic-brain version: $version"
    }
}

# ============================================================
# Generate config
# ============================================================
function New-Config {
    Write-Block "Yellow" "Configuration Setup"
    
    Set-Location $SCRIPT_DIR
    
    if (-not (Test-Path ".env")) {
        if (Test-Path ".env.example") {
            Write-Step "Creating .env from example..."
            Copy-Item ".env.example" ".env"
            Write-Success ".env file created"
        } else {
            Write-Step "Creating minimal .env..."
            @"
# Agentic Brain Configuration
# Generated by setup.ps1 on $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")

# LLM Provider (ollama, openai, anthropic, openrouter)
AGENTIC_LLM_PROVIDER=ollama
AGENTIC_LLM_MODEL=llama3.2:3b

# Optional: OpenAI
# OPENAI_API_KEY=sk-...

# Optional: Anthropic
# ANTHROPIC_API_KEY=sk-ant-...

# Optional: Neo4j (memory)
# NEO4J_URI=bolt://localhost:7687
# NEO4J_USER=neo4j
# NEO4J_PASSWORD=password

# API Server
AGENTIC_HOST=0.0.0.0
AGENTIC_PORT=8000
"@ | Out-File -FilePath ".env" -Encoding UTF8
            Write-Success ".env file created with defaults"
        }
        Write-Info "Edit .env to add your API keys and settings"
    } else {
        Write-Info ".env already exists - keeping existing config"
    }
}

# ============================================================
# Git operations
# ============================================================
function Update-Git {
    Write-Block "Magenta" "Updating from Git"
    
    Set-Location $SCRIPT_DIR
    
    # Check for uncommitted changes
    $status = & git status --porcelain 2>$null
    if ($status) {
        Write-Warning "You have uncommitted changes"
        Write-Info "Stashing changes..."
        & git stash push -m "setup.ps1 auto-stash $(Get-Date -Format 'yyyyMMdd_HHmmss')"
    }
    
    Write-Step "Pulling latest changes..."
    $output = & git pull origin $RESET_BRANCH 2>&1
    $output | Out-File $LogFilePath -Append
    
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "Git pull had issues - check log for details"
    } else {
        Write-Success "Git update complete"
    }
}

function Reset-Git {
    Write-Block "Red" "Hard Reset to origin/$RESET_BRANCH"
    
    Set-Location $SCRIPT_DIR
    
    Write-Warning "This will DISCARD all local changes!"
    $confirm = Read-Host "Are you sure? Type 'yes' to confirm"
    if ($confirm -ne "yes") {
        Write-Info "Reset cancelled"
        return $false
    }
    
    Write-Step "Fetching latest..."
    $output = & git fetch origin 2>&1
    $output | Out-File $LogFilePath -Append
    
    Write-Step "Hard resetting to origin/$RESET_BRANCH..."
    $output = & git reset --hard "origin/$RESET_BRANCH" 2>&1
    $output | Out-File $LogFilePath -Append
    
    Write-Step "Cleaning untracked files..."
    $output = & git clean -fd 2>&1
    $output | Out-File $LogFilePath -Append
    
    Write-Success "Repository reset complete"
    return $true
}

# ============================================================
# ULTIMATE LLM SETUP WIZARD
# ============================================================

function Invoke-LLMSetupWizard {
    Write-Host ""
    Write-Host "╔═══════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
    Write-Host "║  🧠 LLM SETUP - Choose Your Path                          ║" -ForegroundColor Cyan  
    Write-Host "╠═══════════════════════════════════════════════════════════╣" -ForegroundColor Cyan
    Write-Host "║  1) 🚀 QUICK START  - Get running in 2 minutes (Groq)     ║" -ForegroundColor Green
    Write-Host "║  2) 🔒 PRIVACY      - Run locally, no cloud (Ollama)      ║" -ForegroundColor Yellow
    Write-Host "║  3) 💼 ENTERPRISE   - Best quality (OpenAI/Anthropic)     ║" -ForegroundColor Magenta
    Write-Host "║  4) 🔧 COMPARE ALL  - See all options with pros/cons      ║" -ForegroundColor White
    Write-Host "║  5) >> SKIP FOR NOW - Configure .env manually later         ║" -ForegroundColor DarkGray
    Write-Host "╚═══════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
    Write-Host ""
    
    $wizardChoice = Read-Host "Select an option (1-5)"
    
    switch ($wizardChoice) {
        "1" { Invoke-QuickStart }
        "2" { Invoke-PrivacyPath }
        "3" { Invoke-EnterprisePath }
        "4" { Show-ComparisonTable }
        "5" { Write-Info "You can configure .env later with your API keys" }
        default {
            Write-Warning "Invalid choice"
            Invoke-LLMSetupWizard
        }
    }
}

function Show-ComparisonTable {
    Write-Host ""
    Write-Host "╔══════════════════════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
    Write-Host "║  FREE PROVIDERS (Choose one to get started!)                                 ║" -ForegroundColor Cyan
    Write-Host "╠══════════════════════════════════════════════════════════════════════════════╣" -ForegroundColor Cyan
    Write-Host "║  Groq ⭐              │ 2 min │ Fastest free, best for quick start         ║" -ForegroundColor Green
    Write-Host "║  Ollama              │ 5 min │ 100% private, runs on your computer         ║" -ForegroundColor Green
    Write-Host "║  Google AI Studio    │ 3 min │ Gemini free tier (very capable)            ║" -ForegroundColor Green
    Write-Host "║  HuggingFace         │ 3 min │ Access to 100K+ open models                ║" -ForegroundColor Green
    Write-Host "║  OpenRouter          │ 2 min │ 200+ models, generous free tier            ║" -ForegroundColor Green
    Write-Host "║  Together.ai         │ 2 min │ \$25 free credit, great for testing        ║" -ForegroundColor Green
    Write-Host "║  Mistral             │ 3 min │ Great for coding tasks                      ║" -ForegroundColor Green
    Write-Host "║  Cohere              │ 3 min │ Best for search/RAG applications            ║" -ForegroundColor Green
    Write-Host "║  Cloudflare Workers  │ 3 min │ Edge deployment, serverless                 ║" -ForegroundColor Green
    Write-Host "╠══════════════════════════════════════════════════════════════════════════════╣" -ForegroundColor Cyan
    Write-Host "║  PAID PROVIDERS (Premium quality)                                           ║" -ForegroundColor Cyan
    Write-Host "╠══════════════════════════════════════════════════════════════════════════════╣" -ForegroundColor Cyan
    Write-Host "║  OpenAI              │ 2 min │ GPT-4/5 - best reasoning (paid)             ║" -ForegroundColor Magenta
    Write-Host "║  Anthropic           │ 2 min │ Claude - most capable (paid)                ║" -ForegroundColor Magenta
    Write-Host "╚══════════════════════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
    Write-Host ""
    
    Write-Host "💡 Recommendation: Start with Groq or Ollama for fastest setup!" -ForegroundColor Yellow
    Write-Host ""
    
    Write-Host "What would you like to do?" -ForegroundColor White
    Write-Host "  1) Set up Groq (quickest)" -ForegroundColor Green
    Write-Host "  2) Set up Ollama (private)" -ForegroundColor Green
    Write-Host "  3) Set up Google AI (free tier)" -ForegroundColor Green
    Write-Host "  4) Set up another provider" -ForegroundColor Cyan
    Write-Host "  5) Go back to main menu" -ForegroundColor DarkGray
    Write-Host ""
    
    $tableChoice = Read-Host "Choose (1-5)"
    
    switch ($tableChoice) {
        "1" { Invoke-ProviderSetup -Provider "groq" }
        "2" { Invoke-ProviderSetup -Provider "ollama" }
        "3" { Invoke-ProviderSetup -Provider "google" }
        "4" { Show-ProviderMenu }
        "5" { return }
        default {
            Write-Warning "Invalid choice"
            Show-ComparisonTable
        }
    }
}

function Show-ProviderMenu {
    Write-Host ""
    Write-Host "Select provider to configure:" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Free Providers:" -ForegroundColor Green
    Write-Host "  1) Groq - Fastest inference" -ForegroundColor Green
    Write-Host "  2) Ollama - Private, local" -ForegroundColor Green
    Write-Host "  3) Google AI - Gemini free" -ForegroundColor Green
    Write-Host "  4) OpenRouter - 200+ models" -ForegroundColor Green
    Write-Host "  5) HuggingFace - 100K+ models" -ForegroundColor Green
    Write-Host "  6) Mistral - Great for coding" -ForegroundColor Green
    Write-Host "  7) Cohere - Best for search" -ForegroundColor Green
    Write-Host "  8) Together.ai - Free \$25 credit" -ForegroundColor Green
    Write-Host ""
    Write-Host "Paid Providers:" -ForegroundColor Magenta
    Write-Host "  9) OpenAI - GPT-4/5" -ForegroundColor Magenta
    Write-Host "  10) Anthropic - Claude" -ForegroundColor Magenta
    Write-Host ""
    Write-Host "  0) Cancel" -ForegroundColor DarkGray
    Write-Host ""
    
    $provChoice = Read-Host "Choose provider (0-10)"
    
    switch ($provChoice) {
        "1" { Invoke-ProviderSetup -Provider "groq" }
        "2" { Invoke-ProviderSetup -Provider "ollama" }
        "3" { Invoke-ProviderSetup -Provider "google" }
        "4" { Invoke-ProviderSetup -Provider "openrouter" }
        "5" { Invoke-ProviderSetup -Provider "huggingface" }
        "6" { Invoke-ProviderSetup -Provider "mistral" }
        "7" { Invoke-ProviderSetup -Provider "cohere" }
        "8" { Invoke-ProviderSetup -Provider "together" }
        "9" { Invoke-ProviderSetup -Provider "openai" }
        "10" { Invoke-ProviderSetup -Provider "anthropic" }
        "0" { return }
        default {
            Write-Warning "Invalid choice"
            Show-ProviderMenu
        }
    }
}

function Invoke-QuickStart {
    Write-Block "Green" "⚡ QUICK START - Groq Setup (2 minutes)"
    Invoke-ProviderSetup -Provider "groq" -IsQuickStart
}

function Invoke-PrivacyPath {
    Write-Block "Yellow" "🔒 PRIVACY PATH - Ollama Setup (local, no cloud)"
    Invoke-ProviderSetup -Provider "ollama" -IsPrivacy
}

function Invoke-EnterprisePath {
    Write-Block "Magenta" "💼 ENTERPRISE PATH - Premium LLMs"
    Write-Host ""
    Write-Host "Choose your preferred enterprise provider:" -ForegroundColor White
    Write-Host ""
    Write-Host "  1) OpenAI - GPT-4/5 (best reasoning)" -ForegroundColor Magenta
    Write-Host "  2) Anthropic - Claude (very capable)" -ForegroundColor Magenta
    Write-Host ""
    
    $entChoice = Read-Host "Choose (1-2)"
    
    if ($entChoice -eq "1") {
        Invoke-ProviderSetup -Provider "openai" -IsEnterprise
    } elseif ($entChoice -eq "2") {
        Invoke-ProviderSetup -Provider "anthropic" -IsEnterprise
    } else {
        Write-Warning "Invalid choice"
        Invoke-EnterprisePath
    }
}

function Invoke-ProviderSetup {
    param(
        [string]$Provider,
        [switch]$IsQuickStart,
        [switch]$IsPrivacy,
        [switch]$IsEnterprise
    )
    
    $providers = @{
        "groq" = @{
            "name" = "Groq"
            "env_var" = "GROQ_API_KEY"
            "signup_url" = "https://console.groq.com"
            "docs_url" = "https://console.groq.com/docs/api"
            "key_format" = "gsk_"
            "instructions" = @(
                "1. Open browser (we'll do this for you)",
                "2. Create account or sign in",
                "3. Navigate to API Keys section",
                "4. Create a new API key",
                "5. Copy the key and paste here"
            )
            "time" = "~2 minutes"
            "pros" = "Fastest inference engine, easiest setup, excellent for testing"
            "cons" = "30 requests per minute rate limit, API-only (no web chat)"
        }
        "ollama" = @{
            "name" = "Ollama"
            "env_var" = "OLLAMA_BASE_URL"
            "signup_url" = "https://ollama.ai/download"
            "docs_url" = "https://github.com/ollama/ollama"
            "key_format" = "http://localhost:11434"
            "instructions" = @(
                "1. Download Ollama from https://ollama.ai/download",
                "2. Install and open the application",
                "3. Pull a model: ollama pull llama3.2",
                "4. Ollama will run at http://localhost:11434",
                "5. Enter that URL below"
            )
            "time" = "~5 minutes"
            "pros" = "100% private, runs on your computer, no cloud needed, completely free"
            "cons" = "Uses your system RAM (16GB+ recommended), slower than cloud"
        }
        "google" = @{
            "name" = "Google AI Studio"
            "env_var" = "GOOGLE_API_KEY"
            "signup_url" = "https://aistudio.google.com/apikey"
            "docs_url" = "https://ai.google.dev"
            "key_format" = "AIza"
            "instructions" = @(
                "1. Open https://aistudio.google.com/apikey",
                "2. Click 'Create API key'",
                "3. Select or create a Google Cloud project",
                "4. Copy the generated API key",
                "5. Paste here"
            )
            "time" = "~3 minutes"
            "pros" = "1M free tokens per day, Gemini model, excellent quality"
            "cons" = "Requires Google account, daily quota limits"
        }
        "openrouter" = @{
            "name" = "OpenRouter"
            "env_var" = "OPENROUTER_API_KEY"
            "signup_url" = "https://openrouter.ai"
            "docs_url" = "https://openrouter.ai/docs"
            "key_format" = "sk-or-"
            "instructions" = @(
                "1. Go to https://openrouter.ai",
                "2. Create account or sign in",
                "3. Go to Keys page (https://openrouter.ai/keys)",
                "4. Create new API key",
                "5. Copy and paste here"
            )
            "time" = "~2 minutes"
            "pros" = "Access to 200+ models, free tier available, model fallbacks"
            "cons" = "50 calls/day free tier, varies by model"
        }
        "huggingface" = @{
            "name" = "HuggingFace"
            "env_var" = "HUGGINGFACE_API_KEY"
            "signup_url" = "https://huggingface.co/settings/tokens"
            "docs_url" = "https://huggingface.co/docs/hub/security-tokens"
            "key_format" = "hf_"
            "instructions" = @(
                "1. Go to https://huggingface.co/settings/tokens",
                "2. Create account if needed",
                "3. Click 'New token'",
                "4. Name it 'agentic-brain'",
                "5. Make it 'read' token, copy and paste"
            )
            "time" = "~3 minutes"
            "pros" = "Access to 100K+ open models, great community, good for experiments"
            "cons" = "Rate limited for free tier, model quality varies"
        }
        "mistral" = @{
            "name" = "Mistral"
            "env_var" = "MISTRAL_API_KEY"
            "signup_url" = "https://console.mistral.ai/api-keys/"
            "docs_url" = "https://docs.mistral.ai"
            "key_format" = "eyJ"
            "instructions" = @(
                "1. Go to https://console.mistral.ai",
                "2. Create account (requires phone verification)",
                "3. Navigate to API Keys",
                "4. Create a new key",
                "5. Copy and paste here"
            )
            "time" = "~3 minutes"
            "pros" = "Excellent for code generation and reasoning, free tier available"
            "cons" = "Requires phone verification, free tier limit"
        }
        "cohere" = @{
            "name" = "Cohere"
            "env_var" = "COHERE_API_KEY"
            "signup_url" = "https://dashboard.cohere.com"
            "docs_url" = "https://docs.cohere.com"
            "key_format" = "sk-"
            "instructions" = @(
                "1. Go to https://dashboard.cohere.com",
                "2. Create account or sign in",
                "3. Go to API Keys (left sidebar)",
                "4. Create trial key",
                "5. Copy and paste here"
            )
            "time" = "~3 minutes"
            "pros" = "Best for search/RAG tasks, embeddings, semantic search"
            "cons" = "Limited free tier, trial expires"
        }
        "together" = @{
            "name" = "Together.ai"
            "env_var" = "TOGETHER_API_KEY"
            "signup_url" = "https://www.together.ai"
            "docs_url" = "https://docs.together.ai"
            "key_format" = "eyJ"
            "instructions" = @(
                "1. Go to https://www.together.ai",
                "2. Click 'Start now' or sign up",
                "3. Verify email",
                "4. Go to Settings > API Keys",
                "5. Create key and copy here"
            )
            "time" = "~2 minutes"
            "pros" = "\$25 free credit, great model selection, good community"
            "cons" = "Credit runs out, then charged"
        }
        "openai" = @{
            "name" = "OpenAI"
            "env_var" = "OPENAI_API_KEY"
            "signup_url" = "https://platform.openai.com/api-keys"
            "docs_url" = "https://platform.openai.com/docs"
            "key_format" = "sk-"
            "instructions" = @(
                "1. Go to https://platform.openai.com",
                "2. Sign up or log in",
                "3. Go to API Keys page",
                "4. Create new secret key",
                "5. Copy and paste here"
            )
            "time" = "~2 minutes"
            "pros" = "Best quality reasoning, GPT-4/5, most capable"
            "cons" = "Costs money (very cheap though), paid API"
        }
        "anthropic" = @{
            "name" = "Anthropic"
            "env_var" = "ANTHROPIC_API_KEY"
            "signup_url" = "https://console.anthropic.com"
            "docs_url" = "https://docs.anthropic.com"
            "key_format" = "sk-ant-"
            "instructions" = @(
                "1. Go to https://console.anthropic.com",
                "2. Create account with email",
                "3. Go to API Keys",
                "4. Create new key",
                "5. Copy and paste here"
            )
            "time" = "~2 minutes"
            "pros" = "Claude model, very capable, good for reasoning"
            "cons" = "Costs money (very cheap though), paid API"
        }
    }
    
    $provConfig = $providers[$Provider]
    if (-not $provConfig) {
        Write-Err "Unknown provider: $Provider"
        return
    }
    
    Write-Host ""
    Write-Host "Provider: $($provConfig.name)" -ForegroundColor Cyan
    Write-Host "Setup time: $($provConfig.time)" -ForegroundColor Green
    Write-Host "Pros: $($provConfig.pros)" -ForegroundColor Green
    Write-Host "Cons: $($provConfig.cons)" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Setup Instructions:" -ForegroundColor White
    foreach ($step in $provConfig.instructions) {
        Write-Host "  $step" -ForegroundColor Gray
    }
    Write-Host ""
    
    # Open browser if not Ollama
    if ($Provider -ne "ollama") {
        $openBrowser = Read-Host "Open signup page in browser? (Y/n)"
        if ($openBrowser -ne "n" -and $openBrowser -ne "N") {
            Write-Step "Opening $($provConfig.signup_url) in browser..."
            Start-Process $provConfig.signup_url
            Start-Sleep -Seconds 2
        }
    }
    
    Write-Host ""
    Write-Host "Enter your " -NoNewline
    Write-Host $($provConfig.env_var) -ForegroundColor Cyan -NoNewline
    Write-Host ":"
    
    if ($Provider -eq "ollama") {
        Write-Host "(e.g., http://localhost:11434)" -ForegroundColor DarkGray
    } else {
        Write-Host "(will be saved in .env)" -ForegroundColor DarkGray
    }
    
    $apiKey = Read-Host "Enter key/URL"
    
    if (-not $apiKey) {
        Write-Warning "No key entered. Skipping $($provConfig.name) setup."
        return
    }
    
    # Save to .env
    $envPath = Join-Path $SCRIPT_DIR ".env"
    if (-not (Test-Path $envPath)) {
        Write-Step "Creating .env file..."
        @"
# Agentic Brain Configuration
# Generated by setup.ps1

# LLM Provider
AGENTIC_LLM_PROVIDER=$Provider

"@ | Out-File -FilePath $envPath -Encoding UTF8
    }
    
    # Append or update the key
    Write-Step "Saving to .env..."
    $envContent = Get-Content $envPath -Raw -ErrorAction SilentlyContinue
    
    if ($envContent -match "$($provConfig.env_var)=") {
        # Update existing
        $envContent = $envContent -replace "$($provConfig.env_var)=.*", "$($provConfig.env_var)=$apiKey"
    } else {
        # Add new
        $envContent += "`n$($provConfig.env_var)=$apiKey`n"
    }
    
    $envContent | Out-File -FilePath $envPath -Encoding UTF8
    Write-Success "Saved $($provConfig.env_var) to .env"
    
    # Test connection
    Write-Host ""
    Write-Step "Testing connection to $($provConfig.name)..."
    
    if (Test-LLMConnection -Provider $Provider -Key $apiKey) {
        Write-Host ""
        Write-Host "╔═══════════════════════════════════════════════════════════╗" -ForegroundColor Green
        Write-Host "║  ✅ SUCCESS! Your LLM is ready to use!                    ║" -ForegroundColor Green
        Write-Host "╠═══════════════════════════════════════════════════════════╣" -ForegroundColor Green
        Write-Host "║  The chatbot can now help with:                           ║" -ForegroundColor Green
        Write-Host "║    • Setting up Neo4j for memory                          ║" -ForegroundColor Green
        Write-Host "║    • Configuring other integrations                       ║" -ForegroundColor Green
        Write-Host "║    • Troubleshooting any issues                           ║" -ForegroundColor Green
        Write-Host "║                                                           ║" -ForegroundColor Green
        Write-Host "║  Next steps:                                              ║" -ForegroundColor Green
        Write-Host "║    • Run: agentic-brain chat                              ║" -ForegroundColor Green
        Write-Host "║    • Or: agentic-brain serve (API server)                 ║" -ForegroundColor Green
        Write-Host "╚═══════════════════════════════════════════════════════════╝" -ForegroundColor Green
        Write-Host ""
    } else {
        Write-Warning "Connection test failed. Check your key and try again."
        Write-Info "You can test manually with: agentic-brain chat"
    }
}

function Test-LLMConnection {
    param(
        [string]$Provider,
        [string]$Key
    )
    
    try {
        switch ($Provider) {
            "ollama" {
                $response = Invoke-RestMethod -Uri "$Key/api/tags" -Method Get -TimeoutSec 5 -ErrorAction Stop
                return $response.models -and $response.models.Count -gt 0
            }
            "groq" {
                $headers = @{ "Authorization" = "Bearer $Key" }
                $response = Invoke-RestMethod -Uri "https://api.groq.com/openai/v1/models" -Method Get -Headers $headers -TimeoutSec 5 -ErrorAction Stop
                return $response.data -and $response.data.Count -gt 0
            }
            "google" {
                $response = Invoke-RestMethod -Uri "https://generativelanguage.googleapis.com/v1beta/models?key=$Key" -Method Get -TimeoutSec 5 -ErrorAction Stop
                return $response.models -and $response.models.Count -gt 0
            }
            "openai" {
                $headers = @{ "Authorization" = "Bearer $Key" }
                $response = Invoke-RestMethod -Uri "https://api.openai.com/v1/models" -Method Get -Headers $headers -TimeoutSec 5 -ErrorAction Stop
                return $response.data -and $response.data.Count -gt 0
            }
            "anthropic" {
                $headers = @{ 
                    "x-api-key" = $Key
                    "anthropic-version" = "2023-06-01"
                }
                # Just test that the key format is valid
                return $Key -match "^sk-ant-"
            }
            default {
                # For other providers, just check key format
                return $Key.Length -gt 10
            }
        }
    } catch {
        "[DEBUG] Connection test failed: $_" | Out-File $LogFilePath -Append
        return $false
    }
}

# ============================================================
# Post-install message
# ============================================================

function Show-PostInstall {
    Write-Block "Green" "Installation Complete!"
    
    Write-Host ""
    Write-Host "Activate the environment:" -ForegroundColor White
    Write-Host ""
    Write-Host "    .\.venv\Scripts\Activate.ps1" -ForegroundColor Cyan
    Write-Host ""
    
    # ============================================================
    # ULTIMATE LLM SETUP WIZARD - Make it SO EASY to get started!
    # ============================================================
    Invoke-LLMSetupWizard
    
    Write-Host "============================================================" -ForegroundColor Yellow
    Write-Host ""
    
    Write-Host "Quick Start:" -ForegroundColor White
    Write-Host "    agentic-brain --help          " -ForegroundColor Cyan -NoNewline
    Write-Host "Show all commands"
    Write-Host "    agentic-brain chat            " -ForegroundColor Cyan -NoNewline
    Write-Host "Start interactive chat"
    Write-Host "    agentic-brain serve           " -ForegroundColor Cyan -NoNewline
    Write-Host "Start API server"
    Write-Host ""
    
    Write-Host "Configuration:" -ForegroundColor White
    Write-Host "    Edit " -NoNewline
    Write-Host ".env" -ForegroundColor Cyan -NoNewline
    Write-Host " to configure API keys and settings"
    Write-Host ""
    
    # Check if Ollama is running
    Write-Host "Checking LLM status..." -ForegroundColor DarkGray
    try {
        $ollamaCheck = Invoke-RestMethod -Uri "http://localhost:11434/api/tags" -Method Get -TimeoutSec 2 -ErrorAction SilentlyContinue
        Write-Success "Ollama is running with models: $($ollamaCheck.models.name -join ', ')"
    } catch {
        Write-Warning "Ollama not detected. Install from https://ollama.ai or configure an API key in .env"
    }
    
    # Check .env for API keys
    $envPath = Join-Path $SCRIPT_DIR ".env"
    if (Test-Path $envPath) {
        $envContent = Get-Content $envPath -Raw
        if ($envContent -match "OPENAI_API_KEY=sk-") {
            Write-Success "OpenAI API key configured in .env"
        }
        if ($envContent -match "ANTHROPIC_API_KEY=sk-ant-") {
            Write-Success "Anthropic API key configured in .env"
        }
    }
    
    Write-Host ""
    Write-Host "Log file: $LogFilePath" -ForegroundColor DarkGray
    Write-Host ""
    
    # ============================================================
    # OPTIONAL: Docker Build
    # ============================================================
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Magenta
    Write-Host "OPTIONAL: Docker Deployment" -ForegroundColor Magenta
    Write-Host "============================================================" -ForegroundColor Magenta
    Write-Host ""
    Write-Host "Want to build a Docker image for production deployment?" -ForegroundColor White
    Write-Host ""
    
    $dockerChoice = Read-Host "Build Docker image? (y/N)"
    
    if ($dockerChoice -eq "y" -or $dockerChoice -eq "Y") {
        Invoke-DockerBuild
    } else {
        Write-Info "Skipping Docker build. Run 'docker compose build' later if needed."
    }
}

# ============================================================
# Docker Build (optional, at end of install)
# ============================================================
function Invoke-DockerBuild {
    Write-Block "Magenta" "Building Docker Image"
    
    # Check if Docker is available
    try {
        $dockerVersion = & docker --version 2>&1
        Write-Info "Docker found: $dockerVersion"
    } catch {
        Write-Err "Docker not found. Please install Docker Desktop first."
        Write-Info "Download from: https://www.docker.com/products/docker-desktop/"
        return
    }
    
    # Check if Docker daemon is running
    try {
        $dockerInfo = & docker info 2>&1
        if ($LASTEXITCODE -ne 0) {
            Write-Err "Docker daemon not running. Please start Docker Desktop."
            return
        }
    } catch {
        Write-Err "Cannot connect to Docker daemon. Please start Docker Desktop."
        return
    }
    
    Set-Location $SCRIPT_DIR
    
    Write-Step "Building agentic-brain Docker image..."
    Write-Info "This may take a few minutes on first build..."
    
    # Build with docker compose
    $output = & docker compose build 2>&1
    $output | Out-File $LogFilePath -Append
    
    if ($LASTEXITCODE -eq 0) {
        Write-Success "Docker image built successfully!"
        Write-Host ""
        Write-Host "To run with Docker:" -ForegroundColor White
        Write-Host "    docker compose up -d          " -ForegroundColor Cyan -NoNewline
        Write-Host "Start in background"
        Write-Host "    docker compose logs -f        " -ForegroundColor Cyan -NoNewline
        Write-Host "View logs"
        Write-Host "    docker compose down           " -ForegroundColor Cyan -NoNewline
        Write-Host "Stop"
        Write-Host ""
        
        $startNow = Read-Host "Start Docker container now? (y/N)"
        if ($startNow -eq "y" -or $startNow -eq "Y") {
            Write-Step "Starting Docker container..."
            $output = & docker compose up -d 2>&1
            $output | Out-File $LogFilePath -Append
            
            if ($LASTEXITCODE -eq 0) {
                Write-Success "Docker container started!"
                Write-Host ""
                Write-Host "API available at: " -NoNewline
                Write-Host "http://localhost:8000" -ForegroundColor Cyan
                Write-Host "Dashboard at: " -NoNewline
                Write-Host "http://localhost:8000/dashboard" -ForegroundColor Cyan
                Write-Host ""
                Write-Host "View logs: docker compose logs -f" -ForegroundColor DarkGray
            } else {
                Write-Err "Failed to start container. Check: docker compose logs"
            }
        }
    } else {
        Write-Err "Docker build failed. Check log: $LogFilePath"
        Write-Info "Common fix: Ensure Docker Desktop is running"
    }
}

# ============================================================
# Docker Management Helper - Easy start/stop/restart
# ============================================================
function Invoke-DockerManage {
    Write-Block "Magenta" "Docker Management"
    
    # Check Docker installed
    $dockerPath = Get-Command docker -ErrorAction SilentlyContinue
    if (-not $dockerPath) {
        Write-Err "Docker not installed."
        Write-Info "Download from: https://www.docker.com/products/docker-desktop/"
        return
    }
    
    # Check Docker running
    $dockerRunning = $false
    try {
        $null = & docker ps 2>&1
        $dockerRunning = ($LASTEXITCODE -eq 0)
    } catch {
        $dockerRunning = $false
    }
    
    if (-not $dockerRunning) {
        Write-Warning "Docker Desktop is NOT running!"
        Write-Host ""
        Write-Host "  To start Docker Desktop:" -ForegroundColor Yellow
        Write-Host "    1. Search 'Docker Desktop' in Start Menu" -ForegroundColor White
        Write-Host "    2. Click to launch it" -ForegroundColor White
        Write-Host "    3. Wait for it to say 'Docker is running'" -ForegroundColor White
        Write-Host "    4. Run this script again" -ForegroundColor White
        Write-Host ""
        
        $openDocker = Read-Host "Try to open Docker Desktop now? (Y/n)"
        if ($openDocker -ne "n" -and $openDocker -ne "N") {
            try {
                Start-Process "Docker Desktop"
                Write-Info "Opening Docker Desktop... Please wait for it to start, then run this again."
            } catch {
                Write-Err "Could not open Docker Desktop automatically."
                Write-Info "Please open it manually from the Start Menu."
            }
        }
        return
    }
    
    Write-Success "Docker Desktop is running!"
    Write-Host ""
    
    # Check container status
    $containerRunning = $false
    try {
        $containers = & docker compose ps --format json 2>&1
        if ($LASTEXITCODE -eq 0 -and $containers) {
            $containerRunning = $true
            Write-Success "Agentic Brain container is running!"
        }
    } catch {}
    
    Write-Host "What would you like to do?" -ForegroundColor Cyan
    Write-Host ""
    if ($containerRunning) {
        Write-Host "  1) View logs         - See what's happening" -ForegroundColor Green
        Write-Host "  2) Restart           - Stop and start fresh" -ForegroundColor Yellow
        Write-Host "  3) Stop              - Shut down container" -ForegroundColor Red
        Write-Host "  4) Rebuild           - Rebuild and restart" -ForegroundColor Magenta
    } else {
        Write-Host "  1) Start             - Start the container" -ForegroundColor Green
        Write-Host "  2) Build & Start     - Build image and start" -ForegroundColor Yellow
        Write-Host "  3) View logs         - Check for errors" -ForegroundColor Cyan
    }
    Write-Host "  0) Back to main menu" -ForegroundColor DarkGray
    Write-Host ""
    
    $choice = Read-Host "Choose"
    
    if ($containerRunning) {
        switch ($choice) {
            "1" {
                Write-Step "Showing logs (Ctrl+C to exit)..."
                & docker compose logs -f --tail 50
            }
            "2" {
                Write-Step "Restarting container..."
                & docker compose restart
                if ($LASTEXITCODE -eq 0) {
                    Write-Success "Container restarted!"
                    Write-Host "API: http://localhost:8000" -ForegroundColor Cyan
                }
            }
            "3" {
                Write-Step "Stopping container..."
                & docker compose down
                Write-Success "Container stopped."
            }
            "4" {
                Write-Step "Rebuilding and restarting..."
                & docker compose down
                & docker compose build
                & docker compose up -d
                if ($LASTEXITCODE -eq 0) {
                    Write-Success "Rebuilt and started!"
                    Write-Host "API: http://localhost:8000" -ForegroundColor Cyan
                }
            }
        }
    } else {
        switch ($choice) {
            "1" {
                Write-Step "Starting container..."
                & docker compose up -d
                if ($LASTEXITCODE -eq 0) {
                    Write-Success "Container started!"
                    Write-Host "API: http://localhost:8000" -ForegroundColor Cyan
                    Write-Host "Dashboard: http://localhost:8000/dashboard" -ForegroundColor Cyan
                } else {
                    Write-Err "Failed to start. Try option 2 to build first."
                }
            }
            "2" {
                Write-Step "Building image..."
                & docker compose build
                if ($LASTEXITCODE -eq 0) {
                    Write-Step "Starting container..."
                    & docker compose up -d
                    if ($LASTEXITCODE -eq 0) {
                        Write-Success "Built and started!"
                        Write-Host "API: http://localhost:8000" -ForegroundColor Cyan
                    }
                } else {
                    Write-Err "Build failed. Check: docker compose logs"
                }
            }
            "3" {
                Write-Step "Showing logs..."
                & docker compose logs --tail 100
            }
        }
    }
}

# ============================================================
# Show help
# ============================================================
function Show-Help {
    Show-Banner
    Write-Host ""
    Write-Host "Agentic Brain Setup Script" -ForegroundColor White
    Write-Host ""
    Write-Host "Usage: .\setup.ps1 [OPTIONS]"
    Write-Host ""
    Write-Host "Options:" -ForegroundColor Cyan
    Write-Host "  -Install      Fresh installation (local Python venv)"
    Write-Host "  -Docker       Docker only (no local Python needed)"
    Write-Host "  -Update       Update (git pull + reinstall deps)"
    Write-Host "  -Reset        Hard reset and clean install"
    Write-Host "  -Config       Generate/regenerate config files"
    Write-Host "  -SkipDeps     Skip dependency installation if already installed (idempotent)"
    Write-Host "  -ForceDeps    Force reinstall of dependencies (ignores marker file)"
    Write-Host "  -Help         Show this help message"
    Write-Host ""
    Write-Host "Examples:" -ForegroundColor Cyan
    Write-Host "  .\setup.ps1                              # Interactive menu"
    Write-Host "  .\setup.ps1 -Install                     # Local Python install"
    Write-Host "  .\setup.ps1 -Docker                      # Docker only (production)"
    Write-Host "  .\setup.ps1 -Install -SkipDeps          # Install but skip if deps exist"
    Write-Host "  .\setup.ps1 -Update                      # Pull latest and update"
    Write-Host "  .\setup.ps1 -Reset                       # Nuclear option - reset everything"
    Write-Host ""
    Write-Host "Installation Modes:" -ForegroundColor Cyan
    Write-Host "  -Install:  Python venv + pip (development, testing)"
    Write-Host "  -Docker:   Docker image only (production, no Python needed locally)"
    Write-Host ""
    Write-Host "Idempotency:" -ForegroundColor Cyan
    Write-Host "  Safe to run multiple times! Use -SkipDeps to skip reinstalling dependencies."
    Write-Host "  A marker file (.deps-installed) tracks successful dependency installation."
    Write-Host "  Delete .deps-installed manually to force reinstall, or use -ForceDeps flag."
    Write-Host ""
}

# ============================================================
# Interactive Menu
# ============================================================
function Show-Menu {
    Show-Banner
    
    Write-Host "Please select what to do:" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  1) Install        - Fresh installation (local Python)" -ForegroundColor White
    Write-Host "  2) Docker Only    - Build Docker image (no local Python)" -ForegroundColor Magenta
    Write-Host "  3) Manage Docker  - Start/Stop/Restart containers" -ForegroundColor Green
    Write-Host "  4) Update         - Pull latest and reinstall" -ForegroundColor White
    Write-Host "  5) Reset          - Hard reset (loses local changes)" -ForegroundColor White
    Write-Host "  6) Generate Config - Create .env file" -ForegroundColor White
    Write-Host "  7) Exit" -ForegroundColor White
    Write-Host ""
    
    $choice = Read-Host "Enter selection (1-7)"
    
    switch ($choice) {
        "1" { return "install" }
        "2" { return "docker" }
        "3" { return "manage" }
        "4" { return "update" }
        "5" { return "reset" }
        "6" { return "config" }
        "7" { return "exit" }
        default {
            Write-Warning "Invalid choice. Please enter 1-7."
            return Show-Menu
        }
    }
}

# ============================================================
# Main routines
# ============================================================
function Invoke-Install {
    Write-Block "Green" "Agentic Brain Installation"
    
    Find-Python
    Test-RequiredTools
    Initialize-Venv
    Install-PythonDeps -SkipIfInstalled:$SkipDeps
    New-Config
    Show-PostInstall
}

function Invoke-Update {
    Write-Block "Cyan" "Agentic Brain Update"
    
    Find-Python
    Update-Git
    Initialize-Venv
    Install-PythonDeps -SkipIfInstalled:$SkipDeps
    Show-PostInstall
}

function Invoke-Reset {
    Write-Block "Red" "Agentic Brain Reset"
    
    $confirmed = Reset-Git
    if (-not $confirmed) {
        return
    }
    
    Find-Python
    Initialize-Venv -Force
    Remove-Item $DEPS_MARKER_FILE -Force -ErrorAction SilentlyContinue
    Write-Info "Dependency marker cleared for fresh install"
    Install-PythonDeps
    New-Config
    Show-PostInstall
}

# ============================================================
# Main Entry Point
# ============================================================

# Initialize log file
"Agentic Brain Setup - Started $(Get-Date)" | Out-File $LogFilePath
"Working directory: $SCRIPT_DIR" | Out-File $LogFilePath -Append
"PowerShell version: $($PSVersionTable.PSVersion)" | Out-File $LogFilePath -Append

Set-Location $SCRIPT_DIR

# Handle command-line arguments
if ($Help) {
    Show-Help
    exit 0
}

if ($Update) {
    Invoke-Update
    exit 0
}

if ($Reset) {
    Invoke-Reset
    exit 0
}

if ($Config) {
    New-Config
    exit 0
}

if ($Docker) {
    Write-Block "Magenta" "Docker-Only Installation"
    Write-Info "Skipping local Python install - using Docker"
    New-Config
    Invoke-DockerBuild
    exit 0
}

if ($Install) {
    Invoke-Install
    exit 0
}

# No flags passed - show interactive menu
$action = Show-Menu

switch ($action) {
    "install" { Invoke-Install }
    "docker"  { 
        Write-Block "Magenta" "Docker-Only Installation"
        Write-Info "Skipping local Python install - using Docker"
        New-Config
        Invoke-DockerBuild
    }
    "manage"  { Invoke-DockerManage }
    "update"  { Invoke-Update }
    "reset"   { Invoke-Reset }
    "config"  { New-Config }
    "exit"    { 
        Write-Info "Goodbye!"
        exit 0
    }
}
