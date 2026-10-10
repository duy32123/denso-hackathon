import {buildGraph, RELATIONS} from './space-graph.js';

// Follow stored references only. A situation is a recorded relation, not a
// prediction that its condition is true or that the machine is safe to operate.
export function situations(graph) {
  return graph.nodes.filter(n => n.kind === 'relation').sort((a, b) =>
    (a.ref.workflow_id === 'REAL_WF_0003' ? -1 : 0) - (b.ref.workflow_id === 'REAL_WF_0003' ? -1 : 0) || a.id.localeCompare(b.id)
  ).map(node => {
    const info = graph.workflows.get(node.workflow), r = node.data;
    const path = new Set([node.id, info.id(r.from_step_id), info.id(r.to_step_id)]);
    for (const cid of [...r.condition_claim_ids, ...r.claim_ids]) path.add(info.id(cid));
    for (const sid of [r.from_step_id, r.to_step_id]) {
      const step = info.wf.steps.find(s => s.step_id === sid);
      for (const role of ['action', 'rationale', 'outcome', 'acceptance_criteria'])
        for (const cid of step.fields[role].claim_ids) path.add(info.id(cid));
      for (const q of info.wf.questions.filter(q => q.step_id === sid && q.status === 'open')) path.add(info.id(q.question_id));
    }
    for (const id of [...path]) {
      const n = graph.byId.get(id);
      if (n?.kind === 'claim') for (const link of n.data.evidence_links) path.add(info.id(link.evidence_id));
    }
    for (const id of [...path]) {
      const n = graph.byId.get(id);
      if (n?.kind === 'evidence') path.add(`${graph.root}:source:${n.data.source_id}`);
    }
    const conditions = r.condition_claim_ids.map(cid => graph.byId.get(info.id(cid))).filter(Boolean);
    return {node, info, path, conditions, from: graph.byId.get(info.id(r.from_step_id)), to: graph.byId.get(info.id(r.to_step_id)),
      label: conditions.map(n => n.title).join(' · ') || `${RELATIONS[r.relation_type]} · ${node.title}`};
  });
}

// Identity is explicit corpus/workflow/entity ID. No text similarity or guessed
// matching; changes include review flags, scope and evidence links.
export const identity = n => n.ref ? `${n.ref.workflow_id}:${n.kind}:${n.data[`${n.kind}_id`] || n.ref.workflow_id}` : n.id;
const canonical = value => JSON.stringify(normalize(value));
function normalize(value) {
  if (Array.isArray(value)) return value.map(normalize);
  if (value && typeof value === 'object') return Object.fromEntries(Object.keys(value).sort().map(k => [k, normalize(value[k])]));
  return value;
}
function payload(n) {
  if (n.kind !== 'workflow') return n.data;
  const {revision, created_at, supersedes_revision, claims, evidence, steps, questions, relations, change_log, review_events, ...metadata} = n.data;
  return metadata;
}
export function changedFields(before, after) {
  const a = payload(before) || {}, b = payload(after) || {};
  return [...new Set([...Object.keys(a), ...Object.keys(b)])].filter(k => canonical(a[k]) !== canonical(b[k]));
}
function indexGraph(graph) {
  graph.byId = new Map(graph.nodes.map(n => [n.id, n]));
  graph.adjacency = new Map(graph.nodes.map(n => [n.id, new Set()]));
  for (const e of graph.edges) { graph.adjacency.get(e.from).add(e.to); graph.adjacency.get(e.to).add(e.from); }
  graph.counts = Object.fromEntries(Object.keys(graph.counts).map(k => [k, graph.nodes.filter(n => n.kind === k).length]));
  return graph;
}
export function compareSnapshots(mode, beforeSnapshot, afterSnapshot) {
  if (beforeSnapshot.workflow.workflow_id !== afterSnapshot.workflow.workflow_id ||
      beforeSnapshot.workflow.revision >= afterSnapshot.workflow.revision)
    throw new Error('Cần hai phiên bản tăng dần của cùng một quy trình.');
  const before = buildGraph(mode, [beforeSnapshot], {includeClosedQuestions: true}), after = buildGraph(mode, [afterSnapshot], {includeClosedQuestions: true});
  const old = new Map(before.nodes.map(n => [identity(n), n])), next = new Map(after.nodes.map(n => [identity(n), n]));
  const aliases = new Map(), counts = {added: 0, changed: 0, removed: 0, unchanged: 0};
  for (const n of after.nodes) {
    const prior = old.get(identity(n));
    if (prior) { n.position = [...prior.position]; aliases.set(prior.id, n.id); }
    n.beforeNode = prior; n.afterNode = {...n}; n.fields = prior ? changedFields(prior, n) : [];
    n.change = prior ? n.fields.length ? 'changed' : 'unchanged' : 'added'; counts[n.change]++;
  }
  const removed = before.nodes.filter(n => !next.has(identity(n))).map(n => {
    counts.removed++; return {...n, beforeNode: n, change: 'removed', fields: []};
  });
  const key = (g, e) => `${identity(g.byId.get(e.from))}|${e.kind}|${identity(g.byId.get(e.to))}`;
  const oldEdges = new Map(before.edges.map(e => [key(before, e), e])), newEdges = new Map(after.edges.map(e => [key(after, e), e]));
  const edgeCounts = {added: 0, changed: 0, removed: 0, unchanged: 0};
  const edges = after.edges.map(e => {
    const prior = oldEdges.get(key(after, e));
    const change = prior ? canonical(prior.data) === canonical(e.data) ? 'unchanged' : 'changed' : 'added';
    edgeCounts[change]++; return {...e, change};
  });
  for (const [id, e] of oldEdges) if (!newEdges.has(id)) {
    edgeCounts.removed++; edges.push({...e, from: aliases.get(e.from) || e.from, to: aliases.get(e.to) || e.to, change: 'removed'});
  }
  const union = indexGraph({...after, nodes: [...after.nodes, ...removed], edges,
    workflows: new Map([...before.workflows, ...after.workflows]), aliases});
  // Both end states use the same coordinates for surviving IDs.
  return {before, after: indexGraph(after), union, counts, edgeCounts, beforeSnapshot, afterSnapshot};
}
