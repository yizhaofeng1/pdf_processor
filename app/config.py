import sys
from pathlib import Path
import os
from dotenv import load_dotenv

# Handle PyInstaller frozen runtime environment
if getattr(sys, "frozen", False):
    # PyInstaller temporary extraction directory for read-only bundled assets
    BUNDLE_DIR = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    # Directory where the executable binary resides (for persistent user data)
    APP_DIR = Path(sys.executable).parent
    default_data_dir = APP_DIR / "data"
else:
    BUNDLE_DIR = Path(__file__).resolve().parent.parent
    APP_DIR = BUNDLE_DIR
    default_data_dir = BUNDLE_DIR / "data"

BASE_DIR = BUNDLE_DIR

# Load environment variables if .env exists
if (APP_DIR / ".env").exists():
    load_dotenv(APP_DIR / ".env")
elif (BUNDLE_DIR / ".env").exists():
    load_dotenv(BUNDLE_DIR / ".env")

# Project directories
DATA_DIR = Path(os.getenv("APP_DATA_DIR", default_data_dir))
CACHE_DIR = DATA_DIR / "cache"
THUMBNAILS_DIR = DATA_DIR / "thumbnails"
PROJECTS_DIR = DATA_DIR / "projects"
SCHEMAS_DIR = BUNDLE_DIR / "schemas"
PROMPTS_DIR = BUNDLE_DIR / "prompts"

# Database path
DEFAULT_DB_PATH = DATA_DIR / "exam_split.db"

# PDF Rendering defaults
DEFAULT_RENDER_DPI = int(os.getenv("RENDER_DPI", "200"))
DEFAULT_HORIZONTAL_PADDING_RATIO = 0.005
DEFAULT_VERTICAL_PADDING_RATIO = 0.004

# Concurrency & Network defaults
MAX_CONCURRENT_REQUESTS = int(os.getenv("MAX_CONCURRENT_REQUESTS", "2"))
REQUEST_TIMEOUT_SECONDS = 60.0

# AI Provider configurations
DEFAULT_PROVIDER = os.getenv("DEFAULT_PROVIDER", "deepseek")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")


def ensure_data_directories() -> None:
    """Ensure all runtime directories exist."""
    for directory in (DATA_DIR, CACHE_DIR, THUMBNAILS_DIR, PROJECTS_DIR):
        directory.mkdir(parents=True, exist_ok=True)
