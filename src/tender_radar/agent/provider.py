"""LLM provider abstraction: the loop sees this protocol, never a vendor SDK.

Swapping Gemini for another model means writing one new class with the same
three-method surface — the loop and the evals don't change.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class ToolCall:
    name: str
    arguments: dict[str, Any]


@dataclass
class ModelTurn:
    """One model response: either tool calls to execute, or the final text."""

    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    raw: Any = None  # provider-native content, echoed back on the next turn


class LLMProvider(Protocol):
    def generate(
        self,
        system: str,
        history: list[Any],
        tools: list[dict[str, Any]],
    ) -> ModelTurn: ...

    def user_message(self, text: str) -> Any: ...

    def tool_results(self, turn: ModelTurn, results: list[tuple[str, str]]) -> list[Any]: ...


def _clean_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Strip JSON-Schema keys Gemini's function declarations reject."""
    allowed = {"type", "description", "properties", "items", "enum", "required", "format"}
    cleaned = {}
    for key, value in schema.items():
        if key not in allowed:
            continue
        if key == "properties":
            cleaned[key] = {name: _clean_schema(sub) for name, sub in value.items()}
        elif key == "items":
            cleaned[key] = _clean_schema(value)
        elif key == "type" and isinstance(value, list):
            cleaned[key] = next((t for t in value if t != "null"), "string")
        else:
            cleaned[key] = value
    # anyOf/unions collapse to string: good enough for tool arguments
    if "type" not in cleaned and "enum" not in cleaned:
        cleaned["type"] = "string"
    return cleaned


class GeminiProvider:
    """Gemini Flash on the free tier, via google-genai."""

    def __init__(self, model: str = "gemini-flash-latest", api_key: str | None = None):
        from google import genai

        self._client = genai.Client(api_key=api_key or os.environ.get("GEMINI_API_KEY"))
        self._model = model

    def generate(self, system: str, history: list[Any], tools: list[dict[str, Any]]) -> ModelTurn:
        from google.genai import types

        declarations = [
            types.FunctionDeclaration(
                name=tool["name"],
                description=tool.get("description", ""),
                parameters=_clean_schema(tool.get("inputSchema") or {"type": "object"}),
            )
            for tool in tools
        ]
        response = self._client.models.generate_content(
            model=self._model,
            contents=history,
            config=types.GenerateContentConfig(
                system_instruction=system,
                tools=[types.Tool(function_declarations=declarations)],
                temperature=0.0,
            ),
        )
        candidate = response.candidates[0]
        calls = [
            ToolCall(name=part.function_call.name, arguments=dict(part.function_call.args or {}))
            for part in candidate.content.parts or []
            if part.function_call
        ]
        return ModelTurn(text=response.text or "", tool_calls=calls, raw=candidate.content)

    def user_message(self, text: str) -> Any:
        from google.genai import types

        return types.Content(role="user", parts=[types.Part.from_text(text=text)])

    def tool_results(self, turn: ModelTurn, results: list[tuple[str, str]]) -> list[Any]:
        from google.genai import types

        parts = [
            types.Part.from_function_response(name=name, response={"result": payload})
            for name, payload in results
        ]
        return [turn.raw, types.Content(role="user", parts=parts)]
