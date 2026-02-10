from PySide6.QtWidgets import QApplication
from ui import MainWindow
from backend import AppState, MachineController


def main() -> None:
    app = QApplication([])
    state = AppState()
    controller = MachineController(state)
    w = MainWindow(state=state, controller=controller)
    w.show()
    app.exec()


if __name__ == "__main__":
    main()
