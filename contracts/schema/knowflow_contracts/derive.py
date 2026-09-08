"""D-01: quy tac dan xuat Claim.support_status tu EvidenceLink.

Ban DOCX chi noi support_status la "danh gia tong hop" ma khong cho quy tac.
Neu de moi doi tu tinh, hai ben se lech nhau va validator khong bat duoc.
Quy tac duoi day la mot lua chon co chu dich, kiem bang code:

    1. Vua co link `supported` vua co link `contradicted` -> ambiguous
       (nguon canh tranh, khong duoc im lang chon mot ben).
    2. Co `contradicted` -> contradicted.
    3. Co `ambiguous` -> ambiguous.
    4. Co `supported` -> supported.
    5. Con lai (rong hoac toan `insufficient`) -> insufficient.

Cong them: claim con conflict chua giai quyet (`conflicts_with` khong rong)
khong bao gio duoc `supported` (muc 5 cua Schema chung) -> ha xuong ambiguous.
"""

from __future__ import annotations

from collections.abc import Iterable

from .enums import SupportStatus
from .models import EvidenceLink


def derive_support_status(
    evidence_links: Iterable[EvidenceLink | dict],
    *,
    has_unresolved_conflict: bool = False,
) -> SupportStatus:
    statuses = set()
    for link in evidence_links:
        raw = link["support_status"] if isinstance(link, dict) else link.support_status
        statuses.add(SupportStatus(raw))

    if SupportStatus.SUPPORTED in statuses and SupportStatus.CONTRADICTED in statuses:
        result = SupportStatus.AMBIGUOUS
    elif SupportStatus.CONTRADICTED in statuses:
        result = SupportStatus.CONTRADICTED
    elif SupportStatus.AMBIGUOUS in statuses:
        result = SupportStatus.AMBIGUOUS
    elif SupportStatus.SUPPORTED in statuses:
        result = SupportStatus.SUPPORTED
    else:
        result = SupportStatus.INSUFFICIENT

    if has_unresolved_conflict and result == SupportStatus.SUPPORTED:
        return SupportStatus.AMBIGUOUS
    return result
