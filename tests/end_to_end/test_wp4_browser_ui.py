"""Opt-in WP4 Windows Edge UI smoke, localhost only, isolated profile and fake LLM.

No user browser profile, no Gemini calls. KNOWFLOW_BROWSER_TEST=1 enables this
when Edge and the optional websockets package are installed.
"""

import base64
import json
import os
import socket
import subprocess
import threading
import time
from pathlib import Path
from urllib.request import ProxyHandler, build_opener

import pytest

from conftest import FIXTURE_ROOT, REPO_ROOT, read_bundle, write_bundle
from retrieval.api.app import create_app
from retrieval.generation.models import AnswerDraft, Verification
from retrieval.generation.browse import WorkflowBrowser
from retrieval.generation.feedback import StubFeedbackService
from retrieval.generation.service import QAService
from retrieval.importer import import_bundle
from retrieval.indexing.search_index import build_index
from retrieval.retrieval.engine import RetrievalConfig


class Model:
    def draft(self, payload):
        item = next((item for item in payload["candidates"] if "grease" in item["claim"]["text"].lower()),
                    payload["candidates"][0])
        return AnswerDraft(status="answered", statements=[{
            "text": item["claim"]["text"], "claim_ref": item["claim_ref"],
            "evidence_ids": [item["evidence"][0]["evidence"]["evidence_id"]]}])

    def verify(self, payload):
        return Verification(answers_question=True, supported=[True] * len(payload["statements"]))

    def close(self):
        pass


class Page:
    def __init__(self, ws):
        self.ws, self.counter, self.errors, self.requests = ws, 0, [], []

    def call(self, method, params=None):
        self.counter += 1
        self.ws.send(json.dumps({"id": self.counter, "method": method, "params": params or {}}))
        while True:
            result = json.loads(self.ws.recv(timeout=15))
            if result.get("method") == "Runtime.exceptionThrown":
                self.errors.append(result["params"])
            if result.get("method") == "Network.requestWillBeSent":
                self.requests.append(result["params"]["request"]["url"])
            if result.get("id") == self.counter:
                assert "error" not in result, result
                return result.get("result", {})

    def evaluate(self, expression):
        result = self.call("Runtime.evaluate", {"expression": expression, "returnByValue": True, "awaitPromise": True})
        assert "exceptionDetails" not in result, result
        return result["result"].get("value")

    def wait(self, expression, timeout=20):
        until = time.monotonic() + timeout
        while time.monotonic() < until:
            if self.evaluate(expression):
                return
            time.sleep(.1)
        pytest.fail(f"UI wait timed out: {expression}; body={self.evaluate('document.body.innerText')}")


