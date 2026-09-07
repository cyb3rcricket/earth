# Planet Earth • Photorealistic 3D WebGL Visualization

A high-fidelity, physically-principled 3D interactive visualization of Planet Earth rendered in real-time with **Three.js (WebGL r160)**. The engine features a multi-layered celestial hierarchy, custom GLSL physically-inspired shaders, authentic geographic albedo and topographic relief, land-masked nocturnal city lights, dynamic ocean specular glints, atmospheric Rayleigh limb scattering, and an orbital telemetry flight deck.

---

## Table of Contents

- [Overview & Visual Architecture](#overview--visual-architecture)
- [Key Features](#key-features)
- [Directory & File Structure](#directory--file-structure)
- [Asset Documentation](#asset-documentation)
  - [Active Assets (WebGL Production)](#1-active-assets-webgl-production)
  - [Source / Raw Satellite Assets](#2-source--raw-satellite-assets)
  - [Legacy / Historical Prototype Assets](#3-legacy--historical-prototype-assets)
- [Texture Pipeline & CLI Guide](#texture-pipeline--cli-guide)
  - [Standard 2:1 Equirectangular Generator (`build_webgl_textures.py`)](#standard-21-equirectangular-generator-build_webgl_texturespy)
  - [Enhanced Square Texture Processor (`process_enhanced_assets.py`)](#enhanced-square-texture-processor-process_enhanced_assetspy)
  - [Procedural Asset Generator (`generate_assets.py`)](#procedural-asset-generator-generate_assetspy)
- [Running Locally](#running-locally)
- [Controls, Physics & Telemetry](#controls-physics--telemetry)
  - [Pointer & Touch Controls](#pointer--touch-controls)
  - [Keyboard Navigation](#keyboard-navigation)
  - [Orbital Telemetry & Presentation HUD](#orbital-telemetry--presentation-hud)
  - [Accessibility & Motion Preferences](#accessibility--motion-preferences)
- [Shader Architecture](#shader-architecture)
  - [Optical Foundations & Atmospheric Physics](#1-optical-foundations--atmospheric-physics)
  - [High-Precision Normal Mapping & Relief Self-Shadowing](#2-high-precision-normal-mapping--relief-self-shadowing)
  - [Shader Breakdown](#3-shader-breakdown)

---

## Overview & Visual Architecture

Planet Earth is rendered in a physically-principled Three.js WebGL viewport featuring:

```
Celestial Universe Scene
├── Skybox Background (Equirectangular Deep Space Sphere)
├── Celestial Star Sphere (Radius: 150.0, Inverted Sphere)
├── Deep Space Star Particles (1,800 stars with 3 stellar classification tints)
└── Axial Tilt Group (Fixed 23.44° Obliquity of the Ecliptic: degToRad(-23.44))
    ├── Earth Surface Mesh (Radius: 1.0, 128×128 SphereGeometry, Custom GLSL)
    ├── Cloud Layer Mesh (Radius: 1.008, 128×128 SphereGeometry, Custom GLSL)
    ├── Atmosphere Rayleigh Scattering Shell (Radius: 1.036, Single-Scattering GLSL)
    └── Outer Corona Glow Shell (Radius: 1.10, Forward Mie Glare GLSL)
```

- **World-Space Fixed Sunlight**: The Sun is positioned in world coordinates at vector `(-1.4, 0.8, 1.2).normalize()`, shining from the upper-left and slightly toward the viewer. As the user rotates the Earth or auto-rotation advances, geography moves naturally beneath a fixed solar terminator, day/night boundary, and twilight Rayleigh fringe.
- **Independent Atmospheric Circulation**: The cloud deck orbits at an independent rotational velocity (~1.18× surface rotation rate) at radius `1.008`, casting soft projective shadows across continents and oceans below.
- **Tone Mapping & Exposure**: ACES Filmic tone mapping (`THREE.ACESFilmicToneMapping`) with an exposure of `1.05` delivers high-dynamic-range rendering of bright sunglints and subtle nighttime city illuminations without clipping or banding.

---

## Key Features

- **Multi-Layer Celestial Hierarchy**: Separate scene graph nodes for planetary tilt, surface rotation, cloud rotation, and static cosmic environments.
- **Custom GLSL Shaders**:
  - Blinn-Phong specular sunglint on water bodies with zero specular reflection on landmasses.
  - High-precision precomputed tangent-space normal mapping (`normal.png`) with equirectangular metric tensor compensation ($\text{scale}_x = 1 / \max(0.06, \sin(\pi v))$), delivering sharp, undistorted mountain relief across all latitudes (Himalayas, Andes, Alps, Rockies).
  - Directional horizon relief self-shadowing along the terminator, where adjacent mountain peaks cast sharp, jagged cast shadows across valleys and plains at grazing sun angles.
  - Singularity-free analytic orthonormal tangent frame $(T, B, N)$ eliminating polar distortions.
  - Rayleigh sunset/twilight rim scattering with warm golden-orange coloration along the day/night terminator.
  - Authentically masked city lights glowing in golden-amber strictly on land (no artificial light pollution in oceans).
  - Dynamic projective cloud shadow mapping onto the daytime surface.
- **Deep Space Environment**: A panoramic starfield background combined with 1,800 procedural GPU particle stars categorized into stellar types (cool blue-white O/B stars, warm golden-amber K/M stars, and neutral white A/F stars).
- **Physics-Based Orbital Controls**: Unified pointer interaction supporting mouse, touch, and trackpad gestures with rotational inertia, friction damping ($0.955$), clamped latitude ($-85^\circ$ to $+85^\circ$), and smooth camera zooming ($1.55$ to $6.0$ units).
- **Live Orbital Telemetry**: Dynamic readouts tracking simulated altitude (3,500 km LEO to 35,786 km GEO), sub-satellite geographic coordinates, orbital inclination ($23.44^\circ$), and rotation period.
- **Presentation HUD**: Non-intrusive collapsible panel allowing real-time adjustment of planetary rotation speed, cloud density, atmospheric glow, and shadow intensity.

---

## Directory & File Structure

```
earth/
├── assets/
│   ├── earth/                          # Active 2:1 WebGL textures (4096x2048 production)
│   │   ├── albedo.png                  # Active: 4096x2048 RGB NASA Blue Marble Next Generation
│   │   ├── bump.png                    # Active: 4096x2048 RGB NASA Earth Observatory & GEBCO elevation relief
│   │   ├── clouds.png                  # Active: 4096x2048 RGBA NASA MODIS global cloud composite
│   │   ├── night.png                   # Active: 4096x2048 RGB NASA Black Marble VIIRS city lights
│   │   ├── specular.png                # Active: 4096x2048 RGB NASA Blue Marble ocean specular mask
│   │   ├── stars.jpg                   # Active: 4096x2048 RGB Milky Way celestial sphere
│   │   ├── daylight-surface.png        # Intermediate/Legacy: 2048x2048 square composite
│   │   ├── night-lights.png            # Intermediate/Legacy: 2048x2048 square night lights
│   │   ├── cloud-shadow.png            # Intermediate/Legacy: 2048x2048 square cloud shadow
│   │   ├── surface-detail.png          # Intermediate/Legacy: 2048x2048 square terrain relief
│   │   └── atmosphere-mask.png         # Intermediate/Legacy: 1024x1024 limb mask
│   ├── raw/                            # Authoritative 8K/21K source datasets
│   │   ├── nasa_blue_marble_8k_albedo.jpg      # 8192x4096 NASA Blue Marble true-color albedo
│   │   ├── nasa_daymap_8k_surface.jpg          # 8192x4096 NASA MODIS true-color surface map
│   │   ├── nasa_black_marble_8k_night.jpg      # 8192x4096 NASA Black Marble / VIIRS nocturnal lights
│   │   ├── nasa_gebco_elevation_relief.png     # 21600x10800 NASA & GEBCO digital elevation model
│   │   ├── nasa_water_mask_8k_specular.tif     # 8192x4096 NASA Blue Marble ocean/land mask
│   │   ├── nasa_modis_8k_clouds.jpg            # 8192x4096 NASA MODIS satellite cloud composite
│   │   ├── deep_space_8k_milky_way.jpg         # 8192x4096 Deep space Milky Way starfield
│   │   └── [historical archives]               # Earlier reference textures
│   ├── earth-clouds.png                # Legacy: 2048x2048 2D CSS prototype clouds
│   ├── earth-night.png                 # Legacy: 2048x2048 2D CSS prototype night lights
│   └── earth-surface.png               # Legacy: 2048x2048 2D CSS prototype surface
├── js/
│   ├── controls.js                     # Planetary kinematics, inertia, zoom, & keyboard input
│   ├── main.js                         # WebGL engine, Three.js setup, scene graph, render loop
│   ├── shaders.js                      # Custom GLSL shaders (Surface, Clouds, Atmosphere, Corona)
│   └── three.module.js                 # Three.js r160 ES Module
├── download_nasa_datasets.py           # Automated acquisition tool for authentic 8K/21K datasets
├── build_webgl_textures.py             # Active production texture builder (2:1 equirectangular)
├── process_enhanced_assets.py          # Enhanced square asset processor (with polar extensions)
├── generate_assets.py                  # Procedural texture generator (legacy prototype pipeline)
├── index.html                          # Application entry point, canvas, HUD & telemetry DOM
├── script.js                           # Legacy 2D CSS DOM rotation engine (historical)
├── styles.css                          # Viewport styling, HUD glassmorphism, responsive telemetry
└── README.md                           # Project documentation
```

---

## Asset Documentation

Assets are strictly classified into three categories: **Active Assets**, **Source / Raw Datasets**, and **Legacy / Historical Assets**.

### 1. Active Assets (WebGL Production - 4096×2048)

These are the primary 2:1 equirectangular textures loaded at runtime by `js/main.js` via `THREE.TextureLoader`:

| Asset Path | Dimensions | Channels | Authoritative Source & Shader Role |
| :--- | :--- | :--- | :--- |
| `assets/earth/albedo.png` | 4096×2048 | RGB (8-bit) | **NASA Blue Marble Next Generation**: True-color satellite albedo captured by NASA's MODIS sensors. Features authentic continental biomes, vegetated canopies, arid deserts, polar ice, and shallow coastal turquoise bathymetry (Caribbean, Great Barrier Reef). Sampled by `EarthSurfaceShader.uDayTexture`. |
| `assets/earth/bump.png` | 4096×2048 | RGB (8-bit) | **NASA Earth Observatory (ID 73934) & GEBCO**: Digital elevation model (DEM) encoding global topographic relief. Sampled by `EarthSurfaceShader.uBumpTexture` exclusively in the grazing terminator zone for 6-step directional mountain horizon self-shadowing. |
| `assets/earth/normal.png` | 4096×2048 | RGB (8-bit) | **Precomputed Tangent-Space Normal Map**: High-precision non-color linear tangent-space normal map precomputed from elevation relief with equirectangular metric tensor compensation and land masking. Sampled by `EarthSurfaceShader.uNormalTexture` for terrain surface lighting, eliminating the per-fragment 3×3 Sobel reconstruction. |
| `assets/earth/night.png` | 4096×2048 | RGB (8-bit) | **NASA Black Marble / Suomi NPP VIIRS**: Nocturnal city lights mapped with high geographic precision. Processed with land-masking to guarantee zero light spill over open oceans, with warm golden-amber incandescent glow. Sampled by `EarthSurfaceShader.uNightTexture`. |
| `assets/earth/specular.png` | 4096×2048 | RGB (8-bit) | **NASA Blue Marble Hydrography Mask**: High-contrast binary water mask ($1.0$ on oceans, seas, and major lakes, $0.0$ on land). Modulates Blinn-Phong specular sunglint on water bodies. Sampled by `EarthSurfaceShader.uSpecularTexture`. |
| `assets/earth/clouds.png` | 4096×2048 | RGBA (8-bit) | **NASA MODIS Global Cloud Composite**: Satellite-derived cloud coverage with optical depth mapped to alpha transparency ($0.0$ for clear skies, up to $0.95$ for storm centers). Casts dynamic ground shadows on terrain and renders independently on the cloud sphere. Sampled by `CloudsShader.uCloudsTexture` and `EarthSurfaceShader.uCloudsTexture`. |
| `assets/earth/stars.jpg` | 4096×2048 | RGB (8-bit) | **Milky Way Celestial Sphere**: Panoramic deep space starfield capture featuring the Milky Way galactic core and interstellar dust clouds. Applied to outer sphere (`radius: 150`, `THREE.BackSide`). |

### 2. Source / Raw Datasets (`assets/raw/`)

Stored in `assets/raw/`, these are authentic high-resolution master datasets (8192×4096 or 21600×10800) downloaded by `download_nasa_datasets.py`:

- `nasa_blue_marble_8k_albedo.jpg` (8192×4096): NASA Blue Marble Next Generation master albedo.
- `nasa_daymap_8k_surface.jpg` (8192×4096): NASA MODIS true-color daylight surface map.
- `nasa_black_marble_8k_night.jpg` (8192×4096): NASA Black Marble / VIIRS nocturnal luminescence.
- `nasa_gebco_elevation_relief.png` (21600×10800): NASA Earth Observatory & GEBCO global elevation map.
- `nasa_water_mask_8k_specular.tif` (8192×4096): NASA Blue Marble hydrographic land/water mask.
- `nasa_modis_8k_clouds.jpg` (8192×4096): NASA MODIS global satellite cloud composite.
- `deep_space_8k_milky_way.jpg` (8192×4096): High-resolution cosmic Milky Way panorama.

### 3. Licensing & Attribution

- **NASA Datasets**: Public domain (United States Government work under 17 U.S.C. § 105). Credit: NASA Earth Observatory, NASA Visible Earth, NASA Goddard Space Flight Center.
- **Solar System Scope Textures**: Creative Commons Attribution 4.0 International (CC BY 4.0). Credit: Solar System Scope ([solarsystemscope.com](https://www.solarsystemscope.com/)) based on NASA elevation and imagery data.
- **GEBCO Topography**: Open-access bathymetric and topographic data used in accordance with the GEBCO license agreement.

### 4. Legacy / Historical Prototype Assets

- **In `assets/` root**: `assets/earth-surface.png`, `assets/earth-clouds.png`, `assets/earth-night.png` (2048×2048 procedural square prototypes).
- **In project root**: `script.js` (legacy 2D DOM / CSS prototype controller).

---

## Texture Pipeline & CLI Guide

The texture processing scripts use **Python 3** with macOS native `sips` acceleration and pure standard library (`struct`, `zlib`, `argparse`). No third-party Python dependencies (such as Pillow) are required. All paths resolve dynamically relative to the repository root.

### Dataset Downloader (`download_nasa_datasets.py`)

Automates downloading all 8K/21K master datasets from verified public repositories into `assets/raw/`:

```bash
python3 download_nasa_datasets.py
```

### Standard 2:1 Equirectangular Generator (`build_webgl_textures.py`)

`build_webgl_textures.py` is the **production build tool** that converts the master datasets in `assets/raw/` into optimized 2:1 equirectangular textures in `assets/earth/`.

#### Usage & Options

```bash
python3 build_webgl_textures.py [OPTIONS]
```

| Flag | Default | Description |
| :--- | :--- | :--- |
| `--preset {1k,2k,4k,8k}` | `4k` | Resolution preset helper (`1k`: 1024×512, `2k`: 2048×1024, `4k`: 4096×2048, `8k`: 8192×4096). |
| `--width WIDTH` | `4096` | Output texture width in pixels (overrides preset). |
| `--height HEIGHT` | `2048` | Output texture height in pixels (overrides preset). |
| `--raw-dir PATH` | `./assets/raw` | Input directory containing raw NASA source textures. |
| `--earth-dir PATH` | `./assets/earth` | Output directory for WebGL textures. |
| `--seam-width WIDTH` | `64` | Symmetric horizontal smoothstep cross-fade seam blend width in pixels along the $180^\circ$ meridian. |
| `--normal-map` | `False` | Generate high-precision tangent-space normal map (`normal.png`) from elevation relief as part of the full build. |
| `--normal-only` | `False` | Fast path: generate only `normal.png` using existing `bump.png` and `specular.png` (or raw source). |
| `--normal-scale SCALE` | `2.05` | Slope scale multiplier for tangent-space normal gradient (default: 2.05, matching shader `uBumpScale`). |
| `--dry-run` | `False` | Inspect input paths, target directories, and asset existence without writing files. |

#### CLI Examples

```bash
# Display help and options
python3 build_webgl_textures.py --help

# Generate default high-resolution 4K (4096x2048) production textures including normal.png
python3 build_webgl_textures.py --normal-map

# Fast rebuild of only normal.png at default 4K resolution (under 10s)
python3 build_webgl_textures.py --normal-only

# Generate 1K, 2K, or 8K normal maps
python3 build_webgl_textures.py --normal-only --preset 1k
python3 build_webgl_textures.py --normal-only --preset 2k
python3 build_webgl_textures.py --normal-only --preset 8k

# Generate ultra-high-resolution 8K (8192x4096) full texture suite with normal map
python3 build_webgl_textures.py --preset 8k --normal-map

# Generate 2K (2048x1024) performance textures with normal map
python3 build_webgl_textures.py --preset 2k --normal-map

# Validate sources and configuration without writing files
python3 build_webgl_textures.py --dry-run
```

### Enhanced Square Texture Processor (`process_enhanced_assets.py`)

Generates square (1:1 aspect ratio) textures with polar padding for Arctic and Antarctic ice sheets:

```bash
# Standard 2048x2048 build
python3 process_enhanced_assets.py

# 4K preset build
python3 process_enhanced_assets.py --preset 4k

# Dry run inspection
python3 process_enhanced_assets.py --dry-run
```

### Procedural Asset Generator (`generate_assets.py`)

Generates fully procedural Earth textures (coastlines, biomes, noise clouds, night lights) without external satellite photos:

```bash
python3 generate_assets.py --assets-dir ./assets
```

---

## Running Locally

Because the application uses modern ES Modules (`import * as THREE from './three.module.js'`) and loads textures via WebGL `TextureLoader`, the project must be served through an HTTP/HTTPS web server (rather than opened directly via `file://`).

### Quick Start with Python

From the project root directory:

```bash
# Python 3 built-in HTTP server
python3 -m http.server 8000
```

Open your browser and navigate to:
```
http://localhost:8000
```

### Quick Start with Node.js

Alternatively, use any static file server:

```bash
# Using npx serve
npx serve .

# Using http-server
npx http-server -p 8000
```

---

## Controls, Physics & Telemetry

### Pointer & Touch Controls

- **Drag (Mouse / Single Touch / Trackpad)**:
  - Rotates the planet across longitude (east/west) and latitude (north/south).
  - Rotation vectors are projected directly into Earth's tilted axial reference frame ($-23.44^\circ$).
- **Rotational Inertia & Momentum**:
  - Releasing during a drag gesture applies realistic angular momentum with friction damping ($0.955$ per frame).
  - Fling velocity is safely clamped to prevent disorienting spins.
- **Latitude Clamping**:
  - Vertical tilt is clamped to $[-85.0^\circ, +85.0^\circ]$, preventing gimbal lock and unnatural polar inversion.
- **Camera Zoom (Mouse Wheel / Two-Finger Pinch)**:
  - Smooth distance zooming clamped between $1.55$ (low orbit / continent inspection) and $6.0$ units (deep space vantage).
  - Adaptive zoom scaling provides finer control when zoomed in close to the surface.
- **Auto-Rotation & Idle Resume**:
  - Earth continuously rotates at an authentic sidereal rate (default 90-second period).
  - Any user interaction immediately pauses auto-rotation. After $2.5$ seconds of idle time, auto-rotation smoothly ramps back up over $1.5$ seconds.

### Keyboard Navigation

| Key | Action |
| :--- | :--- |
| `ArrowLeft` | Rotate west by $4.0^\circ$ increments |
| `ArrowRight` | Rotate east by $4.0^\circ$ increments |
| `ArrowUp` | Tilt north by $4.0^\circ$ increments (clamped to $+85^\circ$) |
| `ArrowDown` | Tilt south by $4.0^\circ$ increments (clamped to $-85^\circ$) |
| `Home` | Reset sub-satellite orientation to Prime Meridian / Equator ($0.0^\circ\text{ N}, 0.0^\circ\text{ E}$) |
| `Spacebar` | Toggle pause / resume planetary rotation |

### Orbital Telemetry & Presentation HUD

- **Live Telemetry Readout** (bottom-left glassmorphism badge):
  - **ALTITUDE**: Dynamic calculation based on camera distance:
    $$\text{Altitude} = (\text{CameraDistance} - 1.0) \times 6,371\text{ km}$$
    Displays altitude from ~3,500 km in close zoom up to geosynchronous orbits (>35,000 km).
  - **INCLINATION**: Fixed axial obliquity readout ($23.44^\circ$).
  - **SUB-SATELLITE**: Real-time geographic coordinates ($Lat^\circ\text{ N/S}, Lon^\circ\text{ E/W}$) directly under the camera vantage point.
  - **PERIOD**: Current rotational period in seconds.
- **Presentation HUD** (bottom-right collapsible panel):
  - **Rotation Speed**: Adjust planetary rotation period between 20s and 180s.
  - **Cloud Density**: Slider from 0% (clear sky) to 100% (dense cloud cover).
  - **Atmosphere Glow**: Slider from 0% (vacuum / space station view) to 150% (luminous limb scattering).
  - **Shadow Depth**: Adjust shadow intensity of cloud deck cast onto the surface (60% to 100%).
  - **Pause / Reset**: Toggle rotation state or restore all parameters to default.

### Accessibility & Motion Preferences

The application listens to the operating system's `prefers-reduced-motion` media query:
- When reduced motion is detected, auto-rotation and rotational inertia are disabled automatically.
- The 3D canvas includes explicit `role="region"` and `aria-label` tags for screen readers, and is keyboard-focusable (`tabindex="0"`).

---

## Shader Architecture

The custom GLSL shaders (`js/shaders.js`) implement physically-principled planetary illumination and single-scattering optics:

### 1. Optical Foundations & Atmospheric Physics

#### Rayleigh Scattering ($\lambda^{-4}$ Dependence)
Rayleigh scattering occurs when solar photons scatter elastically off molecular nitrogen ($\text{N}_2$) and oxygen ($\text{O}_2$) particles much smaller than the light's wavelength. The scattering coefficient $\boldsymbol{\beta}_R(\lambda)$ varies inversely with the fourth power of wavelength:

$$\boldsymbol{\beta}_R(\lambda) \propto \frac{1}{\lambda^4}$$

For primary spectral bands—red ($\lambda_r = 650\text{ nm}$), green ($\lambda_g = 570\text{ nm}$), and blue ($\lambda_b = 475\text{ nm}$)—the relative scattering ratios are:

$$\left(\frac{475}{650}\right)^4 \approx 0.284, \quad \left(\frac{475}{570}\right)^4 \approx 0.482, \quad \left(\frac{475}{475}\right)^4 = 1.000$$

Calibrated to normalized planetary units (Earth radius $R_p = 1.0$), the Rayleigh scattering vector is:

$$\boldsymbol{\beta}_R = \text{vec3}(5.8, 13.5, 33.1) \times 2.0 = \text{vec3}(11.6, 27.0, 66.2)$$

Because blue light scatters $\sim 5.7\times$ more intensely than red, the daytime sky and daylight limb glow in authentic sapphire blue.

#### Rayleigh Phase Function
Rayleigh scattering exhibits symmetric forward and backward dipole scattering:

$$P_R(\theta) = \frac{3}{16\pi} \left(1 + \cos^2\theta\right)$$

where $\cos\theta = \mathbf{D}_{\text{ray}} \cdot \mathbf{L}_{\text{sun}}$ is the cosine of the scattering angle between the view ray and the incident solar vector.

#### Mie Aerosol Scattering & Henyey-Greenstein Forward Haze
Scattering off atmospheric aerosols, water droplets, and dust is governed by Mie theory. Mie scattering is largely wavelength-independent ($\boldsymbol{\beta}_M = \text{vec3}(4.0)$), and its angular distribution is modeled via the Henyey-Greenstein phase function:

$$P_M(\theta, g) = \frac{1}{4\pi} \frac{1 - g^2}{\left(1 + g^2 - 2g\cos\theta\right)^{1.5}}$$

with forward anisotropy parameter $g \approx 0.78$ in the atmospheric shell and $g \approx 0.82$ in the outer coronal halo. As the viewer looks toward the sun along the planetary limb ($\cos\theta \to 1$), the denominator collapses, producing the brilliant forward-scattered solar halo.

#### Beer-Lambert Law & Sunset Extinction
Light propagating through an absorbing and scattering medium experiences exponential extinction:

$$T(\mathbf{a}, \mathbf{b}) = \exp\left( -\int_{\mathbf{a}}^{\mathbf{b}} \left( \boldsymbol{\beta}_R \rho_R(h(s)) + \boldsymbol{\sigma}_{e,M} \rho_M(h(s)) \right) \, ds \right)$$

Along grazing sunset/sunrise paths near the terminator ($\mathbf{N} \cdot \mathbf{L} \approx 0$), the solar optical depth $\boldsymbol{\tau}_{\text{sun}}$ increases up to $20\times$. Because $\beta_{R,\text{blue}} \gg \beta_{R,\text{red}}$, blue and cyan wavelengths are completely extinguished ($\exp(-\tau_{\text{blue}}) \to 0$), transmitting purely golden amber and ruby red light into the twilight horizon.

#### Exponential Density Falloff & Boundary Smoothing
Atmospheric density drops exponentially with altitude $h = \|\mathbf{x}\| - R_p$:

$$\rho_R(h) = \exp\left(-\frac{h}{H_R}\right) \cdot f_{\text{taper}}(h), \quad \rho_M(h) = \exp\left(-\frac{h}{H_M}\right) \cdot f_{\text{taper}}(h)$$

with scale heights $H_R = 0.0080$ (~8 km) and $H_M = 0.0032$ (~3.2 km). To guarantee zero harsh boundaries or "hula hoop" ring artifacts at the outer shell radius ($R_{\text{atmo}} = 1.036$), a smooth cubic Hermite taper smoothly drives density to identically zero:

$$f_{\text{taper}}(h) = 1.0 - \text{smoothstep}\left(0.70, 1.0, \frac{h}{R_{\text{atmo}} - R_p}\right)$$

---

### 2. High-Precision Normal Mapping & Relief Self-Shadowing

The terrain lighting architecture separates surface normal lighting from elevation-based horizon shadowing:
- **`normal.png`** (Tangent-Space Normal Map): Handles surface normal perturbation and fine topographic relief lighting across all illuminated landmasses via a single texture sample.
- **`bump.png`** (Digital Elevation Model): Preserved exclusively for the 6-step directional terrain horizon self-shadow raymarch along the low-angle solar terminator.

#### Offline Precomputed Normal Map Generation
Evaluating a $3 \times 3$ Sobel neighborhood dynamically on the GPU required 9 texture samples of `uBumpTexture`, coordinate math, trigonometric latitude metric scaling, and derivative calculations for every rendered surface fragment. To optimize GPU performance, this operation is precomputed offline into `assets/earth/normal.png` by `build_webgl_textures.py`.

A symmetric 2D $3 \times 3$ Sobel filter evaluates the continuous partial spatial derivatives from the elevation data:

$$G_u = \frac{\partial h}{\partial u} = \frac{1}{8} \begin{bmatrix} -1 & 0 & 1 \\ -2 & 0 & 2 \\ -1 & 0 & 1 \end{bmatrix} * h(u, v), \quad G_v = \frac{\partial h}{\partial v} = \frac{1}{8} \begin{bmatrix} 1 & 2 & 1 \\ 0 & 0 & 0 \\ -1 & -2 & -1 \end{bmatrix} * h(u, v)$$

*(Note: in equirectangular image pixel coordinates where row index $y$ increases southward while UV coordinate $v$ increases northward, $G_v$ computes north-minus-south elevation gradient).*

#### Equirectangular Metric Tensor Scale Compensation
In a 2:1 equirectangular projection, lines of longitude converge toward the poles as $\cos(\text{lat}) = \sin(\pi v)$. Without metric tensor compensation, horizontal pixel spacing $\Delta u$ represents a physically smaller distance at high latitudes than at the equator, causing severe flattening of mid- and high-latitude topography. The exact metric compensation factor is:

$$\text{scale}_x(v) = \frac{1.0}{\max(0.06, \sin(\pi v))}$$

The physical gradient vector components are:

$$G_x = G_u \cdot \text{scale}_x(v) \cdot \mu_{\text{bump}} \cdot (1 - M_{\text{ocean}}), \quad G_y = G_v \cdot \mu_{\text{bump}} \cdot (1 - M_{\text{ocean}})$$

where $\mu_{\text{bump}}$ is the bump scale factor (`scale_factor = 2.05`) and $M_{\text{ocean}} \in [0, 1]$ is the hydrographic specular mask (ensuring ocean waters remain completely flat $(128, 128, 255)$).

The tangent-space unit normal $\hat{\mathbf{n}}_{\text{tan}} = \text{normalize}(-G_x, -G_y, 1.0)$ is encoded into 8-bit RGB channels $[0, 255]$:
- $\text{R} = \text{int}((\hat{n}_x \times 0.5 + 0.5) \times 255)$ (Tangent X: East / West, $+u$)
- $\text{G} = \text{int}((\hat{n}_y \times 0.5 + 0.5) \times 255)$ (Tangent Y: North / South, $+v$)
- $\text{B} = \text{int}((\hat{n}_z \times 0.5 + 0.5) \times 255)$ (Tangent Z: Outward Normal, $+z$)

The texture is treated strictly as **linear non-color data** (`THREE.NoColorSpace`), preventing any gamma distortion.

#### Runtime Tangent-Space Normal Decoding & World Transformation
In `EarthSurfaceShader`, the precomputed normal map is sampled once:

$$\mathbf{n}_{\text{tan}} = \text{texture2D}(uNormalTexture, \mathbf{uv}).\text{rgb} \times 2.0 - 1.0$$

The tangent-space vector is modulated by `uNormalScale` and the runtime `landMask`, then transformed into world space using the singularity-free analytic orthonormal tangent frame $(T, B, N)$:

$$\mathbf{N}_{\text{perturbed}} = \text{normalize}\left(n_{\text{tan}, x} \cdot \mathbf{T} + n_{\text{tan}, y} \cdot \mathbf{B} + n_{\text{tan}, z} \cdot \mathbf{N}\right)$$

#### Singularity-Free Orthonormal Tangent Frame
To eliminate the classical polar gimbal lock singularity $\mathbf{N} \times (0, 1, 0) \to \mathbf{0}$, the exact planetary spin axis $\mathbf{U}_{\text{world}} = \text{normalize}(\mathbf{M}_{\text{world}} \cdot (0, 1, 0, 0)^T)$ is transformed dynamically to construct an orthonormal basis $(T, B, N)$:

$$\mathbf{T} = \begin{cases} \text{normalize}(\mathbf{U}_{\text{world}} \times \mathbf{N}) & \|\mathbf{U}_{\text{world}} \times \mathbf{N}\| > 10^{-4} \\ \text{normalize}(\mathbf{U}_{\text{world}} \times \mathbf{A}_{\text{ref}}) & \text{otherwise} \end{cases}$$

$$\mathbf{B} = \mathbf{N} \times \mathbf{T}$$

where $\mathbf{A}_{\text{ref}}$ is a stable orthogonal reference axis. Tangent $\mathbf{T}$ points strictly East along lines of latitude ($+u$), and bitangent $\mathbf{B}$ points strictly North along lines of longitude ($+v$).

#### Directional Mountain Horizon Self-Shadowing along Terminator
`bump.png` remains responsible for low-angle terrain self-shadowing. In the terminator zone ($\mathbf{N} \cdot \mathbf{L} \in [-0.06, 0.28]$), incident sunlight grazes the planet at low elevation angles. The incident solar vector $\mathbf{L}$ is projected into the orthonormal tangent plane $(T, B)$:

$$\mathbf{L}_{\text{tangent}} = \begin{pmatrix} \mathbf{L} \cdot \mathbf{T} \\ \mathbf{L} \cdot \mathbf{B} \end{pmatrix}, \quad \hat{\mathbf{L}}_{\text{tangent}} = \frac{\mathbf{L}_{\text{tangent}}}{\|\mathbf{L}_{\text{tangent}}\|}$$

The UV step vector facing the sun incorporates metric tensor scale compensation:

$$\Delta \mathbf{uv} = \begin{pmatrix} \hat{\mathbf{L}}_{\text{tangent}, x} \cdot \text{scale}_x(v) \cdot \Delta u_{\text{texel}} \\ \hat{\mathbf{L}}_{\text{tangent}, y} \cdot \Delta v_{\text{texel}} \end{pmatrix} \times 2.8$$

A directional 6-step shadow march samples adjacent elevation points $h_k = h(\mathbf{uv} + k \cdot \Delta \mathbf{uv})$ along the line of sight toward the sun. The incoming solar ray height at step $k$ is:

$$h_{\text{ray}}(k) = h_0 + k \cdot \frac{\max(0.002, \mathbf{N} \cdot \mathbf{L})}{\|\mathbf{L}_{\text{tangent}}\|} \cdot \sigma_{\text{elev}}$$

where $\sigma_{\text{elev}} = 0.048$ is the calibrated solar elevation slope. If an adjacent mountain peak obstructs the low-angle sun vector ($h_k - \epsilon > h_{\text{ray}}(k)$):

$$S_{\text{occlusion}} = \max_k \left( \text{clamp}\left( (h_k - \epsilon - h_{\text{ray}}(k)) \cdot 14.0, \, 0.0, \, 1.0 \right) \right)$$

The shadow factor is smoothly blended into full daytime diffuse irradiance as the sun climbs above $15^\circ$ ($\mathbf{N} \cdot \mathbf{L} \approx 0.26$) and into nocturnal lighting below the horizon:

$$S_{\text{terrain}} = 1.0 - S_{\text{occlusion}} \cdot \text{smoothstep}(0.26, 0.06, \mathbf{N} \cdot \mathbf{L}) \cdot \text{smoothstep}(-0.06, -0.01, \mathbf{N} \cdot \mathbf{L}) \cdot \left(\frac{u_{\text{shadow}}}{100}\right)$$

#### Performance Optimization & Texture Sample Reduction
- **Daylight Surface (away from terminator)**: Terrain normal reconstruction drops from 9 bump texture samples down to **1 normal map sample** (88.9% reduction in texture samples).
- **Nightside Surface**: Drops from 9 bump texture samples down to **1 normal map sample** (88.9% reduction).
- **Terminator Zone**: 9 bump samples for Sobel normal calculation are replaced by 1 normal map sample, retaining the 6 directional march samples + 1 center sample only where $\mathbf{N} \cdot \mathbf{L} \in [-0.06, 0.28]$.
- Across >90% of the planetary surface, per-fragment texture fetches for terrain relief are reduced from 9 to 1, while preserving identical mountain prominence and crisp relief across all latitudes.

---

### 3. Shader Breakdown

1. **`AtmosphereShader`** (Radius: 1.036, `THREE.BackSide`, `THREE.AdditiveBlending`):
   - Computes numerical ray-marching across $N = 16$ primary view steps and $M = 4$ secondary solar optical depth steps.
   - Evaluates analytical ray-sphere intersections for both the atmospheric shell ($R_{\text{atmo}} = 1.036$) and the solid planetary surface ($R_p = 1.0$).
   - Performs analytical Earth shadow tests:
     $$s_{\text{close}} = -\mathbf{x} \cdot \mathbf{L}, \quad d_{\perp}^2 = \|\mathbf{x}\|^2 - s_{\text{close}}^2$$
     When $s_{\text{close}} > 0$ and $d_{\perp}^2 < R_p^2$, the sample point is inside Earth's umbral shadow ($T_{\text{sun}} = 0$). Nightside pixels produce zero radiance, guaranteeing a pure pitch-black silhouette with stars fully visible behind it.
   - Modulates atmospheric radiance smoothly via the presentation HUD slider `uAtmosphereIntensity`.

2. **`CoronaGlowShader`** (Radius: 1.10, `THREE.BackSide`, `THREE.AdditiveBlending`):
   - Renders the outer exospheric forward-scattering halo and solar glint from radius $1.020$ out to $1.100$.
   - Uses the Henyey-Greenstein phase function ($g = 0.82$) modulated by directional forward-visibility masks and Earth shadow occlusion.
   - Dissolves to zero on the dark hemisphere and away from the sun, preventing ghost glows or concentric ring artifacts.

3. **`EarthSurfaceShader`**:
   - **High-Precision Tangent-Space Normal Mapping**: Samples the precomputed linear non-color tangent-space normal map (`normal.png`) with metric tensor scale compensation and singularity-free analytic tangent frame $(T, B, N)$, eliminating runtime 3×3 Sobel elevation reconstruction.
   - **Terminator Mountain Relief Self-Shadowing**: Fast 6-step directional shadow raymarch using `bump.png` elevation data along the projected tangent sun vector casting dramatic mountain shadows across valleys at sunrise/sunset.
   - **Ocean Specular Glint**: Evaluates Blinn-Phong half-angle reflection modulated by the NASA Blue Marble hydrographic mask, restricted strictly to water surfaces.
   - **Physically-Derived Sunset Terminator**: Attenuates daylight irradiance via the Beer-Lambert law ($T_{\text{sun}} = \exp(-\boldsymbol{\tau}_{\text{sun}})$), smoothly transforming daytime satellite colors into warm golden-amber and crimson bands along the terminator ($\mathbf{N} \cdot \mathbf{L} \approx 0$).
   - **Aerial Perspective & Stratospheric Limb Haze**: Evaluates view-angle optical depth $\boldsymbol{\tau}_{\text{view}}$ and inscattering $\mathbf{L}_{\text{in}}$ matching the atmospheric Rayleigh coefficients. At the planetary limb ($\mathbf{N} \cdot \mathbf{V} \to 0$), the terrain dissolves seamlessly into the atmospheric envelope with zero boundary mismatch.
   - **Nocturnal Illumination**: Fades in land-masked NASA Black Marble city lights on the dark hemisphere ($1.0 - \text{smoothstep}(-0.12, 0.06, \mathbf{N} \cdot \mathbf{L})$).
   - **Cloud Shadows**: Projects dynamic cloud shadows with directional solar offset onto the daytime terrain.

4. **`CloudsShader`** (Radius: 1.008, Independent Circulation):
   - Modulates NASA MODIS cloud albedo with diffuse sunlight and grazing sunset extinction ($T_{\text{sun}}$).
   - Softens opacity on the dark hemisphere to maintain visibility of incandescent nocturnal cities through cloud decks.

---

## Verification & Build Validation

To verify the installation and run all checks:

```bash
# Verify Python script syntax
python3 -m py_compile build_webgl_textures.py
python3 -m py_compile process_enhanced_assets.py
python3 -m py_compile generate_assets.py

# Test CLI help menus
python3 build_webgl_textures.py --help
python3 process_enhanced_assets.py --help
python3 generate_assets.py --help

# Test texture generation dry-run
python3 build_webgl_textures.py --dry-run
python3 process_enhanced_assets.py --dry-run
```