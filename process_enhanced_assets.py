#!/usr/bin/env python3
"""
Hyper-fast, ultra-high-fidelity asset processor using macOS native sips resampling:
- assets/earth/stars.jpg: Deep-space cosmic background
- assets/earth/clouds.png: 2048x2048 transparent RGBA satellite clouds with seamless horizontal wrap & polar extensions
- assets/earth/cloud-shadow.png: 2048x2048 soft cloud shadow mask
- assets/earth/night-lights.png: 2048x2048 city lights strictly on land with golden-amber glow
- assets/earth/surface-detail.png: 2048x2048 high-resolution terrain relief and elevation texture
- assets/earth/daylight-surface.png: 2048x2048 photorealistic satellite surface map with verified coastlines & shelves

All paths are resolved relative to this script's directory by default.
Dimensions and input/output directories are configurable via CLI arguments.
"""

import argparse
import math
import os
import shutil
import struct
import subprocess
import sys
import time
import zlib

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_RAW_DIR = os.path.join(SCRIPT_DIR, "assets", "raw")
DEFAULT_OUT_DIR = os.path.join(SCRIPT_DIR, "assets", "earth")
DEFAULT_EXISTING_SURFACE = os.path.join(SCRIPT_DIR, "assets", "earth-surface.png")

PRESETS = {
    '1k': (1024, 1024),
    '2k': (2048, 2048),
    '4k': (4096, 4096),
}


