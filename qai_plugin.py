# vim: ts=4 et sw=4 sts=4
# -*- coding: utf-8 -*-
import json
import random
import asyncio
import re
import aiohttp
import aiomysql
import itertools
import irc3
from irc3.plugins.command import command
import time
from urllib.parse import urlparse, parse_qs
import threading

import slack
import challonge
import repetition
from taunts import TAUNTS, SPAM_PROTECT_TAUNTS, KICK_TAUNTS
from links import LINKS, LINKS_SYNONYMES, WIKI_LINKS, WIKI_LINKS_SYNONYMES, OTHER_LINKS

ALL_TAUNTS = [] # extended in init
BADWORDS = {}
REPETITIONS = {}
NICKSERVIDENTIFIEDRESPONSES = {}
NICKSERVIDENTIFIEDRESPONSESLOCK = None
TWITCH_STREAMS = "https://api.twitch.tv/kraken/streams/?game=Supreme+Commander:+Forged+Alliance" #add the game name at the end of the link (space = "+", eg: Game+Name)
HITBOX_STREAMS = "https://api.hitbox.tv/media/live/list?filter=popular&game=811&hiddenOnly=false&limit=30&liveonly=true&media=true"
YOUTUBE_NON_API_SEARCH_LINK = "https://www.youtube.com/results?search_query=supreme+commander+%7C+forged+alliance&search_sort=video_date_uploaded&filters=video"
YOUTUBE_SEARCH = "https://www.googleapis.com/youtube/v3/search?order=date&type=video&part=snippet&q=Forged%2BAlliance|Supreme%2BCommander&relevanceLanguage=en&maxResults=15&key={}"
YOUTUBE_DETAIL = "https://www.googleapis.com/youtube/v3/videos?part=snippet,statistics&id={}&key={}"
LETMEGOOGLE = "http://lmgtfy.com/?q="
URL_MATCH = ".*(https?:\/\/[^ ]+\.[^ ]*).*"
REPLAY_MATCH = ".*(#[0-9]+).*"


@irc3.extend
def action(bot, *args):
    bot.privmsg(args[0], '\x01ACTION ' + args[1] + '\x01')

