#!/usr/bin/env python3
"""
Generate standard 2:1 equirectangular textures for Three.js WebGL Earth visualization:
- assets/earth/albedo.png: Authentic NASA Blue Marble Next Generation daylight surface
- assets/earth/bump.png: NASA Earth Observatory & GEBCO elevation relief for terrain bump mapping
- assets/earth/night.png: NASA Black Marble / Suomi NPP VIIRS land-masked nocturnal city lights
- assets/earth/clouds.png: Authentic NASA MODIS satellite cloud composite with alpha transparency
- assets/earth/specular.png: NASA Blue Marble high-contrast ocean specular mask
- assets/earth/stars.jpg: Deep space Milky Way starfield background sphere

All paths are resolved relative to this repository root by default.
Supports resolution presets: 1k (1024x512), 2k (2048x1024), 4k (4096x2048, default), 8k (8192x4096).
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
DEFAULT_EARTH_DIR = os.path.join(SCRIPT_DIR, "assets", "earth")

PRESETS = {
    '1k': (1024, 512),
    '2k': (2048, 1024),
    '4k': (4096, 2048),
    '8k': (8192, 4096),
}


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate 2:1 equirectangular textures for Three.js Earth visualization.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate default 4K (4096x2048) textures from authentic NASA datasets:
  python3 build_webgl_textures.py

  # Generate 8K (8192x4096) master textures:
  python3 build_webgl_textures.py --preset 8k

  # Generate 2K (2048x1024) performance textures:
  python3 build_webgl_textures.py --preset 2k

  # Inspect inputs and targets without writing:
  python3 build_webgl_textures.py --dry-run
        """
    )
    parser.add_argument(
        "--preset",
        choices=list(PRESETS.keys()),
        default="4k",
        help="Resolution preset: 1k (1024x512), 2k (2048x1024), 4k (4096x2048, default), 8k (8192x4096)."
    )
    parser.add_argument(
        "--width",
        type=int,
        default=None,
        help="Custom texture width in pixels (overrides preset)."
    )
    parser.add_argument(
        "--height",
        type=int,
        default=None,
        help="Custom texture height in pixels (overrides preset)."
    )
    parser.add_argument(
        "--raw-dir",
        default=DEFAULT_RAW_DIR,
        help=f"Directory containing raw NASA source textures (default: {DEFAULT_RAW_DIR})"
    )
    parser.add_argument(
        "--earth-dir",
        default=DEFAULT_EARTH_DIR,
        help=f"Directory for output WebGL textures (default: {DEFAULT_EARTH_DIR})"
    )
    parser.add_argument(
        "--seam-width",
        type=int,
        default=None,
        help="Horizontal cross-fade seam blend width in pixels (default: scaled to width, 64px for 4K)"
    )
    parser.add_argument(
        "--normal-map",
        action="store_true",
        help="Generate high-precision tangent-space normal map (normal.png) from elevation relief"
    )
    parser.add_argument(
        "--normal-only",
        action="store_true",
        help="Generate only the tangent-space normal map (normal.png) without rebuilding other textures"
    )
    parser.add_argument(
        "--normal-scale",
        type=float,
        default=2.05,
        help="Scale factor for tangent-space normal gradient (default: 2.05, matching shader uBumpScale)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print configuration and verify source files without processing textures"
    )
    return parser.parse_args()


def find_asset(directory, preferred_name, fallback_prefixes=None):
    """Find a file in directory matching preferred_name or starting with one of fallback_prefixes."""
    if not os.path.isdir(directory):
        return None

    # Exact preferred file
    pref_path = os.path.join(directory, preferred_name)
    if os.path.isfile(pref_path):
        return pref_path

    if fallback_prefixes:
        for prefix in fallback_prefixes:
            for fname in sorted(os.listdir(directory)):
                if fname.startswith(prefix) and not fname.endswith('.bmp') and not fname.endswith('.tmp'):
                    candidate = os.path.join(directory, fname)
                    if os.path.isfile(candidate):
                        return candidate

    return None


