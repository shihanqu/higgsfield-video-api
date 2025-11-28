#!/usr/bin/env python
"""
Run the Higgsfield API server.

This script can be run directly from PyCharm (right-click -> Run)
or from the command line: python run_server.py

Server settings can be configured in config.py or via environment variables.
"""
import uvicorn

from config import SERVER_HOST, SERVER_PORT, SERVER_RELOAD

if __name__ == "__main__":
    print(f"Starting Higgsfield API server at http://{SERVER_HOST}:{SERVER_PORT}")
    print("Press Ctrl+C to stop\n")
    
    uvicorn.run(
        "src.main:app",
        host=SERVER_HOST,
        port=SERVER_PORT,
        reload=SERVER_RELOAD,
    )

