"""Thin wrapper around the Anthropic SDK for the one thing this agent needs:
send a prompt, get back generated code as text.

Credential resolution is left entirely to the SDK (ANTHROPIC_API_KEY env var,
or an `ant auth login` profile) -- this module never asks for or handles a
raw key itself.
"""

from __future__ import annotations

import re

import anthropic

import config


class CodeGenerationError(RuntimeError):
    """Raised when Claude can't be reached, or its reply has no code block."""


def get_client() -> anthropic.Anthropic:
    return anthropic.Anthropic()


def generate_code(client: anthropic.Anthropic, system: str, user_prompt: str) -> str:
    """Send one request to Claude and return the extracted Python source.

    Raises CodeGenerationError on any API failure or on a reply that doesn't
    contain a fenced ```python block, so the caller can decide whether to
    retry.
    """
    try:
        response = client.messages.create(
            model=config.MODEL_ID,
            max_tokens=config.MAX_TOKENS,
            system=system,
            thinking={"type": "adaptive"},
            output_config={"effort": config.EFFORT},
            messages=[{"role": "user", "content": user_prompt}],
        )
    except anthropic.AuthenticationError as exc:
        raise CodeGenerationError(
            "Anthropic API authentication failed -- set ANTHROPIC_API_KEY "
            "or run `ant auth login`."
        ) from exc
    except anthropic.RateLimitError as exc:
        retry_after = exc.response.headers.get("retry-after", "a while") if exc.response else "a while"
        raise CodeGenerationError(f"Rate limited by the API; retry after {retry_after}.") from exc
    except anthropic.APIConnectionError as exc:
        raise CodeGenerationError(f"Network error reaching the Anthropic API: {exc}") from exc
    except anthropic.APIStatusError as exc:
        raise CodeGenerationError(f"Anthropic API error ({exc.status_code}): {exc.message}") from exc

    if response.stop_reason == "refusal":
        category = getattr(response.stop_details, "category", None)
        raise CodeGenerationError(f"Claude declined the request (category: {category}).")

    text = "".join(block.text for block in response.content if block.type == "text")
    return _extract_code_block(text)


def _extract_code_block(text: str) -> str:
    match = re.search(r"```python\s*\n(.*?)```", text, re.DOTALL)
    if not match:
        match = re.search(r"```\s*\n(.*?)```", text, re.DOTALL)
    if not match:
        raise CodeGenerationError(
            "Claude's reply did not contain a fenced code block:\n" + text[:1000]
        )
    return match.group(1).strip() + "\n"
