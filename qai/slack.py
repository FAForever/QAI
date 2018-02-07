import json
import threading
import time
from slackclient import SlackClient
from slackclient.server import SlackLoginError


class SlackThread(threading.Thread):
    def __init__(self, api_key):
        threading.Thread.__init__(self)
        self.API_KEY = api_key
        self.DATA = {}
        self.SC = SlackClient(self.API_KEY)
        self.CON = None
        self.lock = threading.Lock()
        self.messageId = 0
        self.handledEvents = {
            'message':      self.__event__message,
        }
        self.ready = False

    def run(self):
        works = True
        try:
            self.CON = self.SC.rtm_connect()
        except SlackLoginError as ex:
            print('Slack login error: ' + ex.reply)
        if not self.CON:
            print('Failed starting a Slack RTM session.')
            works = False
        if not self.rebuild_data():
            print('Failed accessing slack data.')
            works = False
        if works:
            print('Established Slack connection')
            self.ready = True
        else:
            print('Slack connection not established')
            return

        count_for_ping = 0
        while True:
            for event in self.SC.rtm_read():
                try:
                    self.handledEvents[event['type']](event)
                except SlackLoginError as ex:
                    print('Slack login error: ' + ex.reply)
                except Exception as ex:
                    print('TODO: Better exception handling.')
                    # print(event)
                    pass
            count_for_ping += 0.1
            if count_for_ping > 3:
                self.SC.server.ping()
                count_for_ping = 0
            time.sleep(0.1)

    def rebuild_data(self):
        self.lock.acquire()
        # test = False
        try:
            tmp_val = self.SC.api_call("api.test")
            test = json.loads(tmp_val.decode())
        except AttributeError as ex:
            print('TODO: Better exception handling. \n\t')
            return False
        if not test.get('ok'):
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

    def __get_message_id(self):
        self.lock.acquire()
        m_id = self.messageId
        self.messageId += 1
        self.lock.release()
        return m_id

    def __get_user_id(self, name):
        return self.__get_id('users', name)

    def __get_channel_id(self, name):
        return self.__get_id('channels', name)

    def __get_id(self, sub, name):
        if self.ready:
            for key in self.DATA[sub].keys():
                if self.DATA[sub][key]['name'] == name:
                    return key
            return None

    def __get_pm_channel_id(self, name):
        user = self.__get_user_id(name)
        if user is None:
            return None
        channel_id = self.DATA['users'][user].get('pm_channel_id')
        if channel_id is None:
            data = json.loads((self.SC.api_call("im.open", user=user)).decode())
            channel_id = data["channel"]["id"]
            self.DATA['users'][user]['pm_channel_id'] = channel_id
        return channel_id

    def send_message_to_user(self, user, text):
        channel_id = self.__get_pm_channel_id(user)
        if channel_id is None:
            return
        self.__send_message(channel_id, text)

    def send_message_to_channel(self, channel, text):
        channel_id = self.__get_channel_id(channel)
        if channel_id is None:
            return
        self.__send_message(channel_id, text)

    def __send_message(self, target, text):
        self.lock.acquire()
        self.SC.api_call(
            "chat.postMessage",
            as_user="true",
            channel=target,
            text=text)
        self.lock.release()

    def __event__message(self, event):
        # print(self.DATA['users'][event['user']]['name'] + ": " + event['text'])
        pass
