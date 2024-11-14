# -*- coding: utf-8 -*-
# pylint: disable=E1101, C0330, C0103
#   E1101: Module X has no Y member
#   C0330: Wrong continued indentation
#   C0103: Invalid attribute/variable/method name
"""
plotcanvas.py
=============

This is the main window that you will want to import into your application.

"""

import base64
import io
import sys
from typing import Tuple, Union, Sequence, Literal, Optional

import wx
import numpy as np
from numpy.typing import NDArray

from .polyobjects import (PlotPrintout, PlotGraphics, PolyMarker, PolyLine,
                          PolyBoxPlot, LINESTYLE)
from .utils import (DisplaySide, set_displayside, pendingDeprecation,
                    TempStyle, scale_and_shift_point)
from ._ico import *


ID_HOME = 10000
ID_SAVE = 10001

def base64_to_bitmap(base64_str: str, size=()) -> wx.Bitmap:
    image_data = base64.b64decode(base64_str)
    stream = io.BytesIO(image_data)
    image = wx.Image(stream, wx.BITMAP_TYPE_ANY)
    if size:
        image = image.Scale(*size) # 调整大小
    return wx.Bitmap(image)


class PlotCanvas(wx.Panel):
    """
    Creates a PlotCanvas object.

    Subclass of a wx.Panel which holds two scrollbars and the actual
    plotting canvas (self.canvas). It allows for simple general plotting
    of data with zoom, labels, and automatic axis scaling.

    This is the main window that you will want to import into your
    application.
    
    :param style: The toolbar location style
    :type style: int {`wx.TB_BOTTOM`, `wx.TB_TOP`} (default: `wx.TB_BOTTOM`)

    Parameters for ``__init__`` are the same as any :class:`wx.Panel`.
    """

    def __init__(self,
                 parent,
                 id=wx.ID_ANY,
                 pos=wx.DefaultPosition,
                 size=wx.DefaultSize,
                 style=wx.TB_BOTTOM,
                 name='plotCanvas'):
        wx.Panel.__init__(self, parent, id, pos, size, name=name)
        self.parent = parent

        self.canvas = wx.Window(self)
        self.sb_vert = wx.ScrollBar(self, style=wx.SB_VERTICAL)
        self.sb_vert.SetScrollbar(0, 1000, 1000, 1000)
        self.sb_hor = wx.ScrollBar(self, style=wx.SB_HORIZONTAL)
        self.sb_hor.SetScrollbar(0, 1000, 1000, 1000)

        self.toolbar = wx.ToolBar(self, style=wx.TB_HORIZONTAL)
        self.toolbar.AddTool(ID_HOME, '主页', base64_to_bitmap(ico_home, (32, 32)),
                             '重置为初始位置')
        self.toolbar.AddTool(ID_SAVE, '保存', base64_to_bitmap(ico_save, (32, 32)),
                             '保存视图')
        self.toolbar.AddStretchableSpace()
        self.labloc = wx.StaticText(self.toolbar)
        self.toolbar.AddControl(self.labloc)
        self.toolbar.Realize()

        default_font = wx.Font(12, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL,
                               wx.FONTWEIGHT_NORMAL, False,
                               faceName='Microsoft Yahei')
        self.SetFont(default_font)
        self.labloc.SetFont(default_font)

        self._init_layout(style)
        self.Fit()
        self.SetBackgroundColour('white')
        self.SetForegroundColour('black')

        self._init_cursor()
        self._init_var()
        self._init_pen()
        self._init_bind()

#region _init
    def _init_var(self):
        # Things for printing
        self._print_data = None
        self._pageSetupData = None
        self.printerScale = 1

        # scrollbar variables
        self._sb_ignore = False
        self._sb_show = False
        self._adjustingSB = False
        self._sb_xfullrange = 0
        self._sb_yfullrange = 0
        self._sb_xunit = 0
        self._sb_yunit = 0

        self._zoomEnabled: bool = False
        self._dragEnabled: bool = False
        self._labxy_l: int = 0

        # Drawing Variables
        self.last_draw = None
        self._pointScale = 1
        self._pointShift = 0
        self._xSpec = 'auto'
        self._ySpec = 'auto'

        # Initial Plot Options
        self._logScale: Tuple[bool, bool] = (False, False)
        self._absScale: Tuple[bool, bool] = (False, False)
        self._gridEnabled: Tuple[bool, bool] = (True, True)
        self._legendEnabled:bool = False
        self._titleEnabled: bool = True
        self._axesLabelsEnabled: bool = True
        self._centerLinesEnabled: bool = False
        self._diagonalsEnabled: bool = False
        self._ticksEnabled = DisplaySide(False, False, False, False)
        self._axesEnabled = DisplaySide(True, True, True, True)
        self._axesValuesEnabled = DisplaySide(True, True, False, False)

        # Fonts
        self._fontCache = {}
        self._fontSizeAxis = 10
        self._fontSizeTitle = 15
        self._fontSizeLegend = 8
        self._fontSizeLoc = 10

        # pointLabels
        self._pointLabelEnabled: bool = False
        self.last_PointLabel = None
        self._pointLabelFunc = None

        if sys.platform != 'darwin':
            self._logicalFunction = wx.EQUIV  # (NOT src) XOR dst
        else:
            # wx.EQUIV not supported on Mac OS X
            self._logicalFunction = wx.COPY

        self._useScientificNotation: bool = False

        self._antiAliasingEnabled: bool = False
        self._hiResEnabled: bool = False
        self._pointSize: Tuple[float, float] = (1.0, 1.0)
        self._fontScale: float = 1.0

    def _init_cursor(self):
        # set cursor as cross-hairs
        self.defaultCursor = wx.Cursor(wx.CURSOR_ARROW)
        self.HandCursor = wx.Cursor(wx.CURSOR_HAND)
        self.SizeNSCursor = wx.Cursor(wx.CURSOR_SIZENS)  # 上下抓手
        self.SizeWECursor = wx.Cursor(wx.CURSOR_SIZEWE)  # 左右抓手
        self.GrabHandCursor = wx.Cursor(wx.CURSOR_SIZING)  # 十字抓手
        self.MagCursor = wx.Cursor(wx.CURSOR_MAGNIFIER)  # 放大镜
        self.canvas.SetCursor(self.defaultCursor)

    def _init_layout(self, style):
        # layout
        sizer = wx.FlexGridSizer(2, 2, 0, 0)
        sizer.AddGrowableRow(0, 1)
        sizer.AddGrowableCol(0, 1)
        
        sizer0 = wx.BoxSizer(wx.VERTICAL)
        if style == wx.TB_TOP:
            sizer0.Add(self.toolbar, 0, wx.EXPAND)
        sizer0.Add(self.canvas, 1, wx.EXPAND)
        if style == wx.TB_BOTTOM:
            sizer0.Add(self.toolbar, 0, wx.EXPAND)

        sizer.Add(sizer0, 1, wx.EXPAND)
        sizer.Add(self.sb_vert, 0, wx.EXPAND)
        sizer.Add(self.sb_hor, 0, wx.EXPAND)
        sizer.Add((0, 0))

        self.sb_vert.Show(False)
        self.sb_hor.Show(False)

        self.SetSizer(sizer)

    def _init_bind(self):
        # toolbar events
        self.Bind(wx.EVT_TOOL, self.OnMouseMiddleUp, id=ID_HOME)
        self.Bind(wx.EVT_TOOL, self._on_save, id=ID_SAVE)
        # Create some mouse events for zooming
        self.canvas.Bind(wx.EVT_LEFT_DOWN, self.OnMouseLeftDown)
        self.canvas.Bind(wx.EVT_LEFT_UP, self.OnMouseLeftUp)
        self.canvas.Bind(wx.EVT_MOTION, self.OnMotion)
        self.canvas.Bind(wx.EVT_LEFT_DCLICK, self.OnMouseDoubleClick)
        self.canvas.Bind(wx.EVT_RIGHT_DOWN, self.OnMouseRightDown)
        self.canvas.Bind(wx.EVT_RIGHT_UP, self.OnMouseRightUp)
        self.canvas.Bind(wx.EVT_RIGHT_DCLICK, self.OnMouseRightDClick)
        self.canvas.Bind(wx.EVT_MOUSEWHEEL, self.OnMouseWheel)
        self.canvas.Bind(wx.EVT_MIDDLE_UP, self.OnMouseMiddleUp)
        # scrollbar events
        self.Bind(wx.EVT_SCROLL_THUMBTRACK, self.OnScroll)
        self.Bind(wx.EVT_SCROLL_PAGEUP, self.OnScroll)
        self.Bind(wx.EVT_SCROLL_PAGEDOWN, self.OnScroll)
        self.Bind(wx.EVT_SCROLL_LINEUP, self.OnScroll)
        self.Bind(wx.EVT_SCROLL_LINEDOWN, self.OnScroll)
        # canvas events
        self.canvas.Bind(wx.EVT_LEAVE_WINDOW, self.OnLeave)
        self.canvas.Bind(wx.EVT_PAINT, self.OnPaint)
        self.canvas.Bind(wx.EVT_SIZE, self.OnSize)
        # OnSize called to make sure the buffer is initialized.
        # This might result in OnSize getting called twice on some
        # platforms at initialization, but little harm done.
        self.OnSize(None)  # sets the initial size based on client size

    def _init_pen(self):
        # Default Pens
        self._gridPen = wx.Pen(wx.Colour(180, 180, 180, 255),
                               int(self._pointSize[0]), wx.PENSTYLE_DOT)
        self._centerLinePen = wx.Pen(wx.RED, int(self._pointSize[0]),
                                     wx.PENSTYLE_SHORT_DASH)
        self._axesPen = wx.Pen(wx.BLACK, int(self._pointSize[0]),
                               wx.PENSTYLE_SOLID)
        self._tickPen = wx.Pen(wx.BLACK, int(self._pointSize[0]),
                               wx.PENSTYLE_SOLID)
        self._tickLength = tuple(-x * 2 for x in self._pointSize)
        self._diagonalPen = wx.Pen(wx.BLUE, int(self._pointSize[0]),
                                   wx.PENSTYLE_DOT_DASH)
#endregion

