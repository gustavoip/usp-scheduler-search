import asyncio
import weakref
import datetime
from typing import List
from asyncio import Semaphore

import aiohttp
import arrow
import requests
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
    'sex': 4
}

WEEKDAYS_FORMAT = {
    0: 'Segunda-feira',
    1: 'Terça-feira',
    2: 'Quarta-feira',
    3: 'Quinta-feira',
    4: 'Sexta-feira'
}

sem = Semaphore(50)

_PRINT_VERSION = '&print=true'
_JUPITERWEB_BASE_URL = "https://uspdigital.usp.br/jupiterweb/"
_GET_COURSE_DETAILS_URL = _JUPITERWEB_BASE_URL + "obterDisciplina?sgldis={}&verdis=1"
_GET_COURSE_CLASS_URL = _JUPITERWEB_BASE_URL + "obterTurma?sgldis={}" + _PRINT_VERSION
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
        print('GET', url)
        async with client.get(url) as response:
            return await response.text()


class Requirement:
    def __init__(self, name: str, requirement_type: str):
        self.requirement_type = requirement_type
        self.name = name


def _parse_date(date: str) -> datetime.date:
    return datetime.datetime.strptime(date, '%d/%m/%Y').date()


class Course:
    def __init__(self, code: str, name: str, department_code: int):
        self.code = code
        self.name = name
        self.department_code = department_code
        self.requirements = []
        self.classes = []

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

        for d, c in zip(details, classes):
            class_ = Class(
                course_ref=weakref.proxy(self),
                professor=c[1][-1],
                code=d[0][-1],
                start_date=_parse_date(d[1][-1]),
                end_date=_parse_date(d[2][-1]),
                observation=d[-1][-1])
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

    def __repr__(self):
        classes = len(self.classes)
        classes_str = f"{classes} turma" if classes == 1 else f"{classes} turmas"
        requirements = len(self.requirements)
        requirements_str = f"{requirements} turma" if requirements == 1 else f"{requirements} requisitos"
        return f"<{self.code} - {self.name} - {classes_str} - {requirements_str}>"


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
        if self.end_time <= lecture.start_time or self.start_time >= lecture.end_time:
            return False
        return True

    def __repr__(self):
        s1 = self.start_time.strftime("%H:%m")
        s2 = self.end_time.strftime("%H:%m")
        return f"{WEEKDAYS_FORMAT[self.weekday]}: {s1} -> {s2}"


class Class:
    def __init__(self, course_ref: Course, code: str, professor: str, start_date: datetime.date,
                 end_date: datetime.date, observation: str):
        self.professor = professor
        self.course = course_ref
        self.code = code
        self.start_date = start_date
        self.end_date = end_date
        self.observation = observation

    @property
    def name(self):
        return self.course.name


async def get_courses_by_department(department_code: int, client: aiohttp.ClientSession, retrieve_data=False) -> List[
    Course]:
    courses = []
    content = await get(url=_GET_COURSES_BY_DEPARMENT_URL.format(department_code), client=client)
    soup = bs(content, "html.parser")
    tables = _get_tables_with_no_subtables(soup.find_all('table'))
    for t in tables:
        courses_ = parse_n_columns_html_table(4, t)
        if courses_ and len(courses_[0]) == 4:
            for c in courses_[1:]:
                course = Course(
                    code=c[0],
                    name=c[1],
                    department_code=department_code)
                if retrieve_data:
                    await course._refresh_classes(client)
                    await course._refresh_requirements(client)
                courses.append(course)
    return courses


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    client = aiohttp.ClientSession()

    c = loop.run_until_complete(get_courses_by_department(department_code=55, client=client, retrieve_data=True))
