"""
BCGA rule workshop: paste/upload a rule → .blend + PNG preview → optional town library.

    streamlit run streamlit_app/rule_workshop.py

Needs Blender on PATH (or BLENDER_EXECUTABLE). No Gemini key required.
"""
from __future__ import annotations

import os
import sys
import tempfile

import streamlit as st

# Allow importing sibling modules and repo packages
_APP_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.abspath(os.path.join(_APP_DIR, ".."))
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from blender_jobs import find_blender, run_generate, run_preview  # noqa: E402
from dsl_generator import RuleFileError, validate_rule_file  # noqa: E402
from pro.city.building_rules import (  # noqa: E402
    default_rules_dir,
    list_building_rules,
    save_rule_to_pool,
)

st.set_page_config(page_title="BCGA rule workshop", layout="wide")
st.title("BCGA rule workshop")
st.caption(
    "Paste or upload a building DSL (`.py`), build a Blender file, render a preview, "
    "and optionally save the rule into the town pool used by `run_random_city.py`."
)

MINIMAL_EXAMPLE = '''from pro import *

@rule
def Begin():
    color("#b8895a")
    extrude(random(6, 10))
    try:
        hip_roof(32, 0.35)
    except Exception:
        pass
'''

with st.sidebar:
    st.header("Blender")
    default_blender = find_blender() or ""
    blender_path = st.text_input(
        "Blender executable",
        value=default_blender,
        help="Defaults from BLENDER_EXECUTABLE or PATH.",
    )
    seed_raw = st.text_input("Seed (optional)", value="")
    seed = int(seed_raw) if seed_raw.strip().lstrip("-").isdigit() else None
    preview_w = st.number_input("Preview width", min_value=320, max_value=3840, value=1280, step=160)
    preview_h = st.number_input("Preview height", min_value=240, max_value=2160, value=720, step=90)
    timeout_sec = st.number_input("Timeout (seconds)", min_value=30, max_value=900, value=240, step=30)
    st.info(
        "Default footprint is **20×10 m** unless your rule calls "
        "`rectangle(w, d, …)` and `delete()` itself."
    )
    pool = default_rules_dir(_REPO_ROOT)
    st.caption("Town library: `%s` (%d rules)" % (pool, len(list_building_rules(pool))))

uploaded = st.file_uploader("Upload rule .py", type=["py"])
source = st.text_area(
    "Or paste rule source",
    value=MINIMAL_EXAMPLE if uploaded is None else "",
    height=320,
)
if uploaded is not None:
    source = uploaded.getvalue().decode("utf-8")

col_a, col_b = st.columns(2)
build_clicked = col_a.button("Build & preview", type="primary")
save_clicked = col_b.button("Save to town library")

if "workshop" not in st.session_state:
    st.session_state.workshop = {}


def _build_and_preview(rule_source: str) -> dict:
    blender = find_blender(blender_path.strip() or None)
    if not blender:
        raise RuntimeError(
            "Blender not found. Set BLENDER_EXECUTABLE or enter a path in the sidebar."
        )
    try:
        validate_rule_file(rule_source)
    except RuleFileError as e:
        raise RuntimeError("Rule validation failed:\n%s" % e) from e

    tmp = tempfile.mkdtemp(prefix="bcga_workshop_")
    rule_path = os.path.join(tmp, "rule.py")
    blend_path = os.path.join(tmp, "building.blend")
    png_path = os.path.join(tmp, "preview.png")
    with open(rule_path, "w", encoding="utf-8") as f:
        f.write(rule_source)

    ok, out, err = run_generate(
        blender, rule_path, blend_path, seed=seed, timeout_sec=int(timeout_sec)
    )
    if not ok or not os.path.isfile(blend_path):
        raise RuntimeError("generate.py failed:\n%s\n%s" % (out, err))

    ok, out2, err2 = run_preview(
        blender,
        blend_path,
        png_path,
        width=int(preview_w),
        height=int(preview_h),
        timeout_sec=int(timeout_sec),
    )
    if not ok or not os.path.isfile(png_path):
        raise RuntimeError("preview render failed:\n%s\n%s" % (out2, err2))

    return {
        "tmpdir": tmp,
        "rule_path": rule_path,
        "blend_path": blend_path,
        "png_path": png_path,
        "source": rule_source,
        "log": (out or "") + "\n" + (err or "") + "\n" + (out2 or "") + "\n" + (err2 or ""),
    }


if build_clicked:
    if not (source or "").strip():
        st.error("Provide rule source (upload or paste).")
    else:
        with st.spinner("Building in Blender and rendering preview…"):
            try:
                st.session_state.workshop = _build_and_preview(source)
                st.success("Build + preview complete.")
            except Exception as e:
                st.session_state.workshop = {}
                st.error(str(e))

ws = st.session_state.workshop
if ws.get("png_path") and os.path.isfile(ws["png_path"]):
    st.subheader("Preview")
    st.image(ws["png_path"], use_container_width=True)
    c1, c2, c3 = st.columns(3)
    with open(ws["png_path"], "rb") as f:
        c1.download_button("Download PNG", f, file_name="preview.png", mime="image/png")
    with open(ws["blend_path"], "rb") as f:
        c2.download_button(
            "Download .blend", f, file_name="building.blend", mime="application/octet-stream"
        )
    c3.download_button(
        "Download rule.py",
        ws.get("source") or source,
        file_name="rule.py",
        mime="text/x-python",
    )
    with st.expander("Blender log"):
        st.code(ws.get("log") or "")

if save_clicked:
    src = (ws.get("source") if ws else None) or source
    if not (src or "").strip():
        st.error("Nothing to save — paste a rule or build first.")
    else:
        try:
            validate_rule_file(src)
            path = save_rule_to_pool(src, rules_dir=default_rules_dir(_REPO_ROOT), start_at=20)
            st.success(
                "Saved to town library as `%s`. "
                "`run_random_city.py` will pick it up on the next run."
                % path
            )
        except RuleFileError as e:
            st.error("Cannot save — validation failed:\n%s" % e)
        except Exception as e:
            st.error(str(e))
