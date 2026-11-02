#Persistent
#SingleInstance Force
SetWorkingDir "C:\Users\BASEDGOD\Desktop\_SCRIPTS\vlc"

; ══════════════════════════════════════════════════════════
; ABRASAX HOTKEY BINDINGS v1.0
; AutoHotkey v2.0 — PRIMAL_HEX: 4f5349524953424c58434b
; ══════════════════════════════════════════════════════════

; ─── VLC CONTROL ───

; Ctrl+Alt+V = Toggle VLC play/stop
^!v:: {
    if ProcessExist("vlc.exe") {
        ; VLC running — kill it
        ProcessClose("vlc.exe")
        ToolTip("VLC STOPPED")
    } else {
        ; VLC not running — launch
        Run('"C:\Program Files\VideoLAN\VLC\vlc.exe" '
            . '"C:\Users\BASEDGOD\Desktop\_SCRIPTS\vlc\playlists\ehgeh.xspf" '
            . '--avcodec-hw=any --avcodec-dr --avcodec-threads=0 --avcodec-hurry-up '
            . '--avcodec-corrupted --vout=direct3d11 --d3d11-upscale-mode=super '
            . '--no-dvdnav --playlist-autostart --loop --no-video-title-show --video-on-top')
        ToolTip("VLC STARTED")
    }
    SetTimer(() => ToolTip(), -1000)
}

; Ctrl+Alt+L = Launch large videos from F: drive
^!l:: {
    Run('"C:\Program Files\VideoLAN\VLC\vlc.exe" '
        . '"F:\SORTED_MEDIA\Videos\04_Large_1GB_to_5GB" '
        . '--avcodec-hw=any --avcodec-corrupted --vout=direct3d11 --d3d11-upscale-mode=super '
        . '--no-dvdnav --playlist-autostart --loop --no-video-title-show')
    ToolTip("LARGE VIDEOS LAUNCHED")
    SetTimer(() => ToolTip(), -1000)
}

; Ctrl+Alt+G = GPU telemetry popup
^!g:: {
    Run('nvidia-smi --query-gpu=name,utilization.gpu,utilization.decoder,memory.used,memory.total,temperature.gpu,power.draw,clocks.current.video --format=csv -l 5')
}

; Ctrl+Alt+K = Kill all VLC
^!k:: {
    ProcessClose("vlc.exe")
    ToolTip("VLC KILLED")
    SetTimer(() => ToolTip(), -1000)
}

; Ctrl+Alt+M = Launch master launcher
^!m:: {
    Run('"C:\Users\BASEDGOD\Desktop\_SCRIPTS\vlc\scripts\VLC_ABRASAX_LAUNCHER.bat"')
}

; ─── PI AGENTS ───

; Ctrl+Alt+1 = Focus Dell top-left window
^!1:: {
    try {
        hWnd := WinExist("ahk_exe cmd.exe", " - pi")
        if hWnd {
            WinActivate(hWnd)
            WinMove(1536, 0, 766, 430, hWnd)
        }
    }
}

; Ctrl+Alt+2 = Focus Dell top-right window
^!2:: {
    try {
        hWnd := WinExist("ahk_exe cmd.exe", "ABRASAX")
        if hWnd {
            WinActivate(hWnd)
            WinMove(2304, 0, 766, 430, hWnd)
        }
    }
}

; Ctrl+Alt+3 = Focus Dell bottom-left window
^!3:: {
    try {
        hWnd := WinExist("ahk_exe cmd.exe", "_SCRIPTS")
        if hWnd {
            WinActivate(hWnd)
            WinMove(1536, 432, 766, 430, hWnd)
        }
    }
}

; Ctrl+Alt+4 = Focus Dell bottom-right window
^!4:: {
    try {
        hWnd := WinExist("ahk_exe cmd.exe", "Desktop")
        if hWnd {
            WinActivate(hWnd)
            WinMove(2304, 432, 766, 430, hWnd)
        }
    }
}

; ─── TOOLS ───

; Ctrl+Shift+F = Everything search
^+f::Run("C:\Program Files\Everything\Everything.exe")

; Win+Space = QuickLook (preview file)
#Space::Send("{Space}")
