#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""
Erstellt eine CSV Datei aus der mit LaTeX die Namensschilder generiert werden.
"""
import collections
import csv
import itertools
import json
import random
import warnings
from pathlib import Path
import re
import sys
from typing import Dict, List, Union, Optional
import os

EVENT_ID = '2025'

# hier ggf. eine Liste mit order codes nutzen um selektiv badges zu erstellen
# https://pretix.eu/control/event/fossgis/2023/orders/<order code>/
#
ORDER_CODES = None
# ORDER_CODES = ['RK9LH']
# ORDER_CODES = ['BPJ3S']
# ORDER_CODES = ['XYMHH', 'BPJ3S']

# CSV_LIMIT
# beschränkt das aus der json generierte CSV auf CSV_LIMIT Zeilen.
# Gut um schnell zu testen ob das PDF sinnvoll aussieht
CSV_LIMIT: int = None



# Hier die Fragecodes eintragen, deren Antworten in die CSV übernommen werden sollen
# siehe https://pretix.eu/control/event/fossgis/2025/questions/
# siehe data/questions.json
# {identifier : CSV Spaltenname}
CSV_QUESTIONS = {
    'YFHZVZCA': 'schild',
    'MBWBQDPJ': 'schild_firma',
    'NGMAWELJ': 'schild_nickname',
    'EA7G3AUG': 'name_engel1',
    'NAKTGXCW': 'name_engel2',
    'YNH7QNRG': 'name_osm',
}

# Hier die Produkte (aka Items) eintragen, deren Antworten als Spalte in die CSV übernommen werden sollen
# siehe https://pretix.eu/control/event/fossgis/2025/items/
# siehe data/items.json
# {Produktname oder Product ID : CSV Spaltenname}
#
CSV_PRODUCTS = {
    'Konferenz-T-Shirt' : 'tshirt',
    'Konferenz-T-Shirt Helfende': 'tshirt_helfer',
    'Ich nehme an der Abendveranstaltung teil.': 'av',
    'Ich möchte einen gedruckten Tagungsband erhalten.': 'tb',
}

# Hier die Produkt-ID (int) oder den Namen (str) der Exkursionen angeben
EXKURSIONEN = [
    'Geographischer Stadtrundgang',
    679198,
    675184,
]


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


ROOT = Path(__file__).parents[1]

DIR_DATA = ROOT / 'data' / EVENT_ID
PATH_ORDERS = DIR_DATA / 'orders.json'  # Bestelldaten
PATH_ITEMS = DIR_DATA / 'items.json'  # Produktdaten


class BadgeInfo(object):
    """
    Alles Infos die in eine *.csv Zeile und mit einem Badge ausgedruckt werden sollen.
    """

    def __init__(self, order='', positionid=0):
        self.order: str = order
        self.posid: int = positionid
        self.vorname: str = ''
        self.name: str = ''
        self.firma: str = ''
        self.mail: str = ''
        self.ticket: str = ''
        self.exkursionen: List[str] = []
        self.workshops: List[str] = []

        # weitere zu erfassende Produkte / Fragen
        for q in list(CSV_QUESTIONS.values()) + list(CSV_PRODUCTS.values()):
            assert q not in self.__dict__.keys(), 'Duplicate key: ' + q
            self.__dict__[q] = None



    def id(self) -> str:
        return f'{self.order}{self.posid}'

    def __str__(self):
        return f'Ticket:#{self.order},{self.name},{self.vorname}'


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


def tex_escape(text: Optional[str]) -> str:
    """
    :param text: a plain text message
    :return: the message escaped to appear correctly in LaTeX
    """
    if text is None:
        return ''
    return rx_tex_escape.sub(lambda match: conv[match.group()], text)

def replace_strings(text: str, replacements: dict):
    for newtext, oldtext in replacements.items():
        if isinstance(oldtext, str):
            text = text.replace(oldtext, newtext)
        if oldtext.search(text):
            return newtext
    return text

def itemName(item:dict) -> str:
    return item['name']['de']

def ticketItemIDs(products) -> List[int]:
    """
    Gibt alle jene item IDs zurück, die zu einem Ticket gehören für das
    ein Badge erstellt werden soll.
    :param products: list
    :param categories: list
    :return:
    """
    personalized = [item for item in products if item['personalized'] == True]
    on_site = [item for item in personalized if not re.search('online', itemName(item), re.IGNORECASE)]

    return [item['id'] for item in on_site]

def workshopItemIDs(products, categories) -> List[int]:

    cat_ids = [c['id'] for c in categories if re.search('^Workshop', itemName(c), re.IGNORECASE)]
    return [p['id'] for p in products if p['category'] in cat_ids]

def exkursionItemIDs(products, categories) -> List[int]:
    cat_ids = [c['id'] for c in categories if re.search('Exkursion', itemName(c), re.IGNORECASE)]
    return [p['id'] for p in products if p['category'] in cat_ids]

rx_online = re.compile('online', re.IGNORECASE)

def readBadgeInfos(dir_json) -> List[BadgeInfo]:
    BADGES: Dict[str, BadgeInfo] = {}

    dir_json = Path(dir_json)
    assert dir_json.is_dir()

    PRODUCTS = readJson(dir_json / 'items.json')
    CATEGORIES = readJson(dir_json / 'categories.json')
    QUESTIONS = readJson(dir_json / 'questions.json')

    ORDERS = readJson(DIR_DATA / 'orders.json')
    if isinstance(ORDER_CODES, list):
        ORDERS = [o for o in ORDERS if o['code'] in ORDER_CODES]


    def itemIDs(pattern:str, is_category=False) -> List[int]:
        if is_category:
            cat_ids = [c['id'] for c in CATEGORIES if re.search(pattern, c['name']['de'])]
            return [p['id'] for p in PRODUCTS if p['category'] in cat_ids]
        else:
            return [c['id'] for c in PRODUCTS if re.search(pattern, c['name']['de'])]

    TicketIDs = ticketItemIDs(PRODUCTS)
    WorkshopIDs = workshopItemIDs(PRODUCTS, CATEGORIES)
    ExkursionIDs = exkursionItemIDs(PRODUCTS, CATEGORIES)

    PRODUCTS = {p['id']: p for p in PRODUCTS}
    TICKETS = {pid:p for pid, p in PRODUCTS.items() if pid in TicketIDs}
    WORKSHOPS = {pid:p for pid, p in PRODUCTS.items() if pid in WorkshopIDs}
    EXKURSIONEN = {pid:p for pid, p in PRODUCTS.items() if pid in ExkursionIDs}

    # Lese Bestellungen
    for order in ORDERS:
        ORDERCODE = order['code']
        ORDER_BADGES = {}
        # Lese Positionen
        # eine Bestellung kann verschiedene Tickets beinhalten, denen wiederum andere positionen
        # zugeordnet sein können

        all_positions = {p['id']: p for p in order['positions']}
        unhandled_positions = {p['id']: p for p in order['positions']}

        # 1. Tickets lesen
        for (pid, pos) in [(pid,pos) for pid, pos in unhandled_positions.items() if pos['item'] in TicketIDs]:
            item_id = pos['item']
            badgeInfo = BadgeInfo(ORDERCODE, pos['positionid'])
            badgeInfo.mail = pos['attendee_email']

            name_parts = pos['attendee_name_parts']
            if name_parts['_scheme'] == 'given_family':
                badgeInfo.name = name_parts['family_name']
                badgeInfo.vorname = name_parts['given_name']
            else:
                raise NotImplementedError(f"unknown name scheme {name_parts['_scheme']}")

            badgeInfo.ticket = TICKETS[item_id]['name']['de']
            badgeInfo.firma = pos['company']

            for answer in pos['answers']:
                qid = answer['question_identifier']
                question = CSV_QUESTIONS.get(qid)
                if question:
                    setattr(badgeInfo, question, answer['answer'])

            ORDER_BADGES[pid] = badgeInfo
            unhandled_positions.pop(pid)

        # 2. Workshops lesen

        # 3. Verbleibenden Positionen den erstellten Badges zuordnen
        for (pid, pos) in [(pid,pos) for pid, pos in unhandled_positions.items()]:
            pos = unhandled_positions[pid]
            item_id = pos['item']
            product = PRODUCTS[item_id]
            product_name = itemName(product)
            product_id = product['id']

            addon_to = pos.get('addon_to')

            if addon_to:
                addon_base = all_positions[addon_to]
                addon_base_item = PRODUCTS[addon_base['item']]
                addon_base_name = itemName(addon_base_item)
            else:
                assert rx_online.search(product_name), f'Unbehandeltes Product: {product_name}'
                continue

            if addon_to not in ORDER_BADGES:
                assert rx_online.search(addon_base_name), \
                    f'Unbehandeltes Addon "{product_name}" für {addon_base_name}'
            else:
                badgeInfo: BadgeInfo = ORDER_BADGES[addon_to]

                variation_id = pos['variation']
                if variation_id:
                    value = [v['value']['de'] for v in product['variations'] if v['id'] == pos['variation']][0]
                else:
                    value = True

                if item_id in WorkshopIDs:
                    badgeInfo.workshops.append(product_name)
                elif item_id in ExkursionIDs:
                    badgeInfo.exkursionen.append(product_name)
                else:
                    if product_name in CSV_PRODUCTS:
                        setattr(badgeInfo, CSV_PRODUCTS[product_name], value)
                    elif product_id in CSV_PRODUCTS:
                        setattr(badgeInfo, CSV_PRODUCTS[product_id], value)


        for badge in ORDER_BADGES.values():
            assert badge.id() not in BADGES
            BADGES[badge.id()] = badge
    return list(BADGES.values())

def writeBadgeCsv(badgeInfos: List[BadgeInfo], path_csv: Path, fill:bool=True):
    path_csv = Path(path_csv)

    n = len(badgeInfos)
    if n == 0:
        warnings.warn(Warning('empty list of badges'), stacklevel=2)
        return None

    badgeInfos = sorted([p for p in badgeInfos], key=lambda p: (p.name, p.vorname))

    if fill:
        while not len(badgeInfos) % 4 == 0:
            badgeInfos.append(BadgeInfo())

    with (open(path_csv, 'w', encoding='utf-8', newline='') as file):

        # schreibe alle Attribute als CSV Spalte
        p = badgeInfos[0]
        attributes = [k for k in p.__dict__.keys() if not k.startswith('_')]

        prio = ['order', 'posid', 'name', 'vorname', 'mail', 'ticket']
        header = [p for p in prio if p in attributes]
        header += sorted([a for a in attributes if a not in header])
        header += ['needs_check']

        writer = csv.DictWriter(file, header, dialect=csvDialect)
        writer.writeheader()

        cnt = 0
        for i, person in enumerate(badgeInfos):

            data = {k: person.__dict__.get(k, None) for k in header}
            for k in list(data.keys()):
                v = data[k]
                if isinstance(v, list):
                    v = [line for line in v if isinstance(line, str) and len(line) > 0]
                    latex = f'{len(v)}'
                    if len(v) > 0:
                        v = [tex_escape(line) for line in v]
                        if True:
                            latex += r'\\ -- ' + r' \\ -- '.join(v)
                        else:
                            # geht leider nicht, weil
                            latex += r' \begin{itemize} '
                            latex += r' \item ' + r' \item '.join(v)
                            latex += r' \end{itemize}\leavevmode '
                    else:
                        latex = '0'
                    v = latex
                elif isinstance(v, str):
                    #if k == 'company':
                    #    v = replace_strings(v, REPLACE_IN_COMPANIES)
                    v = tex_escape(v)

                if k in ['name', 'vorname']:
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
                            parts[i] = re.sub('-', '- ', part)
                            pass
                    v = ' '.join(parts)
                data[k] = v
            writer.writerow(data)

            cnt += 1


def readPseudoBadgeInfos(dir_data: Union[str, Path]) -> List[BadgeInfo]:

    dir_data = Path(dir_data)
    assert dir_data.is_dir()
    # es werden verändert: Namen, Vornamen, emails, firmennamem
    # es wird genutzt: tatsächliche Bestelloptionen aus dem Pretix



    names = [('Max', 'Mustermann'),
             ('Maria','Musterfrau'),
             ('Max', 'Power'),
             ('Dorothea-Doppelname', 'Familien-Doppelname'),
             ('Dreifach Langer Vorname', 'von und zu Familienname'),
             ('Jakob', 'Nachname1-Nachname2-Nachname3'),
             ('Isabel', 'Isernhagen'),
             ('Anna', 'Annaberg'),
             ('Charlotte', 'Charlottenburg'),
             ('David', 'Domaschke'),
             ('Karl-Gustav', 'Karlson vom Dach Familie'),
             ('Karl', 'Napf'),
             ('Rudi', 'Sorglos'),
             ('Dieter', 'Dosenkohl'),
             ('Vladimir', 'Vladimirowitsch'),
             ('Knecht', 'Ruprecht'),
             ('Tapferes', 'Schneiderlein'),
             ('Gestiefelter', 'Kater'),
             ('Prinzessin', 'Leia'),
             ('Lord Darth', 'Vader'),
             ('Jean-Luc', 'Piccard'),
            ]


    firmen = ['Firma In-der-Kürze-liegt die Würze GmbH mit langem Namen',
              'Bundesamt für XY und Z',
              'Obelix Hinkelstein & Co GmbH',
              ]

    notes = [None,
             'weitere Anmerkungen, kurz gehalten',
             'so richtig viele weitere Anmerkungen und nochmal ganz andere Anmerkungen']

    real_badges = readBadgeInfos(dir_data)
    schild_optionen = list(set(b.schild for b in real_badges if b.schild))
    tshirs = list(set(b.tshirt for b in real_badges))
    tshirts_helfer = list(set(b.tshirt_helfer for b in real_badges))
    tickets = list(set(b.ticket for b in real_badges))
    exkursionen = set([])
    workshops = set([])
    for b in real_badges:
        for e in b.exkursionen:
            exkursionen.add(e)
        for w in b.workshops:
            workshops.add(w)
    exkursionen = list(exkursionen)
    workshops = list(workshops)
    BADGES = []

    def rnd(options: List, multiple: bool = False):
        if random.choice([True, False]):
            if multiple:
                return random.sample(options, random.choice(range(len(options))))
            else:
                return random.choice(options)

        else:
            if multiple:
                return []
            else:
                return None

    letters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'

    for (vorname, name) in names: # itertools.product(tickets, names) :
        badge = BadgeInfo()
        badge.name = name
        badge.vorname = vorname
        badge.order = ''.join(random.sample(letters, 5))
        badge.ticket = random.choice(tickets)
        badge.av = random.choice([True, False])
        badge.tb = random.choice([True, False])
        badge.mail = f'{badge.vorname}.{badge.name}@nomail.xyz'.lower()
        badge.tshirt = rnd(tshirs)
        badge.tshirt_helfer = rnd(tshirts_helfer)
        badge.workshops = rnd(workshops, multiple=True)
        badge.exkursionen = rnd(exkursionen, multiple=True)
        schild = random.choice(schild_optionen)
        badge.schild = schild
        if 'Firma' in schild:
            badge.schild_firma = random.choice(firmen)
        if  'Nickname' in schild:
            badge.schild_nickname = 'nick_' + vorname.lower()
        badge.notes = rnd(notes)
        badge.firma = random.choice(firmen)
        BADGES.append(badge)
    return BADGES

def readJson(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

if __name__ == '__main__':

    DIR_CSV = ROOT / 'csv'
    os.makedirs(DIR_CSV, exist_ok=True)

    # 1. read badges
    if False:
        badges = readBadgeInfos(DIR_DATA)
    else:
        #  pseudonymisierte Beispieldaten
        print('Create pseudo tickets')
        badges = readPseudoBadgeInfos(DIR_DATA)


    if False:
        # schreibe Workshop liste
        workshops = set()
        for b in badges:
            for w in b.workshops:
                workshops.add(w)

    if True:
        # 3. Separiere nach Ticket
        tickets = set([b.ticket for b in badges])

        ticket_types = {
            'Konferenz': 'conf',
            'Hackathon': 'hackaton',
            'OpenStreetMap': 'osm',
            'Community Sprint': 'sprint',
        }

        for prefix, suffix in ticket_types.items():
            ticket_badges = [v for v in badges if v.ticket.startswith(prefix)]
            path_csv = DIR_CSV / f'badges{EVENT_ID}_{suffix}.csv'
            if CSV_LIMIT:
                ticket_badges = tickets_badges[:min(len(ticket_badges),max_rows)]
            if len(ticket_badges) > 0:
                writeBadgeCsv(ticket_badges, path_csv)
                print(f'{path_csv} : {len(ticket_badges)} tickets')
            else:
                warnings.warn(f'No "{prefix}" tickets found')
    if True:
        # Füge leere Badges hinzu und
        emptyBadges = 30
        # Fülle auf A4 Blatt auf (4 Badges pro Blatt)
        while emptyBadges % 4 != 0:
            emptyBadges += 1

        badges = [BadgeInfo() for i in range(emptyBadges)]
        path_csv = DIR_CSV / f'badges{EVENT_ID}_leer.csv'
        writeBadgeCsv(badges, path_csv)
        print(f'{path_csv} : {len(badges)} tickes')


