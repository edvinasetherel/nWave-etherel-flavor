#!/usr/bin/env python3
"""Build (and optionally install) the fork's nwave-ai wheel in one command.

The public checkout does not contain the generated ``lib/python/des`` directory
that the wheel force-includes; upstream's release pipeline stages it. This
script reproduces that staging so a fork build works from a plain checkout:

  1. scripts/build_dist.py            → dist/ (DES module with rewritten imports)
  2. dist/lib/python/des              → lib/python/des (wheel force-include source)
  3. uv build --wheel                 → dist/wheels/nwave_ai-<version>-py3-none-any.whl
  4. (--install) uv tool install --reinstall <wheel>, nwave-ai install, nwave-ai doctor

Usage:
    python scripts/build_fork.py
    python scripts/build_fork.py --install
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DIST_DIR = PROJECT_ROOT / "dist"
WHEEL_DIR = DIST_DIR / "wheels"
STAGED_DES_SOURCE = DIST_DIR / "lib" / "python" / "des"
STAGED_DES_TARGET = PROJECT_ROOT / "lib" / "python" / "des"


class BuildError(Exception):
    """A build step failed; the message says which one and why."""


def require_tool(name: str) -> str:
    """Return the absolute path of an executable on PATH, or fail with guidance."""
    path = shutil.which(name)
    if path is None:
        raise BuildError(f"'{name}' was not found on PATH.")
    return path


def run_step(title: str, command: list[str]) -> None:
    """Run one build step, streaming its output; fail the build on a non-zero exit."""
    print(f"\n==> {title}", flush=True)
    # UTF-8 output: the installer prints Unicode (logo, emoji) that the Windows
    # default cp1252 encoding cannot write when output is piped or redirected.
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
    result = subprocess.run(command, cwd=PROJECT_ROOT, env=env, check=False)
    if result.returncode != 0:
        raise BuildError(f"{title} failed (exit {result.returncode}).")


def stage_des_module() -> None:
    """Copy the built DES module to the path the wheel force-includes."""
    print("\n==> Staging DES module for the wheel", flush=True)
    if not STAGED_DES_SOURCE.is_dir():
        raise BuildError(f"Expected built DES module at {STAGED_DES_SOURCE}.")
    if STAGED_DES_TARGET.exists():
        shutil.rmtree(STAGED_DES_TARGET)
    shutil.copytree(STAGED_DES_SOURCE, STAGED_DES_TARGET)


def build_wheel(uv: str) -> Path:
    """Build the wheel into a clean directory and return its path."""
    if WHEEL_DIR.exists():
        shutil.rmtree(WHEEL_DIR)
    run_step("Building wheel", [uv, "build", "--wheel", "--out-dir", str(WHEEL_DIR)])
    wheels = sorted(WHEEL_DIR.glob("nwave_ai-*.whl"))
    if len(wheels) != 1:
        raise BuildError(
            f"Expected exactly one wheel in {WHEEL_DIR}, found {len(wheels)}."
        )
    return wheels[0]


def install_wheel(uv: str, wheel: Path) -> None:
    """Install the wheel as a uv tool, deploy the framework, and run the health check."""
    run_step(
        "Installing nwave-ai from the fork wheel",
        [uv, "tool", "install", "--reinstall", str(wheel)],
    )
    nwave_ai = shutil.which("nwave-ai")
    if nwave_ai is None:
        raise BuildError(
            "nwave-ai was installed but is not on PATH yet. Run 'uv tool update-shell', open a new shell, then 'nwave-ai install'."
        )
    run_step("Deploying the framework (nwave-ai install)", [nwave_ai, "install"])
    run_step("Checking the installation (nwave-ai doctor)", [nwave_ai, "doctor"])


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build (and optionally install) the fork's nwave-ai wheel."
    )
    parser.add_argument(
        "--install",
        action="store_true",
        help="After building, install the wheel with uv, run 'nwave-ai install' and 'nwave-ai doctor'.",
    )
    args = parser.parse_args()

    try:
        uv = require_tool("uv")
        run_step(
            "Building dist/ from source",
            [sys.executable, str(PROJECT_ROOT / "scripts" / "build_dist.py")],
        )
        stage_des_module()
        wheel = build_wheel(uv)
        print(f"\nBuilt {wheel.relative_to(PROJECT_ROOT)}")
        if args.install:
            install_wheel(uv, wheel)
            print("\nFork installed. Restart Claude Code to pick up the changes.")
    except BuildError as error:
        print(f"\nError: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
