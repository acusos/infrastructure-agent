from src.tools.logs import get_recent_errors


def test_logs():

    result = get_recent_errors()

    assert isinstance(result, str)

    assert len(result) > 0
