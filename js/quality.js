/**
 * Quality & Performance Architecture for Three.js/WebGL Earth Renderer
 *
 * Implements:
 * - Centralized quality presets (ULTRA, HIGH, MEDIUM, LOW)
 * - Hardware profiling & capability probing (GPU renderer, mobile/touch, max texture size)
 * - AUTO warmup benchmarking (150 frames with P95 latency evaluation & latching)
 * - Dynamic tier switching via compile-time material defines & needsUpdate
 * - Adaptive DPR clamping for high-DPI fill rate optimization
 * - Texture anisotropy clamping
 * - localStorage preset persistence ('earth_quality_preset')
 * - Performance diagnostics telemetry overlay (hotkey 'D')
 */

export const QUALITY_PRESETS = {
  ULTRA: {
    name: 'Ultra',
    dprMax: 2.0,
    atmosphereViewSamples: 16,
    atmosphereSunSamples: 4,
    terrainShadowSteps: 6,
    oceanWaveOctaves: 3,
    anisotropy: 8,
    targetTextureDir: '4k'
  },
  HIGH: {
    name: 'High',
    dprMax: 1.5,
    atmosphereViewSamples: 12,
    atmosphereSunSamples: 3,
    terrainShadowSteps: 4,
    oceanWaveOctaves: 3,
    anisotropy: 4,
    targetTextureDir: '4k'
  },
  MEDIUM: {
    name: 'Medium',
    dprMax: 1.25,
    atmosphereViewSamples: 8,
    atmosphereSunSamples: 2,
    terrainShadowSteps: 3,
    oceanWaveOctaves: 1,
    anisotropy: 2,
    targetTextureDir: '2k'
  },
  LOW: {
    name: 'Low',
    dprMax: 1.0,
    atmosphereViewSamples: 5,
    atmosphereSunSamples: 2,
    terrainShadowSteps: 0,
    oceanWaveOctaves: 0,
    anisotropy: 1,
    targetTextureDir: '1k'
  }
};

export class QualityManager {
  constructor({
    renderer,
    surfaceMaterial,
    atmosphereMaterial,
    camera = null,
    controls = null,
    onTierChange = null
  }) {
    this.renderer = renderer;
    this.surfaceMaterial = surfaceMaterial;
    this.atmosphereMaterial = atmosphereMaterial;
    this.camera = camera;
    this.controls = controls;
    this.onTierChange = onTierChange;

    this.STORAGE_KEY = 'earth_quality_preset';

    // Hardware Profiling State
    this.gpuRenderer = '';
    this.gpuVendor = '';
    this.maxTextureSize = 4096;
    this.isTouch = false;
    this.isMobile = false;
    this.suggestedTier = 'HIGH';

    this.profileHardware();

    // Determine initial tier from storage or hardware detection
    let storedTier = null;
    try {
      storedTier = localStorage.getItem(this.STORAGE_KEY);
    } catch (e) {}

    const validManualTiers = ['ultra', 'high', 'medium', 'low'];
    if (storedTier && validManualTiers.includes(storedTier.toLowerCase())) {
      this.selectedTier = storedTier.toLowerCase();
      this.activeTier = this.selectedTier.toUpperCase();
      this.isBenchmarking = false;
    } else {
      this.selectedTier = 'auto';
      this.activeTier = this.suggestedTier;
      this.isBenchmarking = true;
    }

    // Warmup Benchmarking State
    this.warmupFrameCount = 0;
    this.warmupFrameTimes = [];
    this.warmupMaxFrames = 150;
    this.warmupSkipFrames = 5;
    this.p95FrameTimeMs = 0;

    // Rolling Performance Metrics
    this.currentFps = 60.0;
    this.currentFrameTimeMs = 16.6;
    this.fpsHistory = [];
    this.lastTelemetryUpdateTime = 0;
    this.telemetryVisible = false;
    this.telemetryBadgeEl = null;

    // Apply resolved initial tier
    this.applyTier(this.activeTier, false);

    // Bind UI dropdown if already in DOM
    this.syncUiDropdown();
  }

  profileHardware() {
    try {
      const gl = this.renderer ? this.renderer.getContext() : null;
      if (gl) {
        const dbg = gl.getExtension('WEBGL_debug_renderer_info');
        if (dbg) {
          this.gpuRenderer = gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL) || '';
          this.gpuVendor = gl.getParameter(dbg.UNMASKED_VENDOR_WEBGL) || '';
        } else {
          this.gpuRenderer = gl.getParameter(gl.RENDERER) || '';
          this.gpuVendor = gl.getParameter(gl.VENDOR) || '';
        }
        this.maxTextureSize = gl.getParameter(gl.MAX_TEXTURE_SIZE) || 4096;
      }
    } catch (e) {
      console.warn('[QualityManager] Failed to query WebGL device info:', e);
    }

