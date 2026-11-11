@echo off
rem Nova AI Browser: run a browser tool. Usage: nova-browser <tool> [key=value ...] | nova-browser tools
rem Runs the browser host the Nova apps registered (with Node, or inside Nova AI Desktop).
setlocal
if defined NOVA_AI_BROWSER_HOME (set "host=%NOVA_AI_BROWSER_HOME%\bin\nova-ai-browser-host.bat") else (set "host=%USERPROFILE%\.nova-ai\browser\bin\nova-ai-browser-host.bat")
if not exist "%host%" (
    echo Nova AI Browser is not set up on this computer. Turn on the Nova AI Browser plug-in in Nova AI Desktop, or start Nova AI for VS Code or the Nova AI CLI once, then restart the browser. 1>&2
    exit /b 2
)
call "%host%" call %*
exit /b %errorlevel%
