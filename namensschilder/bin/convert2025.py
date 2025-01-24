#!/usr/bin/python3
# -*- coding: utf-8 -*-
import collections
import csv
import json
from pathlib import Path
import random
import re
import sys
from typing import Dict, List
import os

ROOT = Path(__file__).parents[1]
YEAR = '2025'

DIR_DATA = ROOT / 'data' / YEAR
PATH_ORDERS = DIR_DATA / 'orders.json'  # Bestelldaten
PATH_NREI = DIR_DATA / 'nrei.json'  # 'Rechnungsdaten -> für Firmennamen
PATH_ITEMS = DIR_DATA / 'items.json'  # Produktdaten
PATH_BADGE_CSV = ROOT / 'csv' / 'badges2025.csv'
os.makedirs(PATH_BADGE_CSV.parent, exist_ok=True)

# if True -> generiert ein pseudodata.badges.csv mit Max & Maria Musterfrau data
PSEUDODATA: bool = False

# hier ggf. eine Liste mit order codes nutzen um selektiv badges zu erstellen
# https://pretix.eu/control/event/fossgis/2023/orders/<order code>/
#
ORDER_CODES = None
# ORDER_CODES = ['RK9LH']
# ORDER_CODES = ['BPJ3S']
ORDER_CODES = ['XYMHH']

# if >0 -> beschränkt das aus der json generierte CSV auf CSV_LIMIT Zeilen.
# Gut um schnell zu testen ob das PDF sinnvoll aussieht
CSV_LIMIT: int = -1

#
QUESTION_CODES = {
    'YFHZVZCA': 'Namensschild',
    'MBWBQDPJ': 'Firmenname',
    'NGMAWELJ': 'Nickname',
    'EA7G3AUG': 'EngelName',
    'NAKTGXCW': 'EngelName2',
    'YNH7QNRG': 'OSMName',
}

PRODUCT_NAMES = {
    'Geographischer Stadtrundgang': 'ex_1',
    'Konferenz-T-Shirt' : 'tshirt',
    'Konferenz-T-Shirt Helfende': 'tshirt_helfer',
    'Ich nehme an der Abendveranstaltung teil.': 'av',
}


# Hier können typos korrigiert, Firmennamen gekürzt und vereinheitlicht werden
DELETE_FROM_NAMES = [
    re.compile(r'FD Vermesssung und Geodaten Stadt Hildesheim[ ]*'),
    re.compile(r'Software Development[ ]*'),
    re.compile(r'Web GIS Freelance[ ]*'),
    re.compile(r'.* Consultants[ ]*'),
    re.compile(r'.* GmbH[ ]*'),
    re.compile(r'FH Aachen[ ]*'),
    re.compile(r'NTI Deutschland.*'),
]
REPLACE_IN_COMPANIES = {
    'Bundesamt für Kartographie und Geodäsie': re.compile('(BKG|Bundesamt für Kartographie und Geodäsie)'),
    'WhereGroup GmbH': re.compile(r'WhereGrouo?p GmbH', re.I),
    'DB Systel GmbH': re.compile('DB Systel GmbH c/o Deutsche Bahn AG'),
    'Landesamt für Geoinformation und Landesvermessung Niedersachsen': re.compile(
        r'LGLN|Landesamt für Geoinformation und Landesvermessung Niedersachsen', re.I),
    'Landesamt für Vermessung und Geobasisinformation Rheinland-Pfalz': re.compile(
        r'Landesamt für Vermessung und Geobasisinformation Rheinland-Pfalz', re.I),
    'Landesamt für Geoinformation und Landentwicklung Baden-Württemberg':
        re.compile(r'Landesamt für Geoinformation und Landentwicklung (Baden-Württemberg|BW)', re.I),
    'Landesvermessung und Geobasisinformation Brandenburg': re.compile('^LGB$'),
    'Staatsbibliothek zu Berlin': re.compile(r'staatsbibliothek zu berlin', re.I),
    'Umweltbundesamt (UBA)': re.compile(r'umweltbundesamt|\(UBA\)', re.I),
    'Stadt Leipzig': re.compile(r'Stadt Leipzig', re.I),
    'Technische Universität Chemnitz': re.compile('Technische Universität Chemnitz'),
    'Bezirksamt Tempelhof-Schöneberg von Berlin': re.compile(r'Bezirksamt Tempelhof-Schöneberg von Berlin', re.I),
    'DB Fahrwegdienste GmbH': re.compile(r'DB Fahrwegdienste GmbH', re.I),
    'Landesamt für Geoinformation & Landesvermessung Niedersachsen': re.compile('LGLN'),
    'Leibniz-Zentrum für Agrarlandschaftsforschung (ZALF)': re.compile('ZALF'),
    'Deutsches Zentrum für Luft- und Raumfahrt (DLR)': re.compile('Deutsches Zentrum für Luft- und Raumfahrt'),
}

