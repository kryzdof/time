import sys
import json
import os
import shutil
import calendar

from itertools import zip_longest

try:
    from PySide2 import QtCore, QtWidgets, QtGui
except ImportError:
    print("PySide2 not found - installing now")
    import subprocess

    # subprocess.check_call([sys.executable, "-m", "pip", "install", "PySide2==5.11.2"])
    #
    subprocess.check_call([sys.executable, "-m", "pip", "install", "PySide2==5.11.2",
                           "--index-url", r"https://eu.artifactory.conti.de/api/pypi/i_bs_ultra_tools_pypi_l/simple",
                           "--extra-index-url", "https://pypi.python.org/simple", "--no-cache-dir"])
    from PySide2 import QtCore, QtWidgets, QtGui


def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS,
        # and places our data files in a folder relative to that temp
        # folder named as specified in the datas tuple in the spec file
        print(sys._MEIPASS)
        print(sys)
        base_path = os.path.join(sys._MEIPASS, 'pics')
    except Exception:
        # sys._MEIPASS is not defined, so use the original path
        base_path = os.path.join(os.path.curdir, "pics")

    return os.path.join(base_path, relative_path)


def timeInMinutes(time):
    return time.hour() * 60 + time.minute()


def minutesInTime(minutes):
    return QtCore.QTime(minutes // 60, minutes % 60)


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
            t = QtCore.QTime(minutesInTime(timestamps[0]))
            startTimes = QtWidgets.QTimeEdit(t)
            startTimes.setDisplayFormat("hh:mm")
            startTimes.setWrapping(True)
            startTimes.editingFinished.connect(self.updateDiffs)
            self.startTimes.append(startTimes)
            mainLayout.addWidget(startTimes, x + 1, 1)
            autoTime = QtWidgets.QPushButton(QtGui.QPixmap(resource_path("time.png")), "")
            autoTime.QTimeReference = startTimes
            autoTime.clicked.connect(self.updateAutoTime)
            mainLayout.addWidget(autoTime, x + 1, 0)

            t = QtCore.QTime(minutesInTime(timestamps[1]))
            endTimes = QtWidgets.QTimeEdit(t)
            endTimes.setDisplayFormat("hh:mm")
            endTimes.setWrapping(True)
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
            t = QtCore.QTime(minutesInTime(timestamps[0]))
            self.startTimes[x].setTime(t)
            t = QtCore.QTime(minutesInTime(timestamps[1]))
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
            timeStamps.append((timeInMinutes(self.startTimes[x].time()), timeInMinutes(self.endTimes[x].time())))
        return timeInMinutes(totalStart), timeInMinutes(totalEnd), timeStamps


class SettingsDialog(QtWidgets.QDialog):
    def __init__(self, parent):
        super().__init__(parent=parent)

        self.config = {}

        self.setWindowTitle("Settings")
        mainLayout = QtWidgets.QVBoxLayout()

        timeSettingsLayout = QtWidgets.QGridLayout()
        timeSettingsWidgets = QtWidgets.QGroupBox("Time Settings")

        for x, dayStr in enumerate([d for d in calendar.day_name]):
            label = QtWidgets.QLabel(dayStr)
            timeSettingsLayout.addWidget(label, x + 1, 0)

        self.workingTimes = []
        for x in range(1, 8):
            if x < 4:
                t = QtCore.QTime(6, 10)
            elif x < 6:
                t = QtCore.QTime(6, 9)
            else:
                t = QtCore.QTime(0, 0)
            workingTime = QtWidgets.QTimeEdit(t)
            workingTime.setDisplayFormat("hh:mm")
            workingTime.setWrapping(True)
            self.workingTimes.append(workingTime)
            timeSettingsLayout.addWidget(workingTime, x, 1)

        timeSettingsWidgets.setLayout(timeSettingsLayout)

        lunchSettingsLayout = QtWidgets.QGridLayout()
        lunchSettingsWidgets = QtWidgets.QGroupBox("Lunch Settings")

        label = QtWidgets.QLabel("Normal Lunch Break")
        lunchSettingsLayout.addWidget(label, 0, 0)
        self.lunchTime = QtWidgets.QTimeEdit(QtCore.QTime(0, 30))
        self.lunchTime.setDisplayFormat("hh:mm")
        self.lunchTime.setWrapping(True)
        lunchSettingsLayout.addWidget(self.lunchTime, 0, 1)

        lunchSettingsWidgets.setLayout(lunchSettingsLayout)

        buttonbox = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        buttonbox.accepted.connect(self.accept)
        buttonbox.rejected.connect(self.reject)

        mainLayout.addWidget(timeSettingsWidgets)
        mainLayout.addWidget(lunchSettingsWidgets)
        mainLayout.addWidget(buttonbox)
        self.setLayout(mainLayout)

    def accept(self):
        self.config["hours"] = [timeInMinutes(QtCore.QTime(0, 0))] + [timeInMinutes(x.time()) for x in
                                                                      self.workingTimes]
        self.config["lunchBreak"] = timeInMinutes(self.lunchTime.time())
        self.saveConfig()
        super().accept()

    def saveConfig(self):
        file = f"settings.json"
        with open(file, "w") as fp:
            json.dump(self.config, fp)

    def loadConfig(self):
        file = f"settings.json"
        config = None
        while True:
            try:
                with open(file, "r") as fp:
                    config = json.load(fp)
                return config
            except:
                return config

    def getConfig(self):
        config = None
        while config is None:
            config = self.loadConfig()
            if not config:
                self.exec_()
        cfg = {"hours": [minutesInTime(x) for x in config["hours"]],
               "lunchBreak": config["lunchBreak"]}
        return cfg


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, parent=None):
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

        topLine.setLayout(topLineLayout)

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

            starttime = QtWidgets.QTimeEdit()
            starttime.setDisplayFormat("hh:mm")
            starttime.editingFinished.connect(self.updateDateLabels)
            starttime.setWrapping(True)
            self.starttimeTime.append(starttime)
            mainWidgetLayout.addWidget(starttime, days, 2)

            endtime = QtWidgets.QTimeEdit()
            endtime.setDisplayFormat("hh:mm")
            endtime.editingFinished.connect(self.updateDateLabels)
            endtime.setWrapping(True)
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

        scrollarea = QtWidgets.QScrollArea()
        scrollarea.setWidget(mainWidget)
        scrollarea.setWidgetResizable(True)
        scrollarea.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scrollarea.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        scrollarea.setSizeAdjustPolicy(scrollarea.AdjustToContents)
        scrollarea.ensureWidgetVisible(self.dateButtons[self.datetime.date().day() - 1], 200, 200)

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
        splitter.addWidget(scrollarea)
        splitter.setChildrenCollapsible(False)
        splitter.handle(1).setCursor(QtCore.Qt.ArrowCursor)

        self.settings = SettingsDialog(self)

        self.setCentralWidget(splitter)
        self.loadMonth()
        self.config = self.settings.getConfig()
        self.scroll = scrollarea
        self.updateDateLabels()
        self.resize(QtCore.QSize(mainWidget.sizeHint().width(), self.size().height() + 50))

    def onSettingsClicked(self):
        if self.settings.exec_():
            self.config = self.settings.getConfig()
            self.updateDateLabels()

    def openDetailTimesDialog(self):
        pushButton = self.sender()
        dlg = DetailTimesDialog(self, pushButton.text(), pushButton.timestamps[2])
        if dlg.exec_():
            pushButton.timestamps = dlg.getDetails()
            self.updateDateLabels()

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
                self.dateButtons[x].setText(f"{dayString[dayOfWeek]} {x+1}.{month}.{year}")
                # self.dataButtons[x].set
                self.plannedTimeLabels[x].setText(hours[dayOfWeek])

                if x + 1 < today.day() and month == today.month():
                    self.dateButtons[x].setStyleSheet("color: rgb(100, 100, 100)")
                elif x + 1 == today.day() and month == today.month():
                    self.dateButtons[x].setStyleSheet("color: red")
                else:
                    self.dateButtons[x].setStyleSheet("color: black")

                if self.dateButtons[x].timestamps[0] and self.dateButtons[x].timestamps[1]:
                    self.starttimeTime[x].setTime(QtCore.QTime(minutesInTime(self.dateButtons[x].timestamps[0])))
                    self.endtimeTime[x].setTime(QtCore.QTime(minutesInTime(self.dateButtons[x].timestamps[1])))
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

                    if not self.endtimeTime[x].time().msecsSinceStartOfDay() and self.starttimeTime[
                        x].time().msecsSinceStartOfDay():
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
            self.hoursZA.setText(f"ZA: -{ZA//3600}:{ZA%3600//60:002}")
        elif ZA >= 0:
            self.hoursZA.setText(f"ZA: {ZA//3600}:{ZA%3600//60:002}")
        self.hoursTotal.setText(f'{tH//3600}:{tH%3600//60:002}/{pTH//3600}:{pTH%3600//60:002}')

    def onMonthChanged(self):
        self.saveMonth()
        self.oldDateTime = self.datetime.date()
        self.loadMonth()
        self.updateDateLabels()

    def saveMonth(self):
        # gather all data and store it somewhere
        data = {"MonthAndYear": self.oldDateTime.toString("MMMM yyyy")}
        for x in range(self.oldDateTime.daysInMonth()):
            s = timeInMinutes(self.starttimeTime[x].time())
            e = timeInMinutes(self.endtimeTime[x].time())
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
                    self.starttimeTime[x].setTime(minutesInTime(s))
                    self.endtimeTime[x].setTime(minutesInTime(e))
                    self.vacationCheckBoxes[x].setChecked(v)
                    self.breakCheckBoxes[x].setChecked(lb)
                    self.dateButtons[x].timestamps = timestamps
        else:
            date = self.datetime.date()
            for x in range(date.daysInMonth()):
                self.starttimeTime[x].setTime(minutesInTime(0))
                self.endtimeTime[x].setTime(minutesInTime(0))
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


def start_GUI():
    """Starts the GUI
    """
    app = QtWidgets.QApplication(sys.argv)
    app.setStyleSheet("QLabel { qproperty-alignment: AlignCenter; }")
    app.setApplicationName('Time Converter')
    window = MainWindow()
    window.show()
    app.exec_()


def main():
    start_GUI()


if __name__ == '__main__':
    main()
