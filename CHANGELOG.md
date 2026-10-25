# Changelog

All notable changes to Parallax Studio. Newest first.

## [Unreleased]

## [0.10.1] - 2026-10-25

### Fixed

- The Linux RPM of 0.10.0 did not start: it could not load numpy. Packaging stripped every bundled library, and the older strip on the build machine left two empty segments in numpy's OpenBLAS at file offsets that are not page-aligned, which newer systems refuse to load. The RPM now ships the libraries exactly as built, and the build fails if any of them change. The DEB, the tarball, Windows and macOS were not affected.

## [0.10.0] - 2026-10-25

### Added

- **Portrait**, an idle loop for a picture of one person. The face is found and the head and hair move as one rigid piece, a slow tilt and nod that never stretches the face, while the body turns in depth around the head, the hips sway and the chest lifts with each breath.
- **Flaunt**: the hips swing side to side while the shoulders lean the other way, the raised hip tips up and the head tilts toward it.
- **Bounce**: a bounce on the spot with the feet on the ground. The body rises and falls, the legs bend instead of lifting off, and the chest follows a beat behind and travels further.
- In Portrait, Flaunt and Bounce the background stays still, both for cut-outs with transparency and for full scenes, where the person is found by segmentation.
- In those three motions Erase holds any area still while the rest moves, and Paint lets it move again. The overlay shows what moves in red and what is held in blue. Undo, redo and saved projects keep it.
- macOS Apple Silicon builds, as a disk image and a zip.
- A labelled frame-rate control (24, 30 or 60 fps) beside the preview.

### Changed

- Controls a motion does not use are dimmed while it is on, with a tooltip saying why, instead of sitting there doing nothing.
- The first-run model download asks only for what the app uses: the default depth model, the person segmentation model and MoveNet Thunder, about 75 MB.

### Removed

- **Body Relief**, and its Settings page. It pinned the face and background still with edges only a couple of pixels wide right beside moving parts, so the picture tore along those outlines on almost every photo. Portrait, Flaunt and Bounce cover people without tearing.

### Fixed

- Model downloads failed on systems that keep their certificates somewhere other than where the build machine did: a packaged build carries its own SSL library, which then found no certificate store and rejected every connection before it started. The app now ships its own certificate bundle.
- A failed model download no longer looks like a button that did nothing. The panel says it is connecting while a download opens, and the error stays on screen instead of being cleared in the same moment it was shown.
- The Windows installer job found NSIS in the wrong place, and the macOS build now has an app icon.

## [0.9.8] - 2026-08-03

First public release.