def parse_args():
    parser = argparse.ArgumentParser(
        description="Process enhanced square Earth textures with polar extensions.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process standard 2048x2048 enhanced assets:
  python3 process_enhanced_assets.py

  # Process 4K (4096x4096) assets using preset:
  python3 process_enhanced_assets.py --preset 4k

  # Custom dimensions and directories:
  python3 process_enhanced_assets.py --width 2048 --height 2048 --out-dir ./output
        """
    )
    parser.add_argument(
        "--width",
        type=int,
        default=2048,
        help="Texture width in pixels (default: 2048)"
    )
    parser.add_argument(
        "--height",
        type=int,
        default=2048,
        help="Texture height in pixels (default: 2048)"
    )
    parser.add_argument(
        "--preset",
        choices=list(PRESETS.keys()),
        help="Resolution preset: 1k (1024x1024), 2k (2048x2048), 4k (4096x4096). Overrides --width/--height."
    )
    parser.add_argument(
        "--world-height",
        type=int,
        default=None,
        help="Central world map height in pixels (default: height // 2)"
    )
    parser.add_argument(
        "--raw-dir",
        default=DEFAULT_RAW_DIR,
        help=f"Directory containing raw satellite textures (default: {DEFAULT_RAW_DIR})"
    )
    parser.add_argument(
        "--out-dir",
        default=DEFAULT_OUT_DIR,
        help=f"Output directory for generated assets (default: {DEFAULT_OUT_DIR})"
    )
    parser.add_argument(
        "--existing-surface",
        default=DEFAULT_EXISTING_SURFACE,
        help=f"Path to verified base earth surface map (default: {DEFAULT_EXISTING_SURFACE})"
    )
    parser.add_argument(
        "--seam-width",
        type=int,
        default=64,
        help="Horizontal cross-fade seam blend width in pixels (default: 64)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print configuration and verify source files without processing textures"
    )
    return parser.parse_args()


def find_asset(directory, prefix, exact_name=None):
    """Find a file starting with prefix in directory, or exact_name."""
    if exact_name:
        candidate = os.path.join(directory, exact_name)
        if os.path.isfile(candidate):
            return candidate
    if os.path.isdir(directory):
        for fname in sorted(os.listdir(directory)):
            if fname.startswith(prefix) and not fname.endswith('.bmp'):
                return os.path.join(directory, fname)
    if exact_name:
        return os.path.join(directory, exact_name)
    return None


def resample_and_load_bmp(src_path, target_w, target_h):
    """Use sips to resample input image to target dimensions and load raw RGB bytes in milliseconds."""
    if not os.path.isfile(src_path):
        raise FileNotFoundError(f"Source image not found: {src_path}")

    tmp_bmp = src_path + f".{target_w}x{target_h}.bmp"
    try:
        subprocess.run(
            ['sips', '-z', str(target_h), str(target_w), src_path, '-s', 'format', 'bmp', '--out', tmp_bmp],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE
        )
        with open(tmp_bmp, 'rb') as f:
            header = f.read(54)
            offset = struct.unpack('<I', header[10:14])[0]
            w = struct.unpack('<i', header[18:22])[0]
            h = struct.unpack('<i', header[22:26])[0]
            bpp = struct.unpack('<H', header[28:30])[0]
            f.seek(offset)
            raw = f.read()
    finally:
        if os.path.exists(tmp_bmp):
            try:
                os.remove(tmp_bmp)
            except OSError:
                pass

    abs_h = abs(h)
    top_down = (h < 0)
    bytes_per_pixel = bpp // 8
    row_stride = ((w * bytes_per_pixel + 3) // 4) * 4

    rgb = bytearray(w * abs_h * 3)
    for y in range(abs_h):
        src_y = y if top_down else (abs_h - 1 - y)
        src_row = src_y * row_stride
        dst_row = y * w * 3
        for x in range(w):
            b = raw[src_row + x * bytes_per_pixel]
            g = raw[src_row + x * bytes_per_pixel + 1]
            r = raw[src_row + x * bytes_per_pixel + 2]
            rgb[dst_row + x * 3] = r
            rgb[dst_row + x * 3 + 1] = g
            rgb[dst_row + x * 3 + 2] = b
    return w, abs_h, rgb


def write_png_rgb(filename, width, height, rgb_bytes):
    def chunk(chunk_type, data):
        return (struct.pack('>I', len(data)) +
                chunk_type + data +
                struct.pack('>I', zlib.crc32(chunk_type + data) & 0xffffffff))

    header = b'\x89PNG\r\n\x1a\n'
    ihdr = chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0))
    raw_lines = bytearray()
    row_bytes = width * 3
    for y in range(height):
        raw_lines.append(0)
        raw_lines.extend(rgb_bytes[y * row_bytes : (y + 1) * row_bytes])
    idat = chunk(b'IDAT', zlib.compress(bytes(raw_lines), 4))
    iend = chunk(b'IEND', b'')
    with open(filename, 'wb') as f:
        f.write(header + ihdr + idat + iend)
    print(f"✓ Saved {filename} ({os.path.getsize(filename):,} bytes)", flush=True)


def write_png_rgba(filename, width, height, rgba_bytes):
    def chunk(chunk_type, data):
        return (struct.pack('>I', len(data)) +
                chunk_type + data +
                struct.pack('>I', zlib.crc32(chunk_type + data) & 0xffffffff))

    header = b'\x89PNG\r\n\x1a\n'
    ihdr = chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0))
    raw_lines = bytearray()
    row_bytes = width * 4
    for y in range(height):
        raw_lines.append(0)
        raw_lines.extend(rgba_bytes[y * row_bytes : (y + 1) * row_bytes])
    idat = chunk(b'IDAT', zlib.compress(bytes(raw_lines), 4))
    iend = chunk(b'IEND', b'')
    with open(filename, 'wb') as f:
        f.write(header + ihdr + idat + iend)
    print(f"✓ Saved {filename} ({os.path.getsize(filename):,} bytes)", flush=True)


def smoothstep(e0, e1, x):
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
    return t * t * (3.0 - 2.0 * t)


def main():
    args = parse_args()

    if args.preset:
        width, height = PRESETS[args.preset.lower()]
    else:
        width, height = args.width, args.height

    h_world = args.world_height if args.world_height else height // 2
    pad_y = (height - h_world) // 2
    raw_dir = os.path.abspath(args.raw_dir)
    out_dir = os.path.abspath(args.out_dir)
    seam_w = max(0, args.seam_width)

    # Locate existing base surface texture
    existing_surface = os.path.abspath(args.existing_surface)
    if not os.path.isfile(existing_surface):
        # Fallback search
        candidate = os.path.join(SCRIPT_DIR, "assets", "earth-surface.png")
        if os.path.isfile(candidate):
            existing_surface = candidate

    print("🚀 Enhanced Asset Processor")
    print(f"   Canvas Dimensions : {width}x{height}")
    print(f"   World Map Height  : {h_world}px (Padding: {pad_y}px top/bottom)")
    print(f"   Raw Directory     : {raw_dir}")
    print(f"   Output Directory  : {out_dir}")
    print(f"   Base Surface Map  : {existing_surface}")
    print(f"   Seam Blend Width  : {seam_w}px")

    if args.dry_run:
        print("\n[Dry Run] Validating asset sources:")
        stars_src = find_asset(raw_dir, "deep_space_starfield", "deep_space_starfield_1788751651724.jpg")
        print(f" - Stars source      : {stars_src} (exists: {os.path.isfile(stars_src) if stars_src else False})")
        clouds_src = find_asset(raw_dir, "satellite_clouds_texture", "satellite_clouds_texture_1788751665410.jpg")
        print(f" - Clouds source     : {clouds_src} (exists: {os.path.isfile(clouds_src) if clouds_src else False})")
        relief_src = find_asset(raw_dir, "earth_terrain_relief", "earth_terrain_relief_1788751699195.jpg")
        print(f" - Relief source     : {relief_src} (exists: {os.path.isfile(relief_src) if relief_src else False})")
        night_src = find_asset(raw_dir, "earth_night_lights", "earth_night_lights_1788751730768.jpg")
        print(f" - Night source      : {night_src} (exists: {os.path.isfile(night_src) if night_src else False})")
        sat_src = find_asset(raw_dir, "earth_satellite_daylight", "earth_satellite_daylight_1788751747278.jpg")
        print(f" - Daylight source   : {sat_src} (exists: {os.path.isfile(sat_src) if sat_src else False})")
        print(f" - Base Surface      : {existing_surface} (exists: {os.path.isfile(existing_surface)})")
        print("[Dry Run] Complete. Exiting without modifications.")
        return

    os.makedirs(out_dir, exist_ok=True)
    t0 = time.time()

    # 1. STARS: Deep Space Cosmic Background
    print("1. Copying deep space starfield...", flush=True)
    src_stars = find_asset(raw_dir, "deep_space_starfield", "deep_space_starfield_1788751651724.jpg")
    dst_stars = os.path.join(out_dir, "stars.jpg")
    if src_stars and os.path.isfile(src_stars):
        shutil.copy2(src_stars, dst_stars)
        print(f"✓ Saved stars.jpg ({os.path.getsize(dst_stars):,} bytes)", flush=True)

    # 2. CLOUDS & CLOUD SHADOW: Real satellite cloud coverage
    print("2. Resampling and processing satellite clouds...", flush=True)
    src_clouds = find_asset(raw_dir, "satellite_clouds_texture", "satellite_clouds_texture_1788751665410.jpg")
    cw, ch, c_rgb = resample_and_load_bmp(src_clouds, width, h_world)

    clouds_rgba = bytearray(width * height * 4)
    shadow_rgba = bytearray(width * height * 4)

    # Top polar cap (Arctic wisps)
    for y in range(pad_y):
        factor = y / float(pad_y) if pad_y > 0 else 1.0
        factor = factor * factor
        src_row = 0
        dst_row = y * width * 4
        for x in range(width):
            px = dst_row + x * 4
            spx = src_row + x * 3
            lum = 0.299 * c_rgb[spx] + 0.587 * c_rgb[spx + 1] + 0.114 * c_rgb[spx + 2]
            alpha_f = smoothstep(35.0, 200.0, lum) * factor * 0.75
            if alpha_f > 0.03:
                alpha = int(alpha_f * 210)
                clouds_rgba[px] = 250
                clouds_rgba[px + 1] = 252
                clouds_rgba[px + 2] = 255
                clouds_rgba[px + 3] = alpha
                shadow_rgba[px + 3] = int(alpha * 0.4)

    # Central world clouds
    for wy in range(h_world):
        y = pad_y + wy
        src_row = wy * width * 3
        dst_row = y * width * 4
        for x in range(width):
            px = dst_row + x * 4
            spx = src_row + x * 3
            lum = 0.299 * c_rgb[spx] + 0.587 * c_rgb[spx + 1] + 0.114 * c_rgb[spx + 2]

            # Seamless edge cross-fade
            if seam_w > 0 and x < seam_w:
                right_spx = src_row + (width - seam_w + x) * 3
                right_lum = 0.299 * c_rgb[right_spx] + 0.587 * c_rgb[right_spx + 1] + 0.114 * c_rgb[right_spx + 2]
                t = x / float(seam_w)
                t = t * t * (3.0 - 2.0 * t)
                lum = right_lum * (1.0 - t) + lum * t

            alpha_f = smoothstep(28.0, 215.0, lum)
            if alpha_f > 0.02:
                alpha = int(alpha_f * 225)
                whiteness = int(242 + alpha_f * 13)
                clouds_rgba[px] = whiteness
                clouds_rgba[px + 1] = whiteness
                clouds_rgba[px + 2] = min(255, whiteness + 4)
                clouds_rgba[px + 3] = alpha

                # Shadow mask
                shadow_rgba[px] = 0
                shadow_rgba[px + 1] = 0
                shadow_rgba[px + 2] = 0
                shadow_rgba[px + 3] = int(alpha * 0.42)

    # Bottom polar cap (Antarctic circumpolar wisps)
    for y in range(pad_y + h_world, height):
        factor = (height - 1 - y) / float(pad_y) if pad_y > 0 else 1.0
        factor = factor * factor
        src_row = (h_world - 1) * width * 3
        dst_row = y * width * 4
        for x in range(width):
            px = dst_row + x * 4
            spx = src_row + x * 3
            lum = 0.299 * c_rgb[spx] + 0.587 * c_rgb[spx + 1] + 0.114 * c_rgb[spx + 2]
            alpha_f = smoothstep(35.0, 200.0, lum) * factor * 0.75
            if alpha_f > 0.03:
                alpha = int(alpha_f * 210)
                clouds_rgba[px] = 250
                clouds_rgba[px + 1] = 252
                clouds_rgba[px + 2] = 255
                clouds_rgba[px + 3] = alpha
                shadow_rgba[px + 3] = int(alpha * 0.4)

    write_png_rgba(os.path.join(out_dir, "clouds.png"), width, height, clouds_rgba)
    write_png_rgba(os.path.join(out_dir, "cloud-shadow.png"), width, height, shadow_rgba)

    # 3. TERRAIN RELIEF: Topographic elevation shading
    print("3. Resampling and processing terrain relief...", flush=True)
    src_relief = find_asset(raw_dir, "earth_terrain_relief", "earth_terrain_relief_1788751699195.jpg")
    rw, rh, r_rgb = resample_and_load_bmp(src_relief, width, h_world)

    relief_rgb = bytearray(width * height * 3)
    # Fill polar padding with neutral midtone (128)
    for y in range(pad_y):
        row = y * width * 3
        for x in range(width):
            relief_rgb[row + x * 3] = 128
            relief_rgb[row + x * 3 + 1] = 128
            relief_rgb[row + x * 3 + 2] = 128

    for wy in range(h_world):
        y = pad_y + wy
        src_row = wy * width * 3
        dst_row = y * width * 3
        for x in range(width):
            spx = src_row + x * 3
            dpx = dst_row + x * 3
            r = r_rgb[spx]
            g = r_rgb[spx + 1]
            b = r_rgb[spx + 2]

            if seam_w > 0 and x < seam_w:
                right_spx = src_row + (width - seam_w + x) * 3
                t = x / float(seam_w)
                t = t * t * (3.0 - 2.0 * t)
                r = int(r_rgb[right_spx] * (1.0 - t) + r * t)
                g = int(r_rgb[right_spx + 1] * (1.0 - t) + g * t)
                b = int(r_rgb[right_spx + 2] * (1.0 - t) + b * t)

            relief_rgb[dpx] = r
            relief_rgb[dpx + 1] = g
            relief_rgb[dpx + 2] = b

    for y in range(pad_y + h_world, height):
        row = y * width * 3
        for x in range(width):
            relief_rgb[row + x * 3] = 128
            relief_rgb[row + x * 3 + 1] = 128
            relief_rgb[row + x * 3 + 2] = 128

    write_png_rgb(os.path.join(out_dir, "surface-detail.png"), width, height, relief_rgb)

    # 4. NIGHT LIGHTS & DAYLIGHT SURFACE: Geographically authentic land masking
    print("4. Compositing geographically authentic surface and night lights...", flush=True)
    src_night = find_asset(raw_dir, "earth_night_lights", "earth_night_lights_1788751730768.jpg")
    nw, nh, n_rgb = resample_and_load_bmp(src_night, width, h_world)

    src_sat = find_asset(raw_dir, "earth_satellite_daylight", "earth_satellite_daylight_1788751747278.jpg")
    sw, sh, s_rgb = resample_and_load_bmp(src_sat, width, h_world)

    ew, eh, e_rgb = resample_and_load_bmp(existing_surface, width, height)

    night_rgb = bytearray(width * height * 3)
    daylight_rgb = bytearray(width * height * 3)

    # Top Arctic Ice
    for y in range(pad_y):
        row = y * width * 3
        for x in range(width):
            px = row + x * 3
            daylight_rgb[px] = e_rgb[px]
            daylight_rgb[px + 1] = e_rgb[px + 1]
            daylight_rgb[px + 2] = e_rgb[px + 2]

    # Central World
    for wy in range(h_world):
        y = pad_y + wy
        src_row = wy * width * 3
        full_row = y * width * 3

        for x in range(width):
            spx = src_row + x * 3
            fpx = full_row + x * 3

            er = e_rgb[fpx]
            eg = e_rgb[fpx + 1]
            eb = e_rgb[fpx + 2]

            # In our verified map: ocean is deep blue (eb > er + 12 and eg < 135 and er < 38)
            is_ocean = (eb > er + 12 and eg < 135 and er < 38)

            # Sample satellite photo and night lights
            sr = s_rgb[spx]
            sg = s_rgb[spx + 1]
            sb = s_rgb[spx + 2]

            nr = n_rgb[spx]
            ng = n_rgb[spx + 1]
            nb = n_rgb[spx + 2]

            if seam_w > 0 and x < seam_w:
                right_spx = src_row + (width - seam_w + x) * 3
                t = x / float(seam_w)
                t = t * t * (3.0 - 2.0 * t)
                sr = int(s_rgb[right_spx] * (1.0 - t) + sr * t)
                sg = int(s_rgb[right_spx + 1] * (1.0 - t) + sg * t)
                sb = int(s_rgb[right_spx + 2] * (1.0 - t) + sb * t)
                nr = int(n_rgb[right_spx] * (1.0 - t) + nr * t)
                ng = int(n_rgb[right_spx + 1] * (1.0 - t) + ng * t)
                nb = int(n_rgb[right_spx + 2] * (1.0 - t) + nb * t)

            # --- Daylight Compositing ---
            if is_ocean:
                daylight_rgb[fpx] = er
                daylight_rgb[fpx + 1] = eg
                daylight_rgb[fpx + 2] = eb
            else:
                sat_lum = (sr * 0.299 + sg * 0.587 + sb * 0.114) / 128.0
                daylight_rgb[fpx] = int(min(255, er * (0.55 + 0.45 * sat_lum)))
                daylight_rgb[fpx + 1] = int(min(255, eg * (0.55 + 0.45 * sat_lum)))
                daylight_rgb[fpx + 2] = int(min(255, eb * (0.55 + 0.45 * sat_lum)))

            # --- Night Lights Compositing (strictly on land) ---
            lum_n = (nr * 0.3 + ng * 0.59 + nb * 0.11)
            if not is_ocean and lum_n > 20:
                inten = min(1.0, (lum_n - 18) / 150.0)
                night_rgb[fpx] = int(min(255, inten * 255))
                night_rgb[fpx + 1] = int(min(255, inten * 210))
                night_rgb[fpx + 2] = int(min(255, inten * 125))

    # Bottom Antarctic Continent Ice
    for y in range(pad_y + h_world, height):
        row = y * width * 3
        for x in range(width):
            px = row + x * 3
            daylight_rgb[px] = e_rgb[px]
            daylight_rgb[px + 1] = e_rgb[px + 1]
            daylight_rgb[px + 2] = e_rgb[px + 2]

    write_png_rgb(os.path.join(out_dir, "daylight-surface.png"), width, height, daylight_rgb)
    write_png_rgb(os.path.join(out_dir, "night-lights.png"), width, height, night_rgb)

    print(f"✨ Enhanced assets completed in {time.time() - t0:.2f}s!", flush=True)


if __name__ == "__main__":
    main()
