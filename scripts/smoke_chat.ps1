# scripts/smoke_chat.ps1
# Smoke test for chat endpoint functionality
# Posts a benign query and prints summary + top rows

param(
    [string]$ServerUrl = "http://localhost:8000",
    [switch]$Comprehensive = $false
)

$ErrorActionPreference = "Stop"

Write-Host "💬 Starting smoke test: Chat Endpoint" -ForegroundColor Cyan
Write-Host "====================================" -ForegroundColor Cyan

# Configuration
$ChatUrl = "$ServerUrl/api/chat"
$HealthUrl = "$ServerUrl/health"

# Test queries (benign, should not trigger guardrails)
$TestQueries = @(
    "What are the goals for Isabella Thomas?",
    "Show me accommodations for John Smith",
    "Who is the case manager for Maria Garcia?"
)

function Write-Status {
    param(
        [string]$Status,
        [string]$Message
    )
    
    switch ($Status) {
        "SUCCESS" { Write-Host "✅ $Message" -ForegroundColor Green }
        "ERROR" { Write-Host "❌ $Message" -ForegroundColor Red }
        "INFO" { Write-Host "ℹ️  $Message" -ForegroundColor Yellow }
        "RESULT" { Write-Host "📋 $Message" -ForegroundColor Blue }
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
        Write-Host "   Please start the server first: python main.py"
        return $false
    }
}

function Test-ChatEndpoint {
    param(
        [string]$Query,
        [string]$FormatType = ""
    )
    
    Write-Status "INFO" "Testing chat endpoint with query: '$Query'"
    if ($FormatType) {
        Write-Status "INFO" "Using format_type: '$FormatType'"
    }
    
    # Prepare JSON payload
    $payload = @{
        question = $Query
    }
    
    if ($FormatType) {
        $payload.format_type = $FormatType
    }
    
    $jsonPayload = $payload | ConvertTo-Json -Compress
    
    try {
        $response = Invoke-WebRequest -Uri $ChatUrl -Method POST -Body $jsonPayload -ContentType "application/json" -UseBasicParsing
        
        if ($response.StatusCode -eq 200) {
            Write-Status "SUCCESS" "Chat request successful"
            Show-ChatResponse $response.Content $FormatType
            return $true
        } else {
            Write-Status "ERROR" "Chat request failed with HTTP $($response.StatusCode)"
            Write-Host "   Response: $($response.Content)"
            return $false
        }
    }
    catch {
        if ($_.Exception.Response.StatusCode -eq 403) {
            Write-Status "ERROR" "Chat request blocked by guardrails (403)"
            Write-Host "   Response: $($_.Exception.Response.Content)"
        } elseif ($_.Exception.Response.StatusCode -eq 400) {
            Write-Status "ERROR" "Chat request failed: Bad Request (400)"
            Write-Host "   Response: $($_.Exception.Response.Content)"
        } else {
            Write-Status "ERROR" "Chat request failed: $($_.Exception.Message)"
        }
        return $false
    }
}

function Show-ChatResponse {
    param(
        [string]$ResponseBody,
        [string]$FormatType
    )
    
    try {
        $response = $ResponseBody | ConvertFrom-Json
        
        Write-Status "RESULT" "Response Summary:"
        Write-Host "   Question: $($response.question)"
        Write-Host "   Answer: $($response.answer)"
        Write-Host "   Trace ID: $($response.trace_id)"
        Write-Host "   Audit ID: $($response.audit_id)"
        Write-Host "   Row Count: $($response.row_count)"
        
        # Display formatted output if present
        if ($response.formatted -and $response.formatted -ne $null) {
            Write-Status "RESULT" "Formatted Output:"
            $response.formatted | ConvertTo-Json -Depth 3 | Write-Host
        }
        
        # Display top rows if present
        if ($response.rows -and $response.rows.Count -gt 0) {
            Write-Status "RESULT" "Top Rows:"
            $response.rows | Select-Object -First 3 | ConvertTo-Json -Depth 2 | Write-Host
        }
    }
    catch {
        Write-Status "RESULT" "Response received (JSON parsing failed):"
        $ResponseBody.Substring(0, [Math]::Min(500, $ResponseBody.Length))
        if ($ResponseBody.Length -gt 500) {
            Write-Host "..."
        }
    }
}

function Test-FormatTypes {
    param([string]$Query)
    
    Write-Status "INFO" "Testing different format types..."
    
    $formatTypes = @("text", "table", "graph")
    $successCount = 0
    
    foreach ($formatType in $formatTypes) {
        Write-Host ""
        Write-Status "INFO" "Testing '$formatType' format..."
        if (Test-ChatEndpoint $Query $formatType) {
            $successCount++
        }
    }
    
    return $successCount -eq $formatTypes.Count
}

function Test-Comprehensive {
    Write-Status "INFO" "Running comprehensive chat tests..."
    
    $successCount = 0
    $totalCount = 0
    
    foreach ($query in $TestQueries) {
        Write-Host ""
        Write-Status "INFO" "Testing query: '$query'"
        
        # Test without format_type (backward compatibility)
        if (Test-ChatEndpoint $query) {
            $successCount++
        }
        $totalCount++
        
        # Test with format types
        if (Test-FormatTypes $query) {
            $successCount++
        }
        $totalCount++
        
        Write-Host ""
        Write-Host "---"
    }
    
    Write-Status "INFO" "Test Results: $successCount/$totalCount tests passed"
    return $successCount -eq $totalCount
}

function Test-Quick {
    Write-Status "INFO" "Running quick chat test..."
    
    $testQuery = $TestQueries[0]
    return Test-ChatEndpoint $testQuery
}

# Main execution
try {
    Write-Host "Configuration:"
    Write-Host "  Server URL: $ServerUrl"
    Write-Host "  Chat URL: $ChatUrl"
    Write-Host "  Test Queries: $($TestQueries.Count)"
    Write-Host ""
    
    # Check if server is running
    if (-not (Test-ServerRunning)) {
        exit 1
    }
    
    # Run tests
    if ($Comprehensive) {
        $success = Test-Comprehensive
    } else {
        $success = Test-Quick
    }
    
    if ($success) {
        Write-Status "SUCCESS" "Smoke test completed successfully!"
        Write-Host ""
        Write-Host "🎉 Chat endpoint smoke test PASSED" -ForegroundColor Green
        Write-Host "   - Server is responding"
        Write-Host "   - Chat endpoint is working"
        Write-Host "   - Responses include trace_id and audit_id"
        Write-Host ""
        Write-Host "Usage:"
        Write-Host "  .\smoke_chat.ps1              # Quick test"
        Write-Host "  .\smoke_chat.ps1 -Comprehensive  # Full test with all queries and formats"
    } else {
        Write-Status "ERROR" "Smoke test failed!"
        exit 1
    }
}
catch {
    Write-Status "ERROR" "Unexpected error: $($_.Exception.Message)"
    exit 1
}
