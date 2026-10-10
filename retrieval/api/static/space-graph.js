// Project explicit snapshot references into a display graph. Coordinates are layout,
// never inferred semantic similarity. Entity identity includes corpus/workflow/revision.
export const TYPES = {
  root: {label: 'Kho tri thức', color: '#b7ffe9', radius: 3.3},
  workflow: {label: 'Quy trình', color: '#80e6c7', radius: 2.5},
  step: {label: 'Bước', color: '#70aaff', radius: 1.2},
  claim: {label: 'Phát biểu', color: '#b4a1ff', radius: .65},
  relation: {label: 'Quan hệ bước', color: '#f6c378', radius: 1.15},
  evidence: {label: 'Bằng chứng', color: '#5ed4e5', radius: .45},
  question: {label: 'Câu hỏi mở', color: '#ffad69', radius: 1},
  source: {label: 'Nguồn', color: '#9ebbd0', radius: 1.3}
};
export const ROLES = {context: 'Bối cảnh', observation: 'Dấu hiệu', action: 'Thao tác', rationale: 'Lý do', condition: 'Điều kiện', outcome: 'Kết quả ghi nhận', acceptance_criteria: 'Tiêu chí xác nhận'};
export const RELATIONS = {observed_next: 'Tiếp theo trong nguồn', requires: 'Điều kiện tiên quyết', branch_if: 'Nhánh có điều kiện', repeated_step: 'Thao tác lặp', corrects: 'Đính chính'};
export function buildGraph(mode, snapshots) {
  const nodes = [], edges = [], byId = new Map(), workflows = new Map();
  const put = n => { if (!byId.has(n.id)) { nodes.push(n); byId.set(n.id, n); } return byId.get(n.id); };
  const edge = (from, to, kind, data = null) => edges.push({from, to, kind, data});
  const root = `${mode}:dev`;
  put({id: root, kind: 'root', title: mode === 'real' ? 'KnowFlow · Haas pilot' : 'KnowFlow · Mô phỏng', position: [0, 0, 0]});
  const ordered = [...snapshots].sort((a, b) => a.workflow.workflow_id.localeCompare(b.workflow.workflow_id));
  ordered.forEach((snapshot, wi) => {
    const wf = snapshot.workflow, prefix = `${root}:${wf.workflow_id}@${wf.revision}`;
    const id = entity => `${prefix}:${entity}`;
    const angle = (wi / Math.max(ordered.length, 1)) * Math.PI * 2 + Math.PI / 4;
    const center = ordered.length === 1 ? [24, 0, 0] : [Math.cos(angle) * 54, Math.sin(angle) * 31, Math.sin(angle * 2) * 13];
    const pos = (x, y, z) => [center[0] + x, center[1] + y, center[2] + z];
    workflows.set(prefix, {snapshot, wf, id, prefix, center});
    const ref = {workflow_id: wf.workflow_id, revision: wf.revision};
    const base = {workflow: prefix, ref};
    put({...base, id: prefix, kind: 'workflow', title: wf.title, data: wf, position: center});
    edge(root, prefix, 'contains_workflow');
    const steps = [...wf.steps].sort((a, b) => a.display_order - b.display_order);
    const claimSteps = new Map();
    steps.forEach((step, si) => {
      const a = si / Math.max(steps.length, 1) * Math.PI * 2;
      const p = pos(Math.cos(a) * 17, Math.sin(a) * 14, Math.sin(a * 2) * 7);
      put({...base, id: id(step.step_id), kind: 'step', title: `${step.display_order}. ${step.title}`, data: step, position: p});
      edge(prefix, id(step.step_id), 'contains_step');
      for (const [role, field] of Object.entries(step.fields)) for (const cid of field.claim_ids) {
        if (!claimSteps.has(cid)) claimSteps.set(cid, []);
        claimSteps.get(cid).push({step, role});
        edge(id(step.step_id), id(cid), `field:${role}`);
      }
    });
    wf.claims.forEach((claim, ci) => {
      const owner = claimSteps.get(claim.claim_id)?.[0];
      const anchor = owner ? byId.get(id(owner.step.step_id)).position : center;
      const a = ci * 2.39996323, r = 3.5 + (ci % 4) * 1.2;
      put({...base, id: id(claim.claim_id), kind: 'claim', title: claim.text, data: claim,
        position: [anchor[0] + Math.cos(a) * r, anchor[1] + Math.sin(a) * r, anchor[2] + ((ci % 5) - 2) * 2.8]});
      for (const link of claim.evidence_links) edge(id(claim.claim_id), id(link.evidence_id), 'supported_by', link);
      for (const cid of claim.conflicts_with) edge(id(claim.claim_id), id(cid), 'conflicts_with');
      for (const cid of claim.supersedes_claim_ids) edge(id(claim.claim_id), id(cid), 'supersedes');
    });
    wf.evidence.forEach((ev, ei) => {
      const a = ei * 2.39996323, r = 23 + (ei % 4) * 1.7;
      put({...base, id: id(ev.evidence_id), kind: 'evidence', title: ev.quote || ev.observation_note || ev.evidence_id, data: ev,
        position: pos(Math.cos(a) * r, Math.sin(a) * r * .7, ((ei % 7) - 3) * 4)});
      edge(id(ev.evidence_id), `${root}:source:${ev.source_id}`, 'from_source');
      for (const eid of ev.parent_evidence_ids) edge(id(ev.evidence_id), id(eid), 'derived_from');
    });
    wf.relations.forEach((rel, ri) => {
      const from = byId.get(id(rel.from_step_id)), to = byId.get(id(rel.to_step_id));
      if (!from || !to) return;
      put({...base, id: id(rel.relation_id), kind: 'relation', title: `${RELATIONS[rel.relation_type]} · ${from.data.display_order} → ${to.data.display_order}`, data: rel,
        position: from.position.map((v, axis) => (v + to.position[axis]) / 2 + (axis === 2 ? 5 + ri : 0))});
      edge(id(rel.from_step_id), id(rel.relation_id), 'relation_from', rel);
      edge(id(rel.relation_id), id(rel.to_step_id), rel.relation_type, rel);
      for (const cid of rel.claim_ids) edge(id(rel.relation_id), id(cid), 'relation_basis');
      for (const cid of rel.condition_claim_ids) edge(id(rel.relation_id), id(cid), 'branch_condition');
    });
    wf.questions.filter(q => q.status === 'open').forEach((q, qi) => {
      const step = byId.get(id(q.step_id)); if (!step) return;
      put({...base, id: id(q.question_id), kind: 'question', title: q.question, data: q,
        position: step.position.map((v, axis) => v + [2 + qi, 5, 6][axis])});
      edge(id(q.step_id), id(q.question_id), `missing:${q.target_field}`);
    });
    for (const source of snapshot.sources) {
      const sid = `${root}:source:${source.source_id}`;
      put({id: sid, kind: 'source', title: source.title, data: source,
        position: [Math.cos(nodes.filter(n => n.kind === 'source').length * 2.4) * 27, -43, Math.sin(nodes.filter(n => n.kind === 'source').length * 2.4) * 20]});
      edge(prefix, sid, 'uses_source');
    }
  });
  // Historical superseded IDs may not exist in this revision; do not invent nodes.
  const validEdges = edges.filter(e => byId.has(e.from) && byId.has(e.to));
  const adjacency = new Map(nodes.map(n => [n.id, new Set()]));
  for (const e of validEdges) { adjacency.get(e.from).add(e.to); adjacency.get(e.to).add(e.from); }
  const counts = Object.fromEntries(Object.keys(TYPES).map(type => [type, nodes.filter(n => n.kind === type).length]));
  return {nodes, edges: validEdges, byId, workflows, adjacency, counts, root, mode};
}
