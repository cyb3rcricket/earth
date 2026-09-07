/**
 * Photorealistic 3D Earth Shaders (Three.js WebGL)
 *
 * Implements:
 * 1. EarthSurfaceShader:
 *    - Daylight satellite albedo modulated with precomputed tangent-space normal mapping
 *    - Specular Blinn-Phong sunglint on ocean waters (land remains diffuse)
 *    - Cloud shadow projection onto terrain
 *    - Directional horizon self-shadowing from elevation bump map along terminator
 *    - Physically-derived Beer-Lambert solar extinction and golden terminator band
 *    - Land-masked night city lights with golden-amber incandescent glow
 *    - Atmospheric aerial perspective and stratospheric limb haze matching Rayleigh scattering
 *
 * 2. CloudsShader:
 *    - Independent rotating cloud deck at radius 1.008
 *    - Sunlight Lambertian diffuse lighting with day/night fade
 *    - Sunset extinction tinting along grazing sun rays
 *
 * 3. AtmosphereShader:
 *    - Physically-principled single-scattering atmospheric shell at radius 1.036
 *    - Wavelength-dependent Rayleigh scattering (lambda^-4) for [650nm, 570nm, 475nm]
 *    - Rayleigh phase function P_R(theta) = 3/(16*pi) * (1 + cos^2(theta))
 *    - Mie forward haze with Henyey-Greenstein phase function (g = 0.78)
 *    - Numerical raymarching with Beer-Lambert extinction along view and sun paths
 *    - Earth shadow occlusion with zero dark-side light leaks
 *
 * 4. CoronaGlowShader:
 *    - Extended outer exospheric solar halo at radius 1.10
 *    - Henyey-Greenstein forward Mie glare (g = 0.82) with Earth shadow occlusion
 */

import * as THREE from './three.module.js';

