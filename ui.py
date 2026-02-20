from __future__ import annotations

from PySide6.QtCore import Qt, QSize, Slot
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QStackedWidget, QMessageBox, QFileDialog,
    QComboBox, QSlider, QDoubleSpinBox, QGroupBox, QGridLayout,
    QRadioButton, QButtonGroup, QTextEdit, QFrame, QSpinBox, QCheckBox
)

from backend import AppState, MachineController


INFO_TEXT = (
   ""
)


def _title_label(text: str) -> QLabel:
    lbl = QLabel(text)
    f = QFont()
    f.setPointSize(20)
    f.setBold(True)
    lbl.setFont(f)
    return lbl


def _subtle_label(text: str) -> QLabel:
    lbl = QLabel(text)
    f = QFont()
    f.setPointSize(10)
    f.setBold(False)
    lbl.setFont(f)
    lbl.setStyleSheet("color: #666;")
    return lbl


class RectanglePreview(QWidget):
    """Live preview of safe area and current rectangle (green=valid, red=invalid)."""

    def __init__(self, controller: "MachineController", state: "AppState") -> None:
        super().__init__()
        self.controller = controller
        self.state = state
        self.setMinimumHeight(240)
        self.state.changed.connect(self.update)

    def paintEvent(self, event) -> None:
        from PySide6.QtGui import QPainter, QPen, QColor, QBrush

        BED_W = 170.0
        BED_H = 230.0

        p = self.state.params
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        margin = 16.0
        avail_w = max(10.0, float(self.width()) - 2 * margin)
        avail_h = max(10.0, float(self.height()) - 2 * margin)
        side = max(10.0, min(avail_w, avail_h))

        ox = (float(self.width()) - side) / 2.0
        oy = (float(self.height()) - side) / 2.0

        def mx(x_mm: float) -> float:
            return ox + (x_mm / BED_W) * side

        def my(y_mm: float) -> float:
            return oy + side - (y_mm / BED_H) * side

        # Bed outline
        painter.setPen(QPen(QColor(200, 200, 200), 2))
        painter.setBrush(QBrush(Qt.NoBrush))
        #painter.drawRect(ox, oy, side, side)

        # Usable area outline
        sx0 = float(p.safe_x_min)
        sx1 = float(p.safe_x_max)
        sy0 = float(p.safe_y_min)
        sy1 = float(p.safe_y_max)

        painter.setPen(QPen(QColor(120, 180, 255), 2))
        painter.setBrush(QBrush(Qt.NoBrush))
        rx = mx(sx0)
        ry = my(sy1)
        rw = mx(sx1) - mx(sx0)
        rh = my(sy0) - my(sy1)
        painter.drawRect(rx, ry, rw, rh)

        # Requested rectangle
        orient = str(p.fiber_orientation)
        L = float(p.fiber_length)
        Wd = float(p.fiber_width)
        sx = float(p.start_x)
        sy = float(p.start_y + 20)

        if orient == "Horizontal":
            x0, x1 = sx, sx + L
            y0, y1 = sy, sy + Wd
        else:
            x0, x1 = sx, sx + Wd
            y0, y1 = sy, sy + L

        try:
            _ = self.controller.get_draw_rectangle()
            valid = True
        except Exception:
            valid = False

        painter.setPen(QPen(QColor(30, 30, 30), 2))
        painter.setBrush(QBrush(QColor(0, 180, 0, 110) if valid else QColor(200, 0, 0, 110)))

        rrx = mx(x0)
        rry = my(y1)
        rrw = mx(x1) - mx(x0)
        rrh = my(y0) - my(y1)
        painter.drawRect(rrx, rry, rrw, rrh)




