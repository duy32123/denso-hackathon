"""WP1 search text v1: preserve claim text, attribution and scope verbatim."""

from knowflow_contracts.models import Claim, Step, Workflow
from knowflow_contracts.search import (
    ClaimReviewFlag, IndexBuild, SearchMetadata, SearchText,
    StepSearchRecord, WorkflowSearchRecord,
)

TEXT_TEMPLATE_VERSION = "wp1-original-1"


def _flag(claim: Claim) -> ClaimReviewFlag:
    return ClaimReviewFlag(
        **claim.model_dump(include={
            "claim_id", "evidence_type", "support_status", "source_review", "technical_review",
        }),
        has_unresolved_conflict=bool(claim.conflicts_with),
    )


def _claim_text(claim: Claim) -> str:
    return "\n".join([
        f"{claim.role}: {claim.text}",
        f"attribution: {claim.attribution.model_dump_json()}",
        f"scope: {claim.scope.model_dump_json()}",
    ])


def _step_claim_ids(workflow: Workflow, step: Step) -> list[str]:
    ids = [cid for field in step.fields.model_dump().values() for cid in field["claim_ids"]]
    # Keep actual relation claims/conditions, without inventing dependencies.
    for relation in workflow.relations:
        if step.step_id in (relation.from_step_id, relation.to_step_id):
            ids.extend(relation.claim_ids)
            ids.extend(relation.condition_claim_ids)
    return list(dict.fromkeys(ids))


def build_records(
    workflow: Workflow, build: IndexBuild,
) -> list[WorkflowSearchRecord | StepSearchRecord]:
    """Keep all review flags, including conflicts; eligibility is a WP2 query gate."""
    metadata = SearchMetadata.model_validate(
        workflow.context.model_dump(exclude={"metadata_provenance"})
    )
    common = dict(
        workflow_id=workflow.workflow_id, revision=workflow.revision,
        source_type=workflow.source_type, dataset_split=workflow.dataset_split,
        lifecycle=workflow.lifecycle, language=workflow.language,
        source_ids=workflow.source_ids, metadata=metadata, build=build,
    )
    context_text = f"context: {metadata.model_dump_json()}"
    records = [WorkflowSearchRecord(
        **common, title=workflow.title, step_count=len(workflow.steps),
        claim_review_flags=[_flag(c) for c in workflow.claims],
        text=SearchText(search_text_original="\n".join([
            workflow.title, context_text, *(_claim_text(c) for c in workflow.claims),
        ])),
    )]
    claims = {c.claim_id: c for c in workflow.claims}
    for step in sorted(workflow.steps, key=lambda s: (s.display_order, s.step_id)):
        ids = _step_claim_ids(workflow, step)
        records.append(StepSearchRecord(
            **common, step_id=step.step_id, display_order=step.display_order,
            title=step.title, claim_ids=ids,
            claim_review_flags=[_flag(claims[cid]) for cid in ids],
            text=SearchText(search_text_original="\n".join([
                workflow.title, step.title, context_text,
                *(_claim_text(claims[cid]) for cid in ids),
            ])),
        ))
    return records
