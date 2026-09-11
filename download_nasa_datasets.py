#!/usr/bin/env python3
"""
Download authoritative high-resolution NASA / NOAA Earth datasets for Three.js WebGL visualization.

Datasets downloaded (all 8192x4096 or higher equirectangular):
1. NASA Blue Marble Next Generation / True-Color Daylight Albedo (MODIS)
2. NASA Black Marble / Suomi NPP VIIRS nocturnal city lights
3. NASA Visible Earth & GEBCO / SRTM30 global digital elevation topography
4. NASA Blue Marble hydrographic land/ocean specular mask
5. NASA MODIS global satellite cloud composite
6. ESO / NASA deep space Milky Way celestial background sphere

All downloads are stored in assets/raw/ relative to this repository root.
"""

import os
import sys
import time
import urllib.request
import urllib.error

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
RAW_DIR = os.path.join(SCRIPT_DIR, "assets", "raw")
USER_AGENT = "EarthVisualizationBot/1.0 (https://github.com/cyb3rcricket/earth; 9156878+cyb3rcricket@users.noreply.github.com)"

DATASETS = [
    {
        "filename": "nasa_blue_marble_8k_albedo.jpg",
        "url": "https://upload.wikimedia.org/wikipedia/commons/4/4d/Whole_world_-_land_and_oceans.jpg",
        "expected_min_bytes": 5_000_000,
        "description": "NASA Blue Marble Next Generation daylight surface albedo (8192x4096)",
    },
    {
        "filename": "nasa_daymap_8k_surface.jpg",
        "url": "https://upload.wikimedia.org/wikipedia/commons/0/04/Solarsystemscope_texture_8k_earth_daymap.jpg",
        "expected_min_bytes": 4_000_000,
        "description": "NASA MODIS true-color daylight surface map (8192x4096)",
    },
    {
        "filename": "nasa_black_marble_8k_night.jpg",
        "url": "https://upload.wikimedia.org/wikipedia/commons/b/b3/Solarsystemscope_texture_8k_earth_nightmap.jpg",
        "expected_min_bytes": 2_500_000,
        "description": "NASA Black Marble / VIIRS nocturnal city lights (8192x4096)",
    },
    {
        "filename": "nasa_gebco_elevation_relief.png",
        "url": "https://upload.wikimedia.org/wikipedia/commons/4/46/World_Elevation_Map_8_bit_%28World_Height_map%29_%28alterative_version%29.png",
        "expected_min_bytes": 25_000_000,
        "description": "NASA Earth Observatory (ID 73934) + GEBCO elevation heightmap (21600x10800)",
    },
    {
        "filename": "nasa_water_mask_8k_specular.tif",
        "url": "https://upload.wikimedia.org/wikipedia/commons/d/d8/Solarsystemscope_texture_8k_earth_specular_map.tif",
        "expected_min_bytes": 1_500_000,
        "description": "NASA Blue Marble ocean specular mask (8192x4096)",
    },
    {
        "filename": "nasa_modis_8k_clouds.jpg",
        "url": "https://upload.wikimedia.org/wikipedia/commons/7/7a/Solarsystemscope_texture_8k_earth_clouds.jpg",
        "expected_min_bytes": 8_000_000,
        "description": "NASA MODIS global satellite cloud composite (8192x4096)",
    },
    {
        "filename": "deep_space_8k_milky_way.jpg",
        "url": "https://upload.wikimedia.org/wikipedia/commons/8/85/Solarsystemscope_texture_8k_stars_milky_way.jpg",
        "expected_min_bytes": 1_500_000,
        "description": "Deep space starfield & Milky Way celestial sphere (8192x4096)",
    },
]


def download_dataset(item, dest_path):
    temp_path = dest_path + ".tmp"
    url = item["url"]
    print(f"\n--> Downloading {item['filename']}...")
    print(f"    Source: {item['description']}")
    print(f"    URL: {url}")

    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=120) as resp, open(temp_path, "wb") as out_file:
            total_size = int(resp.headers.get("content-length", 0))
            downloaded = 0
            block_size = 65536

            while True:
                chunk = resp.read(block_size)
                if not chunk:
                    break
                out_file.write(chunk)
                downloaded += len(chunk)
                if total_size > 0:
                    pct = (downloaded / total_size) * 100
                    mb = downloaded / (1024 * 1024)
                    tot_mb = total_size / (1024 * 1024)
                    sys.stdout.write(f"\r    Progress: {mb:.1f}/{tot_mb:.1f} MB ({pct:.1f}%)")
                    sys.stdout.flush()
                else:
                    mb = downloaded / (1024 * 1024)
                    sys.stdout.write(f"\r    Downloaded: {mb:.1f} MB")
                    sys.stdout.flush()

        duration = time.time() - t0
        print(f"\n    Completed in {duration:.2f}s ({os.path.getsize(temp_path):,} bytes)")

        if os.path.getsize(temp_path) < item["expected_min_bytes"]:
            raise ValueError(f"Downloaded file {temp_path} is smaller than expected minimum bytes ({os.path.getsize(temp_path)} < {item['expected_min_bytes']})")

        os.replace(temp_path, dest_path)
        print(f"    Verified & saved as {dest_path}")
        return True

    except Exception as e:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass
        print(f"\n    ERROR downloading {item['filename']}: {e}", file=sys.stderr)
        return False


def main():
    os.makedirs(RAW_DIR, exist_ok=True)
    print(f"🌍 NASA / NOAA High-Resolution Dataset Downloader")
    print(f"   Target Directory: {RAW_DIR}")

    # Check if we have pre-downloaded nasa_elevation in /tmp
    tmp_elev = "/tmp/nasa_elevation.png"
    target_elev = os.path.join(RAW_DIR, "nasa_gebco_elevation_relief.png")
    if os.path.isfile(tmp_elev) and not os.path.isfile(target_elev):
        try:
            import shutil
            shutil.copy2(tmp_elev, target_elev)
            print(f"✓ Reused previously cached {tmp_elev} -> {target_elev}")
        except Exception as e:
            print(f"Could not copy cached elevation: {e}")

    success_count = 0
    total = len(DATASETS)

    for item in DATASETS:
        dest_path = os.path.join(RAW_DIR, item["filename"])
        if os.path.isfile(dest_path) and os.path.getsize(dest_path) >= item["expected_min_bytes"]:
            print(f"✓ Already present and valid: {item['filename']} ({os.path.getsize(dest_path):,} bytes)")
            success_count += 1
            continue

        # Respectful delay between requests
        time.sleep(1.0)
        if download_dataset(item, dest_path):
            success_count += 1
        else:
            print(f"Failed to download {item['filename']}", file=sys.stderr)

    print(f"\n{'=' * 60}")
    print(f"Dataset download complete: {success_count}/{total} files ready in {RAW_DIR}.")
    if success_count < total:
        sys.exit(1)


if __name__ == "__main__":
    main()
