' Start splash immediately with mshta, then start-webview.cmd already minimized.
' 1 = SW_SHOWNORMAL (HTA splash), 7 = SW_SHOWMINNOACTIVE (helper console)
Option Explicit
Dim fso, sh, dir, cmd, rc, splash
Set fso = CreateObject("Scripting.FileSystemObject")
Set sh = CreateObject("WScript.Shell")
dir = fso.GetParentFolderName(WScript.ScriptFullName)
sh.CurrentDirectory = dir
splash = dir & "\lit\assets\splash.hta"
If fso.FileExists(splash) Then
  sh.Run "mshta.exe """ & splash & """", 1, False
End If
cmd = "cmd.exe /c """ & dir & "\start-webview.cmd"""
rc = sh.Run(cmd, 7, True)
' Only our explicit start failures return 1. Crash/kill codes are not install problems.
If rc = 1 Then
  MsgBox "Local Issue Tracker failed to start (code " & rc & ")." & vbCrLf & _
    "Double-click install.cmd, then try again.", 16, "Local Issue Tracker"
End If