class MainWindow(QMainWindow):
    def __init__(self, state: AppState, controller: MachineController) -> None:
        super().__init__()
        self.state = state
        self.controller = controller

        self.setWindowTitle("Nanofiber Machine")
        self.setMinimumSize(QSize(980, 780))

        root = QWidget()
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        self.setCentralWidget(root)

        self.sidebar = QListWidget()
        self.sidebar.setFixedWidth(190)
        self.sidebar.setFrameShape(QFrame.NoFrame)
        self.sidebar.setSpacing(2)

        self.stack = QStackedWidget()

        root_layout.addWidget(self.sidebar)
        root_layout.addWidget(self.stack, 1)

        self.page_welcome = WelcomePage(self)
        self.page_draw = DrawPage(self)
        self.page_syringe = SyringePage(self)
        self.page_summary = SummaryPage(self)
        self.page_connection = ConnectionPage(self)
        self.page_log = LogPage(self)

        self._add_page("Welcome", self.page_welcome)
        self._add_page("Draw", self.page_draw)
        self._add_page("Syringe", self.page_syringe)
        self._add_page("Summary", self.page_summary)
        self._add_page("Connection", self.page_connection)
        self._add_page("Log", self.page_log)

        self.sidebar.currentRowChanged.connect(self.stack.setCurrentIndex)

        self._set_project_mode(False)
        self.sidebar.setCurrentRow(0)

        self.controller.connection_changed.connect(self.page_connection.on_connection_changed)
        self.state.log.connect(self.page_log.append_log)

    def _add_page(self, title: str, widget: QWidget) -> None:
        self.stack.addWidget(widget)
        self.sidebar.addItem(QListWidgetItem(title))

    def _set_project_mode(self, enabled: bool) -> None:
        for i in range(1, self.sidebar.count()):
            item = self.sidebar.item(i)
            item.setFlags(item.flags() | Qt.ItemIsEnabled if enabled else item.flags() & ~Qt.ItemIsEnabled)

    def go(self, name: str) -> None:
        mapping = {"Welcome": 0, "Draw": 1, "Syringe": 2, "Summary": 3, "Connection": 4, "Log": 5}
        self.sidebar.setCurrentRow(mapping[name])

    def start_new_project(self) -> None:
        self._set_project_mode(True)
        self.setWindowTitle("Nanofiber Machine - New Project")
        self.go("Draw")
        self.controller.log("New project")

    def load_project_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Load Project", "", "JSON files (*.json)")
        if not path:
            return
        try:
            self.controller.load_project(path)
            self._set_project_mode(True)
            self.setWindowTitle(f"Nanofiber Machine - {path.split('/')[-1]}")
            self.go("Draw")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not load project:\n{e}")

    def save_project_dialog(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Save Project", "", "JSON files (*.json)")
        if not path:
            return
        if not path.lower().endswith(".json"):
            path += ".json"
        try:
            self.controller.save_project(path)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not save project:\n{e}")

    def save_pdf_dialog(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Save PDF", "", "PDF files (*.pdf)")
        if not path:
            return
        if not path.lower().endswith(".pdf"):
            path += ".pdf"
        try:
            self.controller.save_pdf(path)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not save PDF:\n{e}")

    def show_info(self) -> None:
        QMessageBox.information(self, "Application info", INFO_TEXT)


class WelcomePage(QWidget):
    def __init__(self, mw: MainWindow) -> None:
        super().__init__()
        self.mw = mw

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(16)

        title = QLabel("NanoFiber Fabrication Interface\nfor Ender printer")
        f = QFont()
        f.setPointSize(26)
        f.setBold(True)
        title.setFont(f)
        title.setAlignment(Qt.AlignCenter)

        btn_row = QHBoxLayout()
        self.btn_new = QPushButton("New")
        self.btn_load = QPushButton("Load")
        self.btn_info = QPushButton("Info")

        self.btn_new.setMinimumHeight(48)
        self.btn_load.setMinimumHeight(48)
        self.btn_info.setMinimumHeight(40)

        btn_row.addWidget(self.btn_new)
        btn_row.addWidget(self.btn_load)

        layout.addWidget(title)
        layout.addLayout(btn_row)
        layout.addWidget(self.btn_info, 0, Qt.AlignCenter)

        self.btn_new.clicked.connect(self.mw.start_new_project)
        self.btn_load.clicked.connect(self.mw.load_project_dialog)
        self.btn_info.clicked.connect(self.mw.show_info)


class DrawPage(QWidget):
    def __init__(self, mw: MainWindow) -> None:
        super().__init__()
        self.mw = mw
        self.state = mw.state
        self.controller = mw.controller

        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 14, 18, 14)
        outer.setSpacing(10)

        outer.addWidget(_title_label("Drawing"))

        # Force rectangle mode (legacy UI removed)
        self.state.set_param("mode", "CustomCentered")

        # ---------------- Rectangle parameters ----------------
        rect = QGroupBox("Rectangle parameters")
        rect_grid = QGridLayout(rect)
        rect_grid.setHorizontalSpacing(14)
        rect_grid.setVerticalSpacing(10)

        self.fiber_orientation = QComboBox()
        self.fiber_orientation.addItems(["Horizontal", "Vertical"])
        self.fiber_orientation.currentTextChanged.connect(lambda t: self.state.set_param("fiber_orientation", t))

        self.fiber_length = QDoubleSpinBox()
        self.fiber_length.setDecimals(2)
        self.fiber_length.setRange(0.0, 10000.0)
        self.fiber_length.setSingleStep(1.0)
        self.fiber_length.valueChanged.connect(lambda v: self.state.set_param("fiber_length", float(v)))

        self.fiber_width = QDoubleSpinBox()
        self.fiber_width.setDecimals(2)
        self.fiber_width.setRange(0.0, 10000.0)
        self.fiber_width.setSingleStep(1.0)
        self.fiber_width.valueChanged.connect(lambda v: self.state.set_param("fiber_width", float(v)))

        self.fiber_spacing = QDoubleSpinBox()
        self.fiber_spacing.setDecimals(2)
        self.fiber_spacing.setRange(0.01, 10000.0)
        self.fiber_spacing.setSingleStep(0.1)
        self.fiber_spacing.valueChanged.connect(lambda v: self.state.set_param("fiber_spacing", float(v)))

        self.start_x = QDoubleSpinBox()
        self.start_x.setDecimals(2)
        self.start_x.setRange(-1000.0, 1000.0)
        self.start_x.setSingleStep(1.0)
        self.start_x.valueChanged.connect(lambda v: self.state.set_param("start_x", float(v)))

        self.start_y = QDoubleSpinBox()
        self.start_y.setDecimals(2)
        self.start_y.setRange(-1000.0, 1000.0)
        self.start_y.setSingleStep(1.0)
        self.start_y.valueChanged.connect(lambda v: self.state.set_param("start_y", float(v)))

        rect_grid.addWidget(QLabel("Orientation"), 0, 0)
        rect_grid.addWidget(self.fiber_orientation, 0, 1)
        rect_grid.addWidget(QLabel("Length (mm)"), 1, 0)
        rect_grid.addWidget(self.fiber_length, 1, 1)
        rect_grid.addWidget(QLabel("Width (mm)"), 2, 0)
        rect_grid.addWidget(self.fiber_width, 2, 1)
        rect_grid.addWidget(QLabel("Spacing (mm)"), 3, 0)
        rect_grid.addWidget(self.fiber_spacing, 3, 1)
        rect_grid.addWidget(QLabel("Starting X (mm)"), 4, 0)
        rect_grid.addWidget(self.start_x, 4, 1)
        rect_grid.addWidget(QLabel("Starting Y (mm)"), 5, 0)
        rect_grid.addWidget(self.start_y, 5, 1)

        outer.addWidget(rect)

        outer.addWidget(_subtle_label("Preview (230×230 bed, usable area, rectangle)"))
        self.preview = RectanglePreview(self.controller, self.state)
        outer.addWidget(self.preview)

        # ---------------- Common motion/deposition (kept) ----------------
        common = QGroupBox("Common parameters")
        common_grid = QGridLayout(common)
        common_grid.setHorizontalSpacing(14)
        common_grid.setVerticalSpacing(10)

        # speed slider + label
        self.speed = QSlider(Qt.Horizontal)
        self.speed.setRange(100, 5000)
        self.speed.valueChanged.connect(lambda v: self.state.set_param("speed", int(v)))
        self.speed_label = QLabel("")

        # droplet amount
        self.amount = QDoubleSpinBox()
        self.amount.setDecimals(3)
        self.amount.setRange(0.0, 1000.0)
        self.amount.setSingleStep(0.1)
        self.amount.valueChanged.connect(lambda v: self.state.set_param("droplet_amount", float(v)))

        # z-hop
        self.zhop = QDoubleSpinBox()
        self.zhop.setDecimals(2)
        self.zhop.setRange(0.0, 1000.0)
        self.zhop.setSingleStep(0.5)
        self.zhop.valueChanged.connect(lambda v: self.state.set_param("z_hop", float(v)))

        # z-offset
        self.zoffset = QDoubleSpinBox()
        self.zoffset.setDecimals(3)
        self.zoffset.setRange(-1000.0, 1000.0)
        self.zoffset.setSingleStep(0.01)
        self.zoffset.valueChanged.connect(lambda v: self.state.set_param("z_offset", float(v)))

        # pause ms
        self.pause_ms = QSpinBox()
        self.pause_ms.setRange(0, 600000)
        self.pause_ms.valueChanged.connect(lambda v: self.state.set_param("pause_ms", int(v)))

        self.chk_afterdrop = QCheckBox("Afterdrop")
        self.chk_afterdrop.toggled.connect(lambda v: self.state.set_param("afterdrop", bool(v)))

        self.chk_clean = QCheckBox("Clean")
        self.chk_clean.toggled.connect(lambda v: self.state.set_param("clean", bool(v)))

        self.btn_test_z = QPushButton("Test Z-Offset")
        self.btn_test_z.clicked.connect(self.controller.test_zoffset)

        common_grid.addWidget(QLabel("Speed"), 0, 0)
        common_grid.addWidget(self.speed, 0, 1, 1, 2)
        common_grid.addWidget(self.speed_label, 0, 3)
        common_grid.addWidget(QLabel("Droplet Amount (E units)"), 1, 0)
        common_grid.addWidget(self.amount, 1, 1)
        common_grid.addWidget(QLabel("Z-Offset (mm)"), 1, 2)
        common_grid.addWidget(self.zoffset, 1, 3)
        common_grid.addWidget(QLabel("Z-Hop (mm)"), 2, 0)
        common_grid.addWidget(self.zhop, 2, 1)
        common_grid.addWidget(QLabel("Pause (ms)"), 2, 2)
        common_grid.addWidget(self.pause_ms, 2, 3)
        common_grid.addWidget(self.chk_afterdrop, 3, 0, 1, 2)
        common_grid.addWidget(self.chk_clean, 3, 2, 1, 2)
        common_grid.addWidget(self.btn_test_z, 4, 0, 1, 4)

        outer.addWidget(common)

        # navigation
        nav = QHBoxLayout()
        nav.addStretch(1)
        self.btn_next = QPushButton("Next →")
        self.btn_next.clicked.connect(lambda: self.mw.go("Syringe"))
        nav.addWidget(self.btn_next)
        outer.addLayout(nav)

        self.state.changed.connect(self._sync_from_state)
        self._sync_from_state()

    @Slot()
    def _sync_from_state(self) -> None:
        p = self.state.params

        # rectangle
        self.fiber_orientation.blockSignals(True)
        self.fiber_orientation.setCurrentText(str(p.fiber_orientation))
        self.fiber_orientation.blockSignals(False)

        for w, val in [(self.fiber_length, p.fiber_length), (self.fiber_width, p.fiber_width), (self.fiber_spacing, p.fiber_spacing),
                      (self.start_x, p.start_x), (self.start_y, p.start_y)]:
            w.blockSignals(True)
            w.setValue(float(val))
            w.blockSignals(False)

        # common
        self.speed.blockSignals(True)
        self.speed.setValue(int(p.speed))
        self.speed.blockSignals(False)
        self.speed_label.setText(f"{int(p.speed)} mm/min")

        for w, val in [(self.amount, p.droplet_amount), (self.zhop, p.z_hop), (self.zoffset, p.z_offset)]:
            w.blockSignals(True)
            w.setValue(float(val))
            w.blockSignals(False)

        self.pause_ms.blockSignals(True)
        self.pause_ms.setValue(int(p.pause_ms))
        self.pause_ms.blockSignals(False)

        self.chk_afterdrop.blockSignals(True)
        self.chk_afterdrop.setChecked(bool(p.afterdrop))
        self.chk_afterdrop.blockSignals(False)

        self.chk_clean.blockSignals(True)
        self.chk_clean.setChecked(bool(p.clean))
        self.chk_clean.blockSignals(False)


class SyringePage(QWidget):
    def __init__(self, mw: MainWindow) -> None:
        super().__init__()
        self.mw = mw
        self.state = mw.state
        self.controller = mw.controller

        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 14, 18, 14)
        outer.setSpacing(10)

        outer.addWidget(_title_label("Syringe"))

        grid = QGridLayout()
        grid.setHorizontalSpacing(24)
        grid.setVerticalSpacing(18)

        def big_btn(text: str) -> QPushButton:
            b = QPushButton(text)
            b.setMinimumSize(QSize(140, 70))
            f = b.font()
            f.setPointSize(18 if text != "Home" else 16)
            b.setFont(f)
            return b

        self.btn_home = big_btn("Home")
        self.btn_1 = big_btn("1")
        self.btn_2 = big_btn("2")
        self.btn_3 = big_btn("3")
        self.btn_4 = big_btn("4")
        self.btn_5 = big_btn("5")

        grid.addWidget(self.btn_home, 0, 0)
        grid.addWidget(self.btn_1, 0, 1)
        grid.addWidget(self.btn_3, 0, 2)
        grid.addWidget(self.btn_5, 0, 3)
        grid.addWidget(self.btn_2, 1, 1)
        grid.addWidget(self.btn_4, 1, 2)
        outer.addLayout(grid)

        cur_row = QHBoxLayout()
        cur_row.addWidget(QLabel("Current amount:"), 0, Qt.AlignLeft)
        self.lbl_current = QLabel("0.00")
        f = QFont(); f.setPointSize(14)
        self.lbl_current.setFont(f)
        cur_row.addWidget(self.lbl_current, 0, Qt.AlignLeft)
        cur_row.addStretch(1)
        outer.addLayout(cur_row)

        intake_row = QHBoxLayout()
        intake_row.addWidget(QLabel("Droplet size to intake"), 0, Qt.AlignLeft)
        self.spin_droplet = QSpinBox()
        self.spin_droplet.setRange(0, 10000)
        self.spin_droplet.valueChanged.connect(lambda v: self.state.set_param("syringe_droplet_units", int(v)))
        intake_row.addWidget(self.spin_droplet, 0, Qt.AlignLeft)
        intake_row.addStretch(1)

        self.btn_intake = QPushButton("Droplet amount to intake")
        self.btn_intake.setMinimumSize(QSize(280, 70))
        intake_row.addWidget(self.btn_intake, 0, Qt.AlignRight)
        outer.addLayout(intake_row)

        outer.addStretch(1)

        nav = QHBoxLayout()
        nav.addStretch(1)
        self.btn_back = QPushButton("Back")
        self.btn_next = QPushButton("Next")
        self.btn_back.clicked.connect(lambda: self.mw.go("Draw"))
        self.btn_next.clicked.connect(lambda: self.mw.go("Summary"))
        nav.addWidget(self.btn_back)
        nav.addWidget(self.btn_next)
        outer.addLayout(nav)

        self.btn_home.clicked.connect(self.controller.syringe_home)
        self.btn_1.clicked.connect(lambda: self.controller.syringe_goto_ml(1))
        self.btn_2.clicked.connect(lambda: self.controller.syringe_goto_ml(2))
        self.btn_3.clicked.connect(lambda: self.controller.syringe_goto_ml(3))
        self.btn_4.clicked.connect(lambda: self.controller.syringe_goto_ml(4))
        self.btn_5.clicked.connect(lambda: self.controller.syringe_goto_ml(5))
        self.btn_intake.clicked.connect(self.controller.syringe_intake_amount)

        self.state.changed.connect(self._sync_from_state)
        self._sync_from_state()

    @Slot()
    def _sync_from_state(self) -> None:
        p = self.state.params
        self.lbl_current.setText(f"{p.syringe_current_amount:.2f}")
        self.spin_droplet.blockSignals(True)
        self.spin_droplet.setValue(int(p.syringe_droplet_units))
        self.spin_droplet.blockSignals(False)


