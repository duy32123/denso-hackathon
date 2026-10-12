import * as THREE from './vendor/three/three.module.min.js';
import {buildGraph, TYPES, ROLES} from './space-graph.js';
import {situations, compareSnapshots} from './space-explore.js';
import {createRoute, STAGES, edgeKey, nodeId} from './space-route.js';

const $ = id => document.getElementById(id);
const text = (tag, value, className) => { const n = document.createElement(tag); n.textContent = value; if (className) n.className = className; return n; };
const action = (label, callback) => { const b = text('button', label, 'inspector-action'); b.type = 'button'; b.addEventListener('click', callback); return b; };
const sourceStates = {pending: 'Chờ đối chiếu nguồn', source_checked: 'Đã đối chiếu nguồn', rejected: 'Nguồn bị từ chối'};
const technicalStates = {not_requested: 'Chưa xác nhận chuyên môn', pending: 'Chờ chuyên gia', expert_validated: 'Đã xác nhận chuyên môn trong phạm vi ghi nhận', rejected: 'Chuyên môn bị từ chối'};
const stage = $('space-stage'), shell = $('space-shell'), content = $('inspector-content');
const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)');
let graph = null, catalog = null, selected = null, loading = 0, panelToken = 0, tourIndex = -1, stops = [];
let renderer = null, scene, camera, mesh, edgeLines, highlightLines, selectionRing;
let labelNodes = [], frame = 0, lastTime = 0, inViewport = true;
const enabled = new Set(Object.keys(TYPES));
const orbit = {theta: .06, phi: 1.16, radius: 180, target: new THREE.Vector3(), desiredTarget: new THREE.Vector3(), desiredRadius: 180, rotating: false};
const raycaster = new THREE.Raycaster(), pointer = new THREE.Vector2(), dummy = new THREE.Object3D();
const nodePositions = [], color = new THREE.Color();
const projection = new THREE.Vector3(), neighborhood = new Set();
let clusterDecorations = [];
let baseGraph = null, lens = 'overview', situation = null, comparison = null, phase = 'changes';
let viewToken = 0, viewController = null, history = null;
let routeUI = null, routeDisplay = null, routeParticles = null, routeStarted = 0;
const changeColors = {added: '#15803d', changed: '#c26a06', removed: '#c2362b', unchanged: '#c9d3dd'};
// San khau sang (theme.css --stage): lam mo = pha ve mau nen, khong nhan ve mau den.
const STAGE_BG = new THREE.Color('#eef3f7');
const fade = amount => color.lerp(STAGE_BG, 1 - amount);
const changeLabels = {added: 'Thêm mới', changed: 'Thay đổi', removed: 'Đã bỏ', unchanged: 'Giữ nguyên'};
const nodeAt = id => graph?.byId.get(graph.aliases?.get(id) || id);

async function get(url, signal) {
  const response = await fetch(url, {cache: 'no-store', signal});
  const data = await response.json();
  if (!response.ok) throw new Error(data.error?.message || 'Không đọc được kho tri thức.');
  return data;
}
const params = (build = catalog.index_build_id) => new URLSearchParams({mode: graph.mode, dataset_split: 'dev', index_build_id: build});
const evidenceUrl = (n, evidence) => `/v1/evidence/${encodeURIComponent(n.ref.workflow_id)}/${n.ref.revision}/${encodeURIComponent(evidence.evidence_id)}?${params(graph.workflows.get(n.workflow).snapshot.index_build_id)}`;
function sourceLink(url) {
  try {
    const parsed = new URL(url); if (!['https:', 'http:'].includes(parsed.protocol)) return null;
    const a = text('a', 'Mở trang nguồn ↗'); a.href = parsed.href; a.target = '_blank'; a.rel = 'noopener noreferrer'; return a;
  } catch { return null; }
}
function clearEvidence() { panelToken++; $('space-evidence').replaceChildren(); }
async function showEvidence(n, evidence) {
  const token = ++panelToken, generation = loading, box = $('space-evidence');
  box.replaceChildren(text('p', 'Đang mở bằng chứng…'));
  const url = evidenceUrl(n, evidence);
  try {
    const data = await get(url);
    if (token !== panelToken || generation !== loading) return;
    box.replaceChildren(text('h3', 'Bằng chứng gốc'), text('p', `${data.source.title} · r${data.workflow.revision}`, 'inspector-note'));
    const loc = data.evidence.locator;
    if (loc.start_ms !== null) box.append(text('p', `${(loc.start_ms / 1000).toFixed(1)}–${(loc.end_ms / 1000).toFixed(1)} giây`, 'inspector-note'));
    box.append(text('blockquote', data.text || data.evidence.quote || data.evidence.observation_note || 'Không có đoạn văn đã lưu.'));
    if (data.asset_available) {
      const image = document.createElement('img'), asset = new URL(url, location.origin); asset.pathname += '/asset';
      image.src = asset.href; image.alt = data.evidence.observation_note || 'Khung hình từ nguồn'; box.append(image);
    }
    if (!data.available) box.append(text('p', 'Nguồn này hiện chưa mở được.', 'inspector-note'));
    const link = sourceLink(data.source.url); if (link) box.append(link);
    box.append(text('p', `${data.evidence.evidence_id} · ${graph.mode === 'synthetic' ? 'Dữ liệu mô phỏng' : 'Nguồn pilot'}`, 'inspector-note'));
    const inspector = document.querySelector('.space-inspector');
    inspector.scrollTo({top: inspector.scrollTop + box.getBoundingClientRect().top - inspector.getBoundingClientRect().top - 16, behavior: reducedMotion.matches ? 'instant' : 'smooth'});
  } catch (error) { if (token === panelToken && generation === loading) box.replaceChildren(text('p', error.message)); }
}
function reviewChips(claim) {
  const box = document.createElement('div');
  box.append(text('span', sourceStates[claim.source_review], `inspector-chip ${claim.source_review === 'source_checked' ? '' : claim.source_review}`));
  box.append(text('span', technicalStates[claim.technical_review], `inspector-chip ${claim.technical_review === 'expert_validated' ? '' : 'pending'}`));
  if (claim.support_status !== 'supported' || claim.evidence_type === 'inferred' || claim.conflicts_with.length) box.append(text('span', 'Cần kiểm tra căn cứ / mâu thuẫn', 'inspector-chip pending'));
  return box;
}
function claimCard(n, claim) {
  const box = text('div', '', 'inspector-claim');
  box.append(text('p', claim.text), reviewChips(claim));
  const wf = graph.workflows.get(n.workflow), evidence = new Map(wf.wf.evidence.map(ev => [ev.evidence_id, ev]));
  for (const link of claim.evidence_links) {
    const ev = evidence.get(link.evidence_id); if (!ev) continue;
    const label = ev.modality === 'speech' ? 'Lời nói' : ev.modality === 'visual' ? 'Hình ảnh' : 'Văn bản';
    const b = action(`${label} · Mở bằng chứng ↗`, () => showEvidence(n, ev)); b.dataset.evidenceId = ev.evidence_id; box.append(b);
  }
  if (!claim.evidence_links.length) box.append(text('p', 'Chưa có bằng chứng liên kết.', 'inspector-note'));
  const scope = document.createElement('details'); scope.className = 'inspector-scope';
  scope.append(text('summary', 'Phạm vi áp dụng'), text('p', claim.scope.description || 'Phạm vi chưa được ghi nhận', 'inspector-note')); box.append(scope);
  return box;
}
function linkedButton(id, label) { return action(label || nodeAt(id)?.title || id, () => selectNode(graph.aliases?.get(id) || id)); }
function renderInspector(n) {
  clearEvidence(); content.replaceChildren();
  $('inspector-kind').textContent = TYPES[n.kind].label.toLocaleUpperCase('vi');
  $('inspector-title').textContent = n.title;
  if (lens === 'history' && comparison && phase === 'changes') { renderChangeInspector(n); return; }
  const wfInfo = n.workflow ? graph.workflows.get(n.workflow) : null;
  if (wfInfo) content.append(text('p', `${n.ref.workflow_id} · r${n.ref.revision} · ${wfInfo.wf.context.manufacturer || 'Chưa rõ nhà sản xuất'}`, 'inspector-note'));
  if (n.kind === 'root') {
    content.append(text('p', 'Kinh nghiệm được tổ chức thành quy trình, bước và phát biểu. Mỗi phát biểu liên kết tới nguồn; phần còn thiếu trở thành câu hỏi để tiếp tục thu thập.'));
    content.append(text('p', 'Các cụm cùng xuất hiện trong một kho. Quan hệ kỹ thuật giữa nhiều quy trình cần được xác minh riêng.', 'inspector-note'));
    for (const info of graph.workflows.values()) if (graph.byId.has(info.prefix)) content.append(linkedButton(info.prefix, info.wf.title));
  } else if (n.kind === 'workflow') {
    const wf = n.data;
    content.append(text('p', `${wf.steps.length} bước · ${wf.claims.length} phát biểu · ${wf.relations.length} quan hệ bước · ${wf.questions.filter(q => q.status === 'open').length} câu hỏi mở`));
    content.append(text('p', `Phân hệ: ${wf.context.subsystem || 'Chưa xác định'} · Model máy: ${wf.context.machine_model || 'Chưa xác định'}`));
    const checked = wf.claims.filter(c => c.source_review === 'source_checked').length;
    const expert = wf.claims.filter(c => c.technical_review === 'expert_validated').length;
    content.append(text('span', `${checked}/${wf.claims.length} đối chiếu nguồn`, 'inspector-chip'), text('span', `${expert}/${wf.claims.length} xác nhận chuyên môn`, 'inspector-chip pending'));
    content.append(text('h3', 'Bắt đầu từ một bước'));
    for (const step of wf.steps) content.append(linkedButton(wfInfo.id(step.step_id), `${step.display_order}. ${step.title}`));
  } else if (n.kind === 'step') {
    const claims = new Map(wfInfo.wf.claims.map(c => [c.claim_id, c]));
    for (const [role, field] of Object.entries(n.data.fields)) {
      content.append(text('h3', ROLES[role]));
      if (!field.claim_ids.length) content.append(text('p', field.state === 'not_applicable' ? 'Không áp dụng' : 'Chưa được nguồn ghi nhận', 'inspector-note'));
      for (const cid of field.claim_ids) {
        const c = claims.get(cid); if (c) content.append(linkedButton(wfInfo.id(cid), c.text));
      }
    }
    const relations = wfInfo.wf.relations.filter(r => r.from_step_id === n.data.step_id || r.to_step_id === n.data.step_id);
    if (relations.length) content.append(text('h3', 'Quan hệ của bước'));
    for (const r of relations) content.append(linkedButton(wfInfo.id(r.relation_id)));
    const questions = wfInfo.wf.questions.filter(q => q.step_id === n.data.step_id && q.status === 'open');
    if (questions.length) content.append(text('h3', 'Cần bổ sung kinh nghiệm'));
    for (const q of questions) content.append(linkedButton(wfInfo.id(q.question_id), q.question));
  } else if (n.kind === 'claim') {
    content.append(text('p', ROLES[n.data.role] || 'Căn cứ quan hệ', 'inspector-note'), claimCard(n, n.data));
    content.append(text('p', `Người / nguồn phát biểu: ${n.data.attribution.label || 'Chưa ghi nhận'}`, 'inspector-note'));
  } else if (n.kind === 'relation') {
    const r = n.data, claims = new Map(wfInfo.wf.claims.map(c => [c.claim_id, c]));
    content.append(linkedButton(wfInfo.id(r.from_step_id), `Từ: ${nodeAt(wfInfo.id(r.from_step_id)).title}`));
    content.append(linkedButton(wfInfo.id(r.to_step_id), `Đến: ${nodeAt(wfInfo.id(r.to_step_id)).title}`));
    if (r.condition_claim_ids.length) content.append(text('h3', 'Điều kiện chuyển bước'));
    for (const cid of r.condition_claim_ids) content.append(claimCard(n, claims.get(cid)));
    content.append(text('h3', 'Căn cứ của quan hệ'));
    for (const cid of r.claim_ids) content.append(claimCard(n, claims.get(cid)));
  } else if (n.kind === 'evidence') {
    content.append(text('p', n.data.modality === 'visual' ? 'Khung hình có mốc thời gian' : n.data.modality === 'speech' ? 'Lời nói có mốc thời gian' : 'Đoạn tài liệu', 'inspector-note'));
    showEvidence(n, n.data);
  } else if (n.kind === 'question') {
    content.append(text('span', n.data.status === 'open' ? 'Cần người có kinh nghiệm bổ sung' : `Câu hỏi: ${n.data.status}`, 'inspector-chip pending'));
    content.append(text('p', `Trường cần làm rõ: ${ROLES[n.data.target_field]}`), linkedButton(wfInfo.id(n.data.step_id), `Xem bước: ${nodeAt(wfInfo.id(n.data.step_id)).title}`));
    content.append(text('p', 'Phản hồi được giữ cùng người cung cấp và đi qua review để tạo phiên bản tri thức mới.'));
    const link = text('a', 'Mở biểu mẫu bổ sung kinh nghiệm ↗');
    link.href = `/?${new URLSearchParams({mode: graph.mode, workflow: n.ref.workflow_id, revision: n.ref.revision, question: n.data.question_id})}`;
    if (n.data.status === 'open' && catalog.workflows.some(w => w.workflow_id === n.ref.workflow_id && w.revision === n.ref.revision)) content.append(link);
    else content.append(text('p', 'Câu hỏi thuộc bản lịch sử. Mở bản hiện tại để bổ sung kinh nghiệm.', 'inspector-note'));
  } else if (n.kind === 'source') {
    content.append(text('p', n.data.access_note || 'Nguồn đầu vào của pilot.'));
    const link = sourceLink(n.data.url); if (link) content.append(link);
    content.append(text('p', n.data.source_id, 'inspector-note'));
  }
  document.querySelector('.space-inspector').scrollTop = 0;
}

