import calendar
import json
from itertools import zip_longest

import keyring
from PySide6 import QtCore, QtWidgets, QtGui
from keyring.backends.Windows import WinVaultKeyring

from utils import minutesToTime, timeToMinutes, getJiraInstance, resource_path

keyring.set_keyring(WinVaultKeyring())


class AdvancedTimeEdit(QtWidgets.QTimeEdit):
    connectHoursAndMinutes = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setDisplayFormat("hh:mm")
        self.setWrapping(True)

    def stepBy(self, steps):
        if self.connectHoursAndMinutes:
            currentTime = self.time()
            super().stepBy(steps)
            if self.currentSection() == self.MinuteSection:
                if currentTime.minute() == 0 and steps < 0:
                    self.setTime(self.time().addSecs(-3600))
                if currentTime.minute() == 59 and steps > 0:
                    self.setTime(self.time().addSecs(3600))
        else:
            super().stepBy(steps)


class AdvancedSpinBox(QtWidgets.QSpinBox):
    wrapped = QtCore.Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWrapping(True)

    def stepBy(self, step):
        if self.value() == self.minimum() and step < 0:
            self.wrapped.emit(-1)
        if self.value() == self.maximum() and step > 0:
            self.wrapped.emit(1)
        super().stepBy(step)


class DetailTimesDialog(QtWidgets.QDialog):
    def __init__(self, parent, title, data):
        super().__init__(parent=parent)

        self.timeStampData = data
        self.totalDiff = 0

        self.setWindowTitle(title)

        mainLayout = QtWidgets.QGridLayout()

        self.startTimes = []
        self.endTimes = []
        self.timeDuration = []

        label = QtWidgets.QLabel("Start Times")
        label.setAlignment(QtCore.Qt.AlignHCenter)
        mainLayout.addWidget(label, 0, 0, 1, 2)
        label = QtWidgets.QLabel("End Times")
        label.setAlignment(QtCore.Qt.AlignHCenter)
        mainLayout.addWidget(label, 0, 2, 1, 2)
        label = QtWidgets.QLabel("Diff Times")
        label.setAlignment(QtCore.Qt.AlignHCenter)
        mainLayout.addWidget(label, 0, 4)

        for x, timestamps in zip_longest(
            range(10), self.timeStampData, fillvalue=(0, 0)
        ):
            t = QtCore.QTime(minutesToTime(timestamps[0]))
            startTimes = AdvancedTimeEdit(t)
            startTimes.editingFinished.connect(self.updateDiffs)
            self.startTimes.append(startTimes)
            mainLayout.addWidget(startTimes, x + 1, 1)
            autoTime = QtWidgets.QPushButton(
                QtGui.QPixmap(resource_path("time.png")), ""
            )
            autoTime.QTimeReference = startTimes
            autoTime.clicked.connect(self.updateAutoTime)
            mainLayout.addWidget(autoTime, x + 1, 0)

            t = QtCore.QTime(minutesToTime(timestamps[1]))
            endTimes = AdvancedTimeEdit(t)
            endTimes.editingFinished.connect(self.updateDiffs)
            self.endTimes.append(endTimes)
            mainLayout.addWidget(endTimes, x + 1, 2)
            autoTime = QtWidgets.QPushButton(
                QtGui.QPixmap(resource_path("time.png")), ""
            )
            autoTime.QTimeReference = endTimes
            autoTime.clicked.connect(self.updateAutoTime)
            mainLayout.addWidget(autoTime, x + 1, 3)

            label = QtWidgets.QLabel("")
            self.timeDuration.append(label)
            mainLayout.addWidget(label, x + 1, 4)

        label = QtWidgets.QLabel("Total time:")
        mainLayout.addWidget(label, 11, 1)

        self.totalTime = QtWidgets.QLabel("")
        mainLayout.addWidget(self.totalTime, 11, 2)

        buttonbox = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok
            | QtWidgets.QDialogButtonBox.Cancel
            | QtWidgets.QDialogButtonBox.Reset
        )
        buttonbox.accepted.connect(self.accept)
        buttonbox.rejected.connect(self.reject)
        buttonbox.button(QtWidgets.QDialogButtonBox.Reset).clicked.connect(
            self.resetTimes
        )

        mainLayout.addWidget(buttonbox, 20, 0, 1, 5)
        self.setLayout(mainLayout)
        self.updateDiffs()

    def updateAutoTime(self):
        timeEdit = self.sender().QTimeReference
        timeEdit.setTime(QtCore.QTime.currentTime())

    def updateDiffs(self):
        self.totalDiff = 0
        for x in range(10):
            diff = self.startTimes[x].time().secsTo(self.endTimes[x].time())
            self.totalDiff += diff
            if not diff:
                self.timeDuration[x].hide()
            else:
                diffTime = QtCore.QTime(0, 0).addSecs(diff)
                self.timeDuration[x].setText(diffTime.toString("h:mm"))
                self.timeDuration[x].show()

        self.totalTime.setText(
            QtCore.QTime(0, 0).addSecs(self.totalDiff).toString("h:mm")
        )

    def resetTimes(self):
        for x, timestamps in zip_longest(
            range(10), self.timeStampData, fillvalue=(0, 0)
        ):
            t = QtCore.QTime(minutesToTime(timestamps[0]))
            self.startTimes[x].setTime(t)
            t = QtCore.QTime(minutesToTime(timestamps[1]))
            self.endTimes[x].setTime(t)
        self.updateDiffs()

    def accept(self):
        super().accept()

    def getDetails(self):
        if self.totalDiff:
            totalStart = QtCore.QTime(7, 0)
            totalEnd = totalStart.addSecs(self.totalDiff)
        else:
            totalStart = QtCore.QTime(0, 0)
            totalEnd = QtCore.QTime(0, 0)
        timeStamps = []
        for x in range(10):
            timeStamps.append(
                (
                    timeToMinutes(self.startTimes[x].time()),
                    timeToMinutes(self.endTimes[x].time()),
                )
            )
        return timeToMinutes(totalStart), timeToMinutes(totalEnd), timeStamps


