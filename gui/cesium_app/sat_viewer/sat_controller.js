/**
 * sat_controller.js — 위성 3D 뷰어 메인 컨트롤러 (v0.5.0)
 * SpaceD-AADE  Satellite Scenario Viewer
 *
 * 공개 API (window):
 *   window.showSatViewer(scenarios)    — [{sat_id, name, sat_config}, ...]
 *   window.hideSatViewer()
 *   window.updateSatViewer(scenarios)  — 전체 재빌드
 *   window.selectSatInViewer(sat_id)   — 특정 위성 하이라이트
 */
import * as THREE        from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { buildSatellite, disposeSatellite } from './sat_builder.js';

// ── 상태 ────────────────────────────────────────────────────────────────────
let renderer    = null;
let scene       = null;
let camera      = null;
let controls    = null;
let animId      = null;
let initPromise = null;
let isVisible   = false;
let resizeObs   = null;

// 시나리오별 Three.js 그룹 관리: key=sat_id, value={group,label,rimLight,index,xOffset}
const satObjects  = new Map();
let selectedSatId = null;

const CONT_ID = 'satViewerContainer';
const HUD_ID  = 'satViewerHud';

// ── 위성 간 색상 팔레트 ────────────────────────────────────────────────────
const PALETTE = [
  0x00dcff, 0xff6b6b, 0x39ff96, 0xffa040,
  0xc080ff, 0xffdc40, 0x40c8ff, 0xff80c0,
];
function getPaletteColor(i) { return PALETTE[i % PALETTE.length]; }

// ── 캔버스 기반 이름 라벨 스프라이트 ────────────────────────────────────────
function makeLabel(text, color) {
  const w = 256, h = 48;
  const c = document.createElement('canvas');
  c.width = w; c.height = h;
  const ctx = c.getContext('2d');
  ctx.clearRect(0, 0, w, h);
  const hex = '#' + color.toString(16).padStart(6, '0');
  ctx.fillStyle = hex;
  ctx.font = 'bold 18px Consolas,monospace';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  const label = text.length > 18 ? text.slice(0, 17) + '…' : text;
  ctx.fillText(label, w / 2, h / 2);
  const tex = new THREE.CanvasTexture(c);
  const mat = new THREE.SpriteMaterial({ map: tex, transparent: true, depthTest: false });
  const sprite = new THREE.Sprite(mat);
  sprite.scale.set(1.6, 0.32, 1);
  return sprite;
}

// ── 림 라이트 (선택 하이라이트) ──────────────────────────────────────────────
function makeRimLight(color) {
  const l = new THREE.PointLight(color, 0, 8);
  return l;
}

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
  scene.add(new THREE.AmbientLight(0x1a2840, 0.55));

  const sun = new THREE.DirectionalLight(0xfff4e0, 2.0);
  sun.position.set(5, 8, 4);
  sun.castShadow = true;
  sun.shadow.mapSize.setScalar(1024);
  sun.shadow.camera.near   = 0.05;
  sun.shadow.camera.far    = 80;
  sun.shadow.camera.left   = sun.shadow.camera.bottom = -12;
  sun.shadow.camera.right  = sun.shadow.camera.top    =  12;
  sun.shadow.bias = -0.0008;
  scene.add(sun);

  const fill = new THREE.DirectionalLight(0x2255cc, 0.40);
  fill.position.set(0, -5, 1);
  scene.add(fill);

  const back = new THREE.DirectionalLight(0x223355, 0.25);
  back.position.set(-3, 1, -3);
  scene.add(back);
}

// ── 초기화 (한 번만 실행) ────────────────────────────────────────────────────
async function initSatViewer() {
  const container = document.getElementById(CONT_ID);
  const canvas    = container.querySelector('canvas');
  const W = container.clientWidth  || 800;
  const H = container.clientHeight || 600;

  renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: false });
  renderer.setSize(W, H, false);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setClearColor(0x020508, 1);
  renderer.shadowMap.enabled   = true;
  renderer.shadowMap.type      = THREE.PCFSoftShadowMap;
  renderer.toneMapping         = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.2;

  scene  = new THREE.Scene();
  scene.background = new THREE.Color(0x020508);
  camera = new THREE.PerspectiveCamera(40, W / H, 0.001, 500);

  buildLights();
  buildStarField();

  controls = new OrbitControls(camera, canvas);
  controls.enableDamping   = true;
  controls.dampingFactor   = 0.06;
  controls.autoRotate      = true;
  controls.autoRotateSpeed = 0.6;
  controls.minDistance     = 0.05;
  controls.maxDistance     = 100;

  let resumeTimer = null;
  controls.addEventListener('start', () => {
    controls.autoRotate = false;
    clearTimeout(resumeTimer);
  });
  controls.addEventListener('end', () => {
    resumeTimer = setTimeout(() => { controls.autoRotate = true; }, 3000);
  });

  // 클릭 선택
  canvas.addEventListener('pointerdown', onCanvasClick);

  resizeObs = new ResizeObserver(() => {
    if (!renderer || !isVisible) return;
    const W = container.clientWidth, H = container.clientHeight;
    if (W < 1 || H < 1) return;
    camera.aspect = W / H;
    camera.updateProjectionMatrix();
    renderer.setSize(W, H, false);
  });
  resizeObs.observe(container);
}

