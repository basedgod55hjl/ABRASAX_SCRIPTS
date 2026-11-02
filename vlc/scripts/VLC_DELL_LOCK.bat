@echo off
:: ═══════════════════════════════════════════════════════════════
:: ABRASAX VLC — DELL P2319H PERMANENT PINNER
:: Forces all VLC windows to the Dell screen (X=1536, Y=0)
:: PRIMAL_HEX: 4f5349524953424c58434b
:: ═══════════════════════════════════════════════════════════════
title VLC DELL SCREEN LOCK

:LOOP
timeout /t 3 /nobreak >nul
tasklist /fi "IMAGENAME eq vlc.exe" 2>nul | find /i "vlc.exe" >nul
if errorlevel 1 goto LOOP

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
"Add-Type @'^
using System;^
using System.Runtime.InteropServices;^
public class WM {^
[DllImport(\"user32.dll\")]^
public static extern bool SetWindowPos(IntPtr h, IntPtr a, int x, int y, int cx, int cy, uint f);^
public static IntPtr HT = IntPtr.Zero;^
public const uint SNZ = 0x0004;^
public const uint SW = 0x0040;^
}^
'@;^
Get-Process vlc ^| ForEach-Object {^
  $h=$_.MainWindowHandle;^
  if($h) { [WM]::SetWindowPos($h, [WM]::HT, 1536, 0, 1536, 864, [WM]::SNZ -bor [WM]::SW) }^
}"

goto LOOP
