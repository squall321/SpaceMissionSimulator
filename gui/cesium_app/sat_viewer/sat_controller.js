/**
 * sat_controller.js — 위성 3D 뷰어 메인 컨트롤러
 * SpaceD-AADE v0.4.0  Satellite 3D Viewer
 *
 * 공개 API (window):
 *   window.showSatViewer(cfg)   — 탭 활성화 시 Python에서 호출
 *   window.hideSatViewer()      — 탭 비활성화 시 Python에서 호출
 *   window.updateSatViewer(cfg) — 설정 변경 시 Python에서 호출
 */
import * as THREE      from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { buildSatellite, disposeSatellite } from './sat_builder.js';

// ── 상태 ────────────────────────────────────────────────────────────────────
let renderer    = null;
let scene       = null;
let camera      = null;
let controls    = null;
let satGroup    = null;
let animId      = null;
let initPromise = null;
let isVisible   = false;
let resizeObs   = null;

const CONT_ID  = 'satViewerContainer';
const HUD_ID   = 'satViewerHud';

// ── 별 배경 ──────────────────────────────────────────────────────────────────
function buildStarField() {
  const pos = new Float32Array(5000 * 3);
  for (let i = 0; i < pos.length; i++) pos[i] = (Math.random() - 0.5) * 300;
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  const mat = new THREE.PointsMaterial({ color: 0xffffff, size: 0.12, sizeAttenuation: true });
  scene.add(new THREE.Points(geo, mat));
}

// ── 조명 ────────────────────────────────────────────────────────────────────
function buildLights() {
  // 우주 환경광 (짙은 청색)
  scene.add(new THREE.AmbientLight(0x1a2840, 0.55));

  // 태양광 (따뜻한 흰색, shadow on)
  const sun = new THREE.DirectionalLight(0xfff4e0, 2.0);
  sun.position.set(5, 8, 4);
  sun.castShadow = true;
  sun.shadow.mapSize.setScalar(1024);
  sun.shadow.camera.near   = 0.05;
  sun.shadow.camera.far    = 60;
  sun.shadow.camera.left   = sun.shadow.camera.bottom = -6;
  sun.shadow.camera.right  = sun.shadow.camera.top    =  6;
  sun.shadow.bias = -0.0008;
  scene.add(sun);

  // 지구 반사광 (아래에서 올라오는 청록색)
  const earth = new THREE.DirectionalLight(0x2255cc, 0.40);
  earth.position.set(0, -5, 1);
  scene.add(earth);

  // 보조 채도광 (짙은 남색)
  const fill = new THREE.DirectionalLight(0x223355, 0.25);
  fill.position.set(-3, 1, -3);
  scene.add(fill);
}

// ── 초기화 (한 번만 실행) ────────────────────────────────────────────────────
async function initSatViewer() {
  const container = document.getElementById(CONT_ID);
  const canvas    = container.querySelector('canvas');
  const W = container.clientWidth  || 800;
  const H = container.clientHeight || 600;

  // ── 렌더러
  renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: false });
  renderer.setSize(W, H, false);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setClearColor(0x020508, 1);
  renderer.shadowMap.enabled  = true;
  renderer.shadowMap.type     = THREE.PCFSoftShadowMap;
  renderer.toneMapping        = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.2;

  // ── 씬
  scene = new THREE.Scene();
  scene.background = new THREE.Color(0x020508);

  // ── 카메라
  camera = new THREE.PerspectiveCamera(40, W / H, 0.001, 500);

  // ── 조명 + 별
  buildLights();
  buildStarField();

  // ── OrbitControls
  controls = new OrbitControls(camera, canvas);
  controls.enableDamping   = true;
  controls.dampingFactor   = 0.06;
  controls.autoRotate      = true;
  controls.autoRotateSpeed = 1.0;
  controls.minDistance     = 0.05;
  controls.maxDistance     = 50;

  // 수동 조작 → 3초 후 자동 회전 재개
  let resumeTimer = null;
  controls.addEventListener('start', () => {
    controls.autoRotate = false;
    clearTimeout(resumeTimer);
  });
  controls.addEventListener('end', () => {
    resumeTimer = setTimeout(() => { controls.autoRotate = true; }, 3000);
  });

  // ── ResizeObserver
  resizeObs = new ResizeObserver(() => {
    if (!renderer || !isVisible) return;
    const W = container.clientWidth;
    const H = container.clientHeight;
    if (W < 1 || H < 1) return;
    camera.aspect = W / H;
    camera.updateProjectionMatrix();
    renderer.setSize(W, H, false);
  });
  resizeObs.observe(container);
}

