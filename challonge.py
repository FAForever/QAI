import json
import random
import asyncio
import re
import aiohttp

CHALLONGE_TOURNEYS = ""

def setChallongeTourneyLink(link):
    global CHALLONGE_TOURNEYS
    CHALLONGE_TOURNEYS = link

#----------------------------------------------

@asyncio.coroutine
def tourney_list():
    req = yield from aiohttp.request('GET', CHALLONGE_TOURNEYS + "tournaments.json")
    try:
        return json.loads((yield from req.read()).decode())
    except:
        return []

@asyncio.coroutine
def printable_tourney_list():
    tourneys = yield from tourney_list()
    tourney_strings = []

    for tourney in tourneys:
        try:
            description = tourney['tournament'].get("description")

            tourney_strings.append("{name}: {description} ({link})".format(
                **{
                    "name": tourney['tournament'].get("name", "Untitled"),
                    "description": re.sub("<[^<>]+>", "", re.sub("(<span>|[\r\n]|[\n]|[\.]|[\?]).*", "", description)),
                    "link": tourney['tournament'].get("full_challonge_url"),
                }))
        except (KeyError, ValueError):
            continue
    return tourney_strings