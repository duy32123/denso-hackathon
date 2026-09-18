"""Sinh synthetic KB theo ma tran coverage cua ke hoach doi 2 (muc 1.4).

Chay: python scripts/build_synthetic_kb.py

Sinh bang code voi seed co dinh => chay lai cho ket qua giong het tung byte,
khong goi LLM, khong ton API. Toan bo noi dung la MO PHONG: thiet bi gia
DEMO_TC_A / DEMO_TC_B cua hang gia DemoWorks, de khong ai nham voi mot quy
trinh Haas/DENSO that.

Dau ra:
  data/synthetic_samples/serving/    mot bundle hop le, dung de import va phuc vu
  data/synthetic_samples/negative/   cac bundle CO Y SAI, chi dung negative test
  data/synthetic_samples/generator.json  seed / version / thong ke coverage

Ke hoach muc 1: bundle negative KHONG duoc nhap vao KB phuc vu.
Ke hoach muc 6 ("synthetic qua sach"): co y chen thieu thong tin, conflict,
revision, va nhieu kieu ASR vao quote.
"""

from __future__ import annotations

import json
import os
import random
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
    write_bundle,
)

# Test dung KNOWFLOW_SYNTHETIC_OUT de sinh lai vao thu muc tam roi so tung byte
# voi ban da commit; mac dinh luon la thu muc trong repo.
OUT = Path(os.environ.get("KNOWFLOW_SYNTHETIC_OUT") or ROOT / "data" / "synthetic_samples")
SEED = 20260918
GENERATOR_VERSION = "synthetic-kb-1.0.0"
TEMPLATE_VERSION = "syn-templates-1"

MANUFACTURER = "DemoWorks"
FAMILY = "DEMO-TC"
MODEL_A = "DEMO_TC_A"
MODEL_B = "DEMO_TC_B"

# Ma alarm gan giong nhau: kiem tra retrieval KHONG duoc gop 2066 voi 2067 hay 20.66.
ALARMS = ("2066", "2067", "20.66", "1042", "1043")

_counter = {"src": 0}


def next_source_id() -> str:
    _counter["src"] += 1
    return f"SYN_SRC_{_counter['src']:04d}"


# --- nhieu kieu ASR ----------------------------------------------------------

_NOISE = {
    "kiem": "kiem",
    "thao": "thao",
    "khoa": "khoa",
    "chot": "chot",
}


def asr_noise(text: str, rng: random.Random) -> str:
    """Lam ban quote giong loi ASR: viet lien hoac nghe nham mot tu chu.

    KHONG dung vao chu so hay ma thiet bi/alarm: D-07 doi claim chua ma/so phai
    co quote nguyen van, lam ban so se bien canh bao thanh du lieu sai that.
    """
    words = text.split(" ")
    candidates = [
        i for i, w in enumerate(words)
        if len(w) > 3 and w.isalpha() and w.lower() == w and not any(ch.isdigit() for ch in w)
    ]
    if len(candidates) < 2:
        return text
    i = rng.choice(candidates[:-1])
    words[i : i + 2] = [words[i] + words[i + 1]]          # mat khoang trang, loi ASR pho bien
    return " ".join(words)


# --- bo dung mot workflow ----------------------------------------------------


def build_workflow(
    wf_id: str,
    *,
    title: str,
    steps_spec: list[dict],
    context: dict,
    source_title: str,
    rng: random.Random,
    language: str = "vi",
    timed: bool = True,
    noisy_quotes: bool = False,
    presenter: str = "Nhan vat mo phong",
    extra_sources: list[dict] | None = None,
    relations: list[dict] | None = None,
    questions: list[dict] | None = None,
    **wf_kw,
) -> tuple[list[dict], dict]:
    """Dung mot workflow tu dac ta buoc.

    steps_spec: [{"title": str, "<role>": [(modality, claim_text, evidence_text, opts)]}]
    opts la dict tuy chon cho make_claim (evidence_type, link_status, conflicts_with...).
    Tra ve (danh sach source, workflow).
    """
    src_id = next_source_id()
    evidence: list[dict] = []
    claims: list[dict] = []
    steps: list[dict] = []
    transcript: list[str] = []
    cursor = 1_000

    for s_i, spec in enumerate(steps_spec, start=1):
        step_id = f"{wf_id}_ST_{s_i:03d}"
        fields: dict[str, dict] = {}
        for role, entries in spec.items():
            if role == "title":
                continue
            claim_ids: list[str] = []
            for modality, claim_text, evidence_text, *rest in entries:
                opts = dict(rest[0]) if rest else {}
                ev_id = f"{wf_id}_EV_{len(evidence) + 1:03d}"
                cl_id = f"{wf_id}_CL_{len(claims) + 1:03d}"
                spoken = evidence_text
                if noisy_quotes and modality == "speech":
                    spoken = asr_noise(spoken, rng)
                transcript.append(spoken)
                if timed:
                    start, end = cursor, cursor + 4_000
                    cursor = end + 500
                    loc = {"start_ms": start, "end_ms": end}
                else:
                    # Nguon chi co van ban: khong co clip de mo, nen modality la text.
                    # Ke hoach muc 1: khong duoc goi mot timestamp gia la bang chung video.
                    loc = {"text_span": spoken}
                    modality = "text"
                if modality == "visual":
                    evidence.append(make_evidence(ev_id, src_id, modality="visual",
                                                  observation_note=spoken, **loc))
                elif modality == "speech":
                    evidence.append(make_evidence(ev_id, src_id, modality="speech", quote=spoken, **loc))
                else:
                    evidence.append(make_evidence(ev_id, src_id, modality="text", quote=spoken,
                                                  text_span=spoken))
                opts.setdefault("evidence_type", "observed" if modality == "visual" else "stated")
                opts.setdefault("explanation", "Cau mo phong neu truc tiep noi dung nay."
                                if language == "vi" else "The simulated line states this directly.")
                opts.setdefault("scope_description", "Chi trong bo du lieu mo phong"
                                if language == "vi" else "Simulated dataset only")
                claims.append(make_claim(cl_id, claim_text, role, [ev_id], **opts))
                claim_ids.append(cl_id)
            fields[role] = fref("present", claim_ids)
        steps.append(make_step(step_id, s_i, spec["title"], **fields))

    duration = cursor + 5_000 if timed else None
    source = make_source(
        src_id,
        title=source_title,
        raw_text=" ".join(transcript),
        duration_ms=duration,
        presenter=presenter,
        language=language,
    )
    sources = [source, *(extra_sources or [])]
    workflow = make_workflow(
        wf_id,
        title=title,
        source_ids=[s["source_id"] for s in sources],
        context=context,
        steps=steps,
        claims=claims,
        evidence=evidence,
        language=language,
        relations=relations or [],
        questions=questions or [],
        **wf_kw,
    )
    return sources, workflow


