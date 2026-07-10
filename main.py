"""
AutoDoc Agent — FastAPI Application.
Exposes POST /agent endpoint for autonomous document generation.
"""

import os
import asyncio
import logging
from contextlib import asynccontextmanager

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

import config
from models import AgentRequest, AgentResponse
from planner import generate_plan
from executor import execute_plan
from docgen import generate_document

# ── Logging Setup ───────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(name)-14s │ %(levelname)-7s │ %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("autodoc")


# ── Lifespan (startup / shutdown) ──────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown logic."""
    # Startup
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    logger.info("=" * 60)
    logger.info("  AutoDoc Agent is starting up")
    logger.info(f"  LLM Provider : {config.LLM_PROVIDER}")
    if config.LLM_PROVIDER == "ollama":
        logger.info(f"  Ollama Model  : {config.OLLAMA_MODEL}")
        logger.info(f"  Ollama URL    : {config.OLLAMA_BASE_URL}")
    logger.info(f"  Output Dir    : {config.OUTPUT_DIR}")
    logger.info("=" * 60)
    yield
    # Shutdown
    logger.info("AutoDoc Agent shutting down.")


# ── FastAPI App ─────────────────────────────────────────────────────────────

app = FastAPI(
    title="AutoDoc Agent",
    description=(
        "An autonomous AI agent that takes a natural language request, "
        "plans its execution, generates content using an LLM, and produces "
        "a polished Microsoft Word (.docx) business document."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# ── Static Files ────────────────────────────────────────────────────────────

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# ── CORS Middleware ─────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Routes ──────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse, tags=["UI"])
async def root():
    """Serve the frontend UI."""
    html_file = STATIC_DIR / "index.html"
    return HTMLResponse(content=html_file.read_text(encoding="utf-8"))


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint."""
    return {
        "service": "AutoDoc Agent",
        "status": "running",
        "version": "1.0.0",
        "llm_provider": config.LLM_PROVIDER,
    }


@app.post("/agent", response_model=AgentResponse, tags=["Agent"])
async def agent_endpoint(request: AgentRequest):
    """
    Main agent endpoint.
    
    Accepts a natural language request, plans the document structure,
    generates content for each section, and produces a formatted .docx file.
    """
    logger.info("=" * 60)
    logger.info(f"  New request received")
    logger.info(f"  Request: {request.request[:100]}...")
    logger.info("=" * 60)

    try:
        loop = asyncio.get_event_loop()

        # ── Step 1: Planning ────────────────────────────────────────────
        logger.info("PHASE 1: Planning...")
        plan = await loop.run_in_executor(None, generate_plan, request.request)

        logger.info(f"  Document type : {plan.document_type}")
        logger.info(f"  Sections      : {plan.sections}")
        logger.info(f"  Assumptions   : {plan.assumptions}")
        logger.info(f"  Steps         : {len(plan.steps)}")

        # ── Step 2: Execution ───────────────────────────────────────────
        logger.info("PHASE 2: Executing plan (drafting sections)...")
        sections = await loop.run_in_executor(None, execute_plan, plan, request.request)

        logger.info(f"  Sections drafted: {len(sections)}")

        # ── Step 3: Document Generation ─────────────────────────────────
        logger.info("PHASE 3: Generating Word document...")
        file_path = await loop.run_in_executor(None, generate_document, plan.document_type, sections)

        logger.info(f"  Document saved: {file_path}")

        # ── Step 4: Response Assembly ───────────────────────────────────
        response = AgentResponse(
            document_type=plan.document_type,
            plan=[step.action for step in plan.steps] if plan.steps else plan.sections,
            assumptions=plan.assumptions,
            file_path=file_path,
        )

        logger.info("Request completed successfully!")
        logger.info("=" * 60)

        return response

    except Exception as e:
        logger.error(f"Agent failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Agent processing failed: {str(e)}",
        )


@app.get("/outputs/{filename}", tags=["Documents"])
async def download_document(filename: str):
    """Download a generated document by filename."""
    filepath = os.path.join(config.OUTPUT_DIR, filename)

    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Document not found.")

    return FileResponse(
        path=filepath,
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


@app.get("/outputs", tags=["Documents"])
async def list_documents():
    """List all generated documents."""
    if not os.path.exists(config.OUTPUT_DIR):
        return {"documents": []}

    files = [
        f for f in os.listdir(config.OUTPUT_DIR)
        if f.endswith(".docx")
    ]
    return {"documents": sorted(files, reverse=True)}