#region set_get
    def SetCursor(self, cursor: wx.Cursor) -> None:
        """Sets the cursor on the canvas 设置窗口的光标"""
        self.canvas.SetCursor(cursor)

    def _setPen(self, name: str, ls, colour) -> None:
        if not isinstance(colour, wx.Colour):
            colour = wx.Colour(colour)
        setattr(self, name, wx.Pen(colour, int(self._pointSize[0]), LINESTYLE[ls]))
        self.Redraw()

    def SetGridPen(self, ls: Literal['-', '--', ':', '__', '-.'] = ':', colour=(180, 180, 180)) -> None:
        """
        Set the grid pen. 
        
        Parameters
        ----------
        ls : {'-', '--', ':', '__', '-.'}
            Line style of grid pen.
        colour : `wx.Colour` | str | tuple[int, int, int]
            Colour of grid pen.
        """
        self._setPen('_gridPen', ls, colour)

    def SetDiagonalPen(self, ls: Literal['-', '--', ':', '__', '-.'] = ':', colour=wx.BLUE) -> None:
        """
        Set the diagonal pen. 
        
        Parameters
        ----------
        ls : {'-', '--', ':', '__', '-.'}
            Line style of diagonal pen.
        colour : `wx.Colour` | str | tuple of 3 ints
            Colour of diagonal pen.
        """
        self._setPen('_diagonalPen', ls, colour)

    def SetCenterLinePen(self, ls: Literal['-', '--', ':', '__', '-.'] = ':', colour=wx.RED) -> None:
        """
        Set the center line pen. 
        
        Parameters
        ----------
        ls : {'-', '--', ':', '__', '-.'}
            Line style of center line pen.
        colour : `wx.Colour` | str | tuple of 3 ints
            Colour of center line pen.
        """
        self._setPen('_centerLinePen', ls, colour)

    def SetAxesPen(self, ls: Literal['-', '--', ':', '__', '-.'] = ':', colour=wx.BLACK) -> None:
        """
        Set the axes lines pen. 
        
        Parameters
        ----------
        ls : {'-', '--', ':', '__', '-.'}
            Line style of axes pen.
        colour : `wx.Colour` | str | tuple of 3 ints
            Colour of axes pen.
        """
        self._setPen('_axesPen', ls, colour)

    def SetTickPen(self, ls: Literal['-', '--', ':', '__', '-.'] = ':', colour=wx.BLACK) -> None:
        """
        Set the tick markers pen. 
        
        Parameters
        ----------
        ls : {'-', '--', ':', '__', '-.'}
            Line style of tick pen.
        colour : `wx.Colour` | str | tuple of 3 ints
            Colour of tick pen.
        """
        self._setPen('_tickPen', ls, colour)

    def SetLogScale(self, logscale: Tuple[bool, bool] = (True, True)) -> None:
        """
        Set the log scale boolean value. 对数刻度

        Parameters
        ----------
        logscale : tuple of bools, length 2
            A tuple of `(x_axis_is_log_scale, y_axis_is_log_scale)` booleans.
        """
        if not isinstance(logscale, tuple) or len(logscale) != 2:
            raise TypeError('logscale must be a 2-tuple of bools, e.g. (False, False)')
        if self.last_draw is not None:
            graphics, xAxis, yAxis = self.last_draw
            graphics.logScale = logscale
            self.last_draw = (graphics, None, None)
        self._xSpec = 'min'
        self._ySpec = 'min'
        self._logScale = logscale

    def GetLogScale(self) -> Tuple[bool, bool]:
        """
        Get the log scale boolean value.
        The logScale value as a 2-tuple of bools:
        `(x_axis_is_log_scale, y_axis_is_log_scale)`
        """
        return self._logScale

    def SetAbsScale(self, absscale: Tuple[bool, bool] = (True, True)) -> None:
        """
        Set the abs scale boolean value. 绝对值刻度

        Parameters
        ----------
        absscale : tuple of bools, length 2
            A tuple of `(x_axis_is_abs_scale, y_axis_is_abs_scale)` booleans.
        """
        if not isinstance(absscale, tuple) or len(absscale) != 2:
            raise TypeError('absscale must be a 2-tuple of bools, e.g. (False, False)')
        if self.last_draw is not None:
            graphics, xAxis, yAxis = self.last_draw
            graphics.logScale = absscale
            self.last_draw = (graphics, None, None)
        self._xSpec = 'min'
        self._ySpec = 'min'
        self._absScale = absscale

    def GetAbsScale(self) -> Tuple[bool, bool]:
        """
        Get the abs scale boolean value.
        The absScale value as a 2-tuple of bools:
        `(x_axis_is_abs_scale, y_axis_is_abs_scale)`
        """
        return self._absScale

    def SetFontSizeAxis(self, point: int = 10) -> None:
        """Set the tick and axis label font size (default is 10 point)"""
        self._fontSizeAxis = point

    def GetFontSizeAxis(self) -> int:
        """Get current tick and axis label font size in points"""
        return self._fontSizeAxis

    def SetFontSizeTitle(self, point: int = 15) -> None:
        """Set title font size (default is 15 point)"""
        self._fontSizeTitle = point

    def GetFontSizeTitle(self) -> int:
        """Get title font size (default is 15 point)"""
        return self._fontSizeTitle

    def SetFontSizeLegend(self, point: int = 8) -> None:
        """Set legend font size (default is 8 point)"""
        self._fontSizeLegend = point

    def GetFontSizeLegend(self) -> int:
        """Get legend font size (default is 8 point)"""
        return self._fontSizeLegend

    def SetFontSizeLoc(self, point: int = 10) -> None:
        """Set toolbar location font size (default is 10 point)"""
        self._fontSizeLoc = point

    def GetFontSizeLoc(self) -> int:
        """Get toolbar location font size (default is 10 point)"""
        return self._fontSizeLoc

    def SetShowScrollbars(self, value: bool = True) -> None:
        """Set the showScrollbars value. 是否显示滚动条"""
        if not isinstance(value, bool):
            raise TypeError('Value should be True or False')
        if value == self._sb_show:
            # no change, so don't do anything
            return
        self._sb_show = value
        self.sb_vert.Show(value)
        self.sb_hor.Show(value)

        def _do_update():
            self.Layout()
            if self.last_draw is not None:
                self._adjustScrollbars()

        wx.CallAfter(_do_update)

    def GetShowScrollbars(self):
        """Get the showScrollbars value. 是否显示滚动条"""
        return self._sb_show

    def SetUseScientificNotation(self, value: bool = True) -> None:
        """Set the useScientificNotation value. 是否使用科学记数法"""
        if not isinstance(value, bool):
            raise TypeError('Value should be True or False')
        self._useScientificNotation = value

    def GetUseScientificNotation(self) -> bool:
        """Get the useScientificNotation value. 是否使用科学记数法"""
        return self._useScientificNotation

    def SetEnableAntiAliasing(self, value: bool = True) -> None:
        """Set the enableAntiAliasing value."""
        if not isinstance(value, bool):
            raise TypeError('Value should be True or False')
        self._antiAliasingEnabled = value
        self.Redraw()

    def GetEnableAntiAliasing(self) -> bool:
        """Get the enableAntiAliasing value."""
        return self._antiAliasingEnabled

    def SetEnableHiRes(self, value: bool = True) -> None:
        """Set the enableHiRes value."""
        if not isinstance(value, bool):
            raise TypeError('Value should be True or False')
        self._hiResEnabled = value
        self.Redraw()

    def GetEnableHiRes(self):
        """Get the enableHiRes value."""
        return self._hiResEnabled

    def SetEnableGrid(self, value: Union[bool, Tuple[bool, bool]] = True) -> None:
        """
        Set the enableGrid value.
        
        Parameters
        ----------
        value : bool or 2-tuple of bools
            The enableGrid value, whether the grid is enabled.
            A bool or 2-tuple of bools, e.g. (True, True)
            
        If set to a single boolean value, then both X and y grids will be
        enabled (`enableGrid = True`) or disabled (`enableGrid = False`).

        If a 2-tuple of bools, the 1st value is the X (vertical) grid and
        the 2nd value is the Y (horizontal) grid.
        """
        if isinstance(value, bool):
            value = (value, value)
        elif isinstance(value, tuple) and len(value) == 2:
            pass
        else:
            raise TypeError('Value must be a bool or 2-tuple of bool.')

        self._gridEnabled = value
        self.Redraw()

    def GetEnableGrid(self) -> Tuple[bool, bool]:
        """Get the enableGrid value."""
        return self._gridEnabled

    def SetEnableCenterLines(self, value: Union[bool, Literal['Horizontal', 'Vertical']]) -> None:
        """
        Set the enableCenterLines value.

        Parameters
        ----------
        value : bool or {'Horizontal', 'Vertical'}
            The enableCenterLines value, whether the center lines are
            enabled.

        If set to a single boolean value, then both horizontal and vertical
        lines will be enabled or disabled.

        If a string, must be one of `('Horizontal', 'Vertical')`.
        """
        if value not in (True, False, 'Horizontal', 'Vertical'):
            raise TypeError('Value should be True, False, '
                            '\'Horizontal\' or \'Vertical\'')
        self._centerLinesEnabled = value
        self.Redraw()

    def GetEnableCenterLines(self) -> bool:
        """Get the enableCenterLines value."""
        return self._centerLinesEnabled

    def SetEnableDiagonals(self, value: Union[bool, Literal['Bottomleft-Topright', 'Bottomright-Topleft']]) -> None:
        """
        Set the enableDiagonals value.

        Parameters
        ----------
        value : bool or {'Bottomleft-Topright', 'Bottomright-Topleft'}
            The enableDiagonals value, whether the diagonal lines are
            enabled.

        If set to a single boolean value, then both diagonal lines will
        be enabled or disabled.

        If a string, must be one of `('Bottomleft-Topright',
        'Bottomright-Topleft')`.
        """
        # TODO: Rename Bottomleft-TopRight, Bottomright-Topleft
        if value not in (True, False, 'Bottomleft-Topright',
                         'Bottomright-Topleft'):
            raise TypeError('Value should be True, False, '
                '\'Bottomleft-Topright\' or \'Bottomright-Topleft\''
            )
        self._diagonalsEnabled = value
        self.Redraw()

    def GetEnableDiagonals(self) -> bool:
        """Get the enableDiagonals value."""
        return self._diagonalsEnabled

    def SetEnableLegend(self, value: bool = True) -> None:
        """Set the enableLegend value."""
        if not isinstance(value, bool):
            raise TypeError('Value should be True or False')
        self._legendEnabled = value
        self.Redraw()

    def GetEnableLegend(self) -> bool:
        """Get the enableLegend value."""
        return self._legendEnabled

    def SetEnableTitle(self, value: bool = True) -> None:
        """Set the enableTitle value."""
        if not isinstance(value, bool):
            raise TypeError('Value must be a bool.')
        self._titleEnabled = value
        self.Redraw()

    def GetEnableTitle(self) -> bool:
        """Get the enableTitle value."""
        return self._titleEnabled

    def SetEnablePointLabel(self, value: bool = True) -> None:
        """Set the enablePointLabel value."""
        if not isinstance(value, bool):
            raise TypeError('Value must be a bool.')
        self._pointLabelEnabled = value
        self.Redraw()  # will erase existing pointLabel if present
        self.last_PointLabel = None

    def GetEnablePointLabel(self) -> bool:
        """Get the enablePointLabel value."""
        return self._pointLabelEnabled

    def SetEnableAxes(self, value: Union[bool, Tuple[bool, bool], Tuple[bool, bool, bool, bool]]) -> None:
        """
        Set the enableAxes value.
        Parameters
        ----------
        value : bool, 2-tuple of bool, or 4-tuple of bool
            The enableAxes value, whether the axes are enabled.
            
        - If bool, enable or disable all axis
        - If 2-tuple, enable or disable the bottom or left axes: `(bottom, left)`
        - If 4-tuple, enable or disable each axis individually: `(bottom, left, top, right)`
        """
        self._axesEnabled = set_displayside(value)
        self.Redraw()

    def GetEnableAxes(self):
        """Get the enableAxes value."""
        return self._axesEnabled

    def SetEnableAxesValues(self, value: Union[bool, Tuple[bool, bool], Tuple[bool, bool, bool, bool]]) -> None:
        """
        Set the enableAxesValues value.
        Parameters
        ----------
        value : bool, 2-tuple of bool, or 4-tuple of bool
            The enableAxesValues value, whether the axis values are enabled.
            
        - If bool, enable or disable all axis values
        - If 2-tuple, enable or disable the bottom or left axes values: `(bottom, left)`
        - If 4-tuple, enable or disable each axis value individually: `(bottom, left, top, right)`
        """
        self._axesValuesEnabled = set_displayside(value)
        self.Redraw()
    
    def GetEnableAxesValues(self) -> DisplaySide:
        """Get the enableAxesValues value."""
        return self._axesValuesEnabled

    def SetEnableTicks(self, value: Union[bool, Tuple[bool, bool]]) -> None:
        """
        Set the enableTicks value.
        
        Parameters
        ----------
        value : bool or 2-tuple of bools
            The enableTicks value, whether the ticks is enabled.
            A bool or 2-tuple of bools, e.g. (True, True)
            
        - If bool, enable or disable all ticks
        - If 2-tuple, enable or disable the bottom or left ticks: `(bottom, left)`
        - If 4-tuple, enable or disable each tick side individually: `(bottom, left, top, right)`
        """
        self._ticksEnabled = set_displayside(value)
        self.Redraw()
    
    def GetEnableTicks(self) -> DisplaySide:
        """Get the enableTicks value."""
        return self._ticksEnabled

    def SetTickLength(self, length: Sequence[float]) -> None:
        """
        Set the length of the tick marks on an axis.
        
        Parameters
        ----------
        length : tuple of (xlength, ylength)
            The length of the tick marks on an axis.
        """
        if not isinstance(length, (tuple, list)):
            raise TypeError('`length` must be a 2-tuple of ints or floats')
        self._tickLength = length
    
    def GetTickLength(self) -> Sequence[float]:
        """Get the tickLength value."""
        return self._tickLength

    def GetTickLengthPrinterScale(self) -> Tuple[float, float]:
        """Get the tickLength value in printer scale."""
        return (3 * self.printerScale * self._tickLength[0],
                3 * self.printerScale * self._tickLength[1])

    def SetEnablePlotTitle(self, value: bool = True) -> None:
        """Set the enablePlotTitle value."""
        if not isinstance(value, bool):
            raise TypeError('`value` must be boolean True or False')
        self._titleEnabled = value
        self.Redraw()
    
    def GetEnablePlotTitle(self) -> bool:
        """Get the enablePlotTitle value."""
        return self._titleEnabled

    def SetPointLabelFunc(self, func) -> None:
        """
        Set the enablePointLabel value.
        
        :param func: the value of pointLabelFunc.
        :type func: Callable

        TODO: More information is needed.
        Sets the function with custom code for pointLabel drawing
        """
        self._pointLabelFunc = func

    def GetPointLabelFunc(self):
        """Get the enablePointLabel value."""
        return self._pointLabelFunc

    def GetXY(self, event) -> NDArray[np.float64]:
        """Wrapper around _getXY, which handles log scales"""
        xy = self._getXY(event)
        if self._logScale[0]:
            xy[0] = np.power(10, xy[0])
        if self._logScale[1]:
            xy[1] = np.power(10, xy[1])
        return xy

    def _getXY(self, event) -> NDArray[np.float64]:
        """Takes a mouse event and returns the XY user axis values."""
        # x, y = self.PositionScreenToUser(event.GetPosition())
        return self.PositionScreenToUser(event.GetPosition())

    def PositionUserToScreen(self, pntXY) -> NDArray[np.float64]:
        """Converts User position to Screen Coordinates"""
        userPos = np.asarray(pntXY)
        # x, y = userPos * self._pointScale + self._pointShift
        return userPos * self._pointScale + self._pointShift

    def PositionScreenToUser(self, pntXY) -> NDArray[np.float64]:
        """Converts Screen position to User Coordinates"""
        screenPos = np.asarray(pntXY)
        # x, y = (screenPos - self._pointShift) / self._pointScale
        return (screenPos - self._pointShift) / self._pointScale

    def SetXSpec(self,
                 spectype: Union[Sequence[Union[float, int]], float, int,
                                 Literal['none', 'min', 'auto']] = 'auto') -> None:
        """
        Set the xSpec value.

        Parameters
        ----------
        spectype: str, int, or length-2 sequence of floats Default is 'auto'.
            xSpec value
            - 'none' : shows no axis or tick mark values
            - 'min' : shows min bounding box values
            - 'auto' : rounds axis range to sensible values
            - number : like 'min', but with <number> tick marks
            - list or tuple : a list of (min, max) values. Must be length 2.

        .. seealso::
           :attr:`~PlotCanvas.SetYSpec`
        
        """
        ok_values = ('none', 'min', 'auto')
        if spectype not in ok_values and not isinstance(spectype, (int, float)):
            if not isinstance(spectype, (list, tuple)) and len(spectype != 2):
                raise TypeError('xSpec must be \'none\', \'min\', \'auto\', '
                           'a real number, or sequence of real numbers (length 2)')
        self._xSpec = spectype

    def SetYSpec(self, spectype: Union[Sequence[Union[float, int]], float, int,
                                 Literal['none', 'min', 'auto']] = 'auto') -> None:
        """
        Set the ySpec value.

        Parameters
        ----------
        spectype: str, real, or length-2 sequence of reals Default is 'auto'.
            ySpec value
            - 'none' : shows no axis or tick mark values
            - 'min' : shows min bounding box values
            - 'auto' : rounds axis range to sensible values
            - number : like 'min', but with number tick marks
            - list or tuple : a list of (min, max) values. Must be length 2.

        .. seealso::
           :attr:`~PlotCanvas.SetXSpec`
        """
        ok_values = ('none', 'min', 'auto')
        if spectype not in ok_values and not isinstance(spectype, (int, float)):
            if not isinstance(spectype, (list, tuple)) and len(spectype != 2):
                raise TypeError('xSpec must be \'none\', \'min\', \'auto\', '
                           'a real number, or sequence of real numbers (length 2)')
        self._ySpec = spectype

    def GetXSpec(self):
        """Get the xSpec value."""
        return self._xSpec

    def GetYSpec(self):
        """Get the ySpec value."""
        return self._ySpec

    def GetXMaxRange(self) -> NDArray[np.float64]:
        """
        Get the xMaxRange value.
        The plots' maximum X range as a `numpy.ndarray` of `(min, max)`.
        
        .. seealso::
           :attr:`~PlotCanvas.GetYMaxRange`
        """
        xAxis = self._getXMaxRange()
        if self._logScale[0]:
            xAxis = np.power(10, xAxis)
        return xAxis

    def _getXMaxRange(self) -> NDArray[np.float64]:
        """Returns (minX, maxX) x-axis range for displayed graph"""
        graphics = self.last_draw[0]
        p1, p2 = graphics.boundingBox()  # min, max points of graphics
        xAxis = self._axisInterval(self._xSpec, p1[0], p2[0])  # in user units
        return xAxis

    def GetYMaxRange(self) -> NDArray[np.float64]:
        """
        Get the yMaxRange value.
        The plots' maximum Y range as `numpy.ndarray` of `(min, max)`.
        
        .. seealso::
           :attr:`~PlotCanvas.GetXMaxRange`
        """
        yAxis = self._getYMaxRange()
        if self._logScale[1]:
            yAxis = np.power(10, yAxis)
        return yAxis

    def _getYMaxRange(self) -> NDArray[np.float64]:
        """Returns (minY, maxY) y-axis range for displayed graph"""
        graphics = self.last_draw[0]
        p1, p2 = graphics.boundingBox()  # min, max points of graphics
        yAxis = self._axisInterval(self._ySpec, p1[1], p2[1])
        return yAxis

    def GetXCurrentRange(self) -> NDArray[np.float64]:
        """
        Get the xCurrentRange value.
        The plots' X range of the currently displayed portion as
        a `numpy.ndarray` of `(min, max)`

        .. seealso::
           :attr:`~PlotCanvas.GetYCurrentRange`
        """
        xAxis = self._getXCurrentRange()
        if self._logScale[0]:
            xAxis = np.power(10, xAxis)
        return xAxis

    def _getXCurrentRange(self) -> Optional[NDArray[np.float64]]:
        """Returns (minX, maxX) x-axis for currently displayed
        portion of graph"""
        return self.last_draw[1]

    def GetYCurrentRange(self) -> NDArray[np.float64]:
        """
        Get the yCurrentRange value.
        The plots' Y range of the currently displayed portion as
        a `numpy.ndarray` of `(min, max)`

        .. seealso::
           :attr:`~PlotCanvas.GetXCurrentRange`
        """
        yAxis = self._getYCurrentRange()
        if self._logScale[1]:
            yAxis = np.power(10, yAxis)
        return yAxis

    def _getYCurrentRange(self) -> Optional[NDArray[np.float64]]:
        """Returns (minY, maxY) y-axis for currently displayed
        portion of graph"""
        return self.last_draw[2]