def ctx(**over) -> dict:
    base = {"manufacturer": MANUFACTURER, "machine_family": FAMILY, "task_type": "maintenance"}
    base.update(over)
    return make_context(**base)


# --- ngan hang noi dung ------------------------------------------------------

TOPICS_VI = [
    ("loc-khi", "Thay bo loc khi cum cap dao", "bo loc khi", "air_filter"),
    ("cam-bien", "Hieu chinh cam bien vi tri hoc dao", "cam bien vi tri", "position_sensor"),
    ("day-dai", "Thay day dai truyen dong", "day dai", "drive_belt"),
    ("ve-sinh", "Ve sinh khoang chua phoi", "khoang chua phoi", "chip_tray"),
    ("siet-bu-long", "Siet lai bu long chan de", "bu long chan de", "base_bolt"),
    ("reset-cum", "Reset cum cap dao sau bao loi", "cum cap dao", "changer_unit"),
    ("boi-tron", "Boi tron con truot hoc dao", "con truot", "pocket_slider"),
    ("kiem-ap", "Kiem tra ap suat khi nen", "duong khi nen", "air_line"),
    ("thay-o-bi", "Thay o bi truc chinh", "o bi", "spindle_bearing"),
    ("can-chinh", "Can chinh mam cap", "mam cap", "chuck"),
]

# Chu de RIENG cho cac workflow co y bo trong phan ly do. Khong nhom nao khac
# duoc dung chung: neu mot workflow khac giai thich ho cung mot cum thi thong tin
# khong con thieu o muc corpus, va cau hoi "vi sao" dang le phai tra loi duoc.
TOPICS_MISSING = [
    ("bom-lam-mat", "Thay bom dung dich lam mat", "bom lam mat", "coolant_pump"),
    ("voi-phun", "Thong voi phun dung dich", "voi phun", "coolant_nozzle"),
    ("cua-an-toan", "Chinh cong tac cua an toan", "cua an toan", "safety_door"),
    ("bang-dieu-khien", "Thay mang phim bang dieu khien", "mang phim", "control_panel"),
]

TOPICS_EN = [
    ("filter-en", "Replace the tool changer air filter", "air filter", "air_filter"),
    ("sensor-en", "Calibrate the tool position sensor", "position sensor", "position_sensor"),
]

ACTIONS_VI = [
    "thao nap che {comp} bang luc tay",
    "lau sach be mat {comp} bang gie kho",
    "kiem tra {comp} xem co vet nut khong",
    "lap lai {comp} dung chieu da danh dau",
    "siet cac vit quanh {comp} theo thu tu cheo",
    "cho may chay khong tai mot phut sau khi lap {comp}",
    "ngat nguon truoc khi cham vao {comp}",
    "danh dau vi tri {comp} truoc khi thao",
]
OBSERVATIONS_VI = [
    "{comp} bam bui day, mau xam",
    "nguoi thao tac dung khoa luc de siet {comp}",
    "co vet dau ri quanh {comp}",
    "den bao tren bang dieu khien chuyen sang mau xanh",
]
RATIONALES_VI = [
    "lam vay de {comp} khong bi lech khi lap lai",
    "lam vay de tranh bui roi vao trong cum",
    "lam vay vi lap sai chieu se ket khi chay",
]
CONDITIONS_VI = [
    "chi lam khi may da dung han",
    "chi lam khi ap suat khi da xa het",
    "chi lam neu den bao van con sang sau khi reset",
]
OUTCOMES_VI = [
    "{comp} ve dung vi tri, khong con khe ho",
    "khong con tieng keu khi cum chay thu",
    "den bao tat sau khi hoan tat",
]
ACCEPTANCE_VI = [
    "lac tay khong thay {comp} xe dich",
    "chay thu mot chu ky khong bao loi",
]

