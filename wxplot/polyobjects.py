# -*- coding: utf-8 -*-

from collections import namedtuple
from typing import List, Literal, Optional, Sequence, Tuple, Union

import numpy as np
import wx
from numpy.typing import NDArray
from wx.lib.plot.polyobjects import PlotGraphics as _PlotGraphics
from wx.lib.plot.polyobjects import PlotPrintout
from wx.lib.plot.polyobjects import PolyPoints as _PolyPoints
from wx.lib.plot.utils import TempStyle, pairwise

LINESTYLE = {
    '-': wx.PENSTYLE_SOLID,
    '--': wx.PENSTYLE_LONG_DASH,
    ':': wx.PENSTYLE_DOT,
    '__': wx.PENSTYLE_SHORT_DASH,
    '-.': wx.PENSTYLE_DOT_DASH,
    wx.PENSTYLE_SOLID: wx.PENSTYLE_SOLID,
    wx.PENSTYLE_LONG_DASH: wx.PENSTYLE_LONG_DASH,
    wx.PENSTYLE_DOT: wx.PENSTYLE_DOT,
    wx.PENSTYLE_SHORT_DASH: wx.PENSTYLE_SHORT_DASH,
    wx.PENSTYLE_DOT_DASH: wx.PENSTYLE_DOT_DASH
}
BRUSHSTYLE = {
    'solid': wx.BRUSHSTYLE_SOLID,
    'transparent': wx.BRUSHSTYLE_TRANSPARENT,
    wx.BRUSHSTYLE_SOLID: wx.BRUSHSTYLE_SOLID,
    wx.BRUSHSTYLE_TRANSPARENT: wx.BRUSHSTYLE_TRANSPARENT,
}


class PolyPoints(_PolyPoints):

    _points: NDArray[np.float64]
    _logscale: Tuple[bool, bool]
    _absScale: Tuple[bool, bool]
    _symlogscale: Tuple[bool, bool]
    _pointSize: Tuple[float, float]
    currentScale: Tuple[float, float]
    currentShift: Tuple[float, float]
    scaled: NDArray[np.float64]

    def __init__(self, points, **attr):
        _PolyPoints.__init__(self, points, attr)
        # self._points: NDArray[np.float64] = np.asarray(points, np.float64)

        for it in ('_style', '_fillstyle', '_edgestyle'):
            if hasattr(self, it):
                style = getattr(self, it)
                try:
                    self.attributes[it[1:]] = style[self.attributes[it[1:]]]
                except KeyError:
                    err_txt = 'Style attribute incorrect. Should be one of {}'
                    raise KeyError(err_txt.format(style.keys()))

    def draw(self, dc: wx.DC, printerScale: float, coord: Optional[NDArray[np.float64]] = None):
        raise NotImplementedError

    def drawlegend(self, dc: wx.DC, printerScale: float, coord: NDArray[np.float64]):
        self.draw(dc, printerScale, coord)


