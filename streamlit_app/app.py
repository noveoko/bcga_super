"""
Aerial photo -> BCGA rule file.

Upload a photo, crop to the building of interest, trace its approximate
footprint, tag a few attributes, and generate a runnable rule (.py) file
via the Gemini API -- built on the operator contract already documented in
examples/IMAGE_TO_RULE_PROMPT.md, and statically validated (see
dsl_generator.validate_rule_file) before you ever see it.

Run with:
    streamlit run streamlit_app/app.py

Needs a Gemini API key: set GEMINI_API_KEY, or paste one into the sidebar
for this session only (never written to disk).
"""
import io
import os

import streamlit as st
from PIL import Image
from streamlit_drawable_canvas import st_canvas

from dsl_generator import (
    RuleFileError,
    footprint_bbox_size_m,
    generate_rule_file,
    pixel_polygon_to_meters,
)

st.set_page_config(page_title="Aerial photo -> BCGA rule", layout="wide")
st.title("Aerial photo -> BCGA rule file")
st.caption(
    "Upload a photo, crop to one building, trace its approximate footprint, "
    "tag what you know, and generate a runnable rule file."
)

ROLES = ["house", "apartment", "church", "barn", "shed", "warehouse", "shop", "civic", "other"]
MATERIALS = ["brick", "stone", "wood", "stucco/plaster", "concrete", "corrugated metal", "unknown"]
PHASES = ["built", "initial", "construction", "damaged", "destroyed", "aged"]

if "footprint_pts" not in st.session_state:
    st.session_state.footprint_pts = []


def _reset_footprint():
    st.session_state.footprint_pts = []


with st.sidebar:
    st.header("Gemini API key")
    api_key = st.text_input(
        "API key", value=os.environ.get("GEMINI_API_KEY", ""), type="password",
        help="Used only for this session, never written to disk. Get one at "
             "https://aistudio.google.com/apikey",
    )
    model_name = st.selectbox("Model", ["gemini-2.5-pro", "gemini-2.5-flash"], index=0)
    max_repair_attempts = st.slider(
        "Auto-repair attempts", 0, 3, 1,
        help="If the model's first attempt fails validation, send it the specific "
             "problems found and ask for a fix, up to this many times.",
    )

st.subheader("1. Upload and crop")
uploaded = st.file_uploader("Aerial or street photo", type=["png", "jpg", "jpeg"])

if uploaded is None:
    st.info("Upload a photo to get started.")
    st.stop()

image = Image.open(uploaded).convert("RGB")
st.write("Drag the corners of the box below to isolate the building of interest.")

# A lightweight crop UI: reuse the same canvas component for a single
# draggable rectangle rather than pulling in a second cropping dependency.
crop_canvas = st_canvas(
    fill_color="rgba(255, 165, 0, 0.15)",
    stroke_width=2,
    stroke_color="#ff8800",
    background_image=image,
    update_streamlit=True,
    height=min(image.height, 600),
    width=min(image.width, 900),
    drawing_mode="rect",
    key="crop_canvas",
)

crop_box = None
if crop_canvas.json_data is not None and crop_canvas.json_data.get("objects"):
    obj = crop_canvas.json_data["objects"][-1]  # most recent rectangle
    scale_x = image.width / crop_canvas.image_data.shape[1] if crop_canvas.image_data is not None else 1.0
    scale_y = image.height / crop_canvas.image_data.shape[0] if crop_canvas.image_data is not None else 1.0
    x0 = obj["left"] * scale_x
    y0 = obj["top"] * scale_y
    x1 = x0 + obj["width"] * obj.get("scaleX", 1.0) * scale_x
    y1 = y0 + obj["height"] * obj.get("scaleY", 1.0) * scale_y
    crop_box = (max(0, int(x0)), max(0, int(y0)), min(image.width, int(x1)), min(image.height, int(y1)))

if crop_box is None:
    st.warning("Draw a rectangle on the photo to select the building, then continue.")
    st.stop()

cropped = image.crop(crop_box)
st.image(cropped, caption="Cropped to building of interest", width=400)

st.subheader("2. Trace the approximate footprint")
st.write(
    "Click each corner of the building's footprint, in order, on the cropped "
    "image below (roofline is usually the best guide on an aerial shot)."
)

col_a, col_b = st.columns([3, 1])
with col_a:
    footprint_canvas = st_canvas(
        fill_color="rgba(0, 140, 255, 0.2)",
        stroke_width=3,
        stroke_color="#0088ff",
        background_image=cropped,
        update_streamlit=True,
        height=cropped.height,
        width=cropped.width,
        drawing_mode="point",
        point_display_radius=5,
        key="footprint_canvas",
    )
with col_b:
    st.button("Clear points", on_click=_reset_footprint)
    longest_side_m = st.number_input(
        "Longest side of the building, in meters (your best estimate)",
        min_value=1.0, max_value=200.0, value=12.0, step=0.5,
        help="The traced shape is scaled so its longest bounding-box side "
             "equals this. Everything else (area, other side) follows from "
             "the shape you traced, not a second guess.",
    )

footprint_pts_px = []
if footprint_canvas.json_data is not None:
    for obj in footprint_canvas.json_data.get("objects", []):
        if obj.get("type") == "circle":
            footprint_pts_px.append((obj["left"] + obj["radius"], obj["top"] + obj["radius"]))

if len(footprint_pts_px) < 3:
    st.warning("Click at least 3 corners to define a footprint.")
    st.stop()

footprint_m = pixel_polygon_to_meters(footprint_pts_px, longest_side_m)
w_m, d_m = footprint_bbox_size_m(footprint_m)
st.success("Footprint: %d points traced, ~%.1f m x %.1f m bounding box." % (len(footprint_m), w_m, d_m))

st.subheader("3. What do you already know?")
c1, c2, c3 = st.columns(3)
with c1:
    storeys = st.number_input("Floors / storeys", min_value=1, max_value=20, value=2, step=1)
    role = st.selectbox("Building type", ROLES, index=0)
with c2:
    material = st.selectbox("Primary material", MATERIALS, index=6)
with c3:
    phase = st.selectbox("Condition / phase", PHASES, index=0)
notes = st.text_area("Anything else worth telling the model (optional)", "")

st.subheader("4. Generate")
if st.button("Generate rule file", type="primary", disabled=not api_key):
    buf = io.BytesIO()
    cropped.save(buf, format="PNG")
    with st.spinner("Calling Gemini and validating the result..."):
        try:
            source = generate_rule_file(
                buf.getvalue(), "image/png", footprint_m,
                storeys=storeys, role=role,
                material=None if material == "unknown" else material,
                phase=phase, notes=notes or None,
                api_key=api_key, model=model_name,
                max_repair_attempts=max_repair_attempts,
            )
        except RuleFileError as e:
            st.error("Generation failed validation after all repair attempts:")
            for p in e.problems:
                st.write("- " + p)
            st.stop()
        except Exception as e:  # network/API errors, missing google-genai, etc.
            st.error("Generation failed: %s" % e)
            st.stop()

    st.success("Rule file generated and passed validation.")
    st.code(source, language="python")
    st.download_button("Download rule.py", source, file_name="rule.py", mime="text/x-python")
    st.subheader("5. Build it")
    st.code(
        "blender --background --factory-startup --python generate.py -- "
        "--rule rule.py --output out/building.blend",
        language="bash",
    )