    if (typeof window !== 'undefined') {
      this.isTouch = ('ontouchstart' in window) || (navigator.maxTouchPoints > 1);
      const minDim = Math.min(window.innerWidth || 1024, window.innerHeight || 768);
      this.isMobile = this.isTouch && minDim <= 800;
    }

    const lowerInfo = `${this.gpuRenderer} ${this.gpuVendor}`.toLowerCase();

    // Intelligent classification
    if (/swiftshader|llvmpipe|softpipe|mesa|virtualbox|vmware/i.test(lowerInfo)) {
      this.suggestedTier = 'LOW';
    } else if (this.maxTextureSize < 4096) {
      this.suggestedTier = 'LOW';
    } else if (this.isMobile) {
      this.suggestedTier = 'MEDIUM';
    } else if (/apple m[0-9]+ (max|ultra)|rtx [3-5][0-9]{3}|rx 7[0-9]{3}|rx 6[8-9][0-9]{2}|geforce rtx/i.test(lowerInfo)) {
      this.suggestedTier = 'ULTRA';
    } else if (/apple m[0-9]+|geforce gtx|radeon rx|iris xe|radeon vega|adreno 7|mali-g7/i.test(lowerInfo)) {
      this.suggestedTier = 'HIGH';
    } else if (/intel hd|intel uhd|adreno|mali/i.test(lowerInfo)) {
      this.suggestedTier = 'MEDIUM';
    } else {
      this.suggestedTier = 'HIGH';
    }