def resample_and_load_bmp(src_path, target_w, target_h):
    """Use macOS sips to resample input image to target dimensions and load raw RGB bytes in row-major order."""
    if not os.path.isfile(src_path):
        raise FileNotFoundError(f"Source image not found: {src_path}")

    tmp_bmp = src_path + f".{target_w}x{target_h}.tmp.bmp"
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

    # Optimize for standard 24-bit BGR BMP with zero padding (when w is multiple of 4)
    if bytes_per_pixel == 3 and row_stride == w * 3 and not top_down:
        # BMP is stored bottom-up; flip rows to top-down
        rgb = bytearray(w * abs_h * 3)
        row_bytes = w * 3
        for y in range(abs_h):
            src_row_start = (abs_h - 1 - y) * row_bytes
            dst_row_start = y * row_bytes
            # BGR -> RGB swap
            rgb[dst_row_start : dst_row_start + row_bytes : 3] = raw[src_row_start + 2 : src_row_start + row_bytes : 3]
            rgb[dst_row_start + 1 : dst_row_start + row_bytes : 3] = raw[src_row_start + 1 : src_row_start + row_bytes : 3]
            rgb[dst_row_start + 2 : dst_row_start + row_bytes : 3] = raw[src_row_start : src_row_start + row_bytes : 3]
        return w, abs_h, rgb

    # General fallback for arbitrary BMP padding or orientation
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


def apply_seam_blend_rgb(rgb_bytes, width, height, seam_w):
    """Apply symmetric smoothstep cross-fade across the antimeridian (column 0 and column width-1)."""
    if seam_w <= 0:
        return
    row_bytes = width * 3
    weights = [0.0] * seam_w
    inv_weights = [0.0] * seam_w
    for x in range(seam_w):
        s = x / float(seam_w)
        smooth = s * s * (3.0 - 2.0 * s)
        t = 0.5 + 0.5 * smooth
        weights[x] = t
        inv_weights[x] = 1.0 - t

    for y in range(height):
        row_start = y * row_bytes
        for x in range(seam_w):
            t = weights[x]
            inv_t = inv_weights[x]
            left_idx = row_start + x * 3
            right_idx = row_start + (width - 1 - x) * 3

            r_left = rgb_bytes[left_idx]
            g_left = rgb_bytes[left_idx + 1]
            b_left = rgb_bytes[left_idx + 2]

            r_right = rgb_bytes[right_idx]
            g_right = rgb_bytes[right_idx + 1]
            b_right = rgb_bytes[right_idx + 2]

            rgb_bytes[left_idx] = int(t * r_left + inv_t * r_right)
            rgb_bytes[left_idx + 1] = int(t * g_left + inv_t * g_right)
            rgb_bytes[left_idx + 2] = int(t * b_left + inv_t * b_right)

            rgb_bytes[right_idx] = int(t * r_right + inv_t * r_left)
            rgb_bytes[right_idx + 1] = int(t * g_right + inv_t * g_left)
            rgb_bytes[right_idx + 2] = int(t * b_right + inv_t * b_left)


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
    print(f"✓ Saved {os.path.basename(filename)} ({width}x{height}, {os.path.getsize(filename):,} bytes)", flush=True)


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
    print(f"✓ Saved {os.path.basename(filename)} ({width}x{height}, {os.path.getsize(filename):,} bytes)", flush=True)


def smoothstep(e0, e1, x):
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
    return t * t * (3.0 - 2.0 * t)


