import pytest
from core.service_container import ServiceContainer

class MockService:
    def __init__(self, name: str):
        self.name = name

class AnotherService:
    pass

def test_service_container_register_and_get():
    container = ServiceContainer()
    service_a = MockService("A")
    service_b = AnotherService()
    
    container.register(MockService, service_a)
    container.register(AnotherService, service_b)
    
    assert container.get(MockService) is service_a
    assert container.get(AnotherService) is service_b
    assert container.get(MockService).name == "A"

def test_service_container_key_error():
    container = ServiceContainer()
    
    with pytest.raises(KeyError) as exc_info:
        container.get(MockService)
        
    assert "Service 'MockService' is not registered" in str(exc_info.value)
