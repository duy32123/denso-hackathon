"""V01-V10: cac rang buoc lien thuc the, chay sau khi parse thanh cong.

Moi ham `_v0x_*` bam sat mot dong trong bang muc 8 cua Schema chung. Neu them
kiem tra moi, them o dung ma va bo sung fixture tuong ung - dung tao ma moi
neu chua cap nhat tai lieu hop dong.
"""

from __future__ import annotations

import re

from .derive import derive_support_status
from .enums import (
    AttributionKind,
    ClaimRole,
    EvidenceKind,
    FIELD_ROLES,
    FieldState,
    Lifecycle,
    Modality,
    ProvenanceBasis,
    RelationType,
    ReviewDecision,
    ReviewDimension,
    SourceKind,
    SourceReview,
    SourceType,
    SupportStatus,
    TechnicalReview,
)
from .issues import Report
from .models import ParsedBundle, Source, Workflow
from .snapshot import snapshot_content_hash

_HAS_DIGIT = re.compile(r"\d")


def _wf_path(wf: Workflow, suffix: str = "") -> str:
    base = f"{wf.workflow_id}@r{wf.revision}"
    return f"{base}.{suffix}" if suffix else base


def check_bundle(bundle: ParsedBundle, report: Report) -> None:
    sources = {s.source_id: s for s in bundle.sources}

    _v02_corpus(bundle, sources, report)
    _v03_bundle_ids(bundle, report)
    _v09_reimport_keys(bundle, report)
    _v03_evidence_immutability(bundle, report)

    for wf in bundle.workflows:
        _v03_references(wf, sources, report)
        _v04_locators(wf, sources, report)
        _v05_fields_and_roles(wf, report)
        _v06_claims_and_links(wf, bundle, report)
        _v07_review_and_conflict(wf, bundle, report)
        _v08_relations(wf, report)
        _v09_revision_history(wf, report)

    _v10_withdrawal(bundle, report)


# --- V02: corpus, split, nguon -----------------------------------------------


def _v02_corpus(bundle: ParsedBundle, sources: dict[str, Source], report: Report) -> None:
    manifest = bundle.manifest

    for src in bundle.sources:
        path = f"sources[{src.source_id}]"
        if src.source_type != manifest.source_type:
            report.error(
                "V02",
                path,
                f"source_type={src.source_type} khac manifest={manifest.source_type}: "
                "mot bundle chi chua mot source_type",
            )
        if src.source_kind == SourceKind.SYNTHETIC_FIXTURE and src.source_type != SourceType.SYNTHETIC:
            report.error("V02", path, "source_kind=synthetic_fixture nhung source_type khong phai synthetic")
        if src.source_type == SourceType.REAL:
            if src.source_kind == SourceKind.SYNTHETIC_FIXTURE:
                report.error("V02", path, "nguon real khong duoc dung source_kind=synthetic_fixture")
            if not src.url and not src.asset_uri:
                report.error("V02", path, "nguon real phai co it nhat mot duong dan truy cap (url hoac asset_uri)")
            if src.source_kind == SourceKind.OFFICIAL_SERVICE_VIDEO and src.duration_ms is None:
                report.error("V02", path, "video that phai co duration_ms da do")
        if src.source_kind in (SourceKind.EXPERT_ANSWER, SourceKind.SYNTHETIC_FIXTURE) and src.raw_text is None:
            report.error("V02", path, f"source_kind={src.source_kind} bat buoc raw_text")

    for wf in bundle.workflows:
        path = _wf_path(wf)
        if wf.source_type != manifest.source_type:
            report.error("V02", path, f"source_type={wf.source_type} khac manifest={manifest.source_type}")
        if wf.dataset_split != manifest.dataset_split:
            report.error("V02", path, f"dataset_split={wf.dataset_split} khac manifest={manifest.dataset_split}")
        if wf.schema_version != manifest.schema_version:
            report.error("V01", path, "schema_version cua workflow khac manifest")
        for sid in wf.source_ids:
            src = sources.get(sid)
            if src is not None and src.source_type != wf.source_type:
                report.error(
                    "V02",
                    _wf_path(wf, f"source_ids[{sid}]"),
                    f"tron corpus: nguon {sid} la {src.source_type}, workflow la {wf.source_type}",
                )


# --- V03: ID va tham chieu ---------------------------------------------------


