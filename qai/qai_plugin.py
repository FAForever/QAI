# vim: ts=4 et sw=4 sts=4
# -*- coding: utf-8 -*-
import json
import random
import asyncio
import re
import aiohttp
import itertools
import time
from datetime import datetime, timedelta
from urllib.parse import urlparse, parse_qs
import threading
import irc3
from irc3.plugins.command import command
from irc3.utils import IrcString

from qai import repetition, challonge, slack, reminder_thread
from qai.taunts import TAUNTS, SPAM_PROTECT_TAUNTS, KICK_TAUNTS
from qai.links import LINKS, LINKS_SYNONYMES, WIKI_LINKS, WIKI_LINKS_SYNONYMES, OTHER_LINKS
from qai.decorators import nickserv_identified, channel_only

ALL_TAUNTS = []  # extended in init
BAD_WORDS = {}
REACTION_WORDS = {}
REPETITIONS = {}
OFFLINE_MESSAGE_RECEIVERS = {}
REMINDER_RECEIVERS = {}
NICK_SERV_IDENTIFIED_RESPONSES = {}
NICK_SERV_IDENTIFIED_RESPONSES_LOCK = None
MAIN_CHANNEL = "#aeolus"
TWITCH_API_LOGIN = "https://api.twitch.tv/kraken/users/"
TWITCH_STREAMS = "https://api.twitch.tv/kraken/streams/?game=Supreme+Commander:+Forged+Alliance"  # add the game name at the end of the link (space = "+", eg: Game+Name)
HIT_BOX_STREAMS = "https://api.hitbox.tv/media/live/list?filter=popular&game=811&hiddenOnly=false&limit=30&liveonly=true&media=true"
YOUTUBE_NON_API_SEARCH_LINK = "https://www.youtube.com/results?search_query=supreme+commander+%7C+forged+alliance&search_sort=video_date_uploaded&filters=video"
YOUTUBE_SEARCH = "https://www.googleapis.com/youtube/v3/search?order=date&type=video&part=snippet&q=Forged%2BAlliance|Supreme%2BCommander&relevanceLanguage=en&maxResults=15&key={}"
YOUTUBE_DETAIL = "https://www.googleapis.com/youtube/v3/videos?part=snippet,statistics&id={}&key={}"
YOUTUBE_STREAMS = "https://content.googleapis.com/youtube/v3/search?eventType=live&maxResults=5&order=viewCount&part=snippet&q=Supreme%2BCommander&relevanceLanguage=en&type=video&key={}"
LET_ME_GOOGLE_IT_FOR_YOU = "http://lmgtfy.com/?q="
URL_MATCH = ".*(https?:\/\/[^ ]+\.[^ ]*).*"
REPLAY_MATCH = ".*(#[0-9]+).*"


@irc3.extend
def action(bot, *args):
    bot.privmsg(args[0], '\x01ACTION ' + args[1] + '\x01')


