"""
Amplitude Analytics API Integration
Provides tools for accessing Amplitude dashboard data
"""

from .segmentation import (
    get_amplitude_event_segmentation,
    get_amplitude_event_segmentation_simple
)
from .funnel import get_amplitude_funnel

__all__ = [
    "get_amplitude_event_segmentation",
    "get_amplitude_event_segmentation_simple",
    "get_amplitude_funnel"
]