    console.log(`[QualityManager] Profiled hardware: ${this.gpuRenderer || 'Generic GPU'} | MaxTex: ${this.maxTextureSize} | Mobile: ${this.isMobile} | Auto Initial Tier: ${this.suggestedTier}`);
  }

  get currentPreset() {
    return QUALITY_PRESETS[this.activeTier] || QUALITY_PRESETS.HIGH;
  }

  getEffectiveDpr() {
    const preset = this.currentPreset;
    const deviceDpr = (typeof window !== 'undefined' && window.devicePixelRatio) ? window.devicePixelRatio : 1.0;
    return Math.min(deviceDpr, preset.dprMax);
  }

  applyTier(tierName, saveToStorage = true) {
    const tier = (tierName || 'HIGH').toUpperCase();
    const preset = QUALITY_PRESETS[tier] || QUALITY_PRESETS.HIGH;
    this.activeTier = tier;

    // 1. Update defines on surfaceMaterial
    if (this.surfaceMaterial) {
      this.surfaceMaterial.defines = this.surfaceMaterial.defines || {};
      const shadowChanged = this.surfaceMaterial.defines.TERRAIN_SHADOW_STEPS !== preset.terrainShadowSteps;
      const waveChanged = this.surfaceMaterial.defines.OCEAN_WAVE_OCTAVES !== preset.oceanWaveOctaves;

      this.surfaceMaterial.defines.TERRAIN_SHADOW_STEPS = preset.terrainShadowSteps;
      this.surfaceMaterial.defines.OCEAN_WAVE_OCTAVES = preset.oceanWaveOctaves;

      if (shadowChanged || waveChanged) {
        this.surfaceMaterial.needsUpdate = true;
      }
    }

    // 2. Update defines on atmosphereMaterial
    if (this.atmosphereMaterial) {
      this.atmosphereMaterial.defines = this.atmosphereMaterial.defines || {};
      const viewChanged = this.atmosphereMaterial.defines.NUM_VIEW_SAMPLES !== preset.atmosphereViewSamples;
      const sunChanged = this.atmosphereMaterial.defines.NUM_SUN_SAMPLES !== preset.atmosphereSunSamples;

      this.atmosphereMaterial.defines.NUM_VIEW_SAMPLES = preset.atmosphereViewSamples;
      this.atmosphereMaterial.defines.NUM_SUN_SAMPLES = preset.atmosphereSunSamples;

      if (viewChanged || sunChanged) {
        this.atmosphereMaterial.needsUpdate = true;
      }
    }

    // 3. Clamp Device Pixel Ratio
    const effectiveDpr = this.getEffectiveDpr();
    if (this.renderer) {
      this.renderer.setPixelRatio(effectiveDpr);
    }

    // 4. Update Texture Anisotropy
    if (this.renderer && this.surfaceMaterial && this.surfaceMaterial.uniforms) {
      const maxDeviceAniso = this.renderer.capabilities ? this.renderer.capabilities.getMaxAnisotropy() : 16;
      const targetAniso = Math.min(preset.anisotropy, maxDeviceAniso);

      for (const key of Object.keys(this.surfaceMaterial.uniforms)) {
        const u = this.surfaceMaterial.uniforms[key];
        if (u && u.value && u.value.isTexture) {
          if (u.value.anisotropy !== targetAniso) {
            u.value.anisotropy = targetAniso;
            u.value.needsUpdate = true;
          }
        }
      }
    }

    if (saveToStorage && this.selectedTier !== 'auto') {
      try {
        localStorage.setItem(this.STORAGE_KEY, this.selectedTier);
      } catch (e) {}
    }

    this.syncUiDropdown();

    if (typeof this.onTierChange === 'function') {
      this.onTierChange({
        selected: this.selectedTier,
        active: this.activeTier,
        preset: this.currentPreset
      });
    }

    console.log(`[QualityManager] Applied tier: ${this.activeTier} (Mode: ${this.selectedTier.toUpperCase()}, DPR: ${effectiveDpr.toFixed(2)}, ShadowSteps: ${preset.terrainShadowSteps}, OceanOctaves: ${preset.oceanWaveOctaves}, AtmoView: ${preset.atmosphereViewSamples}, AtmoSun: ${preset.atmosphereSunSamples})`);
  }

  setTier(tier) {
    const raw = (tier || 'auto').toLowerCase();
    if (raw === 'auto') {
      this.selectedTier = 'auto';
      try {
        localStorage.setItem(this.STORAGE_KEY, 'auto');
      } catch (e) {}
      this.activeTier = this.suggestedTier;
      this.isBenchmarking = true;
      this.warmupFrameCount = 0;
      this.warmupFrameTimes = [];
      this.applyTier(this.activeTier, false);
    } else {
      const upper = raw.toUpperCase();
      if (QUALITY_PRESETS[upper]) {
        this.selectedTier = raw;
        this.isBenchmarking = false;
        this.applyTier(upper, true);
      } else {
        console.warn(`[QualityManager] Unknown tier '${tier}', ignoring.`);
      }
    }
    this.syncUiDropdown();
  }

  getTier() {
    return {
      selected: this.selectedTier,
      active: this.activeTier.toLowerCase(),
      preset: this.currentPreset
    };
  }

  update(dtSeconds) {
    const now = (typeof performance !== 'undefined') ? performance.now() : Date.now();
    const frameTimeMs = dtSeconds * 1000.0;
    this.currentFrameTimeMs = frameTimeMs;

    // Rolling FPS metric
    this.fpsHistory.push(frameTimeMs);
    if (this.fpsHistory.length > 60) {
      this.fpsHistory.shift();
    }
    const avgMs = this.fpsHistory.reduce((a, b) => a + b, 0) / this.fpsHistory.length;
    this.currentFps = avgMs > 0 ? (1000.0 / avgMs) : 60.0;

    // AUTO Warmup Benchmark
    if (this.isBenchmarking) {
      this.warmupFrameCount++;
      if (this.warmupFrameCount > this.warmupSkipFrames) {
        this.warmupFrameTimes.push(frameTimeMs);
      }

      if (this.warmupFrameCount >= this.warmupMaxFrames) {
        this.finishBenchmark();
      }
    }

    // Telemetry display update (rate-limited ~4 Hz)
    if (this.telemetryVisible && (now - this.lastTelemetryUpdateTime > 250)) {
      this.lastTelemetryUpdateTime = now;
      this.renderTelemetryBadge();
    }
  }

  finishBenchmark() {
    this.isBenchmarking = false;
    if (this.warmupFrameTimes.length === 0) return;

    const sorted = [...this.warmupFrameTimes].sort((a, b) => a - b);
    const p95Index = Math.min(sorted.length - 1, Math.floor(sorted.length * 0.95));
    const p95 = sorted[p95Index];
    this.p95FrameTimeMs = p95;

    console.log(`[QualityManager] Auto warmup benchmark completed (${this.warmupFrameTimes.length} frames). P95 frame time: ${p95.toFixed(2)} ms (${(1000.0 / p95).toFixed(1)} FPS target)`);

    const tiers = ['ULTRA', 'HIGH', 'MEDIUM', 'LOW'];
    let currentIdx = tiers.indexOf(this.activeTier);
    if (currentIdx === -1) currentIdx = 1;

    if (p95 > 28.0) {
      // High frame times, drop to LOW
      if (this.activeTier !== 'LOW') {
        console.warn(`[QualityManager] P95 frame time ${p95.toFixed(2)}ms > 28ms. Stepping down to LOW.`);
        this.applyTier('LOW', false);
      }
    } else if (p95 > 24.0) {
      // Moderate latency, step down one tier
      if (currentIdx < tiers.length - 1) {
        const nextTier = tiers[currentIdx + 1];
        console.warn(`[QualityManager] P95 frame time ${p95.toFixed(2)}ms > 24ms. Stepping down from ${this.activeTier} to ${nextTier}.`);
        this.applyTier(nextTier, false);
      }
    } else {
      console.log(`[QualityManager] Performance optimal at ${this.activeTier} (P95: ${p95.toFixed(2)}ms). Retaining tier.`);
    }
  }

  syncUiDropdown() {
    if (typeof document === 'undefined') return;
    const select = document.getElementById('qualitySelect');
    if (select && select.value !== this.selectedTier) {
      select.value = this.selectedTier;
    }
  }

  toggleTelemetryOverlay() {
    this.telemetryVisible = !this.telemetryVisible;
    if (!this.telemetryBadgeEl && typeof document !== 'undefined') {
      this.telemetryBadgeEl = document.getElementById('perfTelemetryBadge');
    }
    if (this.telemetryBadgeEl) {
      this.telemetryBadgeEl.style.display = this.telemetryVisible ? 'flex' : 'none';
      if (this.telemetryVisible) {
        this.renderTelemetryBadge();
      }
    }
    return this.telemetryVisible;
  }

  renderTelemetryBadge() {
    if (!this.telemetryBadgeEl) return;
    const report = this.getReport();
    const p = report.preset;
    const modeLabel = report.tier.selected === 'auto' ? 'Auto' : 'Manual';
    const calls = report.rendering.drawCalls;
    const tris = (report.rendering.triangles / 1000).toFixed(1) + 'K';
    const gpuShort = (this.gpuRenderer || 'WebGL Renderer')
      .replace(/^ANGLE \(([^,]+),.*$/, '$1')
      .replace(/^Apple (.+)$/, '$1');

    this.telemetryBadgeEl.innerHTML = `
      <div class="perf-row perf-title"><span>DIAGNOSTICS TELEMETRY</span><span class="perf-tag">[D] CLOSE</span></div>
      <div class="perf-row"><span>FPS:</span><strong>${report.performance.fps.toFixed(1)} (${report.performance.frameTimeMs.toFixed(1)} ms)</strong></div>
      <div class="perf-row"><span>TIER:</span><strong>${report.tier.active} (${modeLabel})</strong></div>
      <div class="perf-row"><span>DPR:</span><strong>${report.dpr.effective.toFixed(2)} (Max: ${p.dprMax.toFixed(2)})</strong></div>
      <div class="perf-row"><span>VIEWPORT:</span><strong>${window.innerWidth} &times; ${window.innerHeight}</strong></div>
      <div class="perf-row"><span>ATMOSPHERE:</span><strong>${p.atmosphereViewSamples}v / ${p.atmosphereSunSamples}s</strong></div>
      <div class="perf-row"><span>SHADOW / WAVE:</span><strong>${p.terrainShadowSteps} steps / ${p.oceanWaveOctaves} oct</strong></div>
      <div class="perf-row"><span>DRAWS / TRIS:</span><strong>${calls} calls / ${tris}</strong></div>
      <div class="perf-row perf-gpu"><span>GPU:</span><span title="${this.gpuRenderer}">${gpuShort}</span></div>
    `;
  }

  getReport() {
    const rendererInfo = (this.renderer && this.renderer.info)
      ? this.renderer.info.render
      : { calls: 0, triangles: 0, lines: 0, points: 0 };

    return {
      tier: {
        selected: this.selectedTier,
        active: this.activeTier
      },
      preset: { ...this.currentPreset },
      dpr: {
        device: (typeof window !== 'undefined' && window.devicePixelRatio) ? window.devicePixelRatio : 1.0,
        effective: this.getEffectiveDpr()
      },
      gpu: {
        renderer: this.gpuRenderer,
        vendor: this.gpuVendor,
        maxTextureSize: this.maxTextureSize
      },
      performance: {
        fps: this.currentFps,
        frameTimeMs: this.currentFrameTimeMs,
        p95Ms: this.p95FrameTimeMs
      },
      rendering: {
        drawCalls: rendererInfo.calls,
        triangles: rendererInfo.triangles,
        lines: rendererInfo.lines,
        points: rendererInfo.points
      },
      defines: {
        surface: this.surfaceMaterial ? { ...this.surfaceMaterial.defines } : {},
        atmosphere: this.atmosphereMaterial ? { ...this.atmosphereMaterial.defines } : {}
      }
    };
  }
}
