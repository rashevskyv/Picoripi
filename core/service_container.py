from typing import Dict, Type, Any, TypeVar

T = TypeVar('T')

class ServiceContainer:
    """Service container implementation."""
    def __init__(self) -> None:
        """Initialize a new instance."""
        self._services: Dict[Type[Any], Any] = {}

    def register(self, service_type: Type[T], instance: T) -> None:
        """
        Registers a service instance in the container.
        """
        self._services[service_type] = instance

    def get(self, service_type: Type[T]) -> T:
        """
        Retrieves a registered service instance from the container by its type.
        Raises KeyError if the service is not registered.
        """
        if service_type not in self._services:
            raise KeyError(f"Service '{service_type.__name__}' is not registered.")
        return self._services[service_type]
