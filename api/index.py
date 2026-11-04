"""
Vercel Serverless Function Entry Point for Library Book Usage Analysis System.
Exports the WSGI Flask application object `app` for Vercel's Python runtime.
"""

import sys
import os

# Ensure the project root directory is added to sys.path so modules (app, config, db, analytics) import cleanly
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from app import app

# Vercel discovers and executes `app`
if __name__ == '__main__':
    app.run()
