// Map public telemetry to existing graph IDs. No inferred edges or model thoughts.
export const STAGES = {
  started: ['Neo vào kho tri thức', 'Chạy bộ truy xuất trên index của đồ thị đang mở.'],
  context: ['Kiểm tra ngữ cảnh', 'Kiểm tra nhà sản xuất, phân hệ và các điều kiện nhận diện quy trình.'],
  relevance: ['Kiểm tra độ liên quan', 'Kiểm tra câu hỏi có căn cứ trong kho trước khi chọn nội dung.'],
  ranked: ['Chọn quy trình', 'Xếp hạng kết quả thật. Điểm tìm kiếm không phải xác suất đúng kỹ thuật.'],
  matched: ['Tìm bước và phát biểu', 'Lấy các bước khớp trực tiếp và phát biểu đủ điều kiện review.'],
  expanded: ['Theo quan hệ của bước', 'Mở rộng tới tiên quyết, điều kiện nhánh hoặc đính chính đã lưu.'],
  retrieval_complete: ['Ghi nhận kết quả và phần thiếu', 'Giữ câu hỏi mở và mâu thuẫn; phần thiếu chưa trở thành câu trả lời.'],
  evidence: ['Kiểm tra bằng chứng', 'Đối chiếu snapshot và kiểm tra mở được bằng chứng của từng phát biểu.'],
  drafting: ['AI soạn câu trả lời', 'Model nhận các ứng viên đã kiểm; chưa có câu trả lời được chấp nhận.'],
  verifying: ['Kiểm tra câu trả lời', 'Kiểm tra trích dẫn, phiên bản, căn cứ và mức hỗ trợ của từng phát biểu.'],
  citations: ['Giữ trích dẫn đã qua kiểm tra', 'Chỉ làm sáng phần được câu trả lời cuối cùng trích dẫn.'],
  done: ['Hoàn tất lượt truy xuất', 'Đọc kết quả và mở nguồn; có thể phát lại hoặc xem từng chặng.']
};
export const edgeKey = e => `${e.from}|${e.kind}|${e.to}`;
export function nodeId(graph, ref) {
  if (ref.kind === 'source') return `${graph.root}:source:${ref.entity_id}`;
  const prefix = `${graph.root}:${ref.workflow_id}@${ref.revision}`;
  return ref.kind === 'workflow' ? prefix : `${prefix}:${ref.entity_id}`;
}
export function resolveFrame(graph, event, visited = new Set()) {
  const active = new Set(), states = new Map(), hops = [];
  if (event.stage === 'started') { active.add(graph.root); states.set(graph.root, 'selected'); }
  for (const ref of event.refs || []) {
    const id = nodeId(graph, ref);
    if (!graph.byId.has(id)) continue;
    active.add(id); states.set(id, ref.state);
    if (ref.traversal_from && ref.traversal_to) {
      const prefix = `${graph.root}:${ref.workflow_id}@${ref.revision}`;
      for (const [from, to] of [[`${prefix}:${ref.traversal_from}`, id], [id, `${prefix}:${ref.traversal_to}`]])
        if (graph.edges.some(e => (e.from === from && e.to === to) || (e.from === to && e.to === from))) hops.push({from, to});
    }
  }
  const all = new Set([...visited, ...active]), edges = new Set();
  for (const e of graph.edges) if (all.has(e.from) && all.has(e.to) && (active.has(e.from) || active.has(e.to))) {
    edges.add(edgeKey(e));
    if (!hops.length && ['contains_workflow', 'contains_step', 'supported_by', 'from_source'].includes(e.kind)) hops.push({from: e.from, to: e.to});
  }
  const primary = [...active].find(id => graph.byId.get(id).kind === 'relation') ||
    [...active].find(id => graph.byId.get(id).kind === 'step') ||
    [...active].find(id => states.get(id) === 'selected') || [...active][0] || graph.root;
  return {event, active, visited: all, states, edges, hops, primary};
}

