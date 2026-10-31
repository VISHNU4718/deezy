"""Vercel entry point: exposes the FastAPI app as a serverless function."""

from deezy.interface.web.api import app

__all__ = ["app"]
