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

import challonge
from taunts import TAUNTS, SPAM_PROTECT_TAUNTS, KICK_TAUNTS
from links import LINKS, LINKS_SYNONYMES, WIKI_LINKS, WIKI_LINKS_SYNONYMES

ALL_TAUNTS = [] # extended in init
TWITCH_STREAMS = "https://api.twitch.tv/kraken/streams/?game=Supreme+Commander:+Forged+Alliance" #add the game name at the end of the link (space = "+", eg: Game+Name)
HITBOX_STREAMS = "https://api.hitbox.tv/media/live/list?filter=popular&game=811&hiddenOnly=false&limit=30&liveonly=true&media=true"
YOUTUBE_SEARCH = "https://www.googleapis.com/youtube/v3/search?order=date&type=video&part=snippet&q=Forged%2BAlliance|Supreme%2BCommander&relevanceLanguage=eng&maxResults=15&key={}"
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
        global ALL_TAUNTS
        ALL_TAUNTS.extend(TAUNTS)
        ALL_TAUNTS.extend(SPAM_PROTECT_TAUNTS)
        challonge.setChallongeData(self.bot.config['challonge_username'], self.bot.config['challonge_api_key'])

    @classmethod
    def reload(cls, old):
        return cls(old.bot)

    def after_reload(self):
        self._taunt('#qai_channel')

    @irc3.event(irc3.rfc.CONNECTED)
    def nickserv_auth(self, *args, **kwargs):
        self.bot.privmsg('nickserv', 'identify %s' % self.bot.config['nickserv_password'])

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

    @command(permission='admin')
    def taunt(self, mask, target, args):
        """Send a taunt

            %%taunt
            %%taunt <person>
        """
        p = args.get('<person>')
        if p == self.bot.config['nick']:
            p = mask.nick
        self._taunt(channel=target, prefix=p)

    @command(permission='admin')
    def explode(self, mask, target, args):
        """Explode

            %%explode
        """
        self.bot.action(target, "explodes")

    @command(permission='admin')
    def hug(self, mask, target, args):
        """Hug someone

            %%hug
            %%hug <someone>
        """
        someone = args['<someone>']
        if someone == None:
            someone = mask.nick
        elif someone == self.bot.config['nick']:
            self._taunt(channel=target, prefix=mask.nick)
            return
        self.bot.action(target, "hugs " + someone)

    @command(permission='admin')
    def flip(self, mask, target, args):
        """Flip table

            %%flip
        """
        self.bot.privmsg(target, "(╯°□°）╯︵ ┻━┻")

    @command
    def join(self, mask, target, args):
        """Overtake the given channel

            %%join <channel>
        """
        self.bot.join(args['<channel>'])

    @command(permission='admin')
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
    def link(self, mask, target, args):
        """Link to a website

            %%link
            %%link <argument>
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
    def puppet(self, mask, target, args):
        """Puppet

            %%puppet <target> WORDS ...
        """
        t = args.get('<target>')
        m = " ".join(args.get('WORDS'))
        self.bot.privmsg(t, m)

    @command(permission='admin', public=False)
    def reload(self, mask, target, args):
        """Reboot the mainframe

            %%reload
        """
        self.bot.reload(self.bot.config['nick'])

    @command(permission='admin')
    def slap(self, mask, target, args):
        """Slap this guy

            %%slap <guy>
        """
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
                if channel_title not in self.bot.db['blacklist'].get('users', {}) \
                        and channel_title != '':
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
    def blacklist(self, mask, target, args):
        """Blacklist given channel/user from !casts, !streams

            %%blacklist
            %%blacklist <user>
        """
        if 'blacklist' not in self.bot.db:
            self.bot.db['blacklist'] = {'users': {}}
        user = args.get('<user>')
        if user is not None:
            users = self.bot.db['blacklist'].get('users', {})
            users[user] = True
            self.bot.db.set('blacklist', users=users)
            return "Added {} to blacklist".format(user)
        else:
            return self.bot.db['blacklist'].get('users', {})

    @command(permission='chatlist')
    def move(self, mask, target, args):
        """Move nick into channel

            %%move <nick> <channel>
        """
        channel, nick = args.get('<channel>'), args.get('<nick>')
        self.move_user(channel, nick)
        self.bot.privmsg(mask.nick, "OK moved %s to %s" % (nick, channel))

    @command(permission='chatlist')
    def chatlist(self, mask, target, args):
        """Chat lists

            %%chatlist
            %%chatlist <channel>
            %%chatlist add <channel> <user>
            %%chatlist del <channel> <user>
        """
        print(args)
        if 'chatlists' not in self.bot.db:
            self.bot.db['chatlists'] = {}
        channel, user, add, remove = args.get('<channel>'), args.get('<user>'), args.get('add'), args.get('del')
        if not add and not remove:
            if not channel:
                self.bot.privmsg(mask.nick, repr(self.bot.db.get('chatlists')))
            else:
                self.bot.privmsg(mask.nick, repr(self.bot.db['chatlists'].get(channel, {}).keys()))
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
            self.bot.privmsg(mask.nick, "OK removed %s from %s" % (user, channel))

    @command
    def google(self, mask, target, args):
        """google

            %%google WORDS ...
        """
        link = LETMEGOOGLE + "+".join(args.get('WORDS'))
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
