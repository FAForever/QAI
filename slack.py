import json
import asyncio
import websockets
from slacker import Slacker

APIKEY = ""
SLACK = None
CON = ""
DATA = {}


def setSlackData(apikey):
    global APIKEY, SLACK
    APIKEY = apikey
    SLACK = Slacker(APIKEY)


def start():
    global CON, DATA
    CON = SLACK.rtm.start()

    DATA['users'] = {}
    for user in CON.body['users']:
        DATA['users'][user['id']] = {
            'name': user['name'],
        }
    DATA['channels'] = {}
    for channel in CON.body['channels']:
        DATA['channels'][channel['id']] = {
            'name': channel['name'],
        }

    printTests()



def getUserId(name):
    return getId('users', name)


def getChannelId(name):
    return getId('channels', name)


def getId(sub, name):
    for key in DATA[sub].keys():
        if DATA[sub][key]['name'] == name:
            return key
    return None




def printTests():
    print("user washy is: " + getUserId('washy'))
    print("channel random is: " + getChannelId('random'))

    #for key in DATA['channels'].keys():
    #    print(key + ": " + DATA['channels'][key]['name'])

    #print(CON.body['url'])