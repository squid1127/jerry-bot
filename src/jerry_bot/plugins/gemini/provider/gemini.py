"""Gemini provider for the Gemini plugin."""

from typing import AsyncIterator

from google.genai import Client, types
from google.genai.errors import ClientError

from .base import Provider
from ..models import (
    FunctionCall,
    LLMContext,
    ModelContextRole,
    LLMResponseStream,
)
from ..config import ProviderConfig
from ..models.exceptions import ProviderAPIError


class GeminiProvider(Provider):
    """Provider implementation for Gemini LLMs."""

    def __init__(self, provider_config: ProviderConfig, name: str):
        super().__init__(provider_config, name)
        self.client = Client(api_key=provider_config.api_key)

    @staticmethod
    def _build_contents(context: LLMContext) -> list[types.Content]:
        """Convert model context messages into Gemini API content objects."""
        contents: list[types.Content] = []
        for msg in context.messages:
            role = "user" if msg.role == ModelContextRole.USER else "model"
            contents.append(
                types.Content(role=role, parts=[types.Part.from_text(text=msg.content)])
            )
        return contents

    @staticmethod
    def _build_config(context: LLMContext) -> types.GenerateContentConfig:
        """Build Gemini generation config from model context settings."""
        return types.GenerateContentConfig(
            system_instruction=context.prompt or None,
            temperature=context.profile.temperature,
            max_output_tokens=context.profile.max_tokens,
            top_k=context.profile.top_k,
            top_p=context.profile.top_p,
        )

    @staticmethod
    def _normalize_function_args(raw_args: object) -> dict:
        """Normalize Gemini function-call args into a plain dictionary."""
        if isinstance(raw_args, dict):
            return raw_args
        if raw_args is None:
            return {}

        try:
            return dict(raw_args)  # type: ignore[arg-type]
        except Exception:
            return {"_raw": str(raw_args)}

    @classmethod
    def _extract_function_call_from_part(cls, part: object) -> FunctionCall | None:
        """Convert one chunk part into a FunctionCall when possible."""
        function_call = getattr(part, "function_call", None)
        if function_call is None:
            return None

        name = getattr(function_call, "name", None)
        if not name:
            return None

        arguments = cls._normalize_function_args(getattr(function_call, "args", None))
        return FunctionCall(name=name, arguments=arguments)

    @staticmethod
    def _extract_function_calls(chunk: object) -> list[FunctionCall]:
        """Extract structured function-call requests from a Gemini stream chunk."""
        extracted: list[FunctionCall] = []
        candidates = getattr(chunk, "candidates", None) or []
        for candidate in candidates:
            content = getattr(candidate, "content", None)
            parts = getattr(content, "parts", None) or []
            for part in parts:
                function_call = GeminiProvider._extract_function_call_from_part(part)
                if function_call is not None:
                    extracted.append(function_call)

        return extracted

    async def generate(self, context: LLMContext) -> AsyncIterator[LLMResponseStream]:
        """Generate a response from the Gemini model based on the provided context."""
        contents = self._build_contents(context)
        config = self._build_config(context)

        try:
            async for chunk in await self.client.aio.models.generate_content_stream(  # type: ignore[misc]
                model=context.profile.name,
                contents=contents,
                config=config,
            ):
                if chunk.text:
                    yield LLMResponseStream(content=chunk.text)

                for function_call in self._extract_function_calls(chunk):
                    yield LLMResponseStream(function_call=function_call)
        except Exception as e:
            raise ProviderAPIError(f"Gemini API error: {e}")

    async def model_exists(self, model_name: str) -> bool:
        """Check if a model with the given name exists in Gemini."""
        try:
            await self.client.aio.models.get(model=model_name)
            return True
        except ClientError as e:
            normalized_model_name = (
                model_name
                if model_name.startswith("models/")
                else f"models/{model_name}"
            )
            error_text = str(e)

            # Only treat Gemini's explicit 404 model-not-found response as "does not exist".
            if (
                getattr(e, "code", None) == 404
                and "Model is not found:" in error_text
                and normalized_model_name in error_text
            ):
                return False

            raise ProviderAPIError(
                f"Error checking model existence for '{model_name}': {e}"
            ) from e
        except Exception as e:
            raise ProviderAPIError(
                f"Unexpected error checking model existence for '{model_name}': {e}"
            ) from e
