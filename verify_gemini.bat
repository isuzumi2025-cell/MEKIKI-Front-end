@echo off
chcp 65001 > nul
echo ==========================================
echo 🧪 Gemini OCR Integration Verification
echo ==========================================
echo.
echo Running verification script...
echo.
python test_gemini_integration.py
echo.
echo ==========================================
if %ERRORLEVEL% EQU 0 (
    echo ✅ Verification Successful!
) else (
    echo ❌ Verification Failed. Check logs above.
)
echo ==========================================
pause
