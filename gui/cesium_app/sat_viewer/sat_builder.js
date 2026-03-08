/**
 * sat_builder.js — 위성 형상 빌더 (6종 버스 타입)
 * SpaceD-AADE v0.4.0  Satellite 3D Viewer
 *
 * 버스 타입 선택 기준 (dual_boards):
 *   1–4    → CubeSat 3U   (10×34×10 cm)
 *   5–10   → CubeSat 6U   (22×34×10 cm)
 *   11–20  → SmallSat     (50×50×50 cm)
 *   21–50  → MedSat       (100×80×100 cm)
 *   51–100 → LargeSat     (200×150×150 cm)
 *   101+   → DatacenterSat(300×250×200 cm)
 */
import * as THREE from 'three';
import {
  createBusMaterial, createPanelMaterial, createPanelEdgeMaterial,
  createAntennaMaterial, createThrusterMaterial, createRadiatorMaterial,
  createCameraMaterial, createLensMaterial, disposeMaterial,
} from './sat_materials.js';

// ── 버스 정의 테이블 ─────────────────────────────────────────────────────────
const BUS_DEFS = {
  cubesat_3u: { w: 0.10, h: 0.34, d: 0.10, label: 'CubeSat 3U',    mli: false, thrusters: false, tracker: false },
  cubesat_6u: { w: 0.22, h: 0.34, d: 0.10, label: 'CubeSat 6U',    mli: false, thrusters: false, tracker: false },
  smallsat:   { w: 0.50, h: 0.50, d: 0.50, label: 'SmallSat',      mli: true,  thrusters: true,  tracker: true  },
  medsat:     { w: 1.00, h: 0.80, d: 1.00, label: 'Medium Sat',    mli: true,  thrusters: true,  tracker: true  },
  largesat:   { w: 2.00, h: 1.50, d: 1.50, label: 'Large Sat',     mli: true,  thrusters: true,  tracker: true  },
  datacenter: { w: 3.00, h: 2.50, d: 2.00, label: 'Datacenter Sat',mli: true,  thrusters: true,  tracker: true  },
};

export function getBusType(dual_boards = 20) {
  const n = Number(dual_boards) || 1;
  if (n <=   4) return 'cubesat_3u';
  if (n <=  10) return 'cubesat_6u';
  if (n <=  20) return 'smallsat';
  if (n <=  50) return 'medsat';
  if (n <= 100) return 'largesat';
  return 'datacenter';
}

// ── 전체 dispose ─────────────────────────────────────────────────────────────
export function disposeSatellite(group) {
  if (!group) return;
  group.traverse(obj => {
    if (!obj.isMesh) return;
    obj.geometry?.dispose();
    disposeMaterial(obj.material);
  });
}

// ── 내부 헬퍼 ────────────────────────────────────────────────────────────────
function mesh(geo, mat, opts = {}) {
  const m = new THREE.Mesh(geo, mat);
  if (opts.pos)  m.position.set(...opts.pos);
  if (opts.rot)  m.rotation.set(...opts.rot);
  if (opts.name) m.name = opts.name;
  m.castShadow    = true;
  m.receiveShadow = true;
  return m;
}

// ── 버스 본체 ────────────────────────────────────────────────────────────────
function buildBus(group, def) {
  const geo = new THREE.BoxGeometry(def.w, def.h, def.d, 1, 1, 1);
  group.add(mesh(geo, createBusMaterial({ mli: def.mli }), { name: 'bus' }));
}

