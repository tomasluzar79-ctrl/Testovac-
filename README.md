# F1 tipovačka pro partu

Společnou verzi obsluhuje `league.py` na adrese `/`. Původní samostatná tipovačka zůstává v `index.html`. Každý hráč zadá společný kód party, vybere si přezdívku a uloží osobní kód pro další zařízení. Uzávěrku kontroluje server podle času startu.

## Spuštění

Na serveru s Dockerem sestav obraz příkazem `docker build -t f1-liga .`. Nastav dvě různé tajné hodnoty prostředí `LEAGUE_INVITE` (pro hráče) a `LEAGUE_ADMIN` (jen pro správce). Pak spusť:

```sh
docker run -d --restart unless-stopped --name f1-liga -p 127.0.0.1:8080:8080 -v f1-data:/data -e LEAGUE_INVITE -e LEAGUE_ADMIN -e HTTPS_ONLY=1 f1-liga
```

Před server nastav HTTPS reverzní proxy na port 8080. Objem `f1-data` obsahuje SQLite databázi a vyžaduje trvalé uložení. Při lokálním testu přes HTTP vynech `-e HTTPS_ONLY=1`. Bez Dockeru lze použít Python 3.10+, `pip install -r requirements.txt` a `python league.py`.

Každých 15 minut server načte kalendář 2026 z Jolpica a pro skončené závody s alespoň jedním tiketem porovná termín s výsledkovou tabulkou Formula1.com. Pódium a nejrychlejší kolo bere ze stránek dané GP. Výpadek nezruší poslední známý výsledek. Při další úspěšné kontrole se body vypočtou z aktuálních dat. Ostatní výsledky potvrdí správce v sekci pod žebříčkem. Obnovení stránky zobrazí aktuální body. Ve společné verzi platí výchozí bodování původní stránky. Osobní kódy jsou přihlašovací údaje. Lokální historické tikety se samy neimportují.