const $ = id => document.getElementById(id);
const text = (tag, value, className) => { const n = document.createElement(tag); n.textContent = value; if (className) n.className = className; return n; };
export function createRoute({getGraph, getCatalog, onFrame, onClear, reducedMotion}) {
  let events = [], cursor = -1, token = 0, controller = null, timer = 0, playing = false, pending = false, lastSequence = 0;
  function controls() {
    $('route-play').disabled = !events.length; $('route-play').textContent = playing ? 'Tạm dừng' : 'Tiếp tục'; $('route-play').setAttribute('aria-pressed', String(playing));
    $('route-prev').disabled = cursor <= 0; $('route-next').disabled = cursor >= events.length - 1;
    $('route-replay').disabled = !events.length; $('route-stop').disabled = !pending && !playing;
    $('route-run').disabled = pending; $('route-question').disabled = pending;
    $('route-top-k').disabled = pending; $('route-generate').disabled = pending;
    $('route-position').textContent = events.length ? `${Math.max(0, cursor + 1)} / ${events.length} chặng${pending ? ' · đang nhận trace' : ''}` : 'Chưa chạy truy xuất';
  }
  function pause() { playing = false; clearTimeout(timer); timer = 0; controls(); }
  function reset() {
    token++; controller?.abort(); controller = null; pause(); pending = false; events = []; cursor = -1; lastSequence = 0;
    $('route-timeline').replaceChildren(); $('route-message').textContent = ''; controls(); onClear();
  }
  function show(index) {
    if (!events.length) return;
    cursor = Math.max(0, Math.min(index, events.length - 1));
    if (events[cursor].type === 'result' && !pending) { playing = false; clearTimeout(timer); timer = 0; }
    let visited = new Set(), states = new Map(), edges = new Set(), frame, lastActive;
    for (const event of events.slice(0, cursor + 1)) {
      frame = resolveFrame(getGraph(), event, visited); visited = frame.visited;
      if (frame.active.size) lastActive = frame;
      for (const [id, state] of frame.states) states.set(id, state);
      for (const edge of frame.edges) edges.add(edge);
    }
    const completed = frame.event.data?.answer ? frame.event.data.answer.status === 'answered' : frame.event.data?.status === 'retrieved';
    if (frame.event.type === 'result' && completed && lastActive) frame = {...frame, active: lastActive.active, edges: lastActive.edges, primary: lastActive.primary, hops: []};
    onFrame({...frame, states, trailEdges: edges, playing, pending, position: cursor + 1, total: events.length});
    for (const b of $('route-timeline').querySelectorAll('button')) {
      b.classList.toggle('is-complete', +b.dataset.routeStage < cursor);
      b.setAttribute('aria-pressed', String(+b.dataset.routeStage === cursor));
    }
    const current = $('route-timeline').querySelector(`[data-route-stage="${cursor}"]`), timeline = $('route-timeline');
    if (current) timeline.scrollTo({left: timeline.scrollLeft + current.getBoundingClientRect().left - timeline.getBoundingClientRect().left - 8, behavior: 'instant'});
    controls();
  }
  function schedule() {
    clearTimeout(timer);
    if (!playing) return;
    timer = setTimeout(() => {
      timer = 0;
      if (cursor < events.length - 1) show(cursor + 1);
      else if (!pending) { pause(); if (cursor >= 0) show(cursor); return; }
      schedule();
    }, (reducedMotion.matches ? 1000 : 1300) / +$('route-speed').value);
  }
  function accept(event, generation, mode, build) {
    if (generation !== token) return;
    if (event.mode !== mode || event.dataset_split !== 'dev' || event.index_build_id !== build) throw new Error('Trace không thuộc kho và index đang mở. Tải lại đồ thị.');
    if (event.type === 'error') throw new Error(event.message || 'Chưa hoàn tất lượt truy xuất.');
    if (!['stage', 'result'].includes(event.type) || !STAGES[event.stage] || event.seq !== lastSequence + 1 || event.origin !== 'observed_pipeline') throw new Error('Trace không hợp lệ; đã dừng trình diễn.');
    lastSequence = event.seq; events.push(event);
    const b = text('button', `${events.length.toString().padStart(2, '0')} · ${STAGES[event.stage][0]}`); b.type = 'button'; b.dataset.routeStage = events.length - 1; b.setAttribute('aria-pressed', 'false');
    b.addEventListener('click', () => { pause(); show(+b.dataset.routeStage); }); $('route-timeline').append(b);
    if (cursor < 0) show(0); controls();
  }
  async function run() {
    const question = $('route-question').value.trim(); if (!question) { $('route-message').textContent = 'Nhập câu hỏi để bắt đầu.'; return; }
    reset(); const generation = token, graph = getGraph(), mode = graph.mode, build = getCatalog().index_build_id;
    controller = new AbortController(); pending = true; playing = true; controls();
    $('route-message').textContent = 'Đang chạy truy xuất thật. Nhịp làm sáng được giãn để trình chiếu.';
    onFrame({event: {stage: 'started', refs: [], data: {}}, ...resolveFrame(graph, {stage: 'started'}), playing: true, pending: true, trailEdges: new Set(), position: 0, total: 0});
    schedule();
    try {
      const response = await fetch('/v1/trace', {method: 'POST', headers: {'Content-Type': 'application/json'}, signal: controller.signal,
        body: JSON.stringify({query: {question, context: mode === 'real' ? {manufacturer: 'Haas', subsystem: 'SMTC'} : {}, mode, dataset_split: 'dev'},
          index_build_id: build, top_k: +$('route-top-k').value, generate_answer: $('route-generate').checked})});
      if (!response.ok) { const data = await response.json(); throw new Error(data.error?.message || 'Chưa mở được lượt truy xuất.'); }
      const reader = response.body.getReader(), decoder = new TextDecoder(); let buffered = '';
      while (true) {
        const {done, value} = await reader.read(); if (generation !== token) { await reader.cancel(); return; }
        buffered += decoder.decode(value, {stream: !done});
        let end;
        while ((end = buffered.indexOf('\n')) >= 0) {
          const line = buffered.slice(0, end).trim(); buffered = buffered.slice(end + 1);
          if (line) accept(JSON.parse(line), generation, mode, build);
        }
        if (done) break;
      }
      if (buffered.trim()) accept(JSON.parse(buffered), generation, mode, build);
      if (events.at(-1)?.type !== 'result') throw new Error('Luồng kết thúc trước khi có kết quả; hãy chạy lại.');
      pending = false; $('route-message').textContent = 'Đã nhận trace thực. Nhịp trình chiếu giãn các sự kiện để dễ quan sát; tạm dừng hoặc chọn từng chặng để mở nội dung và nguồn.'; controls();
    } catch (error) {
      if (generation !== token || error.name === 'AbortError') return;
      controller?.abort(); pending = false; pause(); $('route-message').textContent = error.message;
      if (cursor >= 0) show(cursor);
    }
  }
  $('route-form').addEventListener('submit', event => { event.preventDefault(); run(); });
  $('route-play').addEventListener('click', () => { if (playing) { pause(); show(cursor); } else { playing = true; controls(); schedule(); if (cursor >= 0) show(cursor); } });
  $('route-prev').addEventListener('click', () => { pause(); show(cursor - 1); });
  $('route-next').addEventListener('click', () => { pause(); show(cursor + 1); });
  $('route-replay').addEventListener('click', () => { pause(); playing = true; show(0); schedule(); });
  $('route-stop').addEventListener('click', () => { controller?.abort(); pending = false; pause(); $('route-message').textContent = 'Đã dừng lượt trình diễn. Các chặng đã nhận vẫn xem lại được.'; if (cursor >= 0) show(cursor); });
  $('route-speed').addEventListener('change', schedule);
  for (const b of document.querySelectorAll('[data-route-question]')) b.addEventListener('click', () => { reset(); $('route-question').value = b.dataset.routeQuestion; $('route-question').focus(); });
  controls();
  return {reset, pause, get events() { return events; }, get playing() { return playing; }, get pending() { return pending; }, get cursor() { return cursor; }};
}
