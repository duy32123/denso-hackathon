/* A2 knowledge map: a view of one immutable snapshot, built only from its records.
   Display order supplies node positions, never invented edges or prerequisites. */
(() => {
  const SVG = 'http://www.w3.org/2000/svg';
  const RELATIONS = {
    observed_next: ['Tiếp theo trong nguồn', 'Thể hiện thứ tự được nguồn ghi nhận; không tự suy ra điều kiện bắt buộc.'],
    requires: ['Điều kiện tiên quyết', 'Bước đích cần điều kiện hoặc kết quả của bước gốc, theo phát biểu được dẫn nguồn.'],
    branch_if: ['Nhánh có điều kiện', 'Chỉ chuyển sang bước đích khi điều kiện trên quan hệ được đáp ứng.'],
    repeated_step: ['Thao tác lặp lại', 'Mỗi lần thực hiện có bước và bằng chứng riêng.'],
    corrects: ['Đính chính', 'Bước đích sửa nội dung của bước gốc; giữ cả hai để đối chiếu.']
  };
  const STATES = {present: 'Có nội dung', missing: 'Chưa được ghi nhận', ambiguous: 'Cần làm rõ', not_applicable: 'Không áp dụng'};
  const SOURCE_REVIEW = {pending: 'Chờ đối chiếu nguồn', source_checked: 'Đã đối chiếu nguồn', rejected: 'Bị từ chối qua review'};
  const TECHNICAL_REVIEW = {not_requested: 'Chưa xác nhận chuyên môn', pending: 'Chờ xác nhận chuyên môn', expert_validated: 'Đã xác nhận chuyên môn trong phạm vi ghi nhận', rejected: 'Bị từ chối về kỹ thuật'};
  const ROLES = {context: 'Bối cảnh', observation: 'Dấu hiệu', action: 'Thao tác', rationale: 'Lý do', condition: 'Điều kiện', outcome: 'Kết quả ghi nhận', acceptance_criteria: 'Tiêu chí xác nhận'};
  const card = (tag, label, className) => {
    const result = node(tag, label); if (className) result.className = className; return result;
  };
  const button = (label, action, className = 'knowledge-button') => {
    const result = card('button', label, className); result.type = 'button';
    result.addEventListener('click', action); return result;
  };
  function svg(tag, attrs = {}, label) {
    const result = document.createElementNS(SVG, tag);
    for (const [key, value] of Object.entries(attrs)) result.setAttribute(key, String(value));
    if (label !== undefined) result.textContent = label;
    return result;
  }
  function activate(element, action) {
    element.addEventListener('click', action);
    element.addEventListener('keydown', event => {
      if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); action(); }
    });
  }
  function clear() {
    el('knowledge-map').replaceChildren(node('p', 'Chọn một quy trình để khám phá các bước, quan hệ và phần kiến thức còn thiếu.'));
    el('knowledge-detail').replaceChildren();
  }
  function titleLines(text) {
    const words = String(text).split(/\s+/), lines = [''];
    for (const word of words) {
      const last = lines.length - 1;
      if (lines[last] && (lines[last] + ' ' + word).length > 28) lines.push(word);
      else lines[last] += (lines[last] ? ' ' : '') + word;
    }
    return lines.slice(0, 2).map((line, index) => index === 1 && lines.length > 2 ? line + '…' : line);
  }
  function render(data, callbacks) {
    const wf = data.workflow, box = el('knowledge-map'), detail = el('knowledge-detail');
    box.replaceChildren(); detail.replaceChildren();
    const steps = [...wf.steps].sort((a, b) => a.display_order - b.display_order);
    const claims = new Map(wf.claims.map(c => [c.claim_id, c]));
    const evidence = new Map(wf.evidence.map(e => [e.evidence_id, e]));
    const stepById = new Map(steps.map(s => [s.step_id, s]));
    const gaps = steps.reduce((sum, step) => sum + Object.values(step.fields).filter(f => ['missing', 'ambiguous'].includes(f.state)).length, 0);
    const openQuestions = wf.questions.filter(q => q.status === 'open');
    box.append(card('h3', wf.title));
    box.append(card('p', `${steps.length} bước · ${wf.relations.length} quan hệ đã ghi nhận · ${gaps} trường còn thiếu / cần làm rõ · ${openQuestions.length} câu hỏi mở`, 'knowledge-stats'));
    const context = wf.context;
    box.append(card('p', `${context.manufacturer || 'Chưa rõ nhà sản xuất'} · ${context.subsystem || 'Chưa rõ phân hệ'} · Model: ${context.machine_model || 'chưa xác định'} · r${wf.revision}`, 'muted'));
    box.append(card('p', 'Bấm một bước hoặc quan hệ để xem tri thức, bằng chứng và trạng thái review. Số bước là thứ tự hiển thị; mũi tên chỉ thể hiện Relation đã ghi trong snapshot.', 'muted'));
    if (!steps.length) { box.append(node('p', 'Snapshot chưa có bước để vẽ.')); return; }

    const positions = new Map(steps.map((step, index) => [step.step_id, {x: 120 + (index % 3) * 240, y: 54 + Math.floor(index / 3) * 134, row: Math.floor(index / 3)}]));
    const graph = svg('svg', {viewBox: `0 0 720 ${Math.ceil(steps.length / 3) * 134}`, role: 'group', 'aria-label': 'Các bước và quan hệ trong quy trình', class: 'knowledge-graph'});
    const defs = svg('defs');
    for (const type of Object.keys(RELATIONS)) {
      const marker = svg('marker', {id: `knowledge-arrow-${type}`, markerWidth: 10, markerHeight: 10, refX: 8, refY: 3, orient: 'auto', markerUnits: 'strokeWidth'});
      marker.append(svg('path', {d: 'M0,0 L0,6 L8,3 z', class: `arrow-${type}`})); defs.append(marker);
    }
    graph.append(defs);
    const relationElements = new Map(), stepElements = new Map();
    for (const relation of wf.relations) {
      const from = positions.get(relation.from_step_id), to = positions.get(relation.to_step_id);
      if (!from || !to) continue;
      const dx = to.x - from.x, dy = to.y - from.y, distance = Math.hypot(dx, dy) || 1;
      const x1 = from.x + dx / distance * 29, y1 = from.y + dy / distance * 29;
      const x2 = to.x - dx / distance * 32, y2 = to.y - dy / distance * 32;
      // Explicit self-relations remain visible as loops instead of a zero-length line.
      let path;
      if (dx === 0 && dy === 0) {
        path = `M${from.x - 18},${from.y - 20} C${from.x - 78},${from.y - 64} ${from.x + 78},${from.y - 64} ${from.x + 18},${from.y - 20}`;
      } else if (from.row === to.row && Math.abs(dx) === 240) {
        path = `M${x1},${y1} L${x2},${y2}`;
      } else if (from.row === to.row) {
        // Route over the row so an edge spanning several nodes does not cross their labels.
        path = `M${from.x + 29},${from.y} H${from.x + 105} V${from.y - 35} H${to.x - 105} V${to.y} H${to.x - 32}`;
      } else {
        const lane = from.row < to.row ? (from.row + 1) * 134 - 4 : from.row * 134 - 8;
        path = `M${from.x + 29},${from.y} H${from.x + 105} V${lane} H${to.x + 105} V${to.y} H${to.x + 32}`;
      }
      const element = svg('g', {class: `knowledge-edge edge-${relation.relation_type}`, 'data-relation-id': relation.relation_id});
      element.append(svg('title', {}, `${stepById.get(relation.from_step_id).title} → ${stepById.get(relation.to_step_id).title}: ${RELATIONS[relation.relation_type]?.[0] || relation.relation_type}`));
      element.append(svg('path', {d: path, 'marker-end': `url(#knowledge-arrow-${relation.relation_type})`}));
      graph.append(element); relationElements.set(relation.relation_id, element);
    }
    for (const step of steps) {
      const point = positions.get(step.step_id);
      const group = svg('g', {class: 'knowledge-node', tabindex: 0, role: 'button', 'aria-pressed': 'false', 'aria-label': `${step.display_order}. ${step.title}`, 'data-knowledge-step': step.step_id});
      group.append(svg('title', {}, `${step.step_id}: ${step.title}`));
      group.append(svg('circle', {cx: point.x, cy: point.y, r: 25}));
      group.append(svg('text', {x: point.x, y: point.y + 5, 'text-anchor': 'middle', class: 'knowledge-number'}, step.display_order));
      titleLines(step.title).forEach((line, index) => group.append(svg('text', {x: point.x, y: point.y + 44 + index * 17, 'text-anchor': 'middle', class: 'knowledge-node-title'}, line)));
      activate(group, () => selectStep(step.step_id));
      graph.append(group); stepElements.set(step.step_id, group);
    }
    const viewport = card('div', '', 'knowledge-viewport'); viewport.append(graph); box.append(viewport);
    const relationPicker = card('div', '', 'knowledge-relations');
    for (const relation of wf.relations) {
      const from = stepById.get(relation.from_step_id), to = stepById.get(relation.to_step_id);
      if (!from || !to) continue;
      const pick = button(`${from.display_order} → ${to.display_order} · ${RELATIONS[relation.relation_type]?.[0] || relation.relation_type}`,
        () => selectStep(relation.to_step_id, relation.relation_id));
      pick.dataset.knowledgeRelation = relation.relation_id; relationPicker.append(pick);
    }
    box.append(relationPicker);
    if (!wf.relations.length) box.append(card('p', 'Nguồn này chưa có quan hệ được ghi nhận. Các bước được giữ riêng để kiểm tra và bổ sung.', 'muted'));

    function claimView(cid) {
      const claim = claims.get(cid); if (!claim) return node('p', 'Không tìm thấy phát biểu trong snapshot này.');
      const item = card('article', '', 'knowledge-claim'); item.dataset.knowledgeClaim = cid;
      item.append(node('p', claim.text));
      item.append(card('p', `${SOURCE_REVIEW[claim.source_review]} · ${TECHNICAL_REVIEW[claim.technical_review]}`, 'knowledge-review'));
      if (claim.support_status !== 'supported' || claim.evidence_type === 'inferred' || claim.conflicts_with.length) {
        item.append(card('p', `Cần kiểm tra: ${claim.evidence_type} · ${claim.support_status}${claim.conflicts_with.length ? ' · có mâu thuẫn' : ''}`, 'knowledge-warning'));
      }
      item.append(card('p', `${claim.attribution.label || 'Nguồn chưa nêu người phát biểu'} · ${claim.scope.description}`, 'muted'));
      for (const link of claim.evidence_links) {
        const ev = evidence.get(link.evidence_id); if (!ev) continue;
        const modality = {speech: 'Lời nói', visual: 'Hình ảnh', text: 'Văn bản'}[ev.modality];
        const time = ev.locator.start_ms === null ? '' : ` · ${Math.floor(ev.locator.start_ms / 1000)}–${Math.ceil(ev.locator.end_ms / 1000)} giây`;
        const open = button(`${modality}${time} · Mở bằng chứng`, () => callbacks.openEvidence(ev));
        open.title = `${ev.source_id} · ${link.explanation}`; item.append(open);
      }
      if (!claim.evidence_links.length) item.append(card('p', 'Phát biểu chưa có bằng chứng liên kết.', 'knowledge-warning'));
      return item;
    }
    function fieldView(step, role) {
      const field = step.fields[role], group = card('div', '', `knowledge-field knowledge-state-${field.state}`);
      group.append(node('h4', ROLES[role]), card('p', STATES[field.state], 'knowledge-field-state'));
      for (const cid of field.claim_ids) group.append(claimView(cid));
      if (!field.claim_ids.length) group.append(node('p', 'Nguồn chưa cung cấp nội dung cho phần này.'));
      return group;
    }
    function selectStep(id, selectedRelation = null) {
      const step = stepById.get(id); if (!step) return;
      for (const [sid, group] of stepElements) {
        group.classList.toggle('selected', sid === id); group.setAttribute('aria-pressed', String(sid === id));
      }
      for (const [rid, group] of relationElements) group.classList.toggle('selected', rid === selectedRelation);
      detail.replaceChildren();
      detail.append(node('h3', `${step.display_order}. ${step.title}`));
      const lenses = card('div', '', 'knowledge-lenses');
      for (const [label, roles] of [
        ['Làm gì?', ['action', 'observation']], ['Khi nào?', ['context', 'condition']],
        ['Vì sao?', ['rationale']], ['Kiểm chứng bằng gì?', ['acceptance_criteria', 'outcome']]
      ]) {
        const lens = card('article', '', 'knowledge-lens'); lens.append(node('h3', label));
        for (const role of roles) lens.append(fieldView(step, role));
        lenses.append(lens);
      }
      const connected = wf.relations.filter(r => r.from_step_id === id || r.to_step_id === id);
      const otherRelations = [];
      for (const relation of connected) {
        const block = card('details', '', 'knowledge-relation-detail'); block.open = relation.relation_id === selectedRelation;
        block.dataset.knowledgeRelationDetail = relation.relation_id;
        const from = stepById.get(relation.from_step_id), to = stepById.get(relation.to_step_id);
        block.append(node('summary', `${from.display_order} → ${to.display_order} · ${RELATIONS[relation.relation_type][0]}`));
        block.append(node('p', `${from.title} → ${to.title}`), node('p', RELATIONS[relation.relation_type][1]));
        for (const cid of relation.condition_claim_ids) {
          block.append(node('h4', 'Điều kiện chuyển bước'), claimView(cid));
        }
        for (const cid of relation.claim_ids) { block.append(node('h4', 'Căn cứ của quan hệ'), claimView(cid)); }
        if (relation.relation_id === selectedRelation) detail.append(block);
        else otherRelations.push(block);
      }
      detail.append(lenses, ...otherRelations);
      const questions = openQuestions.filter(q => q.step_id === id);
      const gapBox = card('div', '', 'knowledge-gaps');
      gapBox.append(node('h3', `Câu hỏi để thu thập kinh nghiệm · ${questions.length}`));
      for (const question of questions) {
        const item = card('article', '', 'knowledge-gap'); item.dataset.knowledgeQuestion = question.question_id;
        item.append(node('p', question.question), card('p', `${ROLES[question.target_field]} · ${question.reason}`, 'muted'));
        item.append(button('Bổ sung cho câu hỏi này', () => callbacks.openQuestion(question)));
        gapBox.append(item);
      }
      if (!questions.length) gapBox.append(node('p', 'Chưa có câu hỏi mở được ghi cho bước này. Các trường còn thiếu vẫn được giữ ở trên.'));
      detail.append(gapBox);
    }
    const focused = steps.find(step => Object.values(step.fields).some(field => field.claim_ids.includes(callbacks.focusClaim)));
    const focusedRelation = wf.relations.find(r => r.claim_ids.includes(callbacks.focusClaim) || r.condition_claim_ids.includes(callbacks.focusClaim));
    selectStep(focused?.step_id || focusedRelation?.to_step_id || steps[0].step_id, focusedRelation?.relation_id);
  }
  window.knowledgeMap = {render, clear};
})();