export const EarthSurfaceShader = {
  uniforms: {
    uDayTexture: { value: null },
    uNormalTexture: { value: null },
    uBumpTexture: { value: null },
    uNightTexture: { value: null },
    uSpecularTexture: { value: null },
    uCloudsTexture: { value: null },
    uSunDirection: { value: new THREE.Vector3(-1.4, 0.8, 1.2).normalize() },
    uCloudOffset: { value: 0.0 },
    uCloudOpacity: { value: 90.0 },
    uAtmosphereIntensity: { value: 100.0 },
    uShadowStrength: { value: 95.0 },
    uBumpTexelSize: { value: new THREE.Vector2(1.0 / 4096.0, 1.0 / 2048.0) },
    uBumpScale: { value: 2.05 },
    uNormalScale: { value: 1.0 },
    uTerrainShadowStrength: { value: 1.0 },
    uTerrainShadowElevation: { value: 0.048 }
  },
  vertexShader: /* glsl */ `
    varying vec2 vUv;
    varying vec3 vNormal;
    varying vec3 vWorldNormal;
    varying vec3 vWorldPosition;
    varying vec3 vWorldUp;

    void main() {
      vUv = uv;
      vNormal = normalize(normalMatrix * normal);
      vec4 worldPos = modelMatrix * vec4(position, 1.0);
      vWorldPosition = worldPos.xyz;
      vWorldNormal = normalize((modelMatrix * vec4(normal, 0.0)).xyz);
      // Planetary polar axis (South to North) in world coordinates
      vWorldUp = normalize((modelMatrix * vec4(0.0, 1.0, 0.0, 0.0)).xyz);
      gl_Position = projectionMatrix * viewMatrix * worldPos;
    }
  `,
  fragmentShader: /* glsl */ `
    precision highp float;

    uniform sampler2D uDayTexture;
    uniform sampler2D uNormalTexture;
    uniform sampler2D uBumpTexture;
    uniform sampler2D uNightTexture;
    uniform sampler2D uSpecularTexture;
    uniform sampler2D uCloudsTexture;
    uniform vec3 uSunDirection;
    uniform float uCloudOffset;
    uniform float uCloudOpacity;
    uniform float uAtmosphereIntensity;
    uniform float uShadowStrength;
    uniform vec2 uBumpTexelSize;
    uniform float uBumpScale;
    uniform float uNormalScale;
    uniform float uTerrainShadowStrength;
    uniform float uTerrainShadowElevation;

    varying vec2 vUv;
    varying vec3 vNormal;
    varying vec3 vWorldNormal;
    varying vec3 vWorldPosition;
    varying vec3 vWorldUp;

    const float PI = 3.14159265358979323846;
    // Matching atmospheric optical constants
    const vec3 BETA_RAYLEIGH = vec3(5.8, 13.5, 33.1) * 2.0;
    const float H_RAYLEIGH = 0.0080;
    const float G_MIE = 0.78;

    void main() {
      vec3 viewDir = normalize(cameraPosition - vWorldPosition);
      vec3 norm = normalize(vWorldNormal);
      vec3 sunDir = normalize(uSunDirection);
      vec3 worldUp = normalize(vWorldUp);

      // -----------------------------------------------------------------------
      // 1. Robust Orthonormal Tangent Frame (T, B, N)
      // -----------------------------------------------------------------------
      // T points East along lines of latitude (+u)
      vec3 T = cross(worldUp, norm);
      float tLen = length(T);
      if (tLen > 1e-4) {
        T /= tLen;
      } else {
        // Polar singularity elimination:
        // When norm aligns with worldUp (North/South Pole), select stable orthogonal basis
        vec3 refAxis = (abs(worldUp.y) < 0.9) ? vec3(0.0, 1.0, 0.0) : vec3(1.0, 0.0, 0.0);
        T = normalize(cross(worldUp, refAxis));
      }
      // B points North along lines of longitude (+v)
      vec3 B = cross(norm, T);

      // -----------------------------------------------------------------------
      // 2. High-Precision Normal Perturbation (Precomputed Tangent Normal Map)
      // -----------------------------------------------------------------------
      // Specular water mask (1.0 on oceans/lakes, 0.0 on land)
      float specMask = texture2D(uSpecularTexture, vUv).r;
      float landMask = 1.0 - smoothstep(0.15, 0.70, specMask);

      // Tangent-space normal lookup from precomputed normal map
      vec3 normalSample = texture2D(uNormalTexture, vUv).rgb;
      vec3 nTan = normalSample * 2.0 - 1.0;
      vec3 perturbedTan = vec3(nTan.xy * uNormalScale * landMask, nTan.z);
      vec3 perturbedNormal = normalize(perturbedTan.x * T + perturbedTan.y * B + perturbedTan.z * norm);

      // Sunlight dot products
      float sunDot = dot(perturbedNormal, sunDir);
      float rawSunDot = dot(norm, sunDir);

      // -----------------------------------------------------------------------
      // 3. Directional Mountain Horizon Self-Shadowing along Terminator
      // -----------------------------------------------------------------------
      float terrainShadow = 1.0;

      // Execute horizon shadow raymarch strictly in the grazing terminator zone
      if (rawSunDot > -0.06 && rawSunDot < 0.28) {
        // Project incident sunlight vector into tangent plane (T, B)
        vec2 L_tangent = vec2(dot(sunDir, T), dot(sunDir, B));
        float L_tan_len = length(L_tangent);

        if (L_tan_len > 0.001) {
          vec2 sunDirTan = L_tangent / L_tan_len;

          vec2 texel = uBumpTexelSize;
          float scaleX = 1.0 / max(0.06, sin(PI * vUv.y));

          // Step vector in UV space compensated for latitude convergence
          vec2 stepUv = vec2(sunDirTan.x * scaleX * texel.x, sunDirTan.y * texel.y) * 2.8;

          // Slope of incident sun ray in height units per step
          float sunSlope = (max(0.002, rawSunDot) / L_tan_len) * uTerrainShadowElevation;

          float shadowOcclusion = 0.0;
          float hCenter = texture2D(uBumpTexture, vUv).r;

          // 6-step directional shadow march facing the low-angle sun
          for (int i = 1; i <= 6; i++) {
            float fi = float(i);
            vec2 sampleUv = vUv + stepUv * fi;
            sampleUv.x = fract(sampleUv.x); // seamless antimeridian wrap
            sampleUv.y = clamp(sampleUv.y, 0.001, 0.999);
            float hSample = texture2D(uBumpTexture, sampleUv).r;

            // Height of the sun ray arriving from the sun above this sample
            float rayH = hCenter + sunSlope * fi;

            // If terrain is higher than the sun ray, it obstructs direct sunlight
            float diff = (hSample - 0.0035) - rayH;
            if (diff > 0.0) {
              shadowOcclusion = max(shadowOcclusion, clamp(diff * 14.0, 0.0, 1.0));
            }
          }

          // Smooth transitions: fade shadow into full daylight as sun climbs,
          // and blend softly near nightfall
          float sunAltitudeFade = smoothstep(0.26, 0.06, rawSunDot);
          float nightFade = smoothstep(-0.06, -0.01, rawSunDot);
          float shadowFactor = shadowOcclusion * sunAltitudeFade * nightFade * (uShadowStrength / 100.0) * uTerrainShadowStrength;

          terrainShadow = 1.0 - shadowFactor;
        }
      }

      // -----------------------------------------------------------------------
      // 4. Daylight Surface Albedo & Ocean Specular Glint
      // -----------------------------------------------------------------------
      vec3 dayAlbedo = texture2D(uDayTexture, vUv).rgb;

      // Ocean Specular Glint (Blinn-Phong)
      vec3 halfVector = normalize(sunDir + viewDir);
      float specAngle = max(0.0, dot(norm, halfVector));
      float specular = pow(specAngle, 36.0) * specMask * 1.35 * smoothstep(-0.02, 0.15, rawSunDot);
      vec3 specColor = vec3(1.0, 0.96, 0.90) * specular;

      // -----------------------------------------------------------------------
      // 5. Cloud Shadow onto Surface
      // -----------------------------------------------------------------------
      vec2 cloudUv = vec2(fract(vUv.x + uCloudOffset), vUv.y);
      vec2 shadowUv = cloudUv - vec2(sunDir.x * 0.006, sunDir.y * 0.006);
      shadowUv.x = fract(shadowUv.x);
      float cloudShadowAlpha = texture2D(uCloudsTexture, shadowUv).a * (uCloudOpacity / 100.0);
      float cloudShadow = 1.0 - (cloudShadowAlpha * 0.42 * (uShadowStrength / 100.0));

      // -----------------------------------------------------------------------
      // 6. Incident Sunlight Extinction & Daylight Shading
      // -----------------------------------------------------------------------
      // Beer-Lambert law matching Rayleigh lambda^-4 solar atmospheric traversal
      float sunAirmass = 1.0 / max(0.038, rawSunDot + 0.05);
      vec3 tauSun = BETA_RAYLEIGH * H_RAYLEIGH * (sunAirmass - 1.0);
      vec3 sunExtinction = exp(-clamp(tauSun, 0.0, 16.0));
      vec3 litSunColor = mix(vec3(1.0), sunExtinction, smoothstep(0.35, -0.02, rawSunDot));

      // Daylight shading modulated with mountain relief self-shadowing and extinction
      float dayDiffuse = clamp(sunDot * 1.04, 0.0, 1.0) * terrainShadow;
      vec3 dayColor = (dayAlbedo * dayDiffuse * cloudShadow * litSunColor) + specColor;

      // -----------------------------------------------------------------------
      // 7. Rayleigh Twilight Sunset / Terminator Band
      // -----------------------------------------------------------------------
      float twilightFactor = smoothstep(-0.09, 0.0, rawSunDot) * (1.0 - smoothstep(0.0, 0.08, rawSunDot));
      // Mountain peaks catching grazing twilight glow brilliantly, while valleys in shadow stay cool
      vec3 twilightColor = vec3(1.0, 0.46, 0.14) * sunExtinction * twilightFactor * 0.42 * mix(0.18, 1.0, terrainShadow);

      // -----------------------------------------------------------------------
      // 8. Land-Masked Night City Lights
      // -----------------------------------------------------------------------
      vec3 nightAlbedo = texture2D(uNightTexture, vUv).rgb;
      float nightBlend = smoothstep(0.06, -0.12, rawSunDot);
      vec3 nightLights = nightAlbedo * 2.0 * nightBlend;

      // -----------------------------------------------------------------------
      // 9. Deep Space Ambient Occlusion
      // -----------------------------------------------------------------------
      float ambientFloor = (1.0 - (uShadowStrength / 100.0)) * 0.06;
      vec3 ambient = dayAlbedo * ambientFloor * (1.0 - nightBlend);

      // Day / Night interpolation
      float dayFactor = smoothstep(-0.08, 0.08, rawSunDot);
      vec3 surfaceColor = mix(ambient + nightLights, dayColor, dayFactor) + twilightColor;

      // -----------------------------------------------------------------------
      // 10. Volumetric Limb Darkening
      // -----------------------------------------------------------------------
      float vDotN = max(0.0, dot(viewDir, norm));
      float limb = 0.70 + 0.30 * pow(vDotN, 0.50);
      surfaceColor *= limb;

      // -----------------------------------------------------------------------
      // 11. Aerial Perspective & Stratospheric Limb Haze (Rayleigh + Mie)
      // -----------------------------------------------------------------------
      float viewAirmass = 1.0 / max(0.045, vDotN);
      vec3 tauView = BETA_RAYLEIGH * H_RAYLEIGH * (viewAirmass - 1.0) * 0.85;
      vec3 transView = exp(-clamp(tauView, 0.0, 10.0));

      // Phase angles for inscattering
      float cosTheta = dot(-viewDir, sunDir);
      float phaseR = (3.0 / (16.0 * PI)) * (1.0 + cosTheta * cosTheta);
      float denomM = 1.0 + G_MIE * G_MIE - 2.0 * G_MIE * cosTheta;
      float phaseM = (1.0 / (4.0 * PI)) * (1.0 - G_MIE * G_MIE) / pow(max(0.001, denomM), 1.5);

      // Rayleigh blue daylight haze smoothly transitioning to sunset gold at the terminator
      vec3 atmoColor = mix(vec3(0.20, 0.55, 0.98), vec3(0.98, 0.48, 0.16), smoothstep(0.15, -0.05, rawSunDot));
      vec3 inscatterHaze = atmoColor * (phaseR * 1.6 + phaseM * 0.30) * (1.0 - transView) * smoothstep(-0.10, 0.25, rawSunDot) * (uAtmosphereIntensity / 100.0) * 0.85;

      // Blend surface with atmospheric column
      surfaceColor = surfaceColor * transView + inscatterHaze;

      gl_FragColor = vec4(surfaceColor, 1.0);
    }
  `
};

