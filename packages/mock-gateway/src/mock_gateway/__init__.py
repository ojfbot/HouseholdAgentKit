"""Gateway twin (K17). This package holds IQ's catalog-and-slots half; HP's core half
(mock Gateway server, consent gate, mock Sparky) lands alongside it in the same package."""

from mock_gateway.catalog import (
    CATALOG_VERSION,
    STORES,
    DiscoverQuery,
    DiscoverResult,
    TwinCatalog,
    TwinEvent,
    seeded_violations,
)
from mock_gateway.clock import TZ, SimClock, at
from mock_gateway.labels import BEHAVIOURS, LABELS, labels_for
from mock_gateway.seams import CatalogSlotsPort, Twin, make_twin
from mock_gateway.slots import Hold, Slot, SlotsResponse, TwinSlots

__all__ = [
    "BEHAVIOURS",
    "CATALOG_VERSION",
    "LABELS",
    "STORES",
    "TZ",
    "CatalogSlotsPort",
    "DiscoverQuery",
    "DiscoverResult",
    "Hold",
    "SimClock",
    "Slot",
    "SlotsResponse",
    "Twin",
    "TwinCatalog",
    "TwinEvent",
    "TwinSlots",
    "at",
    "labels_for",
    "make_twin",
    "seeded_violations",
]
