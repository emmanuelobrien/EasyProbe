#!/usr/bin/env python3

"""
You can use this script to assemble a .ttf font file from the SVG icons and
JSON metadata in glyphs/.

This is only necessary if you want to change or validate the .ttf file checked
into the repo.

You can also use it to extract the glyphs from an existing .ttf file using
the --extract argument.

Run this script from the directory where it lives.

Requires the fontforge library (eg., apt install python3-fontforge)

Bug: If you generate the font, then extract the metadata, a few of the glyphs
lose one pixel of width.  Since we should normally be just going one direction
(metadata -> font) rather than extracting and recreating, this shouldn't cause
much trouble.  I tried a bunch of variations on how we round width and
left_side_bearing and couldn't find a stable fixpoint.
"""

import os
import argparse
import glob
import json
import math
from fontforge import font, open as ff_open


def generate_font(manifest_filename, output_file):
    """
    Create a TTF font from a directory of SVG files and JSON metadata.

    Args:
        manifest (str): Filename for JSON metadata
        output_file (str): Path for output TTF file
    """
    print(f"Reading from {manifest_filename}")
    if not os.path.exists(manifest_filename):
        raise FileNotFoundError(f"Manifest file not found: {manifest_filename}.")

    with open(manifest_filename) as f:
        manifest = json.load(f)

    # Create new font with metadata from manifest
    f = font()
    f.encoding = "UnicodeFull"
    f.fontname = manifest["fontname"]
    f.familyname = manifest["familyname"]
    f.fullname = manifest["fullname"]
    f.em = manifest["em"]
    f.ascent = manifest["ascent"]
    f.descent = manifest["descent"]
    f.weight = manifest["weight"]
    f.version = manifest["version"]

    svg_dir = os.path.dirname(os.path.abspath(manifest_filename))

    # Process SVG files using manifest data
    processed = []
    for glyph_data in manifest["glyphs"]:
        svg_path = os.path.join(svg_dir, glyph_data["file"])

        if not os.path.exists(svg_path):
            print(f"Warning: Missing SVG file: {glyph_data['file']}")
            continue

        try:
            glyph = f.createChar(glyph_data["unicode"], glyph_data["name"])
            glyph.importOutlines(svg_path)

            # Set exact metrics from manifest
            glyph.width = glyph_data["width"]
            glyph.left_side_bearing = round(glyph_data["left_side_bearing"])

            processed.append(glyph_data["file"])
            print(f"Processed {glyph_data['file']} at U+{glyph_data['unicode']:04X}")
        except Exception as e:
            print(f"Error processing {glyph_data['file']}: {e}")

    # Generate font file
    f.generate(output_file)
    print(f"\nGenerated font file: {output_file}")
    print(f"Processed {len(processed)} glyphs")
    return len(processed)


def extract_font(output_dir, font_path):
    """
    Extract glyphs from a TTF file into individual SVG files.

    Args:
        font_path (str): Path to the TTF file
        output_dir (str): Directory to save SVG files and JSON manifest
    """
    os.makedirs(output_dir, exist_ok=True)
    font = ff_open(font_path)

    # Collect font metadata
    manifest = {
        "fontname": font.fontname,
        "familyname": font.familyname,
        "fullname": font.fullname,
        "em": font.em,
        "ascent": font.ascent,
        "descent": font.descent,
        "weight": font.weight,
        "version": font.version,
        "glyphs": [],
    }

    # Process each glyph in the font
    for glyph in font.glyphs():
        # Skip non-drawing glyphs
        if not glyph.isWorthOutputting():
            continue

        codepoint = f"{glyph.unicode:04x}"

        # Bug: Fontforge automatically generates .notdef and nonmarkingreturn
        # codepoints when you create the font, but when you go to extract
        # them, it generates .SVG files it can't parse.  So don't try to extract
        # them.
        if codepoint in ("-001", "000d", "fffd"):
            continue

        filename = f"u{codepoint}.svg"
        output_path = os.path.join(output_dir, filename)

        # Export the glyph as SVG
        glyph.export(output_path, layer="fore")

        # Store glyph metadata with exact metrics
        manifest["glyphs"].append(
            {
                "name": glyph.glyphname,
                "unicode": glyph.unicode,
                "file": filename,
                "width": glyph.width,
                "left_side_bearing": glyph.left_side_bearing,
            }
        )
        print(f"Extracted: {filename} ({glyph.glyphname})")

    # Save manifest as JSON
    manifest_path = os.path.join(output_dir, "manifest.json")
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"\nExtracted {len(manifest['glyphs'])} glyphs to {output_dir}")
    print(f"Generated manifest: {manifest_path}")
    return manifest


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "--manifest",
        type=str,
        help="Use this JSON metadata file to generate the --ttf file",
        default="glyphs/manifest.json",
    )
    parser.add_argument(
        "--ttf",
        type=str,
        help="Generate or disassemble this font file",
        default="../easyprobe.ttf",
    )
    parser.add_argument(
        "--extract",
        action="store_true",
        help="Disassemble the file in --ttf instead of creating it.",
    )
    parser.add_argument(
        "--extract-dir",
        type=str,
        help="Directory for --extract to store extracted glyphs",
        default="extracted-glyphs",
    )
    args = parser.parse_args()

    if args.extract:
        print(f"Extracting glyphs from existing font {args.ttf} to {args.extract_dir}")
        extract_font(output_dir=args.extract_dir, font_path=args.ttf)
    else:
        print(f"Generating font from glyphs")
        generate_font(manifest_filename=args.manifest, output_file=args.ttf)


if __name__ == "__main__":
    main()
