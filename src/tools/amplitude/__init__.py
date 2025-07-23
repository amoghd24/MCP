"""
Amplitude Analytics API Integration
Provides tools for accessing Amplitude dashboard data
"""

from .segmentation import (
    get_amplitude_event_segmentation,
    get_amplitude_event_segmentation_simple
)

__all__ = [
    "get_amplitude_event_segmentation",
    "get_amplitude_event_segmentation_simple"
]