"""WaveformPanel: live pressure, flow and volume curves (pyqtgraph), 10 s window, sweep mode.

Like a bedside monitor, the trace is written left to right and a short gap is erased ahead of the
write position. Samples arrive at 50 Hz; the screen redraws at 25 fps. Y ranges are fixed per patient
category so the curves do not jump around.
"""
from __future__ import annotations

import numpy as np
import pyqtgraph as pg

from hmi.device.messages import Sample
from hmi.model.patient import Category
from hmi.qt import QtCore
from hmi.ui.theme import BG, BORDER, MUTED, WAVE_COLORS

WINDOW_S = 10.0
POINTS = 500          # 10 s x 50 Hz
GAP_POINTS = 15       # 0.3 s erase gap ahead of the sweep
REDRAW_MS = 40        # 25 fps
TRACES = (("pressure", "Paw", "cmH2O"), ("flow", "Flow", "L/min"), ("volume", "Volume", "mL"))
Y_RANGES = {
    Category.ADULT: {"pressure": (-2, 50), "flow": (-100, 100), "volume": (0, 800)},
    Category.PEDIATRIC: {"pressure": (-2, 40), "flow": (-50, 50), "volume": (0, 300)},
}


class WaveformPanel(pg.GraphicsLayoutWidget):
    def __init__(self):
        super().__init__()
        # pg.GraphicsLayoutWidget.__init__ sets an instance attribute `clear` (bound to its
        # internal layout's clear()), which would shadow our own clear() method below.
        self.__dict__.pop("clear", None)
        pg.setConfigOptions(antialias=False)
        self.setBackground(BG)
        self._x = np.linspace(0.0, WINDOW_S, POINTS, endpoint=False)
        self._data = {key: np.full(POINTS, np.nan) for key, _, _ in TRACES}
        self._plots: dict[str, pg.PlotItem] = {}
        self._curves: dict[str, pg.PlotDataItem] = {}
        self.index = 0
        self._dirty = False
        for row, (key, title, unit) in enumerate(TRACES):
            plot = self.addPlot(row=row, col=0)
            plot.setMenuEnabled(False)
            plot.setMouseEnabled(x=False, y=False)
            plot.hideButtons()
            plot.showGrid(x=False, y=True, alpha=0.15)
            plot.setXRange(0, WINDOW_S, padding=0)
            plot.setLabel("left", f"{title} ({unit})", color=WAVE_COLORS[key])
            plot.getAxis("left").setWidth(64)
            plot.getAxis("left").setTextPen(MUTED)
            plot.getAxis("bottom").setTextPen(MUTED)
            plot.getAxis("bottom").setStyle(showValues=(row == len(TRACES) - 1))
            plot.addLine(y=0, pen=pg.mkPen(BORDER))
            self._curves[key] = plot.plot(self._x, self._data[key], pen=pg.mkPen(WAVE_COLORS[key], width=2),
                                          connect="finite")
            self._plots[key] = plot
        self.set_category(Category.ADULT)
        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self.redraw)
        self._timer.start(REDRAW_MS)

    def set_category(self, category: Category) -> None:
        for key, (low, high) in Y_RANGES[category].items():
            self._plots[key].setYRange(low, high, padding=0)

    def add_sample(self, s: Sample) -> None:
        i = self.index
        self._data["pressure"][i] = s.pressure
        self._data["flow"][i] = s.flow
        self._data["volume"][i] = s.volume
        gap = (i + 1 + np.arange(GAP_POINTS)) % POINTS
        for values in self._data.values():
            values[gap] = np.nan
        self.index = (i + 1) % POINTS
        self._dirty = True

    def redraw(self) -> None:
        if not self._dirty:
            return
        for key, curve in self._curves.items():
            curve.setData(self._x, self._data[key], connect="finite")
        self._dirty = False

    def clear(self) -> None:
        for values in self._data.values():
            values[:] = np.nan
        self.index = 0
        self._dirty = True

    def trace(self, key: str) -> np.ndarray:
        return self._data[key]
