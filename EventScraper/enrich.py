"""
Fields the UI filters on (themes, town, distance), derived from an event when
it's served rather than stored, so improving the rules here also updates
events that were scraped earlier.

Themes: one fixed set. Sources' own tags map onto it (TAG_THEMES), and words in
the title add more (TITLE_THEMES); Barneveldse Krant and wattedoenin have no
tags at all. An event can have several themes, or none ("Overig" in the UI).

Town: the last part of `location` ("Venue, Town"); failing that, a known town
named elsewhere in the location or the title; failing that, the home town of a
source that only covers Barneveld. Distance is from Barneveld centre to the
town's centroid.
"""

import re

from base_scraper import haversine_km
from config import HOME_LAT, HOME_LNG

TAG_THEMES = {
    # veluwe.nl
    "muziek & entertainment": "Muziek & theater",
    "erfgoed & cultuur": "Kunst & cultuur",
    "oorlog & vrijheid": "Kunst & cultuur",
    "markten & streekbeleving": "Markten & winkelen",
    "eten & drinken": "Eten & drinken",
    "familie & kinderen": "Kinderen & gezin",
    "natuur & outdoor": "Natuur & sport",
    "actief & sportief": "Natuur & sport",
    "workshops & belevenissen": "Workshops & cursussen",
    "feestdagen & vakanties": "Feestdagen",
    # visitregiobarneveld.nl (events and attractions)
    "voor kinderen": "Kinderen & gezin",
    "speeltuin": "Kinderen & gezin",
    "kinderboerderij": "Kinderen & gezin",
    "winkelen": "Markten & winkelen",
    "boerderijwinkel": "Markten & winkelen",
    "wandelen": "Natuur & sport",
    "fietsen": "Natuur & sport",
    "zwemmen": "Natuur & sport",
    "actief": "Natuur & sport",
    "pluktuin": "Natuur & sport",
    "wisent": "Natuur & sport",
    "musea": "Kunst & cultuur",
    "molens": "Kunst & cultuur",
    "monumenten": "Kunst & cultuur",
    "historie": "Kunst & cultuur",
}

# Matched case-insensitively against the title. Mostly word stems, so
# "concert" also catches "jubileumconcert" and "kerst" catches "Kerstmarkt".
TITLE_THEMES = [
    ("Muziek & theater", r"concert|koor|orgel|muziek|band\b|\brock|optreden|zang|meezing|tribute"
                         r"|\bdj\b|disco|theater|toneel|voorstelling|cabaret|musical|film"),
    ("Kunst & cultuur", r"expositie|tentoonstelling|museum|kunst|atelier|galerie|lezing|erfgoed"
                        r"|histori|geschiedenis|rondleiding|monument|molen|grafiek|fotografie"
                        r"|beeldhouw|schilderij|\bboek|\bbook|literat|gedicht|po[eë]zie"
                        r"|herdenking|bevrijding|cultu"),
    ("Markten & winkelen", r"markt|beurs|braderie|bazaa?r|rommel|verkoop|kofferbak|koopavond|\bwinkel"),
    ("Eten & drinken", r"diner|lunch|ontbijt|brunch|proeverij|proeven|wijn|\bbier|koffie"
                       r"|high[ -]?tea|pannenkoek|culinair|\bkook|soep|food|barbecue|\bbbq\b"
                       r"|borrel|chocola"),
    ("Kinderen & gezin", r"kind|peuter|kleuter|baby|jeugd|tiener|puber|gezin|famil|voorlees"
                         r"|\bspeel(?!t\b)|kids|knutsel|speurtocht|sprookje|sinterklaas"),
    ("Natuur & sport", r"wandel|fiets|natuur|excursie|safari|boswachter|vogel|\bivn\b|tuin|bloei|imker"
                       r"|paddenstoel|\bwild|\bheide|\bbos\b|sport|toernooi|hardloop|\bloop\b"
                       r"|marathon|zwem|schaats|ijsbaan|golf|yoga|klimbos|klimmen|mountainbike"
                       r"|\bmtb\b|ruiter|paard"),
    ("Workshops & cursussen", r"workshop|cursus|training|masterclass|lessen\b|tekenles|schilderles"
                              r"|knutsel|maken\b|haak|\bbrei|creatief|repair|techclub"),
    ("Feestdagen", r"sinterklaas|pieten|\bpiet\b|pepernot|chocoladeletter|kerst|oud en nieuw"
                   r"|oudejaars|nieuwjaar|halloween|griezel|\bpasen|paas|koningsdag|carnaval"
                   r"|sint[- ]?maarten|lampion|intocht"),
]
_TITLE_THEME_RES = [(theme, re.compile(pattern, re.IGNORECASE)) for theme, pattern in TITLE_THEMES]

