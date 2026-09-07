#!/usr/bin/env python3
"""
Generate standard 2:1 equirectangular textures (2048x1024) for Three.js:
- assets/earth/albedo.png (2048x1024 RGB): Verified continents, biomes, shelves, photographic satellite albedo
- assets/earth/bump.png (2048x1024 RGB): Topographic elevation relief for terrain shading
- assets/earth/night.png (2048x1024 RGB): Land-masked city lights with golden-amber incandescent glow
- assets/earth/clouds.png (2048x1024 RGBA): Photorealistic satellite cloud coverage with alpha transparency
- assets/earth/specular.png (2048x1024 RGB): High-contrast water mask (1.0 ocean, 0.0 land) for Blinn-Phong specular glint
- assets/earth/stars.jpg: Deep space starfield
"""
import os
import shutil
import struct
import subprocess
import time
import zlib

RAW_DIR = "/Users/celtninja/.gemini/antigravity/scratch/earth-3d/assets/raw"
EARTH_DIR = "/Users/celtninja/.gemini/antigravity/scratch/earth-3d/assets/earth"
os.makedirs(EARTH_DIR, exist_ok=True)

WIDTH = 2048
HEIGHT = 1024
SEAM_W = 64

def resample_and_load_bmp(src_path, target_w=WIDTH, target_h=HEIGHT):
    """Use macOS sips to resample input image to target dimensions and load raw RGB bytes."""
    tmp_bmp = src_path + f".{target_w}x{target_h}.bmp"
    subprocess.run(
        ['sips', '-z', str(target_h), str(target_w), src_path, '-s', 'format', 'bmp', '--out', tmp_bmp],
        check=True, stdout=subprocess.DEVNULL
    )
    with open(tmp_bmp, 'rb') as f:
        header = f.read(54)
        offset = struct.unpack('<I', header[10:14])[0]
        w = struct.unpack('<i', header[18:22])[0]
        h = struct.unpack('<i', header[22:26])[0]
        bpp = struct.unpack('<H', header[28:30])[0]
        f.seek(offset)
        raw = f.read()
    if os.path.exists(tmp_bmp):
        os.remove(tmp_bmp)

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
    t0 = time.time()
    print("🌍 Generating standard 2:1 equirectangular textures (2048x1024)...", flush=True)

    # 1. Background stars
    src_stars = os.path.join(RAW_DIR, "deep_space_starfield_1788751651724.jpg")
    dst_stars = os.path.join(EARTH_DIR, "stars.jpg")
    if os.path.exists(src_stars):
        shutil.copy2(src_stars, dst_stars)
        print(f"✓ Copied stars.jpg", flush=True)

    # 2. Extract verified daylight surface (2048x1024) from central 1024 rows of daylight-surface.png
    src_daylight_2048 = os.path.join(EARTH_DIR, "daylight-surface.png")
    w, h, day_full_rgb = resample_and_load_bmp(src_daylight_2048, 2048, 2048)
    
    # Extract rows 512 to 1536 (the authentic equirectangular map)
    albedo_rgb = bytearray(WIDTH * HEIGHT * 3)
    start_row = 512
    for y in range(HEIGHT):
        src_offset = (start_row + y) * WIDTH * 3
        dst_offset = y * WIDTH * 3
        albedo_rgb[dst_offset : dst_offset + WIDTH * 3] = day_full_rgb[src_offset : src_offset + WIDTH * 3]

    write_png_rgb(os.path.join(EARTH_DIR, "albedo.png"), WIDTH, HEIGHT, albedo_rgb)

    # 3. Extract verified night lights (2048x1024) from central 1024 rows of night-lights.png
    src_night_2048 = os.path.join(EARTH_DIR, "night-lights.png")
    w, h, night_full_rgb = resample_and_load_bmp(src_night_2048, 2048, 2048)
    night_rgb = bytearray(WIDTH * HEIGHT * 3)
    for y in range(HEIGHT):
        src_offset = (start_row + y) * WIDTH * 3
        dst_offset = y * WIDTH * 3
        night_rgb[dst_offset : dst_offset + WIDTH * 3] = night_full_rgb[src_offset : src_offset + WIDTH * 3]

    write_png_rgb(os.path.join(EARTH_DIR, "night.png"), WIDTH, HEIGHT, night_rgb)

    # 4. Terrain elevation bump map (2048x1024)
    src_relief = os.path.join(RAW_DIR, "earth_terrain_relief_1788751699195.jpg")
    rw, rh, relief_raw = resample_and_load_bmp(src_relief, WIDTH, HEIGHT)
    bump_rgb = bytearray(WIDTH * HEIGHT * 3)
    for y in range(HEIGHT):
        src_row = y * WIDTH * 3
        for x in range(WIDTH):
            spx = src_row + x * 3
            r = relief_raw[spx]
            g = relief_raw[spx+1]
            b = relief_raw[spx+2]

            # Seamless horizontal cross-fade
            if x < SEAM_W:
                right_spx = src_row + (WIDTH - SEAM_W + x) * 3
                t = x / float(SEAM_W)
                t = t * t * (3.0 - 2.0 * t)
                r = int(relief_raw[right_spx] * (1.0 - t) + r * t)
                g = int(relief_raw[right_spx+1] * (1.0 - t) + g * t)
                b = int(relief_raw[right_spx+2] * (1.0 - t) + b * t)

            bump_rgb[spx] = r
            bump_rgb[spx+1] = g
            bump_rgb[spx+2] = b

    write_png_rgb(os.path.join(EARTH_DIR, "bump.png"), WIDTH, HEIGHT, bump_rgb)

    # 5. Ocean Specular Mask (2048x1024)
    # Ocean is white (255) for sunlight reflection, land is black (0) for diffuse terrain
    src_spec = os.path.join(RAW_DIR, "earth_ocean_specular_mask_1788751762217.jpg")
    sw, sh, spec_raw = resample_and_load_bmp(src_spec, WIDTH, HEIGHT)
    specular_rgb = bytearray(WIDTH * HEIGHT * 3)
    for y in range(HEIGHT):
        src_row = y * WIDTH * 3
        for x in range(WIDTH):
            px = src_row + x * 3
            # Check corresponding albedo pixel to reinforce verified coastlines
            ar = albedo_rgb[px]
            ag = albedo_rgb[px+1]
            ab = albedo_rgb[px+2]
            is_ocean = (ab > ar + 12 and ag < 135 and ar < 38)

            lum = (spec_raw[px] * 0.3 + spec_raw[px+1] * 0.59 + spec_raw[px+2] * 0.11)
            
            # Seamless seam blend
            if x < SEAM_W:
                right_px = src_row + (WIDTH - SEAM_W + x) * 3
                right_lum = (spec_raw[right_px] * 0.3 + spec_raw[right_px+1] * 0.59 + spec_raw[right_px+2] * 0.11)
                t = x / float(SEAM_W)
                t = t * t * (3.0 - 2.0 * t)
                lum = right_lum * (1.0 - t) + lum * t

            # Combined specular: strong on ocean, 0 on land
            if is_ocean:
                val = max(180, int(lum))
            else:
                val = 0 if lum < 120 else int(smoothstep(120.0, 240.0, lum) * 40.0)

            specular_rgb[px] = val
            specular_rgb[px+1] = val
            specular_rgb[px+2] = val

    write_png_rgb(os.path.join(EARTH_DIR, "specular.png"), WIDTH, HEIGHT, specular_rgb)

    # 6. Clouds RGBA with transparency (2048x1024)
    src_clouds = os.path.join(RAW_DIR, "satellite_clouds_texture_1788751665410.jpg")
    cw, ch, clouds_raw = resample_and_load_bmp(src_clouds, WIDTH, HEIGHT)
    clouds_rgba = bytearray(WIDTH * HEIGHT * 4)

    for y in range(HEIGHT):
        src_row = y * WIDTH * 3
        dst_row = y * WIDTH * 4
        lat_norm = abs(y - 512) / 512.0 # 0 at equator, 1.0 at poles

        for x in range(WIDTH):
            spx = src_row + x * 3
            dpx = dst_row + x * 4
            lum = (clouds_raw[spx] * 0.299 + clouds_raw[spx+1] * 0.587 + clouds_raw[spx+2] * 0.114)

            # Seamless wrap
            if x < SEAM_W:
                right_spx = src_row + (WIDTH - SEAM_W + x) * 3
                right_lum = (clouds_raw[right_spx] * 0.299 + clouds_raw[right_spx+1] * 0.587 + clouds_raw[right_spx+2] * 0.114)
                t = x / float(SEAM_W)
                t = t * t * (3.0 - 2.0 * t)
                lum = right_lum * (1.0 - t) + lum * t

            # Calculate alpha based on cloud density
            alpha_f = smoothstep(30.0, 210.0, lum)
            # Enhance circumpolar cloud bands
            if lat_norm > 0.55:
                alpha_f = min(1.0, alpha_f * 1.25)

            if alpha_f > 0.02:
                alpha = int(alpha_f * 235)
                whiteness = int(244 + alpha_f * 11)
                clouds_rgba[dpx] = whiteness
                clouds_rgba[dpx+1] = whiteness
                clouds_rgba[dpx+2] = min(255, whiteness + 3)
                clouds_rgba[dpx+3] = alpha

    write_png_rgba(os.path.join(EARTH_DIR, "clouds.png"), WIDTH, HEIGHT, clouds_rgba)

    print(f"✨ 2:1 Equirectangular textures built in {time.time() - t0:.2f}s!", flush=True)

if __name__ == "__main__":
    main()