class PolyMarker(PolyPoints):
    """
    Creates a PolyMarker object.

    Parameters
    ----------
    - points: list of `[x, y]` values
        The marker coordinates.
    - colour: `wx.Colour` | str
        The marker outline colour.
    - width: float
        The marker outline width.
    - size: float
        The marker size.
    - fillcolour: `wx.Colour` | str | None
        The marker fill colour. If None, the outline colour is used.
    - fillstyle: {'solid', 'transparent'}
        The marker fill style.
    - marker: {'circle', 'dot', 'square', 'triangle', 'triangle_down', 'cross', 'plus'}
        The marker type.
        - circle: A circle of diameter `size`
        - dot: A dot. Does not have a size.
        - square: A square with side length `size`
        - triangle: An upward-pointed triangle
        - triangle_down: A downward-pointed triangle
        - cross: An "X" shape
        - plus: A "+" shape
    - legend: str
        The legend string.

    warning
    ----------
       All methods except ``__init__`` are private.
    """
    _fillstyle = BRUSHSTYLE
    _attributes = {
        'colour': 'black',
        'width': 1.,
        'size': 2.,
        'fillcolour': None,
        'fillstyle': wx.BRUSHSTYLE_SOLID,
        'marker': 'circle',
        'legend': ''
    }

    def __init__(self,
                 points,
                 *,
                 colour='black',
                 width: float = 1.,
                 size: float = 2.,
                 fillcolour=None,
                 fillstyle: Literal['solid', 'transparent'] = 'solid',
                 marker: Literal['circle', 'dot', 'square', 'triangle',
                                 'triangle_down', 'cross', 'plus'] = 'circle',
                 legend: str = ''):
        PolyPoints.__init__(self,
                            points,
                            colour=colour,
                            width=width,
                            size=size,
                            fillcolour=fillcolour,
                            fillstyle=fillstyle,
                            marker=marker,
                            legend=legend)

    def draw(self, dc: wx.DC, printerScale: float, coord: Optional[NDArray[np.float64]] = None):
        """ Draw the points """
        colour = self.attributes['colour']
        width = self.attributes['width'] * printerScale * self._pointSize[0]
        size = self.attributes['size'] * printerScale * self._pointSize[0]
        fillcolour = self.attributes['fillcolour']
        fillstyle = self.attributes['fillstyle']
        marker = self.attributes['marker']

        if colour and not isinstance(colour, wx.Colour):
            colour = wx.Colour(colour)
        if fillcolour and not isinstance(fillcolour, wx.Colour):
            fillcolour = wx.Colour(fillcolour)

        dc.SetPen(wx.Pen(colour, int(width)))
        if fillcolour:
            dc.SetBrush(wx.Brush(fillcolour, fillstyle))
        else:
            dc.SetBrush(wx.Brush(colour, fillstyle))
        if coord is None:
            if len(self.scaled):  # bugfix for Mac OS X
                self._drawmarkers(dc, self.scaled, marker, size)
        else:
            self._drawmarkers(dc, coord, marker, size)  # draw legend marker

    def _drawmarkers(self, dc, coords, marker, size):
        f = getattr(self, '_{}'.format(marker))
        f(dc, coords, size)

    def getSymExtent(self, printerScale: float) -> Tuple[float, float]:
        """Width and Height of Marker"""
        s = 5 * self.attributes['size'] * printerScale * self._pointSize[0]
        return s, s

    def _circle(self, dc, coords, size=1):
        fact = 2.5 * size
        wh = 5.0 * size
        rect = np.zeros((len(coords), 4), float) + [0.0, 0.0, wh, wh]
        rect[:, 0:2] = coords - [fact, fact]
        dc.DrawEllipseList(rect.astype(np.int64))

    def _dot(self, dc, coords, size=1):
        coords = [(int(c[0]), int(c[1])) for c in coords]
        dc.DrawPointList(coords)

    def _square(self, dc, coords, size=1):
        fact = 2.5 * size
        wh = 5.0 * size
        rect = np.zeros((len(coords), 4), float) + [0.0, 0.0, wh, wh]
        rect[:, 0:2] = coords - [fact, fact]
        dc.DrawRectangleList(rect.astype(np.int64))

    def _triangle(self, dc, coords, size=1):
        shape = [(-2.5 * size, 1.44 * size), (2.5 * size, 1.44 * size),
                 (0.0, -2.88 * size)]
        poly = np.repeat(coords, 3, 0)
        poly.shape = (len(coords), 3, 2)
        poly += shape
        dc.DrawPolygonList(poly.astype(np.int64))

    def _triangle_down(self, dc, coords, size=1):
        shape = [(-2.5 * size, -1.44 * size), (2.5 * size, -1.44 * size),
                 (0.0, 2.88 * size)]
        poly = np.repeat(coords, 3, 0)
        poly.shape = (len(coords), 3, 2)
        poly += shape
        dc.DrawPolygonList(poly.astype(np.int64))

    def _cross(self, dc, coords, size=1):
        fact = 2.5 * size
        for f in [[-fact, -fact, fact, fact], [-fact, fact, fact, -fact]]:
            lines = np.concatenate((coords, coords), axis=1) + f
            dc.DrawLineList(lines.astype(np.int64))

    def _plus(self, dc, coords, size=1):
        fact = 2.5 * size
        for f in [[-fact, 0, fact, 0], [0, -fact, 0, fact]]:
            lines = np.concatenate((coords, coords), axis=1) + f
            dc.DrawLineList(lines.astype(np.int64))


