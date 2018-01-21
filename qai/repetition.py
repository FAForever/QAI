import threading
import time


class repetitionThread(threading.Thread):
    def __init__(self, bot, channel, text, seconds):
        threading.Thread.__init__(self)
        self._stop = threading.Event()
        self.bot = bot
        self.channel = channel
        self.text = text
        self.seconds = seconds

    def run(self):
        while not self.isStopped():
            self.bot.privmsg(self.channel, self.text)
            time.sleep(self.seconds)

    def stop(self):
        self._stop.set()

    def isStopped(self):
        return self._stop.isSet()