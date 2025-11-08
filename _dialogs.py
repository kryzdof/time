import calendar
import json
from itertools import zip_longest
from pathlib import Path

import keyring
from keyring.backends.Windows import WinVaultKeyring
from PySide6 import QtCore, QtGui, QtWidgets

from _utils import getJiraInstance, logging, minutesToTime, resource_path, timeToMinutes

keyring.set_keyring(WinVaultKeyring())


class AdvancedTimeEdit(QtWidgets.QTimeEdit):
    connectHoursAndMinutes = False

    def __init__(self, *args: list, **kwargs: dict) -> None:
        super().__init__(*args, **kwargs)
        self.setDisplayFormat("hh:mm")
        self.setWrapping(True)

    def stepBy(self, steps: int) -> None:
        if self.connectHoursAndMinutes:
            currentTime = self.time()
            super().stepBy(steps)
            if self.currentSection() == self.MinuteSection:
                if currentTime.minute() == 0 and steps < 0:
                    self.setTime(self.time().addSecs(-3600))
                if currentTime.minute() == 59 and steps > 0:  # noqa: PLR2004
                    self.setTime(self.time().addSecs(3600))
        else:
            super().stepBy(steps)


class VacationButton(QtWidgets.QPushButton):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.showContextMenu)
        self.setCheckable(True)
        self.setIcon(QtGui.QPixmap(resource_path("black-plane.png")))
        self.isZA = False

    def showContextMenu(self, pos: QtCore.QPoint) -> None:
        contextMenu = QtWidgets.QMenu(self)
        takeZA = contextMenu.addAction("Take ZA")
        takeZA.setCheckable(True)
        takeZA.setChecked(self.isZA)

        action = contextMenu.exec_(self.mapToGlobal(pos))
        if action == takeZA:
            self.isZA = not self.isZA
            self.setChecked(self.isZA)
            self.clicked.emit()


class TimeTypeButton(QtWidgets.QPushButton):
    stateNames = ("Home Office", "Office", "Doctor Appointment", "Sick Leave")
    stateIcons = ("house.png", "office.png", "doctor.png", "poison.png")

    def __init__(self, stateType: int = 0, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.showContextMenu)
        self.state = stateType
        self.setIcon(QtGui.QPixmap(resource_path(self.stateIcons[self.state])))
        self.clicked.connect(self.nextState)

    def nextState(self) -> None:
        self.state = (self.state + 1) % len(self.stateIcons)
        self.setIcon(QtGui.QPixmap(resource_path(self.stateIcons[self.state])))

    def setState(self, state: int) -> None:
        self.state = state
        self.setIcon(QtGui.QPixmap(resource_path(self.stateIcons[self.state])))

    def showContextMenu(self, pos: QtCore.QPoint) -> None:
        contextMenu = QtWidgets.QMenu(self)
        actions = []
        for index, state in enumerate(self.stateNames):
            actions.append(contextMenu.addAction(QtGui.QPixmap(resource_path(self.stateIcons[index])), state))

        action = contextMenu.exec_(self.mapToGlobal(pos))
        for act in actions:
            if action == act:
                self.state = actions.index(act)
                self.setIcon(QtGui.QPixmap(resource_path(self.stateIcons[self.state])))


class AdvancedSpinBox(QtWidgets.QSpinBox):
    wrapped = QtCore.Signal(int)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWrapping(True)

    def stepBy(self, step: int) -> None:
        if self.value() == self.minimum() and step < 0:
            self.wrapped.emit(-1)
        if self.value() == self.maximum() and step > 0:
            self.wrapped.emit(1)
        super().stepBy(step)


