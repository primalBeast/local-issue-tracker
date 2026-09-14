# Minimize the console that launched this script (same window keeps its log text).
# 6 = SW_MINIMIZE
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public static class LitConsole {
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
  [DllImport("kernel32.dll")] public static extern IntPtr GetConsoleWindow();
}
"@
$hwnd = [LitConsole]::GetConsoleWindow()
if ($hwnd -ne [IntPtr]::Zero) {
  [void][LitConsole]::ShowWindow($hwnd, 6)
}
