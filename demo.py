"""Local demo with isolated storage, no third-party packages required."""
import os
import sqlite3
import time
import webbrowser
from pathlib import Path
from tempfile import gettempdir
from wsgiref.simple_server import make_server

import league

def main():
    league.DB = str(Path(gettempdir()) / 'f1-tipovacka-demo.sqlite3')
    os.environ.update(LEAGUE_INVITE='BOX2026', LEAGUE_ADMIN='KOMISAR', HTTPS_ONLY='0')
    with sqlite3.connect(league.DB) as db:
        league.init(db)
        now = int(time.time())
        db.execute("INSERT OR REPLACE INTO races(id,name,start) VALUES(?,?,?)",
                   ('demo-open', 'Testovací závod', now + 86400))
    with make_server('127.0.0.1', 0, league.app) as server:
        url = f'http://127.0.0.1:{server.server_port}/'
        print(f'{url}   Kod party: BOX2026', flush=True)
        webbrowser.open(url)
        server.serve_forever()

if __name__ == '__main__':
    main()
