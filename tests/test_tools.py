from src.tools.gpu import get_gpu_status
from src.tools.memory import get_memory_status
from src.tools.disk import get_disk_status
from src.tools.docker import get_docker_status
from src.tools.services import get_failed_services


def test_gpu():
    result = get_gpu_status()
    assert result is not None


def test_memory():
    result = get_memory_status()
    assert result is not None


def test_disk():
    result = get_disk_status()
    assert result is not None


def test_docker():
    result = get_docker_status()
    assert result is not None


def test_services():
    result = get_failed_services()
    assert result is not None