@irc3.plugin
class Plugin(object):

    def __init__(self, bot):
        self.bot = bot
        self.timers = {}
        self._rage = {}
        global ALL_TAUNTS, NICKSERVIDENTIFIEDRESPONSESLOCK
        ALL_TAUNTS.extend(TAUNTS)
        ALL_TAUNTS.extend(SPAM_PROTECT_TAUNTS)
        challonge.setChallongeData(self.bot.config['challonge_username'], self.bot.config['challonge_api_key'])
        NICKSERVIDENTIFIEDRESPONSESLOCK = threading.Lock()

        self.slackThread = slack.slackThread(self.bot.config['slack_api_key'])
        self.slackThread.daemon = True
        self.slackThread.start()

    @classmethod
    def reload(cls, old):
        return cls(old.bot)

    def after_reload(self):
        self._taunt('#qai_channel')

    @irc3.event(irc3.rfc.CONNECTED)
    def nickserv_auth(self, *args, **kwargs):
        self.bot.privmsg('nickserv', 'identify %s' % self.bot.config['nickserv_password'])
        if 'badwords' in self.bot.db:
            if 'words' in self.bot.db['badwords']:
                global BADWORDS
                BADWORDS = self.bot.db['badwords'].get('words', {}) #doing this here to init BADWORDS after the bot got its db
        if 'repetitions' in self.bot.db:
            if 'text' in self.bot.db['repetitions']:
                text = self.bot.db['repetitions'].get('text', {})
                global REPETITIONS
                for t in text.keys():
                    REPETITIONS[t] = repetition.repetitionThread(self.bot, text[t].get('channel'), text[t].get('text'), int(text[t].get('seconds')))
                    REPETITIONS[t].start()

    @irc3.event(irc3.rfc.JOIN)
    def on_join(self, channel, mask):
        if channel == '#aeolus':
            for channel in self.bot.db['chatlists']:
                if mask.nick in self.bot.db['chatlists'].get(channel, {}).keys():
                    self.move_user(channel, mask.nick)

    def move_user(self, channel, nick):
        self.bot.privmsg('OperServ', 'svsjoin %s %s' % (nick, channel))

    @irc3.event(irc3.rfc.PRIVMSG)
    @asyncio.coroutine
    def on_privmsg(self, *args, **kwargs):
        msg, channel, sender = kwargs['data'], kwargs['target'], kwargs['mask']
        if self.bot.config['nick'] in sender.nick:
            return
        try:
            link_url = re.match(URL_MATCH, msg).groups()[0]
            uri = urlparse(link_url)
            ytid = parse_qs(uri.query).get('v', '')[0]
            if len(ytid) > 0:
                req = yield from aiohttp.request('GET', YOUTUBE_DETAIL.format(ytid, self.bot.config['youtube_key']))
                data = json.loads((yield from req.read()).decode())['items'][0]

                self.bot.privmsg(channel, "{title} - {views} views - {likes} likes (Linked above by {sender})".format(title=data['snippet']['title'],
                                                            views=data['statistics']['viewCount'],
                                                            likes=data['statistics']['likeCount'],
                                                            sender=sender.nick))
        except (KeyError, ValueError, AttributeError, IndexError):
            pass

        try:
            replayId = re.match(REPLAY_MATCH, msg).groups()[0]
            replayId = replayId.replace('#', '')
            if int(replayId) >= 1000000:
                url = LINKS["replay"].replace("ID", replayId)
                self.bot.privmsg(channel, url)
        except:
            pass

        if channel.startswith("#"):
            lowercaseMsg = msg.lower()
            for badword in BADWORDS:
                if badword in lowercaseMsg:
                    self.report(sender.nick, badword, channel, msg, BADWORDS[badword])

        if sender.startswith("NickServ!"):
            self.__handleNickservMessage(msg)

    @command(permission='admin')
    @asyncio.coroutine
    def taunt(self, mask, target, args):
        """Send a taunt

            %%taunt
            %%taunt <person>
        """
        if not (yield from self.__isNickservIdentified(mask.nick)):
            return
        p = args.get('<person>')
        if p == self.bot.config['nick']:
            p = mask.nick
        self._taunt(channel=target, prefix=p, tauntTable=TAUNTS)

    @command(permission='admin')
    @asyncio.coroutine
    def explode(self, mask, target, args):
        """Explode

            %%explode
        """
        if not (yield from self.__isNickservIdentified(mask.nick)):
            return
        self.bot.action(target, "explodes")

    @command(permission='admin')
    @asyncio.coroutine
    def hug(self, mask, target, args):
        """Hug someone

            %%hug
            %%hug <someone>
        """
        if not (yield from self.__isNickservIdentified(mask.nick)):
            return
        someone = args['<someone>']
        if someone == None:
            someone = mask.nick
        elif someone == self.bot.config['nick']:
            self._taunt(channel=target, prefix=mask.nick)
            return
        self.bot.action(target, "hugs " + someone)

    @command(permission='admin')
    @asyncio.coroutine
    def flip(self, mask, target, args):
        """Flip table

            %%flip
        """
        if not (yield from self.__isNickservIdentified(mask.nick)):
            return
        self.bot.privmsg(target, "(╯°□°）╯︵ ┻━┻")

    @command(permission='admin')
    @asyncio.coroutine
    def join(self, mask, target, args):
        """Overtake the given channel

            %%join <channel>
        """
        if not (yield from self.__isNickservIdentified(mask.nick)):
            return
        self.bot.join(args['<channel>'])

    @command(permission='admin')
    @asyncio.coroutine
    def leave(self, mask, target, args):
        """Leave the given channel

            %%leave
            %%leave <channel>
        """
        if not (yield from self.__isNickservIdentified(mask.nick)):
            return
        channel = args['<channel>']
        if channel is None:
            channel = target
        self.bot.part(channel)

    @command
    def gullible(self, mask, target, args):
        """Display additional commands

            %%gullible
        """
        self._taunt(channel=target, prefix=mask.nick, tauntTable=SPAM_PROTECT_TAUNTS)

    @command
    def link(self, mask, target, args):
        """Link to a website

            %%link
            %%link <argument>
            %%link <argument> WORDS...
        """
        try:
            self.bot.privmsg(target, LINKS_SYNONYMES[args['<argument>']])
            return
        except:
            pass

        try:
            self.bot.privmsg(target, LINKS[args['<argument>']])
        except:
            if self.spam_protect('links', mask, target, args):
                return

            msg = ""
            if not args['<argument>'] is None:
                msg = "Unknown link: \"" + args['<argument>'] + "\". "
            msg += "Do you mean one of these: " + " / ".join(LINKS.keys()) + " ?"
            self.bot.privmsg(target, msg)

    @command
    def wiki(self, mask, target, args):
        """Link to a wiki page

            %%wiki
            %%wiki <argument>
            %%wiki <argument> WORDS...
        """
        try:
            self.bot.privmsg(target, WIKI_LINKS_SYNONYMES[args['<argument>']])
            return
        except:
            pass

        try:
            self.bot.privmsg(target, WIKI_LINKS[args['<argument>']])
        except:
            if self.spam_protect('wiki', mask, target, args):
                return

            msg = ""
            if not args['<argument>'] is None:
                msg = "Unknown wiki link: \"" + args['<argument>'] + "\". Do you mean one of these: "
            else:
                msg = LINKS["wiki"] + " For better matches try !wiki " 
            msg += " / ".join(WIKI_LINKS.keys())
            if not args['<argument>'] is None:
                msg += " ?"
            self.bot.privmsg(target, msg)

    @command(permission='admin', public=False)
    @asyncio.coroutine
    def puppet(self, mask, target, args):
        """Puppet

            %%puppet <target> WORDS ...
        """
        if not (yield from self.__isNickservIdentified(mask.nick)):
            return
        t = args.get('<target>')
        m = " ".join(args.get('WORDS'))
        self.bot.privmsg(t, m)

    @command(permission='admin', public=False)
    @asyncio.coroutine
    def reload(self, mask, target, args):
        """Reboot the mainframe

            %%reload
        """
        if not (yield from self.__isNickservIdentified(mask.nick)):
            return
        self.bot.reload(self.bot.config['nick'])

    @command(permission='admin')
    @asyncio.coroutine
    def slap(self, mask, target, args):
        """Slap this guy

            %%slap <guy>
        """
        if not (yield from self.__isNickservIdentified(mask.nick)):
            return
        self.bot.action(target, "slaps %s " % args['<guy>'])

    def _taunt(self, channel=None, prefix=None, tauntTable=None):
        if channel is None:
            channel = "#qai_channel"
        if tauntTable is None:
            tauntTable = ALL_TAUNTS
        if prefix is None:
            prefix = ''
        else:
            prefix = '%s: ' % prefix
        self.bot.privmsg(channel, "%s%s" % (prefix, random.choice(tauntTable)))

    @asyncio.coroutine
    def hitbox_streams(self):
        req = yield from aiohttp.request('GET', HITBOX_STREAMS)
        data = yield from req.read()
        try:
            data = json.loads(data.decode())
            livestreams = data.get('livestreams', None)
            if not livestreams:
                livestreams = data['livestream']
            return livestreams
        except (KeyError, ValueError):
            return []

    @asyncio.coroutine
    def twitch_streams(self):
        req = yield from aiohttp.request('GET', TWITCH_STREAMS)
        data = yield from req.read()
        try:
            return json.loads(data.decode())['streams']
        except (KeyError, ValueError):
            return []

    @command
    @asyncio.coroutine
    def casts(self, mask, target, args):
        """List recent casts

            %%casts
        """
        if self.spam_protect('casts', mask, target, args):
            return
        req = yield from aiohttp.request('GET', YOUTUBE_SEARCH.format(self.bot.config['youtube_key']))
        data = json.loads((yield from req.read()).decode())
        casts = []
        try:
            for item in itertools.takewhile(lambda _: len(casts) < 5, data['items']):
                channel_title = item['snippet']['channelTitle']
                if channel_title not in self.bot.db['blacklist'].get('users', {}) and channel_title != '':
                    casts.append(item)
                    try:
                        self.bot.action(target,
                            "{channel}: {title} - {date}: {link}".format(
                            **{
                                "id": item['id']['videoId'],
                                "title": item['snippet']['title'],
                                "channel": channel_title,
                                "description": item['snippet']['description'],
                                "date": time.strftime("%x",
                                                      time.strptime(item['snippet']['publishedAt'],
                                                                    self.bot.config['youtube_time_fmt'])),
                                "link": "http://youtu.be/{}".format(item['id']['videoId'])
                            }))
                    except (KeyError, ValueError):
                        pass
        except (KeyError):
            pass
        self.bot.action(target, "Find more here: {}".format(YOUTUBE_NON_API_SEARCH_LINK))

    def spam_protect(self, cmd, mask, target, args):
        if not cmd in self.timers:
            self.timers[cmd] = {}
        if not target in self.timers[cmd]:
            self.timers[cmd][target] = 0
        if time.time() - self.timers[cmd][target] <= self.bot.config['spam_protect_time']:
            try: 
                self._rage[mask.nick] += 1
            except:
                self._rage[mask.nick] = 1

            if self._rage[mask.nick] >= self.bot.config['rage_to_kick']:
                self._taunt(channel=target, prefix=mask.nick, tauntTable=KICK_TAUNTS)
                self.bot.privmsg(target, "!kick {}".format(mask.nick))
                self._rage[mask.nick] = 1
            else:  
                self._taunt(channel=target, prefix=mask.nick, tauntTable=SPAM_PROTECT_TAUNTS)
            return True
        self._rage = {}
        self.timers[cmd][target] = time.time()

    def __handleNickservMessage(self, message):
        if message.startswith('STATUS'):
            words = message.split(" ")
            global NICKSERVIDENTIFIEDRESPONSES, NICKSERVIDENTIFIEDRESPONSESLOCK
            NICKSERVIDENTIFIEDRESPONSESLOCK.acquire()
            NICKSERVIDENTIFIEDRESPONSES[words[1]] = words[2]
            NICKSERVIDENTIFIEDRESPONSESLOCK.release()

    @asyncio.coroutine
    def __isNickservIdentified(self, nick):
        self.bot.privmsg('nickserv', "status {}".format(nick))
        remainingTries = 20
        while remainingTries > 0:
            if NICKSERVIDENTIFIEDRESPONSES.get(nick):
                value = NICKSERVIDENTIFIEDRESPONSES[nick]
                NICKSERVIDENTIFIEDRESPONSESLOCK.acquire()
                del NICKSERVIDENTIFIEDRESPONSES[nick]
                NICKSERVIDENTIFIEDRESPONSESLOCK.release()
                if int(value) == 3:
                    return True
                return False
            remainingTries -= 1
            yield from asyncio.sleep(0.1)
        return False

    @command
    @asyncio.coroutine
    def streams(self, mask, target, args):
        """List current live streams

            %%streams
        """
        if self.spam_protect('streams', mask, target, args):
            return
        streams = yield from self.hitbox_streams()
        streams.extend((yield from self.twitch_streams()))
        blacklist = self.bot.db['blacklist'].get('users', {})
        for stream in streams:
            try:
                if stream["media_display_name"] in blacklist:
                    streams.remove(stream)
            except:
                if stream["channel"]["display_name"] in blacklist:
                    streams.remove(stream)

        if len(streams) > 0:
            self.bot.privmsg(target, "%i streams online:" % len(streams))
            for stream in streams:
                t = stream["channel"].get("updated_at", "T0")
                date = t.split("T")
                hour = date[1].replace("Z", "")

                try: 
                    self.bot.action(target,
                                     "%s - %s - %s Since %s (%s viewers) "
                                     % (stream["media_display_name"],
                                        stream["media_status"],
                                        stream["channel"]["channel_link"],
                                        stream["media_live_since"],
                                        stream["media_views"]))

                except KeyError:
                    self.bot.action(target,
                                     "%s - %s - %s since %s (%i viewers) "
                                     % (stream["channel"]["display_name"],
                                        stream["channel"]["status"],
                                        stream["channel"]["url"],
                                        hour,
                                        stream["viewers"]))
        else:
            self.bot.privmsg(target, "Nobody is streaming :'(")

    @command(permission='admin', public=False)
    @asyncio.coroutine
    def blacklist(self, mask, target, args):
        """Blacklist given channel/user from !casts, !streams

            %%blacklist get
            %%blacklist add <user>
            %%blacklist del <user>
        """
        if not (yield from self.__isNickservIdentified(mask.nick)):
            return
        if 'blacklist' not in self.bot.db:
            self.bot.db['blacklist'] = {'users': {}}
        add, delete, get, user = args.get('add'), args.get('del'), args.get('get'), args.get('<user>')
        if get:
            return self.bot.db['blacklist'].get('users', {})
        if user is not None:
            users = self.bot.db['blacklist'].get('users', {})
            if add:
                users[user] = True
                self.bot.db.set('blacklist', users=users)
                return "Added {} to blacklist".format(user)
            if delete:
                if users.get(user):
                    del users[user]
                    return "Removed {} from the blacklist".format(user)
                return "{} is not on the blacklist.".format(user)
        return "Something went wrong."

    @command(permission='admin', public=False)
    @asyncio.coroutine
    def badwords(self, mask, target, args):
        """Adds/removes a given keyword from the checklist 

            %%badwords get
            %%badwords add <word> <gravity>
            %%badwords del <word>
        """
        if not (yield from self.__isNickservIdentified(mask.nick)):
            return
        global BADWORDS
        if 'badwords' not in self.bot.db:
            self.bot.db['badwords'] = {'words': {}}
        add, delete, get, word, gravity = args.get('add'), args.get('del'), args.get('get'), args.get('<word>'), args.get('<gravity>')
        if add:
            try:
                words = self.bot.db['badwords'].get('words', {})
                words[word] = int(gravity)
                self.bot.db.set('badwords', words=words)
                BADWORDS = words
                return 'Added "{word}" to watched badwords with gravity {gravity}'.format(**{
                        "word": word,
                        "gravity": gravity, 
                    })
            except:
                return "Failed adding the word. Did you not use a number for the gravity?"
        elif delete:
            words = self.bot.db['badwords'].get('words', {})
            if words.get(word):
                del self.bot.db['badwords']['words'][word]
                BADWORDS = self.bot.db['badwords'].get('words', {})
                return 'Removed "{word}" from watched badwords'.format(**{
                        "word": word,
                    })
            else:
                return 'Word not found in the list.'
        elif get:
            words = self.bot.db['badwords'].get('words', {})
            self.bot.privmsg(mask.nick, str(len(words)) + " checked badwords:")
            for word in words.keys():
                self.bot.privmsg(mask.nick, '  word: "%s", gravity: %s' % (word, words[word]))

    @command(permission='admin', public=False)
    @asyncio.coroutine
    def repeat(self, mask, target, args):
        """Makes QAI repeat WORDS in <channel> each <seconds>. Use <ID> to remove them again.

            %%repeat get
            %%repeat add <ID> <seconds> <channel> WORDS ...
            %%repeat del <ID>
        """
        if not (yield from self.__isNickservIdentified(mask.nick)):
            return
        global REPETITIONS
        if 'repetitions' not in self.bot.db:
            self.bot.db['repetitions'] = {'text': {}}
        add, delete, get, ID, seconds, channel, WORDS = args.get('add'), args.get('del'), args.get('get'), args.get('<ID>'), args.get('<seconds>'), args.get('<channel>'), " ".join(args.get('WORDS'))
        if get:
            text = self.bot.db['repetitions'].get('text', {})
            self.bot.privmsg(mask.nick, str(len(text)) + " texts repeating:")
            for t in text.keys():
                self.bot.privmsg(mask.nick, '  ID: "%s", each %i seconds, channel: %s, text: %s' % (t, text[t].get('seconds'), text[t].get('channel'), text[t].get('text')))
        elif add:
            try:
                text = self.bot.db['repetitions'].get('text', {})
                if text.get(ID):
                    return "ID already exists. Pick another."
                text[ID] = {
                    "seconds": int(seconds),
                    "text": WORDS,
                    "channel": channel,
                }
                self.bot.db.set('repetitions', text=text)
                REPETITIONS[ID] = repetition.repetitionThread(self.bot, channel, WORDS, int(seconds))
                REPETITIONS[ID].daemon = True
                REPETITIONS[ID].start()
                return 'Done.'
            except:
                return "Failed adding the text."
        elif delete:
            try:
                text = self.bot.db['repetitions'].get('text', {})
                if text.get(ID):
                    del text[ID]
                    self.bot.db.set('repetitions', text=text)
                    REPETITIONS[ID].stop()
                    del REPETITIONS[ID]
                    return 'Done.'
                else:
                    return "Not repeating something with ID <" + ID + ">"
            except:
                return "Failed deleting."

    @command(permission='chatlist')
    @asyncio.coroutine
    def move(self, mask, target, args):
        """Move nick into channel

            %%move <nick> <channel>
        """
        if not (yield from self.__isNickservIdentified(mask.nick)):
            return
        channel, nick = args.get('<channel>'), args.get('<nick>')
        self.move_user(channel, nick)
        self.bot.privmsg(mask.nick, "OK moved %s to %s" % (nick, channel))

    @command(permission='chatlist')
    @asyncio.coroutine
    def chatlist(self, mask, target, args):
        """Chat lists

            %%chatlist
            %%chatlist <channel>
            %%chatlist add <channel> <user>
            %%chatlist del <channel> <user>
        """
        if not (yield from self.__isNickservIdentified(mask.nick)):
            return
        if 'chatlists' not in self.bot.db:
            self.bot.db['chatlists'] = {}
        channel, user, add, remove = args.get('<channel>'), args.get('<user>'), args.get('add'), args.get('del')
        if not add and not remove:
            if not channel:
                self.bot.privmsg(mask.nick, ", ".join(self.bot.db.get('chatlists')))
            else:
                self.bot.privmsg(mask.nick, ", ".join(self.bot.db['chatlists'].get(channel, {}).keys()))
        elif add:
            if channel not in self.bot.db['chatlists']:
                self.bot.db['chatlists'][channel] = {}
            self.bot.db['chatlists'][channel][user] = True
            self.move_user(channel, user)
            self.bot.privmsg(mask.nick, "OK added and moved %s to %s" % (user, channel))
        elif remove:
            if channel not in self.bot.db['chatlists']:
                self.bot.db['chatlists'][channel] = {}
            del self.bot.db['chatlists'][channel][user]
            if len(self.bot.db['chatlists'][channel]) == 0:
                del self.bot.db['chatlists'][channel]
            self.bot.privmsg(mask.nick, "OK removed %s from %s" % (user, channel))

    @command
    def google(self, mask, target, args):
        """google

            %%google WORDS ...
        """
        link = LETMEGOOGLE + "+".join(args.get('WORDS'))
        self.bot.privmsg(target, link)

    @command
    def name(self, mask, target, args):
        """name

            %%name
            %%name <username>
            %%name <username> WORDS ...
        """
        name = args.get('<username>')
        if name == None:
            self.bot.privmsg(target, LINKS["namechange"])
            return
        link = OTHER_LINKS["oldnames"] + name
        self.bot.privmsg(target, link)

    @command
    @asyncio.coroutine
    def tourneys(self, mask, target, args):
        """Check tourneys

            %%tourneys
        """
        if self.spam_protect('tourneys', mask, target, args):
            return
        tourneys = yield from challonge.printable_tourney_list()
        if len(tourneys) < 1:
            self.bot.privmsg(target, "No tourneys found!")

        self.bot.privmsg(target, str(len(tourneys)) + " tourneys:")
        for tourney in tourneys:
            self.bot.action(target, tourney)

    def report(self, name, word, channel, text, gravity):
        reportMsg = 'User "{name}" used bad word "{word}" in irc channel "{channel}". Full text: "{text}". (Gravity {gravity})'.format(**{
                'name' : name,
                'word' : word,
                'channel' : channel,
                'text' : text,
                'gravity' : gravity,
            })
        if gravity >= self.bot.config['report_to_irc_threshold']:
            self.bot.privmsg('#' + self.bot.config['report_to_irc_channel'], reportMsg)
        if gravity >= self.bot.config['report_to_slack_threshold']:
            self.slackThread.sendMessageToChannel(self.bot.config['report_to_slack_channel'], reportMsg)
        if gravity >= self.bot.config['report_instant_kick_threshold']:
            self._taunt(channel=channel, prefix=name, tauntTable=KICK_TAUNTS)
            self.bot.privmsg(channel, "!kick {}".format(name))
