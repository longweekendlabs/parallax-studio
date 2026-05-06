# Parallax Studio — ROADMAP
**Long Weekend Labs | Target: macOS Apple Silicon first**

Agent legend: [CLAUDE CODE] [CODEX] [GEMINI] [COPILOT] [EMRE]

---

## Current State

Specced and visually directed. Original Windows-first plan has been replaced.

New direction:

- Build only for **macOS Apple Silicon** first.
- Use the MacBook Neo as the primary dev/test machine.
- Forget Windows and Linux until the Apple Silicon version proves the workflow.
- Binding design concept is now included inside `PROJECT.md` under **Visual Design (BINDING)**.
- Phase 0 must build the visual shell before any real business logic.

---

## Phase 0 — Visual Shell

**Goal:** Make the app visually match the approved concept before building real functionality.

**Scope:** Look only. No real image processing, no real project files, no real export, no AI model wiring.

**Gate:** Emre runs the shell on the MacBook Neo, takes a screenshot, compares it to `~/AI/scratch/parallax-studio/concept.png`, and explicitly approves it in chat.

Phase 1 is blocked until this gate is passed.

- [ ] [EMRE] Save the generated concept image as `~/AI/scratch/parallax-studio/concept.png`
- [x] [CLAUDE CODE] Create project folder structure from `PROJECT.md`
- [x] [CLAUDE CODE] Create minimal runnable PySide6/PyQt6 app shell
- [x] [CLAUDE CODE] Implement `theme.py` with the binding Darkroom Motion Studio palette
- [x] [CLAUDE CODE] Implement `main_window.py` with five-zone layout: top bar, left layers, center preview, right controls, bottom loop strip
- [x] [CLAUDE CODE] Implement `layer_panel.py` with hardcoded dummy layer cards: Foreground, Character, Background
- [x] [CLAUDE CODE] Implement selected layer styling with cyan border/glow, not native Qt blue selection
- [x] [CLAUDE CODE] Implement `canvas.py` visual shell: dark stage, checkerboard area, preview frame, floating status pills
- [x] [CLAUDE CODE] Implement `controls.py` visual shell: Depth Brush and Motion cards, sliders, dropdowns, buttons
- [x] [CLAUDE CODE] Implement `timeline.py` visual shell: play/pause, duration, scrub marker, speed slider, Bounce/Seamless toggles
- [x] [CLAUDE CODE] Add placeholder artwork/gradient blocks only if no sample images exist; do not block shell on real assets
- [ ] [EMRE] Run app locally on MacBook Neo
- [ ] [EMRE] Screenshot app shell and compare against concept
- [ ] [EMRE] Approve Phase 0 or request visual fixes

### Phase 0 Acceptance Criteria

- App opens on macOS Apple Silicon.
- It resembles the approved concept at a glance.
- Center canvas dominates the window.
- Left layer cards do not look like default QListWidget text rows.
- Right controls do not look like default office form widgets.
- Bottom loop strip exists.
- Export button is amber and visually primary.
- Accent colors match the binding palette.
- No real feature work has polluted the shell.

---

## Phase 1 — Local App Skeleton and Project Plumbing

**Blocked until Phase 0 approved.**

Goal: turn the visual shell into a clean local app foundation without yet building full image editing.

- [ ] [CLAUDE CODE] Decide final UI binding: PySide6 preferred unless concrete blocker appears
- [ ] [GEMINI] Create `requirements.txt` with minimal pinned dependencies for macOS Apple Silicon
- [ ] [CLAUDE CODE] Add macOS app paths helper: `~/Library/Application Support/Parallax Studio/`
- [ ] [CLAUDE CODE] Add app settings load/save skeleton
- [ ] [CLAUDE CODE] Add menu/command actions for New, Open, Save, Save As, Export but keep them mostly stubbed
- [ ] [CODEX] Add drag/drop file detection into canvas or layer panel
- [ ] [CLAUDE CODE] Add clean error/status message system
- [ ] [EMRE] Confirm the app launches repeatedly without terminal errors

---

## Phase 2 — Layer System

Goal: real imported image layers, displayed statically.