def _v03_bundle_ids(bundle: ParsedBundle, report: Report) -> None:
    seen_sources: set[str] = set()
    for src in bundle.sources:
        if src.source_id in seen_sources:
            report.error("V03", f"sources[{src.source_id}]", "source_id trung trong bundle")
        seen_sources.add(src.source_id)

    for src in bundle.sources:
        for rid in src.related_source_ids:
            if rid not in seen_sources:
                report.warn(
                    "V03",
                    f"sources[{src.source_id}].related_source_ids",
                    f"tro toi source ngoai bundle: {rid}",
                )


def _v03_references(wf: Workflow, sources: dict[str, Source], report: Report) -> None:
    claim_ids = {c.claim_id for c in wf.claims}
    evidence_ids = {e.evidence_id for e in wf.evidence}
    step_ids = {s.step_id for s in wf.steps}
    relation_ids = {r.relation_id for r in wf.relations}

    _check_unique(wf, "claims", [c.claim_id for c in wf.claims], report)
    _check_unique(wf, "evidence", [e.evidence_id for e in wf.evidence], report)
    _check_unique(wf, "steps", [s.step_id for s in wf.steps], report)
    _check_unique(wf, "relations", [r.relation_id for r in wf.relations], report)
    _check_unique(wf, "questions", [q.question_id for q in wf.questions], report)

    orders = [s.display_order for s in wf.steps]
    if len(set(orders)) != len(orders):
        report.error("V03", _wf_path(wf, "steps"), "display_order phai duy nhat trong workflow")

    for sid in wf.source_ids:
        if sid not in sources:
            report.error("V03", _wf_path(wf, "source_ids"), f"source_id khong ton tai trong bundle: {sid}")

    for ev in wf.evidence:
        path = _wf_path(wf, f"evidence[{ev.evidence_id}]")
        if ev.source_id not in wf.source_ids:
            report.error("V03", path, f"source_id {ev.source_id} khong nam trong workflow.source_ids")
        for pid in ev.parent_evidence_ids:
            if pid not in evidence_ids:
                report.error("V03", path, f"parent_evidence_ids tro toi evidence khong ton tai: {pid}")
        if not ev.evidence_id.startswith(wf.workflow_id):
            report.warn("V03", path, "evidence_id nen mang tien to workflow_id (ID nested)")

    for step in wf.steps:
        for role in FIELD_ROLES:
            ref = getattr(step.fields, role)
            for cid in ref.claim_ids:
                if cid not in claim_ids:
                    report.error(
                        "V03",
                        _wf_path(wf, f"steps[{step.step_id}].fields.{role}"),
                        f"claim_id khong ton tai trong snapshot: {cid}",
                    )

    for claim in wf.claims:
        path = _wf_path(wf, f"claims[{claim.claim_id}]")
        for link in claim.evidence_links:
            if link.evidence_id not in evidence_ids:
                report.error("V03", path, f"evidence_links tro toi evidence khong ton tai: {link.evidence_id}")
        for cid in claim.conflicts_with:
            if cid not in claim_ids:
                report.error("V03", path, f"conflicts_with phai cung snapshot: {cid} khong ton tai")
            if cid == claim.claim_id:
                report.error("V03", path, "claim khong the conflict voi chinh no")
        if claim.claim_id in claim.supersedes_claim_ids:
            report.error("V03", path, "supersedes_claim_ids khong duoc chua chinh no")

    for rel in wf.relations:
        path = _wf_path(wf, f"relations[{rel.relation_id}]")
        for key, sid in (("from_step_id", rel.from_step_id), ("to_step_id", rel.to_step_id)):
            if sid not in step_ids:
                report.error("V03", path, f"{key} tro toi step khong ton tai: {sid}")

    for q in wf.questions:
        if q.step_id not in step_ids:
            report.error(
                "V03",
                _wf_path(wf, f"questions[{q.question_id}]"),
                f"step_id khong ton tai: {q.step_id}",
            )
        for sid in q.answer_source_ids:
            if sid not in sources:
                report.error(
                    "V03",
                    _wf_path(wf, f"questions[{q.question_id}]"),
                    f"answer_source_ids tro toi source ngoai bundle: {sid}",
                )

    for ev in wf.review_events:
        path = _wf_path(wf, f"review_events[{ev.review_id}]")
        pool = claim_ids if ev.target_type == "claim" else relation_ids
        if ev.target_id not in pool:
            report.error("V03", path, f"target_id khong ton tai trong snapshot: {ev.target_id}")

    _v03_metadata_provenance(wf, sources, report)