class SummaryPage(QWidget):
    def __init__(self, mw: MainWindow) -> None:
        super().__init__()
        self.mw = mw
        self.state = mw.state

        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 14, 18, 14)
        outer.setSpacing(10)

        top = QHBoxLayout()
        top.addWidget(_title_label("Summary"))
        top.addStretch(1)
        self.btn_update = QPushButton("Update")
        self.btn_update.clicked.connect(self.update_labels)
        top.addWidget(self.btn_update)
        outer.addLayout(top)

        self.labels = {}
        info_grid = QGridLayout()

        keys = [
            "Mode",
            "Layers",
            "Legacy Orientation",
            "Cups",
            "Speed",
            "Step (legacy)",
            "Z-Offset",
            "Z-Hop",
            "Pause (ms)",
            "Droplet Amount",
            "Afterdrop",
            "Clean",
            "Safe Area X",
            "Safe Area Y",
            "Safe Center",
            "Custom Orientation",
            "Fiber Length",
            "Fiber Width",
            "Fiber Spacing",
            "Syringe Current Amount",
            "Syringe Droplet Units",
        ]
        for r, k in enumerate(keys):
            info_grid.addWidget(QLabel(f"{k}:"), r, 0, alignment=Qt.AlignLeft)
            val = QLabel("-")
            val.setTextInteractionFlags(Qt.TextSelectableByMouse)
            info_grid.addWidget(val, r, 1, alignment=Qt.AlignLeft)
            self.labels[k] = val

        outer.addLayout(info_grid)

        btn_col = QVBoxLayout()
        self.btn_save_project = QPushButton("Save Project")
        self.btn_save_pdf = QPushButton("Save PDF")
        self.btn_load = QPushButton("Load")
        btn_col.addWidget(self.btn_save_project)
        btn_col.addWidget(self.btn_save_pdf)
        btn_col.addWidget(self.btn_load)
        btn_col.addStretch(1)

        row = QHBoxLayout()
        row.addLayout(btn_col)
        row.addStretch(1)
        outer.addLayout(row)

        nav = QHBoxLayout()
        nav.addStretch(1)
        self.btn_back = QPushButton("Back")
        self.btn_next = QPushButton("Next")
        self.btn_back.clicked.connect(lambda: self.mw.go("Syringe"))
        self.btn_next.clicked.connect(lambda: self.mw.go("Connection"))
        nav.addWidget(self.btn_back)
        nav.addWidget(self.btn_next)
        outer.addLayout(nav)

        self.btn_save_project.clicked.connect(self.mw.save_project_dialog)
        self.btn_save_pdf.clicked.connect(self.mw.save_pdf_dialog)
        self.btn_load.clicked.connect(self.mw.load_project_dialog)

        self.state.changed.connect(self.update_labels)
        self.update_labels()

    @Slot()
    def update_labels(self) -> None:
        p = self.state.params
        x_min, x_max, y_min, y_max = p.safe_x_min, p.safe_x_max, p.safe_y_min, p.safe_y_max
        xc = (x_min + x_max) / 2.0
        yc = (y_min + y_max) / 2.0

        self.labels["Mode"].setText(p.mode)
        self.labels["Layers"].setText(str(p.layers))
        self.labels["Legacy Orientation"].setText(p.orientation)
        self.labels["Cups"].setText(str(p.cups))

        self.labels["Speed"].setText(f"{p.speed} mm/min")
        self.labels["Step (legacy)"].setText(f"{p.step} mm")
        self.labels["Z-Offset"].setText(f"{p.z_offset} mm")
        self.labels["Z-Hop"].setText(f"{p.z_hop} mm")
        self.labels["Pause (ms)"].setText(str(p.pause_ms))
        self.labels["Droplet Amount"].setText(str(p.droplet_amount))
        self.labels["Afterdrop"].setText("on" if p.afterdrop else "off")
        self.labels["Clean"].setText("on" if p.clean else "off")

        self.labels["Safe Area X"].setText(f"[{x_min}, {x_max}]")
        self.labels["Safe Area Y"].setText(f"[{y_min}, {y_max}]")
        self.labels["Safe Center"].setText(f"({xc:.2f}, {yc:.2f})")

        self.labels["Custom Orientation"].setText(p.fiber_orientation)
        self.labels["Fiber Length"].setText(f"{p.fiber_length} mm")
        self.labels["Fiber Width"].setText(f"{p.fiber_width} mm")
        self.labels["Fiber Spacing"].setText(f"{p.fiber_spacing} mm")

        self.labels["Syringe Current Amount"].setText(f"{p.syringe_current_amount:.2f}")
        self.labels["Syringe Droplet Units"].setText(str(p.syringe_droplet_units))


