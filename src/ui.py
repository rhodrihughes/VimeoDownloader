#!/usr/bin/env python3
"""
CustomTkinter GUI for Vimeo Downloader — wizard-style stepped flow.
"""

import threading
import re
import customtkinter as ctk
from pathlib import Path
from tkinter import filedialog
from downloader import VimeoDownloader

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

STEP_INACTIVE = {"fg_color": "#1e1e1e", "border_color": "#333333", "border_width": 1}
STEP_ACTIVE   = {"fg_color": "#1a2a3a", "border_color": "#1f6aa5", "border_width": 2}
STEP_DONE     = {"fg_color": "#1a2e1a", "border_color": "#2d7a2d", "border_width": 1}


class StepCard(ctk.CTkFrame):
    """A collapsible card representing one wizard step."""

    def __init__(self, parent, number, title, **kwargs):
        super().__init__(parent, corner_radius=10, **STEP_INACTIVE, **kwargs)
        self.number = number
        self.title = title
        self._expanded = False

        # Header row (always visible)
        self.header = ctk.CTkFrame(self, fg_color="transparent")
        self.header.pack(fill="x", padx=14, pady=10)

        self.badge = ctk.CTkLabel(
            self.header, text=str(number), width=28, height=28,
            corner_radius=14, fg_color="#333333", text_color="#888888",
            font=ctk.CTkFont(size=13, weight="bold")
        )
        self.badge.pack(side="left", padx=(0, 10))

        self.title_label = ctk.CTkLabel(
            self.header, text=title, font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#888888", anchor="w"
        )
        self.title_label.pack(side="left", fill="x", expand=True)

        self.status_label = ctk.CTkLabel(
            self.header, text="", font=ctk.CTkFont(size=12),
            text_color="#4caf50", anchor="e"
        )
        self.status_label.pack(side="right")

        # Body (shown when expanded)
        self.body = ctk.CTkFrame(self, fg_color="transparent")

    def expand(self):
        if not self._expanded:
            self.body.pack(fill="x", padx=14, pady=(0, 14))
            self._expanded = True

    def collapse(self):
        if self._expanded:
            self.body.pack_forget()
            self._expanded = False

    def set_active(self):
        self.configure(**STEP_ACTIVE)
        self.badge.configure(fg_color="#1f6aa5", text_color="white")
        self.title_label.configure(text_color="white")
        self.expand()

    def set_done(self, summary=""):
        self.configure(**STEP_DONE)
        self.badge.configure(fg_color="#2d7a2d", text_color="white", text="✓")
        self.title_label.configure(text_color="#cccccc")
        self.status_label.configure(text=summary)
        self.collapse()

    def set_inactive(self):
        self.configure(**STEP_INACTIVE)
        self.badge.configure(fg_color="#333333", text_color="#888888", text=str(self.number))
        self.title_label.configure(text_color="#888888")
        self.status_label.configure(text="")
        self.collapse()


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Vimeo Downloader")
        self.geometry("680x860")
        self.resizable(False, False)

        self._folders = []
        self._downloader = None
        self._access_token = None

        self._build_ui()
        self._go_to_step(1)

    # ------------------------------------------------------------------ #
    #  UI construction                                                     #
    # ------------------------------------------------------------------ #

    def _build_ui(self):
        ctk.CTkLabel(
            self, text="Vimeo Account Video Downloader",
            font=ctk.CTkFont(size=22, weight="bold")
        ).pack(padx=24, pady=(20, 4), anchor="w")

        ctk.CTkLabel(
            self, text="Follow the steps below to download your Vimeo videos.",
            font=ctk.CTkFont(size=13), text_color="#888888"
        ).pack(padx=24, pady=(0, 4), anchor="w")

        # Disclaimer + API key help link
        disclaimer_row = ctk.CTkFrame(self, fg_color="transparent")
        disclaimer_row.pack(padx=24, pady=(0, 14), anchor="w", fill="x")

        ctk.CTkLabel(
            disclaimer_row,
            text="Only download videos that belong to your own Vimeo account.",
            font=ctk.CTkFont(size=12), text_color="#e67e22"
        ).pack(side="left")

        ctk.CTkButton(
            disclaimer_row, text="How to get your API key →",
            font=ctk.CTkFont(size=12), fg_color="transparent",
            hover_color="#2a2a2a", text_color="#5b9bd5",
            width=0, command=self._show_api_instructions
        ).pack(side="right")

        # Scrollable area for steps
        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.pack(fill="both", expand=True, padx=16, pady=(0, 8))

        # ── Step 1: API Token ──────────────────────────────────────────
        self.step1 = StepCard(self.scroll, 1, "Enter your Vimeo API token")
        self.step1.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(
            self.step1.body,
            text="Get a token at developer.vimeo.com/apps  →  My Access Token",
            font=ctk.CTkFont(size=12), text_color="#888888"
        ).pack(anchor="w", pady=(0, 6))

        self.token_entry = ctk.CTkEntry(
            self.step1.body, placeholder_text="Paste access token here",
            show="*", width=580
        )
        self.token_entry.pack(pady=(0, 8))

        token_row = ctk.CTkFrame(self.step1.body, fg_color="transparent")
        token_row.pack(fill="x")
        self.verify_btn = ctk.CTkButton(
            token_row, text="Verify Token", width=140, command=self._verify_token
        )
        self.verify_btn.pack(side="left")
        self.token_status = ctk.CTkLabel(
            token_row, text="", font=ctk.CTkFont(size=12), text_color="#888888"
        )
        self.token_status.pack(side="left", padx=12)

        # ── Step 2: Download folder ────────────────────────────────────
        self.step2 = StepCard(self.scroll, 2, "Choose a download folder")
        self.step2.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(
            self.step2.body,
            text="Where should the videos be saved?",
            font=ctk.CTkFont(size=12), text_color="#888888"
        ).pack(anchor="w", pady=(0, 6))

        folder_row = ctk.CTkFrame(self.step2.body, fg_color="transparent")
        folder_row.pack(fill="x")
        self.folder_entry = ctk.CTkEntry(
            folder_row, placeholder_text="Select or type a folder path…", width=480
        )
        self.folder_entry.pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            folder_row, text="Browse", width=90, command=self._browse_folder
        ).pack(side="left")

        self.folder_confirm_btn = ctk.CTkButton(
            self.step2.body, text="Confirm Location", width=160,
            command=self._confirm_folder
        )
        self.folder_confirm_btn.pack(pady=(10, 0), anchor="w")

        # ── Step 3: Vimeo folder ───────────────────────────────────────
        self.step3 = StepCard(self.scroll, 3, "Select a Vimeo folder (optional)")
        self.step3.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(
            self.step3.body,
            text="Download from a specific folder, or download everything.",
            font=ctk.CTkFont(size=12), text_color="#888888"
        ).pack(anchor="w", pady=(0, 6))

        self.vimeo_folder_var = ctk.StringVar(value="All videos")
        self.vimeo_folder_menu = ctk.CTkOptionMenu(
            self.step3.body, variable=self.vimeo_folder_var,
            values=["All videos"], width=580
        )
        self.vimeo_folder_menu.pack(pady=(0, 8))

        self.vimeo_folder_continue_btn = ctk.CTkButton(
            self.step3.body, text="Continue", width=120,
            command=self._confirm_folder_selection
        )
        self.vimeo_folder_continue_btn.pack(anchor="w")

        # ── Step 4: Quality ────────────────────────────────────────────
        self.step4 = StepCard(self.scroll, 4, "Choose video quality")
        self.step4.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(
            self.step4.body,
            text="Source is the original upload quality. Falls back to best available if not found.",
            font=ctk.CTkFont(size=12), text_color="#888888"
        ).pack(anchor="w", pady=(0, 8))

        self.quality_var = ctk.StringVar(value="Source")
        quality_row = ctk.CTkFrame(self.step4.body, fg_color="transparent")
        quality_row.pack(anchor="w", pady=(0, 10))
        for q in ["Source", "1080p", "720p", "540p"]:
            ctk.CTkRadioButton(
                quality_row, text=q, variable=self.quality_var, value=q
            ).pack(side="left", padx=(0, 20))

        ctk.CTkButton(
            self.step4.body, text="Continue", width=120,
            command=self._confirm_quality
        ).pack(anchor="w")

        # ── Step 5: Options ────────────────────────────────────────────
        self.step5 = StepCard(self.scroll, 5, "Download options")
        self.step5.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(
            self.step5.body,
            text="Configure how the download runs.",
            font=ctk.CTkFont(size=12), text_color="#888888"
        ).pack(anchor="w", pady=(0, 8))

        self.retry_var = ctk.BooleanVar(value=False)
        self.multithread_var = ctk.BooleanVar(value=True)

        ctk.CTkCheckBox(
            self.step5.body,
            text="Retry mode — only download videos from retry_later.csv",
            variable=self.retry_var
        ).pack(anchor="w", pady=(0, 6))

        ctk.CTkCheckBox(
            self.step5.body,
            text="Multithreading — 3 concurrent downloads (faster)",
            variable=self.multithread_var
        ).pack(anchor="w", pady=(0, 10))

        ctk.CTkButton(
            self.step5.body, text="Start Download", width=160,
            fg_color="#1f6aa5", hover_color="#144e7a",
            command=self._start_download
        ).pack(anchor="w")

        # ── Progress + log (always visible at bottom) ──────────────────
        progress_card = ctk.CTkFrame(self.scroll, corner_radius=10, fg_color="#1e1e1e")
        progress_card.pack(fill="x", pady=(0, 8))

        inner = ctk.CTkFrame(progress_card, fg_color="transparent")
        inner.pack(fill="x", padx=14, pady=12)

        # Overall progress
        ctk.CTkLabel(
            inner, text="OVERALL", font=ctk.CTkFont(size=11),
            text_color="#666666"
        ).pack(anchor="w")
        self.progress_bar = ctk.CTkProgressBar(inner, width=580)
        self.progress_bar.set(0)
        self.progress_bar.pack(pady=(2, 2))
        self.progress_label = ctk.CTkLabel(
            inner, text="Waiting to start…", font=ctk.CTkFont(size=12),
            text_color="#888888"
        )
        self.progress_label.pack(anchor="w", pady=(0, 2))
        self.bandwidth_label = ctk.CTkLabel(
            inner, text="", font=ctk.CTkFont(size=11),
            text_color="#555555"
        )
        self.bandwidth_label.pack(anchor="w", pady=(0, 12))

        # Per-worker progress slots (3 concurrent workers)
        ctk.CTkLabel(
            inner, text="ACTIVE DOWNLOADS", font=ctk.CTkFont(size=11),
            text_color="#666666"
        ).pack(anchor="w", pady=(0, 6))

        self._worker_bars = []    # CTkProgressBar per slot
        self._worker_labels = []  # CTkLabel per slot (filename + size)
        self._worker_speed_labels = []  # CTkLabel per slot (speed)

        for i in range(3):
            slot = ctk.CTkFrame(inner, fg_color="#2a2a2a", corner_radius=6)
            slot.pack(fill="x", pady=(0, 6))

            header = ctk.CTkFrame(slot, fg_color="transparent")
            header.pack(fill="x", padx=10, pady=(6, 2))

            ctk.CTkLabel(
                header, text=f"Worker {i + 1}", font=ctk.CTkFont(size=11),
                text_color="#555555", width=60, anchor="w"
            ).pack(side="left")

            lbl = ctk.CTkLabel(
                header, text="—", font=ctk.CTkFont(size=11),
                text_color="#888888", anchor="w"
            )
            lbl.pack(side="left", padx=(6, 0))
            self._worker_labels.append(lbl)

            spd = ctk.CTkLabel(
                header, text="", font=ctk.CTkFont(size=11),
                text_color="#4a9eda", anchor="e"
            )
            spd.pack(side="right")
            self._worker_speed_labels.append(spd)

            bar = ctk.CTkProgressBar(slot, width=560)
            bar.set(0)
            bar.pack(padx=10, pady=(0, 8))
            self._worker_bars.append(bar)

        self.log_box = ctk.CTkTextbox(inner, width=580, height=140, state="disabled")
        self.log_box.pack(pady=(8, 0))

        self.stop_btn = ctk.CTkButton(
            inner, text="Stop", width=100, fg_color="#c0392b",
            hover_color="#922b21", command=self._stop_download, state="disabled"
        )
        self.stop_btn.pack(pady=(8, 0), anchor="w")

    # ------------------------------------------------------------------ #
    #  Step navigation                                                     #
    # ------------------------------------------------------------------ #

    def _go_to_step(self, step):
        self._current_step = step
        cards = [self.step1, self.step2, self.step3, self.step4, self.step5]
        for i, card in enumerate(cards, 1):
            if i < step:
                pass  # already marked done, leave it
            elif i == step:
                card.set_active()
            else:
                card.set_inactive()

    # ------------------------------------------------------------------ #
    #  API key instructions window                                         #
    # ------------------------------------------------------------------ #

    def _show_api_instructions(self):
        win = ctk.CTkToplevel(self)
        win.title("How to get your Vimeo API key")
        win.geometry("560x520")
        win.resizable(False, False)
        win.grab_set()  # modal

        ctk.CTkLabel(
            win, text="Getting your Vimeo API token",
            font=ctk.CTkFont(size=18, weight="bold")
        ).pack(padx=24, pady=(24, 4), anchor="w")

        ctk.CTkLabel(
            win, text="Follow these steps to create a personal access token:",
            font=ctk.CTkFont(size=13), text_color="#888888"
        ).pack(padx=24, pady=(0, 16), anchor="w")

        steps = [
            ("1", "Go to developer.vimeo.com/apps and sign in."),
            ("2", "Click 'Create an app' and give it any name\n    (e.g. 'My Downloader')."),
            ("3", "Open your new app and go to the\n    'Authentication' tab."),
            ("4", "Scroll to 'Generate an Access Token'."),
            ("5", "Under Scopes, tick:\n    • Public\n    • Private\n    • Video Files\n    • Download"),
            ("6", "Click 'Generate' and copy the token.\n    You won't be able to see it again."),
        ]

        for num, text in steps:
            row = ctk.CTkFrame(win, fg_color="transparent")
            row.pack(fill="x", padx=24, pady=3)

            ctk.CTkLabel(
                row, text=num, width=26, height=26, corner_radius=13,
                fg_color="#1f6aa5", text_color="white",
                font=ctk.CTkFont(size=12, weight="bold")
            ).pack(side="left", anchor="n", pady=2)

            ctk.CTkLabel(
                row, text=text, font=ctk.CTkFont(size=13),
                text_color="#cccccc", justify="left", anchor="w", wraplength=460
            ).pack(side="left", padx=(10, 0), anchor="w")

        # Warning box
        warn = ctk.CTkFrame(win, fg_color="#2a1f0a", corner_radius=8)
        warn.pack(fill="x", padx=24, pady=(16, 0))
        ctk.CTkLabel(
            warn,
            text="Keep your token private. Do not share.",
            font=ctk.CTkFont(size=12), text_color="#e67e22", wraplength=480
        ).pack(padx=14, pady=10)

        ctk.CTkButton(
            win, text="Close", width=100, command=win.destroy
        ).pack(pady=20)

    # ------------------------------------------------------------------ #
    #  Step 1 — Token                                                      #
    # ------------------------------------------------------------------ #

    def _verify_token(self):
        token = re.sub(r'[^\x20-\x7E]', '', ''.join(self.token_entry.get().split()))
        if not token:
            self.token_status.configure(text="⚠️  Please paste a token first.", text_color="#e67e22")
            return
        self.verify_btn.configure(state="disabled", text="Verifying…")
        self.token_status.configure(text="", text_color="#888888")
        threading.Thread(target=self._do_verify, args=(token,), daemon=True).start()

    def _do_verify(self, token):
        try:
            temp = VimeoDownloader(token, download_dir=None, log_callback=lambda m: None)
            folders = temp.get_user_folders()
            self._folders = folders
            self._access_token = token

            names = ["All videos"] + [f.get("name", "Untitled") for f in folders]

            def _update_menu():
                # Recreate the option menu so values reliably refresh
                self.vimeo_folder_menu.destroy()
                self.vimeo_folder_var.set("All videos")
                self.vimeo_folder_menu = ctk.CTkOptionMenu(
                    self.step3.body, variable=self.vimeo_folder_var,
                    values=names, width=580
                )
                self.vimeo_folder_menu.pack(pady=(0, 8), before=self.vimeo_folder_continue_btn)

            masked = f"…{token[-6:]}"
            self.after(0, _update_menu)
            self.after(0, lambda: self.step1.set_done(f"Token verified ({masked})"))
            self.after(0, lambda: self._go_to_step(2))
            self.after(0, lambda: self._log(f"✓ Token verified. Found {len(folders)} folder(s)."))
        except Exception as e:
            self.after(0, lambda: self.token_status.configure(
                text=f"❌ {str(e)}", text_color="#e74c3c"
            ))
            self.after(0, lambda: self.verify_btn.configure(state="normal", text="Verify Token"))

    # ------------------------------------------------------------------ #
    #  Step 2 — Download folder                                           #
    # ------------------------------------------------------------------ #

    def _browse_folder(self):
        path = filedialog.askdirectory(title="Select Download Folder")
        if path:
            self.folder_entry.delete(0, "end")
            self.folder_entry.insert(0, path)

    def _confirm_folder(self):
        path = self.folder_entry.get().strip().strip("'\"").replace("\\ ", " ")
        if not path:
            self._log("⚠️  Please enter or browse to a folder.")
            return
        import os
        if os.path.exists(path) and not os.path.isdir(path):
            self._log("❌ That path exists but isn't a folder.")
            return
        self._download_path = path
        short = path if len(path) <= 40 else "…" + path[-38:]
        self.step2.set_done(short)
        self._go_to_step(3)
        self._log(f"✓ Download folder: {path}")

    # ------------------------------------------------------------------ #
    #  Step 3 — Vimeo folder                                              #
    # ------------------------------------------------------------------ #

    def _confirm_folder_selection(self):
        name = self.vimeo_folder_var.get()
        self._selected_folder_id = None
        if name != "All videos":
            for f in self._folders:
                if f.get("name") == name:
                    self._selected_folder_id = f["uri"].split("/")[-1]
                    break
        self.step3.set_done(name)
        self._go_to_step(4)
        self._log(f"✓ Vimeo folder: {name}")

    # ------------------------------------------------------------------ #
    #  Step 4 — Quality                                                   #
    # ------------------------------------------------------------------ #

    def _confirm_quality(self):
        q = self.quality_var.get()
        self.step4.set_done(q)
        self._go_to_step(5)
        self._log(f"✓ Quality: {q}")

    # ------------------------------------------------------------------ #
    #  Step 5 — Start download                                            #
    # ------------------------------------------------------------------ #

    def _start_download(self):
        quality_map = {"Source": "source", "1080p": "1080p", "720p": "720p", "540p": "540p"}
        quality = quality_map.get(self.quality_var.get(), "source")

        opts = []
        if self.retry_var.get():
            opts.append("Retry mode")
        if self.multithread_var.get():
            opts.append("Multithreading")
        self.step5.set_done(", ".join(opts) if opts else "Default")

        self.stop_btn.configure(state="normal")
        self.progress_bar.set(0)
        self.progress_label.configure(text="Starting…")
        self._stop_flag = False

        # Reset all worker slots
        for i in range(3):
            self._worker_bars[i].set(0)
            self._worker_labels[i].configure(text="—", text_color="#888888")

        # Slot assignment: maps video name → slot index (thread-safe)
        self._slot_map = {}
        self._free_slots = list(range(3))
        self._slot_lock = threading.Lock()
        # Speed tracking: slot -> (last_bytes, last_time)
        self._slot_speed = {i: (0, 0.0) for i in range(3)}
        self._last_slot_speed = {i: 0 for i in range(3)}

        threading.Thread(
            target=self._run_download,
            args=(quality,),
            daemon=True
        ).start()

    def _run_download(self, quality):
        try:
            self._downloader = VimeoDownloader(
                self._access_token,
                download_dir=self._download_path,
                quality_preference=quality,
                force_source=(quality == "source"),
                enable_multithreading=self.multithread_var.get(),
                max_workers=3,
                log_callback=self._log
            )

            def on_progress(completed, total):
                pct = completed / total if total else 0
                self.after(0, lambda: self.progress_bar.set(pct))
                self.after(0, lambda: self.progress_label.configure(
                    text=f"{completed} of {total} videos"
                ))

            def on_file_progress(name, done, total_bytes):
                import time
                now = time.monotonic()

                # Assign a slot the first time we see this file
                with self._slot_lock:
                    if name not in self._slot_map:
                        if self._free_slots:
                            slot = self._free_slots.pop(0)
                            self._slot_map[name] = slot
                            self._slot_speed[slot] = (0, now)
                        else:
                            return
                    slot = self._slot_map[name]

                # Calculate per-slot speed
                prev_bytes, prev_time = self._slot_speed[slot]
                elapsed = now - prev_time
                if elapsed > 0.3:  # update speed every ~300ms
                    speed_bps = (done - prev_bytes) / elapsed
                    self._slot_speed[slot] = (done, now)
                else:
                    speed_bps = None  # not enough time elapsed, keep last

                pct = done / total_bytes if total_bytes else 0
                done_mb = done / (1024 * 1024)
                total_mb = total_bytes / (1024 * 1024)
                display = name if len(name) <= 35 else name[:33] + "…"
                file_label = f"{display}  {done_mb:.1f} / {total_mb:.1f} MB  ({pct*100:.0f}%)"

                def _fmt_speed(bps):
                    if bps is None or bps < 0:
                        return ""
                    if bps >= 1024 * 1024:
                        return f"{bps / (1024*1024):.1f} MB/s"
                    return f"{bps / 1024:.0f} KB/s"

                speed_str = _fmt_speed(speed_bps) if speed_bps is not None else None

                # Sum all active slot speeds for total bandwidth
                def _update(s=slot, p=pct, fl=file_label, ss=speed_str, sb=speed_bps):
                    self._worker_bars[s].set(p)
                    self._worker_labels[s].configure(text=fl, text_color="#cccccc")
                    if ss is not None:
                        self._worker_speed_labels[s].configure(text=ss)
                        self._last_slot_speed[s] = sb if sb else 0
                        total_bps = sum(self._last_slot_speed.values())
                        bw = _fmt_speed(total_bps)
                        self.bandwidth_label.configure(
                            text=f"Total bandwidth: {bw}" if bw else ""
                        )
                self.after(0, _update)

                # Release slot when complete
                if done >= total_bytes and total_bytes > 0:
                    def _release(s=slot, n=name):
                        with self._slot_lock:
                            if n in self._slot_map:
                                del self._slot_map[n]
                                self._free_slots.append(s)
                        self._slot_speed[s] = (0, 0.0)
                        self._last_slot_speed[s] = 0
                        total_bps = sum(self._last_slot_speed.values())
                        bw = _fmt_speed(total_bps)
                        self._worker_bars[s].set(0)
                        self._worker_labels[s].configure(text="—", text_color="#888888")
                        self._worker_speed_labels[s].configure(text="")
                        self.bandwidth_label.configure(
                            text=f"Total bandwidth: {bw}" if bw else ""
                        )
                    self.after(200, _release)

            counts = self._downloader.download_all(
                retry_mode=self.retry_var.get(),
                folder_id=self._selected_folder_id,
                overall_progress_callback=on_progress,
                file_progress_callback=on_file_progress
            )

            summary = (f"Done — ✅ {counts['successful']}  ❌ {counts['failed']}  "
                       f"⏭️ {counts['skipped']}  🔄 {counts['retry']}")
            self.after(0, lambda: self.progress_bar.set(1))
            self.after(0, lambda: self.progress_label.configure(text=summary))
            # Reset all worker slots
            def _reset_slots():
                for i in range(3):
                    self._worker_bars[i].set(0)
                    self._worker_labels[i].configure(text="—", text_color="#888888")
                    self._worker_speed_labels[i].configure(text="")
                self._last_slot_speed = {}
                self.bandwidth_label.configure(text="")
            self.after(0, _reset_slots)
            self._log(summary)

        except Exception as e:
            self._log(f"❌ Unexpected error: {str(e)}")
        finally:
            self.after(0, lambda: self.stop_btn.configure(state="disabled"))

    def _stop_download(self):
        # Confirmation dialog
        dialog = ctk.CTkToplevel(self)
        dialog.title("Stop downloads?")
        dialog.geometry("400x160")
        dialog.resizable(False, False)
        dialog.grab_set()

        ctk.CTkLabel(
            dialog, text="Stop all downloads?",
            font=ctk.CTkFont(size=15, weight="bold")
        ).pack(padx=24, pady=(20, 4), anchor="w")

        ctk.CTkLabel(
            dialog,
            text="Any files currently downloading will be deleted.",
            font=ctk.CTkFont(size=12), text_color="#888888"
        ).pack(padx=24, anchor="w")

        btn_row = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_row.pack(pady=20)

        def _confirm():
            dialog.destroy()
            self.stop_btn.configure(state="disabled")
            self._log("⚠️  Stopping downloads and removing partial files…")
            if self._downloader:
                self._downloader.cancel()

        def _cancel():
            dialog.destroy()

        ctk.CTkButton(
            btn_row, text="Stop Downloads", width=140,
            fg_color="#c0392b", hover_color="#922b21", command=_confirm
        ).pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            btn_row, text="Keep Going", width=120,
            fg_color="#2a2a2a", hover_color="#3a3a3a", command=_cancel
        ).pack(side="left")

    # ------------------------------------------------------------------ #
    #  Logging                                                             #
    # ------------------------------------------------------------------ #

    def _log(self, message):
        def _append():
            self.log_box.configure(state="normal")
            self.log_box.insert("end", message + "\n")
            self.log_box.see("end")
            self.log_box.configure(state="disabled")
        self.after(0, _append)


def run():
    app = App()
    app.mainloop()
