# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber
# =============================================================================
# Agentic Brain - Bulletproof PowerShell Installer
# Based on Retool install patterns
# =============================================================================
# Usage: irm https://raw.githubusercontent.com/joseph-webber/agentic-brain/main/install.ps1 | iex
# =============================================================================

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

# Configuration
$RepoUrl = "https://github.com/joseph-webber/agentic-brain.git"
$InstallDir = if ($env:AGENTIC_BRAIN_DIR) { $env:AGENTIC_BRAIN_DIR } else { "$HOME\agentic-brain" }
$Branch = if ($env:AGENTIC_BRAIN_BRANCH) { $env:AGENTIC_BRAIN_BRANCH } else { "main" }
$EnvFile = Join-Path $InstallDir ".env"

function Write-Banner {
    Write-Host ""
    Write-Host "╔═══════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
    Write-Host "║             🧠 Agentic Brain Installer 🧠                     ║" -ForegroundColor Cyan
    Write-Host "║                                                               ║" -ForegroundColor Cyan
    Write-Host "║  Universal AI Brain with Neo4j, Redis & Redpanda             ║" -ForegroundColor Cyan
    Write-Host "║                  (Bulletproof Edition)                        ║" -ForegroundColor Cyan
    Write-Host "╚═══════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
    Write-Host ""
}

function Write-Info($Message) {
    Write-Host "ℹ️  $Message" -ForegroundColor Blue
}

function Write-Success($Message) {
    Write-Host "✅ $Message" -ForegroundColor Green
}

function Write-Warning($Message) {
    Write-Host "⚠️  $Message" -ForegroundColor Yellow
}

function Write-Error($Message) {
    Write-Host "❌ $Message" -ForegroundColor Red
}

# Check if command exists
function Test-Command($Command) {
    $null -ne (Get-Command $Command -ErrorAction SilentlyContinue)
}

# Random password generator (like Retool)
function New-RandomPassword($Length) {
    $bytes = [System.Byte[]]::new($Length)
    $rng = [System.Security.Cryptography.RNGCryptoServiceProvider]::new()
    $rng.GetBytes($bytes)
    $rng.Dispose()
    $base64 = [Convert]::ToBase64String($bytes)
    # Remove special characters that might cause issues with URLs/shells
    $base64 -replace '[+/=]', '' | Select-Object -First 1 -OutVariable password | ForEach-Object {
        $_.Substring(0, [Math]::Min($Length, $_.Length))
    }
}

# Check Docker
function Test-Docker {
    Write-Info "Checking Docker installation..."
    
    if (-not (Test-Command "docker")) {
        Write-Warning "Docker is not installed"
        $response = Read-Host "  Would you like to install Docker? (y/n)"
        
        if ($response -eq "y" -or $response -eq "Y") {
            if (Test-Command "winget") {
                Write-Info "Installing Docker Desktop via winget..."
                winget install Docker.DockerDesktop --accept-package-agreements --silent 2>&1 | Out-Null
                Write-Success "Docker installed. Please start Docker Desktop and run this script again."
                exit 0
            } else {
                Write-Error "winget not found. Please install Docker manually:"
                Write-Host "  https://docs.docker.com/desktop/install/windows-install/"
                exit 1
            }
        } else {
            Write-Error "Docker is required."
            exit 1
        }
    }
    
    # Check if Docker daemon is running
    try {
        $null = docker info 2>&1
        if ($LASTEXITCODE -ne 0) { throw "Docker not running" }
        Write-Success "Docker is installed and running"
    }
    catch {
        Write-Error "Docker daemon is not running!"
        Write-Host ""
        Write-Host "Please start Docker Desktop and try again."
        exit 1
    }
}

