# -*- coding: utf-8 -*-
import json
import random
import asyncio
import aiohttp
import aiomysql
import itertools
import irc3
from irc3.plugins.command import command
import time

from taunts import TAUNTS

TWITCH_STREAMS = "https://api.twitch.tv/kraken/streams/?game=Supreme+Commander:+Forged+Alliance" #add the game name at the end of the link (space = "+", eg: Game+Name)
HITBOX_STREAMS = "https://www.hitbox.tv/api/media/live/list?filter=popular&game=811&hiddenOnly=false&limit=30&liveonly=true&media=true"
YOUTUBE_SEARCH = "https://www.googleapis.com/youtube/v3/search?safeSearch=strict&order=date&part=snippet&q=Forged%2BAlliance&key={}"

@irc3.plugin
class Plugin(object):

    def __init__(self, bot):
        self.bot = bot

    @classmethod
    def reload(cls, old):
        return cls(old.bot)

    def after_reload(self):
        self._taunt('#qai_channel')

    @irc3.event(irc3.rfc.CONNECTED)
    def nickserv_auth(self, *args, **kwargs):
        print(self.bot.config)
        self.bot.privmsg('nickserv', 'identify %s' % self.bot.config['nickserv_password'])

    @irc3.event(irc3.rfc.JOIN)
    def on_join(self, channel, mask):
        if channel == '#aeolus' and mask == self.bot.mask:
            self._taunt(channel)

    @command(permission='admin')
    def taunt(self, mask, target, args):
        """Send a taunt

            %%taunt
            %%taunt <person>
        """
        self._taunt(channel=target, prefix=args.get('<person>', ''))

    @command
    def join(self, mask, target, args):
        """Overtake the given channel

            %%join <channel>
        """
        self.bot.join(args['<channel>'])

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
        yield "slap! %s " % args['<guy>']

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
            return json.loads(data.decode())['livestreams']
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
        req = yield from aiohttp.request('GET', YOUTUBE_SEARCH.format(self.bot.config['youtube_key']))
        data = json.loads((yield from req.read()).decode())
        casts = []
        print(data)
        self.bot.privmsg(target, "Recent casts:")
        for item in itertools.takewhile(lambda _: len(casts) < 5, data['items']):
            try:
                self.bot.privmsg(target,
                    "{title} - {date}: {link}".format(
                    **{
                        "id": item['id']['videoId'],
                        "title": item['snippet']['title'],
                        "description": item['snippet']['description'],
                        "date": time.strftime("%x",
                                              time.strptime(item['snippet']['publishedAt'],
                                                            self.bot.config['youtube_time_fmt'])),
                        "link": "http://youtu.be/{}".format(item['id']['videoId'])
                    }))
            except (KeyError, ValueError):
                pass

    @command
    @asyncio.coroutine
    def streams(self, mask, target, args):
        """List current live streams

            %%streams
        """
        streams = yield from self.hitbox_streams()
        streams.extend((yield from self.twitch_streams()))

        if len(streams) > 0:
            self.bot.privmsg(target, "%i streams online:" % len(streams))
            for stream in streams:
                t = stream["channel"]["updated_at"]
                date = t.split("T")
                hour = date[1].replace("Z", "")

                try:
                    self.bot.privmsg(target,
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