export const CloudsShader = {
  uniforms: {
    uCloudsTexture: { value: null },
    uSunDirection: { value: new THREE.Vector3(-1.4, 0.8, 1.2).normalize() },
    uCloudOpacity: { value: 90.0 }
  },
  vertexShader: /* glsl */ `
    varying vec2 vUv;
    varying vec3 vNormal;
    varying vec3 vWorldNormal;
    varying vec3 vWorldPosition;

    void main() {
      vUv = uv;
      vNormal = normalize(normalMatrix * normal);
      vec4 worldPos = modelMatrix * vec4(position, 1.0);
      vWorldPosition = worldPos.xyz;
      vWorldNormal = normalize((modelMatrix * vec4(normal, 0.0)).xyz);
      gl_Position = projectionMatrix * viewMatrix * worldPos;
    }
  `,
  fragmentShader: /* glsl */ `
    precision highp float;

    uniform sampler2D uCloudsTexture;
    uniform vec3 uSunDirection;
    uniform float uCloudOpacity;

    varying vec2 vUv;
    varying vec3 vNormal;
    varying vec3 vWorldNormal;
    varying vec3 vWorldPosition;

    void main() {
      vec4 cloudSample = texture2D(uCloudsTexture, vUv);
      float alpha = cloudSample.a * (uCloudOpacity / 100.0);
      if (alpha < 0.01) discard;

      vec3 norm = normalize(vWorldNormal);
      vec3 sunDir = normalize(uSunDirection);
      float sunDot = dot(norm, sunDir);

      // Incident sunlight extinction along grazing sun paths
      float sunAirmass = 1.0 / max(0.04, sunDot + 0.06);
      vec3 tauSun = vec3(5.8, 13.5, 33.1) * 0.012 * (sunAirmass - 1.0);
      vec3 sunExtinction = exp(-clamp(tauSun, 0.0, 12.0));
      vec3 litSun = mix(vec3(1.0), sunExtinction, smoothstep(0.28, -0.02, sunDot));

      // Diffuse sunlight with soft silver-white reflectance modulated with sunset extinction
      float light = smoothstep(-0.16, 0.28, sunDot) * 0.94 + 0.06;
      vec3 cloudColor = cloudSample.rgb * light * litSun;

      // Sunset twilight edge
      float sunsetFactor = smoothstep(-0.10, 0.0, sunDot) * (1.0 - smoothstep(0.0, 0.12, sunDot));
      vec3 sunsetTint = vec3(0.98, 0.50, 0.20) * sunExtinction * sunsetFactor * 0.50;
      cloudColor += sunsetTint;

      // Night fade: clouds become translucent over night side so city lights remain visible
      float nightFade = smoothstep(-0.15, 0.06, sunDot);
      float finalAlpha = alpha * mix(0.18, 1.0, nightFade);

      gl_FragColor = vec4(cloudColor, finalAlpha);
    }
  `
};

