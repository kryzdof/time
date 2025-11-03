import os
import sys

import keyring
from PySide6 import QtCore, QtWidgets
from jira import JIRA, JIRAError
from requests.exceptions import ConnectTimeout


def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS,
        # and places our data files in a folder relative to that temp
        # folder named as specified in the datas tuple in the spec file
        base_path = os.path.join(sys._MEIPASS, "pics")
    except AttributeError:
        # sys._MEIPASS is not defined, so use the original path
        base_path = os.path.join(os.path.curdir, "pics")

    return os.path.join(base_path, relative_path)


def getJiraInstance(urlstart, uid, password=None):
    if password is None:
        password = keyring.get_password("jiraconnection", uid)
    try:
        jira = JIRA(
            urlstart,
            basic_auth=(uid, password),
            options={"agile_rest_path": "agile"},
            max_retries=0,
            timeout=5,
        )
    except JIRAError as e:
        print(e)
        if e.status_code == 401:
            raise ConnectionError("Username or Password is wrong")
        raise
    except ConnectTimeout:
        raise ConnectionError(f"Could not connect to {urlstart}")
    return jira


def JiraWriteLog(cfg, ticket, duration):
    try:
        jira = getJiraInstance(cfg["url"], cfg["uid"])
    except Exception as e:
        QtWidgets.QMessageBox.critical(None, "Jira Connection Error", str(e), QtWidgets.QMessageBox.Ok)
        return False
    try:
        jira.add_worklog(ticket, timeSpentSeconds=duration)
    except JIRAError as e:
        if e.status_code == 404:
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


def timeToMinutes(qtime):
    return qtime.hour() * 60 + qtime.minute()


def minutesToTime(minutes):
    return QtCore.QTime(minutes // 60, minutes % 60)
