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

from taunts import TAUNTS

TWITCH_STREAMS = "https://api.twitch.tv/kraken/streams/?game=Supreme+Commander:+Forged+Alliance" #add the game name at the end of the link (space = "+", eg: Game+Name)
HITBOX_STREAMS = "https://www.hitbox.tv/api/media/live/list?filter=popular&game=811&hiddenOnly=false&limit=30&liveonly=true&media=true"
YOUTUBE_SEARCH = "https://www.googleapis.com/youtube/v3/search?safeSearch=strict&order=date&part=snippet&q=Forged%2BAlliance&maxResults=15&key={}"
YOUTUBE_DETAIL = "https://www.googleapis.com/youtube/v3/videos?part=snippet,statistics&id={}&key={}"
URL_MATCH = ".*(https?:\/\/[^ ]+\.[^ ]*).*"

@irc3.extend
def action(bot, *args):
    bot.privmsg(args[0], '\x01ACTION ' + args[1] + '\x01')

@irc3.plugin
class Plugin(object):

    def __init__(self, bot):
        self.bot = bot
        self.timers = {'casts': 0, 'streams': 0}
        self._rage = 0

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
                    self.bot.privmsg('OperServ', 'svsjoin %s %s' % (mask.nick, channel))

    @irc3.event(irc3.rfc.PRIVMSG)
    @asyncio.coroutine
    def on_privmsg(self, *args, **kwargs):
        msg, channel, sender = kwargs['data'], kwargs['target'], kwargs['mask']
        if 'QAI' in sender.nick:
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
        except (KeyError, ValueError, AttributeError):
            pass

    @command(permission='admin')
    def taunt(self, mask, target, args):
        """Send a taunt

            %%taunt
            %%taunt <person>
        """
        p = args.get('<person>')
        if p == 'QAI':
            p = mask.nick
        self._taunt(channel=target, prefix=p)

    @command(permission='admin')
    def explode(self, mask, target, args):
        """Explode

            %%explode
        """
        self.bot.action(target, "explodes")

    @command
    def join(self, mask, target, args):
        """Overtake the given channel

            %%join <channel>
        """
        self.bot.join(args['<channel>'])

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
        self.bot.reload('qai')

    @command(permission='admin')
    def slap(self, mask, target, args):
        """Slap this guy

            %%slap <guy>
        """
        self.bot.action(target, "slaps %s " % args['<guy>'])

    def _taunt(self, channel=None, prefix=None):
        if channel is None:
            channel = "#qai_channel"
        if prefix is None:
            prefix = ''
        else:
            prefix = '%s: ' % prefix
        self.bot.privmsg(channel, "%s%s" % (prefix, random.choice(TAUNTS)))

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

    def spam_protect(self, cmd, mask, target, args):
        if time.time() - self.timers[cmd] <= 60*5:
            self._taunt(channel=target, prefix=mask.nick)
            if self._rage > 2:
                self.bot.privmsg(target, "!kick {}".format(mask.nick))
            self._rage += 1
            return True
        self._rage = 0
        self.timers[cmd] = time.time()

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
                                     "%s - %s - %s since %s (%i viewers) "
                                     % (stream["channel"]["display_name"],
                                        stream["channel"]["status"],
                                        stream["channel"]["url"],
                                        hour,
                                        stream["viewers"]))
                except KeyError:
                    self.bot.privmsg(target,
                                     "%s - %s - %s Since %s (%s viewers) "
                                     % (stream["media_display_name"],
                                        stream["media_status"],
                                        stream["channel"]["channel_link"],
                                        stream["media_live_since"],
                                        stream["media_views"]))
        else:
            self._taunt(target)

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
            self.bot.privmsg(mask.nick, "OK added %s to %s" % (user, channel))
        elif remove:
            if channel not in self.bot.db['chatlists']:
                self.bot.db['chatlists'][channel] = {}
            del self.bot.db['chatlists'][channel][user]
            self.bot.privmsg(mask.nick, "OK removed %s from %s" % (user, channel))


