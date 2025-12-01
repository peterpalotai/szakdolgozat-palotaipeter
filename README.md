# szakdolgozat-palotaipeter
Ez a repository tartalmazza a szakdolgozatomban megvalósított alkalamzást, mely a különböző féle gazdasági számítások és vizualizációk megjelenéséért felelős.

## Setup utasítások

A futtatás előtt egy paracssorral kiadható, hogy az összes szükséges Python packge feltelepítésre vagy a megfelelő verzió frissítésére kerüljön.

```bash
pip install -r requirements.txt
```


```toml
[database]
host = "your-postgresql-host"
port = "5432"
database = "your-database-name"
user = "your-username"
password = "your-password"
```
A .toml file-ban megtalálható adatabázis credential secretek kezelése nem kerül feltültése githubra. .gitignore file-ba definiálva lett, hogy ne kerüljön a branch-re fel a file. Ez csak egy vázlat, hogy segítsen annak elképzelésében, hogy a kezelés, hogy működik.

A futtatáshoz a következő parancsot szükséges megadni:

```bash
streamlit run dfv-dashboard.py
```

## Oldalak leírása

### Főoldal
A főoldal lehetővé teszi az adatbázisban tárolt mérési adatok megjeleítését és elemzését. A felhasználó kiválaszthatja a dinamikus fűtésvezérlő vagy a termosztátos vezérlő adatait, amelyeket táblázatos formában jelenít meg lapozással (5, 15, 25 elem/oldal). Emellett interaktív grafikonok segítségével megtekintheti a teljesítmény, áram, hőmérséklet és páratartalom adatokat időbeli bontásban. Az oldal tartalmazza a CO₂ kibocsátási adatok megjelenítését is, amelyek a fűtőberendezés teljesítménye alapján számolódnak.


https://github.com/user-attachments/assets/85d21804-5045-4b33-8b3f-8b90c8f7eef4


### Energia előrejelzés oldal
Ez az oldal SARIMAX időbeli előrejelzési modellt használ a jövőbeli energiafogyasztás becslésére. A felhasználó választhat a havi, negyedéves vagy féléves előrejelzési időszakok közül. Az oldal megjeleníti a historikus adatokat, a modell által generált előrejelzést, valamint a becsült költségeket az E.ON vállalat által meghatározott veszteségiáram beszerzési árai alapján. Az előrejelzés interaktív grafikonokon jelenik meg, amelyek lehetővé teszik a részletes adatok elemzését.


https://github.com/user-attachments/assets/6a036f03-d7b6-4bdc-823b-ec2d49289178


### Megtakarítások oldal

#### CO₂ megtakarítások
Ez az aloldal összehasonlítja a dinamikus fűtésvezérlő és a termosztátos vezérlő CO₂ kibocsátását. A felhasználó kiválaszthatja a vizsgált időszakot és a fűtőberendezés teljesítményét. Az oldal összefoglaló metrikákat jelenít meg (összes CO₂ megtakarítás, átlagos napi megtakarítás), valamint részletes összehasonlító táblázatot és grafikonokat. Emellett hőtérképet is tartalmaz, amely vizuálisan mutatja a megtakarításokat naponta.


https://github.com/user-attachments/assets/51ac9cd6-63d7-4ddd-b4e3-9f12588fd707


#### Fogyasztási és költség megtakarítások
Ez az aloldal részletesen elemzi a két vezérlő típus és a folyamatos üzemelés közötti fogyasztási és költségi különbségeket. Megjeleníti a napi energiafogyasztást és költségeket táblázatos formában lapozással (5, 15, 25 elem/oldal), valamint összefoglaló metrikákat (összes megtakarítás, megtérülési idő, érzékenységvizsgálat). Az oldal tartalmazza a megtérülési időszak elemzését grafikonokkal, amelyek segítenek megérteni a beruházás gazdasági hatékonyságát.


https://github.com/user-attachments/assets/6e57c809-4de3-4b2d-b50b-1418bf476966