function setRotate(value) {
  orbit.rotating = value && !reducedMotion.matches && !!renderer;
  $('space-rotate').setAttribute('aria-pressed', String(orbit.rotating));
  $('space-rotate').textContent = orbit.rotating ? 'Dừng xoay' : 'Tự xoay';
  wake();
}
function selectNode(id, fly = true) {
  const n = graph?.byId.get(id); if (!n) return;
  if (lens === 'route') routeUI?.pause();
  if (lens === 'history' && phase === 'changes' && $('changes-only').checked && n.change === 'unchanged') $('changes-only').checked = false;
  if (lens === 'situation' && situation && !situation.path.has(id)) { setLens('overview'); selectNode(id, fly); return; }
  enabled.add(n.kind); const checkbox = document.querySelector(`[data-space-type="${n.kind}"]`); if (checkbox) checkbox.checked = true;
  selected = id; setRotate(false); neighborhood.clear(); neighborhood.add(id);
  for (const neighbor of graph.adjacency.get(id)) neighborhood.add(neighbor);
  // Include the actual evidence of a selected relation/claim, preserving its references.
  if (['relation', 'step'].includes(n.kind)) for (const nid of [...neighborhood]) {
    if (graph.byId.get(nid).kind === 'claim') for (const neighbor of graph.adjacency.get(nid)) {
      if (graph.byId.get(neighbor).kind === 'evidence') neighborhood.add(neighbor);
    }
  }
  if (fly) {
    orbit.desiredTarget.fromArray(n.position);
    orbit.desiredRadius = n.kind === 'root' ? 180 : n.kind === 'workflow' ? 86 : 62;
    if (reducedMotion.matches) { orbit.target.copy(orbit.desiredTarget); orbit.radius = orbit.desiredRadius; }
  }
  renderInspector(n); updateVisibility(); updateLabels(); wake();
  $('space-canvas').dataset.selectedNode = n.id;
}
function overview() {
  if (!graph) return;
  selected = null; neighborhood.clear(); clearEvidence();
  orbit.desiredTarget.set(0, 0, 0); orbit.desiredRadius = 180; orbit.theta = .06; orbit.phi = 1.16;
  if (reducedMotion.matches) { orbit.target.copy(orbit.desiredTarget); orbit.radius = orbit.desiredRadius; }
  renderInspector(graph.byId.get(graph.root)); updateVisibility(); updateLabels(); wake();
  $('space-canvas').dataset.selectedNode = '';
}
function removeObject(obj, disposeGeometry = true) {
  if (!obj) return; scene.remove(obj);
  if (obj.isInstancedMesh) obj.dispose();
  if (disposeGeometry) obj.geometry?.dispose();
  if (Array.isArray(obj.material)) obj.material.forEach(m => m.dispose()); else obj.material?.dispose();
}
function drawGraph() {
  if (!renderer) return;
  removeObject(mesh); removeObject(edgeLines); removeObject(highlightLines);
  for (const obj of clusterDecorations) removeObject(obj); clusterDecorations = [];
  nodePositions.length = 0;
  const geometry = new THREE.SphereGeometry(1, 12, 8);
  const material = new THREE.MeshBasicMaterial({color: 0xffffff});
  mesh = new THREE.InstancedMesh(geometry, material, graph.nodes.length);
  mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
  graph.nodes.forEach((n, index) => {
    nodePositions.push(new THREE.Vector3(...n.position)); dummy.position.fromArray(n.position); dummy.scale.setScalar(TYPES[n.kind].radius); dummy.updateMatrix();
    mesh.setMatrixAt(index, dummy.matrix); mesh.setColorAt(index, color.set(TYPES[n.kind].color));
  });
  // Instances span several clusters; picking/culling uses the whole graph bound.
  mesh.computeBoundingSphere(); scene.add(mesh);
  edgeLines = new THREE.LineSegments(new THREE.BufferGeometry(), new THREE.LineBasicMaterial({vertexColors: true, transparent: true, opacity: .5}));
  highlightLines = new THREE.LineSegments(new THREE.BufferGeometry(), new THREE.LineBasicMaterial({color: '#0f766e', transparent: true, opacity: .9}));
  scene.add(edgeLines, highlightLines);
  for (const info of graph.workflows.values()) {
    if (!graph.byId.has(info.prefix)) continue;
    const points = Array.from({length: 81}, (_, i) => {
      const a = i / 80 * Math.PI * 2; return new THREE.Vector3(info.center[0] + Math.cos(a) * 29, info.center[1] + Math.sin(a) * 21, info.center[2] - 4);
    });
    const ring = new THREE.Line(new THREE.BufferGeometry().setFromPoints(points), new THREE.LineBasicMaterial({color: '#9fb2c5', transparent: true, opacity: .55})); ring.userData.workflow = info.prefix; scene.add(ring); clusterDecorations.push(ring);
  }
  updateVisibility(); updateLabels(); resize(); wake();
}
function updateVisibility() {
  if (!graph || !mesh) return;
  const focus = selected && graph.byId.get(selected);
  for (const ring of clusterDecorations) ring.visible = lens === 'route' && routeDisplay?.scope ? ring.userData.workflow === routeDisplay.scope : lens === 'situation' ? ring.userData.workflow === situation?.node.workflow : !focus?.workflow || ring.userData.workflow === focus.workflow;
  const changesOnly = lens === 'history' && phase === 'changes' && $('changes-only').checked;
  const changedNodes = new Set(graph.nodes.filter(n => n.change && n.change !== 'unchanged').map(n => n.id));
  if (changesOnly) for (const e of graph.edges.filter(e => e.change !== 'unchanged')) { changedNodes.add(e.from); changedNodes.add(e.to); }
  const visible = n => enabled.has(n.kind) && (lens === 'route' ? (!routeDisplay?.scope || n.workflow === routeDisplay.scope || n.kind === 'source' && routeDisplay.visited.has(n.id)) : lens === 'situation' && situation ? situation.path.has(n.id) :
    (!changesOnly || changedNodes.has(n.id)) && (!focus || focus.kind === 'root' ||
    (focus.workflow ? n.workflow === focus.workflow || neighborhood.has(n.id) : neighborhood.has(n.id))));
  graph.nodes.forEach((n, i) => {
    const show = visible(n); dummy.position.fromArray(n.position); dummy.scale.setScalar(show ? TYPES[n.kind].radius : 0); dummy.updateMatrix(); mesh.setMatrixAt(i, dummy.matrix);
    color.set(lens === 'history' && phase === 'changes' ? changeColors[n.change] : TYPES[n.kind].color);
    if (lens === 'route' && routeDisplay) {
      const state = routeDisplay.states.get(n.id);
      if (state === 'blocked') color.set('#c2362b');
      else if (state === 'context') color.set('#c26a06');
      else if (state === 'cited') color.set('#059669');
      if (!routeDisplay.visited.has(n.id)) fade(.12);
      else if (!routeDisplay.active.has(n.id)) fade(.45);
    } else if (selected && !neighborhood.has(n.id) && lens !== 'history') fade(.18);
    mesh.setColorAt(i, color);
  });
  mesh.instanceMatrix.needsUpdate = true; mesh.instanceColor.needsUpdate = true;
  const coords = [], colors = [], highlighted = [];
  for (const e of graph.edges) {
    if (!visible(graph.byId.get(e.from)) || !visible(graph.byId.get(e.to))) continue;
    const from = graph.byId.get(e.from).position, to = graph.byId.get(e.to).position;
    const active = lens === 'route' ? routeDisplay?.edges.has(edgeKey(e)) : lens === 'situation' ? true : selected && neighborhood.has(e.from) && neighborhood.has(e.to);
    coords.push(...from, ...to);
    color.set(lens === 'history' && phase === 'changes' ? changeColors[e.change] : e.kind.startsWith('missing:') || ['branch_if', 'branch_condition'].includes(e.kind) ? '#c98a2c' : '#8193a6');
    if (lens === 'route' && !active) fade(routeDisplay?.trailEdges.has(edgeKey(e)) ? .7 : .08);
    else if (selected && !active && lens !== 'history') fade(.15);
    colors.push(color.r, color.g, color.b, color.r, color.g, color.b);
    if (active && lens !== 'history') {
      highlighted.push(...from, ...to);
      // Arrowheads preserve direction for the recorded decision and evidence chain.
      if (['relation_from', 'branch_if', 'requires', 'supported_by', 'from_source'].includes(e.kind)) {
        const end = new THREE.Vector3(...to), direction = end.clone().sub(new THREE.Vector3(...from)).normalize();
        end.addScaledVector(direction, -TYPES[graph.byId.get(e.to).kind].radius - .3);
        const side = new THREE.Vector3().crossVectors(direction, new THREE.Vector3(0, 0, 1));
        if (side.lengthSq() < .01) side.crossVectors(direction, new THREE.Vector3(0, 1, 0));
        side.normalize().multiplyScalar(.55);
        const tail = end.clone().addScaledVector(direction, -1.5);
        highlighted.push(...tail.clone().add(side).toArray(), ...end.toArray(), ...tail.sub(side).toArray(), ...end.toArray());
      }
    }
  }
  edgeLines.geometry.dispose(); edgeLines.geometry = new THREE.BufferGeometry();
  edgeLines.geometry.setAttribute('position', new THREE.Float32BufferAttribute(coords, 3)); edgeLines.geometry.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3));
  highlightLines.geometry.dispose(); highlightLines.geometry = new THREE.BufferGeometry();
  highlightLines.geometry.setAttribute('position', new THREE.Float32BufferAttribute(highlighted, 3));
  selectionRing.visible = !!selected && enabled.has(graph.byId.get(selected)?.kind);
  if (selectionRing.visible) { selectionRing.position.fromArray(graph.byId.get(selected).position); selectionRing.scale.setScalar(TYPES[graph.byId.get(selected).kind].radius + .7); }
  const visibleCount = graph.nodes.filter(visible).length;
  $('space-canvas').dataset.visibleNodes = String(visibleCount);
  updateLabels(); wake();
}
function updateLabels() {
  $('space-labels').replaceChildren(); labelNodes = [];
  if (!graph || !renderer) return;
  const candidates = lens === 'route' && routeDisplay ? [...routeDisplay.active].map(id => graph.byId.get(id)).filter(n => n && ['workflow', 'step', 'relation', 'claim'].includes(n.kind)).sort((a, b) => (a.id === routeDisplay.primary ? -1 : 0) - (b.id === routeDisplay.primary ? -1 : 0)).slice(0, 6) : lens === 'situation' && situation ? [graph.byId.get(selected) || situation.node, situation.from, situation.to, ...situation.conditions].filter((n, i, all) => all.findIndex(x => x.id === n.id) === i) :
    lens === 'history' && phase === 'changes' ? graph.nodes.filter(n => ['added', 'changed', 'removed'].includes(n.change)).sort((a, b) => (a.kind === 'claim' ? -1 : 0) - (b.kind === 'claim' ? -1 : 0)).slice(0, 7) :
    selected ? [graph.byId.get(selected), ...[...neighborhood].filter(id => id !== selected).map(id => graph.byId.get(id)).filter(n => ['step', 'workflow', 'relation', 'question'].includes(n.kind))].slice(0, 9) : graph.nodes.filter(n => ['root', 'workflow'].includes(n.kind));
  for (const n of candidates) {
    if (!enabled.has(n.kind)) continue;
    const label = text('div', n.kind === 'workflow' ? n.title : n.title.length > 65 ? `${n.title.slice(0, 62)}…` : n.title, `space-node-label ${['workflow', 'root'].includes(n.kind) ? 'is-hub' : ''} ${n.id === selected ? 'is-selected' : ''}`);
    $('space-labels').append(label); labelNodes.push({n, label});
  }
}
function updateCamera(delta) {
  const factor = reducedMotion.matches ? 1 : 1 - Math.exp(-delta * 5);
  orbit.target.lerp(orbit.desiredTarget, factor); orbit.radius += (orbit.desiredRadius - orbit.radius) * factor;
  if (orbit.rotating) orbit.theta += delta * .085;
  camera.position.set(orbit.target.x + orbit.radius * Math.sin(orbit.phi) * Math.sin(orbit.theta), orbit.target.y + orbit.radius * Math.cos(orbit.phi), orbit.target.z + orbit.radius * Math.sin(orbit.phi) * Math.cos(orbit.theta));
  camera.lookAt(orbit.target); camera.updateMatrixWorld();
  if (selectionRing.visible) selectionRing.quaternion.copy(camera.quaternion);
}
function renderLabels() {
  const w = stage.clientWidth, h = stage.clientHeight, occupied = [];
  for (const {n, label} of labelNodes) {
    projection.fromArray(n.position).project(camera);
    const x = (projection.x * .5 + .5) * w, y = (-projection.y * .5 + .5) * h + 15;
    const invalid = projection.z > 1 || projection.z < -1 || x < 10 || x > w - 10 || y < 10 || y > h - 45;
    const overlap = occupied.some(p => Math.abs(p.x - x) < 185 && Math.abs(p.y - y) < 60);
    label.hidden = invalid || overlap;
    if (!label.hidden) { label.style.transform = `translate(${Math.max(95, Math.min(w - 95, x))}px, ${y}px) translateX(-50%)`; occupied.push({x, y}); }
  }
}
function wake() {
  if (renderer && !frame && inViewport && !document.hidden) frame = requestAnimationFrame(animate);
}
function animate(time) {
  frame = 0;
  if (!renderer || !inViewport || document.hidden) { lastTime = 0; return; }
  const delta = lastTime ? Math.min((time - lastTime) / 1000, .05) : 1 / 60; lastTime = time;
  updateCamera(delta); updateRouteParticles(time); renderer.render(scene, camera); renderLabels();
  const moving = orbit.target.distanceTo(orbit.desiredTarget) > .02 || Math.abs(orbit.radius - orbit.desiredRadius) > .02;
  if (orbit.rotating || moving || lens === 'route' && routeUI?.playing && !reducedMotion.matches) frame = requestAnimationFrame(animate); else lastTime = 0;
}
function resize() {
  if (!renderer) return;
  renderer.setSize(stage.clientWidth, stage.clientHeight); camera.aspect = stage.clientWidth / Math.max(stage.clientHeight, 1); camera.updateProjectionMatrix(); wake();
}
function hitAt(x, y) {
  if (!graph || !mesh) return null;
  const rect = renderer.domElement.getBoundingClientRect(); pointer.set((x - rect.left) / rect.width * 2 - 1, -(y - rect.top) / rect.height * 2 + 1);
  raycaster.setFromCamera(pointer, camera);
  const hit = raycaster.intersectObject(mesh)[0];
  const n = hit ? graph.nodes[hit.instanceId] : null; return n && enabled.has(n.kind) ? n : null;
}
function initRenderer() {
  try { renderer = new THREE.WebGLRenderer({alpha: true, antialias: true}); }
  catch {
    const box = text('div', '', 'space-fallback'); box.append(text('p', 'Trình duyệt này chưa mở được WebGL 3D. Bạn vẫn có thể tìm và đọc tri thức bằng các nút bên cạnh.'));
    const link = text('a', 'Mở bản đồ quy trình'); link.href = '/'; box.append(link); $('space-canvas').append(box); $('space-canvas').dataset.renderer = 'unavailable';
    $('space-rotate').disabled = true; return;
  }
  renderer.setPixelRatio(Math.min(devicePixelRatio, 1.8)); renderer.setClearColor(0xeef3f7, 0);
  scene = new THREE.Scene(); camera = new THREE.PerspectiveCamera(48, 1, .1, 1200);
  $('space-canvas').append(renderer.domElement); $('space-canvas').dataset.renderer = 'webgl';
  renderer.domElement.tabIndex = 0; renderer.domElement.setAttribute('role', 'img'); renderer.domElement.setAttribute('aria-label', 'Đồ thị tri thức 3D. Phím mũi tên xoay, cộng trừ zoom, Home về toàn cảnh. Tìm và chọn nút bằng ô tìm kiếm.');
  const starPositions = [];
  // Decorative particles, deterministic and excluded from graph/counts.
  let seed = 32123;
  const random = () => { seed = (seed * 1664525 + 1013904223) >>> 0; return seed / 4294967296; };
  for (let i = 0; i < 430; i++) starPositions.push((random() - .5) * 440, (random() - .5) * 300, -100 - random() * 250);
  const stars = new THREE.Points(new THREE.BufferGeometry(), new THREE.PointsMaterial({size: .5, color: '#c3cfdb', transparent: true, opacity: .7}));
  stars.geometry.setAttribute('position', new THREE.Float32BufferAttribute(starPositions, 3)); scene.add(stars);
  selectionRing = new THREE.Mesh(new THREE.TorusGeometry(1, .08, 6, 48), new THREE.MeshBasicMaterial({color: '#0b5f58'})); selectionRing.visible = false; scene.add(selectionRing);
  routeParticles = new THREE.InstancedMesh(new THREE.SphereGeometry(.8, 10, 8), new THREE.MeshBasicMaterial({color: '#0f766e'}), 3); routeParticles.visible = false; routeParticles.frustumCulled = false; scene.add(routeParticles);
  const pointers = new Map(); let down = null, traveled = 0, pinch = 0;
  const canvas = renderer.domElement;
  canvas.addEventListener('pointerdown', event => {
    if (event.button !== 0) return; canvas.setPointerCapture(event.pointerId); pointers.set(event.pointerId, {x: event.clientX, y: event.clientY});
    down = {x: event.clientX, y: event.clientY}; traveled = 0; pinch = 0; setRotate(false); canvas.focus({preventScroll: true}); $('space-tooltip').hidden = true;
  });
  canvas.addEventListener('pointermove', event => {
    if (!pointers.has(event.pointerId)) {
      const n = hitAt(event.clientX, event.clientY), tip = $('space-tooltip'); tip.hidden = !n; canvas.style.cursor = n ? 'pointer' : 'grab';
      if (n) { tip.textContent = `${TYPES[n.kind].label} · ${n.title}`; tip.style.left = `${Math.min(event.clientX - canvas.getBoundingClientRect().left + 14, stage.clientWidth - 275)}px`; tip.style.top = `${event.clientY - canvas.getBoundingClientRect().top + 14}px`; }
      return;
    }
    const old = pointers.get(event.pointerId); pointers.set(event.pointerId, {x: event.clientX, y: event.clientY});
    if (pointers.size === 2) {
      const [a, b] = [...pointers.values()], distance = Math.hypot(a.x - b.x, a.y - b.y);
      if (pinch > 0) orbit.desiredRadius = THREE.MathUtils.clamp(orbit.desiredRadius * pinch / Math.max(distance, 1), 22, 350);
      pinch = distance; traveled = 100;
    } else {
      const dx = event.clientX - old.x, dy = event.clientY - old.y; traveled += Math.abs(dx) + Math.abs(dy);
      orbit.theta -= dx * .006; orbit.phi = THREE.MathUtils.clamp(orbit.phi - dy * .006, .12, Math.PI - .12);
    }
    wake();
  });
  canvas.addEventListener('pointerup', event => {
    const clicked = pointers.size === 1 && traveled < 6 && down; pointers.delete(event.pointerId); pinch = 0;
    if (clicked) { const n = hitAt(event.clientX, event.clientY); if (n) selectNode(n.id); }
    down = null;
  });
  canvas.addEventListener('pointercancel', event => { pointers.delete(event.pointerId); down = null; pinch = 0; });
  canvas.addEventListener('pointerleave', () => { $('space-tooltip').hidden = true; });
  canvas.addEventListener('wheel', event => { event.preventDefault(); setRotate(false); orbit.desiredRadius = THREE.MathUtils.clamp(orbit.desiredRadius * Math.exp(Math.sign(event.deltaY) * .1), 22, 350); wake(); }, {passive: false});
  canvas.addEventListener('keydown', event => {
    if (!['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', '+', '=', '-', 'Home', ' '].includes(event.key)) return;
    event.preventDefault(); setRotate(false);
    if (event.key === 'ArrowLeft') orbit.theta -= .12;
    if (event.key === 'ArrowRight') orbit.theta += .12;
    if (event.key === 'ArrowUp') orbit.phi = Math.max(.12, orbit.phi - .12);
    if (event.key === 'ArrowDown') orbit.phi = Math.min(Math.PI - .12, orbit.phi + .12);
    if (['+', '='].includes(event.key)) orbit.desiredRadius = Math.max(22, orbit.desiredRadius * .85);
    if (event.key === '-') orbit.desiredRadius = Math.min(350, orbit.desiredRadius * 1.15);
    if (event.key === 'Home') overview();
    if (event.key === ' ') setRotate(true);
    wake();
  });
  canvas.addEventListener('webglcontextlost', event => { event.preventDefault(); $('space-status').textContent = 'Đồ họa 3D tạm dừng. Bạn vẫn có thể tìm và đọc tri thức; tải lại trang để mở lại đồ họa.'; if (frame) cancelAnimationFrame(frame); frame = 0; renderer = null; });
  new ResizeObserver(resize).observe(stage);
  new IntersectionObserver(entries => { inViewport = entries[0].isIntersecting; if (inViewport) wake(); }, {threshold: .01}).observe(stage);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) wake(); });
  reducedMotion.addEventListener('change', () => { if (reducedMotion.matches) setRotate(false); });
  resize();
}

