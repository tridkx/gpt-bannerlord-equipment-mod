"""Read-only inventory of the local Bannerlord equipment toolchain."""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--game", type=Path, default=Path(r"D:\SteamLibrary\steamapps\common\Mount & Blade II Bannerlord"))
    parser.add_argument("--blender", type=Path, default=Path(r"D:\Blender Foundation\Blender 5.2\blender.exe"))
    parser.add_argument("--mbtool", type=Path, default=Path(r"D:\mb-tools\mbtool\bin\Release\net9.0\mbtool.exe"))
    parser.add_argument("--asset-tool", type=Path, help="Defaults to workspace tools/AssetTool/AssetTool.dll")
    parser.add_argument("--example-workspace", type=Path, help="Model-specific project; inferred for the local Tianxiang example")
    parser.add_argument("--helpers", type=Path, default=Path(r"D:\gpt-mb2-mod"))
    parser.add_argument("--require-example-pipeline", action="store_true")
    parser.add_argument("--check-blender-python", action="store_true", help="Launch factory-startup background Blender to import dependencies; no model opened or saved")
    args = parser.parse_args()
    args.workspace = args.workspace.resolve()
    workspace_root = args.workspace
    if (args.workspace / "mod.json").is_file() and args.workspace.parent.name == "mods":
        workspace_root = args.workspace.parents[1]
    if args.asset_tool is None:
        args.asset_tool = workspace_root / "tools/AssetTool/AssetTool.dll"
    if args.example_workspace is None:
        candidate = workspace_root / "mods/TianxiangT5"
        args.example_workspace = args.workspace if (args.workspace / "mod.json").is_file() else (candidate if candidate.is_dir() else args.workspace)
    checks = []

    def record(name, found, required, **detail):
        checks.append({"name": name, "found": bool(found), "required": required, **detail})

    def file_check(name, path, required=True, directory=False):
        record(name, path.is_dir() if directory else path.is_file(), required, path=str(path))

    file_check("workspace", args.workspace, directory=True)
    file_check("game_modules", args.game / "Modules", directory=True)
    file_check("blender", args.blender)
    file_check("mbtool", args.mbtool)
    file_check("asset_tool", args.asset_tool)
    file_check("asset_tool_library", args.asset_tool.parent / "mbtool.dll")
    def probe_imports(name, modules, paths=(), blender=False, required=True):
        # Separate process and -B avoid changing sys.path or creating helper caches.
        code = "import sys,json,importlib; sys.dont_write_bytecode=True; "
        code += "sys.path[:0]=" + repr([str(p) for p in paths]) + "; "
        code += "modules=" + repr(modules) + "; "
        code += "loaded=[importlib.import_module(m) for m in modules]; "
        code += "print('PREFLIGHT_IMPORTS='+json.dumps({m:getattr(v,'__version__','imported') for m,v in zip(modules,loaded)}))"
        command = ([str(args.blender), "--background", "--factory-startup", "--python-exit-code", "1", "--python-expr", code]
                   if blender else [sys.executable, "-B", "-X", "utf8", "-c", code])
        try:
            result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8",
                                    errors="replace", stdin=subprocess.DEVNULL, timeout=45)
            marker = next((line.split("PREFLIGHT_IMPORTS=", 1)[1] for line in result.stdout.splitlines()
                           if line.startswith("PREFLIGHT_IMPORTS=")), None)
            found = result.returncode == 0 and marker is not None
            record(name, found, required, modules=modules,
                   versions=json.loads(marker) if marker else {},
                   error=result.stderr[-3000:] if not found else "")
        except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
            record(name, False, required, modules=modules, error=str(exc))

    probe_imports("python_base_imports", ["numpy", "PIL.Image"])
    if args.require_example_pipeline:
        probe_imports("python_scipy_imports", ["scipy.spatial"])
    git_path = shutil.which("git")
    dotnet_path = shutil.which("dotnet")
    record("git", git_path is not None, True, path=git_path)
    record("dotnet", dotnet_path is not None, True, path=dotnet_path)
    runtimes = []
    if dotnet_path:
        try:
            result = subprocess.run([dotnet_path, "--list-runtimes"], capture_output=True,
                                    text=True, encoding="utf-8", errors="replace",
                                    stdin=subprocess.DEVNULL, timeout=30)
            runtimes = result.stdout.splitlines()
            record("dotnet_runtime_inventory", result.returncode == 0, True,
                   runtimes=runtimes, error=result.stderr.strip())
        except (OSError, subprocess.TimeoutExpired) as exc:
            record("dotnet_runtime_inventory", False, True, error=str(exc))
    for name, config in (
        ("asset_tool", args.asset_tool.with_suffix(".runtimeconfig.json")),
        ("mbtool", args.mbtool.with_suffix(".runtimeconfig.json")),
    ):
        try:
            runtime = json.loads(config.read_text(encoding="utf-8-sig"))["runtimeOptions"]
            frameworks = runtime.get("frameworks", [])
            if "framework" in runtime:
                frameworks = [runtime["framework"], *frameworks]
            if not frameworks:
                record(name + "_runtime", False, True, path=str(config),
                       error="No framework declaration; check self-contained deployment manually")
            for framework in frameworks:
                # Check the default same-major/minor patch roll-forward case.
                requested = tuple(int(v) for v in framework["version"].split(".")[:3])
                versions = []
                for line in runtimes:
                    parts = line.split()
                    if len(parts) >= 2 and parts[0] == framework["name"]:
                        try:
                            versions.append(tuple(int(v) for v in parts[1].split(".")[:3]))
                        except ValueError:
                            pass
                found = any(v[:2] == requested[:2] and v >= requested for v in versions)
                record(name + "_runtime", found, True, path=str(config),
                       framework=framework, note="Checks default same-major/minor patch roll-forward")
        except (OSError, ValueError, KeyError, TypeError) as exc:
            record(name + "_runtime", False, True, path=str(config), error=str(exc))
    example_required = args.require_example_pipeline
    for name, path in (
        ("example_rigger", args.example_workspace / "tools/rig_model.py"),
        ("example_exporter", args.example_workspace / "tools/export_geometry.py"),
        ("example_builder", args.example_workspace / "tools/build_package.py"),
        ("tangent_helper", args.helpers / "pipeline/build_assets.py"),
        ("texture_helper", args.helpers / "pipeline/convert_textures.py"),
        ("geometry_reader", args.helpers / "tools/georead.py"),
        ("skeleton_reader", args.helpers / "previewer/baker/skeleton.py"),
        ("animation_reader", args.helpers / "previewer/baker/animation.py"),
    ):
        file_check(name, path, example_required)
    helper_paths = [args.helpers / "pipeline", args.helpers / "tools", args.helpers / "previewer"]
    if args.require_example_pipeline:
        probe_imports("example_helper_imports", ["build_assets", "convert_textures", "georead",
                                               "baker.skeleton", "baker.animation"], helper_paths)
    if args.check_blender_python:
        modules = ["bpy", "mathutils", "numpy"]
        if args.require_example_pipeline:
            modules.append("build_assets")
        probe_imports("blender_python_imports", modules, helper_paths, blender=True)
    missing = [c["name"] for c in checks if c["required"] and not c["found"]]
    print(json.dumps({
        "status": "ready" if not missing else "incomplete",
        "scope": "Tool inventory and requested dependency imports only; no model builds, game launch or game-version compatibility test",
        "missing_required": missing, "checks": checks,
    }, ensure_ascii=False, indent=2))
    return 2 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
