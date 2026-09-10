"""
Blender subprocess helpers for the rule workshop (no Streamlit / no bpy).

Build:  generate.py → .blend
Preview: examples/_render_preview.py → .png
"""
from __future__ import annotations

import os
import shutil
import subprocess
from typing import List, Optional, Tuple


def repo_root() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def find_blender(explicit: Optional[str] = None) -> Optional[str]:
    if explicit:
        return shutil.which(explicit) or (explicit if os.path.isfile(explicit) else None)
    env = os.environ.get("BLENDER_EXECUTABLE")
    if env:
        found = shutil.which(env)
        if found:
            return found
        if os.path.isfile(env):
            return env
    return shutil.which("blender")


def generate_cmd(
    blender: str,
    rule_path: str,
    blend_out: str,
    *,
    seed: Optional[int] = None,
    width: float = 20.0,
    depth: float = 10.0,
    generate_script: Optional[str] = None,
) -> List[str]:
    root = repo_root()
    script = generate_script or os.path.join(root, "generate.py")
    cmd = [
        blender,
        "--background",
        "--factory-startup",
        "--python",
        os.path.abspath(script),
        "--",
        "--rule",
        os.path.abspath(rule_path),
        "--output",
        os.path.abspath(blend_out),
        "--width",
        str(width),
        "--depth",
        str(depth),
    ]
    if seed is not None:
        cmd.extend(["--seed", str(seed)])
    return cmd


def preview_cmd(
    blender: str,
    blend_path: str,
    png_out: str,
    *,
    width: int = 1280,
    height: int = 720,
    preview_script: Optional[str] = None,
) -> List[str]:
    root = repo_root()
    script = preview_script or os.path.join(root, "examples", "_render_preview.py")
    return [
        blender,
        "--background",
        os.path.abspath(blend_path),
        "--python",
        os.path.abspath(script),
        "--",
        "--output",
        os.path.abspath(png_out),
        "--width",
        str(width),
        "--height",
        str(height),
    ]


def _run(cmd: List[str], timeout_sec: int, cwd: Optional[str] = None) -> Tuple[bool, str, str]:
    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd or repo_root(),
            capture_output=True,
            text=True,
            timeout=timeout_sec,
        )
    except subprocess.TimeoutExpired as e:
        return (
            False,
            e.stdout or "",
            (e.stderr or "") + "\nTimed out after %ds" % timeout_sec,
        )
    except FileNotFoundError as e:
        return False, "", str(e)
    return proc.returncode == 0, proc.stdout or "", proc.stderr or ""


def run_generate(
    blender: str,
    rule_path: str,
    blend_out: str,
    *,
    seed: Optional[int] = None,
    width: float = 20.0,
    depth: float = 10.0,
    timeout_sec: int = 180,
) -> Tuple[bool, str, str]:
    return _run(
        generate_cmd(blender, rule_path, blend_out, seed=seed, width=width, depth=depth),
        timeout_sec,
    )


def run_preview(
    blender: str,
    blend_path: str,
    png_out: str,
    *,
    width: int = 1280,
    height: int = 720,
    timeout_sec: int = 180,
) -> Tuple[bool, str, str]:
    return _run(
        preview_cmd(blender, blend_path, png_out, width=width, height=height),
        timeout_sec,
    )
