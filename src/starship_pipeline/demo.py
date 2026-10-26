"""Original, synthetic records for the network-free demo and tests.

The SWAPI-shaped identifiers below are fixture identities, not claims about
the corresponding real API records. This dataset is never fetched remotely.
"""


def fixture() -> tuple[list[dict], list[dict]]:
    people = [
        {
            "url": "https://swapi.dev/api/people/9001/",
            "name": "Ari Vale",
            "height": "172",
            "mass": "68",
        },
        {
            "url": "https://swapi.dev/api/people/9002/",
            "name": "Mira Chen",
            "height": "180",
            "mass": "unknown",
        },
        {
            "url": "https://swapi.dev/api/people/9003/",
            "name": "Sol Reed",
            "height": "unknown",
            "mass": "83",
        },
    ]
    ships = [
        {
            "url": "https://swapi.dev/api/starships/9001/",
            "name": "Aurora",
            "model": "Courier Mk I",
            "manufacturer": "Orion Works",
            "length": "34.5",
            "pilots": [people[0]["url"], people[1]["url"]],
        },
        {
            "url": "https://swapi.dev/api/starships/9002/",
            "name": "Horizon",
            "model": "Survey Mk II",
            "manufacturer": "Atlas Engineering",
            "length": "1,200",
            "pilots": [people[0]["url"]],
        },
        {
            "url": "https://swapi.dev/api/starships/9003/",
            "name": "Relay",
            "model": "Drone Mk I",
            "manufacturer": "Orion Works",
            "length": "unknown",
            "pilots": [],
        },
    ]
    return people, ships
