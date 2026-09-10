"""Command construction for Streamlit Blender jobs (no Blender required)."""
import os

from streamlit_app.blender_jobs import generate_cmd, preview_cmd, repo_root


def test_generate_cmd_has_separator_and_abspaths(tmp_path):
    rule = str(tmp_path / "rule.py")
    out = str(tmp_path / "out.blend")
    open(rule, "w").write("x")
    cmd = generate_cmd("blender", rule, out, seed=7)
    assert cmd[0] == "blender"
    assert "--background" in cmd
    assert "--factory-startup" in cmd
    assert "--" in cmd
    assert cmd[cmd.index("--") + 1] == "--rule"
    assert os.path.isabs(cmd[cmd.index("--rule") + 1])
    assert os.path.isabs(cmd[cmd.index("--output") + 1])
    assert cmd[cmd.index("--seed") + 1] == "7"
    assert os.path.basename(cmd[cmd.index("--python") + 1]) == "generate.py"


def test_preview_cmd_opens_blend_then_script(tmp_path):
    blend = str(tmp_path / "b.blend")
    png = str(tmp_path / "p.png")
    open(blend, "w").write("x")
    cmd = preview_cmd("blender", blend, png, width=800, height=600)
    assert cmd[0] == "blender"
    assert "--background" in cmd
    assert os.path.abspath(blend) in cmd
    assert "--python" in cmd
    assert cmd[cmd.index("--python") + 1].endswith("_render_preview.py")
    assert "--" in cmd
    assert cmd[cmd.index("--output") + 1] == os.path.abspath(png)
    assert cmd[cmd.index("--width") + 1] == "800"


def test_repo_root_points_at_project():
    root = repo_root()
    assert os.path.isfile(os.path.join(root, "generate.py"))
    assert os.path.isdir(os.path.join(root, "examples"))
