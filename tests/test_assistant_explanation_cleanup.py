"""The assistant's explanation must not echo its own prompt or repeat itself.

The console rendered raw model output, and the bundled small model restated the
structured finding summary it was given and then repeated whole passages, so the
finding pane showed a wall of duplicated prose.
"""

from __future__ import annotations

import pytest

from webui.assistant import _tidy_explanation


def test_echoed_summary_fields_are_removed() -> None:
    text = (
        "Severity: low Status: open Affected component: Prompt layer "
        "Recommendation: Separate trusted instructions. "
        "The agent does not isolate retrieved content."
    )

    cleaned = _tidy_explanation(text)

    assert cleaned == "The agent does not isolate retrieved content."


def test_repeated_bullets_appear_once() -> None:
    text = (
        "Likely causes: • The agent is not configured. • Retrieval is unrestricted. "
        "Possible threats: • The agent is not configured. • Retrieval is unrestricted."
    )

    cleaned = _tidy_explanation(text)

    assert cleaned.count("The agent is not configured") == 1
    assert cleaned.count("Retrieval is unrestricted") == 1


def test_repeated_sentences_appear_once() -> None:
    text = "The attacker can bypass controls. The attacker can bypass controls. It is medium severity."

    assert _tidy_explanation(text) == "The attacker can bypass controls. It is medium severity."


def test_a_lead_in_with_no_surviving_list_is_dropped() -> None:
    text = "Causes: • One thing. Threats: • One thing."

    assert _tidy_explanation(text) == "Causes: One thing."


def test_output_that_is_only_an_echo_is_returned_unchanged() -> None:
    """Filtering may only remove noise, never leave the reviewer with nothing."""
    assert _tidy_explanation("Severity: low") == "Severity: low"


@pytest.mark.parametrize("value", ["", "   ", None])
def test_empty_input_stays_empty(value) -> None:
    assert _tidy_explanation(value) == ""


def test_a_clean_explanation_is_left_alone() -> None:
    text = "The prompt boundary is not enforced. Review the system prompt and retrieval isolation."

    assert _tidy_explanation(text) == text
