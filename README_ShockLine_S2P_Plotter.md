# Anritsu ShockLine S2P Advanced Plotter

A Python GUI for plotting Anritsu ShockLine MS46122B / Touchstone `.s2p` files.

## What it reproduces

The application is designed around the 4-trace screen shown in the supplied Anritsu screenshot:

1. **Tr1 – S11 Return Loss / Log Magnitude**
2. **Tr2 – S22 Return Loss / Log Magnitude**
3. **Tr3 – S21 Transmission / Insertion Loss**
4. **Tr4 – S11 Smith Chart**

It also provides frequency markers similar to the VNA marker readout.

## S2P format supported

The parser supports Touchstone 2-port data in:

- RI = Real / Imaginary
- MA = Magnitude / Angle
- DB = dB / Angle

It supports frequency units:

- Hz
- kHz
- MHz
- GHz

It uses the standard Touchstone 2-port order:

`S11, S21, S12, S22`

This matches the Anritsu export shown in the supplied spreadsheet:

`FREQ, S11RE, S11IM, S21RE, S21IM, S12RE, S12IM, S22RE, S22IM`

## Install

Python 3.10+ is recommended.

```bash
pip install numpy matplotlib
```

Tkinter is normally included with Python on Windows.

## Run

```bash
python shockline_s2p_plotter.py
```

## Marker workflow

Enter any of these:

- `1.723 GHz`
- `1723 MHz`
- `1723000000 Hz`

or simply enter `1.723` because the GUI treats a unit-less marker as GHz.

You can also **click directly on the rectangular graph** to place a marker.

Each marker reports:

- Frequency
- S11 dB
- S22 dB
- S21 dB
- S11 VSWR
- S11 magnitude
- S11 phase

The marker can use either interpolation between sweep points or the nearest measured sweep point.

## Test limits

Default values are based on the supplied screenshot:

- S11 = -26 dB
- S22 = -26 dB
- S21 = -0.44 dB

These are editable.

## Export

- PNG
- PDF
- SVG
- Marker CSV

The marker CSV contains complex S11 values, magnitude, phase, VSWR, S22 and S21 values.

## Important RF note

The S11/S22 plots are **20 log10(|S|)**, which is the normal logarithmic magnitude display in dB.

For a conventional "return loss" value reported as a positive number, use:

`Return Loss = -20 log10(|S11|)`

The Anritsu screenshot uses a negative dB display, so this application intentionally follows that display convention.

## Next upgrades

This prototype is deliberately structured so the following can be added without changing the S2P parser:

- Touchstone file comparison (DUT A vs DUT B)
- Pass/fail result per marker
- Limit masks over arbitrary frequency ranges
- Automatic marker search for max/min S11/S22/S21
- Band-specific marker presets
- Measurement report generator
- Excel export
- SCPI live connection to MS46122B
- Automatic capture from the VNA
- Multiple S2P overlays
- Trace colors and user-defined units