ACTIONS_EN = [
    "remove the {comp} cover by hand",
    "wipe the {comp} surface with a dry cloth",
    "refit the {comp} in the marked orientation",
    "tighten the screws around the {comp} in a cross pattern",
]
RATIONALES_EN = [
    "this keeps the {comp} from sitting crooked when it goes back on",
    "this keeps debris out of the unit",
]


def say_vi(text: str) -> str:
    return "Roi, minh " + text + "."


def state_vi(text: str) -> str:
    return "Nguoi noi cho biet " + text + "."


def procedure_steps(topic, n_steps: int, rng: random.Random, *, omit=(), language="vi") -> list[dict]:
    """Sinh 5-12 buoc cho mot chu de. `omit` la cac role co y bo trong."""
    _, title, comp, _slug = topic
    acts = ACTIONS_EN if language == "en" else ACTIONS_VI
    rats = RATIONALES_EN if language == "en" else RATIONALES_VI
    # Lay hanh dong khong lap trong cung workflow: hai buoc trung het tieu de lam
    # nhan gold khong phan biet duoc. Khi het von tu thi ghi ro day la lan lam lai.
    order = rng.sample(range(len(acts)), k=min(n_steps, len(acts)))
    specs: list[dict] = []
    for i in range(1, n_steps + 1):
        pick = order[(i - 1) % len(order)]
        act = acts[pick].format(comp=comp)
        if i > len(order):
            act = f"{act} (lan lam lai thu {(i - 1) // len(order) + 1})"
        if language == "en":
            spec = {
                "title": act[0].upper() + act[1:],
                "action": [("speech", f"The speaker says to {act}.", f"Okay, now we {act}.")],
            }
            if "rationale" not in omit and rng.random() < .7:
                rat = rng.choice(rats).format(comp=comp)
                spec["rationale"] = [("speech", f"The speaker gives the reason: {rat}.",
                                      f"We do it because {rat}.")]
        else:
            spec = {
                "title": act[0].upper() + act[1:],
                "action": [("speech", state_vi(act), say_vi(act))],
            }
            if "rationale" not in omit and rng.random() < .7:
                rat = rng.choice(rats).format(comp=comp)
                spec["rationale"] = [("speech", state_vi(rat), say_vi(rat))]
            if "observation" not in omit and rng.random() < .5:
                obs = rng.choice(OBSERVATIONS_VI).format(comp=comp)
                spec["observation"] = [("visual", f"Quan sat thay {obs}.", f"Trong hinh: {obs}.")]
            if "condition" not in omit and rng.random() < .35:
                cond = rng.choice(CONDITIONS_VI)
                spec["condition"] = [("speech", f"Nguoi noi neu dieu kien: {cond}.", f"Nho la {cond}.")]
            if "outcome" not in omit and rng.random() < .4:
                out = rng.choice(OUTCOMES_VI).format(comp=comp)
                spec["outcome"] = [("visual", f"Ket qua quan sat duoc: {out}.", f"Sau buoc nay: {out}.")]
            if "acceptance_criteria" not in omit and rng.random() < .3:
                acc = rng.choice(ACCEPTANCE_VI).format(comp=comp)
                spec["acceptance_criteria"] = [("speech", f"Nguoi noi neu cach kiem: {acc}.",
                                               f"Kiem lai bang cach {acc}.")]
        if i == 1:
            spec["context"] = [("speech", f"Buoc nay lam tren cum {comp}.",
                                f"Phan nay minh lam tren {comp}." if language == "vi"
                                else f"This part is on the {comp}.")]
        specs.append(spec)
    return specs


# --- bien doi sau khi dung ---------------------------------------------------

from copy import deepcopy  # noqa: E402

from knowflow_contracts.derive import derive_support_status  # noqa: E402


def add_questions(wf: dict, role: str, reason: str, text: str, limit: int = 2) -> None:
    """Ghi lai phan con thieu thanh Question, khong tu dien noi dung."""
    added = 0
    for step in wf["steps"]:
        if added >= limit:
            break
        if step["fields"][role]["state"] == "missing":
            added += 1
            wf["questions"].append(make_question(
                f"{wf['workflow_id']}_Q_{len(wf['questions']) + 1:03d}",
                step["step_id"], role, reason, text.format(title=step["title"].lower()),
            ))


