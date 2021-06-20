import sys
import json
import os
import shutil
import calendar
import time
import keyring
from keyring.backends.Windows import WinVaultKeyring

from itertools import zip_longest

from jira import JIRA, JIRAError
from requests.exceptions import ConnectTimeout

from PySide2 import QtCore, QtWidgets, QtGui


# done: when creating a new workpackage check unique names
# done: align width of WorkPackageWidget's children to fit together
# done: downsize if a workpackage is deleted
# done: use icons instead of text
# done: ask before deleting a workpackage!
# done: make work packages editable
# done: add settings for Jira connection (URL, uid, pw)
# done: how to save pw securely? --> keyring
# done: implement Jira hour logging
# done: add create button to WorkPackageView?

keyring.set_keyring(WinVaultKeyring())

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS,
        # and places our data files in a folder relative to that temp
        # folder named as specified in the datas tuple in the spec file
        base_path = os.path.join(sys._MEIPASS, 'pics')
    except Exception:
        # sys._MEIPASS is not defined, so use the original path
        base_path = os.path.join(os.path.curdir, "pics")

    return os.path.join(base_path, relative_path)


def getJiraInstance(uid, password=None):
    if password is None:
        password = keyring.get_password("jiraconnection", uid)
    try:
        jira = JIRA(WorkPackageWidget.urlStart, basic_auth=(uid, password),
                    options={"agile_rest_path": "agile"}, max_retries=0, timeout=5)
    except JIRAError as e:
        print(e)
        if e.status_code == 401:
            raise ConnectionError("Username or Password is wrong")
        raise
    except ConnectTimeout:
        raise ConnectionError(f"Could not connect to {WorkPackageWidget.urlStart}")
    return jira


def JiraWriteLog(uid, ticket, duration):
    try:
        jira = getJiraInstance(uid)
    except Exception as e:
        ret = QtWidgets.QMessageBox.critical(None, "Jira Connection Error", str(e),
                                             QtWidgets.QMessageBox.Ok)
        return False
    try:
        jira.add_worklog(ticket, timeSpentSeconds=duration)
    except JIRAError as e:
        if e.status_code == 404:
            ret = QtWidgets.QMessageBox.critical(None, "Work Log Creation Error",
                                                 f"Issue {ticket} not found",
                                                 QtWidgets.QMessageBox.Ok)
        else:
            ret = QtWidgets.QMessageBox.critical(None, "Work Log Creation Error",
                                                 f"Error: '{e.text}'\nStatus Code: {e.status_code}",
                                                 QtWidgets.QMessageBox.Ok)
        return False
    except Exception as e:
        ret = QtWidgets.QMessageBox.critical(None, "Work Log Creation Error", str(e),
                                             QtWidgets.QMessageBox.Ok)
        return False
    return True


def timeToMinutes(qTime):
    return qTime.hour() * 60 + qTime.minute()


