import calendar
import json
import os
import shutil
import sys
import time

import psutil
import win32com.client
import win32gui
import win32process
from PySide6 import QtCore, QtWidgets, QtGui

import _dialogs as dialogs
from _utils import resource_path, minutesToTime, timeToMinutes, JiraWriteLog

version = "replace me for real version"


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, parent=None, app=None):
        super(MainWindow, self).__init__(parent)

        self.setObjectName("Times")
        self.setWindowTitle(f"Times {version}")
        self.setMinimumWidth(500)

        topLine = QtWidgets.QGroupBox()
        topLineLayout = QtWidgets.QGridLayout()

        self.datetime = QtWidgets.QDateTimeEdit(QtCore.QDate.currentDate())
        self.datetime.setDisplayFormat("MMMM yyyy")
        self.datetime.dateChanged.connect(self.onMonthChanged)
        topLineLayout.addWidget(self.datetime, 0, 0, 1, 3)
        self.oldDateTime = self.datetime.date()

        self.onSitePercentage = QtWidgets.QLabel("'HO%")
        self.onSitePercentage.setToolTip("Display the % of office days in the complete month")
        topLineLayout.addWidget(self.onSitePercentage, 0, 5)

        self.hoursZA = QtWidgets.QLabel("ZA")
        self.hoursTotal = QtWidgets.QLabel("Total")
        topLineLayout.addWidget(self.hoursZA, 0, 7)
        topLineLayout.addWidget(self.hoursTotal, 0, 8)

        settingsButton = QtWidgets.QPushButton("Settings")
        settingsButton.clicked.connect(self.onSettingsClicked)
        topLineLayout.addWidget(settingsButton, 0, 9)

        self.workpackagesButton = QtWidgets.QPushButton("WP")
        self.workpackagesButton.setCheckable(True)
        self.workpackagesButton.clicked.connect(self.openWorkPackageView)
        topLineLayout.addWidget(self.workpackagesButton, 0, 10)

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
        self.HOCheckBoxes = []
        for days in range(31):
            dateButton = QtWidgets.QPushButton(str(days))
            dateButton.clicked.connect(self.openDetailTimesDialog)
            self.dateButtons.append(dateButton)
            mainWidgetLayout.addWidget(dateButton, days, 0)

            label = QtWidgets.QLabel(str(days))
            self.plannedTimeLabels.append(label)
            mainWidgetLayout.addWidget(label, days, 1)

            starttime = dialogs.AdvancedTimeEdit()
            starttime.editingFinished.connect(self.updateDateLabels)
            self.starttimeTime.append(starttime)
            mainWidgetLayout.addWidget(starttime, days, 2)

            endtime = dialogs.AdvancedTimeEdit()
            endtime.editingFinished.connect(self.updateDateLabels)
            self.endtimeTime.append(endtime)
            mainWidgetLayout.addWidget(endtime, days, 4)

            autoTime = QtWidgets.QPushButton(QtGui.QPixmap(resource_path("time.png")), "")
            autoTime.setObjectName(str(days))
            autoTime.setToolTip(
                "If start time is 00:00, it will set it to the current time\n"
                "If start time is something different, it will set the end time to the current time"
            )
            autoTime.clicked.connect(self.autoUpdateTime)
            self.autoTimes.append(autoTime)
            mainWidgetLayout.addWidget(autoTime, days, 5)

            label = QtWidgets.QLabel("")
            self.diffTimeLabels.append(label)
            mainWidgetLayout.addWidget(label, days, 6)

            checkbox = dialogs.VacationButton()
            checkbox.clicked.connect(self.updateDateLabels)
            self.vacationCheckBoxes.append(checkbox)
            mainWidgetLayout.addWidget(checkbox, days, 7)

            label = QtWidgets.QLabel("")
            self.fullTimeLabels.append(label)
            mainWidgetLayout.addWidget(label, days, 8)

            breakCheckBox = QtWidgets.QPushButton()
            breakCheckBox.clicked.connect(self.updateDateLabels)
            breakCheckBox.setCheckable(True)
            breakCheckBox.setIcon(QtGui.QPixmap(resource_path("lunch.png")))
            breakCheckBox.setToolTip(
                "Green if you had lunch - will reduce the worked time on this day by the configured normal lunch break"
            )
            self.breakCheckBoxes.append(breakCheckBox)
            mainWidgetLayout.addWidget(breakCheckBox, days, 9)

            HOCheckBox = QtWidgets.QPushButton()
            HOCheckBox.setCheckable(True)
            HOCheckBox.setChecked(True)
            HOCheckBox.setIcon(QtGui.QPixmap(resource_path("house.png")))
            HOCheckBox.setToolTip("Green if you worked from home - helps you remember that")
            HOCheckBox.clicked.connect(self.updateonSitePercentage)
            self.HOCheckBoxes.append(HOCheckBox)
            mainWidgetLayout.addWidget(HOCheckBox, days, 10)

        mainWidgetLayout.setRowStretch(31, 100)
        self.setStyleSheet("QPushButton:checked {background-color: LightGreen;}")
        mainWidget.setLayout(mainWidgetLayout)

        scrollArea = QtWidgets.QScrollArea()
        scrollArea.setWidget(mainWidget)
        scrollArea.setWidgetResizable(True)
        scrollArea.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scrollArea.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        scrollArea.setSizeAdjustPolicy(QtWidgets.QAbstractScrollArea.AdjustToContents)
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

        vSplitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        vSplitter.addWidget(topLine)
        vSplitter.addWidget(scrollArea)
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
        wpl = self.config["wpLocation"]
        if wpl < 2:
            self.hSplitter.insertWidget(wpl, self.workPackageView)

        self.workPackageView.setVisible(self.config["wpActive"])

        self.setCentralWidget(self.hSplitter)

        self.app = app
        if self.app:
            self.app.setQuitOnLastWindowClosed(not self.config["minimize"])
            self.menu = None
            self.trayActions = dict()
            self.trayIcon = None
            self.createTray()

        self.scroll = scrollArea
        self.updateDateLabels()
        self.resize(QtCore.QSize(mainWidget.sizeHint().width(), self.size().height() + 50))

        self.cyclicCounter = 0
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.cyclicFunction)
        self.timer.start(1000)
        self.adjustSize()

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

    def trayActivated(self, reason):
        if reason == QtWidgets.QSystemTrayIcon.Trigger:
            self.restore()
        if reason == QtWidgets.QSystemTrayIcon.MiddleClick:
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
        file = "workpackages.json"
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
        file = "workpackages.json"
        if self.workPackages:
            workPackages = []
            for wp in self.workPackages:
                workPackages.append(wp.asJson())
            with open(file, "w") as fp:
                json.dump(workPackages, fp, indent=4)

    def newWorkPackage(self):
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

    def removeWorkPackage(self, wp):
        self.workPackages.remove(wp)
        self.createTrayMenu()

    def openWorkPackageView(self):
        self.workPackageView.setVisible(self.workpackagesButton.isChecked())

    def onSettingsClicked(self):
        if self.settings.exec():
            oldConfig = self.config
            self.config = self.settings.getConfig()
            wplChanged = self.config["wpLocation"] != oldConfig["wpLocation"]
            self.updateDateLabels()
            self.app.setQuitOnLastWindowClosed(not self.config["minimize"])
            if wplChanged:
                self.workPackageView.hide()
                wpl = self.config["wpLocation"]
                if wpl < 2:
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

    def openDetailTimesDialog(self):
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
                print(officeTime / totalTime * 100, self.config["dailyOfficePercentage"])
                self.HOCheckBoxes[self.dateButtons.index(pushButton)].setChecked(
                    officeTime / totalTime * 100 <= self.config["dailyOfficePercentage"]
                )
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
                self.trayActions["Start Day"].setDisabled(self.starttimeTime[x].time().msecsSinceStartOfDay())
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

                self.detailInputs(x)

                calcNeeded = seconds[dayOfWeek] and (
                    not self.vacationCheckBoxes[x].isChecked()
                    or self.vacationCheckBoxes[x].isChecked()
                    and self.vacationCheckBoxes[x].isZA
                )
                if calcNeeded:
                    self.starttimeTime[x].show()
                    self.endtimeTime[x].show()
                    self.autoTimes[x].show()
                    self.diffTimeLabels[x].show()
                    self.fullTimeLabels[x].show()
                    if self.vacationCheckBoxes[x].isChecked() and self.vacationCheckBoxes[x].isZA:
                        self.starttimeTime[x].setEnabled(False)
                        self.endtimeTime[x].setEnabled(False)
                        self.autoTimes[x].setEnabled(False)
                        self.breakCheckBoxes[x].hide()
                        self.HOCheckBoxes[x].hide()
                    else:
                        self.breakCheckBoxes[x].show()
                        self.HOCheckBoxes[x].show()

                    self.addLunchBreak(x, seconds[dayOfWeek])

                    # calc diff time
                    newStart = self.starttimeTime[x].time().addSecs(seconds[dayOfWeek])
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

                    if x + 1 <= today.day() or month is not today.month():
                        ZA += diff

                    # planned total hours per day:
                    pTH += seconds[dayOfWeek]

                    # worked hours per day:
                    tH += self.workedDayHours(x)
                else:
                    self.starttimeTime[x].hide()
                    self.endtimeTime[x].hide()
                    self.autoTimes[x].hide()
                    self.diffTimeLabels[x].hide()
                    self.fullTimeLabels[x].hide()
                    self.breakCheckBoxes[x].hide()
                    self.HOCheckBoxes[x].hide()
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
                self.HOCheckBoxes[x].hide()

        self.setZAHours(ZA)
        self.hoursTotal.setText(f"{tH // 3600}:{tH % 3600 // 60:002}/{pTH // 3600}:{pTH % 3600 // 60:002}")
        self.updateonSitePercentage()

    def updateonSitePercentage(self):
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

    def detailInputs(self, index: int):
        if self.dateButtons[index].timestamps[0] and self.dateButtons[index].timestamps[1]:
            self.starttimeTime[index].setTime(QtCore.QTime(minutesToTime(self.dateButtons[index].timestamps[0])))
            self.endtimeTime[index].setTime(QtCore.QTime(minutesToTime(self.dateButtons[index].timestamps[1])))
            self.starttimeTime[index].setEnabled(False)
            self.endtimeTime[index].setEnabled(False)
        else:
            self.starttimeTime[index].setEnabled(True)
            self.endtimeTime[index].setEnabled(True)

    def addLunchBreak(self, index: int, daySeconds: int):
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

    def workedDayHours(self, index: int):
        if self.starttimeTime[index].time().msecsSinceStartOfDay():
            diff = self.starttimeTime[index].time().secsTo(self.endtimeTime[index].time())
            if self.breakCheckBoxes[index].isChecked():
                diff -= self.config["lunchBreak"] * 60
            diffTime = QtCore.QTime(0, 0).addSecs(diff)
            self.fullTimeLabels[index].setText(diffTime.toString("hh:mm"))
            # mark the time red if it is more than 10.5 hours
            if diff > 36000:
                self.fullTimeLabels[index].setStyleSheet("color: red")
            else:
                self.fullTimeLabels[index].setStyleSheet("color: black")
            return diff
        else:
            self.fullTimeLabels[index].setText("")
            return 0

    def setZAHours(self, za: int):
        if za < 0:
            za = abs(za)
            self.hoursZA.setText(f"ZA: -{za // 3600}:{za % 3600 // 60:002}")
        elif za >= 0:
            self.hoursZA.setText(f"ZA: {za // 3600}:{za % 3600 // 60:002}")

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
            ho = self.HOCheckBoxes[x].isChecked()
            timestamps = self.dateButtons[x].timestamps
            za = v and self.vacationCheckBoxes[x].isZA
            data[f"{x}"] = [s, e, v, lb, ho, timestamps, za]
        if not os.path.exists("data"):
            os.mkdir("data")
        with open(rf"data\{data['MonthAndYear']}.json", "w") as fp:
            json.dump(data, fp, indent=4)

    def loadMonth(self):
        # load all data if possible
        file = rf"data\{self.oldDateTime.toString('MMMM yyyy')}.json"
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
                        ho = True
                        timestamps = [0, 0, [(0, 0)] * 10]
                        za = False
                    elif len(_data) == 4:
                        s, e, v, lb = _data
                        ho = True
                        timestamps = [0, 0, [(0, 0)] * 10]
                        za = False
                    elif len(_data) == 5:
                        s, e, v, lb, timestamps = _data
                        ho = True
                        za = False
                    elif len(_data) == 6:
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


