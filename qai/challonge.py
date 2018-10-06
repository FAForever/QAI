import json
import random
import aiohttp
import string

USER = ""
API_KEY = ""
API_LINK = ""


def set_challonge_data(username, api_key):
    global USER, API_KEY, API_LINK
    USER, API_KEY, API_LINK = username, api_key, "https://" + username + ":" + api_key + "@api.challonge.com/v1/"

# http://api.challonge.com/v1
# ----------------------------------------------


def get_faf_default_settings():
    # they will have to converted into the 'tournament[name]' style
    return {
        "name": "Blitz tournament",
        "description": "Automatically generated tournament",
        "tournament_type": "single elimination",
        # "single elimination",
        # "double elimination",
        # "round robin", "swiss"
        # "hold_third_place_match" : True,
        # "open_signup" : False,
        # "ranked_by" : "match wins",
        # "signup_cap" : 32,
    }


def __build_json_params(params, prefix=None):
    p = {}
    for key in params.keys():
        if prefix:
            p["%s[%s]" % (prefix, key)] = params[key]
        else:
            p[key] = params[key]
    return p

# ----------------------------------------------


async def tourney_list():
    async with aiohttp.request('GET', API_LINK + "tournaments.json") as req:
        try:
            return json.loads((await req.read()).decode())
        except Exception as ex:
            return []


async def get_tourney_by_link(link):
    async with aiohttp.request('GET', API_LINK + "tournaments/" + link + ".json") as req:
        tourney = await req
    try:
        tourney = json.loads((await tourney.read()).decode())
        if tourney.get("error", False):
            return None
        return tourney
    except Exception as ex:
        return None


async def get_available_tourney_link():
    while True:
        link = 'FAF_'
        for _ in range(10):
            value = string.ascii_uppercase + string.ascii_lowercase + string.digits
            link += ''.join(random.SystemRandom().choice(value))
        is_available = ((await get_tourney_by_link(link)) is None)
        if is_available:
            return link


async def printable_tourney_list():
    tourneys = await tourney_list()
    tourney_strings = []

    for tourney in tourneys:
        try:
            if tourney["tournament"].get("completed_at", None) is not None:
                continue
            # description = tourney['tournament'].get("description")
            tourney_strings.append("{name}: {link} - {participants} signups".format(
                **{
                    "name": tourney['tournament'].get("name", "Untitled"),
                    "link": tourney['tournament'].get("full_challonge_url"),
                    "participants": tourney['tournament'].get("participants_count"),
                }))
        except (KeyError, ValueError):
            continue
    return tourney_strings


async def printable_tourney_list_ids():
    tourneys = await tourney_list()
    tourney_strings = []

    for tourney in tourneys:
        try:
            # description = tourney['tournament'].get("description")

            tourney_strings.append("{id}: \"{name}\"".format(
                **{
                    "name": tourney['tournament'].get("name", "Untitled"),
                    "id": tourney['tournament'].get("id"),
                }))
        except (KeyError, ValueError):
            continue
    return tourney_strings


async def create_tourney(args):
    link = await get_available_tourney_link()

    defaults = get_faf_default_settings()
    for arg in args.keys():
        defaults[arg] = args[arg]
    defaults["url"] = link

    data = __build_json_params(defaults, "tournament")
    j = json.dumps(data)

    print(data)
    with aiohttp.request('POST', API_LINK + "tournaments.json", data=j) as req:
        response = await req
        text = json.loads((await response.read()).decode())
    print(text)