- [ ] [CLAUDE CODE] Implement `layer.py` data model: source path, image data, name, visibility, opacity, intensity, depth map placeholder
- [ ] [CLAUDE CODE] Add image import through file picker
- [ ] [CODEX] Add drag/drop image import
- [ ] [CLAUDE CODE] Show real layer thumbnails in layer panel
- [ ] [CLAUDE CODE] Add layer select/remove/duplicate/rename
- [ ] [CLAUDE CODE] Add visibility toggle
- [ ] [CLAUDE CODE] Add reorder support
- [ ] [CODEX] Implement static alpha compositing bottom-to-top
- [ ] [CLAUDE CODE] Display static composite in center canvas
- [ ] [EMRE] Test with three layers: background, character, foreground

### Phase 2 Acceptance Criteria

- Three real images can be imported.
- Layers appear in the left panel with thumbnails.
- User can reorder layers.
- Visibility changes affect the preview.
- Composite preview looks correct and does not crash with transparent PNGs.

---

## Phase 3 — Depth Painting

Goal: manual depth painting works without AI.

- [ ] [CLAUDE CODE] Add paint mode for selected layer
- [ ] [CODEX] Implement brush engine: size, hardness, opacity, depth value
- [ ] [CODEX] Implement per-layer depth map as NumPy float array
- [ ] [CLAUDE CODE] Render semi-transparent depth overlay on selected layer
- [ ] [CODEX] Add undo/redo stack, 20 steps per layer
- [ ] [CODEX] Add clear depth to flat mid-grey
- [ ] [CODEX] Add invert depth
- [ ] [CODEX] Add blur depth
- [ ] [CLAUDE CODE] Wire brush sliders to real paint behavior
- [ ] [EMRE] Paint depth on character PNG and confirm it feels usable

### Phase 3 Acceptance Criteria

- User can paint on selected layer.
- Overlay is readable.
- Brush does not feel laggy on MacBook Neo.
- Undo/redo works.
- Clear/invert/blur work.
- Manual workflow is useful even without AI depth.

---

## Phase 4 — Animation Engine

Goal: convert layers + depth maps into live parallax motion.

- [ ] [CODEX] Implement `animator.py` displacement function using NumPy/OpenCV remap
- [ ] [CODEX] Implement motion path generators: Gentle Float, Horizontal Drift, Vertical Drift, Zoom Breathe, Parallax Orbit
- [ ] [CLAUDE CODE] Implement `compositor.py` per-frame layer displacement and alpha composite
- [ ] [CLAUDE CODE] Wire preview timer at target 24fps
- [ ] [CLAUDE CODE] Wire Layer Intensity and Global Intensity controls
- [ ] [CLAUDE CODE] Wire speed/duration controls
- [ ] [CLAUDE CODE] Wire Bounce / Seamless loop behavior
- [ ] [EMRE] Test all motion styles on a three-layer scene

### Phase 4 Acceptance Criteria

- Preview animates.
- Motion loops cleanly.
- Intensity controls visibly change movement.
- At least Gentle Float and Parallax Orbit feel natural.
- Performance is acceptable on Apple Silicon.

---

## Phase 5 — Project Save/Load

Goal: projects survive close/reopen.

- [ ] [GEMINI] Implement `.parlx` serializer/deserializer in `project.py`
- [ ] [CLAUDE CODE] Save layer order, source paths, visibility, opacity, intensity, depth maps, motion settings
- [ ] [CLAUDE CODE] Add New/Open/Save/Save As actions
- [ ] [CLAUDE CODE] Add recent projects list on launch
- [ ] [CODEX] Add missing-source placeholder handling
- [ ] [EMRE] Save a project, close app, reopen, verify project restores correctly

### Phase 5 Acceptance Criteria

- Project can be saved.
- Project can be reopened.
- Depth maps survive round-trip.
- Missing image paths do not crash the app.

---

## Phase 6 — Export

Goal: produce usable MP4 and GIF loops.

- [ ] [CLAUDE CODE] Implement frame sequence render through compositor
- [ ] [CLAUDE CODE] Implement MP4 export through imageio + ffmpeg
- [ ] [CODEX] Implement GIF export through Pillow with reasonable palette optimization
- [ ] [CLAUDE CODE] Add export dialog: format, duration, FPS, resolution, output path
- [ ] [CLAUDE CODE] Add export progress bar and cancellation if practical
- [ ] [GEMINI] Document Homebrew ffmpeg dependency for dev if ffmpeg is not bundled yet
- [ ] [EMRE] Test MP4 in QuickTime/VLC
- [ ] [EMRE] Test GIF in browser

### Phase 6 Acceptance Criteria