# Check Docker Compose
function Test-DockerCompose {
    Write-Info "Checking Docker Compose..."
    
    # Try docker compose (v2) first
    try {
        $null = docker compose version 2>&1
        if ($LASTEXITCODE -eq 0) {
            $script:ComposeCmd = "docker compose"
            Write-Success "Docker Compose v2 found"
            return
        }
    } catch {}
    
    # Try docker-compose (v1)
    if (Test-Command "docker-compose") {
        $script:ComposeCmd = "docker-compose"
        Write-Success "Docker Compose v1 found"
        return
    }
    
    Write-Error "Docker Compose not found!"
    Write-Host ""
    Write-Host "Docker Desktop includes Compose by default."
    Write-Host "Please ensure Docker Desktop is fully installed."
    exit 1
}

# Setup repository
function Set-Repository {
    Write-Info "Setting up repository..."
    
    if (Test-Path "$InstallDir\.git") {
        Write-Info "Repository exists, updating..."
        Set-Location $InstallDir
        
        git fetch origin 2>&1 | Out-Null
        try {
            git checkout $Branch 2>&1 | Out-Null
        } catch {
            git checkout -b $Branch "origin/$Branch" 2>&1 | Out-Null
        }
        
        try {
            git pull origin $Branch --ff-only 2>&1 | Out-Null
        } catch {
            Write-Warning "Pull conflict, resetting to origin/$Branch"
            git reset --hard "origin/$Branch" 2>&1 | Out-Null
        }
        
        Write-Success "Repository updated"
    }
    else {
        Write-Info "Cloning repository (this may take a minute)..."
        
        # Create parent directory if needed
        $ParentDir = Split-Path $InstallDir -Parent
        if (-not (Test-Path $ParentDir)) {
            New-Item -ItemType Directory -Path $ParentDir -Force | Out-Null
        }
        
        git clone --depth 1 --branch $Branch $RepoUrl $InstallDir 2>&1 | Out-Null
        Set-Location $InstallDir
        
        Write-Success "Repository cloned to $InstallDir"
    }
}

# Setup environment (Retool pattern)
function Set-Environment {
    Write-Info "Generating environment configuration..."
    
    # Check if .env already exists (Retool pattern: exit if it does)
    if (Test-Path $EnvFile) {
        Write-Warning ".env file already exists at $EnvFile"
        Write-Warning "Skipping environment setup to preserve existing configuration"
        return
    }
    
    # Generate random passwords (Retool pattern)
    $Neo4jPassword = New-RandomPassword 64
    $RedisPassword = New-RandomPassword 64
    $EncryptionKey = New-RandomPassword 64
    # JWT_SECRET: Generate using GUID combination for better randomness
    $JwtSecret = [System.Guid]::NewGuid().ToString().Replace("-", "") + [System.Guid]::NewGuid().ToString().Replace("-", "")
    
    # Upgrade pip first (critical for Windows - clears cache issues)
    Write-Info "Upgrading pip to latest version..."
    try {
        python.exe -m pip install --no-cache-dir --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org --upgrade pip
        Write-Success "pip upgraded successfully"
    } catch {
        Write-Warning "pip upgrade encountered an issue, continuing..."
    }
    
    # Handle corporate SSL/proxy
    if ($env:REQUESTS_CA_BUNDLE -or $env:SSL_CERT_FILE) {
        Write-Info "Corporate SSL detected, configuring trusted hosts..."
        $env:PIP_TRUSTED_HOST = "pypi.org pypi.python.org files.pythonhosted.org"
    }
    
    # Create .env file (like Retool)
    $EnvContent = @"
# ============================================================================
# Agentic Brain Configuration
# Generated by bulletproof installer on $(Get-Date)
# ============================================================================

# Core Application Settings
ENVIRONMENT=production
DEBUG=false
APP_PORT=8000

# ============================================================================
# Neo4j Graph Database
# ============================================================================
NEO4J_HOST=neo4j
NEO4J_PORT=7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=$Neo4jPassword
NEO4J_URI=bolt://neo4j:7687
NEO4J_ADMIN_USER=neo4j
NEO4J_ADMIN_PASSWORD=$Neo4jPassword

# ============================================================================
# Redis Cache
# ============================================================================
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=$RedisPassword
REDIS_DB=0

# ============================================================================
# Redpanda Message Queue
# ============================================================================
REDPANDA_HOST=redpanda
REDPANDA_PORT=9092
REDPANDA_BROKERS=redpanda:9092

# ============================================================================
# Security & Encryption
# ============================================================================
# Key to encrypt/decrypt sensitive values in Neo4j
ENCRYPTION_KEY=$EncryptionKey

# Key to sign JWT authentication tokens
JWT_SECRET=$JwtSecret

# ============================================================================
# LLM Provider Configuration
# Choose ONE provider and add your API key if needed
# ============================================================================

# Groq (Fastest, free tier available)
# GROQ_API_KEY=your-groq-key-here

# OpenAI (Best quality)
# OPENAI_API_KEY=your-openai-key-here

# Anthropic Claude (Great reasoning)
# ANTHROPIC_API_KEY=your-anthropic-key-here

# Local Ollama (Works offline, free)
OLLAMA_BASE_URL=http://localhost:11434
DEFAULT_LLM_PROVIDER=ollama
DEFAULT_LLM_MODEL=llama3.2

# ============================================================================
# Corporate Proxy / SSL Configuration
# ============================================================================
# Uncomment if behind corporate proxy with SSL inspection
# PIP_TRUSTED_HOST=pypi.org pypi.python.org files.pythonhosted.org
# REQUESTS_CA_BUNDLE=C:\path\to\ca-bundle.crt
# SSL_CERT_FILE=C:\path\to\ca-bundle.crt

# ============================================================================
# Advanced Configuration (usually not needed)
# ============================================================================
LOG_LEVEL=INFO
TELEMETRY_ENABLED=true
METRICS_PORT=9090

# ============================================================================
# IMPORTANT: Customize before production deployment!
# 1. Change all passwords to strong, unique values
# 2. Add your LLM API key(s) if using cloud providers
# 3. Configure SSL certificates for HTTPS
# 4. Set up proper backups and monitoring
# ============================================================================
"@
    
    Set-Content -Path $EnvFile -Value $EnvContent -Encoding UTF8
    
    Write-Success "Created .env file with random passwords"
    Write-Host ""
    Write-Host "  📝 .env file location: $EnvFile"
    Write-Host "  🔐 Passwords generated: Neo4j, Redis, JWT, Encryption"
    Write-Host ""
}

