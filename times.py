"""Main application window for time tracking."""

from __future__ import annotations

import calendar
import json
import os
import shutil
import sys
import time
from pathlib import Path

import psutil
import win32com.client
import win32gui
import win32process
from PySide6 import QtCore, QtGui, QtWidgets

import _dialogs as dialogs
from _utils import JiraWriteLog, logging, minutesToTime, resource_path, timeToMinutes

version = "replace me for real version"

MAXIMUM_DAILY_ALLOWED_WORK_HOURS = 10


class MainWindow(QtWidgets.QMainWindow):
    """Main application window for time tracking."""

    def __init__(self, parent: QtWidgets.QWidget | None = None, app: QtWidgets.QApplication | None = None) -> None:
        """Create main application window for time tracking."""
        super().__init__(parent)

        self.setObjectName("Times")
        self.setWindowTitle(f"Times {version}")
        self.setMinimumWidth(500)

        self.dateButtons = []
        self.plannedTimeLabels = []
        self.starttimeTime = []
        self.endtimeTime = []
        self.autoTimes = []
        self.diffTimeLabels = []
        self.vacationCheckBoxes = []
        self.fullTimeLabels = []
        self.breakCheckBoxes = []
        self.HOCheckBoxes = []

        mainWidget = self.createMainWidget()

        vSplitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        vSplitter.addWidget(self.createTopLine())
        vSplitter.addWidget(self.createScrollArea(mainWidget))
        vSplitter.setChildrenCollapsible(False)
        vSplitter.handle(1).setCursor(QtCore.Qt.ArrowCursor)

        self.settings = dialogs.SettingsDialog(self)
        self.loadMonth()
        self.config = self.settings.getConfig()
        self.workPackages = self.loadWorkPackages()
        self.workPackageView = WorkPackageView(self)
        self.workpackagesButton.setChecked(self.config["wpActive"])

        self.hSplitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        self.hSplitter.addWidget(vSplitter)
        self.hSplitter.setChildrenCollapsible(False)
        wpl = self.config["wpLocation"]
        if wpl < 2:  # noqa: PLR2004  - could be fixed at some point by making it an enum...
            self.hSplitter.insertWidget(wpl, self.workPackageView)

        self.workPackageView.setVisible(self.config["wpActive"])

        self.setCentralWidget(self.hSplitter)

        self.app = app
        if self.app:
            self.app.setQuitOnLastWindowClosed(not self.config["minimize"])
            self.menu = None
            self.trayActions = {}
            self.trayIcon = None
            self.createTray()

        self.updateDateLabels()
        self.resize(QtCore.QSize(mainWidget.sizeHint().width() + 20, self.size().height() + 50))

        self.cyclicCounter = 0
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.cyclicFunction)
        self.timer.start(1000)

    def createTopLine(self) -> QtWidgets.QGroupBox:
        """Create the top line with controls."""
        topLine = QtWidgets.QGroupBox()
        layout = QtWidgets.QGridLayout()

        self.datetime = QtWidgets.QDateTimeEdit(QtCore.QDate.currentDate())
        self.datetime.setDisplayFormat("MMMM yyyy")
        self.datetime.dateChanged.connect(self.onMonthChanged)
        layout.addWidget(self.datetime, 0, 0, 1, 3)
        self.oldDateTime = self.datetime.date()

        self.onSitePercentage = QtWidgets.QLabel("'HO%")
        self.onSitePercentage.setToolTip("Display the % of office days in the complete month")
        layout.addWidget(self.onSitePercentage, 0, 5)

        self.hoursZA = QtWidgets.QLabel("ZA")
        self.hoursTotal = QtWidgets.QLabel("Total")
        layout.addWidget(self.hoursZA, 0, 7)
        layout.addWidget(self.hoursTotal, 0, 8)

        settingsButton = QtWidgets.QPushButton("Settings")
        settingsButton.clicked.connect(self.onSettingsClicked)
        layout.addWidget(settingsButton, 0, 9)

        self.workpackagesButton = QtWidgets.QPushButton("WP")
        self.workpackagesButton.setCheckable(True)
        self.workpackagesButton.clicked.connect(self.openWorkPackageView)
        layout.addWidget(self.workpackagesButton, 0, 10)
        topLine.setLayout(layout)
        topLine.setFixedHeight(40)
        return topLine

    def createDayWidgets(self, day: int, layout: QtWidgets.QGridLayout) -> None:
        """Create widgets for the day of the month."""
        dateButton = QtWidgets.QPushButton(str(day))
        dateButton.clicked.connect(self.openDetailTimesDialog)
        self.dateButtons.append(dateButton)
        layout.addWidget(dateButton, day, 0)

        label = QtWidgets.QLabel(str(day))
        self.plannedTimeLabels.append(label)
        layout.addWidget(label, day, 1)

        starttime = dialogs.AdvancedTimeEdit()
        starttime.editingFinished.connect(self.updateDateLabels)
        self.starttimeTime.append(starttime)
        layout.addWidget(starttime, day, 2)

        endtime = dialogs.AdvancedTimeEdit()
        endtime.editingFinished.connect(self.updateDateLabels)
        self.endtimeTime.append(endtime)
        layout.addWidget(endtime, day, 4)

        autoTime = QtWidgets.QPushButton(QtGui.QPixmap(resource_path("time.png")), "")
        autoTime.setObjectName(str(day))
        autoTime.setToolTip(
            "If start time is 00:00, it will set it to the current time\n"
            "If start time is something different, it will set the end time to the current time"
        )
        autoTime.clicked.connect(self.autoUpdateTime)
        self.autoTimes.append(autoTime)
        layout.addWidget(autoTime, day, 5)

        label = QtWidgets.QLabel("")
        self.diffTimeLabels.append(label)
        layout.addWidget(label, day, 6)

        checkbox = dialogs.VacationButton()
        checkbox.clicked.connect(self.updateDateLabels)
        self.vacationCheckBoxes.append(checkbox)
        layout.addWidget(checkbox, day, 7)

        label = QtWidgets.QLabel("")
        self.fullTimeLabels.append(label)
        layout.addWidget(label, day, 8)

        breakCheckBox = QtWidgets.QPushButton()
        breakCheckBox.clicked.connect(self.updateDateLabels)
        breakCheckBox.setCheckable(True)
        breakCheckBox.setIcon(QtGui.QPixmap(resource_path("lunch.png")))
        breakCheckBox.setToolTip(
            "Green if you had lunch - will reduce the worked time on this day by the configured normal lunch break"
        )
        self.breakCheckBoxes.append(breakCheckBox)
        layout.addWidget(breakCheckBox, day, 9)

        HOCheckBox = QtWidgets.QPushButton()
        HOCheckBox.setCheckable(True)
        HOCheckBox.setChecked(True)
        HOCheckBox.setIcon(QtGui.QPixmap(resource_path("house.png")))
        HOCheckBox.setToolTip("Green if you worked from home - helps you remember that")
        HOCheckBox.clicked.connect(self.updateonSitePercentage)
        self.HOCheckBoxes.append(HOCheckBox)
        layout.addWidget(HOCheckBox, day, 10)

    def createMainWidget(self) -> QtWidgets.QWidget:
        """Create the main widget containing all day widgets."""
        mainWidget = QtWidgets.QGroupBox()
        mainWidgetLayout = QtWidgets.QGridLayout()
        for days in range(31):
            self.createDayWidgets(days, mainWidgetLayout)

        mainWidgetLayout.setRowStretch(31, 100)
        self.setStyleSheet("QPushButton:checked {background-color: LightGreen;}")
        mainWidget.setLayout(mainWidgetLayout)
        return mainWidget

    def createScrollArea(self, widget: QtWidgets.Qw) -> QtWidgets.QScrollArea:
        """Create the scroll area for the main widget."""
        scrollArea = QtWidgets.QScrollArea()
        scrollArea.setWidget(widget)
        scrollArea.setWidgetResizable(True)
        scrollArea.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scrollArea.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        scrollArea.setSizeAdjustPolicy(QtWidgets.QAbstractScrollArea.AdjustToContents)
        return scrollArea

    def cyclicFunction(self) -> None:
        """Update work packages and UI. Saves the workpackage data every 60 calls."""
        self.cyclicCounter = self.cyclicCounter % 60 + 1
        self.colorDates()
        self.workPackageView.updateChildrenData()
        for wp in self.workPackages:
            if wp.isChecked():
                wp.setText(str(wp))
                if self.cyclicCounter // 60:
                    self.saveWorkPackages()

    def stopAllTracking(self, checked: bool | None = None) -> None:
        """Stop tracking on all work packages."""
        if checked:
            for wp in self.workPackages:
                if wp.isChecked() and wp != self.sender():
                    wp.trigger()

    def createTray(self) -> None:
        """Create the system tray icon and its context menu."""
        self.trayIcon = QtWidgets.QSystemTrayIcon(QtGui.QIcon(resource_path("time.png")), self.app)
        self.trayIcon.show()
        self.trayIcon.activated.connect(self.trayActivated)
        self.createTrayMenu()

    def createTrayMenu(self) -> None:
        """Create the context menu for the system tray icon."""
        self.menu = QtWidgets.QMenu()

        action_newWP = QtGui.QAction("New Work Package")
        action_newWP.triggered.connect(self.newWorkPackage)
        self.menu.addAction(action_newWP)
        self.trayActions["New Work Package"] = action_newWP

        self.menu.addSeparator()

        if self.workPackages:
            for wp in self.workPackages:
                self.menu.addAction(wp)
            self.menu.addSeparator()

        action_startDay = QtGui.QAction("Start Day")
        action_startDay.triggered.connect(self.startDay)
        self.menu.addAction(action_startDay)
        self.trayActions["Start Day"] = action_startDay

        action_endDay = QtGui.QAction("End Day")
        action_endDay.triggered.connect(self.endDay)
        self.menu.addAction(action_endDay)
        self.trayActions["End Day"] = action_endDay

        self.menu.addSeparator()

        action_open = QtGui.QAction("Open")
        action_open.triggered.connect(self.restore)
        self.menu.addAction(action_open)
        self.trayActions["Open"] = action_open

        action_exit = QtGui.QAction("Exit")
        action_exit.triggered.connect(self.app.exit)
        self.menu.addAction(action_exit)
        self.trayActions["Exit"] = action_exit

        self.trayIcon.setContextMenu(self.menu)

    def trayActivated(self, reason: QtWidgets.QSystemTrayIcon.ActivationReason) -> None:
        """Handle activation of the system tray icon."""
        if reason == QtWidgets.QSystemTrayIcon.Trigger:
            self.restore()
        if reason == QtWidgets.QSystemTrayIcon.MiddleClick:
            self.app.exit()

    def restore(self) -> None:
        """Restore the main window from the system tray."""
        self.show()  # if closed to tray
        self.activateWindow()  # if in the background
        self.setWindowState(self.windowState() & ~QtCore.Qt.WindowMinimized | QtCore.Qt.WindowActive)  # if minimized

    def startDay(self) -> None:
        """Set the start time for the current day to the current time."""
        self.datetime.setDate(QtCore.QDate.currentDate())
        x = QtCore.QDate.currentDate().day() - 1
        h = QtCore.QTime.currentTime().hour()
        m = QtCore.QTime.currentTime().minute()
        self.starttimeTime[x].setTime(QtCore.QTime(h, m))
        self.updateDateLabels()
        self.saveMonth()

    def endDay(self) -> None:
        """Set the end time for the current day to the current time."""
        self.datetime.setDate(QtCore.QDate.currentDate())
        x = QtCore.QDate.currentDate().day() - 1
        h = QtCore.QTime.currentTime().hour()
        m = QtCore.QTime.currentTime().minute()
        self.endtimeTime[x].setTime(QtCore.QTime(h, m))
        self.updateDateLabels()
        self.saveMonth()

    def loadWorkPackages(self) -> list[WorkPackage]:
        """Load work packages from a JSON file."""
        file = Path("workpackages.json")
        workPackages = []
        try:
            with file.open() as fp:
                jsonWP = json.load(fp)
            for wpJson in jsonWP:
                wp = WorkPackage(wpJson["name"], wpJson["ticket"], wpJson["loggedTime"])
                wp.triggered.connect(self.stopAllTracking)
                workPackages.append(wp)
        except Exception:  # noqa: BLE001 - this should be okay for ruff because it is logged as exception with traceback
            logging.exception("Could not load work packages")
        return workPackages

    def saveWorkPackages(self) -> None:
        """Save the current work packages to a JSON file."""
        file = Path("workpackages.json")
        if self.workPackages:
            workPackages = [wp.asJson() for wp in self.workPackages]
            with file.open("w") as fp:
                json.dump(workPackages, fp, indent=4)

    def newWorkPackage(self) -> None:
        """Create a new work package with a unique name and start logging time on it."""
        name, ok = QtWidgets.QInputDialog.getText(
            self, "Name of new Work Package", "Please put in the name", QtWidgets.QLineEdit.Normal
        )
        while name in [wp.name for wp in self.workPackages] and ok:
            name, ok = QtWidgets.QInputDialog.getText(
                self, "Name of new Work Package", "The name has to be unique", QtWidgets.QLineEdit.Normal
            )
        if ok:
            wp = WorkPackage(name)
            wp.triggered.connect(self.stopAllTracking)
            wp.trigger()
            self.workPackages.append(wp)
            self.createTrayMenu()
            self.workPackageView.addWorkPackage(wp)

    def removeWorkPackage(self, wp: WorkPackage) -> None:
        """Remove a work package from the list and update the tray menu."""
        self.workPackages.remove(wp)
        self.createTrayMenu()

    def openWorkPackageView(self) -> None:
        """Show or hide the work package view based on the button state."""
        self.workPackageView.setVisible(self.workpackagesButton.isChecked())

    def onSettingsClicked(self) -> None:
        """Open the settings dialog and apply changes if accepted."""
        if self.settings.exec():
            oldConfig = self.config
            self.config = self.settings.getConfig()
            wplChanged = self.config["wpLocation"] != oldConfig["wpLocation"]
            self.updateDateLabels()
            self.app.setQuitOnLastWindowClosed(not self.config["minimize"])
            if wplChanged:
                self.workPackageView.hide()
                wpl = self.config["wpLocation"]
                if wpl < 2:  # noqa: PLR2004  - could be fixed at some point by making it an enum...
                    self.hSplitter.insertWidget(wpl, self.workPackageView)
                    self.workpackagesButton.setChecked(True)
                    self.workPackageView.show()
                    height = self.height()
                    self.adjustSize()
                    self.resize(self.width(), height)
                else:
                    self.workPackageView.setParent(None)
                    self.workPackageView = WorkPackageView(self)
                    self.workPackageView.show()
                    self.workPackageView.adjustSize()
                    height = self.height()
                    self.adjustSize()
                    self.resize(self.width(), height)

    def openDetailTimesDialog(self) -> None:
        """Open the detail times dialog for a specific day."""
        pushButton = self.sender()
        dlg = dialogs.DetailTimesDialog(self, pushButton.text(), pushButton.timestamps[2])
        if dlg.exec():
            pushButton.timestamps = dlg.getDetails()
            if self.config["dailyOfficePercentageAutoCalc"] and (pushButton.timestamps[0] or pushButton.timestamps[1]):
                totalTime = pushButton.timestamps[1] - pushButton.timestamps[0]
                officeTime = totalTime
                for start, end, state in pushButton.timestamps[2]:
                    if state == 0:
                        officeTime -= end - start
                self.HOCheckBoxes[self.dateButtons.index(pushButton)].setChecked(
                    officeTime / totalTime * 100 <= self.config["dailyOfficePercentage"]
                )
            self.updateDateLabels()

    def colorDates(self, day: int | None = None) -> None:
        """
        Color the date buttons based on the current date.

        if day is set only color this specific day
        """
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
                self.trayActions["Start Day"].setDisabled(self.starttimeTime[x].time().msecsSinceStartOfDay())
            else:
                self.dateButtons[x].setStyleSheet("")

    def updateDateLabels(self) -> None:
        """Update all date labels and calculations for the current month."""
        dayString = ["", *list(calendar.day_abbr)]
        hours = [x.toString("h:mm") for x in self.config["hours"]]
        zero = QtCore.QTime(0, 0)
        seconds = [zero.secsTo(x) for x in self.config["hours"]]

        date = self.datetime.date()
        month = date.month()
        year = date.year()

        ZA = 0
        tH = 0  # total time worked (seconds)
        pTH = 0  # planned total time this month (seconds)

        for x in range(31):
            if x < date.daysInMonth():
                self.dateButtons[x].show()
                self.plannedTimeLabels[x].show()
                dayOfWeek = QtCore.QDate(year, month, x + 1).dayOfWeek()
                self.dateButtons[x].setText(f"{dayString[dayOfWeek]} {x + 1}.{month}.{year}")
                self.plannedTimeLabels[x].setText(hours[dayOfWeek])

                self.colorDates(x)

                self.detailInputs(x)

                calcNeeded = seconds[dayOfWeek] and (
                    not self.vacationCheckBoxes[x].isChecked()
                    or (self.vacationCheckBoxes[x].isChecked() and self.vacationCheckBoxes[x].isZA)
                )
                if calcNeeded:
                    self.vacationCheckBoxes[x].show()
                    self.starttimeTime[x].show()
                    self.endtimeTime[x].show()
                    self.autoTimes[x].show()
                    self.diffTimeLabels[x].show()
                    self.fullTimeLabels[x].show()
                    self.starttimeTime[x].setEnabled(not self.vacationCheckBoxes[x].isZA)
                    self.endtimeTime[x].setEnabled(not self.vacationCheckBoxes[x].isZA)
                    self.autoTimes[x].setEnabled(not self.vacationCheckBoxes[x].isZA)
                    if self.vacationCheckBoxes[x].isZA:
                        self.breakCheckBoxes[x].hide()
                        self.HOCheckBoxes[x].hide()
                    else:
                        self.breakCheckBoxes[x].show()
                        self.HOCheckBoxes[x].show()

                    ZA += self.calcTimes(x, seconds[dayOfWeek])
                    tH += self.workedDayHours(x)
                    pTH += seconds[dayOfWeek]
                else:
                    self.hideMostDay(x)
            else:
                self.hideAllDay(x)
        self.setZAHours(ZA)
        self.hoursTotal.setText(f"{tH // 3600}:{tH % 3600 // 60:002}/{pTH // 3600}:{pTH % 3600 // 60:002}")
        self.updateonSitePercentage()

    def calcTimes(self, x: int, daySeconds: int) -> int:
        """Calculate and set the time differences for a specific day."""
        self.addEndTime(x, daySeconds)

        # calc diff time
        newStart = self.starttimeTime[x].time().addSecs(daySeconds)
        diff = newStart.secsTo(self.endtimeTime[x].time())
        if self.breakCheckBoxes[x].isChecked() and self.endtimeTime[x].time().msecsSinceStartOfDay():
            diff -= self.config["lunchBreak"] * 60
        if diff < 0:
            diffTime = QtCore.QTime(0, 0).addSecs(-diff)
            self.diffTimeLabels[x].setText(diffTime.toString("-h:mm"))
        elif diff > 0:
            diffTime = QtCore.QTime(0, 0).addSecs(diff)
            self.diffTimeLabels[x].setText(diffTime.toString("h:mm"))
        else:
            self.diffTimeLabels[x].hide()

        month = self.datetime.date().month()
        today = QtCore.QDate.currentDate()
        if x + 1 <= today.day() or month is not today.month():
            return diff
        return 0

    def hideMostDay(self, x: int) -> None:
        """Hide most widgets for a specific day, keeping date and planned time visible."""
        self.starttimeTime[x].hide()
        self.endtimeTime[x].hide()
        self.autoTimes[x].hide()
        self.diffTimeLabels[x].hide()
        self.fullTimeLabels[x].hide()
        self.breakCheckBoxes[x].hide()
        self.HOCheckBoxes[x].hide()

    def hideAllDay(self, x: int) -> None:
        """Hide all widgets for a specific day."""
        self.dateButtons[x].hide()
        self.plannedTimeLabels[x].hide()
        self.starttimeTime[x].hide()
        self.endtimeTime[x].hide()
        self.autoTimes[x].hide()
        self.diffTimeLabels[x].hide()
        self.vacationCheckBoxes[x].hide()
        self.fullTimeLabels[x].hide()
        self.breakCheckBoxes[x].hide()
        self.HOCheckBoxes[x].hide()

    def updateonSitePercentage(self) -> None:
        """Calculate and update the on-site work percentage."""
        workingDays = 0
        officeDays = 0
        for HOCheckBox in self.HOCheckBoxes:
            if not HOCheckBox.isHidden():
                workingDays += 1
                if not HOCheckBox.isChecked():
                    officeDays += 1
        if workingDays:
            onSitePercentage = officeDays / workingDays * 100
            self.onSitePercentage.setText(f"{onSitePercentage:.0f}%")
            if onSitePercentage < self.config["officePercentage"]:
                self.onSitePercentage.setStyleSheet("color: red")
            else:
                self.onSitePercentage.setStyleSheet("")
                self.onSitePercentage.setStyle(None)

    def detailInputs(self, index: int) -> None:
        """Enable/disable inputs based on stored timestamps."""
        if self.dateButtons[index].timestamps[0] and self.dateButtons[index].timestamps[1]:
            self.starttimeTime[index].setTime(QtCore.QTime(minutesToTime(self.dateButtons[index].timestamps[0])))
            self.endtimeTime[index].setTime(QtCore.QTime(minutesToTime(self.dateButtons[index].timestamps[1])))
            self.starttimeTime[index].setEnabled(False)
            self.endtimeTime[index].setEnabled(False)
        else:
            self.starttimeTime[index].setEnabled(True)
            self.endtimeTime[index].setEnabled(True)

    def addEndTime(self, index: int, daySeconds: int) -> None:
        """Automatically set end time if only start time is set and forecastEndTimes is enabled."""
        if (
            not self.endtimeTime[index].time().msecsSinceStartOfDay()
            and self.starttimeTime[index].time().msecsSinceStartOfDay()
            and self.config["forecastEndTimes"]
        ):
            # no end time set yet but start time is --> automatically set endtime
            startTimeSeconds = QtCore.QTime(0, 0).secsTo(self.starttimeTime[index].time())
            diffTime = self.endtimeTime[index].time().addSecs(startTimeSeconds + daySeconds)
            if self.breakCheckBoxes[index].isChecked():
                diffTime = diffTime.addSecs(self.config["lunchBreak"] * 60)
            self.endtimeTime[index].setTime(diffTime)

    def workedDayHours(self, index: int) -> int:
        """Calculate and set the worked hours for a day."""
        if self.starttimeTime[index].time().msecsSinceStartOfDay():
            diff = self.starttimeTime[index].time().secsTo(self.endtimeTime[index].time())
            if self.breakCheckBoxes[index].isChecked():
                diff -= self.config["lunchBreak"] * 60
            diffTime = QtCore.QTime(0, 0).addSecs(diff)
            self.fullTimeLabels[index].setText(diffTime.toString("hh:mm"))
            # mark the time red if it is more than 10 hours
            if diff > MAXIMUM_DAILY_ALLOWED_WORK_HOURS * 3600:
                self.fullTimeLabels[index].setStyleSheet("color: red")
            else:
                self.fullTimeLabels[index].setStyleSheet("")
                self.fullTimeLabels[index].setStyle(None)
                # setting the style sheet alone did not remove the red color on Windows
            return diff
        self.fullTimeLabels[index].setText("")
        return 0

    def setZAHours(self, za: int) -> None:
        """Set the ZA hours label."""
        if za < 0:
            za = abs(za)
            self.hoursZA.setText(f"ZA: -{za // 3600}:{za % 3600 // 60:002}")
        elif za >= 0:
            self.hoursZA.setText(f"ZA: {za // 3600}:{za % 3600 // 60:002}")

    def onMonthChanged(self) -> None:
        """Handle the month change event to save and load data."""
        self.saveMonth()
        self.oldDateTime = self.datetime.date()
        self.loadMonth()
        self.updateDateLabels()

    def saveMonth(self) -> None:
        """Save all data for the selected month."""
        data = {"MonthAndYear": self.oldDateTime.toString("MMMM yyyy")}
        for x in range(self.oldDateTime.daysInMonth()):
            s = timeToMinutes(self.starttimeTime[x].time())
            e = timeToMinutes(self.endtimeTime[x].time())
            v = self.vacationCheckBoxes[x].isChecked()
            lb = self.breakCheckBoxes[x].isChecked()
            ho = self.HOCheckBoxes[x].isChecked()
            timestamps = self.dateButtons[x].timestamps
            za = v and self.vacationCheckBoxes[x].isZA
            data[f"{x}"] = [s, e, v, lb, ho, timestamps, za]
        dataFolder = Path("data")
        if not dataFolder.exists():
            dataFolder.mkdir()
        monthFile = dataFolder / f"{data['MonthAndYear']}.json"
        with monthFile.open("w") as fp:
            json.dump(data, fp, indent=4)

    def loadMonth(self) -> None:
        """Load all data for the selected month."""
        file = Path(rf"data\{self.oldDateTime.toString('MMMM yyyy')}.json")
        if file.exists():
            shutil.copy(file, str(file).replace(".json", ".json.bak"))
            with file.open() as fp:
                data = json.load(fp)
                date = self.datetime.date()
                for x in range(date.daysInMonth()):
                    # backwards compatibility:
                    _data = data[f"{x}"]
                    if len(_data) == 3:  # noqa: PLR2004
                        s, e, v = _data
                        lb = True
                        ho = True
                        timestamps = [0, 0, [(0, 0)] * 10]
                        za = False
                    elif len(_data) == 4:  # noqa: PLR2004
                        s, e, v, lb = _data
                        ho = True
                        timestamps = [0, 0, [(0, 0)] * 10]
                        za = False
                    elif len(_data) == 5:  # noqa: PLR2004
                        s, e, v, lb, timestamps = _data
                        ho = True
                        za = False
                    elif len(_data) == 6:  # noqa: PLR2004
                        s, e, v, lb, ho, timestamps = _data
                        za = False
                    else:
                        s, e, v, lb, ho, timestamps, za = _data
                    self.starttimeTime[x].setTime(minutesToTime(s))
                    self.endtimeTime[x].setTime(minutesToTime(e))
                    self.vacationCheckBoxes[x].setChecked(v)
                    self.breakCheckBoxes[x].setChecked(lb)
                    self.HOCheckBoxes[x].setChecked(ho)
                    self.dateButtons[x].timestamps = timestamps
                    self.vacationCheckBoxes[x].isZA = za
        else:
            date = self.datetime.date()
            for x in range(date.daysInMonth()):
                self.starttimeTime[x].setTime(minutesToTime(0))
                self.endtimeTime[x].setTime(minutesToTime(0))
                self.vacationCheckBoxes[x].setChecked(False)
                self.breakCheckBoxes[x].setChecked(True)
                self.dateButtons[x].timestamps = [0, 0, [(0, 0)] * 10]

    def autoUpdateTime(self) -> None:
        """Automatically set start or end time to current time."""
        x = int(self.sender().objectName())
        h = QtCore.QTime.currentTime().hour()
        m = QtCore.QTime.currentTime().minute()
        if not self.starttimeTime[x].time().msecsSinceStartOfDay():
            self.starttimeTime[x].setTime(QtCore.QTime(h, m))
        else:
            if m == 60:  # noqa: PLR2004  # it magically is 60 minutes
                m = 0
                h += 1
            self.endtimeTime[x].setTime(QtCore.QTime(h, m))
        self.updateDateLabels()

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        """Handle the close event to save data before exiting."""
        self.saveMonth()
        super().closeEvent(event)


