# 3DGS → SOG 转换器
*3DGS → SOG Converter*

![中文界面](assets/screenshot-zh.png)  
![English UI](assets/screenshot-en.png)

一个带图形界面的开源小工具，用于把 3D Gaussian Splatting 场景批量转换为 PlayCanvas 的 SOG 格式。  
A small open-source desktop GUI for batch-converting 3D Gaussian Splatting scenes into PlayCanvas SOG files.

界面支持中英文自动切换，也支持用命令行参数指定启动语言；本 README 采用中文一行、英文一行的逐行对照排版。  
The interface follows the OS language or an explicit command-line flag; this README alternates Chinese and English line by line.

> 本工具只做格式转换，不含训练或重建能力。SOG 由 PlayCanvas 提出，适合网页与桌面查看器分发。  
> This tool only converts formats; it does not train or reconstruct scenes. SOG was introduced by PlayCanvas for web and desktop delivery.

## 特性
*Features*

- 纯 Python 标准库（tkinter）编写 GUI，无第三方 Python 依赖。  
  GUI built with the Python standard library (tkinter); no third-party Python packages.
- 转换引擎使用 PlayCanvas 开源的 `@playcanvas/splat-transform` CLI。  
  Conversion is powered by PlayCanvas's open-source `@playcanvas/splat-transform` CLI.
- 支持单个文件、多个文件或整个文件夹（可递归），输出目录可任意指定。  
  Accepts single files, multiple files or whole folders (optionally recursive), with a configurable output folder.
- 支持覆盖已存在的输出、覆盖源文件，以及按数量或百分比压缩点数。  
  Supports overwriting existing outputs, replacing source files, and decimating by count or percentage.
- 所有写入先落临时文件再原子替换，转换失败不会破坏已有输出。  
  Every output is written to a temporary file and atomically replaced, so a failed conversion never damages an existing file.
- 中英文界面与日志同步切换，MIT 许可。  
  UI and log messages switch language together; released under the MIT License.

## 界面语言
*Interface language*

启动时按以下优先级决定语言，界面、日志、对话框与错误提示全部同步。  
The language is chosen at startup with the following priority; the UI, log, dialogs and error messages all follow it.

1. 命令行参数 `--lang zh` 或 `--lang en`。  
   The `--lang zh` or `--lang en` command-line argument.
2. 环境变量 `SOG_LANG`（可填 `zh`、`en`、`zh-CN`、`en-US` 等）。  
   The `SOG_LANG` environment variable (`zh`, `en`, `zh-CN`, `en-US`, ...).
3. 操作系统显示语言：Windows 读取 UI language，其他平台读取 `LANG` / `LC_*` 与 locale。  
   The OS display language: Windows UI language, or `LANG` / `LC_*` and locale on other platforms.
4. 以上都识别不了时回退到英文。  
   English is used as the final fallback.

```bash
# 自动跟随系统语言
# Follow the OS language
python app.py

# 强制中文
# Force Chinese
python app.py --lang zh

# 强制英文
# Force English
python app.py --lang en

# 也可以用环境变量
# An environment variable works too
SOG_LANG=en python app.py
```

Windows 下同样可以把参数传给 `run.bat`，例如 `run.bat --lang en`。  
On Windows the same flag works with `run.bat`, for example `run.bat --lang en`.

语言在启动时确定，窗口右上角会显示当前语言（中文 / English）；切换语言请重新启动程序。  
The language is fixed at startup and shown in the top-right corner; restart the app to switch languages.

## 效果参考
*Size reference*

同一份 64 MB 的 SH0 PLY（1,179,648 个高斯）在本工具对应命令下的实测结果。  
Measured results for one 64 MB SH0 PLY containing 1,179,648 Gaussians.

| 输出 / Output | 点数 / Splats | 体积 / Size |
| --- | --- | --- |
| 原始 PLY | 1,179,648 | 64 MB |
| Raw PLY | 1,179,648 | 64 MB |
| SOG（保持原样） | 1,179,648 | 11.6 MB |
| SOG (keep all) | 1,179,648 | 11.6 MB |
| SOG（减点到 400K） | 400,000 | 4.5 MB |
| SOG (decimated to 400K) | 400,000 | 4.5 MB |

## 运行要求
*Requirements*

