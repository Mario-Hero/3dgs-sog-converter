"""Tkinter GUI for the 3DGS -> SOG converter.

Standard library only. The conversion itself lives in ``core.py`` and is
executed in a worker thread so the window stays responsive.
"""

from __future__ import annotations

import os
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk

from . import core

WINDOW_TITLE = "3DGS → SOG Converter"
MAX_LOG_LINES = 2000


class ConverterApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(WINDOW_TITLE)
        self.geometry("960x760")
        self.minsize(860, 680)
        self._enable_windows_dpi()

        self.cli: str | None = core.find_cli()
        self.queue: queue.Queue = queue.Queue()
        self.cancel_event = threading.Event()
        self.worker: threading.Thread | None = None
        self._replace_warned = False

        self._build_widgets()
        self.after(80, self._poll_queue)
        self._refresh_cli_status()

    @staticmethod
    def _enable_windows_dpi() -> None:
        if os.name != "nt":
            return
        try:
            import ctypes

            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (AttributeError, OSError):
            pass

    # ------------------------------------------------------------------ UI

    def _build_widgets(self) -> None:
        root = ttk.Frame(self, padding=12)
        root.pack(fill=tk.BOTH, expand=True)
        root.columnconfigure(0, weight=1)
        row = 0

        header = ttk.Frame(root)
        header.grid(row=row, column=0, sticky="ew", pady=(0, 10))
        ttk.Label(header, text=WINDOW_TITLE, font=("TkDefaultFont", 14, "bold")).pack(side=tk.LEFT)
        self.cli_label = ttk.Label(header, text="检测工具中…", foreground="#666666")
        self.cli_label.pack(side=tk.RIGHT)
        row += 1

        # ---- input -----------------------------------------------------
        inputs = ttk.LabelFrame(root, text=" 1. 输入（文件或文件夹） ", padding=10)
        inputs.grid(row=row, column=0, sticky="ew", pady=4)
        inputs.columnconfigure(0, weight=1)
        row += 1

        list_frame = ttk.Frame(inputs)
        list_frame.grid(row=0, column=0, columnspan=4, sticky="ew", pady=(0, 8))
        list_frame.columnconfigure(0, weight=1)
        self.input_list = tk.Listbox(list_frame, height=6, selectmode=tk.EXTENDED,
                                     activestyle="dotbox")
        self.input_list.grid(row=0, column=0, sticky="ew")
        scroll = ttk.Scrollbar(list_frame, orient=tk.VERTICAL,
                               command=self.input_list.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.input_list.configure(yscrollcommand=scroll.set)

        buttons = ttk.Frame(inputs)
        buttons.grid(row=1, column=0, columnspan=4, sticky="w")
        ttk.Button(buttons, text="添加文件…", command=self._add_files).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(buttons, text="添加文件夹…", command=self._add_folder).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(buttons, text="移除选中", command=self._remove_selected).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(buttons, text="清空", command=self._clear_inputs).pack(side=tk.LEFT)
        self.recursive_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(buttons, text="包含子文件夹", variable=self.recursive_var).pack(side=tk.LEFT, padx=(18, 0))

        # ---- output ----------------------------------------------------
        outputs = ttk.LabelFrame(root, text=" 2. 输出 ", padding=10)
        outputs.grid(row=row, column=0, sticky="ew", pady=4)
        outputs.columnconfigure(1, weight=1)
        row += 1

        ttk.Label(outputs, text="输出目录:").grid(row=0, column=0, sticky="w")
        self.output_var = tk.StringVar()
        self.output_entry = ttk.Entry(outputs, textvariable=self.output_var)
        self.output_entry.grid(row=0, column=1, sticky="ew", padx=6)
        self.output_browse = ttk.Button(outputs, text="浏览…", command=self._browse_output)
        self.output_browse.grid(row=0, column=2)
        self.output_open = ttk.Button(outputs, text="打开", command=self._open_output)
        self.output_open.grid(row=0, column=3, padx=(6, 0))

        self.overwrite_var = tk.BooleanVar(value=False)
        self.overwrite_check = ttk.Checkbutton(
            outputs, text="覆盖已存在的输出文件", variable=self.overwrite_var)
        self.overwrite_check.grid(row=1, column=0, columnspan=4, sticky="w", pady=(8, 0))

        self.replace_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            outputs,
            text="覆盖源文件：输出到源目录同名 .sog，成功后把原文件移入回收站",
            variable=self.replace_var, command=self._on_replace_toggle,
        ).grid(row=2, column=0, columnspan=4, sticky="w", pady=(4, 0))

        # ---- compression ----------------------------------------------
        options = ttk.LabelFrame(root, text=" 3. 压缩选项 ", padding=10)
        options.grid(row=row, column=0, sticky="ew", pady=4)
        row += 1

        ttk.Label(options, text="压缩点数:").grid(row=0, column=0, sticky="w")
        mode_frame = ttk.Frame(options)
        mode_frame.grid(row=0, column=1, columnspan=5, sticky="w", padx=6)
        self.mode_var = tk.StringVar(value="keep")
        ttk.Radiobutton(mode_frame, text="保持原样", value="keep",
                        variable=self.mode_var, command=self._sync_mode).pack(side=tk.LEFT)
        ttk.Radiobutton(mode_frame, text="指定数量", value="count",
                        variable=self.mode_var, command=self._sync_mode).pack(side=tk.LEFT, padx=(14, 0))
        self.count_entry = ttk.Entry(mode_frame, width=10)
        self.count_entry.insert(0, "400000")
        self.count_entry.pack(side=tk.LEFT, padx=(4, 0))
        ttk.Radiobutton(mode_frame, text="保留百分比", value="percent",
                        variable=self.mode_var, command=self._sync_mode).pack(side=tk.LEFT, padx=(14, 0))
        self.percent_entry = ttk.Entry(mode_frame, width=6)
        self.percent_entry.insert(0, "50")
        self.percent_entry.pack(side=tk.LEFT, padx=(4, 0))
        ttk.Label(mode_frame, text="%").pack(side=tk.LEFT)

        self.filter_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options, text="剔除极低透明度高斯 (opacity > 0.02，仅在减点时生效)",
                        variable=self.filter_var).grid(row=1, column=0, columnspan=6, sticky="w", pady=(8, 0))

        ttk.Label(options, text="WebP 压缩强度 (0–9):").grid(row=2, column=0, sticky="w", pady=(8, 0))
        self.effort_var = tk.StringVar(value="6")
        ttk.Spinbox(options, from_=0, to=9, width=5, textvariable=self.effort_var).grid(
            row=2, column=1, sticky="w", padx=6, pady=(8, 0))
        self.cpu_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(options, text="强制 CPU 压缩（无可用 GPU 时勾选）",
                        variable=self.cpu_var).grid(row=2, column=2, columnspan=4, sticky="w", pady=(8, 0))

        # ---- actions ---------------------------------------------------
        actions = ttk.Frame(root)
        actions.grid(row=row, column=0, sticky="ew", pady=(10, 6))
        row += 1
        self.start_button = ttk.Button(actions, text="开始转换", command=self._start)
        self.start_button.pack(side=tk.LEFT)
        self.cancel_button = ttk.Button(actions, text="取消", command=self._cancel, state=tk.DISABLED)
        self.cancel_button.pack(side=tk.LEFT, padx=6)
        self.progress = ttk.Progressbar(actions, mode="determinate")
        self.progress.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=12)
        self.status_var = tk.StringVar(value="就绪")
        ttk.Label(actions, textvariable=self.status_var, width=16).pack(side=tk.RIGHT)

        # ---- log -------------------------------------------------------
        log_frame = ttk.LabelFrame(root, text=" 日志 ", padding=6)
        log_frame.grid(row=row, column=0, sticky="nsew", pady=4)
        root.rowconfigure(row, weight=1)
        self.log_text = scrolledtext.ScrolledText(
            log_frame, height=12, wrap=tk.WORD, font="TkFixedFont",
            state=tk.DISABLED, background="#141414", foreground="#dddddd",
            insertbackground="#dddddd",
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)
        self._log("提示: 首次使用请先安装 Node.js 与 @playcanvas/splat-transform（见 README）。")
        self._sync_mode()

    # ------------------------------------------------------------- helpers

    def _log(self, message: str) -> None:
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, message + "\n")
        line_count = int(self.log_text.index("end-1c").split(".")[0])
        if line_count > MAX_LOG_LINES:
            self.log_text.delete("1.0", f"{line_count - MAX_LOG_LINES}.0")
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def _refresh_cli_status(self) -> None:
        if not self.cli:
            self.cli_label.configure(text="✗ 未找到 splat-transform", foreground="#c0392b")
            self.start_button.configure(state=tk.DISABLED)
            self._log("错误: 未找到 splat-transform。请执行 npm install -g @playcanvas/splat-transform，"
                      "或设置环境变量 SPLAT_TRANSFORM 指向可执行文件。")
            return
        version = core.cli_version(self.cli)
        self.cli_label.configure(text=f"✓ {version}", foreground="#1d7a4d")
        self._log(f"已找到转换工具: {self.cli} ({version})")

    def _sync_mode(self) -> None:
        mode = self.mode_var.get()
        self.count_entry.configure(state=tk.NORMAL if mode == "count" else tk.DISABLED)
        self.percent_entry.configure(state=tk.NORMAL if mode == "percent" else tk.DISABLED)

    def _autofill_output(self, path: str) -> None:
        if self.output_var.get().strip():
            return
        parent = Path(path).parent if Path(path).is_file() else Path(path)
        self.output_var.set(str(parent / "sog_output"))

    def _add_files(self) -> None:
        paths = filedialog.askopenfilenames(
            title="选择 3DGS 文件",
            filetypes=[("3DGS 文件", "*.ply *.spz *.splat *.ksplat"), ("所有文件", "*.*")],
        )
        for path in paths:
            if path not in self.input_list.get(0, tk.END):
                self.input_list.insert(tk.END, path)
        if paths:
            self._autofill_output(paths[0])
            self._log(f"已添加 {len(paths)} 个文件")

    def _add_folder(self) -> None:
        path = filedialog.askdirectory(title="选择包含 3DGS 文件的文件夹")
        if not path:
            return
        if path not in self.input_list.get(0, tk.END):
            self.input_list.insert(tk.END, path)
        self._autofill_output(path)
        self._log(f"已添加文件夹: {path}")

    def _remove_selected(self) -> None:
        for index in reversed(self.input_list.curselection()):
            self.input_list.delete(index)

    def _clear_inputs(self) -> None:
        self.input_list.delete(0, tk.END)

    def _browse_output(self) -> None:
        path = filedialog.askdirectory(title="选择输出目录")
        if path:
            self.output_var.set(path)

    def _open_output(self) -> None:
        path = Path(self.output_var.get().strip() or ".")
        if not path.is_dir():
            messagebox.showinfo(WINDOW_TITLE, "输出目录尚不存在。")
            return
        import subprocess
        import sys

        try:
            if os.name == "nt":
                os.startfile(str(path))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except (AttributeError, OSError):
            messagebox.showinfo(WINDOW_TITLE, str(path))

    def _on_replace_toggle(self) -> None:
        enabled = self.replace_var.get()
        state = tk.DISABLED if enabled else tk.NORMAL
        self.output_entry.configure(state=state)
        self.output_browse.configure(state=state)
        if enabled:
            self.overwrite_var.set(True)
            self.overwrite_check.configure(state=tk.DISABLED)
            if not self._replace_warned:
                self._replace_warned = True
                ok = messagebox.askyesno(
                    WINDOW_TITLE,
                    "「覆盖源文件」会把转换结果写到原文件所在目录，并在转换成功后\n"
                    "把原始文件移入系统回收站（可从回收站恢复）。\n\n"
                    "建议先对少量文件试用，并保留原始素材备份。\n\n确定启用吗？",
                    icon=messagebox.WARNING,
                )
                if not ok:
                    self.replace_var.set(False)
                    self._on_replace_toggle()
                    return
        else:
            self.overwrite_check.configure(state=tk.NORMAL)
            self.overwrite_var.set(False)

    # -------------------------------------------------------------- worker

    def _build_options(self) -> core.Options:
        mode = self.mode_var.get()
        entry = self.count_entry if mode == "count" else self.percent_entry
        raw_value = entry.get().strip() if mode != "keep" else ""
        if mode == "keep":
            value = 0
        elif not raw_value:
            raise ValueError("请填写目标点数或保留百分比")
        else:
            try:
                value = int(raw_value)
            except ValueError as exc:
                raise ValueError("点数与百分比必须是整数") from exc

        opts = core.Options(
            output_dir=Path(self.output_var.get().strip()) if self.output_var.get().strip() else None,
            overwrite_existing=self.overwrite_var.get(),
            replace_source=self.replace_var.get(),
            decimate_mode=mode,
            decimate_value=value,
            filter_low_opacity=self.filter_var.get(),
            webp_effort=int(self.effort_var.get()),
            use_cpu=self.cpu_var.get(),
        )
        opts.validate()
        return opts

    def _start(self) -> None:
        if self.worker and self.worker.is_alive():
            return
        if not self.cli:
            messagebox.showerror(WINDOW_TITLE, "未找到 splat-transform，请先安装（见 README）。")
            return

        paths = list(self.input_list.get(0, tk.END))
        if not paths:
            messagebox.showwarning(WINDOW_TITLE, "请先添加文件或文件夹。")
            return
        try:
            opts = self._build_options()
        except ValueError as exc:
            messagebox.showwarning(WINDOW_TITLE, str(exc))
            return

        sources = core.collect_inputs(paths, recursive=self.recursive_var.get())
        if not sources:
            messagebox.showwarning(WINDOW_TITLE, "未找到可转换的 .ply / .spz / .splat / .ksplat 文件。")
            return
        jobs = core.plan_jobs(sources, opts)

        if opts.replace_source:
            preview = "\n".join(str(p) for p in sources[:5])
            more = f"\n… 共 {len(sources)} 个文件" if len(sources) > 5 else ""
            ok = messagebox.askyesno(
                WINDOW_TITLE,
                f"即将对 {len(sources)} 个文件执行「覆盖源文件」，原文件会被移入回收站：\n\n"
                f"{preview}{more}\n\n确定继续吗？",
                icon=messagebox.WARNING,
            )
            if not ok:
                return

        self.log_text.configure(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        self.log_text.configure(state=tk.DISABLED)
        self._log(f"开始转换，共 {len(jobs)} 个任务。")

        self.cancel_event.clear()
        self.start_button.configure(state=tk.DISABLED)
        self.cancel_button.configure(state=tk.NORMAL)
        self.progress.configure(value=0, maximum=len(jobs))
        self.status_var.set("转换中…")

        cli = self.cli
        self.worker = threading.Thread(
            target=self._worker, args=(jobs, opts, cli), daemon=True
        )
        self.worker.start()

    def _worker(self, jobs, opts: core.Options, cli: str) -> None:
        def emit(message: str) -> None:
            self.queue.put(("log", message))

        def check() -> None:
            if self.cancel_event.is_set():
                raise core.Cancelled()

        def progress(done: int, total: int, result: core.Result) -> None:
            self.queue.put(("progress", (done, total, result)))

        try:
            report = core.run_conversion(jobs, opts, cli, emit, check, progress)
            self.queue.put(("done", report))
        except core.Cancelled:
            self.queue.put(("cancelled", None))
        except Exception as exc:  # noqa: BLE001 - surfaced to the user
            self.queue.put(("fatal", str(exc)))

    def _cancel(self) -> None:
        if self.worker and self.worker.is_alive():
            self.cancel_event.set()
            self.status_var.set("取消中…")
            self._log("收到取消请求，等待当前步骤结束…")

    def _poll_queue(self) -> None:
        try:
            while True:
                kind, payload = self.queue.get_nowait()
                if kind == "log":
                    self._log(str(payload))
                elif kind == "progress":
                    done, total, result = payload
                    self.progress.configure(value=done)
                    self.status_var.set(f"{done}/{total}")
                elif kind == "done":
                    self._finish(payload)
                elif kind == "cancelled":
                    self._log("已取消。")
                    self._reset_buttons("已取消")
                elif kind == "fatal":
                    self._log(f"错误: {payload}")
                    messagebox.showerror(WINDOW_TITLE, str(payload))
                    self._reset_buttons("出错")
        except queue.Empty:
            pass
        self.after(80, self._poll_queue)

    def _finish(self, report: core.Report) -> None:
        self._log(
            f"全部完成：成功 {report.converted}，跳过 {report.skipped}，失败 {report.failed}，共 {report.total}。"
        )
        self._reset_buttons("完成")
        if report.failed:
            messagebox.showwarning(
                WINDOW_TITLE,
                f"完成，但有 {report.failed} 个任务失败，请查看日志。",
            )
        elif report.skipped and not report.converted:
            messagebox.showinfo(
                WINDOW_TITLE,
                "没有文件被转换（目标文件均已存在）。\n可勾选「覆盖已存在的输出文件」。",
            )

    def _reset_buttons(self, status: str) -> None:
        self.start_button.configure(state=tk.NORMAL)
        self.cancel_button.configure(state=tk.DISABLED)
        self.status_var.set(status)


def main() -> None:
    app = ConverterApp()
    app.mainloop()


if __name__ == "__main__":
    main()
