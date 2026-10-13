try:
    import sys
    from pathlib import Path

    import core
    from PySide6.QtCore import QSettings, Qt
    from PySide6.QtWidgets import (
        QApplication,
        QComboBox,
        QDialog,
        QDialogButtonBox,
        QFileDialog,
        QFormLayout,
        QHBoxLayout,
        QInputDialog,
        QLabel,
        QLineEdit,
        QMainWindow,
        QMessageBox,
        QPushButton,
        QSpinBox,
       QStackedWidget,
        QVBoxLayout,
        QWidget,
    )
except:
    print("FAILED TO IMPORT MODULES. PLEASE RUN THE INSTALLER AND THE README.")
    sys.exit()


ACTIONS = ("Create New Mod", "Edit Existing Mod", "Import Mod", "About", "Exit")


class AOYWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ASTRObjectify")
        self.setMinimumSize(620, 440)
        self.resize(900, 600)
        self.active_mod = None
        self.settings = QSettings("AOY", "ASTRObjectify")
        self.recent_button: QPushButton | None = None

        self.screens = QStackedWidget()
        self.setCentralWidget(self.screens)
        self.home_screen = self._make_home_screen()
        self.workspace_screen = QWidget()
        self.screens.addWidget(self.home_screen)
        self.screens.addWidget(self.workspace_screen)

        self.file_menu = self.menuBar().addMenu("File")
        export_action = self.file_menu.addAction("Export Mod")
        export_action.triggered.connect(self.export_mod)
        self.file_menu.addSeparator()
        exit_action = self.file_menu.addAction("Exit")
        exit_action.triggered.connect(self.return_home)

        self.edit_menu = self.menuBar().addMenu("Edit")
        edit_metadata_action = self.edit_menu.addAction("Edit Metadata")
        edit_metadata_action.triggered.connect(self.edit_metadata)
        self.menuBar().hide()

        self.setStyleSheet("""
            QMainWindow, QWidget { background-color: #191d26; color: #eef1f7; }
            QLabel#title { font-size: 30px; font-weight: 600; }
            QPushButton { background-color: #101d38; color: #eef1f7; border: 1px solid #263b63; border-radius: 10px; padding: 12px 18px; font-size: 16px; }
            QPushButton:hover { background-color: #1b2e52; }
            QPushButton:pressed { background-color: #0b1427; }
            QPushButton#recent { padding: 6px 12px; font-size: 13px; }
            QMenuBar { background-color: #222733; color: #eef1f7; }
            QMenuBar::item { background-color: #222733; padding: 4px 10px; border: 1px solid #303746; }
            QMenuBar::item:selected { background-color: #303746; }
            QMenu { background-color: #222733; color: #eef1f7; }
            QMenu::item { padding: 7px 28px 7px 12px; }
            QMenu::item:selected { background-color: #303746; }
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
            elif label == "Exit":
                button.clicked.connect(self.exit_app)
            layout.addWidget(button, alignment=Qt.AlignHCenter)

        layout.addStretch(1)

        footer = QHBoxLayout()
        self.recent_button = QPushButton()
        self.recent_button.setObjectName("recent")
        self.recent_button.setMinimumSize(120, 32)
        self.recent_button.setMaximumWidth(220)
        self.recent_button.clicked.connect(self.open_recent_mod)
        footer.addStretch(1)
        footer.addWidget(self.recent_button, alignment=Qt.AlignRight)
        layout.addLayout(footer)
        return page

    def _get_recent_mod_path(self) -> Path | None:
        try:
            stored = self.settings.value("recentMod", "", type=str)
        except Exception:
            stored = self.settings.value("recentMod", "")
        if not stored:
            return None
        path = Path(str(stored)).expanduser()
        if path.is_symlink() or not path.is_dir():
            return None
        return path.resolve()

    def _refresh_recent_button(self) -> None:
        if self.recent_button is None:
            return
        recent = self._get_recent_mod_path()
        if recent is None:
            self.recent_button.hide()
            return
        self.recent_button.setText(recent.name)
        self.recent_button.setToolTip(f"Open most recent mod:\n{recent}")
        self.recent_button.show()

    def open_recent_mod(self):
        recent = self._get_recent_mod_path()
        if recent is None:
            QMessageBox.information(self, "No Recent Mod", "No recently edited mod was found.")
            self._refresh_recent_button()
            return
        self.open_mod_workspace(recent)

    def show_home(self):
        self.active_mod = None
        self.setWindowTitle("ASTRObjectify")
        self.screens.setCurrentWidget(self.home_screen)
        self.menuBar().hide()
        self._refresh_recent_button()

    def open_mod_workspace(self, mod_folder):
        mod_folder = Path(mod_folder).expanduser().resolve()
        self.active_mod = mod_folder
        try:
            core.ensure_select_marker(mod_folder)
        except Exception:
            pass
        try:
            self.settings.setValue("recentMod", str(mod_folder))
        except Exception:
            pass
        self.setWindowTitle(f"ASTRObjectify - {mod_folder.name}")
        self.screens.setCurrentWidget(self.workspace_screen)
        self.menuBar().show()

    def create_new_mod(self):
        name, accepted = QInputDialog.getText(self, "Create New Mod", "Enter the name of the mod:")
        if not accepted:
            return
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

        dialog = QDialog(self)
        dialog.setWindowTitle("Edit Existing Mod")
        dialog.setMinimumWidth(420)
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("Choose a mod to edit:"))
        selection = QComboBox()
        selection.addItems(mod_names)
        selection.setEnabled(bool(mod_names))
        layout.addWidget(selection)
        marker_name = getattr(core, "SELECT_MARKER", "SELECT.HERE")
        layout.addWidget(QLabel(f"Or select a {marker_name} file:"))
        browse_row = QHBoxLayout()
        path_display = QLineEdit()
        path_display.setReadOnly(True)
        path_display.setPlaceholderText(f"No {marker_name} selected")
        browse_button = QPushButton("Browse...")
        browse_row.addWidget(path_display)
        browse_row.addWidget(browse_button)
        layout.addLayout(browse_row)
        buttons = QDialogButtonBox(QDialogButtonBox.Open | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        chosen = {"path": None}

        def on_browse():
            try:
                start_dir = str(core._workspace_path())
            except Exception:
                start_dir = ""
            selected, _ = QFileDialog.getOpenFileName(
                dialog, f"Select Mod ({marker_name})", start_dir,
                f"Mod marker ({marker_name})")
            if not selected:
                return
            if Path(selected).name != marker_name:
                QMessageBox.warning(dialog, "Wrong File",
                                    f"Please select the {marker_name} file inside the mod folder.")
                return
            chosen["path"] = selected
            path_display.setText(selected)

        browse_button.clicked.connect(on_browse)

        if dialog.exec() != QDialog.Accepted:
            return
        try:
            if chosen["path"]:
                marker_path = Path(chosen["path"])
                if marker_path.name != marker_name or not marker_path.is_file():
                    raise FileNotFoundError(f"Please select the {marker_name} file.")
                mod_folder = marker_path.parent.resolve()
                if not mod_folder.is_dir():
                    raise FileNotFoundError(f"Mod folder not found: {mod_folder}")
            else:
                if not mod_names:
                    QMessageBox.information(self, "No Mods Found", "There are no mod folders in Workspaces yet.")
                    return
                mod_folder = core.get_mod_workspace(selection.currentText())
        except (FileNotFoundError, ValueError, OSError) as exc:
            QMessageBox.critical(self, "Could Not Open Mod", str(exc))
            return
        self.open_mod_workspace(mod_folder)

    def edit_metadata(self):
        if self.active_mod is None:
            return
        try:
            metafile = core.read_mod_metafile(self.active_mod)
        except (ValueError, OSError) as exc:
            QMessageBox.critical(self, "Could Not Read Metadata", str(exc))
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Edit Metadata")
        dialog.setMinimumWidth(380)
        layout = QVBoxLayout(dialog)

        layout.addWidget(QLabel("Mod identity:"))
        identity_form = QFormLayout()
        priority_spin = QSpinBox()
        priority_spin.setRange(0, 799)
        try:
            priority_spin.setValue(int(metafile.get("priority", 0)))
        except (TypeError, ValueError):
            priority_spin.setValue(0)
        name_edit = QLineEdit(str(metafile.get("mod_name", "")))
        version_edit = QLineEdit(str(metafile.get("version", "0.1.0")))
        version_edit.setPlaceholderText("1.0.0")
        identity_form.addRow("Priority:", priority_spin)
        identity_form.addRow("Mod name / ID:", name_edit)
        identity_form.addRow("Version:", version_edit)
        layout.addLayout(identity_form)
        hint = QLabel("Priority, Name and Version rename the package folder, update metadata.json, and control the export filename.")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() != QDialog.Accepted:
            return
        try:
            workspace = core.update_mod_metafile(
                self.active_mod,
                priority_spin.value(),
                name_edit.text(),
                version_edit.text(),
            )
        except FileExistsError as exc:
            QMessageBox.critical(self, "Name Already Exists", str(exc))
            return
        except (ValueError, OSError) as exc:
            QMessageBox.critical(self, "Could Not Update Metadata", str(exc))
            return
        self.open_mod_workspace(workspace)

    def export_mod(self):
        if self.active_mod is None:
            return
        try:
            meta = core.read_mod_metafile(self.active_mod)
            package_folder_name = meta.get("package_folder")
            if not package_folder_name:
                raise ValueError("Could not find package folder in workspace.")

            input_dir = self.active_mod / package_folder_name
            if not input_dir.is_dir():
                raise FileNotFoundError(f"Package folder not found: {input_dir}")

            try:
                core.rebuild_integrator(self.active_mod)
                meta = core.read_mod_metafile(self.active_mod)
            except (ValueError, OSError) as exc:
                raise RuntimeError(f"Could not auto-build integrator: {exc}") from exc

            pak_name = core.pak_filename(meta["priority"], meta["mod_name"], meta["version"])
            versions_dir = self.active_mod / "versions"
            versions_dir.mkdir(parents=True, exist_ok=True)
            output_pak = versions_dir / pak_name

            process = core.pack_pak(input_dir, output_pak)
            if process.returncode != 0:
                error_msg = core.format_process_result(process) or f"repak exited with code {process.returncode}"
                raise RuntimeError(error_msg)

            QMessageBox.information(
                self,
                "Export Complete",
                f"Mod successfully exported to:\n{output_pak.name}\n\nin folder:\n{versions_dir}",
            )
        except Exception as exc:
            QMessageBox.critical(self, "Export Failed", str(exc))

    def return_home(self):
        self.show_home()

    def exit_app(self):
        try:
            print("\n\n\nHope you enjoyed!\n\n\n")
        except (EOFError, OSError):
            pass
        sys.exit()


def main():
    app = QApplication.instance() or QApplication(sys.argv)
    window = AOYWindow()
    window.show()
    app.exec()


if __name__ == "__main__":
    main()