# Start services
function Start-Services {
    Write-Info "Starting Agentic Brain services..."
    Set-Location $InstallDir
    
    # Pull images
    Write-Info "Pulling Docker images (this may take a few minutes)..."
    try {
        if ($ComposeCmd -eq "docker compose") {
            docker compose pull --quiet 2>&1 | Out-Null
        } else {
            docker-compose pull --quiet 2>&1 | Out-Null
        }
        Write-Success "Docker images pulled"
    } catch {
        Write-Info "Pulling images with output..."
        if ($ComposeCmd -eq "docker compose") {
            docker compose pull
        } else {
            docker-compose pull
        }
    }
    
    # Start services
    Write-Info "Starting services with: $ComposeCmd up -d"
    if ($ComposeCmd -eq "docker compose") {
        docker compose up -d
    } else {
        docker-compose up -d
    }
    
    Write-Success "Services started successfully"
}

# Wait for health
function Wait-ForHealth {
    Write-Info "Waiting for services to become healthy..."
    
    $MaxWait = 180
    $Waited = 0
    $Interval = 3
    
    $Neo4jReady = $false
    $RedisReady = $false
    $RedpandaReady = $false
    
    Write-Host ""
    while ($Waited -lt $MaxWait) {
        try {
            # Check Neo4j
            if (-not $Neo4jReady) {
                $null = Invoke-WebRequest -Uri "http://localhost:7474" -UseBasicParsing -TimeoutSec 2 -ErrorAction SilentlyContinue
                if ($?) {
                    Write-Success "✓ Neo4j is ready (http://localhost:7474)"
                    $Neo4jReady = $true
                }
            }
            
            # Check Redis
            if (-not $RedisReady) {
                $redis = docker exec agentic-brain-redis redis-cli -a "$RedisPassword" ping 2>&1
                if ($redis -match "PONG") {
                    Write-Success "✓ Redis is ready"
                    $RedisReady = $true
                }
            }
            
            # Check Redpanda
            if (-not $RedpandaReady) {
                $null = Invoke-WebRequest -Uri "http://localhost:9644/v1/status/ready" -UseBasicParsing -TimeoutSec 2 -ErrorAction SilentlyContinue
                if ($?) {
                    Write-Success "✓ Redpanda is ready"
                    $RedpandaReady = $true
                }
            }
            
            # All healthy?
            if ($Neo4jReady -and $RedisReady -and $RedpandaReady) {
                Write-Host ""
                return
            }
        } catch {}
        
        Write-Host "." -NoNewline
        Start-Sleep -Seconds $Interval
        $Waited += $Interval
    }
    
    Write-Host ""
    Write-Warning "Services are starting (may take a few more moments)..."
    Write-Info "Check status with: $ComposeCmd ps"
    Write-Info "View logs with: $ComposeCmd logs -f"
}

