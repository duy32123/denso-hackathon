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
        self.ws, self.counter, self.errors = ws, 0, []

    def call(self, method, params=None):
        self.counter += 1
        self.ws.send(json.dumps({"id": self.counter, "method": method, "params": params or {}}))
        while True:
            result = json.loads(self.ws.recv(timeout=15))
            if result.get("method") == "Runtime.exceptionThrown":
                self.errors.append(result["params"])
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
        proc = subprocess.Popen([str(edge), "--headless=new", "--disable-gpu", "--no-first-run",
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
        page = Page(ws); page.call("Runtime.enable")
        page.wait("document.querySelector('#workflow-select')?.options.length > 1")
        assert page.evaluate("document.querySelector('#question').value") == "How is the pocket slider lubricated?"
        page.evaluate("document.querySelector('#ask').requestSubmit()")
        page.wait("document.querySelector('#status').textContent === 'answered' && document.querySelector('#evidence blockquote') !== null")
        assert page.evaluate("document.querySelectorAll('#citations button').length") > 0
        page.evaluate("const picker = document.querySelector('#workflow-select'); picker.value = [...picker.options].find(x => x.textContent.startsWith('B0_SRC_HAAS_0005')).value; picker.dispatchEvent(new Event('change'))")
        page.wait("document.querySelector('#workflow-status').textContent.includes('B0_SRC_HAAS_0005 r2 ·') && document.querySelector('#workflow-history').textContent.includes('EV_033')")
        page.evaluate("document.querySelector('[data-claim-id=\"B0_SRC_HAAS_0005_CL_020\"] button').click()")
        page.wait("document.querySelector('#evidence').textContent.includes('B0_SRC_HAAS_0005_EV_033')")
        assert "apply some grease" in page.evaluate("document.querySelector('#evidence blockquote').textContent")
        assert "Attribution:" in page.evaluate("document.querySelector('#evidence').textContent")
        assert "Scope:" in page.evaluate("document.querySelector('#evidence').textContent")
        assert page.evaluate("document.querySelectorAll('.state-missing').length") > 0
        page.evaluate("document.querySelector('[data-claim-id=\"B0_SRC_HAAS_0005_CL_020\"]').closest('details').open = true; document.querySelector('[data-claim-id=\"B0_SRC_HAAS_0005_CL_020\"]').closest('details').parentElement.open = true; document.querySelector('[data-claim-id=\"B0_SRC_HAAS_0005_CL_020\"]').scrollIntoView({block:'center'})")
        assert page.evaluate("document.querySelector('.evidence-panel').getBoundingClientRect().top >= 0 && document.querySelector('.evidence-panel').getBoundingClientRect().bottom <= innerHeight")
        page.evaluate("window.scrollTo(0, 0)")
        screenshot = tmp_path / "wp4-browser.png"
        screenshot.write_bytes(base64.b64decode(page.call("Page.captureScreenshot", {"captureBeyondViewport": True})["data"]))
        print(f"browser_screenshot={screenshot.as_posix()}")
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
        assert page.evaluate("document.querySelector('#demo-question').disabled")
        # A slow response from the previous corpus must not repaint the new one.
        page.evaluate("(() => { const original = window.fetch; window.fetch = (url, options) => String(url).startsWith('/v1/workflows?mode=real') ? new Promise(resolve => setTimeout(() => resolve(original(url, options)), 400)) : original(url, options); const select = document.querySelector('#mode'); select.value = 'real'; select.dispatchEvent(new Event('change')); select.value = 'synthetic'; select.dispatchEvent(new Event('change')); })()")
        page.wait("document.querySelector('#workflow-select').options.length > 1")
        page.evaluate("new Promise(resolve => setTimeout(resolve, 800))")
        assert not page.evaluate("document.body.innerText.includes('B0_SRC_HAAS_0005')")
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