def _v03_metadata_provenance(wf: Workflow, sources: dict[str, Source], report: Report) -> None:
    ctx = wf.context
    prov = ctx.metadata_provenance
    scalar_keys = ("manufacturer", "machine_family", "machine_model", "subsystem", "task_type")
    list_keys = ("symptoms", "alarm_codes", "components")

    for key in scalar_keys + list_keys:
        entry = getattr(prov, key)
        value = getattr(ctx, key)
        path = _wf_path(wf, f"context.metadata_provenance.{key}")
        empty = value is None if key in scalar_keys else not value

        if entry.basis == ProvenanceBasis.SOURCE:
            if not entry.source_ids:
                report.error("V03", path, "basis=source phai co source_ids")
            if empty:
                report.error("V03", path, "basis=source nhung gia tri rong/null")
        if entry.basis == ProvenanceBasis.UNKNOWN and not empty:
            report.error("V03", path, "basis=unknown nhung metadata co gia tri")
        for sid in entry.source_ids:
            if sid not in sources:
                report.error("V03", path, f"source_ids tro toi nguon ngoai bundle: {sid}")
            elif sid not in wf.source_ids:
                report.error("V03", path, f"source_ids khong nam trong workflow.source_ids: {sid}")


def _check_unique(wf: Workflow, label: str, ids: list[str], report: Report) -> None:
    seen: set[str] = set()
    for value in ids:
        if value in seen:
            report.error("V03", _wf_path(wf, label), f"ID trung trong snapshot: {value}")
        seen.add(value)


def _v03_evidence_immutability(bundle: ParsedBundle, report: Report) -> None:
    """D-02: cung workflow_id + cung evidence_id => noi dung phai giong nhau.

    Neu doi locator/quote thi phai cap evidence_id moi, neu khong moi citation
    da phat hanh o revision cu se tro sai cho.
    """
    seen: dict[tuple[str, str], tuple[int, dict]] = {}
    for wf in bundle.workflows:
        for ev in wf.evidence:
            key = (wf.workflow_id, ev.evidence_id)
            payload = ev.model_dump(mode="json")
            if key in seen:
                prev_rev, prev_payload = seen[key]
                if prev_payload != payload:
                    report.error(
                        "V03",
                        _wf_path(wf, f"evidence[{ev.evidence_id}]"),
                        f"evidence doi noi dung giua revision {prev_rev} va {wf.revision}: "
                        "phai cap evidence_id moi (D-02)",
                    )
            else:
                seen[key] = (wf.revision, payload)


# --- V04: locator ------------------------------------------------------------


def _v04_locators(wf: Workflow, sources: dict[str, Source], report: Report) -> None:
    for ev in wf.evidence:
        path = _wf_path(wf, f"evidence[{ev.evidence_id}].locator")
        loc = ev.locator
        src = sources.get(ev.source_id)

        has_time = loc.start_ms is not None or loc.end_ms is not None
        has_text = loc.page is not None or bool(loc.text_span)
        if not has_time and not has_text:
            report.error("V04", path, "phai co it nhat mot locator dinh vi duoc")

        if has_time:
            if loc.start_ms is None or loc.end_ms is None:
                report.error("V04", path, "khoang thoi gian phai co ca start_ms va end_ms")
            elif loc.start_ms >= loc.end_ms:
                report.error("V04", path, f"can 0 <= start_ms < end_ms, dang co [{loc.start_ms}, {loc.end_ms})")
            elif src is not None and src.duration_ms is not None and loc.end_ms > src.duration_ms:
                report.error(
                    "V04",
                    path,
                    f"end_ms={loc.end_ms} vuot duration_ms={src.duration_ms} cua nguon {src.source_id}",
                )

        if src is not None and src.source_kind == SourceKind.OFFICIAL_SERVICE_VIDEO:
            if ev.modality in (Modality.VISUAL, Modality.SPEECH) and not has_time:
                report.error("V04", path, "evidence video (visual/speech) phai co moc thoi gian goc")

        if ev.modality == Modality.TEXT and not has_text:
            report.warn("V04", path, "evidence text nen co page hoac text_span")


# --- V05: FieldRef.state va claim role ---------------------------------------


