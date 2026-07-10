# AutoDoc Agent — Autonomous Document Generation Agent

An autonomous AI agent that takes a natural language request, plans its own
execution steps, generates content using an LLM, and produces a polished
Microsoft Word (.docx) business document — end to end, with no human
intervention beyond the initial request.

## Overview

AutoDoc Agent exposes a single REST endpoint (`POST /agent`) that accepts a
free-text request (e.g. "Create meeting minutes for a project kickoff") and
returns:
- The document type the agent inferred
- The task plan the agent generated for itself
- Any assumptions it made to fill gaps in the request
- A path to the generated `.docx` file

The agent handles both clear, well-specified requests and ambiguous,
under-specified ones — deciding on document structure itself when the user
doesn't provide one.

## Architecture

```
main.py         FastAPI app, exposes POST /agent
planner.py      LLM call #1 — generates a structured task plan (JSON)
executor.py     Loops through plan, LLM call(s) #2 — drafts content per section
docgen.py       Converts content dict into a formatted .docx via python-docx
llm_client.py   Thin wrapper around the LLM provider (Ollama / Groq / Gemini)
models.py       Pydantic schemas for request/response/plan validation
config.py       Settings and environment variable loading
outputs/        Generated Word documents land here
tests/          Test script with both test cases
```

### Workflow

1. **Receive request** — `POST /agent` with `{"request": "<text>"}`
2. **Plan** — LLM is prompted to return a JSON task list: document type,
   required sections, and any assumptions needed to proceed.
3. **Validate** — Plan is checked for well-formed JSON and required fields;
   falls back to a default plan on failure.
4. **Execute** — Each planned section is drafted by the LLM. Mock data is
   used for facts not provided by the user (names, dates, figures).
5. **Generate document** — `python-docx` assembles the drafted content into
   a formatted Word file (headings, paragraphs, tables).
6. **Respond** — API returns the plan, assumptions, and file path.

## Tech Stack

| Component | Library | Purpose |
|-----------|---------|---------|
| REST API | FastAPI + uvicorn | HTTP endpoint |
| Validation | Pydantic | Request/response models |
| LLM Client | Ollama (local) | LLM inference — qwen2.5:7b |
| Document Gen | python-docx | Word .docx creation |
| Env Config | python-dotenv | Load API keys from .env |
| HTTP Client | httpx | HTTP calls to Ollama API |

## Setup

### Prerequisites

- **Python 3.11+**
- **Ollama** installed and running ([ollama.com](https://ollama.com))
- **qwen2.5:7b** model pulled:
  ```bash
  ollama pull qwen2.5:7b
  ```

### Installation

```bash
# Clone or navigate to the project directory
cd "Autonomous Document Generation Agent"

# Install dependencies
pip install -r requirements.txt

# Start the server
uvicorn main:app --reload
```

The server starts at `http://localhost:8000`. API docs are at `http://localhost:8000/docs`.

## Usage

### via curl

```bash
curl -X POST http://localhost:8000/agent \
  -H "Content-Type: application/json" \
  -d '{"request": "Create meeting minutes for a project kickoff meeting between engineering and the client for a new CRM system."}'
```

### via PowerShell

```powershell
Invoke-RestMethod -Uri http://localhost:8000/agent -Method POST `
  -ContentType "application/json" `
  -Body '{"request": "Create meeting minutes for a project kickoff meeting between engineering and the client for a new CRM system."}'
```

### via Swagger UI

Open `http://localhost:8000/docs` in your browser and use the interactive API.

### Response

```json
{
  "document_type": "Meeting Minutes",
  "plan": [
    "Identify document type",
    "Generate meeting metadata",
    "Draft agenda items",
    "Draft discussion notes",
    "Draft action items",
    "Format into Word document"
  ],
  "assumptions": [],
  "file_path": "outputs/meeting_minutes_2026-07-09.docx"
}
```

## Test Cases

Run both test cases with the included test script:

```bash
# Terminal 1: Start server
uvicorn main:app --reload

# Terminal 2: Run tests
python tests/test_agent.py
```

**Test 1: Standard request**
> "Create meeting minutes for a project kickoff meeting between engineering
> and the client for a new CRM system."

The agent identifies the document type directly, plans standard meeting
minutes sections, and generates the document with mock attendees, agenda,
and action items.

**Test 2: Ambiguous/complex request**
> "I need something for my manager about how the project is going, not sure
> what format, just make it look professional."

The agent infers a **Status Report**, chooses sections itself, records its
assumptions, and fills gaps with mock data.

## Switching LLM Providers

Edit `.env` to switch providers:

```bash
# Use Groq (cloud, free tier)
LLM_PROVIDER=groq
GROQ_API_KEY=your_key_here

# Use Google Gemini (cloud, free tier)
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_key_here

# Use Ollama (local, default)
LLM_PROVIDER=ollama
OLLAMA_MODEL=qwen2.5:7b
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/` | Health check |
| `POST` | `/agent` | Generate a document |
| `GET`  | `/outputs` | List generated documents |
| `GET`  | `/outputs/{filename}` | Download a document |

## Engineering Improvement: Multi-Step Planning

**What was implemented:** The agent performs an explicit two-phase process.
It first calls the LLM purely to generate a task plan as structured JSON,
separate from content generation. Only after the plan is validated does the
agent execute each task step, rather than asking the LLM to produce the
entire document in one shot.

**Why this was chosen:** A single prompt-to-document call is fast but
opaque and unreliable for ambiguous requests — the model has no explicit
reasoning trace, and failures are hard to debug. Separating planning from
execution:
- Makes the agent's reasoning inspectable (the plan is returned to the caller)
- Lets each section be generated with a focused, smaller prompt
- Makes failures isolatable — if one section fails, it can be retried
- Mirrors real agentic architecture (plan → act)

**Error handling & recovery:**
- JSON extraction handles markdown fences and extra text from the LLM
- Pydantic validation catches malformed plan structures
- Fallback to a default plan if the LLM returns unusable output
- Per-section error handling — failed sections get placeholder text

## Known Limitations / Tradeoffs

- Mock data is used in place of real system integrations (CRM, calendar, HR)
- No persistent conversation memory between requests — each call is stateless
- Output structure may vary between runs due to autonomous planning
- Local Ollama models (7B) may occasionally produce malformed JSON — the fallback system handles this gracefully