// ── 레이캐스터 클릭 선택 ─────────────────────────────────────────────────────
const _ray   = new THREE.Raycaster();
const _mouse = new THREE.Vector2();

function onCanvasClick(e) {
  const canvas = document.getElementById(CONT_ID).querySelector('canvas');
  const rect   = canvas.getBoundingClientRect();
  _mouse.set(
    ((e.clientX - rect.left)  / rect.width)  * 2 - 1,
    -((e.clientY - rect.top) / rect.height) * 2 + 1,
  );
  _ray.setFromCamera(_mouse, camera);
  const meshes = [];
  satObjects.forEach(({ group }, sid) =>
    group.traverse(o => { if (o.isMesh) { o.userData.__satId = sid; meshes.push(o); } })
  );
  const hits = _ray.intersectObjects(meshes, false);
  if (hits.length) selectSat(hits[0].object.userData.__satId);
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

// ── 위성 1기 씬에 추가 ───────────────────────────────────────────────────────
function addOneSatellite(scenario, index, xOffset) {
  const { sat_id, name, sat_config } = scenario;
  const colHex = getPaletteColor(index);

  const group = buildSatellite(sat_config);
  group.userData.cfg = sat_config;   // HUD 표시용
  group.position.set(xOffset, 0, 0);
  scene.add(group);

  const size   = group.userData.size;
  const label  = makeLabel(name || sat_id, colHex);
  label.position.set(xOffset, (size.y / 2) + 0.30, 0);
  scene.add(label);

  const rimLight = makeRimLight(colHex);
  rimLight.position.set(xOffset, 0, 0);
  scene.add(rimLight);

  satObjects.set(sat_id, { group, label, rimLight, index, xOffset, size });
}

// ── 전체 시나리오 재빌드 ─────────────────────────────────────────────────────
function rebuildAll(scenarios) {
  // 기존 오브젝트 정리
  satObjects.forEach(({ group, label, rimLight }) => {
    disposeSatellite(group);
    scene.remove(group);
    label.material.map?.dispose();
    label.material.dispose();
    scene.remove(label);
    scene.remove(rimLight);
  });
  satObjects.clear();
  selectedSatId = null;

  if (!scenarios || scenarios.length === 0) {
    updateHUD(null);
    return;
  }

  const GAP = 0.6;
  let cursor = 0;

  scenarios.forEach((sc, i) => {
    addOneSatellite(sc, i, cursor);
    const entry = satObjects.get(sc.sat_id);
    const sz    = entry.size;
    if (i < scenarios.length - 1) {
      cursor += sz.x + GAP;
    }
  });

  // 전체 중앙 정렬
  let sumX = 0;
  satObjects.forEach(e => { sumX += e.xOffset; });
  const centerX = sumX / satObjects.size;
  satObjects.forEach(e => {
    e.group.position.x   -= centerX;
    e.label.position.x   -= centerX;
    e.rimLight.position.x -= centerX;
    e.xOffset            -= centerX;
  });

  // 카메라: 전체 bbox
  const bbox = new THREE.Box3();
  satObjects.forEach(({ group }) => bbox.expandByObject(group));
  const bboxSz  = new THREE.Vector3();
  bbox.getSize(bboxSz);
  const bboxCtr = new THREE.Vector3();
  bbox.getCenter(bboxCtr);

  const extent = Math.max(bboxSz.x, bboxSz.y, bboxSz.z);
  const dist   = extent * 2.2 + 0.5;
  camera.position.set(bboxCtr.x, bboxCtr.y + dist * 0.35, bboxCtr.z + dist);
  camera.lookAt(bboxCtr);
  controls.target.copy(bboxCtr);
  controls.minDistance = extent * 0.2;
  controls.maxDistance = extent * 20;
  controls.update();

  // 첫 번째 위성 자동 선택
  selectSat(scenarios[0].sat_id);
}

// ── 위성 선택 및 하이라이트 ─────────────────────────────────────────────────
function selectSat(sat_id) {
  // 이전 림 라이트 끄기
  if (selectedSatId && satObjects.has(selectedSatId)) {
    satObjects.get(selectedSatId).rimLight.intensity = 0;
  }

  selectedSatId = sat_id;
  const entry = satObjects.get(sat_id);
  if (!entry) return;

  entry.rimLight.intensity = 3.5;
  entry.rimLight.distance  = 6;

  // Python 카드도 동기화 (QWebChannel bridge)
  window._bridge?.notify_sat_selected?.(sat_id);

  // 카메라 타겟 부드럽게 이동
  const fromTarget = controls.target.clone();
  const toTarget   = new THREE.Vector3(entry.xOffset, 0, 0);
  let t = 0;
  const tid = setInterval(() => {
    t++;
    controls.target.lerpVectors(fromTarget, toTarget, t / 30);
    controls.update();
    if (t >= 30) clearInterval(tid);
  }, 16);

  updateHUD(entry, sat_id);
}

// ── HUD 업데이트 ─────────────────────────────────────────────────────────────
function updateHUD(entry, sat_id) {
  const el = document.getElementById(HUD_ID);
  if (!el) return;

  if (!entry) {
    el.innerHTML = `<div class="sv-title">◈ SATELLITE SCENARIOS</div>
      <div style="color:#2a4050;font-size:10px;margin-top:8px;">시나리오 없음</div>`;
    return;
  }

  const busLabel = entry.group.userData.busLabel || '—';
  const cfg      = entry.group.userData.cfg      || {};
  const mass = (
    (Number(cfg.mass_bus_kg)         || 0) +
    (Number(cfg.mass_panel_kg)       || 0) +
    (Number(cfg.mass_electronics_kg) || 0) +
    (Number(cfg.mass_battery_kg)     || 0)
  ).toFixed(1);
  const power = Number(cfg.total_power_w || 0).toFixed(0);
  const panel = Number(cfg.panel_area_m2 || 0).toFixed(1);
  const apt   = Number(cfg.aperture_cm   || 0).toFixed(1);
  const cnt   = satObjects.size;
  const idx   = entry.index + 1;

  el.innerHTML = `
    <div class="sv-title">◈ SATELLITE SCENARIOS (${cnt}개)</div>
    <div class="sv-row"><span class="sv-lbl">선택</span><span class="sv-val sv-cyan">${sat_id}</span></div>
    <div class="sv-row"><span class="sv-lbl">Bus Type</span><span class="sv-val">${busLabel}</span></div>
    <div class="sv-row"><span class="sv-lbl">Total Mass</span><span class="sv-val">${mass} kg</span></div>
    <div class="sv-row"><span class="sv-lbl">Power</span><span class="sv-val">${power} W</span></div>
    <div class="sv-row"><span class="sv-lbl">Panel</span><span class="sv-val">${panel} m²</span></div>
    <div class="sv-row"><span class="sv-lbl">Aperture</span><span class="sv-val">${apt} cm</span></div>
    <div class="sv-row"><span class="sv-lbl">시나리오</span><span class="sv-val">${idx} / ${cnt}</span></div>
    <div style="color:#2a4050;font-size:9.5px;margin-top:6px;">클릭으로 위성 선택</div>
  `;
}

// ── Cesium 렌더 모드 제어 ─────────────────────────────────────────────────────
function setCesiumLowPower(on) {
  const v = window._cesiumViewer;
  if (!v) return;
  v.scene.requestRenderMode       = on;
  v.scene.maximumRenderTimeChange = on ? Infinity : 0;
}

// ── sat_builder 에서 cfg 저장을 위한 훅 ─────────────────────────────────────
// sat_builder.buildSatellite(cfg) 가 반환한 group 에 userData.cfg 를 추가
// sat_builder 를 수정하지 않고 여기서 처리
function buildAndTag(cfg) {
  const g = buildSatellite(cfg);
  g.userData.cfg = cfg;  // HUD 표시용 cfg 보관
  return g;
}

// ── 공개 API ─────────────────────────────────────────────────────────────────
window.showSatViewer = function (scenarios) {
  // ① 컨테이너를 먼저 보이게 해야 canvas가 실제 크기를 가짐
  const cont = document.getElementById(CONT_ID);
  cont.style.display = 'block';
  isVisible = true;
  setCesiumLowPower(true);

  // ② 그 다음 초기화 — rAF 1프레임 후 레이아웃 확정 보장
  // 하위 호환: 단일 cfg dict 전달 시 자동 래핑
  if (!Array.isArray(scenarios)) {
    scenarios = scenarios ? [{ sat_id: 'SAT-1', name: 'SAT-1', sat_config: scenarios }] : [];
  }

  if (!initPromise) {
    requestAnimationFrame(() => {
      initPromise = initSatViewer();
      initPromise
        .then(() => { rebuildAll(scenarios); startLoop(); })
        .catch(err => {
          console.error('[satViewer] init failed:', err);
          cont.style.display = 'none';
          isVisible = false;
          setCesiumLowPower(false);
        });
    });
  } else {
    initPromise
      .then(() => { rebuildAll(scenarios); startLoop(); })
      .catch(err => console.error('[satViewer] rebuildAll failed:', err));
  }
};

window.hideSatViewer = function () {
  stopLoop();
  isVisible = false;
  document.getElementById(CONT_ID).style.display = 'none';
  setCesiumLowPower(false);
};

window.updateSatViewer = function (scenarios) {
  if (!initPromise || !scene) return;
  if (!Array.isArray(scenarios)) {
    scenarios = scenarios ? [{ sat_id: 'SAT-1', name: 'SAT-1', sat_config: scenarios }] : [];
  }
  initPromise.then(() => rebuildAll(scenarios));
};

window.selectSatInViewer = function (sat_id) {
  if (!scene) return;
  selectSat(sat_id);
};