class SettingsDialog(QtWidgets.QDialog):
    def __init__(self, parent):
        super().__init__(parent=parent)

        self.config = self.getConfig()
        self.setWindowTitle("Settings")
        mainLayout = QtWidgets.QGridLayout()

        timeSettingsLayout = QtWidgets.QGridLayout()
        timeSettingsWidgets = QtWidgets.QGroupBox("Time Settings")
        _timeSettingsWidgetsText = "Guess what! That are the daily working hours you think you should be working :)"
        timeSettingsWidgets.setToolTip(_timeSettingsWidgetsText)
        timeSettingsWidgets.setWhatsThis(_timeSettingsWidgetsText)
        for x, dayStr in enumerate([d for d in calendar.day_name]):
            label = QtWidgets.QLabel(dayStr)
            timeSettingsLayout.addWidget(label, x + 1, 0)
        self.workingTimes = []
        for x in range(1, 8):
            t = self.config["hours"][x]
            workingTime = AdvancedTimeEdit(t)
            self.workingTimes.append(workingTime)
            timeSettingsLayout.addWidget(workingTime, x, 1)
        timeSettingsWidgets.setLayout(timeSettingsLayout)

        lunchSettingsLayout = QtWidgets.QGridLayout()
        lunchSettingsWidgets = QtWidgets.QGroupBox("Lunch Settings")
        _lunchSettingsWidgetsText = (
            "This time will be reduced from your working hours if the lunch break checkbox "
            "is set"
        )
        lunchSettingsWidgets.setToolTip(_lunchSettingsWidgetsText)
        lunchSettingsWidgets.setWhatsThis(_lunchSettingsWidgetsText)
        label = QtWidgets.QLabel("Normal Lunch Break")
        lunchSettingsLayout.addWidget(label, 0, 0)
        self.lunchTime = AdvancedTimeEdit(
            QtCore.QTime(0, 0).addSecs(self.config["lunchBreak"] * 60)
        )
        lunchSettingsLayout.addWidget(self.lunchTime, 0, 1)
        lunchSettingsWidgets.setLayout(lunchSettingsLayout)

        generalSettingsLayout = QtWidgets.QGridLayout()
        generalSettingsWidgets = QtWidgets.QGroupBox("General Settings")
        self.autoCalcEndTime = QtWidgets.QCheckBox("Forecast end time")
        self.autoCalcEndTime.setChecked(self.config["forecastEndTimes"])
        _autoCalcEndTimeText = (
            "This will automatically calculate the end time of the day according "
            "to the supposed working hours for this day"
        )
        self.autoCalcEndTime.setToolTip(_autoCalcEndTimeText)
        self.autoCalcEndTime.setWhatsThis(_autoCalcEndTimeText)

        self.hourWrapAround = QtWidgets.QCheckBox("Wrap hours")
        self.hourWrapAround.setChecked(self.config["connectHoursAndMinutes"])
        _hourWrapAroundText = "If minutes wrap around, the hour will also be changed"
        self.hourWrapAround.setToolTip(_hourWrapAroundText)
        self.hourWrapAround.setWhatsThis(_hourWrapAroundText)

        self.minimize = QtWidgets.QCheckBox("Quit to Tray")
        self.minimize.setChecked(self.config["minimize"])
        _minimizeText = "Minimize to tray instead of closing"
        self.minimize.setToolTip(_minimizeText)
        self.minimize.setWhatsThis(_minimizeText)

        generalSettingsLayout.addWidget(self.autoCalcEndTime, 0, 0)
        generalSettingsLayout.addWidget(self.hourWrapAround, 1, 0)
        generalSettingsLayout.addWidget(self.minimize, 2, 0)

        generalSettingsWidgets.setLayout(generalSettingsLayout)

        JiraSettingsLayout = QtWidgets.QGridLayout()
        JiraSettingsWidgets = QtWidgets.QGroupBox("Jira Settings")

        self.jiraUrlLabel = QtWidgets.QLabel("Jira URL")
        self.jiraUrlLE = QtWidgets.QLineEdit(self.config["url"])
        self.uidLabel = QtWidgets.QLabel("User ID")
        self.uidLE = QtWidgets.QLineEdit(self.config["uid"])
        self.passwordLabel = QtWidgets.QLabel("Password")
        self.passwordLE = QtWidgets.QLineEdit(
            keyring.get_password("jiraconnection", self.config["uid"])
        )
        self.passwordLE.setEchoMode(QtWidgets.QLineEdit.Password)
        self.jiraVerifyButton = QtWidgets.QPushButton("Verify")
        self.jiraVerifyButton.clicked.connect(self.verifyJira)
        JiraSettingsLayout.addWidget(self.jiraUrlLabel, 0, 0)
        JiraSettingsLayout.addWidget(self.jiraUrlLE, 0, 1, 1, 2)
        JiraSettingsLayout.addWidget(self.uidLabel, 1, 0)
        JiraSettingsLayout.addWidget(self.uidLE, 1, 1, 1, 2)
        JiraSettingsLayout.addWidget(self.passwordLabel, 2, 0)
        JiraSettingsLayout.addWidget(self.passwordLE, 2, 1, 1, 2)
        JiraSettingsLayout.addWidget(self.jiraVerifyButton, 3, 2)

        JiraSettingsWidgets.setLayout(JiraSettingsLayout)

        workPackageLayout = QtWidgets.QGridLayout()
        workPackageLocationWidgets = QtWidgets.QGroupBox("WorkPackage Settings")
        self.workPackageLocationLabel = QtWidgets.QLabel("Workpackage Location:")
        self.workPackageLocationCombo = QtWidgets.QComboBox()
        self.workPackageLocationCombo.insertItems(0, ["left", "right", "popup"])
        self.workPackageLocationCombo.setCurrentIndex(self.config["wpLocation"])
        self.workPackageOnStartUpActive = QtWidgets.QCheckBox("Show Work Packages on Start")
        self.workPackageOnStartUpActive.setChecked(self.config["wpActive"])
        workPackageLayout.addWidget(self.workPackageLocationLabel, 0, 0)
        workPackageLayout.addWidget(self.workPackageLocationCombo, 0, 1)
        workPackageLayout.addWidget(self.workPackageOnStartUpActive, 1, 0, 1, 2)
        workPackageLocationWidgets.setLayout(workPackageLayout)

        buttonbox = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        buttonbox.accepted.connect(self.accept)
        buttonbox.rejected.connect(self.reject)

        mainLayout.addWidget(timeSettingsWidgets, 0, 0, 2, 1)
        mainLayout.addWidget(lunchSettingsWidgets, 0, 1)
        mainLayout.addWidget(generalSettingsWidgets, 1, 1)
        mainLayout.addWidget(workPackageLocationWidgets, 2, 0, 1, 2)
        mainLayout.addWidget(JiraSettingsWidgets, 3, 0, 1, 2)
        mainLayout.addWidget(buttonbox)
        self.setLayout(mainLayout)

    def accept(self):
        cfg = self.getConfig()
        cfg["hours"] = [timeToMinutes(QtCore.QTime(0, 0))] + [
            timeToMinutes(x.time()) for x in self.workingTimes
        ]
        cfg["lunchBreak"] = timeToMinutes(self.lunchTime.time())
        cfg["connectHoursAndMinutes"] = self.hourWrapAround.isChecked()
        cfg["forecastEndTimes"] = self.autoCalcEndTime.isChecked()
        cfg["minimize"] = self.minimize.isChecked()
        cfg["url"] = self.jiraUrlLE.text().rstrip("/")
        if cfg["uid"] != self.uidLE.text():
            if keyring.get_password("jiraconnection", cfg["uid"]):
                keyring.delete_password("jiraconnection", cfg["uid"])
        cfg["uid"] = self.uidLE.text()
        cfg["wpLocation"] = self.workPackageLocationCombo.currentIndex()
        cfg["wpActive"] = self.workPackageOnStartUpActive.isChecked()
        keyring.set_password("jiraconnection", cfg["uid"], self.passwordLE.text())
        self.saveConfig(cfg)
        super().accept()

    def verifyJira(self):
        if self.uidLE.text() and self.passwordLE.text():
            try:
                getJiraInstance(
                    self.jiraUrlLE.text().rstrip("/"),
                    self.uidLE.text(),
                    self.passwordLE.text(),
                )
                QtWidgets.QMessageBox.information(
                    self,
                    "Jira Connection OK",
                    "Connection to Jira established\n User and Password accepted",
                    QtWidgets.QMessageBox.Ok,
                )
            except Exception as e:
                QtWidgets.QMessageBox.warning(
                    self, "Jira Connection Error", str(e), QtWidgets.QMessageBox.Ok
                )

    @staticmethod
    def saveConfig(cfg):
        file = "settings.json"
        with open(file, "w") as fp:
            json.dump(cfg, fp, indent=4)

    @staticmethod
    def loadConfig():
        file = "settings.json"
        config = dict()
        try:
            with open(file, "r") as fp:
                config = json.load(fp)
            return config
        except Exception as e:
            print(f"Using default config - Couldn't load from file: {e}")
            return config

    def getConfig(self):
        config = self.loadConfig()
        t1 = 8 * 60 + 15
        t2 = 5 * 60 + 30
        t3 = 0
        cfg = {
            "hours": [
                minutesToTime(x)
                for x in config.get("hours", [t3, t1, t1, t1, t1, t2, t3, t3])
            ],
            "lunchBreak": config.get("lunchBreak", 30),
            "connectHoursAndMinutes": config.get("connectHoursAndMinutes", False),
            "forecastEndTimes": config.get("forecastEndTimes", True),
            "minimize": config.get("minimize", True),
            "url": config.get("url", "https://jira-ibs.zone2.agileci.conti.de"),
            "uid": config.get("uid", ""),
            "wpLocation": config.get("wpLocation", 2),
            "wpActive": config.get("wpActive", False)
        }
        AdvancedTimeEdit.connectHoursAndMinutes = cfg["connectHoursAndMinutes"]
        return cfg
