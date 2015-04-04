#!/usr/bin/python
#-------------------------------------------------------------------------------
# Copyright (c) 2014 Gael Honorez.
# All rights reserved. This program and the accompanying materials
# are made available under the terms of the GNU Public License v3.0
# which accompanies this distribution, and is available at
# http://www.gnu.org/licenses/gpl.html
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#-------------------------------------------------------------------------------



import sys    # sys.setdefaultencoding is cancelled by site.py
reload(sys)    # to re-enable sys.setdefaultencoding()
sys.setdefaultencoding('utf-8')
from irc import bot as ircbot
from irc.bot import Channel
import time
from PySide import QtSql

from fractions import Fraction
from twitch import *
import json

from passwords import DB_SERVER, DB_PORT, DB_LOGIN, DB_PASSWORD, DB_TABLE

from configobj import ConfigObj
config = ConfigObj("/etc/faforever/faforever.conf")
fafbot_config = ConfigObj("fafbot.conf")['fafbot']

from threading import Timer

TWITCH_STREAMS = "https://api.twitch.tv/kraken/streams/?game=" #add the game name at the end of the link (space = "+", eg: Game+Name)
STREAMER_INFO  = "https://api.twitch.tv/kraken/streams/" #add streamer name at the end of the link
GAME = "Supreme+Commander:+Forged+Alliance"
HITBOX_STREAMS = "https://www.hitbox.tv/api/media/live/list?filter=popular&game=811&hiddenOnly=false&limit=30&liveonly=true&media=true"

class bettingSystem(object):
    def __init__(self):
        self.matches = {}

    def addMatch(self, match):
        try:
            if not match.uid in self.matches:
                self.matches[match.uid] = match
            return self.matches[match.uid]
        except:
            return None

    def getMatches(self):
        try:
            return self.matches
        except:
            return None

    def deleteMatch(self, uid):
        try:
            if uid in self.matches:
                del self.matches[uid]
        except:
            pass


