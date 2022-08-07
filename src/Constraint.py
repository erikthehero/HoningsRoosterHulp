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
    def __init__(self, general_request_fn=None, specific_request_fn=None):
        self.general_request_fn = general_request_fn
        self.specific_request_fn = specific_request_fn
        self.requests = self._InitRequestsFromFile(self.general_request_fn)
        self.requests.extend(self._InitRequestsFromFile(self.specific_request_fn))

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
            max_cost = 2
            min_cost = 3

            for bundle in shift_week_bundles:
                hard_max = 60 # pp92 CAO Gehandicaptenzorg 2021-2024: max 60 urige werkweek
                cv, cc = self._Add_soft_sum_constraint(n, bundle, shifts, model, work, hard_min, soft_min, min_cost, soft_max, hard_max, max_cost, "weekly_contract_hours")
                cost_variables.extend(cv)
                cost_coefficients.extend(cc)
                i+=1

        return cost_variables, cost_coefficients

    def add_skill_requirement_resuscitate(self, model, nurses, shifts, work):
        dl_shift_bundles = self._GetShiftSequences(shifts, "dl")
        a_shift_bundles = self._GetShiftSequences(shifts, "a")
        n_shift_bundles = self._GetShiftSequences(shifts, "n")
        nurses_with_resuscitate_skill = self._GetNursesThatCanResuscitate(nurses)

        for i in range(len(dl_shift_bundles[0])): # dl
            model.Add(sum(work[n, dl_shift_bundles[0][i]] for n in nurses_with_resuscitate_skill) + sum(work[n, dl_shift_bundles[1][i]] for n in nurses_with_resuscitate_skill)>=1)

        for i in range(len(a_shift_bundles[0])): # a
            model.Add(sum(work[n, a_shift_bundles[0][i]] for n in nurses_with_resuscitate_skill) + sum(work[n, a_shift_bundles[1][i]] for n in nurses_with_resuscitate_skill)>=1)

        for i in range(len(n_shift_bundles[0])): # n
            model.Add(sum(work[n, n_shift_bundles[0][i]] for n in nurses_with_resuscitate_skill) + sum(work[n, n_shift_bundles[1][i]] for n in nurses_with_resuscitate_skill)>=1)
        
        return

    def add_hard_requests_do_not_work_day(self, model, nurses, shifts, work):
        for request in self.requests:
            if not self._Request_type_is_hard_do_not_work_day(request):
                continue
            day_num = shifts.ConvertDayStrToDayNum(request.day)
            shift_day_bundles = self._GetShiftDayBundles(shifts, request.shift)
            for bundle in shift_day_bundles:
                bundle_day = shifts.shifts[bundle[0]].start_date.weekday()
                if not bundle_day == day_num:
                    continue
                
                for n,nurse in enumerate(nurses.nurses):
                    if not nurse.name == request.name:
                        continue
                    if request.do_assign:
                        model.Add(sum(work[n,s] for s in bundle)==1)
                    else:
                        model.Add(sum(work[n,s] for s in bundle)==0)
        return

    def add_hard_requests_do_not_work_shift(self, model, nurses, shifts, work):
        for request in self.requests:
            if not self._Request_type_is_hard_do_not_work_shift(request):
                continue
            shift_bundles = self._GetShiftSequences(shifts, request.shift)
            for bundle in shift_bundles:               
                for n,nurse in enumerate(nurses.nurses):
                    if not nurse.name == request.name:
                        continue
                    model.Add(sum(work[n,s] for s in bundle)==0)
        return

    def add_hard_requests_rest_after_n_shifts(self, model, nurses, shifts, work):
        for request in self.requests:
            if not self._Request_type_is_hard_rest_after_n_shifts(request):
                continue
            days_day_seq_bundles = self._GetDaysDayCombinationBundles(shifts, request.streakmax)
            for n,nurse in enumerate(nurses.nurses):
                if not nurse.name == request.name:
                    continue
                for bundle in days_day_seq_bundles:
                    conditional_shifts = []
                    for s in bundle[0]:
                        conditional_shifts.append(work[n,s]) 
                    model.Add(sum(work[n,s] for s in bundle[1][0])==0).OnlyEnforceIf(conditional_shifts)
        return

    def add_hard_requests_work_specific_day_shift(self, model, nurses, shifts, work):
        for request in self.requests:
            if not self._Request_type_is_hard_work_specific_day_shift(request):
                continue
            specific_day = request.full_date
            for s,shift in enumerate(shifts.shifts):
                for n,nurse in enumerate(nurses.nurses):
                    if not nurse.name == request.name:
                        continue
                    if self._ShiftAndDateAreSameDay(shift, specific_day) and specific_day.shift == shift.abbreviation:
                        model.Add(work[n, s] == 1)
        return

    def _Request_type_is_hard_work_specific_day_shift(self, request):
        if request.full_date:
            return True
        return False

    def _GetDaysDayCombinationBundles(self, shifts, sequence_length, rest_length=1):
        days_day_combination_bundles = []
        seq_shift_combinations = self._GetSequenceShiftCombinations(sequence_length)
        shift_day_bundles = self._GetShiftDayBundles(shifts)
        for s, shift in enumerate(shifts.shifts):
            days_day_combination_bundle = []
            days_day_combination_free_bundle = []

            s_bundle_ind = -1
            for ind, bundle in enumerate(shift_day_bundles):
                if s in bundle:
                    s_bundle_ind = ind
                    break
            if s_bundle_ind == -1:
                continue

            if s_bundle_ind+sequence_length >= len(shift_day_bundles):
                break

            for cmb in seq_shift_combinations:
                days_day_combination_bundle.append(s)
                for i in range(sequence_length-1):
                    days_day_combination_bundle.append(shift_day_bundles[i+s_bundle_ind+1][+cmb[i]])
                    
                days_day_combination_free_bundle.append(shift_day_bundles[s_bundle_ind+sequence_length])
                days_day_combination_bundles.append((days_day_combination_bundle, days_day_combination_free_bundle))
                days_day_combination_bundle = []
                days_day_combination_free_bundle = []
        return days_day_combination_bundles

    def _GetSequenceShiftCombinations(self, sequence_length):
        assert(sequence_length >1 and sequence_length <= 5)
        seq_shift_combinations = []
        if sequence_length == 2:
            for i in range(8):
                seq_shift_combinations.append([i])

        elif sequence_length == 3:
            for i in range(8):
                for j in range(8):
                    seq_shift_combinations.append([i,j])

        elif sequence_length == 4:
            for i in range(8):
                for j in range(8):
                    for k in range(8):
                        seq_shift_combinations.append([i,j,k])

        elif sequence_length == 5:
            for i in range(8):
                for j in range(8):
                    for k in range(8):
                        for l in range(8):
                            seq_shift_combinations.append([i,j,k,l])

        return seq_shift_combinations

    def _GetDaysDaySequenceBundles(self, shifts, sequence_length, rest_length=1):
        days_day_seq_bundles = []
        cur_shift = shifts.shifts[0]
        for s, shift in enumerate(shifts.shifts):
            days_day_seq_bundle = []
            days_day_seq_free_bundle = []
            if s + 8*(sequence_length+1) > len(shifts.shifts):
                break
            for i in range(8*(sequence_length+1)):
                if i > 8*sequence_length:
                    days_day_seq_free_bundle.append(s+i)
                else:
                    days_day_seq_bundle.append(s+i)

            days_day_seq_bundles.append((days_day_seq_bundle, days_day_seq_free_bundle))    
            days_day_seq_bundle = []
            days_day_seq_free_bundle = []

        return days_day_seq_bundles

    def add_soft_requests_do_assign_shift(self, model, nurses, shifts, work):
        cost = 10 #TODO: tune param
        tmp_var, tmp_coeffs = [],[]
        for request in self.requests:
            if not self._Request_type_is_soft_do_assign_shift(request):
                continue
            shift_bundles = self._GetShiftSequences(shifts, request.shift, request.day)
            for bundle in shift_bundles:
                for n,nurse in enumerate(nurses.nurses):
                    if not nurse.name == request.name:
                        continue
                    for s in bundle:
                        if request.do_assign:
                            tmp_var.append(work[n,s].Not()) # penalize not assigning this shift
                        else:
                            tmp_var.append(work[n,s])
                        tmp_coeffs.append(cost)
        return tmp_var, tmp_coeffs

    def add_favor_whole_weekend(self, model, nurses, shifts, work):
        #tmp_var, tmp_coeffs = [],[]
        shift_sequences_saturday = self._GetShiftSequences(shifts, shift_target=None, day_target="za")
        shift_sequences_sunday = self._GetShiftSequences(shifts, shift_target=None, day_target="zo")
        sunday_start_ind = len(shift_sequences_sunday[0]) - len(shift_sequences_saturday[0]) #TODO: to be tested for months starting at sundays

        for n,nurse in enumerate(nurses.nurses):
            for si in range(len(shift_sequences_saturday)):
                for ind in range(len(shift_sequences_saturday[si])):
                    model.Add(work[n, shift_sequences_sunday[si][ind+sunday_start_ind]]==1).OnlyEnforceIf(work[n, shift_sequences_saturday[si][ind]])

        return

    def add_max_5_shifts_per_week(self, model, nurses, shifts, work):
        shift_week_bundles = self._GetShiftWeekBundles(shifts)
        for n,_ in enumerate(nurses.nurses):
            for bundle in shift_week_bundles:
                model.Add(sum(work[n, s] for s in bundle) <= 5)
        return

    def add_penalty_to_zzp_allocation(self, model, nurses, shifts, work):
        cost = 1 #TODO: tune param
        obj_zzp_vars, obj_zzp_coeffs = [],[]
        zzp_nurses =  self._GetAllNursesWithZZPContract(nurses)
        for s,_ in enumerate(shifts.shifts):
            for n in zzp_nurses:
                obj_zzp_vars.append(work[n,s])
                obj_zzp_coeffs.append(cost)
        return obj_zzp_vars, obj_zzp_coeffs

    def _GetAllNursesWithZZPContract(self, nurses):
        zzp_nurses = []
        for n, nurse in enumerate(nurses.nurses):
            if nurse.zzper:
                zzp_nurses.append(n)
        return zzp_nurses

    def _Request_type_is_soft_do_assign_shift(self, request):
        if not request.full_date and request.shift and not request.is_hard:
            return True
        return False
        
    def _Request_type_is_hard_do_not_work_day(self, request):
        if not request.full_date and request.day and request.is_hard: #TODO: full_date probably can be incorporated
            return True
        return False

    def _Request_type_is_hard_rest_after_n_shifts(self, request):
        if not request.full_date and not request.day and request.streakmax and request.is_hard: #TODO: full_date probably can be incorporated
            return True
        return False

    def _Request_type_is_hard_do_not_work_shift(self, request): #TODO: full_date probably can be incorporated
        if not request.full_date and not request.day and request.shift and not request.do_assign and request.is_hard:
            return True
        return False        

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

    def add_penalized_day_evening_transition_constraint(self, model, nurses, shifts, work):
        # Penalized transitions
        # previous_day_shift, next_day_shift, penalty (0=hard)
        cost = 30
        penalized_transitions = [("dk0",  "a0", cost), # ochtend -> avond / nacht
                                 ("dk0",  "a1", cost),
                                 ("dm0",  "a0", cost),
                                 ("dm0",  "a1", cost),
                                 ("dl0",  "a0", cost),
                                 ("dl0",  "a1", cost),
                                 ("dl1",  "a0", cost),
                                 ("dl1",  "a1", cost),
                                 ("dk0",  "n0", cost),
                                 ("dk0",  "n1", cost),
                                 ("dm0",  "n0", cost),
                                 ("dm0",  "n1", cost),
                                 ("dl0",  "n0", cost),
                                 ("dl0",  "n1", cost),
                                 ("dl1",  "n0", cost),
                                 ("dl1",  "n1", cost),
                                 ("dl0", "dl1", 0),  # zelfde shift, zelfde rij
                                 ("dl1", "dl0", 0),
                                 ( "a0",  "a1", 0),
                                 ( "a1",  "a0", 0),
                                 ( "n0",  "n1", 0),
                                 ( "n1",  "n0", 0),
                                 ( "a0", "dk0", cost), # avond -> ochtend
                                 ( "a0", "dm0", cost),
                                 ( "a0", "dl1", cost),
                                 ( "a0", "dl1", cost),
                                 ( "a1", "dk0", cost),
                                 ( "a1", "dm0", cost),
                                 ( "a1", "dl1", cost),
                                 ( "a1", "dl1", cost)]

        obj_bool_vars = []
        obj_bool_coeffs = []
        for previous_shift, next_shift, cost in penalized_transitions:
            transitions = self._GetShiftDayToDayTransitions(shifts, previous_shift, next_shift)
            for n,nurse in enumerate(nurses.nurses):
                for transition in transitions:
                    t = [work[n,transition[0]].Not(), work[n,transition[1]].Not()]
                    if cost == 0:
                        model.Add(work[n,transition[1]]==0).OnlyEnforceIf(work[n,transition[0]])
                    else:
                        trans_var = model.NewBoolVar(f"transition ({nurse.name} {transition[0]} {transition[1]})")
                        t.append(trans_var)
                        model.AddBoolOr(t)
                        obj_bool_vars.append(trans_var)
                        obj_bool_coeffs.append(cost)
        return obj_bool_vars, obj_bool_coeffs

    def add_sequence_constraint(self, model, nurses, shifts, work):
        min_seq_len = 3
        min_cost = 2 # TODO: tune param
        obj_seq_vars = [] 
        obj_seq_coeffs = []
        sequences_of_followup_shifts = self._GetShiftSequences(shifts)

        for n,_ in enumerate(nurses.nurses):
            for seq in sequences_of_followup_shifts:
                for length in range(0, min_seq_len):
                    for start in range(len(seq) - length + 1):
                        span = self._NegatedBoundedSpan(n, seq, work, start, length)
                        name = ': under_span(start=%i, length=%i)' % (start, length)
                        lit = model.NewBoolVar(f"under_span {n} {start} {length}")
                        span.append(lit)
                        model.AddBoolOr(span)
                        obj_seq_vars.append(lit)
                        obj_seq_coeffs.append(min_cost * (min_seq_len - length))
        return obj_seq_vars, obj_seq_coeffs

    def _GetNursesThatCanResuscitate(self, nurses):
        nurses_with_resuscitate_skill = []
        for n,nurse in enumerate(nurses.nurses):
            if nurse.resuscitate:
                nurses_with_resuscitate_skill.append(n)
        return nurses_with_resuscitate_skill

    def _NegatedBoundedSpan(self, n, seq, work, start, length):
        span = []
        # Left border (start of works, or works[start - 1])
        if start > 0:
            span.append(work[n, seq[start - 1]] )
        for i in range(length):
            span.append(work[n, seq[start + i]].Not()) 
        # Right border (end of works or works[start + length])
        if start + length < len(seq):
            span.append(work[n, seq[start + length]])
        return span

    def _GetShiftSequences(self, shifts, shift_target=None, day_target=None):
        shift_types = shifts.GetTypes()
        sequences = []
        for st in shift_types:
            if shift_target and not st[:-1] == shift_target: # not the shift type we are explicitly looking for
                continue
            sequence = []
            for s, shift in enumerate(shifts.shifts):
                if day_target and not shifts.ConvertDayStrToDayNum(day_target)==shift.start_date.weekday():
                    continue
                if shift.abbreviation == st:
                    sequence.append(s)
            sequences.append(sequence)
        return sequences

    def _GetShiftDayToDayTransitions(self, shifts, previous_shift_type, next_shift_type):
        day_to_day_transitions = []
        previous_shift = None
        for s,shift in enumerate(shifts.shifts):
            if not previous_shift:
                if shift.abbreviation == previous_shift_type:
                    previous_shift = (s, shift)
                continue

            if not self._ShiftsAreSameDay(previous_shift[1], shift) and shift.abbreviation == next_shift_type:
                day_to_day_transitions.append((previous_shift[0], s))
                previous_shift = None

        return day_to_day_transitions

    def _ShiftsAreSameDay(self, shift1, shift2):
        return shift1.start_date.replace(hour=0, minute=0, second=0, microsecond=0) == shift2.start_date.replace(hour=0, minute=0, second=0, microsecond=0)
    
    def _ShiftAndDateAreSameDay(self, shift1, specific_date):
        return shift1.start_date.replace(hour=0, minute=0, second=0, microsecond=0) == specific_date.replace(hour=0, minute=0, second=0, microsecond=0)

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
        for s, shift in enumerate(shifts.shifts):
            if cur_week != shift.start_date.isocalendar().week:
                shift_week_bundles.append(cur_shift_bundle)
                cur_week = shift.start_date.isocalendar().week
                cur_shift_bundle = []
            cur_shift_bundle.append(s)
        shift_week_bundles.append(cur_shift_bundle)
        return shift_week_bundles

    def _GetShiftDayBundles(self, shifts, shift_type=None):
        shift_day_bundles = []
        cur_day = (shifts.shifts[0].start_date.year, shifts.shifts[0].start_date.month, shifts.shifts[0].start_date.day)
        cur_shift_bundle = []
        for s, shift in enumerate(shifts.shifts):
            if shift_type and not shift.abbreviation[:-1] == shift_type:
                continue
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

        requests = []

        if not fn:
            return requests

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
                requests.append(Constraint(name, full_date, day, shift, do_assign, streakmin, streakmax, max_sum, is_hard))
        return requests

        
