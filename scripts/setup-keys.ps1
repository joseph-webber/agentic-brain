#Requires -Version 5.0
<#
.SYNOPSIS
    API Key Configuration Script for Agentic Brain
    
.DESCRIPTION
    Helps Windows users securely set up API keys for various LLM providers
    in a user-friendly, guided manner.
    
    This script:
    - Prompts for API keys with clear instructions
    - Creates .env and .env.docker configuration files
    - Detects default providers based on available keys
    - Optionally restarts Docker containers
    - Provides a summary of configuration
    
.EXAMPLE
    .\setup-keys.ps1
    
.NOTES
    Author: Agentic Brain Team
    Version: 1.0
    Platform: Windows PowerShell 5.0+
#>

param(
    [switch]$SkipDockerRestart,
    [switch]$Quiet
)

# ============================================================================
# CONFIGURATION
# ============================================================================

$projectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$envFile = Join-Path $projectRoot ".env"
$envDockerFile = Join-Path $projectRoot ".env.docker"
$scriptsDir = $PSScriptRoot

# Provider information with instructions
$providers = @{
    "Ollama" = @{
        key = "OLLAMA_API_KEY"
        url = "https://ollama.ai"
        free = $true
        instructions = @"
FREE - Local LLM Server
━━━━━━━━━━━━━━━━━━━━━━
1. Download Ollama from https://ollama.ai
2. Run: ollama serve
3. Pull a model: ollama pull llama2
4. Default endpoint: http://localhost:11434
5. Leave blank to use local Ollama
"@
        example = "leave blank for local"
    }
    
    "Groq" = @{
        key = "GROQ_API_KEY"
        url = "https://console.groq.com"
        free = $true
        instructions = @"
FREE - Fastest Inference API
━━━━━━━━━━━━━━━━━━━━━━━━━━
1. Create account at https://console.groq.com
2. Go to API Keys section
3. Create a new API key
4. Copy the key (looks like: gsk_...)
"@
        example = "gsk_xxxxxxxxxxxxxxxxxxxx"
    }
    
    "Google Gemini" = @{
        key = "GOOGLE_API_KEY"
        url = "https://makersuite.google.com/app/apikey"
        free = $true
        instructions = @"
FREE - Google's Latest Model
━━━━━━━━━━━━━━━━━━━━━━━━━
1. Visit https://makersuite.google.com/app/apikey
2. Click "Create API Key"
3. Copy the generated key
4. Free tier includes: 60 requests/minute
"@
        example = "AIzaSy..."
    }
    
    "OpenAI" = @{
        key = "OPENAI_API_KEY"
        url = "https://platform.openai.com/api-keys"
        free = $false
        instructions = @"
PAID - OpenAI GPT Models
━━━━━━━━━━━━━━━━━━━━━━
1. Create account at https://platform.openai.com
2. Go to API Keys: https://platform.openai.com/api-keys
3. Click "Create new secret key"
4. Copy the key (looks like: sk-...)
5. Requires valid payment method
"@
        example = "sk_xxxxxxxxxxxxxxxxxxxxxxxx"
    }
    
    "Anthropic" = @{
        key = "ANTHROPIC_API_KEY"
        url = "https://console.anthropic.com"
        free = $false
        instructions = @"
PAID - Claude Models
━━━━━━━━━━━━━━━━━━
1. Create account at https://console.anthropic.com
2. Go to API Keys section
3. Create a new API key
4. Copy the key (looks like: sk-ant-...)
5. Requires valid payment method
"@
        example = "sk-ant-xxxxxxxxxxxxxxxxxxxxxxxx"
    }
    
    "xAI" = @{
        key = "XAI_API_KEY"
        url = "https://console.x.ai"
        free = $false
        instructions = @"
PAID - xAI Grok Model
━━━━━━━━━━━━━━━━━━━
1. Create account at https://console.x.ai
2. Go to API Keys section
3. Create a new API key
4. Copy the key
5. Requires valid payment method
"@
        example = "xai_xxxxxxxxxxxxxxxxxxxxxxxx"
    }
}

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

