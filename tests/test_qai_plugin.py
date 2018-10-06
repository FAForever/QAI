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

        assert iscoroutine(QAI.hidden(*command_arguments))
        assert iscoroutine(QAI.taunt(*command_arguments))
        assert iscoroutine(QAI.explode(*command_arguments))
        assert iscoroutine(QAI.hug(*command_arguments))
        assert iscoroutine(QAI.flip(*command_arguments))
        assert iscoroutine(QAI.join(*command_arguments))
        assert iscoroutine(QAI.leave(*command_arguments))
        assert iscoroutine(QAI.offline_message(*command_arguments))
        assert iscoroutine(QAI.puppet(*command_arguments))
        assert iscoroutine(QAI.mode(*command_arguments))
        assert iscoroutine(QAI.reload(*command_arguments))
        assert iscoroutine(QAI.slap(*command_arguments))
        assert iscoroutine(QAI.casts(*command_arguments))
        assert iscoroutine(QAI.streams(*command_arguments))
        assert iscoroutine(QAI.groupping(*command_arguments))
        assert iscoroutine(QAI.group(*command_arguments))
        assert iscoroutine(QAI.group_manage(*command_arguments))
        assert iscoroutine(QAI.blacklist(*command_arguments))
        assert iscoroutine(QAI.bad_words(*command_arguments))
        assert iscoroutine(QAI.rwords(*command_arguments))
        assert iscoroutine(QAI.reaction_words(*command_arguments))
        assert iscoroutine(QAI.repeat(*command_arguments))
        assert iscoroutine(QAI.move(*command_arguments))
        assert iscoroutine(QAI.chat_list(*command_arguments))
        assert iscoroutine(QAI.tournaments(*command_arguments))
        assert iscoroutine(QAI.tourneys(*command_arguments))
