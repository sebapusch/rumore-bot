import datetime

COMMAND = "rumore"

MESSAGES = {
    "question": "Come stai oggi?",
    "registered": "Ok, alle {time} vi chiederò come state"
}

MOODS = {
    9: "Miglior giornata {year}",
    8: "Incredibilmente bene",
    7: "Benissimo",
    6: "Bene",
    5: "Benino",
    4: "Così Così",
    3: "Maluccio",
    2: "Male",
    1: "Malissimo",
    0: "Peggior giornata {year}",
}

MOOD_PHRASES = {
    9: "Incredibilmente bene",
    8: "Incredibilmente bene",
    7: "Benissimo",
    6: "Bene",
    5: "Benino",
    4: "Così Così",
    3: "Maluccio",
    2: "Male",
    1: "Malissimo",
    0: "Malissimo",
}

MOOD_ID_LOOKUP = {(9 - k): k for k in MOODS}


def mood_options() -> list[str]:
    year = str(datetime.datetime.now().year)
    return [MOODS[k].replace("{year}", year) for k in MOODS]