# name: (lat, lng, municipality). Centroids from PDOK Locatieserver (type
# woonplaats); the Ermelo hamlets, Schaarsbergen and Wenum-Wiesel aren't
# woonplaatsen, so theirs are neighbourhood (buurt) centroids. Achterveld
# straddles Barneveld and Leusden; the village itself is on the Leusden side.
TOWNS = {
    "Achterveld": (52.1407, 5.4788, "Leusden"),
    "Amerongen": (51.9961, 5.4495, "Utrechtse Heuvelrug"),
    "Amersfoort": (52.1682, 5.3894, "Amersfoort"),
    "Apeldoorn": (52.2108, 5.9737, "Apeldoorn"),
    "Arnhem": (52.0011, 5.8926, "Arnhem"),
    "Baarn": (52.2071, 5.2713, "Baarn"),
    "Barneveld": (52.1412, 5.5829, "Barneveld"),
    "Beekbergen": (52.1441, 5.9679, "Apeldoorn"),
    "Bennekom": (52.0074, 5.6697, "Ede"),
    "Braamt": (51.9247, 6.2623, "Montferland"),
    "Bunschoten-Spakenburg": (52.2375, 5.364, "Bunschoten"),
    "De Glind": (52.1199, 5.5152, "Barneveld"),
    "De Klomp": (52.0419, 5.5853, "Ede"),
    "De Steeg": (52.0246, 6.0662, "Rheden"),
    "Deelen": (52.078, 5.893, "Ede"),
    "Dieren": (52.0514, 6.0853, "Rheden"),
    "Doorn": (52.0373, 5.3423, "Utrechtse Heuvelrug"),
    "Doorwerth": (51.974, 5.7864, "Renkum"),
    "Drie": (52.2661, 5.678, "Ermelo"),
    "Driebergen-Rijsenburg": (52.0499, 5.2862, "Utrechtse Heuvelrug"),
    "Ede": (52.046, 5.6849, "Ede"),
    "Ederveen": (52.0588, 5.5834, "Ede"),
    "Eemnes": (52.2519, 5.2827, "Eemnes"),
    "Eerbeek": (52.095, 6.0513, "Brummen"),
    "Elburg": (52.4489, 5.8423, "Elburg"),
    "Ellecom": (52.027, 6.1004, "Rheden"),
    "Elspeet": (52.2971, 5.7865, "Nunspeet"),
    "Emst": (52.3176, 5.9462, "Epe"),
    "Epe": (52.3574, 5.9584, "Epe"),
    "Ermelo": (52.2882, 5.6662, "Ermelo"),
    "Garderen": (52.224, 5.7017, "Barneveld"),
    "Harderwijk": (52.3375, 5.6359, "Harderwijk"),
    "Harskamp": (52.1339, 5.777, "Ede"),
    "Heelsum": (51.982, 5.7625, "Renkum"),
    "Heveadorp": (51.9737, 5.8126, "Renkum"),
    "Hierden": (52.3564, 5.6765, "Harderwijk"),
    "Hoenderloo": (52.1127, 5.8568, "Ede"),
    "Hoevelaken": (52.1784, 5.46, "Nijkerk"),
    "Hoog Soeren": (52.2122, 5.8624, "Apeldoorn"),
    "Hoogland": (52.1922, 5.3498, "Amersfoort"),
    "Hulshorst": (52.3574, 5.7286, "Nunspeet"),
    "Kootwijk": (52.1725, 5.7597, "Barneveld"),
    "Kootwijkerbroek": (52.1537, 5.6764, "Barneveld"),
    "Leersum": (52.0229, 5.4323, "Utrechtse Heuvelrug"),
    "Leusden": (52.1169, 5.4048, "Leusden"),
    "Loenen": (52.1097, 6.0075, "Apeldoorn"),
    "Lunteren": (52.101, 5.6184, "Ede"),
    "Maarn": (52.0656, 5.3649, "Utrechtse Heuvelrug"),
    "Maarsbergen": (52.0529, 5.4087, "Utrechtse Heuvelrug"),
    "Nijkerk": (52.218, 5.4889, "Nijkerk"),
    "Nijkerkerveen": (52.1945, 5.4682, "Nijkerk"),
    "Nijmegen": (51.8348, 5.8332, "Nijmegen"),
    "Nunspeet": (52.376, 5.7912, "Nunspeet"),
    "Oldebroek": (52.4295, 5.9223, "Oldebroek"),
    "Oosterbeek": (51.9856, 5.8381, "Renkum"),
    "Otterlo": (52.0792, 5.7943, "Ede"),
    "Putten": (52.2439, 5.5827, "Putten"),
    "Renkum": (51.9915, 5.7412, "Renkum"),
    "Renswoude": (52.0689, 5.5342, "Renswoude"),
    "Rheden": (52.027, 6.0157, "Rheden"),
    "Rhenen": (51.9772, 5.5752, "Rhenen"),
    "Rozendaal": (52.0425, 5.9679, "Rozendaal"),
    "Schaarsbergen": (52.0241, 5.8727, "Arnhem"),
    "Scherpenzeel": (52.0893, 5.5005, "Scherpenzeel"),
    "Soest": (52.1609, 5.2951, "Soest"),
    "Speuld": (52.2704, 5.7088, "Ermelo"),
    "Staverden": (52.2824, 5.7416, "Ermelo"),
    "Stoutenburg": (52.1523, 5.4359, "Leusden"),
    "Stroe": (52.1929, 5.6979, "Barneveld"),
    "Terschuur": (52.1603, 5.5196, "Barneveld"),
    "Uddel": (52.2355, 5.795, "Apeldoorn"),
    "Ugchelen": (52.1705, 5.9011, "Apeldoorn"),
    "Ulft": (51.8952, 6.3743, "Oude IJsselstreek"),
    "Vaassen": (52.2869, 5.9322, "Epe"),
    "Veenendaal": (52.0237, 5.5557, "Veenendaal"),
    "Velp": (51.9971, 5.9856, "Rheden"),
    "Vierhouten": (52.3309, 5.8278, "Nunspeet"),
    "Voorthuizen": (52.1879, 5.6208, "Barneveld"),
    "Wageningen": (51.9735, 5.6635, "Wageningen"),
    "Wekerom": (52.1026, 5.7053, "Ede"),
    "Wenum-Wiesel": (52.2542, 5.9271, "Apeldoorn"),
    "Wezep": (52.4568, 5.9897, "Oldebroek"),
    "Wolfheze": (52.0071, 5.7849, "Renkum"),
    "Woudenberg": (52.0812, 5.4266, "Woudenberg"),
    "Zeist": (52.0884, 5.2517, "Zeist"),
    "Zutphen": (52.1354, 6.208, "Zutphen"),
    "Zwartebroek": (52.1794, 5.5124, "Barneveld"),
}
_TOWN_NAMES = {name.lower(): name for name in TOWNS}
# Free-text search skips names that are also ordinary words ("drie" = three).
_TOWN_RE = re.compile(
    r"\b(" + "|".join(re.escape(n) for n in sorted(TOWNS, key=len, reverse=True) if n not in {"Drie", "Doorn"}) + r")\b",
    re.IGNORECASE,
)

