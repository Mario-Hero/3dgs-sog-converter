"""Tkinter GUI for the 3DGS -> SOG converter.

Standard library only. All visible strings come from :mod:`sog_converter.i18n`,
so the UI follows the OS language or an explicit ``--lang`` argument.
The conversion itself lives in ``core.py`` and runs in a worker thread.
"""

from __future__ import annotations

import os
import queue
import subprocess
import sys
import time
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk

from . import core, i18n

MAX_LOG_LINES = 2000


class ConverterApp(tk.Tk):
    def __init__(self) -> None:
        self._enable_high_dpi()
        super().__init__()
        self.title_text = i18n.t("app_title")
        self.title(self.title_text)
        self.minsize(860, 680)
        self._apply_dpi_scaling()

        self.cli: str | None = core.find_cli()
        self.queue: queue.Queue = queue.Queue()
        self.cancel_event = threading.Event()
        self.worker: threading.Thread | None = None
        self._replace_warned = False
        self._poll_after_id: str | None = None
        # Time tracking for the elapsed / remaining display.
        self._start_time: float = 0.0
        self._done: int = 0
        self._total: int = 0
        self._time_after: str | None = None

        self._build_widgets()
        self.update_idletasks()
        # Size the window to its real content instead of a hard-coded height,
        # otherwise the bottom action buttons overflow and get clipped.
        fit_w = max(960, self.winfo_reqwidth())
        fit_h = max(680, self.winfo_reqheight())
        self.geometry(f"{fit_w}x{fit_h}")
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(80, self._poll_queue)
        self._refresh_cli_status()

    def _on_close(self) -> None:
        """Cancel the polling timer before destroying the window."""
        if self._poll_after_id is not None:
            try:
                self.after_cancel(self._poll_after_id)
            except tk.TclError:
                pass
        if self._time_after is not None:
            try:
                self.after_cancel(self._time_after)
            except tk.TclError:
                pass
        self.destroy()

    @staticmethod
    def _enable_high_dpi() -> None:
        """Declare DPI awareness before any window is created.

        Must run before ``tkinter.Tk()`` so the OS reports the true monitor
        DPI instead of bitmap-stretching the window (which makes it tiny or
        blurry on high-DPI displays).
        """
        if os.name != "nt":
            return
        try:
            import ctypes

            # PROCESS_PER_MONITOR_DPI_AWARE_V2 (best) -> per-monitor -> system.
            try:
                ctypes.windll.shcore.SetProcessDpiAwarenessContext(-4)
            except (AttributeError, OSError):
                try:
                    ctypes.windll.shcore.SetProcessDpiAwareness(2)
                except (AttributeError, OSError):
                    ctypes.windll.user32.SetProcessDPIAware()
        except (AttributeError, OSError):
            pass

    def _apply_dpi_scaling(self) -> None:
        """Ask Tk to scale fonts to the real monitor DPI.

        Tk only knows the default (96 DPI) font metrics unless we tell it the
        physical DPI, so a 150% display would otherwise show tiny text.
        """
        if os.name != "nt":
            return
        try:
            import ctypes

            self.update_idletasks()
            hwnd = self.winfo_id()
            dpi = ctypes.windll.user32.GetDpiForWindow(hwnd) if hwnd else 0
            if not dpi or dpi <= 0:
                dpi = ctypes.windll.user32.GetDpiForSystem()
            if dpi and dpi > 0:
                self.tk.call("tk", "scaling", "-displayof", ".", dpi / 72.0)
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

        # ---- left: export format selector ----
        self.format_keys = ["sog", "compressed_ply"]
        self.format_values = [i18n.t("fmt_sog"), i18n.t("fmt_compressed_ply")]
        self.format_var = tk.StringVar(value=self.format_values[0])
        ttk.Label(header, text=i18n.t("lbl_format")).pack(side=tk.LEFT)
        self.format_combo = ttk.Combobox(
            header, values=self.format_values, textvariable=self.format_var,
            state="readonly", width=26,
        )
        self.format_combo.pack(side=tk.LEFT, padx=(6, 0))

        # spacer pushes the tool controls to the far right
        ttk.Frame(header).pack(side=tk.LEFT, fill=tk.X, expand=True)

        # ---- right: tool locator ----
        self.cli_browse = ttk.Button(header, text=i18n.t("btn_locate_tool"),
                                     command=self._browse_cli)
        self.cli_browse.pack(side=tk.RIGHT, padx=(8, 0))
        self.cli_label = ttk.Label(header, text=i18n.t("cli_detecting"),
                                   foreground="#666666")
        self.cli_label.pack(side=tk.RIGHT)
        row += 1

        # ---- input -----------------------------------------------------
        inputs = ttk.LabelFrame(root, text=i18n.t("frame_input"), padding=10)
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
        ttk.Button(buttons, text=i18n.t("btn_add_files"),
                   command=self._add_files).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(buttons, text=i18n.t("btn_add_folder"),
                   command=self._add_folder).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(buttons, text=i18n.t("btn_remove"),
                   command=self._remove_selected).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(buttons, text=i18n.t("btn_clear"),
                   command=self._clear_inputs).pack(side=tk.LEFT)
        self.recursive_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(buttons, text=i18n.t("chk_recursive"),
                        variable=self.recursive_var).pack(side=tk.LEFT, padx=(18, 0))

        # ---- output ----------------------------------------------------
        outputs = ttk.LabelFrame(root, text=i18n.t("frame_output"), padding=10)
        outputs.grid(row=row, column=0, sticky="ew", pady=4)
        outputs.columnconfigure(1, weight=1)
        row += 1

        ttk.Label(outputs, text=i18n.t("lbl_output_dir")).grid(row=0, column=0, sticky="w")
        self.output_var = tk.StringVar()
        self.output_entry = ttk.Entry(outputs, textvariable=self.output_var)
        self.output_entry.grid(row=0, column=1, sticky="ew", padx=6)
        self.output_browse = ttk.Button(outputs, text=i18n.t("btn_browse"),
                                        command=self._browse_output)
        self.output_browse.grid(row=0, column=2)
        self.output_open = ttk.Button(outputs, text=i18n.t("btn_open"),
                                      command=self._open_output)
        self.output_open.grid(row=0, column=3, padx=(6, 0))

        self.overwrite_var = tk.BooleanVar(value=False)
        self.overwrite_check = ttk.Checkbutton(
            outputs, text=i18n.t("chk_overwrite"), variable=self.overwrite_var)
        self.overwrite_check.grid(row=1, column=0, columnspan=4, sticky="w", pady=(8, 0))

        self.replace_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            outputs, text=i18n.t("chk_replace"),
            variable=self.replace_var, command=self._on_replace_toggle,
        ).grid(row=2, column=0, columnspan=4, sticky="w", pady=(4, 0))

        # ---- compression ----------------------------------------------
        options = ttk.LabelFrame(root, text=i18n.t("frame_options"), padding=10)
        options.grid(row=row, column=0, sticky="ew", pady=4)
        row += 1

        ttk.Label(options, text=i18n.t("lbl_decimate")).grid(row=0, column=0, sticky="w")
        mode_frame = ttk.Frame(options)
        mode_frame.grid(row=0, column=1, columnspan=5, sticky="w", padx=6)
        self.mode_var = tk.StringVar(value="keep")
        ttk.Radiobutton(mode_frame, text=i18n.t("radio_keep"), value="keep",
                        variable=self.mode_var, command=self._sync_mode).pack(side=tk.LEFT)
        ttk.Radiobutton(mode_frame, text=i18n.t("radio_count"), value="count",
                        variable=self.mode_var, command=self._sync_mode).pack(side=tk.LEFT, padx=(14, 0))
        self.count_entry = ttk.Entry(mode_frame, width=10)
        self.count_entry.insert(0, "400000")
        self.count_entry.pack(side=tk.LEFT, padx=(4, 0))
        ttk.Radiobutton(mode_frame, text=i18n.t("radio_percent"), value="percent",
                        variable=self.mode_var, command=self._sync_mode).pack(side=tk.LEFT, padx=(14, 0))
        self.percent_entry = ttk.Entry(mode_frame, width=6)
        self.percent_entry.insert(0, "50")
        self.percent_entry.pack(side=tk.LEFT, padx=(4, 0))
        ttk.Label(mode_frame, text="%").pack(side=tk.LEFT)

        self.filter_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options, text=i18n.t("chk_filter"),
                        variable=self.filter_var).grid(
                            row=1, column=0, columnspan=6, sticky="w", pady=(8, 0))

        ttk.Label(options, text=i18n.t("lbl_webp")).grid(row=2, column=0, sticky="w", pady=(8, 0))
        self.effort_var = tk.StringVar(value="6")
        ttk.Spinbox(options, from_=0, to=9, width=5,
                    textvariable=self.effort_var).grid(
                        row=2, column=1, sticky="w", padx=6, pady=(8, 0))
        self.cpu_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(options, text=i18n.t("chk_cpu"),
                        variable=self.cpu_var).grid(
                            row=2, column=2, columnspan=4, sticky="w", pady=(8, 0))

        # ---- actions ---------------------------------------------------
        actions = ttk.Frame(root)
        actions.grid(row=row, column=0, sticky="ew", pady=(10, 6))
        row += 1
        self.start_button = ttk.Button(actions, text=i18n.t("btn_start"),
                                       command=self._start)
        self.start_button.pack(side=tk.LEFT)
        self.cancel_button = ttk.Button(actions, text=i18n.t("btn_cancel"),
                                        command=self._cancel, state=tk.DISABLED)
        self.cancel_button.pack(side=tk.LEFT, padx=6)
        self.progress = ttk.Progressbar(actions, mode="determinate")
        self.progress.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=12)
        self.time_var = tk.StringVar(value=i18n.t("time_idle"))
        ttk.Label(actions, textvariable=self.time_var, width=30,
                  anchor="e").pack(side=tk.RIGHT, padx=(0, 8))
        self.status_var = tk.StringVar(value=i18n.t("status_ready"))
        ttk.Label(actions, textvariable=self.status_var, width=16).pack(side=tk.RIGHT)

        # ---- log -------------------------------------------------------
        log_frame = ttk.LabelFrame(root, text=i18n.t("frame_log"), padding=6)
        log_frame.grid(row=row, column=0, sticky="nsew", pady=4)
        root.rowconfigure(row, weight=1)
        self.log_text = scrolledtext.ScrolledText(
            log_frame, height=12, wrap=tk.WORD, font="TkFixedFont",
            state=tk.DISABLED, background="#141414", foreground="#dddddd",
            insertbackground="#dddddd",
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)
        self._log(i18n.t("log_hint"))
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
            self.cli_label.configure(text=i18n.t("cli_missing"), foreground="#c0392b")
            self.start_button.configure(state=tk.DISABLED)
            self._log(i18n.t("log_cli_missing"))
            return
        version = core.cli_version(self.cli)
        self.cli_label.configure(text=i18n.t("cli_ok", version=version),
                                 foreground="#1d7a4d")
        self._log(i18n.t("log_cli_found", cli=self.cli, version=version))

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
            title=i18n.t("dlg_open_files"),
            filetypes=[(i18n.t("dlg_filetypes"), "*.ply *.spz *.splat *.ksplat"),
                       (i18n.t("dlg_all_files"), "*.*")],
        )
        for path in paths:
            if path not in self.input_list.get(0, tk.END):
                self.input_list.insert(tk.END, path)
        if paths:
            self._autofill_output(paths[0])
            self._log(i18n.t("log_added_files", count=len(paths)))

    def _add_folder(self) -> None:
        path = filedialog.askdirectory(title=i18n.t("dlg_open_folder"))
        if not path:
            return
        if path not in self.input_list.get(0, tk.END):
            self.input_list.insert(tk.END, path)
        self._autofill_output(path)
        self._log(i18n.t("log_added_folder", path=path))

    def _remove_selected(self) -> None:
        for index in reversed(self.input_list.curselection()):
            self.input_list.delete(index)

    def _clear_inputs(self) -> None:
        self.input_list.delete(0, tk.END)

    def _browse_output(self) -> None:
        path = filedialog.askdirectory(title=i18n.t("dlg_output"))
        if path:
            self.output_var.set(path)

    def _browse_cli(self) -> None:
        path = filedialog.askopenfilename(
            title=i18n.t("dlg_locate_tool"),
            filetypes=[
                (i18n.t("dlg_tool_filetypes"), "*.cmd *.exe *.bat *.ps1"),
                (i18n.t("dlg_all_files"), "*.*"),
            ],
        )
        if not path:
            return
        self.cli = path
        core.save_cli_config(path)
        self._log(i18n.t("log_cli_set", cli=path))
        self._refresh_cli_status()

    def _open_output(self) -> None:
        path = Path(self.output_var.get().strip() or ".")
        if not path.is_dir():
            messagebox.showinfo(self.title_text, i18n.t("info_output_missing"))
            return
        try:
            if os.name == "nt":
                os.startfile(str(path))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except (AttributeError, OSError):
            messagebox.showinfo(self.title_text, str(path))

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
                    self.title_text, i18n.t("warn_replace_body"),
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
            raise ValueError(i18n.t("err_no_points"))
        else:
            try:
                value = int(raw_value)
            except ValueError as exc:
                raise ValueError(i18n.t("err_points_int")) from exc

        fmt = self.format_keys[self.format_values.index(self.format_var.get())]
        opts = core.Options(
            output_dir=Path(self.output_var.get().strip()) if self.output_var.get().strip() else None,
            overwrite_existing=self.overwrite_var.get(),
            replace_source=self.replace_var.get(),
            decimate_mode=mode,
            decimate_value=value,
            filter_low_opacity=self.filter_var.get(),
            webp_effort=int(self.effort_var.get()),
            use_cpu=self.cpu_var.get(),
            output_format=fmt,
        )
        opts.validate()
        return opts

    def _start(self) -> None:
        if self.worker and self.worker.is_alive():
            return
        if not self.cli:
            messagebox.showerror(self.title_text, i18n.t("err_no_cli"))
            return

        paths = list(self.input_list.get(0, tk.END))
        if not paths:
            messagebox.showwarning(self.title_text, i18n.t("warn_no_input"))
            return
        try:
            opts = self._build_options()
        except ValueError as exc:
            messagebox.showwarning(self.title_text, str(exc))
            return

        sources = core.collect_inputs(paths, recursive=self.recursive_var.get())
        if not sources:
            messagebox.showwarning(self.title_text, i18n.t("warn_no_sources"))
            return
        jobs = core.plan_jobs(sources, opts)

        if opts.replace_source:
            preview = "\n".join(str(p) for p in sources[:5])
            more = ("\n" + i18n.t("confirm_more", count=len(sources))) if len(sources) > 5 else ""
            ok = messagebox.askyesno(
                self.title_text,
                i18n.t("confirm_replace_body", count=len(sources), preview=preview, more=more),
                icon=messagebox.WARNING,
            )
            if not ok:
                return

        self.log_text.configure(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        self.log_text.configure(state=tk.DISABLED)
        self._log(i18n.t("log_start", count=len(jobs)))

        self.cancel_event.clear()
        self.start_button.configure(state=tk.DISABLED)
        self.cancel_button.configure(state=tk.NORMAL)
        self.progress.configure(value=0, maximum=len(jobs))
        self.status_var.set(i18n.t("status_running"))

        # Start the elapsed / remaining time display.
        self._start_time = time.time()
        self._done = 0
        self._total = len(jobs)
        self._update_time()
        self._time_after = self.after(1000, self._tick_time)

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
            self.status_var.set(i18n.t("status_cancelling"))
            self._log(i18n.t("log_cancel_request"))

    def _poll_queue(self) -> None:
        try:
            while True:
                kind, payload = self.queue.get_nowait()
                if kind == "log":
                    self._log(str(payload))
                elif kind == "progress":
                    done, total, _ = payload
                    self._done, self._total = done, total
                    self.progress.configure(value=done)
                    self.status_var.set(f"{done}/{total}")
                    self._update_time()
                elif kind == "done":
                    self._finish(payload)
                elif kind == "cancelled":
                    self._total = self._done
                    self._update_time()
                    self._log(i18n.t("log_cancelled"))
                    self._reset_buttons(i18n.t("status_cancelled"))
                elif kind == "fatal":
                    self._total = self._done
                    self._update_time()
                    self._log(i18n.t("log_error", message=payload))
                    messagebox.showerror(self.title_text, str(payload))
                    self._reset_buttons(i18n.t("status_error"))
        except queue.Empty:
            pass
        self._poll_after_id = self.after(80, self._poll_queue)

    def _finish(self, report: core.Report) -> None:
        self._done = report.total
        self._update_time()
        self._log(i18n.t("log_finish", converted=report.converted,
                         skipped=report.skipped, failed=report.failed,
                         total=report.total))
        self._reset_buttons(i18n.t("status_done"))
        if report.failed:
            messagebox.showwarning(
                self.title_text, i18n.t("warn_some_failed", failed=report.failed))
        elif report.skipped and not report.converted:
            messagebox.showinfo(self.title_text, i18n.t("info_all_skipped"))

    @staticmethod
    def _fmt_duration(seconds: float) -> str:
        """Format a duration as ``mm:ss`` or ``h:mm:ss``."""
        seconds = int(seconds)
        hours, rem = divmod(seconds, 3600)
        minutes, secs = divmod(rem, 60)
        if hours:
            return f"{hours:d}:{minutes:02d}:{secs:02d}"
        return f"{minutes:02d}:{secs:02d}"

    def _update_time(self) -> None:
        """Refresh the elapsed / remaining label from the tracked counters."""
        if not self._start_time:
            return
        elapsed = time.time() - self._start_time
        if self._done > 0 and self._total > 0 and self._done < self._total:
            remain = elapsed * (self._total - self._done) / self._done
            remain_str = self._fmt_duration(remain)
        else:
            remain_str = "--:--"
        self.time_var.set(
            i18n.t("time_format", elapsed=self._fmt_duration(elapsed), remain=remain_str)
        )

    def _tick_time(self) -> None:
        """Re-render the time label every second while a job is running."""
        if self.worker is not None and self.worker.is_alive():
            self._update_time()
            self._time_after = self.after(1000, self._tick_time)
        else:
            self._time_after = None

    def _reset_buttons(self, status: str) -> None:
        self.start_button.configure(state=tk.NORMAL)
        self.cancel_button.configure(state=tk.DISABLED)
        self.status_var.set(status)


def main() -> None:
    app = ConverterApp()
    app.mainloop()


if __name__ == "__main__":
    main()
