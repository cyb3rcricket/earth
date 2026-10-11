# Earth

A spinny, pretty Earth in your browser. Drag it around, zoom in, and watch city lights come on along the night side. I'm Cricket ([@Cyb3rCricket](https://x.com/Cyb3rCricket)), and I made this because space is neat.

## Run it

It's a static page, but browsers won't load textures straight from a file, so serve the folder:

```bash
git clone https://github.com/cyb3rcricket/earth.git
cd earth
python3 -m http.server 8000
```

Then open http://localhost:8000.

- **Drag** (or use the arrow keys) to spin it, and **scroll or pinch** to zoom. **Home** resets the view.
- Click the **gear** in the bottom-right to change rotation speed, clouds, glow, shadow depth, and graphics quality.
- Press **D** for a performance readout.

## How it works

- **[Three.js](https://threejs.org) r160** does the 3D. A copy lives in `js/three.module.js`, so it needs no internet once it's cloned.
- **The globe** is a sphere wrapped in real map images: a daytime surface, a night-lights map, a cloud layer, a bump map for mountains, and an ocean "shininess" map. They're in `assets/earth/`.
- **Custom shaders** (`js/shaders.js`) do the lighting tricks. The sun stays fixed, so day fades into night as the planet turns. Oceans glint, city lights only show on land, clouds cast soft shadows, and a thin blue haze sits around the edge.
- **`js/quality.js`** turns the detail down on slower devices.
- The orbit numbers in the bottom-left (altitude, coordinates, period) are **pretend**. They're there for vibes and follow the camera, not a real satellite.

### Rebuilding the textures (optional)

You don't need to do this to run it. The ready-made textures are already in `assets/earth/`.

```bash
python3 download_nasa_datasets.py     # grabs the big source maps into assets/raw/
python3 build_webgl_textures.py       # turns them into the textures in assets/earth/
python3 build_webgl_textures.py --help
```

The source maps come from Wikimedia Commons. Most are Solar System Scope's NASA-based Earth maps, plus a world elevation map. The URLs are in `download_nasa_datasets.py`.

## The honest catch

- **It's big.** The repo is about 190 MB, mostly because the 8K source maps in `assets/raw/` are committed. The app itself only uses the roughly 24 MB in `assets/earth/`.
- **The texture builder only works on a Mac.** `build_webgl_textures.py` uses macOS's `sips` tool to resize images.
- **It wants a decent GPU.** Older laptops and phones fall back to lower quality and still might chug.
- **It's pretty, not a simulation.** The sun doesn't follow the real date and time, and the telemetry is made up.
