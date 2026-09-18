"""Sinh 10 contract fixture trong data/fixtures/.

Chay: python scripts/build_fixtures.py
Fixture duoc sinh bang code de checksum va record_count luon dung; noi dung
la du lieu MO PHONG, ten thiet bi gia (DEMO_TC_A/B) de khong ai nham voi mot
quy trinh Haas/DENSO that.

Moi thu muc fixture co: manifest.json, sources.jsonl, workflows.jsonl,
expected.json (ky vong cho validator + ky vong hanh vi RAG, do NGUOI chot).

Bo dung record nam o scripts/bundle_builders.py, dung chung voi
scripts/build_synthetic_kb.py.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from bundle_builders import (  # noqa: E402
    TS,
    fref,
    make_claim,
    make_context,
    make_evidence,
    make_question,
    make_relation,
    make_source,
    make_step,
    make_workflow,
    prov,
    rag,
)
from bundle_builders import write_bundle as _write_bundle  # noqa: E402

OUT = ROOT / "data" / "fixtures"


def write_bundle(fixture_id: str, **kw) -> Path:
    """Giu nguyen chu ky cu cua 10 fixture; dich luon la data/fixtures/."""
    return _write_bundle(fixture_id, root=OUT, **kw)

# --- 10 fixture --------------------------------------------------------------


def f01_complete() -> None:
    wf_id = "SYN_WF_0001"
    src = make_source("SYN_SRC_0001", title="Thao tac mo phong tren DEMO_TC_A", duration_ms=60_000)
    ev = [
        make_evidence(f"{wf_id}_EV_001", src["source_id"], modality="speech", quote="Truoc khi thao, toi kiem tra khoa an toan.", start_ms=1_000, end_ms=6_000),
        make_evidence(f"{wf_id}_EV_002", src["source_id"], modality="visual", observation_note="Nguoi thao tac xoay chot khoa sang vi tri LOCK.", start_ms=6_000, end_ms=12_000),
        make_evidence(f"{wf_id}_EV_003", src["source_id"], modality="speech", quote="Lam vay de cum khong tu xoay khi minh thao.", start_ms=12_000, end_ms=18_000),
        make_evidence(f"{wf_id}_EV_004", src["source_id"], modality="speech", quote="Chi lam khi may da dung han.", start_ms=18_000, end_ms=22_000),
        make_evidence(f"{wf_id}_EV_005", src["source_id"], modality="visual", observation_note="Chot khoa nam trong ranh, cum khong xoay khi lac tay.", start_ms=22_000, end_ms=30_000),
        make_evidence(f"{wf_id}_EV_006", src["source_id"], modality="speech", quote="Neu con lac duoc thi chua an khop.", start_ms=30_000, end_ms=35_000),
        make_evidence(f"{wf_id}_EV_007", src["source_id"], modality="speech", quote="Buoc nay lam tren cum DEMO_TC_A.", start_ms=100, end_ms=1_000),
        make_evidence(f"{wf_id}_EV_008", src["source_id"], modality="visual", observation_note="Nguoi thao tac chuyen sang thao nap che.", start_ms=35_000, end_ms=42_000),
        make_evidence(f"{wf_id}_EV_009", src["source_id"], modality="speech", quote="Xong khoa thi minh mo nap che.", start_ms=35_000, end_ms=40_000),
    ]
    claims = [
        make_claim(f"{wf_id}_CL_001", "Buoc nay duoc thuc hien tren cum DEMO_TC_A.", "context", [f"{wf_id}_EV_007"]),
        make_claim(f"{wf_id}_CL_002", "Chot khoa dang o vi tri chua khoa truoc khi bat dau.", "observation", [f"{wf_id}_EV_002"], evidence_type="observed"),
        make_claim(f"{wf_id}_CL_003", "Nguoi thao tac xoay chot khoa sang vi tri LOCK.", "action", [f"{wf_id}_EV_002", f"{wf_id}_EV_001"], evidence_type="observed"),
        make_claim(f"{wf_id}_CL_004", "Nguoi noi cho biet khoa chot de cum khong tu xoay khi thao.", "rationale", [f"{wf_id}_EV_003"]),
        make_claim(f"{wf_id}_CL_005", "Nguoi noi neu chi thuc hien khi may da dung han.", "condition", [f"{wf_id}_EV_004"]),
        make_claim(f"{wf_id}_CL_006", "Sau khi xoay, cum khong xoay duoc khi lac tay.", "outcome", [f"{wf_id}_EV_005"], evidence_type="observed"),
        make_claim(f"{wf_id}_CL_007", "Nguoi noi coi la dat khi cum khong con lac duoc.", "acceptance_criteria", [f"{wf_id}_EV_006"]),
        make_claim(f"{wf_id}_CL_008", "Nguoi thao tac mo nap che sau khi khoa chot.", "action", [f"{wf_id}_EV_008"], evidence_type="observed"),
        make_claim(f"{wf_id}_CL_009", "Nguon cho thay buoc mo nap che dien ra ngay sau buoc khoa chot.", "relation", [f"{wf_id}_EV_009"]),
    ]
    steps = [
        make_step(
            f"{wf_id}_ST_001", 1, "Khoa chot an toan",
            context=[f"{wf_id}_CL_001"], observation=[f"{wf_id}_CL_002"], action=[f"{wf_id}_CL_003"],
            rationale=[f"{wf_id}_CL_004"], condition=[f"{wf_id}_CL_005"], outcome=[f"{wf_id}_CL_006"],
            acceptance_criteria=[f"{wf_id}_CL_007"],
        ),
        make_step(f"{wf_id}_ST_002", 2, "Mo nap che", action=[f"{wf_id}_CL_008"]),
    ]
    ctx = make_context(machine_model="DEMO_TC_A", subsystem="tool_changer", task_type="maintenance")
    wf = make_workflow(
        wf_id, title="Khoa chot truoc khi mo nap che", source_ids=[src["source_id"]], context=ctx,
        steps=steps, claims=claims, evidence=ev,
        relations=[make_relation(f"{wf_id}_RL_001", f"{wf_id}_ST_001", f"{wf_id}_ST_002", "observed_next", [f"{wf_id}_CL_009"])],
    )
    write_bundle(
        "F01_complete", sources=[src], workflows=[wf],
        expected={
            "fixture_id": "F01_complete",
            "title": "Workflow day du bay field",
            "purpose": "Duong co so: moi field co claim, moi claim co evidence mo duoc.",
            "validator": {"outcome": "accept", "expected_error_codes": []},
            "rag": [
                rag("Truoc khi mo nap che can lam gi?", "answered", must_cite_claims=[f"{wf_id}_CL_003"]),
                rag("Vi sao phai khoa chot?", "answered", must_cite_claims=[f"{wf_id}_CL_004"],
                    note="Phai dan claim rationale, khong duoc dien bang kien thuc nen."),
                rag("Momen siet la bao nhieu?", "insufficient_evidence",
                    note="Nguon khong noi ve momen siet."),
            ],
        },
    )


def f02_rationale_missing() -> None:
    wf_id = "SYN_WF_0002"
    src = make_source("SYN_SRC_0002", title="Quan sat hai mau", raw_text="Toi dat hai mau canh nhau.")
    ev = [make_evidence(f"{wf_id}_EV_001", src["source_id"], text_span="Toi dat hai mau canh nhau.", quote="Toi dat hai mau canh nhau.")]
    claims = [make_claim(f"{wf_id}_CL_001", "Nguoi noi cho biet da dat hai mau canh nhau.", "action", [f"{wf_id}_EV_001"])]
    steps = [make_step(f"{wf_id}_ST_001", 1, "Dat hai mau canh nhau", action=[f"{wf_id}_CL_001"])]
    wf = make_workflow(
        wf_id, title="Quan sat mau", source_ids=[src["source_id"]],
        context=make_context(task_type="inspection"), steps=steps, claims=claims, evidence=ev,
        questions=[make_question(f"{wf_id}_Q_001", f"{wf_id}_ST_001", "rationale", "missing", "Viec dat hai mau canh nhau nham muc dich gi?")],
    )
    write_bundle(
        "F02_rationale_missing", sources=[src], workflows=[wf],
        expected={
            "fixture_id": "F02_rationale_missing",
            "title": "Thieu rationale (vi du muc 9-10 cua Schema chung)",
            "purpose": "Thieu du lieu phai o FieldRef.state, khong tao claim gia.",
            "validator": {"outcome": "accept", "expected_error_codes": []},
            "rag": [
                rag("Nguoi noi da lam gi voi hai mau?", "answered", must_cite_claims=[f"{wf_id}_CL_001"]),
                rag("Vi sao dat hai mau canh nhau?", "insufficient_evidence",
                    note="Duoc phep hoi bo sung, tuyet doi khong tu sinh ly do."),
                rag("Hai mau co giong het nhau khong?", "insufficient_evidence"),
            ],
        },
    )


def f03_model_unknown() -> None:
    wf_id = "SYN_WF_0003"
    src = make_source("SYN_SRC_0003", title="Thao tac khong neu ro may", raw_text="Minh reset lai cum roi chay thu.")
    ev = [
        make_evidence(f"{wf_id}_EV_001", src["source_id"], text_span="Minh reset lai cum roi chay thu.", quote="Minh reset lai cum roi chay thu."),
    ]
    claims = [make_claim(f"{wf_id}_CL_001", "Nguoi noi cho biet da reset cum roi chay thu.", "action", [f"{wf_id}_EV_001"])]
    steps = [make_step(f"{wf_id}_ST_001", 1, "Reset cum va chay thu", action=[f"{wf_id}_CL_001"])]
    wf = make_workflow(
        wf_id, title="Reset cum (chua ro may)", source_ids=[src["source_id"]],
        context=make_context(task_type="recovery"), steps=steps, claims=claims, evidence=ev,
        questions=[make_question(f"{wf_id}_Q_001", f"{wf_id}_ST_001", "context", "identity", "Thao tac nay ap dung cho may/model nao?")],
    )
    write_bundle(
        "F03_model_unknown", sources=[src], workflows=[wf],
        expected={
            "fixture_id": "F03_model_unknown",
            "title": "Metadata may chua biet (null)",
            "purpose": "null khong duoc coi la khop; phai hoi lai khi anh huong tinh ap dung.",
            "validator": {"outcome": "accept", "expected_error_codes": []},
            "rag": [
                rag("Toi dung DEMO_TC_B, co reset duoc theo cach nay khong?", "needs_clarification",
                    note="machine_model null => khong duoc khang dinh la ap dung duoc."),
                rag("Nguon mo ta thao tac gi?", "answered", must_cite_claims=[f"{wf_id}_CL_001"],
                    note="Duoc phep mo ta nguon kem gioi han pham vi."),
            ],
        },
    )


def f04_model_mismatch() -> None:
    workflows, sources = [], []
    for wf_id, model, text in (
        ("SYN_WF_0004", "DEMO_TC_A", "Tren DEMO_TC_A minh xoay chot sang trai."),
        ("SYN_WF_0005", "DEMO_TC_B", "Tren DEMO_TC_B minh xoay chot sang phai."),
    ):
        src = make_source(f"SYN_SRC_{wf_id[-4:]}", title=f"Thao tac tren {model}", raw_text=text)
        ev = [make_evidence(f"{wf_id}_EV_001", src["source_id"], text_span=text, quote=text)]
        claims = [make_claim(f"{wf_id}_CL_001", f"Tren {model}, nguoi noi xoay chot theo mot chieu xac dinh.", "action", [f"{wf_id}_EV_001"])]
        steps = [make_step(f"{wf_id}_ST_001", 1, "Xoay chot", action=[f"{wf_id}_CL_001"])]
        sources.append(src)
        workflows.append(make_workflow(
            wf_id, title=f"Xoay chot tren {model}", source_ids=[src["source_id"]],
            context=make_context(machine_model=model, subsystem="tool_changer", task_type="maintenance",
                                 provenance={"machine_model": prov("source", [src["source_id"]], "Nguon neu ro ten may")}),
            steps=steps, claims=claims, evidence=ev,
        ))
    write_bundle(
        "F04_model_mismatch", sources=sources, workflows=workflows,
        expected={
            "fixture_id": "F04_model_mismatch",
            "title": "Hai may ten gan giong nhau",
            "purpose": "Metadata khac model da biet phai bi loai truoc khi tra loi.",
            "validator": {"outcome": "accept", "expected_error_codes": []},
            "rag": [
                rag("Tren DEMO_TC_B xoay chot chieu nao?", "answered",
                    must_cite_claims=["SYN_WF_0005_CL_001"], must_not_cite_claims=["SYN_WF_0004_CL_001"]),
                rag("Tren DEMO_TC_C xoay chot chieu nao?", "insufficient_evidence",
                    note="Khong duoc noi long bo loc model khi it ket qua."),
            ],
        },
    )


def f05_locator_invalid() -> None:
    wf_id = "SYN_WF_0006"
    src = make_source("SYN_SRC_0006", title="Clip mo phong 60 giay", duration_ms=60_000)
    ev = [
        make_evidence(f"{wf_id}_EV_001", src["source_id"], modality="speech", quote="Cau nay co moc nguoc.", start_ms=9_000, end_ms=4_000),
        make_evidence(f"{wf_id}_EV_002", src["source_id"], modality="speech", quote="Cau nay vuot thoi luong clip.", start_ms=50_000, end_ms=90_000),
    ]
    claims = [
        make_claim(f"{wf_id}_CL_001", "Nguoi noi mo ta mot thao tac.", "action", [f"{wf_id}_EV_001"]),
        make_claim(f"{wf_id}_CL_002", "Nguoi noi mo ta ket qua.", "outcome", [f"{wf_id}_EV_002"]),
    ]
    steps = [make_step(f"{wf_id}_ST_001", 1, "Thao tac co moc sai", action=[f"{wf_id}_CL_001"], outcome=[f"{wf_id}_CL_002"])]
    wf = make_workflow(wf_id, title="Locator sai", source_ids=[src["source_id"]],
                       context=make_context(task_type="other"), steps=steps, claims=claims, evidence=ev)
    write_bundle(
        "F05_locator_invalid", sources=[src], workflows=[wf],
        expected={
            "fixture_id": "F05_locator_invalid",
            "title": "Evidence lech moc thoi gian",
            "purpose": "Negative test: moc [start, end) nguoc va vuot duration_ms phai bi chan truoc khi index.",
            "validator": {"outcome": "reject", "expected_error_codes": ["V04"]},
            "rag": [],
        },
    )


def f06_conflict() -> None:
    wf_id = "SYN_WF_0007"
    src_a = make_source("SYN_SRC_0007", title="Nguon A", raw_text="Sau khi reset thi den bao tat.")
    src_b = make_source("SYN_SRC_0008", title="Nguon B", raw_text="Sau khi reset den bao van sang.")
    ev = [
        make_evidence(f"{wf_id}_EV_001", src_a["source_id"], text_span="Sau khi reset thi den bao tat.", quote="Sau khi reset thi den bao tat."),
        make_evidence(f"{wf_id}_EV_002", src_b["source_id"], text_span="Sau khi reset den bao van sang.", quote="Sau khi reset den bao van sang."),
    ]
    claims = [
        make_claim(f"{wf_id}_CL_001", "Nguon A neu den bao tat sau khi reset.", "outcome", [f"{wf_id}_EV_001"], conflicts_with=[f"{wf_id}_CL_002"]),
        make_claim(f"{wf_id}_CL_002", "Nguon B neu den bao van sang sau khi reset.", "outcome", [f"{wf_id}_EV_002"], conflicts_with=[f"{wf_id}_CL_001"]),
        make_claim(f"{wf_id}_CL_003", "Nguoi noi cho biet da reset cum.", "action", [f"{wf_id}_EV_001"]),
    ]
    steps = [make_step(f"{wf_id}_ST_001", 1, "Reset cum",
                       action=[f"{wf_id}_CL_003"],
                       outcome=fref("ambiguous", [f"{wf_id}_CL_001", f"{wf_id}_CL_002"]))]
    wf = make_workflow(wf_id, title="Hai nguon noi khac nhau ve ket qua",
                       source_ids=[src_a["source_id"], src_b["source_id"]],
                       context=make_context(task_type="recovery"), steps=steps, claims=claims, evidence=ev)
    write_bundle(
        "F06_conflict", sources=[src_a, src_b], workflows=[wf],
        expected={
            "fixture_id": "F06_conflict",
            "title": "Claim mau thuan giua hai nguon",
            "purpose": "Conflict khong duoc bien mat vi bi loc; phai trung ca hai nguon.",
            "validator": {"outcome": "accept", "expected_error_codes": []},
            "rag": [
                rag("Sau khi reset thi den bao the nao?", "conflicting_sources",
                    must_cite_claims=[f"{wf_id}_CL_001", f"{wf_id}_CL_002"],
                    note="Khong duoc am tham chon mot ben; claim ambiguous khong duoc dung de de xuat thao tac."),
            ],
        },
    )


def f07_repeated_step() -> None:
    wf_id = "SYN_WF_0008"
    src = make_source("SYN_SRC_0009", title="Thao tac lap lai", duration_ms=45_000)
    ev = [
        make_evidence(f"{wf_id}_EV_001", src["source_id"], modality="visual", observation_note="Nguoi thao tac siet oc lan thu nhat.", start_ms=1_000, end_ms=8_000),
        make_evidence(f"{wf_id}_EV_002", src["source_id"], modality="visual", observation_note="Nguoi thao tac siet lai chinh con oc do lan thu hai.", start_ms=20_000, end_ms=28_000),
        make_evidence(f"{wf_id}_EV_003", src["source_id"], modality="speech", quote="Lan nay minh siet lai cho chac.", start_ms=20_000, end_ms=24_000),
    ]
    claims = [
        make_claim(f"{wf_id}_CL_001", "Nguoi thao tac siet oc lan thu nhat.", "action", [f"{wf_id}_EV_001"], evidence_type="observed"),
        make_claim(f"{wf_id}_CL_002", "Nguoi thao tac siet lai chinh con oc do lan thu hai.", "action", [f"{wf_id}_EV_002"], evidence_type="observed"),
        make_claim(f"{wf_id}_CL_003", "Nguon cho thay lan siet thu hai lap lai thao tac cua lan thu nhat.", "relation", [f"{wf_id}_EV_003"]),
    ]
    steps = [
        make_step(f"{wf_id}_ST_001", 1, "Siet oc (lan 1)", action=[f"{wf_id}_CL_001"]),
        make_step(f"{wf_id}_ST_002", 2, "Siet oc (lan 2)", action=[f"{wf_id}_CL_002"]),
    ]
    wf = make_workflow(
        wf_id, title="Thao tac duoc lam lai", source_ids=[src["source_id"]],
        context=make_context(task_type="maintenance"), steps=steps, claims=claims, evidence=ev,
        relations=[make_relation(f"{wf_id}_RL_001", f"{wf_id}_ST_001", f"{wf_id}_ST_002", "repeated_step", [f"{wf_id}_CL_003"])],
    )
    write_bundle(
        "F07_repeated_step", sources=[src], workflows=[wf],
        expected={
            "fixture_id": "F07_repeated_step",
            "title": "Buoc lap lai",
            "purpose": "Moi lan thuc hien la mot node rieng; khong ep workflow thanh DAG.",
            "validator": {"outcome": "accept", "expected_error_codes": []},
            "rag": [
                rag("Con oc duoc siet may lan?", "answered",
                    must_cite_claims=[f"{wf_id}_CL_001", f"{wf_id}_CL_002"],
                    note="Hai lan la hai node, khong duoc gop thanh mot."),
            ],
        },
    )


def f08_branch_if() -> None:
    wf_id = "SYN_WF_0009"
    src = make_source("SYN_SRC_0010", title="Nhanh co dieu kien", raw_text="Neu den bao con sang thi chuyen sang kiem cam bien.")
    ev = [
        make_evidence(f"{wf_id}_EV_001", src["source_id"], text_span="Neu den bao con sang thi chuyen sang kiem cam bien.", quote="Neu den bao con sang thi chuyen sang kiem cam bien."),
        make_evidence(f"{wf_id}_EV_002", src["source_id"], text_span="Buoc dau minh reset cum.", quote="Buoc dau minh reset cum."),
        make_evidence(f"{wf_id}_EV_003", src["source_id"], text_span="Luc do minh do lai cam bien.", quote="Luc do minh do lai cam bien."),
    ]
    claims = [
        make_claim(f"{wf_id}_CL_001", "Nguoi noi cho biet buoc dau la reset cum.", "action", [f"{wf_id}_EV_002"]),
        make_claim(f"{wf_id}_CL_002", "Nguoi noi neu dieu kien: den bao con sang.", "condition", [f"{wf_id}_EV_001"]),
        make_claim(f"{wf_id}_CL_003", "Nguoi noi cho biet khi do se do lai cam bien.", "action", [f"{wf_id}_EV_003"]),
        make_claim(f"{wf_id}_CL_004", "Nguon neu ro viec chuyen sang kiem cam bien phu thuoc dieu kien den bao.", "relation", [f"{wf_id}_EV_001"]),
    ]
    steps = [
        make_step(f"{wf_id}_ST_001", 1, "Reset cum", action=[f"{wf_id}_CL_001"]),
        make_step(f"{wf_id}_ST_002", 2, "Kiem cam bien", action=[f"{wf_id}_CL_003"], condition=[f"{wf_id}_CL_002"]),
    ]
    wf = make_workflow(
        wf_id, title="Nhanh theo dieu kien", source_ids=[src["source_id"]],
        context=make_context(task_type="troubleshooting"), steps=steps, claims=claims, evidence=ev,
        relations=[make_relation(f"{wf_id}_RL_001", f"{wf_id}_ST_001", f"{wf_id}_ST_002", "branch_if",
                                 [f"{wf_id}_CL_004"], [f"{wf_id}_CL_002"])],
    )
    write_bundle(
        "F08_branch_if", sources=[src], workflows=[wf],
        expected={
            "fixture_id": "F08_branch_if",
            "title": "Nhanh co dieu kien",
            "purpose": "branch_if phai kem condition claim; khong bien thu tu thoi gian thanh phu thuoc.",
            "validator": {"outcome": "accept", "expected_error_codes": []},
            "rag": [
                rag("Khi nao thi phai kiem cam bien?", "answered",
                    must_cite_claims=[f"{wf_id}_CL_002"],
                    note="Cau tra loi phai giu dieu kien, khong noi 'luon phai kiem cam bien'."),
            ],
        },
    )


def f09_revision_update() -> None:
    wf_id = "SYN_WF_0010"
    src = make_source("SYN_SRC_0011", title="Thao tac chua neu ly do", raw_text="Minh thao nap che truoc.")
    expert = make_source(
        "SYN_SRC_0012", source_kind="expert_answer", title="Phan hoi bo sung (mo phong)",
        raw_text="Thao nap che truoc de nhin duoc duong day tin hieu.", presenter="Nguoi tra loi mo phong",
    )
    ev_base = make_evidence(f"{wf_id}_EV_001", src["source_id"], text_span="Minh thao nap che truoc.", quote="Minh thao nap che truoc.")
    ev_answer = make_evidence(f"{wf_id}_EV_002", expert["source_id"],
                              text_span="Thao nap che truoc de nhin duoc duong day tin hieu.",
                              quote="Thao nap che truoc de nhin duoc duong day tin hieu.")
    claim_action = make_claim(f"{wf_id}_CL_001", "Nguoi noi cho biet thao nap che truoc.", "action", [f"{wf_id}_EV_001"])
    claim_rationale = make_claim(f"{wf_id}_CL_002", "Nguoi tra loi cho biet thao nap che truoc de nhin duoc duong day tin hieu.", "rationale", [f"{wf_id}_EV_002"])

    rev1 = make_workflow(
        wf_id, title="Thao nap che", source_ids=[src["source_id"]],
        context=make_context(task_type="maintenance"),
        steps=[make_step(f"{wf_id}_ST_001", 1, "Thao nap che", action=[f"{wf_id}_CL_001"])],
        claims=[claim_action], evidence=[ev_base],
        questions=[make_question(f"{wf_id}_Q_001", f"{wf_id}_ST_001", "rationale", "missing", "Vi sao phai thao nap che truoc?")],
    )
    rev2 = make_workflow(
        wf_id, revision=2, supersedes_revision=1, title="Thao nap che",
        source_ids=[src["source_id"], expert["source_id"]],
        context=make_context(task_type="maintenance"),
        steps=[make_step(f"{wf_id}_ST_001", 1, "Thao nap che", action=[f"{wf_id}_CL_001"], rationale=[f"{wf_id}_CL_002"])],
        claims=[claim_action, claim_rationale], evidence=[ev_base, ev_answer],
        questions=[make_question(f"{wf_id}_Q_001", f"{wf_id}_ST_001", "rationale", "missing", "Vi sao phai thao nap che truoc?",
                                 status="answered", answer_source_ids=[expert["source_id"]],
                                 resolution_note="Da co phan hoi; cho kiem lai truoc khi chuyen resolved.")],
        change_log=[{
            "changed_at": TS, "actor_id": "fixture_builder",
            "reason": "Bo sung rationale tu phan hoi chuyen mon (mo phong).",
            "previous_revision": 1, "id_mapping": [],
        }],
    )
    write_bundle(
        "F09_revision_update", sources=[src, expert], workflows=[rev1, rev2],
        expected={
            "fixture_id": "F09_revision_update",
            "title": "Vong feedback tao revision moi",
            "purpose": "Phan hoi tao Source expert_answer + revision moi; cau tra loi doi, lich su van xem duoc.",
            "validator": {"outcome": "accept", "expected_error_codes": []},
            "rag": [
                rag("Vi sao phai thao nap che truoc?", "answered", must_cite_claims=[f"{wf_id}_CL_002"],
                    note="Chi latest revision duoc dung de khang dinh; khong duoc bao 'chuyen gia xac nhan' "
                         "chi vi co phan hoi (technical_review van not_requested)."),
            ],
            "importer": {
                "reimport_same_content": "no-op",
                "reimport_same_key_other_content": "error, khong overwrite",
                "latest_revision": 2,
            },
        },
    )


def f10_corpus_mixing() -> None:
    wf_id = "REAL_WF_0001"
    real_src = make_source(
        "REAL_SRC_0001", source_type="real", source_kind="official_service_video",
        title="Video dich vu (gia dinh cho negative test)", raw_text=None, duration_ms=120_000,
        url="https://example.invalid/video/1", presenter=None, language="en",
    )
    syn_src = make_source("SYN_SRC_0013", title="Fixture lot vao bundle real", raw_text="Cau mo phong.")
    ev = [
        make_evidence(f"{wf_id}_EV_001", real_src["source_id"], modality="speech", quote="This is a simulated line.", start_ms=1_000, end_ms=5_000),
        make_evidence(f"{wf_id}_EV_002", syn_src["source_id"], text_span="Cau mo phong.", quote="Cau mo phong."),
    ]
    claims = [
        make_claim(f"{wf_id}_CL_001", "Nguoi noi mo ta mot thao tac.", "action", [f"{wf_id}_EV_001"]),
        make_claim(f"{wf_id}_CL_002", "Claim nay thuc chat den tu fixture synthetic.", "outcome", [f"{wf_id}_EV_002"]),
    ]
    steps = [make_step(f"{wf_id}_ST_001", 1, "Thao tac", action=[f"{wf_id}_CL_001"], outcome=[f"{wf_id}_CL_002"])]
    wf = make_workflow(
        wf_id, title="Bundle real bi tron synthetic", source_type="real",
        source_ids=[real_src["source_id"], syn_src["source_id"]],
        context=make_context(task_type="other"), steps=steps, claims=claims, evidence=ev,
    )
    write_bundle(
        "F10_corpus_mixing", sources=[real_src, syn_src], workflows=[wf],
        source_type="real", team="team_1",
        expected={
            "fixture_id": "F10_corpus_mixing",
            "title": "Synthetic lot vao corpus real",
            "purpose": "Negative test: mot bundle chi duoc chua mot source_type. Phai tu choi nguyen goi.",
            "validator": {"outcome": "reject", "expected_error_codes": ["V02"]},
            "rag": [],
        },
    )


BUILDERS = (
    f01_complete, f02_rationale_missing, f03_model_unknown, f04_model_mismatch, f05_locator_invalid,
    f06_conflict, f07_repeated_step, f08_branch_if, f09_revision_update, f10_corpus_mixing,
)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for builder in BUILDERS:
        builder()
        print(f"built {builder.__name__}")
    index = sorted(p.name for p in OUT.iterdir() if p.is_dir())
    (OUT / "index.json").write_text(
        json.dumps({"schema_version": "1.0.0", "fixtures": index}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"{len(index)} fixture -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