function Write-Header {
    param([string]$Text)
    Write-Host "`n" -NoNewline
    Write-Host "╔════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
    Write-Host "║ $($Text.PadRight(56)) ║" -ForegroundColor Cyan
    Write-Host "╚════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
    Write-Host ""
}

function Write-Section {
    param([string]$Text)
    Write-Host "`n▶ $Text" -ForegroundColor Green
    Write-Host "─" * 60 -ForegroundColor DarkGray
}

function Write-Success {
    param([string]$Text)
    Write-Host "✓ $Text" -ForegroundColor Green
}

function Write-Warning {
    param([string]$Text)
    Write-Host "⚠ $Text" -ForegroundColor Yellow
}

function Write-Error {
    param([string]$Text)
    Write-Host "✗ $Text" -ForegroundColor Red
}

function Write-Info {
    param([string]$Text)
    Write-Host "ℹ $Text" -ForegroundColor Cyan
}

function Read-SecureInput {
    param(
        [string]$Prompt,
        [string]$DefaultValue = ""
    )
    
    if ($DefaultValue) {
        Write-Host "$Prompt [$DefaultValue]: " -ForegroundColor White -NoNewline
    }
    else {
        Write-Host "$Prompt: " -ForegroundColor White -NoNewline
    }
    
    $input = Read-Host
    
    if ([string]::IsNullOrWhiteSpace($input)) {
        return $DefaultValue
    }
    
    return $input.Trim()
}

function Test-DockerRunning {
    try {
        $result = docker version *>$null
        return $?
    }
    catch {
        return $false
    }
}

function Restart-DockerContainers {
    Write-Section "Docker Container Restart"
    
    if (-not (Test-DockerRunning)) {
        Write-Warning "Docker is not running. Start Docker Desktop and try again."
        return
    }
    
    $response = Read-Host "Restart Docker containers? (y/n)"
    
    if ($response -eq 'y' -or $response -eq 'Y') {
        try {
            Write-Info "Stopping containers..."
            docker-compose -f "$projectRoot/docker-compose.yml" down 2>$null
            
            Write-Info "Starting containers..."
            docker-compose -f "$projectRoot/docker-compose.yml" up -d 2>$null
            
            Write-Success "Docker containers restarted successfully!"
        }
        catch {
            Write-Error "Failed to restart Docker: $_"
            Write-Warning "You can manually restart with: docker-compose up -d"
        }
    }
}

# ============================================================================
# PROMPT FUNCTIONS
# ============================================================================

function Prompt-ForApiKey {
    param(
        [string]$ProviderName,
        [hashtable]$ProviderInfo
    )
    
    Write-Section $ProviderName
    Write-Host $ProviderInfo.instructions -ForegroundColor Gray
    
    Write-Host ""
    if ($ProviderInfo.free) {
        Write-Info "This is a FREE provider" -ForegroundColor Green
    }
    else {
        Write-Warning "This is a PAID provider"
    }
    
    Write-Host ""
    Write-Info "Example: $($ProviderInfo.example)" -ForegroundColor DarkGray
    Write-Host ""
    
    $key = Read-SecureInput "Enter $ProviderName API Key (or press Enter to skip)"
    
    return $key
}

# ============================================================================
# ENV FILE FUNCTIONS
# ============================================================================