def _v05_fields_and_roles(wf: Workflow, report: Report) -> None:
    claims = {c.claim_id: c for c in wf.claims}
    referenced_by_field: dict[str, list[str]] = {}
    is_real = wf.source_type == SourceType.REAL

    for step in wf.steps:
        for role in FIELD_ROLES:
            ref = getattr(step.fields, role)
            path = _wf_path(wf, f"steps[{step.step_id}].fields.{role}")

            if ref.state == FieldState.MISSING:
                if ref.claim_ids:
                    report.error("V05", path, "state=missing bat buoc claim_ids rong")
            elif not ref.claim_ids:
                report.error("V05", path, f"state={ref.state} phai co it nhat mot claim_id")

            if len(set(ref.claim_ids)) != len(ref.claim_ids):
                report.error("V05", path, "claim_ids trung lap")

            for cid in ref.claim_ids:
                referenced_by_field.setdefault(cid, []).append(role)
                claim = claims.get(cid)
                if claim is None:
                    continue
                if claim.role != role:
                    report.error(
                        "V05",
                        path,
                        f"claim {cid} co role={claim.role}, khong khop field {role}",
                    )

            if ref.state == FieldState.NOT_APPLICABLE:
                reviewed = any(
                    claims[cid].source_review == SourceReview.SOURCE_CHECKED
                    or claims[cid].technical_review == TechnicalReview.EXPERT_VALIDATED
                    for cid in ref.claim_ids
                    if cid in claims
                )
                if not reviewed:
                    msg = "state=not_applicable can human source review hoac expert review"
                    if is_real:
                        report.error("V05", path, msg)
                    else:
                        report.warn("V05", path, msg + " (bo qua tren corpus synthetic)")

    relation_claim_ids = {cid for rel in wf.relations for cid in rel.claim_ids}
    relation_condition_ids = {cid for rel in wf.relations for cid in rel.condition_claim_ids}

    for claim in wf.claims:
        path = _wf_path(wf, f"claims[{claim.claim_id}]")
        in_field = claim.claim_id in referenced_by_field
        if claim.role == ClaimRole.RELATION:
            if in_field:
                report.error("V05", path, "claim role=relation khong duoc gan vao FieldRef")
            if claim.claim_id not in relation_claim_ids:
                report.error("V05", path, "claim role=relation phai duoc mot Relation tham chieu")
        elif not in_field and claim.claim_id not in relation_condition_ids:
            report.error(
                "V05",
                path,
                "claim mo coi: khong FieldRef nao tham chieu dung role va khong phai claim dieu kien",
            )


# --- V06: claim va evidence link ---------------------------------------------


def _v06_claims_and_links(wf: Workflow, bundle: ParsedBundle, report: Report) -> None:
    evidence = {e.evidence_id: e for e in wf.evidence}

    for ev in wf.evidence:
        path = _wf_path(wf, f"evidence[{ev.evidence_id}]")
        if ev.modality == Modality.SPEECH and not ev.quote:
            report.error("V06", path, "evidence speech phai co quote nguyen van")
        if ev.modality == Modality.VISUAL and not ev.observation_note:
            report.error("V06", path, "evidence visual phai co observation_note")
        if ev.modality == Modality.VISUAL and ev.quote:
            report.warn("V06", path, "evidence visual co quote: kiem lai xem co phai loi modality")

    for claim in wf.claims:
        path = _wf_path(wf, f"claims[{claim.claim_id}]")

        if claim.evidence_type in (EvidenceKind.OBSERVED, EvidenceKind.STATED) and not claim.evidence_links:
            report.error("V06", path, f"claim {claim.evidence_type} phai co it nhat mot evidence_link")

        if claim.evidence_type == EvidenceKind.INFERRED:
            if claim.support_status == SupportStatus.SUPPORTED:
                report.warn(
                    "V06",
                    path,
                    "claim inferred dang supported: van khong duoc tra nhu tri thuc da xac nhan",
                )
            if claim.attribution.kind != AttributionKind.MODEL:
                report.warn("V06", path, "claim inferred nen co attribution.kind=model")

        seen_links: set[str] = set()
        for link in claim.evidence_links:
            if link.evidence_id in seen_links:
                report.error("V06", path, f"evidence_link trung: {link.evidence_id}")
            seen_links.add(link.evidence_id)
            if not link.explanation.strip():
                report.error("V06", path, f"evidence_link {link.evidence_id} thieu explanation")

        expected = derive_support_status(
            claim.evidence_links, has_unresolved_conflict=bool(claim.conflicts_with)
        )
        if claim.support_status != expected:
            report.error(
                "V06",
                path,
                f"support_status={claim.support_status} khong khop quy tac dan xuat D-01 "
                f"(tu evidence_links + conflicts_with => {expected})",
            )

        if claim.evidence_type == EvidenceKind.OBSERVED:
            modalities = {evidence[l.evidence_id].modality for l in claim.evidence_links if l.evidence_id in evidence}
            if modalities and Modality.VISUAL not in modalities:
                report.warn(
                    "V06",
                    path,
                    "claim observed nhung khong co evidence visual: kiem lai evidence_type",
                )

        if _HAS_DIGIT.search(claim.text):
            has_quote = any(
                evidence[l.evidence_id].quote for l in claim.evidence_links if l.evidence_id in evidence
            )
            if claim.evidence_links and not has_quote:
                report.warn(
                    "V06",
                    path,
                    "claim chua so/ma nhung khong evidence nao co quote nguyen van (D-07: ASR hay sai o day)",
                )


