# -*- coding: utf-8 -*-
# pylint: disable=C0413
#   C0413: Import should be placed at the top of the module
"""
A simple plotting library for the wxPython Phoenix project.

"""
__version__ = "0.0.2"
__updated__ = "2024-11-11"
__docformat__ = "restructuredtext en"
__all__ = [
    'PolyLine', 'PolySpline', 'PolyMarker', 'PolyBoxPlot', 'PolyHistogram',
    'PolyBoxPlot', 'PlotGraphics', 'PlotCanvas', 'PlotPrintout'
]

from .plotcanvas import PlotCanvas
from .polyobjects import (PolyLine, PolySpline, PolyMarker, PolyHistogram,
                          PolyBoxPlot, PlotGraphics, PlotPrintout)