| 依赖 / Dependency | 版本 / Version | 说明 / Notes |
| --- | --- | --- |
| Python | 3.9+ | 必须包含 tkinter；python.org 官方安装包默认包含。 |
| Python | 3.9+ | Must include tkinter; official python.org builds do. |
| Node.js | 18+ | 用于运行 `splat-transform`。 |
| Node.js | 18+ | Required to run `splat-transform`. |
| npm | 随 Node.js / bundled | 全局安装 CLI。 |
| npm | bundled with Node.js | Used to install the CLI globally. |
| 显卡驱动 / GPU driver | 可选 / optional | SOG 编码优先走 WebGPU；无 GPU 时可勾选强制 CPU 压缩。 |
| GPU driver | optional | SOG encoding prefers WebGPU; force CPU mode when no GPU is available. |

支持 Windows / macOS / Linux，Windows 下推荐 D3D12 或 Vulkan 驱动。  
Works on Windows, macOS and Linux; D3D12 or Vulkan drivers are recommended on Windows.

## 安装
*Installation*

```bash
# 安装转换引擎（一次即可）
# Install the conversion engine (once)
npm install -g @playcanvas/splat-transform

# 验证
# Verify
splat-transform --version
```

然后启动 GUI。  
Then launch the GUI.

```bash
# Windows：双击 run.bat，或使用 py 启动器
# Windows: double-click run.bat, or use the py launcher
py -3 app.py --lang zh

# macOS / Linux
# macOS / Linux
chmod +x run.sh
./run.sh --lang en

# 通用
# Generic
python app.py
```

窗口右上角会显示检测到的 CLI 版本。若显示红色的「未找到 splat-transform」，可设置 `SPLAT_TRANSFORM` 指向可执行文件。  
The top-right corner shows the detected CLI version. If it reports the CLI as missing, point `SPLAT_TRANSFORM` at the executable.

```bash
# Windows PowerShell
# Windows PowerShell
$env:SPLAT_TRANSFORM = "C:\path\to\splat-transform.cmd"

# macOS / Linux
# macOS / Linux
export SPLAT_TRANSFORM=/usr/local/bin/splat-transform
```

## 使用步骤
*Usage*

1. 添加输入：选一个或多个文件，或选整个目录；支持 `.ply`（含 `.compressed.ply`）、`.spz`、`.splat`、`.ksplat`。  
   Add inputs: pick one or more files, or a whole folder. Supported: `.ply` (including `.compressed.ply`), `.spz`, `.splat`, `.ksplat`.
2. 「包含子文件夹」控制是否递归扫描，已经是 `.sog` 的文件会跳过。  
   "Include subfolders" controls recursion; files already in `.sog` are skipped.
3. 设置输出目录：默认填充为首个输入目录下的 `sog_output`，可点「浏览…」修改。  
   Choose an output folder; it defaults to `sog_output` next to the first input and can be changed with "Browse…".
4. 设置压缩选项：保持点数、指定数量或保留百分比，并可调整 WebP 强度。  
   Set compression options: keep all splats, a target count or a keep percentage, plus WebP effort.
5. 点「开始转换」：日志实时显示实际命令与进度，可随时「取消」。  
   Click "Start conversion"; the log streams the actual commands and progress, and "Cancel" works at any time.
6. 完成后日志给出「成功 / 跳过 / 失败」统计。  
   The log finishes with a converted / skipped / failed summary.

## 选项说明
*Options*

| 选项 / Option | 默认 / Default | 说明 / Description |
| --- | --- | --- |
| 包含子文件夹 | 开 | 文件夹输入是否递归扫描。 |
| Include subfolders | On | Whether folder inputs are scanned recursively. |
| 输出目录 | `sog_output` | 同名输出自动追加 `_2`、`_3` 后缀。 |
| Output folder | `sog_output` | Name collisions get `_2`, `_3` suffixes. |
| 覆盖已存在的输出文件 | 关 | 关闭时遇到同名 `.sog` 会跳过，不会改动旧文件。 |
| Overwrite existing output files | Off | When off, an existing `.sog` is skipped and left untouched. |
| 覆盖源文件 | 关 | 见下一节说明。 |
| Replace source | Off | See the next section. |
| 压缩点数 | 保持原样 | 可填指定数量（如 400000）或保留百分比（如 34%）。 |
| Splat count | Keep all | Enter a target count (e.g. 400000) or a keep percentage (e.g. 34%). |
| 剔除极低透明度高斯 | 开 | 仅在减点时生效，附加 `-V opacity,gt,0.02`。 |
| Drop near-invisible Gaussians | On | Decimation only; adds `-V opacity,gt,0.02`. |
| WebP 压缩强度 | 6 | `--webp-effort 0-9`，数值越大越慢、体积略小。 |
| WebP effort | 6 | `--webp-effort 0-9`; higher values are slower and slightly smaller. |
| 强制 CPU 压缩 | 关 | 添加 `-g cpu`；无 GPU 或驱动异常时勾选，速度会明显变慢。 |
| Force CPU compression | Off | Adds `-g cpu`; use when no GPU is available. It is noticeably slower. |

