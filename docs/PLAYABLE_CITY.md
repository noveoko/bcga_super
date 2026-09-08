# Playable Unreal FPS city

End-to-end: Polish-town layout → hollow walkable houses → FBX + JSON → Unreal First Person.

## One command (Blender half)

```powershell
python pipeline/run_city_fps.py --seed 1927 --max-plots 40 --output out/playable
```

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

1. Create a **UE5 First Person** project (e.g. `CityFPS`).
2. Enable **Editor Scripting Utilities** and **Python Editor Script Plugin**.
3. Create Blueprint `/Game/City/BP_CityDoor`:
   - Static Mesh component (door leaf assigned at import, or a default board).
   - Collision on the mesh.
   - Input (line trace / overlap + key): timeline rotate relative yaw `0 → SwingDegrees` (default 90) around local Z (hinge).
   - Optional: set `SwingDegrees` from a variable the import script can write later.
4. Import once:

```powershell
python pipeline/run_city_fps.py --seed 1927 --max-plots 40 --output out/playable `
  --ue-project path\to\CityFPS.uproject `
  --unreal-cmd "C:\Program Files\Epic Games\UE_5.x\Engine\Binaries\Win64\UnrealEditor-Cmd.exe"
```

Or manually:

```
UnrealEditor-Cmd.exe CityFPS.uproject -unattended -ExecutePythonScript="D:\...\ue\import_city.py" -- --fbx ...\city.fbx --game-json ...\city.game.json --lights-json ...\city.lights.json
```

5. If the town is mirrored, re-run import with `--flip-y`.
6. PIE. You should walk the rynek, open street doors, enter rooms, see interior lights.

## Geometry notes

- Houses (except church/synagogue) are **hollow wall rings** with a real street door opening.
- Interior partition doors also emit `Door_*` leaves.
- Building collision in UE: **Use Complex Collision As Simple**.
- Units: BCGA meters → UE centimeters (`×100`).

## What is still manual

- Creating the `.uproject` and `BP_CityDoor`.
- First-import axis check (`--flip-y` if needed).
- Church/synagogue remain sealed landmarks (no interior walk).
