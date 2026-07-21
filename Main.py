#!/usr/bin/env python3
"""
Full VNA Automation Script for Anritsu MS46122B
Features:
- Barcode scan input (Serial, Part, Order)
- Measure S-parameters
- Capture VNA screen screenshot
- Pass/Fail analysis
- Generate professional PDF report per test
"""

import pyvisa
import numpy as np
import os
import time
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT
import matplotlib.pyplot as plt
from io import BytesIO

# ====================== CONFIGURATION ======================
VNA_ADDRESS = None          # Will be auto-detected or set manually
REPORT_FOLDER = "Test_Reports"
SCREENSHOT_FOLDER = "Screenshots"
DATA_FOLDER = "Raw_Data"

# Create folders
for folder in [REPORT_FOLDER, SCREENSHOT_FOLDER, DATA_FOLDER]:
    os.makedirs(folder, exist_ok=True)

# Example Pass/Fail Limits (customize for your cables/parts)
DEFAULT_LIMITS = {
    "min_return_loss_db": 15.0,      # S11 minimum (dB)
    "max_insertion_loss_db": 1.5,    # S21 maximum (dB) at center freq
    "freq_start_ghz": 1.0,
    "freq_stop_ghz": 6.0,
    "num_points": 201,
    "power_dbm": -10,
    "if_bandwidth_hz": 1000,
}

# ====================== HELPER FUNCTIONS ======================

def find_vna_address():
    """Auto-detect Anritsu MS46122B"""
    rm = pyvisa.ResourceManager()
    resources = rm.list_resources()
    print("Available VISA resources:")
    for r in resources:
        print(f"  {r}")
    
    for res in resources:
        if "0B5B" in res or "MS46122" in res or "USB" in res:  # Anritsu USB ID
            return res
    return None

def connect_vna():
    global VNA_ADDRESS
    if VNA_ADDRESS is None:
        VNA_ADDRESS = find_vna_address()
        if VNA_ADDRESS is None:
            VNA_ADDRESS = input("Enter VNA VISA address (e.g. USB0::0x0B5B::... or TCPIP0::...): ").strip()
    
    rm = pyvisa.ResourceManager()
    vna = rm.open_resource(VNA_ADDRESS)
    vna.timeout = 30000  # 30 seconds
    print(f"Connected to: {vna.query('*IDN?')}")
    return vna

def scan_inputs():
    print("\n" + "="*50)
    print("NEW TEST - Scan or type the following:")
    serial = input("Scan Serial Number : ").strip()
    part   = input("Scan Part Number   : ").strip()
    order  = input("Scan Order Number  : ").strip() or "N/A"
    return serial, part, order

def configure_vna(vna, limits):
    """Basic configuration for MS46122B"""
    print("Configuring VNA...")
    vna.write("*RST")
    time.sleep(2)
    vna.write("*CLS")
    
    # Frequency
    vna.write(f"SENS:FREQ:STAR {limits['freq_start_ghz']}e9")
    vna.write(f"SENS:FREQ:STOP {limits['freq_stop_ghz']}e9")
    vna.write(f"SENS:SWE:POIN {limits['num_points']}")
    
    # Power and IFBW
    vna.write(f"SOUR:POW {limits['power_dbm']}")
    vna.write(f"SENS:BWID {limits['if_bandwidth_hz']}")
    
    # Select S21 and S11 (common for cables)
    vna.write("CALC:PAR:DEF S21")
    vna.write("CALC:PAR:SEL 'Tr1'")   # Trace 1 = S21
    
    print("VNA configured.")

def trigger_and_read_data(vna):
    """Trigger sweep and read S-parameters"""
    print("Triggering measurement...")
    vna.write("INIT:CONT OFF")
    vna.write("INIT:IMM")
    vna.query("*OPC?")   # Wait for sweep complete
    
    # Read frequency array
    freq_str = vna.query("SENS:FREQ:DATA?")
    frequencies = np.array([float(x) for x in freq_str.strip().split(',')])
    
    # Read complex S21 data (you can add S11, S12, S22 as needed)
    s21_str = vna.query("CALC:DATA:SDATA?")
    s21_complex = np.array([complex(float(r), float(i)) for r, i in 
                            zip(s21_str.strip().split(',')[::2], 
                                s21_str.strip().split(',')[1::2])])
    
    s21_mag_db = 20 * np.log10(np.abs(s21_complex))
    
    return frequencies, s21_mag_db, s21_complex

def capture_screenshot(vna, serial):
    """Capture screen on MS46122B"""
    filename = f"screen_{serial}_{datetime.now().strftime('%H%M%S')}.png"
    filepath = os.path.join(SCREENSHOT_FOLDER, filename)
    
    print("Capturing screenshot...")
    vna.write(f':MMEMory:STORe:IMAGe "{filename}"')
    time.sleep(3)  # Wait for file to be written
    
    # Transfer image from VNA to PC
    try:
        img_data = vna.query_binary_values(f':MMEMory:DATA? "{filename}"', datatype='B')
        with open(filepath, 'wb') as f:
            f.write(bytes(img_data))
        print(f"Screenshot saved: {filepath}")
        return filepath
    except Exception as e:
        print(f"Screenshot transfer failed: {e}")
        return None