### 覆盖源文件
*Replace source*

勾选后，输出目录锁定为源文件所在目录，文件名与源同名、扩展名改为 `.sog`。  
When enabled, output is written next to each source file with the same base name and a `.sog` extension.

「覆盖已存在的输出文件」会自动启用；转换成功并通过校验后，原始文件被移入操作系统回收站，可从回收站恢复。  
"Overwrite existing output files" is enabled automatically; after a successful, verified conversion the original file is moved to the OS Recycle Bin and can be restored.

启用时会弹出一次警告，每次开始转换前还会列出受影响文件并要求再次确认。  
Enabling it triggers a warning, and every run lists the affected files and asks for a second confirmation.

只有在输出 `.sog` 成功生成后才会移动原文件；转换失败时原文件保持不动。  
The original is moved only after the `.sog` output is generated and verified; a failed conversion leaves it untouched.

若输入本身是 `.sog`，该文件会被跳过，避免自覆盖。  
Inputs already in `.sog` are skipped to avoid self-overwrite.

回收站功能在 Windows 上通过 `SHFileOperationW` 实现；macOS / Linux 下不会删除原文件，日志会提示手动处理。  
Recycle Bin support uses `SHFileOperationW` on Windows; on macOS / Linux the original is kept and the log asks you to handle it manually.

建议先对少量文件试用，并保留原始素材的独立备份。  
Try it on a few files first and keep a separate backup of your source assets.

## 转换原理
*How conversion works*

`--decimate` 在 `splat-transform` 中必须是最后一个 action 且必须输出 `.ply`，因此启用减点时分两步执行。  
`--decimate` must be the final action in `splat-transform` and must write a `.ply`, so decimation always runs in two steps.

中间文件放在系统临时目录，结束后自动清理。  
Intermediate files live in a system temporary directory and are removed automatically.

```bash
# 第一步：减点（可选）
# Step 1: decimate (optional)
splat-transform input.ply -N -V opacity,gt,0.02 -d 400000 \
  --scratch-dir <temp>/scratch <temp>/decimated.ply

# 第二步：编码 SOG
# Step 2: encode SOG
splat-transform --webp-effort 6 <temp>/decimated.ply output.sog
```

不减点时只需第二步。GUI 日志里显示的实际命令可直接复制用于批处理或 CI。  
Without decimation only step 2 runs. The exact commands shown in the GUI log can be reused in scripts or CI.

所有输出先写为 `.<name>.__tmp__.sog`，校验非空后用 `os.replace` 原子替换目标文件。  
Outputs are first written as `.<name>.__tmp__.sog` and, once verified, atomically moved into place with `os.replace`.

## 脚本调用（无 GUI）
*Scripting (headless)*

`core.py` 不依赖 tkinter，可在批处理脚本或 CI 中直接调用。  
`core.py` has no tkinter dependency and can be imported directly from scripts or CI.

```python
from pathlib import Path
from sog_converter import core, i18n

# 日志与错误信息也跟随界面语言
# Log lines and errors follow the selected UI language too
i18n.set_language("en")

cli = core.find_cli()
opts = core.Options(
    output_dir=Path("./out"),
    overwrite_existing=True,
    decimate_mode="count",
    decimate_value=400000,
    webp_effort=6,
)
opts.validate()

sources = core.collect_inputs([r"D:\captures\sequence"], recursive=True)
jobs = core.plan_jobs(sources, opts)
report = core.run_conversion(jobs, opts, cli, log=print)

print(report.converted, report.skipped, report.failed)
```

## 常见问题
*FAQ*

**问：提示未找到 splat-transform？**  
**Q: The app says splat-transform was not found.**

确认 `npm install -g @playcanvas/splat-transform` 已执行，且 npm 全局 bin 目录在 PATH 中；也可设置 `SPLAT_TRANSFORM`。  
Ensure `npm install -g @playcanvas/splat-transform` has run and npm's global bin is on PATH, or set `SPLAT_TRANSFORM`.

**问：中文路径或带空格的路径能处理吗？**  
**Q: Do non-ASCII or spaced paths work?**

可以。程序使用参数列表方式调用子进程，不经过 shell 拼接。  
Yes. Subprocesses receive an argument list; no shell string is constructed.

**问：转换时卡住或报 WebGPU 错误？**  
**Q: Conversion stalls or reports a WebGPU error.**

