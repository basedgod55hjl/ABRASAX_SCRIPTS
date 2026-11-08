"""Teach the Roslyn stub about UnityEngine.Events.

The stub did not model the UnityEngine.Events namespace, so a missing
`using UnityEngine.Events;` sailed through the stub check and only the real Unity
compiler caught it. The stub should model the namespace that actually exists in
Unity, otherwise it gives false confidence.

Moves UnityEvent out of UnityEngine into UnityEngine.Events, matching Unity.
Idempotent.
"""
import sys

PATH = r"C:\ABRASAX\SCRIPTS\automation\check_unity_script.py"
src = open(PATH, encoding="utf-8").read()

if "namespace UnityEngine.Events" in src:
    print("ALREADY-PATCHED")
    sys.exit(0)

OLD = """    [Serializable]
    public class UnityEvent
    {
        public void Invoke() { }
        public void AddListener(Action a) { }
        public void RemoveListener(Action a) { }
    }
}
"""

NEW = """}

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
"""

if OLD not in src:
    print("ANCHOR-NOT-FOUND: UnityEvent stub block")
    sys.exit(1)

src = src.replace(OLD, NEW, 1)
open(PATH, "w", encoding="utf-8", newline="").write(src)
print("PATCHED: UnityEvent moved to UnityEngine.Events in the stub")
