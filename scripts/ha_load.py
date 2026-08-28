#!/usr/bin/env python3
"""Load the custom integration if Home Assistant is installed."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve()
while ROOT != ROOT.parent:
    if (ROOT / "pyproject.toml").is_file():
        break
    ROOT = ROOT.parent
else:
    raise SystemExit("pyproject.toml not found")

component = ROOT / "custom_components" / "sp_group"
required = [
    component / "manifest.json",
    component / "config_flow.py",
    component / "sensor.py",
    component / "client.py",
    component / "mapper.py",
    component / "coordinator.py",
    component / "entity.py",
    component / "diagnostics.py",
    component / "icons.json",
    component / "strings.json",
]
missing = [str(path) for path in required if not path.is_file()]
print(f"integration_files_ok={not missing}")
if missing:
    print("missing=" + json.dumps(missing))
    raise SystemExit(1)
manifest = json.loads((component / "manifest.json").read_text())
print(f"domain={manifest['domain']}")
print(f"config_flow={manifest['config_flow']}")
print(f"version={manifest['version']}")

try:
    import homeassistant  # noqa: F401
except ImportError as exc:
    print(f"homeassistant_import=failed ({exc})")
    raise SystemExit(0) from None

sys.path.insert(0, str(ROOT))
from custom_components.sp_group import DOMAIN, PLATFORMS  # noqa: E402

print(f"homeassistant_import=ok domain={DOMAIN} platforms={PLATFORMS}")
