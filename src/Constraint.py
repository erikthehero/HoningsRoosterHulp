from calendar import day_abbr
from datetime import datetime
import os

class Constraint:
    def __init__(self, name=None, full_date=None, day=None, shift=None, do_assign=None, streakmin=None, streakmax=None, max_sum=None, is_hard=None):
        self.name = name
        self.full_date = full_date
        self.day = day
        self.shift= shift
        self.do_assign = do_assign
        self.streakmin = streakmin
        self.streakmax = streakmax
        self.max_sum = max_sum
        self.is_hard = is_hard

    def __str__(self):
        return f"name:{self.name}, date:{self.full_date}, day:{self.day}, shift:{self.shift}, do_assign:{self.do_assign}, streakmin:{self.streakmin}, streakmax:{self.streakmax}, is_hard:{self.is_hard}"

class Constraints:
    def __init__(self, fn):
        self.fn = fn
        self.requests = self._InitRequestsFromFile(self.fn)
        pass

    def __str__(self):
        for request in self.requests:
            print(request)
        return ""

    def _InitRequestsFromFile(self, fn):
        assert(fn)
        assert(os.path.isfile(fn))

        constraints = []
        with open(fn) as f:
            while(True):
                line = f.readline()
                
                if not line:
                    break

                if line == "\n":
                    continue

                if line.startswith("#"): # comment
                    continue
                
                line_parts = line.split(";") #TODO: implement this
                name, full_date, day, shift, do_assign, streakmin, streakmax, max_sum, is_hard = None, None, None, None, None, None, None, None, None
                for i, part in enumerate(line_parts):
                    clean_part = part.replace("\t", "").replace(" ", "").replace("\n", "")
                    if not clean_part:
                        continue
                    if i == 0:
                        name = clean_part
                    elif i == 1:
                        full_date = datetime.strptime(clean_part, "%m-%d-%Y")
                    elif i == 2:
                        day = clean_part
                    elif i == 3:
                        shift = clean_part
                    elif i == 4:
                        do_assign = int(clean_part) == 1
                    elif i == 5:
                        streakmin = int(clean_part)
                    elif i == 6:
                        streakmax = int(clean_part)
                    elif i == 7:
                        max_sum   = int(clean_part)
                    elif i == 8:
                        is_hard   = int(clean_part) == 1
                constraints.append(Constraint(name, full_date, day, shift, do_assign, streakmin, streakmax, max_sum, is_hard))
        return constraints
