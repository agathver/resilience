"""
Implementation of a circuit breaker
"""
from datetime import timedelta, datetime
from enum import Enum
from threading import RLock
from typing import List, Type

from .exceptions import CallNotAllowedException
from .utils import RingBuffer, Counter


class CircuitBreakerState(Enum):
    """
    Circuit breaker states
    """
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class Result(Enum):
    """
    Call result
    """
    SUCCESS = True
    FAILURE = False


# pylint: disable=too-many-instance-attributes
class CircuitBreaker:
    """
    Decorator to add a circuit breaker to any function
    """

    def __init__(self, name: str,
                 sliding_window_size: int = 10,
                 trip_threshold: float = 0.5,
                 trip_duration: timedelta = timedelta(seconds=5),
                 allowed_calls_in_half_open: int = 2,
                 allowed_exceptions: List[Type[BaseException]] = None):
        """
        Create a new circuit breaker
        :param name:
        :param sliding_window_size:
        :param trip_threshold:
        :param trip_duration:
        :param allowed_calls_in_half_open:
        :param allowed_exceptions:
        """

        if allowed_exceptions is None:
            allowed_exceptions = []

        self.__name = name
        self.__sliding_window_size = sliding_window_size
        self.__trip_threshold = trip_threshold
        self.__trip_duration = trip_duration
        self.__allowed_calls_in_half_open = allowed_calls_in_half_open
        self.__allowed_exceptions = allowed_exceptions

        self.__executions = RingBuffer(self.__sliding_window_size)
        self.__state_transition_lock = RLock()
        self.__calls_since_half_open = Counter(0)

        self.state = CircuitBreakerState.CLOSED

    def __call__(self, func):
        def wrapped_func(*args, **kwargs):
            if self.state == CircuitBreakerState.OPEN:
                raise CallNotAllowedException("Circuit breaker is open")

            try:
                value = func(*args, **kwargs)
                self.__handle_call_success()
                return value
            except BaseException as exception:
                self.__handle_call_failure(exception)
                raise exception

        return wrapped_func

    def __handle_call_failure(self, exception):
        ignore = any([isinstance(exception, allowed_exception)
                      for allowed_exception in self.__allowed_exceptions])

        if ignore:
            self.__handle_call_success()
            return

        with self.__state_transition_lock:
            if self.state == CircuitBreakerState.HALF_OPEN:
                self.state = CircuitBreakerState.OPEN
            elif self.state == CircuitBreakerState.CLOSED:
                self.__executions.add(Result.FAILURE)

                failures = sum([1 for result in self.__executions if result == Result.FAILURE])

                if failures / self.__sliding_window_size > self.__trip_threshold:
                    self.state = CircuitBreakerState.OPEN

    def __handle_call_success(self):
        with self.__state_transition_lock:
            if self.state == CircuitBreakerState.CLOSED:
                self.__executions.add(Result.SUCCESS)
            elif self.state == CircuitBreakerState.HALF_OPEN:
                self.__calls_since_half_open.increment()

            if self.__calls_since_half_open.value > self.__allowed_calls_in_half_open:
                self.state = CircuitBreakerState.CLOSED

    @property
    def state(self):
        """
        Get current state of the circuit breaker
        :return: string circit breaker state
        """
        with self.__state_transition_lock:
            if self.__state == CircuitBreakerState.OPEN:
                if datetime.now() - self.__state_transitioned_at > self.__trip_duration:
                    self.state = CircuitBreakerState.HALF_OPEN

        return self.__state

    @state.setter
    def state(self, current_state: CircuitBreakerState):
        """
        Set current state of the circuit breaker
        :param current_state:
        :return:
        """

        with self.__state_transition_lock:
            self.__state = current_state
            self.__state_transitioned_at = datetime.now()

            if current_state == CircuitBreakerState.HALF_OPEN:
                self.__calls_since_half_open.value = 0

            if current_state == CircuitBreakerState.CLOSED:
                self.__calls_since_half_open.value = 0
                self.__executions.clear()
