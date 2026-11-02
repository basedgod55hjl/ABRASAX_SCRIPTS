' ABRASAX VLC 64-bit Quick Launch
' Double-click to launch instantly

Dim vlc, playlist, cmd
vlc = "C:\Program Files\VideoLAN\VLC\vlc.exe"
playlist = "C:\Users\BASEDGOD\Desktop\ABRASAX_VLC_MASTER.xspf"

cmd = vlc & " --avcodec-hw=any --direct3d11-hw-decoding --gpu-accel=auto --dxva2=on --d3d11va=on --no-video-title-show """ & playlist & """"

CreateObject("Wscript.Shell").Run cmd, 0, False
