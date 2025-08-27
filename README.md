# img2vid-ffmpeg

A tiny CLI to stitch images into a video **in alphabetical order** using `ffmpeg`.  
It does **not** rely on `-pattern_type glob`; instead it builds a concat list internally, so it works even on ffmpeg builds without globbing support.  
Default output is **16 fps** and **high quality**.

---

## Features

- Alphabetical (case-insensitive) sorting of images
- Works with mixed extensions (jpg, jpeg, png, webp, bmp, tif, tiff)
- Uses ffmpeg concat demuxer with per-frame `duration = 1 / FPS`
- Duplicates the last frame in the concat list so the final duration is respected
- Ensures even dimensions for codec compatibility; optional target resolution with Lanczos scaling
- Sensible defaults: `libx264`, `CRF 16`, `preset slow`, `pix_fmt yuv420p`
- Optional lossless x264 (`CRF 0` + `yuv444p`), or `libx265`, or `prores_ks`
- Recursive folder scanning, custom extension filter, dry-run mode

---

## Requirements

- Python **3.8+**
- `ffmpeg` available on `PATH`  
  (or pass the path via `--ffmpeg`, e.g., `C:\ffmpeg\bin\ffmpeg.exe` on Windows)

---

## Installation

```bash
pip install .
```

> After installation, the CLI command `img2vid` will be available.

---

## Quick Start

```bash
# From your images folder
img2vid
```

This creates `output.mp4` at **16 fps** with high-quality defaults.

---

## Examples

```bash
# Choose input folder and output path
img2vid -i "C:\path\to\images" -o "C:\path\to\output.mp4"
```

```bash
# Fix resolution to 4K (keeps aspect ratio, even-dimension safe)
img2vid --size 3840x2160 -o output_4k.mp4
```

```bash
# Lossless archival MKV (very large files, editing-friendly)
img2vid -o output.mkv --lossless
```

```bash
# Use HEVC (smaller files, slower encode)
img2vid --codec libx265 --crf 22 -o output.mp4
```

```bash
# Recurse into subfolders
img2vid --recursive
```

```bash
# Specify allowed extensions
img2vid --exts jpg,jpeg,png,webp
```

```bash
# Provide an explicit ffmpeg path
img2vid --ffmpeg "C:\ffmpeg\bin\ffmpeg.exe"
```

```bash
# Dry run (print the ffmpeg command without executing)
img2vid --dry-run
```

---

## CLI Options

- `-i, --input` — Input folder (default: current folder)  
- `-o, --output` — Output video file (default: `output.mp4`)  
- `--fps` — Frames per second (default: `16`)  
- `--crf` — Quality (lower = better). Defaults: x264 → `16`, x265 → `22`  
- `--preset` — Encoder preset (`veryslow`, `slower`, `slow`, `medium`, …). Default: `slow`  
- `--pix-fmt` — Pixel format (default: `yuv420p`; with `--lossless`, `yuv444p` is recommended)  
- `--size` — Target resolution `WxH` (e.g., `1920x1080`, `3840x2160`). Uses Lanczos + even-dimension fix  
- `--codec` — `libx264` (default), `libx265`, `prores_ks`, etc.  
- `--recursive` — Scan images recursively  
- `--exts` — Comma-separated extensions (default: `jpg,jpeg,png,webp,bmp,tif,tiff`)  
- `--ffmpeg` — Path to `ffmpeg` executable  
- `--dry-run` — Print the command only  
- `--lossless` — x264 lossless (`CRF 0`) + `yuv444p` unless overridden

---

## How It Works

1. Collects files by extension from the input folder (optionally recursive).  
2. Sorts them alphabetically (case-insensitive).  
3. Writes a temporary concat list with `duration = 1 / FPS` between entries and duplicates the last file.  
4. Runs ffmpeg to encode the video at the chosen FPS, codec, and quality.  
5. Ensures even output dimensions; applies Lanczos scaling if `--size` is provided.

On Windows, the tool writes the concat list in **UTF-8 with BOM** and uses POSIX-style absolute paths to handle non-ASCII filenames safely.

---

## Quality & Compatibility Tips

- `CRF`: lower means higher quality, larger files.  
  - x264 good range: `14–18` (default `16`)  
  - x265 good range: `18–26` (default `22`)
- `preset`: slower presets increase compression efficiency (smaller files at the same quality).
- `pix_fmt`: `yuv420p` is most compatible; `yuv444p` improves text/line fidelity but may reduce compatibility.
- For `libx265` in MP4 containers, the tool adds `-tag:v hvc1` to improve player compatibility.

---

