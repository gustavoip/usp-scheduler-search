import asyncio
import datetime
import weakref
import random
from asyncio import Semaphore
from contextlib import suppress
from typing import List

from tqdm import tqdm
import aiohttp
from bs4 import BeautifulSoup as bs

DEPARTMENTS_CODE = {
    'ICMC': 55,
    'EESC': 18,
    'IFSC': 76,
    'IQSC': 75,
    'IAU': 99
}

WEEKDAYS = {
    'seg': 0,
    'ter': 1,
    'qua': 2,
    'qui': 3,
    'sex': 4,
    'sab': 5
}

WEEKDAYS_FORMAT = {
    0: 'Segunda-feira',
    1: 'Terça-feira',
    2: 'Quarta-feira',
    3: 'Quinta-feira',
    4: 'Sexta-feira',
    5: 'Sábado'
}

sem = Semaphore(50)

_PRINT_VERSION = '&print=true'
_JUPITERWEB_BASE_URL = "https://uspdigital.usp.br/jupiterweb/"
_GET_COURSE_DETAILS_URL = _JUPITERWEB_BASE_URL + "obterDisciplina?sgldis={}&verdis=1"
_GET_COURSE_CLASS_URL = _JUPITERWEB_BASE_URL + "obterTurma?sgldis={}"
_GET_COURSE_REQUIREMENTS_URL = _JUPITERWEB_BASE_URL + "listarCursosRequisitos?coddis={}"
_GET_COURSES_BY_DEPARMENT_URL = _JUPITERWEB_BASE_URL + "jupDisciplinaLista?codcg={}&letra=A-Z&tipo=D"


def _get_tables_with_no_subtables(tables):
    tables_ = []
    for t in tables:
        if len(t.find_all('table')) == 0:
            tables_.append(t)
    return tables_


def _clear_string(data):
    return ' '.join(data.replace('\n', ' ').split()).strip()


def parse_n_columns_html_table(n: int, table):
    data = []
    for tr in table.find_all('tr'):
        tds = tr.find_all('td')
        if len(tds) == n:
            line = []
            for c in range(n):
                str_ = _clear_string(tds[c].get_text())
                line.append(str_)
            data.append(line)
    return data


async def get(client: aiohttp.ClientSession, url: str):
    global sem
    async with sem:
        async with client.get(url) as response:
            return await response.text()


class Requirement:
    def __init__(self, name: str, requirement_type: str):
        self.requirement_type = requirement_type
        self.name = name


def _parse_date(date: str) -> datetime.date:
    return datetime.datetime.strptime(date, '%d/%m/%Y').date()


def _parse_time(time_: str):
    return datetime.datetime.strptime(time_, "%H:%M").time()


class Course:
    def __init__(self, code: str, name: str, department_code: int):
        self.code = code
        self.name = name
        self.department_code = department_code
        self.requirements = []
        self.classes = []

    def __iter__(self):
        return self.classes.__iter__()

    def __getitem__(self, item):
        return self.classes[item]

    async def _refresh_course_details(self, client: aiohttp.ClientSession):
        pass

    async def _refresh_requirements(self, client: aiohttp.ClientSession):
        response = await get(url=_GET_COURSE_REQUIREMENTS_URL.format(self.code), client=client)
        soup = bs(response, 'html.parser')
        tables = _get_tables_with_no_subtables(soup.find_all('table'))
        for t in tables:
            req = parse_n_columns_html_table(2, t)
            if len(req) == 2:
                if req[0][0]:
                    self.requirements.append(req)

    async def _refresh_classes(self, client: aiohttp.ClientSession):
        url = _GET_COURSE_CLASS_URL.format(self.code)
        response = await get(url=url, client=client)
        soup = bs(response, 'html.parser')
        # Evitar duplicidade de dados
        tables = _get_tables_with_no_subtables(soup.find_all('table'))
        classes = []
        details = []
        for t in tables:
            class_ = parse_n_columns_html_table(4, t)
            if class_:
                classes.append(class_)

            detail_ = parse_n_columns_html_table(2, t)
            if len(detail_) == 5:
                details.append(detail_)

        if len(details) != len(classes):
            print(f"Problema {url}")
            return

        last_week_day = None
        for d, c in zip(details, classes):
            class_ = Class(
                url=url,
                course_ref=weakref.proxy(self),
                professor=c[1][-1],
                code=d[0][-1],
                start_date=_parse_date(d[1][-1]),
                end_date=_parse_date(d[2][-1]),
                observation=d[-1][-1])

            for c_ in c[1:]:
                week_day = WEEKDAYS[c_[0]] if c_[0] else last_week_day
                last_week_day = week_day

                start_time = _parse_time(c_[1]) if c_[1] else None
                end_time = _parse_time(c_[2]) if c_[2] else None
                class_.week_lectures.append(WeekLecture(
                    weekday=week_day,
                    start_time=start_time,
                    end_time=end_time
                ))
            self.classes.append(class_)

    def __eq__(self, other):
        if not isinstance(other, Course):
            return False

        for k, v in self.__dict__.items():
            if other[k] != v:
                return False
        return True

    @property
    def professors(self):
        return [p.professor for p in self.classes]

    @property
    def duration(self):
        try:
            return self.classes[0].duration
        except Exception:
            return None

    def overlap_with(self, course):
        if not isinstance(course, Course):
            raise ValueError

        for c in course.classes:
            for c2 in self.classes:
                if c.overlap_with(c2):
                    return True
        return False

    def __repr__(self):
        classes = len(self.classes)
        classes_str = f"{classes} turma" if classes == 1 else f"{classes} turmas"
        requirements = len(self.requirements)
        requirements_str = f"{requirements} turma" if requirements == 1 else f"{requirements} requisitos"
        return f"<Course: {self.code} - {self.name} - {classes_str} - {requirements_str}>"