def minutesToTime(minutes):
    return QtCore.QTime(minutes // 60, minutes % 60)


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

        for x, timestamps in zip_longest(range(10), self.timeStampData, fillvalue=(0, 0)):
            t = QtCore.QTime(minutesToTime(timestamps[0]))
            startTimes = AdvancedTimeEdit(t)
            startTimes.editingFinished.connect(self.updateDiffs)
            self.startTimes.append(startTimes)
            mainLayout.addWidget(startTimes, x + 1, 1)
            autoTime = QtWidgets.QPushButton(QtGui.QPixmap(resource_path("time.png")), "")
            autoTime.QTimeReference = startTimes
            autoTime.clicked.connect(self.updateAutoTime)
            mainLayout.addWidget(autoTime, x + 1, 0)

            t = QtCore.QTime(minutesToTime(timestamps[1]))
            endTimes = AdvancedTimeEdit(t)
            endTimes.editingFinished.connect(self.updateDiffs)
            self.endTimes.append(endTimes)
            mainLayout.addWidget(endTimes, x + 1, 2)
            autoTime = QtWidgets.QPushButton(QtGui.QPixmap(resource_path("time.png")), "")
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

        buttonbox = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok |
                                               QtWidgets.QDialogButtonBox.Cancel |
                                               QtWidgets.QDialogButtonBox.Reset)
        buttonbox.accepted.connect(self.accept)
        buttonbox.rejected.connect(self.reject)
        buttonbox.button(QtWidgets.QDialogButtonBox.Reset).clicked.connect(self.resetTimes)

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
                self.timeDuration[x].setText(diffTime.toString('h:mm'))
                self.timeDuration[x].show()

        self.totalTime.setText(QtCore.QTime(0, 0).addSecs(self.totalDiff).toString('h:mm'))

    def resetTimes(self):
        for x, timestamps in zip_longest(range(10), self.timeStampData, fillvalue=(0, 0)):
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
            timeStamps.append((timeToMinutes(self.startTimes[x].time()), timeToMinutes(self.endTimes[x].time())))
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
        _lunchSettingsWidgetsText = "This time will be reduced from your working hours if the lunch break checkbox " \
                                    "is set"
        lunchSettingsWidgets.setToolTip(_lunchSettingsWidgetsText)
        lunchSettingsWidgets.setWhatsThis(_lunchSettingsWidgetsText)
        label = QtWidgets.QLabel("Normal Lunch Break")
        lunchSettingsLayout.addWidget(label, 0, 0)
        self.lunchTime = AdvancedTimeEdit(QtCore.QTime(0, 0).addSecs(self.config["lunchBreak"] * 60))
        lunchSettingsLayout.addWidget(self.lunchTime, 0, 1)
        lunchSettingsWidgets.setLayout(lunchSettingsLayout)

        generalSettingsLayout = QtWidgets.QGridLayout()
        generalSettingsWidgets = QtWidgets.QGroupBox("General Settings")
        self.autoCalcEndTime = QtWidgets.QCheckBox("Forecast end time")
        self.autoCalcEndTime.setChecked(self.config["forecastEndTimes"])
        _autoCalcEndTimeText = "This will automatically calculate the end time of the day according " \
                               "to the supposed working hours for this day"
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

        workPackageSettingsLayout = QtWidgets.QGridLayout()
        workPackageSettingsWidgets = QtWidgets.QGroupBox("Jira Settings")

        self.jiraUrlLabel = QtWidgets.QLabel("Jira URL")
        self.jiraUrlLE = QtWidgets.QLineEdit(self.config["url"])
        self.uidLabel = QtWidgets.QLabel("User ID")
        self.uidLE = QtWidgets.QLineEdit(self.config["uid"])
        self.passwordLabel = QtWidgets.QLabel("Password")
        self.passwordLE = QtWidgets.QLineEdit(keyring.get_password("jiraconnection", self.config["uid"]))
        self.passwordLE.setEchoMode(QtWidgets.QLineEdit.Password)
        workPackageSettingsLayout.addWidget(self.jiraUrlLabel, 0, 0)
        workPackageSettingsLayout.addWidget(self.jiraUrlLE, 0, 1)
        workPackageSettingsLayout.addWidget(self.uidLabel, 1, 0)
        workPackageSettingsLayout.addWidget(self.uidLE, 1, 1)
        workPackageSettingsLayout.addWidget(self.passwordLabel, 2, 0)
        workPackageSettingsLayout.addWidget(self.passwordLE, 2, 1)

        workPackageSettingsWidgets.setLayout(workPackageSettingsLayout)

        buttonbox = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        buttonbox.accepted.connect(self.accept)
        buttonbox.rejected.connect(self.reject)

        mainLayout.addWidget(timeSettingsWidgets, 0, 0, 2, 1)
        mainLayout.addWidget(lunchSettingsWidgets, 0, 1)
        mainLayout.addWidget(generalSettingsWidgets, 1, 1)
        mainLayout.addWidget(workPackageSettingsWidgets, 2, 0, 1, 2)
        mainLayout.addWidget(buttonbox)
        self.setLayout(mainLayout)

    def accept(self):
        cfg = self.getConfig()
        cfg["hours"] = [timeToMinutes(QtCore.QTime(0, 0))] + [timeToMinutes(x.time()) for x in self.workingTimes]
        cfg["lunchBreak"] = timeToMinutes(self.lunchTime.time())
        cfg["connectHoursAndMinutes"] = self.hourWrapAround.isChecked()
        cfg["forecastEndTimes"] = self.autoCalcEndTime.isChecked()
        cfg["minimize"] = self.minimize.isChecked()
        cfg["url"] = self.jiraUrlLE.text().rstrip("/")
        if keyring.get_password("jiraconnection", cfg["uid"]):
            password = keyring.get_password("jiraconnection", cfg["uid"])
        else:
            password = ""
        if self.uidLE.text() and self.passwordLE.text():
            if cfg["uid"] != self.uidLE.text() or password != self.passwordLE.text():
                try:
                    getJiraInstance(self.uidLE.text(), self.passwordLE.text())
                except Exception as e:
                    ret = QtWidgets.QMessageBox.warning(self, "Jira Connection Error", str(e),
                                                        QtWidgets.QMessageBox.Abort | QtWidgets.QMessageBox.Ignore)
                    if ret == QtWidgets.QMessageBox.Abort:
                        return
        if cfg["uid"] != self.uidLE.text():
            if keyring.get_password("jiraconnection", cfg["uid"]):
                keyring.delete_password("jiraconnection", cfg["uid"])
        cfg["uid"] = self.uidLE.text()
        keyring.set_password("jiraconnection", cfg["uid"], self.passwordLE.text())
        self.saveConfig(cfg)
        super().accept()

    @staticmethod
    def saveConfig(cfg):
        file = f"settings.json"
        with open(file, "w") as fp:
            json.dump(cfg, fp)

    @staticmethod
    def loadConfig():
        file = f"settings.json"
        config = dict()
        try:
            with open(file, "r") as fp:
                config = json.load(fp)
            return config
        except:
            return config

    def getConfig(self):
        config = self.loadConfig()
        t1 = 8 * 60 + 15
        t2 = 5 * 60 + 30
        t3 = 0
        cfg = {"hours": [minutesToTime(x) for x in config.get("hours", [t3, t1, t1, t1, t1, t2, t3, t3])],
               "lunchBreak": config.get("lunchBreak", 30),
               "connectHoursAndMinutes": config.get("connectHoursAndMinutes", False),
               "forecastEndTimes": config.get("forecastEndTimes", True),
               "minimize": config.get("minimize", True),
               "url": config.get("url", WorkPackageWidget.urlStart),
               "uid": config.get("uid", "")}
        AdvancedTimeEdit.connectHoursAndMinutes = cfg["connectHoursAndMinutes"]
        WorkPackageWidget.urlStart = cfg["url"]
        return cfg


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, parent=None, app=None):
        super(MainWindow, self).__init__(parent)

        self.setObjectName("UltraTime")
        self.setWindowTitle("UltraTime")
        self.setMinimumWidth(500)

        topLine = QtWidgets.QGroupBox()
        topLineLayout = QtWidgets.QGridLayout()

        self.datetime = QtWidgets.QDateTimeEdit(QtCore.QDate.currentDate())
        self.datetime.setDisplayFormat("MMMM yyyy")
        self.datetime.dateChanged.connect(self.onMonthChanged)
        topLineLayout.addWidget(self.datetime, 0, 0, 1, 3)
        self.oldDateTime = self.datetime.date()

        self.hoursZA = QtWidgets.QLabel("ZA")
        self.hoursTotal = QtWidgets.QLabel("Total")

        settingsButton = QtWidgets.QPushButton("Settings")
        settingsButton.clicked.connect(self.onSettingsClicked)
        topLineLayout.addWidget(self.hoursZA, 0, 6)
        topLineLayout.addWidget(self.hoursTotal, 0, 8)

        topLineLayout.addWidget(settingsButton, 0, 9)

        workpackagesButton = QtWidgets.QPushButton("WP")
        workpackagesButton.clicked.connect(self.openWorkPackageView)
        topLineLayout.addWidget(workpackagesButton, 0, 10)

        topLine.setLayout(topLineLayout)
        topLine.setFixedHeight(40)

        mainWidget = QtWidgets.QGroupBox()
        mainWidgetLayout = QtWidgets.QGridLayout()
        self.dateButtons = []
        self.plannedTimeLabels = []
        self.starttimeTime = []
        self.endtimeTime = []
        self.autoTimes = []
        self.diffTimeLabels = []
        self.vacationCheckBoxes = []
        self.fullTimeLabels = []
        self.breakCheckBoxes = []
        for days in range(31):
            dateButton = QtWidgets.QPushButton(str(days))
            dateButton.clicked.connect(self.openDetailTimesDialog)
            self.dateButtons.append(dateButton)
            mainWidgetLayout.addWidget(dateButton, days, 0)

            label = QtWidgets.QLabel(str(days))
            self.plannedTimeLabels.append(label)
            mainWidgetLayout.addWidget(label, days, 1)

            starttime = AdvancedTimeEdit()
            starttime.editingFinished.connect(self.updateDateLabels)
            self.starttimeTime.append(starttime)
            mainWidgetLayout.addWidget(starttime, days, 2)

            endtime = AdvancedTimeEdit()
            endtime.editingFinished.connect(self.updateDateLabels)
            self.endtimeTime.append(endtime)
            mainWidgetLayout.addWidget(endtime, days, 4)

            autoTime = QtWidgets.QPushButton(QtGui.QPixmap(resource_path("time.png")), "")
            autoTime.setObjectName(str(days))
            autoTime.setToolTip("If start time is 00:00, it will set it to the current time\n"
                                "If start time is something different, it will set the end time to the current time")
            autoTime.clicked.connect(self.autoUpdateTime)
            self.autoTimes.append(autoTime)
            mainWidgetLayout.addWidget(autoTime, days, 5)

            label = QtWidgets.QLabel("")
            self.diffTimeLabels.append(label)
            mainWidgetLayout.addWidget(label, days, 6)

            checkbox = QtWidgets.QPushButton()
            checkbox.clicked.connect(self.updateDateLabels)
            checkbox.setCheckable(True)
            checkbox.setIcon(QtGui.QPixmap(resource_path("black-plane.png")))
            self.vacationCheckBoxes.append(checkbox)
            mainWidgetLayout.addWidget(checkbox, days, 7)

            label = QtWidgets.QLabel("")
            self.fullTimeLabels.append(label)
            mainWidgetLayout.addWidget(label, days, 8)

            breakCheckBox = QtWidgets.QCheckBox("Lunch Break")
            self.breakCheckBoxes.append(breakCheckBox)
            breakCheckBox.clicked.connect(self.updateDateLabels)
            mainWidgetLayout.addWidget(breakCheckBox, days, 9)

        mainWidget.setLayout(mainWidgetLayout)

        scrollArea = QtWidgets.QScrollArea()
        scrollArea.setWidget(mainWidget)
        scrollArea.setWidgetResizable(True)
        scrollArea.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scrollArea.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        scrollArea.setSizeAdjustPolicy(scrollArea.AdjustToContents)
        scrollArea.ensureWidgetVisible(self.dateButtons[self.datetime.date().day() - 1], 200, 200)

        for x in range(30):
            mainWidget.setTabOrder(self.autoTimes[x], self.autoTimes[x + 1])
        mainWidget.setTabOrder(self.autoTimes[-1], self.starttimeTime[0])
        for x in range(30):
            mainWidget.setTabOrder(self.starttimeTime[x], self.endtimeTime[x])
            mainWidget.setTabOrder(self.endtimeTime[x], self.starttimeTime[x + 1])
        mainWidget.setTabOrder(self.starttimeTime[-1], self.endtimeTime[-1])
        mainWidget.setTabOrder(self.endtimeTime[-1], self.vacationCheckBoxes[0])
        for x in range(30):
            mainWidget.setTabOrder(self.vacationCheckBoxes[x], self.vacationCheckBoxes[x + 1])

        splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        splitter.addWidget(topLine)
        splitter.addWidget(scrollArea)
        splitter.setChildrenCollapsible(False)
        splitter.handle(1).setCursor(QtCore.Qt.ArrowCursor)

        self.settings = SettingsDialog(self)
        self.setCentralWidget(splitter)
        self.loadMonth()
        self.config = self.settings.getConfig()
        self.workPackages = self.loadWorkPackages()
        self.workPackageView = WorkPackageView(self)

        self.app = app
        if self.app:
            self.app.setQuitOnLastWindowClosed(not self.config["minimize"])
            self.menu = None
            self.actions = None
            self.trayIcon = None
            self.createTray()

        self.scroll = scrollArea
        self.updateDateLabels()
        self.resize(QtCore.QSize(mainWidget.sizeHint().width(), self.size().height() + 50))

        self.cyclicCounter = 0
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.cyclicFunction)
        self.timer.start(1000)

    def cyclicFunction(self):
        self.cyclicCounter = self.cyclicCounter % 60 + 1
        self.colorDates()
        self.workPackageView.updateChildrenData()
        for wp in self.workPackages:
            if wp.isChecked():
                wp.setText(str(wp))
                if self.cyclicCounter // 60:
                    self.saveWorkPackages()

    def stopAllTracking(self, checked=None):
        if checked:
            for wp in self.workPackages:
                if wp.isChecked() and wp != self.sender():
                    wp.trigger()

    def createTray(self):
        self.trayIcon = QtWidgets.QSystemTrayIcon(QtGui.QIcon(resource_path("time.png")), self.app)
        self.trayIcon.show()
        self.trayIcon.activated.connect(self.trayActivated)
        self.createTrayMenu()

    def createTrayMenu(self):
        self.menu = QtWidgets.QMenu()
        self.actions = dict()

        action_newWP = QtWidgets.QAction("New Work Package")
        action_newWP.triggered.connect(self.newWorkPackage)
        self.menu.addAction(action_newWP)
        self.actions["New Work Package"] = action_newWP

        self.menu.addSeparator()

        if self.workPackages:
            for wp in self.workPackages:
                self.menu.addAction(wp)
            self.menu.addSeparator()

        action_startDay = QtWidgets.QAction("Start Day")
        action_startDay.triggered.connect(self.startDay)
        self.menu.addAction(action_startDay)
        self.actions["Start Day"] = action_startDay

        action_endDay = QtWidgets.QAction("End Day")
        action_endDay.triggered.connect(self.endDay)
        self.menu.addAction(action_endDay)
        self.actions["End Day"] = action_endDay

        self.menu.addSeparator()

        action_open = QtWidgets.QAction("Open")
        action_open.triggered.connect(self.restore)
        self.menu.addAction(action_open)
        self.actions["Open"] = action_open

        action_exit = QtWidgets.QAction("Exit")
        action_exit.triggered.connect(self.app.exit)
        self.menu.addAction(action_exit)
        self.actions["Exit"] = action_exit

        self.trayIcon.setContextMenu(self.menu)

    def trayActivated(self, reason):
        if reason == self.trayIcon.Trigger:
            self.restore()
        if reason == self.trayIcon.MiddleClick:
            self.app.exit()

    def restore(self):
        self.show()  # if closed to tray
        self.activateWindow()  # if in the background
        self.setWindowState(self.windowState() & ~QtCore.Qt.WindowMinimized | QtCore.Qt.WindowActive)  # if minimized

    def startDay(self):
        self.datetime.setDate(QtCore.QDate.currentDate())
        x = QtCore.QDate.currentDate().day() - 1
        h = QtCore.QTime.currentTime().hour()
        m = QtCore.QTime.currentTime().minute()
        self.starttimeTime[x].setTime(QtCore.QTime(h, m))
        self.updateDateLabels()
        self.saveMonth()

    def endDay(self):
        self.datetime.setDate(QtCore.QDate.currentDate())
        x = QtCore.QDate.currentDate().day() - 1
        h = QtCore.QTime.currentTime().hour()
        m = QtCore.QTime.currentTime().minute()
        self.endtimeTime[x].setTime(QtCore.QTime(h, m))
        self.updateDateLabels()
        self.saveMonth()

    def loadWorkPackages(self):
        file = f"workpackages.json"
        workPackages = []
        try:
            with open(file, "r") as fp:
                jsonWP = json.load(fp)
                for wpJson in jsonWP:
                    wp = WorkPackage(wpJson["name"], wpJson["ticket"], wpJson["loggedTime"])
                    wp.triggered.connect(self.stopAllTracking)
                    workPackages.append(wp)
            return workPackages
        except Exception as e:
            print(e)
            return workPackages

    def saveWorkPackages(self):
        file = f"workpackages.json"
        if self.workPackages:
            workPackages = []
            for wp in self.workPackages:
                workPackages.append(wp.asJson())
            with open(file, "w") as fp:
                json.dump(workPackages, fp)

    def newWorkPackage(self):
        name, ok = QtWidgets.QInputDialog.getText(self, "Name of new Work Package", "Please put in the name")
        while name in [wp.name for wp in self.workPackages] and ok:
            name, ok = QtWidgets.QInputDialog.getText(self, "Name of new Work Package", "The name has to be unique")
        if ok:
            wp = WorkPackage(name)
            wp.triggered.connect(self.stopAllTracking)
            wp.trigger()
            self.workPackages.append(wp)
            self.createTrayMenu()
            self.workPackageView.addWorkPackage(wp)

    def removeWorkPackage(self, wp):
        self.workPackages.remove(wp)
        self.createTrayMenu()

    def openWorkPackageView(self):
        self.workPackageView.show()

    def onSettingsClicked(self):
        if self.settings.exec_():
            self.config = self.settings.getConfig()
            self.updateDateLabels()
            self.app.setQuitOnLastWindowClosed(not self.config["minimize"])

    def openDetailTimesDialog(self):
        pushButton = self.sender()
        dlg = DetailTimesDialog(self, pushButton.text(), pushButton.timestamps[2])
        if dlg.exec_():
            pushButton.timestamps = dlg.getDetails()
            self.updateDateLabels()

    def colorDates(self, day=None):
        date = self.datetime.date()
        month = date.month()
        today = QtCore.QDate.currentDate()

        if day is None:
            start = 0
            end = date.daysInMonth()
        else:
            start = day
            end = day + 1
        for x in range(start, end):
            if x + 1 < today.day() and month == today.month():
                self.dateButtons[x].setStyleSheet("color: rgb(100, 100, 100)")
            elif x + 1 == today.day() and month == today.month():
                self.dateButtons[x].setStyleSheet("color: red")
                self.actions["Start Day"].setDisabled(self.starttimeTime[x].time().msecsSinceStartOfDay())
            else:
                self.dateButtons[x].setStyleSheet("color: black")

    def updateDateLabels(self):
        dayString = [""] + [d for d in calendar.day_abbr]
        hours = [x.toString("h:mm") for x in self.config["hours"]]
        zero = QtCore.QTime(0, 0)
        seconds = [zero.secsTo(x) for x in self.config["hours"]]

        date = self.datetime.date()
        month = date.month()
        year = date.year()
        today = QtCore.QDate.currentDate()

        ZA = 0
        tH = 0  # total hours worked
        pTH = 0  # planned total hours this month
        for x in range(31):
            if x < date.daysInMonth():
                self.dateButtons[x].show()
                self.plannedTimeLabels[x].show()
                self.vacationCheckBoxes[x].show()
                dayOfWeek = QtCore.QDate(year, month, x + 1).dayOfWeek()
                self.dateButtons[x].setText(f"{dayString[dayOfWeek]} {x + 1}.{month}.{year}")
                # self.dataButtons[x].set
                self.plannedTimeLabels[x].setText(hours[dayOfWeek])

                self.colorDates(x)

                if self.dateButtons[x].timestamps[0] and self.dateButtons[x].timestamps[1]:
                    self.starttimeTime[x].setTime(QtCore.QTime(minutesToTime(self.dateButtons[x].timestamps[0])))
                    self.endtimeTime[x].setTime(QtCore.QTime(minutesToTime(self.dateButtons[x].timestamps[1])))
                    self.starttimeTime[x].setEnabled(False)
                    self.endtimeTime[x].setEnabled(False)
                else:
                    self.starttimeTime[x].setEnabled(True)
                    self.endtimeTime[x].setEnabled(True)

                calcNeeded = seconds[dayOfWeek] and not self.vacationCheckBoxes[x].isChecked()
                if calcNeeded:
                    self.starttimeTime[x].show()
                    self.endtimeTime[x].show()
                    self.diffTimeLabels[x].show()
                    self.autoTimes[x].show()
                    self.diffTimeLabels[x].show()
                    self.fullTimeLabels[x].show()
                    self.breakCheckBoxes[x].show()

                    if not self.endtimeTime[x].time().msecsSinceStartOfDay() and \
                            self.starttimeTime[x].time().msecsSinceStartOfDay() and \
                            self.config["forecastEndTimes"]:
                        # no end time set yet but start time is --> automatically set endtime
                        startTimeSeconds = QtCore.QTime(0, 0).secsTo(self.starttimeTime[x].time())
                        diffTime = self.endtimeTime[x].time().addSecs(startTimeSeconds + seconds[dayOfWeek])
                        if self.breakCheckBoxes[x].isChecked():
                            diffTime = diffTime.addSecs(self.config["lunchBreak"] * 60)
                        self.endtimeTime[x].setTime(diffTime)

                    # calc diff time
                    newStart = self.starttimeTime[x].time().addSecs(seconds[dayOfWeek])
                    diff = newStart.secsTo(self.endtimeTime[x].time())
                    if self.breakCheckBoxes[x].isChecked() and self.endtimeTime[x].time().msecsSinceStartOfDay():
                        diff -= self.config["lunchBreak"] * 60
                    if diff < 0:
                        diffTime = QtCore.QTime(0, 0).addSecs(-diff)
                        self.diffTimeLabels[x].setText(diffTime.toString('-h:mm'))
                    elif diff > 0:
                        diffTime = QtCore.QTime(0, 0).addSecs(diff)
                        self.diffTimeLabels[x].setText(diffTime.toString('h:mm'))
                    else:
                        self.diffTimeLabels[x].hide()

                    if x + 1 <= today.day() or month is not today.month():
                        ZA += diff

                    # planned total hours per day:
                    pTH += seconds[dayOfWeek]

                    # worked hours per day:
                    if self.starttimeTime[x].time().msecsSinceStartOfDay():
                        diff = self.starttimeTime[x].time().secsTo(self.endtimeTime[x].time())
                        if self.breakCheckBoxes[x].isChecked():
                            diff -= self.config["lunchBreak"] * 60
                        diffTime = QtCore.QTime(0, 0).addSecs(diff)
                        self.fullTimeLabels[x].setText(diffTime.toString('hh:mm'))
                        tH += diff
                        # mark the time red if it is more than 10.5 hours
                        if diff > 36000:
                            self.fullTimeLabels[x].setStyleSheet("color: red")
                        else:
                            self.fullTimeLabels[x].setStyleSheet("color: black")
                    else:
                        self.fullTimeLabels[x].setText("")
                else:
                    self.starttimeTime[x].hide()
                    self.endtimeTime[x].hide()
                    self.diffTimeLabels[x].hide()
                    self.autoTimes[x].hide()
                    self.diffTimeLabels[x].hide()
                    self.fullTimeLabels[x].hide()
                    self.breakCheckBoxes[x].hide()
            else:
                self.dateButtons[x].hide()
                self.plannedTimeLabels[x].hide()
                self.starttimeTime[x].hide()
                self.endtimeTime[x].hide()
                self.autoTimes[x].hide()
                self.diffTimeLabels[x].hide()
                self.vacationCheckBoxes[x].hide()
                self.fullTimeLabels[x].hide()
                self.breakCheckBoxes[x].hide()
        if ZA < 0:
            ZA = abs(ZA)
            self.hoursZA.setText(f"ZA: -{ZA // 3600}:{ZA % 3600 // 60:002}")
        elif ZA >= 0:
            self.hoursZA.setText(f"ZA: {ZA // 3600}:{ZA % 3600 // 60:002}")
        self.hoursTotal.setText(f'{tH // 3600}:{tH % 3600 // 60:002}/{pTH // 3600}:{pTH % 3600 // 60:002}')

    def onMonthChanged(self):
        self.saveMonth()
        self.oldDateTime = self.datetime.date()
        self.loadMonth()
        self.updateDateLabels()

    def saveMonth(self):
        # gather all data and store it somewhere
        data = {"MonthAndYear": self.oldDateTime.toString("MMMM yyyy")}
        for x in range(self.oldDateTime.daysInMonth()):
            s = timeToMinutes(self.starttimeTime[x].time())
            e = timeToMinutes(self.endtimeTime[x].time())
            v = self.vacationCheckBoxes[x].isChecked()
            lb = self.breakCheckBoxes[x].isChecked()
            timestamps = self.dateButtons[x].timestamps
            data[f"{x}"] = [s, e, v, lb, timestamps]
        if not os.path.exists("data"):
            os.mkdir("data")
        with open(f"data\{data['MonthAndYear']}.json", "w") as fp:
            json.dump(data, fp)

    def loadMonth(self):
        # load all data if possible
        file = f"data\{self.oldDateTime.toString('MMMM yyyy')}.json"
        if os.path.exists(file):
            shutil.copy(file, file.replace(".json", ".json.bak"))
            with open(file, "r") as fp:
                data = json.load(fp)
                date = self.datetime.date()
                for x in range(date.daysInMonth()):
                    # backwards compatibility:
                    _data = data[f"{x}"]
                    if len(_data) == 3:
                        s, e, v = _data
                        lb = True
                        timestamps = [0, 0, [(0, 0)] * 10]
                    elif len(_data) == 4:
                        s, e, v, lb = _data
                        timestamps = [0, 0, [(0, 0)] * 10]
                    else:
                        s, e, v, lb, timestamps = _data
                    self.starttimeTime[x].setTime(minutesToTime(s))
                    self.endtimeTime[x].setTime(minutesToTime(e))
                    self.vacationCheckBoxes[x].setChecked(v)
                    self.breakCheckBoxes[x].setChecked(lb)
                    self.dateButtons[x].timestamps = timestamps
        else:
            date = self.datetime.date()
            for x in range(date.daysInMonth()):
                self.starttimeTime[x].setTime(minutesToTime(0))
                self.endtimeTime[x].setTime(minutesToTime(0))
                self.vacationCheckBoxes[x].setChecked(False)
                self.breakCheckBoxes[x].setChecked(True)
                self.dateButtons[x].timestamps = [0, 0, [(0, 0)] * 10]

    def autoUpdateTime(self):
        x = int(self.sender().objectName())
        h = QtCore.QTime.currentTime().hour()
        m = QtCore.QTime.currentTime().minute()
        if not self.starttimeTime[x].time().msecsSinceStartOfDay():
            self.starttimeTime[x].setTime(QtCore.QTime(h, m))
        else:
            if m == 60:
                m = 0
                h += 1
            self.endtimeTime[x].setTime(QtCore.QTime(h, m))
        self.updateDateLabels()

    def closeEvent(self, event):
        self.saveMonth()
        super(MainWindow, self).closeEvent(event)


