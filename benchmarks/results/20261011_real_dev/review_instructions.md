# Chấm nghĩa độc lập

Không sửa gold hoặc sinh lại đáp án. Đối chiếu `rows.jsonl`, câu hỏi, điều kiện và nguồn nguyên bản.

- Mỗi verdict phải giữ `arm`, `question_id`, `answer_sha256`; đáp án đổi thì verdict stale.
- Điền `reviewer_kind=human` chỉ khi người thật tự đối chiếu nguồn. AI hỗ trợ phải ghi `ai`, tách riêng.
- Điền reviewer, thời điểm, answers_question / conditions_correct / source_supported bằng true hoặc false.
- citations_supported_json là mảng true/false có đúng số phần tử và thứ tự citation; điền note cho lỗi.
- Xem file transcript/source ở audit.json và mốc thời gian hoặc char offset trong sources_json; không chỉ đọc claim.
- Bước verify bằng Gemini là bộ phận hệ thống đang đo, không được tính làm người chấm.
- Citation hợp lệ theo code không chứng minh câu trả lời được nguồn hỗ trợ về nghĩa.
- Với lỗi API, không chấm nghĩa một đáp án không tồn tại; giữ lỗi trong mẫu số 66.
