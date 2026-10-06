# 本机工具与已验证工程

这是 2026-10-06 天香 T5 工程的工具记录。先检查路径存在与版本，再使用；用户给的新路径优先。此技能保存流程与只读检查脚本，模型生成器和 TPAC 库仍在下列工程中，不随技能复制。

## 路径

| 用途 | 本机位置 |
| --- | --- |
| 游戏 | `D:\SteamLibrary\steamapps\common\Mount & Blade II Bannerlord` |
| Blender | `D:\Blender Foundation\Blender 5.2\blender.exe` |
| Python（NumPy、Pillow） | `C:\ProgramData\anaconda3\python.exe` |
| 当前示例工程 | `D:\gpt-mb2-mod2` |
| 修补过的 TPAC 工具 | `D:\mb-tools\mbtool\bin\Release\net9.0\mbtool.exe` |
| 类型化检查/布料补丁工具 | `D:\gpt-mb2-mod2\tools\AssetTool\AssetTool.dll` |
| 切线、压缩贴图助手 | `D:\gpt-mb2-mod\pipeline\build_assets.py`、`convert_textures.py` |
| GDMB 几何读取、离线蒙皮 | `D:\gpt-mb2-mod\tools\georead.py`、`previewer\baker\skeleton.py`、`animation.py` |

`AssetTool.dll` 同目录需要 `mbtool.dll` 和 `AssetTool.runtimeconfig.json`；当前配置使用 .NET 10，mbtool 的配置使用其自身运行时。用 `dotnet --list-runtimes` 检查实际要求。路径都存在也不能证明序列化器兼容当前游戏；还需最终包往返与用户实测。

## 技能自带的只读助手

相对路径以**技能目录**为基准；装好后也可使用绝对路径。示例用当前机器的 Python：

```powershell
& 'C:\ProgramData\anaconda3\python.exe' -X utf8 'scripts\preflight.py' --workspace 'D:\gpt-mb2-mod2'
& 'C:\ProgramData\anaconda3\python.exe' -X utf8 'scripts\audit_package.py' 'D:\gpt-mb2-mod2\module\TianxiangT5\AssetPackages\tx5.tpac' --cloth-vertex-alpha
```

- `preflight.py` 检查本机离线工具、运行时、Python 库；`--require-example-pipeline` 另外要求示例生成脚本及其外部源码助手完整。路径均可通过参数修改。
- `audit_package.py` 调用 mbtool 的 `metacheck`、`mataudit` 和 AssetTool 的 `visibility`，输出 JSON。`--cloth-vertex-alpha` 表示本包的顶点 Alpha 用来存布料距离，要求使用 Alpha Test 的材质忽略该通道；普通顶点透明度模型不要套用这个选项。
- 工具输出缺失、格式不认识、无法解析或外部材质没有提供时，报告检查不完整；不会假装通过。可用 `--materials-json` 提供从其他包读取的材质数组，或包含 `materials` 数组的 visibility JSON。
- 两个助手都不修改模块或游戏。退出码 `0` 表示所覆盖的检查通过，`1` 表示发现问题，`2` 表示输入/工具/检查范围不完整。JSON 中包含范围说明。

## 示例工程里的生成流程

这些脚本含天香 T5 的模型编号、骨骼数、路径和材料计划。新模型先复制并适配到自己的工程，不能直接在原工程运行来代替新模型制作。先阅读入口、输出目标与依赖；本次技能制作无需执行它们。

