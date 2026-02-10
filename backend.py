from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Dict, Any, Tuple

from PySide6.QtCore import QObject, Signal, QThread, Slot

import json
import time
import threading

try:
    import serial
    from serial.tools import list_ports
except Exception:
    serial = None
    list_ports = None

from reportlab.pdfgen import canvas


# ----------------------------- Data Model -----------------------------

@dataclass
class Params:
    # --- Mode ---
    # Legacy: usa a lógica antiga (cups + orientation Horizontal/Vertical/Both)
    # CustomCentered: usa L/W/spacing centralizado na área segura (safe bounds)
    mode: str = "Legacy"  # "Legacy" | "CustomCentered"

    # --- Legacy draw params (GUI.py semantics) ---
    layers: int = 1
    orientation: str = "Horizontal"  # Horizontal | Vertical | Both
    cups: int = 9                    # 3 | 6 | 9

    # --- Motion / deposition ---
    speed: int = 1500                # mm/min
    step: float = 0.1                # mm (Legacy uses step in scan)
    droplet_amount: float = 1.0      # E units
    z_hop: float = 10.0              # mm
    pause_ms: int = 0                # ms (G4 P...)
    z_offset: float = 0.4            # mm

    afterdrop: bool = True
    clean: bool = True

    # --- Syringe bookkeeping ---
    syringe_current_amount: float = 0.0
    syringe_droplet_units: int = 5

    # --- CustomCentered safe bounds (seu retângulo seguro) ---
    safe_x_min: float = 0.0
    safe_x_max: float = 146.0
    safe_y_min: float = 25.0
    safe_y_max: float = 225.0

    # --- CustomCentered parameters ---
    fiber_orientation: str = "Horizontal"  # Horizontal | Vertical
    fiber_length: float = 80.0            # L (mm)
    fiber_width: float = 40.0             # W (mm)
    fiber_spacing: float = 1.0            # S (mm) distância entre fibras


class AppState(QObject):
    changed = Signal()
    log = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.params = Params()

    def set_param(self, name: str, value: Any) -> None:
        if not hasattr(self.params, name):
            raise AttributeError(f"Unknown param: {name}")
        setattr(self.params, name, value)
        self.changed.emit()

    def to_project_dict(self) -> Dict[str, Any]:
        p = self.params
        return {
            "Mode": str(p.mode),

            # legacy
            "Layers": int(p.layers),
            "Orientation": str(p.orientation),
            "Cups": int(p.cups),

            # motion/deposition
            "Speed": int(p.speed),
            "Step": float(p.step),
            "Droplet Amount": float(p.droplet_amount),
            "Z-Hop": float(p.z_hop),
            "Pause (ms)": int(p.pause_ms),
            "Z-Offset": float(p.z_offset),
            "Afterdrop": bool(p.afterdrop),
            "Clean": bool(p.clean),

            # syringe
            "Syringe Current Amount": float(p.syringe_current_amount),
            "Syringe Droplet Units": int(p.syringe_droplet_units),

            # safe area
            "Safe X Min": float(p.safe_x_min),
            "Safe X Max": float(p.safe_x_max),
            "Safe Y Min": float(p.safe_y_min),
            "Safe Y Max": float(p.safe_y_max),

            # custom centered
            "Fiber Orientation": str(p.fiber_orientation),
            "Fiber Length": float(p.fiber_length),
            "Fiber Width": float(p.fiber_width),
            "Fiber Spacing": float(p.fiber_spacing),
        }

    def apply_project_dict(self, data: Dict[str, Any]) -> None:
        p = self.params

        p.mode = str(data.get("Mode", p.mode))

        p.layers = int(data.get("Layers", p.layers))
        p.orientation = str(data.get("Orientation", p.orientation))
        p.cups = int(data.get("Cups", p.cups))

        p.speed = int(data.get("Speed", p.speed))
        p.step = float(data.get("Step", p.step))
        p.droplet_amount = float(data.get("Droplet Amount", p.droplet_amount))
        p.z_hop = float(data.get("Z-Hop", p.z_hop))
        p.pause_ms = int(data.get("Pause (ms)", p.pause_ms))
        p.z_offset = float(data.get("Z-Offset", p.z_offset))
        p.afterdrop = bool(data.get("Afterdrop", p.afterdrop))
        p.clean = bool(data.get("Clean", p.clean))

        p.syringe_current_amount = float(data.get("Syringe Current Amount", p.syringe_current_amount))
        p.syringe_droplet_units = int(data.get("Syringe Droplet Units", p.syringe_droplet_units))

        p.safe_x_min = float(data.get("Safe X Min", p.safe_x_min))
        p.safe_x_max = float(data.get("Safe X Max", p.safe_x_max))
        p.safe_y_min = float(data.get("Safe Y Min", p.safe_y_min))
        p.safe_y_max = float(data.get("Safe Y Max", p.safe_y_max))

        p.fiber_orientation = str(data.get("Fiber Orientation", p.fiber_orientation))
        p.fiber_length = float(data.get("Fiber Length", p.fiber_length))
        p.fiber_width = float(data.get("Fiber Width", p.fiber_width))
        p.fiber_spacing = float(data.get("Fiber Spacing", p.fiber_spacing))

        self.changed.emit()


