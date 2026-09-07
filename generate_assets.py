#!/usr/bin/env python3
"""
Hyper-optimized realistic seamless Earth texture generator with polar extensions.
Generates 2048x2048 textures for full 3D interactive rotation (-85° to +85° latitude):
1. assets/earth-surface.png (2048x2048 RGB)
2. assets/earth-clouds.png  (2048x2048 RGBA)
3. assets/earth-night.png   (2048x2048 RGB)
"""
import math
import random
import struct
import time
import zlib
import os

WIDTH = 2048
HEIGHT = 2048

# World map area in the vertical center:
H_WORLD = 1024
PAD_Y = (HEIGHT - H_WORLD) // 2  # 512 pixels above and below

SW = 512
SH = 512
SW_WORLD = 512
SH_WORLD = 256
S_PAD_Y = (SH - SH_WORLD) // 2   # 128

ASSETS_DIR = "/Users/celtninja/.gemini/antigravity/scratch/earth-3d/assets"
os.makedirs(ASSETS_DIR, exist_ok=True)

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
    print(f"✓ Saved {filename} ({os.path.getsize(filename):,} bytes)")

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
    print(f"✓ Saved {filename} ({os.path.getsize(filename):,} bytes)")

def lonlat_to_xy(lon, lat, w=WIDTH, h=H_WORLD):
    x = (lon + 180.0) / 360.0 * w
    y = (90.0 - lat) / 180.0 * h
    return (x, y)

def rasterize_polygon(poly_lonlat, grid, w=WIDTH, h=H_WORLD, value=1):
    pts = [lonlat_to_xy(lon, lat, w, h) for lon, lat in poly_lonlat]
    n = len(pts)
    if n < 3: return
    ys = [p[1] for p in pts]
    min_y = max(0, int(math.floor(min(ys))))
    max_y = min(h - 1, int(math.ceil(max(ys))))
    for y in range(min_y, max_y + 1):
        nodes = []
        j = n - 1
        for i in range(n):
            yi, xi = pts[i][1], pts[i][0]
            yj, xj = pts[j][1], pts[j][0]
            if (yi < y and yj >= y) or (yj < y and yi >= y):
                x = xi + (y - yi) / (yj - yi) * (xj - xi)
                nodes.append(x)
            j = i
        nodes.sort()
        for k in range(0, len(nodes) - 1, 2):
            x_start = max(0, int(math.ceil(nodes[k])))
            x_end = min(w - 1, int(math.floor(nodes[k+1])))
            row_idx = y * w
            for x in range(x_start, x_end + 1):
                grid[row_idx + x] = value

def subdivide(points, iterations=2, displacement=0.2, seed=42):
    rng = random.Random(seed)
    pts = list(points)
    for it in range(iterations):
        new_pts = []
        scale = displacement / (1.6 ** it)
        n = len(pts)
        for i in range(n):
            p1 = pts[i]
            p2 = pts[(i + 1) % n]
            new_pts.append(p1)
            mx = (p1[0] + p2[0]) * 0.5
            my = (p1[1] + p2[1]) * 0.5
            dx = p2[0] - p1[0]
            dy = p2[1] - p1[1]
            dist = math.sqrt(dx*dx + dy*dy)
            if dist > 0.4:
                px = -dy / dist
                py = dx / dist
                disp = (rng.random() - 0.5) * dist * scale
                ny = max(-89.0, min(89.0, my + py * disp))
                new_pts.append((mx + px * disp, ny))
        pts = new_pts
    return pts