# Print success
function Write-SuccessMessage {
    Write-Host ""
    Write-Host "╔═══════════════════════════════════════════════════════════════╗" -ForegroundColor Green
    Write-Host "║        🎉 Agentic Brain Installed Successfully! 🎉            ║" -ForegroundColor Green
    Write-Host "╚═══════════════════════════════════════════════════════════════╝" -ForegroundColor Green
    Write-Host ""
    
    Write-Host "📍 Service URLs:" -ForegroundColor Cyan
    Write-Host "   • API Server:      http://localhost:8000"
    Write-Host "   • API Docs:        http://localhost:8000/docs"
    Write-Host "   • Neo4j Browser:   http://localhost:7474"
    Write-Host "   • Redpanda UI:     http://localhost:9644"
    Write-Host ""
    
    Write-Host "🔐 Default Credentials:" -ForegroundColor Cyan
    Write-Host "   • Neo4j User:      neo4j"
    Write-Host "   • Neo4j Password:  (See $EnvFile)"
    Write-Host "   • Redis Password:  (See $EnvFile)"
    Write-Host ""
    
    Write-Host "📂 Installation Directory:" -ForegroundColor Cyan
    Write-Host "   $InstallDir"
    Write-Host ""
    
    Write-Host "🚀 Quick Commands:" -ForegroundColor Cyan
    Write-Host "   cd $InstallDir"
    Write-Host "   $ComposeCmd logs -f          # View real-time logs"
    Write-Host "   $ComposeCmd ps               # Check service status"
    Write-Host "   $ComposeCmd down             # Stop services"
    Write-Host "   $ComposeCmd up -d            # Start services"
    Write-Host ""
    
    Write-Host "📝 Next Steps:" -ForegroundColor Cyan
    Write-Host "   1. Review .env file: $EnvFile"
    Write-Host "   2. Add your LLM API key if using cloud provider"
    Write-Host "   3. Visit http://localhost:7474 to explore Neo4j"
    Write-Host "   4. Visit http://localhost:8000/docs for API documentation"
    Write-Host ""
    
    Write-Host "💡 Tips:" -ForegroundColor Yellow
    Write-Host "   • For local LLM: run 'ollama pull llama3.2'"
    Write-Host "   • For production: change all passwords in .env"
    Write-Host "   • Check logs if services don't start: $ComposeCmd logs"
    Write-Host ""
}

# Main
function Main {
    Write-Banner
    
    Write-Info "Checking installation requirements..."
    Write-Host ""
    
    # Pre-flight checks
    Test-Docker
    Test-DockerCompose
    
    # Check git
    if (-not (Test-Command "git")) {
        Write-Error "Git is not installed!"
        Write-Host "Install with: winget install Git.Git"
        exit 1
    }
    Write-Success "Git is installed"
    
    Write-Host ""
    # Setup
    Set-Repository
    Set-Location $InstallDir
    Set-Environment
    
    Write-Host ""
    # Start
    Start-Services
    Wait-ForHealth
    
    # Done!
    Write-SuccessMessage
}

# Run
Main
