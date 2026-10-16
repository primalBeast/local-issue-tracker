' Start splash immediately with mshta. The helper console stays hidden.
' 1 = SW_SHOWNORMAL (HTA splash), 0 = SW_HIDE (no taskbar button)
Option Explicit
Dim fso, sh, dir, cmd, rc, splash
Set fso = CreateObject("Scripting.FileSystemObject")
Set sh = CreateObject("WScript.Shell")
dir = fso.GetParentFolderName(WScript.ScriptFullName)
sh.CurrentDirectory = dir
sh.Environment("PROCESS")("LIT_FROM_VBS") = "1"
splash = dir & "\lit\assets\splash.hta"
If fso.FileExists(splash) Then
  ' Drop a leftover close marker so the new splash does not shut itself immediately.
  On Error Resume Next
  fso.DeleteFile sh.ExpandEnvironmentStrings("%TEMP%\lit-splash.close"), True
  On Error GoTo 0
  ' cmd and Python must not start a second splash (that closes this one and opens another).
  sh.Environment("PROCESS")("LIT_SPLASH") = "1"
  sh.Run "mshta.exe """ & splash & """", 1, False
End If
cmd = "cmd.exe /c """ & dir & "\start-webview.cmd"""
rc = sh.Run(cmd, 0, True)
' Only our explicit start failures return 1. Crash/kill codes are not install problems.
If rc = 1 Then
  Dim logPath, detail, logFile
  logPath = sh.ExpandEnvironmentStrings("%TEMP%\lit-webview-start.log")
  detail = ""
  On Error Resume Next
  If fso.FileExists(logPath) Then
    Set logFile = fso.OpenTextFile(logPath, 1)
    detail = logFile.ReadAll
    logFile.Close
  End If
  On Error GoTo 0
  If Len(detail) > 900 Then detail = Right(detail, 900)
  If Len(detail) = 0 Then detail = "No details were written. Double-click install.cmd, then try again."
  MsgBox "Local Issue Tracker failed to start." & vbCrLf & vbCrLf & detail, 16, "Local Issue Tracker"
End If
