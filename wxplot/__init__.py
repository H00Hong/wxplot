# -*- coding: utf-8 -*-
"""
A simple plotting library for the wxPython Phoenix project.

"""
__version__ = "0.0.2"
__updated__ = "2024-11-11"
__all__ = [
    'PolyLine', 'PolySpline', 'PolyMarker', 'PolyBoxPlot', 'PolyHistogram',
    'PlotGraphics', 'PlotCanvas', 'PlotPrintout'
]

from .plotcanvas import PlotCanvas
from .polyobjects import (PolyLine, PolySpline, PolyMarker, PolyHistogram,
                          PolyBoxPlot, PlotGraphics, PlotPrintout)