// ── 렌더 루프 ────────────────────────────────────────────────────────────────
function startLoop() {
  if (animId) return;
  (function tick() {
    animId = requestAnimationFrame(tick);
    controls?.update();
    renderer?.render(scene, camera);
  })();
}

function stopLoop() {
  if (animId) { cancelAnimationFrame(animId); animId = null; }
}

// ── 위성 재구성 ──────────────────────────────────────────────────────────────
function rebuildSatellite(cfg) {
  if (satGroup) { disposeSatellite(satGroup); scene.remove(satGroup); satGroup = null; }

  satGroup = buildSatellite(cfg);
  scene.add(satGroup);

  // 카메라 거리: bbox 기반 자동 조정
  const size  = satGroup.userData.size;
  const maxD  = Math.max(size.x, size.y, size.z);
  const dist  = maxD * 3.5;
  camera.position.set(dist * 0.7, dist * 0.5, dist);
  camera.lookAt(0, 0, 0);
  controls.target.set(0, 0, 0);
  controls.minDistance = maxD * 0.3;
  controls.maxDistance = maxD * 25;
  controls.update();

  // HUD 업데이트
  updateHUD(cfg, satGroup.userData.busLabel);
}

// ── HUD 오버레이 업데이트 ────────────────────────────────────────────────────
function updateHUD(cfg, busLabel) {
  const el = document.getElementById(HUD_ID);
  if (!el) return;
  const mass = (
    (Number(cfg.mass_bus_kg)         || 0) +
    (Number(cfg.mass_panel_kg)       || 0) +
    (Number(cfg.mass_electronics_kg) || 0) +
    (Number(cfg.mass_battery_kg)     || 0)
  ).toFixed(1);
  const power   = Number(cfg.total_power_w   || 0).toFixed(0);
  const modules = Number(cfg.dual_boards     || 0).toFixed(0);
  const apt     = Number(cfg.aperture_cm     || 0).toFixed(1);
  const panel   = Number(cfg.panel_area_m2   || 0).toFixed(1);

  el.innerHTML = `
    <div class="sv-title">◈ SATELLITE CONFIG</div>
    <div class="sv-row"><span class="sv-lbl">Bus Type</span><span class="sv-val sv-cyan">${busLabel}</span></div>
    <div class="sv-row"><span class="sv-lbl">Total Mass</span><span class="sv-val">${mass} kg</span></div>
    <div class="sv-row"><span class="sv-lbl">Power</span><span class="sv-val">${power} W</span></div>
    <div class="sv-row"><span class="sv-lbl">Dual Boards</span><span class="sv-val">${modules} ea</span></div>
    <div class="sv-row"><span class="sv-lbl">Panel Area</span><span class="sv-val">${panel} m²</span></div>
    <div class="sv-row"><span class="sv-lbl">Aperture</span><span class="sv-val">${apt} cm</span></div>
  `;
}

// ── Cesium 렌더 모드 제어 ─────────────────────────────────────────────────────
function setCesiumLowPower(on) {
  const v = window._cesiumViewer;
  if (!v) return;
  v.scene.requestRenderMode       = on;
  v.scene.maximumRenderTimeChange = on ? Infinity : 0;
}

// ── 공개 API ─────────────────────────────────────────────────────────────────

window.showSatViewer = function (cfg) {
  if (!initPromise) initPromise = initSatViewer();
  initPromise.then(() => {
    document.getElementById(CONT_ID).style.display = 'block';
    isVisible = true;
    setCesiumLowPower(true);
    rebuildSatellite(cfg || {});
    startLoop();
  });
};

window.hideSatViewer = function () {
  stopLoop();
  isVisible = false;
  document.getElementById(CONT_ID).style.display = 'none';
  setCesiumLowPower(false);
};

window.updateSatViewer = function (cfg) {
  if (!initPromise || !scene) return;
  initPromise.then(() => rebuildSatellite(cfg || {}));
};
