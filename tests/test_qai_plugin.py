import configparser
from inspect import iscoroutine
from qai.qai_plugin import Plugin
from warnings import catch_warnings, simplefilter

config = configparser.ConfigParser()
config.read('config.ini')


class bot():
    target = '#qai_testing'
    nick = config['bot']['nick']

    def __init__(self, config):
        self.config = config['bot']


bot_instance = bot(config)
QAI = Plugin(bot_instance)


command_arguments = [
    bot_instance,
    bot_instance.target,
    'args'
]


def test_iscoroutine():
    with catch_warnings():
        simplefilter('ignore', RuntimeWarning)
        assert iscoroutine(QAI.on_priv_msg())
        assert iscoroutine(QAI.hitbox_streams())
        assert iscoroutine(QAI.twitch_streams())
        assert iscoroutine(QAI.youtube_streams())
        assert iscoroutine(QAI._Plugin__is_nick_serv_identified(bot.nick))
        assert iscoroutine(QAI.casts(*command_arguments))
        assert iscoroutine(QAI.streams(*command_arguments))
        assert iscoroutine(QAI.groupping(*command_arguments))
        assert iscoroutine(QAI.tournaments(*command_arguments))
        assert iscoroutine(QAI.tourneys(*command_arguments))
