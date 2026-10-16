# Hide the launcher console, or show it again when startup fails.
# 0 = SW_HIDE (no taskbar button). 9 = SW_RESTORE.
param([ValidateSet("hide", "show")][string]$Action = "hide")
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
  $cmd = 0
  if ($Action -eq "show") { $cmd = 9 }
  [void][LitConsole]::ShowWindow($hwnd, $cmd)
}
