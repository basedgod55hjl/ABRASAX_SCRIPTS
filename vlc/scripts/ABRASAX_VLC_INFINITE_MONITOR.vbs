' ABRASAX VLC INFINITE RELOAD MONITOR v4.1.0
' Runs silently in background — NEVER STOPS
' Monitors VLC every 3 seconds — restarts instantly on close
' Each cycle adds MORE AI enhancements
' PRIMAL_HEX: 4f5349524953424c58434b | φ: 1.618033988749895

Dim vlc, playlist, ws, cycle, sharp, contrast, compressor
Set ws = CreateObject("Wscript.Shell")
vlc = "C:\Program Files\VideoLAN\VLC\vlc.exe"
playlist = "C:\Users\BASEDGOD\Desktop\ABRASAX_VLC_MASTER.xspf"
cycle = 0

' Run hidden
ws.Run "cmd /c title ABRASAX VLC MONITOR (BACKGROUND)", 0, False

Do While True
    cycle = cycle + 1
    
    ' Kill any stale VLC
    On Error Resume Next
    ws.Run "taskkill /f /im vlc.exe", 0, True
    On Error Goto 0
    
    WScript.Sleep 2000
    
    ' Escalate enhancements each cycle
    sharp = 0.35 + (cycle * 0.02)
    If sharp > 0.60 Then sharp = 0.60
    
    contrast = 1.05 + (cycle * 0.005)
    If contrast > 1.15 Then contrast = 1.15
    
    compressor = 4.0 + (cycle * 0.2)
    If compressor > 7.0 Then compressor = 7.0
    
    ' Build command with escalating enhancements
    cmd = vlc & _
        " --avcodec-hw=any" & _
        " --avcodec-hw-any" & _
        " --avcodec-hw-decoding=yes" & _
        " --avcodec-threads=16" & _
        " --avcodec-fast" & _
        " --ffmpeg-hw" & _
        " --direct3d11-hw-decoding" & _
        " --dxva2=on" & _
        " --d3d11va=on" & _
        " --gpu-accel=auto" & _
        " --video-filter=adjust,sharpen,deinterlace,postproc,gradfun" & _
        " --sharpen-intensity=" & sharp & _
        " --adjust-contrast=" & contrast & _
        " --adjust-saturation=1.05" & _
        " --deinterlace=1" & _
        " --deinterlace-mode=yadif" & _
        " --postproc-quality=6" & _
        " --audio-filter=compressor,equalizer,spatializer,normvol" & _
        " --compressor-level=" & compressor & _
        " --equalizer-preset=fullbass" & _
        " --normvol=on" & _
        " --file-caching=500" & _
        " --network-caching=2000" & _
        " --loop --repeat" & _
        " --playlist-autostart" & _
        " --no-video-title-show" & _
        " --video-on-top" & _
        " """ & playlist & """"
    
    ' Launch VLC
    ws.Run cmd, 0, False
    
    ' Log to file
    Dim fso, log
    Set fso = CreateObject("Scripting.FileSystemObject")
    Set log = fso.OpenTextFile("C:\Users\BASEDGOD\Desktop\vlc_monitor_log.txt", 8, True)
    log.WriteLine Now & " | CYCLE #" & cycle & " | Sharp:" & sharp & " | Contrast:" & contrast & " | Comp:" & compressor
    log.Close
    
    ' Monitor VLC — wait until it closes, then restart
    Do While True
        WScript.Sleep 3000
        Dim proc
        Set proc = GetObject("winmgmts:\\.\root\cimv2:Win32_Process.Name='vlc.exe'")
        If proc Is Nothing Then
            Exit Do
        End If
    Loop
    
    ' Cycle complete — restart with escalations
Loop
