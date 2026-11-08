' ABRASAX sense tick - Task Scheduler entry point.
'
' WHY THIS IS SO PLAIN
' --------------------
' Measured on this host, from a scheduled task:
'   * wscript inside a task starts and completes IF it only does file I/O
'     (_t_fileio.vbs -> exit 0, file written).
'   * wscript inside a task HANGS INDEFINITELY the moment it touches
'     CreateObject("WScript.Shell") (_t_run.vbs, sense_tick.vbs -> stuck
'     "Running", Last Result 267009, nothing logged).
'   * The uv venv shim at PYTHON\.venv_gui\Scripts\python.exe re-execs the
'     base interpreter, which re-entered -m abrasax.sense_loop and forked
'     forever when started from a task.
'
' So: this script does NOT spawn anything and does NOT touch WScript.Shell.
' It writes a request file atomically. The resident ABRASAX supervisor is
' already running in the interactive session and picks the request up. If
' nothing is there to pick it up, the request is still a durable record that
' the schedule fired, which is the one thing a cron entry must guarantee.
'
' The request is written to a temp name then renamed, so a reader never sees a
' half-written file.

Option Explicit

Dim fso, logPath, reqPath, tmpPath, ts, body, stamp

logPath = "C:\ABRASAX\LOGS\sense-tick-launcher.log"
reqPath = "C:\ABRASAX\LOGS\sense-tick.request"
tmpPath = reqPath & ".tmp"

Set fso = CreateObject("Scripting.FileSystemObject")

stamp = Year(Now) & "-" & Right("0" & Month(Now), 2) & "-" & Right("0" & Day(Now), 2) & _
        "T" & Right("0" & Hour(Now), 2) & ":" & Right("0" & Minute(Now), 2) & ":" & Right("0" & Second(Now), 2)

' 1. durable proof the schedule fired
Set ts = fso.OpenTextFile(logPath, 8, True)
ts.WriteLine stamp & "  scheduled tick requested"
ts.Close

' 2. the request itself, written atomically
Set ts = fso.OpenTextFile(tmpPath, 2, True)
ts.WriteLine "requested_at=" & stamp
ts.WriteLine "task=ABRASAX-SenseLoop"
ts.WriteLine "command=-m abrasax.sense_loop --count 1"
ts.Close

If fso.FileExists(reqPath) Then
    On Error Resume Next
    fso.DeleteFile reqPath, True
    On Error GoTo 0
End If
fso.MoveFile tmpPath, reqPath

WScript.Quit 0
