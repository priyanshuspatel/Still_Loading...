# Still Loading... Web Application

The official web experience for **Still Loading...** ([stillloading.tech](https://stillloading.tech)).

Transforms invisible digital waiting (MacBook battery charging state and Chrome download percentages) into tangible, beautiful light on an 8-column × 13-row LED matrix.

## Features

- **8×13 LED Matrix Twin:** 104 blue LEDs with 3-bit grayscale (brightness 0..7), custom 3×5 typography, breathing hearts, stall warning frames, and completion bars.
- **MacBook Battery Telemetry:** Real-time percentage, charging state (AC MagSafe / Discharging / Full), battery health, and clamshell sleep notices.
- **Chrome Download Monitor:** Instantaneous progress percentage, downloaded/total bytes, transfer speeds, and auto-priority display switching.
- **Dual Operating Modes:**
  - **Demo Mode:** Fully deterministic, rich scenarios for evaluators and judges without physical hardware.
  - **Live Mode:** Connects to live read-only telemetry bridge with honest connectivity reporting.
- **Clean Architecture:** Strict separation between client-side read-only presentation and private hardware control.

## Technology Stack

- **Framework:** React 18 + TypeScript + Vite
- **Styling:** Tailwind CSS + PostCSS
- **Icons:** Lucide Icons
- **Typography:** Inter + JetBrains Mono

## Getting Started

### Install Dependencies
```bash
cd web
npm install
```

### Run Locally in Development Mode
```bash
npm run dev
```
Open `http://localhost:5173` in your browser.

### Build Production Bundle
```bash
npm run build
```
Generates optimized static assets in `web/dist/`.

### Preview Production Build
```bash
npm run preview
```

## Matrix Math and Frame Alignment

The digital matrix twin directly mirrors `shared/matrix_display.py` and `uno-q/sketch/sketch.ino`:
- Columns: 13 (index 0..12)
- Rows: 8 (index 0..7)
- Total Pixels: 104 LEDs
- Grayscale: 3-bit depth (0 = OFF, 1 = dimmest, 7 = full white-blue halo)
- 100% Representation: '100' digits (cols 1..11 on rows 1..5) plus full 13-pixel row 7 completion bar.
