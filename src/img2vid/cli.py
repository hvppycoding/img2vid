from __future__ import annotations
import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

DEFAULT_EXTS = ["jpg", "jpeg", "png", "webp", "bmp", "tif", "tiff"]


def find_ffmpeg(explicit: str | None) -> str:
    if explicit:
        return explicit
    ff = shutil.which("ffmpeg")
    if not ff:
        raise SystemExit("ERROR: ffmpeg not found on PATH. Install ffmpeg or pass --ffmpeg PATH.")
    return ff


def parse_size(s: str) -> tuple[int, int]:
    try:
        w, h = s.lower().split("x")
        return int(w), int(h)
    except Exception:
        raise argparse.ArgumentTypeError("Size must look like 1920x1080")


def collect_images(folder: Path, recursive: bool, exts: list[str]) -> list[Path]:
    exts_lower = {e.lower().lstrip(".") for e in exts}
    pattern = "**/*" if recursive else "*"
    files = [p for p in folder.glob(pattern) if p.is_file() and p.suffix.lower().lstrip(".") in exts_lower]
    files.sort(key=lambda p: p.name.lower())
    return files


def _escape_single_quotes(s: str) -> str:
    """
    Escape single quotes for ffmpeg concat file when using single-quoted paths.
    Turn:  abc'def  ->  abc'\\''def
    """
    return s.replace("'", r"'\''")


def build_concat_file(imgs: list[Path], fps: float, concat_path: Path) -> None:
    """
    Write concat list as UTF-8 **without BOM** to avoid 'unknown keyword' errors on some ffmpeg builds.
    """
    lines = []
    for i, p in enumerate(imgs):
        posix = p.resolve().as_posix()
        posix = _escape_single_quotes(posix)
        lines.append(f"file '{posix}'\n")
        if i < len(imgs) - 1:
            lines.append(f"duration {1.0 / fps}\n")
    # Repeat last file so last duration is honored
    last_posix = _escape_single_quotes(imgs[-1].resolve().as_posix())
    lines.append(f"file '{last_posix}'\n")

    # ⚠️ No BOM: use plain 'utf-8'
    concat_path.write_text("".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Join images into a video with ffmpeg, alphabetically sorted (no glob needed)."
    )
    ap.add_argument("-i", "--input", type=Path, default=Path("."), help="Input folder (default: current folder)")
    ap.add_argument("-o", "--output", type=Path, default=Path("output.mp4"), help="Output video path")
    ap.add_argument("--fps", type=float, default=16.0, help="Frames per second (default: 16)")
    ap.add_argument("--crf", type=float, default=None, help="CRF quality (lower = better). Default 16 for libx264, 22 for libx265.")
    ap.add_argument("--preset", default="slow", help="Encoder preset (e.g., veryslow, slower, slow, medium). Default: slow")
    ap.add_argument("--pix-fmt", default=None, help="Pixel format (e.g., yuv420p, yuv444p). Default depends on --lossless or codec.")
    ap.add_argument("--size", type=parse_size, default=None, help="Target resolution, e.g., 1920x1080 or 3840x2160")
    ap.add_argument("--codec", default="libx264", help="Video codec (libx264 default; also supports libx265, prores_ks, etc.)")
    ap.add_argument("--recursive", action="store_true", help="Scan images recursively")
    ap.add_argument("--exts", default=",".join(DEFAULT_EXTS), help="Comma-separated extensions (default: jpg,jpeg,png,webp,bmp,tif,tiff)")
    ap.add_argument("--ffmpeg", default=None, help="Path to ffmpeg.exe if not in PATH")
    ap.add_argument("--dry-run", action="store_true", help="Print command without running ffmpeg")
    ap.add_argument("--lossless", action="store_true", help="Use lossless x264 (CRF 0) and yuv444p unless overridden")
    args = ap.parse_args(argv)

    folder = args.input
    if not folder.exists() or not folder.is_dir():
        print(f"ERROR: Input folder does not exist: {folder}", file=sys.stderr)
        return 2

    exts = [e.strip().lower().lstrip(".") for e in args.exts.split(",") if e.strip()]
    imgs = collect_images(folder, args.recursive, exts)
    if not imgs:
        print("ERROR: No images found.", file=sys.stderr)
        return 3

    ffmpeg = find_ffmpeg(args.ffmpeg)

    # Determine quality defaults by codec
    codec = args.codec
    crf = args.crf
    pix_fmt = args.pix_fmt
    if args.lossless and codec.startswith("libx264") and crf is None:
        crf = 0
        if pix_fmt is None:
            pix_fmt = "yuv444p"
    if crf is None:
        crf = 22 if codec.startswith("libx265") else 16
    if pix_fmt is None:
        pix_fmt = "yuv420p"

    # Build filter graph:
    # - optional scaling to target size with Lanczos
    # - ensure even dimensions for codec compatibility
    filters = []
    if args.size:
        w, h = args.size
        filters.append(f"scale={w}:-2:flags=lanczos")
    filters.append("scale=ceil(iw/2)*2:ceil(ih/2)*2")
    vf = ",".join(filters) if filters else None

    # Create temp concat file
    with tempfile.TemporaryDirectory() as td:
        concat_path = Path(td) / "list.txt"
        build_concat_file(imgs, args.fps, concat_path)

        cmd = [ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(concat_path), "-r", str(args.fps)]
        if vf:
            cmd += ["-vf", vf]

        # Codec-specific defaults
        if codec == "prores_ks":
            cmd += ["-c:v", "prores_ks", "-profile:v", "3", "-pix_fmt", "yuv422p10le"]
        else:
            cmd += ["-c:v", codec, "-crf", str(crf), "-preset", args.preset, "-pix_fmt", pix_fmt]

        # If libx265 + .mp4, improve compatibility on some players
        if codec.startswith("libx265") and args.output.suffix.lower() == ".mp4":
            cmd += ["-tag:v", "hvc1"]

        cmd += [str(args.output)]

        if args.dry_run:
            print(" ".join(f'"{c}"' if " " in c else c for c in cmd))
            return 0

        print(f"Found {len(imgs)} images. Encoding to {args.output} ...")
        try:
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as e:
            print("ffmpeg failed. Command was:", file=sys.stderr)
            print(" ".join(cmd), file=sys.stderr)
            return e.returncode

    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
