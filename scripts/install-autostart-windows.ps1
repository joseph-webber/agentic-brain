# ============================================================================
# Agentic Brain - Windows Auto-Start Installer
# ============================================================================
# This script sets up automatic startup for agentic-brain services on Windows
# 
# Supports:
#   - Docker Desktop (auto-start + services)
#   - WSL2 with Docker (auto-start services)
#
# Usage:
#   .\install-autostart-windows.ps1              # Install auto-start
#   .\install-autostart-windows.ps1 -Uninstall  # Remove auto-start
#
# ============================================================================

param(
    [switch]$Uninstall = $false,
    [string]$DockerComposeDir = ".",
    [switch]$Verbose = $false
)

# ============================================================================
# Configuration
# ============================================================================
$ErrorActionPreference = "Stop"
$VerbosePreference = if ($Verbose) { "Continue" } else { "SilentlyContinue" }

$ScriptName = "Agentic Brain Auto-Start"
$TaskPrefix = "AgenticBrain"
$TaskNameDockerStart = "$TaskPrefix-StartDocker"
$TaskNameServices = "$TaskPrefix-StartServices"

# Get the directory where this script is located (or use provided directory)
$InvokeDir = Split-Path $DockerComposeDir -Parent
if ($InvokeDir -eq "") {
    $InvokeDir = Get-Location
}

$DockerComposeFile = Join-Path $InvokeDir "docker-compose.yml"
$StartServicesScript = Join-Path (Split-Path $MyInvocation.MyCommand.Path) "start-agentic-services.ps1"

# ============================================================================
# Helper Functions
# ============================================================================

function Write-Header {
    param([string]$Message)
    Write-Host ""
    Write-Host "=" * 70
    Write-Host $Message
    Write-Host "=" * 70
    Write-Host ""
}

function Write-Status {
    param([string]$Message, [string]$Status = "INFO")
    $color = @{
        "INFO"    = "Cyan"
        "SUCCESS" = "Green"
        "WARNING" = "Yellow"
        "ERROR"   = "Red"
    }[$Status]
    Write-Host "[$(Get-Date -Format 'HH:mm:ss')] [$Status] $Message" -ForegroundColor $color
}