# Sources that only cover Barneveld: events without a usable location are there.
SOURCE_HOME_TOWN = {"barneveld": "Barneveld", "barneveldsekrant": "Barneveld"}


def themes_for(title: str, category: str | None) -> list[str]:
    themes = {TAG_THEMES.get(tag.strip().lower()) for tag in (category or "").split(",")}
    themes.update(theme for theme, rx in _TITLE_THEME_RES if rx.search(title))
    themes.discard(None)
    return sorted(themes)


def town_for(location: str | None, title: str, source_name: str) -> str | None:
    if location:
        last = location.rsplit(",", 1)[-1].strip().lower()
        if last in _TOWN_NAMES:
            return _TOWN_NAMES[last]
    for text in (location, title):
        found = _TOWN_RE.findall(text or "")
        if found:
            return _TOWN_NAMES[found[-1].lower()]
    return SOURCE_HOME_TOWN.get(source_name)


def place_for(location: str | None, title: str, source_name: str) -> tuple[str, str, float] | None:
    """(town, municipality, km from Barneveld), or None for an unknown town."""
    town = town_for(location, title, source_name)
    if town is None:
        return None
    lat, lng, municipality = TOWNS[town]
    return town, municipality, round(haversine_km(HOME_LAT, HOME_LNG, lat, lng), 1)
