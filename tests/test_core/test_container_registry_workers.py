"""A container a plugin registers is registered again in a worker process (the Textures window decodes in a pool)."""
from concurrent.futures import ProcessPoolExecutor

from core.containers import ContainerManager
from core.containers.base_container import BaseArchiveContainer


class FakeContainer(BaseArchiveContainer):
    @classmethod
    def can_handle(cls, data: bytes) -> bool:
        return data[:4] == b"FAKE"

    def __init__(self, data: bytes) -> None:
        self.data = data

    def list_files(self):
        return ["x"]

    def read_file(self, path):
        return self.data

    def write_file(self, path, data):
        self.data = data

    def pack(self):
        return self.data


def _opened(data: bytes) -> str:
    container = ContainerManager.open(data)
    return type(container).__name__ if container else ""


def test_worker_process_opens_a_plugin_container():
    ContainerManager.register(FakeContainer)
    assert FakeContainer in ContainerManager.registered()
    with ProcessPoolExecutor(max_workers=1, initializer=ContainerManager.register_all,
                             initargs=(ContainerManager.registered(),)) as pool:
        assert pool.submit(_opened, b"FAKE data").result(timeout=60) == "FakeContainer"
    with ProcessPoolExecutor(max_workers=1) as pool:   # without the initializer the worker does not know it
        assert pool.submit(_opened, b"FAKE data").result(timeout=60) == ""
