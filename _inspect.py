import requests
from bs4 import BeautifulSoup
from config import HEADERS

r = requests.get("https://visitregiobarneveld.nl/agenda/", headers=HEADERS, timeout=15)
soup = BeautifulSoup(r.text, "html.parser")

for card in soup.select("div.card.position-relative"):
    title = card.select_one("h3, h2")
    date_el = card.select_one("p.card-date")
    title_text = title.get_text(strip=True) if title else "?"
    date_text = date_el.get_text(strip=True) if date_el else "(no date element)"
    print(f"{date_text:<30} {title_text}")
