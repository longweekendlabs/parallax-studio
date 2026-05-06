# Parallax Studio
**Long Weekend Labs | Status: Specced, ready for Phase 0**

---

## What It Is

Parallax Studio is a macOS Apple Silicon desktop tool that transforms static layered artwork into looping 2.5D parallax animations.

The user imports multiple image layers, paints or generates depth maps per layer, previews motion live, and exports a short GIF or MP4 loop.

The first version is built solely for Apple Silicon MacBooks so development and testing can happen directly on the MacBook Neo. Windows is deferred until the macOS version proves the workflow, UI, and animation engine are worth porting.

---

## Problem It Solves

Static character art, scene illustrations, and visual novel assets often feel flat. Existing options are either too complex, online-only, AI-only with poor manual control, or require proper 3D/compositing software.

Parallax Studio gives visual novel creators, AVN creators, and digital artists a focused local workflow:

1. Prepare cut-out assets, for example with LWL Batch Background Remover.
2. Import background, character, and foreground layers.
3. Paint or generate depth per layer.
4. Preview a subtle animated parallax loop.
5. Export GIF or MP4 for use in games, social posts, trailers, itch.io pages, or visual novel scenes.

The app is not intended to replace After Effects, Blender, DaVinci Resolve, or full compositing tools. It should do one job cleanly.

---

## MVP Scope

- macOS Apple Silicon app first.
- Import multiple PNG/JPG/WebP layers.
- Layer stack with thumbnails, visibility toggles, opacity, order, and per-layer intensity.
- Per-layer depth painting.
- Optional local AI depth generation per layer.
- Live animated preview.
- Motion controls: speed, intensity, motion style, loop type.
- Export as MP4 and GIF.
- Save/load `.parlx` project files.
- Recent projects list.

---

## Out of Scope for v1

- Windows builds.
- Linux builds.
- macOS Intel support.
- App Store release.
- Code signing / notarization beyond local developer testing.
- Background inpainting / edge fill.
- Audio sync.
- Batch processing.
- Cloud sync.
- Cloud AI APIs.
- Subscription features.
- Plugin system.
- Full keyframe timeline.

---

## Platform

### v1 Target

- **macOS Apple Silicon only**.
- Primary test machine: MacBook Neo.
- Distribution during development: local run and local app bundle.
- Release target: unsigned or ad-hoc signed `.app` / `.dmg` for personal testing first.

### Deferred

- Windows x86_64.
- Windows ARM64.
- Linux x86_64 / ARM64.
- macOS Intel.

Do not spend Phase 0–v1 effort on cross-platform packaging. Keep the code reasonably portable, but the product target is Apple Silicon first.

---

## Stack

- **Language:** Python 3.11+
- **UI:** PySide6 or PyQt6
- **Image processing:** NumPy + OpenCV
- **Export:** imageio + ffmpeg for MP4, Pillow for GIF
- **AI depth:** local depth model, optional, downloaded on first use
- **Packaging:** PyInstaller or briefcase-style `.app` bundle, decided after the working prototype

### Current UI Toolkit Decision

Use **PySide6 unless there is a concrete blocker**.

Reason: PySide6 is usually a cleaner fit for modern Qt apps and licensing simplicity. PyQt6 is acceptable only if an agent proves PySide6 causes a real blocker.

### AI Depth Decision

AI depth generation is optional, not the core workflow.

Manual depth painting must work first. Auto-depth is a helper button per layer, not a required step and not automatic on import.

For Apple Silicon, prefer a path that can run locally without CUDA. Agents may investigate Core ML / MPS-compatible options, but must not block the MVP on perfect model acceleration.

---

## Key Architecture Decisions

- **Layers are independent.** Each layer has its own source image, depth map, visibility, opacity, intensity, and name.
- **Depth map is painted first, generated second.** AI helps but does not define the product.
- **No OpenGL/Metal renderer in v1 unless absolutely necessary.** Start with NumPy/OpenCV displacement. Revisit only if preview performance is unacceptable on Apple Silicon.
- **Preview is always live.** Changes to motion and depth should be visible quickly.
- **Project format is `.parlx`.** JSON envelope storing layer order, source paths, settings, and depth maps.
- **Source image files are referenced, not embedded.** If files move, the app shows missing-layer placeholders but does not crash.
- **ffmpeg should be bundled eventually.** For dev phase, Homebrew ffmpeg is acceptable.
- **Settings stored under macOS Application Support.** Use `~/Library/Application Support/Parallax Studio/`.
- **Do not overbuild the timeline.** v1 needs loop preview and export duration, not full keyframe editing.

