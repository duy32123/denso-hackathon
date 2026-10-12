"""Safe live provider availability check. Never print SDK exceptions or credentials."""
import json
import os
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from google.genai import types


def main():
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not key:
        print(json.dumps({"key_configured": False}))
        return
    client = genai.Client(api_key=key, http_options=types.HttpOptions(timeout=30000))
    results = {}
    for model in ("gemini-embedding-001", "gemini-3.5-flash-lite"):
        try:
            if "embedding" in model:
                response = client.models.embed_content(
                    model=model, contents="Maintenance source availability check",
                    config=types.EmbedContentConfig(task_type="RETRIEVAL_QUERY", output_dimensionality=768))
                results[model] = {"ok": True, "dimensions": len(response.embeddings[0].values),
                                  "metadata": response.metadata.model_dump(mode="json") if response.metadata else None}
            else:
                response = client.models.generate_content(model=model, contents="Return OK only",
                    config=types.GenerateContentConfig(temperature=0, max_output_tokens=50))
                results[model] = {"ok": True, "model_version": response.model_version,
                                  "usage": response.usage_metadata.model_dump(mode="json") if response.usage_metadata else None}
        except Exception as exc:
            results[model] = {"ok": False, "error_class": type(exc).__name__, "http_code": getattr(exc, "code", None)}
    client.close()
    destination = Path("out/benchmark_knowflow/provider_preflight.json")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(results))


if __name__ == "__main__":
    main()