def get_world_polygons():
    polys = []
    water_polys = []

    # 1. North America
    na_base = [
        (-168, 65.5), (-165, 63.5), (-162, 59.5), (-166, 54), (-160, 56), (-153, 58),
        (-148, 60), (-140, 60), (-136, 58.5), (-130, 54.5), (-128, 51.5), (-123, 49),
        (-124, 46), (-124.5, 42), (-123.5, 38), (-122, 36.5), (-119, 34), (-117, 32.5),
        (-115, 31.8), (-113, 29), (-110, 24), (-109.8, 22.8), (-110.5, 24.3), (-112, 27),
        (-114.5, 31), (-107, 26), (-105, 21.5), (-102, 18), (-97, 16), (-93, 15.5),
        (-90, 14), (-88, 13.5), (-85, 11), (-83.5, 8.5), (-81, 8.2), (-78, 8.5),
        (-77.5, 7.8), (-79, 9), (-82.5, 9.5), (-83.5, 10.5), (-84, 14), (-86, 16),
        (-88, 16), (-88.5, 18), (-87, 21.5), (-90, 21), (-91, 19), (-94, 18),
        (-96, 19), (-97.5, 23), (-97.5, 26), (-94, 29.5), (-90, 29), (-88, 30.5),
        (-84, 30), (-82.5, 28), (-82, 25), (-80.5, 25), (-80, 27), (-81.5, 30.5),
        (-79, 33), (-75.5, 35.2), (-76, 37), (-74.5, 39), (-74, 40.5), (-71, 41.5),
        (-67, 44.5), (-64, 46), (-60, 46), (-59, 49), (-56, 52), (-56, 58),
        (-61, 60), (-65, 62), (-75, 62.5), (-78, 60), (-79, 55), (-80, 51.5),
        (-85, 55), (-92, 57), (-95, 63), (-86, 65), (-82, 66), (-80, 70),
        (-90, 70), (-95, 68), (-105, 68), (-115, 68), (-120, 69), (-130, 70),
        (-140, 69.5), (-150, 70.5), (-156, 71.3), (-162, 70), (-168, 66)
    ]
    polys.append(subdivide(na_base, iterations=2, displacement=0.2, seed=101))

    # 2. Greenland
    greenland_base = [
        (-44, 60), (-40, 62), (-35, 65), (-25, 70), (-18, 77), (-20, 81),
        (-30, 83.5), (-45, 83), (-55, 81), (-60, 78), (-55, 74), (-50, 69),
        (-52, 64), (-48, 61)
    ]
    polys.append(subdivide(greenland_base, iterations=2, displacement=0.25, seed=102))

    # 3. South America
    sa_base = [
        (-77, 8), (-76, 9), (-74, 11), (-71.5, 12), (-70, 11.5), (-65, 10.5),
        (-62, 10), (-60, 8.5), (-58, 6.5), (-54, 5.5), (-50, 1.5), (-48, -0.5),
        (-44, -2.5), (-38, -3.5), (-35, -5.2), (-35, -8), (-37, -11), (-39, -15),
        (-40, -20), (-43, -23), (-47, -24.5), (-48.5, -28), (-52, -32), (-55, -34.5),
        (-58, -34.5), (-57, -37), (-62, -39), (-65, -42), (-66, -46), (-68, -50),
        (-66, -54.5), (-68, -55.5), (-71, -54), (-74, -53), (-75, -48), (-73.5, -42),
        (-72, -37), (-71.5, -32), (-70.5, -25), (-70.5, -20), (-72, -16), (-76, -14),
        (-80, -9), (-81, -5), (-80, -3), (-79, 1), (-77.5, 5)
    ]
    polys.append(subdivide(sa_base, iterations=2, displacement=0.2, seed=103))

    # 4. Eurasia
    eurasia_base = [
        (-9.5, 37), (-9, 39), (-9, 43), (-8, 43.8), (-2, 43.5), (0, 42.5),
        (3, 42.5), (0, 40), (-0.5, 38), (-2, 36.7), (-5.5, 36), (-7.5, 37),
        (3, 43), (4.5, 43.5), (3, 45), (-1, 46), (-4.5, 48.5), (-1.5, 49.5),
        (1.5, 50.5), (4, 51.5), (8, 54), (8.5, 55), (9, 57), (10.5, 57.8),
        (12, 56), (16, 56), (18.5, 59.5), (22, 65), (24, 66), (28, 70),
        (31, 71), (24, 71), (18, 69.5), (12, 67), (8, 63), (5, 62),
        (5, 58.5), (10, 59.5), (13, 55.5), (24, 60), (30, 60), (28, 59),
        (24, 57), (20, 55), (14, 54),
        (32, 65), (38, 67), (40, 68), (50, 68), (60, 69), (68, 69),
        (73, 73), (85, 74), (105, 77), (115, 73), (130, 72), (145, 72),
        (160, 71), (170, 70), (178, 67), (178, 63), (175, 62),
        (166, 60), (163, 56), (156, 51), (157, 57), (150, 60), (143, 59),
        (140, 53), (136, 48), (131, 43), (130, 42), (129.5, 38), (129, 35),
        (126.5, 34.5), (126, 37), (125, 39.5), (124, 40), (121.5, 40.5),
        (118, 39), (120.5, 37.5), (119, 34.5), (122, 30), (120, 27),
        (117, 24), (113.5, 22), (110, 20.5), (108, 21.5), (106, 18),
        (109, 14), (108, 11), (105, 9), (102.5, 11), (100.5, 13), (101.5, 7),
        (104, 2), (103.5, 1.3), (101, 3), (98.5, 8), (98, 14), (95, 16),
        (94, 18), (92, 21), (89, 22), (87, 21.5), (82, 17), (80, 13),
        (80, 10), (77.5, 8.2), (75, 12), (73, 19), (72.5, 21.5), (69, 21),
        (69, 23), (67, 24), (62, 25), (57, 25), (59, 22.5), (56, 26),
        (50, 26), (48, 30), (44, 12.5), (42, 16), (38, 22), (35, 28),
        (34, 28), (35, 32), (35, 33), (34, 36), (30, 36.5), (27, 37),
        (27, 40), (28, 41.5), (26.5, 40.5), (24, 41), (24, 38), (22, 36.5),
        (21.5, 38), (20, 40), (18, 42.5), (14, 45), (13, 45), (15, 42),
        (18.5, 40), (17, 40.5), (15.5, 38), (16, 38), (15, 40.5), (12, 42),
        (10, 43), (9, 44), (7.5, 44)
    ]
    polys.append(subdivide(eurasia_base, iterations=2, displacement=0.18, seed=104))

    # 5. Africa
    africa_base = [
        (-5.5, 36), (-2, 35.5), (3, 36.8), (10, 37), (11, 33), (15, 32.5),
        (20, 32), (25, 32), (30, 31.5), (32, 31.5), (32.5, 29.8), (35, 28),
        (38, 22), (42, 16), (43.5, 12.5), (46, 12), (51, 10.5), (49, 8),
        (47, 4), (43, 0), (40, -3), (39, -6), (40, -10), (40, -15),
        (35, -20), (35, -24), (32.5, -28), (30, -31), (28, -33), (26, -34),
        (20, -34.8), (18.5, -34), (18, -32), (15, -28), (12, -22), (12, -15),
        (13, -9), (12, -6), (9.5, -1), (9.5, 3), (8.5, 4.5), (6, 4.5),
        (3, 6.3), (-1, 5), (-7.5, 4.5), (-12, 7), (-14, 9), (-16.5, 12),
        (-17.5, 14.8), (-16, 20), (-13, 27), (-9, 30), (-6, 35)
    ]
    polys.append(subdivide(africa_base, iterations=2, displacement=0.2, seed=105))

    # 6. Australia
    oz_base = [
        (114, -22), (118, -20), (123, -16), (130, -12), (136, -12), (136, -16),
        (141, -17), (142.5, -11), (145, -15), (149, -21), (153.5, -28), (151.5, -33.8),
        (150, -37.5), (146.5, -39), (141, -38), (137, -35), (138, -34), (134, -32),
        (124, -33), (118, -35), (115, -34), (115.5, -32), (113.5, -26)
    ]
    polys.append(subdivide(oz_base, iterations=2, displacement=0.22, seed=106))

    # 7. Antarctica
    antarctica_base = [
        (-180, -90), (180, -90), (180, -78), (175, -78), (160, -70), (140, -66),
        (120, -66), (90, -65), (60, -66), (30, -68), (0, -70), (-30, -75),
        (-55, -65), (-60, -63), (-65, -68), (-75, -73), (-90, -72), (-120, -73),
        (-150, -75), (-170, -78), (-180, -78)
    ]
    polys.append(antarctica_base)

    # 8. British Isles
    gb_base = [
        (-5, 50), (-1, 50.5), (1.5, 51.5), (1.7, 52.8), (0.2, 53.5), (-1, 55),
        (-2, 57), (-3, 58.5), (-5, 58.5), (-5.5, 56.5), (-4.5, 54), (-4, 53),
        (-5, 52), (-5.5, 50)
    ]
    polys.append(subdivide(gb_base, iterations=2, displacement=0.2, seed=107))

    ireland_base = [
        (-10, 51.5), (-8.5, 51.5), (-6, 52.2), (-6, 54), (-6.5, 55.2),
        (-8.5, 55.2), (-10, 54), (-10.5, 52)
    ]
    polys.append(subdivide(ireland_base, iterations=2, displacement=0.2, seed=108))

    # 9. Madagascar
    madagascar_base = [
        (44, -13), (49, -12), (50.5, -15.5), (48.5, -22), (47, -25.5),
        (44, -25), (43.5, -22), (44, -17)
    ]
    polys.append(subdivide(madagascar_base, iterations=2, displacement=0.2, seed=109))

    # 10. Japan
    japan_honshu = [
        (130, 31.5), (130.5, 33.5), (133, 34), (135.5, 34), (137, 34.5),
        (140, 35.5), (141.5, 38.5), (141, 41.5), (139.5, 40.5), (136.5, 36.5),
        (133, 35.5), (131, 34)
    ]
    polys.append(subdivide(japan_honshu, iterations=2, displacement=0.15, seed=110))

    japan_hokkaido = [
        (140.5, 41.5), (143, 42), (145.5, 43.5), (144, 44.5), (142, 45.5), (141, 43)
    ]
    polys.append(subdivide(japan_hokkaido, iterations=2, displacement=0.15, seed=111))

    # 11. Maritime Southeast Asia
    sumatra = [(95.5, 5.5), (99, 2), (104, -3), (106, -5.8), (103, -4), (98, 1.5)]
    polys.append(subdivide(sumatra, iterations=2, displacement=0.2, seed=112))

    java = [(105.5, -6.5), (114.5, -8.5), (114, -7), (106, -6)]
    polys.append(subdivide(java, iterations=2, displacement=0.2, seed=113))

    borneo = [
        (109, 1), (111, 2), (117, 4.5), (119, 4), (118.5, 1),
        (116.5, -2), (115, -4), (110.5, -3), (109, -0.5)
    ]
    polys.append(subdivide(borneo, iterations=2, displacement=0.2, seed=114))

    sulawesi = [
        (119.5, 1), (121, 1.2), (125, 1.5), (123, 0.5), (120, -1),
        (123, -1), (120, -3), (122.5, -4.5), (120, -5.5), (119.5, -3)
    ]
    polys.append(subdivide(sulawesi, iterations=2, displacement=0.2, seed=115))

    new_guinea = [
        (131, -1), (134, -3), (141, -2.5), (147, -5), (150.5, -10),
        (148, -10), (143, -7.5), (138, -5), (135, -4), (131, -2)
    ]
    polys.append(subdivide(new_guinea, iterations=2, displacement=0.2, seed=116))

    philippines_luzon = [(120, 14), (121.5, 18.5), (122, 16), (124, 13), (121, 12)]
    polys.append(subdivide(philippines_luzon, iterations=2, displacement=0.15, seed=117))

    philippines_mindanao = [(124, 6), (126, 8), (126, 9.5), (124, 9), (122, 8)]
    polys.append(subdivide(philippines_mindanao, iterations=2, displacement=0.15, seed=118))

    # 12. New Zealand & Tasmania
    nz_north = [(173, -35), (175, -34.5), (178, -37.5), (178, -39), (175, -41.5), (174, -39)]
    polys.append(subdivide(nz_north, iterations=2, displacement=0.2, seed=119))

    nz_south = [(174, -41), (174, -43), (170, -46), (167, -46.5), (166.5, -45), (172, -42)]
    polys.append(subdivide(nz_south, iterations=2, displacement=0.2, seed=120))

    tasmania = [(145, -41), (148.5, -41), (148, -43.5), (144.5, -43.5)]
    polys.append(subdivide(tasmania, iterations=2, displacement=0.2, seed=121))

    # 13. Islands
    cuba = [(-84.5, 22), (-81, 23), (-75, 20), (-74, 20.2), (-77, 21.5), (-84, 21.8)]
    polys.append(subdivide(cuba, iterations=2, displacement=0.2, seed=122))

    hispaniola = [(-74.5, 18.5), (-72, 19.8), (-68.5, 18.5), (-71, 17.5)]
    polys.append(subdivide(hispaniola, iterations=2, displacement=0.2, seed=123))

    iceland = [(-24, 65), (-22, 63.8), (-14, 65), (-16, 66.5), (-22, 66.5)]
    polys.append(subdivide(iceland, iterations=2, displacement=0.2, seed=124))

    sri_lanka = [(80, 9.5), (81.8, 7.5), (81, 6), (79.8, 7)]
    polys.append(subdivide(sri_lanka, iterations=2, displacement=0.2, seed=125))

    taiwan = [(120, 22), (121.5, 22), (122, 25), (121, 25.3), (120, 23.5)]
    polys.append(subdivide(taiwan, iterations=2, displacement=0.15, seed=126))

    # 14. Water bodies inside landmasses
    caspian = [(47, 47), (50, 47), (52, 42), (54, 37), (49, 37), (48, 41)]
    water_polys.append(subdivide(caspian, iterations=2, displacement=0.2, seed=127))

    black_sea = [(28, 42), (35, 42), (41, 42), (40, 44), (35, 45), (34, 46), (30, 46.5)]
    water_polys.append(subdivide(black_sea, iterations=2, displacement=0.2, seed=128))

    great_lakes = [
        (-92, 47), (-88, 48), (-84.5, 46), (-82, 44), (-77, 44),
        (-79, 43), (-83, 42), (-87.5, 42), (-90, 45)
    ]
    water_polys.append(subdivide(great_lakes, iterations=2, displacement=0.2, seed=129))

    lake_victoria = [(31.5, -0.5), (34.5, -0.5), (34.5, -2.8), (31.5, -2.8)]
    water_polys.append(subdivide(lake_victoria, iterations=2, displacement=0.2, seed=130))

    lake_baikal = [(103.5, 52), (108, 55.5), (109.5, 56), (105, 52.5)]
    water_polys.append(subdivide(lake_baikal, iterations=2, displacement=0.15, seed=131))

    return polys, water_polys

