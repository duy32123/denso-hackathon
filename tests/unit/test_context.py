"""Conservative identity cues from question text: machine models and alarm codes."""

import pytest

from knowflow_contracts.models import QueryContext
from retrieval.retrieval.context import resolve_context


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
