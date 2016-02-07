import json
import threading
import time
from slackclient import SlackClient


class slackThread(threading.Thread):
    def __init__(self, apikey):
        threading.Thread.__init__(self)
        self.APIKEY = apikey
        self.DATA = {}
        self.SC = SlackClient(self.APIKEY)
        self.CON = None
        self.lock = threading.Lock()
        self.messageId = 0
        self.handledEvents = {
            'message':      self.__event__message,
        }


    def run(self):
        works = True
        self.CON = self.SC.rtm_connect()
        if self.CON == False:
            print('Failed starting a Slack RTM session.')
            works = False
        if not self.rebuildData():
            print('Failed accessing slack data.')
            works = False
        if works:
            print('Established Slack connection')


        countForPing = 0
        while True:
            for event in self.SC.rtm_read():
                try:
                    self.handledEvents[event['type']](event)
                except:
                    #print(event)
                    pass
            countForPing += 0.1
            if countForPing > 3:
                self.SC.server.ping()
                countForPing = 0
            time.sleep(0.1)


    def rebuildData(self):
        self.lock.acquire()
        test = json.loads((self.SC.api_call("api.test")).decode())
        if test.get('ok') == False:
            print('API Test failed. Full response:')
            print(test)
            self.lock.release()
            return False
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
        self.lock.release()
        return True


    def __getMessageId(self):
        self.lock.acquire()
        mId = self.messageId
        self.messageId += 1
        self.lock.release()
        return mId


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
        self.lock.acquire()
        channelId = self.__getPmChannelId(user)
        if channelId == None:
            return
        self.SC.api_call(
            "chat.postMessage",
            as_user="true",
            channel=channelId,
            text=text)
        self.lock.release()


    def __event__message(self, event):
        print(self.DATA['users'][event['user']]['name'] + ": " + event['text'])
