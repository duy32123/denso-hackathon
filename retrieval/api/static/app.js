/* No HTML rendering of model/source/user text. Corpus and build stay attached to citations. */
const el = id => document.getElementById(id);
let generation = 0;
let evidenceGeneration = 0;
const node = (tag, text) => { const n = document.createElement(tag); n.textContent = text; return n; };
function clearResult() {
  generation++; evidenceGeneration++;
  for (const id of ['answer', 'missing', 'unresolved', 'build', 'citations', 'evidence', 'status']) el(id).replaceChildren();
  delete el('status').dataset.state;
  el('evidence').textContent = 'Chọn một claim/citation để đọc bằng chứng. Citation đầu tiên của câu trả lời sẽ tự mở.';
  window.workflowViewer?.clear();
}
el('mode').addEventListener('change', () => {
  clearResult();
  const synthetic = el('mode').value === 'synthetic';
  el('banner').textContent = synthetic ? 'DỮ LIỆU MÔ PHỎNG — chỉ kiểm thử phần mềm; không dùng thao tác trên máy.' : '';
  for (const id of ['manufacturer', 'subsystem', 'machine_model']) el(id).value = '';
  el('demo-question').disabled = synthetic;
  el('question').value = synthetic ? '' : 'How is the pocket slider lubricated?';
  window.workflowViewer?.loadCatalog();
});
el('demo-question').addEventListener('change', () => {
  const choice = el('demo-question').value;
  el('question').value = {grease: 'How is the pocket slider lubricated?',
    grade: 'What grease type and NLGI grade are specified for the pocket slider?',
    model: 'Can this pocket replacement procedure be used on a VF-2?'}[choice];
  el('manufacturer').value = 'Haas'; el('subsystem').value = 'SMTC';
  el('machine_model').value = choice === 'model' ? 'VF-2' : '';
  clearResult();
});
async function openEvidence(url, token, origin = 'citation') {
  const current = ++evidenceGeneration;
  el('evidence').textContent = 'Đang mở bằng chứng…';
  try {
    const response = await fetch(url);
    const data = await response.json();
    if (token !== generation || current !== evidenceGeneration) return;
    if (!response.ok) throw new Error(data.error?.message || 'Không mở được bằng chứng.');
    const box = el('evidence'); box.replaceChildren();
    box.append(node('p', origin === 'workflow' ? 'Đang xem nguồn của claim được chọn trong workflow; có thể khác citation của câu trả lời.' : 'Đang xem nguồn của citation trong câu trả lời.'));
    box.append(node('h3', `${data.workflow.title} · r${data.workflow.revision}`));
    box.append(node('p', `${data.source.title} · ${data.evidence.evidence_id}`));
    box.append(node('p', `Kiểu bằng chứng: ${data.access_kind}${data.available ? '' : ' — không mở được'}`));
    if (data.mode === 'synthetic') box.append(node('p', 'Dữ liệu mô phỏng. Không có video thật.'));
    const loc = data.evidence.locator;
    if (loc.start_ms !== null) box.append(node('p', `Đoạn nguồn: ${loc.start_ms / 1000}–${loc.end_ms / 1000} giây`));
    box.append(node('blockquote', data.text || data.evidence.quote || data.evidence.observation_note || 'Không có đoạn văn đã lưu.'));
    for (const claim of data.claims) {
      box.append(node('p', `${claim.claim_id}: ${claim.text}\n${claim.source_review} / ${claim.technical_review}`));
      if (claim.attribution) box.append(node('p', `Attribution: ${claim.attribution.label} (${claim.attribution.kind})`));
      if (claim.scope) box.append(node('p', `Scope: ${claim.scope.description || 'Không nêu'} (${claim.scope.level})`));
      if (claim.conflicts_with?.length) box.append(node('p', `Conflict chưa giải quyết: ${claim.conflicts_with.join(', ')}`));
    }
    box.append(node('small', `Index của bằng chứng: ${data.index_build_id}`));
    if (data.asset_available) {
      const image = document.createElement('img');
      const asset = new URL(url, window.location.origin); asset.pathname += '/asset';
      image.src = asset.href; image.alt = data.evidence.observation_note || 'Keyframe từ nguồn'; box.append(image);
    }
    if (data.source.url) {
      const link = node('a', 'Mở trang nguồn (chưa kiểm khả năng phát video)');
      link.href = data.source.url; link.target = '_blank'; link.rel = 'noopener noreferrer'; box.append(link);
    }
  } catch (error) {
    if (token === generation && current === evidenceGeneration) el('evidence').textContent = error.message;
  }
}
el('ask').addEventListener('submit', async event => {
  event.preventDefault(); clearResult();
  const token = generation;
  const mode = el('mode').value;
  const context = {};
  for (const id of ['manufacturer', 'subsystem', 'machine_model']) if (el(id).value.trim()) context[id] = el(id).value.trim();
  el('submit').disabled = true; el('status').textContent = 'Đang tìm nguồn và kiểm câu trả lời…';
  try {
    const response = await fetch('/v1/ask', {method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({question: el('question').value, context, mode, dataset_split: 'dev'})});
    const data = await response.json();
    if (token !== generation) return;
    if (!response.ok) throw new Error(data.error?.message || 'Không xử lý được câu hỏi.');
    el('status').textContent = data.status; el('status').dataset.state = data.status; el('answer').textContent = data.answer;
    el('build').textContent = `Index: ${data.index_build_id}`;
    if (data.missing_context.length) el('missing').textContent = `Cần làm rõ: ${data.missing_context.join(', ')}`;
    if (data.unresolved_claim_refs.length) el('unresolved').textContent = `Claim chưa giải quyết: ${data.unresolved_claim_refs.map(r => `${r.workflow_id}@r${r.revision}/${r.entity_id}`).join(', ')}`;
    for (const citation of data.citations) for (const eid of citation.evidence_ids) {
      const ref = citation.claim_ref;
      const params = new URLSearchParams({mode, dataset_split: 'dev', index_build_id: data.index_build_id});
      const url = `/v1/evidence/${encodeURIComponent(ref.workflow_id)}/${ref.revision}/${encodeURIComponent(eid)}?${params}`;
      const button = node('button', `${citation.answer_span}\n${ref.entity_id} · r${ref.revision} · ${citation.source_review} / ${citation.technical_review}`);
      button.type = 'button';
      button.addEventListener('click', () => {
        openEvidence(url, token);
        window.workflowViewer?.show(ref, mode, data.index_build_id, {focusClaim: ref.entity_id});
      });
      el('citations').append(button);
    }
    const firstCitation = el('citations').querySelector('button');
    if (firstCitation) firstCitation.click();
    else el('evidence').textContent = 'Câu trả lời này không có citation. Có thể chọn quy trình ở thanh trên để xem dữ liệu và phần còn thiếu.';
  } catch (error) { if (token === generation) el('status').textContent = error.message; }
  finally { el('submit').disabled = false; }
});
