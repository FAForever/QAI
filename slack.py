import json
import threading
from slackclient import SlackClient


class slackThread(threading.Thread):
    def __init__(self, apikey):
        threading.Thread.__init__(self)
        self.APIKEY = apikey
        self.DATA = {}
        self.SC = SlackClient(self.APIKEY)
        self.CON = None


    def run(self):
        self.CON = self.SC.rtm_connect()
        if self.CON == False:
            print('Failed starting a Slack RTM session.')
        self.rebuildData()
        self.__printTests()


    def rebuildData(self):
        test = json.loads((self.SC.api_call("api.test")).decode())
        if test.get('ok') == False:
            print('API Test failed. Full response:')
            print(test)
            return
        self.DATA['users'] = {}
        for user in json.loads((self.SC.api_call("users.list")).decode()).get('members'):
            self.DATA['users'][user['id']] = {
                'name': user['name'],
            }
        self.DATA['channels'] = {}
        for channel in json.loads((self.SC.api_call("channels.list")).decode()).get('channels'):
            self.DATA['channels'][channel['id']] = {
                'name': channel['name'],
            }


    def __getUserId(self, name):
        return self.__getId('users', name)


    def __getChannelId(self, name):
        return self.__getId('channels', name)


    def __getId(self, sub, name):
        for key in self.DATA[sub].keys():
            if self.DATA[sub][key]['name'] == name:
                return key
        return None


    def __getPmChannelId(self, name):
        user = self.__getUserId(name)
        if user == None:
            return None
        channelId = self.DATA['users'][user].get('pm_channel_id')
        if channelId == None:
            data = json.loads((self.SC.api_call("im.open", user=user)).decode())
            channelId = data["channel"]["id"]
            self.DATA['users'][user]['pm_channel_id'] = channelId
        return channelId


    def sendMessageToUser(self, user, text):
        channelId = self.__getPmChannelId(user)
        if channelId == None:
            return
        self.SC.api_call(
            "chat.postMessage",
            as_user="true",
            channel=channelId,
            text=text)


    def __printTests(self):
        print("user washy is: " + self.__getUserId('washy'))
        print("channel random is: " + self.__getChannelId('random'))
        self.sendMessageToUser('washy', 'test <3 <3')

        #for key in self.DATA['channels'].keys():
        #    print(key + ": " + self.DATA['channels'][key]['name'])