# END SETTINGS



class BadgeInfo(object):
    """
    Alles Infos die in eine *.csv Zeile und mit einem Badge ausgedruckt werden sollen.
    """

    def __init__(self, order, positionid):
        self.order: str = order
        self.posid: int = positionid
        self.given_name: str = None
        self.family_name: str = None
        self.company: str = None
        self.mail: str = None
        self.ticket: str = None
        self.tl_name: str = None
        self.tl_veroeff: bool = False
        self.tl_erhalten: bool = False
        self.essen: str = None
        self.tb: bool = False
        self.tb_adresse: str = None
        self.osm_samstag: bool = False
        self.osm_name: str = None
        self.exkursionen: List[str] = []
        self.workshops: List[str] = []
        self.notes: str = None  # sonstiges
        self.nickname: str = None

        # add an attribute for each question
        for q in list(QUESTION_CODES.values()) + list(PRODUCT_NAMES.values()):
            assert q not in self.__dict__.keys(), 'Duplicate key: ' + q
            self.__dict__[q] = None



    def id(self) -> str:
        return f'{self.order}{self.posid}'

    def __str__(self):
        return f'Ticket:#{self.order},{self.family_name},{self.given_name}'


class csvDialect(csv.Dialect):
    """Describe the usual properties of Unix-generated CSV files."""
    delimiter = ';'
    quotechar = '"'
    doublequote = True
    skipinitialspace = False
    lineterminator = '\n'
    quoting = csv.QUOTE_MINIMAL


def normalizeName(name: str) -> str:
    """

    :param name:
    :return:
    """
    name = name.replace(", BSc", "")
    if name.find(" (") > 0:
        name = name[:name.find(" (")]
    name = re.sub(r'Dipl\.-(Ing|Geogr|Geol)\.[ ]+]', '', name)
    name = re.sub(
        r'(FD Vermesssung und Geodaten Stadt Hildesheim|Staatsbibliothek zu Berlin|Development and Operations| / Sourcepole)[ ]*',
        '', name)
    if ',' in name:
        name = ' '.join(reversed(re.split(r'[ ]*,[ ]*', name)))
    return name


# escape LaTeX characters
# credits to https://stackoverflow.com/questions/16259923/how-can-i-escape-latex-special-characters-inside-django-templates
conv = {
    '&': r'\&',
    '%': r'\%',
    '$': r'\$',
    '#': r'\#',
    '_': r'\_',
    '{': r'\{',
    '}': r'\}',
    '~': r'\textasciitilde{}',
    '^': r'\^{}',
    '\\': r'\textbackslash{}',
    '<': r'\textless{}',
    '>': r'\textgreater{}',
}
rx_tex_escape = re.compile('|'.join(re.escape(str(key)) for key in sorted(conv.keys(), key=lambda item: - len(item))))


def tex_escape(text):
    """
    :param text: a plain text message
    :return: the message escaped to appear correctly in LaTeX
    """
    return rx_tex_escape.sub(lambda match: conv[match.group()], text)


def readCompanyNames(path: Path) -> Dict[str, str]:
    CN = {}
    with open(path, 'r', encoding='utf-8') as f:
        jsonData = json.load(f)

    for data in jsonData['Data']:
        orderCode = data['Hdr']['OID']
        company = data['Hdr']['CN']
        CN[orderCode] = company

    return CN