| 阶段 | 示例脚本与产物 |
| --- | --- |
| 观察输入 | `tools/inspect_model.py`、`components.py`，原始 `model.fbx`、`inspection.blend`、`tex/` |
| 适配/绑骨 | `tools/rig_model.py`、`motion_fit.py` → `source/TianxiangT5_Rigged.blend`、FBX、`build/rig_arrays.npz`、manifest |
| 几何与 LOD | `tools/export_geometry.py` → `build/mesh/`、`geometry.json` |
| 材质/贴图/TPAC | `tools/build_package.py` → spec、BC mip、base.tpac → AssetTool cloth patch → `module/TianxiangT5/AssetPackages/tx5.tpac` |
| 最终包重新导出 | mbtool `exportmod`，每个交付 LOD 单独导出到 `build/final_export*` |
| 离线检查 | `tools/verify_assets.py`、`verify_motion.py`、`verify_posture.py`、`verify_visibility.py`、`verify_grip.py`；按当前返修目标选择，旧断言不直接套用新版本 |
| 预览 | `tools/render_review.py`、`render_motion_review.py`；原生动画读取、逐帧蒙皮与最终包核对见 [动画离线预览流程](asset-workflow.md#原生动画离线预览) |
| 交付 | `tools/package_delivery.py`；安装、版本和 Git 由适配后的发布流程完成 |

构建顺序：原始输入 → 绑骨/局部造型 → LOD/几何 → 材质/贴图/TPAC → 最终包重新导出 → 验证/预览 → 安装/打包 → 本地提交。材质返修可从构建包开始，但重新打包不能悄悄覆盖手改几何。

Blender 示例（当前工程用绝对路径；新工程先适配脚本）：

```powershell
& 'D:\Blender Foundation\Blender 5.2\blender.exe' --background --python-exit-code 1 --python 'D:\gpt-mb2-mod2\tools\rig_model.py'
# 上一步成功并检查输出后再继续
& 'D:\Blender Foundation\Blender 5.2\blender.exe' --background --python-exit-code 1 --python 'D:\gpt-mb2-mod2\tools\export_geometry.py'
& 'C:\ProgramData\anaconda3\python.exe' -X utf8 'D:\gpt-mb2-mod2\tools\build_package.py'
```

每步检查退出码和实际产物，不在前一步失败后继续发布。Windows 下中文输出和读取 UTF-8 技能时使用 Python `-X utf8`。

## 资源工具命令

调用可执行文件或 DLL 时保持参数分离、含空格路径加引号。下表描述的是本机工具能力，升级工具后先读帮助/源码确认。

| mbtool 子命令 | 参数/用途 |
| --- | --- |
| `list` | `<tpac> [filter]`，查资产名称、类型和 GUID |
| `find` | `<dir> <name>`，从实际游戏资源定位样本 |
| `skeljson` | `<skeleton.tpac> <skeletonName> <out.json>` |
| `anim` | `<animations.tpac> <name或guid> <out.json> [skeletons.tpac]` |
| `exportmod` | `<tpac> <outDir> [lod]`，几何 bin、包信息和贴图 PNG |
| `build` | `<spec.json>`，按模板生成 TPAC |
| `metacheck` | `<tpac>`，校验和、元数据往返序列化 |
| `mataudit` | `<tpac>`，检查包内材料引用 |

```powershell
dotnet 'D:\gpt-mb2-mod2\tools\AssetTool\AssetTool.dll' visibility '<最终包绝对路径>'
dotnet 'D:\gpt-mb2-mod2\tools\AssetTool\AssetTool.dll' inspect '<最终包绝对路径>'
dotnet 'D:\gpt-mb2-mod2\tools\AssetTool\AssetTool.dll' materials '<最终包绝对路径>'
```

`visibility` 返回材料 GUID、ShaderMaterialFlags、AlphaTest，以及网格材料、LOD、布料标记、顶点 Alpha 范围和数据 SHA256；`inspect` 返回布料元数据。`patch <in.tpac> <recipe.json> <out.tpac>` 会修改文件，当前参数预设只为天香 T5；新模型先阅读 `tools/AssetTool/Program.cs` 并适配。

当前 `tools/install_release.ps1` 即使接收 Version，仍写死工程、目标、检查报告、暂存文件与 v1.3.0 提交内容。不要当通用发布脚本。`verify_*` 中也有物体名、旧基线标签和统计数的专用断言，新模型应按实际 manifest 改写。

示例中曾用 Roslyn 编译 AssetTool，避开无法恢复的包依赖。迁移时先尝试实际项目构建；如需手工编译，用已安装 SDK、适配目标框架和实际引用，不照抄 SDK 版本号。未完成工具兼容性验证时保留源文件、报告具体缺项，不输出“已生成可用 Mod”。