def add_conflict(sources: list[dict], wf: dict, comp: str) -> None:
    """Hai nguon noi khac nhau ve cung mot con so; ca hai deu duoc giu lai.

    D-01: conflicts_with khac rong => support_status bi ha xuong ambiguous, nen
    claim khong the duoc dung de khang dinh. Retrieval van phai TIM THAY chung
    de canh bao co dan nguon (ke hoach muc 2).
    """
    wf_id = wf["workflow_id"]
    other_src = make_source(next_source_id(),
                            title=f"Ban ghi mo phong thu hai ve {comp}",
                            raw_text=f"Voi {comp} thi minh siet sau vong.",
                            presenter="Nhan vat mo phong thu hai")
    sources.append(other_src)
    wf["source_ids"] = [*wf["source_ids"], other_src["source_id"]]

    ev_a = f"{wf_id}_EV_{len(wf['evidence']) + 1:03d}"
    ev_b = f"{wf_id}_EV_{len(wf['evidence']) + 2:03d}"
    cl_a = f"{wf_id}_CL_{len(wf['claims']) + 1:03d}"
    cl_b = f"{wf_id}_CL_{len(wf['claims']) + 2:03d}"
    main_src = wf["source_ids"][0]

    wf["evidence"].append(make_evidence(ev_a, main_src, modality="speech",
                                        quote=f"Voi {comp} thi minh siet bon vong.",
                                        text_span=None, start_ms=200, end_ms=900))
    wf["evidence"].append(make_evidence(ev_b, other_src["source_id"], modality="text",
                                        quote=f"Voi {comp} thi minh siet sau vong.",
                                        text_span=f"Voi {comp} thi minh siet sau vong."))
    wf["claims"].append(make_claim(cl_a, f"Nguon thu nhat cho biet siet {comp} bon vong.", "action",
                                   [ev_a], conflicts_with=[cl_b]))
    wf["claims"].append(make_claim(cl_b, f"Nguon thu hai cho biet siet {comp} sau vong.", "action",
                                   [ev_b], conflicts_with=[cl_a]))
    order = len(wf["steps"]) + 1
    wf["steps"].append(make_step(f"{wf_id}_ST_{order:03d}", order,
                                 "Siet lai theo so vong duoc neu", action=[cl_a, cl_b]))


def weaken_claim(wf: dict, index: int = 0) -> None:
    """Ha mot evidence link xuong `insufficient` => claim khong con khang dinh duoc."""
    claim = wf["claims"][index]
    for link in claim["evidence_links"]:
        link["support_status"] = "insufficient"
        link["explanation"] = "Doan duoc dan khong noi du y nay."
    claim["support_status"] = derive_support_status(
        claim["evidence_links"], has_unresolved_conflict=bool(claim["conflicts_with"])).value


def make_revision_2(sources: list[dict], wf: dict, comp: str) -> dict:
    """Vong feedback: phan hoi bo sung rationale con thieu, sinh revision moi.

    D-02: evidence cu giu nguyen ID va noi dung; phan bo sung nhan evidence_id moi.
    """
    wf_id = wf["workflow_id"]
    target = next((s for s in wf["steps"] if s["fields"]["rationale"]["state"] == "missing"), None)
    if target is None:
        return wf
    answer = f"Phai lam dung thu tu vi {comp} se ket neu lap nguoc."
    expert = make_source(next_source_id(), source_kind="expert_answer",
                         title="Phan hoi bo sung (mo phong)", raw_text=answer,
                         presenter="Nguoi tra loi mo phong")
    sources.append(expert)

    r2 = deepcopy(wf)
    r2["revision"] = 2
    r2["supersedes_revision"] = 1
    r2["source_ids"] = [*wf["source_ids"], expert["source_id"]]
    ev_id = f"{wf_id}_EV_{len(wf['evidence']) + 1:03d}"
    cl_id = f"{wf_id}_CL_{len(wf['claims']) + 1:03d}"
    r2["evidence"].append(make_evidence(ev_id, expert["source_id"], modality="text",
                                        quote=answer, text_span=answer))
    r2["claims"].append(make_claim(cl_id, f"Nguoi tra loi cho biet {answer.lower()}", "rationale", [ev_id]))
    for step in r2["steps"]:
        if step["step_id"] == target["step_id"]:
            step["fields"]["rationale"] = fref("present", [cl_id])
    for q in r2["questions"]:
        if q["step_id"] == target["step_id"] and q["target_field"] == "rationale":
            q["status"] = "answered"
            q["answer_source_ids"] = [expert["source_id"]]
            q["resolution_note"] = "Da co phan hoi; van cho kiem truoc khi chuyen resolved."
    r2["change_log"] = [{
        "changed_at": TS,
        "actor_id": "synthetic_kb_generator",
        "reason": "Bo sung rationale tu phan hoi mo phong.",
        "previous_revision": 1,
        "id_mapping": [],
    }]
    return r2


# --- sau nhom cua ma tran coverage -------------------------------------------