class WorkPackage(QtWidgets.QAction):
    def __init__(self, name, ticket=None, loggedtime=0):
        self.name = name
        self.ticket = ticket
        self.loggedTime = loggedtime
        self.currentStartTimeStamp = None
        super().__init__(text=name)
        self.setCheckable(True)
        self.setChecked(False)
        self.triggered.connect(self._triggered)
        self.setText(str(self))

    def __str__(self):
        return f"{self.name} - {self.ftime()}"

    def startTracking(self):
        self.currentStartTimeStamp = time.time()

    def stopTracking(self):
        self.loggedTime += time.time() - self.currentStartTimeStamp
        self.currentStartTimeStamp = None

    def _triggered(self):
        if not self.isChecked():
            self.stopTracking()
        else:
            self.startTracking()

    def resetTime(self):
        if self.isChecked():
            self.currentStartTimeStamp = time.time()
        self.loggedTime = 0

    def getCurrentTime(self):
        if self.currentStartTimeStamp:
            return time.time() - self.currentStartTimeStamp
        return 0

    def getTotalTime(self):
        return self.getCurrentTime() + self.loggedTime

    def ftime(self):
        t = self.getTotalTime()
        return f"{int(t // 3600):01d}:{int(t / 60 % 60):02d}:{int(t % 60):02d}"

    def convertCurrentToLogged(self):
        self.loggedTime += time.time() - self.currentStartTimeStamp
        self.currentStartTimeStamp = time.time()

    def asJson(self):
        if self.isChecked():
            self.convertCurrentToLogged()
        return {
            "name": self.name,
            "ticket": self.ticket,
            "loggedTime": self.getTotalTime(),
        }