function Test-Admin {
    $currentPrincipal = [Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
    return $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Get-DockerType {
    # Detect if Docker Desktop or Docker in WSL2
    try {
        $dockerInfo = & docker info 2>$null
        if ($dockerInfo -match "Docker Desktop") {
            return "Docker Desktop"
        } elseif ($dockerInfo -match "Server Version") {
            # Check if running in WSL
            if (Test-Path "/proc/version" -PathType Leaf) {
                return "WSL2"
            }
            return "Docker Engine"
        }
    } catch {
        return $null
    }
}

function Get-DockerDesktopInstallPath {
    # Common Docker Desktop installation paths
    $possiblePaths = @(
        "C:\Program Files\Docker\Docker\Docker Desktop.exe",
        "C:\Program Files (x86)\Docker\Docker\Docker Desktop.exe"
    )
    
    foreach ($path in $possiblePaths) {
        if (Test-Path $path) {
            return $path
        }
    }
    
    return $null
}

function Enable-DockerDesktopAutoStart {
    Write-Status "Configuring Docker Desktop auto-start..." "INFO"
    
    $dockerPath = Get-DockerDesktopInstallPath
    if (-not $dockerPath) {
        Write-Status "Docker Desktop not found in standard location" "WARNING"
        Write-Host "Please manually enable auto-start:"
        Write-Host "  1. Open Docker Desktop"
        Write-Host "  2. Go to Settings > General"
        Write-Host "  3. Check 'Start Docker Desktop when you log in'"
        return $false
    }
    
    # Check if Docker Desktop auto-start is already enabled via registry
    $regPath = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
    $regEntry = "Docker Desktop"
    
    try {
        if (-not (Get-ItemProperty -Path $regPath -Name $regEntry -ErrorAction SilentlyContinue)) {
            # Add registry entry for Docker Desktop auto-start
            New-ItemProperty -Path $regPath -Name $regEntry -Value $dockerPath -Force | Out-Null
            Write-Status "Docker Desktop auto-start enabled" "SUCCESS"
            return $true
        } else {
            Write-Status "Docker Desktop auto-start already enabled" "INFO"
            return $true
        }
    } catch {
        Write-Status "Failed to enable Docker Desktop auto-start: $_" "ERROR"
        return $false
    }
}

function Create-StartServicesScript {
    Write-Status "Creating services startup script..." "INFO"
    
    $scriptDir = Split-Path $MyInvocation.MyCommand.Path
    
    $scriptContent = @"
# ============================================================================
# Agentic Brain - Docker Compose Services Startup Helper
# ============================================================================
# This script is called by Windows Task Scheduler to start agentic-brain
# services after Docker Desktop starts.
# ============================================================================

param(
    [string]`$ComposeDir = "$InvokeDir"
)

`$ErrorActionPreference = "Stop"
`$MaxRetries = 30
`$RetryDelay = 2  # seconds

function Write-Log {
    param([string]`$Message)
    `$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    `$logEntry = "[\`$timestamp] \`$Message"
    Write-Host `$logEntry
    
    # Also log to a file
    `$logFile = Join-Path `$env:APPDATA "AgenticBrain\docker-startup.log"
    `$logDir = Split-Path `$logFile -Parent
    if (-not (Test-Path `$logDir)) {
        New-Item -ItemType Directory -Path `$logDir -Force | Out-Null
    }
    Add-Content -Path `$logFile -Value `$logEntry
}

Write-Log "================ Agentic Brain Startup ================"
Write-Log "Working directory: \`$ComposeDir"
Write-Log "Time: \$(Get-Date)"

# Check if docker-compose.yml exists
`$composeFile = Join-Path `$ComposeDir "docker-compose.yml"
if (-not (Test-Path `$composeFile)) {
    Write-Log "ERROR: docker-compose.yml not found at \`$composeFile"
    exit 1
}

# Wait for Docker to be ready
Write-Log "Waiting for Docker daemon to be ready..."
`$retries = 0
while (`$retries -lt `$MaxRetries) {
    try {
        `$dockerInfo = & docker info 2>null
        if (`$?) {
            Write-Log "Docker daemon is ready"
            break
        }
    } catch {}
    
    `$retries++
    if (`$retries -lt `$MaxRetries) {
        Start-Sleep -Seconds `$RetryDelay
    }
}

if (`$retries -ge `$MaxRetries) {
    Write-Log "ERROR: Docker daemon did not become ready after \$([int](`$MaxRetries * `$RetryDelay)) seconds"
    exit 1
}

# Check if services are already running
Write-Log "Checking for running containers..."
`$runningContainers = & docker ps --filter "name=agentic-brain" -q 2>null
if (`$runningContainers) {
    Write-Log "Services already running: \`$runningContainers"
    exit 0
}

# Start services
Write-Log "Starting agentic-brain services..."
Set-Location `$ComposeDir

try {
    & docker compose up -d
    if (`$?) {
        Write-Log "SUCCESS: Services started successfully"
        Write-Log "Waiting 30 seconds for services to stabilize..."
        Start-Sleep -Seconds 30
        
        Write-Log "Service status:"
        & docker compose ps
        
        exit 0
    } else {
        Write-Log "ERROR: Failed to start services"
        exit 1
    }
} catch {
    Write-Log "ERROR: Exception while starting services: `$_"
    exit 1
}
"@
    
    $scriptPath = Join-Path $scriptDir "start-agentic-services.ps1"
    $scriptContent | Out-File -FilePath $scriptPath -Encoding UTF8 -Force
    Write-Status "Created startup script: $scriptPath" "SUCCESS"
    
    return $scriptPath
}

function Create-TaskSchedulerTask {
    param(
        [string]$TaskName,
        [string]$Description,
        [string]$ScriptPath,
        [string]$Trigger  # "Login" or "SystemStart"
    )
    
    Write-Status "Creating Task Scheduler task: $TaskName" "INFO"
    
    # Check if task already exists
    $existingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($existingTask) {
        Write-Status "Task already exists: $TaskName" "WARNING"
        Write-Status "Removing existing task..." "INFO"
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    }
    
    # Create task action
    $action = New-ScheduledTaskAction `
        -Execute "powershell.exe" `
        -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$ScriptPath`""
    
    # Create task trigger
    if ($Trigger -eq "Login") {
        $trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
    } elseif ($Trigger -eq "SystemStart") {
        $trigger = New-ScheduledTaskTrigger -AtStartup
    } else {
        Write-Status "Invalid trigger type: $Trigger" "ERROR"
        return $false
    }
    
    # Create task settings
    $settings = New-ScheduledTaskSettingsSet `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries `
        -StartWhenAvailable `
        -RunOnlyIfNetworkAvailable
    
    # Create task principal (run as current user, not SYSTEM)
    $principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -RunLevel Highest
    
    try {
        Register-ScheduledTask `
            -TaskName $TaskName `
            -Action $action `
            -Trigger $trigger `
            -Settings $settings `
            -Principal $principal `
            -Description $Description `
            -Force | Out-Null
        
        Write-Status "Task created successfully: $TaskName" "SUCCESS"
        return $true
    } catch {
        Write-Status "Failed to create task: $_" "ERROR"
        return $false
    }
}

function Remove-AutoStart {
    Write-Header "Removing Agentic Brain Auto-Start"
    
    # Remove Docker Desktop auto-start registry entry
    $regPath = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
    $regEntry = "Docker Desktop"
    
    try {
        if (Get-ItemProperty -Path $regPath -Name $regEntry -ErrorAction SilentlyContinue) {
            Remove-ItemProperty -Path $regPath -Name $regEntry
            Write-Status "Removed Docker Desktop auto-start" "SUCCESS"
        }
    } catch {
        Write-Status "Could not remove Docker Desktop auto-start: $_" "WARNING"
    }
    
    # Remove scheduled tasks
    $tasks = @($TaskNameDockerStart, $TaskNameServices)
    foreach ($taskName in $tasks) {
        $task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
        if ($task) {
            try {
                Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
                Write-Status "Removed scheduled task: $taskName" "SUCCESS"
            } catch {
                Write-Status "Failed to remove task $taskName : $_" "ERROR"
            }
        } else {
            Write-Status "Task not found: $taskName" "INFO"
        }
    }
    
    Write-Header "Auto-Start Removal Complete"
}

function Install-AutoStart {
    if (-not (Test-Admin)) {
        Write-Header "ERROR: Administrator Rights Required"
        Write-Host "This script must be run as Administrator to set up auto-start."
        Write-Host ""
        Write-Host "Please run PowerShell as Administrator and try again."
        exit 1
    }
    
    Write-Header "$ScriptName Installer"
    
    # Check prerequisites
    Write-Status "Checking prerequisites..." "INFO"
    
    # Check if docker is installed
    try {
        $dockerVersion = & docker --version 2>$null
        Write-Status "Docker found: $dockerVersion" "SUCCESS"
    } catch {
        Write-Host ""
        Write-Status "Docker not found!" "ERROR"
        Write-Host ""
        Write-Host "Please install Docker Desktop first:"
        Write-Host "  1. Download from: https://www.docker.com/products/docker-desktop"
        Write-Host "  2. Install and restart your computer"
        Write-Host "  3. Run this script again"
        Write-Host ""
        exit 1
    }
    
    # Check if docker-compose.yml exists
    if (-not (Test-Path $DockerComposeFile)) {
        Write-Status "docker-compose.yml not found: $DockerComposeFile" "ERROR"
        Write-Host "Please run this script from the agentic-brain directory"
        exit 1
    }
    
    Write-Status "docker-compose.yml found: $DockerComposeFile" "SUCCESS"
    
    # Detect Docker type
    $dockerType = Get-DockerType
    Write-Status "Docker type detected: $dockerType" "INFO"
    
    Write-Host ""
    Write-Host "Setting up auto-start for agentic-brain services..."
    Write-Host ""
    
    # Enable Docker Desktop auto-start (if applicable)
    if ($dockerType -like "*Docker Desktop*") {
        Enable-DockerDesktopAutoStart | Out-Null
    }
    
    # Create startup script
    $startScript = Create-StartServicesScript
    
    # Create scheduled task for services
    $taskDesc = "Start agentic-brain services (Neo4j, Redis, Redpanda) after Docker is ready"
    $created = Create-TaskSchedulerTask `
        -TaskName $TaskNameServices `
        -Description $taskDesc `
        -ScriptPath $startScript `
        -Trigger "Login"
    
    if (-not $created) {
        Write-Status "Failed to create scheduled task" "ERROR"
        exit 1
    }
    
    # Also create a startup trigger task (runs immediately at system startup)
    $taskDesc2 = "Ensure agentic-brain services are running at system startup"
    Create-TaskSchedulerTask `
        -TaskName "$($TaskNameServices)-Startup" `
        -Description $taskDesc2 `
        -ScriptPath $startScript `
        -Trigger "SystemStart" | Out-Null
    
    Write-Header "Installation Complete!"
    
    Write-Host "Your agentic-brain services are now set to auto-start on login."
    Write-Host ""
    Write-Host "What happens:"
    Write-Host "  1. Docker Desktop starts automatically on login"
    Write-Host "  2. After Docker is ready, scheduled task starts your services:"
    Write-Host "     - Neo4j (bolt://localhost:7687)"
    Write-Host "     - Redis (localhost:6379)"
    Write-Host "     - Redpanda (localhost:9092)"
    Write-Host "     - Agentic Brain API (http://localhost:8000)"
    Write-Host ""
    Write-Host "To verify setup:"
    Write-Host "  - Check Task Scheduler: taskmgr or taskschd.msc"
    Write-Host "  - Run: docker compose ps"
    Write-Host "  - Check logs: Get-Content `$env:APPDATA\AgenticBrain\docker-startup.log"
    Write-Host ""
    Write-Host "To remove auto-start:"
    Write-Host "  .\install-autostart-windows.ps1 -Uninstall"
    Write-Host ""
}

# ============================================================================
# Main Execution
# ============================================================================

if ($Uninstall) {
    Remove-AutoStart
} else {
    Install-AutoStart
}