// ── 태양전지판 ───────────────────────────────────────────────────────────────
function buildSolarPanels(group, def, panel_area_m2) {
  const { w, h } = def;
  const panelH  = h * 0.88;
  const halfArea = Math.max(panel_area_m2 / 2, 0.01);
  const panelW  = halfArea / panelH;
  const panelD  = 0.012;

  // 멀티-재질: [±X, ±Y, FRONT(+Z), BACK(-Z)]
  const panelMat = createPanelMaterial();
  const edgeMat  = createPanelEdgeMaterial();
  const multMat  = [edgeMat, edgeMat, edgeMat, edgeMat, panelMat, edgeMat];

  const antMat = createAntennaMaterial();
  const boomR  = Math.min(w * 0.035, 0.018);

  [-1, 1].forEach(side => {
    const cx = side * (w / 2 + panelW / 2 + 0.005);

    // 패널 판
    const panGeo = new THREE.BoxGeometry(panelW, panelH, panelD);
    group.add(mesh(panGeo, multMat, {
      pos:  [cx, 0, 0],
      name: `panel_${side > 0 ? 'p' : 'n'}`,
    }));

    // 연결 붐
    const boomLen = w * 0.18 + panelW * 0.1;
    const boomGeo = new THREE.CylinderGeometry(boomR, boomR, boomLen, 8);
    const bm = mesh(boomGeo, antMat, {
      pos : [side * (w / 2 + boomLen / 2), 0, 0],
      rot : [0, 0, Math.PI / 2],
      name: `boom_${side > 0 ? 'p' : 'n'}`,
    });
    group.add(bm);
  });
}

// ── 주 안테나(Omni) + 패치 안테나 ────────────────────────────────────────────
function buildAntennas(group, def) {
  const { w, h, d } = def;
  const mat = createAntennaMaterial();

  // 채찍 안테나 (꼭대기)
  const antR = Math.min(w * 0.025, 0.01);
  const antH = h * 0.55;
  const antGeo = new THREE.CylinderGeometry(antR * 0.4, antR, antH, 8);
  group.add(mesh(antGeo, mat, { pos: [0, h / 2 + antH / 2, 0], name: 'antenna_whip' }));

  if (w < 0.4) return; // CubeSat → 채찍 안테나만

  // 패치 안테나 (전면 ±Z)
  const patchR = w * 0.09;
  const patchGeo = new THREE.CylinderGeometry(patchR, patchR * 1.1, 0.012, 12);
  [1, -1].forEach(side => {
    group.add(mesh(patchGeo, mat, {
      pos:  [0, h * 0.25, side * (d / 2 + 0.007)],
      name: `antenna_patch_${side > 0 ? 'p' : 'n'}`,
    }));
  });

  // 고이득 접시 (대형 위성)
  if (w >= 1.0) {
    const dishR = w * 0.18;
    const dishGeo  = new THREE.SphereGeometry(dishR, 16, 8, 0, Math.PI * 2, 0, Math.PI / 2);
    const stalkGeo = new THREE.CylinderGeometry(dishR * 0.04, dishR * 0.04, h * 0.35, 8);
    const dishMat  = new THREE.MeshStandardMaterial({ color: 0xd0d8e0, roughness: 0.25, metalness: 0.85, side: THREE.DoubleSide });

    const dish = mesh(dishGeo, dishMat, { name: 'dish' });
    dish.rotation.x = Math.PI;
    dish.position.set(0, h / 2 + h * 0.35 + dishR, 0);
    group.add(dish);
    group.add(mesh(stalkGeo, mat, { pos: [0, h / 2 + h * 0.175, 0], name: 'dish_stalk' }));
  }
}

// ── 방열판 ───────────────────────────────────────────────────────────────────
function buildRadiators(group, def) {
  const { w, h, d } = def;
  if (w < 0.4) return;
  const mat  = createRadiatorMaterial();
  const radW = w * 0.55; const radH = h * 0.72;
  const geo  = new THREE.BoxGeometry(radW, radH, 0.008);
  [-1, 1].forEach(side => {
    group.add(mesh(geo, mat, {
      pos:  [0, 0, side * (d / 2 + 0.005)],
      name: `radiator_${side > 0 ? 'p' : 'n'}`,
    }));
  });
}

