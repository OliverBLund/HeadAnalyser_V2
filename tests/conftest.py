import sys
from pathlib import Path


def pytest_configure():
    repo_root = Path(__file__).resolve().parents[2]
    v2_root = repo_root / "HeadAnalyser_V2"

    # Allow `import core.*` and `import ui.*` like the application does.
    if str(v2_root) not in sys.path:
        sys.path.insert(0, str(v2_root))

