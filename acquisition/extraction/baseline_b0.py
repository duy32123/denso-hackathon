import json
import os
import sys
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

def load_json(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def run_b0_extraction(transcript_path: str, metadata_path: str, source_id: str, output_path: str):
    api_key = os.getenv("LLM_API_KEY")
    if not api_key:
        print("ERROR: Không tìm thấy LLM_API_KEY trong file .env.")
        print("Vui lòng cấu hình file .env trước khi chạy.")
        sys.exit(1)

    transcript_data = load_json(transcript_path)
    utterances = transcript_data.get("utterances", [])
    
    metadata = {}
    with open(metadata_path, 'r', encoding='utf-8') as f:
        for line in f:
            record = json.loads(line)
            if record.get("source_id") == source_id:
                metadata = record
                break

    formatted_transcript = "".join(
        f"[{source_id}:U{i+1:04d}] ({u['start_ms']} - {u['end_ms']}): {u['text']}\n" 
        for i, u in enumerate(utterances)
    )

    prompt = f"""
    Bạn là một chuyên gia phân tích tài liệu kỹ thuật bảo trì thiết bị.
    Hãy đọc Transcript và Metadata dưới đây để trích xuất thành Draft JSON chuẩn schema 1.0.0.
    
    Source ID: {source_id}
    Title: {metadata.get('title', 'Unknown')}
    
    Transcript:
    {formatted_transcript}
    """
    
    print(f"🚀 Đang kết nối tới LLM API để trích xuất {source_id}...")
    
    try:
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a precise technical data extraction engine that outputs valid JSON only."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )
        
        draft_json = response.choices[0].message.content
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(draft_json)
            
        print(f"✅ Trích xuất tự động thành công! File lưu tại: {output_path}")
        
    except Exception as e:
        print(f"❌ Lỗi khi gọi LLM API: {e}")
        sys.exit(1)

if __name__ == "__main__":
    run_b0_extraction(
        transcript_path="acquisition/preprocessing/transcripts/SRC_HAAS_0005/corrected.json",
        metadata_path="data/sources/haas_pilot_sources.jsonl",
        source_id="SRC_HAAS_0005",
        output_path="acquisition/extraction/drafts/SRC_HAAS_0005.draft.json"
    )