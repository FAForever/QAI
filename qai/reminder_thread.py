import threading
import time
from datetime import datetime


class StartOverException(Exception):
    """Raise to restart the reminder thread loop"""
    pass


# TODO set a limit on reminders per user? also same for offlinemessages
class ReminderThread(threading.Thread):
    def __init__(self, bot_object, bot):
        threading.Thread.__init__(self)
        self.new_reminder = threading.Event()
        self.bot = bot
        self.bot_object = bot_object

    def run(self):
        while True:
            try:
                try:
                    time_to_wait, receiver, reminder = self._time_until_reminding()
                except (KeyError, TypeError, IndexError):
                    raise StartOverException
                time.sleep(1)
                for second in range(0, time_to_wait + 1):
                    if not self.new_reminder_added():
                        time.sleep(1)
                        if second >= time_to_wait:
                            self.bot_object._try_to_remind(receiver, reminder)
                    else:
                        self.unset_new_reminder()
                        raise StartOverException
                raise StartOverException
            except StartOverException as ex:
                time.sleep(1)
                continue

    def _time_until_reminding(self):
        current_time = datetime.now()
        try:
            reminders = self.bot_object._Plugin__db_get(['reminders'])
            receiver_key, reminder_key = self._get_earliest_reminder()
            earliest_reminder_time = datetime.strptime(reminders[receiver_key][reminder_key]['when_to_remind'], '%Y-%m-%d %H:%M:%S.%f')
        except (KeyError, IndexError, TypeError):
            return
        if current_time < earliest_reminder_time:
            difference = earliest_reminder_time - current_time
            time_to_wait = int(difference.total_seconds())
        else:
            time_to_wait = 1
        return time_to_wait, receiver_key, reminder_key

    def _get_earliest_reminder(self):
        reminders_dict = self.bot_object._Plugin__db_get(['reminders'])
        key_order = list(reminders_dict.keys())
        reminder_key_order = [list(reminders_dict[key].keys()) for key in key_order]
        earliest_reminder = '2200-01-01 00:00:00.000000'
        earliest_receiver_key, earliest_reminder_key = None, None
        for i, receiver_key in enumerate(key_order):
            for reminder_key in reminder_key_order[i]:
                if reminders_dict[receiver_key][reminder_key]['when_to_remind'] < earliest_reminder:
                    earliest_reminder = reminders_dict[receiver_key][reminder_key]['when_to_remind']
                    earliest_receiver_key = receiver_key
                    earliest_reminder_key = reminder_key
        return earliest_receiver_key, earliest_reminder_key

    def refresh_with_new_reminder(self):
        return self.new_reminder.set()

    def new_reminder_added(self):
        return self.new_reminder.is_set()

    def unset_new_reminder(self):
        return self.new_reminder.clear()

    def reminders_arent_empty(self):
        if self.bot_object._Plugin__db_get(['reminders']):
            return True
        else:
            return False
