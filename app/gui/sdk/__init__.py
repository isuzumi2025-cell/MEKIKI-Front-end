"""
MEKIKI GUI SDK
UI Threading, Debounce, Image Fit, Telemetry, Coord Transform, Canvas Operations utilities
"""

from .ui_threading import run_bg, ui_call, UIUpdater
from .debounce import debounce, Debouncer
from .image_fit import compute_cover, compute_fit, compute_fit_for_mode, FitResult
from .telemetry import track, track_timing, Timer
from .coord_transform import CanvasTransform, get_canvas_transform, DEFAULT_TRANSFORM
from .canvas_operations import CanvasController, PageNavigator, CanvasState, PageInfo

__all__ = [
    # UI Threading
    'run_bg', 'ui_call', 'UIUpdater',
    # Debounce
    'debounce', 'Debouncer',
    # Image Fit
    'compute_cover', 'compute_fit', 'compute_fit_for_mode', 'FitResult',
    # Telemetry
    'track', 'track_timing', 'Timer',
    # Coord Transform
    'CanvasTransform', 'get_canvas_transform', 'DEFAULT_TRANSFORM',
    # Canvas Operations
    'CanvasController', 'PageNavigator', 'CanvasState', 'PageInfo',
]