def group_missing(rng) -> tuple[list[dict], list[dict], int]:
    """Nhom 1 -- Thieu thong tin: rationale / condition / acceptance_criteria missing."""
    sources, workflows = [], []
    plan = [("rationale", "Vi sao phai {title}?"), ("rationale", "Vi sao phai {title}?"),
            ("rationale", "Vi sao phai {title}?"), ("condition", "Khi nao thi duoc {title}?"),
            ("condition", "Khi nao thi duoc {title}?"), ("acceptance_criteria", "Lam sao biet {title} da dat?"),
            ("acceptance_criteria", "Lam sao biet {title} da dat?"), ("rationale", "Vi sao phai {title}?")]
    for i, (role, question) in enumerate(plan):
        # Ca bo rationale dung chu de rieng => "vi sao" that su khong co dap an trong KB.
        topic = (TOPICS_MISSING[i % len(TOPICS_MISSING)] if role == "rationale"
                 else TOPICS_VI[i % len(TOPICS_VI)])
        wf_id = f"SYN_KB_MISS_{i + 1:02d}"
        srcs, wf = build_workflow(
            wf_id, title=f"{topic[1]} (thieu {role})", source_title=f"Ban ghi mo phong: {topic[1]}",
            steps_spec=procedure_steps(topic, rng.randint(5, 9), rng, omit=(role,)),
            context=ctx(machine_model=MODEL_A if i % 3 else MODEL_B, subsystem="tool_changer",
                        components=[topic[3]]), rng=rng,
        )
        add_questions(wf, role, "missing", question)
        sources += srcs
        workflows.append(wf)
    return sources, workflows, len(workflows)


def group_device(rng) -> tuple[list[dict], list[dict], int]:
    """Nhom 2 -- Khac thiet bi: ten gan nhau, model khac; mot ca metadata null."""
    sources, workflows = [], []
    # Cung mot chu de tren ca hai model, khac nhau o dung MOT con so tra loi duoc.
    # Khong co cho khac nhau nay thi model khong phai du kien quyet dinh, va cau
    # hoi khong neu model dang le van tra loi duoc -- nhom nay se khong kiem gi ca.
    i = 0
    for t_i in range(3):
        topic = TOPICS_VI[t_i]
        for model, torque in ((MODEL_A, "10 Nm"), (MODEL_B, "15 Nm")):
            i += 1
            wf_id = f"SYN_KB_DEV_{i:02d}"
            specs = procedure_steps(topic, rng.randint(5, 8), rng)
            specs.append({
                "title": f"Siet {topic[2]} dung luc cua {model}",
                "action": [("speech", f"Nguoi noi cho biet siet {topic[2]} den {torque} tren {model}.",
                            f"Tren {model} thi minh siet {topic[2]} den {torque}.")],
            })
            srcs, wf = build_workflow(
                wf_id, title=f"{topic[1]} tren {model}",
                source_title=f"Ban ghi mo phong {model}: {topic[1]}", steps_spec=specs,
                context=ctx(machine_model=model, subsystem="tool_changer", components=[topic[3]]), rng=rng,
            )
            sources += srcs
            workflows.append(wf)
    topic = TOPICS_VI[4]
    srcs, wf = build_workflow(
        "SYN_KB_DEV_07", title=f"{topic[1]} (khong ro model)",
        source_title=f"Ban ghi mo phong khong neu model: {topic[1]}",
        steps_spec=procedure_steps(topic, rng.randint(5, 8), rng),
        context=ctx(machine_model=None, subsystem="tool_changer", components=[topic[3]]), rng=rng,
    )
    sources += srcs
    workflows.append(wf)
    return sources, workflows, len(workflows)


def group_provenance(rng) -> tuple[list[dict], list[dict], int]:
    """Nhom 3 -- Nguon/phien ban: conflict, revision cu-moi, withdrawal, claim yeu."""
    sources, workflows = [], []
    ids = 0
    for i in range(3):                                    # conflict trong cung workflow
        topic = TOPICS_VI[i]
        ids += 1
        srcs, wf = build_workflow(
            f"SYN_KB_SRC_{ids:02d}", title=f"{topic[1]} (nguon mau thuan)",
            source_title=f"Ban ghi mo phong: {topic[1]}",
            steps_spec=procedure_steps(topic, rng.randint(5, 7), rng),
            context=ctx(machine_model=MODEL_A, subsystem="tool_changer", components=[topic[3]]), rng=rng,
        )
        add_conflict(srcs, wf, topic[2])
        sources += srcs
        workflows.append(wf)
    for i in range(2):                                    # r1 + r2, evidence bat bien
        topic = TOPICS_VI[3 + i]
        ids += 1
        srcs, wf = build_workflow(
            f"SYN_KB_SRC_{ids:02d}", title=f"{topic[1]} (co revision moi)",
            source_title=f"Ban ghi mo phong: {topic[1]}",
            steps_spec=procedure_steps(topic, rng.randint(5, 7), rng, omit=("rationale",)),
            context=ctx(machine_model=MODEL_A, subsystem="tool_changer", components=[topic[3]]), rng=rng,
        )
        add_questions(wf, "rationale", "missing", "Vi sao phai {title}?", limit=1)
        r2 = make_revision_2(srcs, wf, topic[2])
        sources += srcs
        workflows += [wf, r2]
    topic = TOPICS_VI[5]                                  # nguon bi rut
    ids += 1
    srcs, wf = build_workflow(
        f"SYN_KB_SRC_{ids:02d}", title=f"{topic[1]} (nguon da bi rut)",
        source_title=f"Ban ghi mo phong da bi rut: {topic[1]}",
        steps_spec=procedure_steps(topic, rng.randint(5, 7), rng),
        context=ctx(machine_model=MODEL_A, subsystem="tool_changer", components=[topic[3]]),
        rng=rng, lifecycle="withdrawn",
    )
    sources += srcs
    workflows.append(wf)
    topic = TOPICS_VI[6]                                  # claim khong duoc nguon do lai
    ids += 1
    srcs, wf = build_workflow(
        f"SYN_KB_SRC_{ids:02d}", title=f"{topic[1]} (co claim thieu can cu)",
        source_title=f"Ban ghi mo phong: {topic[1]}",
        steps_spec=procedure_steps(topic, rng.randint(5, 7), rng),
        context=ctx(machine_model=MODEL_A, subsystem="tool_changer", components=[topic[3]]), rng=rng,
    )
    weaken_claim(wf, index=1)
    sources += srcs
    workflows.append(wf)
    return sources, workflows, ids


