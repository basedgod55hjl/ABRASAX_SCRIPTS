' run_hidden.vbs — ABRASAX headless launcher
' Runs the command passed as argument 0 with NO window (0 = hidden), detached, non-blocking.
' Working directory: argument 1 if given, otherwise this script's folder.
' Usage:  wscript //B "run_hidden.vbs" "<full command line>" ["<workdir>"]
If WScript.Arguments.Count = 0 Then WScript.Quit 1
Set fso = CreateObject("Scripting.FileSystemObject")
Set sh = CreateObject("WScript.Shell")
If WScript.Arguments.Count > 1 Then
  sh.CurrentDirectory = WScript.Arguments(1)
Else
  sh.CurrentDirectory = fso.GetParentFolderName(WScript.ScriptFullName)
End If
sh.Run WScript.Arguments(0), 0, False
WScript.Quit 0