@irc3.plugin
class Plugin(object):
    requires = [
        'irc3.plugins.userlist'
    ]

    def __init__(self, bot):
        self.bot = bot
        self.timers = {}
        self._rage = {}
        global ALL_TAUNTS, NICK_SERV_IDENTIFIED_RESPONSES_LOCK, REMINDER_DB_ACTION_LOCK
        ALL_TAUNTS.extend(TAUNTS)
        ALL_TAUNTS.extend(SPAM_PROTECT_TAUNTS)
        challonge.set_challonge_data(self.bot.config['challonge_username'], self.bot.config['challonge_api_key'])
        NICK_SERV_IDENTIFIED_RESPONSES_LOCK = threading.Lock()
        REMINDER_DB_ACTION_LOCK = threading.Lock()

        self.slackThread = slack.SlackThread(self.bot.config['slack_api_key'])
        self.slackThread.daemon = True
        self.slackThread.start()

    def start_reminder_thread(self):
        self.reminder = reminder_thread.ReminderThread(self, self.bot)
        self.reminder.daemon = True
        self.reminder.start()

    @classmethod
    def reload(cls, old):
        return cls(old.bot)

    def after_reload(self):
        self._taunt('#qai_channel')

    @irc3.event(irc3.rfc.CONNECTED)
    def nick_serv_auth(self, *args, **kwargs):
        self.bot.privmsg('nickserv', 'identify %s' % self.bot.config['nickserv_password'])
        global REPETITIONS, BAD_WORDS, REACTION_WORDS, OFFLINE_MESSAGE_RECEIVERS, REMINDER_RECEIVERS

        self.__db_add([], 'chatlists', {}, overwrite_if_exists=False)
        self.__db_add([], 'offlinemessages', {}, overwrite_if_exists=False)
        self.__db_add(['repetitions'], 'text', {}, overwrite_if_exists=False)
        self.__db_add(['blacklist'], 'users', {}, overwrite_if_exists=False)
        self.__db_add(['groups'], 'playergroups', {}, overwrite_if_exists=False)
        self.__db_add(['badwords'], 'words', {}, overwrite_if_exists=False)
        self.__db_add(['reactionwords'], 'words', {}, overwrite_if_exists=False)
        self.__db_add([], 'reminders', {}, overwrite_if_exists=False)
        BAD_WORDS = self.__db_get(['badwords', 'words'])
        REACTION_WORDS = self.__db_get(['reactionwords', 'words'])

        for r in self.__db_get(['offlinemessages']).keys():
            OFFLINE_MESSAGE_RECEIVERS[r] = True
            self._try_deliver_offline_messages(r)

        for r in self.__db_get(['reminders']).keys():
            REMINDER_RECEIVERS[r] = True

        repetitions = self.__db_get(['repetitions', 'text'])
        for t in repetitions.keys():
            REPETITIONS[t] = repetition.RepetitionThread(self.bot, repetitions[t].get('channel'),
                                                         repetitions[t].get('text'), int(repetitions[t].get('seconds')))
            REPETITIONS[t].daemon = True
            REPETITIONS[t].start()
        self.start_reminder_thread()

    @irc3.event(irc3.rfc.JOIN)
    def on_join(self, channel, mask):
        if channel == MAIN_CHANNEL:
            for channel in self.__db_get(['chatlists']):
                if mask.nick in self.__db_get(['chatlists', channel]).keys():
                    self.move_user(channel, mask.nick)
        if OFFLINE_MESSAGE_RECEIVERS.get(mask.nick, False):
            self._try_deliver_offline_messages(mask.nick)

    def move_user(self, channel, nick):
        self.bot.privmsg('OperServ', 'svsjoin %s %s' % (nick, channel))

    @irc3.event(irc3.rfc.PRIVMSG)
    async def on_priv_msg(self, *args, **kwargs):
        msg, channel, sender = kwargs['data'], kwargs['target'], kwargs['mask']
        if self.bot.config['nick'] in sender.nick:
            return
        try:
            link_url = re.match(URL_MATCH, msg).groups()[0]
            uri = urlparse(link_url)
            ytid = parse_qs(uri.query).get('v', '')[0]
            if len(ytid) > 0:
                async with aiohttp.request('GET', YOUTUBE_DETAIL.format(ytid, self.bot.config['youtube_key'])) as req:
                    data = json.loads((await req.read()).decode())['items'][0]

                self.bot.privmsg(channel, "{title} - {views} views - {likes} likes (Linked above by {sender})".format(
                    title=data['snippet']['title'],
                    views=data['statistics']['viewCount'],
                    likes=data['statistics']['likeCount'],
                    sender=sender.nick))
        except (KeyError, ValueError, AttributeError, IndexError):
            pass

        try:
            replay_id = re.match(REPLAY_MATCH, msg).groups()[0]
            replay_id = replay_id.replace('#', '')
            r_id = int(replay_id)
            if 1000000 <= r_id < 100000000:
                url = LINKS["replay"].replace("ID", replay_id)
                self.bot.privmsg(channel, url)
        except Exception as ex:
            pass

        if channel.startswith("#"):
            lowercase_msg = msg.lower()
            for reaction_word in REACTION_WORDS:
                if reaction_word in lowercase_msg:
                    if self.spam_protect('rword-' + reaction_word, sender, channel, args, no_penalty=True):
                        continue
                    self.bot.privmsg(channel, REACTION_WORDS[reaction_word].format(**{
                        "sender": sender.nick,
                    }))
            for bad_word in BAD_WORDS:
                if bad_word in lowercase_msg:
                    self.report(sender.nick, bad_word, channel, msg, BAD_WORDS[bad_word])

        if sender.startswith("NickServ!"):
            self.__handle_nick_serv_message(msg)

    @command(permission='admin', public=False)
    @nickserv_identified
    def hidden(self, mask, target, args):
        """Actually shows hidden commands

            %%hidden
        """
        words = ["join", "leave", "puppet", "reload", "groupmanage", "blacklist", "badwords", "reactionwords", "repeat",
                 "move", "chatlist"]
        self.bot.privmsg(mask.nick, "Hidden commands (!help <command> for more info):")
        for word in words:
            self.bot.privmsg(mask.nick, "- " + word)

    @command(permission='admin')
    @channel_only
    @nickserv_identified
    def taunt(self, mask, target, args):
        """Send a taunt

            %%taunt
            %%taunt <person>
        """
        p = args.get('<person>')
        if p == self.bot.config['nick']:
            p = mask.nick
        self._taunt(channel=target, prefix=p, taunt_table=TAUNTS)

    @command(permission='admin')
    @channel_only
    @nickserv_identified
    def explode(self, mask, target, args):
        """Explode

            %%explode
        """
        self.bot.action(target, "explodes")

    @command(permission='admin')
    @channel_only
    @nickserv_identified
    def hug(self, mask, target, args):
        """Hug someone

            %%hug
            %%hug <someone>
        """
        someone = args['<someone>']
        if someone is None:
            someone = mask.nick
        elif someone == self.bot.config['nick']:
            self._taunt(channel=target, prefix=mask.nick)
            return
        self.bot.action(target, "hugs " + someone)

    @command(permission='admin')
    @channel_only
    @nickserv_identified
    def flip(self, mask, target, args):
        """Flip table

            %%flip
        """
        self.bot.privmsg(target, "(╯°□°）╯︵ ┻━┻")

    @command(permission='admin', show_in_help_list=False)
    @nickserv_identified
    def join(self, mask, target, args):
        """Overtake the given channel

            %%join <channel>
        """
        self.bot.join(args['<channel>'])

    @command(permission='admin', show_in_help_list=False)
    @nickserv_identified
    def leave(self, mask, target, args):
        """Leave the given channel

            %%leave
            %%leave <channel>
        """
        channel = args['<channel>']
        if channel is None:
            channel = target
        self.bot.part(channel)

    @command
    def gullible(self, mask, target, args):
        """Display additional commands

            %%gullible
        """
        self._taunt(channel=target, prefix=mask.nick, taunt_table=SPAM_PROTECT_TAUNTS)

    @command
    def link(self, mask, target, args):
        """Link to a website

            %%link
            %%link <argument>
            %%link <argument> WORDS...
        """
        try:
            self.pm_fix(mask, target, LINKS_SYNONYMES[args['<argument>']])
            return
        except Exception as ex:
            pass

        try:
            self.pm_fix(mask, target, LINKS[args['<argument>']])
        except Exception as ex:
            if self.spam_protect('links', mask, target, args):
                return

            msg = ""
            if not args['<argument>'] is None:
                msg = "Unknown link: \"" + args['<argument>'] + "\". "
            msg += "Do you mean one of these: " + " / ".join(LINKS.keys()) + " ?"
            self.pm_fix(mask, target, msg)

    @command
    def wiki(self, mask, target, args):
        """Link to a wiki page

            %%wiki
            %%wiki <argument>
            %%wiki <argument> WORDS...
        """
        try:
            self.pm_fix(mask, target, WIKI_LINKS_SYNONYMES[args['<argument>']])
            return
        except Exception as ex:
            pass

        try:
            self.pm_fix(mask, target, WIKI_LINKS[args['<argument>']])
        except Exception as ex:
            if self.spam_protect('wiki', mask, target, args):
                return

            # TODO is this necessary?
            # msg = ""
            if not args['<argument>'] is None:
                msg = "Unknown wiki link: \"" + args['<argument>'] + "\". Do you mean one of these: "
            else:
                msg = LINKS["wiki"] + " For better matches try !wiki "
            msg += " / ".join(WIKI_LINKS.keys())
            if not args['<argument>'] is None:
                msg += " ?"
            self.pm_fix(mask, target, msg)

    #TODO get rid of mandatory argument order
    @command
    @nickserv_identified
    def remind(self, mask, target, args):
        """Have the bot deliver a message after specified time.
           Each time argument is optional but must provide at least one.
           The order of arguments must be preserved.
           Example: !remind person in 1 hour 25 minutes 10 seconds look outta the window kid


            %%remind <playername> in [(<days> (day | days))] [(<hours> (hour | hours))] [(<minutes> (minute | minutes))] [(<seconds> (second | seconds))] MESSAGE...
        """
        if self.spam_protect('remind', mask, target, args):
            return
        """Doesn't seem like docopt handles "at least one out of many" argument logic without it getting ugly
         or at least I didn't figure out how to do it so going with a tad less ugly check"""
        if not args.get('<seconds>') and not args.get('<minutes>') and not args.get('<hours>') and not args.get('<days>'):
            return 'Invalid arguments.'

        global REMINDER_RECEIVERS, REMINDER_DB_ACTION_LOCK
        player_name = args.get('<playername>')
        try:
            time_before_reminding = {
                'seconds': int(args.get('<seconds>', 0) or 0),
                'minutes': int(args.get('<minutes>', 0) or 0),
                'hours': int(args.get('<hours>', 0) or 0),
                'days': int(args.get('<days>', 0) or 0)
            }
        except ValueError:
            return 'Only whole numbers allowed.'
        message = 'Reminder: ' + " ".join(args.get('MESSAGE'))
        try:
            with REMINDER_DB_ACTION_LOCK:
                if self.reminder.reminders_arent_empty():
                    self.reminder.refresh_with_new_reminder()
                self.__db_add(['reminders', player_name], mask.nick,
                              {'message': message, 'sender': mask.nick, 'time': str(time.strftime("%d-%m-%Y %H:%M:%S")),
                              'when_to_remind': str(datetime.now() + timedelta(days=time_before_reminding['days'],
                                                                               seconds=time_before_reminding['seconds'],
                                                                               microseconds=0,
                                                                               milliseconds=0,
                                                                               minutes=time_before_reminding['minutes'],
                                                                               hours=time_before_reminding['hours'],
                                                                               weeks=0))},
                                overwrite_if_exists=False, try_saving_with_new_key=True)
                REMINDER_RECEIVERS[player_name] = True
            return 'Reminder taken.'
        except TypeError:
            return 'Invalid arguments.'

    @command(public=False, name='offlinemessage')
    @nickserv_identified
    def offline_message(self, mask, target, args):
        """Store an offline message, it is delivered once the person logs on

            %%offlinemessage <playername> WORDS ...
        """
        player_name, message = args.get('<playername>'), " ".join(args.get('WORDS'))
        if mask.nick == player_name:
            self._taunt(mask.nick)
            return
        is_online, channel = self.__is_in_bot_channel(player_name)
        if is_online:
            return "The player is online in " + channel + ", tell him yourself."
        self.__db_add(['offlinemessages', player_name], mask.nick,
                      {'message': message, 'sender': mask.nick, 'time': str(time.strftime("%d-%m-%Y %H:%M:%S"))},
                      overwrite_if_exists=False, try_saving_with_new_key=True)
        OFFLINE_MESSAGE_RECEIVERS[player_name] = True
        self.bot.privmsg(mask.nick,
                         "The message is saved and will be delivered once " + player_name + " is online again.")

    @command(permission='admin', public=False, show_in_help_list=False)
    @nickserv_identified
    def puppet(self, mask, target, args):
        """Puppet

            %%puppet <target> WORDS ...
        """
        t = args.get('<target>')
        m = " ".join(args.get('WORDS'))
        self.bot.privmsg(t, m)

    @command(permission='admin', public=False, show_in_help_list=False)
    def mode(self, mask, target, args):
        """mode

            %%mode <channel> <mode> <nick>
        """
        # if not (await self.__isNickservIdentified(mask.nick)):
        #    return
        self.bot.send_line('MODE {} {} {}'.format(
            args.get('<channel>'),
            args.get('<mode>'),
            args.get('<nick>'),
        ), nowait=True)

    @command(permission='admin', public=False, show_in_help_list=False)
    @nickserv_identified
    def reload(self, mask, target, args):
        """Reboot the mainframe

            %%reload
        """
        self.bot.reload(self.bot.config['nick'])

    @command(permission='admin')
    @channel_only
    @nickserv_identified
    def slap(self, mask, target, args):
        """Slap this guy

            %%slap <guy>
        """
        self.bot.action(target, "slaps %s " % args['<guy>'])

    #TODO fix for pm too
    def _taunt(self, channel=None, prefix=None, taunt_table=None):
        if channel is None:
            channel = "#qai_channel"
        if taunt_table is None:
            taunt_table = ALL_TAUNTS
        if prefix is None:
            prefix = ''
        else:
            prefix = '%s: ' % prefix
        self.bot.privmsg(channel, "%s%s" % (prefix, random.choice(taunt_table)))

    def _try_to_remind(self, receiver, reminder):
        with REMINDER_DB_ACTION_LOCK:
            global REMINDER_RECEIVERS, OFFLINE_MESSAGE_RECEIVERS
            if REMINDER_RECEIVERS.get(receiver, False):
                message = self.__db_get(['reminders', receiver, reminder])
                is_online, _ = self.__is_in_bot_channel(receiver)
                if is_online:
                    if self.__is_nick_serv_identified(receiver):
                        self.bot.privmsg(receiver, '"{message}" - by {sender}, {time}'.format(**{
                            'message': message.get('message', "<message>"),
                            'sender': message.get('sender', "<sender>"),
                            'time': message.get('time', "<time>")}),
                            nowait=True)
                        self.__db_del(['reminders', receiver], reminder)
                else:
                    self.__db_add(['offlinemessages', receiver], message.get('sender', "<sender>"),
                                  {'message': message.get('message', "<message>"),
                                  'sender': message.get('sender', "<sender>"),
                                  'time': message.get('time', "<time>")},
                                  overwrite_if_exists=False, try_saving_with_new_key=True)
                    OFFLINE_MESSAGE_RECEIVERS[receiver] = True
                    self.__db_del(['reminders', receiver], reminder)

                reminders_left_for_this_receiver = list(self.__db_get(['reminders', receiver]).keys())
                if not reminders_left_for_this_receiver:
                    self.__db_del(['reminders'], receiver)
                    del REMINDER_RECEIVERS[receiver]

    def _try_deliver_offline_messages(self, receiver):
        if OFFLINE_MESSAGE_RECEIVERS.get(receiver, False):
            is_online, _ = self.__is_in_bot_channel(receiver)
            if is_online:
                if self.__is_nick_serv_identified(receiver):
                    messages = self.__db_get(['offlinemessages', receiver]).values()
                    for m in messages:
                        self.bot.privmsg(receiver, '"{message}" - Sent by {sender}, {time}'.format(**{
                            'message': m.get('message', "<message>"),
                            'sender': m.get('sender', "<sender>"),
                            'time': m.get('time', "<time>"),
                        }))
                    del OFFLINE_MESSAGE_RECEIVERS[receiver]
                    self.__db_del(['offlinemessages'], receiver)

    async def hitbox_streams(self):
        async with aiohttp.request('GET', HIT_BOX_STREAMS) as req:
            data = await req.read()
        try:
            data = json.loads(data.decode())
            hitbox_streams = data.get('livestreams', None)
            if not hitbox_streams:
                hitbox_streams = data['livestream']
            live_streams = []
            for stream in hitbox_streams:
                live_streams.append({
                    'channel': stream["media_display_name"],
                    'text': "%s - %s - %s Since %s (%s viewers) "
                            % (stream["media_display_name"],
                               stream["media_status"],
                               stream["channel"]["channel_link"],
                               stream["media_live_since"],
                               stream["media_views"])
                })
            return live_streams
        except (KeyError, ValueError):
            return []

    async def twitch_streams(self):
        async with aiohttp.request('GET', TWITCH_STREAMS,
                                   headers={'Client-ID': self.bot.config['twitch_client_id']}) as req:
            data = await req.read()
        try:
            livestreams = []
            for stream in json.loads(data.decode())['streams']:
                t = stream["channel"].get("updated_at", "T0")
                date = t.split("T")
                hour = date[1].replace("Z", "")
                livestreams.append({
                    'channel': stream["channel"]["display_name"],
                    'text': "%s - %s - %s since %s (%i viewers) "
                            % (stream["channel"]["display_name"],
                               stream["channel"]["status"],
                               stream["channel"]["url"],
                               hour,
                               stream["viewers"])
                })
            return livestreams
        except (KeyError, ValueError):
            return []

    async def youtube_streams(self):
        async with aiohttp.request('GET', YOUTUBE_STREAMS.format(self.bot.config['youtube_key'])) as req:
            data = await req.read()
        try:
            live_streams = []
            for stream in json.loads(data.decode())['items']:
                t = stream["snippet"].get("publishedAt", "T0")
                date = t.split("T")
                hour = date[1].replace("Z", "")
                hour = (hour.split("."))[0]
                live_streams.append({
                    'channel': stream["snippet"]["channelTitle"],
                    'text': "%s - %s - %s since %s "
                            % (stream["snippet"]["channelTitle"],
                               stream["snippet"]["title"],
                               "https://gaming.youtube.com/watch?v=" + stream["id"]["videoId"],
                               hour)
                })
            return live_streams
        except (KeyError, ValueError):
            return []

    @command
    async def casts(self, mask, target, args):
        """List recent casts

            %%casts
        """
        if self.spam_protect('casts', mask, target, args):
            return
        async with aiohttp.request('GET', YOUTUBE_SEARCH.format(self.bot.config['youtube_key'])) as req:
            data = json.loads((await req.read()).decode())
        casts = []
        try:
            for item in itertools.takewhile(lambda _: len(casts) < 5, data['items']):
                channel_title = item['snippet']['channelTitle']
                if channel_title not in self.__db_get(['blacklist', 'users']) and channel_title != '':
                    casts.append(item)
                    try:
                        self.pm_fix(mask, target,
                                        "{channel}: {title} - {date}: {link}".format(
                                            **{
                                                "id": item['id']['videoId'],
                                                "title": item['snippet']['title'],
                                                "channel": channel_title,
                                                "description": item['snippet']['description'],
                                                "date": time.strftime("%x",
                                                                      time.strptime(item['snippet']['publishedAt'],
                                                                                    self.bot.config[
                                                                                        'youtube_time_fmt'])),
                                                "link": "http://youtu.be/{}".format(item['id']['videoId'])
                                            }),
                                    action=True)
                    except (KeyError, ValueError) as ex:
                        pass
        except KeyError:
            pass
        self.pm_fix(mask, target, "Find more here: {}".format(YOUTUBE_NON_API_SEARCH_LINK), action=True)

    def pm_fix(self, mask, target, message, action=False, nowait=False):
        """Fixes bot PMing itself instead of the user if privmsg is called by user in PM instead of a channel."""
        if target == self.bot.config['username']:
            target = mask.nick
        if action is False:
            return self.bot.privmsg(target, message, nowait=nowait)
        else:
            return self.bot.action(target, message)

    #TODO move to decorators?
    def spam_protect(self, cmd, mask, target, args, no_penalty=False):
        # TODO 'not cmd in' vs 'cmd not in' what was intention?
        if cmd not in self.timers:
            self.timers[cmd] = {}
        if target not in self.timers[cmd]:
            self.timers[cmd][target] = 0
        if time.time() - self.timers[cmd][target] <= self.bot.config['spam_protect_time']:
            if no_penalty:
                return True
            try:
                self._rage[mask.nick] += 1
            except Exception as ex:
                self._rage[mask.nick] = 1

            if self._rage[mask.nick] >= self.bot.config['rage_to_kick']:
                self._taunt(channel=target, prefix=mask.nick, taunt_table=KICK_TAUNTS)
                self.bot.privmsg(target, "!kick {}".format(mask.nick))
                self._rage[mask.nick] = 1
            else:
                self._taunt(channel=target, prefix=mask.nick, taunt_table=SPAM_PROTECT_TAUNTS)
            return True
        self._rage = {}
        self.timers[cmd][target] = time.time()

    @staticmethod
    def __handle_nick_serv_message(message):
        if message.startswith('STATUS'):
            words = message.split(" ")
            global NICK_SERV_IDENTIFIED_RESPONSES, NICK_SERV_IDENTIFIED_RESPONSES_LOCK
            NICK_SERV_IDENTIFIED_RESPONSES_LOCK.acquire()
            NICK_SERV_IDENTIFIED_RESPONSES[words[1]] = words[2]
            NICK_SERV_IDENTIFIED_RESPONSES_LOCK.release()

    async def __is_nick_serv_identified(self, nick):
        self.bot.privmsg('nickserv', "status {}".format(nick))
        remaining_tries = 20
        while remaining_tries > 0:
            if NICK_SERV_IDENTIFIED_RESPONSES.get(nick):
                value = NICK_SERV_IDENTIFIED_RESPONSES[nick]
                NICK_SERV_IDENTIFIED_RESPONSES_LOCK.acquire()
                del NICK_SERV_IDENTIFIED_RESPONSES[nick]
                NICK_SERV_IDENTIFIED_RESPONSES_LOCK.release()
                if int(value) == 3:
                    return True
                return False
            remaining_tries -= 1
            await asyncio.sleep(0.1)
        return False

    def __is_in_bot_channel(self, player):
        for channel in self.bot.channels:
            if self.__is_in_channel(player, self.bot.channels[channel]):
                return True, channel
        return False, ""

    @staticmethod
    def __is_in_channel(player, channel):
        if player in channel:
            return True
        return False

    @staticmethod
    def _is_a_channel(channel):
        return IrcString(channel).is_channel

    def __filter_for_players_in_channel(self, player_list, channel_name):
        players = {}
        if channel_name not in self.bot.channels:
            return players
        channel = self.bot.channels[channel_name]
        for p in player_list.keys():
            if self.__is_in_channel(p, channel):
                players[p] = True
        return players

    @command
    async def streams(self, mask, target, args):
        """List current live streams

            %%streams
        """
        if self.spam_protect('streams', mask, target, args):
            return
        streams = await self.hitbox_streams()
        streams.extend((await self.twitch_streams()))
        streams.extend((await self.youtube_streams()))
        blacklist = self.__db_get(['blacklist', 'users'])
        for stream in streams:
            if stream["channel"] in blacklist:
                streams.remove(stream)

        if len(streams) > 0:
            self.pm_fix(mask, target, "%i streams online:" % len(streams))
            for stream in streams:
                self.pm_fix(mask, target, stream['text'], action=True)
        else:
            self.pm_fix(mask, target, "Nobody is streaming :'(")

    @command
    @channel_only
    @nickserv_identified
    async def groupping(self, mask, target, args):
        """Pings people in this group

            %%groupping <groupname>
        """
        group_name = args.get('<groupname>')
        player_groups = self.__db_get(['groups', 'playergroups'])
        if not player_groups.get(group_name):
            return
        players, text = player_groups[group_name].get('players', {}), player_groups[group_name].get('text', "")
        player_list = self.__filter_for_players_in_channel(players, target)
        if not players.get(mask.nick):
            self._taunt(channel=target, prefix=mask.nick, taunt_table=TAUNTS)
            return
        if self.spam_protect('grouping_' + group_name, mask, target, args):
            return
        self.bot.privmsg(target, text + " " + mask.nick + " requests your presence!")
        self.bot.privmsg(target, ", ".join(player_list))

    @command(public=False)
    @nickserv_identified
    def group(self, mask, target, args):
        """Allows joining and leaving ping groups

            %%group get
            %%group join <groupname>
            %%group leave <groupname>
        """
        get, join, leave, group_name = args.get('get'), args.get('join'), args.get('leave'), args.get('<groupname>')
        player_groups = self.__db_get(['groups', 'playergroups'])
        if get:
            self.bot.privmsg(mask.nick, str(len(player_groups)) + " groups: ")
            for g in player_groups.keys():
                players = player_groups[g].get('players', {})
                is_member = ""
                if players.get(mask.nick):
                    is_member = " You are member of this group."
                self.bot.privmsg(mask.nick, 'Group {name} with {num} users.{ismember}'.format(**{
                    "name": g,
                    "num": len(players),
                    "ismember": is_member,
                }))
            return
        if not player_groups.get(group_name):
            return "Group does not exist."
        players = player_groups[group_name].get('players', {})
        if join:
            self.__db_add(['groups', 'playergroups', group_name, 'players'], mask.nick, True)
        elif leave:
            if not players.get(mask.nick):
                return "You are not in this group."
            self.__db_del(['groups', 'playergroups', group_name, 'players'], mask.nick)
        return "Done."

    @command(permission='admin', public=False, show_in_help_list=False)
    @nickserv_identified
    def group_manage(self, mask, target, args):
        """Allows admins to manage groups

            %%groupmanage get
            %%groupmanage add <groupname> TEXT ...
            %%groupmanage del <groupname>
            %%groupmanage join <groupname> <playername>
            %%groupmanage leave <groupname> <playername>
        """
        get, add, delete, join, leave, group_name, player_name, text = args.get('get'), args.get('add'), args.get(
            'del'), args.get('join'), args.get('leave'), args.get('<groupname>'), args.get('<playername>'), " ".join(
            args.get('TEXT'))
        player_groups = self.__db_get(['groups', 'playergroups'])
        if get:
            self.bot.privmsg(mask.nick, str(len(player_groups)) + " groups: ")
            for g in player_groups.keys():
                players = player_groups[g].get('players', {})
                self.bot.privmsg(mask.nick, 'Group {name} with {num} users: {players}'.format(**{
                    "name": g,
                    "num": len(players),
                    "players": ", ".join(players),
                }))
            return

        if add:
            if group_name in player_groups.keys():
                self.__db_add(['groups', 'playergroups', group_name], 'text', text, overwrite_if_exists=True)
                return "Group with that name already exists. The old message was replaced, player list stays."
            self.__db_add(['groups', 'playergroups'], group_name, {'text': text, 'players': {}})
            return "Done."

        if not player_groups.get(group_name):
            return "Group does not exist."
        players = player_groups[group_name].get('players', {})
        if delete:
            self.__db_del(['groups', 'playergroups'], group_name)
        elif join:
            self.__db_add(['groups', 'playergroups', group_name, 'players'], player_name, True)
        elif leave:
            if not players.get(player_name):
                return "The player is not in this group."
            self.__db_del(['groups', 'playergroups', group_name, 'players'], player_name)
        return "Done."

    @command(permission='admin', public=False, show_in_help_list=False)
    @nickserv_identified
    def blacklist(self, mask, target, args):
        """Blacklist given channel/user from !casts, !streams

            %%blacklist get
            %%blacklist add USER ...
            %%blacklist del USER ...
        """
        add, delete, get, user = args.get('add'), args.get('del'), args.get('get'), " ".join(args.get('USER'))
        if get:
            for user in self.__db_get(['blacklist', 'users']).keys():
                self.bot.privmsg(mask.nick, '- ' + user)
            return
        if user is not None:
            users = self.__db_get(['blacklist', 'users'])
            if add:
                self.__db_add(['blacklist', 'users'], user, True)
                return "Added {} to blacklist".format(user)
            if delete:
                if users.get(user):
                    self.__db_del(['blacklist', 'users'], user)
                    return "Removed {} from the blacklist".format(user)
                return "{} is not on the blacklist.".format(user)
        return "Something went wrong."

    @command(permission='admin', public=False, show_in_help_list=False)
    @nickserv_identified
    def bad_words(self, mask, target, args):
        """Adds/removes a given keyword from the checklist

            %%badwords get
            %%badwords add <word> <gravity>
            %%badwords del <word>
        """
        global BAD_WORDS
        add, delete, get, word, gravity = args.get('add'), args.get('del'), args.get('get'), args.get(
            '<word>'), args.get('<gravity>')
        if add:
            try:
                word = word.lower()
                BAD_WORDS, _, _ = self.__db_add(['badwords', 'words'], word, int(gravity), True)
                return 'Added "{word}" to watched badwords with gravity {gravity}'.format(**{
                    "word": word,
                    "gravity": gravity,
                })
            except Exception as ex:
                return "Failed adding the word. Did you not use a number for the gravity?"
        elif delete:
            if BAD_WORDS.get(word):
                BAD_WORDS = self.__db_del(['badwords', 'words'], word)
                return 'Removed "{word}" from watched badwords'.format(**{
                    "word": word,
                })
            else:
                return 'Word not found in the list.'
        elif get:
            words = BAD_WORDS
            self.bot.privmsg(mask.nick, str(len(words)) + " checked badwords:")
            for word in words.keys():
                self.bot.privmsg(mask.nick, '- word: "%s", gravity: %s' % (word, words[word]))

    @command
    def rwords(self, mask, target, args):
        """Prints the list of checked reactionwords

            %%rwords
        """
        if self.spam_protect('rwords', mask, target, args):
            return
        self.pm_fix(mask, target, "Checked reaction words: " + ", ".join(REACTION_WORDS.keys()))

    @command(permission='admin', public=False, show_in_help_list=False)
    @nickserv_identified
    def reaction_words(self, mask, target, args):
        """Adds/removes a given keyword from the checklist.
        "{sender}" in the reply text will be replaced by the name of the person who triggered the response.

            %%reactionwords get
            %%reactionwords add <word> REPLY ...
            %%reactionwords del <word>
        """
        global REACTION_WORDS
        add, delete, get, word, reply = args.get('add'), args.get('del'), args.get('get'), args.get('<word>'), " ".join(
            args.get('REPLY'))
        if add:
            try:
                REACTION_WORDS, _, _ = self.__db_add(['reactionwords', 'words'], word.lower(), reply)
                return 'Added "{word}" to watched reactionwords with reply: "{reply}"'.format(**{
                    "word": word,
                    "reply": reply,
                })
            except Exception as ex:
                return "Failed adding the word."
        elif delete:
            words = self.__db_get(['reactionwords', 'words'])
            if words.get(word):
                REACTION_WORDS = self.__db_del(['reactionwords', 'words'], word)
                return 'Removed "{word}" from watched reactionwords'.format(**{
                    "word": word,
                })
            else:
                return 'Word not found in the list.'
        elif get:
            words = self.__db_get(['reactionwords', 'words'])
            self.bot.privmsg(mask.nick, str(len(words)) + " checked reactionwords:")
            for word in words.keys():
                self.bot.privmsg(mask.nick, '- word: "%s", reply: %s' % (word, words[word]))

    @command(permission='admin', public=False, show_in_help_list=False)
    @nickserv_identified
    def repeat(self, mask, target, args):
        """Makes QAI repeat WORDS in <channel> each <seconds>. Use <ID> to remove them again.

            %%repeat get
            %%repeat add <ID> <seconds> <channel> WORDS ...
            %%repeat del <ID>
        """
        global REPETITIONS
        # TODO Check if id_player could be named better and if words works in lowercase.
        add, delete, get, id_player, seconds, channel, words = args.get('add'), args.get('del'), args.get(
            'get'), args.get(
            '<ID>'), args.get('<seconds>'), args.get('<channel>'), " ".join(args.get('WORDS'))
        text = self.__db_get(['repetitions', 'text'])
        if get:
            self.bot.privmsg(mask.nick, str(len(text)) + " texts repeating:")
            for t in text.keys():
                self.bot.privmsg(mask.nick, '  ID: "%s", each %i seconds, channel: %s, text: %s' % (
                    t, text[t].get('seconds'), text[t].get('channel'), text[t].get('text')))
        elif add:
            try:
                if text.get(id_player):
                    return "ID already exists. Pick another."
                self.__db_add(['repetitions', 'text'], id_player, {
                    "seconds": int(seconds),
                    "text": words,
                    "channel": channel,
                })
                REPETITIONS[id_player] = repetition.RepetitionThread(self.bot, channel, words, int(seconds))
                REPETITIONS[id_player].daemon = True
                REPETITIONS[id_player].start()
                return 'Done.'
            except Exception as ex:
                return "Failed adding the text."
        elif delete:
            try:
                if text.get(id_player):
                    self.__db_del(['repetitions', 'text'], id_player)
                    REPETITIONS[id_player].stop()
                    del REPETITIONS[id_player]
                    return 'Done.'
                else:
                    return "Not repeating something with ID <" + id_player + ">"
            except Exception as ex:
                return "Failed deleting."

    @command(permission='chatlist', show_in_help_list=False)
    @nickserv_identified
    def move(self, mask, target, args):
        """Move nick into channel

            %%move <nick> <channel>
        """
        channel, nick = args.get('<channel>'), args.get('<nick>')
        self.move_user(channel, nick)
        self.bot.privmsg(mask.nick, "OK moved %s to %s" % (nick, channel))

    @command(permission='chatlist', show_in_help_list=False)
    @nickserv_identified
    def chat_list(self, mask, target, args):
        """Chat lists

            %%chatlist
            %%chatlist <channel>
            %%chatlist add <channel> <user>
            %%chatlist del <channel> <user>
        """
        channel, user, add, remove = args.get('<channel>'), args.get('<user>'), args.get('add'), args.get('del')
        if not add and not remove:
            if not channel:
                self.bot.privmsg(mask.nick, ", ".join(self.__db_get(['chatlists'])))
            else:
                self.bot.privmsg(mask.nick, ", ".join(self.__db_get(['chatlists', channel]).keys()))
        elif add:
            self.__db_add(['chatlists', channel], user, True)
            self.move_user(channel, user)
            self.bot.privmsg(mask.nick, "OK added and moved %s to %s" % (user, channel))
        elif remove:
            remaining = self.__db_del(['chatlists', channel], user)
            if len(remaining) == 0:
                self.__db_del(['chatlists'], channel)
            self.bot.privmsg(mask.nick, "OK removed %s from %s" % (user, channel))

    @command
    def google(self, mask, target, args):
        """google

            %%google WORDS ...
        """
        link = LET_ME_GOOGLE_IT_FOR_YOU + "+".join(args.get('WORDS'))
        self.pm_fix(mask, target, link)

    @command
    def name(self, mask, target, args):
        """name

            %%name
            %%name <username>
            %%name <username> WORDS ...
        """
        name = args.get('<username>')
        if name is None:
            self.pm_fix(mask, target, LINKS["namechange"])
            return
        link = OTHER_LINKS["oldnames"] + name
        self.pm_fix(mask, target, link)

    @command
    async def tournaments(self, mask, target, args):
        """Check tourneys

            %%tournaments
        """
        await self.tourneys(mask, target, args)

    @command(show_in_help_list=False)
    async def tourneys(self, mask, target, args):
        """Check tourneys

            %%tourneys
        """
        if self.spam_protect('tourneys', mask, target, args):
            return

        # TODO Why is got None a problem here?
        tourneys = await challonge.printable_tourney_list()
        if len(tourneys) < 1:
            self.pm_fix(mask, target, "No tourneys found!")

        self.bot.privmsg(target, str(len(tourneys)) + " tourneys:")
        for tourney in tourneys:
            self.bot.action(target, tourney)

    def report(self, name, word, channel, text, gravity):
        report_msg = 'User "{name}" used bad word "{word}" in irc channel "{channel}".' \
                     ' Full text: "{text}". (Gravity {gravity})'.format(
                        **{
                            'name': name,
                            'word': word,
                            'channel': channel,
                            'text': text,
                            'gravity': gravity,
                        })
        if gravity >= self.bot.config['report_to_irc_threshold']:
            self.bot.privmsg('#' + self.bot.config['report_to_irc_channel'], report_msg)
        if gravity >= self.bot.config['report_to_slack_threshold']:
            self.slackThread.send_message_to_channel(self.bot.config['report_to_slack_channel'], report_msg)
        if gravity >= self.bot.config['report_instant_kick_threshold']:
            self._taunt(channel=channel, prefix=name, taunt_table=KICK_TAUNTS)
            self.bot.privmsg(channel, "!kick {}".format(name))

    def __db_add(self, path, key, value, overwrite_if_exists=True, try_saving_with_new_key=False):
        cur = self.bot.db
        for p in path:
            if p not in cur:
                cur[p] = {}
            cur = cur[p]
        exists, added_with_new_key = cur.get(key), False
        if overwrite_if_exists:
            cur[key] = value
        elif not exists:
            cur[key] = value
        elif exists and try_saving_with_new_key:
            for i in range(0, 1000):
                if not cur.get(key + str(i)):
                    cur[key + str(i)] = value
                    added_with_new_key = True
                    break
        self.__db_save()
        return cur, exists, added_with_new_key

    def __db_del(self, path, key):
        cur = self.bot.db
        for p in path:
            cur = cur.get(p, {})
        if not cur.get(key) is None:
            del cur[key]
            self.__db_save()
        return cur

    def __db_get(self, path):
        reply = self.bot.db
        for p in path:
            reply = reply.get(p, {})
        return reply

    def __db_save(self):
        self.bot.db.set('misc', lastSaved=time.time())
