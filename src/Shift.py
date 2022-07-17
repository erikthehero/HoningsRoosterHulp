import os
from datetime import datetime, timedelta
from unicodedata import name
from Calendar import Calendar

class Shift:
    def __init__(self, name, abbreviation, start_date, end_date):
        self.name = name
        self.abbreviation = abbreviation
        self.start_date = start_date
        self.end_date = end_date

    def __str__(self):
        return f"{self.name} {self.abbreviation} {self.start_date} {self.end_date}"

class ShiftType:
    def __init__(self, name, abbreviation, start_time, end_time):
        self.name = name
        self.abbreviation = abbreviation
        self.start_time = start_time
        self.end_time = end_time
    def __str__(self):
        return f"{self.name} {self.abbreviation} {self.start_time} {self.end_time}"
    def getName(self):
        return self.name
    def getAbbreviation(self):
        return self.abbreviation
    def getStartTime(self):
        return self.start_time
    def getEndTime(self):
        return self.end_time

class Shifts:
    def __init__(self, fn, year, month):
        self.fn = fn
        self.month = month
        self.year = year
        self.types = self._InitTypesFromFile()
        self.shifts = self._initShiftsFromMonth()
        return

    def __str__(self):
        for shift in self.shifts:
            print(shift)
        return ""

    def printTypes(self):
        for t in self.types:
            print(t)
        return ""

    def _initShiftsFromMonth(self):
        shifts = []
        if self.month == 12:
            end_month = 1
            end_year = self.year + 1
        else:
            end_month = self.month + 1
            end_year = self.year

        curr_date = datetime(self.year, self.month, 1)
        end_date = datetime(end_year, end_month, 1)
        delta = timedelta(days=1)

        while curr_date < end_date:
            for st in self.types:
                shifts.append(Shift(st.getName(), st.getAbbreviation(), st.getStartTime(), st.getEndTime()))
            curr_date += delta
        return shifts

    def _InitTypesFromFile(self):
        assert(self.fn)
        assert(os.path.isfile(self.fn))

        types = []
        with open(self.fn) as f:
            while(True):
                line = f.readline()
                
                if not line:
                    break

                if line.startswith("#"): # comment
                    continue
                
                line_parts = line.split(";")
                name         = line_parts[0]
                abbreviation = line_parts[1]
                start_time   = datetime.strptime(f"{self.year}.{self.month:02d}." + line_parts[2].replace("\t", "").replace(" ", "").replace("\n", ""), "%Y.%m.%H.%M")
                end_time     = datetime.strptime(f"{self.year}.{self.month:02d}." + line_parts[3].replace("\t", "").replace(" ", "").replace("\n", ""), "%Y.%m.%H.%M")
                types.append(ShiftType(name, abbreviation, start_time, end_time))
        return types