# --- V07: review va conflict -------------------------------------------------


def _v07_review_and_conflict(wf: Workflow, bundle: ParsedBundle, report: Report) -> None:
    claims = {c.claim_id: c for c in wf.claims}
    is_synthetic = wf.source_type == SourceType.SYNTHETIC

    events: dict[tuple[str, str, str], list] = {}
    for ev in wf.review_events:
        path = _wf_path(wf, f"review_events[{ev.review_id}]")
        allowed = (
            (ReviewDecision.SOURCE_CHECKED, ReviewDecision.REJECTED)
            if ev.dimension == ReviewDimension.SOURCE
            else (ReviewDecision.EXPERT_VALIDATED, ReviewDecision.REJECTED)
        )
        if ev.decision not in allowed:
            report.error("V07", path, f"dimension={ev.dimension} khong nhan decision={ev.decision}")
        if ev.decision == ReviewDecision.EXPERT_VALIDATED:
            if not ev.reviewer_role.strip():
                report.error("V07", path, "expert_validated bat buoc reviewer_role")
            if not (ev.note or "").strip():
                report.error("V07", path, "expert_validated bat buoc note ghi pham vi xac nhan")
        events.setdefault((ev.target_type, ev.target_id, ev.dimension), []).append(ev)

    for claim in wf.claims:
        path = _wf_path(wf, f"claims[{claim.claim_id}]")

        if claim.source_review != SourceReview.PENDING:
            decisions = {e.decision for e in events.get(("claim", claim.claim_id, "source"), [])}
            if claim.source_review not in decisions:
                report.error(
                    "V07",
                    path,
                    f"source_review={claim.source_review} nhung khong co ReviewEvent tuong ung "
                    "trong revision nay (khong tu ke thua review cu)",
                )

        if claim.technical_review in (TechnicalReview.EXPERT_VALIDATED, TechnicalReview.REJECTED):
            decisions = {e.decision for e in events.get(("claim", claim.claim_id, "technical"), [])}
            if claim.technical_review not in decisions:
                report.error(
                    "V07",
                    path,
                    f"technical_review={claim.technical_review} nhung khong co ReviewEvent technical tuong ung",
                )

        if is_synthetic:
            if claim.source_review != SourceReview.PENDING:
                report.error("V07", path, "fixture synthetic phai giu source_review=pending")
            if claim.technical_review != TechnicalReview.NOT_REQUESTED:
                report.error("V07", path, "fixture synthetic phai giu technical_review=not_requested")

        for cid in claim.conflicts_with:
            other = claims.get(cid)
            if other is not None and claim.claim_id not in other.conflicts_with:
                report.error("V07", path, f"conflicts_with phai doi xung: {cid} khong tro nguoc lai")

        if claim.conflicts_with and claim.support_status == SupportStatus.SUPPORTED:
            report.error("V07", path, "claim con conflict chua giai quyet khong duoc supported")


# --- V08: relation -----------------------------------------------------------


