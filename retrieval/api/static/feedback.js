/* WP4 man Bo sung. Doi 1 (D1-B / WP6) so huu viec ghi; trang nay chi goi sang.
   Khong co duong nao o day ghi thang vao kho chuan, va khong co nut luu gia:
   nut Luu chi bat khi server tra ve mot service ghi THAT. */
(() => {
  const FIELDS = ['context', 'observation', 'action', 'rationale', 'condition', 'outcome', 'acceptance_criteria'];
  let current = null, feedbackGeneration = 0;

  const say = (id, message) => { el(id).textContent = message; };
  const option = (label, value) => { const o = node('option', label); o.value = value; return o; };

  function reset(message) {
    current = null; feedbackGeneration++;
    el('feedback-form').hidden = true;
    el('feedback-save').disabled = true;
    el('feedback-diff').replaceChildren();
    say('feedback-message', '');
    say('feedback-state', message);
  }

  function fill(detail) {
    current = detail; feedbackGeneration++;
    const workflow = detail.data.workflow;
    el('feedback-step').replaceChildren(
      ...workflow.steps.map(step => option(`${step.step_id} · ${step.title}`, step.step_id)));
    el('feedback-field').replaceChildren(...FIELDS.map(role => option(role, role)));
    const open = (workflow.questions || []).filter(q => q.status === 'open');
    el('feedback-question').replaceChildren(
      option('— không gắn câu hỏi nào —', ''),
      ...open.map(q => option(`${q.question_id} · ${q.target_field} · ${q.question}`, q.question_id)));
    el('feedback-form').hidden = false;
    el('feedback-save').disabled = true;
    el('feedback-diff').replaceChildren();
    say('feedback-message', '');
    say('feedback-state',
      `Bổ sung cho ${workflow.workflow_id} r${workflow.revision} · ${open.length} câu hỏi còn mở`);
  }

  function line(box, label, value) {
    const row = node('p', `${label}: ${value}`); box.append(row); return row;
  }

  function renderPreview(preview) {
    const box = el('feedback-diff');
    box.replaceChildren();
    box.append(node('h3', `Sẽ tạo revision r${preview.next_revision} từ r${preview.base_revision}`));

    for (const change of preview.field_changes) {
      line(box, `${change.step_id} · ${change.field}`,
        `${change.before.state} (${change.before.claim_ids.length} claim) → ${change.after.state} (${change.after.claim_ids.length} claim)`);
    }
    for (const claim of preview.new_claims) {
      const card = document.createElement('div');
      card.className = 'claim';
      card.append(node('p', claim.text));
      // Ghi ro de khong ai hieu nham rang co phan hoi la da duoc kiem.
      line(card, 'Trạng thái review', `nguồn: ${claim.source_review} · kỹ thuật: ${claim.technical_review}`);
      box.append(card);
    }
    for (const evidence of preview.new_evidence) {
      line(box, 'Bằng chứng mới', `${evidence.evidence_id} · ${evidence.modality} · nguyên văn giữ nguyên`);
    }
    if (preview.question_transition) {
      line(box, 'Câu hỏi', `${preview.question_transition.question_id}: ${preview.question_transition.from} → ${preview.question_transition.to} (chuyển sang resolved là bước riêng, cần người kiểm)`);
    }
    line(box, 'Nguồn mới', `${preview.source.source_id} · ${preview.source.source_kind}`);
    if (!preview.responder_authenticated) {
      line(box, 'Lưu ý', 'Danh tính người trả lời chưa được xác thực; sẽ ghi đúng như đã khai.');
    }
    for (const warning of preview.warnings || []) box.append(node('p', `Cảnh báo: ${warning}`));
  }

  function request() {
    const responder = {
      actor_id: el('feedback-actor').value.trim(),
      label: el('feedback-label').value.trim(),
      role: el('feedback-role').value.trim(),
    };
    return {
      mode: current.mode, dataset_split: 'dev',
      workflow_id: current.data.workflow.workflow_id,
      base_revision: current.data.workflow.revision,
      step_id: el('feedback-step').value,
      target_field: el('feedback-field').value,
      question_id: el('feedback-question').value || null,
      answer_text: el('feedback-text').value.trim(),
      responder,
      language: 'vi',
    };
  }

  async function call(path) {
    const token = feedbackGeneration;
    const response = await fetch(path, {
      method: 'POST', cache: 'no-store',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(request()),
    });
    const data = await response.json();
    if (token !== feedbackGeneration) return null;      // nguoi dung da doi workflow
    if (response.status === 409) {
      el('feedback-save').disabled = true;
      el('feedback-diff').replaceChildren();
      say('feedback-message',
        `Bản bạn đang xem là r${data.error.base_revision} nhưng kho đã có r${data.error.latest_revision}. ` +
        'Tải lại workflow rồi nhập lại; phản hồi này không được ghi đè lên bản mới.');
      return null;
    }
    if (!response.ok) {
      el('feedback-save').disabled = true;
      say('feedback-message', data.error?.message || 'Không gọi được service ghi.');
      return null;
    }
    return data;
  }

  async function preview() {
    if (!current) return;
    const body = request();
    if (!body.answer_text || !body.responder.actor_id || !body.responder.role) {
      say('feedback-message', 'Cần nguyên văn phản hồi, người trả lời và vai trò thật.');
      return;
    }
    say('feedback-message', 'Đang dựng bản xem trước…');
    try {
      const data = await call('/v1/feedback/preview');
      if (!data) return;
      renderPreview(data);
      if (data.simulated) {
        el('feedback-save').disabled = true;
        say('feedback-message',
          'Bản mô phỏng: service ghi của đội 1 chưa có nên không lưu được. ' +
          'Xem docs/team2_feedback_contract.md.');
      } else {
        el('feedback-save').disabled = false;
        say('feedback-message', 'Đọc kỹ bản xem trước rồi mới lưu.');
      }
    } catch (error) {
      say('feedback-message', error.message);
    }
  }

  async function save() {
    if (!current || el('feedback-save').disabled) return;
    say('feedback-message', 'Đang lưu…');
    try {
      const data = await call('/v1/feedback/submit');
      if (!data) return;
      say('feedback-message', `Đã tạo ${data.workflow_id} r${data.revision}. Tải lại danh sách để xem bản mới.`);
      el('feedback-save').disabled = true;
      window.workflowViewer?.loadCatalog();
    } catch (error) {
      say('feedback-message', error.message);
    }
  }

  el('feedback-question').addEventListener('change', () => {
    const id = el('feedback-question').value;
    if (!id || !current) return;
    const question = (current.data.workflow.questions || []).find(q => q.question_id === id);
    if (!question) return;
    el('feedback-step').value = question.step_id;
    el('feedback-field').value = question.target_field;
  });
  el('feedback-preview').addEventListener('click', preview);
  el('feedback-save').addEventListener('click', save);
  document.addEventListener('workflow-shown', event => fill(event.detail));
  document.addEventListener('workflow-cleared', () => reset('Chọn một workflow ở trên để bổ sung.'));
})();
