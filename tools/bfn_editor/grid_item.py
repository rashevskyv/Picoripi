from PyQt6 import QtCore, QtGui, QtWidgets

class GridItem(QtWidgets.QGraphicsItem):
    def __init__(self, cw: int, ch: int, rows: int, cols: int, parent=None):
        super().__init__(parent)
        self.cw = int(cw)
        self.ch = int(ch)
        self.rows = int(rows)
        self.cols = int(cols)
        self.real_w = self.cw
        self.real_h = self.ch
        self.pen = QtGui.QPen(QtGui.QColor('#446622aa'))
        self.pen.setWidth(1)
        self.pen.setCosmetic(True)

    def boundingRect(self) -> QtCore.QRectF:
        w = self.rows * self.real_w
        h = self.cols * self.real_h
        return QtCore.QRectF(0, 0, w, h)

    def paint(self, painter: QtGui.QPainter, option, widget=None):
        painter.setPen(self.pen)
        # vertical lines
        for gx in range(self.rows + 1):
            x = gx * self.real_w
            painter.drawLine(x, 0, x, self.cols * self.real_h)
        # horizontal lines
        for gy in range(self.cols + 1):
            y = gy * self.real_h
            painter.drawLine(0, y, self.rows * self.real_w, y)

