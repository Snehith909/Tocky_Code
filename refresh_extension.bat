@echo off
echo ============================================
echo Tocky Code - Force Settings Refresh Script
echo ============================================
echo.

echo Step 1: Checking extension installation...
code --list-extensions --show-versions | findstr tocky
echo.

echo Step 2: Uninstalling extension...
code --uninstall-extension tocky.tocky-code
timeout /t 2 /nobreak >nul
echo.

echo Step 3: Installing fresh extension...
cd /d E:\Miniproject
code --install-extension tocky-code-0.1.0.vsix
timeout /t 2 /nobreak >nul
echo.

echo Step 4: Opening VS Code settings...
code --goto "vscode://settings/codeguard.llmProvider"
echo.

echo ============================================
echo IMPORTANT: After VS Code opens:
echo 1. Press Ctrl+Shift+P
echo 2. Type: Developer: Reload Window
echo 3. Press Enter
echo 4. Then go to Settings (Ctrl+,)
echo 5. Search: codeguard.llmProvider
echo 6. You should see 'copilot' option now!
echo ============================================
pause
