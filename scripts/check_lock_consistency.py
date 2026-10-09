#!/usr/bin/env python3
"""
Fail if a package is locked at different versions in the `default` and `develop` sections of Pipfile.lock.

CI tests run with `pipenv sync --dev`, where the `develop` version wins, but the production image only installs
`default`. A mismatch means the tests don't exercise what ships (eg Dependabot bumping `django` in `default` only).
"""

import json
import sys
from pathlib import Path

lock_path = Path(__file__).resolve().parent.parent / "Pipfile.lock"
lock = json.loads(lock_path.read_text())

default, develop = lock["default"], lock["develop"]
mismatches = sorted(
    (name, default[name].get("version"), develop[name].get("version"))
    for name in default.keys() & develop.keys()
    if default[name].get("version") != develop[name].get("version")
)

if mismatches:
    print(
        "Pipfile.lock: packages locked at different versions in `default` and `develop`:"
    )
    for name, default_version, develop_version in mismatches:
        print(f"  {name}: default {default_version}, develop {develop_version}")
    print("Re-lock with `pipenv lock` so both sections agree.")
    sys.exit(1)

print(
    f"Pipfile.lock: {len(default.keys() & develop.keys())} shared packages, all consistent"
)
