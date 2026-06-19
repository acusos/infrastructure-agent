from src.tools.health import get_health_status


def test_health():

    result = get_health_status()

    assert isinstance(result, str)

    assert "AI SERVER HEALTH" in result
    assert "GPU" in result
    assert "MEMORY" in result
    assert "DOCKER" in result
    assert "STORAGE" in result
