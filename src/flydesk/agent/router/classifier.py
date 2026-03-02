"""LLM-based complexity classifier for the model router."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from flydesk.agent.router.models import ClassificationResult, ComplexityTier

if TYPE_CHECKING:
    from flydesk.agent.genai_bridge import DeskAgentFactory

_logger = logging.getLogger(__name__)

_CLASSIFIER_PROMPT = """\
You are a task complexity classifier for an AI assistant. Analyze the user's \
message and context to determine which model tier should handle this request.

## Tiers
- FAST: Simple greetings, yes/no questions, basic lookups, factual recall, \
short confirmations, status checks. No tools needed or single simple tool.
- BALANCED: Standard conversations, moderate reasoning, 1-3 tool calls, \
summarization, standard Q&A with context.
- POWERFUL: Complex reasoning chains, multi-step tool orchestration (4+ tools), \
code generation/review, mathematical analysis, creative writing with specific \
constraints, ambiguous requests requiring deep analysis.

## Context
- Available tools: {tool_count}
- Tool names: {tool_names_summary}
- Conversation turns so far: {turn_count}
- Message length: {char_count} characters

## User Message
{message}

Return ONLY valid JSON (no markdown, no extra text):
{{"tier": "fast|balanced|powerful", "confidence": 0.0-1.0, "reasoning": "brief explanation"}}"""

_FALLBACK = ClassificationResult(
    tier=ComplexityTier.BALANCED,
    confidence=0.0,
    reasoning="Classification failed — using default tier",
)


class ComplexityClassifier:
    """Classifies message complexity using a cheap LLM call."""

    def __init__(
        self,
        agent_factory: DeskAgentFactory,
        classifier_model: str | None = None,
    ) -> None:
        self._agent_factory = agent_factory
        self._classifier_model = classifier_model

    async def classify(
        self,
        message: str,
        tool_count: int,
        tool_names: list[str],
        turn_count: int,
    ) -> ClassificationResult:
        """Classify a message into a complexity tier.

        Returns a safe BALANCED fallback on any failure.
        """
        try:
            return await self._do_classify(message, tool_count, tool_names, turn_count)
        except Exception:
            _logger.debug("Classifier failed, returning fallback.", exc_info=True)
            return _FALLBACK

    async def _do_classify(
        self,
        message: str,
        tool_count: int,
        tool_names: list[str],
        turn_count: int,
    ) -> ClassificationResult:
        prompt = _CLASSIFIER_PROMPT.format(
            tool_count=tool_count,
            tool_names_summary=", ".join(tool_names[:15]) or "none",
            turn_count=turn_count,
            char_count=len(message),
            message=message[:500],
        )

        agent = await self._agent_factory.create_agent(
            "You are a JSON-only classifier. Return only valid JSON.",
            model_override=self._classifier_model,
        )
        if agent is None:
            return _FALLBACK

        result = await agent.run(prompt)
        raw = str(result.output).strip()

        # Strip markdown code fences if present
        if raw.startswith("```"):
            lines = raw.split("\n")
            raw = "\n".join(
                line for line in lines if not line.strip().startswith("```")
            ).strip()

        parsed = json.loads(raw)

        tier_str = parsed.get("tier", "balanced").lower()
        try:
            tier = ComplexityTier(tier_str)
        except ValueError:
            tier = ComplexityTier.BALANCED

        confidence = float(parsed.get("confidence", 0.5))
        confidence = max(0.0, min(1.0, confidence))

        reasoning = str(parsed.get("reasoning", ""))

        return ClassificationResult(
            tier=tier,
            confidence=confidence,
            reasoning=reasoning,
        )