def _v08_relations(wf: Workflow, report: Report) -> None:
    claims = {c.claim_id: c for c in wf.claims}

    for rel in wf.relations:
        path = _wf_path(wf, f"relations[{rel.relation_id}]")

        for cid in rel.claim_ids:
            claim = claims.get(cid)
            if claim is None:
                report.error("V08", path, f"claim_ids tro toi claim khong ton tai: {cid}")
            elif claim.role != ClaimRole.RELATION:
                report.error("V08", path, f"claim {cid} phai co role=relation, dang la {claim.role}")

        for cid in rel.condition_claim_ids:
            claim = claims.get(cid)
            if claim is None:
                report.error("V08", path, f"condition_claim_ids tro toi claim khong ton tai: {cid}")
            elif claim.role != ClaimRole.CONDITION:
                report.error("V08", path, f"claim dieu kien {cid} phai co role=condition, dang la {claim.role}")

        if rel.relation_type == RelationType.BRANCH_IF and not rel.condition_claim_ids:
            report.error("V08", path, "branch_if bat buoc condition_claim_ids khong rong")

        if rel.relation_type != RelationType.BRANCH_IF and rel.condition_claim_ids:
            report.warn("V08", path, f"relation_type={rel.relation_type} co condition_claim_ids: kiem lai y dinh")

        if rel.from_step_id == rel.to_step_id:
            report.error("V08", path, "from_step_id va to_step_id trung nhau")

    _check_requires_cycle(wf, report)


def _check_requires_cycle(wf: Workflow, report: Report) -> None:
    """Chi kiem chu ky tren do thi `requires`. Thao tac lap la hop le."""
    edges: dict[str, list[str]] = {}
    for rel in wf.relations:
        if rel.relation_type == RelationType.REQUIRES:
            edges.setdefault(rel.to_step_id, []).append(rel.from_step_id)

    WHITE, GREY, BLACK = 0, 1, 2
    color: dict[str, int] = {}

    def visit(node: str, trail: list[str]) -> None:
        color[node] = GREY
        for nxt in edges.get(node, []):
            state = color.get(nxt, WHITE)
            if state == GREY:
                cycle = " -> ".join([*trail, node, nxt])
                report.error("V08", _wf_path(wf, "relations"), f"chu ky trong do thi requires: {cycle}")
            elif state == WHITE:
                visit(nxt, [*trail, node])
        color[node] = BLACK

    for node in list(edges):
        if color.get(node, WHITE) == WHITE:
            visit(node, [])


# --- V09: revision -----------------------------------------------------------


def _v09_reimport_keys(bundle: ParsedBundle, report: Report) -> None:
    seen: dict[tuple[str, int], str] = {}
    for wf in bundle.workflows:
        key = wf.key
        digest = snapshot_content_hash(wf)
        if key in seen:
            same = seen[key] == digest
            report.error(
                "V09",
                _wf_path(wf),
                "khoa (workflow_id, revision) trung trong cung bundle"
                + (" voi noi dung giong het" if same else " voi noi dung khac nhau"),
            )
        seen[key] = digest


def _v09_revision_history(wf: Workflow, report: Report) -> None:
    path = _wf_path(wf)
    if wf.revision == 1:
        if wf.supersedes_revision is not None:
            report.error("V09", path, "revision 1 phai co supersedes_revision=null")
    else:
        if wf.supersedes_revision is None:
            report.error("V09", path, f"revision {wf.revision} phai ghi supersedes_revision")
        elif wf.supersedes_revision >= wf.revision:
            report.error("V09", path, "supersedes_revision phai nho hon revision hien tai")
        if not wf.change_log:
            report.error("V09", path, f"tu revision 2 tro di phai co change_log giai thich khac biet")

    for idx, change in enumerate(wf.change_log):
        if change.previous_revision is not None and change.previous_revision >= wf.revision:
            report.error("V09", f"{path}.change_log[{idx}]", "previous_revision phai nho hon revision hien tai")


# --- V10: rut nguon / index --------------------------------------------------


def _v10_withdrawal(bundle: ParsedBundle, report: Report) -> None:
    latest: dict[str, Workflow] = {}
    for wf in bundle.workflows:
        current = latest.get(wf.workflow_id)
        if current is None or wf.revision > current.revision:
            latest[wf.workflow_id] = wf

    for wf_id, wf in latest.items():
        if wf.lifecycle == Lifecycle.WITHDRAWN:
            report.warn(
                "V10",
                _wf_path(wf),
                "latest revision withdrawn: importer phai loai TOAN BO workflow khoi RAG, "
                "khong duoc quay ve revision cu",
            )
