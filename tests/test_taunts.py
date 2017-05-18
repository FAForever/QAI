from taunts import TAUNTS, SPAM_PROTECT_TAUNTS, KICK_TAUNTS


def test_existance():
    assert isinstance(TAUNTS, list)
    assert isinstance(SPAM_PROTECT_TAUNTS, list)
    assert isinstance(KICK_TAUNTS, list)
