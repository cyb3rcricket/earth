/**
 * Planetary Kinematics, Unified Pointer Drag, Inertia, Camera Zoom & Controls
 *
 * Implements:
 * - Direct Pointer Events manipulation (mouse, touch, trackpad)
 * - 1:1 rotation projection into Earth's tilted axial reference frame (-23.44°)
 * - Rotational inertia with 0.955 friction damping
 * - Hard latitude clamping [-85°, +85°]
 * - Smooth camera zoom (mouse wheel & touch pinch) clamped [1.55, 6.0]
 * - Smooth auto-rotation resumption after 2.5s idle
 * - Telemetry readouts: ALTITUDE (dynamic with zoom), SUB-SATELLITE coords, PERIOD
 * - Accessibility: prefers-reduced-motion & keyboard navigation
 */

import * as THREE from './three.module.js';

export class EarthControls {
  constructor({
    domElement,
    camera,
    earthGroup,
    cloudsGroup,
    surfaceMaterial,
    onTelemetryUpdate
  }) {
    this.domElement = domElement;
    this.camera = camera;
    this.earthGroup = earthGroup;
    this.cloudsGroup = cloudsGroup;
    this.surfaceMaterial = surfaceMaterial;
    this.onTelemetryUpdate = onTelemetryUpdate;

    // Kinematics State
    this.rotationY = 0.0;     // Longitude (degrees) [0, 360)
    this.rotationX = 0.0;     // Latitude (degrees) [-85, +85]
    this.velocityY = 0.0;     // Angular velocity Y (deg/frame)
    this.velocityX = 0.0;     // Angular velocity X (deg/frame)

    this.autoRotateSpeed = 360.0 / 90.0; // deg/sec for 90s period (4.0 deg/s)
    this.autoRotateRamp = 1.0;
    this.cloudDrift = 0.0;
    this.isPaused = false;

    // Pointer Drag State
    this.isDragging = false;
    this.activePointerId = null;
    this.lastPointerX = 0;
    this.lastPointerY = 0;
    this.lastPointerTime = 0;
    this.lastInteractionTime = performance.now();

    // Multi-touch Pinch Zoom
    this.activePointers = new Map();
    this.initialPinchDistance = 0;
    this.initialPinchCameraDistance = 3.2;

    // Camera Zoom State
    this.cameraDistance = 3.2;
    this.targetCameraDistance = 3.2;
    this.minCameraDistance = 1.55;
    this.maxCameraDistance = 6.0;

    // Reduced Motion Detection
    this.isReducedMotion = false;
    this.mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
    this.isReducedMotion = this.mediaQuery.matches;
    this.mediaQuery.addEventListener('change', (e) => {
      this.isReducedMotion = e.matches;
      if (this.isReducedMotion) {
        this.velocityX = 0;
        this.velocityY = 0;
        this.autoRotateRamp = 0;
      }
    });

    this.bindEvents();
  }

