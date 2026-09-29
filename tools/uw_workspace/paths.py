"""Repository discovery follows this file, never the caller's current directory."""
from pathlib import Path
REPO = Path(__file__).resolve().parents[2]
PACKAGES = ("runtime", "app", "robot", "simulations", "benchmark", "guard", "controller", "perception", "navigation", "tasks", "localization", "ui", "tools")
