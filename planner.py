"""
Planner module for AutoDoc Agent.
LLM Call #1 — generates a structured task plan from a natural language request.
"""

import json
import logging
import re

from models import AgentPlan, PlanStep
from llm_client import get_llm_client

logger = logging.getLogger(__name__)

# ── System Prompt for Planning ──────────────────────────────────────────────

PLANNER_SYSTEM_PROMPT = """You are an expert document planning agent. Your job is to analyze a user's request and produce a structured plan for generating a business document.

You MUST respond with ONLY valid JSON — no markdown, no explanation, no extra text.

The JSON must follow this exact schema:
{
  "document_type": "string — the type of document (e.g. Meeting Minutes, Status Report, Project Proposal, Technical Specification)",
  "sections": ["string — ordered list of section titles to include in the document"],
  "assumptions": ["string — any assumptions you made because the user's request was vague or missing details"],
  "steps": [
    {
      "step_number": 1,
      "action": "string — what to do in this step",
      "section_title": "string or null — which section this step produces"
    }
  ]
}

Rules:
1. ALWAYS infer a document_type, even if the user doesn't specify one. Pick the most appropriate business document format.
2. sections MUST have at least 2 entries.
3. If the user's request is vague or missing details (names, dates, project details), note each assumption in the assumptions array.
4. Steps should be logical and ordered: first identify metadata, then draft each section.
5. Use realistic, professional section titles appropriate for the document type.
6. Respond with ONLY the JSON object — no markdown fences, no commentary."""


# ── Default Fallback Plan ───────────────────────────────────────────────────

def _default_plan(request: str) -> AgentPlan:
    """Fallback plan when LLM output is malformed or validation fails."""
    logger.warning("Using default fallback plan due to LLM output failure.")
    return AgentPlan(
        document_type="Business Document",
        sections=["Executive Summary", "Details", "Recommendations", "Conclusion"],
        assumptions=[
            "LLM planning output was malformed — using a generic document structure.",
            "Document type could not be inferred — defaulting to 'Business Document'.",
        ],
        steps=[
            PlanStep(step_number=1, action="Generate executive summary", section_title="Executive Summary"),
            PlanStep(step_number=2, action="Draft main details", section_title="Details"),
            PlanStep(step_number=3, action="Draft recommendations", section_title="Recommendations"),
            PlanStep(step_number=4, action="Draft conclusion", section_title="Conclusion"),
        ],
    )


# ── JSON Extraction Helper ──────────────────────────────────────────────────

def _extract_json(text: str) -> str:
    """
    Extract JSON from LLM output that may be wrapped in markdown fences
    or contain extra text before/after the JSON block.
    """
    # Try to find JSON inside markdown code fences
    fence_pattern = r"```(?:json)?\s*\n?(.*?)\n?\s*```"
    match = re.search(fence_pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip()

    # Try to find a JSON object directly
    brace_start = text.find("{")
    brace_end = text.rfind("}")
    if brace_start != -1 and brace_end != -1 and brace_end > brace_start:
        return text[brace_start : brace_end + 1]

    # Return as-is and let json.loads handle the error
    return text.strip()


# ── Public API ──────────────────────────────────────────────────────────────

def generate_plan(request: str) -> AgentPlan:
    """
    Generate a structured task plan from a natural language request.
    
    1. Sends the request to the LLM with planning instructions.
    2. Parses the JSON response into an AgentPlan.
    3. Validates required fields.
    4. Falls back to a default plan on any failure.
    
    Args:
        request: The user's natural language request.
        
    Returns:
        A validated AgentPlan ready for execution.
    """
    llm = get_llm_client()

    try:
        # ── LLM Call #1: Generate the plan ──────────────────────────────
        logger.info("Generating plan via LLM...")
        raw_response = llm.generate(
            system_prompt=PLANNER_SYSTEM_PROMPT,
            user_prompt=f"User request: {request}",
        )
        logger.info(f"Raw planner response:\n{raw_response}")

        # ── Extract and parse JSON ──────────────────────────────────────
        json_str = _extract_json(raw_response)
        plan_data = json.loads(json_str)

        # ── Validate with Pydantic ──────────────────────────────────────
        plan = AgentPlan(**plan_data)

        # ── Guardrail checks ────────────────────────────────────────────
        if not plan.document_type.strip():
            logger.warning("Plan has empty document_type — using fallback.")
            return _default_plan(request)

        if len(plan.sections) == 0:
            logger.warning("Plan has no sections — using fallback.")
            return _default_plan(request)

        logger.info(
            f"Plan generated successfully: "
            f"type='{plan.document_type}', "
            f"sections={len(plan.sections)}, "
            f"assumptions={len(plan.assumptions)}"
        )
        return plan

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM JSON output: {e}")
        return _default_plan(request)

    except Exception as e:
        logger.error(f"Planning failed with error: {e}")
        return _default_plan(request)
