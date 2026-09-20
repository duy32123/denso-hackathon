"""LLM Adapter Pattern for KnowFlow AI Extraction Pipeline.

Provides a unified interface for multiple LLM providers:
- BaseLLMAdapter: Abstract base class defining `generate_structured_output`.
- GeminiAdapter: Google Gemini API adapter using official `google-genai` SDK.
- OpenAIAdapter: OpenAI & compatible API adapter (GPT-4o, DeepSeek, local endpoints).
- LiteLLMAdapter: Optional universal proxy adapter if `litellm` is installed.
- get_llm_adapter: Factory function to resolve provider from config, env, or model name.
"""
from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from pydantic import BaseModel

logger = logging.getLogger("llm_adapters")

# Silence noisy third-party loggers
for noisy_name in ("google", "google_genai", "google.genai", "urllib3", "httpx", "httpcore"):
    logging.getLogger(noisy_name).setLevel(logging.ERROR)


class BaseLLMAdapter(ABC):
    """Abstract Base Class for LLM Adapters."""

    def __init__(self, model: str, api_key: str | None = None, temperature: float = 0.1):
        self.model = model
        self.api_key = api_key
        self.temperature = temperature

    @abstractmethod
    def generate_structured_output(
        self,
        prompt: str,
        schema_class: type[BaseModel] | None = None,
        system_instruction: str | None = None,
        image_paths: list[Path] | None = None,
    ) -> str:
        """Generates structured JSON output from LLM for the given prompt and optional images.

        Returns:
            str: Raw JSON text response from the model.
        """


class GeminiAdapter(BaseLLMAdapter):
    """Adapter for Google Gemini API using google-genai SDK (with google.generativeai fallback)."""

    DEFAULT_MODEL = "gemini-3-flash-preview"

    def __init__(self, model: str | None = None, api_key: str | None = None, temperature: float = 0.1):
        resolved_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("LLM_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not resolved_key:
            raise ValueError(
                "Không tìm thấy GEMINI_API_KEY. Vui lòng cấu hình file .env hoặc truyền api_key."
            )
        super().__init__(model=model or self.DEFAULT_MODEL, api_key=resolved_key, temperature=temperature)

    def generate_structured_output(
        self,
        prompt: str,
        schema_class: type[BaseModel] | None = None,
        system_instruction: str | None = None,
        image_paths: list[Path] | None = None,
    ) -> str:
        sys_inst = system_instruction or "You are a precise technical data extraction engine that outputs valid JSON only."

        # Load images if provided
        media_parts = []
        if image_paths:
            try:
                from PIL import Image
                for p in image_paths:
                    p_resolved = Path(p)
                    if p_resolved.is_file():
                        media_parts.append(Image.open(p_resolved))
            except ImportError:
                logger.warning("Thư viện 'pillow' (PIL) chưa được nạp. Bỏ qua ảnh đầu vào.")

        contents: Any = media_parts + [prompt] if media_parts else prompt

        try:
            # Ưu tiên SDK mới nhất: google-genai
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=self.api_key)
            response = client.models.generate_content(
                model=self.model,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=sys_inst,
                    response_mime_type="application/json",
                    temperature=self.temperature,
                ),
            )
            raw_text = response.text
        except ImportError:
            # Fallback sang google.generativeai
            import google.generativeai as genai_legacy

            genai_legacy.configure(api_key=self.api_key)
            model_obj = genai_legacy.GenerativeModel(
                model_name=self.model,
                system_instruction=sys_inst,
                generation_config={"response_mime_type": "application/json", "temperature": self.temperature},
            )
            legacy_response = model_obj.generate_content(contents)
            raw_text = legacy_response.text

        if not raw_text:
            raise ValueError(f"Gemini API ({self.model}) trả về phản hồi rỗng.")
        return raw_text


class OpenAIAdapter(BaseLLMAdapter):
    """Adapter for OpenAI and OpenAI-compatible endpoints (GPT-4o, DeepSeek, Groq, local Ollama)."""

    DEFAULT_MODEL = "gpt-4o"

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        temperature: float = 0.1,
    ):
        resolved_key = (
            api_key
            or os.getenv("OPENAI_API_KEY")
            or os.getenv("DEEPSEEK_API_KEY")
            or os.getenv("LLM_API_KEY")
        )
        if not resolved_key:
            raise ValueError(
                "Không tìm thấy OPENAI_API_KEY hoặc LLM_API_KEY. Vui lòng cấu hình file .env."
            )
        resolved_base_url = base_url or os.getenv("OPENAI_BASE_URL") or os.getenv("LLM_BASE_URL")
        self.base_url = resolved_base_url
        super().__init__(model=model or self.DEFAULT_MODEL, api_key=resolved_key, temperature=temperature)

    def generate_structured_output(
        self,
        prompt: str,
        schema_class: type[BaseModel] | None = None,
        system_instruction: str | None = None,
        image_paths: list[Path] | None = None,
    ) -> str:
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("Thư viện 'openai' chưa được cài đặt. Hãy chạy: pip install openai") from None

        sys_inst = system_instruction or "You are a precise technical data extraction engine that outputs valid JSON only."
        client = OpenAI(api_key=self.api_key, base_url=self.base_url)

        user_content: Any
        if image_paths:
            import base64
            user_content = [{"type": "text", "text": prompt}]
            for p in image_paths:
                p_path = Path(p)
                if p_path.is_file():
                    ext = p_path.suffix.lstrip(".").lower()
                    mime = "image/jpeg" if ext in ("jpg", "jpeg") else f"image/{ext}"
                    b64 = base64.b64encode(p_path.read_bytes()).decode("utf-8")
                    user_content.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime};base64,{b64}"},
                    })
        else:
            user_content = prompt

        messages: Any = [
            {"role": "system", "content": sys_inst},
            {"role": "user", "content": user_content},
        ]

        response = client.chat.completions.create(
            model=self.model,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=self.temperature,
        )

        raw_text = response.choices[0].message.content
        if not raw_text:
            raise ValueError(f"OpenAI API ({self.model}) trả về phản hồi rỗng.")
        return raw_text


