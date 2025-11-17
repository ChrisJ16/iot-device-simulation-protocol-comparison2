import random
import time
from threading import Lock

# Fault injection parameters (defaults)
LOSS_RATE = 0.2  # probability of message loss
LATENCY_RANGE = (0, 0)  # in milliseconds
FAIL_PROB = 0.3 # probability of device failure per message
_device_failures = {}  # device_id -> failed_until (timestamp)
_lock = Lock()


def should_drop() -> bool:
    return random.random() < LOSS_RATE


def get_network_delay() -> float:
    """Return a delay in seconds to simulate network latency."""
    lo, hi = LATENCY_RANGE
    if hi <= lo:
        return lo / 1000.0
    return random.uniform(lo, hi) / 1000.0


def maybe_fail(device_id: str):
    """Randomly set a failure for device_id based on FAIL_PROB.

    If device is chosen to fail, set a random failure duration (2-10s).
    """
    global _device_failures
    if random.random() < FAIL_PROB:
        dur = random.uniform(2.0, 10.0)
        until = time.time() + dur
        with _lock:
            _device_failures[device_id] = until


def is_device_failed(device_id: str) -> bool:
    with _lock:
        until = _device_failures.get(device_id)
        if not until:
            return False
        if time.time() > until:
            # recovered
            del _device_failures[device_id]
            return False
        return True
