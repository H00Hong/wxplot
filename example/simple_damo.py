"""
plot example
"""
import wx
import sys, os.path

sys.path.append(os.path.split(os.path.dirname(__file__))[0])
import wxplot


def line_ls():
    data = [[(x, (x + i)**2) for x in range(10)] for i in range(10)]  # 定义数据
    linestyle = ['-', ':', '--', '-.', '__']
    marker = ['circle', 'square', 'triangle', 'none', 'none']
    colour = ['gray', 'red', 'blue', 'purple', 'green']
    lines = [
        wxplot.PolyLine(data[i],
                        colour=colour[i],
                        marker=marker[i],
                        style=linestyle[i],
                        width=2,
                        size=2,
                        legend=f'line{i}') for i in range(5)
    ]

    graphics = wxplot.PlotGraphics(lines,
                                   title='Line Plot',
                                   xLabel='X',
                                   yLabel='Y')  # 定义图形，线段，标题，X轴标签，Y轴标签
    return graphics


class PlotFrame(wx.Frame):

    def __init__(self, title='example'):
        wx.Frame.__init__(self, None, title=title, size=(800, 600))

        self.graphics = line_ls()

        self.figure = wxplot.PlotCanvas(self)  # 定义画布
        self.figure.SetEnableLegend(True)  # 启用图例
        self.figure.SetGridPen('--', )  # 设置网格线
        self.figure.Draw(self.graphics)  # 绘制图形
        # self.figure.SetLogScale((False,True))

        self.Centre()  # 居中
        self.Show()  # 显示窗口


if __name__ == '__main__':
    app = wx.App()
    PlotFrame()
    app.MainLoop()
