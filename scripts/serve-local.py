"""Serve prepared Web assets and API locally. Never install or update on startup."""

import argparse
from pathlib import Path

import uvicorn
from factoryflow.bootstrap import create_app
from factoryflow.platform.config import Settings

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8100)
    parser.add_argument("--config", type=Path, help="Explicit private application JSON config")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("port must be between 1 and 65535")
    try:
        settings = Settings.load(args.config) if args.config else None
        application = create_app(web_directory=ROOT / "apps" / "web" / "dist", settings=settings)
    except ValueError as error:
        parser.error(str(error))
    # Local identity is implemented; LAN/TLS deployment still needs separate verification.
    uvicorn.run(application, host="127.0.0.1", port=args.port, access_log=False)


if __name__ == "__main__":
    main()
