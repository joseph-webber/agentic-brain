"""Google Docs processor stub.

The Google Docs processor was removed during refactor.
This stub provides the expected interface for backward compatibility.
"""
import logging

logger = logging.getLogger(__name__)


class GoogleDocType:
    DOCUMENT = "document"
    SPREADSHEET = "spreadsheet"
    PRESENTATION = "presentation"


class GoogleDocMetadata:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class GoogleDocsProcessor:
    """Stub for Google Docs processor."""

    def __init__(self, **kwargs):
        logger.debug("GoogleDocsProcessor stub initialized")

    def process(self, *args, **kwargs):
        raise NotImplementedError("GoogleDocsProcessor has been removed during refactor")
