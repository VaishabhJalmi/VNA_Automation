#!/usr/bin/env python3
"""
ShockLine S2P Advanced Plotter
------------------------------
A standalone Python GUI for Anritsu ShockLine / Touchstone .s2p files.

Features
- Reads Touchstone .s2p files with RI, MA or DB data
- Automatically detects Hz/kHz/MHz/GHz units
- 4-panel view similar to the Anritsu ShockLine screen:
    TR1: S11 Return Loss / Log Magnitude
    TR2: S22 Return Loss / Log Magnitude
    TR3: S21 Transmission / Insertion Loss
    TR4: S11 Smith Chart
- Up to 12 frequency markers
- Marker values shown in a table and on all applicable traces
- Nearest-point or interpolated marker readout
- Pass/fail limit lines for S11, S22 and S21
- Trace visibility controls
- Frequency range controls
- Grid, legend and marker controls
- CSV marker export
- PNG/PDF plot export
- Dark Anritsu-like user interface
- No scikit-rf dependency required

Install:
    pip install numpy matplotlib

Run:
    python shockline_s2p_plotter.py
"""

import csv
import math
import re
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure
from matplotlib.ticker import FuncFormatter


# ----------------------------- Touchstone parser -----------------------------

class S2PData:
    def __init__(self):
        self.filename = ""
        self.frequency = np.array([])
        self.s11 = np.array([], dtype=complex)
        self.s21 = np.array([], dtype=complex)
        self.s12 = np.array([], dtype=complex)
        self.s22 = np.array([], dtype=complex)
        self.unit = "GHz"
        self.format = "RI"
        self.z0 = 50.0

    @staticmethod
    def _complex(a, b, fmt):
        fmt = fmt.upper()
        if fmt == "RI":
            return complex(a, b)
        if fmt == "MA":
            # Touchstone MA = magnitude / angle in degrees
            return abs(a) * np.exp(1j * np.deg2rad(b))
        if fmt == "DB":
            # Touchstone DB = dB magnitude / angle in degrees
            return 10 ** (a / 20.0) * np.exp(1j * np.deg2rad(b))
        raise ValueError(f"Unsupported data format: {fmt}")

    @classmethod
    def load(cls, filename):
        obj = cls()
        obj.filename = str(filename)

        unit_scale = {
            "HZ": 1.0,
            "KHZ": 1e3,
            "MHZ": 1e6,
            "GHZ": 1e9,
        }

        unit = "GHZ"
        fmt = "MA"
        z0 = 50.0
        rows = []
        pending = ""

        with open(filename, "r", encoding="utf-8", errors="replace") as f:
            for raw in f:
                # Remove inline comments
                line = raw.split("!")[0].strip()
                if not line:
                    continue

                if line.startswith("#"):
                    tokens = line[1:].upper().split()
                    for t in tokens:
                        if t in unit_scale:
                            unit = t
                        elif t in ("RI", "MA", "DB"):
                            fmt = t
                        elif t == "R":
                            # R is followed by the reference impedance.
                            pass
                    m = re.search(r"\bR\s+([+-]?\d+(?:\.\d*)?)", line.upper())
                    if m:
                        z0 = float(m.group(1))
                    continue

                # A Touchstone data point normally contains 9 values.
                pending = (pending + " " + line).strip()
                vals = pending.replace(",", " ").split()
                # Ignore a possible nonnumeric header line.
                try:
                    nums = [float(v) for v in vals]
                except ValueError:
                    pending = ""
                    continue

                while len(nums) >= 9:
                    rows.append(nums[:9])
                    nums = nums[9:]
                pending = " ".join(str(x) for x in nums)

        if not rows:
            raise ValueError("No valid S2P data points were found.")

        arr = np.asarray(rows, dtype=float)
        freq_hz = arr[:, 0] * unit_scale[unit]

        # Standard 2-port Touchstone order:
        # S11, S21, S12, S22
        s11 = np.array([obj._complex(r[1], r[2], fmt) for r in arr])
        s21 = np.array([obj._complex(r[3], r[4], fmt) for r in arr])
        s12 = np.array([obj._complex(r[5], r[6], fmt) for r in arr])
        s22 = np.array([obj._complex(r[7], r[8], fmt) for r in arr])

        order = np.argsort(freq_hz)
        obj.frequency = freq_hz[order]
        obj.s11 = s11[order]
        obj.s21 = s21[order]
        obj.s12 = s12[order]
        obj.s22 = s22[order]
        obj.unit = unit
        obj.format = fmt
        obj.z0 = z0

        # Remove duplicate frequency points while preserving the last point.
        _, idx = np.unique(obj.frequency, return_index=True)
        # unique returns first index; this is enough for normal VNA files.
        idx = np.sort(idx)
        obj.frequency = obj.frequency[idx]
        obj.s11 = obj.s11[idx]
        obj.s21 = obj.s21[idx]
        obj.s12 = obj.s12[idx]
        obj.s22 = obj.s22[idx]

        return obj


