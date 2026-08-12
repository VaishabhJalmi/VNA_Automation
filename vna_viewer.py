import sys
import numpy as np
import pandas as pd

from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QFileDialog,
    QWidget,
    QVBoxLayout,
    QAction,
    QDockWidget,
    QTableWidget,
    QTableWidgetItem
)


from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt import NavigationToolbar2QT



from matplotlib.figure import Figure

import matplotlib.pyplot as plt

try:
    import skrf as rf
    HAS_SKRF = True
except:
    HAS_SKRF = False


PASS_LIMITS = {
    "S11": 0.1,
    "S22": 0.15,
    "S21": -50
}


class Marker:

    def __init__(self, ax, name, color):

        self.ax = ax
        self.name = name
        self.color = color

        self.freq = None
        self.value = None

        self.point, = ax.plot(
            [],
            [],
            marker='v',
            markersize=10,
            color='white',
            picker=8
        )

        self.label = ax.text(
            0,
            0,
            name,
            color='white',
            fontsize=9
        )


class VNAGUI(QMainWindow):

    def __init__(self):

        super().__init__()

        self.setWindowTitle("VNA Viewer")
        self.resize(1500, 900)

        self.active_marker = None

        self.fig = Figure(facecolor="#101010")
        self.canvas = FigureCanvas(self.fig)

        self.toolbar = NavigationToolbar2QT(
            self.canvas,
            self
        )

        central = QWidget()
        self.setCentralWidget(central)

        layout = QVBoxLayout(central)
        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas)

        self.marker_table = QTableWidget()
        self.marker_table.setColumnCount(3)
        self.marker_table.setHorizontalHeaderLabels(
            ["Marker", "Frequency", "Value"]
        )

        dock = QDockWidget("Markers")
        dock.setWidget(self.marker_table)
        self.addDockWidget(
            2,
            dock
        )

        self.create_menu()

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

    def create_menu(self):

        menu = self.menuBar()

        file_menu = menu.addMenu("File")

        act = QAction("Open CSV", self)

        act.triggered.connect(
            self.open_csv
        )

        file_menu.addAction(act)

    def open_csv(self):

        file, _ = QFileDialog.getOpenFileName(
            self,
            "Open CSV",
            "",
            "CSV (*.csv)"
        )

        if file:
            self.load_csv(file)

    def load_csv(self, file):

        with open(file, 'r') as f:
            lines = f.readlines()

        header_line = None

        for i, line in enumerate(lines):
            if line.startswith("PNT,"):
                header_line = i
                break

        self.df = pd.read_csv(
            file,
            skiprows=header_line
        )

        self.plot_traces()

    def style_axis(self, ax):

        ax.set_facecolor("#141414")

        ax.grid(True,
                color="#444444",
                linestyle='-')

        ax.tick_params(
            colors="white"
        )

        for s in ax.spines.values():
            s.set_color("white")

    def plot_traces(self):

        self.fig.clear()

        self.ax1 = self.fig.add_subplot(221)
        self.ax2 = self.fig.add_subplot(222)
        self.ax3 = self.fig.add_subplot(223)
        self.ax4 = self.fig.add_subplot(224)

        for ax in [self.ax1, self.ax2, self.ax3]:
            self.style_axis(ax)

        self.style_axis(self.ax4)

        self.ax1.plot(
            self.df["FREQ1.GHZ"],
            self.df["LOGMAG1"],
            color='yellow'
        )

        self.ax2.plot(
            self.df["FREQ2.GHZ"],
            self.df["LOGMAG2"],
            color='lime'
        )

        self.ax3.plot(
            self.df["FREQ3.GHZ"],
            self.df["LOGMAG3"],
            color='cyan'
        )

        self.ax1.set_title(
            "Tr1 S11",
            color='yellow'
        )

        self.ax2.set_title(
            "Tr2 S22",
            color='lime'
        )

        self.ax3.set_title(
            "Tr3 S21",
            color='cyan'
        )

        r = self.df["RESISTANCE4"]
        x = self.df["REACTANCE4"]

        z = r + 1j*x

        if HAS_SKRF:

            rf.plotting.plot_smith(
                chart_type='z',
                ax=self.ax4
            )

        self.ax4.plot(
            np.real(z),
            np.imag(z),
            color='magenta',
            lw=2
        )

        self.ax4.set_title(
            "Tr4 Smith",
            color='magenta'
        )

        self.draw_pass_fail()

        self.create_markers()

        self.fig.tight_layout()

        self.canvas.draw()

    def draw_pass_fail(self):

        traces = [
            (self.ax1, self.df["LOGMAG1"], "S11"),
            (self.ax2, self.df["LOGMAG2"], "S22"),
            (self.ax3, self.df["LOGMAG3"], "S21")
        ]

        for ax, data, name in traces:

            if name == "S21":
                passed = np.all(
                    data < PASS_LIMITS[name]
                )
            else:
                passed = np.all(
                    data < PASS_LIMITS[name]
                )

            color = "lime" if passed else "red"

            ax.text(
                0.98,
                0.98,
                "PASS" if passed else "FAIL",
                transform=ax.transAxes,
                ha='right',
                va='top',
                color=color,
                fontsize=12,
                weight='bold'
            )

    def create_markers(self):

        self.markers = []

        freqs = self.df["FREQ1.GHZ"]
        data = self.df["LOGMAG1"]

        positions = [
            0.723,
            1.9,
            2.3,
            2.9,
            3.3,
            3.8
        ]

        for i, freq in enumerate(positions):

            idx = np.abs(
                freqs - freq
            ).idxmin()

            m = Marker(
                self.ax1,
                f"M{i+1}",
                "white"
            )

            x = freqs.iloc[idx]
            y = data.iloc[idx]

            m.freq = x
            m.value = y

            m.point.set_data(
                [x],
                [y]
            )

            m.label.set_position(
                (x, y)
            )

            self.markers.append(m)

        self.update_marker_table()

        self.delta_text = self.ax1.text(
            0.02,
            0.02,
            "",
            transform=self.ax1.transAxes,
            color='cyan',
            fontsize=10
        )

        self.update_delta()

    def update_delta(self):

        if len(self.markers) < 2:
            return

        m1 = self.markers[0]
        m2 = self.markers[1]

        dfreq = abs(
            m2.freq - m1.freq
        )

        dmag = (
            m2.value - m1.value
        )

        self.delta_text.set_text(
            f"ΔF={dfreq*1000:.1f}MHz\n"
            f"ΔY={dmag:.4f}dB"
        )

    def update_marker_table(self):

        self.marker_table.setRowCount(
            len(self.markers)
        )

        for row, m in enumerate(
            self.markers
        ):

            self.marker_table.setItem(
                row,
                0,
                QTableWidgetItem(m.name)
            )

            self.marker_table.setItem(
                row,
                1,
                QTableWidgetItem(
                    f"{m.freq:.6f} GHz"
                )
            )

            self.marker_table.setItem(
                row,
                2,
                QTableWidgetItem(
                    f"{m.value:.5f} dB"
                )
            )

    def on_pick(self, event):

        for m in self.markers:

            if event.artist == m.point:
                self.active_marker = m
                break

    def on_release(self, event):

        self.active_marker = None

    def on_motion(self, event):

        if self.active_marker is None:
            return

        if event.inaxes != self.ax1:
            return

        freq = event.xdata

        freqs = self.df["FREQ1.GHZ"]
        values = self.df["LOGMAG1"]

        idx = np.abs(
            freqs - freq
        ).idxmin()

        x = freqs.iloc[idx]
        y = values.iloc[idx]

        self.active_marker.freq = x
        self.active_marker.value = y

        self.active_marker.point.set_data(
            [x],
            [y]
        )

        self.active_marker.label.set_position(
            (x, y)
        )

        self.update_marker_table()

        self.update_delta()

        self.canvas.draw_idle()


def main():

    app = QApplication(sys.argv)

    app.setStyle("Fusion")

    w = VNAGUI()
    w.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()