class LiteLLMAdapter(BaseLLMAdapter):
    """Universal Adapter using LiteLLM (supports 100+ LLMs via unified interface)."""

    DEFAULT_MODEL = "gpt-4o"

    def __init__(self, model: str | None = None, api_key: str | None = None, temperature: float = 0.1):
        super().__init__(model=model or self.DEFAULT_MODEL, api_key=api_key, temperature=temperature)

    def generate_structured_output(
        self,
        prompt: str,
        schema_class: type[BaseModel] | None = None,
        system_instruction: str | None = None,
        image_paths: list[Path] | None = None,
    ) -> str:
        try:
            import litellm
        except ImportError:
            raise ImportError("Thư viện 'litellm' chưa được cài đặt. Hãy chạy: pip install litellm") from None

        sys_inst = system_instruction or "You are a precise technical data extraction engine that outputs valid JSON only."
        messages = [
            {"role": "system", "content": sys_inst},
            {"role": "user", "content": prompt},
        ]

        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "response_format": {"type": "json_object"},
            "temperature": self.temperature,
        }
        if self.api_key:
            kwargs["api_key"] = self.api_key

        response = litellm.completion(**kwargs)
        raw_text = response.choices[0].message.content
        if not raw_text:
            raise ValueError(f"LiteLLM ({self.model}) trả về phản hồi rỗng.")
        return raw_text


def get_llm_adapter(
    provider: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    temperature: float = 0.1,
) -> BaseLLMAdapter:
    """Factory function: resolves the appropriate LLM adapter.

    Resolution hierarchy:
        1. Explicit `provider` argument ("gemini", "openai", "deepseek", "litellm").
        2. Environment variable `LLM_PROVIDER`.
        3. Model name heuristics (e.g. starts with 'gemini', 'gpt', 'deepseek').
        4. Environment variable presence (GEMINI_API_KEY -> Gemini, OPENAI_API_KEY -> OpenAI).
    """
    selected_provider = provider or os.getenv("LLM_PROVIDER")

    if selected_provider:
        selected_provider = selected_provider.strip().lower()

    # Heuristic based on model name if provider not explicitly specified
    if not selected_provider and model:
        m_lower = model.lower()
        if "gemini" in m_lower:
            selected_provider = "gemini"
        elif "gpt" in m_lower or "o1" in m_lower or "o3" in m_lower:
            selected_provider = "openai"
        elif "deepseek" in m_lower:
            selected_provider = "openai"  # OpenAI-compatible
        elif "/" in m_lower:
            selected_provider = "litellm"

    # Heuristic based on available keys
    if not selected_provider:
        if os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"):
            selected_provider = "gemini"
        elif os.getenv("OPENAI_API_KEY"):
            selected_provider = "openai"
        else:
            # Default to gemini
            selected_provider = "gemini"

    logger.debug(f"Đã xác định LLM Provider: '{selected_provider}'")

    if selected_provider == "gemini":
        return GeminiAdapter(model=model, api_key=api_key, temperature=temperature)
    elif selected_provider in ("openai", "deepseek"):
        # Auto-configure deepseek base_url if model is deepseek and no base_url provided
        if selected_provider == "deepseek" or (model and "deepseek" in model.lower()):
            resolved_base_url = base_url or os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
            return OpenAIAdapter(model=model or "deepseek-chat", api_key=api_key, base_url=resolved_base_url, temperature=temperature)
        return OpenAIAdapter(model=model, api_key=api_key, base_url=base_url, temperature=temperature)
    elif selected_provider == "litellm":
        return LiteLLMAdapter(model=model, api_key=api_key, temperature=temperature)
    else:
        raise ValueError(
            f"Provider '{selected_provider}' không được hỗ trợ. Các lựa chọn hợp lệ: 'gemini', 'openai', 'deepseek', 'litellm'."
        )