#endregion

#region module_methods
    @property
    def print_data(self):
        if not self._print_data:
            self._print_data = wx.PrintData()
            self._print_data.SetPaperId(wx.PAPER_LETTER)
            self._print_data.SetOrientation(wx.LANDSCAPE)
        return self._print_data

    @property
    def pageSetupData(self):
        if not self._pageSetupData:
            self._pageSetupData = wx.PageSetupDialogData()
            self._pageSetupData.SetMarginBottomRight((25, 25))
            self._pageSetupData.SetMarginTopLeft((25, 25))
            self._pageSetupData.SetPrintData(self.print_data)
        return self._pageSetupData

    def PageSetup(self) -> None:
        """Brings up the page setup dialog"""
        data = self.pageSetupData
        data.SetPrintData(self.print_data)
        dlg = wx.PageSetupDialog(self.parent, data)
        try:
            if dlg.ShowModal() == wx.ID_OK:
                data = dlg.GetPageSetupData()
                # updates page parameters from dialog
                self.pageSetupData.SetMarginBottomRight(
                    data.GetMarginBottomRight())
                self.pageSetupData.SetMarginTopLeft(data.GetMarginTopLeft())
                self.pageSetupData.SetPrintData(data.GetPrintData())
                self._print_data = wx.PrintData(
                    data.GetPrintData())  # updates print_data
        finally:
            dlg.Destroy()

    def Printout(self, paper=None) -> None:
        """Print current plot."""
        if paper is not None:
            self.print_data.SetPaperId(paper)
        pdd = wx.PrintDialogData(self.print_data)
        printer = wx.Printer(pdd)
        out = PlotPrintout(self)
        print_ok = printer.Print(self.parent, out)
        if print_ok:
            self._print_data = wx.PrintData(
                printer.GetPrintDialogData().GetPrintData())
        out.Destroy()

    def PrintPreview(self) -> None:
        """Print-preview current plot."""
        printout = PlotPrintout(self)
        printout2 = PlotPrintout(self)
        self.preview = wx.PrintPreview(printout, printout2, self.print_data)
        if not self.preview.IsOk():
            wx.MessageDialog(
                self, 'Print Preview failed.\n'
                'Check that default printer is configured\n', 'Print error',
                wx.OK | wx.CENTRE).ShowModal()
        self.preview.SetZoom(40)
        # search up tree to find frame instance
        frameInst = self
        while not isinstance(frameInst, wx.Frame):
            frameInst = frameInst.GetParent()
        frame = wx.PreviewFrame(self.preview, frameInst, 'Preview')
        frame.Initialize()
        frame.SetPosition(self.GetPosition())
        frame.SetSize((600, 550))
        frame.Centre(wx.BOTH)
        frame.Show(True)

    def SaveFile(self, fileName='') -> bool:
        """
        Saves the file to the type specified in the extension. If no file
        name is specified a dialog box is provided.  Returns True if
        successful, otherwise False.

        .bmp  Save a Windows bitmap file.
        .xbm  Save an X bitmap file.
        .xpm  Save an XPM bitmap file.
        .png  Save a Portable Network Graphics file.
        .jpg  Save a Joint Photographic Experts Group file.

        """
        extensions = {
            'bmp': wx.BITMAP_TYPE_BMP,
            'xbm': wx.BITMAP_TYPE_XBM,
            'xpm': wx.BITMAP_TYPE_XPM,
            'jpg': wx.BITMAP_TYPE_JPEG,
            'png': wx.BITMAP_TYPE_PNG,
        }

        fType = fileName[-3:].lower()
        dlg1 = None
        while fType not in extensions:

            msg_txt = (
                'File name extension\n'  # implicit str concat
                'must be one of\nbmp, xbm, xpm, png, or jpg')

            if dlg1:  # FileDialog exists: Check for extension
                dlg2 = wx.MessageDialog(self, msg_txt, 'File Name Error',
                                        wx.OK | wx.ICON_ERROR)
                try:
                    dlg2.ShowModal()
                finally:
                    dlg2.Destroy()
            # FileDialog doesn't exist: just check one
            else:
                msg_txt = ('Choose a file with extension bmp, '
                           'gif, xbm, xpm, png, or jpg')
                wildcard_str = ('PNG files (*.png)|*.png|'
                                'JPG files (*.jpg)|*.jpg|'
                                'BMP files (*.bmp)|*.bmp|'
                                'XBM files (*.xbm)|*.xbm|'
                                'XPM files (*.xpm)|*.xpm')
                dlg1 = wx.FileDialog(
                    self,
                    msg_txt,
                    '.',
                    '',
                    wildcard_str,
                    wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
                )

            if dlg1.ShowModal() == wx.ID_OK:
                fileName = dlg1.GetPath()
                fType = fileName[-3:].lower()
            else:  # exit without saving
                dlg1.Destroy()
                return False

        if dlg1:
            dlg1.Destroy()

        # Save Bitmap
        res = self._Buffer.SaveFile(fileName, extensions[fType])
        return res

    def Reset(self) -> None:
        """Unzoom the plot."""
        self._labxy_l = 0
        self.last_PointLabel = None  # reset pointLabel
        if self.last_draw is not None:
            self._Draw(self.last_draw[0])

    def ScrollRight(self, units) -> None:
        """Move view right number of axis units."""
        self.last_PointLabel = None  # reset pointLabel
        if self.last_draw is not None:
            graphics, xAxis, yAxis = self.last_draw
            xAxis = xAxis + units
            self._Draw(graphics, xAxis, yAxis)

    def ScrollUp(self, units) -> None:
        """Move view up number of axis units."""
        self.last_PointLabel = None  # reset pointLabel
        if self.last_draw is not None:
            graphics, xAxis, yAxis = self.last_draw
            yAxis = yAxis + units
            self._Draw(graphics, xAxis, yAxis)

    def Draw(self, graphics: PlotGraphics, xAxis=None, yAxis=None, dc=None) -> None:
        """Wrapper around _Draw, which handles log axes"""

        graphics.logScale = self._logScale

        # check Axis is either tuple or none
        err_txt = 'xAxis should be None or (minX, maxX). Got type `{}`.'
        if not isinstance(xAxis, (tuple, np.ndarray, list)) and xAxis is not None:
            raise TypeError(err_txt.format(type(xAxis)))

        err_txt = 'yAxis should be None or (minY, maxY). Got type `{}`.'
        if not isinstance(yAxis, (tuple, np.ndarray, list)) and yAxis is not None:
            raise TypeError(err_txt.format(type(yAxis)))

        # check case for axis = (a,b) where a==b caused by improper zooms
        if xAxis is not None:
            if xAxis[0] == xAxis[1]:
                return
            if self._logScale[0]:
                xAxis = np.log10(xAxis)
        if yAxis is not None:
            if yAxis[0] == yAxis[1]:
                return
            if self._logScale[1]:
                yAxis = np.log10(yAxis)
        self._Draw(graphics, xAxis, yAxis, dc)

    def _Draw(self, graphics: PlotGraphics, xAxis=None, yAxis=None, dc=None) -> None:
        """
        Draw objects in graphics with specified x and y axis.
        graphics- instance of PlotGraphics with list of PolyXXX objects
        xAxis - tuple with (min, max) axis range to view
        yAxis - same as xAxis
        dc - drawing context - doesn't have to be specified.
        If it's not, the offscreen buffer is used
        """

        if dc is None:
            # sets new dc and clears it
            dc = wx.BufferedDC(wx.ClientDC(self.canvas), self._Buffer)
            bbr = wx.Brush(self.GetBackgroundColour(), wx.BRUSHSTYLE_SOLID)
            dc.SetBackground(bbr)
            dc.SetBackgroundMode(wx.SOLID)
            dc.Clear()
        if self._antiAliasingEnabled:
            if not isinstance(dc, wx.GCDC):
                try:
                    dc = wx.GCDC(dc)
                except Exception:  # XXX: Yucky.
                    pass
                else:
                    if self._hiResEnabled:
                        # high precision: each logical unit is 1/20 of a point
                        dc.SetMapMode(wx.MM_TWIPS)
                    self._pointSize = tuple(1.0 / lscale
                                            for lscale in dc.GetLogicalScale())
                    self._setSize()
        elif self._pointSize != (1.0, 1.0):
            self._pointSize = (1.0, 1.0)
            self._setSize()

        if (sys.platform in ('darwin', 'win32') or not isinstance(dc, wx.GCDC)
                or wx.VERSION >= (2, 9)):
            self._fontScale = sum(self._pointSize) / 2.0
        else:
            # on Linux, we need to correct the font size by a certain
            # factor if wx.GCDC is used, to make text the same size as
            # if wx.GCDC weren't used
            screenppi = map(float, wx.ScreenDC().GetPPI())
            ppi = dc.GetPPI()
            self._fontScale = ((screenppi[0] / ppi[0] * self._pointSize[0] +
                                screenppi[1] / ppi[1] * self._pointSize[1]) /
                               2.0)

        graphics._pointSize = self._pointSize

        dc.SetTextForeground(self.GetForegroundColour())
        dc.SetTextBackground(self.GetBackgroundColour())

        # dc.Clear()

        # set font size for every thing but title and legend
        dc.SetFont(self._getFont(self._fontSizeAxis))
        self.labloc.SetFont(self._getFont(self._fontSizeLoc))

        # sizes axis to axis type, create lower left and upper right
        # corners of plot
        if xAxis is None or yAxis is None:
            # One or both axis not specified in Draw
            p1, p2 = graphics.boundingBox()  # min, max points of graphics
            if xAxis is None:
                xAxis = self._axisInterval(self._xSpec, p1[0], p2[0])  # in user units
            if yAxis is None:
                yAxis = self._axisInterval(self._ySpec, p1[1], p2[1])
            # Adjust bounding box for axis spec
            # lower left corner user scale (xmin,ymin)
            p1[0], p1[1] = xAxis[0], yAxis[0]
            # upper right corner user scale (xmax,ymax)
            p2[0], p2[1] = xAxis[1], yAxis[1]
        else:
            # Both axis specified in Draw
            xAxis = np.nan_to_num(xAxis)
            yAxis = np.nan_to_num(yAxis)
            p1, p2 = np.asarray([xAxis, yAxis]).T

        # saves most recent values
        self.last_draw = (graphics, np.asarray(xAxis), np.asarray(yAxis))

        # Get ticks and textExtents for axis if required
        xticks = yticks = None
        xTextExtent = yTextExtent = (0, 0)  # No text for ticks
        if self._xSpec != 'none':
            xticks = self._xticks(xAxis[0], xAxis[1])
            # w h of x axis text last number on axis
            xTextExtent = dc.GetTextExtent(xticks[-1][1])

        if self._ySpec != 'none':
            yticks = self._yticks(yAxis[0], yAxis[1])
            if self._logScale[1]:
                # make sure we have enough room to display SI notation.
                yTextExtent = dc.GetTextExtent('-2e-2')
            else:
                yTextExtentBottom = dc.GetTextExtent(yticks[0][1])
                yTextExtentTop = dc.GetTextExtent(yticks[-1][1])
                yTextExtent = (max(yTextExtentBottom[0], yTextExtentTop[0]),
                               max(yTextExtentBottom[1], yTextExtentTop[1]))

        # TextExtents for Title and Axis Labels
        titleWH, xLabelWH, yLabelWH = self._titleLablesWH(dc, graphics)

        # TextExtents for Legend
        legendBoxWH, legendSymExt, legendTextExt = self._legendWH(dc, graphics)

        # room around graph area
        # use larger of number width or legend width
        rhsW = max(xTextExtent[0], legendBoxWH[0]) + 5 * self._pointSize[0]
        lhsW = yTextExtent[0] + yLabelWH[1] + 3 * self._pointSize[0]
        bottomH = (max(xTextExtent[1], yTextExtent[1] / 2.) + xLabelWH[1] +
                   2 * self._pointSize[1])
        topH = yTextExtent[1] / 2. + titleWH[1]
        # make plot area smaller by text size
        textSize_scale = np.asarray([rhsW + lhsW, bottomH + topH])
        # shift plot area by this amount
        textSize_shift = np.asarray([lhsW, bottomH])

        # Draw the labels (title, axes labels)
        self._drawPlotAreaLabels(dc, graphics, lhsW, rhsW, titleWH, bottomH,
                                 topH, xLabelWH, yLabelWH)

        # drawing legend makers and text
        if self._legendEnabled:
            self._drawLegend(dc, graphics, rhsW, topH, legendBoxWH,
                             legendSymExt, legendTextExt)

        # allow for scaling and shifting plotted points
        scale = ((self.plotbox_size - textSize_scale) / (p2 - p1) * np.array(
            (1, -1)))
        shift = (-p1 * scale + self.plotbox_origin + textSize_shift * np.array(
            (1, -1)))
        # make available for mouse events
        self._pointScale = scale / self._pointSize
        self._pointShift = shift / self._pointSize
        self._drawPlotAreaItems(dc, p1, p2, scale, shift, xticks, yticks)

        graphics.scaleAndShift(scale, shift)
        # thicken up lines and markers if printing
        graphics.printerScale = self.printerScale

        # set clipping area so drawing does not occur outside axis box
        ptx, pty, rectWidth, rectHeight = self._point2ClientCoord(p1, p2)
        # allow graph to overlap axis lines by adding units to w and h
        dc.SetClippingRegion(int(ptx * self._pointSize[0]),
                             int(pty * self._pointSize[1]),
                             int(rectWidth * self._pointSize[0] + 2),
                             int(rectHeight * self._pointSize[1] + 1))
        # Draw the lines and markers
        #        start = _time.perf_counter()
        graphics.draw(dc)
        #        time_str = 'entire graphics drawing took: {} seconds'
        #        print(time_str.format(_time.perf_counter() - start))
        # remove the clipping region
        dc.DestroyClippingRegion()

        self._adjustScrollbars()

    def Redraw(self, dc=None) -> None:
        """Redraw the existing plot."""
        if self.last_draw is not None:
            graphics, xAxis, yAxis = self.last_draw
            self._Draw(graphics, xAxis, yAxis, dc)

    def Clear(self) -> None:
        """Erase the window."""
        self.last_PointLabel = None  # reset pointLabel
        dc = wx.BufferedDC(wx.ClientDC(self.canvas), self._Buffer)
        bbr = wx.Brush(self.GetBackgroundColour(), wx.SOLID)
        dc.SetBackground(bbr)
        dc.SetBackgroundMode(wx.SOLID)
        dc.Clear()
        if self._antiAliasingEnabled:
            try:
                dc = wx.GCDC(dc)
            except Exception:
                pass
        dc.SetTextForeground(self.GetForegroundColour())
        dc.SetTextBackground(self.GetBackgroundColour())
        self.last_draw = None

    def Zoom(self, Center: NDArray, Ratio: Tuple[float, float]) -> None:
        """
        Zoom on the plot
        Centers on the X,Y coords given in Center
        Zooms by the Ratio = (Xratio, Yratio) given
        """
        self.last_PointLabel = None  # reset maker
        x, y = Center
        if self.last_draw is not None:
            graphics, xAxis, yAxis = self.last_draw
            dx = ((xAxis[0] + xAxis[1]) / 2 - x) * Ratio[0]
            dy = ((yAxis[0] + yAxis[1]) / 2 - y) * Ratio[1]
            w = (xAxis[1] - xAxis[0]) * Ratio[0]
            h = (yAxis[1] - yAxis[0]) * Ratio[1]
            xAxis = (x - w / 2 + dx, x + w / 2 + dx)
            yAxis = (y - h / 2 + dy, y + h / 2 + dy)
            self._Draw(graphics, xAxis, yAxis)

    def GetClosestPoints(self, pntXY, pointScaled=True):
        """
        Returns list with
        [curveNumber, legend, index of closest point,
        pointXY, scaledXY, distance]
        list for each curve.
        Returns [] if no curves are being plotted.

        x, y in user coords
        if pointScaled == True based on screen coords
        if pointScaled == False based on user coords
        """
        if self.last_draw is None:
            # no graph available
            return []
        graphics, xAxis, yAxis = self.last_draw
        l = []
        for i, obj in enumerate(graphics):
            # check there are points in the curve
            if len(obj.points) == 0:
                continue  # go to next obj
            # [curveNum, legend, closest pt index, pointXY, scaledXY, dist]
            cn = [i, obj.getLegend()] + obj.getClosestPoint(pntXY, pointScaled)
            l.append(cn)
        return l

    def GetClosestPoint(self, pntXY, pointScaled=True):
        """
        Returns list with
        [curveNumber, legend, index of closest point,
        pointXY, scaledXY, distance]
        list for only the closest curve.
        Returns [] if no curves are being plotted.

        x, y in user coords
        if pointScaled == True based on screen coords
        if pointScaled == False based on user coords
        """
        # closest points on screen based on screen scaling (pointScaled=True)
        closestPts = self.GetClosestPoints(pntXY, pointScaled)
        if closestPts == []:
            return []  # no graph present
        # find one with least distance
        dists = [c[-1] for c in closestPts]
        mdist = min(dists)  # Min dist
        i = dists.index(mdist)  # index for min dist
        return closestPts[i]  # this is the closest point on closest curve

    def UpdatePointLabel(self, mDataDict):
        """
        Updates the pointLabel point on screen with data contained in
        mDataDict.

        mDataDict will be passed to your function set by
        SetPointLabelFunc.  It can contain anything you
        want to display on the screen at the scaledXY point
        you specify.

        This function can be called from parent window with onClick,
        onMotion events etc.
        """
        if self.last_PointLabel is not None:
            # compare pointXY
            if np.any(mDataDict['pointXY'] != self.last_PointLabel['pointXY']):
                # closest changed
                self._drawPointLabel(self.last_PointLabel)  # erase old
                self._drawPointLabel(mDataDict)  # plot new
        else:
            # just plot new with no erase
            self._drawPointLabel(mDataDict)  # plot new
        # save for next erase
        self.last_PointLabel = mDataDict