class DetailTimesDialog(QtWidgets.QDialog):
    def __init__(self, parent: QtWidgets.QWidget | None, title: str, data: list[tuple[int, int, int]]) -> None:
        super().__init__(parent=parent)

        self.timeStampData = data
        self.totalDiff = 0

        self.setWindowTitle(title)

        mainLayout = QtWidgets.QGridLayout()

        self.startTimes = []
        self.endTimes = []
        self.timeDuration = []
        self.timeTypes = []

        label = QtWidgets.QLabel("Start Times")
        label.setAlignment(QtCore.Qt.AlignHCenter)
        mainLayout.addWidget(label, 0, 0, 1, 2)
        label = QtWidgets.QLabel("End Times")
        label.setAlignment(QtCore.Qt.AlignHCenter)
        mainLayout.addWidget(label, 0, 2, 1, 2)
        label = QtWidgets.QLabel("Diff Times")
        label.setAlignment(QtCore.Qt.AlignHCenter)
        mainLayout.addWidget(label, 0, 4)
        label = QtWidgets.QLabel("Time Type")
        label.setAlignment(QtCore.Qt.AlignHCenter)
        mainLayout.addWidget(label, 0, 5)

        self.createTimeEditLines(mainLayout)

        label = QtWidgets.QLabel("Total time:")
        mainLayout.addWidget(label, 11, 1)

        self.totalTime = QtWidgets.QLabel("")
        mainLayout.addWidget(self.totalTime, 11, 2)

        buttonbox = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok
            | QtWidgets.QDialogButtonBox.Cancel
            | QtWidgets.QDialogButtonBox.Reset
            | QtWidgets.QDialogButtonBox.Discard,
        )
        buttonbox.accepted.connect(self.accept)
        buttonbox.rejected.connect(self.reject)
        buttonbox.button(QtWidgets.QDialogButtonBox.Reset).clicked.connect(self.resetTimes)
        buttonbox.button(QtWidgets.QDialogButtonBox.Discard).clicked.connect(self.discardTimes)

        mainLayout.addWidget(buttonbox, 20, 0, 1, 5)
        self.setLayout(mainLayout)
        self.updateDiffs()

    def createTimeEditLines(self, layout: QtWidgets.QGridLayout) -> None:
        """Create the time edit lines."""
        for x, timestamps in zip_longest(range(10), self.timeStampData, fillvalue=(0, 0, 0)):
            if len(timestamps) == 2:  # noqa: PLR2004
                start, end, timeType = *timestamps, 0
            else:
                start, end, timeType = timestamps

            autoTime = QtWidgets.QPushButton(QtGui.QPixmap(resource_path("time.png")), "")
            autoTime.clicked.connect(self.updateAutoTime)
            layout.addWidget(autoTime, x + 1, 0)
            t = QtCore.QTime(minutesToTime(start))
            startTimes = AdvancedTimeEdit(t)
            startTimes.timeChanged.connect(self.updateDiffs)
            self.startTimes.append(startTimes)
            layout.addWidget(startTimes, x + 1, 1)
            autoTime.QTimeReference = startTimes

            t = QtCore.QTime(minutesToTime(end))
            endTimes = AdvancedTimeEdit(t)
            endTimes.timeChanged.connect(self.updateDiffs)
            self.endTimes.append(endTimes)
            layout.addWidget(endTimes, x + 1, 2)
            autoTime = QtWidgets.QPushButton(QtGui.QPixmap(resource_path("time.png")), "")
            autoTime.QTimeReference = endTimes
            autoTime.clicked.connect(self.updateAutoTime)
            layout.addWidget(autoTime, x + 1, 3)

            label = QtWidgets.QLabel("")
            self.timeDuration.append(label)
            layout.addWidget(label, x + 1, 4)

            timeTypes = TimeTypeButton(timeType)
            self.timeTypes.append(timeTypes)
            layout.addWidget(timeTypes, x + 1, 5)

    def updateAutoTime(self) -> None:
        timeEdit = self.sender().QTimeReference
        h = QtCore.QTime.currentTime().hour()
        m = QtCore.QTime.currentTime().minute()
        timeEdit.setTime(QtCore.QTime(h, m))

    def updateDiffs(self) -> None:
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

        self.totalTime.setText(QtCore.QTime(0, 0).addSecs(self.totalDiff).toString("h:mm"))

    def resetTimes(self) -> None:
        for x, timestamps in zip_longest(range(10), self.timeStampData, fillvalue=(0, 0, 0)):
            if len(timestamps) == 2:  # noqa: PLR2004
                start, end, timeType = *timestamps, 0
            else:
                start, end, timeType = timestamps
            self.startTimes[x].setTime(QtCore.QTime(minutesToTime(start)))
            self.endTimes[x].setTime(QtCore.QTime(minutesToTime(end)))
            self.timeTypes[x].setState(timeType)
        self.updateDiffs()

    def discardTimes(self) -> None:
        for x in range(10):
            t = QtCore.QTime(minutesToTime(0))
            self.startTimes[x].setTime(t)
            t = QtCore.QTime(minutesToTime(0))
            self.endTimes[x].setTime(t)
            self.timeTypes[x].setState(0)
        self.updateDiffs()

    def accept(self) -> None:
        super().accept()

    def getDetails(self) -> tuple[int, int, list[tuple[int, int, int]]]:
        if self.totalDiff:
            totalStart = QtCore.QTime(7, 0)
            totalEnd = totalStart.addSecs(self.totalDiff)
        else:
            totalStart = QtCore.QTime(0, 0)
            totalEnd = QtCore.QTime(0, 0)
        timeStamps = [
            (
                timeToMinutes(self.startTimes[x].time()),
                timeToMinutes(self.endTimes[x].time()),
                self.timeTypes[x].state,
            )
            for x in range(10)
        ]
        return timeToMinutes(totalStart), timeToMinutes(totalEnd), timeStamps


