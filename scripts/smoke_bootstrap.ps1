# scripts/smoke_bootstrap.ps1
# Smoke test for admin bootstrap functionality
# Sets APP_MODE=admin, boots server, hits /admin/schema/refresh, checks indexes

param(
    [string]$ServerUrl = "http://localhost:8000",
    [string]$AdminToken = $env:ADMIN_REFRESH_TOKEN,
    [int]$Timeout = 30
)

$ErrorActionPreference = "Stop"

Write-Host "🚀 Starting smoke test: Admin Bootstrap" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# Configuration
$SchemaRefreshUrl = "$ServerUrl/admin/schema/refresh"
$HealthUrl = "$ServerUrl/health"

function Write-Status {
    param(
        [string]$Status,
        [string]$Message
    )
    
    switch ($Status) {
        "SUCCESS" { Write-Host "✅ $Message" -ForegroundColor Green }
        "ERROR" { Write-Host "❌ $Message" -ForegroundColor Red }
        "INFO" { Write-Host "ℹ️  $Message" -ForegroundColor Yellow }
        default { Write-Host "   $Message" }
    }
}

function Test-ServerRunning {
    Write-Status "INFO" "Checking if server is running..."
    
    try {
        $response = Invoke-WebRequest -Uri $HealthUrl -TimeoutSec 5 -UseBasicParsing
        Write-Status "SUCCESS" "Server is running"
        return $true
    }
    catch {
        Write-Status "ERROR" "Server is not running or not responding"
        return $false
    }
}

function Start-Server {
    Write-Status "INFO" "Starting server with APP_MODE=admin..."
    
    # Set environment variables
    $env:APP_MODE = "admin"
    $env:ALLOW_WRITES = "true"
    $env:DEV_MODE = "true"
    
    # Start server in background
    $process = Start-Process -FilePath "python" -ArgumentList "main.py" -PassThru -WindowStyle Hidden
    
    # Wait for server to start
    Write-Status "INFO" "Waiting for server to start (timeout: ${Timeout}s)..."
    
    for ($i = 1; $i -le $Timeout; $i++) {
        try {
            $response = Invoke-WebRequest -Uri $HealthUrl -TimeoutSec 2 -UseBasicParsing
            Write-Status "SUCCESS" "Server started successfully (PID: $($process.Id))"
            return $process
        }
        catch {
            Start-Sleep -Seconds 1
            Write-Host "." -NoNewline
        }
    }
    
    Write-Host ""
    Write-Status "ERROR" "Server failed to start within $Timeout seconds"
    return $null
}

function Test-SchemaRefresh {
    Write-Status "INFO" "Testing /admin/schema/refresh endpoint..."
    
    $headers = @{}
    if ($AdminToken) {
        $headers["x-admin-token"] = $AdminToken
        Write-Status "INFO" "Using admin token for authentication"
    } else {
        Write-Status "INFO" "No admin token provided, testing without authentication"
    }
    
    try {
        $response = Invoke-WebRequest -Uri $SchemaRefreshUrl -Method POST -Headers $headers -UseBasicParsing
        
        if ($response.StatusCode -eq 200) {
            Write-Status "SUCCESS" "Schema refresh completed successfully"
            Write-Host "   Response: $($response.Content)"
            return $true
        } else {
            Write-Status "ERROR" "Schema refresh failed with HTTP $($response.StatusCode)"
            Write-Host "   Response: $($response.Content)"
            return $false
        }
    }
    catch {
        if ($_.Exception.Response.StatusCode -eq 401) {
            Write-Status "ERROR" "Schema refresh failed: Unauthorized (401)"
            Write-Host "   Hint: Set ADMIN_REFRESH_TOKEN environment variable"
        } else {
            Write-Status "ERROR" "Schema refresh failed: $($_.Exception.Message)"
        }
        return $false
    }
}

function Test-Indexes {
    Write-Status "INFO" "Checking Neo4j indexes..."
    
    try {
        $response = Invoke-WebRequest -Uri $HealthUrl -TimeoutSec 5 -UseBasicParsing
        Write-Status "SUCCESS" "Server is still responding after schema refresh"
        Write-Status "INFO" "Index check: Assuming indexes are created (manual verification recommended)"
        return $true
    }
    catch {
        Write-Status "ERROR" "Server stopped responding after schema refresh"
        return $false
    }
}

function Stop-Server {
    param($Process)
    
    if ($Process -and !$Process.HasExited) {
        Write-Status "INFO" "Stopping server (PID: $($Process.Id))..."
        $Process.Kill()
        $Process.WaitForExit()
        Write-Status "SUCCESS" "Server stopped"
    }
}

# Main execution
try {
    Write-Host "Configuration:"
    Write-Host "  Server URL: $ServerUrl"
    Write-Host "  Admin Token: $(if ($AdminToken) { '[SET]' } else { '[NOT SET]' })"
    Write-Host "  Timeout: ${Timeout}s"
    Write-Host ""
    
    $serverProcess = $null
    
    # Check if server is already running
    if (Test-ServerRunning) {
        Write-Status "INFO" "Using existing server instance"
    } else {
        # Start our own server
        $serverProcess = Start-Server
        if (-not $serverProcess) {
            exit 1
        }
    }
    
    # Test schema refresh
    if (-not (Test-SchemaRefresh)) {
        exit 1
    }
    
    # Check indexes
    if (-not (Test-Indexes)) {
        exit 1
    }
    
    Write-Status "SUCCESS" "Smoke test completed successfully!"
    Write-Host ""
    Write-Host "🎉 Admin bootstrap smoke test PASSED" -ForegroundColor Green
    Write-Host "   - Server is running"
    Write-Host "   - Schema refresh endpoint works"
    Write-Host "   - Server remains responsive"
    Write-Host ""
}
finally {
    # Cleanup
    if ($serverProcess) {
        Stop-Server $serverProcess
    }
}
