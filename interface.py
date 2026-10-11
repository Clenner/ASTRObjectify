import sys
import tkinter
from tkinter import messagebox, simpledialog
from pathlib import Path
import core
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QButtonGroup, QHBoxLayout, QLabel, QMainWindow, QPushButton, QStackedWidget, QVBoxLayout, QWidget


PAGES = ["Home", "Create", "Settings"]


def create_new_mod():
    dialog = tkinter.Tk()
    dialog.withdraw()
    try:
        name = simpledialog.askstring("Create New Mod", "Enter the name of the mod:", parent=dialog)
        if name is None:
            return
        name = name.strip()
        invalid_chars = '<>:"/\\|?*'
        reserved_names = {"CON", "PRN", "AUX", "NUL"}
        reserved_names.update(f"COM{i}" for i in range(1, 10))
        reserved_names.update(f"LPT{i}" for i in range(1, 10))
        if (not name or name in (".", "..") or any(ord(char) < 32 or char in invalid_chars for char in name)
                or name.endswith((" ", ".")) or name.split(".")[0].upper() in reserved_names):
            messagebox.showerror("Invalid Mod Name", "Enter a valid Windows folder name.", parent=dialog)
            return

        workspace = Path(__file__).resolve().parent / "Workspaces"
        workspace.mkdir(parents=True, exist_ok=True)
        mod_folder = workspace / name
        try:
            mod_folder.mkdir(exist_ok=False)
        except FileExistsError:
            messagebox.showerror("Mod Already Exists", f"A folder named '{name}' already exists in Workspaces.", parent=dialog)
            return
        messagebox.showinfo("Mod Created", f"Created mod folder:\n{mod_folder}", parent=dialog)
    except OSError as exc:
        messagebox.showerror("Could Not Create Mod", str(exc), parent=dialog)
    finally:
        dialog.destroy()


def main():
    app = QApplication.instance() or QApplication(sys.argv)
    window = QMainWindow()
    window.setWindowTitle("ASTRObjectify")
    window.setMinimumSize(620, 440)
    window.resize(900, 600)

    root = QWidget()
    root_layout = QVBoxLayout(root)
    root_layout.setContentsMargins(0, 0, 0, 0)
    root_layout.setSpacing(0)

    header = QLabel("ASTRObjectify")
    header.setObjectName("header")
    header.setFixedHeight(78)
    header.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
    root_layout.addWidget(header)

    body = QWidget()
    body_layout = QHBoxLayout(body)
    body_layout.setContentsMargins(0, 0, 0, 0)
    body_layout.setSpacing(0)
    root_layout.addWidget(body, 1)

    sidebar = QWidget()
    sidebar.setObjectName("sidebar")
    sidebar.setMinimumWidth(170)
    sidebar.setMaximumWidth(250)
    sidebar_layout = QVBoxLayout(sidebar)
    sidebar_layout.setContentsMargins(20, 24, 20, 24)
    sidebar_layout.setSpacing(14)
    body_layout.addWidget(sidebar, 1)

    content = QStackedWidget()
    content.setObjectName("content")
    body_layout.addWidget(content, 4)

    nav_group = QButtonGroup(window)
    nav_group.setExclusive(True)

    for index, page_name in enumerate(PAGES):
        button = QPushButton(page_name)
        button.setCheckable(True)
        button.setMinimumHeight(44)
        nav_group.addButton(button, index)
        sidebar_layout.addWidget(button)

        page = QWidget()
        if page_name == "Create":
            page_layout = QVBoxLayout(page)
            page_layout.setContentsMargins(32, 32, 32, 32)
            page_layout.addStretch(1)
            for action_name in ("Create New Mod", "Edit Existing Mod", "Import Mod"):
                action_button = QPushButton(action_name)
                action_button.setObjectName("createAction")
                action_button.setMinimumSize(250, 56)
                action_button.setMaximumWidth(360)
                if action_name == "Create New Mod":
                    action_button.clicked.connect(create_new_mod)
                page_layout.addWidget(action_button, alignment=Qt.AlignHCenter)
            page_layout.addStretch(1)
        content.addWidget(page)

    sidebar_layout.addStretch(1)
    nav_group.button(0).setChecked(True)
    nav_group.idClicked.connect(content.setCurrentIndex)

    window.setStyleSheet("""
        QMainWindow, QWidget#content { background-color: #191d26; color: #eef1f7; }
        QLabel#header { background-color: #222733; color: #eef1f7; padding-left: 24px; font-size: 24px; font-weight: 600; }
        QWidget#sidebar { background-color: #222733; }
        QPushButton { background-color: #303746; color: #eef1f7; border: none; border-radius: 8px; padding: 10px 14px; text-align: left; font-size: 15px; }
        QPushButton:hover { background-color: #414b60; }
        QPushButton:checked { background-color: #4b6797; }
        QPushButton#createAction { background-color: #101d38; border: 1px solid #263b63; border-radius: 10px; text-align: center; font-size: 16px; }
        QPushButton#createAction:hover { background-color: #1b2e52; }
        QPushButton#createAction:pressed { background-color: #0b1427; }
    """)
    window.setCentralWidget(root)
    window.show()
    app.exec()


if __name__ == "__main__":
    main()




