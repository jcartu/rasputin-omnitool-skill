from pathlib import Path

from agent.config import CONFIG

ALLOWED_PREFIXES = [
    Path(CONFIG.outputs_dir).resolve(),
    Path("/mnt/sandbox").resolve(),
    Path("/tmp/become-manus-inbox").resolve(),
]


def is_allowed(path: Path) -> bool:
    resolved = path.resolve()
    return any(
        str(resolved).startswith(str(prefix))
        for prefix in ALLOWED_PREFIXES
    )
