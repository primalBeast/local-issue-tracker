' Start start-webview.cmd already minimized (no extra visible console).
' 7 = SW_SHOWMINNOACTIVE
Option Explicit
Dim fso, sh, dir, cmd, rc
Set fso = CreateObject("Scripting.FileSystemObject")
Set sh = CreateObject("WScript.Shell")
dir = fso.GetParentFolderName(WScript.ScriptFullName)
sh.CurrentDirectory = dir
cmd = "cmd.exe /c """ & dir & "\start-webview.cmd"""
rc = sh.Run(cmd, 7, True)
If rc <> 0 Then
  MsgBox "Local Issue Tracker failed to start (code " & rc & ")." & vbCrLf & _
    "Double-click install.cmd, then try again.", 16, "Local Issue Tracker"
End If
