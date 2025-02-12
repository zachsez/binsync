import traceback
import os

from . import ui_version
if ui_version == "PySide2":
    from PySide2.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit, QMessageBox, \
        QFileDialog, QCheckBox, QGridLayout
    from PySide2.QtCore import QDir
elif ui_version == "PySide6":
    from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit, QMessageBox, \
        QFileDialog, QCheckBox, QGridLayout
    from PySide6.QtCore import QDir
else:
    from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit, QMessageBox, \
        QFileDialog, QCheckBox, QGridLayout
    from PyQt5.QtCore import QDir

from ...client import ConnectionWarnings


class SyncConfig(QDialog):
    """
    The dialog that allows a user to config a BinSync client for:
    - initing a local repo
    - cloning a remote
    - using a locally pulled remote repo
    """
    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller

        self.setWindowTitle("Configure BinSync")

        self._main_layout = QVBoxLayout()
        self._user_edit = None  # type:QLineEdit
        self._repo_edit = None  # type:QLineEdit
        self._remote_edit = None  # type:QLineEdit
        self._initrepo_checkbox = None  # type:QCheckBox

        self._init_widgets()
        self.setLayout(self._main_layout)
        self.show()

    def _init_widgets(self):
        upper_layout = QGridLayout()

        # user label
        user_label = QLabel(self)
        user_label.setText("User name")

        self._user_edit = QLineEdit(self)

        row = 0
        upper_layout.addWidget(user_label, row, 0)
        upper_layout.addWidget(self._user_edit, row, 1)
        row += 1

        # binsync label
        binsync_label = QLabel(self)
        binsync_label.setText("Git repo")

        # repo path
        self._repo_edit = QLineEdit(self)
        self._repo_edit.textChanged.connect(self._on_repo_textchanged)
        self._repo_edit.setFixedWidth(150)

        # repo path selection button
        repo_button = QPushButton(self)
        repo_button.setText("...")
        repo_button.clicked.connect(self._on_repo_clicked)
        repo_button.setFixedWidth(40)

        upper_layout.addWidget(binsync_label, row, 0)
        upper_layout.addWidget(self._repo_edit, row, 1)
        upper_layout.addWidget(repo_button, row, 2)
        row += 1

        # clone from a remote URL
        remote_label = QLabel(self)
        remote_label.setText("Remote URL")
        self._remote_edit = QLineEdit(self)
        self._remote_edit.setEnabled(False)

        upper_layout.addWidget(remote_label, row, 0)
        upper_layout.addWidget(self._remote_edit, row, 1)
        row += 1

        # initialize repo checkbox
        self._initrepo_checkbox = QCheckBox(self)
        self._initrepo_checkbox.setText("Create repository")
        self._initrepo_checkbox.setToolTip("I'm the first user of this binsync project and I'd "
                                           "like to initialize it as a sync repo.")
        self._initrepo_checkbox.setChecked(False)
        self._initrepo_checkbox.setEnabled(False)

        upper_layout.addWidget(self._initrepo_checkbox, row, 1)
        row += 1

        # buttons
        self._ok_button = QPushButton(self)
        self._ok_button.setText("OK")
        self._ok_button.setDefault(True)
        self._ok_button.clicked.connect(self._on_ok_clicked)

        cancel_button = QPushButton(self)
        cancel_button.setText("Cancel")
        cancel_button.clicked.connect(self._on_cancel_clicked)

        buttons_layout = QHBoxLayout()
        buttons_layout.addWidget(self._ok_button)
        buttons_layout.addWidget(cancel_button)

        # main layout
        self._main_layout.addLayout(upper_layout)
        self._main_layout.addLayout(buttons_layout)

    #
    # Event handlers
    #

    def _on_ok_clicked(self):
        user = self._user_edit.text()
        path = self._repo_edit.text()
        init_repo = self._initrepo_checkbox.isChecked()

        if not user:
            QMessageBox(self).critical(None, "Invalid user name",
                                       "User name cannot be empty."
                                       )
            return

        if user.lower() == "__root__":
            QMessageBox(self).critical(None, "Invalid user name",
                                       "User name cannot (and should not) be \'__root__\'."
                                       )
            return

        if not os.path.isdir(path) and not init_repo:
            QMessageBox(self).critical(None, "Repo does not exist",
                                       "The specified sync directory does not exist. "
                                       "Do you maybe want to initialize it?"
                                       )
            return

        # convert to remote repo if no local is provided
        if not self.is_git_repo(path):
            remote_url = self._remote_edit.text()
        else:
            remote_url = None

        try:
            connection_warnings = self.controller.connect(user, path, init_repo=init_repo, remote_url=remote_url)
        except Exception as e:
            QMessageBox(self).critical(None, "Error connecting to repository", str(e))
            traceback.print_exc()
            return

        self._parse_and_display_connection_warnings(connection_warnings)
        print(f"[BinSync]: Client has connected to sync repo with user: {user}.")
        self.close()

    def _on_repo_clicked(self):
        if 'SNAP' in os.environ:
            directory = QFileDialog.getExistingDirectory(self, "Select sync repo", "",
                                                    QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks | QFileDialog.DontUseNativeDialog)
        else:
            directory = QFileDialog.getExistingDirectory(self, "Select sync repo", "",
                                                         QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks)
        self._repo_edit.setText(QDir.toNativeSeparators(directory))

    def _on_repo_textchanged(self, new_text):
        # is it a git repo?
        if not self.is_git_repo(new_text.strip()):
            # no it's not
            # maybe we want to clone from the remote side?
            self._remote_edit.setEnabled(True)
            self._initrepo_checkbox.setEnabled(True)
        else:
            # yes it is!
            # we don't want to initialize it or allow cloning from the remote side
            self._remote_edit.setEnabled(False)
            self._initrepo_checkbox.setEnabled(False)

    def _on_cancel_clicked(self):
        self.close()

    #
    # Static methods
    #

    @staticmethod
    def is_git_repo(path):
        return os.path.isdir(os.path.join(path, ".git"))

    @staticmethod
    def _parse_and_display_connection_warnings(warnings):
        warning_text = ""

        for warning in warnings:
            if warning == ConnectionWarnings.HASH_MISMATCH:
                warning_text += "Warning: the hash stored for this BinSync project does not match"
                warning_text += " the hash of the binary you are attempting to analyze. It's possible"
                warning_text += " you are working on a different binary.\n"

        if len(warning_text) > 0:
            QMessageBox.warning(
                None,
                "BinSync: Connection Warnings",
                warning_text,
                QMessageBox.Ok,
            )
