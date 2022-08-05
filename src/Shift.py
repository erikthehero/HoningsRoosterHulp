import os
from datetime import datetime, timedelta
from unicodedata import name

class Shift:
    def __init__(self, name, abbreviation, start_date, end_date):
        self.name = name
        self.abbreviation = abbreviation
        self.start_date = start_date
        self.end_date = end_date
        self.work_hours = (self.end_date-self.start_date).total_seconds() / 3600.0

    def __str__(self):
        if self.abbreviation == "a" or self.abbreviation == "n": 
            return f"{self.name}\t\t{self.abbreviation}  {self.start_date} {self.end_date}"
        else:
            return f"{self.name}\t{self.abbreviation} {self.start_date} {self.end_date}"

class ShiftType:
    def __init__(self, name, abbreviation, start_time, end_time, count):
        self.name = name
        self.abbreviation = abbreviation
        self.start_time = start_time
        self.end_time = end_time
        self.count = count
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
    def getCount(self):
        return self.count

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

    def GetTypes(self):
        return ["dk0", "dm0", "dl0", "dl1", "a0", "a1", "n0", "n1"]

    def ConvertDayStrToDayNum(self, day_str):
        if day_str == "ma":
            return 0
        elif day_str == "di":
            return 1
        elif day_str == "wo":
            return 2
        elif day_str == "do":
            return 3
        elif day_str == "vr":
            return 4
        elif day_str == "za":
            return 5
        elif day_str == "zo":
            return 6

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
        delta_n = 0
        while curr_date < end_date:
            for st in self.types:
                for c in range(st.getCount()):
                    if st.getAbbreviation() == "n":
                        shifts.append(Shift(f"{st.getName()}_{c}", st.getAbbreviation()+str(c), st.getStartTime() + timedelta(delta_n), st.getEndTime() + timedelta(delta_n+1)))
                    else:
                        shifts.append(Shift(f"{st.getName()}_{c}", st.getAbbreviation()+str(c), st.getStartTime() + timedelta(delta_n), st.getEndTime() + timedelta(delta_n)))
            curr_date += delta
            delta_n += 1
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
                name         = line_parts[0].replace("\t", "").replace("\n", "")
                abbreviation = line_parts[1].replace("\t", "").replace(" ", "").replace("\n", "")
                start_time   = datetime.strptime(f"{self.year}.{self.month:02d}." + line_parts[2].replace("\t", "").replace(" ", "").replace("\n", ""), "%Y.%m.%H.%M")
                end_time     = datetime.strptime(f"{self.year}.{self.month:02d}." + line_parts[3].replace("\t", "").replace(" ", "").replace("\n", ""), "%Y.%m.%H.%M")
                count        = int(line_parts[4])
                types.append(ShiftType(name, abbreviation, start_time, end_time, count))
        return types