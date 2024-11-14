# -*- coding: utf-8 -*-
# pylint: disable=C0413
#   C0413: Import should be placed at the top of the module
"""
A simple plotting library for the wxPython Phoenix project.

"""
__version__ = "0.0.2"
__updated__ = "2024-11-11"
__docformat__ = "restructuredtext en"

# For those who still use ``from package import *`` for some reason
__all__ = [
    'PolyLine', 'PolySpline', 'PolyMarker', 'PolyBoxPlot', 'PolyHistogram',
    'BoxPlot', 'PolyBoxPlot', 'PlotGraphics', 'PlotCanvas', 'PlotPrintout'
]

# Expose items so that the old API can still be used.
from .plotcanvas import PlotCanvas

from .polyobjects import (PolyPoints, PolyLine, PolySpline, PolyMarker,
                          PolyBars, PolyHistogram, PolyBoxPlot,
                          PlotGraphics, PlotPrintout)

from .utils import TempStyle, pendingDeprecation, PlotPendingDeprecation

# For backwards compat.
# BoxPlot = PolyBoxPlot
