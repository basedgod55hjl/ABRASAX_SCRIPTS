"""Compile-gate the Unity floating-brain client with the real Roslyn compiler.

There is no Unity editor licensed on this host, so FloatingBrainRenderer.cs cannot
be built by Unity. It can still be type-checked: this throws minimal UnityEngine
stubs into a throwaway .NET project together with the real script and runs
`dotnet build`. Any syntax error, unresolved symbol or API misuse fails the build.

That is what caught two real bugs on first run — a missing `using System.Net.Http;`
and a missing ImageConversion/JsonUtility surface — before any of it reached a
Unity project.

Exit 0 = the script compiles clean.
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(r"C:\ABRASAX")
WORK = ROOT / "BUILD" / "unity-syntaxcheck"
SCRIPT = ROOT / "APPS" / "unity-assets" / "BrainUI" / "Scripts" / "FloatingBrainRenderer.cs"

STUBS = r'''// Minimal UnityEngine surface so the renderer script can be type-checked.
// Not a Unity reimplementation; behaviour is intentionally shallow.
using System;
using System.Collections;

namespace UnityEngine
{
    public class Object { public string name; public static void Destroy(Object o) { } }
    public class Component : Object
    {
        public GameObject gameObject = new GameObject();
        public Transform transform = new Transform();
    }
    public class GameObject : Object { public Transform transform = new Transform(); }
    public class Transform : Object { }
    public class Coroutine { }
    public class MonoBehaviour : Component
    {
        public Coroutine StartCoroutine(IEnumerator routine) => new Coroutine();
        public void StopAllCoroutines() { }
    }

    [AttributeUsage(AttributeTargets.Field)] public sealed class HeaderAttribute : Attribute { public HeaderAttribute(string s) { } }
    [AttributeUsage(AttributeTargets.Field)] public sealed class TooltipAttribute : Attribute { public TooltipAttribute(string s) { } }
    [AttributeUsage(AttributeTargets.Field)] public sealed class RangeAttribute : Attribute { public RangeAttribute(float a, float b) { } }
    [AttributeUsage(AttributeTargets.Field)] public sealed class MinAttribute : Attribute { public MinAttribute(float a) { } }
    [AttributeUsage(AttributeTargets.Class)] public sealed class AddComponentMenuAttribute : Attribute { public AddComponentMenuAttribute(string s) { } }

    public static class Debug
    {
        public static void Log(object m) { }
        public static void LogWarning(object m) { }
        public static void LogError(object m) { }
    }

    public static class Mathf
    {
        public const float PI = 3.14159265f;
        public static float Max(float a, float b) => a > b ? a : b;
        public static int Max(int a, int b) => a > b ? a : b;
        public static float Clamp(float v, float a, float b) => v < a ? a : (v > b ? b : v);
        public static int Clamp(int v, int a, int b) => v < a ? a : (v > b ? b : v);
        public static int RoundToInt(float v) => (int)Math.Round(v);
        public static float Sqrt(float v) => (float)Math.Sqrt(v);
        public static float Sin(float v) => (float)Math.Sin(v);
        public static float Cos(float v) => (float)Math.Cos(v);
    }

    public static class Time
    {
        public static float deltaTime => 0.016f;
        public static float realtimeSinceStartup => 1.0f;
    }

    public enum FilterMode { Point, Bilinear, Trilinear }
    public enum TextureWrapMode { Repeat, Clamp, Mirror, MirrorOnce }
    public enum TextureFormat { RGBA32, ARGB32, RGB24, R8 }

    public class Texture : Object { }

    public class Texture2D : Texture
    {
        public FilterMode filterMode;
        public TextureWrapMode wrapMode;
        public int anisoLevel;
        public int width, height;
        public Texture2D(int w, int h) { width = w; height = h; }
        public Texture2D(int width, int height, TextureFormat textureFormat, bool mipChain) { this.width = width; this.height = height; }
        public void Apply(bool updateMipmaps, bool makeNoLongerReadable) { }
        public bool LoadImage(byte[] d) => d != null && d.Length > 0;
    }

    public static class JsonUtility
    {
        public static T FromJson<T>(string json) => default(T);
        public static string ToJson(object o) => "{}";
    }

    public static class ImageConversion
    {
        public static bool LoadImage(Texture2D t, byte[] d, bool markNonReadable) => t.LoadImage(d);
    }

}

namespace UnityEngine.Events
{
    // Unity puts UnityEvent here, not in UnityEngine. Modelling it correctly is the
    // point: an earlier version of this stub hid a real `using UnityEngine.Events;`
    // omission from the Roslyn check, and only the Unity compiler caught it.
    [Serializable]
    public class UnityEvent
    {
        public void Invoke() { }
        public void AddListener(Action a) { }
        public void RemoveListener(Action a) { }
    }

    [Serializable]
    public class UnityEvent<T>
    {
        public void Invoke(T value) { }
        public void AddListener(Action<T> a) { }
        public void RemoveListener(Action<T> a) { }
    }
}

namespace UnityEngine.Networking
{
    public class DownloadHandler { }
    public class UploadHandler { }
    public sealed class UploadHandlerRaw : UploadHandler { public UploadHandlerRaw(byte[] d) { } }
    public class UnityWebRequestAsyncOperation { }

    public class UnityWebRequest : IDisposable
    {
        public enum Result { InProgress, Success, ConnectionError, ProtocolError, DataProcessingError }
        public UploadHandler uploadHandler;
        public Result result;
        public string error;
        public static UnityWebRequest Post(string uri, string ct) => new UnityWebRequest();
        public void SetRequestHeader(string n, string v) { }
        public UnityWebRequestAsyncOperation SendWebRequest() => new UnityWebRequestAsyncOperation();
        public void Dispose() { }
    }
}
'''

CSPROJ = '''<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>net8.0</TargetFramework>
    <LangVersion>9.0</LangVersion>
    <Nullable>disable</Nullable>
    <ImplicitUsings>disable</ImplicitUsings>
    <AssemblyName>FloatingBrainSyntaxCheck</AssemblyName>
    <EnableDefaultCompileItems>false</EnableDefaultCompileItems>
    <GenerateAssemblyInfo>false</GenerateAssemblyInfo>
    <ProduceReferenceAssembly>false</ProduceReferenceAssembly>
  </PropertyGroup>
  <ItemGroup>
    <Compile Include="UnityStubs.cs" />
    <Compile Include="{script}" />
  </ItemGroup>
</Project>
'''


def main():
    if not SCRIPT.exists():
        print(f"FAIL: script not found at {SCRIPT}")
        return 1

    WORK.mkdir(parents=True, exist_ok=True)
    (WORK / "UnityStubs.cs").write_text(STUBS, encoding="utf-8")
    (WORK / "SyntaxCheck.csproj").write_text(
        CSPROJ.replace("{script}", str(SCRIPT)), encoding="utf-8")

    # Clean previous output so a stale success cannot be mistaken for a fresh one.
    for d in ("bin", "obj"):
        shutil.rmtree(WORK / d, ignore_errors=True)

    print(f"compiling {SCRIPT.name} against Unity stubs...")
    r = subprocess.run(["dotnet", "build", "-c", "Release", "--nologo"],
                       cwd=str(WORK), capture_output=True, text=True, timeout=600)
    out = (r.stdout or "") + (r.stderr or "")
    print(out.strip()[-2500:])

    if r.returncode != 0:
        print(f"\nFAIL: compile gate failed (exit {r.returncode})")
        return 1

    dll = WORK / "bin" / "Release" / "net8.0" / "FloatingBrainSyntaxCheck.dll"
    if not dll.exists():
        print("\nFAIL: build reported success but produced no assembly")
        return 1

    print(f"\nPASS: compiled clean -> {dll.name} ({dll.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