class WorkPackage(QtGui.QAction):
    """Work package to track time spent on a specific task."""

    def __init__(self, name: str, ticket: str | None = None, loggedtime: int = 0) -> None:
        """Work package to track time spent on a specific task."""
        self.name = name
        self.ticket = ticket
        self.loggedTime = loggedtime
        self.currentStartTimeStamp = None
        super().__init__(text=name)
        self.setCheckable(True)
        self.setChecked(False)
        self.triggered.connect(self._triggered)
        self.setText(str(self))

    def __str__(self) -> str:
        """Return the string representation of the work package."""
        return f"{self.name} - {self.ftime()}"

    def startTracking(self) -> None:
        """Start tracking by storing the current time."""
        self.currentStartTimeStamp = time.time()

    def stopTracking(self) -> None:
        """Stop tracking and add the current time to logged time."""
        self.loggedTime += time.time() - self.currentStartTimeStamp
        self.currentStartTimeStamp = None

    def _triggered(self) -> None:
        """Handle the triggered signal to start/stop tracking."""
        if not self.isChecked():
            self.stopTracking()
        else:
            self.startTracking()

    def resetTime(self) -> None:
        """Reset the tracked time to zero."""
        if self.isChecked():
            self.currentStartTimeStamp = time.time()
        self.loggedTime = 0

    def getCurrentTime(self) -> float:
        """Return the currently tracked time in seconds."""
        if self.currentStartTimeStamp:
            return time.time() - self.currentStartTimeStamp
        return 0

    def getTotalTime(self) -> float:
        """Return the total logged time in seconds."""
        return self.getCurrentTime() + self.loggedTime

    def ftime(self) -> str:
        """Return the formatted time string HH:MM:SS."""
        t = self.getTotalTime()
        return f"{int(t // 3600):01d}:{int(t / 60 % 60):02d}:{int(t % 60):02d}"

    def convertCurrentToLogged(self) -> None:
        """Convert the currently tracked time to logged time."""
        self.loggedTime += time.time() - self.currentStartTimeStamp
        self.currentStartTimeStamp = time.time()

    def asJson(self) -> dict:
        """Return the work package as a JSON serializable dictionary."""
        if self.isChecked():
            self.convertCurrentToLogged()
        return {
            "name": self.name,
            "ticket": self.ticket,
            "loggedTime": self.getTotalTime(),
        }


