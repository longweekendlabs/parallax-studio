# Parallax Studio

**Turn a still image into a looping 2.5D parallax animation. Entirely on your own machine.**

[![GitHub Release](https://img.shields.io/github/v/release/longweekendlabs/parallax-studio?style=flat-square)](https://github.com/longweekendlabs/parallax-studio/releases/latest)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg?style=flat-square)](LICENSE)
[![Platform: Linux + macOS](https://img.shields.io/badge/Platform-Linux%20%2B%20macOS-lightgrey?style=flat-square)](#platform-support)
[![Offline: no cloud APIs](https://img.shields.io/badge/AI-runs%20offline-2ea44f?style=flat-square)](#depth-without-painting)

Parallax Studio is for visual novel art, scene illustrations, character cutouts, and any workflow where you want motion out of still layers without opening a compositing suite.

Every model it uses runs locally. Nothing is uploaded, and there are no API keys or accounts.

![Parallax Studio preview](docs/assets/parallax-studio-ui.png)

---

## Features

- **Paint depth by hand** — Brush with size, hardness, strength and depth value, over a colour-ramped overlay that shows what you have painted.
- **Import multiple layers** — PNG, JPG, JPEG and WebP, moved and scaled directly on the canvas.
- **Live preview** — Plays at 24, 30 or 60 fps, and reports the rate it is really achieving so the preview can be trusted against the export.
- **Export** — MP4 or GIF, with optional NVIDIA GPU rendering and NVENC encoding when the hardware is present.
- **Projects** — `.parlx` files keep layer order, transforms, motion settings and depth data.

## Depth without painting

Two buttons generate depth, both from models downloaded on first use and cached afterwards.

**Auto Depth** runs Depth Anything V2 and separates a subject from its background properly. The result is feathered at depth discontinuities: a hard silhouette does not stretch under displacement, it tears, and the sampling grid folds back over itself along the outline.

**Body Relief** is for photographs of people. It finds every figure and its pose, then rebuilds the depth *inside* each one so chest, waist, hips, arms and legs each carry their own parallax instead of the figure sliding as a single cutout. It touches the subject only: backgrounds and faces come out bit-for-bit identical to Auto Depth. Strength and pose model are in Settings.

| Model | Size | Licence | Used for |
|---|---|---|---|
| Depth Anything V2 Small | 50 MB | Apache-2.0 | Auto Depth |
| MediaPipe Selfie Segmentation | 0.5 MB | Apache-2.0 | finding the subject |
| MoveNet MultiPose | 19 MB | Apache-2.0 | up to 6 figures, default |
| MoveNet Thunder / Lightning | 25 / 9 MB | Apache-2.0 | single figure, optional |

## Platform Support

| Platform | Status |
|---|---|
| **Linux x86_64** | Supported. RPM and portable tarball built by `build_rpm.sh` / `build_linux.sh`. |
| **macOS Apple Silicon** | Supported. `.app` and `.dmg` built by `build_macos.sh`, macOS 12+. |
| **Windows** | Not built yet. It runs from source; there is no packaged installer. |

Built with:
- Python 3.11-3.13
- PySide6 (Qt)
- NumPy & OpenCV
- ONNX Runtime, for the depth and pose models
- imageio & Pillow

## Download

Head to the **[Releases page](https://github.com/longweekendlabs/parallax-studio/releases/latest)**.

| Platform | Package | Notes |
|---|---|---|
| **Linux x86_64** | `.rpm` / `.tar.gz` | Built with `build_rpm.sh` and `build_linux.sh`. |
| **macOS Apple Silicon** | `.dmg` / `.app` | macOS 12+ required. |
| **Windows** | run from source | See Quick Start below. |

The AI models are not bundled. They download on first use of Auto Depth or Body Relief and are kept on your machine afterwards.

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

To build a Linux RPM:

```bash
chmod +x build_rpm.sh
./build_rpm.sh
```

The RPM lands in `dist/rpm/`. Install it with `sudo rpm -Uvh dist/rpm/parallax-studio-*.rpm`.

To build a standalone macOS app bundle and disk image:

```bash
chmod +x build_macos.sh
./build_macos.sh
```

The output will be located in `dist/Parallax Studio.app` and `dist/Parallax Studio.dmg`.

To build a standalone Linux app directory:

```bash
chmod +x build_linux.sh
./build_linux.sh
```

The output will be located in `dist/parallax-studio/`. Run it with:

```bash
./dist/parallax-studio/parallax-studio
```

If your distro's default `python3` is newer than the pinned dependency set supports, install Python 3.11 or 3.12 and run:

```bash
PYTHON_BIN=python3.11 ./build_linux.sh
```

## Project Format

`.parlx` is a JSON project file that stores layer order, source paths, transforms, motion settings, and compressed depth maps. Source images are referenced by path to keep project files lightweight.

## License

MIT License. See [LICENSE](LICENSE) for details.

---

Made with ♥ by **[Long Weekend Labs](https://github.com/longweekendlabs)**