// ── 추력기 ───────────────────────────────────────────────────────────────────
function buildThrusters(group, def) {
  if (!def.thrusters) return;
  const { w, h, d } = def;
  const thrR  = Math.min(w * 0.042, 0.065);
  const thrH  = h * 0.09;
  const mat   = createThrusterMaterial();
  const geo   = new THREE.CylinderGeometry(thrR * 0.55, thrR, thrH, 8);
  const ox = w / 2 * 0.72, oz = d / 2 * 0.72;
  [[-1,-1],[1,-1],[-1,1],[1,1]].forEach(([sx, sz]) => {
    group.add(mesh(geo, mat, {
      pos:  [sx * ox, -(h / 2 + thrH / 2), sz * oz],
      name: `thr_${sx > 0 ? 'px' : 'nx'}${sz > 0 ? 'pz' : 'nz'}`,
    }));
  });
}

// ── 카메라(페이로드) ─────────────────────────────────────────────────────────
function buildCamera(group, def, aperture_cm) {
  const { w, h } = def;
  const camR = Math.min(Math.max(aperture_cm / 100 / 2, 0.005), w * 0.32);
  const camH = camR * 2.8;
  const mat  = createCameraMaterial();

  // 경통
  group.add(mesh(
    new THREE.CylinderGeometry(camR, camR * 1.08, camH, 16),
    mat, { pos: [0, -(h / 2 + camH / 2), 0], name: 'camera_barrel' }
  ));

  // 렌즈 원판
  const lens = mesh(
    new THREE.CircleGeometry(camR * 0.88, 16),
    createLensMaterial(),
    { name: 'camera_lens' }
  );
  lens.position.set(0, -(h / 2 + camH + 0.001), 0);
  lens.rotation.x = Math.PI / 2;
  group.add(lens);

  // 덮개 링 (망원경 경통 끝 테두리)
  group.add(mesh(
    new THREE.TorusGeometry(camR, camR * 0.08, 8, 24),
    mat,
    { pos: [0, -(h / 2 + camH + 0.002), 0], rot: [Math.PI / 2, 0, 0], name: 'camera_ring' }
  ));
}

// ── 스타 트래커 ──────────────────────────────────────────────────────────────
function buildStarTracker(group, def) {
  if (!def.tracker) return;
  const { w, h, d } = def;
  const r = Math.min(w * 0.038, 0.04);
  const mat = createThrusterMaterial();
  const geo = new THREE.CylinderGeometry(r, r, r * 3.5, 8);
  group.add(mesh(geo, mat, {
    pos: [w * 0.38, h / 2 - r * 1.5, -d * 0.38],
    rot: [0.35, 0, 0.28],
    name: 'star_tracker',
  }));
}

// ── GPS 안테나 (소형 돌기) ────────────────────────────────────────────────────
function buildGPS(group, def) {
  if (def.w < 0.4) return;
  const { w, h, d } = def;
  const r   = Math.min(w * 0.028, 0.025);
  const mat = createAntennaMaterial();
  group.add(mesh(
    new THREE.CylinderGeometry(r, r * 1.3, r * 2.5, 8),
    mat, { pos: [-w * 0.35, h / 2 + r * 1.25, 0], name: 'gps_ant' }
  ));
}

// ── 공개 API ─────────────────────────────────────────────────────────────────
export function buildSatellite(cfg = {}) {
  const dual_boards   = Number(cfg.dual_boards   ?? 20);
  const panel_area_m2 = Number(cfg.panel_area_m2 ?? 4.0);
  const aperture_cm   = Number(cfg.aperture_cm   ?? 15.0);

  const busType = getBusType(dual_boards);
  const def     = { ...BUS_DEFS[busType] };

  const group = new THREE.Group();
  group.name  = 'satellite';

  buildBus         (group, def);
  buildSolarPanels (group, def, panel_area_m2);
  buildAntennas    (group, def);
  buildRadiators   (group, def);
  buildThrusters   (group, def);
  buildCamera      (group, def, aperture_cm);
  buildStarTracker (group, def);
  buildGPS         (group, def);

  // bbox 계산 → 카메라 거리 자동 설정용
  const bbox = new THREE.Box3().setFromObject(group);
  const size = new THREE.Vector3();
  bbox.getSize(size);
  group.userData.size     = size;
  group.userData.busType  = busType;
  group.userData.busLabel = def.label;

  return group;
}