def add_relation(wf: dict, relation_type: str, from_i: int, to_i: int, text: str,
                 cond_text: str | None = None) -> None:
    """Them Relation co dan nguon. Claim role=relation khong duoc nam trong FieldRef (V05)."""
    wf_id = wf["workflow_id"]
    src = wf["source_ids"][0]
    n_ev, n_cl, n_rel = len(wf["evidence"]), len(wf["claims"]), len(wf["relations"])
    start = 100 + 60 * n_rel
    ev_id, cl_id = f"{wf_id}_EV_{n_ev + 1:03d}", f"{wf_id}_CL_{n_cl + 1:03d}"
    wf["evidence"].append(make_evidence(ev_id, src, modality="speech", quote=text,
                                        start_ms=start, end_ms=start + 500))
    wf["claims"].append(make_claim(cl_id, f"Nguon neu ro quan he giua hai buoc: {text}", "relation", [ev_id]))

    cond_ids: list[str] = []
    if cond_text is not None:
        ev2, cl2 = f"{wf_id}_EV_{n_ev + 2:03d}", f"{wf_id}_CL_{n_cl + 2:03d}"
        wf["evidence"].append(make_evidence(ev2, src, modality="speech", quote=cond_text,
                                            start_ms=start + 600, end_ms=start + 1_100))
        wf["claims"].append(make_claim(cl2, f"Nguoi noi neu dieu kien: {cond_text}", "condition", [ev2]))
        field = wf["steps"][to_i]["fields"]["condition"]
        if field["state"] == "present":
            field["claim_ids"].append(cl2)
        else:
            wf["steps"][to_i]["fields"]["condition"] = fref("present", [cl2])
        cond_ids = [cl2]

    wf["relations"].append(make_relation(
        f"{wf_id}_REL_{n_rel + 1:03d}", wf["steps"][from_i]["step_id"], wf["steps"][to_i]["step_id"],
        relation_type, [cl_id], cond_ids,
    ))


def group_relations(rng) -> tuple[list[dict], list[dict], int]:
    """Nhom 4 -- Quan he buoc: nhanh, buoc lap, thu tu quan sat duoc."""
    sources, workflows = [], []
    recipes = [("branch", 0), ("branch", 1), ("repeat", 2), ("repeat", 3),
               ("chain", 4), ("chain", 5), ("chain", 6)]
    for i, (kind, t_i) in enumerate(recipes):
        topic = TOPICS_VI[t_i % len(TOPICS_VI)]
        wf_id = f"SYN_KB_REL_{i + 1:02d}"
        srcs, wf = build_workflow(
            wf_id, title=f"{topic[1]} ({kind})", source_title=f"Ban ghi mo phong: {topic[1]}",
            steps_spec=procedure_steps(topic, rng.randint(6, 9), rng),
            context=ctx(machine_model=MODEL_A if i % 3 else MODEL_B, subsystem="tool_changer",
                        components=[topic[3]]), rng=rng,
        )
        if kind == "branch":
            add_relation(wf, "branch_if", 1, 2, "Neu den bao con sang thi minh lam tiep buoc kiem cam bien.",
                         cond_text="chi lam buoc nay neu den bao van con sang")
        elif kind == "repeat":
            # Buoc lap la hop le, khong duoc ep thanh DAG.
            add_relation(wf, "repeated_step", 2, 1, "Cho nao chua sach thi minh quay lai lau lan nua.")
            add_relation(wf, "observed_next", 1, 2, "Lau xong thi minh lap lai.")
        else:
            add_relation(wf, "observed_next", 0, 1, "Xong phan nay thi minh sang buoc ke tiep.")
            add_relation(wf, "observed_next", 1, 2, "Roi moi den buoc sau do.")
            # observed_next KHONG duoc nang thanh requires: thu tu quan sat duoc khong phai phu thuoc.
        sources += srcs
        workflows.append(wf)
    return sources, workflows, len(workflows)


