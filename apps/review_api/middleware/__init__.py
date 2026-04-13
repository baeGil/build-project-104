"""Middleware for Contract Review API."""

from apps.review_api.middleware.timing import TimingMiddleware

__all__ = ["TimingMiddleware"]