@pytest.mark.skipif(os.getenv("KNOWFLOW_BROWSER_TEST") != "1", reason="Opt-in isolated Edge UI smoke")
def test_english_demo_auto_evidence_fields_revision_history_and_mode_switch(tmp_path):
    if os.name != "nt":
        pytest.skip("This optional smoke uses Windows Edge")
    connect = pytest.importorskip("websockets.sync.client").connect
    import uvicorn

    edge = Path("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe")
    if not edge.is_file():
        pytest.skip("Microsoft Edge is not installed at the standard path")
    real = tmp_path / "real.sqlite"
    bundle = REPO_ROOT / "acquisition/export/haas_pilot_dev_bundle"
    data = read_bundle(bundle)
    old = {**data, "workflows": [wf for wf in data["workflows"]
                               if wf["workflow_id"] == "B0_SRC_HAAS_0005" and wf["revision"] == 1]}
    assert old["workflows"]
    import_bundle(write_bundle(tmp_path / "r1", old), real, source_type="real", split="dev")
    build_index(real, mode="real", split="dev")
    import_bundle(bundle, real, source_type="real", split="dev")
    build_index(real, mode="real", split="dev")
    synthetic = tmp_path / "synthetic.sqlite"
    import_bundle(FIXTURE_ROOT / "F01_complete", synthetic, source_type="synthetic", split="dev")
    build_index(synthetic, mode="synthetic", split="dev")
    service = QAService({("real", "dev"): real, ("synthetic", "dev"): synthetic}, repo_root=REPO_ROOT,
                        config=RetrievalConfig(strategy="lexical"), model_factory=Model)
    # Ban gia lap: du de dung man Bo sung, va `submit` van bao 503 nhu that.
    service.feedback = StubFeedbackService(WorkflowBrowser(service.database))
    sock = socket.socket(); sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(create_app(service), log_level="error"))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()
    proc = ws = None
    try:
        deadline = time.monotonic() + 10
        while not server.started and time.monotonic() < deadline:
            time.sleep(.05)
        assert server.started
        profile = tmp_path / "edge-profile"
        proc = subprocess.Popen([str(edge), "--headless=new", "--use-gl=angle", "--use-angle=swiftshader",
                                 "--enable-unsafe-swiftshader", "--no-first-run",
                                 "--no-default-browser-check", "--disable-extensions", "--disable-sync",
                                 "--disable-background-networking", "--disable-component-update",
                                 "--remote-debugging-port=0", "--remote-debugging-address=127.0.0.1",
                                 "--window-size=1440,1100", f"--user-data-dir={profile}",
                                 f"http://127.0.0.1:{port}"], stdin=subprocess.DEVNULL,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                creationflags=subprocess.CREATE_NO_WINDOW)
        active = profile / "DevToolsActivePort"
        deadline = time.monotonic() + 20
        while not active.is_file() and time.monotonic() < deadline:
            time.sleep(.1)
        assert active.is_file(), "Edge did not start its isolated debugging endpoint"
        debug_port = int(active.read_text().splitlines()[0])
        opener = build_opener(ProxyHandler({}))
        with opener.open(f"http://127.0.0.1:{debug_port}/json/list", timeout=10) as response:
            targets = json.load(response)
        target = next(item for item in targets if item["type"] == "page" and f":{port}" in item["url"])
        ws = connect(target["webSocketDebuggerUrl"], proxy=None, max_size=20_000_000)
        page = Page(ws); page.call("Runtime.enable"); page.call("Page.enable")
        page.wait("document.querySelector('#workflow-select')?.options.length > 1")
        assert page.evaluate("document.querySelector('#question').value") == "How is the pocket slider lubricated?"
        page.evaluate("document.querySelector('#ask').requestSubmit()")
        page.wait("document.querySelector('#status').textContent === 'answered' && document.querySelector('#evidence blockquote') !== null")
        assert page.evaluate("document.querySelectorAll('#citations button').length") > 0
        page.evaluate("const picker = document.querySelector('#workflow-select'); picker.value = [...picker.options].find(x => x.textContent.startsWith('B0_SRC_HAAS_0005')).value; picker.dispatchEvent(new Event('change'))")
        page.wait("document.querySelector('#workflow-status').textContent.includes('B0_SRC_HAAS_0005 r2 ·') && document.querySelector('#workflow-history').textContent.includes('EV_033')")
        # A2 map: layout order is not silently converted to dependency edges.
        assert page.evaluate("document.querySelectorAll('.knowledge-node').length") == 9
        assert page.evaluate("document.querySelectorAll('.knowledge-edge').length") == 0
        assert page.evaluate("[...document.querySelectorAll('.knowledge-lens > h3')].map(x => x.textContent)") == [
            "Làm gì?", "Khi nào?", "Vì sao?", "Kiểm chứng bằng gì?"]
        page.evaluate("document.querySelector('[data-knowledge-step=\"B0_SRC_HAAS_0005_ST_006\"]').dispatchEvent(new KeyboardEvent('keydown', {key:'Enter', bubbles:true}))")
        page.evaluate("document.querySelector('[data-knowledge-claim=\"B0_SRC_HAAS_0005_CL_020\"] button').click()")
        page.wait("document.querySelector('#evidence').textContent.includes('B0_SRC_HAAS_0005_EV_033')")
        # Contract muc 5.1: nguoi ghi revision la loi tu khai, lich su khong duoc trinh bay nhu da xac thuc.
        assert "codex (tự khai, chưa xác thực)" in page.evaluate("document.querySelector('#workflow-history').textContent")
        page.evaluate("document.querySelector('[data-claim-id=\"B0_SRC_HAAS_0005_CL_020\"] button').click()")
        page.wait("document.querySelector('#evidence').textContent.includes('B0_SRC_HAAS_0005_EV_033')")
        assert "apply some grease" in page.evaluate("document.querySelector('#evidence blockquote').textContent")
        assert "Attribution:" in page.evaluate("document.querySelector('#evidence').textContent")
        assert "Scope:" in page.evaluate("document.querySelector('#evidence').textContent")
        assert page.evaluate("document.querySelectorAll('.state-missing').length") > 0
        # Man Bo sung ngay duoi da hien trang thai ghi that; panel cau hoi khong
        # duoc lap lai thong bao "chua bat" cu, sai voi RealFeedbackService mac dinh.
        assert "Chưa bật gửi feedback" not in page.evaluate("document.querySelector('#workflow-questions').textContent")
        page.evaluate("document.querySelector('[data-claim-id=\"B0_SRC_HAAS_0005_CL_020\"]').closest('details').open = true; document.querySelector('[data-claim-id=\"B0_SRC_HAAS_0005_CL_020\"]').closest('details').parentElement.open = true; document.querySelector('[data-claim-id=\"B0_SRC_HAAS_0005_CL_020\"]').scrollIntoView({block:'center'})")
        assert page.evaluate("document.querySelector('.evidence-panel').getBoundingClientRect().top >= 0 && document.querySelector('.evidence-panel').getBoundingClientRect().bottom <= innerHeight")
        page.evaluate("window.scrollTo(0, 0)")
        screenshot = tmp_path / "wp4-browser.png"
        screenshot.write_bytes(base64.b64decode(page.call("Page.captureScreenshot", {"captureBeyondViewport": True})["data"]))
        print(f"browser_screenshot={screenshot.as_posix()}")
        # Actual branch condition, original evidence and targeted question-to-feedback.
        page.evaluate("const recoveryPicker = document.querySelector('#workflow-select'); recoveryPicker.value = [...recoveryPicker.options].find(x => x.textContent.startsWith('REAL_WF_0003')).value; recoveryPicker.dispatchEvent(new Event('change'))")
        page.wait("document.querySelector('#workflow-status').textContent.includes('REAL_WF_0003 r2 ·')")
        assert page.evaluate("document.querySelectorAll('.knowledge-edge').length") == 1
        page.evaluate("document.querySelector('[data-knowledge-relation=\"REAL_WF_0003_RL_001\"]').click()")
        assert page.evaluate("document.querySelector('[data-knowledge-relation-detail=\"REAL_WF_0003_RL_001\"]').open")
        assert "Điều kiện chuyển bước" in page.evaluate("document.querySelector('#knowledge-detail').textContent")
        assert page.evaluate("document.querySelector('[data-knowledge-claim=\"REAL_WF_0003_CL_013\"] button') !== null")
        page.evaluate("document.querySelector('#knowledge-heading').scrollIntoView({block:'start'})")
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        map_screenshot = tmp_path / "a2-knowledge-map.png"
        map_screenshot.write_bytes(base64.b64decode(page.call("Page.captureScreenshot")["data"]))
        print(f"knowledge_map_screenshot={map_screenshot.as_posix()}")
        page.call("Emulation.setDeviceMetricsOverride", {"width": 375, "height": 900, "deviceScaleFactor": 1, "mobile": True})
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        assert page.evaluate("document.querySelector('.knowledge-viewport').scrollWidth > document.querySelector('.knowledge-viewport').clientWidth")
        page.call("Emulation.clearDeviceMetricsOverride")
        page.evaluate("document.querySelector('[data-knowledge-step=\"REAL_WF_0003_ST_005\"]').dispatchEvent(new MouseEvent('click', {bubbles:true}))")
        assert "Chưa được ghi nhận" in page.evaluate("document.querySelector('#knowledge-detail').textContent")
        page.evaluate("document.querySelector('[data-knowledge-question=\"REAL_WF_0003_Q_001\"] button').click()")
        assert page.evaluate("document.querySelector('#feedback-question').value") == "REAL_WF_0003_Q_001"
        assert page.evaluate("document.querySelector('#feedback-step').value") == "REAL_WF_0003_ST_005"
        assert page.evaluate("document.querySelector('#feedback-field').value") == "rationale"
        assert page.evaluate("document.querySelector('#feedback-save').disabled")
        page.evaluate("const pocketPicker = document.querySelector('#workflow-select'); pocketPicker.value = [...pocketPicker.options].find(x => x.textContent.startsWith('B0_SRC_HAAS_0005')).value; pocketPicker.dispatchEvent(new Event('change'))")
        page.wait("document.querySelector('#workflow-status').textContent.includes('B0_SRC_HAAS_0005 r2 ·')")
        # Man Bo sung. Stub chay duoc preview, nhung nut Luu PHAI van tat: chua co
        # service ghi cua doi 1 thi khong duoc co nut luu gia.
        page.wait("!document.querySelector('#feedback-form').hidden")
        page.evaluate("document.querySelector('#feedback-actor').value = 'dpv137'")
        page.evaluate("document.querySelector('#feedback-label').value = 'Nguoi thu nghiem'")
        page.evaluate("document.querySelector('#feedback-role').value = 'ky thuat vien bao tri'")
        page.evaluate("document.querySelector('#feedback-text').value = 'Thao nap che truoc de nhin duoc duong day tin hieu.'")
        page.evaluate("document.querySelector('#feedback-preview').click()")
        page.wait("document.querySelector('#feedback-diff').textContent.includes('revision')")
        assert page.evaluate("document.querySelector('#feedback-save').disabled")
        assert "mô phỏng" in page.evaluate("document.querySelector('#feedback-message').textContent")
        assert "pending" in page.evaluate("document.querySelector('#feedback-diff').textContent")

        page.evaluate("[...document.querySelectorAll('#workflow-history button')].find(x => x.textContent === 'Xem r1').click()")
        page.wait("document.querySelector('#workflow-status').textContent.includes('B0_SRC_HAAS_0005 r1 ·')")
        page.evaluate("document.querySelector('[data-claim-id=\"B0_SRC_HAAS_0005_CL_020\"] button').click()")
        page.wait("document.querySelector('#evidence').textContent.includes('B0_SRC_HAAS_0005_EV_019')")
        assert "apply some grease" not in page.evaluate("document.querySelector('#evidence blockquote').textContent")
        page.evaluate("document.querySelector('#mode').value = 'synthetic'; document.querySelector('#mode').dispatchEvent(new Event('change'))")
        page.wait("document.querySelector('#workflow-select').options.length > 1")
        assert "MÔ PHỎNG" in page.evaluate("document.querySelector('#banner').textContent")
        assert not page.evaluate("document.body.innerText.includes('B0_SRC_HAAS_0005')")
        assert page.evaluate("document.querySelectorAll('.knowledge-node').length") == 0
        assert page.evaluate("document.querySelector('#demo-question').disabled")
        # A slow response from the previous corpus must not repaint the new one.
        page.evaluate("(() => { const original = window.fetch; window.fetch = (url, options) => String(url).startsWith('/v1/workflows?mode=real') ? new Promise(resolve => setTimeout(() => resolve(original(url, options)), 400)) : original(url, options); const select = document.querySelector('#mode'); select.value = 'real'; select.dispatchEvent(new Event('change')); select.value = 'synthetic'; select.dispatchEvent(new Event('change')); })()")
        page.wait("document.querySelector('#workflow-select').options.length > 1")
        page.evaluate("new Promise(resolve => setTimeout(resolve, 800))")
        assert not page.evaluate("document.body.innerText.includes('B0_SRC_HAAS_0005')")
        # Genuine WebGL space, built from the same indexed snapshots, no CDN/LLM.
        page.call("Network.enable")
        page.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-reduced-motion", "value": "reduce"}]})
        page.call("Page.navigate", {"url": f"http://127.0.0.1:{port}/space"})
        page.wait("document.querySelector('#space-canvas')?.dataset.nodeCount > 0")
        assert page.evaluate("document.querySelector('#space-canvas').dataset.renderer") == "webgl"
        page.wait("window.knowflowSpace.renderer.info.render.calls > 0")
        counts = page.evaluate("window.knowflowSpace.graph.counts")
        latest = {}
        for workflow in data["workflows"]:
            if workflow["revision"] > latest.get(workflow["workflow_id"], {}).get("revision", 0):
                latest[workflow["workflow_id"]] = workflow
        assert counts["workflow"] == len(latest)
        for kind, field in (("step", "steps"), ("claim", "claims"), ("evidence", "evidence"), ("relation", "relations")):
            assert counts[kind] == sum(len(wf[field]) for wf in latest.values())
        assert counts["question"] == sum(q["status"] == "open" for wf in latest.values() for q in wf["questions"])
        assert page.evaluate("(() => {const g=window.knowflowSpace.graph; return new Set(g.nodes.map(n=>n.id)).size===g.nodes.length && g.edges.every(e=>g.byId.has(e.from)&&g.byId.has(e.to));})()")
        assert page.evaluate("window.knowflowSpace.graph.nodes.filter(n=>n.kind==='relation').every(n=>window.knowflowSpace.graph.workflows.get(n.workflow).wf.relations.some(r=>r.relation_id===n.data.relation_id))")
        assert page.evaluate("!window.knowflowSpace.orbit.rotating")
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        space_screenshot = tmp_path / "a2-knowledge-space.png"
        space_screenshot.write_bytes(base64.b64decode(page.call("Page.captureScreenshot")["data"]))
        print(f"knowledge_space_screenshot={space_screenshot.as_posix()}")
        # Pick a real node through the canvas raycaster, then orbit/zoom via input.
        root_point = page.evaluate("window.knowflowSpace.project(window.knowflowSpace.graph.root)")
        page.call("Input.dispatchMouseEvent", {"type": "mousePressed", "x": root_point["x"], "y": root_point["y"], "button": "left", "clickCount": 1})
        page.call("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": root_point["x"], "y": root_point["y"], "button": "left", "clickCount": 1})
        assert page.evaluate("document.querySelector('#space-canvas').dataset.selectedNode === window.knowflowSpace.graph.root")
        theta = page.evaluate("window.knowflowSpace.orbit.theta")
        page.evaluate("document.querySelector('#space-canvas canvas').dispatchEvent(new KeyboardEvent('keydown', {key:'ArrowRight',bubbles:true}))")
        assert page.evaluate("window.knowflowSpace.orbit.theta") > theta
        theta = page.evaluate("window.knowflowSpace.orbit.theta")
        page.call("Input.dispatchMouseEvent", {"type": "mousePressed", "x": root_point["x"], "y": root_point["y"], "button": "left", "clickCount": 1})
        page.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": root_point["x"] + 45, "y": root_point["y"] + 15, "buttons": 1})
        page.call("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": root_point["x"] + 45, "y": root_point["y"] + 15, "button": "left", "clickCount": 1})
        assert page.evaluate("window.knowflowSpace.orbit.theta") != theta
        radius = page.evaluate("window.knowflowSpace.orbit.desiredRadius")
        page.evaluate("document.querySelector('#space-canvas canvas').dispatchEvent(new WheelEvent('wheel', {deltaY:-100,cancelable:true}))")
        assert page.evaluate("window.knowflowSpace.orbit.desiredRadius") < radius
        # Story selects the actual branch and opens evidence from its own revision.
        page.evaluate("document.querySelector('#tour-start').click(); document.querySelector('#tour-next').click()")
        assert "Nhánh có điều kiện" in page.evaluate("document.querySelector('#inspector-title').textContent")
        assert "Điều kiện chuyển bước" in page.evaluate("document.querySelector('#inspector-content').textContent")
        assert "Chưa xác nhận chuyên môn" in page.evaluate("document.querySelector('#inspector-content').textContent")
        evidence_id = page.evaluate("document.querySelector('#inspector-content [data-evidence-id]').dataset.evidenceId")
        page.evaluate("document.querySelector('#inspector-content [data-evidence-id]').click()")
        page.wait(f"document.querySelector('#space-evidence').textContent.includes('{evidence_id}')")
        assert "r2" in page.evaluate("document.querySelector('#space-evidence').textContent")
        page.wait("window.knowflowSpace.orbit.target.distanceTo(window.knowflowSpace.orbit.desiredTarget) < .02")
        branch_screenshot = tmp_path / "a2-knowledge-space-branch.png"
        branch_screenshot.write_bytes(base64.b64decode(page.call("Page.captureScreenshot")["data"]))
        print(f"knowledge_space_branch_screenshot={branch_screenshot.as_posix()}")
        page.evaluate("document.querySelector('#tour-close').click()")
        # Filters/search operate on graph nodes, including a keyboard-accessible route.
        page.evaluate("document.querySelector('#space-reset').click()")
        visible_count = page.evaluate("+document.querySelector('#space-canvas').dataset.visibleNodes")
        page.evaluate("const evFilter=document.querySelector('[data-space-type=evidence]'); evFilter.checked=false; evFilter.dispatchEvent(new Event('change'))")
        assert page.evaluate("+document.querySelector('#space-canvas').dataset.visibleNodes") == visible_count - counts["evidence"]
        page.evaluate("const restoredFilter=document.querySelector('[data-space-type=evidence]'); restoredFilter.checked=true; restoredFilter.dispatchEvent(new Event('change'))")
        # Search by content rather than requiring knowledge of IDs.
        page.evaluate("document.querySelector('#space-search').value='why'; document.querySelector('#space-search').dispatchEvent(new Event('input'))")
        page.wait("document.querySelector('#space-search-results button') !== null")
        page.evaluate("document.querySelector('#space-search-results button').click()")
        assert page.evaluate("document.querySelector('#space-canvas').dataset.selectedNode !== ''")
        page.call("Emulation.setDeviceMetricsOverride", {"width": 375, "height": 900, "deviceScaleFactor": 1, "mobile": True})
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.call("Emulation.clearDeviceMetricsOverride")
        page.evaluate("document.querySelector('#space-fullscreen').click()")
        page.wait("document.querySelector('#space-shell').classList.contains('is-presenting')")
        assert page.evaluate("document.querySelector('#space-shell').clientWidth === innerWidth && document.querySelector('#space-stage').clientWidth > 0")
        page.evaluate("document.querySelector('#stage-tour').click()")
        assert not page.evaluate("document.querySelector('#tour-card').hidden")
        page.evaluate("document.querySelector('#tour-close').click()")
        page.evaluate("document.querySelector('#presentation-exit').click()")
        page.wait("!document.querySelector('#space-shell').classList.contains('is-presenting')")
        # Follow a real open question to the existing feedback form.
        page.evaluate("document.querySelector('#tour-start').click(); document.querySelector('#tour-next').click(); document.querySelector('#tour-next').click(); document.querySelector('#tour-next').click()")
        deep_link = page.evaluate("document.querySelector('#inspector-content a').href")
        page.call("Page.navigate", {"url": deep_link})
        page.wait("document.querySelector('#feedback-question')?.value === 'REAL_WF_0003_Q_001'")
        assert page.evaluate("document.querySelector('#feedback-step').value") == "REAL_WF_0003_ST_005"
        assert page.evaluate("document.querySelector('#feedback-field').value") == "rationale"
        # Namespace changes clear old entities; stale responses cannot repaint them.
        page.call("Page.navigate", {"url": f"http://127.0.0.1:{port}/space"})
        page.wait("document.querySelector('#space-canvas')?.dataset.nodeCount > 0")
        page.evaluate("document.querySelector('#space-mode').value='synthetic'; document.querySelector('#space-mode').dispatchEvent(new Event('change'))")
        page.wait("window.knowflowSpace?.graph?.mode === 'synthetic'")
        assert "MÔ PHỎNG" in page.evaluate("document.body.innerText")
        assert not page.evaluate("document.body.innerText.includes('B0_SRC_HAAS_0005')")
        assert page.evaluate("window.knowflowSpace.graph.nodes.every(n=>n.id.startsWith('synthetic:dev'))")
        # WebGL unavailable: data, search and evidence remain usable.
        # Only the configured namespace should remain selectable on this server.
        service.databases.pop(("synthetic", "dev"))
        page.call("Page.addScriptToEvaluateOnNewDocument", {"source": "window.__webglBlockedForTest=true; const originalGetContext=HTMLCanvasElement.prototype.getContext; HTMLCanvasElement.prototype.getContext=function(kind,...args){return kind.startsWith('webgl')?null:originalGetContext.call(this,kind,...args)}"})
        page.call("Page.reload", {"ignoreCache": True})
        page.wait("window.__webglBlockedForTest === true")
        page.wait("document.querySelector('#space-canvas')?.dataset.renderer === 'unavailable' && window.knowflowSpace?.graph?.mode === 'real' && document.querySelector('#space-canvas').dataset.nodeCount > 0")
        assert page.evaluate("document.querySelector('#space-mode option[value=synthetic]').disabled")
        page.evaluate("document.querySelector('#space-search').value='Nhánh có điều kiện'; document.querySelector('#space-search').dispatchEvent(new Event('input')); document.querySelector('#space-search-results button').click()")
        assert "Điều kiện chuyển bước" in page.evaluate("document.querySelector('#inspector-content').textContent")
        assert all(url.startswith((f"http://127.0.0.1:{port}/", "data:")) for url in page.requests)
        assert page.errors == []
        page.call("Browser.close")
    finally:
        if ws:
            ws.close()
        if proc:
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.terminate(); proc.wait(timeout=5)
        server.should_exit = True
        thread.join(timeout=5)
        sock.close()
