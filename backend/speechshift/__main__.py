from __future__ import annotations

import uvicorn

from speechshift.config import get_settings


def main() -> None:
    settings = get_settings()
    uvicorn.run(
        "speechshift.main:create_app",
        factory=True,
        host=settings.app_host,
        port=settings.app_port,
        log_config=None,
    )


if __name__ == "__main__":
    main()

