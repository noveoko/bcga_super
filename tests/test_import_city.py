"""Pure-Python tests for ue/import_city.py helpers (no Unreal)."""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "ue")))

from import_city import (  # noqa: E402
    DEFAULT_VIEW,
    VIEW_FIRST_PERSON,
    VIEW_THIRD_PERSON,
    actor_scale_from_mesh_extent,
    door_blueprint_candidates,
    game_mode_candidates,
    import_argv,
    is_world_mesh_name,
    mesh_short_name,
    _parse,
    _to_ue,
)


def test_default_view_is_third_person():
    assert DEFAULT_VIEW == VIEW_THIRD_PERSON
    args = _parse(["--fbx", "a.fbx", "--game-json", "a.json"])
    assert args.view == VIEW_THIRD_PERSON


def test_parse_first_person_view():
    args = _parse(["--fbx", "a.fbx", "--game-json", "a.json", "--view", VIEW_FIRST_PERSON])
    assert args.view == VIEW_FIRST_PERSON


def test_game_mode_candidates_differ_by_view():
    third = game_mode_candidates(VIEW_THIRD_PERSON)
    first = game_mode_candidates(VIEW_FIRST_PERSON)
    assert third and first
    assert third != first
    assert any("ThirdPerson" in p for p in third)
    assert any("FirstPerson" in p for p in first)


def test_door_blueprint_accepts_city_and_root_paths():
    paths = door_blueprint_candidates()
    assert "/Game/City/BP_CityDoor" in paths
    assert "/Game/BP_CityDoor" in paths


def test_is_world_mesh_skips_doors_and_cameras():
    assert is_world_mesh_name("Kamienica_012") is True
    assert is_world_mesh_name("Road_003") is True
    assert is_world_mesh_name("Ground") is True
    assert is_world_mesh_name("Door_042_0") is False
    assert is_world_mesh_name("door_leaf") is False
    assert is_world_mesh_name("Camera") is False
    assert is_world_mesh_name("Sun") is False


def test_mesh_short_name():
    assert mesh_short_name("/Game/City/Meshes/Kamienica_012.Kamienica_012") == "Kamienica_012"


def test_actor_scale_skips_double_cm_conversion():
    assert actor_scale_from_mesh_extent(160.0) == 100.0   # still in meters
    assert actor_scale_from_mesh_extent(16000.0) == 1.0   # already centimeters


def test_to_ue_scale_and_flip():
    assert _to_ue([1.0, 2.0, 0.15], 100.0, False) == (100.0, 200.0, 15.0)
    assert _to_ue([1.0, 2.0, 0.15], 100.0, True) == (100.0, -200.0, 15.0)


def test_import_argv_reads_tokens_after_dashdash_on_unreal_command_line():
    cmdline = (
        r'"C:\Program Files\Epic Games\UE_5.7\Engine\Binaries\Win64\UnrealEditor-Cmd.exe" '
        r'"D:\proj\InitialWorld.uproject" -unattended '
        r'-ExecutePythonScript="D:/proj/ue/import_city.py" -- '
        r'--fbx "D:/proj/out/city.fbx" --game-json "D:/proj/out/city.game.json" '
        r"--view first-person"
    )
    argv = import_argv(argv=["import_city.py"], cmdline=cmdline)
    args = _parse(argv)
    assert args.fbx.replace("\\", "/") == "D:/proj/out/city.fbx"
    assert args.game_json.replace("\\", "/") == "D:/proj/out/city.game.json"
    assert args.view == VIEW_FIRST_PERSON
