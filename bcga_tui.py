"""
BCGA TUI -- a terminal UI for iterating on rule files without opening
Blender's GUI each time. Builds directly on:
  - generate.py (the headless CLI entry point)
  - pro/base.py's Rule.to_dict()/tracing (the resolved building trace)

Usage:
    python3 bcga_tui.py [rules_directory]

Requires the `rich` package (pip install rich) and a `blender` executable
on PATH (or set the BLENDER_EXECUTABLE environment variable).

Design note: the interactive parts (menus/prompts) are kept thin and
separate from the actual logic (find_blender, list_rule_files,
run_generation, build_trace_tree) so the logic can be unit tested without
a live terminal -- see the test suite used to validate this file.
"""
import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, IntPrompt, Confirm
from rich.table import Table
from rich.tree import Tree

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
GENERATE_SCRIPT = os.path.join(REPO_ROOT, "generate.py")

console = Console()


def find_blender():
    """Locates a Blender executable, or None if none can be found."""
    envPath = os.environ.get("BLENDER_EXECUTABLE")
    if envPath and shutil.which(envPath):
        return envPath
    return shutil.which("blender")


def list_rule_files(rulesDir):
    """Returns a sorted list of .py rule files in rulesDir (non-recursive)."""
    if not os.path.isdir(rulesDir):
        return []
    return sorted(
        p for p in glob.glob(os.path.join(rulesDir, "*.py"))
        if os.path.isfile(p)
    )


def run_generation(blenderExe, ruleFile, outputPath, count=1, seed=None,
                    width=20, depth=10, spacing=5, jsonPath=None, timeoutSec=180):
    """
    Runs generate.py headlessly via a real Blender subprocess.
    Returns (success: bool, stdout: str, stderr: str).
    """
    cmd = [
        blenderExe, "--background", "--factory-startup", "--python", GENERATE_SCRIPT, "--",
        "--rule", ruleFile, "--output", outputPath,
        "--count", str(count), "--width", str(width), "--depth", str(depth),
        "--spacing", str(spacing),
    ]
    if seed is not None:
        cmd += ["--seed", str(seed)]
    if jsonPath:
        cmd += ["--export-json", jsonPath]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeoutSec)
    except subprocess.TimeoutExpired as e:
        return False, e.stdout or "", (e.stderr or "") + "\nTimed out after %ds" % timeoutSec
    except FileNotFoundError as e:
        return False, "", str(e)
    return proc.returncode == 0, proc.stdout, proc.stderr


def build_trace_tree(node, label=None):
    """
    Converts a resolved building trace dict (from Rule.to_dict()) into a
    rich.tree.Tree for pretty terminal display. Pure/no I/O, so it's
    unit-testable against a plain dict.
    """
    if not isinstance(node, dict):
        return Tree(str(node))

    nodeType = node.get("type", "Node")
    if nodeType == "Rule":
        title = "[bold cyan]%s[/bold cyan]" % node.get("rule", "Rule")
        if "value" in node:
            title += "  [dim]<- %s[/dim]" % node["value"]
    else:
        title = "[green]%s[/green]" % nodeType
        # show a few interesting scalar attrs inline, skip noisy/nested ones
        skipKeys = {"type", "children", "parts"}
        bits = []
        for k, v in node.items():
            if k in skipKeys:
                continue
            if isinstance(v, (int, float, str, bool)):
                bits.append("%s=%s" % (k, v))
        if bits:
            title += "  [dim](%s)[/dim]" % ", ".join(bits)

    tree = Tree(title) if label is None else Tree("[bold]%s[/bold]" % label)
    if label is not None:
        child = tree.add(title)
    else:
        child = tree

    for part in node.get("parts", []):
        child.add(build_trace_tree(part))
    for c in node.get("children", []):
        child.add(build_trace_tree(c))

    return tree


def _select_rule_file(rulesDir):
    files = list_rule_files(rulesDir)
    if not files:
        console.print("[red]No .py rule files found in %s[/red]" % rulesDir)
        manual = Prompt.ask("Enter a rule file path directly (or leave blank to cancel)", default="")
        return manual or None

    table = Table(title="Available rule files")
    table.add_column("#", justify="right")
    table.add_column("File")
    for i, f in enumerate(files, 1):
        table.add_row(str(i), os.path.relpath(f, rulesDir))
    console.print(table)

    choice = Prompt.ask(
        "Pick a rule file by number, or enter a path directly",
        default="1",
    )
    if choice.isdigit() and 1 <= int(choice) <= len(files):
        return files[int(choice) - 1]
    return choice


def main():
    console.print(Panel.fit("[bold]BCGA TUI[/bold]\nIterate on rule files without opening Blender's GUI", border_style="cyan"))

    blenderExe = find_blender()
    if not blenderExe:
        console.print("[red]Could not find a `blender` executable on PATH.[/red]")
        console.print("Set the BLENDER_EXECUTABLE environment variable, or add Blender to PATH.")
        sys.exit(1)
    console.print("Using Blender: [green]%s[/green]" % blenderExe)

    rulesDir = sys.argv[1] if len(sys.argv) > 1 else REPO_ROOT
    ruleFile = _select_rule_file(rulesDir)
    if not ruleFile or not os.path.isfile(ruleFile):
        console.print("[red]No valid rule file selected.[/red]")
        sys.exit(1)

    count = IntPrompt.ask("How many variants?", default=1)
    seed = IntPrompt.ask("Random seed (blank for random)", default=None, show_default=False) \
        if Confirm.ask("Use a fixed seed for reproducibility?", default=False) else None
    width = IntPrompt.ask("Footprint width (m)", default=20)
    depth = IntPrompt.ask("Footprint depth (m)", default=10)

    outDir = tempfile.mkdtemp(prefix="bcga_tui_")
    outputPath = os.path.join(outDir, "building.blend")
    jsonPath = os.path.join(outDir, "trace.json")

    with console.status("[cyan]Running Blender headlessly...[/cyan]"):
        ok, stdout, stderr = run_generation(
            blenderExe, ruleFile, outputPath,
            count=count, seed=seed, width=width, depth=depth, jsonPath=jsonPath,
        )

    if not ok:
        console.print("[red]Generation failed:[/red]")
        console.print(stderr or stdout)
        sys.exit(1)

    console.print("[green]Generated %d building(s):[/green] %s" % (count, outputPath))

    if os.path.isfile(jsonPath):
        with open(jsonPath) as f:
            trace = json.load(f)
        buildings = trace if isinstance(trace, list) else [trace]
        for i, building in enumerate(buildings):
            console.print(build_trace_tree(building, label="Building %d" % i if count > 1 else None))


if __name__ == "__main__":
    main()
