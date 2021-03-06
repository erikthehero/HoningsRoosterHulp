import math
from calendar import Calendar, day_abbr as day_abbrs, month_name as month_names

from bokeh.document import Document
from bokeh.embed import file_html
from bokeh.layouts import gridplot
from bokeh.models import (CategoricalAxis, ContinuousAxis, CategoricalScale, ColumnDataSource,
                          FactorRange, HoverTool, Plot, Rect, Text,  Range1d)
from bokeh.resources import INLINE
from bokeh.sampledata.us_holidays import us_holidays
from bokeh.util.browser import view
import colorcet as cc

class RosterVisualizer:
    def __init__(self):
        self.color_workday = "linen"
        self.color_weekend = "lightsteelblue"
        self.nurse_colors = cc.glasbey_bw_minc_20_minl_30

    def visualize(self, nurses, shifts, work, solver):
        plots = []
        months = self._GetAllMonths(shifts)
        for year,month in months:
            plots.append(self._VisualizeMonthReal(year, month, nurses, shifts, work, solver))
        grid = gridplot(toolbar_location=None, children=[plots])

        doc = Document()
        doc.add_root(grid)
        doc.validate()
        filename = "HoningsRooster.html"
        with open(filename, "w") as f:
            f.write(file_html(doc, INLINE, "HoningsRooster"))
        print("Wrote %s" % filename)
        view(filename)

        return

    def _VisualizeMonthReal(self, year:int, month:int, nurses, shifts, work, solver) -> Plot:
        firstweekday = "Mon"
        firstweekday = list(day_abbrs).index(firstweekday)
        calendar = Calendar(firstweekday=firstweekday)
        self.month_days = [ None if not day else str(day) for day in calendar.itermonthdays(year, month)]
        month_weeks = len(self.month_days)//7
        def weekday(date):
            return (date.weekday() - firstweekday) % 7

        def pick_weekdays(days):
            return [ days[i % 7] for i in range(firstweekday, firstweekday+7) ]

        day_names = pick_weekdays(day_abbrs)
        day_numbers = [i for i in range(0,7)]
        week_days = pick_weekdays([self.color_workday]*5 + [self.color_weekend]*2)

        source = ColumnDataSource(data=dict(
            days            = day_numbers * month_weeks, #list(day_names)*month_weeks,
            weeks           = sum([ [week]*7 for week in range(month_weeks) ], []),
            #weeks           = sum([ [week]*7 for week in range(month_weeks) ], []),
            month_days      = self.month_days,
            day_backgrounds = sum([week_days]*month_weeks, []),
        ))

        """
        holidays = [ (date, summary.replace("(US-OPM)", "").strip()) for (date, summary) in us_holidays
            if date.year == year and date.month == month and "(US-OPM)" in summary ]
        holidays_source = ColumnDataSource(data=dict(
            holidays_days  = [ day_names[weekday(date)] for date, _ in holidays ],
            holidays_weeks = [ str((weekday(date.replace(day=1)) + date.day) // 7) for date, _ in holidays ],
            month_holidays = [ summary for _, summary in holidays ],
        ))
        """

        #xdr = FactorRange(factors=list(day_names))
        #ydr = FactorRange(factors=list(reversed([ str(week) for week in range(month_weeks) ])))
        #x_scale, y_scale = CategoricalScale(), CategoricalScale()

        #plot = Plot(x_range=xdr, y_range=ydr, x_scale=x_scale, y_scale=y_scale, width=600, height=600, outline_line_color=None)
        ymin = min(source.data["weeks"])
        ymax = max(source.data["weeks"])
        plot = Plot(width=800, height=800, y_range=Range1d(start=ymax+1, end=ymin-1), outline_line_color=None)
        plot.title.text = month_names[month]
        plot.title.text_font_size = "16px"
        plot.title.text_color = "black"
        plot.title.offset = 25
        plot.min_border_left = 0
        plot.min_border_bottom = 5

        rect = Rect(x="days", y="weeks", width=1.0, height=1.0, fill_color="day_backgrounds", line_color="black")
        plot.add_glyph(source, rect)


        nurse_sources = self._GetNurseShiftSourcesForVisualization(nurses, shifts, work, solver)
        for nurse_source_key in nurse_sources.keys():
            rect = Rect(x="days", y="weeks", width=1.0, height=1.0, line_color="black")
            plot.add_glyph(nurse_sources[nurse_source_key], rect)

        # test rects
        offset = 0.125
        test_rect_source = ColumnDataSource(data=dict(
            x            = [2, 2, 2, 2, 2, 2, 2, 2],
            y            = [3-3*offset-0.5*offset, 3-2*offset-0.5*offset, 3-1*offset-0.5*offset, 3-0.5*offset, 3+1*offset-0.5*offset, 3+2*offset-0.5*offset, 3+3*offset-0.5*offset, 3+4*offset-0.5*offset], # 3+5*offset-0.5*offset
        ))
        test_rect = Rect(x="x", y="y", width=1.0, height=0.125, fill_color="red",fill_alpha=0.5, line_color="black")
        plot.add_glyph(test_rect_source, test_rect)

        #rect = Rect(x="holidays_days", y="holidays_weeks", width=0.9, height=0.9, fill_color="pink", line_color="indianred")
        #rect_renderer = plot.add_glyph(holidays_source, rect)

        text = Text(x="days", y="weeks", text="month_days", text_align="center", text_baseline="middle", text_font_size = "14px")
        plot.add_glyph(source, text)

        #xaxis = CategoricalAxis()
        #xaxis.major_label_text_font_size = "11px"
        #xaxis.major_label_standoff = 0
        #xaxis.major_tick_line_color = None
        #xaxis.axis_line_color = None
        #plot.add_layout(xaxis, 'above')

        #hover_tool = HoverTool(renderers=[rect_renderer], tooltips=[("Holiday", "@month_holidays")])
        #plot.tools.append(hover_tool)

        return plot

    def _GetYOffsetFromShift(self, sa):
        offset = 0.125
        if sa == "dk0":
            return -3*offset-0.5*offset
        elif sa == "dm0":
            return -2*offset-0.5*offset
        elif sa == "dl0":
            return -1*offset-0.5*offset
        elif sa == "dl1":
            return -0.5*offset
        elif sa == "a0":
            return  1*offset-0.5*offset
        elif sa == "a1":
            return  2*offset-0.5*offset
        elif sa == "n0":
            return  3*offset-0.5*offset
        elif sa == "n1":
            return  4*offset-0.5*offset
        return None

    def _GetMonthWeekFromMonthDay(self, month_day):
        index = self.month_days.index(str(month_day))
        week = math.floor(float(index) / 7.0)
        return week

    def _GetNurseShiftSourcesForVisualization(self, nurses, shifts, work, solver):
        sources = {}
        for n, nurse in enumerate(nurses.nurses):
            days  = []
            weeks = []
            for s, shift in enumerate(shifts.shifts):
                if solver.Value(work[n,s]):
                    days.append(shift.start_date.day) # TODO: fix day, should be in range 0:7
                    weeks.append(self._GetMonthWeekFromMonthDay(shift.start_date.day) + self._GetYOffsetFromShift(shift.abbreviation)) # TODO: check this
            sources[nurse.name] = ColumnDataSource(data=dict(
                days  = days,
                weeks = weeks
            ))
        return sources

    def _GetAllMonths(self, shifts):
        months = []
        for s in shifts.shifts:
            year = s.start_date.year
            month = s.start_date.month
            if (year, month) not in months:
                months.append((year, month))
        return months
    
    def _GetAllMonthShifts(self, month, shifts):
        month_shifts = []
        for s in shifts.shifts:
            if s.start_date.month == month:
                month_shifts.append(s)
        return month_shifts