class ConnectionPage(QWidget):
    def __init__(self, mw: MainWindow) -> None:
        super().__init__()
        self.mw = mw
        self.controller = mw.controller

        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 14, 18, 14)
        outer.setSpacing(10)

        top = QHBoxLayout()
        top.addWidget(_title_label("Connection"))
        top.addStretch(1)
        self.btn_info = QPushButton("Info")
        self.btn_info.clicked.connect(self.mw.show_info)
        top.addWidget(self.btn_info)
        outer.addLayout(top)

        self.lbl_state = QLabel("Disconnected")
        f = QFont(); f.setPointSize(16); f.setBold(True)
        self.lbl_state.setFont(f)
        self.lbl_state.setStyleSheet("color: #b00020;")

        self.btn_connect = QPushButton("Connect")
        self.btn_disconnect = QPushButton("Disconnect")
        self.btn_disconnect.setEnabled(False)

        conn_row = QHBoxLayout()
        conn_row.addWidget(self.btn_connect)
        conn_row.addWidget(self.btn_disconnect)
        conn_row.addWidget(self.lbl_state, 1)
        outer.addLayout(conn_row)

        action_row = QHBoxLayout()
        self.btn_move = QPushButton("Movement test")
        self.btn_start = QPushButton("Do Science!")
        self.btn_pause = QPushButton("Pause")
        self.btn_pause.setEnabled(False)

        action_row.addWidget(self.btn_move)
        action_row.addWidget(self.btn_start)
        action_row.addWidget(self.btn_pause)
        outer.addStretch(1)
        outer.addLayout(action_row)

        nav = QHBoxLayout()
        nav.addStretch(1)
        self.btn_back = QPushButton("Back")
        self.btn_back.clicked.connect(lambda: self.mw.go("Summary"))
        nav.addWidget(self.btn_back)
        outer.addLayout(nav)

        self.btn_connect.clicked.connect(self._connect)
        self.btn_disconnect.clicked.connect(self._disconnect)
        self.btn_move.clicked.connect(self.controller.movement_test)
        self.btn_start.clicked.connect(self._start)
        self.btn_pause.clicked.connect(self.controller.toggle_pause)

        self.controller.drawing_running_changed.connect(self._on_drawing_running)
        self.controller.drawing_paused_changed.connect(self._on_drawing_paused)

    @Slot()
    def _connect(self) -> None:
        ok = self.controller.connect()
        if not ok:
            QMessageBox.critical(self, "Error", "Could not connect to the printer")

    @Slot()
    def _disconnect(self) -> None:
        ok = self.controller.disconnect()
        if not ok:
            QMessageBox.critical(self, "Error", "Could not disconnect from the printer")

    @Slot(bool)
    def on_connection_changed(self, connected: bool) -> None:
        if connected:
            self.lbl_state.setText("Connected")
            self.lbl_state.setStyleSheet("color: #1b7f3a;")
            self.btn_connect.setEnabled(False)
            self.btn_disconnect.setEnabled(True)
        else:
            self.lbl_state.setText("Disconnected")
            self.lbl_state.setStyleSheet("color: #b00020;")
            self.btn_connect.setEnabled(True)
            self.btn_disconnect.setEnabled(False)

    @Slot()
    def _start(self) -> None:
        self.controller.start_drawing()

    @Slot(bool)
    def _on_drawing_running(self, running: bool) -> None:
        self.btn_start.setEnabled(not running)
        self.btn_pause.setEnabled(running)
        if not running:
            self.btn_pause.setText("Pause")

    @Slot(bool)
    def _on_drawing_paused(self, paused: bool) -> None:
        self.btn_pause.setText("Resume" if paused else "Pause")


class LogPage(QWidget):
    def __init__(self, mw: MainWindow) -> None:
        super().__init__()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 14, 18, 14)
        outer.setSpacing(10)

        outer.addWidget(_title_label("Log"))

        self.text = QTextEdit()
        self.text.setReadOnly(True)
        self.text.setPlaceholderText("This is the Log")
        outer.addWidget(self.text, 1)

    @Slot(str)
    def append_log(self, msg: str) -> None:
        self.text.append(msg)
