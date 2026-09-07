# Walkable Unreal city from BCGA

Goal: take a generated Polish town and play it in Unreal as a third-person walker who can open doors and enter every house. Python + Blender can get most of the way; Unreal Editor Python can spawn the level; a small amount of one-time UE setup stays manual.

The current `city_latest.blend` is a **render**. It is not a game. Three geometry facts block walking today:

1. **Houses are solid.** `Begin()` does `extrude(WALL_H)` of the whole footprint, then copies interiors *inside* that volume. A capsule hits the outer box and never reaches rooms.
2. **Street doors are paint.** `Door()` on `StreetFacade` only recolors a strip. There is no hole through the outer wall.
3. **Interior “doors” are empty spans.** `openings()` leaves a 0.9×2.1m gap in partition walls, but there is no leaf mesh, no hinge, no actor.

Fix those in Blender, then export meshes + a sidecar of door/spawn transforms. Unreal imports the static world and turns the sidecar into interactable doors.

```
layout JSON  →  Blender (hollow houses, door leaves, applied roads)
             →  FBX/glTF + city_game.json
             →  UE Editor Python (import, collision, Door actors, PlayerStart)
             →  Third Person template (character, camera, input)
```

Units: BCGA is meters. Unreal is centimeters. Export with scale 100, or set the Interchange/FBX importer to “meters → cm”.

---

## What Python / Blender can do (most of the work)

### 1. Hollow shells (required)

Stop extruding the footprint as a filled prism. Build a **wall ring** of the same thickness as interior `margin` (0.18m) so the street door lines up with the corridor:

- Keep `copy(FloorSlabs())` / interiors as they are.
- `inset(0.18, cap >> delete(), side >> ExteriorWall())` on the ground footprint. Inset-without-height already emits 2-D side strips (the margin ring). `ExteriorWall` `extrude`s them to `WALL_H`.
- Roof: `copy` the outer (or inner) top at `WALL_H` and run `PitchedRoof()` there, not as the cap of a solid extrude.
- Ground-floor slab already fills the interior; the old solid core goes away.

Street door: on the **front** strip only (polygon edge 0→1), call `openings(WALL_H)` with one `Opening(width=1.15, height=2.1, offset=…)` matching the facade `Door()` bay. Other sides stay solid. Then the facade `split` for windows can still run on the extruded outer faces if we keep `front >> StreetFacade()` via `decompose` after extrude — or we accept colored bays only on the front wall’s outer face.

This is the single highest-leverage change. Without it, Unreal import is a maze of sealed boxes.

### 2. Door leaves as separate objects (required)

For every opening (street + interior), emit a **child mesh** `Door_{plot}_{i}`:

- Board 0.9×2.1×0.04m (street slightly wider).
- Object origin at the **hinge** (left or right jamb), Z-up, local +X into the swing.
- Named and collected under `Doors/`.
- Not parented in a way that FBX bakes the transform away; world transform must survive import.

Python already knows jamb positions (`decompose_spans` + wall polygon + elevation). `city_builder` / a post-pass in `bpro` can instance a cube, place it, and append a record to a list.

### 3. Game sidecar JSON (required)

Written next to the FBX, e.g. `out/city_game.json`:

```json
{
  "units": "m",
  "player_start": [x, y, z, yaw],
  "doors": [
    {
      "name": "Door_042_0",
      "location": [x, y, z],
      "hinge_axis": [0, 0, 1],
      "forward": [dx, dy, 0],
      "swing_deg": 90,
      "width": 0.9, "height": 2.1,
      "plot_id": 42, "kind": "street" | "interior"
    }
  ],
  "buildings": [{"name": "Kamienica_042", "plot_id": 42, "storeys": 2}]
}
```

Player start: on the rynek cobbles, facing a kamienica street door. Computed from layout JSON (plaza centroid + nearest plot with `frontage=shop` or `role=kamienica`).

### 4. Export hygiene (required)

`city_builder.py` today writes `.blend/.obj/.glb/.fbx` but:

- Road ribbons are **Geometry Nodes** — `bpy.ops.object.convert(target="MESH")` (or `modifier_apply`) before export or UE gets curves, not sidewalks.
- One object per house is OK (interiors are already in that mesh). Doors must stay **separate** objects.
- Apply location/rotation/scale.
- Triangulate.
- Collection names: `Buildings`, `Doors`, `Roads`, `Ground`, `Plaza`.
- Prefer **FBX** (UE Interchange is boring and reliable) or **glTF 2.0**. Datasmith is nicer for metadata but adds a Blender plugin dependency; FBX + JSON is enough.
- Optional: `UCX_` collision hulls. For walkable interiors, **complex-as-simple** on the house mesh is the right default (stairs and door holes are concave). Doors get a simple box collision that moves with the actor.