  bindEvents() {
    const el = this.domElement;

    // Pointer events
    el.addEventListener('pointerdown', this.onPointerDown.bind(this), { passive: false });
    window.addEventListener('pointermove', this.onPointerMove.bind(this), { passive: false });
    window.addEventListener('pointerup', this.onPointerUp.bind(this));
    window.addEventListener('pointercancel', this.onPointerUp.bind(this));
    el.addEventListener('dragstart', (e) => e.preventDefault());

    // Wheel zoom
    el.addEventListener('wheel', this.onWheel.bind(this), { passive: false });

    // Keyboard navigation
    el.addEventListener('keydown', this.onKeyDown.bind(this));
    window.addEventListener('keydown', (e) => {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'BUTTON') return;
      if (e.code === 'Space') {
        e.preventDefault();
        this.togglePause();
      }
    });
  }

  onPointerDown(e) {
    if (e.button !== 0 && e.pointerType === 'mouse') return;

    this.activePointers.set(e.pointerId, { x: e.clientX, y: e.clientY });

    if (this.activePointers.size === 1) {
      this.isDragging = true;
      this.activePointerId = e.pointerId;
      this.domElement.classList.add('is-dragging');

      try {
        this.domElement.setPointerCapture(e.pointerId);
      } catch (err) {}

      this.lastPointerX = e.clientX;
      this.lastPointerY = e.clientY;
      this.lastPointerTime = performance.now();
      this.lastInteractionTime = performance.now();

      this.velocityX = 0.0;
      this.velocityY = 0.0;
      this.autoRotateRamp = 0.0;
    } else if (this.activePointers.size === 2) {
      // Begin pinch zoom
      const pts = Array.from(this.activePointers.values());
      this.initialPinchDistance = Math.hypot(pts[0].x - pts[1].x, pts[0].y - pts[1].y);
      this.initialPinchCameraDistance = this.targetCameraDistance;
    }

    e.preventDefault();
  }

  onPointerMove(e) {
    if (this.activePointers.has(e.pointerId)) {
      this.activePointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
    }

    // Two-finger pinch zoom
    if (this.activePointers.size === 2) {
      const pts = Array.from(this.activePointers.values());
      const currentDist = Math.hypot(pts[0].x - pts[1].x, pts[0].y - pts[1].y);
      if (this.initialPinchDistance > 10) {
        const ratio = this.initialPinchDistance / Math.max(10, currentDist);
        this.targetCameraDistance = Math.max(
          this.minCameraDistance,
          Math.min(this.maxCameraDistance, this.initialPinchCameraDistance * ratio)
        );
      }
      this.lastInteractionTime = performance.now();
      e.preventDefault();
      return;
    }

    if (!this.isDragging || e.pointerId !== this.activePointerId) return;

    const now = performance.now();
    const dt = Math.max(1, now - this.lastPointerTime);
    const dx = e.clientX - this.lastPointerX;
    const dy = e.clientY - this.lastPointerY;

    // 1:1 natural sphere surface tracking
    const rect = this.domElement.getBoundingClientRect();
    const globeDiameter = Math.min(rect.width, rect.height) * (3.2 / this.cameraDistance);
    const sensitivity = 360.0 / (Math.PI * Math.max(200, globeDiameter));

    // Project screen delta into Earth's tilted axial frame (-23.44°)
    const tiltRad = (-23.44 * Math.PI) / 180.0;
    const cosTilt = Math.cos(-tiltRad);
    const sinTilt = Math.sin(-tiltRad);
    const dxTilted = dx * cosTilt - dy * sinTilt;
    const dyTilted = dx * sinTilt + dy * cosTilt;

    const dLon = -dxTilted * sensitivity;
    const dLat = dyTilted * sensitivity;

    this.rotationY += dLon;
    this.rotationX = Math.max(-85.0, Math.min(85.0, this.rotationX + dLat));

    // Normalized velocity calculation (deg per 60fps frame)
    const frameFactor = 16.67 / dt;
    const instVelY = dLon * frameFactor;
    const instVelX = dLat * frameFactor;

    this.velocityY = this.velocityY * 0.35 + instVelY * 0.65;
    this.velocityX = this.velocityX * 0.35 + instVelX * 0.65;

    this.lastPointerX = e.clientX;
    this.lastPointerY = e.clientY;
    this.lastPointerTime = now;
    this.lastInteractionTime = now;

    e.preventDefault();
  }

  onPointerUp(e) {
    this.activePointers.delete(e.pointerId);

    if (this.isDragging && e.pointerId === this.activePointerId) {
      this.isDragging = false;
      this.activePointerId = null;
      this.domElement.classList.remove('is-dragging');

      const now = performance.now();
      if (now - this.lastPointerTime > 80 || this.isReducedMotion) {
        this.velocityX = 0.0;
        this.velocityY = 0.0;
      } else {
        const MAX_FLING = 3.2;
        this.velocityX = Math.max(-MAX_FLING, Math.min(MAX_FLING, this.velocityX));
        this.velocityY = Math.max(-MAX_FLING, Math.min(MAX_FLING, this.velocityY));
      }

      try {
        this.domElement.releasePointerCapture(e.pointerId);
      } catch (err) {}

      this.lastInteractionTime = now;
    }
  }

  onWheel(e) {
    e.preventDefault();
    this.lastInteractionTime = performance.now();

    // Adaptive zoom delta based on current camera distance
    const zoomFactor = 0.0022 * (this.cameraDistance / 3.0);
    const delta = e.deltaY * zoomFactor;

    this.targetCameraDistance = Math.max(
      this.minCameraDistance,
      Math.min(this.maxCameraDistance, this.targetCameraDistance + delta)
    );
  }

  onKeyDown(e) {
    const STEP = 4.0;
    let handled = false;

    switch (e.key) {
      case 'ArrowLeft':
        this.rotationY -= STEP;
        handled = true;
        break;
      case 'ArrowRight':
        this.rotationY += STEP;
        handled = true;
        break;
      case 'ArrowUp':
        this.rotationX = Math.min(85.0, this.rotationX + STEP);
        handled = true;
        break;
      case 'ArrowDown':
        this.rotationX = Math.max(-85.0, this.rotationX - STEP);
        handled = true;
        break;
      case 'Home':
        this.rotationX = 0.0;
        this.rotationY = 0.0;
        handled = true;
        break;
    }

    if (handled) {
      e.preventDefault();
      this.lastInteractionTime = performance.now();
      this.autoRotateRamp = 0.0;
      this.velocityX = 0.0;
      this.velocityY = 0.0;
    }
  }

  togglePause() {
    this.isPaused = !this.isPaused;
    if (this.isPaused) {
      this.velocityX = 0.0;
      this.velocityY = 0.0;
      this.autoRotateRamp = 0.0;
    } else {
      this.lastInteractionTime = performance.now() - 3000;
    }
    return this.isPaused;
  }

  reset() {
    this.rotationX = 0.0;
    this.rotationY = 0.0;
    this.velocityX = 0.0;
    this.velocityY = 0.0;
    this.targetCameraDistance = 3.2;
    this.autoRotateRamp = 1.0;
    this.lastInteractionTime = performance.now();
    if (this.isPaused) {
      this.togglePause();
    }
  }

  update(dtSeconds, now) {
    // 1. Camera Zoom Damping
    this.cameraDistance += (this.targetCameraDistance - this.cameraDistance) * 0.14;
    this.camera.position.z = this.cameraDistance;

    // 2. Rotational Inertia
    if (!this.isDragging && !this.isReducedMotion) {
      const hasVelocity = Math.abs(this.velocityX) > 0.002 || Math.abs(this.velocityY) > 0.002;

      if (hasVelocity) {
        this.rotationY += this.velocityY;
        this.rotationX = Math.max(-85.0, Math.min(85.0, this.rotationX + this.velocityX));

        // 0.955 friction damping
        this.velocityX *= 0.955;
        this.velocityY *= 0.955;

        if (this.rotationX >= 85.0 || this.rotationX <= -85.0) {
          this.velocityX = 0.0;
        }
      } else {
        this.velocityX = 0.0;
        this.velocityY = 0.0;
      }

      // Auto-rotation resume after 2.5s idle
      const timeSinceInteraction = now - this.lastInteractionTime;
      if (!this.isPaused && timeSinceInteraction > 2500) {
        this.autoRotateRamp = Math.min(1.0, this.autoRotateRamp + dtSeconds * 0.5);
        this.rotationY += this.autoRotateSpeed * this.autoRotateRamp * dtSeconds;
      }
    }

    // 3. Independent Cloud Drift
    if (!this.isPaused && !this.isReducedMotion) {
      this.cloudDrift += 0.85 * dtSeconds; // subtle eastward cloud circulation
    }

    // Wrap longitude into [0, 360)
    this.rotationY = ((this.rotationY % 360.0) + 360.0) % 360.0;

    // 4. Update Three.js Meshes
    // Earth group holds planet surface
    const lonRad = THREE.MathUtils.degToRad(-this.rotationY);
    const latRad = THREE.MathUtils.degToRad(this.rotationX);

    if (this.earthGroup) {
      this.earthGroup.rotation.y = lonRad;
      this.earthGroup.rotation.x = latRad;
    }

    if (this.cloudsGroup) {
      const cloudLonRad = THREE.MathUtils.degToRad(-(this.rotationY + this.cloudDrift));
      this.cloudsGroup.rotation.y = cloudLonRad;
      this.cloudsGroup.rotation.x = latRad;
    }

    // Update cloud offset for surface shadow projection
    if (this.surfaceMaterial && this.surfaceMaterial.uniforms) {
      this.surfaceMaterial.uniforms.uCloudOffset.value = (this.cloudDrift / 360.0) % 1.0;
    }

    // 5. Telemetry updates
    if (this.onTelemetryUpdate) {
      // Dynamic altitude based on camera distance
      const zoomRatio = (this.cameraDistance - this.minCameraDistance) / (this.maxCameraDistance - this.minCameraDistance);
      // Close zoom (1.55) is ~420 km; default zoom (3.2) is ~35,786 km; distant zoom (6.0) is ~120,000 km
      const altKm = Math.round(420 + Math.pow(zoomRatio, 2.1) * 119580);

      // Coordinates
      const latAbs = Math.abs(this.rotationX).toFixed(1);
      const latHem = this.rotationX >= 0 ? 'N' : 'S';
      const lonNorm = ((this.rotationY % 360.0) + 360.0) % 360.0;
      const lon180 = lonNorm > 180.0 ? lonNorm - 360.0 : lonNorm;
      const lonAbs = Math.abs(lon180).toFixed(1);
      const lonHem = lon180 >= 0 ? 'E' : 'W';

      this.onTelemetryUpdate({
        altitude: `${altKm.toLocaleString()} km`,
        coordinates: `${latAbs}\u00B0 ${latHem}, ${lonAbs}\u00B0 ${lonHem}`,
        period: `${(360.0 / this.autoRotateSpeed).toFixed(1)}s`
      });
    }
  }
}