class PolyLine(PolyMarker):
    """
    Creates PolyLine object

    Parameters
    ----------
    - points : list of ``[x, y]`` values
        The points that make up the line
    - colour : `wx.Colour` | str
        The colour of the line
    - width : float
        The width of the line
    - style : {'-', '--', ':', '__', '-.'}
        The line style
        - '-': Solid line
        - '--': Long dashed line
        - ':': Dotted line
        - '-.': Dot dash line
        - '__': Short dashed line
    - legend : str
        The legend string
    - drawstyle : {'line', 'steps-pre', 'steps-post', 'steps-mid-x', 'steps-mid-y'}
        The type of connector to use
        - line: Draws an straight line between consecutive points
        - steps-pre: Draws a line down from point A and then right to point B
        - steps-post: Draws a line right from point A and then down to point B
        - steps-mid-x: Draws a line horizontally to half way between A and B, 
                       then draws a line vertically, then again horizontally to point B.
        - steps-mid-y: Draws a line vertically to half way between A and B, 
                       then draws a line horizonatally, then again vertically to point B.
                       *Note: This typically does not look very good*
    - marker : {'circle', 'dot', 'square', 'triangle', 'triangle_down', 'cross', 'plus', 'none'}
        The type of marker to use. If `'none'`, no marker is drawn
        - none: No marker
        - circle: A circle of diameter `size`
        - dot: A dot. Does not have a size.
        - square: A square with side length `size`
        - triangle: An upward-pointed triangle
        - triangle_down: A downward-pointed triangle
        - cross: An "X" shape
        - plus: A "+" shape
    - size : float
        The size of the marker
    - fillcolour : `wx.Colour` | str | None
        The fill colour of the marker. If None, the outline colour is used
    - fillstyle : {'solid', 'transparent'}
        The fill style of the marker
        
    
    .. warning::

       All methods except ``__init__`` are private.
    """
    _style = LINESTYLE
    _attributes = {
        'colour': 'black',
        'width': 1.,
        'style': '-',
        'legend': '',
        'drawstyle': 'line',
        'size': 2.,
        'fillcolour': None,
        'fillstyle': 'solid',
        'marker': 'none'
    }
    _drawstyles = ('line', 'steps-pre', 'steps-post', 'steps-mid-x',
                   'steps-mid-y')

    def __init__(self,
                 points,
                 *,
                 colour='black',
                 width: float = 1.,
                 style: Literal['-', '--', ':', '__', '-.'] = '-',
                 legend: str = '',
                 drawstyle: Literal['line', 'steps-pre', 'steps-post',
                                    'steps-mid-x', 'steps-mid-y'] = 'line',
                 marker: Literal['circle', 'dot', 'square', 'triangle',
                                 'triangle_down', 'cross', 'plus', 'none'] = 'none',
                 size: float = 2.,
                 fillcolour=None,
                 fillstyle: Literal['solid', 'transparent'] = 'solid'):
        PolyPoints.__init__(self,
                            points,
                            colour=colour,
                            width=width,
                            style=style,
                            legend=legend,
                            drawstyle=drawstyle,
                            size=size,
                            fillcolour=fillcolour,
                            fillstyle=fillstyle,
                            marker=marker)

    def _draw(self, dc, printerScale, coord):
        """
        Draw the lines.
        """
        colour = self.attributes['colour']
        width = self.attributes['width'] * printerScale * self._pointSize[0]
        style = self.attributes['style']
        drawstyle = self.attributes['drawstyle']

        if not isinstance(colour, wx.Colour):
            colour = wx.Colour(colour)
        pen = wx.Pen(colour, int(width), style)
        pen.SetCap(wx.CAP_BUTT)
        dc.SetPen(pen)
        if coord is None:
            if len(self.scaled):  # bugfix for Mac OS X
                for c1, c2 in zip(self.scaled, self.scaled[1:]):
                    self._path(dc, c1, c2, drawstyle)
        else:
            coord = [(int(c[0]), int(c[1])) for c in coord]
            dc.DrawLines(coord)  # draw legend line

    def draw(self, dc, printerScale: float, coord: Optional[NDArray[np.float64]] = None):
        """
        Draw the lines with marker.

        :param dc: The DC to draw on.
        :type dc: :class:`wx.DC`
        :param printerScale:
        :type printerScale: float
        :param coord: The range of coordinate
        :type coord: NDArray | None
        """
        self._draw(dc, printerScale, coord)
        if self.attributes['marker'] != 'none':
            super().draw(dc, printerScale, coord)

    def drawlegend(self, dc: wx.DC, printerScale: float, coord: NDArray[np.float64]) -> None:
        temp = self.attributes['size']
        self.attributes['size'] = 1.5
        self._draw(dc, printerScale, coord)
        if self.attributes['marker'] != 'none':
            pnt1, pnt2 = coord
            super().draw(dc, printerScale, ((pnt1 + pnt2) / 2).reshape((1,)+pnt1.shape))
        self.attributes['size'] = temp

    def getSymExtent(self, printerScale) -> Tuple[float, float]:
        """
        Get the Width and Height of the symbol.

        :param printerScale:
        :type printerScale: float
        """
        a = printerScale * self._pointSize[0]
        h = self.attributes['width'] * a
        w = 5 * h
        s = 0 if self.attributes['marker'] == 'none' else 5 * self.attributes['size'] * a
        return max(s, w), max(s, h)

    def _path(self, dc, coord1: List[float], coord2: List[float],
              drawstyle: str):
        """
        Calculates the path from coord1 to coord 2 along X and Y

        :param dc: The DC to draw on.
        :type dc: :class:`wx.DC`
        :param coord1: The first coordinate in the coord pair
        :type coord1: list, length 2: ``[x, y]``
        :param coord2: The second coordinate in the coord pair
        :type coord2: list, length 2: ``[x, y]``
        :param drawstyle: The type of connector to use
        :type drawstyle: str
        """
        if drawstyle == 'line':
            # Straight line between points.
            line = [coord1, coord2]
        elif drawstyle == 'steps-pre':
            # Up/down to next Y, then right to next X
            intermediate = [coord1[0], coord2[1]]
            line = [coord1, intermediate, coord2]
        elif drawstyle == 'steps-post':
            # Right to next X, then up/down to Y
            intermediate = [coord2[0], coord1[1]]
            line = [coord1, intermediate, coord2]
        elif drawstyle == 'steps-mid-x':
            # need 3 lines between points: right -> up/down -> right
            mid_x = ((coord2[0] - coord1[0]) / 2) + coord1[0]
            intermediate1 = [mid_x, coord1[1]]
            intermediate2 = [mid_x, coord2[1]]
            line = [coord1, intermediate1, intermediate2, coord2]
        elif drawstyle == 'steps-mid-y':
            # need 3 lines between points: up/down -> right -> up/down
            mid_y = ((coord2[1] - coord1[1]) / 2) + coord1[1]
            intermediate1 = [coord1[0], mid_y]
            intermediate2 = [coord2[0], mid_y]
            line = [coord1, intermediate1, intermediate2, coord2]
        else:
            err_txt = 'Invalid drawstyle \'{}\'. Must be one of {}.'
            raise ValueError(err_txt.format(drawstyle, self._drawstyles))

        line = [(int(p[0]), int(p[1])) for p in line]
        dc.DrawLines(line)


