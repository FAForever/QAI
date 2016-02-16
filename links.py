LINKS = {
    "faf":        "FAF main page! http://www.faforever.com",
    "forum":        "FAF Forum! http://forums.faforever.com/index.php",
    "support":      "Tech support! http://forums.faforever.com/viewforum.php?f=3",
    "wiki":         "FAF Wiki! http://wiki.faforever.com/index.php?title=Main_Page",
    "news":         "What's new? http://www.faforever.com/news/",

    "replay":       "Replay link: http://replay.faforever.com/ID",
    "unitsdb":      "Unit database: http://content.faforever.com/faf/unitsDB/",
    "namechange":   "Change username: http://app.faforever.com/faf/userName.php",
    "clans":        "FAF clans! http://www.faforever.com/clans/clans_list",

    "github":       "FAF on Github: https://github.com/FAForever",
    "youtube":      "FAF Youtube: https://www.youtube.com/channel/UCkAWiUu4QE172kv-ZuyR42w",

    "replayparser": "Replay parser: http://fafafaf.bitbucket.org/",
    "tumblr":       "FAF Reactions on tumblr: http://fafreactions.tumblr.com/",

    "wwpc":         "World Wide People's Championship: http://forums.faforever.com/viewtopic.php?f=26&t=10627",
    "2v2wwpc":      "2v2 World Wide People's Championship: http://forums.faforever.com/viewtopic.php?f=26&t=9059",
}
LINKS_SYNONYMES = {
    "techsupport":  LINKS["support"],
    "git": LINKS["github"],
    "whatsnew": LINKS["news"],
}

LINKS_SYNONYMES["parser"] = LINKS_SYNONYMES["replays"] = LINKS_SYNONYMES["parsereplay"] = LINKS["replayparser"]
LINKS_SYNONYMES["wwpc2v2"] = LINKS_SYNONYMES["wwpc2x2"] = LINKS_SYNONYMES["2x2wwpc"] = LINKS["2v2wwpc"]

WIKI_LINKS = {
    "adjacency":         "Information on the adjacency bonus: http://wiki.faforever.com/index.php?title=Adjacency_Bonus",
    "avatars":           "Avatars and how to get them: http://wiki.faforever.com/index.php?title=FAF_chat#Avatars",
    "balance":           "How game quality works: http://wiki.faforever.com/index.php?title=The_game_balance_index",
    "chat":              "The FAF chat tab: http://wiki.faforever.com/index.php?title=FAF_chat",
    "connection":        "Help with connection issues: http://wiki.faforever.com/index.php?title=Connection_issues_and_solutions",
    "coop":              "The coop missions and campaign: http://wiki.faforever.com/index.php?title=Coop_Missions",
    "engymod":           "The integrated Engy Mod: http://wiki.faforever.com/index.php?title=Game_Modifications_(Mods)#Engy_Mod",
    "galacticwar":       "Galactic war and playing it: http://wiki.faforever.com/index.php?title=Galactic_War",
    "hostgame":          "How to host and join games: http://wiki.faforever.com/index.php?title=Host_and_join_games",
    "hotbuild":          "Setting up and using HotBuild: http://wiki.faforever.com/index.php?title=Game_Modifications_(Mods)#Gaz_UI_and_Hotbuild",
    "ladder":            "Info on the FAF 1v1 ladder: http://wiki.faforever.com/index.php?title=The_Ladder",
    "ladderpool":        "The Current Ladder map pool: http://wiki.faforever.com/index.php?title=The_Ladder#Map_Pool",
    "leaderboards":      "The 1v1 Ladder Leaderboards: http://wiki.faforever.com/index.php?title=Leaderboards_and_Rating",
    "mapeditor":         "Getting and using the map editor: http://wiki.faforever.com/index.php?title=Map_Editor",
    "irc":               "Connecting to and using FAF chat with IRC: http://wiki.faforever.com/index.php?title=Chat_/_IRC_server",
    "maps":              "The FAF Map Vault: http://wiki.faforever.com/index.php?title=Map_Vault",
    "mapdownload":       "How to download maps: http://wiki.faforever.com/index.php?title=Map_Vault#3._Download_button",
    "moderators":        "List of FAF moderators: http://wiki.faforever.com/index.php?title=User_Groups#FAF_Moderators",
    "mods":              "How mods work with FAF: http://wiki.faforever.com/index.php?title=Game_Modifications_(Mods)",
    "mumble":            "Using Mumble with FAF: http://wiki.faforever.com/index.php?title=Voicechat_(Mumble)",
    "patches":           "All the patch changelogs: http://wiki.faforever.com/index.php?title=Main_Page#Patch_Change_Logs",
    "replays":           "The FAF replay vault: http://wiki.faforever.com/index.php?title=Replay_Vault_%26_Live_Games",
    "rating":            "How rating works in FAF: http://wiki.faforever.com/index.php?title=Global_Ranking",
    "rules":             "The FAF client and forum rules: http://wiki.faforever.com/index.php?title=FAF_Client/Forum_Rules",
    "splitattack":       "Using Split attack in game: http://wiki.faforever.com/index.php?title=Game_Modifications_(Mods)#Split_Attack",
    "trainers":          "List of personal trainers in FAF: http://wiki.faforever.com/index.php?title=User_Groups#Trainers",
    "trueskill":         "Trueskill explained: http://wiki.faforever.com/index.php?title=How_Trueskill_works",
    "tutorials":         "Help with learning how to play: http://wiki.faforever.com/index.php?title=Learning_SupCom",
}
WIKI_LINKS_SYNONYMES = {
    "patchnotes":       WIKI_LINKS["patches"],
    "campaign":         WIKI_LINKS["coop"],
    "missions":         WIKI_LINKS["coop"],
    "training":         WIKI_LINKS["trainers"],
    "chattab":          WIKI_LINKS["chat"],
    "voice":            WIKI_LINKS["mumble"],
    "voicechat":        WIKI_LINKS["mumble"],
}


OTHER_LINKS = {
    "oldnames":        "http://app.faforever.com/faf/userName.php?name=",
}