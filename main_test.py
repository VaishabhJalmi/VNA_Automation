import sys
import os
import time
from datetime import datetime

import pyvisa
import numpy as np

from qtpy.QtWidgets import (
    QApplication,
    QWidget,
    QLabel,
    QPushButton,
    QLineEdit,
    QTextEdit,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QMessageBox,
)

from qtpy.QtGui import QPixmap
from qtpy.QtCore import Qt

# PDF imports
from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.styles import getSampleStyleSheet


REPORT_FOLDER = "Test_Reports"
SCREENSHOT_FOLDER = "Screenshots"

os.makedirs(REPORT_FOLDER, exist_ok=True)
os.makedirs(SCREENSHOT_FOLDER, exist_ok=True)

DEFAULT_LIMITS = {
    "freq_start_ghz": 1,
    "freq_stop_ghz": 6,
    "num_points": 201,
    "power_dbm": -10,
    "if_bandwidth_hz": 1000,
    "max_insertion_loss_db": 1.5,
}


class VNAGUI(QWidget):

    def __init__(self):
        super().__init__()

        self.vna = None

        self.setWindowTitle("Anritsu MS46122B Automation")
        self.resize(900, 700)

        self.setup_ui()
        self.connect_vna()

    def setup_ui(self):

        form = QFormLayout()

        self.serial_edit = QLineEdit()
        self.part_edit = QLineEdit()
        self.order_edit = QLineEdit()

        form.addRow("Serial Number:", self.serial_edit)
        form.addRow("Part Number:", self.part_edit)
        form.addRow("Order Number:", self.order_edit)

        self.start_btn = QPushButton("Start Test")
        self.exit_btn = QPushButton("Exit")

        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.start_btn)
        btn_layout.addWidget(self.exit_btn)

        self.result_label = QLabel("READY")
        self.result_label.setAlignment(Qt.AlignCenter)
        self.result_label.setStyleSheet("""
            font-size: 24px;
            font-weight: bold;
            color: blue;
        """)

        self.image_label = QLabel()
        self.image_label.setFixedHeight(350)
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet("border:1px solid gray")

        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)

        layout = QVBoxLayout()

        layout.addLayout(form)
        layout.addLayout(btn_layout)
        layout.addWidget(self.result_label)
        layout.addWidget(QLabel("Screenshot Preview"))
        layout.addWidget(self.image_label)
        layout.addWidget(QLabel("Log"))
        layout.addWidget(self.log_box)

        self.setLayout(layout)

        self.start_btn.clicked.connect(self.start_test)
        self.exit_btn.clicked.connect(self.close)

    def log(self, msg):
        self.log_box.append(msg)
        QApplication.processEvents()

    def connect_vna(self):

        try:
            rm = pyvisa.ResourceManager()

            resources = rm.list_resources()

            self.log("Searching VNA...")

            if not resources:
                self.log("No VISA devices found")
                return

            address = resources[0]

            self.vna = rm.open_resource(address)
            self.vna.timeout = 30000

            idn = self.vna.query("*IDN?")
            self.log(f"Connected: {idn}")

        except Exception as e:
            QMessageBox.critical(self, "VNA Error", str(e))

    def configure_vna(self):

        self.log("Configuring VNA...")

        self.vna.write("*RST")

        self.vna.write(
            f"SENS:FREQ:STAR {DEFAULT_LIMITS['freq_start_ghz']}e9"
        )

        self.vna.write(
            f"SENS:FREQ:STOP {DEFAULT_LIMITS['freq_stop_ghz']}e9"
        )

        self.vna.write(
            f"SENS:SWE:POIN {DEFAULT_LIMITS['num_points']}"
        )

    def trigger_measurement(self):

        self.log("Running sweep...")

        self.vna.write("INIT:IMM")
        self.vna.query("*OPC?")

        data = self.vna.query("CALC:DATA:FDAT?")

        values = np.array(
            [float(x) for x in data.split(",")]
        )

        return values

    def analyze(self, values):

        max_il = np.max(values)

        passed = (
            max_il <= DEFAULT_LIMITS["max_insertion_loss_db"]
        )

        return "PASS" if passed else "FAIL"

    def capture_screenshot(self, serial):

        filename = f"{serial}.png"

        filepath = os.path.join(
            SCREENSHOT_FOLDER,
            filename
        )

        try:
            self.log("Capturing screenshot...")

            self.vna.write(
                f':MMEMory:STORE:IMAGe "{filename}"'
            )

            time.sleep(2)

            image_data = self.vna.query_binary_values(
                f':MMEMory:DATA? "{filename}"',
                datatype="B"
            )

            with open(filepath, "wb") as f:
                f.write(bytes(image_data))

            return filepath

        except Exception as e:
            self.log(f"Screenshot failed: {e}")
            return None

    def generate_pdf(
        self,
        serial,
        part,
        order,
        result,
    ):

        filename = f"{serial}.pdf"

        pdf_path = os.path.join(
            REPORT_FOLDER,
            filename
        )

        doc = SimpleDocTemplate(pdf_path)

        styles = getSampleStyleSheet()

        story = []

        story.append(
            Paragraph(
                "Anritsu MS46122B Test Report",
                styles["Title"]
            )
        )

        story.append(
            Paragraph(
                f"Serial: {serial}",
                styles["Normal"]
            )
        )

        story.append(
            Paragraph(
                f"Part: {part}",
                styles["Normal"]
            )
        )

        story.append(
            Paragraph(
                f"Order: {order}",
                styles["Normal"]
            )
        )

        story.append(
            Paragraph(
                f"Result: {result}",
                styles["Heading2"]
            )
        )

        doc.build(story)

        self.log(f"PDF Saved: {pdf_path}")

    def start_test(self):

        serial = self.serial_edit.text().strip()
        part = self.part_edit.text().strip()
        order = self.order_edit.text().strip()

        if not serial:
            QMessageBox.warning(
                self,
                "Input",
                "Enter Serial Number"
            )
            return

        if self.vna is None:
            QMessageBox.critical(
                self,
                "Connection Error",
                "VNA not connected."
            )
            return

        try:
            self.configure_vna()

            values = self.trigger_measurement()

            result = self.analyze(values)

            if result == "PASS":
                self.result_label.setText("PASS")
                self.result_label.setStyleSheet(
                    "font-size:28px;color:green;font-weight:bold;"
                )
            else:
                self.result_label.setText("FAIL")
                self.result_label.setStyleSheet(
                    "font-size:28px;color:red;font-weight:bold;"
                )

            image = self.capture_screenshot(serial)

            if image and os.path.exists(image):

                pix = QPixmap(image)

                self.image_label.setPixmap(
                    pix.scaled(
                        self.image_label.width(),
                        self.image_label.height(),
                        Qt.KeepAspectRatio
                    )
                )

            self.generate_pdf(
                serial,
                part,
                order,
                result
            )

            self.log(
                f"Completed Test -> {serial} : {result}"
            )

        except Exception as e:

            QMessageBox.critical(
                self,
                "Test Error",
                str(e)
            )


if __name__ == "__main__":

    app = QApplication(sys.argv)

    win = VNAGUI()
    win.show()

    sys.exit(app.exec_())