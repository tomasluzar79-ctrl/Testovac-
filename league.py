import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import threading
import time
import traceback
from contextlib import closing
from datetime import datetime, timezone
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.parse import parse_qs

import results

ROOT = Path(__file__).resolve().parent
DB = os.environ.get('LEAGUE_DB', 'league.sqlite3')
DRIVERS = json.loads((ROOT/'drivers.json').read_text(encoding='utf8'))
FIELDS = {
    'p1': ('Vítěz', 10), 'p2': ('2. místo', 10), 'p3': ('3. místo', 10),
    'fastestLap': ('Nejrychlejší kolo', 7), 'dotd': ('Jezdec dne', 7),
    'rain': ('Déšť během závodu', 5), 'safetyCarCount': ('Počet SC / VSC', 8),
    'dnfCount': ('Počet odstoupení', 8), 'firstDnf': ('První odstoupivší', 12),
    'lap1Crash': ('Nehoda top týmu v 1. kole', 6), 'finishers': ('Dokončí alespoň 16 vozů', 5)}
AUTO = ('p1','p2','p3','fastestLap')

def options(k):
    if k in ('rain','lap1Crash','finishers'):
        return {'yes':'Ano','no':'Ne'}
    if k in ('dnfCount','safetyCarCount'):
        return {str(n):str(n) for n in range(23)}
    return dict(DRIVERS, NONE='Nikdo') if k == 'firstDnf' else DRIVERS

def points(k, tip, result):
    if k not in result or not tip.get(k):
        return None
    if tip[k] == result[k]:
        return FIELDS[k][1]
    if k in AUTO[:3] and tip[k] in [result.get(p) for p in AUTO[:3]]:
        return 4
    if k in ('dnfCount','safetyCarCount') and abs(int(tip[k])-int(result[k])) == 1:
        return 3
    return 0

def init(db):
    db.executescript('''
    CREATE TABLE IF NOT EXISTS players(id INTEGER PRIMARY KEY,name TEXT UNIQUE COLLATE NOCASE,token TEXT UNIQUE);
    CREATE TABLE IF NOT EXISTS races(id TEXT PRIMARY KEY,name TEXT,start INTEGER,source TEXT,auto TEXT DEFAULT '{}',bonus TEXT DEFAULT '{}');
    CREATE TABLE IF NOT EXISTS tips(race TEXT,player INTEGER,ticket TEXT,PRIMARY KEY(race,player));
    ''')

def sync():
    with closing(sqlite3.connect(DB)) as db:
        with db:
            db.executemany('INSERT INTO races(id,name,start) VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,start=excluded.start', results.calendar())
        links = results.published()
        for race,start in db.execute('SELECT DISTINCT id,start FROM races JOIN tips ON tips.race=races.id WHERE start<?',(time.time(),)).fetchall():
            dt = datetime.fromtimestamp(start,timezone.utc)
            # Las Vegas starts the previous evening in local time. Compare both dates only there.
            days = [dt.strftime('%d %b')]
            if race == 'vegas':
                days.append(datetime.fromtimestamp(start-86400,timezone.utc).strftime('%d %b'))
            url = next((links[d] for d in days if d in links),None)
            if url:
                try:
                    data = results.official(url)
                    if data:
                        with db:
                            old = json.loads(db.execute('SELECT auto FROM races WHERE id=?',(race,)).fetchone()[0])
                            db.execute('UPDATE races SET source=?,auto=? WHERE id=?',(url,json.dumps(old|data),race))
                except Exception:
                    traceback.print_exc()

def loop():
    while True:
        try:
            sync()
        except Exception:
            traceback.print_exc()
        time.sleep(900)

def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()

class Problem(Exception):
    pass

def check(condition, msg):
    if not condition:
        raise Problem(msg)

