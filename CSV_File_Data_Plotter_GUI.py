
# ============================================================
# Author - Vaishabh Jalmi  Version - 1.0
# ============================================================


import sys
import numpy as np
import pandas as pd

from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QFileDialog,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QAction,
    QDockWidget,
    QTableWidget,
    QTableWidgetItem,
    QMessageBox,
    QLabel,
    QGroupBox,
    QPushButton,
    QDoubleSpinBox,
    QFormLayout,
    QHeaderView
)

from PyQt5.QtGui import QColor, QFont
from PyQt5.QtCore import Qt

from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT
)

from matplotlib.figure import Figure


# ============================================================
# USER CONFIGURATION Author - Vaishabh Jalmi
# ============================================================

Z0 = 50.0


# ------------------------------------------------------------
# DUT SPECIFICATIONS
#
# S11 / S22:
# PASS when measured value <= limit
#
# S21:
# PASS when measured value >= limit
# ------------------------------------------------------------

SPECIFICATIONS = {

    "S11": {
        "limit": -26.0,
        "operator": "<=",
        "unit": "dB"
    },

    "S22": {
        "limit": -26.0,
        "operator": "<=",
        "unit": "dB"
    },

    "S21": {
        "limit": -2.0,
        "operator": ">=",
        "unit": "dB"
    }
}


# ============================================================
# DEFAULT MARKER FREQUENCIES
# ============================================================

MARKER_POSITIONS = {

    "S11": [
        0.723,
        1.900,
        2.300,
        2.900,
        3.300,
        3.800
    ],

    "S22": [
        0.723,
        1.900,
        2.300,
        2.900,
        3.300,
        3.800
    ],

    "S21": [
        0.723,
        1.900,
        2.300,
        2.900,
        3.300,
        3.800
    ]
}


# ============================================================
# COLORS
# ============================================================

TRACE_COLORS = {

    "S11": "yellow",
    "S22": "lime",
    "S21": "cyan",
    "SMITH": "magenta"

}


# ============================================================
# MARKER CLASS
# ============================================================

class Marker:

    def __init__(
        self,
        ax,
        name,
        trace,
        color="white"
    ):

        self.ax = ax

        self.name = name

        self.trace = trace

        self.color = color

        self.freq = None

        self.value = None

        self.resistance = None

        self.reactance = None

        self.gamma = None

        self.point, = ax.plot(

            [],

            [],

            marker="v",

            markersize=9,

            markerfacecolor=color,

            markeredgecolor="black",

            linestyle="None",

            picker=10,

            zorder=20

        )

        self.label = ax.text(

            0,

            0,

            name,

            color=color,

            fontsize=9,

            fontweight="bold",

            zorder=21

        )


# ============================================================
# MAIN GUI
# ============================================================