class PolySpline(PolyLine):
    """
    Creates PolySpline object
    
    Parameters
    ----------
    - points : list of `[x, y]` values
        The points that make up the spline
    - colour : `wx.Colour` | str
        The colour of the line
    - width : float
        The width of the line
    - style : {'-', '--', ':', '__', '-.'}
        The line style
        - '-': Solid line
        - '--': Long dashed line
        - ':': Dotted line
        - '-.': Dot dash line
        - '__': Short dashed line
    - legend : str
        The legend string
    - marker : {'circle', 'dot', 'square', 'triangle', 'triangle_down', 'cross', 'plus', 'none'}
        The type of marker to use. If `'none'`, no marker is drawn
        - none: No marker
        - circle: A circle of diameter `size`
        - dot: A dot. Does not have a size.
        - square: A square with side length `size`
        - triangle: An upward-pointed triangle
        - triangle_down: A downward-pointed triangle
        - cross: An "X" shape
        - plus: A "+" shape
    - size : float
        The size of the marker
    - fillcolour : `wx.Colour` | str | None
        The fill colour of the marker. If None, the outline colour is used
    - fillstyle : {'solid', 'transparent'}
        The fill style of the marker

    .. warning::

       All methods except ``__init__`` are private.
    """
    _attributes = {
        'colour': 'black',
        'width': 1.,
        'style': '-',
        'legend': '',
        'drawstyle': 'line',
        'size': 2.,
        'fillcolour': None,
        'fillstyle': wx.BRUSHSTYLE_SOLID,
        'marker': 'none'
    }

    def __init__(self,
                 points,
                 *,
                 colour='black',
                 width: float = 1.,
                 style: Literal['-', '--', ':', '__', '-.'] = '-',
                 legend: str = '',
                 marker: Literal['circle', 'dot', 'square', 'triangle',
                                 'triangle_down', 'cross', 'plus', 'none'] = 'none',
                 size: float = 2.,
                 fillcolour=None,
                 fillstyle: Literal['solid', 'transparent'] = 'solid'):
        PolyPoints.__init__(self,
                            points,
                            colour=colour,
                            width=width,
                            style=style,
                            legend=legend,
                            size=size,
                            fillcolour=fillcolour,
                            fillstyle=fillstyle,
                            marker=marker)

    def _draw(self, dc, printerScale, coord):
        """ Draw the spline """
        colour = self.attributes['colour']
        width = self.attributes['width'] * printerScale * self._pointSize[0]
        style = self.attributes['style']
        if not isinstance(colour, wx.Colour):
            colour = wx.Colour(colour)
        pen = wx.Pen(colour, int(width), style)
        pen.SetCap(wx.CAP_ROUND)
        dc.SetPen(pen)
        if coord is None:
            if len(self.scaled) >= 3:
                dc.DrawSpline(self.scaled.astype(np.int64))
        else:
            coord = [(int(c[0]), int(c[1])) for c in coord]
            dc.DrawLines(coord)  # draw legend line


class PolyBarsBase(PolyPoints):
    """
    Base class for PolyBars and PolyHistogram.

    .. warning::

       All methods are private.
    """
    _edgestyle = LINESTYLE
    _fillstyle = BRUSHSTYLE
    _attributes = {
        'edgecolour': 'black',
        'edgewidth': 2.,
        'edgestyle': '-',
        'legend': '',
        'fillcolour': 'red',
        'fillstyle': 'solid',
        'barwidth': 1.
    }

    def __init__(self, points, **attr):
        """
        """
        PolyPoints.__init__(self, points, **attr)

    def _scaleAndShift(self, data: NDArray, scale=(1, 1), shift=(0, 0)):
        """same as override method, but returns a value."""
        return np.asarray(data) * scale + shift

    def getSymExtent(self, printerScale: float) -> Tuple[float, float]:
        """Width and Height of Marker"""
        h = self.attributes['edgewidth'] * printerScale * self._pointSize[0]
        w = 5 * h
        return w, h

    def set_pen_and_brush(self, dc, printerScale):
        pencolour = self.attributes['edgecolour']
        penwidth = (self.attributes['edgewidth'] * printerScale *
                    self._pointSize[0])
        penstyle = self.attributes['edgestyle']
        fillcolour = self.attributes['fillcolour']
        fillstyle = self.attributes['fillstyle']

        if not isinstance(pencolour, wx.Colour):
            pencolour = wx.Colour(pencolour)
        pen = wx.Pen(pencolour, int(penwidth), penstyle)
        pen.SetCap(wx.CAP_BUTT)

        if not isinstance(fillcolour, wx.Colour):
            fillcolour = wx.Colour(fillcolour)
        brush = wx.Brush(fillcolour, fillstyle)

        dc.SetPen(pen)
        dc.SetBrush(brush)

    def scale_rect(self, rect):
        # Scale the points to the plot area
        scaled_rect = self._scaleAndShift(rect, self.currentScale,
                                          self.currentShift)

        # Convert to (left, top, width, height) for drawing
        wx_rect = [
            scaled_rect[0][0],  # X (left)
            scaled_rect[0][1],  # Y (top)
            scaled_rect[1][0] - scaled_rect[0][0],  # Width
            scaled_rect[1][1] - scaled_rect[0][1]   # Height
        ]

        return wx_rect

    def draw(self, dc: wx.DC, printerScale: float, coord: Optional[NDArray[np.float64]]=None):
        raise NotImplementedError

    def drawlegend(self, dc: wx.DC, printerScale: float, coord: NDArray[np.float64]):
        self.draw(dc, printerScale, coord)