function Create-EnvFile {
    param(
        [hashtable]$ApiKeys,
        [string]$DefaultProvider
    )
    
    $envContent = @"
# ============================================================================
# AGENTIC BRAIN - LOCAL DEVELOPMENT CONFIGURATION
# ============================================================================
# Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
# Platform: Windows
#
# WARNING: This file contains API keys. DO NOT commit to version control!
# Add .env to .gitignore if not already present.
# ============================================================================

# ──────────────────────────────────────────────────────────────────────────
# DEFAULT PROVIDER (auto-detected based on available keys)
# ──────────────────────────────────────────────────────────────────────────
DEFAULT_LLM_PROVIDER=$DefaultProvider

# ──────────────────────────────────────────────────────────────────────────
# FREE PROVIDERS (recommended for development)
# ──────────────────────────────────────────────────────────────────────────

# Ollama - Local LLM Server (FREE)
# Run locally: ollama serve
# Download: https://ollama.ai
# Models: llama2, mistral, neural-chat, etc.
OLLAMA_API_KEY=$($ApiKeys['Ollama'] ? $ApiKeys['Ollama'] : '# Leave empty for local Ollama')
OLLAMA_BASE_URL=http://localhost:11434

# Groq - Fastest API (FREE)
# Sign up: https://console.groq.com
GROQ_API_KEY=$($ApiKeys['Groq'] ? $ApiKeys['Groq'] : '# sk_...')

# Google Gemini - Latest Models (FREE tier available)
# Sign up: https://makersuite.google.com/app/apikey
GOOGLE_API_KEY=$($ApiKeys['Google Gemini'] ? $ApiKeys['Google Gemini'] : '# AIzaSy...')

# ──────────────────────────────────────────────────────────────────────────
# PAID PROVIDERS (production use)
# ──────────────────────────────────────────────────────────────────────────

# OpenAI - GPT Models (PAID)
# Sign up: https://platform.openai.com/api-keys
OPENAI_API_KEY=$($ApiKeys['OpenAI'] ? $ApiKeys['OpenAI'] : '# sk_...')
OPENAI_ORG_ID=

# Anthropic - Claude Models (PAID)
# Sign up: https://console.anthropic.com
ANTHROPIC_API_KEY=$($ApiKeys['Anthropic'] ? $ApiKeys['Anthropic'] : '# sk-ant-...')

# xAI - Grok Model (PAID)
# Sign up: https://console.x.ai
XAI_API_KEY=$($ApiKeys['xAI'] ? $ApiKeys['xAI'] : '# xai_...')

# ──────────────────────────────────────────────────────────────────────────
# DEVELOPMENT SETTINGS
# ──────────────────────────────────────────────────────────────────────────
DEBUG=false
LOG_LEVEL=info
ENABLE_CACHE=true
CACHE_TTL=3600

# ──────────────────────────────────────────────────────────────────────────
# SECURITY NOTES
# ──────────────────────────────────────────────────────────────────────────
# 1. Never commit this file to version control
# 2. Use strong API keys (rotate regularly)
# 3. Monitor API usage in provider dashboards
# 4. Set rate limits where available
# 5. Use separate keys for dev/staging/production
"@

    try {
        Set-Content -Path $envFile -Value $envContent -Encoding UTF8 -Force
        Write-Success "Created .env file: $envFile"
        return $true
    }
    catch {
        Write-Error "Failed to create .env file: $_"
        return $false
    }
}

function Create-EnvDockerFile {
    param(
        [hashtable]$ApiKeys,
        [string]$DefaultProvider
    )
    
    $envContent = @"
# ============================================================================
# AGENTIC BRAIN - DOCKER CONFIGURATION
# ============================================================================
# Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
# Platform: Windows (Docker Desktop)
#
# This file is used for Docker containers. It's separate from .env
# to allow different configurations for containerized environments.
# ============================================================================

# ──────────────────────────────────────────────────────────────────────────
# DEFAULT PROVIDER
# ──────────────────────────────────────────────────────────────────────────
DEFAULT_LLM_PROVIDER=$DefaultProvider

# ──────────────────────────────────────────────────────────────────────────
# API KEYS (Same as .env, but can be overridden for Docker)
# ──────────────────────────────────────────────────────────────────────────
OLLAMA_API_KEY=$($ApiKeys['Ollama'] ? $ApiKeys['Ollama'] : '')
OLLAMA_BASE_URL=http://host.docker.internal:11434

GROQ_API_KEY=$($ApiKeys['Groq'] ? $ApiKeys['Groq'] : '')
GOOGLE_API_KEY=$($ApiKeys['Google Gemini'] ? $ApiKeys['Google Gemini'] : '')
OPENAI_API_KEY=$($ApiKeys['OpenAI'] ? $ApiKeys['OpenAI'] : '')
ANTHROPIC_API_KEY=$($ApiKeys['Anthropic'] ? $ApiKeys['Anthropic'] : '')
XAI_API_KEY=$($ApiKeys['xAI'] ? $ApiKeys['xAI'] : '')

# ──────────────────────────────────────────────────────────────────────────
# DOCKER-SPECIFIC SETTINGS
# ──────────────────────────────────────────────────────────────────────────
DOCKER_ENV=development
COMPOSE_PROJECT_NAME=agentic-brain

# For connecting to host services from Docker container
# Use host.docker.internal instead of localhost
HOST_DOCKER_INTERNAL=host.docker.internal

# ──────────────────────────────────────────────────────────────────────────
# DEVELOPMENT SETTINGS
# ──────────────────────────────────────────────────────────────────────────
DEBUG=false
LOG_LEVEL=info
ENABLE_CACHE=true

# ──────────────────────────────────────────────────────────────────────────
# CONTAINER RESOURCES
# ──────────────────────────────────────────────────────────────────────────
MEMORY_LIMIT=2g
CPU_LIMIT=2
"@

    try {
        Set-Content -Path $envDockerFile -Value $envContent -Encoding UTF8 -Force
        Write-Success "Created .env.docker file: $envDockerFile"
        return $true
    }
    catch {
        Write-Error "Failed to create .env.docker file: $_"
        return $false
    }
}