def replace_strings(text: str, replacements: dict):
    for newtext, oldtext in replacements.items():
        if isinstance(oldtext, str):
            text = text.replace(oldtext, newtext)
        if oldtext.search(text):
            return newtext
    return text


def extractSurname(name: str) -> str:
    name = normalizeName(name)
    split = name.split(" ")
    return split[-1]


def extractFirstName(name: str) -> str:
    name = normalizeName(name)
    return name.split(' ')[0]


# print(json.dumps(data, indent=4))



def writeItems(items: Dict[int, str], path_csv: Path):
    path_csv = Path(path_csv)
    # print Items and write them into a CSV
    with open(path_csv, 'w', encoding='utf-8', newline='') as f:
        header = ['ItemID', 'Name']
        writer = csv.DictWriter(f, header)
        writer.writeheader()
        for key, value in items.items():
            writer.writerow(dict(ItemID=key, Name=value))


def readBadgeInfos(DIR_JSON_DATA) -> Dict[str, BadgeInfo]:
    BADGES: Dict[str, BadgeInfo] = {}

    DIR_JSON_DATA = Path(DIR_JSON_DATA)
    assert DIR_JSON_DATA.is_dir()

    PRODUCTS = readJson(DIR_DATA / 'items.json')
    CATEGORIES = readJson(DIR_DATA / 'categories.json')
    QUESTIONS = readJson(DIR_DATA / 'questions.json')



    def itemIDs(pattern:str, is_category=False) -> List[int]:
        if is_category:
            cat_ids = [c['id'] for c in CATEGORIES if re.search(pattern, c['name']['de'])]
            return [p['id'] for p in PRODUCTS if p['category'] in cat_ids]
        else:
            return [c['id'] for c in PRODUCTS if re.search(pattern, c['name']['de'])]

    P_Tickets = itemIDs('^(Konferenzticket|OpenStreetMap-Samstag).*')
    P_WORKSHOPS = itemIDs('^Workshop', True)
    s = ""
    def getQuestionId(question: str) -> int:
        return [q['id'] for q in QUESTIONS if q['question']['de'] == question][0]


    PRODUCTS = {p['id']: p for p in PRODUCTS}

    TICKETS = {pid:p for pid, p in PRODUCTS.items() if pid in P_Tickets}
    WORKSHOPS = {pid:p for pid, p in PRODUCTS.items() if pid in P_WORKSHOPS}

    ORDERS = readJson(DIR_DATA / 'orders.json')

    if isinstance(ORDER_CODES, list):
        ORDERS = [o for o in ORDERS if o['code'] in ORDER_CODES]

    # 1. Create Badge for each ticket order
    for order in ORDERS:
        ORDERCODE = order['code']
        ORDER_BADGES = {}

        for pos in order['positions']:
            itemid = pos['item']
            addon_to = pos.get('addon_to')
            PRODUCT = PRODUCTS[itemid]
            product_name = PRODUCT['name']['de']

            if itemid in P_Tickets:

                badgeInfo = BadgeInfo(ORDERCODE, pos['positionid'])
                badgeInfo.mail = pos['attendee_email']
                ORDER_BADGES[pos['id']] = badgeInfo
                name_parts = pos['attendee_name_parts']
                if name_parts['_scheme'] == 'given_family':
                    badgeInfo.family_name = name_parts['family_name']
                    badgeInfo.given_name = name_parts['given_name']
                else:
                    raise NotImplementedError(f"unknown name scheme {name_parts['_scheme']}")

                badgeInfo.ticket = TICKETS[itemid]['name']['de']
                badgeInfo.company = pos['company']

                for answer in pos['answers']:
                    qid = answer['question_identifier']
                    question = QUESTION_CODES.get(qid)
                    if question:
                        setattr(badgeInfo, question, answer['answer'])

            elif addon_to:
                # not a Ticket, something else and hopefully related to a Ticket/Badge
                badgeInfo: BadgeInfo = ORDER_BADGES[addon_to]

                variation_id = pos['variation']
                if variation_id:
                    value = [v['value']['de'] for v in PRODUCT['variations'] if v['id'] == pos['variation']][0]
                else:
                    value = PRODUCT['name']['de']
                if itemid in P_WORKSHOPS:
                    badgeInfo.workshops.append(value)
                else:
                    if product_name in PRODUCT_NAMES:
                        setattr(badgeInfo, PRODUCT_NAMES[product_name], value)
                    s = ""
            else:
                s = ""
        for badge in ORDER_BADGES.values():
            assert badge.id() not in BADGES
            BADGES[badge.id()] = badge
    return BADGES