class PolyBars(PolyBarsBase):
    """
    Creates a PolyBars object.

    Parameters
    ----------
    - points : list of `(center, height)` values
        The points that make up the line
    - barwidth : float | list[float]
        The width of the bars
    - edgecolour : `wx.Colour` | str
        The colour of the line
    - edgewidth : float
        The width of the edges
    - edgestyle : {'-', '--', ':', '__', '-.'}
        The line style
        - '-': Solid line
        - '--': Long dashed line
        - ':': Dotted line
        - '-.': Dot dash line
        - '__': Short dashed line
    - fillcolour : `wx.Colour` | str
        The fill colour of the bars.
    - fillstyle : {'solid', 'transparent'}
        The fill style of the marker
    - legend : str
        The legend string

    .. important::

       If ``barwidth`` is a list of floats:

       + each bar will have a separate width
       + ``len(barwidth)`` must equal ``len(points)``.

    .. warning::

       All methods except ``__init__`` are private.
    """

    def __init__(self,
                 points,
                 *,
                 barwidth: Union[float, Sequence[float]] = 1.,
                 edgecolour='black',
                 edgewidth: int = 1.,
                 edgestyle: Literal['-', '--', ':', '__', '-.'] = '-',
                 fillcolour='red',
                 fillstyle: Literal['solid', 'transparent'] = 'solid',
                 legend: str = ''):
        super().__init__(points,
                         barwidth=barwidth,
                         edgecolour=edgecolour,
                         edgewidth=edgewidth,
                         edgestyle=edgestyle,
                         fillcolour=fillcolour,
                         fillstyle=fillstyle,
                         legend=legend)

    def calc_rect(self, x, y, w):
        """ Calculate the rectangle for plotting. """
        return self.scale_rect([
            [x - w / 2, y],  # left, top
            [x + w / 2, 0]   # right, bottom
        ])

    def draw(self, dc, printerScale, coord=None):
        """ Draw the bars """
        self.set_pen_and_brush(dc, printerScale)
        barwidth = self.attributes['barwidth']

        if coord is None:
            if isinstance(barwidth, (int, float)):
                # use a single width for all bars
                pts = ((x, y, barwidth) for x, y in self.points)
            elif isinstance(barwidth, (list, tuple)):
                # use a separate width for each bar
                if len(barwidth) != len(self.points):
                    err_str = ('Barwidth ({} items) and Points ({} items) do '
                               'not have the same length!')
                    err_str = err_str.format(len(barwidth), len(self.points))
                    raise ValueError(err_str)
                pts = ((x, y, w) for (x, y), w in zip(self.points, barwidth))
            else:
                # invalid attribute type
                err_str = ('Invalid type for \'barwidth\'. Expected float, '
                           'int, or list or tuple of (int or float). Got {}.')
                raise TypeError(err_str.format(type(barwidth)))

            rects = [self.calc_rect(x, y, w) for x, y, w in pts]
            rects = [(int(r[0]), int(r[1]), int(r[2]), int(r[3]))
                     for r in rects]
            dc.DrawRectangleList(rects)
        else:
            dc.DrawLines(coord)  # draw legend line


