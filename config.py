"""
Configuration module for AutoDoc Agent.
Loads environment variables and defines application settings.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── LLM Provider ────────────────────────────────────────────────────────────
# Supported: "ollama", "groq", "gemini"
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama")

# ── Ollama Settings ─────────────────────────────────────────────────────────
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")

# ── Groq Settings (optional) ───────────────────────────────────────────────
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

# ── Gemini Settings (optional) ──────────────────────────────────────────────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

# ── Generation Settings ─────────────────────────────────────────────────────
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.7"))
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "4096"))
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "120"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "2"))

# ── Output Settings ─────────────────────────────────────────────────────────
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "outputs")
