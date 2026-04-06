"""Gemini model client factory."""

from autogen_ext.models.openai import OpenAIChatCompletionClient


def make_client(
    model: str,
    api_key: str,
    temperature: float = 0.70,
    function_calling: bool = False,
) -> OpenAIChatCompletionClient:
    return OpenAIChatCompletionClient(
        model=model,
        api_key=api_key,
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        temperature=temperature,
        model_capabilities={"vision": False, "function_calling": function_calling, "json_output": False},
    )