def group_language(rng) -> tuple[list[dict], list[dict], int]:
    """Nhom 5 -- Ngon ngu va tim kiem: Viet-Anh, ma alarm gan giong, sai chinh ta."""
    sources, workflows = [], []
    for i, topic in enumerate(TOPICS_EN):                 # corpus tieng Anh (D-03)
        wf_id = f"SYN_KB_LANG_{i + 1:02d}"
        srcs, wf = build_workflow(
            wf_id, title=topic[1], source_title=f"Simulated recording: {topic[1]}",
            steps_spec=procedure_steps(topic, rng.randint(5, 8), rng, language="en"),
            context=ctx(machine_model=MODEL_A, subsystem="tool_changer", components=[topic[3]]),
            rng=rng, language="en", presenter="Simulated presenter",
        )
        sources += srcs
        workflows.append(wf)
    for j, alarm in enumerate(ALARMS[:3]):                # 2066 / 2067 / 20.66
        topic = TOPICS_VI[(j + 5) % len(TOPICS_VI)]
        wf_id = f"SYN_KB_LANG_{j + 3:02d}"
        srcs, wf = build_workflow(
            wf_id, title=f"Xu ly bao loi {alarm}", source_title=f"Ban ghi mo phong: bao loi {alarm}",
            steps_spec=procedure_steps(topic, rng.randint(5, 8), rng),
            context=ctx(machine_model=MODEL_A if j else MODEL_B, subsystem="tool_changer",
                        task_type="troubleshooting", alarm_codes=[alarm], symptoms=["den bao sang"],
                        components=[topic[3]]), rng=rng,
        )
        sources += srcs
        workflows.append(wf)
    for k in range(2):                                    # quote co nhieu kieu ASR
        topic = TOPICS_VI[(k + 8) % len(TOPICS_VI)]
        wf_id = f"SYN_KB_LANG_{k + 6:02d}"
        srcs, wf = build_workflow(
            wf_id, title=f"{topic[1]} (ban ghi co loi nhan dang)",
            source_title=f"Ban ghi mo phong co loi ASR: {topic[1]}",
            steps_spec=procedure_steps(topic, rng.randint(5, 8), rng),
            context=ctx(machine_model=MODEL_A, subsystem="tool_changer", components=[topic[3]]),
            rng=rng, noisy_quotes=True,
        )
        sources += srcs
        workflows.append(wf)
    return sources, workflows, len(workflows)


def group_evidence(rng) -> tuple[list[dict], list[dict], int]:
    """Nhom 6 -- Evidence: fixture chi co van ban, va ban ghi co nhieu."""
    sources, workflows = [], []
    for i in range(2):                                    # khong co timestamp: chi mo duoc text
        topic = TOPICS_VI[i]
        srcs, wf = build_workflow(
            f"SYN_KB_EV_{i + 1:02d}", title=f"{topic[1]} (tai lieu van ban mo phong)",
            source_title=f"Tai lieu mo phong: {topic[1]}",
            steps_spec=procedure_steps(topic, rng.randint(5, 7), rng),
            context=ctx(machine_model=MODEL_A if i else MODEL_B, subsystem="tool_changer",
                        components=[topic[3]]),
            rng=rng, timed=False,
        )
        sources += srcs
        workflows.append(wf)
    for i in range(2):
        topic = TOPICS_VI[i + 2]
        srcs, wf = build_workflow(
            f"SYN_KB_EV_{i + 3:02d}", title=f"{topic[1]} (nhieu quan sat hinh anh)",
            source_title=f"Ban ghi mo phong: {topic[1]}",
            steps_spec=procedure_steps(topic, rng.randint(6, 9), rng),
            context=ctx(machine_model=MODEL_A, subsystem="tool_changer", components=[topic[3]]),
            rng=rng, noisy_quotes=(i == 1),
        )
        sources += srcs
        workflows.append(wf)
    return sources, workflows, len(workflows)


# --- bundle CO Y SAI: chi dung negative test ---------------------------------