- MP4 export works.
- GIF export works.
- Exported loop visually matches preview closely enough.
- App remains responsive or at least shows progress during export.

---

## Phase 7 — Optional AI Depth Generation

Goal: add local auto-depth as a helper, not a dependency.

This phase can move earlier only if manual depth and animation are already stable.

- [ ] [GEMINI] Investigate Apple Silicon-friendly local depth model options
- [ ] [GEMINI] Identify smallest practical model and runtime path
- [ ] [CLAUDE CODE] Implement `model_downloader.py` with progress and cancellation
- [ ] [CLAUDE CODE] Implement `depth_estimator.py`
- [ ] [CODEX] Add pre/post-processing: resize, normalize, restore layer dimensions
- [ ] [CLAUDE CODE] Wire Auto Depth button for selected layer only
- [ ] [CODEX] Add brightness/contrast adjustment for generated depth
- [ ] [EMRE] Compare generated depth on character art and background scene

### Phase 7 Acceptance Criteria

- Auto Depth runs locally or fails gracefully.
- It does not block manual workflow.
- Generated maps are editable.
- Model download is not forced on first launch.

---

## Phase 8 — Local macOS Packaging

Goal: create a usable local `.app` bundle for the MacBook Neo.

- [ ] [GEMINI] Create `build_macos.sh`
- [ ] [GEMINI] Package app with PyInstaller or chosen macOS packaging route
- [ ] [CLAUDE CODE] Ensure assets/icons/theme files are included in bundle
- [ ] [CLAUDE CODE] Ensure app support paths work from bundled app
- [ ] [GEMINI] Add optional DMG packaging only after `.app` works
- [ ] [EMRE] Launch app from Finder
- [ ] [EMRE] Confirm import/save/export work from bundled app

### Phase 8 Acceptance Criteria

- `dist/Parallax Studio.app` exists.
- App launches outside terminal.
- Core workflow works in bundled app.
- No Windows/Linux packaging work has been added yet.

---

## Phase 9 — Polish and v0.1.0

Goal: stabilize the Apple Silicon prototype into a clean first release.

- [ ] [CODEX] Polish status messages
- [ ] [CODEX] Polish empty states
- [ ] [CLAUDE CODE] Add unsaved changes indicator
- [ ] [CLAUDE CODE] Add keyboard shortcuts: New, Open, Save, Undo, Redo, Play/Pause
- [ ] [CODEX] Improve slider/value display consistency
- [ ] [CODEX] Fix visual spacing issues from Emre screenshot review
- [ ] [GEMINI] Write README only after app behavior is real
- [ ] [EMRE] Full smoke test on MacBook Neo
- [ ] [EMRE] Tag local milestone v0.1.0 when satisfied

---

## Future Phase — Windows Port

Do not start until Apple Silicon v0.1.0 is approved.

Potential Windows tasks later:

- Replace macOS paths with cross-platform appdirs helper.
- Test PySide6/PyQt6 rendering on Windows.
- Bundle ffmpeg in Windows build.
- Build Windows x86_64 `.exe`.
- Consider Windows ARM64 only after x86_64 works.
- Revisit AI depth acceleration on CUDA for NVIDIA machines.

---

## Decisions Log

| Decision | Reason |
|---|---|
| Apple Silicon first | Development and testing happen directly on MacBook Neo |
| Windows/Linux deferred | Avoid wasting time on packaging before product is proven |
| PySide6 preferred | Cleaner Qt licensing/story unless a blocker appears |
| Manual depth first | Product must remain useful without AI model setup |
| AI depth optional | Helpful accelerator, not the main workflow |
| No OpenGL/Metal in v1 unless needed | Avoid renderer complexity; start with NumPy/OpenCV |
| Visual shell before functionality | Prevent structurally-correct but ugly vibe-coded UI |
| Bottom loop strip required in Phase 0 | Makes the app feel like animation software from the start |
| `.parlx` stores source paths | Keeps project files small; missing files handled gracefully |
| No extra project docs | LWL standard is exactly PROJECT.md and ROADMAP.md |

---

## Agent Notes

- Use `[skip ci]` for docs/config commits.
- Do not push every tiny iteration to GitHub Actions.
- Do not create extra markdown files.
- Do not start Windows/Linux packaging.
- Do not implement AI depth before manual paint and preview are working unless explicitly instructed.
- Do not let Phase 1 begin until Emre approves the Phase 0 screenshot.
