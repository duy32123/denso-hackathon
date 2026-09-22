"""Conservative identity cues, controlled subsystem aliases and hard context gates."""

import pytest

from knowflow_contracts.models import QueryContext, Workflow
from retrieval.retrieval.context import context_gate, normal, resolve_context


DOUBLE_ARM_SUBSYSTEM = "side-mount tool changer (SMTC), double arm"


@pytest.fixture
def double_arm_workflow(f01):
    workflow = Workflow.model_validate(f01["workflows"][0])
    return workflow.model_copy(update={
        "context": workflow.context.model_copy(update={"subsystem": DOUBLE_ARM_SUBSYSTEM, "machine_model": None}),
    })


@pytest.mark.parametrize("alias", [
    "SMTC", "Side Mount Tool Changer", "side-mount tool changer (SMTC)",
    "SMTC, double arm", "side-mount tool changer, double arm", DOUBLE_ARM_SUBSYSTEM,
])
def test_smtc_component_qualified_alias(alias, double_arm_workflow):
    assert normal("subsystem", alias) == "smtc"
    assert context_gate(double_arm_workflow, QueryContext(subsystem=alias)) == ([], [])
    # Resolving identity never edits the source metadata.
    assert double_arm_workflow.context.subsystem == DOUBLE_ARM_SUBSYSTEM


@pytest.mark.parametrize("subsystem", [
    "umbrella tool changer", "umbrella SMTC", "double arm",
    "SMTC unknown variant", "side-mount tool changer (SMTC), umbrella",
])
def test_smtc_alias_does_not_swallow_other_subsystems(subsystem, double_arm_workflow):
    assert normal("subsystem", subsystem) != "smtc"
    assert context_gate(double_arm_workflow, QueryContext(subsystem=subsystem)) == (["subsystem"], [])


@pytest.mark.parametrize("provided", [QueryContext(), QueryContext(subsystem="SMTC")])
def test_full_smtc_label_and_acronym_are_not_conflicting(provided, double_arm_workflow):
    context, conflicts, _ = resolve_context(
        f"Inspect the {DOUBLE_ARM_SUBSYSTEM}", provided, [double_arm_workflow],
    )
    assert conflicts == []
    assert context_gate(double_arm_workflow, context) == ([], [])


def test_smtc_alias_keeps_missing_model_guard(double_arm_workflow):
    assert context_gate(double_arm_workflow, QueryContext(subsystem="SMTC", machine_model="VF-2")) == (
        [], ["machine_model"],
    )


def resolve(question):
    return resolve_context(question, QueryContext(), [])


@pytest.mark.parametrize("question,models", [
    ("Thay hốc dao cho máy VF-2", ["vf-2"]),
    ("umc 750 spindle", ["umc 750"]),
    ("EC-400 pallet changer", ["ec-400"]),
    ("st10 lathe", ["st10"]),
    ("Kiểm tra nguồn DC 24 V", None),   # a voltage, not a machine
    ("ST 10 lathe", None),               # short prefix must touch the number
])
def test_machine_model_detection(question, models):
    assert resolve(question)[2].get("machine_model") == models


@pytest.mark.parametrize("question,codes", [
    ("Báo lỗi 2066 khi thay dao?", ["2066"]),
    ("Máy báo lỗi 2066.", ["2066"]),      # sentence dot is not part of the code
    ("mã lỗi số 108", ["108"]),
    ("loi 2066 khi thay dao", ["2066"]),
    ("alarm code: 2066", ["2066"]),
    ("Alarm #102", ["102"]),
    ("Đi theo lối 2 bên máy", []),
    ("Lời 3 trong video", []),
    ("lợi 2 lần", []),
])
def test_alarm_code_detection(question, codes):
    assert resolve(question)[0].alarm_codes == codes