#endregion

#region event_handlers
    @property
    def _DragEnabled(self):
        return self._dragEnabled

    @_DragEnabled.setter
    def _DragEnabled(self, value):
        assert isinstance(value, bool), 'Value must be a bool.'
        if value:
            self.SetCursor(self.GrabHandCursor)
            if not self.canvas.HasCapture():
                self.canvas.CaptureMouse()
        else:
            self.SetCursor(self.defaultCursor)
            if self.canvas.HasCapture():
                self.canvas.ReleaseMouse()
        self._dragEnabled = value

    @property
    def _ZoomEnabled(self):
        return self._zoomEnabled

    @_ZoomEnabled.setter
    def _ZoomEnabled(self, value: Tuple[bool, str]):
        assert isinstance(value, tuple), 'Value must be a tuple.'
        assert isinstance(value[0], bool), 'Value[0] must be a bool.'
        if value[0]:
            if value[1] == 'x':
                self.SetCursor(self.SizeWECursor)
            elif value[1] == 'y':
                self.SetCursor(self.SizeNSCursor)
            if not self.canvas.HasCapture():
                self.canvas.CaptureMouse()
        else:
            self.SetCursor(self.defaultCursor)
            if self.canvas.HasCapture():
                self.canvas.ReleaseMouse()
        self._zoomEnabled = value[0]

    def OnMouseWheel(self, event) -> None:
        # 鼠标滚轮 缩放图像 前滚放大 后滚缩小
        rotation = event.GetWheelRotation()
        # self.SetCursor(self.MagCursor)
        ratio = (0.9, 0.9) if rotation > 0 else (1.1, 1.1)
        self.Zoom(self._getXY(event), ratio)
        # self.SetCursor(self.defaultCursor)

    def set_labxy(self, pntXY) -> None:
        s = 'X = {:.3f} ; Y = {:.3f}       '.format(pntXY[0], pntXY[1])
        self.labloc.SetLabel(s)
        if self._labxy_l < len(s):
            # self.Layout()
            self.toolbar.Realize()
            self._labxy_l = len(s)

    def OnMotion(self, event) -> None:
        # 实时显示坐标
        self.set_labxy(self.GetXY(event))
        if self.last_draw is None:
            self._move_leave()
            return

        xy = self._getXY(event)
        # print(xy)
        graphics, xAxis, yAxis = self.last_draw
        # 拖拽处理
        if self._DragEnabled:
            dx, dy = xy - self._dragPoint0
            xAxis = xAxis - dx
            yAxis = yAxis - dy
            self._Draw(graphics, xAxis, yAxis)
            self._dragPoint0 = xy
            self._move_leave()
        # 单方向缩放处理
        if self._ZoomEnabled:
            dx, dy = xy - self._zoomPoint1
            if abs(dx) > abs(dy):
                raito = (1 - dx / (xAxis[1] - xAxis[0]), 1)
                self._ZoomEnabled = (True, 'x')
            elif abs(dy) > abs(dx):
                raito = (1, 1 - dy / (yAxis[1] - yAxis[0]))
                self._ZoomEnabled = (True, 'y')
            else:
                raito = (1, 1)
            self.Zoom(self._zoomPoint0, raito)
            self._zoomPoint1 = xy
            self._move_leave()

    def _move_leave(self) -> None:
        if not self.canvas.HasCapture():
            self._DragEnabled = False
            self._ZoomEnabled = (False, '')

    def OnMouseLeftDown(self, event) -> None:
        self._dragPoint0 = self._getXY(event)
        # 开启拖拽
        self._DragEnabled = True

    def OnMouseLeftUp(self, event) -> None:
        # 关闭拖拽
        self._DragEnabled = False

    def OnMouseDoubleClick(self, event) -> None:
        # wx.CallLater(200, self.Reset)
        pass

    def OnMouseRightDown(self, event) -> None:
        self._zoomPoint0 = self._getXY(event)
        self._zoomPoint1 = self._getXY(event)
        # 开启缩放
        self._ZoomEnabled = (True, '')

    def OnMouseRightUp(self, event) -> None:
        # 关闭缩放
        self._ZoomEnabled = (False, '')

    def OnMouseRightDClick(self, event) -> None:
        # wx.CallLater(200, self.Reset)
        pass

    def OnMouseMiddleUp(self, event) -> None:
        self.Reset()

    def _on_save(self, event) -> None:
        self.SaveFile()

    def OnPaint(self, event) -> None:
        # All that is needed here is to draw the buffer to screen
        if self.last_PointLabel is not None:
            self._drawPointLabel(self.last_PointLabel)  # erase old
            self.last_PointLabel = None
        dc = wx.BufferedPaintDC(self.canvas, self._Buffer)
        if self._antiAliasingEnabled:
            try:
                dc = wx.GCDC(dc)
            except Exception:
                pass

    def OnSize(self, event) -> None:
        # The Buffer init is done here, to make sure the buffer is always
        # the same size as the Window
        Size = self.canvas.GetClientSize()
        Size.width = max(1, Size.width)
        Size.height = max(1, Size.height)

        # Make new offscreen bitmap: this bitmap will always have the
        # current drawing in it, so it can be used to save the image to
        # a file, or whatever.
        self._Buffer = wx.Bitmap(Size.width, Size.height)
        self._setSize()

        self.last_PointLabel = None  # reset pointLabel

        if self.last_draw is None:
            self.Clear()
        else:
            graphics, xSpec, ySpec = self.last_draw
            self._Draw(graphics, xSpec, ySpec)

    def OnLeave(self, event) -> None:
        """Used to erase pointLabel when mouse outside window"""
        if self._DragEnabled:
            self._DragEnabled = False # 取消拖拽
        if self._ZoomEnabled:
            self._ZoomEnabled = (False, '') # 取消缩放
        if self.last_PointLabel is not None:
            self._drawPointLabel(self.last_PointLabel)  # erase old
            self.last_PointLabel = None

    def OnScroll(self, event) -> None:
        if not self._adjustingSB:
            self._sb_ignore = True
            sbpos = event.GetPosition()

            if event.GetOrientation() == wx.VERTICAL:
                fullrange = self.sb_vert.GetRange()
                pagesize = self.sb_vert.GetPageSize()
                sbpos = fullrange - pagesize - sbpos
                dist = (sbpos * self._sb_yunit -
                        (self._getYCurrentRange()[0] - self._sb_yfullrange[0]))
                self.ScrollUp(dist)

            if event.GetOrientation() == wx.HORIZONTAL:
                dist = (sbpos * self._sb_xunit -
                        (self._getXCurrentRange()[0] - self._sb_xfullrange[0]))
                self.ScrollRight(dist)
