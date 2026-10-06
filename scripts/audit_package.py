"""Read-only TPAC metadata, material-reference and vertex-alpha audit."""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path


def run(command, timeout):
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8-sig",
                            errors="replace", stdin=subprocess.DEVNULL, timeout=timeout)
    if result.returncode:
        raise RuntimeError(f"Command failed ({result.returncode}): {command[0]}\n"
                           f"{result.stderr.strip()}\n{result.stdout.strip()}")
    return result.stdout.strip()


def audit_alpha(data, external_materials, cloth_vertex_alpha):
    materials = {m["Guid"].lower(): m for m in external_materials}
    materials.update({m["Guid"].lower(): m for m in data["materials"]})
    errors, incomplete, observations = [], [], []
    if not data["meshes"]:
        errors.append({"kind": "no_meshes", "message": "Equipment package has no mesh"})
    for mesh in data["meshes"]:
        context = {"mesh": mesh["Name"], "lod": mesh["Lod"]}
        if mesh["Vertices"] <= 0:
            errors.append({**context, "kind": "empty_mesh"})
        a_min, a_max = mesh["AlphaMin"], mesh["AlphaMax"]
        if not (0 <= a_min <= a_max <= 255):
            errors.append({**context, "kind": "invalid_vertex_alpha", "range": [a_min, a_max]})
            continue
        mat = materials.get(mesh["Material"].lower())
        if mat is None:
            incomplete.append({**context, "kind": "unresolved_material",
                               "guid": mesh["Material"], "message": "Supply external material JSON if reference is intentional"})
            continue
        flags = set(mat["ShaderMaterialFlags"] or [])
        if "alpha_test" not in flags or "disable_vertex_color_alpha" in flags:
            continue
        threshold = float(mat["AlphaTest"])
        detail = {**context, "material": mat["Name"], "vertex_alpha_range": [a_min, a_max],
                  "alpha_test": threshold, "cloth_enabled": "uses_cloth_simulation" in (mesh["Flags"] or [])}
        if a_max / 255.0 < threshold:
            errors.append({**detail, "kind": "standard_shader_fully_clipped_risk",
                           "message": "Even texture alpha 1 cannot reach threshold when the standard shader multiplies vertex alpha"})
        elif cloth_vertex_alpha:
            errors.append({**detail, "kind": "cloth_alpha_used_as_opacity",
                           "message": "Cloth-distance alpha must be ignored by opacity in ShaderMaterialFlags"})
        elif a_min < 255:
            observations.append({**detail, "kind": "vertex_opacity_modulation",
                                 "message": "Check shader and texture intent; --cloth-vertex-alpha applies the cloth-distance invariant"})
    return errors, incomplete, observations


def sha256(path):
    value = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path)
    parser.add_argument("--mbtool", type=Path, default=Path(r"D:\mb-tools\mbtool\bin\Release\net9.0\mbtool.exe"))
    parser.add_argument("--asset-tool", type=Path, default=Path(r"D:\gpt-mb2-mod2\tools\AssetTool\AssetTool.dll"))
    parser.add_argument("--dotnet", default=shutil.which("dotnet") or "dotnet")
    parser.add_argument("--materials-json", type=Path, help="External Material[] or visibility JSON from AssetTool")
    parser.add_argument("--cloth-vertex-alpha", action="store_true")
    parser.add_argument("--timeout", type=int, default=60, help="Per command timeout in seconds")
    args = parser.parse_args()
    report = {"package": str(args.package.resolve()), "status": "incomplete",
              "scope": "Metadata round-trip, references and standard shader vertex-alpha risk only; textures, custom shader paths, geometry, weights, cloth dynamics and game behavior are not validated",
              "cloth_vertex_alpha": args.cloth_vertex_alpha, "errors": [], "incomplete": [], "observations": []}
    try:
        if args.timeout <= 0:
            raise ValueError("--timeout must be positive")
        for path in (args.package, args.mbtool, args.asset_tool):
            if not path.is_file():
                raise FileNotFoundError(path)
        report["package_sha256"] = sha256(args.package)
        metadata = run([str(args.mbtool), "metacheck", str(args.package)], args.timeout)
        references = run([str(args.mbtool), "mataudit", str(args.package)], args.timeout)
        report["tool_output"] = {"metacheck": metadata, "mataudit": references}
        pattern = r"checksum ok=(\d+) bad=(\d+)\s*\|\s*metadata identical=(\d+) differ=(\d+) noSerializer=(\d+)"
        match = re.search(pattern, metadata)
        if not match:
            report["incomplete"].append({"kind": "unrecognized_metacheck_output"})
        else:
            ok, bad, identical, differ, unsupported = map(int, match.groups())
            if bad or differ:
                report["errors"].append({"kind": "metadata_roundtrip", "bad_checksums": bad, "different_metadata": differ})
            if unsupported or not ok or not identical:
                report["incomplete"].append({"kind": "metadata_coverage", "unsupported": unsupported})
        missing = re.findall(r"\bmissing=(\d+)", references)
        no_material = re.search(r"metameshes with no material at all=(\d+)", references)
        if not missing or no_material is None:
            report["incomplete"].append({"kind": "unrecognized_mataudit_output"})
        if no_material and int(no_material.group(1)):
            report["errors"].append({"kind": "metameshes_without_material", "count": int(no_material.group(1))})
        data = json.loads(run([args.dotnet, str(args.asset_tool), "visibility", str(args.package)], args.timeout))
        external_materials = []
        if args.materials_json:
            external = json.loads(args.materials_json.read_text(encoding="utf-8-sig"))
            external_materials = external if isinstance(external, list) else external["materials"]
        errors, incomplete, observations = audit_alpha(data, external_materials, args.cloth_vertex_alpha)
        report["errors"].extend(errors)
        report["incomplete"].extend(incomplete)
        report["observations"].extend(observations)
        # A package-local audit can flag intentional references to native/external materials.
        # Even with external JSON, uninspected SecondMaterial/MetaMesh references remain incomplete.
        if any(int(v) for v in missing):
            report["incomplete"].append({"kind": "package_local_material_references", "missing_counts": list(map(int, missing)),
                                         "message": "Check MetaMesh and SecondMaterial refs as well as primary materials"})
        report["counts"] = {"materials": len(data["materials"]), "submeshes": len(data["meshes"]),
                            "cloth_submeshes": sum("uses_cloth_simulation" in (m["Flags"] or []) for m in data["meshes"]),
                            "lods": sorted({m["Lod"] for m in data["meshes"]})}
        if sha256(args.package) != report["package_sha256"]:
            report["incomplete"].append({"kind": "package_changed_during_audit"})
        report["status"] = "fail" if report["errors"] else "incomplete" if report["incomplete"] else "pass"
    except (OSError, ValueError, KeyError, TypeError, AttributeError, RuntimeError, subprocess.TimeoutExpired) as exc:
        report["incomplete"].append({"kind": "tool_or_input_error", "message": str(exc)})
        report["status"] = "incomplete"
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return {"pass": 0, "fail": 1, "incomplete": 2}[report["status"]]


if __name__ == "__main__":
    raise SystemExit(main())
