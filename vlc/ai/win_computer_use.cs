@'
using System;
using System.Drawing;
using System.Drawing.Imaging;
using System.Windows.Forms;
using System.Runtime.InteropServices;
public class WinComputerUse {
    // ── Screen capture ──
    [DllImport("user32.dll")] public static extern IntPtr GetDesktopWindow();
    [DllImport("user32.dll")] public static extern IntPtr GetWindowDC(IntPtr hWnd);
    [DllImport("user32.dll")] public static extern int ReleaseDC(IntPtr hWnd, IntPtr hDC);
    [DllImport("gdi32.dll")] public static extern bool BitBlt(IntPtr hdc, int x, int y, int w, int h, IntPtr hdcSrc, int x1, int y1, int rop);
    
    public static string CaptureScreen() {
        var bounds = Screen.PrimaryScreen.Bounds;
        var all = new Rectangle(
            SystemInformation.VirtualScreen.X,
            SystemInformation.VirtualScreen.Y,
            SystemInformation.VirtualScreen.Width,
            SystemInformation.VirtualScreen.Height
        );
        using (var bmp = new Bitmap(all.Width, all.Height)) {
            using (var g = Graphics.FromImage(bmp)) {
                g.CopyFromScreen(all.X, all.Y, 0, 0, all.Size);
            }
            string path = System.IO.Path.GetTempPath() + "win_cu_" + DateTime.Now.Ticks + ".png";
            bmp.Save(path, ImageFormat.Png);
            return path;
        }
    }
    
    // ── Window enumeration ──
    public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);
    [DllImport("user32.dll")] public static extern bool EnumWindows(EnumWindowsProc proc, IntPtr lParam);
    [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr hWnd, System.Text.StringBuilder text, int count);
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT rect);
    [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr hWnd);
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
    [DllImport("user32.dll")] public static extern bool MoveWindow(IntPtr hWnd, int x, int y, int w, int h, bool repaint);
    [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
    
    public struct RECT { public int Left; public int Top; public int Right; public int Bottom; }
    
    public static string ListWindows() {
        var result = new System.Text.StringBuilder();
        int idx = 0;
        EnumWindows((hWnd, lp) => {
            var sb = new System.Text.StringBuilder(256);
            GetWindowText(hWnd, sb, 256);
            string title = sb.ToString().Trim();
            if (!string.IsNullOrEmpty(title) && IsWindowVisible(hWnd)) {
                RECT r;
                GetWindowRect(hWnd, out r);
                result.AppendLine($"{idx}: \"{title}\" @({r.Left},{r.Top}) {r.Right-r.Left}x{r.Bottom-r.Top}");
                idx++;
            }
            return true;
        }, IntPtr.Zero);
        return result.ToString();
    }
    
    public static IntPtr FindWindowByTitle(string substr) {
        IntPtr found = IntPtr.Zero;
        EnumWindows((hWnd, lp) => {
            var sb = new System.Text.StringBuilder(256);
            GetWindowText(hWnd, sb, 256);
            if (sb.ToString().IndexOf(substr, StringComparison.OrdinalIgnoreCase) >= 0 && IsWindowVisible(hWnd)) {
                found = hWnd;
                return false;
            }
            return true;
        }, IntPtr.Zero);
        return found;
    }
    
    public static bool MoveTo(IntPtr hWnd, int x, int y, int w, int h) {
        return MoveWindow(hWnd, x, y, w, h, true);
    }
    
    public static bool Focus(IntPtr hWnd) {
        return ShowWindow(hWnd, 9) && SetForegroundWindow(hWnd);
    }
}
'@