function renderSearch() {
  const query = $('space-search').value.trim().toLocaleLowerCase('vi'), results = $('space-search-results');
  results.replaceChildren(); results.hidden = !query;
  if (!query || !graph) return;
  const found = graph.nodes.filter(n => enabled.has(n.kind) && `${n.title} ${n.id} ${n.ref?.workflow_id || ''} ${TYPES[n.kind].label}`.toLocaleLowerCase('vi').includes(query));
  results.append(text('p', `${found.length} kết quả${found.length > 12 ? ' · hiển thị 12 kết quả đầu' : ''}`));
  for (const n of found.slice(0, 12)) {
    const b = action(`${TYPES[n.kind].label} · ${n.title}`, () => { selectNode(n.id); results.hidden = true; stage.scrollIntoView({behavior: reducedMotion.matches ? 'instant' : 'smooth', block: 'start'}); }); b.dataset.spaceResult = n.id; results.append(b);
  }
  if (!found.length) results.append(text('p', 'Thử từ khóa khác hoặc bật thêm loại nút bên dưới.'));
}
function renderLegend() {
  for (const [kind, definition] of Object.entries(TYPES)) {
    if (kind === 'root') continue;
    const label = document.createElement('label'), check = document.createElement('input'); check.type = 'checkbox'; check.checked = true; check.dataset.spaceType = kind;
    const dot = text('span', '', 'legend-dot'); dot.style.setProperty('--node-color', definition.color);
    label.append(check, dot, text('span', definition.label)); $('space-legend').append(label);
    check.addEventListener('change', () => {
      if (check.checked) enabled.add(kind); else enabled.delete(kind);
      if (selected && !enabled.has(graph?.byId.get(selected)?.kind)) overview();
      updateVisibility(); renderSearch();
    });
  }
}
function prepareTour() {
  const relation = graph.nodes.find(n => n.kind === 'relation' && n.ref.workflow_id === 'REAL_WF_0003') || graph.nodes.find(n => n.kind === 'relation');
  const basisId = relation && graph.workflows.get(relation.workflow).id(relation.data.claim_ids[0]);
  const claim = graph.byId.get(basisId) || graph.nodes.find(n => n.kind === 'claim' && n.data.evidence_links.length);
  const question = graph.nodes.find(n => n.kind === 'question' && n.ref.workflow_id === 'REAL_WF_0003') || graph.nodes.find(n => n.kind === 'question');
  const wf = relation ? graph.byId.get(relation.workflow) : graph.nodes.find(n => n.kind === 'workflow');
  stops = [{title: 'Một kho kinh nghiệm dùng chung', text: `${graph.counts.workflow} quy trình và ${graph.counts.claim} phát biểu trong kho đang chọn. Chọn từng cụm để khám phá thao tác cùng nguồn hỗ trợ.`, node: null}];
  if (relation) stops.push({title: 'Quyết định có điều kiện', text: 'Quan hệ giữa các bước giữ điều kiện chuyển bước và căn cứ từ nguồn. Đọc điều kiện trong bảng bên cạnh.', node: relation.id});
  if (claim) stops.push({title: 'Mở nguồn của một phát biểu', text: 'Phát biểu dẫn tới đoạn lời nói, khung hình hoặc tài liệu. Bấm “Mở bằng chứng” để đối chiếu trực tiếp.', node: claim.id});
  if (question) stops.push({title: 'Phần chưa biết cần được bổ sung', text: 'Câu hỏi mở gắn đúng bước và trường còn thiếu. Người có kinh nghiệm bổ sung, người kiểm đối chiếu, tri thức được cập nhật thành phiên bản mới.', node: question.id});
  if (wf) stops.push({title: 'Tích lũy có review và phạm vi', text: 'Số phát biểu đã đối chiếu nguồn và đã xác nhận chuyên môn được ghi riêng. Bản demo hiện dùng nguồn pilot; hiệu quả đào tạo cần đo trong thử nghiệm tiếp theo.', node: wf.id});
}
function showStop(index) {
  if (!graph || !stops.length) return;
  tourIndex = Math.max(0, Math.min(index, stops.length - 1)); const stop = stops[tourIndex];
  $('tour-card').hidden = false; $('tour-count').textContent = `CÂU CHUYỆN ${tourIndex + 1} / ${stops.length}`;
  $('tour-title').textContent = stop.title; $('tour-text').textContent = stop.text;
  $('tour-prev').disabled = tourIndex === 0; $('tour-next').textContent = tourIndex === stops.length - 1 ? 'Kết thúc ✓' : 'Tiếp →';
  if (stop.node) selectNode(stop.node); else { overview(); setRotate(!reducedMotion.matches); }
}
function closeTour() { tourIndex = -1; $('tour-card').hidden = true; setRotate(false); }
function clearRoute() {
  routeDisplay = null; if (routeParticles) routeParticles.visible = false;
  $('space-canvas').dataset.routeStage = ''; $('space-canvas').dataset.routeNodes = '[]';
  if (graph) { updateVisibility(); updateLabels(); wake(); }
}
function updateRouteParticles(time) {
  if (!routeParticles) return;
  const hops = routeDisplay?.hops || [];
  routeParticles.visible = lens === 'route' && routeUI?.playing && hops.length > 0 && !reducedMotion.matches;
  if (!routeParticles.visible) return;
  for (let i = 0; i < 3; i++) {
    const progress = Math.max(0, (time - routeStarted) / 1600 + i / 3), hop = hops[Math.floor(progress) % hops.length];
    dummy.position.fromArray(graph.byId.get(hop.from).position).lerp(new THREE.Vector3(...graph.byId.get(hop.to).position), progress % 1);
    dummy.scale.setScalar(enabled.has(graph.byId.get(hop.from).kind) && enabled.has(graph.byId.get(hop.to).kind) ? 1 : 0); dummy.updateMatrix(); routeParticles.setMatrixAt(i, dummy.matrix);
  }
  routeParticles.instanceMatrix.needsUpdate = true;
}
function showRouteFrame(frame) {
  if (lens !== 'route' || !baseGraph) return;
  const scopeRef = (frame.event.refs || []).find(r => r.kind === 'workflow' && r.state === 'selected');
  const scope = scopeRef ? nodeId(graph, scopeRef) : routeDisplay?.scope;
  routeDisplay = {...frame, scope}; routeStarted = performance.now(); selected = null; neighborhood.clear(); setRotate(false);
  for (const id of frame.active) { const n = graph.byId.get(id); if (n) { enabled.add(n.kind); const c = document.querySelector(`[data-space-type="${n.kind}"]`); if (c) c.checked = true; } }
  $('space-trace').hidden = false;
  $('space-trace').replaceChildren(text('span', 'TRUY XUẤT THỰC'), text('span', '→', 'trace-arrow'), text('strong', STAGES[frame.event.stage][0]), text('span', frame.total ? `${frame.position} / ${frame.total}` : 'ĐANG CHẠY'));
  const center = scope ? graph.workflows.get(scope)?.center : null;
  orbit.desiredTarget.fromArray(center || [0, 0, 0]); orbit.desiredRadius = center ? 115 : 180;
  if (reducedMotion.matches) { orbit.target.copy(orbit.desiredTarget); orbit.radius = orbit.desiredRadius; }
  renderRouteInspector(frame); updateVisibility(); updateLabels(); wake();
  $('space-canvas').dataset.routeStage = frame.event.stage;
  $('space-canvas').dataset.routeNodes = JSON.stringify([...frame.active]);
}
function renderRouteInspector(frame) {
  clearEvidence(); content.replaceChildren();
  const event = frame.event, data = event.data || {}, [title, description] = STAGES[event.stage];
  $('inspector-kind').textContent = 'ĐƯỜNG TRUY XUẤT CÓ THỂ KIỂM TRA'; $('inspector-title').textContent = title;
  content.append(text('p', description), text('p', 'Nút sáng lấy từ sự kiện backend. Hạt chuyển động mô phỏng nhịp trình chiếu.', 'inspector-note'));
  if (data.strategy) content.append(text('span', `${data.strategy.toUpperCase()}${data.top_k ? ` · TOP ${data.top_k}` : ''}`, 'inspector-chip'));
  const statuses = {retrieved: 'Đã tìm thấy ứng viên', answered: 'Câu trả lời đã qua kiểm tra', insufficient_evidence: 'Chưa đủ bằng chứng', needs_clarification: 'Cần làm rõ ngữ cảnh', conflicting_sources: 'Nguồn có mâu thuẫn'};
  if (data.status) content.append(text('span', statuses[data.status] || data.status, `inspector-chip ${['retrieved', 'answered'].includes(data.status) ? '' : 'pending'}`));
  if (data.latency_ms !== undefined) content.append(text('p', `Truy xuất thực: ${data.latency_ms.toFixed(1)} ms. Nhịp phát đồ thị được giãn để quan sát.`, 'inspector-note'));
  if (event.stage === 'matched') content.append(text('p', `${data.steps} bước khớp trực tiếp · ${data.claims} phát biểu ứng viên.`));
  if (event.stage === 'expanded') content.append(text('p', data.related_steps ? `Thêm ${data.related_steps} bước theo quan hệ đã lưu. Nội dung này bổ sung ngữ cảnh.` : 'Không thêm bước phụ thuộc ở lượt này; các bước cần thiết có thể đã nằm trong kết quả khớp.'));
  if (event.stage === 'evidence') content.append(text('p', `${data.answer_candidates} ứng viên mở được nguồn · ${data.context_candidates} phát biểu ngữ cảnh · ${data.unavailable} không mở đủ bằng chứng.`));
  if (data.missing_context?.length) content.append(text('p', `Cần làm rõ: ${data.missing_context.join(', ')}`, 'inspector-note'));
  if (event.stage === 'done') {
    if (data.answer) {
      content.append(text('h3', 'Kết quả AI đã kiểm'), text('p', data.answer.answer, 'route-answer'));
      for (const citation of data.answer.citations) {
        const n = graph.byId.get(nodeId(graph, {...citation.claim_ref, kind: 'claim', entity_id: citation.claim_ref.entity_id})); if (!n) continue;
        const box = text('div', '', 'route-candidate'); box.append(linkedButton(n.id, citation.answer_span), reviewChips(n.data));
        for (const eid of citation.evidence_ids) { const ev = graph.workflows.get(n.workflow).wf.evidence.find(e => e.evidence_id === eid); if (ev) { const b = action(`Mở nguồn trích dẫn · r${n.ref.revision} ↗`, () => showEvidence(n, ev)); b.dataset.evidenceId = eid; box.append(b); } }
        content.append(box);
      }
    } else content.append(text('h3', 'Ứng viên đã kiểm bằng chứng'), text('p', 'Lượt này chỉ chạy truy xuất. Bật tạo câu trả lời AI để chạy thêm bước soạn và kiểm tra bằng model.', 'inspector-note'));
    if (!data.answer) for (const candidate of data.candidates || []) {
      const n = graph.byId.get(nodeId(graph, {...candidate.claim_ref, kind: 'claim'})); if (!n) continue;
      const box = text('div', '', 'route-candidate'); box.dataset.routeCandidate = n.id;
      box.append(linkedButton(n.id, candidate.text), reviewChips(n.data));
      for (const eid of candidate.evidence_ids) { const ev = graph.workflows.get(n.workflow).wf.evidence.find(e => e.evidence_id === eid); if (ev) { const b = action(`Mở bằng chứng · r${n.ref.revision} ↗`, () => showEvidence(n, ev)); b.dataset.evidenceId = eid; box.append(b); } }
      content.append(box);
    }
    if (!data.candidates?.length && !data.answer) content.append(text('p', 'Không có phát biểu đủ bằng chứng để đưa vào câu trả lời.', 'inspector-note'));
  } else for (const ref of (event.refs || []).filter(r => ['workflow', 'step', 'relation', 'claim', 'question'].includes(r.kind)).slice(0, 7)) {
    const n = graph.byId.get(nodeId(graph, ref)); if (!n) continue;
    const b = linkedButton(n.id, `${ref.state === 'context' ? 'Ngữ cảnh · ' : ref.state === 'blocked' ? 'Bị chặn · ' : ''}${n.title}`);
    content.append(b);
    if (ref.score !== undefined) content.append(text('p', `Điểm xếp hạng: ${ref.score.toFixed(3)}`, 'inspector-note'));
  }
  document.querySelector('.space-inspector').scrollTop = 0;
}
function updateMetrics() {
  $('space-canvas').dataset.nodeCount = String(graph.nodes.length);
  $('space-canvas').dataset.edgeCount = String(graph.edges.length);
  $('space-metrics').replaceChildren();
  for (const [key, label] of [['workflow', 'QUY TRÌNH'], ['claim', 'PHÁT BIỂU'], ['evidence', 'BẰNG CHỨNG'], ['question', 'CÂU HỎI MỞ']]) {
    const count = key === 'question' ? graph.nodes.filter(n => n.kind === 'question' && n.data.status === 'open').length : graph.counts[key];
    const metric = document.createElement('div'); metric.append(text('strong', count), text('span', label)); $('space-metrics').append(metric);
  }
}
function activateGraph(value) {
  graph = value; selected = null; clearEvidence(); $('space-tooltip').hidden = true;
  $('space-search').value = ''; renderSearch(); updateMetrics(); drawGraph(); overview(); prepareTour();
  $('space-status').textContent = `${graph.nodes.length} nút · ${graph.edges.length} liên kết bản ghi và nguồn · ${graph.counts.relation} quan hệ giữa bước`;
}
function resetExplorer() {
  routeUI?.reset();
  shell.classList.remove('is-routing');
  viewToken++; viewController?.abort(); lens = 'overview'; situation = null; comparison = null; history = null; phase = 'changes'; baseGraph = null;
  for (const b of document.querySelectorAll('[data-lens]')) b.setAttribute('aria-pressed', String(b.dataset.lens === lens));
  for (const id of ['situation-controls', 'history-controls', 'route-controls', 'revision-playback', 'explorer-note', 'space-trace']) $(id).hidden = true;
  $('situation-select').replaceChildren(); $('history-workflow').replaceChildren();
  $('changes-only').checked = false;
}
function setLens(value) {
  if (!baseGraph) return;
  routeUI?.reset();
  shell.classList.toggle('is-routing', value === 'route');
  viewToken++; viewController?.abort(); closeTour(); clearEvidence(); lens = value; situation = null; comparison = null;
  for (const b of document.querySelectorAll('[data-lens]')) b.setAttribute('aria-pressed', String(b.dataset.lens === value));
  $('situation-controls').hidden = value !== 'situation'; $('history-controls').hidden = value !== 'history';
  $('route-controls').hidden = value !== 'route';
  $('revision-playback').hidden = true; $('space-trace').hidden = true;
  $('explorer-note').hidden = ['overview', 'route'].includes(value);
  activateGraph(baseGraph);
  if (value === 'situation') applySituation();
  if (value === 'history') loadHistory();
}
function prepareExplorer() {
  const options = situations(baseGraph);
  for (const s of options) {
    const option = text('option', `${s.node.ref.workflow_id} · ${s.label}`); option.value = s.node.id; $('situation-select').append(option);
  }
  $('situation-select').disabled = !options.length; $('situation-trace').disabled = !options.length;
  const workflows = [...baseGraph.workflows.values()].sort((a, b) =>
    (a.wf.workflow_id === 'B0_SRC_HAAS_0005' ? -1 : 0) - (b.wf.workflow_id === 'B0_SRC_HAAS_0005' ? -1 : 0));
  for (const info of workflows) {
    const option = text('option', `${info.wf.workflow_id} · ${info.wf.title}`); option.value = info.prefix; $('history-workflow').append(option);
  }
}
function applySituation() {
  situation = situations(baseGraph).find(s => s.node.id === $('situation-select').value);
  if (!situation) { $('explorer-note').textContent = 'Kho này chưa có quan hệ bước được ghi nhận. Chọn bước ở Toàn cảnh để đọc nguồn và phần còn thiếu.'; return; }
  const s = situation;
  $('explorer-note').textContent = 'Khám phá nhánh đã ghi trong nguồn. Điều kiện thực tế của máy cần được người vận hành xác nhận.';
  $('space-trace').hidden = false; $('space-trace').replaceChildren();
  $('space-trace').append(text('span', `BƯỚC ${s.from.data.display_order}`), text('span', '→', 'trace-arrow'), text('strong', s.node.data.relation_type === 'branch_if' ? 'NHÁNH CÓ ĐIỀU KIỆN' : 'ĐIỀU KIỆN TIÊN QUYẾT'), text('span', '→', 'trace-arrow'), text('span', `BƯỚC ${s.to.data.display_order}`));
  selectNode(s.node.id, false); neighborhood.clear(); for (const id of s.path) neighborhood.add(id);
  const points = [...s.path].map(id => graph.byId.get(id)?.position).filter(Boolean);
  orbit.desiredTarget.fromArray(points.reduce((sum, p) => sum.map((v, i) => v + p[i] / points.length), [0, 0, 0])); orbit.desiredRadius = 100;
  if (reducedMotion.matches) { orbit.target.copy(orbit.desiredTarget); orbit.radius = orbit.desiredRadius; }
  const intro = text('div', '', 'situation-intro');
  intro.append(text('span', 'TỪ ĐIỀU KIỆN TỚI THAO TÁC', 'inspector-note'), text('p', 'Đường sáng nối bước, điều kiện, thao tác và bằng chứng của nhánh này. Các mũi tên đi theo liên kết đã lưu.'));
  content.prepend(intro);
  const claims = new Map(s.info.wf.claims.map(c => [c.claim_id, c]));
  content.append(text('h3', `Khi chuyển tới bước ${s.to.data.display_order}`));
  for (const role of ['action', 'rationale', 'outcome', 'acceptance_criteria']) {
    content.append(text('h3', ROLES[role]));
    const field = s.to.data.fields[role];
    if (!field.claim_ids.length) content.append(text('p', field.state === 'not_applicable' ? 'Không áp dụng' : 'Nguồn chưa ghi nhận — cần thu thập thêm.', 'inspector-note'));
    for (const cid of field.claim_ids) content.append(claimCard(s.node, claims.get(cid)));
  }
  for (const q of s.info.wf.questions.filter(q => q.step_id === s.to.data.step_id && q.status === 'open')) content.append(linkedButton(s.info.id(q.question_id), `Cần hỏi thêm: ${q.question}`));
  updateVisibility(); updateLabels(); wake();
}
function revisionParams(build) { return new URLSearchParams({mode: baseGraph.mode, dataset_split: 'dev', index_build_id: build}); }
async function loadHistory() {
  const info = baseGraph.workflows.get($('history-workflow').value); if (!info) return;
  const token = ++viewToken; viewController?.abort(); viewController = new AbortController(); const signal = viewController.signal;
  history = null; comparison = null; $('revision-playback').hidden = true; $('space-trace').hidden = true;
  $('history-before').disabled = true; $('history-after').disabled = true;
  $('history-before').replaceChildren(); $('history-after').replaceChildren();
  activateGraph(baseGraph); selectNode(info.prefix);
  $('explorer-note').textContent = 'Đang đọc lịch sử phiên bản…';
  try {
    const result = await get(`/v1/workflows/${encodeURIComponent(info.wf.workflow_id)}/${info.wf.revision}/history?${revisionParams(catalog.index_build_id)}`, signal);
    if (token !== viewToken || lens !== 'history') return;
    history = result;
    const available = history.revisions.filter(r => r.index_build_id);
    for (const id of ['history-before', 'history-after']) for (const r of history.revisions) {
      const unavailable = r.review_counts.source.source_checked ? 'chưa có index lịch sử' : 'chưa đủ review nguồn';
      const option = text('option', `r${r.revision}${r.index_build_id ? '' : ` · ${unavailable}`}`); option.value = r.revision; option.disabled = !r.index_build_id; $(id).append(option);
    }
    if (available.length < 2) {
      $('explorer-note').textContent = history.revisions.length < 2 ? 'Quy trình này mới có một phiên bản; chưa có thay đổi để so sánh.' : 'Bản cũ chưa có index lịch sử. Chuẩn bị database demo theo hướng dẫn để mở đúng bằng chứng của cả hai bản.';
      return;
    }
    $('history-before').disabled = false; $('history-after').disabled = false;
    $('history-before').value = available.at(-2).revision; $('history-after').value = available.at(-1).revision;
    revisionLimits(); await loadComparison();
  } catch (error) { if (token === viewToken && error.name !== 'AbortError') $('explorer-note').textContent = error.message; }
}
function revisionLimits(changed) {
  const available = history.revisions.filter(r => r.index_build_id).map(r => r.revision);
  let before = +$('history-before').value, after = +$('history-after').value;
  if (before >= after) {
    if (changed === 'before') after = available.find(r => r > before);
    else before = available.filter(r => r < after).at(-1);
  }
  $('history-before').value = before; $('history-after').value = after;
  for (const o of $('history-before').options) o.disabled = !available.includes(+o.value) || +o.value >= after;
  for (const o of $('history-after').options) o.disabled = !available.includes(+o.value) || +o.value <= before;
}
async function loadComparison() {
  if (!history || lens !== 'history') return;
  const token = ++viewToken; viewController?.abort(); viewController = new AbortController(); const signal = viewController.signal;
  comparison = null; clearEvidence(); $('revision-playback').hidden = true; $('space-trace').hidden = true;
  $('explorer-note').textContent = 'Đang đối chiếu hai snapshot và index của từng phiên bản…';
  // Clear the old comparison immediately, including its picks and source buttons.
  activateGraph(baseGraph);
  try {
    const revisions = [+$('history-before').value, +$('history-after').value];
    const snapshots = await Promise.all(revisions.map(rev => {
      const build = history.revisions.find(r => r.revision === rev)?.index_build_id;
      if (!build) throw new Error('Phiên bản này chưa có index lịch sử.');
      return get(`/v1/workflows/${encodeURIComponent(history.workflow_id)}/${rev}?${revisionParams(build)}`, signal);
    }));
    if (token !== viewToken || lens !== 'history') return;
    comparison = compareSnapshots(baseGraph.mode, ...snapshots);
    $('explorer-note').textContent = 'So sánh cùng ID trong hai bản đã lưu. Đổi màu thể hiện nội dung hoặc liên kết thay đổi; không tự nâng mức xác nhận chuyên môn.';
    $('revision-playback').hidden = false; $('changes-only').checked = false;
    renderRevisionSummary(); setPhase('changes');
  } catch (error) { if (token === viewToken && error.name !== 'AbortError') $('explorer-note').textContent = error.message; }
}
function renderRevisionSummary() {
  const box = $('revision-summary'); box.replaceChildren();
  for (const key of ['added', 'changed', 'removed']) {
    const b = action(`${comparison.counts[key]} ${changeLabels[key].toLocaleLowerCase('vi')}`, () => {
      setPhase('changes'); const n = graph.nodes.find(n => n.change === key && n.kind === 'claim') || graph.nodes.find(n => n.change === key); if (n) selectNode(n.id);
    }); b.className = `change-stat ${key}`; b.disabled = !comparison.counts[key]; box.append(b);
  }
  box.append(text('span', `${comparison.counts.unchanged} nút giữ nguyên`, 'unchanged-count'));
}
function setPhase(value) {
  if (!comparison) return;
  phase = value; for (const b of document.querySelectorAll('[data-phase]')) b.setAttribute('aria-pressed', String(b.dataset.phase === value));
  $('changes-only').disabled = value !== 'changes';
  activateGraph(value === 'changes' ? comparison.union : comparison[value]);
  $('space-trace').hidden = false;
  $('space-trace').replaceChildren(text('span', `r${comparison.beforeSnapshot.workflow.revision}`), text('span', '→', 'trace-arrow'), text('strong', value === 'changes' ? 'TRI THỨC THAY ĐỔI' : value === 'before' ? 'BẢN TRƯỚC' : 'BẢN SAU'), text('span', `r${comparison.afterSnapshot.workflow.revision}`));
  orbit.desiredTarget.set(24, 0, 0); orbit.desiredRadius = 110;
  if (reducedMotion.matches) { orbit.target.copy(orbit.desiredTarget); orbit.radius = orbit.desiredRadius; }
  $('space-status').textContent = `So sánh ${history.workflow_id} · r${comparison.beforeSnapshot.workflow.revision} → r${comparison.afterSnapshot.workflow.revision} · ${value === 'changes' ? 'hiển thị hợp hai bản' : value === 'before' ? 'snapshot trước' : 'snapshot sau'}`;
  wake();
}
function renderChangeInspector(n) {
  const beforeRev = comparison.beforeSnapshot.workflow.revision, afterRev = comparison.afterSnapshot.workflow.revision;
  if (n.kind === 'root') {
    $('inspector-kind').textContent = 'LỊCH SỬ CÓ THỂ KIỂM CHỨNG'; $('inspector-title').textContent = `Tri thức thay đổi · r${beforeRev} → r${afterRev}`;
    content.append(text('p', 'Chọn phần đổi màu để đọc hai bản cạnh nhau và mở nguồn của từng phiên bản. Màu xanh là thêm, vàng là thay đổi, hồng là bỏ.'));
    const ec = comparison.edgeCounts;
    content.append(text('p', `Liên kết: ${ec.added} thêm · ${ec.changed} thay đổi · ${ec.removed} bỏ.`, 'inspector-note'));
    for (const changed of graph.nodes.filter(n => n.change !== 'unchanged')) content.append(linkedButton(changed.id, `${changeLabels[changed.change]} · ${changed.title}`));
    const entry = history.revisions.find(r => r.revision === afterRev);
    if (entry?.change_log.length) {
      content.append(text('h3', 'Nhật ký đã lưu'));
      for (const log of entry.change_log) content.append(text('p', log.reason || log.summary || JSON.stringify(log), 'inspector-note'));
    }
  } else {
    content.append(text('span', changeLabels[n.change], `inspector-chip change-${n.change}`));
    if (n.fields?.length) {
      const labels = {evidence_links: 'liên kết bằng chứng', text: 'nội dung', source_review: 'đối chiếu nguồn', technical_review: 'xác nhận chuyên môn', fields: 'trường tri thức', scope: 'phạm vi', claim_ids: 'căn cứ', condition_claim_ids: 'điều kiện', status: 'trạng thái câu hỏi'};
      content.append(text('p', `Thay đổi: ${n.fields.map(f => labels[f] || f).join(', ')}.`, 'inspector-note'));
    }
    for (const [version, original, rev] of [['before', n.beforeNode, beforeRev], ['after', n.afterNode, afterRev]]) {
      const section = text('section', '', `revision-card revision-${version}`); section.dataset.revision = rev;
      section.append(text('h3', `${version === 'before' ? 'Bản trước' : 'Bản sau'} · r${rev}`));
      if (!original) section.append(text('p', version === 'before' ? 'Chưa có trong bản này.' : 'Không còn trong bản này.', 'inspector-note'));
      else if (original.kind === 'claim') section.append(claimCard(original, original.data));
      else if (original.kind === 'evidence') {
        section.append(text('p', original.data.quote || original.data.observation_note || original.title));
        const b = action(`Mở bằng chứng r${rev} ↗`, () => showEvidence(original, original.data)); b.dataset.evidenceId = original.data.evidence_id; section.append(b);
      } else {
        section.append(text('p', original.title));
        if (original.data && n.fields?.length) {
          const details = document.createElement('details'); details.append(text('summary', 'Chi tiết trường thay đổi'));
          for (const field of n.fields) details.append(text('p', `${field}: ${JSON.stringify(original.data[field])}`, 'inspector-note'));
          section.append(details);
        }
      }
      content.append(section);
    }
  }
  document.querySelector('.space-inspector').scrollTop = 0;
}
function exitPresentation() {
  shell.classList.remove('is-presenting'); $('presentation-exit')?.remove();
  if (document.fullscreenElement) document.exitFullscreen().catch(() => {}); resize();
}
async function present() {
  if (shell.classList.contains('is-presenting')) { exitPresentation(); return; }
  shell.classList.add('is-presenting');
  const b = action('Thoát trình chiếu · Esc', exitPresentation); b.id = 'presentation-exit'; b.className = 'presentation-exit'; shell.append(b);
  try { if (shell.requestFullscreen) await shell.requestFullscreen(); } catch { /* CSS presentation still works when fullscreen is unavailable. */ }
  resize();
}
document.addEventListener('keydown', event => { if (event.key === 'Escape') { exitPresentation(); closeTour(); } });
document.addEventListener('fullscreenchange', () => { if (!document.fullscreenElement && shell.classList.contains('is-presenting')) exitPresentation(); });
let loadController = null;
async function load() {
  const token = ++loading, mode = $('space-mode').value;
  loadController?.abort(); loadController = new AbortController(); const signal = loadController.signal;
  resetExplorer(); closeTour(); clearEvidence(); graph = null; catalog = null; selected = null; setRotate(false); $('space-search').value = ''; renderSearch();
  $('space-tooltip').hidden = true; $('space-labels').replaceChildren(); labelNodes = []; $('space-metrics').replaceChildren();
  if (mesh && scene) { scene.remove(mesh, edgeLines, highlightLines); selectionRing.visible = false; for (const ring of clusterDecorations) scene.remove(ring); }
  $('space-canvas').dataset.nodeCount = '0'; $('space-canvas').dataset.edgeCount = '0'; $('space-canvas').dataset.selectedNode = '';
  $('inspector-title').textContent = 'Đang tải tri thức'; content.replaceChildren(); $('space-status').textContent = 'Đang đọc quy trình và bằng chứng…';
  $('space-namespace').textContent = mode === 'synthetic' ? 'MÔ PHỎNG' : 'HAAS PILOT';
  $('space-scope').textContent = mode === 'synthetic' ? 'DỮ LIỆU MÔ PHỎNG — dùng kiểm thử phần mềm; không dùng thao tác trên máy.' : 'Pilot dùng nguồn Haas. Đối chiếu nguồn và xác nhận chuyên môn là hai bước riêng.';
  try {
    const currentCatalog = await get(`/v1/workflows?${new URLSearchParams({mode, dataset_split: 'dev'})}`, signal);
    if (token !== loading) return;
    const snapshots = await Promise.all(currentCatalog.workflows.map(wf => get(`/v1/workflows/${encodeURIComponent(wf.workflow_id)}/${wf.revision}?${new URLSearchParams({mode, dataset_split: 'dev', index_build_id: currentCatalog.index_build_id})}`, signal)));
    if (token !== loading) return;
    catalog = currentCatalog; graph = buildGraph(mode, snapshots); baseGraph = graph; prepareExplorer(); updateMetrics();
    $('space-status').textContent = `${graph.nodes.length} nút · ${graph.edges.length} liên kết bản ghi và nguồn · ${graph.counts.relation} quan hệ giữa bước`;
    if (!snapshots.length) $('space-status').textContent = 'Kho đang chọn chưa có quy trình. Hãy import và build index hoặc chọn kho khác.';
    drawGraph(); overview(); prepareTour();
    if (!reducedMotion.matches && renderer) setRotate(true);
  } catch (error) {
    if (token === loading && error.name !== 'AbortError') { $('space-status').textContent = error.message; $('inspector-title').textContent = 'Chưa mở được kho tri thức'; content.append(action('Tải lại kho', load)); }
  }
}
// Read-only inspection hooks. AI calls occur only through the explicit trace option.
window.knowflowSpace = {get graph() { return graph; }, get lens() { return lens; }, get situation() { return situation; }, get comparison() { return comparison; }, get route() { return routeUI; }, get routeDisplay() { return routeDisplay; }, get routeParticles() { return routeParticles; }, select: selectNode, get orbit() { return orbit; }, get renderer() { return renderer; },
  project(id) { const n = graph?.byId.get(id); if (!n || !camera) return null; const p = new THREE.Vector3(...n.position).project(camera), r = renderer.domElement.getBoundingClientRect(); return {x: r.left + (p.x * .5 + .5) * r.width, y: r.top + (-p.y * .5 + .5) * r.height, z: p.z}; }};