class PolyHistogram(PolyBarsBase):
    """
    Creates a PolyHistogram object.

    Parameters
    ----------
    - hist : sequence of ``y`` values that define the heights of the bars
        The histogram data
    - binspec : sequence of ``x`` values that define the edges of the bins
        The bin specification
    - edgecolour : `wx.Colour` | str
        The colour of the line
    - edgewidth : float
        The width of the edges
    - edgestyle : {'-', '--', ':', '__', '-.'}
        The line style
        - '-': Solid line
        - '--': Long dashed line
        - ':': Dotted line
        - '-.': Dot dash line
        - '__': Short dashed line
    - fillcolour : `wx.Colour` | str
        The fill colour of the bars.
    - fillstyle : {'solid', 'transparent'}
        The fill style of the marker
    - legend : str
        The legend string

    .. tip::

       Use ``np.histogram()`` to easily create your histogram parameters::

         hist_data, binspec = np.histogram(data)
         hist_plot = PolyHistogram(hist_data, binspec)

    .. important::

       ``len(binspec)`` must equal ``len(hist) + 1``.

    .. warning::

       All methods except ``__init__`` are private.
    """

    def __init__(self,
                 hist,
                 binspec,
                 *,
                 edgecolour='black',
                 edgewidth: float = 1.,
                 edgestyle: Literal['-', '--', ':', '__', '-.'] = '-',
                 fillcolour='red',
                 fillstyle: Literal['solid', 'transparent'] = 'solid',
                 legend: str = ''):
        if len(binspec) != len(hist) + 1:
            raise ValueError('Len(binspec) must equal len(hist) + 1')

        self.hist = hist
        self.binspec = binspec

        # define the bins and center x locations
        self.bins = np.array(pairwise(self.binspec))
        bar_center_x = self.bins[:, 0] + (self.bins[:, 1] - self.bins[:, 0]) / 2
        # bar_center_x = (pair[0] + (pair[1] - pair[0]) / 2
        #                 for pair in self.bins)
        # points = list(zip(bar_center_x, self.hist))
        points = np.asarray((bar_center_x, self.hist)).T
        PolyPoints.__init__(self,
                            points,
                            edgecolour=edgecolour,
                            edgewidth=edgewidth,
                            edgestyle=edgestyle,
                            fillcolour=fillcolour,
                            fillstyle=fillstyle,
                            legend=legend)

    def calc_rect(self, y, low, high):
        """ Calculate the rectangle for plotting. """
        return self.scale_rect([
            [low, y],  # left, top
            [high, 0]  # right, bottom
        ])

    def draw(self, dc, printerScale, coord=None):
        """ Draw the bars """
        self.set_pen_and_brush(dc, printerScale)

        if coord is None:
            rects = [
                self.calc_rect(y, low, high)
                for y, (low, high) in zip(self.hist, self.bins)
            ]
            rects = [(int(r[0]), int(r[1]), int(r[2]), int(r[3]))
                     for r in rects]

            dc.DrawRectangleList(rects)
        else:
            dc.DrawLines(coord)  # draw legend line


BPData = namedtuple(
    'bpdata',
    ('min', 'low_whisker', 'q25', 'median', 'q75', 'high_whisker', 'max'))


