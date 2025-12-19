from bot.utils.timeparse import parse_time, TimeParseError


def test_parse_minutes():
    delta = parse_time("10m")
    assert delta.total_seconds() == 600


def test_invalid_format():
    try:
        parse_time("abc")
    except TimeParseError:
        assert True
    else:
        assert False