$('space-mode').addEventListener('change', load);
for (const b of document.querySelectorAll('[data-lens]')) b.addEventListener('click', () => setLens(b.dataset.lens));
$('situation-select').addEventListener('change', applySituation);
$('situation-trace').addEventListener('click', applySituation);
$('history-workflow').addEventListener('change', loadHistory);
for (const which of ['before', 'after']) $(`history-${which}`).addEventListener('change', () => { revisionLimits(which); loadComparison(); });
for (const b of document.querySelectorAll('[data-phase]')) b.addEventListener('click', () => setPhase(b.dataset.phase));
$('changes-only').addEventListener('change', () => { selected = null; overview(); updateVisibility(); });
$('space-search').addEventListener('input', renderSearch);
$('space-reset').addEventListener('click', () => { setLens('overview'); overview(); });
$('space-rotate').addEventListener('click', () => setRotate(!orbit.rotating));
$('space-fullscreen').addEventListener('click', present);
$('tour-start').addEventListener('click', () => { setLens('overview'); stage.scrollIntoView({behavior: reducedMotion.matches ? 'instant' : 'smooth', block: 'start'}); showStop(0); });
$('stage-tour').addEventListener('click', () => { setLens('overview'); showStop(0); });
$('tour-prev').addEventListener('click', () => showStop(tourIndex - 1));
$('tour-next').addEventListener('click', () => { if (tourIndex === stops.length - 1) closeTour(); else showStop(tourIndex + 1); });
$('tour-close').addEventListener('click', closeTour);
async function start() {
  try {
    const health = await get('/v1/health');
    const modes = new Set(health.namespaces.filter(n => n.dataset_split === 'dev').map(n => n.mode));
    for (const option of $('space-mode').options) option.disabled = !modes.has(option.value);
    if (!modes.has($('space-mode').value)) {
      const available = [...$('space-mode').options].find(option => !option.disabled);
      if (available) $('space-mode').value = available.value;
    }
  } catch { /* The catalog request below reports the actual availability error. */ }
  load();
}
renderLegend(); initRenderer();
routeUI = createRoute({getGraph: () => graph, getCatalog: () => catalog, onFrame: showRouteFrame, onClear: clearRoute, reducedMotion});
start();
