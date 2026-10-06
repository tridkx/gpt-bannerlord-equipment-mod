# 本机工具与已验证工程

这是 2026-10-06 天香 T5 工程的工具记录。先检查路径存在与版本，再使用；用户给的新路径优先。此技能保存流程与只读检查脚本，模型生成器和 TPAC 库仍在下列工程中，不随技能复制。

## 路径

| 用途 | 本机位置 |
| --- | --- |
| 游戏 | `D:\SteamLibrary\steamapps\common\Mount & Blade II Bannerlord` |
| Blender | `D:\Blender Foundation\Blender 5.2\blender.exe` |
| Python（NumPy、Pillow、示例回归所需 SciPy） | `C:\ProgramData\anaconda3\python.exe` |
| 多模组工作区 | `D:\gpt-mb2-mod2` |
| 天香示例工程 | `D:\gpt-mb2-mod2\mods\TianxiangT5` |
| 修补过的 TPAC 工具 | `D:\mb-tools\mbtool\bin\Release\net9.0\mbtool.exe` |
| 类型化检查/布料补丁工具 | `D:\gpt-mb2-mod2\tools\AssetTool\AssetTool.dll` |
| 切线、压缩贴图助手 | `D:\gpt-mb2-mod\pipeline\build_assets.py`、`convert_textures.py` |
| GDMB 几何读取、离线蒙皮 | `D:\gpt-mb2-mod\tools\georead.py`、`previewer\baker\skeleton.py`、`animation.py` |

`AssetTool.csproj` 目前目标 net9.0，而已部署 DLL 的 runtimeconfig 是 net10.0（曾手工编译）。项目构建目标与部署运行时分别核对；重新构建前记录当前 DLL SHA256、实际引用和运行时，构建后复核功能与最终包，不能据项目文件推断现有 DLL 版本。

`AssetTool.dll` 同目录需要 `mbtool.dll` 和 `AssetTool.runtimeconfig.json`；当前配置使用 .NET 10，mbtool 的配置使用其自身运行时。用 `dotnet --list-runtimes` 检查实际要求。路径都存在也不能证明序列化器兼容当前游戏；还需最终包往返与用户实测。

## 技能自带的只读助手

相对路径以**技能目录**为基准；装好后也可使用绝对路径。示例用当前机器的 Python：

```powershell
& 'C:\ProgramData\anaconda3\python.exe' -X utf8 'scripts\preflight.py' --workspace 'D:\gpt-mb2-mod2' --require-example-pipeline --check-blender-python
& 'C:\ProgramData\anaconda3\python.exe' -X utf8 'scripts\audit_package.py' 'D:\gpt-mb2-mod2\mods\TianxiangT5\module\TianxiangT5\AssetPackages\tx5.tpac' --cloth-vertex-alpha
```

- `preflight.py` 检查本机工具、运行时，并在独立 Python 进程实际导入 NumPy/Pillow；`--require-example-pipeline` 还检查 SciPy、示例脚本和外部源码助手的导入。默认识别本工作区的 `mods/TianxiangT5`；其他工程用 `--example-workspace` 明确指定。`--asset-tool` 默认从工作区根 tools/ 查找，所有外部路径均可覆盖。
- `--check-blender-python` 额外启动 factory-startup 后台 Blender，只导入 bpy、mathutils、NumPy；启用示例流程时还导入几何助手。不打开或保存模型。未启用时不检查 Blender 内 Python 依赖。ready 仅代表所选预检通过，不代表完整构建、最终资源或游戏兼容性通过。
- `audit_package.py` 调用 mbtool 的 `metacheck`、`mataudit` 和 AssetTool 的 `visibility`，输出 JSON。`--cloth-vertex-alpha` 表示本包的顶点 Alpha 用来存布料距离，要求使用 Alpha Test 的材质忽略该通道；普通顶点透明度模型不要套用这个选项。
- 工具输出缺失、格式不认识、无法解析或外部材质没有提供时，报告检查不完整；不会假装通过。可用 `--materials-json` 提供从其他包读取的材质数组，或包含 `materials` 数组的 visibility JSON。
- 两个助手都不修改模块或游戏。退出码 `0` 表示所覆盖的检查通过，`1` 表示发现问题，`2` 表示输入/工具/检查范围不完整。JSON 中包含范围说明。