class WorkPackage(QtGui.QAction):
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

    def __init__(self, parent=None, workpackage=None):
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
            self.setStyleSheet("background: LightGreen; color: #000000")
            self.setAutoFillBackground(True)
        else:
            self.startStopButton.setChecked(False)
            self.startStopButton.setIcon(QtGui.QPixmap(resource_path("play.png")))
            self.setStyleSheet("background: None")
            self.setStyleSheet("")

    def openUrl(self):
        if self._workpackage.ticket:
            urlStart = self.getMainWindow(self.parent()).config["url"]
            url = f"{urlStart}/browse/{self._workpackage.ticket}"
            QtGui.QDesktopServices.openUrl(QtCore.QUrl(url))
        else:
            name, ok = QtWidgets.QInputDialog.getText(
                self, "Ticket-ID (e.g. GMCTC-1234)", "Ticket", QtWidgets.QLineEdit.Normal
            )
            if ok:
                self._workpackage.ticket = name
                self.ticket.setText(name)

    def startStopClicked(self, checked=False):
        self.started.emit(checked)

    def editWP(self):
        WorkPackageEditDialog(self, self._workpackage).exec()

    def removeWP(self):
        if self.getTotalTime() > 60 or self.isActive():
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
            if JiraWriteLog(mainWindow.config, wp.ticket, loggedTime):
                print("log written - deleting logged time")
                wp.resetTime()
                mainWindow.saveWorkPackages()


