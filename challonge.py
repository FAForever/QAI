import json
import random
import asyncio
import re
import aiohttp
import string

USER = ""
APIKEY = ""
API_LINK = ""

def setChallongeData(username, apikey):
    global USER, APIKEY, API_LINK
    USER, APIKEY, API_LINK = username, apikey, "https://"+username+":"+apikey+"@api.challonge.com/v1/"

# http://api.challonge.com/v1
#----------------------------------------------

def getFAFDefaultSettings():
    # they will have to converted into the 'tournament[name]' style
    return {
        "name": "Blitz tournament",
        "description": "Automatically generated tournament",
        "tournament_type" : "single elimination",               #"single elimination", "double elimination", "round robin", "swiss"
        #"hold_third_place_match" : True,
        #"open_signup" : False,
        #"ranked_by" : "match wins",
        #"signup_cap" : 32,
    }

def __buildJSONParams(params, prefix=None):
    p = {}
    for key in params.keys():
        if prefix:
            p["%s[%s]" % (prefix, key)] = params[key]
        else:
            p[key] = params[key]

    return p

#----------------------------------------------

@asyncio.coroutine
def tourney_list():
    req = yield from aiohttp.request('GET', API_LINK + "tournaments.json")
    try:
        return json.loads((yield from req.read()).decode())
    except:
        return []

@asyncio.coroutine
def getTourneyByLink(link):
    tourney = yield from aiohttp.request('GET', API_LINK + "tournaments/" + link + ".json")
    try:
        tourney = json.loads((yield from tourney.read()).decode())
        if error in tourney:
            return None
        return tourney
    except:
        return None

@asyncio.coroutine
def getAvailableTourneyLink():
    while True:
        link = 'FAF_'+''.join(random.SystemRandom().choice(string.ascii_uppercase + string.ascii_lowercase + string.digits) for _ in range(10))
        isAvailable = ((yield from getTourneyByLink(link)) == None)
        if isAvailable:
            return link

@asyncio.coroutine
def printable_tourney_list():
    tourneys = yield from tourney_list()
    tourney_strings = []

    for tourney in tourneys:
        try:
            description = tourney['tournament'].get("description")

            tourney_strings.append("{name}: {description} ({link}) - {participants} signups".format(
                **{
                    "name": tourney['tournament'].get("name", "Untitled"),
                    "description": re.sub("<[^<>]+>", "", re.sub("(<span>|\r\n|\n|\.|\?|http|www).*", "", description)),
                    "link": tourney['tournament'].get("full_challonge_url"),
                    "participants": tourney['tournament'].get("participants_count"),
                }))
        except (KeyError, ValueError):
            continue
    return tourney_strings

@asyncio.coroutine
def printable_tourney_list_ids():
    tourneys = yield from tourney_list()
    tourney_strings = []

    for tourney in tourneys:
        try:
            description = tourney['tournament'].get("description")

            tourney_strings.append("{id}: \"{name}\"".format(
                **{
                    "name": tourney['tournament'].get("name", "Untitled"),
                    "id": tourney['tournament'].get("id"),
                }))
        except (KeyError, ValueError):
            continue
    return tourney_strings

@asyncio.coroutine
def create_tourney(args):
    link = yield from getAvailableTourneyLink()

    defaults = getFAFDefaultSettings()
    for arg in args.keys():
        defaults[arg] = args[arg]
    defaults["url"] = link

    data = __buildJSONParams(defaults, "tournament")
    j = json.dumps(data)

    print(data)
    response = yield from aiohttp.request('POST', API_LINK + "tournaments.json", data=j)
    text = json.loads((yield from response.read()).decode())
    print(text)





