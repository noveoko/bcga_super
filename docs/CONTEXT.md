# Context contract (GenerationSession migration)

BCGA exposes a process-wide `pro.context` **proxy** so existing rule files
(`from pro import *`, `@rule`, `Begin()`) keep working. Internally execution
state lives on a `Context` instance owned by an optional `GenerationSession`.

## GenerationSession (Phase 2)

```python
from pro import GenerationSession

with GenerationSession(seed=12345, blender_context=bpy.context) as session:
    session.set_city_block(plot)
    session.apply("examples/polish_town_1927.py")
    lights = session.all_ceiling_lights
    doors = session.all_game_doors
```

- While the session is active, `pro.context` forwards to `session.context`.
- Orchestrators (`generate.py`, `city_builder.py`, Blender addon) should create
  a session per run/batch rather than poking globals by hand.
- `bpro.apply(..., session=session)` activates that session for one apply if it
  is not already active (so `with GenerationSession()` batches do not flap).

## Field classes

| Class | Examples | Lifetime |
|---|---|---|
| **Session / batch** | `cityBlock`, `blenderContext`, `ruleFile`, `allCeilingLights`, `allGameDoors`, `random` (`seed`/`rng`) | Owned by `GenerationSession` / default `Context`; survives across buildings in one run |
| **Per-apply DSL** | `operator`, `stack`, `deferreds`, `params`, `trace.tracing` | `begin_apply()` → rule execute → `end_apply()` |
| **Per-apply geometry (Blender)** | `bm`, `facesForRemoval`, `vertexRegistry`, `materialManager`, `joinManager` | Registered via `addAttribute` during `bpro.apply`; always cleared in `end_apply()` |
| **Per-apply outputs** | `ceilingLights`, `gameDoors`, `buildingTrace` | Filled during apply; orchestrator copies into `all*` before `end_apply` clears per-building lists |

## Sub-contexts

- `context.random` — `RandomContext` (`set_seed`, `rng`). Aliases: `context.seed`, `context.rng`, `context.set_seed`.
- `context.trace` — `TraceContext`. Aliases: `context.tracing`, `context.buildingTrace`.
- `context.geometry` — `GeometryContext` (`bm`, `facesForRemoval`, `vertexRegistry`, `joinManager`). Aliases: `context.bm`, etc.
- `context.materials` — `MaterialContext` (`manager`). Alias: `context.materialManager`.

Operator **factory** is a process-wide shared dict (`_OPERATOR_FACTORY`) so every
session resolves the same DSL operators.

## Geometry / Material backends (Phase 4)

`bpro.backends.attach_blender_backends(ctx, mesh)` attaches:

- `BlenderGeometryBackend` — owns bmesh open/write/free; supplies `JoinManager` factory
- `BlenderMaterialBackend` — creates `MaterialManager`; exposes render engine id

`GeometryContext.create_join_manager()` replaces the old
`context.joinManager = context.joinManager()` class-vs-instance swap.
`end_apply()` calls `geometry.close()` / `materials.close()`.

`pro/geometry.py` and `pro/material_context.py` stay **bpy-free**.

## GeometryBackend (Priority 3)

Mesh mutation goes through `pro.geom_api.GeometryBackend`:

```python
ctx.geometry.api.extrude_face_region(face)
ctx.geometry.api.translate_verts(verts, delta)
```

- **BlenderGeometryBackend** (`bpro/backends.py`) wraps `bmesh.ops` (Phase A).
- **MemoryGeometryBackend** (Phase B, planned) will implement the same Protocol for pytest without Blender.
- `Shape2d.extrude` / translate / copy call the backend; loop-walking still uses Blender loop refs until shapes are fully abstracted.

## RuleContext (Phase 3)

Operators take an optional `ctx` on `execute(self, ctx=None)`:

```python
def execute(self, ctx=None):
    ctx = resolve_rule_context(ctx)
    shape = ctx.getState().shape
    ...
```

- `Rule.execute` pushes a `RuleContext` (ContextVar) for the duration of the rule body and child operators.
- `resolve_rule_context()` priority: explicit arg → active ContextVar → ambient `pro.context` proxy.
- `Operator.__init__` only registers as a child when an ambient parent operator exists (no dummy parent required in unit tests).
- DSL façades resolve the factory via `resolve_rule_context().factory[...]`.

## Apply lifecycle

1. Orchestrator opens a `GenerationSession` (sets blender context + optional seed).
2. `session.apply(...)` / `bpro.apply(...)` ensures a footprint mesh, then `begin_apply()`.
3. Blender backends attach geometry + materials; shape stack is installed; rule module is loaded; `prepare()` resolves random params.
4. `Begin()` runs; deferred joins resolve via `geometry.create_join_manager()`; lights/doors spawn; mesh is written back.
5. `finally: end_apply()` — `geometry.close()` / `materials.close()` + DSL cleanup.

## What rule files may read

- Plot metadata via **`city_block()`** (preferred) or `context.cityBlock`
- `context.getState().shape` during execution
- `param` / `random` / `choice` / `chance` (RNG goes through `context.rng`)

Rule files should not set `bm`, `blenderContext`, or call `begin_apply` / `end_apply`.

## Plot metadata ergonomics (Phase 5)

**Preferred** — read inside `Begin()` / `@rule` so values come from the active
`GenerationSession` even when the module object is re-used without reload:

```python
from pro import *

@rule
def Begin():
    plot = city_block({"density": 0.5, "role": "house"})
    density = float(plot.get("density") or 0.5)
    extrude(3 + density * 20)
```

See `examples/city_building.py` for a full density-aware example.

**Legacy (still supported)** — module-level `context.cityBlock or {...}` works
when `bpro.getModule()` re-executes the rule file after
`session.set_city_block(...)` (city_builder path). It is fragile on the Blender
addon path that calls `bpro.apply(module)` without reload. Existing large rules
(e.g. `examples/polish_town_1927.py`) may keep import-time binding; new rules
should not. If you must read at import time, call `city_block_at_import(default)`
to emit an explicit `DeprecationWarning`.

## CLI / server pattern

One `GenerationSession` per request or batch:

```python
# Headless CLI (generate.py already does this)
with GenerationSession(seed=seed, blender_context=bpy.context) as session:
    for plot in plots:
        session.set_city_block(plot)
        # create footprint for plot...
        session.apply("rules/house.py")
    return session.all_ceiling_lights, session.all_game_doors

# HTTP worker sketch: new session per request, never share across requests
def handle_build(request):
    with GenerationSession(seed=request.seed, blender_context=bpy.context) as session:
        session.set_city_block(request.plot)
        session.apply(request.rule_path)
        return {"lights": len(session.all_ceiling_lights)}
```
