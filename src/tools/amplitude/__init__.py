"""
Amplitude Analytics API Integration
Provides tools for accessing Amplitude dashboard data
"""

from .segmentation import (
    get_amplitude_event_segmentation,
    get_amplitude_event_segmentation_simple
)
from .funnel import get_amplitude_funnel
from .get_events import (
    get_amplitude_events_list,
    get_amplitude_event_details
)
from .retention import get_amplitude_retention
from .users import get_amplitude_users

__all__ = [
    "get_amplitude_event_segmentation",
    "get_amplitude_event_segmentation_simple",
    "get_amplitude_funnel",
    "get_amplitude_events_list",
    "get_amplitude_event_details",
    "get_amplitude_retention",
    "get_amplitude_users"
]