class WorkPackageWidget(QtWidgets.QWidget):
    started = QtCore.Signal(bool)
    urlStart = "https://jira-ibs.zone2.agileci.conti.de"

    def __init__(self, parent=None, workpackage=None):
        super(WorkPackageWidget, self).__init__(parent)
        self._workpackage = None

        grid = QtWidgets.QGridLayout()
        self.ticket = QtWidgets.QPushButton()
        self.name = QtWidgets.QLabel()
        self.time = QtWidgets.QLabel()
        self.startStopButton = QtWidgets.QPushButton(QtGui.QPixmap(resource_path("play.png")), "")
        self.startStopButton.setCheckable(True)
        self.logButton = QtWidgets.QPushButton(QtGui.QPixmap(resource_path("jira.png")), "Log to Jira")
        self.editButton = QtWidgets.QPushButton(QtGui.QPixmap(resource_path("edit.png")), "")
        self.removeButton = QtWidgets.QPushButton(QtGui.QPixmap(resource_path("delete.png")), "")

        self.ticket.clicked.connect(self.openUrl)
        self.logButton.clicked.connect(self.logToJira)
        self.editButton.clicked.connect(self.editWP)
        self.removeButton.clicked.connect(self.removeWP)

        grid.addWidget(self.ticket, 0, 0)
        grid.addWidget(self.name, 0, 1)
        grid.addWidget(self.time, 0, 2)
        grid.addWidget(self.startStopButton, 0, 3)
        grid.addWidget(self.logButton, 0, 4)
        grid.addWidget(self.editButton, 0, 5)
        grid.addWidget(self.removeButton, 0, 6)
        self.setLayout(grid)

        if workpackage:
            self.setWorkPackage(workpackage)

    def isActive(self):
        return self._workpackage.isChecked()

    def setWorkPackage(self, workpackage: WorkPackage):
        self._workpackage = workpackage
        self.startStopButton.clicked.connect(self._workpackage.trigger)
        self.updateData()

    def updateData(self):
        if self._workpackage.ticket:
            self.ticket.setText(self._workpackage.ticket)
        else:
            self.ticket.setText("Add Ticket #")
        self.name.setText(self._workpackage.name)
        self.time.setText(self._workpackage.ftime())
        if self.isActive():
            self.startStopButton.setChecked(True)
            self.startStopButton.setIcon(QtGui.QPixmap(resource_path("pause.png")))
            self.setStyleSheet("background: LightGreen")
            self.setAutoFillBackground(True)
        else:
            self.startStopButton.setChecked(False)
            self.startStopButton.setIcon(QtGui.QPixmap(resource_path("play.png")))
            self.setStyleSheet("")

    def openUrl(self):
        if self._workpackage.ticket:
            url = f"{self.urlStart}/browse/{self._workpackage.ticket}"
            QtGui.QDesktopServices.openUrl(QtCore.QUrl(url))
        else:
            name, ok = QtWidgets.QInputDialog.getText(self, "Ticket-ID (e.g. GMCTC-1234)", "Ticket")
            if ok:
                self._workpackage.ticket = name
                self.ticket.setText(name)

    def startStopClicked(self, checked=False):
        self.started.emit(checked)

    def editWP(self):
        WorkPackageEditDialog(self, self._workpackage).exec_()

    def removeWP(self):
        ret = QtWidgets.QMessageBox.warning(
            self, "Delete workpackage",
            "The workpackage will be deleted together with all the logged time. Are you sure you want to delete it?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        if ret == QtWidgets.QMessageBox.Yes:
            if isinstance(self.parent(), WorkPackageView):
                self.parent().removeWorkPackage(self)
                self.parent().parent().removeWorkPackage(self._workpackage)
            self.deleteLater()

    def getMainWindow(self, parent):
        if parent:
            if isinstance(parent, MainWindow):
                return parent
            else:
                return self.getMainWindow(parent.parent())
        else:
            return None

    def getTotalTime(self):
        return self._workpackage.getTotalTime()

    def logToJira(self):
        mainWindow = self.getMainWindow(self.parent())
        wp = self._workpackage
        loggedTime = int(self.getTotalTime())
        if wp.ticket and loggedTime:
            if JiraWriteLog(mainWindow.config["uid"], wp.ticket, loggedTime):
                print("log written - deleting logged time")
                wp.resetTime()


class WorkPackageView(QtWidgets.QDialog):
    def __init__(self, parent):
        super().__init__(parent,
                         QtCore.Qt.WindowCloseButtonHint | QtCore.Qt.WindowTitleHint | QtCore.Qt.WindowSystemMenuHint)
        self.setWindowTitle("Work Packages")
        wps = self.parent().workPackages
        self.splitter = QtWidgets.QVBoxLayout()
        for wp in wps:
            print(wp)
            self.splitter.addWidget((WorkPackageWidget(self, wp)))
        # self.splitter.setSizeConstraint(QtWidgets.QLayout.SetFixedSize)
        mainSplitter = QtWidgets.QVBoxLayout()
        mainSplitter.addLayout(self.splitter)
        hSplitter = QtWidgets.QHBoxLayout()

        self.totalTimeLabel = QtWidgets.QLabel("")
        self.newWorkPackageButton = QtWidgets.QPushButton("New Work Package")
        self.newWorkPackageButton.clicked.connect(self.parent().newWorkPackage)

        hSplitter.addWidget(self.totalTimeLabel)
        hSplitter.addWidget(self.newWorkPackageButton)
        mainSplitter.addLayout(hSplitter)

        self.setLayout(mainSplitter)

    def addWorkPackage(self, wp):
        self.splitter.addWidget((WorkPackageWidget(self, wp)))
        self.updateChildrenData()

    def removeWorkPackage(self, wpw):
        for child in self.findChildren(WorkPackageWidget):
            if child == wpw:
                self.children().remove(child)
                break
        else:
            print("nothing found")
        self.updateChildrenData()

    def updateChildrenData(self):
        children = self.findChildren(WorkPackageWidget)
        if children:
            ticketMax = max([wp.ticket.minimumSizeHint().width() for wp in children])
            nameMax = max([wp.name.minimumSizeHint().width() for wp in children])
            timeMax = max([wp.time.minimumSizeHint().width() for wp in children])

            for child in children:
                child.updateData()
                child.ticket.setMinimumWidth(ticketMax)
                child.name.setMinimumWidth(nameMax)
                child.time.setMinimumWidth(timeMax)

            t = sum([wp.getTotalTime() for wp in children])
            totalTime = f"{int(t // 3600):01d}:{int(t / 60 % 60):02d}:{int(t % 60):02d}"
            self.totalTimeLabel.setText(f"Current Total Time: {totalTime}")


class WorkPackageEditDialog(QtWidgets.QDialog):
    def __init__(self, parent, workpackage):
        super().__init__(parent,
                         QtCore.Qt.WindowCloseButtonHint | QtCore.Qt.WindowTitleHint | QtCore.Qt.WindowSystemMenuHint)
        self.setWindowTitle("Edit Work Package")
        self.workpackage = workpackage

        grid = QtWidgets.QGridLayout()
        self.notUnique = QtWidgets.QLabel("Name has to be unique!")
        self.notUnique.setStyleSheet("color: red")
        self.notUnique.setVisible(False)
        self.ticket = QtWidgets.QLabel("Ticket")
        self.name = QtWidgets.QLabel("Name")
        self.time = QtWidgets.QLabel("Time")
        self.ticket.setAlignment(QtCore.Qt.AlignLeft)
        self.name.setAlignment(QtCore.Qt.AlignLeft)
        self.time.setAlignment(QtCore.Qt.AlignLeft)
        grid.addWidget(self.notUnique, 0, 0, 1, 4)
        grid.addWidget(self.ticket, 1, 0)
        grid.addWidget(self.name, 2, 0)
        grid.addWidget(self.time, 3, 0, 2, 1)
        self.ticketLE = QtWidgets.QLineEdit(self.workpackage.ticket)
        self.nameLE = QtWidgets.QLineEdit(self.workpackage.name)

        self.dayLabel = QtWidgets.QLabel("Days")
        self.hourLabel = QtWidgets.QLabel("Hours")
        self.minuteLabel = QtWidgets.QLabel("Minutes")
        self.dayEdit = QtWidgets.QSpinBox()
        self.hourEdit = AdvancedSpinBox()
        self.hourEdit.setRange(0, 23)
        self.hourEdit.wrapped.connect(self.dayEdit.stepBy)
        self.minuteEdit = AdvancedSpinBox()
        self.minuteEdit.setRange(0, 59)
        self.minuteEdit.wrapped.connect(self.hourEdit.stepBy)
        grid.addWidget(self.ticketLE, 1, 1, 1, 3)
        grid.addWidget(self.nameLE, 2, 1, 1, 3)
        grid.addWidget(self.dayLabel, 3, 1)
        grid.addWidget(self.hourLabel, 3, 2)
        grid.addWidget(self.minuteLabel, 3, 3)
        grid.addWidget(self.dayEdit, 4, 1)
        grid.addWidget(self.hourEdit, 4, 2)
        grid.addWidget(self.minuteEdit, 4, 3)

        self.updateTime(True)

        buttonbox = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        buttonbox.accepted.connect(self.accept)
        buttonbox.rejected.connect(self.reject)

        grid.addWidget(buttonbox, 5, 0, 1, 4)
        self.setLayout(grid)

        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.updateTime)
        self.timer.start(1000)

    def updateTime(self, frominit=False):
        isChecked = self.workpackage.isChecked()
        if isChecked or frominit:
            t = self.workpackage.getTotalTime()
            days = t // (60 * 60 * 24)
            t = t - (days * 60 * 60 * 24)
            hours = t // (60 * 60)
            t = t - (hours * 60 * 60)
            minutes = t // 60
            self.dayEdit.setValue(days)
            self.hourEdit.setValue(hours)
            self.minuteEdit.setValue(minutes)

        self.dayEdit.setDisabled(isChecked)
        self.hourEdit.setDisabled(isChecked)
        self.minuteEdit.setDisabled(isChecked)

    def getMainWindow(self, parent):
        if parent:
            if isinstance(parent, MainWindow):
                return parent
            else:
                return self.getMainWindow(parent.parent())
        else:
            return None

    def accept(self):
        mainWindow = self.getMainWindow(self.parent())
        if self.workpackage.name != self.nameLE.text() and self.nameLE.text() in [wp.name for wp in
                                                                                  mainWindow.workPackages]:
            self.notUnique.setVisible(True)
            return
        self.workpackage.name = self.nameLE.text()
        self.workpackage.ticket = self.ticketLE.text()
        if not self.workpackage.isChecked():
            self.workpackage.loggedTime = (self.dayEdit.value() * 60 * 60 * 24) + \
                                          (self.hourEdit.value() * 60 * 60) + \
                                          (self.minuteEdit.value() * 60)
        super().accept()


def start_GUI():
    """Starts the GUI
    """
    app = QtWidgets.QApplication(sys.argv)
    app.setStyleSheet("QLabel { qproperty-alignment: AlignCenter; }")
    app.setApplicationName('Time Converter')
    app.setWindowIcon(QtGui.QPixmap(resource_path("time.png")))
    app.setQuitOnLastWindowClosed(False)
    window = MainWindow(app=app)
    window.setWindowIcon(QtGui.QPixmap(resource_path("time.png")))
    window.show()

    app.exec_()
    window.saveWorkPackages()


def main():
    start_GUI()


if __name__ == '__main__':
    main()
