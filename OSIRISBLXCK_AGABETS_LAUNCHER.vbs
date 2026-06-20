Set WshShell = CreateObject("WScript.Shell")
Set Fso = CreateObject("Scripting.FileSystemObject")
Set ShellApp = CreateObject("Shell.Application")

' --- Elevate to Admin if not already ---
If Not WshShell.Run("cmd /c net session >nul 2>&1", 0, True) = 0 Then
    ' Not admin — relaunch self with runas
    ShellApp.ShellExecute "wscript.exe", Chr(34) & WScript.ScriptFullName & Chr(34), "", "runas", 1
    WScript.Quit
End If

SCRIPTS       = "C:\Users\BASEDGOD\Desktop\ABRASAX AGI\scripts"
ABRASAX       = "C:\Users\BASEDGOD\Desktop\ABRASAX"
PID_FILE      = ABRASAX & "\.agabits.pid"
LOG_FILE      = ABRASAX & "\launcher_log.txt"
MAX_RESTARTS  = 5
RESTART_DELAY = 3000
WATCH_INTERVAL = 5000

' Silence UAC prompt for subprocesses
Dim runStyle : runStyle = 0 ' 0=hide, 1=normal

' Watchdog state arrays
Dim WdRestarts(4) : WdRestarts(0) = 0 : WdRestarts(1) = 0 : WdRestarts(2) = 0 : WdRestarts(3) = 0
Dim WdLastAlert(4) : WdLastAlert(0) = "" : WdLastAlert(1) = "" : WdLastAlert(2) = "" : WdLastAlert(3) = ""

' --- Helpers ---

Sub Log(msg)
    On Error Resume Next
    Dim Ts : Set Ts = Fso.OpenTextFile(LOG_FILE, 8, True)
    Ts.WriteLine Now & " " & msg
    Ts.Close
End Sub

Function IsNodeRunning()
    IsNodeRunning = False
    On Error Resume Next
    If Fso.FileExists(PID_FILE) Then
        Dim RawPid : RawPid = Trim(Fso.OpenTextFile(PID_FILE, 1).ReadAll())
        If IsNumeric(RawPid) And Len(RawPid) > 0 Then
            Dim Col : Set Col = GetObject("winmgmts:\\.\root\cimv2").ExecQuery( _
                "SELECT ProcessId FROM Win32_Process WHERE ProcessId=" & RawPid)
            IsNodeRunning = (Col.Count > 0)
        End If
    End If
End Function

Function PythonProcessCount()
    Dim Col, Count
    On Error Resume Next
    Set Col = GetObject("winmgmts:\\.\root\cimv2").ExecQuery( _
        "SELECT * FROM Win32_Process WHERE Name='python.exe'")
    If Err.Number = 0 Then
        Count = Col.Count
    Else
        Count = -1
    End If
    PythonProcessCount = Count
End Function

' --- Main ---

Log "=== LAUNCHER STARTED (ADMIN) ==="

' 1. Kill old processes
Log "Cleaning up old processes..."
On Error Resume Next
Dim WmiCol, OldProc
Set WmiCol = GetObject("winmgmts:\\.\root\cimv2").ExecQuery( _
    "SELECT * FROM Win32_Process WHERE Name='python.exe'")
For Each OldProc In WmiCol
    OldProc.Terminate()
Next
WScript.Sleep 1500
WshShell.Run "taskkill /F /IM python.exe", runStyle, True
WScript.Sleep 1000

' Also kill old Node.js / abrasaxd processes if desired
WshShell.Run "taskkill /F /IM node.exe 2>nul", runStyle, False

' 2. Launch Node.js bridge (retry loop)
Dim bridgeAttempts : bridgeAttempts = 0
Dim bridgeLaunched : bridgeLaunched = False

Do While bridgeAttempts < MAX_RESTARTS
    If Not IsNodeRunning() Then
        bridgeAttempts = bridgeAttempts + 1
        Log "Launching Node.js bridge (attempt " & bridgeAttempts & ")"
        WshShell.Run "cmd /c node """ & ABRASAX & "\node_agabits_bridge.mjs""", runStyle, False
        WScript.Sleep 3000
    End If
    If IsNodeRunning() Then
        bridgeLaunched = True
        Exit Do
    End If
    WScript.Sleep RESTART_DELAY