# ============================================================================
# DETECTION FUNCTIONS
# ============================================================================

function Detect-DefaultProvider {
    param([hashtable]$ApiKeys)
    
    $enabledProviders = @()
    
    if ($ApiKeys['Groq'] -and $ApiKeys['Groq'].Length -gt 0) { $enabledProviders += "Groq" }
    if ($ApiKeys['Google Gemini'] -and $ApiKeys['Google Gemini'].Length -gt 0) { $enabledProviders += "Google Gemini" }
    if ($ApiKeys['Ollama'] -and $ApiKeys['Ollama'].Length -gt 0) { $enabledProviders += "Ollama" }
    if ($ApiKeys['OpenAI'] -and $ApiKeys['OpenAI'].Length -gt 0) { $enabledProviders += "OpenAI" }
    if ($ApiKeys['Anthropic'] -and $ApiKeys['Anthropic'].Length -gt 0) { $enabledProviders += "Anthropic" }
    if ($ApiKeys['xAI'] -and $ApiKeys['xAI'].Length -gt 0) { $enabledProviders += "xAI" }
    
    # Prioritize free providers, then by order
    $priority = @("Groq", "Google Gemini", "Ollama", "OpenAI", "Anthropic", "xAI")
    
    foreach ($prov in $priority) {
        if ($enabledProviders -contains $prov) {
            return $prov
        }
    }
    
    return "ollama"  # Default fallback
}

# ============================================================================
# MAIN LOGIC
# ============================================================================