# ----------------------------- RF calculations -------------------------------

def db20(z):
    mag = np.maximum(np.abs(z), 1e-15)
    return 20.0 * np.log10(mag)

def vswr(gamma):
    g = np.abs(gamma)
    g = np.minimum(g, 0.999999999)
    return (1 + g) / (1 - g)

def phase_deg(z):
    return np.angle(z, deg=True)

def interp_complex(x, y, target):
    """Linear complex interpolation."""
    if target <= x[0]:
        return y[0]
    if target >= x[-1]:
        return y[-1]
    i = int(np.searchsorted(x, target))
    x0, x1 = x[i - 1], x[i]
    if x1 == x0:
        return y[i]
    t = (target - x0) / (x1 - x0)
    return y[i - 1] + t * (y[i] - y[i - 1])

def fmt_freq(hz):
    if hz >= 1e9:
        return f"{hz/1e9:.6f} GHz"
    if hz >= 1e6:
        return f"{hz/1e6:.6f} MHz"
    if hz >= 1e3:
        return f"{hz/1e3:.3f} kHz"
    return f"{hz:.2f} Hz"

def parse_frequency(text):
    s = text.strip().replace(",", "")
    if not s:
        raise ValueError("Empty frequency.")
    m = re.match(r"^\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*([a-zA-Z]*)\s*$", s)
    if not m:
        raise ValueError(f"Invalid frequency: {text}")
    value = float(m.group(1))
    unit = m.group(2).lower()
    scale = {
        "": 1e9, "ghz": 1e9, "g": 1e9,
        "mhz": 1e6, "m": 1e6,
        "khz": 1e3, "k": 1e3,
        "hz": 1.0,
    }
    if unit not in scale:
        raise ValueError(f"Unknown frequency unit: {unit}")
    return value * scale[unit]


# ------------------------------- Main GUI ------------------------------------

