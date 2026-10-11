import sys
import core
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QButtonGroup, QHBoxLayout, QLabel, QMainWindow, QPushButton, QStackedWidget, QVBoxLayout, QWidget


PAGES = ["Home", "Create", "Assets", "Settings"]


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
        page_layout = QVBoxLayout(page)
        page_title = QLabel(page_name)
        page_title.setObjectName("pageTitle")
        page_title.setAlignment(Qt.AlignCenter)
        page_layout.addStretch(1)
        page_layout.addWidget(page_title, alignment=Qt.AlignCenter)
        page_layout.addStretch(2)
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
        QLabel#pageTitle { color: #eef1f7; font-size: 30px; }
    """)
    window.setCentralWidget(root)
    window.show()
    app.exec()


if __name__ == "__main__":
    main()