class WorkPackageWidget(QtWidgets.QWidget):
    """Widget to display a work package."""

    started = QtCore.Signal(bool)

    def __init__(self, parent: QtWidgets.QWidget | None = None, workpackage: WorkPackage = None) -> None:
        """Widget to display a work package."""
        super().__init__(parent)
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
            self._workpackage = workpackage
            self.startStopButton.clicked.connect(self._workpackage.trigger)
            self.updateData()

    def isActive(self) -> bool:
        """Return True if the work package is active."""
        return self._workpackage.isChecked()

    def updateData(self) -> None:
        """Update the displayed data."""
        if self._workpackage.ticket:
            self.ticket.setText(self._workpackage.ticket)
        else:
            self.ticket.setText("Add Ticket #")
        self.name.setText(self._workpackage.name)
        self.time.setText(self._workpackage.ftime())
        if self.isActive():
            self.startStopButton.setChecked(True)
            self.startStopButton.setIcon(QtGui.QPixmap(resource_path("pause.png")))
            self.setStyleSheet("background: LightGreen; color: #000000")
            self.setAutoFillBackground(True)
        else:
            self.startStopButton.setChecked(False)
            self.startStopButton.setIcon(QtGui.QPixmap(resource_path("play.png")))
            self.setStyleSheet("background: None")
            self.setStyleSheet("")

    def openUrl(self) -> None:
        """Open the Jira ticket URL in the default web browser."""
        if self._workpackage.ticket:
            urlStart = self.getMainWindow(self.parent()).config["url"]
            url = f"{urlStart}/browse/{self._workpackage.ticket}"
            QtGui.QDesktopServices.openUrl(QtCore.QUrl(url))
        else:
            name, ok = QtWidgets.QInputDialog.getText(self, "Ticket-ID (e.g. PR-1234)", "Ticket", QtWidgets.QLineEdit.Normal)
            if ok:
                self._workpackage.ticket = name
                self.ticket.setText(name)

    def startStopClicked(self, checked: bool = False) -> None:
        """Handle start/stop button click."""
        self.started.emit(checked)

    def editWP(self) -> None:
        """Open the work package edit dialog."""
        WorkPackageEditDialog(self, self._workpackage).exec()

    def removeWP(self) -> None:
        """Remove the work package after confirmation."""
        if self.getTotalTime() > 60 or self.isActive():  # noqa: PLR2004  # it magically is 60 seconds
            ret = QtWidgets.QMessageBox.warning(
                self,
                "Delete workpackage",
                "The workpackage will be deleted together with all the logged time. Are you sure you want to delete it?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            )
        else:
            ret = QtWidgets.QMessageBox.Yes
        if ret == QtWidgets.QMessageBox.Yes:
            mainWindow = self.getMainWindow(self.parent())
            mainWindow.removeWorkPackage(self._workpackage)
            self.deleteLater()

    def getMainWindow(self, parent: QtWidgets.QWidget) -> MainWindow | None:
        """Get the main window from parent."""
        if parent:
            if isinstance(parent, MainWindow):
                return parent
            return self.getMainWindow(parent.parent())
        return None

    def getTotalTime(self) -> float:
        """Get the total time logged in seconds."""
        return self._workpackage.getTotalTime()

    def logToJira(self) -> None:
        """Log the actual time to the Jira ticket defined."""
        mainWindow = self.getMainWindow(self.parent())
        wp = self._workpackage
        loggedTime = int(self.getTotalTime())
        if wp.ticket and loggedTime:
            if JiraWriteLog(mainWindow.config, wp.ticket, loggedTime):
                logging.info("log written - deleting logged time.")
                wp.resetTime()
                mainWindow.saveWorkPackages()
        else:
            logging.info("no ticket or time to log.")


class WorkPackageView(QtWidgets.QDialog):
    """View to display all work packages."""

    def __init__(self, parent: QtWidgets.QWidget) -> None:
        """View to display all work packages."""
        super().__init__(
            parent,
            QtCore.Qt.WindowCloseButtonHint | QtCore.Qt.WindowTitleHint | QtCore.Qt.WindowSystemMenuHint,
        )
        self.setWindowTitle("Work Packages")
        wps = self.parent().workPackages
        self.splitter = QtWidgets.QVBoxLayout()
        for wp in wps:
            self.splitter.addWidget(WorkPackageWidget(self, wp))
        self.splitter.addStretch(100)
        scrollArea = QtWidgets.QScrollArea()
        mainWidget = QtWidgets.QGroupBox()
        mainWidget.setLayout(self.splitter)
        scrollArea.setWidget(mainWidget)
        scrollArea.setWidgetResizable(True)
        scrollArea.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scrollArea.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scrollArea.setSizeAdjustPolicy(QtWidgets.QAbstractScrollArea.AdjustToContents)

        hSplitter = QtWidgets.QHBoxLayout()
        self.totalTimeLabel = QtWidgets.QLabel("")
        self.newWorkPackageButton = QtWidgets.QPushButton("New Work Package")
        self.newWorkPackageButton.clicked.connect(self.parent().newWorkPackage)
        hSplitter.addWidget(self.totalTimeLabel)
        hSplitter.addWidget(self.newWorkPackageButton)

        mainSplitter = QtWidgets.QVBoxLayout()
        mainSplitter.addWidget(scrollArea)
        mainSplitter.addLayout(hSplitter)

        self.setLayout(mainSplitter)

    def addWorkPackage(self, wp: WorkPackage) -> None:
        """Add a new WorkPackageWidget to the view."""
        self.splitter.removeItem(self.splitter.itemAt(self.splitter.count() - 1))
        self.splitter.addWidget(WorkPackageWidget(self, wp))
        self.splitter.addStretch(100)
        self.updateChildrenData()

    def updateChildrenData(self) -> None:
        """
        Update all child WorkPackageWidgets.

        Aligns the widths of the ticket, name and time fields across all children.
        Updates the total time label with the sum of all work package times.
        """
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

    def getMainWindow(self, parent: QtWidgets.QWidget) -> MainWindow | None:
        """Get the main window from parent."""
        if parent:
            if isinstance(parent, MainWindow):
                return parent
            return self.getMainWindow(parent.parent())
        return None

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        """Handle close event."""
        mainWnd = self.getMainWindow(self.parent())
        mainWnd.workpackagesButton.setChecked(False)
        super().closeEvent(event)


class WorkPackageEditDialog(QtWidgets.QDialog):
    """Dialog to edit a work package."""

    def __init__(self, parent: QtWidgets.QWidget, workpackage: WorkPackage) -> None:
        """Dialog to edit a work package."""
        super().__init__(
            parent,
            QtCore.Qt.WindowCloseButtonHint | QtCore.Qt.WindowTitleHint | QtCore.Qt.WindowSystemMenuHint,
        )
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
        self.hourEdit = dialogs.AdvancedSpinBox()
        self.hourEdit.setRange(0, 23)
        self.hourEdit.wrapped.connect(self.dayEdit.stepBy)
        self.minuteEdit = dialogs.AdvancedSpinBox()
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

    def updateTime(self, frominit: bool = False) -> None:
        """
        Update the time fields.

        Set frominit to True to force update even if the workpackage is not checked.
        This should be used to initialize the fields when the dialog is created.
        """
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

    def getMainWindow(self, parent: QtWidgets.QWidget) -> MainWindow | None:
        """Get the main window from parent."""
        if parent:
            if isinstance(parent, MainWindow):
                return parent
            return self.getMainWindow(parent.parent())
        return None

    def accept(self) -> None:
        """Call when OK is pressed."""
        mainWindow = self.getMainWindow(self.parent())
        if self.workpackage.name != self.nameLE.text() and self.nameLE.text() in [wp.name for wp in mainWindow.workPackages]:
            self.notUnique.setVisible(True)
            return
        self.workpackage.name = self.nameLE.text()
        self.workpackage.ticket = self.ticketLE.text()
        if not self.workpackage.isChecked():
            self.workpackage.loggedTime = (
                (self.dayEdit.value() * 60 * 60 * 24) + (self.hourEdit.value() * 60 * 60) + (self.minuteEdit.value() * 60)
            )
        super().accept()


def start_GUI() -> None:
    """Start the GUI."""
    app = QtWidgets.QApplication(sys.argv)
    app.setStyleSheet("QLabel { qproperty-alignment: AlignCenter; }")
    app.setApplicationName("Time Converter")
    app.setWindowIcon(QtGui.QPixmap(resource_path("time.png")))
    app.setQuitOnLastWindowClosed(False)

    lockfile = Path("lockfile")
    start = True
    if lockfile.exists():
        with lockfile.open("r") as fp:
            pid = int(fp.read())
        if psutil.pid_exists(pid) and psutil.Process(pid).name() in ["times.exe", "python.exe"]:
            window = findWindow(pid)
            if window:
                ret = QtWidgets.QMessageBox.warning(
                    QtWidgets.QWidget(),
                    "UltraTime already running",
                    "Do you want to start a second instance?\n\n"
                    "It might lead to inconsistencies or overwriting of time data!\n"
                    "Click open to activate the first instance",
                    QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No | QtWidgets.QMessageBox.Open,
                    QtWidgets.QMessageBox.Open,
                )
            else:
                ret = QtWidgets.QMessageBox.warning(
                    QtWidgets.QWidget(),
                    "UltraTime already running",
                    "Do you want to start a second instance?\n\nIt might lead to inconsistencies or overwriting of time data!",
                    QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                    QtWidgets.QMessageBox.No,
                )
            if QtWidgets.QMessageBox.No == ret:
                start = False
                logging.info("Aborted starting")
            if QtWidgets.QMessageBox.Open == ret:
                start = False
                shell = win32com.client.Dispatch("WScript.Shell")
                shell.SendKeys("%")
                win32gui.SetForegroundWindow(window)
                logging.info("Aborted starting - Showed other instance instead")

    if start:
        lockfile.write_text(str(os.getpid()))

        window = MainWindow(app=app)
        window.setWindowIcon(QtGui.QPixmap(resource_path("time.png")))
        window.show()

        app.exec()
        window.saveWorkPackages()
        lockfile.unlink()


def windowEnumerationHandler(hwnd: int, top_windows: list) -> None:
    """Fill top_windows with all window handles."""
    top_windows.append((hwnd, win32gui.GetWindowText(hwnd), win32process.GetWindowThreadProcessId(hwnd)[1]))


def findWindow(pid: int) -> int | None:
    """Find the window handle for the given pid."""
    result = None
    top_windows = []
    win32gui.EnumWindows(windowEnumerationHandler, top_windows)
    for i in top_windows:
        if pid == i[2] and i[1] == "UltraTime":
            result = i[0]
    return result


if __name__ == "__main__":
    start_GUI()
