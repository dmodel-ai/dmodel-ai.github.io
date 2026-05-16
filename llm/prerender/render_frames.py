#!/usr/bin/env python3
"""Render the writhing t-shirt SVG to a VP9-alpha WebM.

The source SVG (art/tshirt-back.svg) drives its writhe via SMIL <animate>
elements inside an feTurbulence/feDisplacementMap filter. That filter is
recomputed every frame in the browser and burns CPU. Instead we sample the
animation trajectory at N discrete times, bake each (dx, dy) into a static
SVG, rasterise with rsvg-convert, and pack the frames into a small WebM that
the browser can decode on the GPU.

The default settings produce art/tshirt-writhe.webm (~360KB, 60 frames over
4.5s, 640px wide, with alpha).
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


# Original SMIL trajectory from art/tshirt-back.svg:
#   dx: values=0;600  dur=4.5s   +  values=0;300  dur=7.281s  (additive)
#   dy: values=0;-120 dur=6.364s +  values=0;-75  dur=14.137s (additive)
DX_PARAMS = [(600.0, 4.5), (300.0, 7.281)]
DY_PARAMS = [(-120.0, 6.364), (-75.0, 14.137)]


def displacement(t: float) -> tuple[float, float]:
    """Compute (dx, dy) at time t using sawtooth sums identical to SMIL."""
    dx = sum(amp * ((t % per) / per) for amp, per in DX_PARAMS)
    dy = sum(amp * ((t % per) / per) for amp, per in DY_PARAMS)
    return dx, dy


# Matches the entire <feOffset>...</feOffset> block, capturing the opening tag
# attrs so we can rewrite dx/dy and drop the children.
FE_OFFSET_RE = re.compile(
    r'<feOffset\b[^>]*?dx="[^"]*"[^>]*?dy="[^"]*"[^>]*?>.*?</feOffset>',
    re.DOTALL,
)


def bake_svg(template: str, dx: float, dy: float) -> str:
    replacement = (
        f'<feOffset in="noise" dx="{dx:.4f}" dy="{dy:.4f}" result="moved"/>'
    )
    new, n = FE_OFFSET_RE.subn(replacement, template, count=1)
    if n != 1:
        raise RuntimeError("expected exactly one <feOffset> block to replace")
    return new


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--svg", type=Path, default=Path("art/tshirt-back.svg"), help="source SVG")
    p.add_argument("--out", type=Path, default=Path("art/tshirt-writhe.webm"), help="output WebM")
    p.add_argument("--frames", type=int, default=60, help="frame count")
    p.add_argument("--duration", type=float, default=4.5, help="loop seconds")
    p.add_argument("--width", type=int, default=640, help="render width px")
    p.add_argument("--crf", type=int, default=35, help="VP9 quality (lower = sharper)")
    p.add_argument("--bitrate", default="250k", help="VP9 target bitrate")
    p.add_argument("--keep-frames", action="store_true", help="don't delete the PNGs")
    args = p.parse_args()

    template = args.svg.read_text()
    work = Path(tempfile.mkdtemp(prefix="writhe-")) if not args.keep_frames else args.out.parent / "frames"
    work.mkdir(parents=True, exist_ok=True)

    try:
        for i in range(args.frames):
            t = i * args.duration / args.frames
            dx, dy = displacement(t)
            baked = bake_svg(template, dx, dy)
            svg_path = work / f"frame_{i:03d}.svg"
            png_path = work / f"frame_{i:03d}.png"
            svg_path.write_text(baked)
            subprocess.run(
                ["rsvg-convert", "-w", str(args.width), str(svg_path), "-o", str(png_path)],
                check=True,
            )
            svg_path.unlink()
            print(f"frame {i:3d}  t={t:6.3f}s  dx={dx:+8.2f}  dy={dy:+8.2f}")

        args.out.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-framerate", f"{args.frames}/{args.duration}",
                "-i", str(work / "frame_%03d.png"),
                "-vf", "format=yuva420p",
                "-c:v", "libvpx-vp9",
                "-b:v", args.bitrate,
                "-crf", str(args.crf),
                "-row-mt", "1",
                "-auto-alt-ref", "0",
                str(args.out),
            ],
            check=True,
        )
        print(f"\nwrote {args.out} ({args.out.stat().st_size:,} bytes)")
    finally:
        if not args.keep_frames:
            shutil.rmtree(work, ignore_errors=True)

    return 0


if __name__ == "__main__":
    sys.exit(main())