class BotModeration(ircbot.SingleServerIRCBot):
    def __init__(self):
        """
        Constructeur qui pourrait prendre des parametres dans un "vrai" programme.
        """
        # FIXME: hardcoded ip
        ircbot.SingleServerIRCBot.__init__(self, [("37.58.123.2", 6667)],
                                           "fafbot", "FAF bot")
        self.nickpass = fafbot_config['nickpass']
        self.nickname = fafbot_config['nickname']

        self.db = QtSql.QSqlDatabase.addDatabase("QMYSQL")
        self.db.setHostName(DB_SERVER)  
        self.db.setPort(DB_PORT)

        self.db.setDatabaseName(DB_TABLE)  
        self.db.setUserName(DB_LOGIN)  
        self.db.setPassword(DB_PASSWORD)
        self.db.open()
        self.db.setConnectOptions("MYSQL_OPT_RECONNECT = 1")

        self.betting = bettingSystem()
        self.info = Information(TWITCH_STREAMS, GAME, STREAMER_INFO)
        self.askForCast = 0
        self.askForYoutube = 0

        Timer(30, self.betCheck).start()

    def isOver(self, uid):
        try:
            query = QtSql.QSqlQuery(self.db)
            query.prepare("SELECT * FROM `game_stats` WHERE `id` = ? AND EndTime IS NOT NULL ")
            query.addBindValue(uid)
            query.exec_()
            if query.size() > 0:
                query.first()
                query.clear()
                return True
            return False
        except:
            return False

    def getWinner(self, uid):
        try:
            query = QtSql.QSqlQuery(self.db)
            query.prepare("SELECT `playerId`, score FROM `game_player_stats` WHERE `gameId` = ?")
            query.addBindValue(uid)
            query.exec_()
            results = {}
            if query.size() > 0:
                while query.next():
                    player = int(query.value(0))
                    score = int(query.value(1))
                    results[score] = player

                return results[max(results)]
            return None
        except:
            return None

    def getNameFromUid(self, uid):
        try:
            query = QtSql.QSqlQuery(self.db)
            query.prepare("(SELECT login FROM faf_lobby.login WHERE id = ? )")
            query.addBindValue(uid)
            query.exec_()
            if query.size() > 0:
                query.first()
                val = str(query.value(0))
                query.clear()
                return val
            else:
                return None     
        except:
            return None   

    def getOdds(self, match):
        try:
            odds = match.odds 
            text = "Odds are %0.2f to 1 in favor of %s" % (Fraction(1.0/odds), self.getNameFromUid(match.mostProbableWinner))
            return text
        except:
            return ''

    def betCheck(self):
        try:
        
            matches = self.betting.getMatches()
            matchsToDelete = []
            for uid in matches:
                #print "checking", uid
                if self.isOver(uid):
                    #print "game is over"
                    winnerUid = self.getWinner(uid)
                    match = matches[uid]
                    odds = match.odds
                    ratio = 0
                    #print "winner is", winnerUid
                    #print "most probable winner was", match.mostProbableWinner  
                    if match.mostProbableWinner == winnerUid:
                        #the most probable winner is the winner, so the odds are in defavor of the winner.
                        ratio = odds
                    else:
                        # we are defeating the odd !
                        ratio = 1.0 + (1.0-odds)

                    betWinners = match.getBetWinners(winnerUid)
                    winnerSize = len(betWinners)
                    loserSize = len(match.players) - winnerSize
                    
                    #print "winners :", winnerUid
                    if betWinners:
                        text = []

                        for betwinnerUid in betWinners:
                            reward = match.getReward(betwinnerUid) 
                            reward = reward + reward * ratio
                            self.addToBalance(reward, betwinnerUid)
                            text = ("%s has won %i on the match \"%s\" (winner was %s). He has now %i credits.") % (self.getNameFromUid(betwinnerUid), reward, match.name, self.getNameFromUid(winnerUid), self.currentBalance(betwinnerUid))
                            self.connection.privmsg("#aeolus", text)
                    else :
                        text = ("no gambler win a bet for %s! (winner of the match was %s)" % (match.name, self.getNameFromUid(winnerUid)))
                        self.connection.privmsg("#aeolus", text)

                    text = ("%i gambler(s) for the winner, %i for the loser.") % (winnerSize, loserSize)
                    self.connection.privmsg("#aeolus", text)
                    matchsToDelete.append(uid)
                    
            for uid in matchsToDelete:
                self.betting.deleteMatch(uid)

            Timer(30, self.betCheck).start()
        except:

            Timer(30, self.betCheck).start()


    def currentBalance(self, uid):
        try:
            query = QtSql.QSqlQuery(self.db)
            query.prepare("SELECT amount FROM faf_lobby.bet WHERE userid = ?")
            query.addBindValue(uid)
            query.exec_()
            if query.size() == 0:
                query3 = QtSql.QSqlQuery(self.db)
                query3.prepare("INSERT INTO `bet`(`userid`, `amount`) VALUES (?,100)")
                query3.addBindValue(uid)
                query3.exec_()
                query.clear()
                query3.clear()
                return 100
            else:
                query.first()
                val = query.value(0)
                if val:
                    return int(val)
                else:
                    return 0
        except:
            return 0

    def getUid(self, nickname):
        try:
            query = QtSql.QSqlQuery(self.db)
            query.prepare("(SELECT id FROM faf_lobby.login WHERE login = ? )")
            query.addBindValue(nickname)
            query.exec_()
            if query.size() > 0:
                query.first()
                return int(query.value(0))
            else:
                return None
        except:
            return None

    def updateBalance(self, amount, uid):
        try:
            query = QtSql.QSqlQuery(self.db)
            query.prepare("UPDATE faf_lobby.bet SET amount = ? WHERE userid = ?")
            query.addBindValue(amount)
            query.addBindValue(uid)
            query.exec_()
        except:
            pass

    def on_pubmsg(self, c, e):
        try:
            message = e.arguments[0]
            if message.startswith("!streams"):
                if time.time() - self.askForCast > 60*10:
                    self.askForCast = time.time()
                    streams = self.info.get_game_streamer_names()
                    try:
                        streams_hitbox = json.loads(urllib2.urlopen(HITBOX_STREAMS).read())
                    except:
                        streams_hitbox = {"livestream": []}
                    num_of_streams = len(streams["streams"]) + len(streams_hitbox["livestream"])
                    if num_of_streams > 0:
                        self.connection.privmsg("#aeolus", "%i Streams online :" % num_of_streams)
                        for stream in streams["streams"]:
                            #print stream["channel"]
                            t = stream["channel"]["updated_at"]
                            date = t.split("T")
                            hour = date[1].replace("Z", "")

                            self.connection.privmsg("#aeolus", "%s - %s - %s Since %s (%i viewers) " % (stream["channel"]["display_name"], stream["channel"]["status"], stream["channel"]["url"], hour, stream["viewers"]))
                        for stream in streams_hitbox["livestream"]:
                            self.connection.privmsg("#aeolus", "%s - %s - %s Since %s (%s viewers) " % (stream["media_display_name"], stream["media_status"], stream["channel"]["channel_link"], stream["media_live_since"], stream["media_views"]))
                    else:
                        self.connection.privmsg("#aeolus", "No one is streaming :'(")
            if message.startswith("!casts"):
                if time.time() - self.askForYoutube > 60*10:
                    self.askForYoutube = time.time()
                    con = urllib2.urlopen("http://gdata.youtube.com/feeds/api/videos?q=forged+alliance+-SWTOR&max-results=5&v=2&orderby=published&alt=jsonc")
                    info = con.read()
                    con.close()
                    data = json.loads(info)
                    self.connection.privmsg("#aeolus", "5 Latest youtube videos:")
                    for item in data['data']['items']:
                        t = item["uploaded"]
                        date = t.split("T")[0]
                        like = "0"
                        if "likeCount" in item:
                            like = item['likeCount']
                        self.connection.privmsg("#aeolus", "%s by %s - %s - %s (%s likes) " % (item['title'], item["uploader"], item['player']['default'].replace("&feature=youtube_gdata_player", ""), date, like))



        except:
            pass

    def on_welcome(self, c, e):
        """

        """
        print "got welcomed"
        #self.connection.join("#aeolus")
        try:
            if self.nickpass and c.get_nickname() != self.nickname:
                # Reclaim our desired nickname
                #print "nick on use"
                c.privmsg('nickserv', 'ghost %s %s' % (self.nickname, self.nickpass))
        except:
            pass
    def on_privnotice(self, c, e):
        try:
            source = e.source.nick        
            print source, e.arguments[0]
            if source and source.lower() == 'ze_pilot_':
                if 'SENDALL' in e.arguments[0] :
                    users = self.channels["#aeolus"].users()
                    chunks = lambda l, n: [l[x: x+n] for x in xrange(0, len(l), n)]
                    mesg = e.arguments[0][9:]
                    print mesg 
                    c = chunks(users, 40)
                    for manyPlayer in c:
                        s=  ",".join(manyPlayer)
                        raw = "PRIVMSG %s :%s" % (s, mesg)
                        print raw
                        #self.send_raw(raw)
                        #self.connection.privmsg(s, mesg)
                elif 'REGISTER' in e.arguments[0]:
                    self.connection.privmsg('nickserv', 'register %s fafbot@faforever.com' % (self.nickpass))
                elif 'LOGIN' in e.arguments[0]:
                    self.connection.privmsg('nickserv', 'identify %s %s' % (self.nickname, self.nickpass))
            
            elif source and source.lower() == 'nickserv':
                if 'IDENTIFY' in e.arguments[0] :
                    # Received request to identify
                    print "identifying"
                    if self.nickpass and self.nickname == c.get_nickname():
                        self.connection.privmsg('nickserv', 'identify %s %s' % (self.nickname, self.nickpass))
                        
                elif "Password accepted" in e.arguments[0]:
                    print "password accepted, joining"
                    time.sleep(1)
                    self.connection.privmsg('Chanserv', 'INVITE #aeon')
                    self.connection.privmsg('Chanserv', 'INVITE #cybran')
                    self.connection.privmsg('Chanserv', 'INVITE #seraphim')
                    self.connection.privmsg('Chanserv', 'INVITE #uef')
                    time.sleep(5)
                    
                    self.connection.join("#aeon")
                    time.sleep(1)
                    self.connection.join("#cybran")
                    time.sleep(1)
                    self.connection.join("#seraphim")
                    time.sleep(1)
                    self.connection.join("#uef")
                    self.connection.join("#aeolus")
                
                
        except:
            pass
    def _on_join(self, c, e):
        try:
            ch = e.target
            nick = e.source.nick
            if nick == c.get_nickname():
                self.channels[ch] = Channel()
                self.connection.send_raw("NAMES" + (ch))
                #self.connection.send_raw("PRIVMSG %s :%s" % ("#aeolus", "yo!"))
            elif "aeolus" in ch :
                #print nick,"has joined", ch
                query = QtSql.QSqlQuery(self.db)
                query.prepare("SELECT faction, IFNULL(dominant,-1) FROM galacticwar.accounts LEFT join galacticwar.domination on galacticwar.accounts.faction = galacticwar.domination.slave WHERE  galacticwar.accounts.uid = (SELECT id FROM faf_lobby.login WHERE login = ? )")
                query.addBindValue(nick)
                query.exec_()
                if query.size() > 0:
                    query.first()
                    if int(query.value(1)) != -1:
                        faction = int(query.value(1))
                    else:
                        faction = int(query.value(0))
                    if faction == 0 :
                        channel = "#UEF"
                    elif faction == 1 :
                        channel = "#Aeon"
                    elif faction == 2 :
                        channel = "#Cybran"
                    elif faction == 3 :
                        channel = "#Seraphim"
    
                    self.connection.privmsg('chanserv', 'INVITE %s %s' % (channel, nick))
            self.channels[ch].add_user(nick)
        except:
            pass

if __name__ == "__main__":
    BotModeration().start()
