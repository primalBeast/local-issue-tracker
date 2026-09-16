' Start splash immediately (pythonw Tk — PowerShell is often blocked on work PCs),
' then start-webview.cmd already minimized.
' 1 = SW_SHOWNORMAL (Tk splash), 7 = SW_SHOWMINNOACTIVE (helper console)
Option Explicit
Dim fso, sh, dir, cmd, rc, splash, pythonw
Set fso = CreateObject("Scripting.FileSystemObject")
Set sh = CreateObject("WScript.Shell")
dir = fso.GetParentFolderName(WScript.ScriptFullName)
sh.CurrentDirectory = dir
pythonw = dir & "\.venv\Scripts\pythonw.exe"
splash = dir & "\lit\assets\show-splash.ps1"
If fso.FileExists(pythonw) Then
  sh.Run """" & pythonw & """ -m lit.splash_app", 1, False
ElseIf fso.FileExists(splash) Then
  sh.Run "powershell.exe -STA -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File """ & splash & """", 0, False
End If
cmd = "cmd.exe /c """ & dir & "\start-webview.cmd"""
rc = sh.Run(cmd, 7, True)
' Only our explicit start failures return 1. Crash/kill codes are not install problems.
If rc = 1 Then
  MsgBox "Local Issue Tracker failed to start (code " & rc & ")." & vbCrLf & _
    "Double-click install.cmd, then try again.", 16, "Local Issue Tracker"
End If
