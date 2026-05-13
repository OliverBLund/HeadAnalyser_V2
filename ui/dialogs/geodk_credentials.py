"""Geo.dk credential prompt dialogs (token stays in Python, never in JS)."""

from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QCheckBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from styles.colors import Colors


class GeoDKCredentialsDialog(QDialog):
    def __init__(
        self,
        *,
        parent=None,
        username: str = "",
        role: str = "",
        insecure_ssl: bool = False,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Geo.dk Credentials")
        self.setModal(True)
        self.resize(420, 220)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        hint = QLabel(
            "Enter your Geo.dk credentials to request cross sections.\n"
            "The token is stored only in this app session."
        )
        hint.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: 11px;")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignLeft)
        form.setFormAlignment(Qt.AlignTop)

        self.username_edit = QLineEdit(str(username or "").strip())
        self.username_edit.setPlaceholderText("you@example.com")
        form.addRow("Username:", self.username_edit)

        self.password_edit = QLineEdit("")
        self.password_edit.setEchoMode(QLineEdit.Password)
        self.password_edit.setPlaceholderText("Password")
        form.addRow("Password:", self.password_edit)

        self.role_edit = QLineEdit(str(role or "").strip())
        self.role_edit.setPlaceholderText("(optional)")
        form.addRow("Role:", self.role_edit)

        layout.addLayout(form)

        self.insecure_ssl_check = QCheckBox("Insecure SSL (disable certificate verification)")
        self.insecure_ssl_check.setChecked(bool(insecure_ssl))
        self.insecure_ssl_check.setToolTip("Debug only. Use if your environment lacks CA certificates.")
        layout.addWidget(self.insecure_ssl_check)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        cancel_btn = QPushButton("Cancel")
        ok_btn = QPushButton("Continue")
        ok_btn.setDefault(True)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(ok_btn)
        layout.addLayout(btn_row)

        cancel_btn.clicked.connect(self.reject)
        ok_btn.clicked.connect(self._on_ok_clicked)

    def _on_ok_clicked(self) -> None:
        if not self.username().strip() or not self.password().strip():
            # Keep it lightweight; validation errors will be shown by caller if needed.
            pass
        self.accept()

    def username(self) -> str:
        return str(self.username_edit.text() or "").strip()

    def password(self) -> str:
        return str(self.password_edit.text() or "").strip()

    def role(self) -> str:
        return str(self.role_edit.text() or "").strip()

    def insecure_ssl(self) -> bool:
        return bool(self.insecure_ssl_check.isChecked())

