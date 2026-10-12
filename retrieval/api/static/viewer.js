/* Read-only WP4 browser. All source/model text is rendered with textContent. */
(() => {
  let catalogGeneration = 0, viewGeneration = 0, catalog = null;
  const entry = new URLSearchParams(location.search);
  let entryPending = entry.has('workflow');
  const areas = ['workflow-meta', 'workflow-steps', 'workflow-relations', 'workflow-questions'];
  const counts = value => Object.entries(value || {}).map(([key, count]) => `${key}: ${count}`).join(' · ') || '—';
  const text = value => value === null || value === undefined || value === '' ? 'Không nêu' :
    typeof value === 'object' ? JSON.stringify(value) : String(value);
  const details = (title, open = false) => {
    const section = document.createElement('details'); section.open = open;
    section.append(node('summary', title)); return section;
  };
  const button = (label, action) => {
    const result = node('button', label); result.type = 'button'; result.addEventListener('click', action); return result;
  };
  const params = (mode, build) => new URLSearchParams({mode, dataset_split: 'dev', index_build_id: build});
  const route = (ref, mode, build) => `/v1/workflows/${encodeURIComponent(ref.workflow_id)}/${ref.revision}?${params(mode, build)}`;
  async function get(url) {
    const response = await fetch(url, {cache: 'no-store'});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error?.message || 'Không đọc được dữ liệu.');
    return data;
  }
  function clear() {
    viewGeneration++;
    window.knowledgeMap.clear();
    for (const id of areas) el(id).replaceChildren();
    el('workflow-status').textContent = '';
    el('workflow-history').textContent = 'Chọn một workflow để xem lịch sử.';
    document.dispatchEvent(new CustomEvent('workflow-cleared'));
  }
  async function loadCatalog() {
    const token = ++catalogGeneration, mode = el('mode').value;
    catalog = null;
    el('workflow-select').replaceChildren(node('option', 'Chọn workflow…'));
    el('workflow-select').firstChild.value = '';
    el('catalog-status').textContent = 'Đang đọc index…';
    try {
      const data = await get(`/v1/workflows?${new URLSearchParams({mode, dataset_split: 'dev'})}`);
      if (token !== catalogGeneration || mode !== el('mode').value) return;
      catalog = data;
      data.workflows.forEach((wf, index) => {
        const option = node('option', `${wf.workflow_id} · r${wf.revision} · ${wf.title}`);
        option.value = String(index); el('workflow-select').append(option);
      });
      el('catalog-status').textContent = `${data.workflows.length} quy trình trong kho đang chọn. Bộ lọc thiết bị được áp dụng ở phần hỏi đáp.`;
      el('catalog-status').title = data.index_build_id;
      if (entryPending) {
        entryPending = false;
        const index = data.workflows.findIndex(wf => wf.workflow_id === entry.get('workflow') && String(wf.revision) === entry.get('revision'));
        if (index >= 0) {
          el('workflow-select').value = String(index);
          show(data.workflows[index], mode, data.index_build_id, {focusQuestion: entry.get('question')});
        } else el('catalog-status').textContent += ' Phiên bản trong liên kết chưa có ở index đang phục vụ.';
      }
    } catch (error) {
      if (token === catalogGeneration) el('catalog-status').textContent = error.message;
    }
  }
  function claimCard(claim, ref, mode, build, token) {
    const box = document.createElement('article'); box.className = 'claim'; box.dataset.claimId = claim.claim_id;
    box.append(node('strong', claim.claim_id), node('p', claim.text));
    box.append(node('p', `${claim.evidence_type} · ${claim.support_status} · ${claim.source_review} / ${claim.technical_review}`));
    box.append(node('p', `Attribution: ${claim.attribution.label} (${claim.attribution.kind})`));
    box.append(node('p', `Scope: ${claim.scope.description || 'Không nêu'} (${claim.scope.level})`));
    if (claim.conflicts_with.length) box.append(node('p', `Conflict chưa giải quyết: ${claim.conflicts_with.join(', ')}`));
    for (const link of claim.evidence_links) {
      const url = `/v1/evidence/${encodeURIComponent(ref.workflow_id)}/${ref.revision}/${encodeURIComponent(link.evidence_id)}?${params(mode, build)}`;
      const open = button(`${link.evidence_id} · ${link.support_status} · Mở nguồn`, () => {
        openEvidence(url, token, 'workflow');
        if (window.matchMedia('(max-width: 740px)').matches) el('evidence').scrollIntoView({behavior: 'smooth', block: 'start'});
      });
      open.title = link.explanation; box.append(open, node('p', link.explanation));
    }
    if (!claim.evidence_links.length) box.append(node('p', 'Không có evidence link.'));
    return box;
  }
  function renderWorkflow(data, mode, build, options) {
    const wf = data.workflow, token = generation;
    const meta = el('workflow-meta');
    meta.append(node('h3', `${wf.title} · ${wf.workflow_id} · r${wf.revision}`));
    meta.append(node('p', `${wf.lifecycle} · nguồn: ${counts(data.review_counts.source)} · kỹ thuật: ${counts(data.review_counts.technical)}`));
    meta.append(node('p', 'Đọc snapshot, không phải câu trả lời được phê duyệt. Claim pending/rejected/conflict vẫn hiển thị để kiểm; không được dùng như chỉ dẫn đã xác nhận.'));
    const context = document.createElement('dl'); context.className = 'metadata';
    for (const [key, value] of Object.entries(wf.context)) {
      if (key === 'metadata_provenance') continue;
      context.append(node('dt', key), node('dd', text(value)));
    }
    meta.append(context, node('small', `Index: ${build}`));
    for (const source of data.sources) meta.append(node('p', `${source.source_id}: ${source.title}\n${source.access_note || ''}`));
    const claims = new Map(wf.claims.map(claim => [claim.claim_id, claim]));
    window.knowledgeMap.render(data, {
      focusClaim: options.focusClaim,
      openEvidence: evidence => {
        const url = `/v1/evidence/${encodeURIComponent(wf.workflow_id)}/${wf.revision}/${encodeURIComponent(evidence.evidence_id)}?${params(mode, build)}`;
        openEvidence(url, token, 'workflow');
        el('evidence').scrollIntoView({behavior: 'smooth', block: 'start'});
      },
      openQuestion: question => document.dispatchEvent(new CustomEvent('knowledge-question-selected', {
        detail: {workflow_id: wf.workflow_id, revision: wf.revision, question_id: question.question_id}
      }))
    });
    wf.steps.forEach((step, index) => {
      const focused = Object.values(step.fields).some(field => field.claim_ids.includes(options.focusClaim));
      const card = details(`${step.display_order}. ${step.title} · ${step.step_id}`, focused || (!options.focusClaim && index === 0));
      for (const [role, field] of Object.entries(step.fields)) {
        const section = details(`${role} · ${field.state} · ${field.claim_ids.length} claim`, field.claim_ids.includes(options.focusClaim));
        section.className = `field state-${field.state}`;
        if (!field.claim_ids.length) section.append(node('p', 'Chưa có claim cho field này; không tự bổ sung bằng kiến thức nền.'));
        for (const cid of field.claim_ids) section.append(claimCard(claims.get(cid), wf, mode, build, token));
        card.append(section);
      }
      el('workflow-steps').append(card);
    });
    const relations = details(`Quan hệ giữa các Step · ${wf.relations.length}`);
    for (const relation of wf.relations) {
      relations.append(node('p', `${relation.from_step_id} — ${relation.relation_type} → ${relation.to_step_id}`));
      if (relation.condition_claim_ids.length) relations.append(node('p', `Điều kiện: ${relation.condition_claim_ids.join(', ')}`));
      for (const cid of relation.claim_ids) relations.append(claimCard(claims.get(cid), wf, mode, build, token));
    }
    if (!wf.relations.length) relations.append(node('p', 'Không có Relation records; thứ tự Step không tự chứng minh quan hệ phụ thuộc.'));
    el('workflow-relations').append(relations);
    const questions = details(`Câu hỏi bổ sung đã ghi trong snapshot · ${wf.questions.length}`, true);
    for (const q of wf.questions) {
      const item = document.createElement('article');
      item.append(node('strong', `${q.question_id} · ${q.status}`), node('p', q.question));
      item.append(node('p', `${q.step_id} / ${q.target_field} · ${q.reason}`));
      if (q.resolution_note) item.append(node('p', q.resolution_note));
      if (q.answer_source_ids.length) item.append(node('p', `Nguồn phản hồi: ${q.answer_source_ids.join(', ')}`));
      questions.append(item);
    }
    if (!wf.questions.length) questions.append(node('p', 'Chưa có Question records. Các field missing vẫn được giữ nguyên ở trên.'));
    el('workflow-questions').append(questions);
  }
  function renderHistory(data, mode) {
    const box = el('workflow-history'); box.replaceChildren();
    box.append(node('p', `${data.workflow_id} · lịch sử đến r${data.through_revision}. Xem bản cũ không đổi index phục vụ.`));
    for (const entry of [...data.revisions].reverse()) {
      const card = details(`r${entry.revision} · ${entry.lifecycle} · ${entry.created_at}`, entry.revision === data.through_revision);
      card.append(node('p', `Nguồn: ${counts(entry.review_counts.source)} · Kỹ thuật: ${counts(entry.review_counts.technical)}`));
      if (entry.index_build_id) card.append(button(`Xem r${entry.revision}`, () => {
        evidenceGeneration++;
        el('evidence').textContent = 'Đang xem revision khác. Chọn claim trong workflow để mở đúng nguồn của revision này.';
        show({workflow_id: data.workflow_id, revision: entry.revision}, mode, entry.index_build_id, {keepHistory: true});
      }));
      else card.append(node('p', 'Bản này chưa có index lịch sử; không tự dùng index mới để mở citation cũ.'));
      if (entry.diff) {
        const diff = entry.diff;
        card.append(node('p', `So với r${diff.from_revision}: claim thêm ${diff.claims.added.length}, bỏ ${diff.claims.removed.length}, đổi ${diff.claims.changed.length}.`));
        for (const change of diff.claims.changed) {
          const item = details(`${change.id} · thay đổi: ${change.fields.join(', ')}`, true);
          for (const field of change.fields) {
            item.append(node('p', `${field} — Trước: ${text(change.before[field])}`));
            item.append(node('p', `${field} — Sau: ${text(change.after[field])}`));
          }
          card.append(item);
        }
        for (const group of ['claims', 'steps', 'questions', 'relations', 'evidence']) {
          const change = diff[group];
          if (change.added.length) card.append(node('p', `${group} thêm: ${change.added.join(', ')}`));
          if (change.removed.length) card.append(node('p', `${group} bỏ: ${change.removed.join(', ')}`));
          if (group !== 'claims' && change.changed.length) card.append(node('p', `${group} đổi: ${change.changed.map(x => `${x.id} (${x.fields.join(', ')})`).join('; ')}`));
        }
        if (diff.context_changed) card.append(node('p', 'Context đã thay đổi; đối chiếu hai snapshot trước khi áp dụng.'));
      } else card.append(node('p', entry.previous_revision ? `Chưa có snapshot r${entry.previous_revision} để so sánh.` : 'Revision đầu tiên.'));
      if (entry.unresolved_conflicts.length) card.append(node('p', `Conflict chưa giải quyết: ${entry.unresolved_conflicts.join(', ')}`));
      const log = details('Change log và người kiểm');
      for (const event of entry.change_log) {
        // Contract muc 5.1: khong co dang nhap, nen actor_id luon la loi tu khai.
        log.append(node('p', `${event.actor_id} (tự khai, chưa xác thực) · ${event.changed_at}: ${event.reason}`));
        for (const mapping of event.id_mapping) log.append(node('p', `${mapping.old_id} → ${mapping.new_ids.join(', ') || '(không có ID thay thế)'}`));
      }
      for (const event of entry.review_events) log.append(node('p', `${event.target_id} · ${event.dimension}: ${event.decision} · ${event.reviewer_id} (${event.reviewer_role}) · ${event.reviewed_at}${event.note ? '\n' + event.note : ''}`));
      card.append(log); box.append(card);
    }
  }
  async function show(ref, mode, build, options = {}) {
    if (mode !== el('mode').value) return;
    const token = ++viewGeneration, queryToken = generation;
    window.knowledgeMap.clear();
    for (const id of areas) el(id).replaceChildren();
    el('workflow-status').textContent = `Đang đọc ${ref.workflow_id} r${ref.revision}…`;
    if (!options.keepHistory) el('workflow-history').textContent = 'Đang đọc lịch sử…';
    try {
      const data = await get(route(ref, mode, build));
      if (token !== viewGeneration || queryToken !== generation) return;
      renderWorkflow(data, mode, build, options);
      el('workflow-status').textContent = `Đang xem ${ref.workflow_id} r${ref.revision} · chỉ đọc`;
      // Man Bo sung doc tu day de khong giu mot ban sao trang thai thu hai.
      document.dispatchEvent(new CustomEvent('workflow-shown', {detail: {ref, mode, build, data}}));
      if (options.focusQuestion && data.workflow.questions.some(q => q.question_id === options.focusQuestion && q.status === 'open')) {
        document.dispatchEvent(new CustomEvent('knowledge-question-selected', {detail: {
          workflow_id: ref.workflow_id, revision: ref.revision, question_id: options.focusQuestion
        }}));
      }
      if (!options.keepHistory) {
        const path = `/v1/workflows/${encodeURIComponent(ref.workflow_id)}/${ref.revision}/history?${params(mode, build)}`;
        try {
          const history = await get(path);
          if (token === viewGeneration && queryToken === generation) renderHistory(history, mode);
        } catch (error) {
          if (token === viewGeneration && queryToken === generation) el('workflow-history').textContent = error.message;
        }
      }
    } catch (error) {
      if (token === viewGeneration && queryToken === generation) {
        el('workflow-status').textContent = error.message;
        if (!options.keepHistory) el('workflow-history').textContent = 'Chưa tải được lịch sử.';
      }
    }
  }
  el('refresh-workflows').addEventListener('click', loadCatalog);
  el('workflow-select').addEventListener('change', () => {
    const index = el('workflow-select').value;
    if (!catalog || index === '') return;
    evidenceGeneration++;
    el('evidence').textContent = 'Bấm “Mở bằng chứng” ở tab Bản đồ tri thức hoặc Chi tiết & nguồn để đọc đoạn gốc tại đây.';
    show(catalog.workflows[Number(index)], catalog.mode, catalog.index_build_id);
  });
  window.workflowViewer = {clear, loadCatalog, show};
  if (['real', 'synthetic'].includes(entry.get('mode')) && entry.get('mode') !== el('mode').value) {
    el('mode').value = entry.get('mode'); el('mode').dispatchEvent(new Event('change'));
  } else loadCatalog();
})();