## 示例工程里的生成流程

这些脚本含天香 T5 的模型编号、骨骼数、路径和材料计划。新模型先复制并适配到自己的工程，不能直接在原工程运行来代替新模型制作。先阅读入口、输出目标与依赖。下表相对路径以 `mods/TianxiangT5/` 为基准；共用入口明确标为工作区根路径。

| 阶段 | 示例脚本与产物 |
| --- | --- |
| 观察输入 | `tools/inspect_model.py`、`components.py`，原始 `input/model.fbx`、`source/inspection.blend`、`tex/` |
| 适配/绑骨 | `tools/rig_model.py`、`motion_fit.py` → `source/TianxiangT5_Rigged.blend`、FBX、`build/rig_arrays.npz`、manifest |
| 几何与 LOD | `tools/export_geometry.py` → `build/mesh/`、`geometry.json` |
| 材质/贴图/TPAC | `tools/build_package.py` → spec、BC mip、base.tpac → AssetTool cloth patch → `module/TianxiangT5/AssetPackages/tx5.tpac` |
| 最终包重新导出 | mbtool `exportmod`，每个交付 LOD 单独导出到 `build/final_export*` |
| 离线检查 | `tools/verify_assets.py`、`verify_motion.py`、`verify_posture.py`、`verify_visibility.py`、`verify_grip.py`；按当前返修目标选择，旧断言不直接套用新版本 |
| 预览 | `tools/render_review.py`、`render_motion_review.py`；原生动画读取、逐帧蒙皮与最终包核对见 [动画离线预览流程](asset-workflow.md#原生动画离线预览) |
| 交付 | 工作区根 `tools/package_delivery.py --mod <ModId> --version <版本>`；先 `--check-only`，源包清单取模组 mod.json |

构建顺序：原始输入 → 绑骨/局部造型 → LOD/几何 → 材质/贴图/TPAC → 最终包重新导出 → 验证/预览 → 安装/打包 → 本地提交。材质返修可从构建包开始，但重新打包不能悄悄覆盖手改几何。

Blender 示例（天香专用，新工程先适配脚本）：

```powershell
& 'D:\Blender Foundation\Blender 5.2\blender.exe' --background --python-exit-code 1 --python 'D:\gpt-mb2-mod2\mods\TianxiangT5\tools\rig_model.py'
# 上一步成功并检查输出后再继续
& 'D:\Blender Foundation\Blender 5.2\blender.exe' --background --python-exit-code 1 --python 'D:\gpt-mb2-mod2\mods\TianxiangT5\tools\export_geometry.py'
& 'C:\ProgramData\anaconda3\python.exe' -X utf8 'D:\gpt-mb2-mod2\mods\TianxiangT5\tools\build_package.py'
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

工作区根 `tools/new_mod.py <ModId>` 只创建隔离目录和 mod.json，不复制天香资源，也不生成可用模块。共用 `tools/install_release.ps1 -Mod <ModId> -Version <版本> -CheckOnly` 检查输入与报告；真实安装需在任务授权范围内去掉 CheckOnly，已有交付包时提供 PreviousVersion 保留旧包。发布检查报告由 mod.json 指定，必须对应当前版本及最终 TPAC SHA256。脚本不自动提交 Git 或打标签。

天香 `tools/verify_*` 仍有物体名、旧基线标签和统计数的专用断言，新模型按实际 manifest 改写。旧标签中的 `module/TianxiangT5/...` 是历史仓库路径，不能简单替换成新路径；对比迁移后的新标签则使用对应版本的真实路径。

示例中曾用 Roslyn 编译 AssetTool，避开无法恢复的包依赖。迁移时先尝试实际项目构建；如需手工编译，用已安装 SDK、适配目标框架和实际引用，不照抄 SDK 版本号。未完成工具兼容性验证时保留源文件、报告具体缺项，不输出“已生成可用 Mod”。