class VNAGUI(QMainWindow):

    def __init__(self):

        super().__init__()

        self.setWindowTitle(
            "Anritsu ShockLine VNA Analyzer"
        )

        self.resize(
            1750,
            1000
        )

        self.df = None

        self.active_marker = None

        self.markers = {

            "S11": [],

            "S22": [],

            "S21": [],

            "SMITH": []

        }

        self.limit_lines = {}

        self.pass_fail_text = {}

        self.summary_labels = {}

        self.delta_text = {}

        # ====================================================
        # FIGURE
        # ====================================================

        self.fig = Figure(

            figsize=(15, 9),

            facecolor="#101010"

        )

        self.canvas = FigureCanvas(

            self.fig

        )

        self.toolbar = NavigationToolbar2QT(

            self.canvas,

            self

        )

        # ====================================================
        # CENTRAL WIDGET
        # ====================================================

        central = QWidget()

        self.setCentralWidget(

            central

        )

        main_layout = QVBoxLayout(

            central

        )

        # ====================================================
        # TOP SUMMARY
        # ====================================================

        self.create_summary_panel(

            main_layout

        )

        # ====================================================
        # TOOLBAR
        # ====================================================

        main_layout.addWidget(

            self.toolbar

        )

        # ====================================================
        # CANVAS
        # ====================================================

        main_layout.addWidget(

            self.canvas

        )

        # ====================================================
        # MARKER TABLE
        # ====================================================

        self.create_marker_dock()

        # ====================================================
        # MENU
        # ====================================================

        self.create_menu()

        # ====================================================
        # MOUSE EVENTS
        # ====================================================

        self.canvas.mpl_connect(

            "pick_event",

            self.on_pick

        )

        self.canvas.mpl_connect(

            "motion_notify_event",

            self.on_motion

        )

        self.canvas.mpl_connect(

            "button_release_event",

            self.on_release

        )

        self.statusBar().showMessage(

            "Open an Anritsu CSV file"

        )

    # ========================================================
    # SUMMARY PANEL
    # ========================================================

    def create_summary_panel(

        self,

        parent_layout

    ):

        box = QGroupBox(

            "DUT TEST RESULT"

        )

        layout = QGridLayout()

        box.setLayout(

            layout

        )

        # Overall result

        self.overall_label = QLabel(

            "NO TEST DATA"

        )

        self.overall_label.setAlignment(

            Qt.AlignCenter

        )

        font = QFont()

        font.setPointSize(

            15

        )

        font.setBold(

            True

        )

        self.overall_label.setFont(

            font

        )

        self.overall_label.setMinimumHeight(

            45

        )

        layout.addWidget(

            self.overall_label,

            0,

            0,

            1,

            4

        )

        # Trace summary

        for col, trace in enumerate(

            ["S11", "S22", "S21"]

        ):

            label = QLabel(

                f"{trace}: Waiting"

            )

            label.setAlignment(

                Qt.AlignCenter

            )

            label.setMinimumHeight(

                40

            )

            layout.addWidget(

                label,

                1,

                col

            )

            self.summary_labels[

                trace

            ] = label

        # Specification summary

        spec_text = (

            f"S11 ≤ {SPECIFICATIONS['S11']['limit']:.1f} dB    |    "

            f"S22 ≤ {SPECIFICATIONS['S22']['limit']:.1f} dB    |    "

            f"S21 ≥ {SPECIFICATIONS['S21']['limit']:.1f} dB"

        )

        spec_label = QLabel(

            spec_text

        )

        spec_label.setAlignment(

            Qt.AlignCenter

        )

        layout.addWidget(

            spec_label,

            2,

            0,

            1,

            4

        )

        parent_layout.addWidget(

            box

        )

    # ========================================================
    # MARKER DOCK
    # ========================================================

    def create_marker_dock(

        self

    ):

        self.marker_table = QTableWidget()

        self.marker_table.setColumnCount(

            8

        )

        self.marker_table.setHorizontalHeaderLabels(

            [

                "Trace",

                "Marker",

                "Frequency",

                "Value",

                "Resistance",

                "Reactance",

                "Margin",

                "Status"

            ]

        )

        self.marker_table.setAlternatingRowColors(

            True

        )

        self.marker_table.horizontalHeader().setSectionResizeMode(

            QHeaderView.ResizeToContents

        )

        dock = QDockWidget(

            "Marker Measurements",

            self

        )

        dock.setWidget(

            self.marker_table

        )

        self.addDockWidget(

            Qt.RightDockWidgetArea,

            dock

        )

    # ========================================================
    # MENU
    # ========================================================

    def create_menu(

        self

    ):

        menu = self.menuBar()

        file_menu = menu.addMenu(

            "File"

        )

        open_action = QAction(

            "Open CSV",

            self

        )

        open_action.triggered.connect(

            self.open_csv

        )

        file_menu.addAction(

            open_action

        )

        # ----------------------------------------------------
        # Reload
        # ----------------------------------------------------

        reload_action = QAction(

            "Reload",

            self

        )

        reload_action.triggered.connect(

            self.reload_file

        )

        file_menu.addAction(

            reload_action

        )

        # ----------------------------------------------------
        # Exit
        # ----------------------------------------------------

        exit_action = QAction(

            "Exit",

            self

        )

        exit_action.triggered.connect(

            self.close

        )

        file_menu.addAction(

            exit_action

        )

    # ========================================================
    # OPEN CSV
    # ========================================================

    def open_csv(

        self

    ):

        file, _ = QFileDialog.getOpenFileName(

            self,

            "Open Anritsu CSV",

            "",

            "CSV Files (*.csv);;All Files (*)"

        )

        if not file:

            return

        try:

            self.current_file = file

            self.load_csv(

                file

            )

        except Exception as e:

            QMessageBox.critical(

                self,

                "CSV Error",

                str(e)

            )

    # ========================================================
    # RELOAD
    # ========================================================

    def reload_file(

        self

    ):

        if not hasattr(

            self,

            "current_file"

        ):

            return

        try:

            self.load_csv(

                self.current_file

            )

        except Exception as e:

            QMessageBox.critical(

                self,

                "Reload Error",

                str(e)

            )

    # ========================================================
    # LOAD CSV
    # ========================================================

    def load_csv(

        self,

        file

    ):

        with open(

            file,

            "r",

            encoding="utf-8",

            errors="ignore"

        ) as f:

            lines = f.readlines()

        header_line = None

        for i, line in enumerate(

            lines

        ):

            if line.strip().startswith(

                "PNT,"

            ):

                header_line = i

                break

        if header_line is None:

            raise ValueError(

                "Could not find the PNT header."

            )

        self.df = pd.read_csv(

            file,

            skiprows=header_line

        )

        self.df.columns = [

            str(c).strip()

            for c in self.df.columns

        ]

        # Convert columns

        for column in self.df.columns:

            self.df[column] = pd.to_numeric(

                self.df[column],

                errors="coerce"

            )

        self.df.dropna(

            how="all",

            inplace=True

        )

        self.df.reset_index(

            drop=True,

            inplace=True

        )

        required = [

            "FREQ1.GHZ",

            "LOGMAG1",

            "FREQ2.GHZ",

            "LOGMAG2",

            "FREQ3.GHZ",

            "LOGMAG3"

        ]

        missing = [

            c

            for c in required

            if c not in self.df.columns

        ]

        if missing:

            raise ValueError(

                "Missing columns:\n\n"

                + "\n".join(missing)

            )

        self.plot_traces()

        self.statusBar().showMessage(

            f"Loaded: {file}"

        )

    # ========================================================
    # AXIS STYLE
    # ========================================================

    def style_axis(

        self,

        ax

    ):

        ax.set_facecolor(

            "#141414"

        )

        ax.grid(

            True,

            color="#444444",

            linestyle="-",

            alpha=0.7

        )

        ax.tick_params(

            colors="white"

        )

        for spine in ax.spines.values():

            spine.set_color(

                "white"

            )

        ax.xaxis.label.set_color(

            "white"

        )

        ax.yaxis.label.set_color(

            "white"

        )

    # ========================================================
    # PLOT EVERYTHING
    # ========================================================

    def plot_traces(

        self

    ):

        self.fig.clear()

        self.limit_lines = {}

        self.pass_fail_text = {}

        self.delta_text = {}

        # ----------------------------------------------------
        # AXES
        # ----------------------------------------------------

        self.ax1 = self.fig.add_subplot(

            221

        )

        self.ax2 = self.fig.add_subplot(

            222

        )

        self.ax3 = self.fig.add_subplot(

            223

        )

        self.ax4 = self.fig.add_subplot(

            224

        )

        for ax in [

            self.ax1,

            self.ax2,

            self.ax3,

            self.ax4

        ]:

            self.style_axis(

                ax

            )

        # ----------------------------------------------------
        # S11
        # ----------------------------------------------------

        self.plot_trace(

            self.ax1,

            "S11",

            "FREQ1.GHZ",

            "LOGMAG1",

            "yellow"

        )

        # ----------------------------------------------------
        # S22
        # ----------------------------------------------------

        self.plot_trace(

            self.ax2,

            "S22",

            "FREQ2.GHZ",

            "LOGMAG2",

            "lime"

        )

        # ----------------------------------------------------
        # S21
        # ----------------------------------------------------

        self.plot_trace(

            self.ax3,

            "S21",

            "FREQ3.GHZ",

            "LOGMAG3",

            "cyan"

        )

        # ----------------------------------------------------
        # Smith
        # ----------------------------------------------------

        self.plot_smith_chart()

        # ----------------------------------------------------
        # PASS / FAIL
        # ----------------------------------------------------

        self.calculate_pass_fail()

        # ----------------------------------------------------
        # MARKERS
        # ----------------------------------------------------

        self.create_all_markers()

        # ----------------------------------------------------
        # Summary
        # ----------------------------------------------------

        self.update_overall_summary()

        self.fig.tight_layout(

            pad=2.0

        )

        self.canvas.draw()

    # ========================================================
    # NORMAL TRACE
    # ========================================================

    def plot_trace(

        self,

        ax,

        trace,

        freq_column,

        value_column,

        color

    ):

        freq = self.df[

            freq_column

        ]

        value = self.df[

            value_column

        ]

        valid = (

            freq.notna()

            &

            value.notna()

        )

        freq = freq[

            valid

        ]

        value = value[

            valid

        ]

        ax.plot(

            freq,

            value,

            color=color,

            linewidth=1.5,

            label=trace

        )

        ax.set_title(

            f"Tr{['S11','S22','S21'].index(trace)+1} - {trace}",

            color=color,

            fontweight="bold"

        )

        ax.set_xlabel(

            "Frequency (GHz)"

        )

        ax.set_ylabel(

            "Magnitude (dB)"

        )

        ax.legend(

            loc="best"

        )

        # ----------------------------------------------------
        # SPEC LIMIT
        # ----------------------------------------------------

        spec = SPECIFICATIONS[

            trace

        ]

        limit = spec[

            "limit"

        ]

        line = ax.axhline(

            limit,

            color="red",

            linestyle="--",

            linewidth=1.5,

            label=(

                f"Limit "

                f"{spec['operator']} "

                f"{limit:.1f} dB"

            )

        )

        self.limit_lines[

            trace

        ] = line

        # ----------------------------------------------------
        # LIMIT LABEL
        # ----------------------------------------------------

        ax.text(

            0.02,

            0.94,

            (

                f"SPEC: "

                f"{spec['operator']} "

                f"{limit:.1f} dB"

            ),

            transform=ax.transAxes,

            color="red",

            fontsize=9,

            fontweight="bold"

        )

    # ========================================================
    # SMITH CHART
    # ========================================================

    def plot_smith_chart(

        self

    ):

        self.ax4.clear()

        self.style_axis(

            self.ax4

        )

        self.ax4.set_aspect(

            "equal",

            adjustable="box"

        )

        required = [

            "RESISTANCE4",

            "REACTANCE4"

        ]

        if not all(

            c in self.df.columns

            for c in required

        ):

            self.ax4.text(

                0.5,

                0.5,

                "Smith chart data\nnot available",

                transform=self.ax4.transAxes,

                color="white",

                ha="center",

                va="center"

            )

            return

        r = self.df[

            "RESISTANCE4"

        ].to_numpy()

        x = self.df[

            "REACTANCE4"

        ].to_numpy()

        valid = (

            np.isfinite(r)

            &

            np.isfinite(x)

        )

        r = r[

            valid

        ]

        x = x[

            valid

        ]

        if len(r) == 0:

            return

        z = r + 1j * x

        gamma = (

            z - Z0

        ) / (

            z + Z0

        )

        gx = np.real(

            gamma

        )

        gy = np.imag(

            gamma

        )

        theta = np.linspace(

            0,

            2 * np.pi,

            1000

        )

        # Outer circle

        self.ax4.plot(

            np.cos(theta),

            np.sin(theta),

            color="#888888",

            linewidth=1.2

        )

        # Resistance circles

        resistance_values = [

            0,

            0.2,

            0.5,

            1,

            2,

            5

        ]

        for resistance in resistance_values:

            center = (

                resistance

                /

                (resistance + 1)

            )

            radius = (

                1

                /

                (resistance + 1)

            )

            t = np.linspace(

                0,

                2 * np.pi,

                500

            )

            cx = (

                center

                +

                radius * np.cos(t)

            )

            cy = (

                radius * np.sin(t)

            )

            self.ax4.plot(

                cx,

                cy,

                color="#333333",

                linewidth=0.6

            )

        # Reactance circles

        reactance_values = [

            -5,

            -2,

            -1,

            -0.5,

            0.5,

            1,

            2,

            5

        ]

        for reactance in reactance_values:

            center_x = 1

            center_y = (

                1 / reactance

            )

            radius = abs(

                1 / reactance

            )

            t = np.linspace(

                0,

                2 * np.pi,

                500

            )

            cx = (

                center_x

                +

                radius * np.cos(t)

            )

            cy = (

                center_y

                +

                radius * np.sin(t)

            )

            mask = (

                (cx >= -1)

                &

                (cx <= 1)

                &

                (cy >= -1)

                &

                (cy <= 1)

            )

            self.ax4.plot(

                cx[mask],

                cy[mask],

                color="#333333",

                linewidth=0.6

            )

        self.ax4.axhline(

            0,

            color="#555555",

            linewidth=0.8

        )

        # DUT S11

        self.ax4.plot(

            gx,

            gy,

            color="magenta",

            linewidth=2,

            label="S11"

        )

        self.ax4.set_xlim(

            -1.1,

            1.1

        )

        self.ax4.set_ylim(

            -1.1,

            1.1

        )

        self.ax4.set_xticks([])

        self.ax4.set_yticks([])

        self.ax4.set_title(

            "Tr4 - S11 Smith Chart",

            color="magenta",

            fontweight="bold"

        )

        self.ax4.legend(

            loc="upper right"

        )

    # ========================================================
    # PASS FAIL CALCULATION
    # ========================================================

    def calculate_pass_fail(

        self

    ):

        self.pass_results = {}

        trace_columns = {

            "S11": "LOGMAG1",

            "S22": "LOGMAG2",

            "S21": "LOGMAG3"

        }

        for trace, column in trace_columns.items():

            freq_column = {

                "S11": "FREQ1.GHZ",

                "S22": "FREQ2.GHZ",

                "S21": "FREQ3.GHZ"

            }[trace]

            data = self.df[

                column

            ].to_numpy()

            freq = self.df[

                freq_column

            ].to_numpy()

            valid = (

                np.isfinite(data)

                &

                np.isfinite(freq)

            )

            data = data[

                valid

            ]

            freq = freq[

                valid

            ]

            if len(data) == 0:

                continue

            limit = SPECIFICATIONS[

                trace

            ][

                "limit"

            ]

            operator = SPECIFICATIONS[

                trace

            ][

                "operator"

            ]

            # ------------------------------------------------
            # S11 / S22
            # ------------------------------------------------

            if operator == "<=":

                passed_array = (

                    data <= limit

                )

                worst_index = np.argmax(

                    data

                )

                worst_value = data[

                    worst_index

                ]

                margin = (

                    limit

                    -

                    worst_value

                )

            # ------------------------------------------------
            # S21
            # ------------------------------------------------

            else:

                passed_array = (

                    data >= limit

                )

                worst_index = np.argmin(

                    data

                )

                worst_value = data[

                    worst_index

                ]

                margin = (

                    worst_value

                    -

                    limit

                )

            passed = bool(

                np.all(

                    passed_array

                )

            )

            worst_frequency = freq[

                worst_index

            ]

            self.pass_results[

                trace

            ] = {

                "passed": passed,

                "worst_value": worst_value,

                "worst_frequency": worst_frequency,

                "margin": margin,

                "limit": limit

            }

            # ------------------------------------------------
            # PASS FAIL TEXT
            # ------------------------------------------------

            result = (

                "PASS"

                if passed

                else

                "FAIL"

            )

            color = (

                "lime"

                if passed

                else

                "red"

            )

            self.pass_fail_text[

                trace

            ] = self.get_axis_for_trace(

                trace

            ).text(

                0.98,

                0.94,

                result,

                transform=self.get_axis_for_trace(

                    trace

                ).transAxes,

                ha="right",

                va="top",

                color=color,

                fontsize=15,

                fontweight="bold",

                bbox=dict(

                    facecolor="#101010",

                    edgecolor=color,

                    linewidth=1.5,

                    alpha=0.9

                )

            )

            # ------------------------------------------------
            # SUMMARY
            # ------------------------------------------------

            summary = (

                f"{trace}: "

                f"{result} | "

                f"Worst "

                f"{worst_value:.2f} dB @ "

                f"{worst_frequency:.4f} GHz | "

                f"Margin "

                f"{margin:+.2f} dB"

            )

            self.summary_labels[

                trace

            ].setText(

                summary

            )

            self.summary_labels[

                trace

            ].setStyleSheet(

                f"""

                QLabel {{

                    color: {color};

                    background-color: #181818;

                    border: 2px solid {color};

                    padding: 5px;

                    font-weight: bold;

                }}

                """

            )

    # ========================================================
    # GET AXIS
    # ========================================================

    def get_axis_for_trace(

        self,

        trace

    ):

        return {

            "S11": self.ax1,

            "S22": self.ax2,

            "S21": self.ax3

        }[trace]

    # ========================================================
    # CREATE MARKERS
    # ========================================================

    def create_all_markers(

        self

    ):

        self.markers = {

            "S11": [],

            "S22": [],

            "S21": [],

            "SMITH": []

        }

        # S11

        self.create_trace_markers(

            "S11",

            self.ax1,

            "FREQ1.GHZ",

            "LOGMAG1",

            MARKER_POSITIONS["S11"]

        )

        # S22

        self.create_trace_markers(

            "S22",

            self.ax2,

            "FREQ2.GHZ",

            "LOGMAG2",

            MARKER_POSITIONS["S22"]

        )

        # S21

        self.create_trace_markers(

            "S21",

            self.ax3,

            "FREQ3.GHZ",

            "LOGMAG3",

            MARKER_POSITIONS["S21"]

        )

        # Smith

        self.create_best_impedance_marker()

        # Delta

        self.create_delta_text(

            "S11",

            self.ax1

        )

        self.create_delta_text(

            "S22",

            self.ax2

        )

        self.create_delta_text(

            "S21",

            self.ax3

        )

        self.update_all_deltas()

        self.update_marker_table()

    # ========================================================
    # CREATE TRACE MARKERS
    # ========================================================

    def create_trace_markers(

        self,

        trace,

        ax,

        freq_column,

        value_column,

        positions

    ):

        frequencies = self.df[

            freq_column

        ].to_numpy()

        values = self.df[

            value_column

        ].to_numpy()

        valid = (

            np.isfinite(frequencies)

            &

            np.isfinite(values)

        )

        frequencies = frequencies[

            valid

        ]

        values = values[

            valid

        ]

        if len(frequencies) == 0:

            return

        color = TRACE_COLORS[

            trace

        ]

        for i, requested_frequency in enumerate(

            positions

        ):

            index = np.abs(

                frequencies

                -

                requested_frequency

            ).argmin()

            marker = Marker(

                ax,

                f"M{i + 1}",

                trace,

                color

            )

            marker.freq = frequencies[

                index

            ]

            marker.value = values[

                index

            ]

            marker.point.set_data(

                [

                    marker.freq

                ],

                [

                    marker.value

                ]

            )

            marker.label.set_position(

                (

                    marker.freq,

                    marker.value

                )

            )

            self.markers[

                trace

            ].append(

                marker

            )

    # ========================================================
    # BEST IMPEDANCE MARKER
    # ========================================================

    def create_best_impedance_marker(

        self

    ):

        required = [

            "FREQ1.GHZ",

            "LOGMAG1",

            "RESISTANCE4",

            "REACTANCE4"

        ]

        if not all(

            c in self.df.columns

            for c in required

        ):

            return

        freq = self.df[

            "FREQ1.GHZ"

        ].to_numpy()

        s11 = self.df[

            "LOGMAG1"

        ].to_numpy()

        resistance = self.df[

            "RESISTANCE4"

        ].to_numpy()

        reactance = self.df[

            "REACTANCE4"

        ].to_numpy()

        valid = (

            np.isfinite(freq)

            &

            np.isfinite(s11)

            &

            np.isfinite(resistance)

            &

            np.isfinite(reactance)

        )

        freq = freq[

            valid

        ]

        s11 = s11[

            valid

        ]

        resistance = resistance[

            valid

        ]

        reactance = reactance[

            valid

        ]

        if len(freq) == 0:

            return

        z = (

            resistance

            +

            1j * reactance

        )

        impedance_error = np.abs(

            z - Z0

        )

        best_index = np.argmin(

            impedance_error

        )

        gamma = (

            z - Z0

        ) / (

            z + Z0

        )

        gx = np.real(

            gamma

        )

        gy = np.imag(

            gamma

        )

        marker = Marker(

            self.ax4,

            "M1",

            "SMITH",

            "white"

        )

        marker.freq = freq[

            best_index

        ]

        marker.value = s11[

            best_index

        ]

        marker.resistance = resistance[

            best_index

        ]

        marker.reactance = reactance[

            best_index

        ]

        marker.gamma = gamma[

            best_index

        ]

        marker.point.set_data(

            [

                gx[best_index]

            ],

            [

                gy[best_index]

            ]

        )

        marker.label.set_position(

            (

                gx[best_index],

                gy[best_index]

            )

        )

        marker.label.set_text(

            "BEST Z"

        )

        self.markers[

            "SMITH"

        ].append(

            marker

        )

        # ----------------------------------------------------
        # Smith information
        # ----------------------------------------------------

        self.ax4.text(

            0.02,

            0.03,

            (

                f"BEST Z\n"

                f"{marker.freq:.6f} GHz\n"

                f"Z = "

                f"{marker.resistance:.2f}"

                f"{marker.reactance:+.2f}j Ω\n"

                f"S11 = "

                f"{marker.value:.2f} dB"

            ),

            transform=self.ax4.transAxes,

            color="white",

            fontsize=9,

            fontweight="bold",

            verticalalignment="bottom"

        )

    # ========================================================
    # DELTA TEXT
    # ========================================================

    def create_delta_text(

        self,

        trace,

        ax

    ):

        self.delta_text[

            trace

        ] = ax.text(

            0.02,

            0.03,

            "",

            transform=ax.transAxes,

            color="white",

            fontsize=9,

            fontweight="bold"

        )

    # ========================================================
    # DELTA
    # ========================================================

    def update_all_deltas(

        self

    ):

        for trace in [

            "S11",

            "S22",

            "S21"

        ]:

            markers = self.markers[

                trace

            ]

            if len(markers) < 2:

                continue

            m1 = markers[0]

            m2 = markers[1]

            delta_frequency = abs(

                m2.freq

                -

                m1.freq

            )

            delta_value = (

                m2.value

                -

                m1.value

            )

            self.delta_text[

                trace

            ].set_text(

                f"M1 → M2\n"

                f"ΔF = "

                f"{delta_frequency * 1000:.1f} MHz\n"

                f"ΔY = "

                f"{delta_value:+.3f} dB"

            )

    # ========================================================
    # OVERALL RESULT
    # ========================================================

    def update_overall_summary(

        self

    ):

        if not hasattr(

            self,

            "pass_results"

        ):

            return

        if len(

            self.pass_results

        ) < 3:

            return

        overall_pass = all(

            result["passed"]

            for result in self.pass_results.values()

        )

        if overall_pass:

            self.overall_label.setText(

                "OVERALL DUT RESULT: PASS"

            )

            self.overall_label.setStyleSheet(

                """

                QLabel {

                    color: lime;

                    background-color: #102010;

                    border: 3px solid lime;

                    font-weight: bold;

                }

                """

            )

        else:

            self.overall_label.setText(

                "OVERALL DUT RESULT: FAIL"

            )

            self.overall_label.setStyleSheet(

                """

                QLabel {

                    color: red;

                    background-color: #200f0f;

                    border: 3px solid red;

                    font-weight: bold;

                }

                """

            )

    # ========================================================
    # MARKER TABLE
    # ========================================================

    def update_marker_table(

        self

    ):

        total_rows = (

            4

            +

            6

            +

            6

            +

            6

            +

            1

        )

        self.marker_table.setRowCount(

            total_rows

        )

        row = 0

        row = self.add_section_header(

            row,

            "TR1 — S11 MARKERS"

        )

        row = self.add_marker_rows(

            row,

            self.markers["S11"]

        )

        row = self.add_section_header(

            row,

            "TR2 — S22 MARKERS"

        )

        row = self.add_marker_rows(

            row,

            self.markers["S22"]

        )

        row = self.add_section_header(

            row,

            "TR3 — S21 MARKERS"

        )

        row = self.add_marker_rows(

            row,

            self.markers["S21"]

        )

        row = self.add_section_header(

            row,

            "TR4 — S11 SMITH / BEST IMPEDANCE"

        )

        self.add_marker_rows(

            row,

            self.markers["SMITH"]

        )

    # ========================================================
    # SECTION HEADER
    # ========================================================

    def add_section_header(

        self,

        row,

        title

    ):

        self.marker_table.setSpan(

            row,

            0,

            1,

            8

        )

        item = QTableWidgetItem(

            title

        )

        item.setTextAlignment(

            Qt.AlignCenter

        )

        item.setBackground(

            QColor("#202020")

        )

        item.setForeground(

            QColor("white")

        )

        font = item.font()

        font.setBold(

            True

        )

        font.setPointSize(

            10

        )

        item.setFont(

            font

        )

        self.marker_table.setItem(

            row,

            0,

            item

        )

        return row + 1

    # ========================================================
    # MARKER TABLE ROWS
    # ========================================================

    def add_marker_rows(

        self,

        row,

        markers

    ):

        for marker in markers:

            self.marker_table.setItem(

                row,

                0,

                QTableWidgetItem(

                    marker.trace

                )

            )

            self.marker_table.setItem(

                row,

                1,

                QTableWidgetItem(

                    marker.name

                )

            )

            self.marker_table.setItem(

                row,

                2,

                QTableWidgetItem(

                    f"{marker.freq:.6f} GHz"

                )

            )

            self.marker_table.setItem(

                row,

                3,

                QTableWidgetItem(

                    f"{marker.value:.4f} dB"

                )

            )

            if marker.trace == "SMITH":

                self.marker_table.setItem(

                    row,

                    4,

                    QTableWidgetItem(

                        f"{marker.resistance:.3f} Ω"

                    )

                )

                self.marker_table.setItem(

                    row,

                    5,

                    QTableWidgetItem(

                        f"{marker.reactance:+.3f} Ω"

                    )

                )

                self.marker_table.setItem(

                    row,

                    6,

                    QTableWidgetItem(

                        "BEST 50Ω"

                    )

                )

                status_item = QTableWidgetItem(

                    "BEST Z"

                )

                status_item.setForeground(

                    QColor("lime")

                )

                self.marker_table.setItem(

                    row,

                    7,

                    status_item

                )

            else:

                self.marker_table.setItem(

                    row,

                    4,

                    QTableWidgetItem(

                        "-"

                    )

                )

                self.marker_table.setItem(

                    row,

                    5,

                    QTableWidgetItem(

                        "-"

                    )

                )

                # --------------------------------------------
                # Marker margin
                # --------------------------------------------

                spec = SPECIFICATIONS[

                    marker.trace

                ]

                limit = spec[

                    "limit"

                ]

                if spec["operator"] == "<=":

                    margin = (

                        limit

                        -

                        marker.value

                    )

                    passed = (

                        marker.value <= limit

                    )

                else:

                    margin = (

                        marker.value

                        -

                        limit

                    )

                    passed = (

                        marker.value >= limit

                    )

                margin_item = QTableWidgetItem(

                    f"{margin:+.3f} dB"

                )

                self.marker_table.setItem(

                    row,

                    6,

                    margin_item

                )

                status = (

                    "PASS"

                    if passed

                    else

                    "FAIL"

                )

                status_item = QTableWidgetItem(

                    status

                )

                status_item.setForeground(

                    QColor(

                        "lime"

                        if passed

                        else

                        "red"

                    )

                )

                self.marker_table.setItem(

                    row,

                    7,

                    status_item

                )

            row += 1

        return row

    # ========================================================
    # PICK EVENT
    # ========================================================

    def on_pick(

        self,

        event

    ):

        for trace in self.markers:

            for marker in self.markers[

                trace

            ]:

                if event.artist == marker.point:

                    self.active_marker = marker

                    self.statusBar().showMessage(

                        f"Dragging "

                        f"{marker.trace} "

                        f"{marker.name}"

                    )

                    return

    # ========================================================
    # MOTION
    # ========================================================

    def on_motion(

        self,

        event

    ):

        if self.active_marker is None:

            return

        marker = self.active_marker

        if marker.trace == "S11":

            if event.inaxes != self.ax1:

                return

            self.move_normal_marker(

                marker,

                "FREQ1.GHZ",

                "LOGMAG1",

                event.xdata

            )

        elif marker.trace == "S22":

            if event.inaxes != self.ax2:

                return

            self.move_normal_marker(

                marker,

                "FREQ2.GHZ",

                "LOGMAG2",

                event.xdata

            )

        elif marker.trace == "S21":

            if event.inaxes != self.ax3:

                return

            self.move_normal_marker(

                marker,

                "FREQ3.GHZ",

                "LOGMAG3",

                event.xdata

            )

        elif marker.trace == "SMITH":

            if event.inaxes != self.ax4:

                return

            self.move_smith_marker(

                marker,

                event.xdata,

                event.ydata

            )

        self.update_marker_table()

        self.update_all_deltas()

        self.canvas.draw_idle()

    # ========================================================
    # MOVE NORMAL MARKER
    # ========================================================

    def move_normal_marker(

        self,

        marker,

        freq_column,

        value_column,

        target_frequency

    ):

        if target_frequency is None:

            return

        frequencies = self.df[

            freq_column

        ].to_numpy()

        values = self.df[

            value_column

        ].to_numpy()

        valid = (

            np.isfinite(frequencies)

            &

            np.isfinite(values)

        )

        frequencies = frequencies[

            valid

        ]

        values = values[

            valid

        ]

        if len(frequencies) == 0:

            return

        index = np.abs(

            frequencies

            -

            target_frequency

        ).argmin()

        marker.freq = frequencies[

            index

        ]

        marker.value = values[

            index

        ]

        marker.point.set_data(

            [

                marker.freq

            ],

            [

                marker.value

            ]

        )

        marker.label.set_position(

            (

                marker.freq,

                marker.value

            )

        )

    # ========================================================
    # MOVE SMITH MARKER
    # ========================================================

    def move_smith_marker(

        self,

        marker,

        mouse_x,

        mouse_y

    ):

        if mouse_x is None or mouse_y is None:

            return

        required = [

            "FREQ1.GHZ",

            "LOGMAG1",

            "RESISTANCE4",

            "REACTANCE4"

        ]

        if not all(

            c in self.df.columns

            for c in required

        ):

            return

        freq = self.df[

            "FREQ1.GHZ"

        ].to_numpy()

        s11 = self.df[

            "LOGMAG1"

        ].to_numpy()

        r = self.df[

            "RESISTANCE4"

        ].to_numpy()

        x = self.df[

            "REACTANCE4"

        ].to_numpy()

        valid = (

            np.isfinite(freq)

            &

            np.isfinite(s11)

            &

            np.isfinite(r)

            &

            np.isfinite(x)

        )

        freq = freq[

            valid

        ]

        s11 = s11[

            valid

        ]

        r = r[

            valid

        ]

        x = x[

            valid

        ]

        z = r + 1j * x

        gamma = (

            z - Z0

        ) / (

            z + Z0

        )

        gx = np.real(

            gamma

        )

        gy = np.imag(

            gamma

        )

        distance = (

            gx - mouse_x

        ) ** 2 + (

            gy - mouse_y

        ) ** 2

        index = np.argmin(

            distance

        )

        marker.freq = freq[

            index

        ]

        marker.value = s11[

            index

        ]

        marker.resistance = r[

            index

        ]

        marker.reactance = x[

            index

        ]

        marker.gamma = gamma[

            index

        ]

        marker.point.set_data(

            [

                gx[index]

            ],

            [

                gy[index]

            ]

        )

        marker.label.set_position(

            (

                gx[index],

                gy[index]

            )

        )

    # ========================================================
    # RELEASE
    # ========================================================

    def on_release(

        self,

        event

    ):

        if self.active_marker is not None:

            marker = self.active_marker

            self.statusBar().showMessage(

                f"{marker.trace} "

                f"{marker.name}: "

                f"{marker.freq:.6f} GHz"

            )

        self.active_marker = None


# ============================================================
# MAIN
# ============================================================

def main():

    app = QApplication(

        sys.argv

    )

    app.setStyle(

        "Fusion"

    )

    window = VNAGUI()

    window.show()

    sys.exit(

        app.exec_()

    )


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    main()