def writeBadgeCsv(badgeInfos: Dict[str, BadgeInfo], path_csv: Path):
    path_csv = Path(path_csv)

    badgeInfos = sorted([p for p in badgeInfos.values()], key=lambda p: p.family_name)
    with open(path_csv, 'w', encoding='utf-8', newline='') as f:

        # schreibe alle Attribute als CSV Spalte
        p = badgeInfos[0]
        header = [k for k in p.__dict__.keys() if not k.startswith('_')]
        header.append('needs_check')
        writer = csv.DictWriter(f, header, dialect=csvDialect)
        writer.writeheader()

        cnt = 0
        for person in badgeInfos:
            if CSV_LIMIT > 0 and cnt >= CSV_LIMIT:
                break
            data = {k: person.__dict__.get(k, None) for k in header}
            for k in list(data.keys()):
                v = data[k]
                if isinstance(v, list):
                    latex = f'{len(v)}'
                    if len(v) > 0:
                        v = [tex_escape(line) for line in v]
                        if False:
                            latex += r'\\ -- ' + r' \\ -- '.join(v)
                        else:
                            # geht leider nicht, weil
                            latex += r' \begin{itemize} '
                            latex += r' \item ' + r' \item '.join(v)
                            latex += r' \end{itemize}\leavevmode '
                    v = latex
                elif isinstance(v, str):
                    if k == 'company':
                        v = replace_strings(v, REPLACE_IN_COMPANIES)
                    v = tex_escape(v)
                if k == 'name':
                    # Füge bei sehr langen Namen ein Leerzeichen ein
                    # damit auf dem Badge ein Zeilenumbruch entsteht
                    v = re.sub(r'(B\.?Sc|M\.?Sc|Dipl\.[- ]*(Geogr|Geol|Ing)\.?)[ ]+', '', v)
                    for rx in DELETE_FROM_NAMES:
                        v = rx.sub('', v)
                    v = re.sub(r'\(.+\)', '', v)
                    v = v.strip()
                    v = re.split(r'\|', v)[0]
                    if ',' in v:
                        print(f'Check "{v}"', file=sys.stderr)
                        data['needs_check'] = True
                    parts = re.split(r'[ ]+', v)
                    for i in range(len(parts)):
                        part = parts[i]
                        if len(part) > 15:
                            parts[i] = re.sub('-', '-""', part)
                    v = ' '.join(parts)
                data[k] = v
            writer.writerow(data)

            cnt += 1


def readJson(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

if __name__ == '__main__':

    # 1. lese JSON

    badges = readBadgeInfos(DIR_DATA)

    # 2. korrekturen


    if False:
        # füge Sondergäste hinzu
        from create_extra_badges import extra_badges

        for i, b in enumerate(extra_badges.values()):
            badges[f'guest_{i + 1}'] = b

        # Füge 30 leere Badges hinzu und
        emptyBadges = 30

        # Fülle A4 Blatt auf
        while (len(badges) + emptyBadges) % 4 != 0:
            emptyBadges += 1

        for i in range(emptyBadges):
            badges[f'empty_{i + 1}'] = BadgeInfo(name='')

        s = ""

    # 4. Schreibe badge CSV
    writeBadgeCsv(badges, PATH_BADGE_CSV)
    print("\nNumber of attendees: " + str(len(badges)))