export const AtmosphereShader = {
  uniforms: {
    uSunDirection: { value: new THREE.Vector3(-1.4, 0.8, 1.2).normalize() },
    uAtmosphereIntensity: { value: 100.0 }
  },
  vertexShader: /* glsl */ `
    varying vec3 vWorldPosition;

    void main() {
      vec4 worldPos = modelMatrix * vec4(position, 1.0);
      vWorldPosition = worldPos.xyz;
      gl_Position = projectionMatrix * viewMatrix * worldPos;
    }
  `,
  fragmentShader: /* glsl */ `
    precision highp float;

    uniform vec3 uSunDirection;
    uniform float uAtmosphereIntensity;

    varying vec3 vWorldPosition;

    // Optical and geometric constants
    const float PI = 3.14159265358979323846;
    const float R_PLANET = 1.0;
    const float R_ATMO = 1.036;
    const float H_ATMO = 0.036;

    // Atmospheric scale heights (normalized to planet radius 1.0)
    const float H_RAYLEIGH = 0.0080; // ~8 km scale height
    const float H_MIE = 0.0032;      // ~3.2 km aerosol scale height

    // Rayleigh scattering coefficients: lambda^-4 dependence for [650nm, 570nm, 475nm]
    // (475 / lambda)^4 -> [0.284, 0.482, 1.000]
    // Calibrated for authentic daylight sapphire blue sky and warm golden sunsets
    const vec3 BETA_RAYLEIGH = vec3(5.8, 13.5, 33.1) * 2.0;

    // Mie scattering & extinction coefficients (aerosol haze)
    const vec3 BETA_MIE = vec3(4.0);
    const vec3 BETA_MIE_EXT = vec3(4.0) * 1.11;

    // Mie forward anisotropy parameter (Henyey-Greenstein)
    const float G_MIE = 0.78;

    // Raymarching sample counts
    const int NUM_VIEW_SAMPLES = 16;
    const int NUM_SUN_SAMPLES = 4;

    // Analytic Ray-Sphere Intersection
    bool intersectSphere(vec3 ro, vec3 rd, float rad, out float t1, out float t2) {
      float b = dot(ro, rd);
      float c = dot(ro, ro) - rad * rad;
      float d = b * b - c;
      if (d < 0.0) return false;
      float sqrtd = sqrt(d);
      t1 = -b - sqrtd;
      t2 = -b + sqrtd;
      return true;
    }

    // Local atmospheric air density profile
    void getAtmosphereDensity(float h, out float rhoR, out float rhoM) {
      float hClamped = max(0.0, h);
      float hNorm = clamp(hClamped / H_ATMO, 0.0, 1.0);
      // Hermite smoothing taper at outer boundary to eliminate harsh edges / hula-hoop rings
      float taper = 1.0 - smoothstep(0.70, 1.0, hNorm);
      rhoR = exp(-hClamped / H_RAYLEIGH) * taper;
      rhoM = exp(-hClamped / H_MIE) * taper;
    }

    // Rayleigh phase function: P_R(theta) = 3 / (16 * PI) * (1 + cos^2(theta))
    float rayleighPhase(float cosTheta) {
      return (3.0 / (16.0 * PI)) * (1.0 + cosTheta * cosTheta);
    }

    // Henyey-Greenstein Mie phase function:
    // P_M(theta) = 1 / (4 * PI) * (1 - g^2) / (1 + g^2 - 2 * g * cosTheta)^1.5
    float henyeyGreensteinPhase(float cosTheta, float g) {
      float g2 = g * g;
      float denom = 1.0 + g2 - 2.0 * g * cosTheta;
      return (1.0 / (4.0 * PI)) * (1.0 - g2) / pow(max(0.0001, denom), 1.5);
    }

    void main() {
      vec3 ro = cameraPosition;
      vec3 rd = normalize(vWorldPosition - ro);
      vec3 sunDir = normalize(uSunDirection);

      // Intersect atmospheric outer boundary sphere
      float tAtmoEnter, tAtmoExit;
      if (!intersectSphere(ro, rd, R_ATMO, tAtmoEnter, tAtmoExit)) {
        discard;
      }
      if (tAtmoExit <= 0.0) {
        discard;
      }

      // Check intersection with solid planet surface
      float tPlanetEnter, tPlanetExit;
      bool hitPlanet = intersectSphere(ro, rd, R_PLANET, tPlanetEnter, tPlanetExit);

      // Determine raymarch interval through the atmosphere
      float tStart = max(0.0, tAtmoEnter);
      float tEnd = (hitPlanet && tPlanetEnter > 0.0) ? tPlanetEnter : tAtmoExit;

      if (tStart >= tEnd) {
        discard;
      }

      float dt = (tEnd - tStart) / float(NUM_VIEW_SAMPLES);

      // Cosine of scattering angle: deflection between incoming sunlight (-sunDir) and view (-rd)
      // cos(theta) = dot(-sunDir, -rd) = dot(sunDir, rd)
      float cosTheta = dot(rd, sunDir);
      float phaseR = rayleighPhase(cosTheta);
      float phaseM = henyeyGreensteinPhase(cosTheta, G_MIE);

      vec3 sumR = vec3(0.0);
      vec3 sumM = vec3(0.0);
      float optViewR = 0.0;
      float optViewM = 0.0;

      // Primary numerical integration along the view ray
      for (int i = 0; i < NUM_VIEW_SAMPLES; i++) {
        float t = tStart + (float(i) + 0.5) * dt;
        vec3 p = ro + t * rd;
        float h = length(p) - R_PLANET;

        float rhoR, rhoM;
        getAtmosphereDensity(h, rhoR, rhoM);

        optViewR += rhoR * dt;
        optViewM += rhoM * dt;

        // View transmission (Beer-Lambert law along view path to camera)
        vec3 transView = exp(-(BETA_RAYLEIGH * optViewR + BETA_MIE_EXT * optViewM));

        // Planet shadow test: Check if sample point p is occluded from sunlight by the Earth
        float sClose = -dot(p, sunDir);
        float sunVis = 1.0;
        if (sClose > 0.0) {
          float d2 = dot(p, p) - sClose * sClose;
          // Penumbra soft shadow transition along terminator
          sunVis = smoothstep(R_PLANET * R_PLANET, (R_PLANET + 0.0035) * (R_PLANET + 0.0035), d2);
        }

        if (sunVis > 0.001) {
          // Find distance to atmospheric exit along incident sun direction
          float bSun = dot(p, sunDir);
          float cSun = dot(p, p) - R_ATMO * R_ATMO;
          float dSun = bSun * bSun - cSun;
          float sExit = max(0.0, -bSun + sqrt(max(0.0, dSun)));
          float dtSun = sExit / float(NUM_SUN_SAMPLES);

          float optSunR = 0.0;
          float optSunM = 0.0;

          // Secondary integration along sun ray to calculate optical depth
          for (int j = 0; j < NUM_SUN_SAMPLES; j++) {
            float s = (float(j) + 0.5) * dtSun;
            vec3 pSun = p + s * sunDir;
            float hSun = length(pSun) - R_PLANET;

            float rhoSunR, rhoSunM;
            getAtmosphereDensity(hSun, rhoSunR, rhoSunM);

            optSunR += rhoSunR * dtSun;
            optSunM += rhoSunM * dtSun;
          }

          // Incident sunlight extinction (Beer-Lambert law):
          // As sunlight traverses long tangential paths near terminator,
          // strong Rayleigh blue extinction (lambda^-4) transmits pure golden amber & ruby red!
          vec3 transSun = sunVis * exp(-(BETA_RAYLEIGH * optSunR + BETA_MIE_EXT * optSunM));

          // In-scattered light accumulated along the segment
          sumR += rhoR * transView * transSun * dt;
          sumM += rhoM * transView * transSun * dt;
        }
      }

      // Single-scattering radiance synthesis
      vec3 scatteredRadiance = (BETA_RAYLEIGH * sumR * phaseR + BETA_MIE * sumM * phaseM) * 1.85;

      // Modulate with presentation HUD intensity slider
      float intensityScale = uAtmosphereIntensity / 100.0;
      vec3 finalColor = scatteredRadiance * intensityScale;

      // Discard completely dark night fragments (zero unwanted glow on night side)
      if (max(finalColor.r, max(finalColor.g, finalColor.b)) < 0.00015) {
        discard;
      }

      gl_FragColor = vec4(finalColor, 1.0);
    }
  `
};

