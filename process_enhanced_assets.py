#!/usr/bin/env python3
"""
Hyper-fast, ultra-high-fidelity asset processor using macOS native sips resampling:
- assets/earth/stars.jpg: Deep-space cosmic background
- assets/earth/clouds.png: 2048x2048 transparent RGBA satellite clouds with seamless horizontal wrap & polar extensions
- assets/earth/cloud-shadow.png: 2048x2048 soft cloud shadow mask
- assets/earth/night-lights.png: 2048x2048 city lights strictly on land with golden-amber glow
- assets/earth/surface-detail.png: 2048x2048 high-resolution terrain relief and elevation texture
- assets/earth/daylight-surface.png: 2048x2048 photorealistic satellite surface map with verified coastlines & shelves
"""
import math
import os
import shutil
import struct
import subprocess
import time
import zlib

RAW_DIR = "/Users/celtninja/.gemini/antigravity/scratch/earth-3d/assets/raw"
OUT_DIR = "/Users/celtninja/.gemini/antigravity/scratch/earth-3d/assets/earth"
os.makedirs(OUT_DIR, exist_ok=True)

WIDTH = 2048
HEIGHT = 2048
H_WORLD = 1024
PAD_Y = (HEIGHT - H_WORLD) // 2  # 512

def resample_and_load_bmp(src_path, target_w=WIDTH, target_h=H_WORLD):
    """Use sips to resample input image to target dimensions and load raw RGB bytes in milliseconds"""
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
    print("🚀 Beginning rapid asset processing via native sips acceleration...", flush=True)

    # 1. STARS: Deep Space Cosmic Background
    print("1. Copying deep space starfield...", flush=True)
    src_stars = os.path.join(RAW_DIR, "deep_space_starfield_1788751651724.jpg")
    dst_stars = os.path.join(OUT_DIR, "stars.jpg")
    if os.path.exists(src_stars):
        shutil.copy2(src_stars, dst_stars)
        print(f"✓ Saved stars.jpg ({os.path.getsize(dst_stars):,} bytes)", flush=True)

    # 2. CLOUDS & CLOUD SHADOW: Real satellite cloud coverage
    print("2. Resampling and processing satellite clouds...", flush=True)
    src_clouds = os.path.join(RAW_DIR, "satellite_clouds_texture_1788751665410.jpg")
    cw, ch, c_rgb = resample_and_load_bmp(src_clouds, WIDTH, H_WORLD)

    clouds_rgba = bytearray(WIDTH * HEIGHT * 4)
    shadow_rgba = bytearray(WIDTH * HEIGHT * 4)
    SEAM_W = 64

    # Top polar cap (Arctic wisps)
    for y in range(PAD_Y):
        factor = y / float(PAD_Y)
        factor = factor * factor
        src_row = 0
        dst_row = y * WIDTH * 4
        for x in range(WIDTH):
            px = dst_row + x * 4
            spx = src_row + x * 3
            lum = 0.299 * c_rgb[spx] + 0.587 * c_rgb[spx+1] + 0.114 * c_rgb[spx+2]
            alpha_f = smoothstep(35.0, 200.0, lum) * factor * 0.75
            if alpha_f > 0.03:
                alpha = int(alpha_f * 210)
                clouds_rgba[px] = 250; clouds_rgba[px+1] = 252; clouds_rgba[px+2] = 255
                clouds_rgba[px+3] = alpha
                shadow_rgba[px+3] = int(alpha * 0.4)

    # Central world clouds
    for wy in range(H_WORLD):
        y = PAD_Y + wy
        src_row = wy * WIDTH * 3
        dst_row = y * WIDTH * 4
        for x in range(WIDTH):
            px = dst_row + x * 4
            spx = src_row + x * 3
            lum = 0.299 * c_rgb[spx] + 0.587 * c_rgb[spx+1] + 0.114 * c_rgb[spx+2]

            # Seamless edge cross-fade
            if x < SEAM_W:
                right_spx = src_row + (WIDTH - SEAM_W + x) * 3
                right_lum = 0.299 * c_rgb[right_spx] + 0.587 * c_rgb[right_spx+1] + 0.114 * c_rgb[right_spx+2]
                t = x / float(SEAM_W)
                t = t * t * (3.0 - 2.0 * t)
                lum = right_lum * (1.0 - t) + lum * t

            alpha_f = smoothstep(28.0, 215.0, lum)
            if alpha_f > 0.02:
                alpha = int(alpha_f * 225)
                whiteness = int(242 + alpha_f * 13)
                clouds_rgba[px] = whiteness
                clouds_rgba[px+1] = whiteness
                clouds_rgba[px+2] = min(255, whiteness + 4)
                clouds_rgba[px+3] = alpha

                # Shadow mask
                shadow_rgba[px] = 0; shadow_rgba[px+1] = 0; shadow_rgba[px+2] = 0
                shadow_rgba[px+3] = int(alpha * 0.42)

    # Bottom polar cap (Antarctic circumpolar wisps)
    for y in range(PAD_Y + H_WORLD, HEIGHT):
        factor = (HEIGHT - 1 - y) / float(PAD_Y)
        factor = factor * factor
        src_row = (H_WORLD - 1) * WIDTH * 3
        dst_row = y * WIDTH * 4
        for x in range(WIDTH):
            px = dst_row + x * 4
            spx = src_row + x * 3
            lum = 0.299 * c_rgb[spx] + 0.587 * c_rgb[spx+1] + 0.114 * c_rgb[spx+2]
            alpha_f = smoothstep(35.0, 200.0, lum) * factor * 0.75
            if alpha_f > 0.03:
                alpha = int(alpha_f * 210)
                clouds_rgba[px] = 250; clouds_rgba[px+1] = 252; clouds_rgba[px+2] = 255
                clouds_rgba[px+3] = alpha
                shadow_rgba[px+3] = int(alpha * 0.4)

    write_png_rgba(os.path.join(OUT_DIR, "clouds.png"), WIDTH, HEIGHT, clouds_rgba)
    write_png_rgba(os.path.join(OUT_DIR, "cloud-shadow.png"), WIDTH, HEIGHT, shadow_rgba)

    # 3. TERRAIN RELIEF: Topographic elevation shading
    print("3. Resampling and processing terrain relief...", flush=True)
    src_relief = os.path.join(RAW_DIR, "earth_terrain_relief_1788751699195.jpg")
    rw, rh, r_rgb = resample_and_load_bmp(src_relief, WIDTH, H_WORLD)

    relief_rgb = bytearray(WIDTH * HEIGHT * 3)
    # Fill polar padding with neutral midtone (128)
    for y in range(PAD_Y):
        row = y * WIDTH * 3
        for x in range(WIDTH):
            relief_rgb[row + x * 3] = 128
            relief_rgb[row + x * 3 + 1] = 128
            relief_rgb[row + x * 3 + 2] = 128

    for wy in range(H_WORLD):
        y = PAD_Y + wy
        src_row = wy * WIDTH * 3
        dst_row = y * WIDTH * 3
        for x in range(WIDTH):
            spx = src_row + x * 3
            dpx = dst_row + x * 3
            r = r_rgb[spx]
            g = r_rgb[spx+1]
            b = r_rgb[spx+2]

            if x < SEAM_W:
                right_spx = src_row + (WIDTH - SEAM_W + x) * 3
                t = x / float(SEAM_W)
                t = t * t * (3.0 - 2.0 * t)
                r = int(r_rgb[right_spx] * (1.0 - t) + r * t)
                g = int(r_rgb[right_spx+1] * (1.0 - t) + g * t)
                b = int(r_rgb[right_spx+2] * (1.0 - t) + b * t)

            relief_rgb[dpx] = r
            relief_rgb[dpx+1] = g
            relief_rgb[dpx+2] = b

    for y in range(PAD_Y + H_WORLD, HEIGHT):
        row = y * WIDTH * 3
        for x in range(WIDTH):
            relief_rgb[row + x * 3] = 128
            relief_rgb[row + x * 3 + 1] = 128
            relief_rgb[row + x * 3 + 2] = 128

    write_png_rgb(os.path.join(OUT_DIR, "surface-detail.png"), WIDTH, HEIGHT, relief_rgb)

    # 4. NIGHT LIGHTS & DAYLIGHT SURFACE: Geographically authentic land masking
    print("4. Compositing geographically authentic surface and night lights...", flush=True)
    src_night = os.path.join(RAW_DIR, "earth_night_lights_1788751730768.jpg")
    nw, nh, n_rgb = resample_and_load_bmp(src_night, WIDTH, H_WORLD)

    src_sat = os.path.join(RAW_DIR, "earth_satellite_daylight_1788751747278.jpg")
    sw, sh, s_rgb = resample_and_load_bmp(src_sat, WIDTH, H_WORLD)

    # Load verified geographic surface
    existing_surface = "/Users/celtninja/.gemini/antigravity/scratch/earth-3d/assets/earth-surface.png"
    ew, eh, e_rgb = resample_and_load_bmp(existing_surface, WIDTH, HEIGHT)

    night_rgb = bytearray(WIDTH * HEIGHT * 3)
    daylight_rgb = bytearray(WIDTH * HEIGHT * 3)

    # Top Arctic Ice
    for y in range(PAD_Y):
        row = y * WIDTH * 3
        for x in range(WIDTH):
            px = row + x * 3
            daylight_rgb[px] = e_rgb[px]
            daylight_rgb[px+1] = e_rgb[px+1]
            daylight_rgb[px+2] = e_rgb[px+2]

    # Central World
    for wy in range(H_WORLD):
        y = PAD_Y + wy
        src_row = wy * WIDTH * 3
        full_row = y * WIDTH * 3

        for x in range(WIDTH):
            spx = src_row + x * 3
            fpx = full_row + x * 3

            er = e_rgb[fpx]
            eg = e_rgb[fpx+1]
            eb = e_rgb[fpx+2]

            # In our verified map: ocean is deep blue (eb > er + 15 and eg < 135 and er < 35)
            is_ocean = (eb > er + 12 and eg < 135 and er < 38)

            # Sample satellite photo and night lights
            sr = s_rgb[spx]
            sg = s_rgb[spx+1]
            sb = s_rgb[spx+2]

            nr = n_rgb[spx]
            ng = n_rgb[spx+1]
            nb = n_rgb[spx+2]

            if x < SEAM_W:
                right_spx = src_row + (WIDTH - SEAM_W + x) * 3
                t = x / float(SEAM_W)
                t = t * t * (3.0 - 2.0 * t)
                sr = int(s_rgb[right_spx] * (1.0 - t) + sr * t)
                sg = int(s_rgb[right_spx+1] * (1.0 - t) + sg * t)
                sb = int(s_rgb[right_spx+2] * (1.0 - t) + sb * t)
                nr = int(n_rgb[right_spx] * (1.0 - t) + nr * t)
                ng = int(n_rgb[right_spx+1] * (1.0 - t) + ng * t)
                nb = int(n_rgb[right_spx+2] * (1.0 - t) + nb * t)

            # --- Daylight Compositing ---
            if is_ocean:
                daylight_rgb[fpx] = er
                daylight_rgb[fpx+1] = eg
                daylight_rgb[fpx+2] = eb
            else:
                # Modulate verified biome hue with photographic satellite luminance
                sat_lum = (sr * 0.299 + sg * 0.587 + sb * 0.114) / 128.0
                daylight_rgb[fpx] = int(min(255, er * (0.55 + 0.45 * sat_lum)))
                daylight_rgb[fpx+1] = int(min(255, eg * (0.55 + 0.45 * sat_lum)))
                daylight_rgb[fpx+2] = int(min(255, eb * (0.55 + 0.45 * sat_lum)))

            # --- Night Lights Compositing ---
            # Strictly on land! Zero artificial lights in the middle of the ocean
            lum_n = (nr * 0.3 + ng * 0.59 + nb * 0.11)
            if not is_ocean and lum_n > 20:
                inten = min(1.0, (lum_n - 18) / 150.0)
                night_rgb[fpx] = int(min(255, inten * 255))
                night_rgb[fpx+1] = int(min(255, inten * 210))
                night_rgb[fpx+2] = int(min(255, inten * 125))

    # Bottom Antarctic Continent Ice
    for y in range(PAD_Y + H_WORLD, HEIGHT):
        row = y * WIDTH * 3
        for x in range(WIDTH):
            px = row + x * 3
            daylight_rgb[px] = e_rgb[px]
            daylight_rgb[px+1] = e_rgb[px+1]
            daylight_rgb[px+2] = e_rgb[px+2]

    write_png_rgb(os.path.join(OUT_DIR, "daylight-surface.png"), WIDTH, HEIGHT, daylight_rgb)
    write_png_rgb(os.path.join(OUT_DIR, "night-lights.png"), WIDTH, HEIGHT, night_rgb)

    print(f"✨ Enhanced assets completed in {time.time() - t0:.2f}s!", flush=True)

if __name__ == "__main__":
    main()
