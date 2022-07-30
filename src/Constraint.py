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
    # https://ambtenarensalaris.nl/wp-content/uploads/2022/07/Cao-Gehandicaptenzorg-2021-2024.pdf
    def __init__(self, fn):
        self.fn = fn
        self.requests = self._InitRequestsFromFile(self.fn)

    def __str__(self):
        for request in self.requests:
            print(request)
        return ""

    def add_fill_every_shift_constraint(self, model, nurses, shifts, work):
        # every shift should be filled by one and only one nurse
        for s,_ in enumerate(shifts.shifts):
            model.Add(sum(work[n, s] for n,_ in enumerate(nurses.nurses)) == 1)
        return

    def add_one_shift_per_day_constraint(self, model, nurses, shifts, work):
        # every nurse should work one and only one shift per day
        shift_day_bundles = self._GetShiftDayBundles(shifts)
        for bundle in shift_day_bundles:
            for n,_ in enumerate(nurses.nurses):
                model.Add(sum(work[n, s] for s in bundle) <= 1)
        return

    def add_rest_after_night_shift_constraint(self, model, nurses, shifts, work):
        # pp92 CAO Gehandicaptenzorg 2021-2024: 14uur rust na nachtdienst
        bundles_total = [self._GetFollowUpShiftsFromShiftType("n0", ["dk0", "dm0", "dl0", "dl1", "a0", "a1"], shifts), self._GetFollowUpShiftsFromShiftType("n1", ["dk0", "dm0", "dl0", "dl1", "a0", "a1"], shifts)]
        
        for bundles in bundles_total:
            for n,_ in enumerate(nurses.nurses): # n0|n1 -> sum(dk0, dm0, dl0, dl1, a0, a1) == 0
                for bundle in bundles:
                    model.Add(sum(work[n,s] for s in bundle[1])==0).OnlyEnforceIf(work[n,bundle[0]])
        return

    def add_weekly_contract_hours_constraint(self, model, nurses, shifts, work):
        hard_min = 0
        shift_week_bundles = self._GetShiftWeekBundles(shifts)
        cost_variables = []
        cost_coefficients = []
        i = 0
        for n,nurse in enumerate(nurses.nurses):
            soft_min = nurse.contract
            soft_max = nurse.contract
            if nurse.zzper:
                max_cost = 2
                min_cost = 2
            else:
                max_cost = 1
                min_cost = 1

            for bundle in shift_week_bundles:
                if i == 1:
                    j = 0
                hard_max = 60 # pp92 CAO Gehandicaptenzorg 2021-2024: max 60 urige werkweek
                cv, cc = self._Add_soft_sum_constraint(n, bundle, shifts, model, work, hard_min, soft_min, min_cost, soft_max, hard_max, max_cost, "")
                cost_variables.extend(cv)
                cost_coefficients.extend(cc)
                i+=1

        return cost_variables, cost_coefficients

    def _Add_soft_sum_constraint(self, n, bundle, shifts, model, work, hard_min, soft_min, min_cost, soft_max, hard_max, max_cost, prefix):
        cost_variables = []
        cost_coefficients = []
        week_faction = len(bundle) / 56.0
        sum_var = model.NewIntVar(hard_min, hard_max, '')
        model.Add(sum_var == sum(work[n, s] * int((shifts.shifts[s].work_hours * week_faction)) for s in bundle)) # sum of hours worked for this week

        # Penalize sums below the soft_min target.
        if soft_min > hard_min and min_cost > 0:
            delta = model.NewIntVar(-60, 60, '')
            model.Add(delta == int(soft_min) - sum_var)
            # TODO(user): Compare efficiency with only excess >= soft_min - sum_var.
            excess = model.NewIntVar(0, 60, prefix + ': under_sum')
            model.AddMaxEquality(excess, [delta, 0])
            cost_variables.append(excess)
            cost_coefficients.append(min_cost)

        # Penalize sums above the soft_max target.
        if soft_max < hard_max and max_cost > 0:
            delta = model.NewIntVar(-60, 60, '')
            model.Add(delta == sum_var - int(soft_max))
            excess = model.NewIntVar(0, 60, prefix + ': over_sum')
            model.AddMaxEquality(excess, [delta, 0])
            cost_variables.append(excess)
            cost_coefficients.append(max_cost)
        
        return cost_variables, cost_coefficients

    def _GetFollowUpShiftsFromShiftType(self, primary_type, target_types, shifts):
        shift_follow_up_bundles = []
        follow_up_bundle = []
        target_bundle = []
        for s,shift in enumerate(shifts.shifts):
            if shift.abbreviation == primary_type:
                if follow_up_bundle and target_bundle:
                    follow_up_bundle.append(target_bundle)
                    shift_follow_up_bundles.append(follow_up_bundle)
                follow_up_bundle = [s]
                target_bundle = []

            if not follow_up_bundle:
                continue

            if shift.abbreviation in target_types:
                target_bundle.append(s)

        return shift_follow_up_bundles

    def _GetShiftWeekBundles(self, shifts):
        shift_week_bundles = []
        cur_week = shifts.shifts[0].start_date.isocalendar().week
        cur_shift_bundle = []
        cur_week_hours = []
        for s, shift in enumerate(shifts.shifts):
            if cur_week != shift.start_date.isocalendar().week:
                shift_week_bundles.append(cur_shift_bundle)
                cur_week = shift.start_date.isocalendar().week
                cur_shift_bundle = []
            cur_shift_bundle.append(s)
        shift_week_bundles.append(cur_shift_bundle)
        return shift_week_bundles

    def _GetShiftDayBundles(self, shifts):
        shift_day_bundles = []
        cur_day = (shifts.shifts[0].start_date.year, shifts.shifts[0].start_date.month, shifts.shifts[0].start_date.day)
        cur_shift_bundle = []
        for s, shift in enumerate(shifts.shifts):
            if cur_day != (shift.start_date.year, shift.start_date.month, shift.start_date.day):
                shift_day_bundles.append(cur_shift_bundle)
                cur_day = (shift.start_date.year, shift.start_date.month, shift.start_date.day)
                cur_shift_bundle = []
            cur_shift_bundle.append(s)

        shift_day_bundles.append(cur_shift_bundle)
        return shift_day_bundles


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

        
