/**
 * Photorealistic 3D Earth Shaders (Three.js WebGL)
 *
 * Implements:
 * 1. EarthSurfaceShader:
 *    - Daylight satellite albedo modulated with terrain relief bump mapping
 *    - Specular Blinn-Phong sunglint on ocean waters (land remains diffuse)
 *    - Cloud shadow projection onto terrain
 *    - Rayleigh twilight sunset fringe along terminator
 *    - Land-masked night city lights with golden-amber incandescent glow
 *    - Limb darkening & stratospheric rim scattering
 *
 * 2. CloudsShader:
 *    - Independent rotating cloud deck at radius 1.008
 *    - Sunlight Lambertian diffuse lighting with day/night fade
 *    - Warm terminator sunset tinting
 *
 * 3. AtmosphereShader:
 *    - Ray-marched / Rayleigh scattering atmospheric shell at radius 1.025
 *    - Additive blending limb glow with sun forward-scattering
 *
 * 4. CoronaGlowShader:
 *    - Soft outer cosmic atmospheric corona at radius 1.10
 */

import * as THREE from './three.module.js';

export const EarthSurfaceShader = {
  uniforms: {
    uDayTexture: { value: null },
    uBumpTexture: { value: null },
    uNightTexture: { value: null },
    uSpecularTexture: { value: null },
    uCloudsTexture: { value: null },
    uSunDirection: { value: new THREE.Vector3(-1.4, 0.8, 1.2).normalize() },
    uCloudOffset: { value: 0.0 },
    uCloudOpacity: { value: 90.0 },
    uAtmosphereIntensity: { value: 100.0 },
    uShadowStrength: { value: 95.0 }
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
    uniform sampler2D uDayTexture;
    uniform sampler2D uBumpTexture;
    uniform sampler2D uNightTexture;
    uniform sampler2D uSpecularTexture;
    uniform sampler2D uCloudsTexture;
    uniform vec3 uSunDirection;
    uniform float uCloudOffset;
    uniform float uCloudOpacity;
    uniform float uAtmosphereIntensity;
    uniform float uShadowStrength;

    varying vec2 vUv;
    varying vec3 vNormal;
    varying vec3 vWorldNormal;
    varying vec3 vWorldPosition;

    void main() {
      vec3 viewDir = normalize(cameraPosition - vWorldPosition);
      vec3 norm = normalize(vWorldNormal);
      vec3 sunDir = normalize(uSunDirection);

      // Topographic elevation bump gradient
      vec2 texel = vec2(1.0 / 2048.0, 1.0 / 1024.0);
      float bCenter = texture2D(uBumpTexture, vUv).r;
      float bRight  = texture2D(uBumpTexture, vUv + vec2(texel.x * 2.0, 0.0)).r;
      float bUp     = texture2D(uBumpTexture, vUv + vec2(0.0, texel.y * 2.0)).r;
      vec3 bumpGrad = vec3((bRight - bCenter) * 1.5, (bUp - bCenter) * 1.5, 0.0);

      // Perturb normal for relief shading
      vec3 tangentX = normalize(cross(norm, vec3(0.0, 1.0, 0.0)));
      if (length(tangentX) < 0.01) tangentX = vec3(1.0, 0.0, 0.0);
      vec3 tangentY = cross(norm, tangentX);
      vec3 perturbedNormal = normalize(norm + tangentX * bumpGrad.x + tangentY * bumpGrad.y);

      // Sunlight angles
      float sunDot = dot(perturbedNormal, sunDir);
      float rawSunDot = dot(norm, sunDir);

      // 1. Daylight Surface
      vec3 dayAlbedo = texture2D(uDayTexture, vUv).rgb;

      // 2. Ocean Specular Glint (Blinn-Phong)
      float specMask = texture2D(uSpecularTexture, vUv).r;
      vec3 halfVector = normalize(sunDir + viewDir);
      float specAngle = max(0.0, dot(norm, halfVector));
      float specular = pow(specAngle, 36.0) * specMask * 1.35 * smoothstep(-0.02, 0.15, rawSunDot);
      vec3 specColor = vec3(1.0, 0.96, 0.90) * specular;

      // 3. Cloud Shadow onto surface
      // Offset cloud texture in direction opposite sun
      vec2 cloudUv = vec2(fract(vUv.x + uCloudOffset), vUv.y);
      vec2 shadowUv = cloudUv - vec2(sunDir.x * 0.006, sunDir.y * 0.006);
      shadowUv.x = fract(shadowUv.x);
      float cloudShadowAlpha = texture2D(uCloudsTexture, shadowUv).a * (uCloudOpacity / 100.0);
      float cloudShadow = 1.0 - (cloudShadowAlpha * 0.42);

      // Daylight shading
      float dayDiffuse = clamp(sunDot * 1.04, 0.0, 1.0);
      vec3 dayColor = (dayAlbedo * dayDiffuse * cloudShadow) + specColor;

      // 4. Rayleigh Twilight Sunset / Terminator Band
      float twilightFactor = smoothstep(-0.09, 0.0, rawSunDot) * (1.0 - smoothstep(0.0, 0.07, rawSunDot));
      vec3 twilightColor = vec3(0.94, 0.44, 0.16) * twilightFactor * 0.36;

      // 5. Land-Masked Night City Lights
      vec3 nightAlbedo = texture2D(uNightTexture, vUv).rgb;
      float nightBlend = smoothstep(0.06, -0.12, rawSunDot);
      vec3 nightLights = nightAlbedo * 2.0 * nightBlend;

      // 6. Deep Space Ambient Occlusion
      float ambientFloor = (1.0 - (uShadowStrength / 100.0)) * 0.06;
      vec3 ambient = dayAlbedo * ambientFloor * (1.0 - nightBlend);

      // Day / Night interpolation
      float dayFactor = smoothstep(-0.08, 0.08, rawSunDot);
      vec3 surfaceColor = mix(ambient + nightLights, dayColor, dayFactor) + twilightColor;

      // 7. Volumetric Limb Darkening
      float vDotN = max(0.0, dot(viewDir, norm));
      float limb = 0.68 + 0.32 * pow(vDotN, 0.45);
      surfaceColor *= limb;

      // 8. Cyan Stratospheric Limb Haze
      float rimFresnel = pow(1.0 - vDotN, 3.8) * smoothstep(-0.12, 0.28, rawSunDot);
      vec3 atmoRim = vec3(0.20, 0.55, 0.98) * rimFresnel * 0.55 * (uAtmosphereIntensity / 100.0);
      surfaceColor += atmoRim;

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

      // Diffuse sunlight with soft silver-white reflectance
      float light = smoothstep(-0.16, 0.28, sunDot) * 0.94 + 0.06;
      vec3 cloudColor = cloudSample.rgb * light;

      // Sunset twilight edge
      float sunsetFactor = smoothstep(-0.10, 0.0, sunDot) * (1.0 - smoothstep(0.0, 0.12, sunDot));
      vec3 sunsetTint = vec3(0.96, 0.50, 0.22) * sunsetFactor * 0.45;
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
    varying vec3 vNormal;
    varying vec3 vWorldPosition;

    void main() {
      vNormal = normalize(normalMatrix * normal);
      vec4 worldPos = modelMatrix * vec4(position, 1.0);
      vWorldPosition = worldPos.xyz;
      gl_Position = projectionMatrix * viewMatrix * worldPos;
    }
  `,
  fragmentShader: /* glsl */ `
    uniform vec3 uSunDirection;
    uniform float uAtmosphereIntensity;

    varying vec3 vNormal;
    varying vec3 vWorldPosition;

    void main() {
      vec3 viewDir = normalize(cameraPosition - vWorldPosition);
      vec3 norm = normalize(vNormal); // BackSide points inwards towards sphere center
      vec3 sunDir = normalize(uSunDirection);

      // Silhouette Fresnel falloff
      float viewAngle = dot(-norm, viewDir);
      float fresnel = pow(clamp(1.0 - abs(viewAngle), 0.0, 1.0), 3.2);

      // Forward sunlight scattering
      float sunDot = dot(-norm, sunDir);
      float sunLit = smoothstep(-0.25, 0.55, sunDot);

      // Rayleigh sapphire blue & sunset orange
      vec3 dayColor = vec3(0.22, 0.58, 1.0);
      vec3 sunsetColor = vec3(0.96, 0.48, 0.18);
      float sunsetFactor = smoothstep(-0.25, -0.06, sunDot) * (1.0 - smoothstep(-0.06, 0.18, sunDot));
      vec3 atmoColor = mix(dayColor, sunsetColor, sunsetFactor * 0.7);

      float intensity = fresnel * (sunLit * 0.85 + 0.15) * (uAtmosphereIntensity / 100.0) * 1.6;
      gl_FragColor = vec4(atmoColor * intensity, intensity);
    }
  `
};

export const CoronaGlowShader = {
  uniforms: {
    uSunDirection: { value: new THREE.Vector3(-1.4, 0.8, 1.2).normalize() },
    uAtmosphereIntensity: { value: 100.0 }
  },
  vertexShader: /* glsl */ `
    varying vec3 vNormal;
    varying vec3 vWorldPosition;

    void main() {
      vNormal = normalize(normalMatrix * normal);
      vec4 worldPos = modelMatrix * vec4(position, 1.0);
      vWorldPosition = worldPos.xyz;
      gl_Position = projectionMatrix * viewMatrix * worldPos;
    }
  `,
  fragmentShader: /* glsl */ `
    uniform vec3 uSunDirection;
    uniform float uAtmosphereIntensity;

    varying vec3 vNormal;
    varying vec3 vWorldPosition;

    void main() {
      vec3 viewDir = normalize(cameraPosition - vWorldPosition);
      vec3 norm = normalize(vNormal);
      vec3 sunDir = normalize(uSunDirection);

      float viewAngle = dot(-norm, viewDir);
      float fresnel = pow(clamp(1.0 - abs(viewAngle), 0.0, 1.0), 5.5);

      float sunDot = dot(-norm, sunDir);
      float sunLit = smoothstep(-0.35, 0.50, sunDot);

      vec3 coronaColor = vec3(0.15, 0.48, 0.95);
      float intensity = fresnel * (sunLit * 0.9 + 0.1) * (uAtmosphereIntensity / 100.0) * 0.75;
      gl_FragColor = vec4(coronaColor * intensity, intensity);
    }
  `
};
