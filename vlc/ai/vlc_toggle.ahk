; CTRL+ALT+V = Stop/Start VLC
^!v::
    Process, Exist, vlc.exe
    if ErrorLevel {
        Process, Close, vlc.exe
        ToolTip, VLC STOPPED
    } else {
        Run, "C:\Program Files\VideoLAN\VLC\vlc.exe" "C:\Users\BASEDGOD\Desktop\_SCRIPTS\vlc\playlists\ehgeh.xspf" --playlist-autostart --loop
        ToolTip, VLC STARTED
    }
    Sleep 1000
    ToolTip
return