---

## Core Features

### Layer System

- Add layer through file picker.
- Drag/drop image files into the app.
- Remove layer.
- Duplicate layer.
- Reorder layers.
- Toggle visibility.
- Adjust opacity.
- Adjust per-layer parallax intensity.
- Rename layer.
- Show thumbnail, file type, and basic file size.

Layer order is bottom-to-top: background at bottom, foreground on top.

### Depth Painting

- Select a layer, then paint on its depth map.
- Brush controls:
  - Size
  - Depth value
  - Hardness
  - Opacity
- White/near means stronger foreground movement.
- Black/far means weaker background movement.
- Clear depth resets to flat mid-grey.
- Invert depth.
- Blur depth.
- Brightness/contrast adjustment for generated maps.
- Undo/redo: 20 steps per layer.
- Depth overlay visible as semi-transparent greyscale over the selected layer.

### AI Depth Generation

- Button: **Auto Depth**.
- Runs only on the selected layer.
- First use may prompt to download model.
- Generated depth can be edited with the same brush tools.
- If model setup is difficult on Apple Silicon, leave button disabled with a clear “coming later” state until manual workflow is complete.

### Animation Controls

- Motion style:
  - Gentle Float
  - Horizontal Drift
  - Vertical Drift
  - Zoom Breathe
  - Parallax Orbit
- Loop type:
  - Seamless
  - Bounce
- Speed / loop duration.
- Global intensity.
- Per-layer intensity.
- Preview FPS target: 24fps.

### Export

- Format:
  - MP4
  - GIF
- Resolution:
  - Original
  - 75%
  - 50%
  - 25%
- FPS:
  - 15
  - 24
  - 30
- Duration:
  - 2–30 seconds
- Output folder remembered between sessions.
- Export progress visible.

### Project Save/Load

- `.parlx` file contains:
  - project version
  - layer order
  - image source paths
  - visibility
  - opacity
  - intensity
  - depth maps
  - motion settings
  - export defaults
- Recent projects shown on launch.
- Missing image paths should show placeholders and warnings, not crashes.

---

## Visual Design (BINDING)

### Design Name

**Darkroom Motion Studio**

### Reference Image

`~/AI/scratch/parallax-studio/concept.png`

The current approved concept direction is the generated dark Parallax Studio interface mockup: three-panel editor, large cinematic center canvas, left layer cards, right depth/motion controls, and bottom loop strip.

If the generated image is used as the binding concept, save it exactly here before Phase 0 starts:

```bash
mkdir -p ~/AI/scratch/parallax-studio
# save concept image as:
# ~/AI/scratch/parallax-studio/concept.png
```

### Visual Goal

Parallax Studio should feel like a focused animation darkroom for visual creators.

It must not look like:

- a boring office utility,
- a generic Python desktop demo,
- a SaaS dashboard,
- a random vibe-coded prototype,
- or a fake heavyweight professional suite.

The target is a small, polished, dark creator tool that clearly serves one workflow: import layers, paint depth, preview motion, export loop.

### Overall Layout

Use a five-part editor layout:

1. Compact top command bar.
2. Left layer stack.
3. Large central live preview stage.
4. Right depth and motion controls.
5. Thin bottom loop/timeline strip.

The center preview must dominate the app. If the canvas feels secondary, the design fails.

Recommended initial window size: around **1280×820** minimum.

### Wireframe

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│  Parallax Studio        New  Open  Save        Preview: 24fps     Export MP4 │
├───────────────┬──────────────────────────────────────────────┬───────────────┤
│ LAYERS        │                                              │ DEPTH BRUSH   │
│               │                                              │               │
│ + Add Layer   │              ┌──────────────────┐            │ Brush Size    │
│               │              │                  │            │ [────●────]   │
│ ┌───────────┐ │              │                  │            │ Depth Value   │
│ │ Foreground│ │              │   LIVE PREVIEW   │            │ [──────●──]   │
│ │ visible   │ │              │                  │            │ Opacity       │
│ └───────────┘ │              │                  │            │ [───●─────]   │
│ ┌───────────┐ │              └──────────────────┘            │               │
│ │ Character │ │        Paint Overlay: ON     Zoom 78%        │ Auto Depth    │
│ │ selected  │ │                                              │ Clear Depth   │
│ └───────────┘ │                                              │ Invert        │
│ ┌───────────┐ │                                              ├───────────────┤
│ │ Background│ │                                              │ MOTION        │
│ │ visible   │ │                                              │ Style         │
│ └───────────┘ │                                              │ Gentle Float  │
│               │                                              │ Intensity     │
├───────────────┴──────────────────────────────────────────────┴───────────────┤
│ Loop  00:00 ━━━━━━━●━━━━━━━━  04.0s     Speed [──●────]   Bounce / Seamless │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Color Palette

