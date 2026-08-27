#!/usr/bin/env python3
"""
Deezy - Personal AI Operator
Entry point for the Deezy application.
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from deezy.interface.cli import main

if __name__ == "__main__":
    main()