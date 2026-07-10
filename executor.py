"""
Executor module for AutoDoc Agent.
LLM Call #2 — drafts content for each planned section.
"""

import json
import logging
import re

from models import AgentPlan, SectionContent
from llm_client import get_llm_client

logger = logging.getLogger(__name__)

# ── System Prompt for Content Generation ────────────────────────────────────

SECTION_SYSTEM_PROMPT = """You are an expert business document writer. You are drafting ONE section of a professional document.

Instructions:
1. Write clear, professional, well-structured content for the specified section.
2. If real data is unavailable, use realistic mock data — full names, specific dates, concrete numbers, and plausible details. NEVER use placeholders like "[Insert Name]" or "TBD".
3. If the section should contain structured/tabular data (like action items, risk tables, attendee lists, budget breakdowns), return BOTH:
   - A "content" field with a brief introductory paragraph.
   - A "table_data" field with a JSON array of objects, where each object is one row with consistent keys.
4. For purely narrative sections (summaries, overviews, discussion notes), return only the "content" field.

You MUST respond with ONLY valid JSON in this exact format:
{
  "content": "The narrative text for this section...",
  "table_data": [{"Column1": "value", "Column2": "value"}, ...] or null
}

Do NOT include markdown fences, explanations, or any text outside the JSON object."""


# ── JSON Extraction Helper ──────────────────────────────────────────────────

def _extract_json(text: str) -> str:
    """Extract JSON from LLM output that may include extra text."""
    # Try markdown fences first
    fence_pattern = r"```(?:json)?\s*\n?(.*?)\n?\s*```"
    match = re.search(fence_pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip()

    # Try to find a JSON object
    brace_start = text.find("{")
    brace_end = text.rfind("}")
    if brace_start != -1 and brace_end != -1 and brace_end > brace_start:
        return text[brace_start : brace_end + 1]

    return text.strip()


def _parse_section_response(raw: str, section_title: str) -> SectionContent:
    """
    Parse the LLM's response for a section into a SectionContent object.
    Falls back to using raw text as content if JSON parsing fails.
    """
    try:
        json_str = _extract_json(raw)
        data = json.loads(json_str)

        content = data.get("content", "")
        table_data = data.get("table_data", None)

        # Ensure table_data is a proper list of dicts or None
        if table_data is not None:
            if not isinstance(table_data, list):
                table_data = None
            elif len(table_data) > 0 and not isinstance(table_data[0], dict):
                table_data = None

        return SectionContent(
            title=section_title,
            content=content,
            table_data=table_data,
        )

    except (json.JSONDecodeError, KeyError, TypeError) as e:
        logger.warning(
            f"Could not parse JSON for section '{section_title}': {e}. "
            f"Using raw text as content."
        )
        # Use the raw response as plain text content
        # Strip any markdown fences if present
        clean = re.sub(r"```(?:json)?\s*", "", raw)
        clean = clean.replace("```", "").strip()
        return SectionContent(
            title=section_title,
            content=clean,
            table_data=None,
        )


# ── Public API ──────────────────────────────────────────────────────────────

def execute_plan(plan: AgentPlan, original_request: str) -> dict[str, SectionContent]:
    """
    Execute the plan by drafting content for each section via LLM calls.
    
    Args:
        plan: The validated AgentPlan from the planner.
        original_request: The user's original request (for context).
        
    Returns:
        A dictionary mapping section titles to their generated content.
    """
    llm = get_llm_client()
    sections: dict[str, SectionContent] = {}

    assumptions_text = (
        "Assumptions made: " + "; ".join(plan.assumptions)
        if plan.assumptions
        else "No specific assumptions — use realistic mock data where needed."
    )

    for i, section_title in enumerate(plan.sections, 1):
        logger.info(f"Drafting section {i}/{len(plan.sections)}: '{section_title}'")

        user_prompt = (
            f"Document type: {plan.document_type}\n"
            f"Section to write: {section_title}\n"
            f"Original user request: {original_request}\n"
            f"{assumptions_text}\n\n"
            f"Draft the '{section_title}' section now."
        )

        try:
            raw_response = llm.generate(
                system_prompt=SECTION_SYSTEM_PROMPT,
                user_prompt=user_prompt,
            )
            logger.debug(f"Raw response for '{section_title}':\n{raw_response}")

            section_content = _parse_section_response(raw_response, section_title)
            sections[section_title] = section_content

            logger.info(
                f"Section '{section_title}' drafted — "
                f"content_length={len(section_content.content)}, "
                f"has_table={'yes' if section_content.table_data else 'no'}"
            )

        except Exception as e:
            logger.error(f"Failed to draft section '{section_title}': {e}")
            # Insert placeholder so the document still gets generated
            sections[section_title] = SectionContent(
                title=section_title,
                content="[Content generation failed for this section — please fill manually]",
                table_data=None,
            )

    logger.info(f"Execution complete — {len(sections)} sections drafted.")
    return sections