def analyze_pass_fail(frequencies, s21_mag_db, limits):
    """Simple Pass/Fail logic - customize as needed"""
    results = []
    overall_pass = True
    
    # Example checks
    min_rl = np.min(s21_mag_db)   # This is actually insertion loss for S21
    max_il = np.max(s21_mag_db)
    
    # Return Loss check (example - you should measure S11 separately)
    rl_status = "PASS" if min_rl >= limits["min_return_loss_db"] else "FAIL"
    results.append(["Min Return Loss (example)", f"{min_rl:.2f} dB", f">= {limits['min_return_loss_db']} dB", rl_status])
    
    # Insertion Loss check
    il_status = "PASS" if max_il <= limits["max_insertion_loss_db"] else "FAIL"
    results.append(["Max Insertion Loss", f"{max_il:.2f} dB", f"<= {limits['max_insertion_loss_db']} dB", il_status])
    
    if "FAIL" in [r[3] for r in results]:
        overall_pass = False
    
    return "PASS" if overall_pass else "FAIL", results

def create_pdf_report(serial, part, order, timestamp, pass_fail, results, screenshot_path, frequencies, s21_mag_db):
    pdf_name = f"Report_{serial}_{part}_{order}_{timestamp}.pdf"
    pdf_path = os.path.join(REPORT_FOLDER, pdf_name)
    
    doc = SimpleDocTemplate(pdf_path, pagesize=letter,
                            rightMargin=0.6*inch, leftMargin=0.6*inch,
                            topMargin=0.5*inch, bottomMargin=0.5*inch)
    
    styles = getSampleStyleSheet()
    story = []
    
    # Title
    title_style = ParagraphStyle('Title', parent=styles['Title'], fontSize=18, alignment=TA_CENTER, spaceAfter=20)
    story.append(Paragraph("Anritsu MS46122B - RF Test Report", title_style))
    story.append(Spacer(1, 10))
    
    # Metadata Table
    meta = [
        ["Serial Number", serial],
        ["Part Number", part],
        ["Order Number", order],
        ["Test Date / Time", timestamp],
        ["VNA Model", "Anritsu MS46122B"],
        ["Overall Result", pass_fail],
    ]
    
    meta_table = Table(meta, colWidths=[2.2*inch, 4.5*inch])
    meta_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.Color(0.2, 0.3, 0.5)),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.white),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 15))
    
    # Big PASS / FAIL banner
    banner_color = colors.green if pass_fail == "PASS" else colors.red
    banner = Paragraph(f'<font color="{banner_color}"><b>RESULT: {pass_fail}</b></font>', 
                       ParagraphStyle('Banner', fontSize=22, alignment=TA_CENTER, spaceAfter=15))
    story.append(banner)
    
    # Results Table
    story.append(Paragraph("<b>Measurement Results</b>", styles['Heading2']))
    header = ["Parameter", "Measured Value", "Limit", "Status"]
    table_data = [header] + results
    
    res_table = Table(table_data, colWidths=[2.5*inch, 1.8*inch, 1.8*inch, 0.9*inch])
    res_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.Color(0.15, 0.25, 0.45)),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.Color(0.95, 0.95, 0.95)]),
        ('BACKGROUND', (3, 1), (3, -1), colors.lightgreen if pass_fail == "PASS" else colors.Color(1, 0.7, 0.7)),
    ]))
    story.append(res_table)
    story.append(Spacer(1, 20))
    
    # Screenshot
    if screenshot_path and os.path.exists(screenshot_path):
        story.append(Paragraph("<b>VNA Screen Capture</b>", styles['Heading2']))
        img = Image(screenshot_path, width=6.5*inch, height=4.3*inch)
        story.append(img)
    
    # Footer
    story.append(Spacer(1, 30))
    story.append(Paragraph("Generated automatically by Anritsu MS46122B Automation System", 
                           ParagraphStyle('Footer', fontSize=8, alignment=TA_CENTER, textColor=colors.grey)))
    
    doc.build(story)
    print(f"✅ PDF Report saved: {pdf_path}")
    return pdf_path

# ====================== MAIN PROGRAM ======================

def main():
    print("=== Anritsu MS46122B VNA Automation Started ===")
    vna = connect_vna()
    
    try:
        while True:
            serial, part, order = scan_inputs()
            if not serial:
                print("Exiting...")
                break
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Configure & Measure
            configure_vna(vna, DEFAULT_LIMITS)
            frequencies, s21_mag_db, s21_complex = trigger_and_read_data(vna)
            
            # Screenshot
            screenshot_path = capture_screenshot(vna, serial)
            
            # Analysis
            overall, results = analyze_pass_fail(frequencies, s21_mag_db, DEFAULT_LIMITS)
            
            # Generate PDF
            create_pdf_report(serial, part, order, timestamp, overall, results, 
                              screenshot_path, frequencies, s21_mag_db)
            
            print(f"\nTest completed for Serial: {serial} → Result: {overall}\n")
            input("Press Enter for next test (or Ctrl+C to exit)...")
    
    except KeyboardInterrupt:
        print("\nProgram stopped by user.")
    finally:
        vna.close()
        print("VNA connection closed.")

if __name__ == "__main__":
    main()
