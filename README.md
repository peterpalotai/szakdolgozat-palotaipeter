# szakdolgozat-palotaipeter
Ez a repository tartalmazza a szakdolgozatomban megvalósított alkalamzást, mely a különböző féle gazdasági számítások és vizualizációk megjelenéséért felelős.

## Setup utasítások

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


```bash
streamlit run dfv-dashboard.py
```