Use the following palette unless the reference image is reworked and a new palette is explicitly approved.

| Purpose | Hex |
|---|---|
| Window background | `#0B1014` |
| Panel background | `#111820` |
| Raised panel | `#17212B` |
| Canvas surround | `#070A0D` |
| Canvas checker dark | `#1A222B` |
| Canvas checker light | `#222C36` |
| Primary accent | `#3DD9C9` |
| Primary accent hover | `#63F2E5` |
| Export accent | `#F2B35E` |
| Danger / remove | `#E05D5D` |
| Main text | `#E7EEF2` |
| Secondary text | `#91A1AD` |
| Muted text | `#5F6F7B` |
| Border | `#24313C` |
| Soft border | `#1B2731` |

Cyan/teal is for live preview, depth, motion, selection, and active states.

Amber is only for final/export actions.

Do not introduce random additional accent colors.

### Typography

Main UI:

```text
Inter, SF Pro Display, SF Pro Text, system-ui, sans-serif
```

Technical/status text:

```text
JetBrains Mono, SF Mono, Menlo, Consolas, monospace
```

Use mono only for FPS, duration, resolution, file paths, and status values.

### Top Command Bar

Top-left:

```text
Parallax Studio
```

Top-center actions:

```text
New    Open    Save
```

Top-right:

```text
Preview 24fps    Export MP4
```

The export button is warm amber and visually primary.

Do not add account buttons, cloud sync, marketplace, model selector, or unrelated navigation.

### Left Layer Panel

The layer panel should feel like stacked animation cells, not a plain file list.

Each layer row/card must include:

- thumbnail,
- layer name,
- visibility icon,
- drag handle,
- overflow/options icon,
- small status text,
- selected state.

Selected layer style:

- cyan border or left accent line,
- subtle glow,
- no native Qt blue highlight.

Layer cards should be custom widgets, not plain text rows.

### Center Preview Stage

The center stage is the soul of the app.

It must include:

- dark canvas surround,
- framed preview area,
- subtle checkerboard transparency background,
- rounded preview frame,
- soft inner shadow,
- floating status pills.

Required floating pills:

```text
Paint Overlay ON
Selected: Character
Zoom 78%
```

Optional status pills:

```text
24 FPS
Unsaved
CPU / Neural Engine / MPS mode
```

When no project is loaded, show an elegant empty state:

```text
Drop PNG layers here
or
Add your first layer
```

Secondary hint:

```text
Tip: background → character → foreground works best
```

Do not show a blank white canvas.

### Right Controls Panel

Split controls into two stacked cards:

1. **Depth Brush**
2. **Motion**

Depth Brush controls:

- Brush Size
- Depth Value
- Hardness
- Opacity
- Auto Depth
- Clear Depth
- Invert
- Blur

Motion controls:

- Motion Style
- Loop Type
- Layer Intensity
- Global Intensity
- Speed / Duration
- Preview FPS

Use human labels. Avoid math-heavy labels in the UI.

Use sliders for creative values. Do not use spinboxes unless a numeric field is genuinely needed.

### Bottom Loop Strip

The bottom loop strip is mandatory in Phase 0, even before real timeline logic exists.

It should show:

- play/pause,
- current time,
- duration,
- scrub marker,
- small filmstrip/preview strip if easy,
- speed slider,
- Bounce / Seamless toggles.

This makes the app read as animation software instead of a generic image utility.

### Widget Mapping

| Concept | Implementation |
|---|---|
| Layer stack | Custom QWidget rows inside QScrollArea or QListWidget with custom item widgets |
| Visibility | Eye / eye-off SVG toggle, not checkbox text |
| Layer order | Drag handle icon, not up/down text buttons |
| Canvas | Custom QWidget/QLabel preview area with dark stage frame and checkerboard background |
| Depth overlay | Semi-transparent grayscale overlay on selected layer |
| Brush controls | Horizontal sliders with value labels |
| Motion style | Styled combo box |
| Loop type | Segmented toggle or styled two-option control |
| Play/pause | Icon button |
| Export | Prominent amber button |
| Status | Bottom status bar plus small floating canvas pills |

