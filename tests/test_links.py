from qai.links import LINKS, LINKS_SYNONYMES, WIKI_LINKS, WIKI_LINKS_SYNONYMES, OTHER_LINKS


def test_existance():
    assert isinstance(LINKS, dict)
    assert isinstance(LINKS_SYNONYMES, dict)
    assert isinstance(WIKI_LINKS, dict)
    assert isinstance(WIKI_LINKS_SYNONYMES, dict)
    assert isinstance(OTHER_LINKS, dict)
