/**
 * sat_materials.js — PBR 재질 + 캔버스 텍스처 팩토리
 * SpaceD-AADE v0.4.0  Satellite 3D Viewer
 */
import * as THREE from 'three';

// ── 캔버스 텍스처 생성기 ─────────────────────────────────────────────────────

/** 태양전지판 격자 텍스처 (8×8 셀 그리드) */
function createSolarCellTexture(w = 256, h = 256) {
  const c = document.createElement('canvas');
  c.width = w; c.height = h;
  const ctx = c.getContext('2d');

  // 배경: 짙은 남색
  ctx.fillStyle = '#08122e';
  ctx.fillRect(0, 0, w, h);

  const cols = 8, rows = 8;
  const cw = w / cols, ch = h / rows;
  for (let r = 0; r < rows; r++) {
    for (let cc = 0; cc < cols; cc++) {
      const x = cc * cw + 1.5, y = r * ch + 1.5;
      // 셀 내부 그라디언트
      const grd = ctx.createLinearGradient(x, y, x + cw - 3, y + ch - 3);
      grd.addColorStop(0.0, '#1c3c90');
      grd.addColorStop(0.5, '#0d205c');
      grd.addColorStop(1.0, '#091840');
      ctx.fillStyle = grd;
      ctx.fillRect(x, y, cw - 3, ch - 3);
      // 미세 하이라이트  
      ctx.strokeStyle = 'rgba(80,140,255,0.35)';
      ctx.lineWidth = 0.5;
      ctx.strokeRect(x, y, cw - 3, ch - 3);
    }
  }
  // 배선 그리드
  ctx.strokeStyle = 'rgba(120,170,255,0.55)';
  ctx.lineWidth = 1.2;
  for (let r = 0; r <= rows; r++) {
    ctx.beginPath(); ctx.moveTo(0, r * ch); ctx.lineTo(w, r * ch); ctx.stroke();
  }
  for (let cc = 0; cc <= cols; cc++) {
    ctx.beginPath(); ctx.moveTo(cc * cw, 0); ctx.lineTo(cc * cw, h); ctx.stroke();
  }
  const tex = new THREE.CanvasTexture(c);
  tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
  return tex;
}

/** MLI(다층 단열재) 금박 텍스처 */
function createMLITexture(w = 256, h = 256) {
  const c = document.createElement('canvas');
  c.width = w; c.height = h;
  const ctx = c.getContext('2d');

  // 기본 금박 그라디언트
  const grd = ctx.createLinearGradient(0, 0, w, h);
  grd.addColorStop(0.00, '#9a6018');
  grd.addColorStop(0.25, '#d4a030');
  grd.addColorStop(0.50, '#f0c040');
  grd.addColorStop(0.75, '#c88020');
  grd.addColorStop(1.00, '#7a4a10');
  ctx.fillStyle = grd;
  ctx.fillRect(0, 0, w, h);

  // 주름 줄무늬
  ctx.strokeStyle = 'rgba(60,30,0,0.35)';
  ctx.lineWidth = 1.5;
  const stripes = 28;
  for (let i = 0; i < stripes; i++) {
    const y = (i / stripes) * h;
    ctx.beginPath();
    ctx.moveTo(0, y); ctx.lineTo(w, y + 3 * Math.sin(i * 0.7));
    ctx.stroke();
  }
  // 광택 반사 스팟
  ctx.fillStyle = 'rgba(255,235,140,0.12)';
  for (let i = 0; i < 25; i++) {
    ctx.beginPath();
    ctx.ellipse(
      Math.random() * w, Math.random() * h,
      3 + Math.random() * 10, 2,
      Math.random() * Math.PI, 0, Math.PI * 2
    );
    ctx.fill();
  }
  return new THREE.CanvasTexture(c);
}

/** 알루미늄 구조체 텍스처 */
function createAlumTexture(w = 128, h = 128) {
  const c = document.createElement('canvas');
  c.width = w; c.height = h;
  const ctx = c.getContext('2d');
  ctx.fillStyle = '#3a4c5c';
  ctx.fillRect(0, 0, w, h);
  ctx.strokeStyle = 'rgba(150,185,210,0.25)';
  ctx.lineWidth = 1;
  for (let i = 0; i < h; i += 6) {
    ctx.beginPath();
    ctx.moveTo(0, i); ctx.lineTo(w, i + 1.5);
    ctx.stroke();
  }
  return new THREE.CanvasTexture(c);
}

/** 방열판 텍스처 (흰색 열제어 코팅) */
function createRadiatorTexture(w = 128, h = 256) {
  const c = document.createElement('canvas');
  c.width = w; c.height = h;
  const ctx = c.getContext('2d');
  ctx.fillStyle = '#c8d8e8';
  ctx.fillRect(0, 0, w, h);
  ctx.strokeStyle = 'rgba(80,110,140,0.3)';
  ctx.lineWidth = 1;
  const rows = 10;
  for (let r = 0; r <= rows; r++) {
    const y = (r / rows) * h;
    ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke();
  }
  return new THREE.CanvasTexture(c);
}

// ── 재질 팩토리 (공개 API) ─────────────────────────────────────────────────

export function createBusMaterial(opts = {}) {
  const { mli = false } = opts;
  if (mli) {
    return new THREE.MeshStandardMaterial({
      map:       createMLITexture(),
      color:     new THREE.Color(0xffffff),
      roughness: 0.55,
      metalness: 0.80,
    });
  }
  return new THREE.MeshStandardMaterial({
    map:       createAlumTexture(),
    color:     new THREE.Color(0xffffff),
    roughness: 0.45,
    metalness: 0.65,
  });
}

export function createPanelMaterial() {
  return new THREE.MeshStandardMaterial({
    map:       createSolarCellTexture(),
    color:     new THREE.Color(0xffffff),
    roughness: 0.20,
    metalness: 0.45,
  });
}

export function createPanelEdgeMaterial() {
  return new THREE.MeshStandardMaterial({
    color:     new THREE.Color(0x2a3a50),
    roughness: 0.55,
    metalness: 0.70,
  });
}

export function createAntennaMaterial() {
  return new THREE.MeshStandardMaterial({
    color:     new THREE.Color(0xb8ccd8),
    roughness: 0.25,
    metalness: 0.90,
  });
}

export function createThrusterMaterial() {
  return new THREE.MeshStandardMaterial({
    color:     new THREE.Color(0x1e2530),
    roughness: 0.75,
    metalness: 0.45,
  });
}

export function createRadiatorMaterial() {
  return new THREE.MeshStandardMaterial({
    map:       createRadiatorTexture(),
    color:     new THREE.Color(0xffffff),
    roughness: 0.35,
    metalness: 0.50,
  });
}

export function createCameraMaterial() {
  return new THREE.MeshStandardMaterial({
    color:     new THREE.Color(0x101520),
    roughness: 0.45,
    metalness: 0.85,
  });
}

export function createLensMaterial() {
  return new THREE.MeshStandardMaterial({
    color:     new THREE.Color(0x060a14),
    roughness: 0.05,
    metalness: 0.95,
  });
}

/** 재질(및 하위 텍스처) 해제 */
export function disposeMaterial(mat) {
  if (!mat) return;
  if (Array.isArray(mat)) { mat.forEach(disposeMaterial); return; }
  mat.map?.dispose();
  mat.normalMap?.dispose();
  mat.roughnessMap?.dispose();
  mat.metalnessMap?.dispose();
  mat.emissiveMap?.dispose();
  mat.dispose();
}