### Anti-Patterns

Do not use:

- default PyQt/PySide grey widgets,
- native blue selected rows,
- Office-style ribbon,
- giant empty group boxes,
- spinboxes for creative controls,
- letter buttons where icons are needed,
- random gradients,
- bright saturated office blue,
- cloud/account/SaaS dashboard elements,
- modal windows for the core workflow,
- tiny canvas surrounded by oversized controls,
- inconsistent icon styles,
- default system font everywhere if Inter/SF can be used cleanly.

Use:

- custom Qt stylesheet,
- icon buttons with tooltips,
- compact cards,
- 1px soft borders,
- rounded controls,
- sliders with visible filled tracks,
- soft status pills,
- dark canvas-first composition,
- clear empty states.

---

## Suggested File Structure

```text
parallax-studio/
├── main.py
├── app/
│   ├── ui/
│   │   ├── main_window.py       # Main window, layout, top bar, panels
│   │   ├── layer_panel.py       # Layer list sidebar, thumbnails, order, visibility
│   │   ├── canvas.py            # Center preview + paint overlay
│   │   ├── controls.py          # Depth brush + motion controls
│   │   ├── timeline.py          # Bottom loop strip
│   │   └── theme.py             # QSS stylesheet, color constants
│   ├── core/
│   │   ├── layer.py             # Layer data model
│   │   ├── compositor.py        # Stack layers into composited frame
│   │   ├── animator.py          # Motion paths + displacement
│   │   ├── depth_estimator.py   # Optional local AI depth wrapper
│   │   ├── exporter.py          # GIF + MP4 export
│   │   └── project.py           # .parlx save/load
│   └── utils/
│       ├── paths.py             # macOS app support paths
│       ├── image_utils.py
│       └── model_downloader.py
├── assets/
│   ├── icons/                   # Monochrome SVGs, one icon set
│   └── fonts/                   # Optional bundled Inter fonts if licensing/files are handled locally
├── requirements.txt
├── build_macos.sh               # Local macOS app bundle build
├── CLAUDE.md
├── AGENTS.md
├── GEMINI.md
└── .github/
    └── copilot-instructions.md
```

Agent config files are infrastructure, not project docs.

Do not create `SPEC.md`, `TASKS.md`, `DEPLOYMENT.md`, `HANDOFF_CURRENT.md`, `DESIGN.md`, or `NOTES.md`.

---

## Dev Setup on MacBook Neo

```bash
git clone https://github.com/longweekendlabs/parallax-studio
cd parallax-studio
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
python main.py
```

If OpenCV, Qt, or ffmpeg dependencies become painful, document the exact Homebrew prerequisites in this section. Do not create a separate deployment document.

---

## Build & Deploy

### Development Build

Start with direct local run:

```bash
source .venv/bin/activate
python main.py
```

### Local App Bundle

Later, add:

```bash
./build_macos.sh
```

Expected output:

```text
dist/Parallax Studio.app
```

DMG packaging is optional after the app works.

### GitHub Actions

Do not set up CI in Phase 0 unless needed.

For early development, prefer local builds on the MacBook Neo.

If GitHub Actions is added later:

- use `[skip ci]` for docs/config commits,
- avoid burning Actions minutes for every tiny iteration,
- tag-based release only,
- Apple Silicon runner availability/cost must be checked before relying on hosted CI.

---

## First-Run Behavior

On first launch:

- show clean empty state,
- do not force model download,
- allow manual workflow without AI depth,
- show model download only when user clicks **Auto Depth**.

On first Auto Depth use:

- ask before downloading model,
- show model size,
- show progress,
- store under `~/Library/Application Support/Parallax Studio/models/`,
- allow cancellation,
- fail gracefully if model setup is unavailable.

---

## Definition of Done for v1

v1 is done when Emre can, on the MacBook Neo:

1. Open the app.
2. Import at least three layers.
3. Select a layer and paint depth.
4. Preview a smooth parallax loop.
5. Adjust motion style, speed, and intensity.
6. Export MP4.
7. Export GIF.
8. Save project.
9. Reopen project.
10. Confirm the app looks visually close to the approved concept.
