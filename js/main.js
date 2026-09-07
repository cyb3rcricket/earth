/**
 * Photorealistic 3D Earth Application Core (Three.js WebGL)
 *
 * Implements:
 * - High-precision SphereGeometry(1.0, 128, 128) with 2:1 equirectangular textures
 * - Fixed directional sunlight in world space (-1.4, 0.8, 1.2)
 * - Earth axial tilt of -23.44°
 * - Multi-layer system: Surface relief, Ocean Specular, Cloud shadows, Cloud deck, Additive Atmosphere & Corona
 * - Deep space celestial sphere with 1,800 twinkling particle stars
 * - Seamless pointer drag, rotational inertia, smooth camera zoom, auto-rotation resume
 * - Aerospace telemetry readout & Collapsible HUD controls
 */

import * as THREE from './three.module.js';
import {
  EarthSurfaceShader,
  CloudsShader,
  AtmosphereShader,
  CoronaGlowShader
} from './shaders.js';
import { EarthControls } from './controls.js';

document.addEventListener('DOMContentLoaded', () => {
  // DOM Elements
  const canvas = document.getElementById('webglCanvas');
  const hudToggleBtn = document.getElementById('hudToggleBtn');
  const hudPanel = document.getElementById('hudPanel');
  const pauseBtn = document.getElementById('pauseBtn');
  const resetBtn = document.getElementById('resetBtn');

  const rotationSpeedInput = document.getElementById('rotationSpeed');
  const rotationVal = document.getElementById('rotationVal');
  const cloudOpacityInput = document.getElementById('cloudOpacity');
  const cloudVal = document.getElementById('cloudVal');
  const atmosphereIntensityInput = document.getElementById('atmosphereIntensity');
  const atmosphereVal = document.getElementById('atmosphereVal');
  const shadowStrengthInput = document.getElementById('shadowStrength');
  const shadowVal = document.getElementById('shadowVal');

  const altDisplay = document.getElementById('altDisplay');
  const coordsDisplay = document.getElementById('coordsDisplay');
  const periodDisplay = document.getElementById('periodDisplay');

  // =========================================================================
  // 1. THREE.JS RENDERER & SCENE SETUP
  // =========================================================================
  const renderer = new THREE.WebGLRenderer({
    canvas,
    antialias: true,
    alpha: true,
    powerPreference: 'high-performance'
  });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2.0));
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.05;

  const scene = new THREE.Scene();

  const camera = new THREE.PerspectiveCamera(
    42,
    window.innerWidth / window.innerHeight,
    0.1,
    1000
  );
  camera.position.set(0, 0, 3.2);

  // Fixed Sunlight in space: Incident from upper-left and slightly towards viewer
  const sunDirection = new THREE.Vector3(-1.4, 0.8, 1.2).normalize();

  // =========================================================================
  // 2. CELESTIAL ENVIRONMENT (DEEP SPACE & PARTICLE STARS)
  // =========================================================================
  const textureLoader = new THREE.TextureLoader();

  // Celestial Background Sphere
  const starSphereGeo = new THREE.SphereGeometry(150, 32, 32);
  const starTexture = textureLoader.load('assets/earth/stars.jpg');
  starTexture.colorSpace = THREE.SRGBColorSpace;
  const starSphereMat = new THREE.MeshBasicMaterial({
    map: starTexture,
    side: THREE.BackSide,
    depthWrite: false
  });
  const starSphereMesh = new THREE.Mesh(starSphereGeo, starSphereMat);
  scene.add(starSphereMesh);

  // Procedural Deep Space Star Particles (1,800 stars)
  const starCount = 1800;
  const starPositions = new Float32Array(starCount * 3);
  const starColors = new Float32Array(starCount * 3);
  const starSizes = new Float32Array(starCount);

  for (let i = 0; i < starCount; i++) {
    // Distribute randomly on sphere surface around radius 80-110
    const u = Math.random();
    const v = Math.random();
    const theta = u * 2.0 * Math.PI;
    const phi = Math.acos(2.0 * v - 1.0);
    const r = 85 + Math.random() * 25;

    starPositions[i * 3] = r * Math.sin(phi) * Math.cos(theta);
    starPositions[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
    starPositions[i * 3 + 2] = r * Math.cos(phi);

    // Warm, neutral, and cool star tints
    const tintChoice = Math.random();
    if (tintChoice < 0.25) {
      // Cool blue-white (O/B type)
      starColors[i * 3] = 0.75;
      starColors[i * 3 + 1] = 0.85;
      starColors[i * 3 + 2] = 1.0;
    } else if (tintChoice < 0.5) {
      // Warm golden-amber (K/M type)
      starColors[i * 3] = 1.0;
      starColors[i * 3 + 1] = 0.88;
      starColors[i * 3 + 2] = 0.72;
    } else {
      // Pure diamond white (A/F type)
      starColors[i * 3] = 0.96;
      starColors[i * 3 + 1] = 0.98;
      starColors[i * 3 + 2] = 1.0;
    }

    starSizes[i] = 1.2 + Math.random() * 1.8;
  }

  const starGeo = new THREE.BufferGeometry();
  starGeo.setAttribute('position', new THREE.BufferAttribute(starPositions, 3));
  starGeo.setAttribute('color', new THREE.BufferAttribute(starColors, 3));

  // Canvas circle texture for smooth round star points
  const pCanvas = document.createElement('canvas');
  pCanvas.width = 16;
  pCanvas.height = 16;
  const pCtx = pCanvas.getContext('2d');
  const pGrad = pCtx.createRadialGradient(8, 8, 0, 8, 8, 8);
  pGrad.addColorStop(0, 'rgba(255,255,255,1.0)');
  pGrad.addColorStop(0.5, 'rgba(255,255,255,0.75)');
  pGrad.addColorStop(1, 'rgba(255,255,255,0)');
  pCtx.fillStyle = pGrad;
  pCtx.beginPath();
  pCtx.arc(8, 8, 8, 0, Math.PI * 2);
  pCtx.fill();
  const pointTexture = new THREE.CanvasTexture(pCanvas);

  const starMat = new THREE.PointsMaterial({
    size: 2.2,
    vertexColors: true,
    map: pointTexture,
    transparent: true,
    blending: THREE.AdditiveBlending,
    depthWrite: false
  });
  const starPoints = new THREE.Points(starGeo, starMat);
  scene.add(starPoints);

  // =========================================================================
  // 3. TEXTURE LOADING & ANISOTROPY
  // =========================================================================
  const maxAnisotropy = Math.min(renderer.capabilities.getMaxAnisotropy(), 8);

  function loadTexture(path, isColor = true, onLoad = null) {
    const tex = textureLoader.load(path, (loadedTex) => {
      if (onLoad) onLoad(loadedTex);
    });
    tex.wrapS = THREE.RepeatWrapping;
    tex.wrapT = THREE.ClampToEdgeWrapping;
    tex.anisotropy = maxAnisotropy;
    if (isColor) {
      tex.colorSpace = THREE.SRGBColorSpace;
    } else {
      tex.colorSpace = THREE.NoColorSpace;
    }
    return tex;
  }

  const dayTexture = loadTexture('assets/earth/albedo.png', true);
  const normalTexture = loadTexture('assets/earth/normal.png', false);
  const bumpTexture = loadTexture('assets/earth/bump.png', false, (tex) => {
    if (tex.image && tex.image.width && tex.image.height && surfaceMaterial) {
      surfaceMaterial.uniforms.uBumpTexelSize.value.set(
        1.0 / tex.image.width,
        1.0 / tex.image.height
      );
    }
  });
  const nightTexture = loadTexture('assets/earth/night.png', true);
  const specularTexture = loadTexture('assets/earth/specular.png', false);
  const cloudsTexture = loadTexture('assets/earth/clouds.png', true);

  // =========================================================================
  // 4. PLANETARY SYSTEM & AXIAL HIERARCHY
  // =========================================================================
  // Axial tilt group: 23.44° tilt in space
  const axialGroup = new THREE.Group();
  axialGroup.rotation.z = THREE.MathUtils.degToRad(-23.44);
  scene.add(axialGroup);

  // Rotational earth group for terrain surface
  const earthGroup = new THREE.Group();
  axialGroup.add(earthGroup);

  // Rotational clouds group for independent atmospheric circulation
  const cloudsGroup = new THREE.Group();
  axialGroup.add(cloudsGroup);

  // High-precision sphere geometry (128x128 segments)
  const sphereGeo = new THREE.SphereGeometry(1.0, 128, 128);

  // 1. Earth Surface Mesh
  const surfaceMaterial = new THREE.ShaderMaterial({
    uniforms: {
      uDayTexture: { value: dayTexture },
      uNormalTexture: { value: normalTexture },
      uBumpTexture: { value: bumpTexture },
      uNightTexture: { value: nightTexture },
      uSpecularTexture: { value: specularTexture },
      uCloudsTexture: { value: cloudsTexture },
      uSunDirection: { value: sunDirection },
      uCloudOffset: { value: 0.0 },
      uCloudOpacity: { value: 90.0 },
      uAtmosphereIntensity: { value: 100.0 },
      uShadowStrength: { value: 95.0 },
      uBumpTexelSize: { value: new THREE.Vector2(1.0 / 4096.0, 1.0 / 2048.0) },
      uBumpScale: { value: 2.05 },
      uNormalScale: { value: 1.0 },
      uTerrainShadowStrength: { value: 1.0 },
      uTerrainShadowElevation: { value: 0.048 },
      // Ocean microfacet BRDF uniforms
      uOceanRoughness: { value: 0.16 },
      uOceanF0: { value: 0.02 },
      uOceanGlintIntensity: { value: 0.35 },
      uOceanMicroWaveScale: { value: 350.0 },
      uOceanMicroWaveStrength: { value: 0.035 },
      uTime: { value: 0.0 }
    },
    vertexShader: EarthSurfaceShader.vertexShader,
    fragmentShader: EarthSurfaceShader.fragmentShader
  });
  const earthMesh = new THREE.Mesh(sphereGeo, surfaceMaterial);
  earthGroup.add(earthMesh);

  // 2. Clouds Mesh (radius 1.008)
  const cloudsGeo = new THREE.SphereGeometry(1.008, 128, 128);
  const cloudsMaterial = new THREE.ShaderMaterial({
    uniforms: {
      uCloudsTexture: { value: cloudsTexture },
      uSunDirection: { value: sunDirection },
      uCloudOpacity: { value: 90.0 }
    },
    vertexShader: CloudsShader.vertexShader,
    fragmentShader: CloudsShader.fragmentShader,
    transparent: true,
    depthWrite: false
  });
  const cloudsMesh = new THREE.Mesh(cloudsGeo, cloudsMaterial);
  cloudsGroup.add(cloudsMesh);

  // 3. Atmosphere Rayleigh Limb Scattering Shell (radius 1.036)
  const atmoGeo = new THREE.SphereGeometry(1.036, 128, 128);
  const atmoMaterial = new THREE.ShaderMaterial({
    uniforms: {
      uSunDirection: { value: sunDirection },
      uAtmosphereIntensity: { value: 100.0 }
    },
    vertexShader: AtmosphereShader.vertexShader,
    fragmentShader: AtmosphereShader.fragmentShader,
    side: THREE.BackSide,
    blending: THREE.AdditiveBlending,
    transparent: true,
    depthWrite: false
  });
  const atmosphereMesh = new THREE.Mesh(atmoGeo, atmoMaterial);
  axialGroup.add(atmosphereMesh);

  // 4. Outer Atmospheric Corona Glow Shell (radius 1.10)
  const coronaGeo = new THREE.SphereGeometry(1.10, 64, 64);
  const coronaMaterial = new THREE.ShaderMaterial({
    uniforms: {
      uSunDirection: { value: sunDirection },
      uAtmosphereIntensity: { value: 100.0 }
    },
    vertexShader: CoronaGlowShader.vertexShader,
    fragmentShader: CoronaGlowShader.fragmentShader,
    side: THREE.BackSide,
    blending: THREE.AdditiveBlending,
    transparent: true,
    depthWrite: false
  });
  const coronaMesh = new THREE.Mesh(coronaGeo, coronaMaterial);
  axialGroup.add(coronaMesh);

  // =========================================================================
  // 5. INTERACTIVE CONTROLS & KINEMATICS
  // =========================================================================
  const controls = new EarthControls({
    domElement: canvas,
    camera,
    earthGroup,
    cloudsGroup,
    surfaceMaterial,
    onTelemetryUpdate: ({ altitude, coordinates, period }) => {
      if (altDisplay) altDisplay.textContent = altitude;
      if (coordsDisplay) coordsDisplay.textContent = coordinates;
      if (periodDisplay) periodDisplay.textContent = period;
    }
  });

  // =========================================================================
  // 6. HUD PRESENTATION CONTROLS
  // =========================================================================
  if (hudToggleBtn && hudPanel) {
    hudToggleBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      hudPanel.classList.toggle('is-open');
    });

    document.addEventListener('click', (e) => {
      if (!hudPanel.contains(e.target) && !hudToggleBtn.contains(e.target)) {
        hudPanel.classList.remove('is-open');
      }
    });
  }

  // Rotation Speed Control
  if (rotationSpeedInput) {
    rotationSpeedInput.addEventListener('input', (e) => {
      const sec = Math.max(10, parseFloat(e.target.value));
      controls.autoRotateSpeed = 360.0 / sec;
      if (rotationVal) rotationVal.textContent = `${sec}s`;
      if (periodDisplay) periodDisplay.textContent = `${sec.toFixed(1)}s`;
    });
  }

  // Cloud Opacity Control
  if (cloudOpacityInput) {
    cloudOpacityInput.addEventListener('input', (e) => {
      const val = parseFloat(e.target.value);
      surfaceMaterial.uniforms.uCloudOpacity.value = val;
      cloudsMaterial.uniforms.uCloudOpacity.value = val;
      if (cloudVal) cloudVal.textContent = `${val}%`;
    });
  }

  // Atmosphere Intensity Control
  if (atmosphereIntensityInput) {
    atmosphereIntensityInput.addEventListener('input', (e) => {
      const val = parseFloat(e.target.value);
      surfaceMaterial.uniforms.uAtmosphereIntensity.value = val;
      atmoMaterial.uniforms.uAtmosphereIntensity.value = val;
      coronaMaterial.uniforms.uAtmosphereIntensity.value = val;
      if (atmosphereVal) atmosphereVal.textContent = `${val}%`;
    });
  }

  // Shadow Depth Control
  if (shadowStrengthInput) {
    shadowStrengthInput.addEventListener('input', (e) => {
      const val = parseFloat(e.target.value);
      surfaceMaterial.uniforms.uShadowStrength.value = val;
      if (shadowVal) shadowVal.textContent = `${val}%`;
    });
  }

  // Pause / Resume Toggle
  if (pauseBtn) {
    pauseBtn.addEventListener('click', () => {
      const paused = controls.togglePause();
      pauseBtn.textContent = paused ? 'Resume' : 'Pause';
    });
  }

  // Reset Parameters
  if (resetBtn) {
    resetBtn.addEventListener('click', () => {
      controls.reset();

      if (rotationSpeedInput) {
        rotationSpeedInput.value = 90;
        controls.autoRotateSpeed = 360.0 / 90.0;
        if (rotationVal) rotationVal.textContent = '90s';
        if (periodDisplay) periodDisplay.textContent = '90.0s';
      }
      if (cloudOpacityInput) {
        cloudOpacityInput.value = 90;
        surfaceMaterial.uniforms.uCloudOpacity.value = 90.0;
        cloudsMaterial.uniforms.uCloudOpacity.value = 90.0;
        if (cloudVal) cloudVal.textContent = '90%';
      }
      if (atmosphereIntensityInput) {
        atmosphereIntensityInput.value = 100;
        surfaceMaterial.uniforms.uAtmosphereIntensity.value = 100.0;
        atmoMaterial.uniforms.uAtmosphereIntensity.value = 100.0;
        coronaMaterial.uniforms.uAtmosphereIntensity.value = 100.0;
        if (atmosphereVal) atmosphereVal.textContent = '100%';
      }
      if (shadowStrengthInput) {
        shadowStrengthInput.value = 95;
        surfaceMaterial.uniforms.uShadowStrength.value = 95.0;
        if (shadowVal) shadowVal.textContent = '95%';
      }
      if (pauseBtn) {
        pauseBtn.textContent = 'Pause';
      }
    });
  }

  // =========================================================================
  // 7. RESPONSIVE RESIZE
  // =========================================================================
  window.addEventListener('resize', () => {
    const width = window.innerWidth;
    const height = window.innerHeight;
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2.0));
  });

  // Expose handles on window for verification, diagnostics and telemetry
  window.earthControls = controls;
  window.surfaceMaterial = surfaceMaterial;
  window.earthRenderer = renderer;
  window.earthScene = scene;
  window.earthCamera = camera;

  // =========================================================================
  // 8. ANIMATION LOOP
  // =========================================================================
  let prevTimestamp = performance.now();

  function animate(now) {
    const dtSeconds = Math.min(0.064, (now - prevTimestamp) / 1000.0);
    prevTimestamp = now;

    // Advance ocean micro-normal animation when rotation/motion is active
    if (surfaceMaterial && surfaceMaterial.uniforms && surfaceMaterial.uniforms.uTime && !controls.isPaused && !controls.isReducedMotion) {
      surfaceMaterial.uniforms.uTime.value += dtSeconds;
    }

    // Update planetary kinematics, inertia & camera damping
    controls.update(dtSeconds, now);

    // Subtle star twinkle
    if (starPoints && !controls.isReducedMotion) {
      starPoints.rotation.y += 0.00008;
    }

    // Render WebGL Scene
    renderer.render(scene, camera);

    requestAnimationFrame(animate);
  }

  requestAnimationFrame(animate);
});
