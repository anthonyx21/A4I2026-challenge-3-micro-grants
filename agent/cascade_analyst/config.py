"""Configuration shared by setup, MCP tools and the agent."""
import os
import re
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)


def identifier(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
        raise ValueError(f"Invalid BigQuery identifier: {value!r}")
    return value


PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "qwiklabs-gcp-04-029c15637557").strip()
if not re.fullmatch(r"[a-z][a-z0-9-]{4,61}[a-z0-9]", PROJECT):
    raise ValueError("GOOGLE_CLOUD_PROJECT must be a project ID")
DATASET = identifier(os.environ.get("BQ_DATASET", "a4i_econ"))
GRAPH = identifier(os.environ.get("BQ_GRAPH", "CascadeEconomy"))
LOCATION = os.environ.get("BQ_LOCATION", "US")
CORRIDOR = os.environ.get("CORRIDOR", "Central Market")
TOOLBOX_URL = os.environ.get("TOOLBOX_URL", "http://127.0.0.1:5000").rstrip("/")
MODEL = os.environ.get("AGENT_MODEL", "gemini-2.5-flash")
