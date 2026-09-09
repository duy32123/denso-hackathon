"""D-05 + D-06: dedup claim va rang buoc ghep quy trinh.

Thu tu bat buoc cua pipeline (D-06):

    cau hoi + metadata
      -> loc mode/split/model/subsystem
      -> workflow index -> chon workflow
      -> step index trong workflow da chon
      -> lay claim va evidence
      -> DEDUP claim  -> rerank
      -> evidence package -> LLM -> tra loi kem citation

Ham o day thuoc lop hop dong vi ca hai doi deu phai hieu giong nhau ve "hai
claim nay co phai mot khong". Cai sai o day khong lam validator do, no lam LLM
tuong mot dieu duoc nhieu nguon doc lap xac nhan.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from .models import EntityRef

ClaimKey = tuple[str, int, str]


@dataclass(frozen=True)
class ClaimHit:
    """Mot lan claim duoc tra ve tu mot step."""

    workflow_id: str
    revision: int
    claim_id: str
    step_id: str
    score: float

    @property
    def key(self) -> ClaimKey:
        return (self.workflow_id, self.revision, self.claim_id)


@dataclass
class DedupedClaim:
    workflow_id: str
    revision: int
    claim_id: str
    score: float
    matched_step_ids: list[str] = field(default_factory=list)

    @property
    def key(self) -> ClaimKey:
        return (self.workflow_id, self.revision, self.claim_id)

    def entity_ref(self) -> EntityRef:
        return EntityRef(
            workflow_id=self.workflow_id,
            revision=self.revision,
            entity_type="claim",
            entity_id=self.claim_id,
        )


def dedup_claim_hits(hits: Iterable[ClaimHit]) -> list[DedupedClaim]:
    """Gop cac lan xuat hien cua cung mot claim thanh mot muc.

    Quy tac (D-05):
    - Khoa dedup la (workflow_id, revision, claim_id). KHONG dung rieng claim_id:
      CL_001 ton tai o nhieu workflow khac nhau, va o nhieu revision khac nhau.
    - Diem = diem CAO NHAT trong cac step da khop, khong cong don. Claim xuat hien
      o nhieu step khong vi the ma dung hon.
    - Giu matched_step_ids de UI noi duoc claim nay den tu nhung buoc nao.
    - KHONG dedup theo noi dung van ban: hai claim giong het cau chu nhung khac
      nguon van phai giu rieng - do co the la hai nguon xac nhan doc lap, hoac
      hai nguon mau thuan.
    """
    merged: dict[ClaimKey, DedupedClaim] = {}

    for hit in hits:
        current = merged.get(hit.key)
        if current is None:
            merged[hit.key] = DedupedClaim(
                workflow_id=hit.workflow_id,
                revision=hit.revision,
                claim_id=hit.claim_id,
                score=hit.score,
                matched_step_ids=[hit.step_id],
            )
            continue
        current.score = max(current.score, hit.score)
        if hit.step_id not in current.matched_step_ids:
            current.matched_step_ids.append(hit.step_id)

    return sorted(merged.values(), key=lambda c: -c.score)


def procedure_workflow_key(claims: Iterable[DedupedClaim]) -> tuple[str, int] | None:
    """Khoa workflow duy nhat cua mot cau tra loi dang "quy trinh lam the nao".

    Tra None neu cac claim den tu nhieu snapshot khac nhau. Goi y cua D-06:
    khong duoc ghep step cua nhieu workflow (hoac nhieu revision) thanh mot quy
    trinh moi - do la quy trinh khong nguon nao mo ta.
    """
    keys = {(c.workflow_id, c.revision) for c in claims}
    return next(iter(keys)) if len(keys) == 1 else None


def spans_multiple_workflows(claims: Iterable[DedupedClaim]) -> bool:
    """True khi tap claim trai tren nhieu snapshot. Tap rong => False."""
    return len({(c.workflow_id, c.revision) for c in claims}) > 1
