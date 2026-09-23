"""The single place where Qt is imported.

pyqtgraph.Qt picks whichever binding is installed (PySide6, PyQt6 or PyQt5), so the same code runs
on the Windows laptop (PySide6 from pip) and on the Raspberry Pi (PySide6 or apt's python3-pyqt5).
Every other module imports Qt names from here.
"""
from pyqtgraph.Qt import QT_LIB, QtCore, QtGui, QtWidgets  # noqa: F401

Signal = QtCore.Signal
Slot = QtCore.Slot

# QShortcut lives in QtGui on Qt 6 and in QtWidgets on Qt 5.
QShortcut = getattr(QtGui, "QShortcut", None) or QtWidgets.QShortcut
