# Playable Unreal city

End-to-end: Polish-town layout → hollow walkable houses → FBX + JSON → Unreal.

**Default character is third-person.** Use `--view first-person` if the Unreal project was created from the First Person template.

## One command (Blender half)

```powershell
python pipeline/run_city.py --seed 1927 --output out/playable
```

(`pipeline/run_city_fps.py` is the same script.) Builds every plot. Pass `--max-plots 40` for a preview.

Produces:

| File | Purpose |
|---|---|
| `out/playable/layout.json` | Town layout |
| `out/playable/city.blend` | Authoring / debug |
| `out/playable/city.fbx` | Unreal mesh import |
| `out/playable/city.game.json` | Doors, player start, building list |
| `out/playable/city.lights.json` | Ceiling point lights (candela) |
| `out/playable/pipeline.log` | Stage log |

## One-time Unreal setup

1. Create a **UE5 Third Person** project (e.g. `CityGame`). For a First Person character instead, create a First Person project and always pass `--view first-person`.
2. Enable **Editor Scripting Utilities** and **Python Editor Script Plugin**.
3. Create Blueprint `/Game/City/BP_CityDoor` (the importer also accepts `/Game/BP_CityDoor`):
   - Static Mesh component (door leaf assigned at import, or a default board).
   - Collision on the mesh.
   - Input (line trace / overlap + key): timeline rotate relative yaw `0 → SwingDegrees` (default 90) around local Z (hinge).
4. Import:

```powershell
python pipeline/run_city.py --seed 1927 --output out/playable `
  --ue-project path\to\CityGame.uproject `
  --unreal-cmd "C:\Program Files\Epic Games\UE_5.x\Engine\Binaries\Win64\UnrealEditor-Cmd.exe"
```

First-person variant (same artifacts, different GameMode):

```powershell
python pipeline/run_city.py --seed 1927 --output out/playable `
  --view first-person `
  --ue-project path\to\CityFPS.uproject `
  --unreal-cmd "C:\Program Files\Epic Games\UE_5.x\Engine\Binaries\Win64\UnrealEditor-Cmd.exe"
```

Or manually:

```
UnrealEditor-Cmd.exe CityGame.uproject -unattended -ExecutePythonScript="D:\...\ue\import_city.py" -- --fbx ...\city.fbx --game-json ...\city.game.json --lights-json ...\city.lights.json --view third-person
```

The importer:

- Writes `/Game/City/Lvl_City` and spawns building/road/ground meshes there
- Sets **Use Complex Collision As Simple** on those meshes
- Spawns doors, ceiling lights, and `PlayerStart`
- Sets World Settings GameMode when it finds the matching template Blueprint

5. If the town is mirrored, re-run with `--flip-y`.
6. PIE from `/Game/City/Lvl_City`. You should walk the rynek, open street doors, enter rooms, see interior lights.

The in-repo `examples/starter_world_unreal/InitialWorld` project is a **First Person** template. Use it with `--view first-person`. For the default third-person path, use a Third Person `.uproject`.

## Geometry notes

- Houses are **hollow wall rings** with a real street door opening (including church/synagogue).
- Interior partition doors also emit `Door_*` leaves.
- Building collision in UE: **Use Complex Collision As Simple** (set by the importer).
- Units: BCGA meters → UE centimeters (`×100` on actors).

Specialty plots (school, karczma, apteka) use dedicated rule files; other plots use `examples/polish_town_1927.py`.

## What is still manual

- Creating the `.uproject` (Third Person or First Person) and `BP_CityDoor`.
- First-import axis check — run once, and add `--flip-y` if the town looks mirrored.