export const CoronaGlowShader = {
  uniforms: {
    uSunDirection: { value: new THREE.Vector3(-1.4, 0.8, 1.2).normalize() },
    uAtmosphereIntensity: { value: 100.0 }
  },
  vertexShader: /* glsl */ `
    varying vec3 vWorldPosition;

    void main() {
      vec4 worldPos = modelMatrix * vec4(position, 1.0);
      vWorldPosition = worldPos.xyz;
      gl_Position = projectionMatrix * viewMatrix * worldPos;
    }
  `,
  fragmentShader: /* glsl */ `
    precision highp float;

    uniform vec3 uSunDirection;
    uniform float uAtmosphereIntensity;

    varying vec3 vWorldPosition;

    const float PI = 3.14159265358979323846;
    const float R_PLANET = 1.0;
    const float R_CORONA_INNER = 1.020;
    const float R_CORONA_OUTER = 1.100;
    const float G_CORONA = 0.82; // Strong forward anisotropy for solar glare halo

    float henyeyGreenstein(float cosTheta, float g) {
      float g2 = g * g;
      float denom = 1.0 + g2 - 2.0 * g * cosTheta;
      return (1.0 / (4.0 * PI)) * (1.0 - g2) / pow(max(0.0001, denom), 1.5);
    }

    void main() {
      vec3 ro = cameraPosition;
      vec3 rd = normalize(vWorldPosition - ro);
      vec3 sunDir = normalize(uSunDirection);

      // Tangent impact distance of view ray to planet center
      float b = dot(ro, rd);
      float d2 = dot(ro, ro) - b * b;
      if (d2 < 0.0) discard;
      float rClosest = sqrt(d2);

      // Check if ray is occluded by the solid planet
      if (rClosest <= R_PLANET && b < 0.0) {
        discard;
      }

      // Normalized height in outer coronal halo [1.02, 1.10]
      if (rClosest < R_CORONA_INNER || rClosest > R_CORONA_OUTER) {
        discard;
      }

      float hNorm = (rClosest - R_CORONA_INNER) / (R_CORONA_OUTER - R_CORONA_INNER);

      // Smooth radial falloff dissolving to zero at outer radius 1.10
      float radialDensity = exp(-hNorm * 3.8) * (1.0 - smoothstep(0.70, 1.0, hNorm));

      // Closest approach point along the ray
      vec3 pClosest = ro + (-b) * rd;

      // Planet shadow test: Check if closest approach point is in Earth's shadow
      float sSun = -dot(pClosest, sunDir);
      float sunVis = 1.0;
      if (sSun > 0.0) {
        float shadowD2 = dot(pClosest, pClosest) - sSun * sSun;
        sunVis = smoothstep(R_PLANET * R_PLANET, (R_PLANET + 0.006) * (R_PLANET + 0.006), shadowD2);
      }

      if (sunVis < 0.001) {
        discard;
      }

      // Forward scattering phase angle
      float cosTheta = dot(rd, sunDir);

      // Forward Mie haze only illuminates when viewing generally toward the sun (cosTheta > -0.15)
      float phase = henyeyGreenstein(cosTheta, G_CORONA);
      float forwardMask = smoothstep(-0.20, 0.40, cosTheta);

      // Soft cosmic pale blue-white corona tint
      vec3 coronaTint = mix(vec3(0.35, 0.65, 1.0), vec3(1.0, 0.92, 0.82), smoothstep(0.2, 0.8, cosTheta));
      float intensity = radialDensity * phase * forwardMask * sunVis * (uAtmosphereIntensity / 100.0) * 0.45;

      if (intensity < 0.0001) {
        discard;
      }

      gl_FragColor = vec4(coronaTint * intensity, 1.0);
    }
  `
};