## Troubleshooting

- **`ffmpeg` not found**  
  Ensure `ffmpeg` is on your `PATH`, or pass `--ffmpeg` with the full path.

- **“No images found.”**  
  Check the folder path and extensions. Try `--recursive` or adjust `--exts`.

- **Mixed or odd dimensions cause errors**  
  The tool enforces even dimensions; if you need a specific size, use `--size WxH`.

- **Playback issues (green/purple tint, etc.)**  
  Try `--pix-fmt yuv420p` (default) for maximum compatibility, or re-encode with a different container (e.g., `.mkv`).

---

# Bounce utility (`img2vid-bounce`)

Adds a “bounce” (forward then backward) segment to your image sequence **without duplicating the last frame** and **without symlinks** (Windows-friendly).  
Works as a preprocessing step: it creates extra images so your existing alphabetical `img2vid` pipeline picks them up automatically.

---

## What it does (step-by-step)

1. Scans the **current folder** for images (default extensions: .png, .jpg, .jpeg, .bmp, .webp, .tif, .tiff).  
2. Sorts them in **alphabetical order** (case-insensitive).  
3. Determines the target segment:  
   - If no arguments are given → uses the **entire range** `[1..N]`.  
   - Or you can specify `--start/--end` (1-based index) or `--from-name/--to-name`.  
4. Generates a reversed copy of the segment **excluding the last frame** (so the pivot isn’t duplicated).  
5. Writes copies as `ENDNAME_001.ext`, `ENDNAME_002.ext`, … next to your images.  
   - It finds the first **contiguous free number block**, so re-running won’t overwrite existing files.

Resulting order (conceptually):  
`… start, …, end, end-1, …, start …` (with `end` not repeated at the join).

---

## Why this is safe for Windows

- Uses `shutil.copy2` only (no symlinks/junctions).  
- Preserves timestamps and metadata where possible.

---

## Typical workflow

1) Run the bounce preprocessor to create the mirrored frames.  
2) Run your existing `img2vid` command to stitch alphabetically.  
3) (Optional) Delete the generated `*_###.ext` files if you need to revert.

---

## Usage

- No arguments (apply to the whole sequence):
  - `img2vid-bounce`

- By index (1-based, inclusive):
  - `img2vid-bounce --start 3 --end 8`

- By filename:
  - `img2vid-bounce --from-name 0003.png --to-name 0008.png`

- Limit to certain extensions:
  - `img2vid-bounce --exts .png .jpg`

- Dry run (show what would be created, but don’t write files):
  - `img2vid-bounce --dry-run --start 10 --end 30`

---

## Options

- `--start INT` – Start index (1-based).  
- `--end INT` – End index (1-based, inclusive).  
- `--from-name NAME` – Start filename (must exist in the alphabetical list).  
- `--to-name NAME` – End filename (must exist in the alphabetical list).  
- `--exts EXT ...` – One or more extensions to include (e.g., `.png .jpg`). If omitted, a common image set is used.  
- `--dry-run` – Print planned copies but **do not** create files.

If none of `--start/--end` or `--from-name/--to-name` are provided, the tool uses the full range `[1..N]`.

---

## File naming details

- If your end file is `0008.png`, generated files will be `0008_001.png`, `0008_002.png`, …  
- The tool searches for the **first gap** large enough to hold all new files (e.g., if `_001` exists, it will start at `_00X` where a big enough contiguous span is free).

---

## Notes & tips

- **Alphabetical vs numeric**: alphabetical order means `1, 10, 2, …`. For numeric ordering, prefer **zero-padded names** (`0001, 0002, …`).  
- **Idempotency**: running it again on the same segment will create a new block (`_00X`) rather than overwriting.  
- **Multiple segments**: run `img2vid-bounce` separately per segment (choose each segment’s `--end` so its clones group under that end name).  
- **Space/time**: copying creates real files; if storage is tight, consider cleaning up `*_###.ext` after rendering.

---

## Example end-to-end

1) Add bounce to frames `0003.png` through `0008.png`:  
   `img2vid-bounce --from-name 0003.png --to-name 0008.png`

2) Render as usual (alphabetical stitching):  
   `img2vid`

The final video will traverse forward through `0003 … 0008`, then step backward `0007 … 0003`—with `0008` not duplicated at the turning point.

---

## Troubleshooting

- “Cannot find file …”: ensure the filename exists **after** alphabetical sorting (case-insensitive).  
- “No images found”: check extensions or specify `--exts`.  
- Unexpected order in final video: verify your filenames are **zero-padded** if you intend numeric ordering.

## License

MIT
