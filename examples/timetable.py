#!/usr/bin/env python3
from collections import namedtuple
from pathlib import Path
import logging
import aspio

aspio.log.addHandler(logging.StreamHandler())
# aspio.log.setLevel(logging.DEBUG)  # Uncomment to enable debug messages from aspio


class SchoolData:
    def __init__(self, *, weekdays, periods_per_day, classes, teachers):
        self.weekdays = weekdays
        self.periods_per_day = periods_per_day
        self.classes = classes
        self.teachers = teachers

    @property
    def days_per_week(self):
        return len(self.weekdays)

Subject = namedtuple('Subject', ['id', 'name'])
Class = namedtuple('Class', ['id', 'requirements'])
Requirement = namedtuple('Requirement', ['subject', 'weekly_periods'])
Teacher = namedtuple('Teacher', ['id', 'name', 'subjects'])

aspio.register_dict(globals())

asp_file = Path(__file__).with_name('timetable.dl')
timetable_program = aspio.Program(filename=asp_file)


def get_school_data() -> SchoolData:
    mat = Subject(id='MAT', name='Mathematics')
    ger = Subject(id='GER', name='German')
    eng = Subject(id='ENG', name='English')
    fre = Subject(id='FRE', name='French')
    lat = Subject(id='LAT', name='Latin')
    phy = Subject(id='PHY', name='Physics')
    che = Subject(id='CHE', name='Chemistry')
    bio = Subject(id='BIO', name='Biology')
    inf = Subject(id='INF', name='Informatics')
    geo = Subject(id='GEO', name='Geography')

    c1a = Class(id='1A', requirements=[
        Requirement(mat, 3),
        Requirement(ger, 5),
        Requirement(eng, 5),
        Requirement(lat, 4),
        Requirement(phy, 1),
        Requirement(bio, 1),
        Requirement(geo, 1),
    ])

    c1b = Class(id='1B', requirements=[
        Requirement(mat, 3),
        Requirement(ger, 4),
        Requirement(eng, 5),
        Requirement(fre, 5),
        Requirement(phy, 1),
        Requirement(bio, 1),
        Requirement(geo, 1),
    ])

    c1c = Class(id='1C', requirements=[
        Requirement(mat, 4),
        Requirement(ger, 4),
        Requirement(eng, 3),
        Requirement(phy, 2),
        Requirement(che, 2),
        Requirement(bio, 2),
        Requirement(inf, 2),
        Requirement(geo, 1),
    ])

    t1 = Teacher(id=1, name='Ms. A', subjects=[mat, phy, inf])
    t2 = Teacher(id=2, name='Mr. B', subjects=[ger, geo, fre])
    t3 = Teacher(id=3, name='Mr. C', subjects=[eng, bio, che])
    t4 = Teacher(id=4, name='Ms. D', subjects=[ger, lat, fre])

    data = SchoolData(
        weekdays=('Mon', 'Tue', 'Wed', 'Thu', 'Fri'),
        periods_per_day=5,
        classes=[c1a, c1b, c1c],
        teachers=[t1, t2, t3, t4],
    )
    return data


def main():
    data = get_school_data()
    print('Computing timetables...')
    result = timetable_program.solve_one(data)
    if result is None:
        print('No feasible timetable exists!')
    else:
        # Output timetable for every class
        for c in data.classes:
            tt = result.class_timetables[c.id]
            print('\nTimetable for class {0}:'.format(c.id))
            # Print table with one column per day, one row per period
            print(''.join('\t{0}'.format(w) for w in data.weekdays))
            for p in range(data.periods_per_day):
                print('{0}: \t{1}'.format(p + 1, '\t'.join(tt[d][p] for d in range(data.days_per_week))))
            # print(''.join('\t{0}'.format(x + 1) for x in range(data.periods_per_day)))
            # for d, dtt in enumerate(tt):
            #     print('{0}: \t{1}'.format(data.weekdays[d], '\t'.join(dtt)))
            # List the teachers assigned to the class
            print('Teachers:')
            for tid, sid in result.teachers[c.id]:
                tname = next(t.name for t in data.teachers if t.id == tid)
                print('\t{0}: {1}'.format(sid, tname))
        # Output timetable for every teacher
        for t in data.teachers:
            tt = result.teacher_timetables[t.id]
            print('\nTimetable for {0}:'.format(t.name))
            # Print table with one column per day, one row per period
            print(''.join('\t{0}'.format(w) for w in data.weekdays))
            for p in range(data.periods_per_day):
                period = [tt[d][p] for d in range(data.days_per_week)]
                period_str = '\t'.join('{0}:{1}'.format(cid, sid) for cid, sid in period)
                print('{0}: \t{1}'.format(p + 1, period_str))
            # for d, dtt in enumerate(tt):
            #     day_str = '\t'.join('{0}:{1}'.format(cid, sid) for cid, sid in dtt)
            #     print('{0}: \t{1}'.format(data.weekdays[d], day_str))


if __name__ == '__main__':
    main()
