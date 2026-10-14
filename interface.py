try:
    import sys
    from pathlib import Path

    import core
    from PySide6.QtCore import QSettings, Qt, QUrl
    from PySide6.QtGui import QDesktopServices
    from PySide6.QtWidgets import (
        QApplication,
        QComboBox,
        QDialog,
        QDialogButtonBox,
        QFileDialog,
        QFormLayout,
        QGridLayout,
        QHBoxLayout,
        QInputDialog,
        QLabel,
        QLineEdit,
        QMainWindow,
        QMessageBox,
        QPushButton,
        QScrollArea,
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
        ws_layout = QVBoxLayout(self.workspace_screen)
        ws_layout.setContentsMargins(24, 18, 24, 18)
        self.tiles_scroll = QScrollArea()
        self.tiles_scroll.setWidgetResizable(True)
        self.tiles_host = QWidget()
        self.tiles_grid = QGridLayout(self.tiles_host)
        self.tiles_scroll.setWidget(self.tiles_host)
        ws_layout.addWidget(self.tiles_scroll, 1)
        self._part_groups: dict = {}
        self.screens.addWidget(self.home_screen)
        self.screens.addWidget(self.workspace_screen)

        self.file_menu = self.menuBar().addMenu("File")
        export_action = self.file_menu.addAction("Export")
        export_action.triggered.connect(self.export_mod)
        self.file_menu.addSeparator()
        exit_action = self.file_menu.addAction("Close")
        exit_action.triggered.connect(self.return_home)

        self.edit_menu = self.menuBar().addMenu("Edit")
        edit_metadata_action = self.edit_menu.addAction("Edit Metadata")
        edit_metadata_action.triggered.connect(self.edit_metadata)
        self.registry_menu = self.menuBar().addMenu("Registry")
        recipes_menu = self.registry_menu.addMenu("Recipes")
        trade_action = recipes_menu.addAction("Trade Platform")
        trade_action.triggered.connect(self.edit_trade_platform)
        self.mod_label = QLabel("")
        self.mod_label.setObjectName("modname")
        self.mod_label.setFont(self.menuBar().font())
        self.menuBar().setCornerWidget(self.mod_label, Qt.TopRightCorner)
        self.menuBar().hide()

        self.setStyleSheet("""
            QMainWindow, QWidget { background-color: #191d26; color: #eef1f7; }
            QLabel#title { font-size: 30px; font-weight: 600; }
            QLabel#modname { color: #eef1f7; padding: 4px 10px; }
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
            elif label == "Import Mod":
                button.clicked.connect(self.import_mod)
            elif label == "About":
                button.clicked.connect(self.show_about)
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
        self.mod_label.clear()
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
        self.mod_label.setText(mod_folder.name)
        self.mod_label.setToolTip(str(mod_folder))
        self.screens.setCurrentWidget(self.workspace_screen)
        self.menuBar().show()
        self._refresh_workspace()

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
            selection.setEnabled(False)

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

    def import_mod(self):
        try:
            start_dir = str(self.settings.value("importDir", "", type=str) or "")
        except Exception:
            start_dir = ""
        pak_path, _ = QFileDialog.getOpenFileName(
            self, "Select Mod .pak", start_dir, "Pak files (*.pak)")
        if not pak_path:
            return
        try:
            self.settings.setValue("importDir", str(Path(pak_path).parent))
        except Exception:
            pass
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            mod_folder = core.import_mod_from_pak(pak_path)
            error = None
        except FileExistsError as exc:
            error = ("Mod Already Exists", str(exc))
        except (ValueError, OSError, RuntimeError) as exc:
            error = ("Import Failed", str(exc))
        finally:
            QApplication.restoreOverrideCursor()
        if error:
            QMessageBox.critical(self, error[0], error[1])
            return
        self.open_mod_workspace(mod_folder)

    def show_about(self):
        try:
            text = (Path(__file__).resolve().parent / "README.md").read_text(encoding="utf-8")
        except OSError as exc:
            QMessageBox.critical(self, "About", f"Could not read README.md: {exc}")
            return
        if "=====ABOUT=====" in text:
            text = text.split("=====ABOUT=====", 1)[1].strip()
        else:
            text = text.strip() or "No about section yet."
        dialog = QDialog(self)
        dialog.setWindowTitle("About")
        dialog.setMinimumSize(420, 300)
        layout = QVBoxLayout(dialog)
        label = QLabel(text)
        label.setWordWrap(True)
        label.setTextFormat(Qt.PlainText)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(label)
        layout.addWidget(scroll, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok)
        buttons.accepted.connect(dialog.accept)
        layout.addWidget(buttons)
        dialog.exec()

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

    def _refresh_workspace(self) -> None:
        if self.active_mod is None:
            return
        try:
            metafile = core.read_mod_metafile(self.active_mod)
            package_name = metafile.get("package_folder") or ""
        except (ValueError, OSError):
            package_name = ""
        while self.tiles_grid.count():
            item = self.tiles_grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._part_groups = {}
        package = self.active_mod / package_name if package_name else None
        if package is not None and package.is_dir():
            try:
                self._part_groups = core.list_mod_parts(package)
            except OSError:
                self._part_groups = {}
        if not self._part_groups:
            return
        columns = 3
        for index, (base, entries) in enumerate(self._part_groups.items()):
            pretty = base.replace("_", " ")
            kinds = sorted({kind for _, kind in entries})
            tile = QPushButton(f"{pretty}\n{len(entries)} file(s) • {' • '.join(kinds)}")
            tile.setMinimumSize(180, 84)
            tile.clicked.connect(lambda _checked=False, key=base: self.show_part_detail(key))
            self.tiles_grid.addWidget(tile, index // columns, index % columns)

    def show_part_detail(self, base: str) -> None:
        entries = self._part_groups.get(base, [])
        if not entries:
            return
        dialog = QDialog(self)
        dialog.setWindowTitle(base.replace("_", " "))
        dialog.setMinimumWidth(480)
        layout = QVBoxLayout(dialog)
        lines = "\n".join(f"{kind}: {ref}" for ref, kind in entries)
        detail = QLabel(lines)
        detail.setWordWrap(True)
        detail.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(detail)
        row = QHBoxLayout()
        reveal_btn = QPushButton("Show in folder")
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(dialog.reject)
        row.addWidget(reveal_btn)
        row.addStretch(1)
        row.addWidget(buttons)
        layout.addLayout(row)

        def on_reveal():
            try:
                metafile = core.read_mod_metafile(self.active_mod)
                package = self.active_mod / (metafile.get("package_folder") or "")
                target = package / (entries[0][0].lstrip("/") + ".uasset")
                folder = target.parent if target.is_file() else package
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))
            except (ValueError, OSError):
                pass

        reveal_btn.clicked.connect(on_reveal)
        dialog.exec()

    def edit_trade_platform(self) -> None:
        if self.active_mod is None:
            return

        def normalized(name: str) -> str:
            return name.lower().replace("_", "")

        try:
            metafile = core.read_mod_metafile(self.active_mod)
            package_name = metafile.get("package_folder") or ""
        except (ValueError, OSError) as exc:
            QMessageBox.critical(self, "Could Not Open Mod", str(exc))
            return
        package = self.active_mod / package_name if package_name else None
        existing: list[str] = []
        if package is not None and package.is_dir():
            try:
                groups = core.list_mod_parts(package)
            except OSError:
                groups = {}
            existing = sorted(base for base in groups if "tradeplatform" in normalized(base))
        if existing:
            self._refresh_workspace()
            self.show_part_detail(existing[0])
            return

        try:
            extracted = core.get_extracted_game_path()
        except OSError:
            extracted = None
        if extracted is None or not extracted.is_dir():
            QMessageBox.warning(self, "Game Files Missing",
                                "Extracted game files were not found in local/. Run the installer first.")
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            index = core.index_game_assets()
        except OSError as exc:
            QMessageBox.critical(self, "Could Not Index Game Files", str(exc))
            return
        finally:
            QApplication.restoreOverrideCursor()
        matches = [rel for rel in index if "tradeplatform" in normalized(rel)]
        recipes = [rel for rel in matches if "recipe" in normalized(rel)]
        targets = recipes or matches
        if not targets:
            QMessageBox.warning(self, "Trade Platform Not Found",
                                "No Trade Platform assets were found in the extracted game files.")
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            for rel in targets:
                core.override_asset_from_game(self.active_mod, rel)
        except (ValueError, OSError) as exc:
            QMessageBox.critical(self, "Could Not Add Trade Platform", str(exc))
            return
        finally:
            QApplication.restoreOverrideCursor()
        self._refresh_workspace()
        refreshed = [base for base in self._part_groups if "tradeplatform" in normalized(base)]
        if refreshed:
            self.show_part_detail(sorted(refreshed)[0])
        else:
            QMessageBox.information(self, "Trade Platform",
                                    f"Added {len(targets)} Trade Platform asset(s).")

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
