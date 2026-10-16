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
        QHeaderView,
        QInputDialog,
        QLabel,
        QLineEdit,
        QMainWindow,
        QMessageBox,
        QPushButton,
        QScrollArea,
        QSpinBox,
        QStackedWidget,
        QTableWidget,
        QTableWidgetItem,
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
            QPushButton:checked { background-color: #1b2e52; border: 2px solid #4d6fb5; }
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
        dialog.setWindowFlags(dialog.windowFlags() | Qt.WindowMinMaxButtonsHint)
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
        dialog.setWindowFlags(dialog.windowFlags() | Qt.WindowMinMaxButtonsHint)
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
        try:
            existing_author = core.read_mod_metadata(self.active_mod).get("metadata", {}).get("author", "")
        except (ValueError, OSError):
            existing_author = ""

        dialog = QDialog(self)
        dialog.setWindowFlags(dialog.windowFlags() | Qt.WindowMinMaxButtonsHint)
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
        author_edit = QLineEdit(str(existing_author or ""))
        author_edit.setPlaceholderText("Your name (shown in mod managers)")
        identity_form.addRow("Priority:", priority_spin)
        identity_form.addRow("Mod name / ID:", name_edit)
        identity_form.addRow("Version:", version_edit)
        identity_form.addRow("Author:", author_edit)
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
                author=author_edit.text(),
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
        dialog.setWindowFlags(dialog.windowFlags() | Qt.WindowMinMaxButtonsHint)
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
        if base == core.TRADE_VALUE_TABLE_LEAF and self._mod_trade_table() is not None:
            edit_btn = QPushButton("Edit Trade Values")
            edit_btn.clicked.connect(lambda: (dialog.accept(), self.edit_trade_values(self._mod_trade_table())))
            row.addWidget(edit_btn)
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

    def _mod_trade_table(self) -> Path | None:
        if self.active_mod is None:
            return None
        try:
            metafile = core.read_mod_metafile(self.active_mod)
            package_name = metafile.get("package_folder") or ""
        except (ValueError, OSError):
            return None
        if not package_name:
            return None
        package = self.active_mod / package_name
        table = package / "Astro" / "Content" / "Globals" / (
            core.TRADE_VALUE_TABLE_LEAF + ".uasset")
        if table.is_file():
            return table
        legacy = package / "Game" / "Globals" / (
            core.TRADE_VALUE_TABLE_LEAF + ".uasset")
        if legacy.is_file():
            try:
                table.parent.mkdir(parents=True, exist_ok=True)
                for sibling in legacy.parent.glob(legacy.stem + ".*"):
                    if sibling.is_file() and not sibling.is_symlink():
                        sibling.rename(table.parent / sibling.name)
                try:
                    legacy.parent.rmdir()
                    legacy.parent.parent.rmdir()
                except OSError:
                    pass
            except OSError:
                return legacy
            return table if table.is_file() else None
        return None

    def edit_trade_platform(self) -> None:
        if self.active_mod is None:
            return
        table = self._mod_trade_table()
        if table is not None:
            self._refresh_workspace()
            self.edit_trade_values(table)
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
            game_rel = core.find_trade_value_table()
        except OSError as exc:
            QMessageBox.critical(self, "Could Not Index Game Files", str(exc))
            return
        finally:
            QApplication.restoreOverrideCursor()
        if game_rel is None:
            QMessageBox.warning(self, "Trade Platform Not Found",
                                "No Trade Platform recipe table was found in the extracted game files.")
            return
        try:
            game_table = (extracted / Path(game_rel)).resolve()
        except OSError as exc:
            QMessageBox.critical(self, "Could Not Open Recipe Table", str(exc))
            return
        self.edit_trade_values(game_table, stage_into_mod=self.active_mod)

    def edit_trade_values(self, table_path: str | Path,
                          stage_into_mod: str | Path | None = None) -> None:
        table = Path(table_path)
        dialog = QDialog(self)
        dialog.setWindowFlags(dialog.windowFlags() | Qt.WindowMinMaxButtonsHint)
        dialog.setWindowTitle("Trade Platform Recipe")
        dialog.setMinimumSize(560, 480)
        layout = QVBoxLayout(dialog)
        body = QHBoxLayout()
        layout.addLayout(body, 1)
        tab_buttons = QVBoxLayout()
        body.addLayout(tab_buttons)
        pages = QStackedWidget()
        body.addWidget(pages, 1)
        try:
            sections = core.read_trade_sections(table)
        except (ValueError, OSError) as exc:
            QMessageBox.critical(self, "Could Not Read Trade Values", str(exc))
            return
        if not sections:
            QMessageBox.critical(self, "Could Not Read Trade Values",
                                  "No trade sections found in this file.")
            return

        def decompose(value: float) -> tuple[int, int]:
            best = (0, 1)
            best_err = abs(value)
            for ratio_in in range(0, 10):
                for ratio_out in range(1, 10):
                    err = abs(ratio_in / ratio_out - value)
                    if err < best_err - 1e-9 or (
                            abs(err - best_err) <= 1e-9 and ratio_in + ratio_out < best[0] + best[1]):
                        best = (ratio_in, ratio_out)
                        best_err = err
            return best

        def frac_text(ratio_in: int, ratio_out: int) -> str:
            return f"{ratio_in / ratio_out:.4f}".rstrip("0").rstrip(".")

        tab_state: list[dict] = []

        def build_tab(rows: list, pos: int) -> QWidget:
            page = QWidget()
            page_layout = QVBoxLayout(page)
            page_layout.addWidget(QLabel(f"{len(rows)} trade values:"))
            grid = QTableWidget(len(rows), 4)
            grid.setHorizontalHeaderLabels(["Item", "Input", "Gets", "Value"])
            grid.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
            for column, width in ((1, 90), (2, 90), (3, 110)):
                grid.horizontalHeader().setSectionResizeMode(column, QHeaderView.Fixed)
                grid.setColumnWidth(column, width)
            grid.verticalHeader().setVisible(False)
            grid.setEditTriggers(QTableWidget.NoEditTriggers)
            state: dict = {"rows": rows, "s_spins": [], "t_spins": [],
                           "val_labels": [], "original": [], "dirty": []}

            def mark_dirty(index: int, st: dict = state) -> None:
                st["dirty"][index] = (st["s_spins"][index].value(),
                                      st["t_spins"][index].value()) != st["original"][index]
                st["val_labels"][index].setText(
                    frac_text(st["s_spins"][index].value(), st["t_spins"][index].value()))

            for index, row in enumerate(rows):
                name_cell = QTableWidgetItem(row["display"])
                name_cell.setFlags(name_cell.flags() & ~Qt.ItemIsEditable)
                name_cell.setToolTip(row.get("leaf") or row["display"])
                grid.setItem(index, 0, name_cell)
                in_spin = QSpinBox()
                in_spin.setRange(0, 9)
                out_spin = QSpinBox()
                out_spin.setRange(1, 9)
                in_spin.blockSignals(True)
                out_spin.blockSignals(True)
                start_in, start_out = decompose(float(row["value"]))
                in_spin.setValue(start_in)
                out_spin.setValue(start_out)
                in_spin.blockSignals(False)
                out_spin.blockSignals(False)
                grid.setCellWidget(index, 1, in_spin)
                grid.setCellWidget(index, 2, out_spin)
                state["s_spins"].append(in_spin)
                state["t_spins"].append(out_spin)
                val_label = QLabel(frac_text(start_in, start_out))
                val_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
                grid.setCellWidget(index, 3, val_label)
                state["val_labels"].append(val_label)
                state["original"].append((start_in, start_out))
                state["dirty"].append(False)
                in_spin.valueChanged.connect(
                    lambda _v, i=index: mark_dirty(i))
                out_spin.valueChanged.connect(
                    lambda _v, i=index: mark_dirty(i))
            page_layout.addWidget(grid, 1)
            tab_row = QHBoxLayout()
            add_btn = QPushButton("＋ Add Trade")
            add_btn.setMinimumSize(120, 36)
            add_btn.clicked.connect(lambda _checked=False, p=pos: add_trade(p))
            tab_row.addWidget(add_btn, alignment=Qt.AlignLeft)
            tab_row.addStretch(1)
            page_layout.addLayout(tab_row)
            tab_state.append(state)
            return page

        live_sections: list = list(sections)
        live_labels: list[str] = [s["label"] for s in live_sections]
        selector_buttons: dict[str, QPushButton] = {}

        def clear_tabs() -> None:
            while pages.count():
                page = pages.widget(0)
                pages.removeWidget(page)
                page.deleteLater()
            selector_buttons.clear()
            tab_state.clear()

        def build_button_column() -> None:
            while tab_buttons.count():
                item = tab_buttons.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()
            for label in live_labels:
                btn = QPushButton(label)
                btn.setCheckable(True)
                btn.setMinimumSize(110, 44)
                tab_buttons.addWidget(btn)
                selector_buttons[label] = btn
                btn.clicked.connect(lambda _checked=False, name=label: select_tab(name))
            tab_buttons.addStretch(1)

        def refresh_tabs(select: str | None = None) -> None:
            nonlocal live_sections, live_labels
            try:
                live_sections = core.read_trade_sections(table)
            except (ValueError, OSError) as exc:
                QMessageBox.critical(dialog, "Could Not Read Trade Values", str(exc))
                return
            live_labels = [s["label"] for s in live_sections]
            clear_tabs()
            for pos, (label, section) in enumerate(zip(live_labels, live_sections)):
                pages.addWidget(build_tab(section["rows"], pos))
            build_button_column()
            select_tab(select or live_labels[-1])

        def select_tab(label: str) -> None:
            for name, btn in selector_buttons.items():
                btn.setChecked(name == label)
            if label in live_labels:
                pages.setCurrentIndex(live_labels.index(label))

        def add_trade(pos: int) -> None:
            try:
                current = core.read_trade_sections(table)
            except (ValueError, OSError) as exc:
                QMessageBox.critical(dialog, "Could Not Read Trade Values", str(exc))
                return
            if not 0 <= pos < len(current):
                return
            owned = {row["ref"] for row in current[pos]["rows"]}
            candidates = []
            for sec in current:
                for row in sec["rows"]:
                    if row["ref"] not in owned and row["ref"] not in [c[0] for c in candidates]:
                        candidates.append((row["ref"], row["display"]))
            if not candidates:
                QMessageBox.information(dialog, "Add Trade", "Every known item is already in this section.")
                return
            form = QDialog(dialog)
            form.setWindowTitle(f"Add Trade — {live_labels[pos]}")
            form.setMinimumWidth(340)
            form_layout = QFormLayout(form)
            picker = QComboBox()
            for ref, display in sorted(candidates, key=lambda c: c[1].casefold()):
                picker.addItem(display, ref)
            form_layout.addRow("Item:", picker)
            form_in = QSpinBox()
            form_in.setRange(0, 9)
            form_in.setValue(1)
            form_layout.addRow("Input:", form_in)
            form_out = QSpinBox()
            form_out.setRange(1, 9)
            form_out.setValue(1)
            form_layout.addRow("Gets:", form_out)
            form_buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            form_layout.addRow(form_buttons)
            form_buttons.accepted.connect(form.accept)
            form_buttons.rejected.connect(form.reject)
            if form.exec() != QDialog.Accepted:
                return
            try:
                core.add_trade_row(table, pos,
                                   picker.currentData(),
                                   form_in.value() / form_out.value())
            except (ValueError, OSError) as exc:
                QMessageBox.critical(dialog, "Could Not Add Trade", str(exc))
                return
            refresh_tabs(live_labels[pos])

        for pos, (label, section) in enumerate(zip(live_labels, live_sections)):
            pages.addWidget(build_tab(section["rows"], pos))
        build_button_column()
        select_tab("Fault Finder" if "Fault Finder" in live_labels else live_labels[-1])
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        layout.addWidget(buttons)

        def on_save() -> None:
            changes = {}
            for state in tab_state:
                for index, row in enumerate(state["rows"]):
                    if not state["dirty"][index]:
                        continue
                    ratio_in = state["s_spins"][index].value()
                    ratio_out = state["t_spins"][index].value()
                    if ratio_out <= 0:
                        continue
                    changes[row["key"]] = ratio_in / ratio_out
            if not changes:
                dialog.accept()
                return
            target = table
            if stage_into_mod is not None:
                try:
                    game_rel = core.find_trade_value_table()
                    if game_rel is None:
                        raise ValueError("Recipe table not found in the extracted game files.")
                    core.override_asset_from_game(stage_into_mod, game_rel, mirror=True)
                    staged = self._mod_trade_table()
                    if staged is None:
                        raise ValueError("Could not stage the recipe table into this mod.")
                    target = staged
                except (ValueError, OSError) as exc:
                    QMessageBox.critical(dialog, "Could Not Stage Recipe Table", str(exc))
                    return
            try:
                core.write_trade_values(target, changes)
            except (ValueError, OSError) as exc:
                QMessageBox.critical(dialog, "Could Not Save Trade Values", str(exc))
                return
            self._refresh_workspace()
            QMessageBox.information(dialog, "Trade Values", f"Saved {len(changes)} trade value(s).")
            dialog.accept()

        buttons.accepted.connect(on_save)
        buttons.rejected.connect(dialog.reject)
        dialog.exec()

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
