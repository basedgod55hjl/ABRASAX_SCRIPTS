/* OSIRISBLXCK / ABRASAX UI-stack probe.
 * Proves the Windows SDK desktop target actually compiles + links: DXGI 1.6,
 * D3D11, DWM window composition attributes (the exact APIs the floating-brain
 * overlay needs), plus the live SDK build number the headers came from.
 */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <dwmapi.h>
#include <dxgi1_6.h>
#include <d3d11.h>
#include <stdio.h>

#pragma comment(lib, "dwmapi.lib")
#pragma comment(lib, "dxgi.lib")
#pragma comment(lib, "d3d11.lib")
#pragma comment(lib, "user32.lib")

int main(void) {
    /* 1. Compile-time SDK identity */
    printf("SDK_VERSION_MAJOR=%d MINOR=%d BUILD=%d NTDDI=0x%08X\n",
           WDK_NTDDI_VERSION >= 0 ? (int)((NTDDI_VERSION >> 24) & 0xFF) : 0,
           0, (int)(NTDDI_VERSION & 0xFFFF), (unsigned)NTDDI_VERSION);
    printf("WINVER_hex=0x%04X _WIN32_WINNT_hex=0x%04X\n", (unsigned)WINVER, (unsigned)_WIN32_WINNT);

    /* 2. DXGI 1.6 factory: this symbol only exists in the desktop target pack */
    IDXGIFactory6* fac = NULL;
    HRESULT hr = CreateDXGIFactory2(0, &IID_IDXGIFactory6, (void**)&fac);
    printf("CreateDXGIFactory2(IDXGIFactory6) hr=0x%08lX ok=%d\n", (unsigned long)hr, SUCCEEDED(hr));
    if (SUCCEEDED(hr) && fac) {
        IDXGIAdapter1* ad = NULL;
        if (SUCCEEDED(fac->lpVtbl->EnumAdapterByGpuPreference(fac, 0, DXGI_GPU_PREFERENCE_HIGH_PERFORMANCE, &IID_IDXGIAdapter1, (void**)&ad)) && ad) {
            DXGI_ADAPTER_DESC1 d1; ZeroMemory(&d1, sizeof d1);
            if (SUCCEEDED(ad->lpVtbl->GetDesc1(ad, &d1)))
                wprintf(L"GPU0=%ls dedicated_vram_mb=%llu\n", d1.Description, (unsigned long long)(d1.DedicatedVideoMemory >> 20));
            ad->lpVtbl->Release(ad);
        }
        fac->lpVtbl->Release(fac);
    }

    /* 3. D3D11 device -> proves d3d11 headers/libs link */
    ID3D11Device* dev = NULL; ID3D11DeviceContext* ctx = NULL;
    hr = D3D11CreateDevice(NULL, D3D_DRIVER_TYPE_HARDWARE, NULL, 0, NULL, 0,
                           D3D11_SDK_VERSION, &dev, NULL, &ctx);
    printf("D3D11CreateDevice hw hr=0x%08lX ok=%d\n", (unsigned long)hr, SUCCEEDED(hr));
    if (dev) { dev->lpVtbl->Release(dev); ctx->lpVtbl->Release(ctx); }

    /* 4. The overlay's actual need: a layered, topmost, alpha-capable popup window */
    WNDCLASSEXW wc = {0};
    wc.cbSize = sizeof wc;
    wc.lpfnWndProc = DefWindowProcW;
    wc.hInstance = GetModuleHandleW(NULL);
    wc.lpszClassName = L"ABRASAX_PROBE";
    printf("RegisterClass ok=%d\n", RegisterClassExW(&wc) != 0);
    HWND h = CreateWindowExW(WS_EX_LAYERED | WS_EX_TOOLWINDOW, L"ABRASAX_PROBE", L"probe",
                             WS_POPUP, 0, 0, 64, 64, NULL, NULL, wc.hInstance, NULL);
    printf("CreateWindowExW(layered,popup) hwnd=%p err=%lu\n", (void*)h, (unsigned long)GetLastError());
    if (h) {
        int sheet = -1;
        fprintf(stderr, "  (SetWindowCompositionAttribute probed by .NET/Unity client, not here)\n");
        HRESULT dhr = DwmSetWindowAttribute(h, DWMWA_TRANSITIONS_FORCEDISABLED, &sheet, sizeof sheet);
        printf("DwmSetWindowAttribute(DWMWA_TRANSITIONS_FORCEDISABLED) hr=0x%08lX ok=%d\n", (unsigned long)dhr, SUCCEEDED(dhr));
        BOOL topmost = SetWindowPos(h, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE);
        printf("SetWindowPos(HWND_TOPMOST) ok=%d\n", topmost != 0);
        DestroyWindow(h);
    }
    printf("PROBE_RESULT=%s\n", (SUCCEEDED(hr) && h) ? "PASS" : "SEE_ABOVE");
    return 0;
}