class WorkPackageView(QtWidgets.QDialog):
    def __init__(self, parent):
        super().__init__(
            parent,
            QtCore.Qt.WindowCloseButtonHint | QtCore.Qt.WindowTitleHint | QtCore.Qt.WindowSystemMenuHint,
        )
        self.setWindowTitle("Work Packages")
        wps = self.parent().workPackages
        self.splitter = QtWidgets.QVBoxLayout()
        for wp in wps:
            print(f"workpackage {wp}")
            self.splitter.addWidget((WorkPackageWidget(self, wp)))
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
        # mainSplitter.addLayout(self.splitter)
        mainSplitter.addLayout(hSplitter)

        self.setLayout(mainSplitter)

    def addWorkPackage(self, wp):
        self.splitter.removeItem(self.splitter.itemAt(self.splitter.count() - 1))
        self.splitter.addWidget((WorkPackageWidget(self, wp)))
        self.splitter.addStretch(100)
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

    def getMainWindow(self, parent):
        if parent:
            if isinstance(parent, MainWindow):
                return parent
            else:
                return self.getMainWindow(parent.parent())
        else:
            return None

    def closeEvent(self, event):
        mainWnd = self.getMainWindow(self.parent())
        mainWnd.workpackagesButton.setChecked(False)
        super().closeEvent(event)


