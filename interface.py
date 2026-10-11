import sys
import tkinter
from tkinter import simpledialog

import core
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)


ACTIONS = ("Create New Mod", "Edit Existing Mod", "Import Mod", "About", "Exit")


class AOYWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ASTRObjectify")
        self.setMinimumSize(620, 440)
        self.resize(900, 600)
        self.active_mod = None

        self.screens = QStackedWidget()
        self.setCentralWidget(self.screens)
        self.home_screen = self._make_home_screen()
        self.workspace_screen = QWidget()
        self.screens.addWidget(self.home_screen)
        self.screens.addWidget(self.workspace_screen)

        self.file_menu = self.menuBar().addMenu("File")
        self.file_menu.setStyleSheet("QMenu { background-color: #222733; color: #eef1f7; } QMenu::item { padding: 7px 28px 7px 12px; } QMenu::item:selected { background-color: #303746; }")
        for label in ("Open", "New", "Save", "Save As"):
            self.file_menu.addAction(label)
        self.file_menu.addSeparator()
        exit_action = self.file_menu.addAction("Exit")
        exit_action.triggered.connect(self.return_home)

        self.edit_menu = self.menuBar().addMenu("Edit")
        edit_metafile_action = self.edit_menu.addAction("Edit Metafile")
        edit_metafile_action.triggered.connect(self.edit_metafile)
        self.edit_menu.addAction("Edit Metadata")
        self.menuBar().hide()

        self.setStyleSheet("""
            QMainWindow, QWidget { background-color: #191d26; color: #eef1f7; }
            QLabel#title { font-size: 30px; font-weight: 600; }
            QPushButton { background-color: #101d38; color: #eef1f7; border: 1px solid #263b63; border-radius: 10px; padding: 12px 18px; font-size: 16px; }
            QPushButton:hover { background-color: #1b2e52; }
            QPushButton:pressed { background-color: #0b1427; }
            QMenuBar { background-color: #222733; color: #eef1f7; }
            QMenuBar::item { background-color: #222733; padding: 4px 10px; border: 1px solid #303746; }
            QMenuBar::item:selected { background-color: #303746; }
        """)
        self.show_home()

    def _make_home_screen(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.addStretch(1)

        title = QLabel("ASTRObjectify")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        layout.addSpacing(28)

        for label in ACTIONS:
            button = QPushButton(label)
            button.setMinimumSize(250, 56)
            button.setMaximumWidth(360)
            if label == "Create New Mod":
                button.clicked.connect(self.create_new_mod)
            elif label == "Edit Existing Mod":
                button.clicked.connect(self.edit_existing_mod)
            layout.addWidget(button, alignment=Qt.AlignHCenter)

        layout.addStretch(1)
        return page

    def show_home(self):
        self.active_mod = None
        self.setWindowTitle("ASTRObjectify")
        self.screens.setCurrentWidget(self.home_screen)
        self.menuBar().hide()

    def open_mod_workspace(self, mod_folder):
        self.active_mod = mod_folder
        self.setWindowTitle(f"ASTRObjectify - {mod_folder.name}")
        self.screens.setCurrentWidget(self.workspace_screen)
        self.menuBar().show()

    def create_new_mod(self):
        dialog = tkinter.Tk()
        dialog.withdraw()
        try:
            name = simpledialog.askstring("Create New Mod", "Enter the name of the mod:", parent=dialog)
        finally:
            dialog.destroy()

        if name is None:
            return
        try:
            mod_folder = core.create_mod_workspace(name)
        except FileExistsError:
            QMessageBox.critical(self, "Mod Already Exists", f"A folder named '{name.strip()}' already exists in Workspaces.")
            return
        except (ValueError, OSError) as exc:
            QMessageBox.critical(self, "Could Not Create Mod", str(exc))
            return

        self.open_mod_workspace(mod_folder)

    def edit_existing_mod(self):
        try:
            mod_names = core.list_mod_workspaces()
        except OSError as exc:
            QMessageBox.critical(self, "Could Not Read Workspaces", str(exc))
            return
        if not mod_names:
            QMessageBox.information(self, "No Mods Found", "There are no mod folders in Workspaces yet.")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Edit Existing Mod")
        dialog.setMinimumWidth(360)
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("Choose a mod to edit:"))
        selection = QComboBox()
        selection.addItems(mod_names)
        layout.addWidget(selection)
        buttons = QDialogButtonBox(QDialogButtonBox.Open | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() != QDialog.Accepted:
            return
        try:
            mod_folder = core.get_mod_workspace(selection.currentText())
        except (FileNotFoundError, ValueError, OSError) as exc:
            QMessageBox.critical(self, "Could Not Open Mod", str(exc))
            return
        self.open_mod_workspace(mod_folder)

    def edit_metafile(self):
        if self.active_mod is None:
            return
        try:
            values = core.read_mod_metafile(self.active_mod)
        except (ValueError, OSError) as exc:
            QMessageBox.critical(self, "Could Not Read Metafile", str(exc))
            return

        dialog = tkinter.Tk()
        dialog.title("Edit Metafile")
        dialog.resizable(False, False)
        dialog.configure(padx=18, pady=16)
        fields = (
            ("Priority", str(int(values.get("priority", 0)))),
            ("Mod name / ID", str(values.get("mod_name", self.active_mod.name))),
            ("Version", str(values.get("version", "0.1.0"))),
        )
        entries = {}
        for row, (label, value) in enumerate(fields):
            tkinter.Label(dialog, text=label).grid(row=row, column=0, sticky="w", padx=(0, 14), pady=6)
            entry = tkinter.Entry(dialog, width=32)
            entry.insert(0, value)
            entry.grid(row=row, column=1, sticky="ew", pady=6)
            entries[label] = entry

        result = {}

        def accept():
            result["priority"] = entries["Priority"].get()
            result["mod_name"] = entries["Mod name / ID"].get()
            result["version"] = entries["Version"].get()
            dialog.destroy()

        def cancel():
            dialog.destroy()

        buttons = tkinter.Frame(dialog)
        buttons.grid(row=len(fields), column=0, columnspan=2, sticky="e", pady=(12, 0))
        tkinter.Button(buttons, text="OK", width=10, command=accept).pack(side="left", padx=(0, 8))
        tkinter.Button(buttons, text="Cancel", width=10, command=cancel).pack(side="left")
        dialog.protocol("WM_DELETE_WINDOW", cancel)
        dialog.mainloop()
        dialog.destroy()

        if not result:
            return
        try:
            workspace = core.update_mod_metafile(
                self.active_mod,
                result["priority"],
                result["mod_name"],
                result["version"],
            )
        except FileExistsError as exc:
            QMessageBox.critical(self, "Name Already Exists", str(exc))
            return
        except (ValueError, OSError) as exc:
            QMessageBox.critical(self, "Could Not Update Metafile", str(exc))
            return
        self.open_mod_workspace(workspace)

    def return_home(self):
        self.show_home()


def main():
    app = QApplication.instance() or QApplication(sys.argv)
    window = AOYWindow()
    window.show()
    app.exec()


if __name__ == "__main__":
    main()