def generate_tangent_space_normal_map(bump_rgb, width, height, seam_w, scale_factor=2.05, spec_mask=None):
    """Generate high-precision tangent-space normal map (normal.png) from elevation bump data.

    Uses a 3x3 Sobel filter and equirectangular metric tensor scale compensation
    (1.0 / max(0.06, sin(pi * v))) to eliminate polar distortion and preserve crisp mountain relief.
    Format:
      R = Tangent X (East / West, +u) in [0, 255]
      G = Tangent Y (North / South, +v) in [0, 255]
      B = Tangent Z (Normal / Outward, +z) in [0, 255]
    """
    normal_rgb = bytearray(width * height * 3)
    row_bytes = width * 3
    inv_255 = 1.0 / 255.0

    # Latitude metric tensor scale lookup: scaleX = 1.0 / max(0.06, sin(pi * v))
    scale_x_lut = [
        1.0 / max(0.06, math.sin(math.pi * (y + 0.5) / float(height)))
        for y in range(height)
    ]

    for y in range(height):
        y_prev = max(0, y - 1) * row_bytes
        y_curr = y * row_bytes
        y_next = min(height - 1, y + 1) * row_bytes
        dst_row = y * row_bytes

        sx = scale_x_lut[y] * scale_factor
        sy = scale_factor
        row_mask_start = y * width

        for x in range(width):
            # Land masking: if specular water mask indicates water (>= 128), set flat normal (0, 0, 1)
            if spec_mask is not None and spec_mask[row_mask_start + x] >= 128:
                dst_idx = dst_row + x * 3
                normal_rgb[dst_idx]     = 128
                normal_rgb[dst_idx + 1] = 128
                normal_rgb[dst_idx + 2] = 255
                continue

            xm1 = ((x - 1 + width) % width) * 3
            x0 = x * 3
            xp1 = ((x + 1) % width) * 3

            # 3x3 Sobel neighborhood (grayscale elevation from red channel)
            # y_prev is North (row y-1), y_curr is center (row y), y_next is South (row y+1)
            # xm1 is West (col x-1), x0 is center (col x), xp1 is East (col x+1)
            h00 = bump_rgb[y_prev + xm1] * inv_255
            h10 = bump_rgb[y_prev + x0]  * inv_255
            h20 = bump_rgb[y_prev + xp1] * inv_255

            h01 = bump_rgb[y_curr + xm1] * inv_255
            h21 = bump_rgb[y_curr + xp1] * inv_255

            h02 = bump_rgb[y_next + xm1] * inv_255
            h12 = bump_rgb[y_next + x0]  * inv_255
            h22 = bump_rgb[y_next + xp1] * inv_255

            # Sobel gradients:
            # gx: East (+x, xp1) minus West (-x, xm1) -> dH/du
            gx = ((h20 + 2.0 * h21 + h22) - (h00 + 2.0 * h01 + h02)) * 0.125 * sx
            # gy: North (-y in image, y_prev) minus South (+y in image, y_next) -> dH/dv (+v is North)
            gy = ((h00 + 2.0 * h10 + h20) - (h02 + 2.0 * h12 + h22)) * 0.125 * sy

            # Tangent-space normal vector: (-gx, -gy, 1.0) normalized
            inv_len = 1.0 / math.sqrt(gx * gx + gy * gy + 1.0)
            nx = -gx * inv_len
            ny = -gy * inv_len
            nz = 1.0 * inv_len

            dst_idx = dst_row + x0
            normal_rgb[dst_idx]     = int(round(max(0.0, min(1.0, nx * 0.5 + 0.5)) * 255.0))
            normal_rgb[dst_idx + 1] = int(round(max(0.0, min(1.0, ny * 0.5 + 0.5)) * 255.0))
            normal_rgb[dst_idx + 2] = int(round(max(0.0, min(1.0, nz * 0.5 + 0.5)) * 255.0))

    apply_seam_blend_rgb(normal_rgb, width, height, seam_w)
    return normal_rgb


