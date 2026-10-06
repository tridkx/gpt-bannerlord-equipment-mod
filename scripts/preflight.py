"""Read-only inventory of the local Bannerlord equipment toolchain."""
import argparse
import importlib.util
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
    parser.add_argument("--asset-tool", type=Path, default=Path(r"D:\gpt-mb2-mod2\tools\AssetTool\AssetTool.dll"))
    parser.add_argument("--example-workspace", type=Path, default=Path(r"D:\gpt-mb2-mod2"))
    parser.add_argument("--helpers", type=Path, default=Path(r"D:\gpt-mb2-mod"))
    parser.add_argument("--require-example-pipeline", action="store_true")
    args = parser.parse_args()
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
    for library in ("numpy", "PIL"):
        try:
            found = importlib.util.find_spec(library) is not None
        except (ImportError, ValueError):
            found = False
        record("python_" + library, found, True, python=sys.executable)
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
    missing = [c["name"] for c in checks if c["required"] and not c["found"]]
    print(json.dumps({
        "status": "ready" if not missing else "incomplete",
        "scope": "Local offline tool inventory only; no builds, game launch or game-version compatibility test",
        "missing_required": missing, "checks": checks,
    }, ensure_ascii=False, indent=2))
    return 2 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
