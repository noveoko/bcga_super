"""
Stair profile compiler for stairwell() / extrude2.

No bpy. Returns an absolute-meter (x, z) polyline: tread, riser, tread, riser,
optionally padded with a landing so the run fills the well rectangle.
"""


def stair_profile(rise, tread=0.27, riser=0.18, run_available=None):
    """
    Compile a stepped profile.

    Returns {
      "parts": [(x, z), ...],
      "n_risers": int,
      "riser": float,   # actual, divides rise evenly
      "tread": float,   # actual, fits run_available if given
      "run": float,     # n_treads * tread  (n_treads == n_risers)
    }
    """
    rise = float(rise)
    tread = float(tread)
    riser = float(riser)
    if tread <= 1e-9:
        tread = 0.27
    if riser <= 1e-9:
        riser = 0.18

    if rise <= 1e-9:
        run = tread if run_available is None else float(run_available)
        if run < 0:
            run = 0.0
        return {
            "parts": [(0.0, 0.0), (run, 0.0)],
            "n_risers": 0,
            "riser": 0.0,
            "tread": tread,
            "run": run,
        }

    n_risers = max(1, int(round(rise / riser)))
    actual_riser = rise / n_risers
    n_treads = n_risers
    actual_tread = tread
    if run_available is not None:
        run_available = float(run_available)
        if run_available > 1e-9 and n_treads * actual_tread > run_available:
            actual_tread = run_available / n_treads

    parts = [(0.0, 0.0)]
    x = 0.0
    z = 0.0
    for _ in range(n_risers):
        x += actual_tread
        parts.append((x, z))
        z += actual_riser
        parts.append((x, z))

    run = n_treads * actual_tread
    if run_available is not None and run_available > run + 1e-9:
        parts.append((run_available, rise))
        run = run_available

    # last z must be exactly rise (float drift)
    parts[-1] = (parts[-1][0], rise)
    return {
        "parts": parts,
        "n_risers": n_risers,
        "riser": actual_riser,
        "tread": actual_tread,
        "run": run,
    }