def main():
    args = parse_args()

    if args.width and args.height:
        width, height = args.width, args.height
    elif args.preset:
        width, height = PRESETS[args.preset.lower()]
    else:
        width, height = PRESETS['4k']

    raw_dir = os.path.abspath(args.raw_dir)
    earth_dir = os.path.abspath(args.earth_dir)

    if args.seam_width is not None:
        seam_w = max(0, args.seam_width)
    else:
        # Scale seam width proportionally: 32 for 2K, 64 for 4K, 128 for 8K
        seam_w = max(16, int(width * (64.0 / 4096.0)))

    print(f"🌍 Three.js WebGL Texture Pipeline")
    print(f"   Resolution      : {width}x{height} (2:1 Equirectangular)")
    print(f"   Raw Directory   : {raw_dir}")
    print(f"   Output Directory: {earth_dir}")
    print(f"   Seam Blend Width: {seam_w}px")

    # Locate source datasets
    src_stars = find_asset(raw_dir, "deep_space_8k_milky_way.jpg", ["deep_space_starfield", "stars"])
    src_albedo = find_asset(raw_dir, "nasa_blue_marble_8k_albedo.jpg", ["nasa_daymap_8k_surface", "earth_satellite_daylight"])
    src_night = find_asset(raw_dir, "nasa_black_marble_8k_night.jpg", ["earth_night_lights", "night"])
    src_bump = find_asset(raw_dir, "nasa_gebco_elevation_relief.png", ["earth_terrain_relief", "relief"])
    src_spec = find_asset(raw_dir, "nasa_water_mask_8k_specular.tif", ["earth_ocean_specular_mask", "specular"])
    src_clouds = find_asset(raw_dir, "nasa_modis_8k_clouds.jpg", ["satellite_clouds_texture", "clouds"])

    if args.dry_run:
        print("\n[Dry Run] Validating asset sources:")
        print(f" - Stars source   : {src_stars}")
        print(f" - Albedo source  : {src_albedo}")
        print(f" - Night source   : {src_night}")
        print(f" - Bump source    : {src_bump}")
        print(f" - Specular source: {src_spec}")
        print(f" - Clouds source  : {src_clouds}")
        print("[Dry Run] Complete. Exiting without modifications.")
        return

    os.makedirs(earth_dir, exist_ok=True)
    t0 = time.time()

    # -------------------------------------------------------------------------
    # Fast path: --normal-only (generate only normal.png)
    # -------------------------------------------------------------------------
    if args.normal_only:
        print("\n[Normal Map Only] Processing normal.png (tangent-space normal map)...")
        # Find elevation source: prefer existing earth/bump.png if matching target resolution, else src_bump
        bump_path = os.path.join(earth_dir, "bump.png")
        if not os.path.isfile(bump_path):
            bump_path = src_bump
        if not bump_path or not os.path.isfile(bump_path):
            raise FileNotFoundError(f"Elevation bump source not found in {earth_dir} or {raw_dir}")

        print(f" - Loading elevation data from: {os.path.basename(bump_path)}")
        bw, bh, bump_rgb = resample_and_load_bmp(bump_path, width, height)
        apply_seam_blend_rgb(bump_rgb, width, height, seam_w)

        # Specular water mask for ocean flattening
        spec_mono = None
        spec_path = os.path.join(earth_dir, "specular.png")
        if not os.path.isfile(spec_path):
            spec_path = src_spec
        if spec_path and os.path.isfile(spec_path):
            print(f" - Loading specular water mask from: {os.path.basename(spec_path)}")
            sw, sh, spec_raw = resample_and_load_bmp(spec_path, width, height)
            lut_spec = bytes([0 if i < 128 else 255 for i in range(256)])
            spec_mono = spec_raw[0::3].translate(lut_spec)

        print(f" - Computing 3x3 Sobel tangent normals with metric scale (scale={args.normal_scale})...")
        normal_rgb = generate_tangent_space_normal_map(
            bump_rgb, width, height, seam_w,
            scale_factor=args.normal_scale,
            spec_mask=spec_mono
        )
        dst_normal = os.path.join(earth_dir, "normal.png")
        write_png_rgb(dst_normal, width, height, normal_rgb)
        total_time = time.time() - t0
        print(f"\n✨ Tangent-space normal map ({width}x{height}) successfully built in {total_time:.2f}s!", flush=True)
        return

    # -------------------------------------------------------------------------
    # 1. Background stars.jpg (Milky Way celestial sphere)
    # -------------------------------------------------------------------------
    dst_stars = os.path.join(earth_dir, "stars.jpg")
    if src_stars and os.path.isfile(src_stars):
        print("\n[1/6] Processing stars.jpg...")
        subprocess.run(
            ['sips', '-z', str(height), str(width), src_stars, '-s', 'format', 'jpeg', '-s', 'formatOptions', '92', '--out', dst_stars],
            check=True, stdout=subprocess.DEVNULL
        )
        print(f"✓ Saved stars.jpg ({width}x{height}, {os.path.getsize(dst_stars):,} bytes)")
    else:
        print("⚠ Stars source not found, keeping existing stars.jpg if present")

    # -------------------------------------------------------------------------
    # 2. Daylight Surface (albedo.png) - NASA Blue Marble Next Generation
    # -------------------------------------------------------------------------
    print("\n[2/6] Processing albedo.png (NASA Blue Marble Next Generation)...")
    if not src_albedo or not os.path.isfile(src_albedo):
        raise FileNotFoundError(f"Daylight albedo source not found in {raw_dir}")

    w, h, albedo_rgb = resample_and_load_bmp(src_albedo, width, height)
    apply_seam_blend_rgb(albedo_rgb, width, height, seam_w)
    write_png_rgb(os.path.join(earth_dir, "albedo.png"), width, height, albedo_rgb)

    # -------------------------------------------------------------------------
    # 3. Ocean Specular Mask (specular.png) - NASA Blue Marble Hydrography
    # -------------------------------------------------------------------------
    print("\n[3/6] Processing specular.png (NASA Hydrographic Specular Mask)...")
    if not src_spec or not os.path.isfile(src_spec):
        raise FileNotFoundError(f"Specular mask source not found in {raw_dir}")

    sw, sh, spec_raw = resample_and_load_bmp(src_spec, width, height)
    specular_rgb = bytearray(width * height * 3)

    # Build clean binary / anti-aliased specular mask (255 water, 0 land)
    # spec_raw is RGB where water is 255 and land is 0
    lut_spec = bytes([0 if i < 128 else 255 for i in range(256)])
    spec_mono = spec_raw[0::3].translate(lut_spec)

    specular_rgb[0::3] = spec_mono
    specular_rgb[1::3] = spec_mono
    specular_rgb[2::3] = spec_mono

    apply_seam_blend_rgb(specular_rgb, width, height, seam_w)
    write_png_rgb(os.path.join(earth_dir, "specular.png"), width, height, specular_rgb)

    # -------------------------------------------------------------------------
    # 4. Night Lights (night.png) - NASA Black Marble / VIIRS
    # -------------------------------------------------------------------------
    print("\n[4/6] Processing night.png (NASA Black Marble City Lights)...")
    if not src_night or not os.path.isfile(src_night):
        raise FileNotFoundError(f"Night lights source not found in {raw_dir}")

    nw, nh, night_rgb = resample_and_load_bmp(src_night, width, height)

    # Subtract low background sensor noise (< 12) so oceans and deep wilderness are dark
    # Boost golden-amber incandescent glow for cities
    lut_night_r = bytes([int(min(255, max(0, (i - 10) * 1.12))) for i in range(256)])
    lut_night_g = bytes([int(min(255, max(0, (i - 10) * 1.05))) for i in range(256)])
    lut_night_b = bytes([int(min(255, max(0, (i - 12) * 0.85))) for i in range(256)])

    night_rgb[0::3] = night_rgb[0::3].translate(lut_night_r)
    night_rgb[1::3] = night_rgb[1::3].translate(lut_night_g)
    night_rgb[2::3] = night_rgb[2::3].translate(lut_night_b)

    # Land-masking: suppress any residual noise over open ocean where specular mask is 255
    # (keeps coastal city lights bright)
    for i in range(width * height):
        if spec_mono[i] == 255:
            # Over open water, suppress lights unless very bright (coastal harbor / offshore rigs)
            r = night_rgb[i * 3]
            if r < 60:
                night_rgb[i * 3] = 0
                night_rgb[i * 3 + 1] = 0
                night_rgb[i * 3 + 2] = 0

    apply_seam_blend_rgb(night_rgb, width, height, seam_w)
    write_png_rgb(os.path.join(earth_dir, "night.png"), width, height, night_rgb)

    # -------------------------------------------------------------------------
    # 5. Topographic Elevation Bump Map (bump.png) - NASA Earth Observatory & GEBCO
    # -------------------------------------------------------------------------
    print("\n[5/6] Processing bump.png (NASA / GEBCO Topographic Relief)...")
    if not src_bump or not os.path.isfile(src_bump):
        raise FileNotFoundError(f"Elevation bump source not found in {raw_dir}")

    bw, bh, bump_rgb = resample_and_load_bmp(src_bump, width, height)
    apply_seam_blend_rgb(bump_rgb, width, height, seam_w)
    write_png_rgb(os.path.join(earth_dir, "bump.png"), width, height, bump_rgb)

    # Optional high-precision tangent-space normal map (normal.png)
    if args.normal_map:
        print("   Generating tangent-space normal map (normal.png) with metric scale compensation...")
        normal_rgb = generate_tangent_space_normal_map(
            bump_rgb, width, height, seam_w,
            scale_factor=args.normal_scale,
            spec_mask=spec_mono
        )
        write_png_rgb(os.path.join(earth_dir, "normal.png"), width, height, normal_rgb)

    # -------------------------------------------------------------------------
    # 6. Satellite Clouds (clouds.png) - NASA MODIS Global Composite
    # -------------------------------------------------------------------------
    print("\n[6/6] Processing clouds.png (NASA MODIS Satellite Clouds RGBA)...")
    if not src_clouds or not os.path.isfile(src_clouds):
        raise FileNotFoundError(f"Cloud composite source not found in {raw_dir}")

    cw, ch, clouds_raw = resample_and_load_bmp(src_clouds, width, height)
    apply_seam_blend_rgb(clouds_raw, width, height, seam_w)

    # Build RGBA cloud texture:
    # Pure cloud color is crisp white (248-255), with alpha derived smoothly from cloud optical density
    clouds_rgba = bytearray(width * height * 4)

    # Alpha LUT: map grayscale cloud luminance (0-255) to alpha transparency (0-245)
    # Clouds below threshold 22 are completely transparent (clear sky)
    # Clouds above 190 are thick storm fronts / cyclones (alpha ~240)
    alpha_lut = bytes([
        int(min(242, max(0, smoothstep(22.0, 195.0, float(i)) * 242.0)))
        for i in range(256)
    ])

    # Cloud luminance from Green channel (strongest signal)
    cloud_lum = clouds_raw[1::3]
    cloud_alpha = cloud_lum.translate(alpha_lut)

    # White cloud RGB
    white_r = bytes([250] * (width * height))
    white_g = bytes([252] * (width * height))
    white_b = bytes([255] * (width * height))

    clouds_rgba[0::4] = white_r
    clouds_rgba[1::4] = white_g
    clouds_rgba[2::4] = white_b
    clouds_rgba[3::4] = cloud_alpha

    write_png_rgba(os.path.join(earth_dir, "clouds.png"), width, height, clouds_rgba)

    total_time = time.time() - t0
    print(f"\n✨ All 2:1 equirectangular textures ({width}x{height}) successfully built in {total_time:.2f}s!", flush=True)


if __name__ == "__main__":
    main()