def negative_bundles(rng) -> list[str]:
    """Moi bundle hong mot kieu. Ke hoach muc 1: KHONG bao gio nhap vao KB phuc vu."""
    built: list[str] = []

    def small(wf_id: str, t_i: int = 0):
        topic = TOPICS_VI[t_i]
        return build_workflow(
            wf_id, title=f"{topic[1]} (bundle negative)", source_title="Ban ghi mo phong",
            steps_spec=procedure_steps(topic, 5, rng),
            context=ctx(machine_model=MODEL_A, subsystem="tool_changer"), rng=rng,
        )

    srcs, wf = small("SYN_NEG_CITE_01")
    wf["claims"][0]["evidence_links"][0]["evidence_id"] = f"{wf['workflow_id']}_EV_999"
    write_bundle("negative/N01_citation_khong_ton_tai", root=OUT, sources=srcs, workflows=[wf],
                 pipeline_version=GENERATOR_VERSION, expected={
                     "bundle_id": "N01_citation_khong_ton_tai",
                     "title": "Citation tro toi evidence khong ton tai",
                     "purpose": "Chan citation bia: evidence_links khong duoc tro ra ngoai snapshot.",
                     "validator": {"outcome": "reject", "expected_error_codes": ["V03"]},
                 })
    built.append("N01_citation_khong_ton_tai")

    srcs, wf = small("SYN_NEG_ORPHAN_01", 1)
    for step in wf["steps"]:                              # go claim dau ra khoi moi FieldRef
        for role, ref in step["fields"].items():
            if wf["claims"][0]["claim_id"] in ref["claim_ids"]:
                step["fields"][role] = fref("missing")
    write_bundle("negative/N02_claim_mo_coi", root=OUT, sources=srcs, workflows=[wf],
                 pipeline_version=GENERATOR_VERSION, expected={
                     "bundle_id": "N02_claim_mo_coi",
                     "title": "Claim khong duoc FieldRef nao tham chieu",
                     "purpose": "Claim mo coi se khong bao gio hien ra tren UI nhung van vao index.",
                     "validator": {"outcome": "reject", "expected_error_codes": ["V05"]},
                 })
    built.append("N02_claim_mo_coi")

    srcs, wf = small("SYN_NEG_CONFLICT_01", 2)
    wf["claims"][0]["conflicts_with"] = [wf["claims"][1]["claim_id"]]   # chieu nguoc lai bi bo trong
    wf["claims"][0]["support_status"] = "ambiguous"
    write_bundle("negative/N03_conflict_mot_chieu", root=OUT, sources=srcs, workflows=[wf],
                 pipeline_version=GENERATOR_VERSION, expected={
                     "bundle_id": "N03_conflict_mot_chieu",
                     "title": "conflicts_with khong doi xung",
                     "purpose": "Mot phia bi giau conflict thi cau tra loi se khang dinh mot chieu.",
                     "validator": {"outcome": "reject", "expected_error_codes": ["V07"]},
                 })
    built.append("N03_conflict_mot_chieu")

    srcs, wf = small("SYN_NEG_REVIEW_01", 3)
    wf["claims"][0]["source_review"] = "source_checked"   # khong co ReviewEvent nao
    write_bundle("negative/N04_review_gia", root=OUT, sources=srcs, workflows=[wf],
                 pipeline_version=GENERATOR_VERSION, expected={
                     "bundle_id": "N04_review_gia",
                     "title": "Nhan review khong co ReviewEvent",
                     "purpose": "Fixture synthetic phai giu pending; khong duoc tu nhan da kiem nguon.",
                     "validator": {"outcome": "reject", "expected_error_codes": ["V07"]},
                 })
    built.append("N04_review_gia")
    return built


# --- main --------------------------------------------------------------------

GROUPS = (
    ("thieu_thong_tin", group_missing),
    ("khac_thiet_bi", group_device),
    ("nguon_phien_ban", group_provenance),
    ("quan_he_buoc", group_relations),
    ("ngon_ngu_tim_kiem", group_language),
    ("evidence", group_evidence),
)


def main() -> int:
    rng = random.Random(SEED)
    sources: list[dict] = []
    workflows: list[dict] = []
    coverage: dict[str, int] = {}

    for name, builder in GROUPS:
        g_sources, g_workflows, n_ids = builder(rng)
        sources += g_sources
        workflows += g_workflows
        coverage[name] = n_ids
        print(f"  {name}: {n_ids} workflow_id, {len(g_workflows)} record")

    ids = {wf["workflow_id"] for wf in workflows}
    steps = [len(wf["steps"]) for wf in workflows]
    assert 30 <= len(ids) <= 50, f"ke hoach yeu cau 30-50 workflow, dang co {len(ids)}"
    assert all(5 <= n <= 12 for n in steps), f"moi workflow phai 5-12 buoc, dang co {sorted(set(steps))}"

    write_bundle("serving", root=OUT, sources=sources, workflows=workflows,
                 source_type="synthetic", dataset_split="dev", team="team_2",
                 bundle_id="BUNDLE_SYN_KB_DEV", pipeline_version=GENERATOR_VERSION)
    negatives = negative_bundles(rng)

    (OUT / "generator.json").write_text(json.dumps({
        "generator_version": GENERATOR_VERSION,
        "template_version": TEMPLATE_VERSION,
        "seed": SEED,
        "schema_version": "1.0.0",
        "source_type": "synthetic",
        "dataset_split": "dev",
        "note": "Du lieu MO PHONG. Khong dung ket qua tren bo nay lam bang chung he thong hieu video.",
        "serving": {
            "bundle_id": "BUNDLE_SYN_KB_DEV",
            "workflow_ids": len(ids),
            "workflow_records": len(workflows),
            "sources": len(sources),
            "steps_total": sum(steps),
            "steps_min": min(steps),
            "steps_max": max(steps),
        },
        "coverage": coverage,
        "negative_bundles": negatives,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")

    print(f"serving: {len(ids)} workflow_id / {len(workflows)} record / {len(sources)} source "
          f"/ {sum(steps)} step")
    print(f"negative: {len(negatives)} bundle -> {OUT / 'negative'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