def dispatch(db, env, headers):
    path = env['PATH_INFO']
    cookie = SimpleCookie()
    cookie.load(env.get('HTTP_COOKIE',''))
    token = cookie['player'].value if 'player' in cookie else ''
    user = db.execute('SELECT id,name FROM players WHERE token=?',(digest(token),)).fetchone()
    if env['REQUEST_METHOD'] == 'POST':
        check(env.get('CONTENT_TYPE','').split(';')[0]=='application/json','Neplatný požadavek.')
        size = int(env.get('CONTENT_LENGTH') or 0)
        check(0<size<=8192,'Neplatná velikost.')
        data = json.loads(env['wsgi.input'].read(size))
        check(isinstance(data,dict),'Neplatný požadavek.')
        if path == '/api/join':
            check(os.environ.get('LEAGUE_INVITE') and hmac.compare_digest(digest(str(data.get('invite',''))),digest(os.environ['LEAGUE_INVITE'])),'Zkontroluj kód party.')
            name = str(data.get('name','')).strip()
            check(0<len(name)<=32,'Zadej přezdívku do 32 znaků.')
            token = secrets.token_urlsafe(32)
            try:
                db.execute('INSERT INTO players(name,token) VALUES(?,?)',(name,digest(token)))
            except sqlite3.IntegrityError:
                raise Problem('Přezdívka je obsazená. Pro návrat použij svůj osobní kód.')
        elif path == '/api/login':
            token = str(data.get('token',''))
            check(db.execute('SELECT 1 FROM players WHERE token=?',(digest(token),)).fetchone(),'Neplatný osobní kód.')
        elif path in ('/api/tip','/api/bonus'):
            race = str(data.get('race',''))
            row = db.execute('SELECT start FROM races WHERE id=?',(race,)).fetchone()
            check(row,'Neznámý závod.')
            ticket = data.get('ticket')
            check(isinstance(ticket,dict),'Neplatný tiket.')
            for k,v in ticket.items():
                check(k in FIELDS and isinstance(v,str) and v in options(k),'Neplatná volba.')
            if path == '/api/bonus':
                key = os.environ.get('LEAGUE_ADMIN','')
                check(key and hmac.compare_digest(digest(str(data.get('key',''))),digest(key)),'Neplatný kód správce.')
                check(row[0]<=time.time() and not set(ticket).intersection(AUTO),'Bonus nelze potvrdit.')
                db.execute('UPDATE races SET bonus=? WHERE id=?',(json.dumps(ticket),race))
            else:
                check(user,'Nejdřív se přihlas.')
                check(all(k in ticket for k in AUTO) and len({ticket[k] for k in AUTO[:3]})==3,'Vyber tři různé jezdce na pódium a nejrychlejší kolo.')
                check(row[0]>time.time(),'Tipování je uzavřené.')
                db.execute('INSERT OR REPLACE INTO tips VALUES(?,?,?)',(race,user[0],json.dumps(ticket)))
            return {}
        else:
            raise Problem('Neznámá adresa.')
        secure = '; Secure' if env['wsgi.url_scheme']=='https' or os.environ.get('HTTPS_ONLY')=='1' else ''
        headers.append(('Set-Cookie','player='+token+'; Path=/; HttpOnly; SameSite=Strict; Max-Age=31536000'+secure))
        return {'token':token}
    check(path=='/api/state','Neznámá adresa.')
    races = db.execute('SELECT id,name,start,auto,bonus,source FROM races ORDER BY start').fetchall()
    results_by_race = {id:json.loads(auto)|json.loads(bonus) for id,_,_,auto,bonus,_ in races}
    selected = parse_qs(env.get('QUERY_STRING','')).get('race',[''])[0]
    totals = dict(db.execute('SELECT id,0 FROM players'))
    mine = {}
    for race,player,raw in db.execute('SELECT race,player,ticket FROM tips'):
        ticket=json.loads(raw)
        totals[player]+=sum(points(k,ticket,results_by_race[race]) or 0 for k in ticket)
        if user and player==user[0] and race==selected:
            mine=ticket
    return {'user':user[1] if user else None,'races':[(i,n,t,s) for i,n,t,_,_,s in races],
        'standings':sorted([(n,totals[i]) for i,n in db.execute('SELECT id,name FROM players')],key=lambda p:-p[1]),
        'ticket':mine,'result':results_by_race.get(selected,{}),
        'points':{k:points(k,mine,results_by_race.get(selected,{})) for k in mine},
        'fields':{k:[label,options(k)] for k,(label,_) in FIELDS.items()},'now':int(time.time())}

def app(env, respond):
    headers=[('Cache-Control','no-store'),('X-Content-Type-Options','nosniff')]
    if env['PATH_INFO']=='/' and env['REQUEST_METHOD']=='GET':
        respond('200 OK',headers+[('Content-Type','text/html; charset=utf-8')])
        return [(ROOT/'league.html').read_bytes()]
    try:
        with closing(sqlite3.connect(DB)) as db, db:
            data=dispatch(db,env,headers)
        status='200 OK'
    except (Problem,ValueError) as e:
        data,status={'error':str(e)},'400 Bad Request'
    respond(status,headers+[('Content-Type','application/json; charset=utf-8')])
    return [json.dumps(data).encode()]

if __name__=='__main__':
    from waitress import serve
    with closing(sqlite3.connect(DB)) as db:
        init(db)
    threading.Thread(target=loop,daemon=True).start()
    serve(app,host='0.0.0.0',port=int(os.environ.get('PORT','8080')))
