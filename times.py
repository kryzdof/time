import sys
import json
import os
import shutil
import calendar

from PySide2 import QtCore, QtWidgets, QtGui


def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS,
        # and places our data files in a folder relative to that temp
        # folder named as specified in the datas tuple in the spec file
        base_path = os.path.join(sys._MEIPASS, 'data')
    except Exception:
        # sys._MEIPASS is not defined, so use the original path
        base_path = 'D:\\diverses\\time'

    return os.path.join(base_path, relative_path)


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, parent=None):
        super(MainWindow, self).__init__(parent)

        self.setObjectName("Time Converter")
        self.setWindowTitle("Time Converter")
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
        topLineLayout.addWidget(self.hoursZA, 0, 6)
        topLineLayout.addWidget(self.hoursTotal, 0, 8)

        topLine.setLayout(topLineLayout)

        mainWidget = QtWidgets.QGroupBox()
        mainWidgetLayout = QtWidgets.QGridLayout()
        self.dateLabels = []
        self.plannedTimeLabels = []
        self.starttimeTime = []
        self.endtimeTime = []
        self.autoTimes = []
        self.diffTimeLabels = []
        self.vacationCheckBoxes = []
        self.starttimeTimeC = []
        self.endtimeTimeC = []
        self.fullTimeLabels = []
        for days in range(31):
            label = QtWidgets.QLabel(str(days))
            self.dateLabels.append(label)
            mainWidgetLayout.addWidget(label, days, 0)

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
            # autoTime = QtWidgets.QPushButton("TEWSA")
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

            label = QtWidgets.QLabel("")
            self.starttimeTimeC.append(label)
            mainWidgetLayout.addWidget(label, days, 9)

            label = QtWidgets.QLabel("")
            self.endtimeTimeC.append(label)
            mainWidgetLayout.addWidget(label, days, 10)

        label = QtWidgets.QLabel("")
        mainWidgetLayout.addWidget(label, 0, 11)

        mainWidget.setLayout(mainWidgetLayout)

        scrollarea = QtWidgets.QScrollArea()
        scrollarea.setWidget(mainWidget)
        scrollarea.setWidgetResizable(True)
        scrollarea.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scrollarea.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        scrollarea.setSizeAdjustPolicy(scrollarea.AdjustToContents)
        scrollarea.ensureWidgetVisible(self.dateLabels[self.datetime.date().day() - 1], 200, 200)

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

        self.setCentralWidget(splitter)
        self.loadMonth()
        # self.config = self.getConfig()
        self.scroll = scrollarea
        self.updateDateLabels()
        self.resize(QtCore.QSize(mainWidget.sizeHint().width(), self.size().height()))

    def getConfig(self):
        file = f"settings.json"
        if os.path.exists(file):
            with open(file, "r") as fp:
                config = json.load(fp)
        else:
            # create config
            long = QtCore.QTime(8, 15)
            short = QtCore.QTime(5, 30)
            config = dict()
            config["dayString"] = [""]+[d for d in calendar.day_abbr]
            config["hours"] = ["", long, long, long, long, short, "", ""]
            config["lunchbreak"] = QtCore.QTime(0, 30)
            date = self.datetime.date()
            for x in range(date.daysInMonth()):
                self.starttimeTime[x].setTime(self.minutesInTime(0))
                self.endtimeTime[x].setTime(self.minutesInTime(0))
        return config

    def updateDateLabels(self):
        dayString = ["", "Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
        long = QtCore.QTime(8, 15).toString("h:mm")
        short = QtCore.QTime(5, 30).toString("h:mm")
        hours = ["", long, long, long, long, short, "", ""]
        long = 31500
        short = 21600
        seconds = [0, long, long, long, long, short, 0, 0]

        date = self.datetime.date()
        month = date.month()
        year = date.year()
        today = QtCore.QDate.currentDate()

        ZA = 0
        tH = 0  # total hours worked
        pTH = 0  # planned total hours this month
        for x in range(31):
            if x < date.daysInMonth():
                self.dateLabels[x].show()
                self.plannedTimeLabels[x].show()
                self.vacationCheckBoxes[x].show()
                dayOfWeek = QtCore.QDate(year, month, x + 1).dayOfWeek()
                self.dateLabels[x].setText(f"{dayString[dayOfWeek]} {x+1}.{month}.{year}")
                self.plannedTimeLabels[x].setText(hours[dayOfWeek])

                if x + 1 < today.day() and month == today.month():
                    self.dateLabels[x].setStyleSheet("color: rgb(100, 100, 100)")
                elif x + 1 == today.day() and month == today.month():
                    self.dateLabels[x].setStyleSheet("color: red")
                else:
                    self.dateLabels[x].setStyleSheet("color: black")

                calcNeeded = seconds[dayOfWeek] and not self.vacationCheckBoxes[x].isChecked()
                if calcNeeded:
                    self.starttimeTime[x].show()
                    self.endtimeTime[x].show()
                    self.diffTimeLabels[x].show()
                    self.autoTimes[x].show()
                    self.diffTimeLabels[x].show()
                    self.starttimeTimeC[x].show()
                    self.endtimeTimeC[x].show()
                    self.fullTimeLabels[x].show()

                    if not self.endtimeTime[x].time().msecsSinceStartOfDay() and self.starttimeTime[
                            x].time().msecsSinceStartOfDay():
                        # no end time set yet but start time is --> automatically set endtime
                        startTimeSeconds = QtCore.QTime(0, 0).secsTo(self.starttimeTime[x].time())
                        diffTime = self.endtimeTime[x].time().addSecs(startTimeSeconds + seconds[dayOfWeek])
                        self.endtimeTime[x].setTime(diffTime)

                    # calc diff time
                    newStart = self.starttimeTime[x].time().addSecs(seconds[dayOfWeek])
                    diff = newStart.secsTo(self.endtimeTime[x].time())
                    # diff = self.starttimeTime[x].time().secsTo(self.endtimeTime[x].time())
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

                    # corrected times:
                    if self.starttimeTime[x].time().hour() >= 9:
                        tdiff = self.starttimeTime[x].time().hour() - 9
                        tdiffMin = self.starttimeTime[x].time().minute()
                        start = self.starttimeTime[x].time().addSecs(-(tdiff * 3600 + tdiffMin * 60))
                        end = self.endtimeTime[x].time().addSecs(-(tdiff * 3600 + tdiffMin * 60))
                        self.starttimeTimeC[x].setText(start.toString("hh:mm"))
                        self.endtimeTimeC[x].setText(end.toString("hh:mm"))
                    else:
                        self.starttimeTimeC[x].setText(self.starttimeTime[x].time().toString("hh:mm"))
                        self.endtimeTimeC[x].setText(self.endtimeTime[x].time().toString("hh:mm"))
                        end = self.endtimeTime[x].time()
                    # mark corrected end time if it is later than 19:00 or within core time
                    if end.hour() >= 19 and end.minute() > 0:
                        self.endtimeTimeC[x].setStyleSheet("color: red")
                    elif self.timeInMinutes(end) < (seconds[dayOfWeek] + 24300) // 60:
                        self.endtimeTimeC[x].setStyleSheet("color: blue")
                    else:
                        self.endtimeTimeC[x].setStyleSheet("color: black")

                    # planned total hours per day:
                    pTH += seconds[dayOfWeek]-1800

                    # worked hours per day:
                    if self.starttimeTime[x].time().msecsSinceStartOfDay():
                        diff = self.starttimeTime[x].time().secsTo(self.endtimeTime[x].time()) - 30 * 60
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
                    self.starttimeTimeC[x].hide()
                    self.endtimeTimeC[x].hide()
                    self.fullTimeLabels[x].hide()
            else:
                self.dateLabels[x].hide()
                self.plannedTimeLabels[x].hide()
                self.starttimeTime[x].hide()
                self.endtimeTime[x].hide()
                self.autoTimes[x].hide()
                self.diffTimeLabels[x].hide()
                self.vacationCheckBoxes[x].hide()
                self.starttimeTimeC[x].hide()
                self.endtimeTimeC[x].hide()
                self.fullTimeLabels[x].hide()
        if ZA < 0:
            print(ZA)
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
            s = self.timeInMinutes(self.starttimeTime[x].time())
            e = self.timeInMinutes(self.endtimeTime[x].time())
            v = self.vacationCheckBoxes[x].isChecked()
            data[f"{x}"] = [s, e, v]
        print(data)
        with open(f"{data['MonthAndYear']}.json", "w") as fp:
            json.dump(data, fp)

    def loadMonth(self):
        # load all data if possible
        file = f"{self.oldDateTime.toString('MMMM yyyy')}.json"
        if os.path.exists(file):
            shutil.copy(file, file.replace(".json", ".json.bak"))
            with open(f"{self.oldDateTime.toString('MMMM yyyy')}.json", "r") as fp:
                data = json.load(fp)
                date = self.datetime.date()
                for x in range(date.daysInMonth()):
                    s, e, v = data[f"{x}"]
                    self.starttimeTime[x].setTime(self.minutesInTime(s))
                    self.endtimeTime[x].setTime(self.minutesInTime(e))
                    self.vacationCheckBoxes[x].setChecked(v)
                print("loading", data)
        else:
            date = self.datetime.date()
            for x in range(date.daysInMonth()):
                self.starttimeTime[x].setTime(self.minutesInTime(0))
                self.endtimeTime[x].setTime(self.minutesInTime(0))

    @staticmethod
    def timeInMinutes(time):
        return time.hour() * 60 + time.minute()

    @staticmethod
    def minutesInTime(minutes):
        return QtCore.QTime(minutes // 60, minutes % 60)

    def autoUpdateTime(self):
        x = int(self.sender().objectName())
        h = QtCore.QTime.currentTime().hour()
        m = QtCore.QTime.currentTime().minute()
        if not self.starttimeTime[x].time().msecsSinceStartOfDay():
            m = m - m % 5
            self.starttimeTime[x].setTime(QtCore.QTime(h, m))
        else:
            m = m + 5 - m % 5
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
    app.setApplicationName('Time Converter')
    window = MainWindow()
    window.show()
    app.exec_()


def main():
    start_GUI()


if __name__ == '__main__':
    main()
