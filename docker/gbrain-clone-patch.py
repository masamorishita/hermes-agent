#!/usr/bin/env python3
"""Idempotent ZeroEntropy/Voyage clone() truncation fix for gbrain (railway branch, BIZ-43).

Mirrors the ssh-air auto-update hook (auto-update-gbrain-gstack.sh): bun < 1.1.27
truncates Response.clone() large bodies, breaking multi-chunk embeds with
"Invalid JSON response". We pin bun 1.0.36 (to match air), so this fix is
required. It is idempotent and becomes a no-op once upstream merges the fix
(the resp.clone().json() pattern disappears).

Usage: gbrain-clone-patch.py <path-to-gateway.ts>
"""
import sys

path = sys.argv[1] if len(sys.argv) > 1 else "src/core/ai/gateway.ts"
try:
    s = open(path).read()
except FileNotFoundError:
    print(f"[gbrain-patch] {path} not found; skipping")
    sys.exit(0)

orig = s
s = s.replace("await resp.clone().json()", "await resp.json()")
s = s.replace(
    "      headers: resp.headers,",
    '      headers: (() => { const _h = new Headers(resp.headers); '
    '_h.delete("content-length"); _h.delete("content-encoding"); '
    '_h.delete("transfer-encoding"); return _h; })(),',
)
if s != orig:
    open(path, "w").write(s)
    print("[gbrain-patch] applied clone() truncation fix")
else:
    print("[gbrain-patch] no changes (already patched or upstream merged)")