勾选「强制 CPU 压缩」重试，或更新显卡驱动；CPU 模式速度会慢 5–10 倍。  
Enable "Force CPU compression" or update your GPU driver; CPU mode is 5–10× slower.

**问：为什么网页端能打开 SOG，却打不开 SPZ？**  
**Q: Why does my web viewer open SOG but not SPZ?**

SOG 是 ZIP 容器（内含 WebP 属性图与 `meta.json`），浏览器原生可解 WebP；SPZ v4 使用 ZSTD，查看器需额外注册解码器。  
SOG is a ZIP of WebP images plus `meta.json`, decoded natively by browsers; SPZ v4 uses ZSTD and needs a registered decoder.

用本工具统一转 SOG 即可规避大部分兼容问题。  
Converting everything to SOG with this tool avoids most of those compatibility issues.

**问：Unity 里怎么查看 SOG？**  
**Q: How do I view SOG in Unity?**

`aras-p/UnityGaussianSplatting` 原版不直接支持 SOG；`Enndee/Splatviewer_VR`（Unity 6 / D3D12 / OpenXR）支持运行时加载 bundled `.sog`，建议 1.2 以上版本。  
Upstream `aras-p/UnityGaussianSplatting` does not read SOG directly; `Enndee/Splatviewer_VR` (Unity 6 / D3D12 / OpenXR) loads bundled `.sog` at runtime, version 1.2 or newer recommended.

**问：点数压缩会损失画质吗？**  
**Q: Does decimation reduce quality?**

会。减点采用渐进式成对合并，低透明度过滤会移除几乎不可见的高斯；金属、玻璃等强反光材质建议保留点数。  
Yes. Decimation merges splats progressively and the opacity filter drops nearly invisible ones; keep the full count for reflective materials.

## 项目结构
*Project layout*

主要文件如下。  
The main files are listed below.

```
3dgs-sog-converter/
├── app.py                    # 入口 / entry point
├── run.bat / run.sh          # 启动脚本 / launch scripts
├── sog_converter/
│   ├── __init__.py
│   ├── core.py               # 转换逻辑 / conversion logic
│   ├── gui.py                # 界面 / Tkinter UI
│   └── i18n.py               # 中英文字串 / bilingual strings
├── tests/
│   ├── test_core.py
│   └── test_i18n.py
├── assets/                   # 中英界面截图 / UI screenshots
├── LICENSE
└── README.md
```

## 运行测试
*Run the tests*

```bash
python -m unittest discover -s tests -v
```

测试只覆盖核心逻辑与语言表，不需要安装 CLI，也不需要图形环境。  
Tests cover the conversion core and the string tables; no CLI and no display are required.

## 上传到 GitHub 前
*Before publishing to GitHub*

- [ ] 把 `LICENSE` 中的版权行改成自己的名字或组织（当前为 `3DGS SOG Converter contributors`）。  
  Replace the copyright holder in `LICENSE` with your own name or organisation.
- [ ] 确认没有把模型文件、日志或 `sog_output/` 提交进仓库（`.gitignore` 已覆盖）。  
  Check that no models, logs or `sog_output/` folders were committed (`.gitignore` covers them).
- [ ] 在 GitHub 仓库设置中填写描述与 topics：`3d-gaussian-splatting`、`sog`、`gaussian-splatting`、`converter`。  
  Add a description and topics in GitHub: `3d-gaussian-splatting`, `sog`, `gaussian-splatting`, `converter`.

## 许可与致谢
*License and credits*

本项目代码采用 MIT License，详见 `LICENSE`。  
The code in this project is released under the MIT License; see `LICENSE`.

转换能力来自以下开源项目，使用时请遵守各自的许可。  
Conversion relies on the following open-source projects; please respect their licenses.

- PlayCanvas `splat-transform`（MIT）：格式转换与 SOG 编码。  
  PlayCanvas `splat-transform` (MIT): format conversion and SOG encoding.
- PlayCanvas Engine（MIT）：SOG 格式与查看器。  
  PlayCanvas Engine (MIT): the SOG format and viewer.
- Niantic SPZ（MIT）：支持的输入格式之一。  
  Niantic SPZ (MIT): one of the supported input formats.

另需注意：若你的 PLY 素材由 INRIA 官方 3DGS 训练代码产出，商业使用需单独确认原项目许可。  
Note: if your PLY assets were produced by INRIA's official 3DGS training code, check that project's license for commercial use.

本工具的 MIT 许可不覆盖素材本身的授权。  
This tool's MIT License does not cover the licensing of your source assets.