class WorkPackageEditDialog(QtWidgets.QDialog):
    def __init__(self, parent, workpackage):
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
        if self.workpackage.name != self.nameLE.text() and self.nameLE.text() in [
            wp.name for wp in mainWindow.workPackages
        ]:
            self.notUnique.setVisible(True)
            return
        self.workpackage.name = self.nameLE.text()
        self.workpackage.ticket = self.ticketLE.text()
        if not self.workpackage.isChecked():
            self.workpackage.loggedTime = (
                (self.dayEdit.value() * 60 * 60 * 24)
                + (self.hourEdit.value() * 60 * 60)
                + (self.minuteEdit.value() * 60)
            )
        super().accept()


def start_GUI():
    """Starts the GUI"""
    app = QtWidgets.QApplication(sys.argv)
    app.setStyleSheet("QLabel { qproperty-alignment: AlignCenter; }")
    app.setApplicationName("Time Converter")
    app.setWindowIcon(QtGui.QPixmap(resource_path("time.png")))
    app.setQuitOnLastWindowClosed(False)

    lockfile = "lockfile"
    start = True
    if os.path.exists(lockfile):
        with open(lockfile, "r") as fp:
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
                        "Do you want to start a second instance?\n\n"
                        "It might lead to inconsistencies or overwriting of time data!",
                        QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                        QtWidgets.QMessageBox.No,
                    )
                if QtWidgets.QMessageBox.No == ret:
                    start = False
                    print("Aborted starting")
                if QtWidgets.QMessageBox.Open == ret:
                    start = False
                    shell = win32com.client.Dispatch("WScript.Shell")
                    shell.SendKeys("%")
                    win32gui.SetForegroundWindow(window)
                    print("Aborted starting - Showed other instance instead")

    if start:
        with open(lockfile, "w") as fp:
            fp.write(str(os.getpid()))

        window = MainWindow(app=app)
        window.setWindowIcon(QtGui.QPixmap(resource_path("time.png")))
        window.show()

        app.exec()
        window.saveWorkPackages()
        os.remove(lockfile)


def windowEnumerationHandler(hwnd, top_windows):
    top_windows.append((hwnd, win32gui.GetWindowText(hwnd), win32process.GetWindowThreadProcessId(hwnd)[1]))


def findWindow(pid):
    result = None
    top_windows = []
    win32gui.EnumWindows(windowEnumerationHandler, top_windows)
    for i in top_windows:
        if pid == i[2] and "UltraTime" == i[1]:
            result = i[0]
    return result


if __name__ == "__main__":
    start_GUI()