function Main {
    Write-Header "API Key Configuration"
    
    Write-Host "Welcome to the Agentic Brain API Key Setup!" -ForegroundColor Cyan
    Write-Host ""
    Write-Info "This wizard will help you configure API keys for various LLM providers."
    Write-Info "You can skip any provider by pressing Enter."
    Write-Host ""
    
    $proceed = Read-Host "Continue? (y/n)"
    if ($proceed -ne 'y' -and $proceed -ne 'Y') {
        Write-Info "Setup cancelled."
        exit 0
    }
    
    # ────────────────────────────────────────────────────────────────────
    # COLLECT API KEYS
    # ────────────────────────────────────────────────────────────────────
    
    $apiKeys = @{}
    
    Write-Header "API KEY COLLECTION"
    
    foreach ($providerName in $providers.Keys) {
        $key = Prompt-ForApiKey -ProviderName $providerName -ProviderInfo $providers[$providerName]
        $apiKeys[$providerName] = $key
    }
    
    # ────────────────────────────────────────────────────────────────────
    # DETECT DEFAULT PROVIDER
    # ────────────────────────────────────────────────────────────────────
    
    $defaultProvider = Detect-DefaultProvider -ApiKeys $apiKeys
    
    Write-Section "Provider Detection"
    Write-Info "Auto-detected default provider: $defaultProvider"
    
    $customDefault = Read-Host "Override default provider? (provider name or press Enter to keep)"
    if (-not [string]::IsNullOrWhiteSpace($customDefault)) {
        if ($providers.ContainsKey($customDefault)) {
            $defaultProvider = $customDefault
            Write-Success "Default provider set to: $defaultProvider"
        }
        else {
            Write-Warning "Unknown provider: $customDefault. Keeping: $defaultProvider"
        }
    }
    
    # ────────────────────────────────────────────────────────────────────
    # CREATE ENV FILES
    # ────────────────────────────────────────────────────────────────────
    
    Write-Section "Creating Configuration Files"
    
    $envCreated = Create-EnvFile -ApiKeys $apiKeys -DefaultProvider $defaultProvider
    $dockerEnvCreated = Create-EnvDockerFile -ApiKeys $apiKeys -DefaultProvider $defaultProvider
    
    if (-not $envCreated -or -not $dockerEnvCreated) {
        Write-Error "Failed to create configuration files!"
        exit 1
    }
    
    # ────────────────────────────────────────────────────────────────────
    # SUMMARY
    # ────────────────────────────────────────────────────────────────────
    
    Write-Header "Configuration Summary"
    
    Write-Host "Configured Providers:" -ForegroundColor Green
    Write-Host ""
    
    $providersConfigured = 0
    foreach ($providerName in $providers.Keys) {
        if ($apiKeys[$providerName] -and $apiKeys[$providerName].Length -gt 0) {
            $status = if ($providers[$providerName].free) { "FREE" } else { "PAID" }
            Write-Host "  ✓ $providerName [$status]" -ForegroundColor Green
            $providersConfigured++
        }
    }
    
    if ($providersConfigured -eq 0) {
        Write-Warning "No providers configured! You can configure them manually:"
        Write-Info "  1. Edit $envFile"
        Write-Info "  2. Restart your application"
    }
    else {
        Write-Host ""
        Write-Success "Successfully configured $providersConfigured provider(s)!"
    }
    
    Write-Host ""
    Write-Host "Default Provider: $defaultProvider" -ForegroundColor Cyan
    
    Write-Host ""
    Write-Section "Next Steps"
    
    Write-Info "1. Configuration files created:"
    Write-Host "   └─ Local:  $envFile" -ForegroundColor DarkGray
    Write-Host "   └─ Docker: $envDockerFile" -ForegroundColor DarkGray
    
    Write-Info "2. Environment variables are now ready to use"
    
    Write-Info "3. Start your application:"
    Write-Host "   npm run dev    (Node.js)" -ForegroundColor DarkGray
    Write-Host "   python main.py (Python)" -ForegroundColor DarkGray
    Write-Host "   docker-compose up (Docker)" -ForegroundColor DarkGray
    
    Write-Info "4. To update keys later, edit the .env file or re-run this script"
    
    # ────────────────────────────────────────────────────────────────────
    # DOCKER RESTART OFFER
    # ────────────────────────────────────────────────────────────────────
    
    if (-not $SkipDockerRestart) {
        Restart-DockerContainers
    }
    
    Write-Host ""
    Write-Header "Setup Complete!"
    Write-Host "Your API keys are configured and ready to use." -ForegroundColor Green
    Write-Host ""
    Write-Warning "Remember: Never commit .env files to version control!"
    Write-Info "Add '.env' and '.env.docker' to your .gitignore file."
    Write-Host ""
}

# ============================================================================
# ENTRY POINT
# ============================================================================

try {
    Main
}
catch {
    Write-Error "An unexpected error occurred: $_"
    Write-Info "For troubleshooting, check:"
    Write-Host "  1. PowerShell version: $PSVersionTable.PSVersion" -ForegroundColor DarkGray
    Write-Host "  2. File permissions: $projectRoot" -ForegroundColor DarkGray
    Write-Host "  3. Antivirus or security software blocking access" -ForegroundColor DarkGray
    exit 1
}
