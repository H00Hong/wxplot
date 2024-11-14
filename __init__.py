# -*- coding: utf-8 -*-
"""
A simple plotting library for the wxPython Phoenix project.

"""
__version__ = "0.0.2"
__updated__ = "2024-11-11"
__docformat__ = "restructuredtext en"

__all__ = [
    'PolyLine', 'PolySpline', 'PolyMarker', 'PolyBoxPlot', 'PolyHistogram',
    'BoxPlot', 'PolyBoxPlot', 'PlotGraphics', 'PlotCanvas', 'PlotPrintout'
]

from .plotcanvas import PlotCanvas

from .polyobjects import (PolyPoints, PolyLine, PolySpline, PolyMarker,
                          PolyBars, PolyHistogram, PolyBoxPlot,
                          PlotGraphics, PlotPrintout)

from .utils import TempStyle, pendingDeprecation, PlotPendingDeprecation
