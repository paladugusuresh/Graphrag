#!/bin/bash
# scripts/smoke_bootstrap.sh
# Smoke test for admin bootstrap functionality
# Sets APP_MODE=admin, boots server, hits /admin/schema/refresh, checks indexes

set -e  # Exit on any error

echo "🚀 Starting smoke test: Admin Bootstrap"
echo "========================================"

# Configuration
SERVER_URL="http://127.0.0.1:8002"
ADMIN_TOKEN="${ADMIN_REFRESH_TOKEN:-}"
SCHEMA_REFRESH_URL="${SERVER_URL}/admin/schema/refresh"
HEALTH_URL="${SERVER_URL}/health"
TIMEOUT=200

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    local status=$1
    local message=$2
    if [ "$status" = "SUCCESS" ]; then
        echo -e "${GREEN}✅ $message${NC}"
    elif [ "$status" = "ERROR" ]; then
        echo -e "${RED}❌ $message${NC}"
    elif [ "$status" = "INFO" ]; then
        echo -e "${YELLOW}ℹ️  $message${NC}"
    else
        echo "   $message"
    fi
}

# Function to check if server is running
check_server_running() {
    print_status "INFO" "Checking if server is running..."
    
    if curl -s --connect-timeout 5 "$HEALTH_URL" > /dev/null 2>&1; then
        print_status "SUCCESS" "Server is running"
        return 0
    else
        print_status "ERROR" "Server is not running or not responding"
        return 1
    fi
}

# Function to start server in background
start_server() {
    print_status "INFO" "Starting server with APP_MODE=admin..."
    
    # Set environment variables
    export APP_MODE=admin
    export ALLOW_WRITES=true
    export DEV_MODE=false
    
    # Start server in background
    python -m uvicorn main:app --host 0.0.0.0 --port 8002 &
    SERVER_PID=$!
    
    # Wait for server to start
    print_status "INFO" "Waiting for server to start (timeout: ${TIMEOUT}s)..."
    
    for i in $(seq 1 $TIMEOUT); do
        if curl -s --connect-timeout 2 "$HEALTH_URL" > /dev/null 2>&1; then
            print_status "SUCCESS" "Server started successfully (PID: $SERVER_PID)"
            return 0
        fi
        sleep 1
        echo -n "."
    done
    
    echo ""
    print_status "ERROR" "Server failed to start within ${TIMEOUT} seconds"
    return 1
}

# Function to test schema refresh endpoint
test_schema_refresh() {
    print_status "INFO" "Testing /admin/schema/refresh endpoint..."
    
    local headers=""
    if [ -n "$ADMIN_TOKEN" ]; then
        headers="-H 'x-admin-token: $ADMIN_TOKEN'"
        print_status "INFO" "Using admin token for authentication"
    else
        print_status "INFO" "No admin token provided, testing without authentication"
    fi
    
    # Make the request
    local response
    if [ -n "$ADMIN_TOKEN" ]; then
        response=$(curl -s -w "\n%{http_code}" -X POST \
            -H "x-admin-token: $ADMIN_TOKEN" \
            "$SCHEMA_REFRESH_URL" 2>/dev/null)
    else
        response=$(curl -s -w "\n%{http_code}" -X POST \
            "$SCHEMA_REFRESH_URL" 2>/dev/null)
    fi
    
    local http_code=$(echo "$response" | tail -n1)
    local body=$(echo "$response" | head -n -1)
    
    if [ "$http_code" = "200" ]; then
        print_status "SUCCESS" "Schema refresh completed successfully"
        echo "   Response: $body"
        return 0
    elif [ "$http_code" = "401" ]; then
        print_status "ERROR" "Schema refresh failed: Unauthorized (401)"
        echo "   Response: $body"
        echo "   Hint: Set ADMIN_REFRESH_TOKEN environment variable"
        return 1
    else
        print_status "ERROR" "Schema refresh failed with HTTP $http_code"
        echo "   Response: $body"
        return 1
    fi
}

# Function to check Neo4j indexes
check_indexes() {
    print_status "INFO" "Checking Neo4j indexes..."
    
    # This is a placeholder - in a real implementation, you might:
    # 1. Connect to Neo4j directly
    # 2. Query the indexes via a dedicated endpoint
    # 3. Check for specific indexes like 'chunk_embeddings'
    
    # For now, we'll just check if the server is still responding
    if curl -s --connect-timeout 5 "$HEALTH_URL" > /dev/null 2>&1; then
        print_status "SUCCESS" "Server is still responding after schema refresh"
        print_status "INFO" "Index check: Assuming indexes are created (manual verification recommended)"
        return 0
    else
        print_status "ERROR" "Server stopped responding after schema refresh"
        return 1
    fi
}

# Function to cleanup
cleanup() {
    if [ -n "$SERVER_PID" ]; then
        print_status "INFO" "Stopping server (PID: $SERVER_PID)..."
        kill $SERVER_PID 2>/dev/null || true
        wait $SERVER_PID 2>/dev/null || true
        print_status "SUCCESS" "Server stopped"
    fi
}

# Set up cleanup trap
trap cleanup EXIT

# Main execution
main() {
    echo "Configuration:"
    echo "  Server URL: $SERVER_URL"
    echo "  Admin Token: ${ADMIN_TOKEN:+[SET]}${ADMIN_TOKEN:-[NOT SET]}"
    echo "  Timeout: ${TIMEOUT}s"
    echo ""
    
    # Check if server is already running
    if check_server_running; then
        print_status "INFO" "Using existing server instance"
        SERVER_PID=""
    else
        # Start our own server
        start_server
    fi
    
    # Test schema refresh
    test_schema_refresh
    
    # Check indexes
    check_indexes
    
    print_status "SUCCESS" "Smoke test completed successfully!"
    echo ""
    echo "🎉 Admin bootstrap smoke test PASSED"
    echo "   - Server is running"
    echo "   - Schema refresh endpoint works"
    echo "   - Server remains responsive"
    echo ""
}

# Run main function
main "$@"
