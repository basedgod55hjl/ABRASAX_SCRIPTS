import sys
sys.path.insert(0, r"C:\ABRASAX")
from abrasax.live_imu import LiveImu
from abrasax.adb_sensors import AdbSensorReader

i = LiveImu(serial="R5CY308WZVK")
print("live_imu status:", i.status())
s = i.sample()
if s:
    print("  origin:", s["origin"], "| heading:", s["heading_deg"], "| rate_hz:", s["rate_hz"])
    print("  accel:", [round(v, 2) for v in s["imu"][:3]])
    print("  gyro :", [round(v, 3) for v in s["imu"][3:6]])
    print("  mag  :", [round(v, 1) for v in s["mag"]])
    print("  measured_fields:", s["measured_fields"])
else:
    print("  NO SAMPLE")

r = AdbSensorReader(serial="R5CY308WZVK")
print("adb_sensors status:", r.status())
d = r.sample()
if d:
    print("  env(hPa,lux):", d["env"], "| fields:", d["measured_fields"])
    print("  derived:", d.get("derived"))