# ----------------------------- Drawing Worker -----------------------------

class DrawingWorker(QObject):
    finished = Signal()
    error = Signal(str)
    status = Signal(str)

    def __init__(self, controller: "MachineController") -> None:
        super().__init__()
        self.controller = controller

    @Slot()
    def run(self) -> None:
        try:
            self.controller._run_drawing_loop(self.status)
        except Exception as e:
            self.error.emit(str(e))
        finally:
            self.finished.emit()


# ----------------------------- Controller -----------------------------

class MachineController(QObject):
    connection_changed = Signal(bool)

    drawing_running_changed = Signal(bool)
    drawing_paused_changed = Signal(bool)

    def __init__(self, state: AppState) -> None:
        super().__init__()
        self.state = state
        self.ser: Optional["serial.Serial"] = None  # type: ignore[name-defined]

        # drawing infra
        self._drawing_thread: Optional[QThread] = None
        self._worker: Optional[DrawingWorker] = None

        self._pause_event = threading.Event()
        self._pause_event.set()  # not paused
        self._stop_event = threading.Event()

    def log(self, msg: str) -> None:
        self.state.log.emit(msg)

    # ---------- Project I/O ----------
    def save_project(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.state.to_project_dict(), f, indent=2)
        self.log("Project saved")

    def load_project(self, path: str) -> None:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.state.apply_project_dict(data)
        self.log("Loaded project")

    # ---------- PDF ----------
    def save_pdf(self, path: str) -> None:
        p = self.state.params
        x_min, x_max, y_min, y_max, xc, yc = self._safe_center()

        summary_dict = {
            "Mode": p.mode,

            "Layers": f"{p.layers}",
            "Legacy Orientation": p.orientation,
            "Cups": f"{p.cups}",

            "Speed": f"{p.speed} mm/min",
            "Step (legacy)": f"{p.step} mm",
            "Z-Offset": f"{p.z_offset} mm",
            "Z-Hop": f"{p.z_hop} mm",
            "Pause": f"{p.pause_ms} ms",
            "Droplet Amount": f"{p.droplet_amount} (E units)",
            "Afterdrop": "on" if p.afterdrop else "off",
            "Clean": "on" if p.clean else "off",

            "Safe Area X": f"[{x_min}, {x_max}]",
            "Safe Area Y": f"[{y_min}, {y_max}]",
            "Safe Center": f"({xc:.2f}, {yc:.2f})",

            "Custom Orientation": p.fiber_orientation,
            "Custom Fiber Length": f"{p.fiber_length} mm",
            "Custom Fiber Width": f"{p.fiber_width} mm",
            "Custom Fiber Spacing": f"{p.fiber_spacing} mm",

            "Syringe Current Amount": f"{p.syringe_current_amount}",
            "Syringe Droplet Units": f"{p.syringe_droplet_units}",
        }

        c = canvas.Canvas(path)
        c.setFont("Helvetica-Bold", 24)
        c.drawString(40, 800, "Project Summary")
        c.setFont("Helvetica", 14)

        y = 760
        for k, v in summary_dict.items():
            c.drawString(40, y, f"{k}: {v}")
            y -= 24
            if y < 60:
                c.showPage()
                c.setFont("Helvetica", 14)
                y = 800

        c.save()
        self.log("PDF saved")

    # ---------- Serial ----------
    def _find_printer_port(self, baudrate: int = 115200) -> Optional[str]:
        if list_ports is None:
            return None
        for port in list(list_ports.comports()):
            dev = getattr(port, "device", None)
            if not dev:
                continue
            try:
                if serial is None:
                    return None
                s = serial.Serial(dev, baudrate=baudrate, timeout=1)
                s.close()
                return dev
            except Exception:
                continue
        return None

    def connect(self, baudrate: int = 115200) -> bool:
        if serial is None:
            self.log("pyserial not available (install pyserial).")
            return False

        port = self._find_printer_port(baudrate=baudrate)
        if not port:
            self.log("No serial port found.")
            return False

        try:
            self.ser = serial.Serial(port, baudrate=baudrate, timeout=1)

            # many printers reboot on serial-open
            time.sleep(2.0)
            try:
                self.ser.reset_input_buffer()
                self.ser.reset_output_buffer()
            except Exception:
                pass

            # mark connected first (so UI updates), then auto-home
            self.connection_changed.emit(True)
            self.log(f"Connected to the printer on {port}")
            self.log("Homing printer...")

            # IMPORTANT: auto-home on every connect
            self._send_and_wait_ok("G28", timeout_s=120.0)

            self.log("Homing done")
            return True

        except Exception as e:
            self.log(f"Could not connect: {e}")
            try:
                if self.ser is not None:
                    self.ser.close()
            except Exception:
                pass
            self.ser = None
            self.connection_changed.emit(False)
            return False

    def disconnect(self) -> bool:
        try:
            self.stop_drawing()
            if self.ser is not None:
                self.ser.close()
                self.ser = None
            self.connection_changed.emit(False)
            self.log("Disconnected from the printer")
            return True
        except Exception as e:
            self.log(f"Could not disconnect: {e}")
            return False

    def _send_and_wait_ok(self, command: str, timeout_s: float = 30.0) -> None:
        """
        Send one command and wait firmware OK.
        Accepts: 'ok' or 'ok ...'
        """
        if self.ser is None:
            raise RuntimeError("No connection to the printer")

        self.ser.write((command + "\n").encode("utf-8"))

        deadline = time.time() + timeout_s
        last_nonempty = None

        while time.time() < deadline:
            raw = self.ser.readline()
            if not raw:
                continue

            line = raw.decode(errors="ignore").strip()
            if not line:
                continue

            last_nonempty = line
            low = line.lower()

            if low == "ok" or low.startswith("ok"):
                return
            if "busy" in low:
                continue
            if "error" in low:
                raise RuntimeError(f"Firmware error after '{command}': {line}")

        raise TimeoutError(
            f"Timeout waiting for ok after: {command}"
            + (f" (last: {last_nonempty})" if last_nonempty else "")
        )

    # ---------- Drawing controls ----------
    def start_drawing(self) -> None:
        """
        Starts drawing in a background QThread so UI remains responsive.
        Parameters (speed, z_offset, z_hop, droplet_amount, etc.) are read live during the run.
        """
        if self.ser is None:
            self.log("Error: No connection to the printer")
            return
        if self._drawing_thread is not None:
            self.log("Drawing already running")
            return

        self._stop_event.clear()
        self._pause_event.set()

        self._drawing_thread = QThread()
        self._worker = DrawingWorker(self)
        self._worker.moveToThread(self._drawing_thread)

        self._drawing_thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._drawing_thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._drawing_thread.finished.connect(self._drawing_thread.deleteLater)

        self._worker.status.connect(self.log)
        self._worker.error.connect(lambda e: self.log(f"Error during Do Science!: {e}"))
        self._drawing_thread.finished.connect(self._on_drawing_finished)

        self.drawing_running_changed.emit(True)
        self.drawing_paused_changed.emit(False)
        self.log("Start")

        self._drawing_thread.start()

    def _on_drawing_finished(self) -> None:
        self._drawing_thread = None
        self._worker = None
        self.drawing_running_changed.emit(False)
        self.drawing_paused_changed.emit(False)
        self.log("Finished")

    def pause_drawing(self) -> None:
        if self._drawing_thread is None:
            return
        self._pause_event.clear()
        self.drawing_paused_changed.emit(True)
        self.log("Paused")

    def resume_drawing(self) -> None:
        if self._drawing_thread is None:
            return
        self._pause_event.set()
        self.drawing_paused_changed.emit(False)
        self.log("Resumed")

    def toggle_pause(self) -> None:
        if self._drawing_thread is None:
            return
        if self._pause_event.is_set():
            self.pause_drawing()
        else:
            self.resume_drawing()

    def stop_drawing(self) -> None:
        if self._drawing_thread is None:
            return
        self._stop_event.set()
        self._pause_event.set()

    # ---------- Safe area helpers ----------
    def _safe_center(self) -> tuple[float, float, float, float, float, float]:
        p = self.state.params
        x_min, x_max, y_min, y_max = p.safe_x_min, p.safe_x_max, p.safe_y_min, p.safe_y_max
        xc = (x_min + x_max) / 2.0
        yc = (y_min + y_max) / 2.0
        return x_min, x_max, y_min, y_max, xc, yc

    def _compute_centered_rect(self, length: float, width: float, orient: str) -> tuple[float, float, float, float]:
        """
        Returns (x0, x1, y0, y1) of the work rectangle centered in safe area.
        For Horizontal fibers: length along X, width along Y.
        For Vertical fibers: length along Y, width along X.
        """
        x_min, x_max, y_min, y_max, xc, yc = self._safe_center()

        if orient == "Horizontal":
            x0, x1 = xc - length / 2.0, xc + length / 2.0
            y0, y1 = yc - width / 2.0,  yc + width / 2.0
        else:
            # Vertical
            x0, x1 = xc - width / 2.0,  xc + width / 2.0
            y0, y1 = yc - length / 2.0, yc + length / 2.0

        if x0 < x_min or x1 > x_max or y0 < y_min or y1 > y_max:
            raise RuntimeError(
                f"Custom area does not fit safe bounds. "
                f"Requested rect: X[{x0:.1f},{x1:.1f}] Y[{y0:.1f},{y1:.1f}], "
                f"Safe: X[{x_min:.1f},{x_max:.1f}] Y[{y_min:.1f},{y_max:.1f}]"
            )

        return x0, x1, y0, y1

    @staticmethod
    def _clamp(v: float, lo: float, hi: float) -> float:
        return max(lo, min(hi, v))

    # ---------- Drawing loop ----------
    def _run_drawing_loop(self, status_signal: Signal) -> None:
        """
        Select mode and run. Mode is read once at start (safer).
        """
        if self.ser is None:
            raise RuntimeError("No connection to the printer")

        mode = str(self.state.params.mode)
        if mode == "CustomCentered":
            self._run_custom_centered(status_signal)
        else:
            self._run_legacy(status_signal)

    def _wait_pause_or_stop(self) -> None:
        # allows responsive stop while paused
        while not self._pause_event.is_set():
            if self._stop_event.is_set():
                raise RuntimeError("Stopped")
            time.sleep(0.05)
        if self._stop_event.is_set():
            raise RuntimeError("Stopped")

    def _send_checked(self, cmd: str) -> None:
        if self._stop_event.is_set():
            raise RuntimeError("Stopped")
        self._wait_pause_or_stop()
        self._send_and_wait_ok(cmd)

    def _run_custom_centered(self, status_signal: Signal) -> None:
        """
        Custom mode:
        - user sets fiber_length (L), fiber_width (W), fiber_spacing (S)
        - rectangle is centered inside safe bounds
        - parameters are read live per-fiber
        """
        send = self._send_checked

        # header
        send("M220 S100")
        send("M302 S0")
        send("M221 S100")
        send("G90")
        send("M82")
        send("G1 Z2 F1500")
        send("G92 E0")

        def extrusion() -> None:
            pp = self.state.params
            send("G91")
            send(f"G1 E-{float(pp.droplet_amount)} F200")
            send("G4 P1000")
            send("G90")
            self.state.set_param(
                "syringe_current_amount",
                self.state.params.syringe_current_amount - float(pp.droplet_amount),
            )

        def afterdrop() -> None:
            pp = self.state.params
            send("G91")
            send(f"G1 E-{float(pp.droplet_amount)} F200")
            send("G4 P500")
            send("G90")
            send(f"G1 F{int(pp.speed)}")
            self.state.set_param(
                "syringe_current_amount",
                self.state.params.syringe_current_amount - float(pp.droplet_amount),
            )

        # run layers (repeat the centered pattern)
        for layer in range(int(self.state.params.layers)):
            pp0 = self.state.params

            orient = str(pp0.fiber_orientation)
            L = float(pp0.fiber_length)
            W = float(pp0.fiber_width)
            S = float(pp0.fiber_spacing)

            if L <= 0 or W < 0:
                raise RuntimeError("Fiber length must be > 0 and width must be >= 0")
            if S <= 0:
                raise RuntimeError("Fiber spacing must be > 0")

            x0, x1, y0, y1 = self._compute_centered_rect(L, W, orient)

            # if width == 0: draw just one fiber
            n_fibers = 1 if W == 0 else int((W // S) + 1)

            send("G90")
            send(f"G1 Z7 F{int(pp0.speed)}")

            # serpentine scan
            for i in range(n_fibers):
                pp = self.state.params  # live params
                speed = int(pp.speed)
                zoff = float(pp.z_offset)
                zhop = float(pp.z_hop)
                pause_ms = int(pp.pause_ms)
                after = bool(pp.afterdrop)
                clean = bool(pp.clean)

                if orient == "Horizontal":
                    y = y0 + i * float(pp.fiber_spacing)
                    if y > y1 + 1e-6:
                        break

                    # alternate direction
                    if (i % 2) == 0:
                        xs, xe = x0, x1
                    else:
                        xs, xe = x1, x0

                    # go to start, deposit, hop
                    send(f"G1 X{xs:.3f} Y{y:.3f} F{speed}")
                    send(f"G1 Z{zoff:.3f} F{speed}")
                    extrusion()
                    send(f"G1 Z{zhop:.3f} F{speed}")
                    if pause_ms:
                        send(f"G4 P{pause_ms}")

                    # travel and land at end
                    send(f"G1 X{xe:.3f} Y{y:.3f} F{speed}")
                    send(f"G1 Z{zoff:.3f} F{speed}")

                    if after:
                        afterdrop()

                    # clean on the end side, clamped to safe bounds
                    if clean:
                        x_min, x_max, y_min, y_max, _, _ = self._safe_center()
                        # move a bit further outside the end side
                        if xe >= (x0 + x1) / 2.0:
                            x_a = self._clamp(xe + 5.0, x_min, x_max)
                            x_b = self._clamp(xe + 10.0, x_min, x_max)
                        else:
                            x_a = self._clamp(xe - 5.0, x_min, x_max)
                            x_b = self._clamp(xe - 10.0, x_min, x_max)
                        send(f"G1 X{x_a:.3f} Z0 F{speed}")
                        send(f"G1 X{x_b:.3f} F{speed}")
                        send(f"G1 Z3 F{speed}")

                    send("M400")

                else:
                    # Vertical
                    x = x0 + i * float(pp.fiber_spacing)
                    if x > x1 + 1e-6:
                        break

                    if (i % 2) == 0:
                        ys, ye = y0, y1
                    else:
                        ys, ye = y1, y0

                    send(f"G1 X{x:.3f} Y{ys:.3f} F{speed}")
                    send(f"G1 Z{zoff:.3f} F{speed}")
                    extrusion()
                    send(f"G1 Z{zhop:.3f} F{speed}")
                    if pause_ms:
                        send(f"G4 P{pause_ms}")

                    send(f"G1 X{x:.3f} Y{ye:.3f} F{speed}")
                    send(f"G1 Z{zoff:.3f} F{speed}")

                    if after:
                        afterdrop()

                    if clean:
                        x_min, x_max, y_min, y_max, _, _ = self._safe_center()
                        if ye >= (y0 + y1) / 2.0:
                            y_a = self._clamp(ye + 5.0, y_min, y_max)
                            y_b = self._clamp(ye + 10.0, y_min, y_max)
                        else:
                            y_a = self._clamp(ye - 5.0, y_min, y_max)
                            y_b = self._clamp(ye - 10.0, y_min, y_max)
                        send(f"G1 Y{y_a:.3f} Z0 F{speed}")
                        send(f"G1 Y{y_b:.3f} F{speed}")
                        send(f"G1 Z3 F{speed}")

                    send("M400")

        # footer
        send("M300 S440 P200")
        send("G0 X10 Y190 Z30 F3000")

    # ---------- Legacy (ported from GUI.py logic, with live params) ----------
    def _limits_from_cups(self, cups: int) -> Tuple[float, float]:
        if cups == 9:
            return 117.0, 172.0
        if cups == 6:
            return 91.0, 145.0
        return 63.0, 117.0

    def _run_legacy(self, status_signal: Signal) -> None:
        send = self._send_checked

        # header
        send("M220 S100")
        send("M302 S0")
        send("M221 S100")
        send("G90")
        send("M82")
        send("G1 Z2 F1500")
        send("G92 E0")

        adjust_different_layers = 3.0

        def extrusion() -> None:
            pp = self.state.params
            send("G91")
            send(f"G1 E-{float(pp.droplet_amount)} F200")
            send("G4 P1000")
            send("G90")
            self.state.set_param(
                "syringe_current_amount",
                self.state.params.syringe_current_amount - float(pp.droplet_amount),
            )

        def afterdrop() -> None:
            pp = self.state.params
            send("G91")
            send(f"G1 E-{float(pp.droplet_amount)} F200")
            send("G4 P500")
            send("G90")
            send(f"G1 F{int(pp.speed)}")
            self.state.set_param(
                "syringe_current_amount",
                self.state.params.syringe_current_amount - float(pp.droplet_amount),
            )

        for layer in range(int(self.state.params.layers)):
            p0 = self.state.params  # snapshot-ish for geometry
            orientation = str(p0.orientation)
            limit_x, limit_y = self._limits_from_cups(int(p0.cups))

            denom = (float(p0.step) / 2.0) if float(p0.step) != 0 else 1e-6
            lines_count = int(round(82.5 / denom))

            # base offsets per layer
            x1 = 25.5 - layer * adjust_different_layers
            x2 = 128.0
            x22 = 25.5
            x3 = 128.0 + layer * adjust_different_layers

            y1 = 79.0 - layer * adjust_different_layers
            y2 = 181.5
            y22 = 79.0 - layer * adjust_different_layers
            y3 = 181.5 + layer * adjust_different_layers

            send("G90")
            send(f"G1 Z7 F{int(self.state.params.speed)}")

            if orientation == "Horizontal":
                y = 90.0
                for _ in range(lines_count):
                    if y >= limit_y:
                        break

                    pp = self.state.params
                    speed = int(pp.speed)
                    zoff = float(pp.z_offset)
                    zhop = float(pp.z_hop)
                    pause_ms = int(pp.pause_ms)

                    send("G90")
                    send(f"G1 X{x1:.3f} Y{y:.3f} F{speed}")
                    send(f"G1 Z{zoff:.3f} F{speed}")
                    extrusion()
                    send(f"G1 Z{zhop:.3f} F{speed}")
                    if pause_ms:
                        send(f"G4 P{pause_ms}")

                    send(f"G1 X{x2:.3f}")
                    send(f"G1 X{x3:.3f} Z{zoff:.3f} F{speed}")

                    if bool(pp.afterdrop):
                        afterdrop()
                    if bool(pp.clean):
                        send(f"G1 X{(x3 + 5.0):.3f} Z0 F{speed}")
                        send(f"G1 X{(x3 + 10.0):.3f} F{speed}")
                        send(f"G1 Z3 F{speed}")

                    y = round(y + float(pp.step), 2)

                    send(f"G1 X{x3:.3f} Y{y:.3f} Z{zoff:.3f}")
                    extrusion()
                    send(f"G1 Z{zhop:.3f} F{speed}")
                    if pause_ms:
                        send(f"G4 P{pause_ms}")

                    send(f"G1 X{x22:.3f} F{speed}")
                    send(f"G1 Z{zoff:.3f} X{x1:.3f} F{speed}")

                    pp2 = self.state.params
                    if bool(pp2.afterdrop):
                        afterdrop()
                    if bool(pp2.clean):
                        send(f"G1 X{(x1 - 5.0):.3f} Z0 F{speed}")
                        send(f"G1 X{(x1 - 10.0):.3f} F{speed}")
                        send(f"G1 Z3 F{speed}")

                    y = round(y + float(self.state.params.step), 2)
                    send("M400")

            elif orientation == "Vertical":
                x = 36.0
                for _ in range(lines_count):
                    if x >= limit_x:
                        break

                    pp = self.state.params
                    speed = int(pp.speed)
                    zoff = float(pp.z_offset)
                    zhop = float(pp.z_hop)
                    pause_ms = int(pp.pause_ms)

                    send("G90")
                    send(f"G1 X{x:.3f} Y{y1:.3f} F{speed}")
                    send(f"G1 Z{zoff:.3f} F{speed}")
                    extrusion()
                    send(f"G1 Z{zhop:.3f} F{speed}")
                    if pause_ms:
                        send(f"G4 P{pause_ms}")

                    send(f"G1 Y{y2:.3f}")
                    send(f"G1 Z{zoff:.3f} Y{y3:.3f} F{speed}")

                    if bool(pp.afterdrop):
                        afterdrop()
                    if bool(pp.clean):
                        send(f"G1 Y{(y3 + 5.0):.3f} Z0 F{speed}")
                        send(f"G1 Y{(y3 + 10.0):.3f} F{speed}")
                        send(f"G1 Z3 F{speed}")

                    x = round(x + float(pp.step), 2)

                    send(f"G1 X{x:.3f} Y{y3:.3f} Z{zoff:.3f}")
                    extrusion()
                    send(f"G1 Z{zhop:.3f} F{speed}")
                    if pause_ms:
                        send(f"G4 P{pause_ms}")

                    send(f"G1 Y{y22:.3f} F{speed}")
                    send(f"G1 Z{zoff:.3f} Y{y1:.3f} F{speed}")

                    pp2 = self.state.params
                    if bool(pp2.afterdrop):
                        afterdrop()
                    if bool(pp2.clean):
                        send(f"G1 Y{(y1 - 5.0):.3f} Z0 F{speed}")
                        send(f"G1 Y{(y1 - 10.0):.3f} F{speed}")
                        send(f"G1 Z3 F{speed}")

                    x = round(x + float(self.state.params.step), 2)
                    send("M400")

            else:
                # Both (simple): do one horizontal pass then one vertical pass in the same layer.
                # (continua compatível e responde a mudanças live)
                # Horizontal quick pass
                y = 89.0
                for _ in range(lines_count):
                    if y >= limit_y:
                        break

                    pp = self.state.params
                    speed = int(pp.speed)
                    zoff = float(pp.z_offset)
                    zhop = float(pp.z_hop)
                    pause_ms = int(pp.pause_ms)

                    send("G90")
                    send(f"G1 X{x1:.3f} Y{y:.3f} F{speed}")
                    send(f"G1 Z{zoff:.3f} F{speed}")
                    extrusion()
                    send(f"G1 Z{zhop:.3f} F{speed}")
                    if pause_ms:
                        send(f"G4 P{pause_ms}")

                    send(f"G1 X{x3:.3f} Y{y:.3f} F{speed}")
                    send(f"G1 Z{zoff:.3f} F{speed}")
                    if bool(pp.afterdrop):
                        afterdrop()
                    if bool(pp.clean):
                        send(f"G1 X{(x3 + 5.0):.3f} Z0 F{speed}")
                        send(f"G1 X{(x3 + 10.0):.3f} F{speed}")
                        send(f"G1 Z3 F{speed}")

                    y = round(y + float(pp.step), 2)
                    send("M400")

                # Vertical quick pass
                x = 35.5
                for _ in range(lines_count):
                    if x >= limit_x:
                        break

                    pp = self.state.params
                    speed = int(pp.speed)
                    zoff = float(pp.z_offset)
                    zhop = float(pp.z_hop)
                    pause_ms = int(pp.pause_ms)

                    send("G90")
                    send(f"G1 X{x:.3f} Y{y1:.3f} F{speed}")
                    send(f"G1 Z{zoff:.3f} F{speed}")
                    extrusion()
                    send(f"G1 Z{zhop:.3f} F{speed}")
                    if pause_ms:
                        send(f"G4 P{pause_ms}")

                    send(f"G1 X{x:.3f} Y{y3:.3f} F{speed}")
                    send(f"G1 Z{zoff:.3f} F{speed}")
                    if bool(pp.afterdrop):
                        afterdrop()
                    if bool(pp.clean):
                        send(f"G1 Y{(y3 + 5.0):.3f} Z0 F{speed}")
                        send(f"G1 Y{(y3 + 10.0):.3f} F{speed}")
                        send(f"G1 Z3 F{speed}")

                    x = round(x + float(pp.step), 2)
                    send("M400")

        # footer
        send("M300 S440 P200")
        send("G0 X10 Y190 Z30 F3000")

    # ---------- Syringe (ported) ----------
    _ML_TO_EPOS = {1: 20, 2: 53, 3: 86, 4: 119, 5: 152}

    def syringe_goto_ml(self, ml_mark: int) -> None:
        if self.ser is None:
            self.log("Error: No connection to the printer")
            return
        if ml_mark not in self._ML_TO_EPOS:
            self.log(f"Syringe: invalid mark {ml_mark}")
            return
        epos = float(self._ML_TO_EPOS[ml_mark])
        self.ser.write((f"M302 S0\nG1 E{int(epos)} F200\n").encode("utf-8"))
        self.state.set_param("syringe_current_amount", epos)
        self.log(f"Go to {ml_mark} ml")

    def syringe_intake_amount(self) -> None:
        if self.ser is None:
            self.log("Error: No connection to the printer")
            return
        p = self.state.params
        units = int(p.syringe_droplet_units)
        self.ser.write(("G91\n").encode("utf-8"))
        self.ser.write((f"M302 S0\nG1 E{units} F200 ;intake {units} units\n").encode("utf-8"))
        self.ser.write(("G90\n").encode("utf-8"))
        self.state.set_param("syringe_current_amount", float(p.syringe_current_amount + units))
        self.log(f"Intake {units} units")

    def syringe_home(self) -> None:
        if self.ser is None:
            self.log("Error: No connection to the printer")
            return

        def check_syringe() -> Optional[str]:
            self.ser.write(("M119\r\n").encode("utf-8"))
            t0 = time.time()
            while time.time() - t0 < 2.0:
                line = self.ser.readline()
                if line == b"filament: open\n":
                    return "empty"
                if line == b"filament: TRIGGERED\n":
                    return "full"
            return None

        try:
            self._send_and_wait_ok("M302 P1")
            self._send_and_wait_ok("M302")

            status = check_syringe()
            self._send_and_wait_ok("G91 E0")

            loops = 0
            while status == "full" and loops < 400:
                self._send_and_wait_ok("G1 E-0.5 F300")
                status = check_syringe()
                if status == "empty":
                    self._send_and_wait_ok("G92 E0")
                    self.state.set_param("syringe_current_amount", 0.0)
                loops += 1

            self._send_and_wait_ok("G92 E0")
            self._send_and_wait_ok("G90")
            self.log("Syringe homed")
        except Exception as e:
            self.log(f"Syringe home error: {e}")

    # ---------- Misc ----------
    def movement_test(self) -> None:
        self.log("Movement test")

    def test_zoffset(self) -> None:
        self.log("Test Z-Offset")
        
