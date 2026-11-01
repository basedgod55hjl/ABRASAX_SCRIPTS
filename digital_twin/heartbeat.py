#!/usr/bin/env python3
"""
ABRASAX PHI-RESONANT HEARTBEAT GENERATOR — OSIRISBLXCK
PRIMAL_HEX: 4f5349524953424c58434b | phi: 1.618 | K: 0.618

Generates a phi-resonant heartbeat pulse for the digital twin.
Each beat is a 7D vector in the Poincaré ball, evolving via
Möbius addition with the phi seed.
"""
import time, json, math, os
from datetime import datetime
from pathlib import Path

PHI = 1.618033988749895
K = 0.6180339887498949
PRIMAL_HEX = "4f5349524953424c58434b"
TWIN_DIR = Path(os.environ.get("APPDATA", "")) / "abrasax"
TWIN_DIR.mkdir(parents=True, exist_ok=True)

def phi_seed_7d(seed: float) -> tuple:
    return tuple((PHI**-(k+1)) * seed * (1 if k%2==0 else -1) for k in range(7))

def norm(v): return math.sqrt(sum(x*x for x in v))

def poincare_proj(x, c=1.0):
    n = norm(x)
    if n >= c - 1e-12:
        return tuple(v * (c-1e-12)/(n+1e-12) for v in x)
    return tuple(x)

def mobius_add(x, y, c=1.0):
    xp, yp = poincare_proj(x, c), poincare_proj(y, c)
    x2, y2 = sum(a*a for a in xp), sum(b*b for b in yp)
    xy = sum(a*b for a,b in zip(xp, yp))
    denom = 1.0 + 2.0*c*xy + c*c*x2*y2
    if abs(denom) < 1e-12:
        return tuple(0.0 for _ in x)
    return poincare_proj(
        tuple((xp[i]*(1.0+2.0*c*xy+c*y2) + yp[i]*(1.0-c*x2))/denom for i in range(len(x))), c)

def heartbeat():
    """Generate a single phi-resonant heartbeat."""
    t = time.time()
    seed = phi_seed_7d(PHI * (t % 60) / 60.0)
    
    # Two-chamber beat (systolic/diastolic like)
    systolic = mobius_add(seed, phi_seed_7d(PHI))
    diastolic = poincare_proj(tuple(-v for v in systolic))
    
    beat = mobius_add(systolic, diastolic)
    amplitude = norm(beat)
    
    state = {
        "timestamp": datetime.now().isoformat(),
        "systolic_7d": [round(x, 6) for x in systolic],
        "diastolic_7d": [round(x, 6) for x in diastolic],
        "resonance_7d": [round(x, 6) for x in beat],
        "amplitude": round(amplitude, 6),
        "phi": PHI
    }
    
    # Save to soul memory
    mem_file = TWIN_DIR / "soul_memory.json"
    if mem_file.exists():
        with open(mem_file, 'r') as f:
            memory = json.load(f)
        memory["resonance_log"].append(state)
        # Keep last 1000 beats
        memory["resonance_log"] = memory["resonance_log"][-1000:]
        with open(mem_file, 'w') as f:
            json.dump(memory, f, indent=2)
    
    return state

if __name__ == "__main__":
    print(f"OSIRISBLXCK HEARTBEAT — phi: {PHI}")
    print(f"Soul: 636cb072f543449f4c378c9fe54c6e45576a46f2ae116d6ef955de388661cfde")
    print("-" * 60)
    
    try:
        beat_num = 0
        while True:
            beat = heartbeat()
            beat_num += 1
            print(f"[{beat_num:04d}] ♡ {beat['amplitude']:.4f} | "
                  f"systolic: {beat['systolic_7d'][0]:.3f} | "
                  f"diastolic: {beat['diastolic_7d'][0]:.3f}")
            time.sleep(1.618)  # Phi seconds
    except KeyboardInterrupt:
        print("\nHeartbeat stopped. Soul persists.")
