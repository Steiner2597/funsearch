"""Prompt templates for LLM-guided heuristics."""

from __future__ import annotations

import textwrap
from collections.abc import Iterable
from typing import Literal


_SIGNATURE = "def score_bin(item_size, remaining_capacity, bin_index, step) -> float:"

VariantType = Literal["A", "B"]


def _base_context() -> str:
    return textwrap.dedent(
        f"""
        You are designing a Python scoring heuristic for online bin packing.

        Context:
        - Items arrive one by one.
        - For each item, we score every existing bin.
        - The bin with the highest score is chosen; if no bin fits, a new bin is opened.
        - The function must be fast, deterministic, and return a finite numeric score.

        Required function signature:
        {_SIGNATURE}

        Return ONLY the function code inside a Python code block. No explanations.
        """
    ).strip()


class PromptTemplate:
    def generate_fresh_candidate(self) -> str:
        prompt = "\n\n".join(
            [
                _base_context(),
                "Write a brand-new heuristic that balances packing tightness and future flexibility.",
                "Output format:\n```python\n<function code>\n```",
            ]
        )
        return prompt

    def mutate_candidate(self, parent_code: str) -> str:
        prompt = "\n\n".join(
            [
                _base_context(),
                "Mutate the existing heuristic below to create a potentially better variant.",
                "Keep the same signature and return type. Make a meaningful change.",
                "Parent code:\n```python\n"
                + parent_code.strip()
                + "\n```",
                "Output format:\n```python\n<mutated function code>\n```",
            ]
        )
        return prompt

    def refine_candidate(self, best_codes: Iterable[str], failure_modes: Iterable[str]) -> str:
        code_block = "\n\n".join(
            f"Candidate {index + 1}:\n```python\n{code.strip()}\n```"
            for index, code in enumerate(best_codes)
        )
        failures = "\n".join(f"- {mode}" for mode in failure_modes)
        prompt = "\n\n".join(
            [
                _base_context(),
                "Refine the heuristic using the strongest parts of the candidates below.",
                "Address the listed failure modes explicitly in the scoring logic.",
                f"Top candidates:\n{code_block}" if code_block else "Top candidates: (none)",
                f"Failure modes:\n{failures}" if failures else "Failure modes: (none)",
                "Output format:\n```python\n<refined function code>\n```",
            ]
        )
        return prompt


class NoveltyPromptTemplate(PromptTemplate):
    """Variant B: Emphasizes novelty and unconventional approaches."""

    def _novelty_context(self) -> str:
        return textwrap.dedent(
            """
            IMPORTANT: Be CREATIVE and UNCONVENTIONAL.
            - Avoid standard best-fit or first-fit patterns
            - Try unusual mathematical functions (trigonometric, logarithmic, polynomial)
            - Consider counterintuitive strategies that might work
            - Experiment with non-obvious scoring factors
            """
        ).strip()

    def generate_fresh_candidate(self) -> str:
        prompt = "\n\n".join(
            [
                _base_context(),
                self._novelty_context(),
                "Write a NOVEL heuristic using unconventional mathematics or counterintuitive logic.",
                "Output format:\n```python\n<function code>\n```",
            ]
        )
        return prompt

    def mutate_candidate(self, parent_code: str) -> str:
        prompt = "\n\n".join(
            [
                _base_context(),
                self._novelty_context(),
                "Radically transform the heuristic below. Don't make small tweaks - try a completely different approach.",
                "Parent code:\n```python\n"
                + parent_code.strip()
                + "\n```",
                "Output format:\n```python\n<mutated function code>\n```",
            ]
        )
        return prompt

    def refine_candidate(self, best_codes: Iterable[str], failure_modes: Iterable[str]) -> str:
        code_block = "\n\n".join(
            f"Candidate {index + 1}:\n```python\n{code.strip()}\n```"
            for index, code in enumerate(best_codes)
        )
        failures = "\n".join(f"- {mode}" for mode in failure_modes)
        prompt = "\n\n".join(
            [
                _base_context(),
                self._novelty_context(),
                "Create a HYBRID that combines the most unusual and effective ideas from these candidates.",
                f"Top candidates:\n{code_block}" if code_block else "Top candidates: (none)",
                f"Failure modes:\n{failures}" if failures else "Failure modes: (none)",
                "Output format:\n```python\n<refined function code>\n```",
            ]
        )
        return prompt


def get_prompt_template(variant: VariantType | None = None) -> PromptTemplate:
    """Get prompt template for the specified variant."""
    if variant == "B":
        return NoveltyPromptTemplate()
    return PromptTemplate()
