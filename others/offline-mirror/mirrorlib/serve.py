"""serve 子命令：啟動某個站台的本機伺服器。"""

from __future__ import annotations

from pathlib import Path

from .standalone_serve import run


def serve_site(root: Path, port: int = 8080, open_browser: bool = False) -> int:
    return run(root, port, open_browser=open_browser)