class PolyBoxPlot(PolyPoints):
    """
    Creates a PolyBoxPlot object.

    Parameters
    ----------
    - points : sequence of int or float
        Raw data to create a box plot from.
    - colour : `wx.Colour` | str
        The colour of the line
    - width : float
        The width of the line
    - style : {'-', '--', ':', '__', '-.'}
        The line style
        - '-': Solid line
        - '--': Long dashed line
        - ':': Dotted line
        - '-.': Dot dash line
        - '__': Short dashed line
    - legend : str
        The legend string

    .. note::

       ``np.NaN`` and ``np.inf`` values are ignored.

    .. admonition:: TODO

       + [ ] Figure out a better way to get multiple box plots side-by-side
         (current method is a hack).
       + [ ] change the X axis to some labels.
       + [ ] Change getClosestPoint to only grab box plot items and outlers?
         Currently grabs every data point.
       + [ ] Add more customization such as Pens/Brushes, outlier shapes/size,
         and box width.
       + [ ] Figure out how I want to handle log-y: log data then calcBP? Or
         should I calc the BP first then the plot it on a log scale?
    """
    _style=LINESTYLE
    _attributes = {
        'colour': 'black',
        'width': 1,
        'style': '-',
        'legend': '',
    }

    def __init__(self,
                 points,
                 *,
                 colour='black',
                 width: float = 1,
                 style: Literal['-', '--', ':', '__', '-.'] = '-',
                 legend: str = ''):
        # Set various attributes
        self.box_width = 0.5

        # Determine the X position and create a 1d dataset.
        self.xpos = points[0, 0]
        points = points[:, 1]

        # Calculate the box plot points and the outliers
        self._bpdata = self.calcBpData(points)
        self._outliers = self.calcOutliers(points)
        points = np.concatenate((self._bpdata, self._outliers))
        points = np.asarray([(self.xpos, x) for x in points])

        # Create a jitter for the outliers
        self.jitter: NDArray[np.float64] = 0.05 * np.random.random_sample(
            len(self._outliers)) + self.xpos - 0.025

        # Init the parent class
        PolyPoints.__init__(self, points, colour=colour, width=width,
                            style=style, legend=legend)

    def _clean_data(self, data=None):
        """
        Removes NaN and Inf from the data.
        """
        if data is None:
            data = self.points

        # clean out NaN and infinity values.
        data = data[~np.isnan(data)]
        data = data[~np.isinf(data)]

        return data

    def boundingBox(self) -> Tuple[NDArray, NDArray]:
        """
        Returns bounding box for the plot.

        Override method.
        """
        xpos = self.xpos

        minXY = np.asarray([xpos - self.box_width / 2, self._bpdata.min * 0.95])
        maxXY = np.asarray([xpos + self.box_width / 2, self._bpdata.max * 1.05])
        return minXY, maxXY

    def getClosestPoint(self, pntXY, pointScaled=True):
        """
        Returns the index of closest point on the curve, pointXY,
        scaledXY, distance x, y in user coords.

        Override method.

        if pointScaled == True, then based on screen coords
        if pointScaled == False, then based on user coords
        """

        xpos = self.xpos

        # combine the outliers with the box plot data
        data_to_use = np.concatenate((self._bpdata, self._outliers))
        data_to_use = np.asarray([(xpos, x) for x in data_to_use])

        if pointScaled:
            # Use screen coords
            p = self.scaled
            pxy = self.currentScale * np.asarray(pntXY) + self.currentShift
        else:
            # Using user coords
            p = self._points
            pxy = np.asarray(pntXY)

        # determine distance for each point
        d = np.sqrt(np.add.reduce((p - pxy)**2, 1))  # sqrt(dx^2+dy^2)
        pntIndex = np.argmin(d)
        dist = d[pntIndex]
        return [
            pntIndex, self.points[pntIndex],
            self.scaled[pntIndex] / self._pointSize, dist
        ]

    def getSymExtent(self, printerScale) -> Tuple[float, float]:
        """Width and Height of Marker"""
        # TODO: does this need to be updated?
        h = self.attributes['width'] * printerScale * self._pointSize[0]
        w = 5 * h
        return w, h

    def calcBpData(self, data=None):
        """
        Box plot points:

        Median (50%)
        75%
        25%
        low_whisker = lowest value that's >= (25% - (IQR * 1.5))
        high_whisker = highest value that's <= 75% + (IQR * 1.5)

        outliers are outside of 1.5 * IQR

        Parameters
        ----------
        data : array-like
            The data to plot

        Returns
        -------
        bpdata : collections.namedtuple
            Descriptive statistics for data:
            (min_data, low_whisker, q25, median, q75, high_whisker, max_data)

        """
        data = self._clean_data(data)

        min_data = float(np.min(data))
        max_data = float(np.max(data))
        q25 = float(np.percentile(data, 25))
        q75 = float(np.percentile(data, 75))

        iqr = q75 - q25

        low_whisker = float(data[data >= q25 - 1.5 * iqr].min())
        high_whisker = float(data[data <= q75 + 1.5 * iqr].max())

        median = float(np.median(data))

        return BPData(min_data, low_whisker, q25, median, q75, high_whisker,
                      max_data)

    def calcOutliers(self, data=None):
        """
        Calculates the outliers. Must be called after calcBpData.
        """
        data = self._clean_data(data)

        outliers = data
        outlier_bool = np.logical_or(outliers > self._bpdata.high_whisker,
                                     outliers < self._bpdata.low_whisker)
        outliers = outliers[outlier_bool]
        return outliers

    def _scaleAndShift(self, data, scale=(1, 1), shift=(0, 0)) -> NDArray:
        """same as override method, but returns a value."""
        scaled = scale * data + shift
        return scaled

    @TempStyle('pen')
    def draw(self, dc, printerScale, coord=None):
        """
        Draws a box plot on the DC.

        Notes
        -----
        The following draw order is required:

        1. First the whisker line
        2. Then the IQR box
        3. Lasly the median line.

        This is because

        + The whiskers are drawn as single line rather than two lines
        + The median line must be visible over the box if the box has a fill.

        Other than that, the draw order can be changed.
        """
        self._draw_whisker(dc, printerScale)
        self._draw_iqr_box(dc, printerScale)
        self._draw_median(dc, printerScale)  # median after box
        self._draw_whisker_ends(dc, printerScale)
        self._draw_outliers(dc, printerScale)

    @TempStyle('pen')
    def _draw_whisker(self, dc, printerScale):
        """Draws the whiskers as a single line"""
        xpos = self.xpos

        # We draw it as one line and then hide the middle part with
        # the IQR rectangle
        whisker_line = np.asarray([[xpos, self._bpdata.low_whisker],
                                 [xpos, self._bpdata.high_whisker]])

        whisker_line = self._scaleAndShift(whisker_line, self.currentScale,
                                           self.currentShift)

        whisker_pen = wx.Pen(wx.BLACK, 2, wx.PENSTYLE_SOLID)
        whisker_pen.SetCap(wx.CAP_BUTT)
        dc.SetPen(whisker_pen)
        dc.DrawLines(whisker_line)

    @TempStyle('pen')
    def _draw_iqr_box(self, dc, printerScale):
        """Draws the Inner Quartile Range box"""
        xpos = self.xpos
        box_w = self.box_width

        iqr_box = [
            [xpos - box_w / 2, self._bpdata.q75],  # left, top
            [xpos + box_w / 2, self._bpdata.q25]
        ]  # right, bottom

        # Scale it to the plot area
        iqr_box = self._scaleAndShift(iqr_box, self.currentScale,
                                      self.currentShift)

        # rectangles are drawn (left, top, width, height) so adjust
        iqr_box = [
            int(iqr_box[0][0]),  # X (left)
            int(iqr_box[0][1]),  # Y (top)
            int(iqr_box[1][0] - iqr_box[0][0]),  # Width
            int(iqr_box[1][1] - iqr_box[0][1])
        ]  # Height

        box_pen = wx.Pen(wx.BLACK, 3, wx.PENSTYLE_SOLID)
        box_brush = wx.Brush(wx.GREEN, wx.BRUSHSTYLE_SOLID)
        dc.SetPen(box_pen)
        dc.SetBrush(box_brush)

        dc.DrawRectangleList([iqr_box])

    @TempStyle('pen')
    def _draw_median(self, dc, printerScale, coord=None):
        """Draws the median line"""
        xpos = self.xpos

        median_line = np.asarray(
            [[xpos - self.box_width / 2, self._bpdata.median],
             [xpos + self.box_width / 2, self._bpdata.median]])

        median_line = self._scaleAndShift(median_line, self.currentScale,
                                          self.currentShift)

        median_pen = wx.Pen(wx.BLACK, 4, wx.PENSTYLE_SOLID)
        median_pen.SetCap(wx.CAP_BUTT)
        dc.SetPen(median_pen)
        dc.DrawLines(median_line)

    @TempStyle('pen')
    def _draw_whisker_ends(self, dc, printerScale):
        """Draws the end caps of the whiskers"""
        xpos = self.xpos
        fence_top = np.asarray(
            [[xpos - self.box_width * 0.2, self._bpdata.high_whisker],
             [xpos + self.box_width * 0.2, self._bpdata.high_whisker]])

        fence_top = self._scaleAndShift(fence_top, self.currentScale,
                                        self.currentShift)

        fence_bottom = np.asarray(
            [[xpos - self.box_width * 0.2, self._bpdata.low_whisker],
             [xpos + self.box_width * 0.2, self._bpdata.low_whisker]])

        fence_bottom = self._scaleAndShift(fence_bottom, self.currentScale,
                                           self.currentShift)

        fence_pen = wx.Pen(wx.BLACK, 2, wx.PENSTYLE_SOLID)
        fence_pen.SetCap(wx.CAP_BUTT)
        dc.SetPen(fence_pen)
        dc.DrawLines(fence_top)
        dc.DrawLines(fence_bottom)

    @TempStyle('pen')
    def _draw_outliers(self, dc, printerScale):
        """Draws dots for the outliers"""
        # Set the pen
        outlier_pen = wx.Pen(wx.BLUE, 5, wx.PENSTYLE_SOLID)
        dc.SetPen(outlier_pen)

        outliers = self._outliers

        # Scale the data for plotting
        pt_data = np.asarray([self.jitter, outliers]).T
        pt_data = self._scaleAndShift(pt_data, self.currentScale,
                                      self.currentShift)

        # Draw the outliers
        size = 0.5
        fact = 2.5 * size
        wh = 5.0 * size
        rect = np.zeros((len(pt_data), 4), float) + [0.0, 0.0, wh, wh]
        rect[:, 0:2] = pt_data - [fact, fact]
        dc.DrawRectangleList(rect.astype(np.int64))


