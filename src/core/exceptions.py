"""
Custom Exceptions

Domain-specific exceptions for FinSage-Lite. Raising typed exceptions
allows routers to map them to precise HTTP status codes.
"""


class IndexNotBuiltError(Exception):
    """Raised when BM25Service is queried before build_index() has been called."""
