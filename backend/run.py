#!/usr/bin/env python3
"""Entry point for FairFuel backend."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.server import start_server

if __name__ == "__main__":
    start_server()