Loop

If Not bridgeLaunched Then
    Log "WARNING: Node.js bridge failed to start after " & MAX_RESTARTS & " attempts"
End If

' 3. Launch VRAM Monitor
Log "Launching VRAM Monitor"
WshShell.Run "cmd /c start ""VRAM"" /MIN cmd /c python """ & SCRIPTS & "\_check_vram.py""", runStyle, False
WScript.Sleep 2000

' 4. Launch Alive Bridge daemon
Log "Launching Alive Bridge"
WshShell.Run "cmd /c start ""ALIVE"" /MIN cmd /c python """ & SCRIPTS & "\_alive_bridge_daemon.py""", runStyle, False
WScript.Sleep 2000

' 5. Launch OSIRISBLXCK v5 Chat
Log "Launching OSIRISBLXCK v5 Chat"
WshShell.Run "cmd /c start ""OSIRISBLXCK_v5"" cmd /k python """ & SCRIPTS & "\osirisblxck_ultimate_v5.py""", 1, False
WScript.Sleep 1000

' 6. Launch Rust daemon (abrasaxd) if compiled
Dim RustDaemonPath : RustDaemonPath = ABRASAX & "\abrasax_rs\target\release\abrasaxd.exe"
If Fso.FileExists(RustDaemonPath) Then
    Log "Launching abrasaxd (Rust daemon)"
    WshShell.Run """" & RustDaemonPath & """", runStyle, False
    WScript.Sleep 2000
Else
    Log "Rust daemon not found at " & RustDaemonPath & " — skipping"
End If

' 7. Confirmation popup
Log "Launcher completed successfully"
WshShell.Popup "OSIRISBLXCK v5 launched!" & vbCrLf & vbCrLf & _
    "- Chat window opening" & vbCrLf & _
    "- Node.js Bridge on port 18790 (auto-relaunch)" & vbCrLf & _
    "- VRAM Monitor" & vbCrLf & _
    "- Alive Bridge" & vbCrLf & _
    "- Rust daemon (if compiled)" & vbCrLf & _
    "- Log: " & LOG_FILE, _
    5, "OSIRISBLXCK [ADMIN]", 64

' 8. --- WATCHDOG LOOP ---
Dim ProcCount

Do While True
    WScript.Sleep WATCH_INTERVAL

    ' --- Node.js bridge watchdog ---
    If Not IsNodeRunning() Then
        WdRestarts(0) = WdRestarts(0) + 1
        If WdRestarts(0) > MAX_RESTARTS Then
            If WdLastAlert(0) = "" Or DateDiff("s", WdLastAlert(0), Now) > 60 Then
                Log "Watchdog: Node.js bridge exceeded max restarts, giving up"
                WdLastAlert(0) = Now
            End If
        Else
            Log "Watchdog: relaunching Node.js bridge (restart #" & WdRestarts(0) & ")"
            WshShell.Run "cmd /c node """ & ABRASAX & "\node_agabits_bridge.mjs""", runStyle, False
            WScript.Sleep 3000
        End If
    End If

    ' --- Python processes watchdog ---
    ProcCount = PythonProcessCount()
    If ProcCount = 0 Then
        Log "Watchdog: No Python processes found, relaunching all..."
        WshShell.Run "cmd /c start ""VRAM"" /MIN cmd /c python """ & SCRIPTS & "\_check_vram.py""", runStyle, False
        WScript.Sleep 1500
        WshShell.Run "cmd /c start ""ALIVE"" /MIN cmd /c python """ & SCRIPTS & "\_alive_bridge_daemon.py""", runStyle, False
        WScript.Sleep 1500
        WshShell.Run "cmd /c start ""OSIRISBLXCK_v5"" cmd /k python """ & SCRIPTS & "\osirisblxck_ultimate_v5.py""", 1, False
    End If
Loop