class SettingsDialog(QtWidgets.QDialog):
    def __init__(self, parent: QtWidgets.QWidget | None) -> None:
        super().__init__(parent=parent)

        self.config = self.getConfig()
        self.setWindowTitle("Settings")
        mainLayout = QtWidgets.QGridLayout()

        timeSettingsWidget, self.workingTimes = self.createTimeSettingsWidget()

        lunchSettingsWidget, self.lunchTime = self.createLunchSettingsWidget()

        generalSettingsWidget, self.autoCalcEndTime, self.hourWrapAround, self.minimize = self.createGeneralSettingsWidget()

        homeOfficeSettingsWidget, self.officePercentage, self.dailyOfficePercentageCheckBox, self.dailyOfficePercentage = (
            self.createHomeOfficeSettingsWidget()
        )

        workPackageWidget, self.workPackageLocationCombo, self.workPackageOnStartUpActive = (
            self.createWorkPackageSettingsWidget()
        )

        JiraSettingsWidget, self.jiraUrlLE, self.uidLE, self.passwordLE = self.createJiraSettingsWidget()

        buttonbox = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        buttonbox.accepted.connect(self.accept)
        buttonbox.rejected.connect(self.reject)

        mainLayout.addWidget(timeSettingsWidget, 0, 0, 2, 1)
        mainLayout.addWidget(lunchSettingsWidget, 0, 1)
        mainLayout.addWidget(generalSettingsWidget, 1, 1)
        mainLayout.addWidget(homeOfficeSettingsWidget, 2, 0, 1, 2)
        mainLayout.addWidget(workPackageWidget, 3, 0, 1, 2)
        mainLayout.addWidget(JiraSettingsWidget, 4, 0, 1, 2)
        mainLayout.addWidget(buttonbox)
        self.setLayout(mainLayout)

    def createTimeSettingsWidget(self) -> (QtWidgets.QGroupBox, list[AdvancedTimeEdit]):
        """Create the time settings widget."""
        timeSettingsLayout = QtWidgets.QGridLayout()
        timeSettingsWidget = QtWidgets.QGroupBox("Time Settings")
        timeSettingsWidgetsText = "Guess what! That are the daily working hours you think you should be working :)"
        timeSettingsWidget.setToolTip(timeSettingsWidgetsText)
        timeSettingsWidget.setWhatsThis(timeSettingsWidgetsText)
        for x, dayStr in enumerate(calendar.day_name):
            label = QtWidgets.QLabel(dayStr)
            timeSettingsLayout.addWidget(label, x + 1, 0)
        workingTimes = []
        for x in range(1, 8):
            t = self.config["hours"][x]
            workingTime = AdvancedTimeEdit(t)
            workingTimes.append(workingTime)
            timeSettingsLayout.addWidget(workingTime, x, 1)
        timeSettingsWidget.setLayout(timeSettingsLayout)
        return timeSettingsWidget, workingTimes

    def createLunchSettingsWidget(self) -> (QtWidgets.QGroupBox, AdvancedTimeEdit):
        """Create the lunch settings widget."""
        lunchSettingsLayout = QtWidgets.QGridLayout()
        lunchSettingsWidgets = QtWidgets.QGroupBox("Lunch Settings")
        lunchSettingsWidgetsText = "This time will be reduced from your working hours if the lunch break checkbox is set"
        lunchSettingsWidgets.setToolTip(lunchSettingsWidgetsText)
        lunchSettingsWidgets.setWhatsThis(lunchSettingsWidgetsText)
        label = QtWidgets.QLabel("Normal Lunch Break")
        lunchSettingsLayout.addWidget(label, 0, 0)
        lunchTime = AdvancedTimeEdit(QtCore.QTime(0, 0).addSecs(self.config["lunchBreak"] * 60))
        lunchSettingsLayout.addWidget(lunchTime, 0, 1)
        lunchSettingsWidgets.setLayout(lunchSettingsLayout)
        return lunchSettingsWidgets, lunchTime

    def createGeneralSettingsWidget(
        self,
    ) -> (QtWidgets.QGroupBox, QtWidgets.QCheckBox, QtWidgets.QCheckBox, QtWidgets.QCheckBox):
        """Create the general settings widget."""
        generalSettingsLayout = QtWidgets.QGridLayout()
        generalSettingsWidget = QtWidgets.QGroupBox("General Settings")
        autoCalcEndTime = QtWidgets.QCheckBox("Forecast end time")
        autoCalcEndTime.setChecked(self.config["forecastEndTimes"])
        autoCalcEndTimeText = (
            "This will automatically calculate the end time of the day according to the supposed working hours for this day"
        )
        autoCalcEndTime.setToolTip(autoCalcEndTimeText)
        autoCalcEndTime.setWhatsThis(autoCalcEndTimeText)

        hourWrapAround = QtWidgets.QCheckBox("Wrap hours")
        hourWrapAround.setChecked(self.config["connectHoursAndMinutes"])
        hourWrapAroundText = "If minutes wrap around, the hour will also be changed"
        hourWrapAround.setToolTip(hourWrapAroundText)
        hourWrapAround.setWhatsThis(hourWrapAroundText)

        minimize = QtWidgets.QCheckBox("Quit to Tray")
        minimize.setChecked(self.config["minimize"])
        minimizeText = "Minimize to tray instead of closing"
        minimize.setToolTip(minimizeText)
        minimize.setWhatsThis(minimizeText)

        generalSettingsLayout.addWidget(autoCalcEndTime, 0, 0)
        generalSettingsLayout.addWidget(hourWrapAround, 1, 0)
        generalSettingsLayout.addWidget(minimize, 2, 0)

        generalSettingsWidget.setLayout(generalSettingsLayout)
        return generalSettingsWidget, autoCalcEndTime, hourWrapAround, minimize

    def createHomeOfficeSettingsWidget(
        self,
    ) -> (QtWidgets.QGroupBox, QtWidgets.QSpinBox, QtWidgets.QCheckBox, QtWidgets.QSpinBox):
        """Create the home office settings widget."""
        homeOfficeSettingsLayout = QtWidgets.QGridLayout()
        homeOfficeSettingsWidget = QtWidgets.QGroupBox("Home Office Settings")

        officePercentage = QtWidgets.QSpinBox(self)
        officePercentage.setRange(0, 100)
        officePercentage.setValue(self.config["officePercentage"])
        officePercentageText = "The office percentage will turn red if below this value"
        officePercentage.setToolTip(officePercentageText)
        officePercentage.setWhatsThis(officePercentageText)
        monthlyLabel = QtWidgets.QLabel("Monthly office % threshold")
        monthlyLabel.setToolTip(officePercentageText)
        monthlyLabel.setWhatsThis(officePercentageText)

        dailyOfficePercentageCheckBox = QtWidgets.QCheckBox("Daily office % threshold")
        dailyOfficePercentageCheckBox.setChecked(self.config["dailyOfficePercentageAutoCalc"])
        dailyOfficePercentageCheckBox.toggled.connect(self.dailyOfficePercentageSetDisabled)
        dailyOfficePercentageText = (
            "Office percentage on a daily basis.\n"
            "If enabled the daily time details are triggering an update on save.\n"
            "If the percentage of office time on that day is higher then the theshold, "
            "it is considered an office day.\n"
            "Any non-home-office time is considered office."
        )
        dailyOfficePercentageCheckBox.setWhatsThis(dailyOfficePercentageText)
        dailyOfficePercentageCheckBox.setWhatsThis(dailyOfficePercentageText)
        dailyOfficePercentage = QtWidgets.QSpinBox(self)
        dailyOfficePercentage.setRange(0, 100)
        dailyOfficePercentage.setValue(self.config["dailyOfficePercentage"])
        dailyOfficePercentage.setDisabled(not self.config["dailyOfficePercentageAutoCalc"])
        dailyOfficePercentage.setToolTip(dailyOfficePercentageText)
        dailyOfficePercentage.setWhatsThis(dailyOfficePercentageText)

        homeOfficeSettingsLayout.addWidget(monthlyLabel, 0, 0)
        homeOfficeSettingsLayout.addWidget(officePercentage, 0, 1)
        homeOfficeSettingsLayout.addWidget(dailyOfficePercentageCheckBox, 1, 0)
        homeOfficeSettingsLayout.addWidget(dailyOfficePercentage, 1, 1)

        homeOfficeSettingsWidget.setLayout(homeOfficeSettingsLayout)
        return homeOfficeSettingsWidget, officePercentage, dailyOfficePercentageCheckBox, dailyOfficePercentage

    def createWorkPackageSettingsWidget(self) -> (QtWidgets.QGroupBox, QtWidgets.QComboBox, QtWidgets.QCheckBox):
        """Create the work package settings widget."""
        workPackageLayout = QtWidgets.QGridLayout()
        workPackageSettingsWidget = QtWidgets.QGroupBox("WorkPackage Settings")
        workPackageLocationLabel = QtWidgets.QLabel("Workpackage Location:")
        workPackageLocationCombo = QtWidgets.QComboBox()
        workPackageLocationCombo.insertItems(0, ["left", "right", "popup"])
        workPackageLocationCombo.setCurrentIndex(self.config["wpLocation"])
        workPackageOnStartUpActive = QtWidgets.QCheckBox("Show Work Packages on Start")
        workPackageOnStartUpActive.setChecked(self.config["wpActive"])

        workPackageLayout.addWidget(workPackageLocationLabel, 0, 0)
        workPackageLayout.addWidget(workPackageLocationCombo, 0, 1)
        workPackageLayout.addWidget(workPackageOnStartUpActive, 1, 0, 1, 2)
        workPackageSettingsWidget.setLayout(workPackageLayout)

        return workPackageSettingsWidget, workPackageLocationCombo, workPackageOnStartUpActive

    def createJiraSettingsWidget(self) -> (QtWidgets.QGroupBox, QtWidgets.QLineEdit, QtWidgets.QLineEdit, QtWidgets.QLineEdit):
        JiraSettingsLayout = QtWidgets.QGridLayout()
        JiraSettingsWidget = QtWidgets.QGroupBox("Jira Settings")

        jiraUrlLabel = QtWidgets.QLabel("Jira URL")
        jiraUrlLE = QtWidgets.QLineEdit(self.config["url"])
        uidLabel = QtWidgets.QLabel("User ID")
        uidLE = QtWidgets.QLineEdit(self.config["uid"])
        passwordLabel = QtWidgets.QLabel("Password")
        passwordLE = QtWidgets.QLineEdit(keyring.get_password("jiraconnection", self.config["uid"]))
        passwordLE.setEchoMode(QtWidgets.QLineEdit.Password)
        jiraVerifyButton = QtWidgets.QPushButton("Verify")
        jiraVerifyButton.clicked.connect(self.verifyJira)
        JiraSettingsLayout.addWidget(jiraUrlLabel, 0, 0)
        JiraSettingsLayout.addWidget(jiraUrlLE, 0, 1, 1, 2)
        JiraSettingsLayout.addWidget(uidLabel, 1, 0)
        JiraSettingsLayout.addWidget(uidLE, 1, 1, 1, 2)
        JiraSettingsLayout.addWidget(passwordLabel, 2, 0)
        JiraSettingsLayout.addWidget(passwordLE, 2, 1, 1, 2)
        JiraSettingsLayout.addWidget(jiraVerifyButton, 3, 2)

        JiraSettingsWidget.setLayout(JiraSettingsLayout)
        return JiraSettingsWidget, jiraUrlLE, uidLE, passwordLE

    def dailyOfficePercentageSetDisabled(self, checked: bool) -> None:
        self.dailyOfficePercentage.setDisabled(not checked)

    def accept(self) -> None:
        cfg = self.getConfig()
        cfg["hours"] = [timeToMinutes(QtCore.QTime(0, 0))] + [timeToMinutes(x.time()) for x in self.workingTimes]
        cfg["lunchBreak"] = timeToMinutes(self.lunchTime.time())
        cfg["connectHoursAndMinutes"] = self.hourWrapAround.isChecked()
        cfg["forecastEndTimes"] = self.autoCalcEndTime.isChecked()
        cfg["minimize"] = self.minimize.isChecked()
        cfg["officePercentage"] = self.officePercentage.value()
        cfg["dailyOfficePercentageAutoCalc"] = self.dailyOfficePercentageCheckBox.isChecked()
        cfg["dailyOfficePercentage"] = self.dailyOfficePercentage.value()
        cfg["url"] = self.jiraUrlLE.text().rstrip("/")
        if cfg["uid"] != self.uidLE.text() and keyring.get_password("jiraconnection", cfg["uid"]):
            keyring.delete_password("jiraconnection", cfg["uid"])
        cfg["uid"] = self.uidLE.text()
        cfg["wpLocation"] = self.workPackageLocationCombo.currentIndex()
        cfg["wpActive"] = self.workPackageOnStartUpActive.isChecked()
        keyring.set_password("jiraconnection", cfg["uid"], self.passwordLE.text())
        self.saveConfig(cfg)
        super().accept()

    def verifyJira(self) -> None:
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
            except Exception as e:  # noqa: BLE001 - this should be okay for ruff because it is logged as exception with traceback
                logging.exception("Error when verifying Jira connection")
                QtWidgets.QMessageBox.warning(self, "Jira Connection Error", str(e), QtWidgets.QMessageBox.Ok)

        else:
            QtWidgets.QMessageBox.warning(
                self,
                "No Credentials",
                "Please provide User ID and Password",
                QtWidgets.QMessageBox.Ok,
            )

    @staticmethod
    def saveConfig(cfg: dict) -> None:
        settings = Path("settings.json")
        with settings.open("w") as fp:
            json.dump(cfg, fp, indent=4)

    @staticmethod
    def loadConfig() -> dict:
        settings = Path("settings.json")
        config = {}
        try:
            with settings.open() as fp:
                config = json.load(fp)
        except Exception:  # noqa: BLE001 - this should be okay for ruff because it is logged as exception with traceback
            logging.exception("Using default config - Couldn't load from file")
        return config

    def getConfig(self) -> dict:
        config = self.loadConfig()
        t1 = 8 * 60 + 15
        t2 = 5 * 60 + 30
        t3 = 0
        cfg = {
            "hours": [minutesToTime(x) for x in config.get("hours", [t3, t1, t1, t1, t1, t2, t3, t3])],
            "lunchBreak": config.get("lunchBreak", 30),
            "connectHoursAndMinutes": config.get("connectHoursAndMinutes", False),
            "forecastEndTimes": config.get("forecastEndTimes", True),
            "minimize": config.get("minimize", True),
            "officePercentage": config.get("officePercentage", 40),
            "dailyOfficePercentageAutoCalc": config.get("dailyOfficePercentageAutoCalc", True),
            "dailyOfficePercentage": config.get("dailyOfficePercentage", 0),
            "url": config.get("url", "https://jira-ibs.zone2.agileci.conti.de"),
            "uid": config.get("uid", ""),
            "wpLocation": config.get("wpLocation", 2),
            "wpActive": config.get("wpActive", False),
        }
        AdvancedTimeEdit.connectHoursAndMinutes = cfg["connectHoursAndMinutes"]
        return cfg
