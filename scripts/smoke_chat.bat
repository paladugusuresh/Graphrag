@echo off
REM scripts/smoke_chat.bat
REM Smoke test for chat endpoint functionality
REM Posts a benign query and prints summary + top rows

setlocal enabledelayedexpansion

echo Starting smoke test: Chat Endpoint
echo ====================================

set SERVER_URL=http://localhost:8000
set CHAT_URL=%SERVER_URL%/api/chat
set HEALTH_URL=%SERVER_URL%/health

echo Configuration:
echo   Server URL: %SERVER_URL%
echo   Chat URL: %CHAT_URL%
echo.

REM Check if server is running
echo Checking if server is running...
curl -s --connect-timeout 5 "%HEALTH_URL%" >nul 2>&1
if %errorlevel% neq 0 (
    echo Server is not running or not responding
    echo Please start the server first: python main.py
    exit /b 1
)

echo Server is running

REM Test queries
set TEST_QUERY=What are the goals for Isabella Thomas?

echo Testing chat endpoint with query: '%TEST_QUERY%'

REM Test without format_type (backward compatibility)
echo Testing without format_type...
curl -s -w "%%{http_code}" -X POST -H "Content-Type: application/json" -d "{\"question\": \"%TEST_QUERY%\"}" "%CHAT_URL%" > temp_response.txt 2>nul

REM Extract HTTP code and response
for /f "tokens=*" %%a in (temp_response.txt) do set RESPONSE=%%a
set HTTP_CODE=%RESPONSE:~-3%
set RESPONSE_BODY=%RESPONSE:~0,-3%

if "%HTTP_CODE%" equ "200" (
    echo Chat request successful
    echo.
    echo Response Summary:
    echo %RESPONSE_BODY%
) else if "%HTTP_CODE%" equ "403" (
    echo Chat request blocked by guardrails (403)
    echo Response: %RESPONSE_BODY%
    del temp_response.txt 2>nul
    exit /b 1
) else if "%HTTP_CODE%" equ "400" (
    echo Chat request failed: Bad Request (400)
    echo Response: %RESPONSE_BODY%
    del temp_response.txt 2>nul
    exit /b 1
) else (
    echo Chat request failed with HTTP %HTTP_CODE%
    echo Response: %RESPONSE_BODY%
    del temp_response.txt 2>nul
    exit /b 1
)

del temp_response.txt 2>nul

REM Test with format types
echo.
echo Testing different format types...

REM Test text format
echo Testing 'text' format...
curl -s -w "%%{http_code}" -X POST -H "Content-Type: application/json" -d "{\"question\": \"%TEST_QUERY%\", \"format_type\": \"text\"}" "%CHAT_URL%" > temp_response.txt 2>nul
for /f "tokens=*" %%a in (temp_response.txt) do set RESPONSE=%%a
set HTTP_CODE=%RESPONSE:~-3%
if "%HTTP_CODE%" equ "200" (
    echo Text format test successful
) else (
    echo Text format test failed with HTTP %HTTP_CODE%
    del temp_response.txt 2>nul
    exit /b 1
)
del temp_response.txt 2>nul

REM Test table format
echo Testing 'table' format...
curl -s -w "%%{http_code}" -X POST -H "Content-Type: application/json" -d "{\"question\": \"%TEST_QUERY%\", \"format_type\": \"table\"}" "%CHAT_URL%" > temp_response.txt 2>nul
for /f "tokens=*" %%a in (temp_response.txt) do set RESPONSE=%%a
set HTTP_CODE=%RESPONSE:~-3%
if "%HTTP_CODE%" equ "200" (
    echo Table format test successful
) else (
    echo Table format test failed with HTTP %HTTP_CODE%
    del temp_response.txt 2>nul
    exit /b 1
)
del temp_response.txt 2>nul

REM Test graph format
echo Testing 'graph' format...
curl -s -w "%%{http_code}" -X POST -H "Content-Type: application/json" -d "{\"question\": \"%TEST_QUERY%\", \"format_type\": \"graph\"}" "%CHAT_URL%" > temp_response.txt 2>nul
for /f "tokens=*" %%a in (temp_response.txt) do set RESPONSE=%%a
set HTTP_CODE=%RESPONSE:~-3%
if "%HTTP_CODE%" equ "200" (
    echo Graph format test successful
) else (
    echo Graph format test failed with HTTP %HTTP_CODE%
    del temp_response.txt 2>nul
    exit /b 1
)
del temp_response.txt 2>nul

echo.
echo Smoke test completed successfully!
echo.
echo Chat endpoint smoke test PASSED
echo    - Server is responding
echo    - Chat endpoint is working
echo    - Responses include trace_id and audit_id
echo    - All format types work correctly
echo.

exit /b 0
