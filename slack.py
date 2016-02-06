import json
import asyncio
import websockets
from slacker import Slacker
from slackclient import SlackClient

APIKEY = ""
SLACK = None
SC = None
CON = None
DATA = {}


def setSlackData(apikey):
    global APIKEY, SLACK, SC
    APIKEY = apikey
    SLACK = Slacker(APIKEY)
    SC = SlackClient(APIKEY)


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

    #printTests()


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