class ShockLinePlotter(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Anritsu ShockLine S2P Advanced Plotter")
        self.geometry("1500x950")
        self.minsize(1100, 700)

        self.data = None
        self.markers = []
        self.marker_limit = 12
        self.dark = True

        self._setup_style()
        self._build_ui()
        self._build_figure()
        self._set_status("Open an .s2p file to begin.")

    # ------------------------- UI setup -------------------------

    def _setup_style(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass

        bg = "#17191d"
        panel = "#20242a"
        fg = "#e8edf2"
        accent = "#31c4a0"

        self.configure(bg=bg)
        style.configure(".", background=bg, foreground=fg, font=("Segoe UI", 10))
        style.configure("TFrame", background=bg)
        style.configure("Panel.TFrame", background=panel)
        style.configure("TLabel", background=bg, foreground=fg)
        style.configure("Panel.TLabel", background=panel, foreground=fg)
        style.configure("TButton", padding=(8, 5))
        style.configure("Accent.TButton", padding=(10, 6))
        style.configure("TCheckbutton", background=bg, foreground=fg)
        style.configure("TRadiobutton", background=bg, foreground=fg)
        style.configure("TEntry", fieldbackground="#111318", foreground=fg)
        style.configure("TCombobox", fieldbackground="#111318", foreground=fg)
        style.configure("Treeview",
                        background="#101216", foreground=fg,
                        fieldbackground="#101216", rowheight=25)
        style.configure("Treeview.Heading",
                        background="#2a3037", foreground="#ffffff")

    def _build_ui(self):
        # Top toolbar
        top = ttk.Frame(self, padding=(8, 7))
        top.pack(side="top", fill="x")

        ttk.Button(top, text="📂 Open S2P", command=self.open_file).pack(side="left", padx=3)
        ttk.Button(top, text="💾 Export Plot", command=self.export_plot).pack(side="left", padx=3)
        ttk.Button(top, text="📄 Export Markers", command=self.export_markers).pack(side="left", padx=3)
        ttk.Button(top, text="↻ Reset View", command=self.reset_view).pack(side="left", padx=3)

        self.file_label = ttk.Label(top, text="No file loaded")
        self.file_label.pack(side="left", padx=15)

        # Main split
        main = ttk.Panedwindow(self, orient="horizontal")
        main.pack(fill="both", expand=True, padx=7, pady=(0, 7))

        left = ttk.Frame(main, style="Panel.TFrame", padding=8)
        right = ttk.Frame(main, style="Panel.TFrame", padding=8)
        main.add(left, weight=0)
        main.add(right, weight=1)

        self._build_controls(left)
        self._build_marker_table(left)
        self._build_figure(right)

        self.status = ttk.Label(self, text="", anchor="w", padding=(8, 3))
        self.status.pack(side="bottom", fill="x")

    def _build_controls(self, parent):
        # File info
        lf = ttk.LabelFrame(parent, text="S2P Information", padding=7)
        lf.pack(fill="x", pady=(0, 7))

        self.info_text = tk.StringVar(value="No file loaded")
        ttk.Label(lf, textvariable=self.info_text, justify="left", wraplength=310).pack(fill="x")

        # Traces
        tr = ttk.LabelFrame(parent, text="Traces", padding=7)
        tr.pack(fill="x", pady=7)

        self.show_s11 = tk.BooleanVar(value=True)
        self.show_s22 = tk.BooleanVar(value=True)
        self.show_s21 = tk.BooleanVar(value=True)
        self.show_smith = tk.BooleanVar(value=True)

        ttk.Checkbutton(tr, text="Tr1  S11  Return Loss", variable=self.show_s11,
                        command=self.redraw).pack(anchor="w")
        ttk.Checkbutton(tr, text="Tr2  S22  Return Loss", variable=self.show_s22,
                        command=self.redraw).pack(anchor="w")
        ttk.Checkbutton(tr, text="Tr3  S21  Insertion Loss", variable=self.show_s21,
                        command=self.redraw).pack(anchor="w")
        ttk.Checkbutton(tr, text="Tr4  S11  Smith Chart", variable=self.show_smith,
                        command=self.redraw).pack(anchor="w")

        # Frequency limits
        fr = ttk.LabelFrame(parent, text="Frequency Range", padding=7)
        fr.pack(fill="x", pady=7)

        self.fmin_var = tk.StringVar()
        self.fmax_var = tk.StringVar()
        row = ttk.Frame(fr)
        row.pack(fill="x")
        ttk.Label(row, text="Start").grid(row=0, column=0, sticky="w")
        ttk.Entry(row, textvariable=self.fmin_var, width=13).grid(row=0, column=1, padx=4)
        ttk.Label(row, text="Stop").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Entry(row, textvariable=self.fmax_var, width=13).grid(row=1, column=1, padx=4)
        ttk.Button(row, text="Apply", command=self.apply_frequency_range).grid(
            row=0, column=2, rowspan=2, padx=4
        )
        ttk.Button(fr, text="Full Span", command=self.reset_view).pack(fill="x", pady=(6, 0))

        # Limits
        lim = ttk.LabelFrame(parent, text="Test Limits", padding=7)
        lim.pack(fill="x", pady=7)

        self.s11_limit_var = tk.StringVar(value="-26")
        self.s22_limit_var = tk.StringVar(value="-26")
        self.s21_limit_var = tk.StringVar(value="-0.44")

        for r, label, var in [
            (0, "S11 max dB", self.s11_limit_var),
            (1, "S22 max dB", self.s22_limit_var),
            (2, "S21 max dB", self.s21_limit_var),
        ]:
            ttk.Label(lim, text=label).grid(row=r, column=0, sticky="w")
            ttk.Entry(lim, textvariable=var, width=10).grid(row=r, column=1, padx=5)
        ttk.Button(lim, text="Apply Limits", command=self.redraw).grid(
            row=3, column=0, columnspan=2, pady=5, sticky="ew"
        )

        # Marker entry
        mk = ttk.LabelFrame(parent, text="Frequency Marker", padding=7)
        mk.pack(fill="x", pady=7)

        self.marker_freq_var = tk.StringVar()
        ttk.Label(mk, text="Frequency (e.g. 1.723 GHz)").pack(anchor="w")
        ent = ttk.Entry(mk, textvariable=self.marker_freq_var)
        ent.pack(fill="x", pady=3)
        ent.bind("<Return>", lambda e: self.add_marker())
        ttk.Button(mk, text="＋ Add Marker", command=self.add_marker).pack(fill="x")
        ttk.Button(mk, text="Remove Selected", command=self.remove_marker).pack(fill="x", pady=3)
        ttk.Button(mk, text="Clear Markers", command=self.clear_markers).pack(fill="x")

        self.interpolate_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            mk, text="Interpolate between sweep points",
            variable=self.interpolate_var, command=self.redraw
        ).pack(anchor="w", pady=(4, 0))

        # Mouse marker
        ttk.Label(
            parent,
            text="Tip: click anywhere on a graph to add a marker at the nearest frequency.",
            wraplength=315, justify="left"
        ).pack(fill="x", pady=8)

    def _build_marker_table(self, parent):
        lf = ttk.LabelFrame(parent, text="Marker Values", padding=5)
        lf.pack(fill="both", expand=True, pady=(7, 0))

        columns = ("#", "Freq", "S11 dB", "S22 dB", "S21 dB", "VSWR", "Γ∠")
        self.marker_tree = ttk.Treeview(lf, columns=columns, show="headings", height=9)
        for c, w in zip(columns, [30, 95, 72, 72, 72, 60, 80]):
            self.marker_tree.heading(c, text=c)
            self.marker_tree.column(c, width=w, anchor="center")
        self.marker_tree.pack(side="left", fill="both", expand=True)

        sb = ttk.Scrollbar(lf, orient="vertical", command=self.marker_tree.yview)
        sb.pack(side="right", fill="y")
        self.marker_tree.configure(yscrollcommand=sb.set)

    # --------------------------- Figure --------------------------------

    def _build_figure(self, parent):
        # Avoid creating two figures if _build_ui calls us once and __init__ calls again.
        if hasattr(self, "canvas"):
            return

        self.figure = Figure(figsize=(10, 7), dpi=100, facecolor="#111318")
        gs = self.figure.add_gridspec(
            2, 2, left=0.055, right=0.985, bottom=0.075, top=0.94,
            hspace=0.28, wspace=0.18
        )
        self.ax_s11 = self.figure.add_subplot(gs[0, 0])
        self.ax_s22 = self.figure.add_subplot(gs[0, 1])
        self.ax_s21 = self.figure.add_subplot(gs[1, 0])
        self.ax_smith = self.figure.add_subplot(gs[1, 1])

        for ax in [self.ax_s11, self.ax_s22, self.ax_s21]:
            ax.set_facecolor("#111318")
            ax.tick_params(colors="#d8dee5")
            for spine in ax.spines.values():
                spine.set_color("#59616b")
            ax.grid(True, alpha=0.22, color="#88919c")
            ax.xaxis.set_major_formatter(FuncFormatter(self._x_formatter))

        self.ax_smith.set_facecolor("#111318")
        self.ax_smith.set_aspect("equal")
        self.ax_smith.axis("off")

        self.canvas = FigureCanvasTkAgg(self.figure, master=self._figure_parent())
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

        toolbar = NavigationToolbar2Tk(self.canvas, self._figure_parent(), pack_toolbar=False)
        toolbar.update()
        toolbar.pack(side="bottom", fill="x")

        self.canvas.mpl_connect("button_press_event", self._plot_click)

    def _figure_parent(self):
        # Find the right pane by walking children.
        # The canvas is only created once, and the right pane is the last child.
        frames = [w for w in self.winfo_children() if isinstance(w, ttk.Panedwindow)]
        if not frames:
            return self
        pane = frames[0]
        return pane.panes() and self.nametowidget(pane.panes()[-1]) or self

    @staticmethod
    def _x_formatter(x, pos):
        if x >= 1:
            return f"{x:g}"
        if x >= 0.001:
            return f"{x*1000:g} M"
        return f"{x*1e6:g} k"

    def _style_axis(self, ax, title, ylabel="dB"):
        ax.set_title(title, color="#f1f4f7", loc="left", fontsize=10, fontweight="bold")
        ax.set_xlabel("Frequency (GHz)", color="#cfd6de")
        ax.set_ylabel(ylabel, color="#cfd6de")
        ax.tick_params(labelsize=8)

    def _draw_limit(self, ax, value, label):
        try:
            v = float(value)
        except Exception:
            return
        ax.axhline(v, linestyle="--", linewidth=1.0, alpha=0.8)
        x0, x1 = ax.get_xlim()
        ax.text(
            x1, v, f"  {label}: {v:g} dB",
            va="bottom", ha="right", fontsize=7, color="#e6e6e6"
        )

    def redraw(self):
        if self.data is None:
            return

        for ax in [self.ax_s11, self.ax_s22, self.ax_s21]:
            ax.clear()
            ax.set_facecolor("#111318")
            ax.tick_params(colors="#d8dee5")
            for spine in ax.spines.values():
                spine.set_color("#59616b")
            ax.grid(True, alpha=0.22, color="#88919c")

        self.ax_smith.clear()
        self.ax_smith.set_facecolor("#111318")
        self.ax_smith.set_aspect("equal")
        self.ax_smith.axis("off")

        d = self.data
        fghz = d.frequency / 1e9

        # Return loss / log magnitude
        if self.show_s11.get():
            self.ax_s11.plot(fghz, db20(d.s11), linewidth=1.6, label="S11")
            self._draw_limit(self.ax_s11, self.s11_limit_var.get(), "LIMIT")
        if self.show_s22.get():
            self.ax_s22.plot(fghz, db20(d.s22), linewidth=1.6, label="S22")
            self._draw_limit(self.ax_s22, self.s22_limit_var.get(), "LIMIT")
        if self.show_s21.get():
            self.ax_s21.plot(fghz, db20(d.s21), linewidth=1.6, label="S21")
            self._draw_limit(self.ax_s21, self.s21_limit_var.get(), "LIMIT")

        for ax in [self.ax_s11, self.ax_s22, self.ax_s21]:
            ax.set_xlim(self._current_xlim(fghz))
            ax.legend(loc="best", fontsize=7, framealpha=0.25)
            for t in ax.get_xticklabels() + ax.get_yticklabels():
                t.set_color("#d8dee5")

        self._style_axis(self.ax_s11, "Tr1  S11  Return Loss / Log Magnitude")
        self._style_axis(self.ax_s22, "Tr2  S22  Return Loss / Log Magnitude")
        self._style_axis(self.ax_s21, "Tr3  S21  Transmission / Insertion Loss")

        self._draw_smith(d)

        # Draw all marker information
        self._draw_markers(fghz)

        self.figure.suptitle(
            f"ShockLine S2P Plotter   |   {Path(d.filename).name}   |   Z0 = {d.z0:g} Ω",
            color="#f2f5f8", fontsize=11, fontweight="bold"
        )
        self.canvas.draw_idle()
        self._refresh_marker_table()

    def _current_xlim(self, fghz):
        try:
            a = float(self.fmin_var.get())
            b = float(self.fmax_var.get())
            if b > a:
                return a, b
        except Exception:
            pass
        return float(fghz[0]), float(fghz[-1])

    # --------------------------- Smith chart ----------------------------

    def _draw_smith(self, d):
        ax = self.ax_smith

        # Standard normalized impedance Smith grid.
        theta = np.linspace(0, 2*np.pi, 720)
        # Outer unit circle
        ax.plot(np.cos(theta), np.sin(theta), linewidth=1.0, alpha=0.85)

        # Constant resistance circles:
        # center r/(1+r), radius 1/(1+r)
        for r in [0.2, 0.5, 1, 2, 5]:
            c = r / (1 + r)
            rad = 1 / (1 + r)
            ax.plot(c + rad*np.cos(theta), rad*np.sin(theta),
                    linewidth=0.45, alpha=0.45)

        # Constant reactance arcs:
        for x in [0.2, 0.5, 1, 2, 5]:
            # z = 1 + jx relation in gamma plane:
            # center (1, 1/x), radius 1/|x|
            cy = 1 / x
            rad = 1 / abs(x)
            ang = np.linspace(np.pi/2, 3*np.pi/2, 500)
            ax.plot(1 + rad*np.cos(ang), cy + rad*np.sin(ang),
                    linewidth=0.45, alpha=0.45)
            ax.plot(1 + rad*np.cos(-ang), -cy + rad*np.sin(-ang),
                    linewidth=0.45, alpha=0.45)

        # Real axis and center
        ax.axhline(0, linewidth=0.5, alpha=0.55)
        ax.plot([0], [0], marker="+", markersize=6, linewidth=1)

        # Labels
        ax.text(0, -1.11, "−1", ha="center", va="top", fontsize=7)
        ax.text(0, 1.08, "+1", ha="center", va="bottom", fontsize=7)
        ax.text(1.02, 0.02, "0 Ω", fontsize=7, va="center")
        ax.text(-1.03, 0.02, "∞ Ω", fontsize=7, va="center", ha="right")
        ax.set_xlim(-1.13, 1.13)
        ax.set_ylim(-1.13, 1.13)

        if self.show_smith.get():
            gamma = d.s11
            # normalized reflection coefficient is already S11.
            ax.plot(gamma.real, gamma.imag, linewidth=1.6, label="S11")
            ax.plot([gamma.real[0]], [gamma.imag[0]], marker="o", markersize=3)
            ax.plot([gamma.real[-1]], [gamma.imag[-1]], marker="s", markersize=3)

        ax.set_title("Tr4  S11  Smith Chart", color="#f1f4f7",
                     loc="left", fontsize=10, fontweight="bold")
        ax.text(
            0.02, -0.075,
            "Constant resistance / reactance grid   |   Γ = S11",
            transform=ax.transAxes, fontsize=7, color="#aeb7c1"
        )

    # --------------------------- Markers --------------------------------

    def add_marker(self):
        if self.data is None:
            messagebox.showwarning("No data", "Open an S2P file first.")
            return
        if len(self.markers) >= self.marker_limit:
            messagebox.showinfo("Marker limit", f"Maximum {self.marker_limit} markers.")
            return

        try:
            hz = parse_frequency(self.marker_freq_var.get())
        except ValueError as e:
            messagebox.showerror("Marker frequency", str(e))
            return

        f0 = self.data.frequency[0]
        f1 = self.data.frequency[-1]
        if not (f0 <= hz <= f1):
            messagebox.showerror(
                "Out of range",
                f"Marker must be between {fmt_freq(f0)} and {fmt_freq(f1)}."
            )
            return

        self.markers.append(hz)
        self.markers.sort()
        self.marker_freq_var.set("")
        self.redraw()

    def remove_marker(self):
        selected = self.marker_tree.selection()
        if not selected:
            return
        # Tree iid is marker index after sorting.
        indices = sorted([int(i) for i in selected], reverse=True)
        for i in indices:
            if 0 <= i < len(self.markers):
                self.markers.pop(i)
        self.redraw()

    def clear_markers(self):
        self.markers = []
        self.redraw()

    def _marker_value(self, z, hz):
        if self.interpolate_var.get():
            return interp_complex(self.data.frequency, z, hz)

        i = int(np.argmin(np.abs(self.data.frequency - hz)))
        return z[i]

    def _draw_markers(self, fghz):
        if not self.markers:
            return

        for idx, hz in enumerate(self.markers, start=1):
            x = hz / 1e9

            # Marker line on rectangular plots
            for ax in [self.ax_s11, self.ax_s22, self.ax_s21]:
                ax.axvline(x, linestyle=":", linewidth=0.9, alpha=0.75)

            # S11 point
            s11 = self._marker_value(self.data.s11, hz)
            s22 = self._marker_value(self.data.s22, hz)
            s21 = self._marker_value(self.data.s21, hz)

            if self.show_s11.get():
                self.ax_s11.plot([x], [db20(s11)], marker="o", markersize=5)
            if self.show_s22.get():
                self.ax_s22.plot([x], [db20(s22)], marker="o", markersize=5)
            if self.show_s21.get():
                self.ax_s21.plot([x], [db20(s21)], marker="o", markersize=5)
            if self.show_smith.get():
                self.ax_smith.plot([s11.real], [s11.imag],
                                   marker="o", markersize=5)

            # Marker label on S11 panel
            self.ax_s11.annotate(
                f"M{idx}\n{fmt_freq(hz)}\n{db20(s11):.3f} dB",
                xy=(x, db20(s11)), xytext=(5, 8),
                textcoords="offset points", fontsize=6.5,
                color="#e9edf2",
                bbox=dict(boxstyle="round,pad=0.25", alpha=0.55)
            )

    def _refresh_marker_table(self):
        for item in self.marker_tree.get_children():
            self.marker_tree.delete(item)

        for idx, hz in enumerate(self.markers):
            s11 = self._marker_value(self.data.s11, hz)
            s22 = self._marker_value(self.data.s22, hz)
            s21 = self._marker_value(self.data.s21, hz)
            self.marker_tree.insert(
                "", "end", iid=str(idx),
                values=(
                    idx + 1,
                    fmt_freq(hz),
                    f"{db20(s11):.3f}",
                    f"{db20(s22):.3f}",
                    f"{db20(s21):.3f}",
                    f"{vswr(s11):.3f}",
                    f"{abs(s11):.4f} ∠ {phase_deg(s11):.1f}°",
                )
            )

    def _plot_click(self, event):
        if self.data is None or event.inaxes not in [
            self.ax_s11, self.ax_s22, self.ax_s21, self.ax_smith
        ]:
            return

        if event.inaxes == self.ax_smith:
            return

        if event.xdata is None:
            return

        if len(self.markers) >= self.marker_limit:
            return

        hz = float(event.xdata) * 1e9
        if self.data.frequency[0] <= hz <= self.data.frequency[-1]:
            self.markers.append(hz)
            self.markers.sort()
            self.redraw()

    # ----------------------------- File --------------------------------

    def open_file(self):
        filename = filedialog.askopenfilename(
            title="Open Anritsu / Touchstone S2P file",
            filetypes=[
                ("Touchstone S2P", "*.s2p *.S2P"),
                ("All files", "*.*"),
            ],
        )
        if not filename:
            return

        try:
            self.data = S2PData.load(filename)
        except Exception as e:
            messagebox.showerror(
                "S2P Read Error",
                f"Could not read this file.\n\n{e}"
            )
            return

        self.markers = []
        f = self.data.frequency
        self.fmin_var.set(f"{f[0]/1e9:.6f}")
        self.fmax_var.set(f"{f[-1]/1e9:.6f}")

        self.file_label.config(text=Path(filename).name)
        self.info_text.set(
            f"File: {Path(filename).name}\n"
            f"Points: {len(f):,}\n"
            f"Range: {fmt_freq(f[0])} → {fmt_freq(f[-1])}\n"
            f"Format: {self.data.format}\n"
            f"Reference: {self.data.z0:g} Ω"
        )
        self._set_status(f"Loaded {Path(filename).name} — {len(f):,} points.")
        self.redraw()

    def apply_frequency_range(self):
        if self.data is None:
            return
        try:
            a = parse_frequency(self.fmin_var.get())
            b = parse_frequency(self.fmax_var.get())
            if b <= a:
                raise ValueError("Stop frequency must be greater than start frequency.")
            if a < self.data.frequency[0] or b > self.data.frequency[-1]:
                raise ValueError("Range is outside the S2P sweep.")
            self.redraw()
        except ValueError as e:
            messagebox.showerror("Frequency range", str(e))

    def reset_view(self):
        if self.data is None:
            return
        self.fmin_var.set(f"{self.data.frequency[0]/1e9:.6f}")
        self.fmax_var.set(f"{self.data.frequency[-1]/1e9:.6f}")
        self.redraw()

    # ----------------------------- Export -------------------------------

    def export_plot(self):
        if self.data is None:
            return
        filename = filedialog.asksaveasfilename(
            title="Export plot",
            defaultextension=".png",
            filetypes=[
                ("PNG image", "*.png"),
                ("PDF document", "*.pdf"),
                ("SVG vector", "*.svg"),
            ],
        )
        if not filename:
            return
        try:
            self.figure.savefig(filename, dpi=250, facecolor=self.figure.get_facecolor(),
                                 bbox_inches="tight")
            self._set_status(f"Plot exported: {filename}")
        except Exception as e:
            messagebox.showerror("Export error", str(e))

    def export_markers(self):
        if self.data is None or not self.markers:
            messagebox.showinfo("Markers", "Add at least one marker first.")
            return

        filename = filedialog.asksaveasfilename(
            title="Export marker table",
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
        )
        if not filename:
            return

        try:
            with open(filename, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow([
                    "Marker", "Frequency_Hz", "Frequency",
                    "S11_dB", "S11_Mag", "S11_Phase_deg", "S11_VSWR",
                    "S11_Re", "S11_Im",
                    "S22_dB", "S22_Mag", "S22_Phase_deg",
                    "S21_dB", "S21_Mag", "S21_Phase_deg"
                ])
                for i, hz in enumerate(self.markers, 1):
                    s11 = self._marker_value(self.data.s11, hz)
                    s22 = self._marker_value(self.data.s22, hz)
                    s21 = self._marker_value(self.data.s21, hz)
                    w.writerow([
                        i, f"{hz:.9f}", fmt_freq(hz),
                        f"{db20(s11):.9f}", f"{abs(s11):.9f}",
                        f"{phase_deg(s11):.9f}", f"{vswr(s11):.9f}",
                        f"{s11.real:.12g}", f"{s11.imag:.12g}",
                        f"{db20(s22):.9f}", f"{abs(s22):.9f}",
                        f"{phase_deg(s22):.9f}",
                        f"{db20(s21):.9f}", f"{abs(s21):.9f}",
                        f"{phase_deg(s21):.9f}",
                    ])
            self._set_status(f"Marker CSV exported: {filename}")
        except Exception as e:
            messagebox.showerror("CSV export error", str(e))

    # ----------------------------- Misc --------------------------------

    def _set_status(self, text):
        if hasattr(self, "status"):
            self.status.config(text=text)


if __name__ == "__main__":
    app = ShockLinePlotter()
    app.mainloop()
