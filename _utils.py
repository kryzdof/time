import sys
from pathlib import Path

import keyring
from jira import JIRA, JIRAError
from PySide6 import QtCore, QtWidgets
from requests.exceptions import ConnectTimeout

HTTP_NOT_FOUND = 404
HTTP_NOT_AUTHORIZED = 401


def resource_path(relative_path: str) -> Path:
    """Get absolute path to resource, works for dev and for PyInstaller."""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS,
        # and places our data files in a folder relative to that temp
        # folder named as specified in the datas tuple in the spec file
        base_path = Path(sys._MEIPASS) / "pics"  # noqa: SLF001
    except AttributeError:
        # sys._MEIPASS is not defined, so use the original path
        base_path = Path.cwd() / "pics"
    return str(base_path / relative_path)


def getJiraInstance(urlstart: str, uid: str, password: str | None = None) -> JIRA:
    if uid is None or uid == "":
        raise ConnectionError("Username is not set! Please set the User ID in the settings.")
    if password is None:
        password = keyring.get_password("jiraconnection", uid)
        if password is None:
            raise ConnectionError("Password is not set")
    try:
        jira = JIRA(
            urlstart,
            basic_auth=(uid, password),
            options={"agile_rest_path": "agile"},
            max_retries=0,
            timeout=5,
        )
    except JIRAError as e:
        if e.status_code == HTTP_NOT_AUTHORIZED:
            raise ConnectionError("Username or Password is wrong") from e
        raise
    except ConnectTimeout as e:
        raise ConnectionError(f"Could not connect to {urlstart}") from e
    return jira


def JiraWriteLog(cfg: dict, ticket: str, duration: int) -> bool:
    try:
        jira = getJiraInstance(cfg["url"], cfg["uid"])
    except Exception as e:
        QtWidgets.QMessageBox.critical(None, "Jira Connection Error", str(e), QtWidgets.QMessageBox.Ok)
        return False
    try:
        jira.add_worklog(ticket, timeSpentSeconds=duration)
    except JIRAError as e:
        if e.status_code == HTTP_NOT_FOUND:
            QtWidgets.QMessageBox.critical(
                None,
                "Work Log Creation Error",
                f"Issue {ticket} not found",
                QtWidgets.QMessageBox.Ok,
            )
        else:
            QtWidgets.QMessageBox.critical(
                None,
                "Work Log Creation Error",
                f"Error: '{e.text}'\nStatus Code: {e.status_code}",
                QtWidgets.QMessageBox.Ok,
            )
        return False
    except Exception as e:
        QtWidgets.QMessageBox.critical(None, "Work Log Creation Error", str(e), QtWidgets.QMessageBox.Ok)
        return False
    return True


def timeToMinutes(qtime: QtCore.QTime) -> int:
    return qtime.hour() * 60 + qtime.minute()


def minutesToTime(minutes: int) -> QtCore.QTime:
    return QtCore.QTime(minutes // 60, minutes % 60)
