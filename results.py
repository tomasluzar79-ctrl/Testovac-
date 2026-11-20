"""Import the calendar and the official result tables."""
import json
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.request import Request, urlopen
from urllib.parse import urljoin

BASE = 'https://www.formula1.com/en/results/2026/races'

def download(url):
    with urlopen(Request(url, headers={'User-Agent': 'F1FriendsLeague/1.0'}), timeout=15) as response:
        return response.read(4_000_000).decode()

class Rows(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.rows = []
        self.row = self.cell = None
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        if tag == 'tr':
            self.row = []
        elif tag == 'td' and self.row is not None:
            self.cell = {'text': '', 'href': ''}
            self.row.append(self.cell)
        elif tag == 'a' and self.cell is not None:
            self.cell['href'] = dict(attrs).get('href', '')

    def handle_endtag(self, tag):
        if tag == 'td':
            self.cell = None
        if tag == 'tr' and self.row is not None:
            if self.row:
                self.rows.append(self.row)
            self.cell = self.row = None

    def handle_data(self, value):
        if self.cell is not None:
            self.cell['text'] += value

def calendar():
    rows = json.loads(download('https://api.jolpi.ca/ergast/f1/2026.json'))['MRData']['RaceTable']['Races']
    for r in rows:
        if r['season'] == '2026' and r.get('time'):
            start = datetime.fromisoformat(r['date'] + 'T' + r['time'].replace('Z','+00:00'))
            yield r['Circuit']['circuitId'], r['raceName'], int(start.timestamp())

def published():
    links = {}
    for row in Rows(download(BASE)).rows:
        url = urljoin(BASE, row[0]['href'])
        if len(row) >= 2 and re.fullmatch(BASE + r'/\d+/[a-z0-9-]+/race-result', url):
            day = ' '.join(row[1]['text'].split())[:6]
            links[day] = url
    return links

def classified(url):
    drivers = {}
    for row in Rows(download(url)).rows:
        pos = row[0]['text'].strip()
        if len(row) >= 3 and pos in ('1', '2', '3'):
            code = re.search(r'([A-Z]{3})\s*$', row[2]['text'])
            if code:
                drivers[int(pos)] = code.group(1)
    return drivers

def official(url):
    podium = classified(url)
    if len(set(podium.values())) != 3:
        return {}
    result = {'p' + str(p): code for p, code in podium.items()}
    fastest = classified(url.replace('/race-result', '/fastest-laps'))
    if 1 in fastest:
        result['fastestLap'] = fastest[1]
    return result