class PlotGraphics(_PlotGraphics):
    """
    Creates a PlotGraphics object.

    Parameters
    ----------
    - objects : Sequence[PolyPoints]
        The Poly objects to plot
    - title : str
        The title shown at the top of the graph
    - xLabel : str
        The x-axis label
    - yLabel : str
        The y-axis label

    .. warning::

       All methods except ``__init__`` are private.
    """

    def __init__(self,
                 objects: Sequence[PolyPoints],
                 title: str = '',
                 xLabel: str = '',
                 yLabel: str = '') -> None:
        if not isinstance(objects, (list, tuple)):
            raise TypeError('objects argument should be list or tuple')
        if any(not isinstance(obj, PolyPoints) for obj in objects):
            raise TypeError('objects argument should be list of PolyPoints')
        self.objects = objects
        self._title = title
        self._xLabel = xLabel
        self._yLabel = yLabel
        self._pointSize = (1.0, 1.0)

    def getSymExtent(self, printerScale) -> Tuple[float, float]:
        """Get max width and height of lines and markers symbols for legend"""
        self.objects[0]._pointSize = self._pointSize
        symExt = self.objects[0].getSymExtent(printerScale)
        for o in self.objects[1:]:
            o._pointSize = self._pointSize
            oSymExt = o.getSymExtent(printerScale)
            # symExt = np.maximum(symExt, oSymExt)
            symExt = (max(symExt[0], oSymExt[0]), max(symExt[1], oSymExt[1]))
        return symExt

    def getLegendNames(self):
        """Returns list of legend names"""
        # lst = [None] * len(self)
        # for i in range(len(self)):
        #     lst[i] = self.objects[i].getLegend()
        return [o.getLegend() for o in self.objects]


__all__ = [
    'LINESTYLE', 'BRUSHSTYLE', 'PlotGraphics', 'PlotPrintout', 'PolyPoints',
    'PolyMarker', 'PolyLine', 'PolyBarsBase', 'PolyBars', 'PolyHistogram',
    'PolyBoxPlot'
]
