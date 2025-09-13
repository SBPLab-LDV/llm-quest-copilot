#!/usr/bin/env python3
"""
Web UI + Web server runner for the healthcare dialogue system.

This starts the Gradio-based web UI on the configured port and binds to 0.0.0.0
so it is accessible from outside the container. It is not a desktop GUI.
"""

import argparse
import logging
import os
import sys

# Ensure project root is on path
PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.ui.app import create_app


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Web UI server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=7860, help="Port to listen (default: 7860)")
    parser.add_argument("--api-url", default="http://0.0.0.0:8000", help="Backend API base URL")
    parser.add_argument("--share", action="store_true", help="Enable Gradio share mode")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logging.info(f"Starting Web UI on {args.host}:{args.port} (API: {args.api_url})")

    app = create_app(api_url=args.api_url)

    # Launch gradio app
    app.launch(server_name=args.host, server_port=args.port, share=args.share)


if __name__ == "__main__":
    main()

