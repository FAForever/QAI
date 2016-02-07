import json
import asyncio
import websockets
from slackclient import SlackClient

APIKEY = ""
SC = None
CON = None
DATA = {}


def setSlackData(apikey):
    global APIKEY, SC
    APIKEY = apikey
    SC = SlackClient(APIKEY)


def start():
    global CON, DATA
    rebuildData()
    #printTests()


def rebuildData():
    DATA['users'] = {}
    for user in json.loads((SC.api_call("users.list")).decode()).get('members'):
        DATA['users'][user['id']] = {
            'name': user['name'],
        }
    DATA['channels'] = {}
    for channel in json.loads((SC.api_call("channels.list")).decode()).get('channels'):
        DATA['channels'][channel['id']] = {
            'name': channel['name'],
        }


def getUserId(name):
    return getId('users', name)


def getChannelId(name):
    return getId('channels', name)


def getId(sub, name):
    for key in DATA[sub].keys():
        if DATA[sub][key]['name'] == name:
            return key
    return None


def getPmChannelId(name):
    user = getUserId(name)
    if user == None:
        return None
    channelId = DATA['users'][user].get('pm_channel_id')
    if channelId == None:
        data = json.loads((SC.api_call("im.open", user=user)).decode())
        channelId = data["channel"]["id"]
        DATA['users'][user]['pm_channel_id'] = channelId
    return channelId


def sendMessageToUser(user, text):
    channelId = getPmChannelId(user)
    if channelId == None:
        return
    SC.api_call(
        "chat.postMessage",
        asUser="true:",
        channel=channelId,
        text=text)






def printTests():
    print("user washy is: " + getUserId('washy'))
    print("channel random is: " + getChannelId('random'))

    #for key in DATA['channels'].keys():
    #    print(key + ": " + DATA['channels'][key]['name'])

    #print(CON.body['url'])