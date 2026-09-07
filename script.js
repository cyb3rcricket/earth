/**
 * Photorealistic 3D Earth - Interactive Physics & Presentation System
 *
 * Capabilities:
 * - Direct Pointer Events manipulation (drag to rotate longitude & latitude)
 * - Restrained rotational inertia with realistic friction damping
 * - Continuous horizontal wrapping (0-360°) and clamped vertical tilt (-85° to +85°)
 * - Seamless auto-rotation pause and progressive ramp-up resume
 * - Fixed lighting, atmosphere, and terminator while geography rotates
 * - Independent atmospheric cloud drift layer
 * - Full accessibility: prefers-reduced-motion, keyboard navigation, focusable globe
 */

document.addEventListener('DOMContentLoaded', () => {
  const root = document.documentElement;
  const earthGlobe = document.getElementById('earthGlobe');
  const hudToggleBtn = document.getElementById('hudToggleBtn');
  const hudPanel = document.getElementById('hudPanel');
  const pauseBtn = document.getElementById('pauseBtn');
  const resetBtn = document.getElementById('resetBtn');

  const rotationSpeedInput = document.getElementById('rotationSpeed');
  const rotationVal = document.getElementById('rotationVal');
  const periodDisplay = document.getElementById('periodDisplay');
  const coordsDisplay = document.getElementById('coordsDisplay');

  const cloudOpacityInput = document.getElementById('cloudOpacity');
  const cloudVal = document.getElementById('cloudVal');

  const atmosphereIntensityInput = document.getElementById('atmosphereIntensity');
  const atmosphereVal = document.getElementById('atmosphereVal');

  const shadowStrengthInput = document.getElementById('shadowStrength');
  const shadowVal = document.getElementById('shadowVal');

  // =========================================================================
  // 1. ROTATIONAL KINEMATICS & PHYSICS STATE
  // =========================================================================
  let rotationY = 0.0;     // Longitude in degrees [0, 360)
  let rotationX = 0.0;     // Latitude in degrees [-85, +85]
  let velocityY = 0.0;     // Angular velocity in Y (deg/frame)
  let velocityX = 0.0;     // Angular velocity in X (deg/frame)

  let isDragging = false;
  let activePointerId = null;
  let lastPointerX = 0;
  let lastPointerY = 0;
  let lastPointerTime = 0;
  let lastInteractionTime = performance.now();

  let autoRotateSpeed = 360.0 / 90.0; // deg/sec for 90s rotation (4 deg/s)
  let autoRotateRamp = 1.0;           // 0.0 (paused) to 1.0 (full speed)
  let cloudDrift = 0.0;               // Independent cloud drift angle (degrees)
  let isPaused = false;

  // Accessibility: prefers-reduced-motion
  const mediaQueryReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  let isReducedMotion = mediaQueryReducedMotion.matches;
  mediaQueryReducedMotion.addEventListener('change', (e) => {
    isReducedMotion = e.matches;
    if (isReducedMotion) {
      velocityX = 0;
      velocityY = 0;
      autoRotateRamp = 0;
    }
  });

  // =========================================================================
  // 2. UNIFIED POINTER EVENTS (TOUCH, MOUSE, TRACKPAD, STYLUS)
  // =========================================================================
  if (earthGlobe) {
    earthGlobe.addEventListener('pointerdown', onPointerDown, { passive: false });
    window.addEventListener('pointermove', onPointerMove, { passive: false });
    window.addEventListener('pointerup', onPointerUp);
    window.addEventListener('pointercancel', onPointerUp);

    // Prevent accidental browser image dragging or ghost selections
    earthGlobe.addEventListener('dragstart', (e) => e.preventDefault());
  }

  function onPointerDown(e) {
    // Only accept primary pointer button (left mouse click or touch)
    if (e.button !== 0 && e.pointerType === 'mouse') return;

    isDragging = true;
    activePointerId = e.pointerId;
    earthGlobe.classList.add('is-dragging');

    // Capture pointer events even when dragged outside globe bounds
    try {
      earthGlobe.setPointerCapture(e.pointerId);
    } catch (err) {
      // Fallback if pointer capture is unsupported
    }

    lastPointerX = e.clientX;
    lastPointerY = e.clientY;
    lastPointerTime = performance.now();
    lastInteractionTime = performance.now();

    // Immediately stop any residual inertia and pause auto-rotation
    velocityX = 0.0;
    velocityY = 0.0;
    autoRotateRamp = 0.0;

    e.preventDefault();
  }

  function onPointerMove(e) {
    if (!isDragging || e.pointerId !== activePointerId) return;

    const now = performance.now();
    const dt = Math.max(1, now - lastPointerTime);
    const dx = e.clientX - lastPointerX;
    const dy = e.clientY - lastPointerY;

    // Calculate natural 1:1 rotation sensitivity based on rendered globe size
    const rect = earthGlobe.getBoundingClientRect();
    const globeDiameter = Math.max(200, rect.width);
    // 360 degrees divided by circumference (pi * diameter) gives exact 1:1 surface tracking
    const sensitivity = 360.0 / (Math.PI * globeDiameter);

    // Project screen dx, dy into the Earth's tilted frame of reference (-23.44°)
    const tiltRad = (-23.44 * Math.PI) / 180.0;
    const cosTilt = Math.cos(-tiltRad);
    const sinTilt = Math.sin(-tiltRad);
    const dxTilted = dx * cosTilt - dy * sinTilt;
    const dyTilted = dx * sinTilt + dy * cosTilt;

    // Dragging left turns Earth eastward; dragging right turns Earth westward
    const dLon = -dxTilted * sensitivity;
    // Dragging down tilts North Pole towards viewer; dragging up tilts South Pole towards viewer
    const dLat = dyTilted * sensitivity;

    rotationY += dLon;
    rotationX = Math.max(-85.0, Math.min(85.0, rotationX + dLat));

    // Smooth velocity calculation normalized to degrees per standard 60fps frame (~16.67ms)
    const frameFactor = 16.67 / dt;
    const instVelY = dLon * frameFactor;
    const instVelX = dLat * frameFactor;

    // Low-pass exponential filter to reject jitter
    velocityY = velocityY * 0.35 + instVelY * 0.65;
    velocityX = velocityX * 0.35 + instVelX * 0.65;

    lastPointerX = e.clientX;
    lastPointerY = e.clientY;
    lastPointerTime = now;
    lastInteractionTime = now;

    e.preventDefault();
  }

  function onPointerUp(e) {
    if (!isDragging || (activePointerId !== null && e.pointerId !== activePointerId)) return;

    isDragging = false;
    activePointerId = null;
    earthGlobe.classList.remove('is-dragging');

    const now = performance.now();

    // If held still for more than 80ms before release, kill fling velocity
    if (now - lastPointerTime > 80) {
      velocityX = 0.0;
      velocityY = 0.0;
    } else {
      // Clamp maximum inertia fling velocity to realistic planetary rotation
      const MAX_FLING = 3.2;
      velocityX = Math.max(-MAX_FLING, Math.min(MAX_FLING, velocityX));
      velocityY = Math.max(-MAX_FLING, Math.min(MAX_FLING, velocityY));
    }

    if (isReducedMotion) {
      velocityX = 0.0;
      velocityY = 0.0;
    }

    try {
      earthGlobe.releasePointerCapture(e.pointerId);
    } catch (err) {
      // Ignore
    }

    lastInteractionTime = now;
  }

  // =========================================================================
  // 3. ACCESSIBLE KEYBOARD NAVIGATION (WHEN GLOBE HAS FOCUS)
  // =========================================================================
  if (earthGlobe) {
    earthGlobe.addEventListener('keydown', (e) => {
      const STEP = 4.0; // degrees per keypress
      let handled = false;

      switch (e.key) {
        case 'ArrowLeft':
          rotationY -= STEP;
          handled = true;
          break;
        case 'ArrowRight':
          rotationY += STEP;
          handled = true;
          break;
        case 'ArrowUp':
          rotationX = Math.min(85.0, rotationX + STEP);
          handled = true;
          break;
        case 'ArrowDown':
          rotationX = Math.max(-85.0, rotationX - STEP);
          handled = true;
          break;
        case 'Home':
          rotationX = 0.0;
          rotationY = 0.0;
          handled = true;
          break;
      }

      if (handled) {
        e.preventDefault();
        lastInteractionTime = performance.now();
        autoRotateRamp = 0.0;
        velocityX = 0.0;
        velocityY = 0.0;
      }
    });
  }

  // Global keyboard shortcuts (when not focused on form controls)
  window.addEventListener('keydown', (e) => {
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'BUTTON') return;
    if (e.code === 'Space') {
      e.preventDefault();
      togglePause();
    } else if (e.key === 'h' || e.key === 'H') {
      if (hudPanel) hudPanel.classList.toggle('is-open');
    }
  });

  // =========================================================================
  // 4. MAIN ANIMATION & PHYSICS LOOP (REQUEST ANIMATION FRAME ~60 FPS)
  // =========================================================================
  let prevTimestamp = performance.now();

  function animate(now) {
    const dtSeconds = Math.min(0.064, (now - prevTimestamp) / 1000.0);
    prevTimestamp = now;

    // --- Physics Phase: Rotational Inertia ---
    if (!isDragging && !isReducedMotion) {
      const hasVelocity = Math.abs(velocityX) > 0.002 || Math.abs(velocityY) > 0.002;

      if (hasVelocity) {
        rotationY += velocityY;
        rotationX = Math.max(-85.0, Math.min(85.0, rotationX + velocityX));

        // Restrained friction damping (0.955 per frame)
        velocityX *= 0.955;
        velocityY *= 0.955;

        // Stop velocity immediately if hitting latitude extremes
        if (rotationX >= 85.0 || rotationX <= -85.0) {
          velocityX = 0.0;
        }
      } else {
        velocityX = 0.0;
        velocityY = 0.0;
      }

      // --- Auto-Rotation Resume Phase ---
      // After globe is untouched for 2.5 seconds, gradually ramp up auto-rotation
      const timeSinceInteraction = now - lastInteractionTime;
      if (!isPaused && timeSinceInteraction > 2500) {
        // Smooth progressive acceleration back to normal planetary speed over ~2 seconds
        autoRotateRamp = Math.min(1.0, autoRotateRamp + dtSeconds * 0.5);
        rotationY += autoRotateSpeed * autoRotateRamp * dtSeconds;
      }
    }

    // --- Independent Cloud Drift ---
    // Atmospheric weather systems circulate at a slightly distinct rate
    if (!isPaused && !isReducedMotion) {
      cloudDrift += 0.85 * dtSeconds; // subtle independent eastward drift
    }

    // Wrap longitude into clean [0, 360) range
    rotationY = ((rotationY % 360.0) + 360.0) % 360.0;

    // --- Render to CSS Custom Properties ---
    // Horizontal mapping: 360 degrees maps to 100% of seamless texture width
    const surfacePosX = -(rotationY / 360.0) * 100.0;
    const cloudsPosX = -((rotationY + cloudDrift) / 360.0) * 100.0;

    // Vertical mapping: Latitude angle (-85° to +85°) maps through sine projection
    // Sinusoidal factor simulates genuine orthographic spherical pitch
    const latRad = (rotationX * Math.PI) / 180.0;
    const latFactor = Math.sin(latRad);
    // At lat=0 (equator): posY = 50%
    // At lat=+85 (North Pole): posY = 50% - 48% = 2%
    // At lat=-85 (South Pole): posY = 50% + 48% = 98%
    const surfacePosY = 50.0 - latFactor * 48.0;
    const cloudsPosY = surfacePosY;

    root.style.setProperty('--surface-pos-x', `${surfacePosX.toFixed(3)}%`);
    root.style.setProperty('--surface-pos-y', `${surfacePosY.toFixed(3)}%`);
    root.style.setProperty('--clouds-pos-x', `${cloudsPosX.toFixed(3)}%`);
    root.style.setProperty('--clouds-pos-y', `${cloudsPosY.toFixed(3)}%`);
    root.style.setProperty('--rotation-x', `${rotationX.toFixed(2)}deg`);
    root.style.setProperty('--rotation-y', `${rotationY.toFixed(2)}deg`);

    // --- Update Telemetry Readout ---
    if (coordsDisplay) {
      const latAbs = Math.abs(rotationX).toFixed(1);
      const latHem = rotationX >= 0 ? 'N' : 'S';
      const lonNorm = ((rotationY % 360.0) + 360.0) % 360.0;
      const lon180 = lonNorm > 180.0 ? lonNorm - 360.0 : lonNorm;
      const lonAbs = Math.abs(lon180).toFixed(1);
      const lonHem = lon180 >= 0 ? 'E' : 'W';
      coordsDisplay.textContent = `${latAbs}\u00B0 ${latHem}, ${lonAbs}\u00B0 ${lonHem}`;
    }

    requestAnimationFrame(animate);
  }

  requestAnimationFrame(animate);

  // =========================================================================
  // 5. HUD PRESENTATION CONTROLS
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
      autoRotateSpeed = 360.0 / sec;
      if (rotationVal) rotationVal.textContent = `${sec}s`;
      if (periodDisplay) periodDisplay.textContent = `${sec.toFixed(1)}s`;
    });
  }

  // Cloud Opacity Control
  if (cloudOpacityInput) {
    cloudOpacityInput.addEventListener('input', (e) => {
      const pct = parseFloat(e.target.value);
      root.style.setProperty('--cloud-opacity', (pct / 100).toFixed(2));
      if (cloudVal) cloudVal.textContent = `${pct}%`;
    });
  }

  // Atmosphere Intensity Control
  if (atmosphereIntensityInput) {
    atmosphereIntensityInput.addEventListener('input', (e) => {
      const pct = parseFloat(e.target.value);
      root.style.setProperty('--atmosphere-intensity', (pct / 100).toFixed(2));
      if (atmosphereVal) atmosphereVal.textContent = `${pct}%`;
    });
  }

  // Shadow Depth Control
  if (shadowStrengthInput) {
    shadowStrengthInput.addEventListener('input', (e) => {
      const pct = parseFloat(e.target.value);
      root.style.setProperty('--shadow-strength', (pct / 100).toFixed(2));
      if (shadowVal) shadowVal.textContent = `${pct}%`;
    });
  }

  // Pause / Resume Toggle
  function togglePause() {
    isPaused = !isPaused;
    if (isPaused) {
      velocityX = 0.0;
      velocityY = 0.0;
      autoRotateRamp = 0.0;
    } else {
      lastInteractionTime = performance.now() - 3000; // resume auto-rotation promptly
    }
    if (pauseBtn) {
      pauseBtn.textContent = isPaused ? 'Resume' : 'Pause';
    }
  }

  if (pauseBtn) {
    pauseBtn.addEventListener('click', togglePause);
  }

  // Reset Parameters
  if (resetBtn) {
    resetBtn.addEventListener('click', () => {
      rotationX = 0.0;
      rotationY = 0.0;
      velocityX = 0.0;
      velocityY = 0.0;
      autoRotateRamp = 1.0;
      lastInteractionTime = performance.now();

      if (rotationSpeedInput) {
        rotationSpeedInput.value = 90;
        autoRotateSpeed = 360.0 / 90.0;
        if (rotationVal) rotationVal.textContent = '90s';
        if (periodDisplay) periodDisplay.textContent = '90.0s';
      }
      if (cloudOpacityInput) {
        cloudOpacityInput.value = 90;
        root.style.setProperty('--cloud-opacity', '0.90');
        if (cloudVal) cloudVal.textContent = '90%';
      }
      if (atmosphereIntensityInput) {
        atmosphereIntensityInput.value = 100;
        root.style.setProperty('--atmosphere-intensity', '1.0');
        if (atmosphereVal) atmosphereVal.textContent = '100%';
      }
      if (shadowStrengthInput) {
        shadowStrengthInput.value = 95;
        root.style.setProperty('--shadow-strength', '0.95');
        if (shadowVal) shadowVal.textContent = '95%';
      }
      if (isPaused) {
        togglePause();
      }
    });
  }
});