### 5. What we should not do in Blender

- Character controller, input, camera.
- Navmesh (UE Recast).
- Lumen / lighting bake (optional later).
- LODs beyond a single generated mesh (257 houses × ~800 verts is already light).

---

## What Unreal Editor Python can do

UE5 has `import unreal` in the editor and `-ExecutePythonScript=` on the command line. That is enough for a repeatable import **once a .uproject exists**.

### One-time manual project (not worth generating)

1. Create a project from the **Third Person** template (capsule, camera, input mapping, GameMode).
2. Enable **Editor Scripting** + **Python Editor Script Plugin**.
3. One Blueprint `BP_CityDoor`: static mesh component, `CanEverAffectNavigation`, overlap/line-trace interact, timeline rotate yaw 0→90 around local Z, block on close. ~30 nodes, or a short C++ actor. Python can *spawn* it; authoring the BP once in the UI is faster.

### Repeatable Python (the extension)

`ue/import_city.py` (runs inside the editor):

1. `AssetImportTask` / Interchange import of `city.fbx` into `/Game/City/Meshes`.
2. Spawn `StaticMeshActor`s for buildings, roads, ground. Set **Collision Complexity = Use Complex Collision As Simple**, Query+Physics.
3. For each `doors[]` entry: spawn `BP_CityDoor` at the converted transform (m→cm, Y-up/Z-up). Assign the imported door mesh. Set swing axis from JSON.
4. Spawn `PlayerStart` from `player_start`.
5. Build navmesh bounds around the city radius (optional; the player does not need it).
6. Save the persistent level.

Coordinate conversion (Blender Z-up, meters → UE Z-up, cm): `(X, Y, Z)_ue = (X, -Y, Z) * 100` if using FBX “experimental” Blender profile, **or** `(X, Y, Z)*100` if the exporter already flips. The importer script should have a `--axis` dry-run that dumps one door at a known plot so we can lock the convention on the first house.

Command-line (after the .uproject exists):

```
UnrealEditor-Cmd.exe CityGame.uproject -unattended -ExecutePythonScript="ue/import_city.py --fbx ... --json ..."
```

No official “generate a whole Third Person game from scratch” API; the template + this script is the intended split.

---

## Playability checklist (after hollow + doors)

| Piece | Status after the work above |
|---|---|
| Walk streets | Ground disk + road meshes, complex collision |
| Enter from street | Front-wall opening + street door actor |
| Walk rooms | Interior floors + pier/lintel walls, capsule 0.42m fits 0.9m doors and 1.15m corridor |
| Stairs | Existing `stairwell` mesh; complex collision; 1.05m well is tight but walkable |
| Interior doors | Leaf actors on partition gaps |
| Church/synagogue | Still solid / no interior (current skip) — leave as landmarks or hollow later |
| 257 houses | Fine as one level (~0.3 km). World Partition not required |

---

## Manual steps we should keep

- Create the UE Third Person project once.
- Author `BP_CityDoor` once (interact + swing).
- Assign a floor/wall material if vertex colors look flat in Lumen (optional).
- Place extra lights inside if interiors are too dark (or enable Lumen + skylight; daylight through the street door may be enough).
- PIE, fix axis if the first import is mirrored.

Everything else can be a button: `python pro/city/layout.py …` → `blender … city_builder.py --game-export` → `UnrealEditor-Cmd … import_city.py`.

---

## Suggested implementation order

1. **Hollow `Begin()` + street `openings()`** in `examples/polish_town_1927.py`. Verify in Blender: camera through the front door into the sień. No UE yet.
2. **Door leaf meshes + `city_game.json`** from `city_builder` / a `bpro` post-pass. Apply GN roads. `--output out/city.fbx`.
3. **UE import script + `BP_CityDoor`**. Import one house, then the full town.
4. (Optional) Exterior window holes, collision simplification, navmesh, indoor lights.

## Files (when we build it)

- Edit: `examples/polish_town_1927.py`, `city_builder.py`, maybe `bpro/op_openings.py` (export hinge frames).
- New: `city_game.json` schema + writer; `ue/import_city.py`; a short `docs` note on UE project setup.

## Non-goals for a first playable

- Multiplayer, inventory, NPCs.
- True door frames/hardware.
- Splitting each house into per-room actors.
- Auto-creating the `.uproject` from Python.
- Pixel-streaming / packaged build pipeline.