def make_noise_grid(seed=42, gw=SW, gh=SH):
    rng = random.Random(seed)
    cw, ch = 64, 64
    coarse = [rng.random() for _ in range(cw * ch)]
    grid = [0.0] * (gw * gh)
    for y in range(gh):
        gy = (y / float(gh)) * (ch - 1)
        y0 = int(gy)
        y1 = min(ch - 1, y0 + 1)
        fy = gy - y0
        fy = fy * fy * (3.0 - 2.0 * fy)
        for x in range(gw):
            gx = (x / float(gw)) * cw
            x0 = int(gx) % cw
            x1 = (x0 + 1) % cw
            fx = gx - int(gx)
            fx = fx * fx * (3.0 - 2.0 * fx)
            v00 = coarse[y0 * cw + x0]
            v10 = coarse[y0 * cw + x1]
            v01 = coarse[y1 * cw + x0]
            v11 = coarse[y1 * cw + x1]
            top = v00 * (1.0 - fx) + v10 * fx
            bot = v01 * (1.0 - fx) + v11 * fx
            grid[y * gw + x] = top * (1.0 - fy) + bot * fy
    return grid

def main():
    t_start = time.time()
    print("🌍 Generating NASA-grade Earth assets (2048x2048 with Polar Extensions)...")

    # Latitude table for central world map
    lat_table = [90.0 - (y / float(H_WORLD)) * 180.0 for y in range(H_WORLD)]
    lon_table = [(x / float(WIDTH)) * 360.0 - 180.0 for x in range(WIDTH)]

    # 1. Rasterize land polygons for world map
    t0 = time.time()
    land_grid = bytearray(WIDTH * H_WORLD)
    polys, waters = get_world_polygons()
    for p in polys:
        rasterize_polygon(p, land_grid, WIDTH, H_WORLD, 1)
    for wp in waters:
        rasterize_polygon(wp, land_grid, WIDTH, H_WORLD, 0)
    print(f"1. Polygons rasterized ({time.time() - t0:.2f}s)")

    # 2. Coastal shelf distance field on downscaled grid
    t0 = time.time()
    small_land = bytearray(SW_WORLD * SH_WORLD)
    for sy in range(SH_WORLD):
        src_y = (sy * H_WORLD) // SH_WORLD
        srow = sy * SW_WORLD
        for sx in range(SW_WORLD):
            src_x = (sx * WIDTH) // SW_WORLD
            small_land[srow + sx] = land_grid[src_y * WIDTH + src_x]

    shelf_dist = bytearray(SW_WORLD * SH_WORLD)
    cur = []
    for sy in range(SH_WORLD):
        srow = sy * SW_WORLD
        for sx in range(SW_WORLD):
            if small_land[srow + sx] == 0:
                for dx, dy in ((-1,0), (1,0), (0,-1), (0,1)):
                    nx = (sx + dx) % SW_WORLD
                    ny = sy + dy
                    if 0 <= ny < SH_WORLD and small_land[ny * SW_WORLD + nx] == 1:
                        shelf_dist[srow + sx] = 1
                        cur.append((sx, sy))
                        break

    for step in range(2, 6):
        nxt = []
        for sx, sy in cur:
            for dx, dy in ((-1,0), (1,0), (0,-1), (0,1)):
                nx = (sx + dx) % SW_WORLD
                ny = sy + dy
                if 0 <= ny < SH_WORLD and small_land[ny * SW_WORLD + nx] == 0 and shelf_dist[ny * SW_WORLD + nx] == 0:
                    shelf_dist[ny * SW_WORLD + nx] = step
                    nxt.append((nx, ny))
        cur = nxt
    print(f"2. Coastal shelf computed ({time.time() - t0:.2f}s)")

    # 3. Generate noise grids
    t0 = time.time()
    noise1 = make_noise_grid(seed=123, gw=SW, gh=SH)
    noise2 = make_noise_grid(seed=456, gw=SW, gh=SH)
    cloud_noise = make_noise_grid(seed=789, gw=SW, gh=SH)
    cloud_fine = make_noise_grid(seed=999, gw=SW, gh=SH)
    print(f"3. Noise fields synthesized ({time.time() - t0:.2f}s)")

    # 4. Render Earth Surface Texture (2048x2048)
    t0 = time.time()
    surface_rgb = bytearray(WIDTH * HEIGHT * 3)

    # A. Top Polar Cap (Arctic Ocean & Sea Ice)
    for y in range(PAD_Y):
        sy = (y * SH) // HEIGHT
        s_row = sy * SW
        row_idx = y * WIDTH
        for x in range(WIDTH):
            sx = (x * SW) // WIDTH
            s_idx = s_row + sx
            px = (row_idx + x) * 3
            n = noise1[s_idx]
            val = int(238 + n * 14)
            surface_rgb[px] = val
            surface_rgb[px + 1] = val
            surface_rgb[px + 2] = min(255, val + 5)

    # B. Central World Map
    for wy in range(H_WORLD):
        y = PAD_Y + wy
        lat = lat_table[wy]
        sy = (wy * SH_WORLD) // H_WORLD
        s_row = (S_PAD_Y + sy) * SW
        small_row = sy * SW_WORLD
        row_idx = y * WIDTH
        w_row_idx = wy * WIDTH

        is_polar = lat < -62.0 or lat > 72.0
        is_tundra = 60.0 < lat <= 72.0
        is_taiga = 50.0 <= lat <= 60.0

        for x in range(WIDTH):
            lon = lon_table[x]
            sx = (x * SW) // WIDTH
            s_idx = s_row + sx
            small_idx = small_row + ((x * SW_WORLD) // WIDTH)
            px = (row_idx + x) * 3

            if land_grid[w_row_idx + x] == 1:
                n1 = noise1[s_idx]
                n2 = noise2[s_idx]

                if is_polar or (lat > 60.0 and -55.0 < lon < -15.0):
                    val = int(242 + n1 * 12)
                    surface_rgb[px] = val
                    surface_rgb[px + 1] = val
                    surface_rgb[px + 2] = min(255, val + 5)
                elif 26.0 <= lat <= 36.0 and 74.0 <= lon <= 101.0: # Himalayas
                    if n1 > 0.45 or lat > 29.0:
                        surface_rgb[px] = 245; surface_rgb[px+1] = 248; surface_rgb[px+2] = 252
                    else:
                        surface_rgb[px] = int(115 + n1 * 30); surface_rgb[px+1] = int(105 + n1 * 25); surface_rgb[px+2] = int(90 + n1 * 20)
                elif -52.0 <= lat <= 10.0 and -76.0 <= lon <= -67.0 and abs(lon - (-71.0)) < 3.2: # Andes
                    if n1 > 0.52:
                        surface_rgb[px] = 240; surface_rgb[px+1] = 245; surface_rgb[px+2] = 250
                    else:
                        surface_rgb[px] = int(120 + n1 * 25); surface_rgb[px+1] = int(100 + n1 * 20); surface_rgb[px+2] = int(85 + n1 * 20)
                elif 34.0 <= lat <= 60.0 and -122.0 <= lon <= -105.0 and abs(lon - (-114.0)) < 4.0: # Rockies
                    if n1 > 0.55:
                        surface_rgb[px] = 238; surface_rgb[px+1] = 242; surface_rgb[px+2] = 248
                    else:
                        surface_rgb[px] = int(118 + n1 * 25); surface_rgb[px+1] = int(108 + n1 * 20); surface_rgb[px+2] = int(92 + n1 * 20)
                elif 15.0 <= lat <= 32.0 and -16.0 <= lon <= 35.0: # Sahara
                    if 4.0 <= lat <= 31.0 and abs(lon - (31.5 + (lat-20)*0.06)) < 0.35:
                        surface_rgb[px] = 35; surface_rgb[px+1] = 80; surface_rgb[px+2] = 30
                    else:
                        surface_rgb[px] = int(212 + n1 * 25); surface_rgb[px+1] = int(162 + n1 * 20); surface_rgb[px+2] = int(86 + n1 * 15)
                elif 12.0 <= lat <= 32.0 and 36.0 <= lon <= 60.0: # Arabia
                    surface_rgb[px] = int(205 + n1 * 25); surface_rgb[px+1] = int(155 + n1 * 20); surface_rgb[px+2] = int(80 + n1 * 15)
                elif -34.0 <= lat <= -18.0 and 115.0 <= lon <= 145.0: # Outback
                    surface_rgb[px] = int(185 + n1 * 30); surface_rgb[px+1] = int(85 + n1 * 20); surface_rgb[px+2] = int(45 + n1 * 15)
                elif 36.0 <= lat <= 47.0 and 76.0 <= lon <= 112.0: # Gobi
                    surface_rgb[px] = int(170 + n1 * 25); surface_rgb[px+1] = int(150 + n1 * 20); surface_rgb[px+2] = int(110 + n1 * 15)
                elif -30.0 <= lat <= -18.0 and 14.0 <= lon <= 26.0: # Kalahari
                    surface_rgb[px] = int(195 + n1 * 25); surface_rgb[px+1] = int(120 + n1 * 20); surface_rgb[px+2] = int(65 + n1 * 15)
                elif -10.0 <= lat <= 8.0 and ((-75.0 <= lon <= -50.0) or (12.0 <= lon <= 30.0) or (95.0 <= lon <= 150.0)): # Rainforest
                    surface_rgb[px] = int(22 + n2 * 14); surface_rgb[px+1] = int(62 + n2 * 22); surface_rgb[px+2] = int(25 + n2 * 14)
                elif is_tundra:
                    surface_rgb[px] = int(85 + n1 * 25); surface_rgb[px+1] = int(98 + n1 * 25); surface_rgb[px+2] = int(78 + n1 * 20)
                elif is_taiga:
                    surface_rgb[px] = int(34 + n2 * 16); surface_rgb[px+1] = int(58 + n2 * 20); surface_rgb[px+2] = int(38 + n2 * 15)
                else: # Temperate
                    surface_rgb[px] = int(55 + n1 * 25); surface_rgb[px+1] = int(88 + n2 * 28); surface_rgb[px+2] = int(42 + n1 * 18)
            else: # Ocean
                dist = shelf_dist[small_idx]
                if dist > 0:
                    factor = (dist - 1) / 4.0
                    r = int(28 * (1.0 - factor) + 6 * factor)
                    g = int(128 * (1.0 - factor) + 20 * factor)
                    b = int(148 * (1.0 - factor) + 52 * factor)
                else:
                    lat_mod = 1.0 - abs(lat) / 180.0 * 0.2
                    r = int(5 * lat_mod)
                    g = int(18 * lat_mod)
                    b = int(44 * lat_mod)
                surface_rgb[px] = r
                surface_rgb[px + 1] = g
                surface_rgb[px + 2] = b

    # C. Bottom Polar Cap (Antarctic Ice Sheet)
    for y in range(PAD_Y + H_WORLD, HEIGHT):
        sy = (y * SH) // HEIGHT
        s_row = sy * SW
        row_idx = y * WIDTH
        for x in range(WIDTH):
            sx = (x * SW) // WIDTH
            s_idx = s_row + sx
            px = (row_idx + x) * 3
            n = noise1[s_idx]
            val = int(244 + n * 10)
            surface_rgb[px] = val
            surface_rgb[px + 1] = val
            surface_rgb[px + 2] = min(255, val + 4)

    write_png_rgb(os.path.join(ASSETS_DIR, "earth-surface.png"), WIDTH, HEIGHT, surface_rgb)
    print(f"4. Earth surface texture completed ({time.time() - t0:.2f}s)")

    # 5. Render Atmospheric Clouds Texture (2048x2048)
    t0 = time.time()
    clouds_rgba = bytearray(WIDTH * HEIGHT * 4)

    cyclones = [
        (-35.0, 56.0, 22.0, True),
        (155.0, 42.0, 24.0, True),
        (135.0, 18.0, 16.0, True),
        (90.0, -52.0, 26.0, False),
    ]
    cyclone_bounds = []
    for cx, cy, cr, ccw in cyclones:
        cyclone_bounds.append((cx - cr, cx + cr, cy - cr, cy + cr, cx, cy, cr, ccw))

    lat_itcz = [max(0.0, 1.0 - abs(lat - 4.5) / 6.5) for lat in lat_table]
    lat_south = [max(0.0, 1.0 - abs(lat - (-50.0)) / 14.0) for lat in lat_table]
    lat_north = [max(0.0, 1.0 - abs(lat - 50.0) / 12.0) for lat in lat_table]

    # A. Top Polar Clouds
    for y in range(PAD_Y):
        sy = (y * SH) // HEIGHT
        s_row = sy * SW
        row_idx = y * WIDTH
        for x in range(WIDTH):
            sx = (x * SW) // WIDTH
            s_idx = s_row + sx
            px = (row_idx + x) * 4
            cn = cloud_noise[s_idx]
            density = max(0.0, (cn - 0.45) * 1.8)
            if density > 0.03:
                clouds_rgba[px] = 245; clouds_rgba[px+1] = 245; clouds_rgba[px+2] = 250
                clouds_rgba[px+3] = int(density * 180)

    # B. Central World Clouds
    for wy in range(H_WORLD):
        y = PAD_Y + wy
        lat = lat_table[wy]
        sy = (wy * SH_WORLD) // H_WORLD
        s_row = (S_PAD_Y + sy) * SW
        row_idx = y * WIDTH
        itcz_w = lat_itcz[wy]
        south_w = lat_south[wy]
        north_w = lat_north[wy]
        is_clear_lat = (18.0 <= lat <= 30.0) or (-30.0 <= lat <= -20.0)

        for x in range(WIDTH):
            lon = lon_table[x]
            sx = (x * SW) // WIDTH
            s_idx = s_row + sx
            px = (row_idx + x) * 4

            cn1 = cloud_noise[s_idx]
            cn2 = cloud_fine[s_idx]
            cval = cn1 * 0.7 + cn2 * 0.3

            cyc_val = 0.0
            for min_lon, max_lon, min_lat, max_lat, cx, cy, cr, ccw in cyclone_bounds:
                dlon = (lon - cx + 180.0) % 360.0 - 180.0
                dlat = lat - cy
                dist_sq = dlon*dlon + dlat*dlat
                if dist_sq < cr * cr:
                    dist = math.sqrt(dist_sq)
                    ang = math.atan2(dlat, dlon)
                    spiral = math.sin(ang * 2.5 + (dist / cr) * 6.0 * (1.0 if ccw else -1.0))
                    rim = 1.0 - (dist / cr)
                    cyc_val = max(cyc_val, (spiral * 0.5 + 0.5) * rim * 1.3)

            clear_suppress = 0.0
            if is_clear_lat:
                if (-16.0 <= lon <= 55.0) or (115.0 <= lon <= 140.0) or (-75.0 <= lon <= -65.0):
                    clear_suppress = 0.75

            density = (cval * 0.45 + itcz_w * cn2 * 0.55 + south_w * cn1 * 0.48 +
                       north_w * cn1 * 0.42 + cyc_val * 0.7) - clear_suppress - 0.28
            density = min(1.0, max(0.0, density * 1.7))

            if density > 0.03:
                alpha = int(density * 225)
                bright = int(240 + density * 15)
                clouds_rgba[px] = bright
                clouds_rgba[px + 1] = bright
                clouds_rgba[px + 2] = min(255, bright + 5)
                clouds_rgba[px + 3] = alpha

    # C. Bottom Polar Clouds
    for y in range(PAD_Y + H_WORLD, HEIGHT):
        sy = (y * SH) // HEIGHT
        s_row = sy * SW
        row_idx = y * WIDTH
        for x in range(WIDTH):
            sx = (x * SW) // WIDTH
            s_idx = s_row + sx
            px = (row_idx + x) * 4
            cn = cloud_noise[s_idx]
            density = max(0.0, (cn - 0.42) * 1.8)
            if density > 0.03:
                clouds_rgba[px] = 245; clouds_rgba[px+1] = 245; clouds_rgba[px+2] = 250
                clouds_rgba[px+3] = int(density * 180)

    write_png_rgba(os.path.join(ASSETS_DIR, "earth-clouds.png"), WIDTH, HEIGHT, clouds_rgba)
    print(f"5. Clouds texture completed ({time.time() - t0:.2f}s)")

    # 6. Render Earth Night Lights Texture (2048x2048)
    t0 = time.time()
    night_rgb = bytearray(WIDTH * HEIGHT * 3)

    cities = [
        (-74.0, 40.7, 7.5, 1.0),
        (-87.6, 41.8, 6.0, 0.9),
        (-84.3, 33.7, 5.0, 0.8),
        (-95.3, 29.7, 5.5, 0.85),
        (-80.2, 25.7, 4.5, 0.8),
        (-118.2, 34.0, 6.5, 0.95),
        (-122.4, 37.7, 5.0, 0.9),
        (-99.1, 19.4, 5.0, 0.85),
        (-46.6, -23.5, 6.0, 0.9),
        (-43.1, -22.9, 5.0, 0.85),
        (-58.3, -34.6, 5.5, 0.85),
        (-0.1, 51.5, 6.5, 1.0),
        (2.3, 48.8, 6.0, 0.95),
        (4.9, 52.3, 6.5, 1.0),
        (13.4, 52.5, 5.0, 0.85),
        (9.1, 45.4, 5.5, 0.9),
        (-3.7, 40.4, 4.5, 0.8),
        (37.6, 55.7, 5.5, 0.9),
        (31.2, 30.0, 5.5, 0.95),
        (55.2, 25.2, 4.5, 0.9),
        (46.7, 24.7, 4.0, 0.8),
        (3.3, 6.5, 4.5, 0.8),
        (28.0, -26.2, 5.0, 0.8),
        (77.2, 28.6, 7.0, 0.95),
        (72.8, 19.0, 6.0, 0.95),
        (88.3, 22.5, 5.5, 0.9),
        (116.4, 39.9, 6.5, 0.95),
        (121.4, 31.2, 7.5, 1.0),
        (113.2, 23.1, 7.0, 1.0),
        (126.9, 37.5, 6.0, 1.0),
        (139.6, 35.6, 8.0, 1.0),
        (135.5, 34.6, 6.5, 0.95),
        (121.5, 25.0, 4.5, 0.9),
        (100.5, 13.7, 4.5, 0.85),
        (103.8, 1.3, 4.0, 0.9),
        (106.8, -6.2, 5.0, 0.85),
        (120.9, 14.5, 5.0, 0.85),
        (151.2, -33.8, 4.5, 0.85),
        (144.9, -37.8, 4.5, 0.85),
    ]

    city_grid = [0.0] * (SW_WORLD * SH_WORLD)
    for cx, cy, r_deg, inten in cities:
        min_sx = int((cx - r_deg + 180.0) / 360.0 * SW_WORLD)
        max_sx = int((cx + r_deg + 180.0) / 360.0 * SW_WORLD)
        min_sy = max(0, int((90.0 - (cy + r_deg)) / 180.0 * SH_WORLD))
        max_sy = min(SH_WORLD - 1, int((90.0 - (cy - r_deg)) / 180.0 * SH_WORLD))
        for sy in range(min_sy, max_sy + 1):
            plat = 90.0 - (sy / float(SH_WORLD)) * 180.0
            dlat = plat - cy
            srow = sy * SW_WORLD
            for sx_i in range(min_sx, max_sx + 1):
                sx = sx_i % SW_WORLD
                plon = (sx / float(SW_WORLD)) * 360.0 - 180.0
                dlon = (plon - cx + 180.0) % 360.0 - 180.0
                dist_sq = dlon*dlon + dlat*dlat
                if dist_sq < r_deg * r_deg:
                    dist = math.sqrt(dist_sq)
                    val = inten * math.exp(-3.0 * (dist / r_deg))
                    city_grid[srow + sx] += val

    for wy in range(H_WORLD):
        lat = lat_table[wy]
        if -58.0 < lat < 68.0:
            y = PAD_Y + wy
            sy = (wy * SH_WORLD) // H_WORLD
            s_row = sy * SW_WORLD
            fine_row = (S_PAD_Y + sy) * SW
            row_idx = y * WIDTH
            w_row_idx = wy * WIDTH

            for x in range(WIDTH):
                if land_grid[w_row_idx + x] == 1:
                    lon = lon_table[x]
                    sx = (x * SW_WORLD) // WIDTH
                    s_idx = s_row + sx
                    inten = city_grid[s_idx]

                    if 22.0 <= lat <= 31.0 and abs(lon - (31.2 + (lat-20)*0.06)) < 0.4:
                        inten += 0.85

                    if inten > 0.03:
                        spark = cloud_fine[fine_row + ((x * SW) // WIDTH)]
                        light_val = min(1.0, inten * (0.65 + 0.7 * spark))
                        px = (row_idx + x) * 3
                        night_rgb[px] = int(min(255, light_val * 255))
                        night_rgb[px + 1] = int(min(255, light_val * 205))
                        night_rgb[px + 2] = int(min(255, light_val * 115))

    write_png_rgb(os.path.join(ASSETS_DIR, "earth-night.png"), WIDTH, HEIGHT, night_rgb)
    print(f"6. Night lights texture completed ({time.time() - t0:.2f}s)")

    print(f"✨ All textures generated in {time.time() - t_start:.2f}s total!")

if __name__ == "__main__":
    main()