def _time_to_datetime(time_: datetime.time) -> datetime.datetime:
    return datetime.datetime.combine(datetime.date.today(), time_)


class WeekLecture:
    def __init__(self, start_time: datetime.time, end_time: datetime.time, weekday: int):
        self.start_time: datetime.time = start_time
        self.end_time: datetime.time = end_time
        self.weekday = weekday

    @property
    def duration(self):
        return (_time_to_datetime(self.end_time) - _time_to_datetime(self.start_time)).total_seconds() / 60

    def overlap_with(self, lecture):
        if not isinstance(lecture, WeekLecture):
            raise ValueError
        if self.end_time <= lecture.start_time or self.start_time >= lecture.end_time:
            return False
        return True

    def __str__(self):
        s1 = self.start_time.strftime("%H:%M") if self.start_time else None
        s2 = self.end_time.strftime("%H:%M") if self.start_time else None
        return f"{WEEKDAYS_FORMAT[self.weekday]}: {s1} -> {s2}"

    def __repr__(self):
        return f"<WeekLecture: {self.__str__()}>"


class Class:
    def __init__(self, url: str, course_ref: Course, code: str, professor: str, start_date: datetime.date,
                 end_date: datetime.date, observation: str):
        self.professor = professor
        self.url = url
        self.week_lectures = []
        self.course = course_ref
        self.code = code
        self.start_date = start_date
        self.end_date = end_date
        self.observation = observation

    def __iter__(self):
        return self.week_lectures.__iter__()

    def __getitem__(self, item):
        return self.week_lectures[item]

    @property
    def name(self):
        return self.course.name

    def overlap_with(self, class_):
        if not isinstance(class_, Class):
            raise ValueError

        for l in class_.week_lectures:
            for l2 in self.week_lectures:
                if l.overlap_with(l2):
                    return True
        return False

    @property
    def duration(self):
        return sum(lecture.duration for lecture in self.week_lectures)

    def __repr__(self):
        return f"<Class: {self.professor} - {', '.join(str(x) for x in self.week_lectures)}>"


async def get_courses_by_department(department_code: int, client: aiohttp.ClientSession,
                                    retrieve_data=False, skip_courses_with_no_classes=False) -> List[Course]:
    courses = []
    content = await get(url=_GET_COURSES_BY_DEPARMENT_URL.format(department_code), client=client)
    soup = bs(content, "html.parser")
    tables = _get_tables_with_no_subtables(soup.find_all('table'))
    for t in tables:
        courses_ = parse_n_columns_html_table(4, t)
        if courses_ and len(courses_[0]) == 4:
            for c in tqdm(courses_[1:]):
                course = Course(
                    code=c[0],
                    name=c[1],
                    department_code=department_code)
                if retrieve_data:
                    await course._refresh_classes(client)
                    if skip_courses_with_no_classes and not course.classes:
                        continue

                    await course._refresh_requirements(client)
                courses.append(course)
    return courses


class AlreadyOccupied(Exception):
    pass


class MultipleEnrolmentNotAllowed(Exception):
    pass


class Grade:
    def __init__(self):
        self.classes: List[Class] = []

    def add_class(self, class_: Class):
        if not isinstance(class_, Class):
            raise ValueError

        for _class in self.classes:
            if _class.overlap_with(class_):
                raise AlreadyOccupied

            if _class == class_ or _class.course.code == class_.course.code:
                raise MultipleEnrolmentNotAllowed

        self.classes.append(class_)

    def __len__(self):
        return len(self.classes)

    def __repr__(self):
        data = []
        for c in self.classes:
            for wl in c:
                data.append(str(wl))
        return f"<Grade: {', '.join(data)}>"

    @property
    def credits(self):
        return sum(x.duration for x in self.classes)


def calculate_conflits(all_classes):
    conflits = {}
    for class_ in all_classes:
        conflits[class_.code] = 0
        for _class in all_classes:
            if _class != class_:
                with suppress(Exception):
                    if _class.overlap_with(class_):
                        conflits[class_.code] += 1
    return conflits


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    client = aiohttp.ClientSession()
    print("Obtendo disciplinas...")
    courses_by_department = get_courses_by_department(
        department_code=55,
        client=client,
        retrieve_data=True,
        skip_courses_with_no_classes=True
    )

    courses = loop.run_until_complete(courses_by_department)
    classes = []
    for c in courses:
        for c2 in c:
            classes.append(c2)

max_grade = Grade()
for _ in range(1000000):
    random.shuffle(classes)
    grade = Grade()
    for c in classes:
        try:
            grade.add_class(c)
        except Exception as e:
            pass
    if len(grade) > len(max_grade):
        print(f"Grade máxima com {len(grade)} disciplinas")
        max_grade = grade
