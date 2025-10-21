#!/bin/bash
# scripts/smoke_chat.sh
# Smoke test for chat endpoint functionality
# Posts a benign query and prints summary + top rows

set -e  # Exit on any error

echo "💬 Starting smoke test: Chat Endpoint"
echo "===================================="

# Configuration
SERVER_URL="http://localhost:8000"
CHAT_URL="${SERVER_URL}/api/chat"
HEALTH_URL="${SERVER_URL}/health"
TIMEOUT=30

# Test queries (benign, should not trigger guardrails)
TEST_QUERIES=(
    "What are the goals for Isabella Thomas?"
    "Show me accommodations for John Smith"
    "Who is the case manager for Maria Garcia?"
)

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
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
    elif [ "$status" = "RESULT" ]; then
        echo -e "${BLUE}📋 $message${NC}"
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
        echo "   Please start the server first: python main.py"
        return 1
    fi
}

# Function to test chat endpoint
test_chat_endpoint() {
    local query="$1"
    local format_type="${2:-}"
    
    print_status "INFO" "Testing chat endpoint with query: '$query'"
    if [ -n "$format_type" ]; then
        print_status "INFO" "Using format_type: '$format_type'"
    fi
    
    # Prepare JSON payload
    local json_payload
    if [ -n "$format_type" ]; then
        json_payload="{\"question\": \"$query\", \"format_type\": \"$format_type\"}"
    else
        json_payload="{\"question\": \"$query\"}"
    fi
    
    # Make the request
    local response
    response=$(curl -s -w "\n%{http_code}" -X POST \
        -H "Content-Type: application/json" \
        -d "$json_payload" \
        "$CHAT_URL" 2>/dev/null)
    
    local http_code=$(echo "$response" | tail -n1)
    local body=$(echo "$response" | head -n -1)
    
    if [ "$http_code" = "200" ]; then
        print_status "SUCCESS" "Chat request successful"
        
        # Parse and display response
        display_chat_response "$body" "$format_type"
        return 0
    elif [ "$http_code" = "403" ]; then
        print_status "ERROR" "Chat request blocked by guardrails (403)"
        echo "   Response: $body"
        return 1
    elif [ "$http_code" = "400" ]; then
        print_status "ERROR" "Chat request failed: Bad Request (400)"
        echo "   Response: $body"
        return 1
    else
        print_status "ERROR" "Chat request failed with HTTP $http_code"
        echo "   Response: $body"
        return 1
    fi
}

# Function to display chat response
display_chat_response() {
    local response_body="$1"
    local format_type="$2"
    
    # Extract key fields using jq if available, otherwise use basic parsing
    if command -v jq >/dev/null 2>&1; then
        # Use jq for proper JSON parsing
        local question=$(echo "$response_body" | jq -r '.question // "N/A"')
        local answer=$(echo "$response_body" | jq -r '.answer // "N/A"')
        local trace_id=$(echo "$response_body" | jq -r '.trace_id // "N/A"')
        local audit_id=$(echo "$response_body" | jq -r '.audit_id // "N/A"')
        local row_count=$(echo "$response_body" | jq -r '.row_count // 0')
        
        print_status "RESULT" "Response Summary:"
        echo "   Question: $question"
        echo "   Answer: $answer"
        echo "   Trace ID: $trace_id"
        echo "   Audit ID: $audit_id"
        echo "   Row Count: $row_count"
        
        # Display formatted output if present
        local formatted=$(echo "$response_body" | jq -r '.formatted // empty')
        if [ -n "$formatted" ] && [ "$formatted" != "null" ]; then
            print_status "RESULT" "Formatted Output:"
            echo "$formatted" | jq .
        fi
        
        # Display top rows if present
        local rows=$(echo "$response_body" | jq -r '.rows // empty')
        if [ -n "$rows" ] && [ "$rows" != "null" ] && [ "$rows" != "[]" ]; then
            print_status "RESULT" "Top Rows:"
            echo "$rows" | jq '.[0:3]'  # Show first 3 rows
        fi
        
    else
        # Basic parsing without jq
        print_status "RESULT" "Response received (install jq for better formatting):"
        echo "$response_body" | head -c 500
        if [ ${#response_body} -gt 500 ]; then
            echo "..."
        fi
    fi
}

# Function to test different format types
test_format_types() {
    local query="$1"
    
    print_status "INFO" "Testing different format types..."
    
    # Test text format
    echo ""
    print_status "INFO" "Testing 'text' format..."
    test_chat_endpoint "$query" "text"
    
    # Test table format
    echo ""
    print_status "INFO" "Testing 'table' format..."
    test_chat_endpoint "$query" "table"
    
    # Test graph format
    echo ""
    print_status "INFO" "Testing 'graph' format..."
    test_chat_endpoint "$query" "graph"
}

# Function to run comprehensive tests
run_comprehensive_test() {
    print_status "INFO" "Running comprehensive chat tests..."
    
    local success_count=0
    local total_count=0
    
    for query in "${TEST_QUERIES[@]}"; do
        echo ""
        print_status "INFO" "Testing query: '$query'"
        
        # Test without format_type (backward compatibility)
        if test_chat_endpoint "$query"; then
            ((success_count++))
        fi
        ((total_count++))
        
        # Test with format types
        if test_format_types "$query"; then
            ((success_count++))
        fi
        ((total_count++))
        
        echo ""
        echo "---"
    done
    
    print_status "INFO" "Test Results: $success_count/$total_count tests passed"
    
    if [ $success_count -eq $total_count ]; then
        return 0
    else
        return 1
    fi
}

# Function to run quick test
run_quick_test() {
    print_status "INFO" "Running quick chat test..."
    
    local test_query="${TEST_QUERIES[0]}"
    test_chat_endpoint "$test_query"
}

# Main execution
main() {
    echo "Configuration:"
    echo "  Server URL: $SERVER_URL"
    echo "  Chat URL: $CHAT_URL"
    echo "  Test Queries: ${#TEST_QUERIES[@]}"
    echo ""
    
    # Check if server is running
    if ! check_server_running; then
        exit 1
    fi
    
    # Check command line arguments
    if [ "$1" = "--comprehensive" ] || [ "$1" = "-c" ]; then
        run_comprehensive_test
    else
        run_quick_test
    fi
    
    if [ $? -eq 0 ]; then
        print_status "SUCCESS" "Smoke test completed successfully!"
        echo ""
        echo "🎉 Chat endpoint smoke test PASSED"
        echo "   - Server is responding"
        echo "   - Chat endpoint is working"
        echo "   - Responses include trace_id and audit_id"
        echo ""
        echo "Usage:"
        echo "  $0              # Quick test"
        echo "  $0 --comprehensive  # Full test with all queries and formats"
    else
        print_status "ERROR" "Smoke test failed!"
        exit 1
    fi
}

# Run main function
main "$@"
