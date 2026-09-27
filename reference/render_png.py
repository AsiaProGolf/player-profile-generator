#!/usr/bin/env python3
"""Export a rendered profile HTML to a clean, tightly-cropped PNG.

Pipeline: HTML -> WeasyPrint PDF -> pdftoppm PNG,
then auto-trim the uniform page background to the card (+ shadow) and re-pad
with an even margin, so the output is a single glance-and-decide image at any
card height.

Render the HTML with `render_profile.py --embed-fonts` first so the vendored
Inter is used (otherwise WeasyPrint falls back to a generic sans).

Usage:
    python3 render_png.py profile.html [--out profile.png] [--dpi 200] [--margin 30]
"""
import argparse
import os
import subprocess
import sys
import tempfile

# html background is propagated to the whole page canvas, so the empty area
# below the card is gray (not white) and the auto-trim can crop it away.
PAGE_CSS = ("@page { size: 860px 4000px; margin: 0; }\n"
            "html { background: #F3F5F8; }\nbody { padding: 30px 24px; }\n")
BG = (243, 245, 248)  # #F3F5F8 page background


def run(cmd):
    subprocess.run(cmd, check=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Rendered profile HTML -> tightly-cropped PNG.")
    ap.add_argument("html")
    ap.add_argument("--out")
    ap.add_argument("--dpi", type=int, default=200)
    ap.add_argument("--margin", type=int, default=30, help="Even gray margin (px) to re-pad after trim.")
    args = ap.parse_args(argv)

    html_path = os.path.abspath(args.html)
    out = args.out or os.path.splitext(html_path)[0] + ".png"

    with tempfile.TemporaryDirectory() as tmp:
        css = os.path.join(tmp, "page.css")
        with open(css, "w") as f:
            f.write(PAGE_CSS)
        pdf = os.path.join(tmp, "p.pdf")
        run(["weasyprint", "-s", css, html_path, pdf])
        # pdftoppm writes <prefix>-1.png (or -01); glob for whatever it makes
        prefix = os.path.join(tmp, "p")
        run(["pdftoppm", "-png", "-r", str(args.dpi), pdf, prefix])
        pngs = sorted(f for f in os.listdir(tmp) if f.startswith("p") and f.endswith(".png"))
        if not pngs:
            print("ERROR: pdftoppm produced no PNG", file=sys.stderr)
            return 1
        raw = os.path.join(tmp, pngs[0])

        from PIL import Image, ImageChops
        im = Image.open(raw).convert("RGB")
        # trim the uniform background to the card. A plain getbbox is fooled by
        # faint sub-pixel rasterisation noise at high DPI, so threshold the
        # difference first — only clearly non-background pixels count.
        bg = Image.new("RGB", im.size, BG)
        diff = ImageChops.difference(im, bg).convert("L")
        bbox = diff.point(lambda x: 255 if x > 16 else 0).getbbox()
        if bbox:
            im = im.crop(bbox)
        m = int(args.margin * args.dpi / 96)  # scale the margin to the render DPI
        padded = Image.new("RGB", (im.width + 2 * m, im.height + 2 * m), BG)
        padded.paste(im, (m, m))
        padded.save(out)
        print("wrote %s  (%dx%d)" % (out, padded.width, padded.height))
    return 0


if __name__ == "__main__":
    sys.exit(main())
