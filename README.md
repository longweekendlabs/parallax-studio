# Parallax Studio

**Turn layered artwork into looping 2.5D parallax animations — locally on macOS.**

[![GitHub Release](https://img.shields.io/github/v/release/longweekendlabs/parallax-studio?style=flat-square)](https://github.com/longweekendlabs/parallax-studio/releases/latest)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg?style=flat-square)](LICENSE)
[![Platform: macOS](https://img.shields.io/badge/Platform-macOS-lightgrey?style=flat-square)](#macos-apple-silicon-only)

Parallax Studio is designed for visual novel art, scene illustrations, character cutouts, and any workflow where you want motion from static layers without moving into a full compositing suite.

![Parallax Studio preview](docs/assets/parallax-studio-ui.png)

---

## Features

- **Import multiple layers** — Support for PNG, JPG, JPEG, and WebP files.
- **Paint depth maps** — Built-in depth map editor with brush size, hardness, opacity, and depth value controls.
- **Canvas transforms** — Move and scale layers directly on the canvas.
- **Live preview** — View motion animations live at 24 fps.
- **High-quality export** — Export your animations to MP4 or GIF.
- **Project management** — Save projects as `.parlx` files that keep layer order, settings, and depth data.

## MacOS Apple Silicon Only

This project targets **macOS Apple Silicon** (M1/M2/M3/M4) first and foremost. It utilizes platform-specific optimizations for smooth performance.

Built with:
- Python 3.11+
- PySide6 (Qt)
- NumPy & OpenCV
- imageio & Pillow

## Download

Head to the **[Releases page](https://github.com/longweekendlabs/parallax-studio/releases/latest)** to grab the latest `.dmg` for your Mac.

| Platform | Package | Notes |
|---|---|---|
| **macOS Apple Silicon** | `.dmg` / `.app` | macOS 12+ required. |

## Quick Start

```bash
# Clone the repository
git clone https://github.com/longweekendlabs/parallax-studio.git
cd parallax-studio

# Setup virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies and run
pip install -r requirements.txt
python main.py
```

## Building Locally

To build a standalone macOS app bundle and disk image:

```bash
chmod +x build_macos.sh
./build_macos.sh
```

The output will be located in `dist/Parallax Studio.app` and `dist/Parallax Studio.dmg`.

## Project Format

`.parlx` is a JSON project file that stores layer order, source paths, transforms, motion settings, and compressed depth maps. Source images are referenced by path to keep project files lightweight.

## License

MIT License. See [LICENSE](LICENSE) for details.

---

Made with ♥ by **[Long Weekend Labs](https://github.com/longweekendlabs)**
