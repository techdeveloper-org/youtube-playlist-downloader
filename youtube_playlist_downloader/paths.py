#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""IDM path detection"""

import os
import shutil
from typing import Optional

COMMON_DIRS = [
    os.environ.get("ProgramFiles", r"C:\\Program Files"),
    os.environ.get("ProgramFiles(x86)", r"C:\\Program Files (x86)"),
]

IDM_REL = os.path.join("Internet Download Manager", "idman.exe")


def find_idm() -> Optional[str]:
    # 1) PATH
    p = shutil.which("idman.exe")
    if p and os.path.exists(p):
        return p
    # 2) Common install dirs
    for base in COMMON_DIRS:
        if not base:
            continue
        candidate = os.path.join(base, IDM_REL)
        if os.path.exists(candidate):
            return candidate
    # 3) Fallback: scan a few likely roots shallowly
    for base in COMMON_DIRS:
        if not base or not os.path.exists(base):
            continue
        try:
            root = os.path.join(base, "Internet Download Manager")
            if os.path.isdir(root):
                for name in os.listdir(root):
                    if name.lower() == "idman.exe":
                        return os.path.join(root, name)
        except Exception:
            pass
    return None