#endregion

#region private_methods
    def _setSize(self, width=None, height=None):
        """DC width and height."""
        if width is None:
            self.width, self.height = self.canvas.GetClientSize()
        else:
            self.width, self.height = width, height
        self.width *= self._pointSize[0]  # high precision
        self.height *= self._pointSize[1]  # high precision
        self.plotbox_size = 0.97 * np.asarray([self.width, self.height])
        xo = 0.5 * (self.width - self.plotbox_size[0])
        yo = self.height - 0.5 * (self.height - self.plotbox_size[1])
        self.plotbox_origin = np.asarray([xo, yo])

    def _setPrinterScale(self, scale):
        """Used to thicken lines and increase marker size for print out."""
        # line thickness on printer is very thin at 600 dot/in. Markers small
        self.printerScale = scale

    def _printDraw(self, printDC):
        """Used for printing."""
        if self.last_draw is not None:
            graphics, xSpec, ySpec = self.last_draw
            self._Draw(graphics, xSpec, ySpec, printDC)

    def _drawPointLabel(self, mDataDict):
        """Draws and erases pointLabels"""
        width = self._Buffer.GetWidth()
        height = self._Buffer.GetHeight()
        if sys.platform not in ('darwin', 'linux'):
            tmp_Buffer = wx.Bitmap(width, height)
            dcs = wx.MemoryDC()
            dcs.SelectObject(tmp_Buffer)
            dcs.Clear()
        else:
            tmp_Buffer = self._Buffer.GetSubBitmap((0, 0, width, height))
            dcs = wx.MemoryDC(self._Buffer)
        self._pointLabelFunc(dcs, mDataDict)  # custom user pointLabel func

        dc = wx.ClientDC(self.canvas)
        dc = wx.BufferedDC(dc, self._Buffer)
        # this will erase if called twice
        dc.Blit(0, 0, width, height, dcs, 0, 0, self._logicalFunction)
        if sys.platform in ('darwin', 'linux'):
            self._Buffer = tmp_Buffer

    def _drawLegend(self, dc: wx.DC, graphics: PlotGraphics, rhsW, topH,
                    legendBoxWH, legendSymExt, legendTextExt):
        """Draws legend symbols and text"""
        # top right hand corner of graph box is ref corner
        trhc = (self.plotbox_origin +
                (self.plotbox_size - [rhsW, topH]) * [1, -1])
        # border space between legend sym and graph box
        legendLHS = .091 * legendBoxWH[0]
        # 1.1 used as space between lines
        lineHeight = max(legendSymExt[1], legendTextExt[1]) * 1.1
        dc.SetFont(self._getFont(self._fontSizeLegend))

        temp1 = trhc[0] + legendLHS
        for i in range(len(graphics)):
            o = graphics[i]
            # s = i * lineHeight
            temp2 = trhc[1] + i * lineHeight * 1.5
            pnt1 = (temp1, temp2)
            pnt2 = (temp1 + legendSymExt[0], temp2)
            pnt = (temp1 + legendSymExt[0] / 2., temp2)
            m1, m2 = np.asarray([pnt1, pnt2]), np.asarray([pnt])
            if isinstance(o, PolyLine):
                o.drawlegend(dc, self.printerScale, coord=m1)
            elif isinstance(o, (PolyMarker, PolyBoxPlot)):
                o.drawlegend(dc, self.printerScale, coord=m2)
            else:
                raise TypeError('object is neither PolyMarker or PolyLine instance')
            # draw legend txt
            pnt = ((temp1 + legendSymExt[0] + 5 * self._pointSize[0]),
                   temp2 - legendTextExt[1] / 2)
            dc.DrawText(o.getLegend(), int(pnt[0]), int(pnt[1]))
        dc.SetFont(self._getFont(self._fontSizeAxis))  # reset

    def _titleLablesWH(self, dc: wx.DC, graphics: PlotGraphics) -> Tuple[wx.Size, wx.Size, wx.Size]:
        """Draws Title and labels and returns width and height for each"""
        # TextExtents for Title and Axis Labels
        dc.SetFont(self._getFont(self._fontSizeTitle))
        if self._titleEnabled:
            title = graphics.GetTitle()
            titleWH = dc.GetTextExtent(title)
        else:
            titleWH = wx.Size(0, 0)
        dc.SetFont(self._getFont(self._fontSizeAxis))
        xLabelWH = dc.GetTextExtent(graphics.GetXLabel())
        yLabelWH = dc.GetTextExtent(graphics.GetYLabel())
        return titleWH, xLabelWH, yLabelWH

    def _legendWH(self, dc: wx.DC, graphics: PlotGraphics) -> Tuple[Tuple[float, float], Tuple[float, float], Tuple[float, float]]:
        """Returns the size in screen units for legend box"""
        if self._legendEnabled is not True:
            legendBoxWH = symExt = txtExt = (0, 0)
        else:
            # find max symbol size
            symExt = graphics.getSymExtent(self.printerScale)
            symExt = (symExt[0] * 3., symExt[1] * 3.)
            # find max legend text extent
            dc.SetFont(self._getFont(self._fontSizeLegend))
            txtList = graphics.getLegendNames()
            txtExt = dc.GetTextExtent(txtList[0])
            for txt in graphics.getLegendNames()[1:]:
                temp: wx.Size = dc.GetTextExtent(txt)
                txtExt:Tuple[float, float] = (max(txtExt[0], temp[0]), 
                                              max(txtExt[1], temp[1]))
            maxW = symExt[0] + txtExt[0]
            maxH = max(symExt[1], txtExt[1])
            # padding .1 for lhs of legend box and space between lines
            maxW = maxW * 1.1
            maxH = maxH * 1.1 * len(txtList)
            dc.SetFont(self._getFont(self._fontSizeAxis))
            legendBoxWH = (maxW, maxH)
        return legendBoxWH, symExt, txtExt

    def _drawRubberBand(self, corner1, corner2):
        """Draws/erases rect box from corner1 to corner2"""
        ptx, pty, rectWidth, rectHeight = self._point2ClientCoord(
            corner1, corner2)
        # draw rectangle
        dc = wx.ClientDC(self.canvas)
        dc.SetPen(wx.Pen(wx.BLACK))
        dc.SetBrush(wx.Brush(wx.WHITE, wx.BRUSHSTYLE_TRANSPARENT))
        dc.SetLogicalFunction(wx.INVERT)
        dc.DrawRectangle(int(ptx), int(pty), int(rectWidth), int(rectHeight))
        dc.SetLogicalFunction(wx.COPY)

    def _getFont(self, size):
        """Take font size, adjusts if printing and returns wx.Font"""
        s = size * self.printerScale * self._fontScale
        of: wx.Font = self.GetFont()
        # Linux speed up to get font from cache rather than X font server
        key = (int(s), of.GetFamily(), of.GetStyle(), of.GetWeight(),
               of.GetUnderlined(), of.GetFaceName())
        font = self._fontCache.get(key, None)
        if font:
            return font  # yeah! cache hit
        else:
            font = wx.Font(int(s), of.GetFamily(),
                           of.GetStyle(), of.GetWeight(), of.GetUnderlined(),
                           of.GetFaceName())
            self._fontCache[key] = font
            return font

    def _point2ClientCoord(self, corner1, corner2) -> Tuple[np.float64, np.float64, NDArray[np.float64], NDArray[np.float64]]:
        """Converts user point coords to client screen int
        coords x,y,width,height"""
        c1 = np.asarray(corner1)
        c2 = np.asarray(corner2)
        # convert to screen coords
        pt1 = c1 * self._pointScale + self._pointShift
        pt2 = c2 * self._pointScale + self._pointShift
        # make height and width positive
        pul = np.minimum(pt1, pt2)  # Upper left corner
        plr = np.maximum(pt1, pt2)  # Lower right corner
        rectWidth, rectHeight = plr - pul
        ptx, pty = pul
        return ptx, pty, rectWidth, rectHeight

    def _axisInterval(self, spec, lower: np.float64, upper: np.float64) -> NDArray[np.float64]:
        """Returns sensible axis range for given spec"""
        if spec == 'none' or spec == 'min' or isinstance(spec, (float, int)):
            if lower == upper:
                return np.asarray((lower - 0.5, upper + 0.5))
            else:
                return np.asarray((lower, upper))
        elif spec == 'auto':
            range = upper - lower
            if range == 0.:
                return np.asarray((lower - 0.5, upper + 0.5))
            log = np.log10(range)
            power = np.floor(log)
            fraction = log - power
            if fraction <= 0.05:
                power = power - 1
            grid = 10.**power
            lower = lower - lower % grid
            mod = upper % grid
            if mod != 0:
                upper = upper - mod + grid
            return np.asarray((lower, upper))

        elif isinstance(spec, tuple):
            lower, upper = spec
            if lower <= upper:
                return np.asarray((lower, upper))
            else:
                return np.asarray((upper, lower))
        else:
            raise ValueError(str(spec) + ': illegal axis specification')

    @TempStyle('pen')
    def _drawGrid(self, dc, p1, p2, scale, shift, xticks, yticks):
        """
        Draws the gridlines

        :param :class:`wx.DC` `dc`: The :class:`wx.DC` to draw on.
        :type `dc`: :class:`wx.DC`
        :param p1: The lower-left hand corner of the plot in plot coords. So,
                   if the plot ranges from x=-10 to 10 and y=-5 to 5, then
                   p1 = (-10, -5)
        :type p1: :class:`np.array`, length 2
        :param p2: The upper-right hand corner of the plot in plot coords. So,
                   if the plot ranges from x=-10 to 10 and y=-5 to 5, then
                   p2 = (10, 5)
        :type p2: :class:`np.array`, length 2
        :param scale: The [X, Y] scaling factor to convert plot coords to
                      DC coords
        :type scale: :class:`np.array`, length 2
        :param shift: The [X, Y] shift values to convert plot coords to
                      DC coords. Must be in plot units, not DC units.
        :type shift: :class:`np.array`, length 2
        :param xticks: The X tick definition
        :type xticks: list of length-2 lists
        :param yticks: The Y tick definition
        :type yticks: list of length-2 lists
        """
        # increases thickness for printing only
        pen = self._gridPen
        penWidth = self.printerScale * pen.GetWidth()
        pen.SetWidth(int(penWidth))
        dc.SetPen(pen)

        x, y, width, height = self._point2ClientCoord(p1, p2)

        if self._xSpec != 'none':
            if self._gridEnabled[0]:
                for x, _ in xticks:
                    pt = scale_and_shift_point(x, p1[1], scale, shift)
                    dc.DrawLine(int(pt[0]), int(pt[1]), int(pt[0]),
                                int(pt[1] - height))

        if self._ySpec != 'none':
            if self._gridEnabled[1]:
                for y, label in yticks:
                    pt = scale_and_shift_point(p1[0], y, scale, shift)
                    dc.DrawLine(int(pt[0]), int(pt[1]), int(pt[0] + width),
                                int(pt[1]))

    @TempStyle('pen')
    def _drawTicks(self, dc, p1, p2, scale, shift, xticks, yticks):
        """Draw the tick marks

        :param :class:`wx.DC` `dc`: The :class:`wx.DC` to draw on.
        :type `dc`: :class:`wx.DC`
        :param p1: The lower-left hand corner of the plot in plot coords. So,
                   if the plot ranges from x=-10 to 10 and y=-5 to 5, then
                   p1 = (-10, -5)
        :type p1: :class:`np.array`, length 2
        :param p2: The upper-right hand corner of the plot in plot coords. So,
                   if the plot ranges from x=-10 to 10 and y=-5 to 5, then
                   p2 = (10, 5)
        :type p2: :class:`np.array`, length 2
        :param scale: The [X, Y] scaling factor to convert plot coords to
                      DC coords
        :type scale: :class:`np.array`, length 2
        :param shift: The [X, Y] shift values to convert plot coords to
                      DC coords. Must be in plot units, not DC units.
        :type shift: :class:`np.array`, length 2
        :param xticks: The X tick definition
        :type xticks: list of length-2 lists
        :param yticks: The Y tick definition
        :type yticks: list of length-2 lists
        """
        # TODO: add option for ticks to extend outside of graph
        #       - done via negative ticklength values?
        #           + works but the axes values cut off the ticks.
        # increases thickness for printing only
        pen = self._tickPen
        penWidth = self.printerScale * pen.GetWidth()
        pen.SetWidth(int(penWidth))
        dc.SetPen(pen)

        # lengthen lines for printing
        xTickLength, yTickLength = self.GetTickLengthPrinterScale()

        ticks = self._ticksEnabled
        if self._xSpec != 'none':  # I don't like this :-/
            if ticks.bottom:
                lines = []
                for x, label in xticks:
                    pt = scale_and_shift_point(x, p1[1], scale, shift)
                    lines.append((int(pt[0]), int(pt[1]), int(pt[0]),
                                  int(pt[1] - xTickLength)))
                dc.DrawLineList(lines)
            if ticks.top:
                lines = []
                for x, label in xticks:
                    pt = scale_and_shift_point(x, p2[1], scale, shift)
                    lines.append((int(pt[0]), int(pt[1]), int(pt[0]),
                                  int(pt[1] + xTickLength)))
                dc.DrawLineList(lines)

        if self._ySpec != 'none':
            if ticks.left:
                lines = []
                for y, label in yticks:
                    pt = scale_and_shift_point(p1[0], y, scale, shift)
                    lines.append((int(pt[0]), int(pt[1]),
                                  int(pt[0] + yTickLength), int(pt[1])))
                dc.DrawLineList(lines)
            if ticks.right:
                lines = []
                for y, label in yticks:
                    pt = scale_and_shift_point(p2[0], y, scale, shift)
                    lines.append((int(pt[0]), int(pt[1]),
                                  int(pt[0] - yTickLength), int(pt[1])))
                dc.DrawLineList(lines)

    @TempStyle('pen')
    def _drawCenterLines(self, dc, p1, p2, scale, shift):
        """Draws the center lines

        :param :class:`wx.DC` `dc`: The :class:`wx.DC` to draw on.
        :type `dc`: :class:`wx.DC`
        :param p1: The lower-left hand corner of the plot in plot coords. So,
                   if the plot ranges from x=-10 to 10 and y=-5 to 5, then
                   p1 = (-10, -5)
        :type p1: :class:`np.array`, length 2
        :param p2: The upper-right hand corner of the plot in plot coords. So,
                   if the plot ranges from x=-10 to 10 and y=-5 to 5, then
                   p2 = (10, 5)
        :type p2: :class:`np.array`, length 2
        :param scale: The [X, Y] scaling factor to convert plot coords to
                      DC coords
        :type scale: :class:`np.array`, length 2
        :param shift: The [X, Y] shift values to convert plot coords to
                      DC coords. Must be in plot units, not DC units.
        :type shift: :class:`np.array`, length 2
        """
        # increases thickness for printing only
        pen = self._centerLinePen
        penWidth = self.printerScale * pen.GetWidth()
        pen.SetWidth(int(penWidth))
        dc.SetPen(pen)

        if self._centerLinesEnabled in ('Horizontal', True):
            y1 = scale[1] * p1[1] + shift[1]
            y2 = scale[1] * p2[1] + shift[1]
            y = (y1 - y2) / 2.0 + y2
            dc.DrawLine(int(scale[0] * p1[0] + shift[0]), int(y),
                        int(scale[0] * p2[0] + shift[0]), int(y))
        if self._centerLinesEnabled in ('Vertical', True):
            x1 = scale[0] * p1[0] + shift[0]
            x2 = scale[0] * p2[0] + shift[0]
            x = (x1 - x2) / 2.0 + x2
            dc.DrawLine(int(x), int(scale[1] * p1[1] + shift[1]), int(x),
                        int(scale[1] * p2[1] + shift[1]))

    @TempStyle('pen')
    def _drawDiagonals(self, dc, p1, p2, scale, shift):
        """
        Draws the diagonal lines.

        :param :class:`wx.DC` `dc`: The :class:`wx.DC` to draw on.
        :type `dc`: :class:`wx.DC`
        :param p1: The lower-left hand corner of the plot in plot coords. So,
                   if the plot ranges from x=-10 to 10 and y=-5 to 5, then
                   p1 = (-10, -5)
        :type p1: :class:`np.array`, length 2
        :param p2: The upper-right hand corner of the plot in plot coords. So,
                   if the plot ranges from x=-10 to 10 and y=-5 to 5, then
                   p2 = (10, 5)
        :type p2: :class:`np.array`, length 2
        :param scale: The [X, Y] scaling factor to convert plot coords to
                      DC coords
        :type scale: :class:`np.array`, length 2
        :param shift: The [X, Y] shift values to convert plot coords to
                      DC coords. Must be in plot units, not DC units.
        :type shift: :class:`np.array`, length 2
        """
        pen = self._diagonalPen
        penWidth = self.printerScale * pen.GetWidth()
        pen.SetWidth(int(penWidth))
        dc.SetPen(pen)

        if self._diagonalsEnabled in ('Bottomleft-Topright', True):
            dc.DrawLine(int(scale[0] * p1[0] + shift[0]),
                        int(scale[1] * p1[1] + shift[1]),
                        int(scale[0] * p2[0] + shift[0]),
                        int(scale[1] * p2[1] + shift[1]))
        if self._diagonalsEnabled in ('Bottomright-Topleft', True):
            dc.DrawLine(int(scale[0] * p1[0] + shift[0]),
                        int(scale[1] * p2[1] + shift[1]),
                        int(scale[0] * p2[0] + shift[0]),
                        int(scale[1] * p1[1] + shift[1]))

    @TempStyle('pen')
    def _drawAxes(self, dc, p1, p2, scale, shift):
        """
        Draw the frame lines.

        :param :class:`wx.DC` `dc`: The :class:`wx.DC` to draw on.
        :type `dc`: :class:`wx.DC`
        :param p1: The lower-left hand corner of the plot in plot coords. So,
                   if the plot ranges from x=-10 to 10 and y=-5 to 5, then
                   p1 = (-10, -5)
        :type p1: :class:`np.array`, length 2
        :param p2: The upper-right hand corner of the plot in plot coords. So,
                   if the plot ranges from x=-10 to 10 and y=-5 to 5, then
                   p2 = (10, 5)
        :type p2: :class:`np.array`, length 2
        :param scale: The [X, Y] scaling factor to convert plot coords to
                      DC coords
        :type scale: :class:`np.array`, length 2
        :param shift: The [X, Y] shift values to convert plot coords to
                      DC coords. Must be in plot units, not DC units.
        :type shift: :class:`np.array`, length 2
        """
        # increases thickness for printing only
        pen = self._axesPen
        penWidth = self.printerScale * pen.GetWidth()
        pen.SetWidth(int(penWidth))
        dc.SetPen(pen)

        axes = self._axesEnabled
        if self._xSpec != 'none':
            if axes.bottom:
                lower, upper = p1[0], p2[0]
                a1 = scale_and_shift_point(lower, p1[1], scale, shift)
                a2 = scale_and_shift_point(upper, p1[1], scale, shift)
                dc.DrawLine(int(a1[0]), int(a1[1]), int(a2[0]), int(a2[1]))
            if axes.top:
                lower, upper = p1[0], p2[0]
                a1 = scale_and_shift_point(lower, p2[1], scale, shift)
                a2 = scale_and_shift_point(upper, p2[1], scale, shift)
                dc.DrawLine(int(a1[0]), int(a1[1]), int(a2[0]), int(a2[1]))

        if self._ySpec != 'none':
            if axes.left:
                lower, upper = p1[1], p2[1]
                a1 = scale_and_shift_point(p1[0], lower, scale, shift)
                a2 = scale_and_shift_point(p1[0], upper, scale, shift)
                dc.DrawLine(int(a1[0]), int(a1[1]), int(a2[0]), int(a2[1]))
            if axes.right:
                lower, upper = p1[1], p2[1]
                a1 = scale_and_shift_point(p2[0], lower, scale, shift)
                a2 = scale_and_shift_point(p2[0], upper, scale, shift)
                dc.DrawLine(int(a1[0]), int(a1[1]), int(a2[0]), int(a2[1]))

    @TempStyle('pen')
    def _drawAxesValues(self, dc, p1, p2, scale, shift, xticks, yticks):
        """
        Draws the axes values: numbers representing each major grid or tick.

        :param :class:`wx.DC` `dc`: The :class:`wx.DC` to draw on.
        :type `dc`: :class:`wx.DC`
        :param p1: The lower-left hand corner of the plot in plot coords. So,
                   if the plot ranges from x=-10 to 10 and y=-5 to 5, then
                   p1 = (-10, -5)
        :type p1: :class:`np.array`, length 2
        :param p2: The upper-right hand corner of the plot in plot coords. So,
                   if the plot ranges from x=-10 to 10 and y=-5 to 5, then
                   p2 = (10, 5)
        :type p2: :class:`np.array`, length 2
        :param scale: The [X, Y] scaling factor to convert plot coords to
                      DC coords
        :type scale: :class:`np.array`, length 2
        :param shift: The [X, Y] shift values to convert plot coords to
                      DC coords. Must be in plot units, not DC units.
        :type shift: :class:`np.array`, length 2
        :param xticks: The X tick definition
        :type xticks: list of length-2 lists
        :param yticks: The Y tick definition
        :type yticks: list of length-2 lists
        """
        # get the tick lengths so that labels don't overlap
        xTickLength, yTickLength = self.GetTickLengthPrinterScale()
        # only care about negative (out of plot area) tick lengths.
        xTickLength = xTickLength if xTickLength < 0 else 0
        yTickLength = yTickLength if yTickLength < 0 else 0

        # TODO: More code duplication? Same as _drawGrid and _drawTicks?
        # TODO: update the bounding boxes when adding right and top values
        axes = self._axesValuesEnabled
        if self._xSpec != 'none':
            if axes.bottom:
                labels = [tick[1] for tick in xticks]
                coords = []
                for x, label in xticks:
                    w = dc.GetTextExtent(label)[0]
                    pt = scale_and_shift_point(x, p1[1], scale, shift)
                    coords.append(
                        (int(pt[0] - w / 2),
                         int(pt[1] + 2 * self._pointSize[1] - xTickLength)))
                dc.DrawTextList(labels, coords)

            if axes.top:
                labels = [tick[1] for tick in xticks]
                coords = []
                for x, label in xticks:
                    w, h = dc.GetTextExtent(label)
                    pt = scale_and_shift_point(x, p2[1], scale, shift)
                    coords.append((int(pt[0] - w / 2),
                                   int(pt[1] - 2 * self._pointSize[1] - h -
                                       xTickLength)))
                dc.DrawTextList(labels, coords)

        if self._ySpec != 'none':
            if axes.left:
                h = dc.GetCharHeight()
                labels = [tick[1] for tick in yticks]
                coords = []
                for y, label in yticks:
                    w = dc.GetTextExtent(label)[0]
                    pt = scale_and_shift_point(p1[0], y, scale, shift)
                    coords.append(
                        (int(pt[0] - w - 3 * self._pointSize[0] + yTickLength),
                         int(pt[1] - 0.5 * h)))
                dc.DrawTextList(labels, coords)

            if axes.right:
                h = dc.GetCharHeight()
                labels = [tick[1] for tick in yticks]
                coords = []
                for y, label in yticks:
                    w = dc.GetTextExtent(label)[0]
                    pt = scale_and_shift_point(p2[0], y, scale, shift)
                    coords.append(
                        (int(pt[0] + 3 * self._pointSize[0] + yTickLength),
                         int(pt[1] - 0.5 * h)))
                dc.DrawTextList(labels, coords)

    @TempStyle('pen')
    def _drawPlotAreaItems(self, dc, p1, p2, scale, shift, xticks, yticks):
        """
        Draws each frame element

        :param :class:`wx.DC` `dc`: The :class:`wx.DC` to draw on.
        :type `dc`: :class:`wx.DC`
        :param p1: The lower-left hand corner of the plot in plot coords. So,
                   if the plot ranges from x=-10 to 10 and y=-5 to 5, then
                   p1 = (-10, -5)
        :type p1: :class:`np.array`, length 2
        :param p2: The upper-right hand corner of the plot in plot coords. So,
                   if the plot ranges from x=-10 to 10 and y=-5 to 5, then
                   p2 = (10, 5)
        :type p2: :class:`np.array`, length 2
        :param scale: The [X, Y] scaling factor to convert plot coords to
                      DC coords
        :type scale: :class:`np.array`, length 2
        :param shift: The [X, Y] shift values to convert plot coords to
                      DC coords. Must be in plot units, not DC units.
        :type shift: :class:`np.array`, length 2
        :param xticks: The X tick definition
        :type xticks: list of length-2 lists
        :param yticks: The Y tick definition
        :type yticks: list of length-2 lists
        """
        if self._gridEnabled:
            self._drawGrid(dc, p1, p2, scale, shift, xticks, yticks)

        if self._ticksEnabled:
            self._drawTicks(dc, p1, p2, scale, shift, xticks, yticks)

        if self._centerLinesEnabled:
            self._drawCenterLines(dc, p1, p2, scale, shift)

        if self._diagonalsEnabled:
            self._drawDiagonals(dc, p1, p2, scale, shift)

        if self._axesEnabled:
            self._drawAxes(dc, p1, p2, scale, shift)

        if self._axesValuesEnabled:
            self._drawAxesValues(dc, p1, p2, scale, shift, xticks, yticks)

    @TempStyle('pen')
    def _drawPlotTitle(self, dc, graphics: PlotGraphics, lhsW, rhsW, titleWH):
        """
        Draws the plot title
        """
        dc.SetFont(self._getFont(self._fontSizeTitle))
        titlePos = (self.plotbox_origin[0] + lhsW +
                    (self.plotbox_size[0] - lhsW - rhsW) / 2. -
                    titleWH[0] / 2.,
                    self.plotbox_origin[1] - self.plotbox_size[1])
        dc.DrawText(graphics.GetTitle(), int(titlePos[0]), int(titlePos[1]))

    def _drawAxesLabels(self, dc, graphics: PlotGraphics, lhsW, rhsW, bottomH, topH,
                        xLabelWH, yLabelWH):
        """
        Draws the axes labels
        """
        # get the tick lengths so that labels don't overlap
        xTickLength, yTickLength = self.GetTickLengthPrinterScale()
        # only care about negative (out of plot area) tick lengths.
        xTickLength = xTickLength if xTickLength < 0 else 0
        yTickLength = yTickLength if yTickLength < 0 else 0

        # TODO: axes values get big when this is turned off
        dc.SetFont(self._getFont(self._fontSizeAxis))
        xLabelPos = (self.plotbox_origin[0] + lhsW +
                     (self.plotbox_size[0] - lhsW - rhsW) / 2. -
                     xLabelWH[0] / 2.,
                     self.plotbox_origin[1] - xLabelWH[1] - yTickLength)
        dc.DrawText(graphics.GetXLabel(), int(xLabelPos[0]), int(xLabelPos[1]))
        yLabelPos = (self.plotbox_origin[0] - 3 * self._pointSize[0] +
                     xTickLength, self.plotbox_origin[1] - bottomH -
                     (self.plotbox_size[1] - bottomH - topH) / 2. +
                     yLabelWH[0] / 2.)
        if graphics.GetYLabel():  # bug fix for Linux
            dc.DrawRotatedText(graphics.GetYLabel(), int(yLabelPos[0]),
                               int(yLabelPos[1]), 90)

    @TempStyle('pen')
    def _drawPlotAreaLabels(self, dc, graphics, lhsW, rhsW, titleWH, bottomH,
                            topH, xLabelWH, yLabelWH):
        """
        Draw the plot area labels.
        """
        if self._titleEnabled:
            self._drawPlotTitle(dc, graphics, lhsW, rhsW, titleWH)

        if self._axesLabelsEnabled:
            self._drawAxesLabels(dc, graphics, lhsW, rhsW, bottomH, topH,
                                 xLabelWH, yLabelWH)

    def _xticks(self, *args):
        if self._logScale[0]:
            return self._logticks(*args)
        else:
            attr = {'numticks': self._xSpec}
            return self._ticks(*args, **attr)

    def _yticks(self, *args):
        if self._logScale[1]:
            return self._logticks(*args)
        else:
            attr = {'numticks': self._ySpec}
            return self._ticks(*args, **attr)

    def _logticks(self, lower, upper):
        #lower,upper = map(np.log10,[lower,upper])
        # print('logticks',lower,upper)
        ticks = []
        mag = np.power(10, np.floor(lower))
        if upper - lower > 6:
            t = np.power(10, np.ceil(lower))
            base = np.power(10, np.floor((upper - lower) / 6))

            def inc(t):
                return t * base - t
        else:
            t = np.ceil(np.power(10, lower) / mag) * mag

            def inc(t):
                return 10**int(np.floor(np.log10(t) + 1e-16))

        majortick = int(np.log10(mag))
        while t <= pow(10, upper):
            if majortick != int(np.floor(np.log10(t) + 1e-16)):
                majortick = int(np.floor(np.log10(t) + 1e-16))
                ticklabel = '1e%d' % majortick
            else:
                if upper - lower < 2:
                    minortick = int(t / pow(10, majortick) + .5)
                    ticklabel = '%de%d' % (minortick, majortick)
                else:
                    ticklabel = ''
            ticks.append((np.log10(t), ticklabel))
            t += inc(t)
        if len(ticks) == 0:
            ticks = [(0, '')]
        return ticks

    def _ticks(self, lower, upper, numticks=None):
        if isinstance(numticks, (float, int)):
            ideal = (upper - lower) / float(numticks)
        else:
            ideal = (upper - lower) / 7.
        log = np.log10(ideal)
        power = np.floor(log)
        if isinstance(numticks, (float, int)):
            grid = ideal
        else:
            fraction = log - power
            factor = 1.
            error = fraction
            for f, lf in self._multiples:
                e = np.fabs(fraction - lf)
                if e < error:
                    error = e
                    factor = f
            grid = factor * 10.**power
        if self._useScientificNotation and (power > 4 or power < -4):
            format = '%+7.1e'
        elif power >= 0:
            digits = max(1, int(power))
            format = '%' + repr(digits) + '.0f'
        else:
            digits = -int(power)
            format = '%' + repr(digits + 2) + '.' + repr(digits) + 'f'
        ticks = []
        t = -grid * np.floor(-lower / grid)
        while t <= upper:
            if t == -0:
                t = 0
            ticks.append((t, format % (t, )))
            t = t + grid
        return ticks

    _multiples = [(2., np.log10(2.)), (5., np.log10(5.))]

    def _adjustScrollbars(self):
        if self._sb_ignore:
            self._sb_ignore = False
            return

        if not self._sb_show:
            return

        self._adjustingSB = True
        needScrollbars = False

        # horizontal scrollbar
        r_current = self._getXCurrentRange()
        r_max = list(self._getXMaxRange())
        sbfullrange = float(self.sb_hor.GetRange())

        r_max[0] = min(r_max[0], r_current[0])
        r_max[1] = max(r_max[1], r_current[1])

        self._sb_xfullrange = r_max

        unit = (r_max[1] - r_max[0]) / float(self.sb_hor.GetRange())
        pos = int((r_current[0] - r_max[0]) / unit)

        if pos >= 0:
            pagesize = int((r_current[1] - r_current[0]) / unit)

            self.sb_hor.SetScrollbar(pos, pagesize, int(sbfullrange), pagesize)
            self._sb_xunit = unit
            needScrollbars = needScrollbars or (pagesize != sbfullrange)
        else:
            self.sb_hor.SetScrollbar(0, 1000, 1000, 1000)

        # vertical scrollbar
        r_current = self._getYCurrentRange()
        r_max = list(self._getYMaxRange())
        sbfullrange = float(self.sb_vert.GetRange())

        r_max[0] = min(r_max[0], r_current[0])
        r_max[1] = max(r_max[1], r_current[1])

        self._sb_yfullrange = r_max

        unit = (r_max[1] - r_max[0]) / sbfullrange
        pos = int((r_current[0] - r_max[0]) / unit)

        if pos >= 0:
            pagesize = int((r_current[1] - r_current[0]) / unit)
            pos = (sbfullrange - 1 - pos - pagesize)
            self.sb_vert.SetScrollbar(int(pos), pagesize, int(sbfullrange),
                                      pagesize)
            self._sb_yunit = unit
            needScrollbars = needScrollbars or (pagesize != sbfullrange)
        else:
            self.sb_vert.SetScrollbar(0, 1000, 1000, 1000)

        self.sb_hor.Show(needScrollbars)
        self.sb_vert.Show(needScrollbars)
        self._adjustingSB = False
#endregion