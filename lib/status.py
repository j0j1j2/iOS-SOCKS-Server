#!python3
# Pretty statistics view originally by @philrosenthal.

import asyncio
import logging
import sys
import threading
import time

if "Pythonista" in sys.executable:
    import console


class ThroughputTracker:
    def __init__(self, smoothing: float = 0.5):
        self._smoothing = smoothing
        self._window = 0
        self._average = 0.0
        self._total = 0
        self._last_update = time.time()

    def add(self, amount: int) -> None:
        self._window += amount

    def update(self) -> tuple[float, int]:
        now = time.time()
        duration = now - self._last_update
        if duration < 0.1:
            return (self._average, self._total)

        self._last_update = now
        new_speed = self._window / duration
        smoothing = self._smoothing**duration
        self._average = smoothing * self._average + (1 - smoothing) * new_speed
        self._total += self._window
        self._window = 0
        return (self._average, self._total)


class TrafficStats:
    def add_inbound(self, nbytes: int) -> None:
        ...

    def add_outbound(self, nbytes: int) -> None:
        ...

    def add_connection(self) -> None:
        ...

    def remove_connection(self) -> None:
        ...


class SimpleTrafficStats(TrafficStats):
    def __init__(self) -> None:
        self.inbound = 0
        self.outbound = 0
        self.connections = 0

    def add_inbound(self, nbytes: int) -> None:
        self.inbound += nbytes

    def add_outbound(self, nbytes: int) -> None:
        self.outbound += nbytes

    def add_connection(self) -> None:
        self.connections += 1

    def remove_connection(self) -> None:
        self.connections -= 1


class StatusMonitor(TrafficStats, logging.Handler):
    def __init__(
        self,
        banner: str,
        interval: float = 1,
        smoothing: float = 0.5,
        log_level: int = logging.NOTSET,
    ):
        logging.Handler.__init__(self, log_level)
        self.banner = banner
        self.interval = interval
        self.inbound = ThroughputTracker(smoothing)
        self.outbound = ThroughputTracker(smoothing)
        self.num_connections = 0
        self.messages: list[str] = []
        self.num_errors = 0
        self._lock = threading.Lock()

    def add_inbound(self, nbytes: int) -> None:
        with self._lock:
            self.inbound.add(nbytes)

    def add_outbound(self, nbytes: int) -> None:
        with self._lock:
            self.outbound.add(nbytes)

    def add_connection(self) -> None:
        with self._lock:
            self.num_connections += 1

    def remove_connection(self) -> None:
        with self._lock:
            self.num_connections -= 1

    def emit(self, record: logging.LogRecord) -> None:
        with self._lock:
            self.messages.append(self.format(record))
            if len(self.messages) > 5:
                self.messages = self.messages[-5:]
            if record.levelno >= logging.ERROR:
                self.num_errors += 1

    def get_snapshot(self) -> dict:
        """Return a frozen snapshot of current stats for the UI to read.
        Thread-safe: uses a lock to prevent torn reads from ThroughputTracker."""
        with self._lock:
            inbound_average, inbound_total = self.inbound.update()
            outbound_average, outbound_total = self.outbound.update()
            return {
                "inbound_speed": inbound_average,
                "inbound_total": inbound_total,
                "outbound_speed": outbound_average,
                "outbound_total": outbound_total,
                "connections": self.num_connections,
                "errors": self.num_errors,
                "messages": list(self.messages),
            }

    async def render_forever(self) -> None:
        while True:
            await asyncio.sleep(self.interval)

            # Clear the console
            if "Pythonista" in sys.executable:
                console.clear()
            else:
                print("\033c", end="")

            print(self.banner)

            snap = self.get_snapshot()
            megabit = 1024 * 1024 / 8
            megabyte = 1024 * 1024

            # Print the table
            print(f"{'Direction':<12} | {'Traffic (Mbps)':<15}")
            print(f"{'-'*12} | {'-'*15}")
            print(f"{'In':<12} | {snap['inbound_speed'] / megabit:<15.2f}")
            print(f"{'Out':<12} | {snap['outbound_speed'] / megabit:<15.2f}")
            # Print a blank line
            print()
            print(f"{'Connections:':<12} {snap['connections']:>6}")
            print(f"{'Total In:':<12} {snap['inbound_total'] / megabyte:>6.2f} MB")
            print(f"{'Total Out:':<12} {snap['outbound_total'] / megabyte:>6.2f} MB")
            print(
                f"{'Total:':<12} {(snap['inbound_total'] + snap['outbound_total']) / megabyte:>6.2f} MB"
            )
            print()
            if snap["errors"]:
                print(f"Errors: {snap['errors']}")
            if snap["messages"]:
                print("Last 5 log messages:")
                for msg in snap["messages"]:
                    print(f"    {msg}")


if __name__ == "__main__":
    import random

    stats = StatusMonitor("Test mode", interval=1)
    logging.getLogger().addHandler(stats)

    async def random_traffic() -> None:
        stats.add_connection()
        while 1:
            await asyncio.sleep(0.1)
            stats.add_inbound(random.randrange(100000))
            stats.add_outbound(random.randrange(100000))
            if random.random() < 0.1:
                logging.error("random error %d", random.randrange(100))

    async def main() -> None:
        asyncio.create_task(random_traffic())
        await stats.render_forever()

    asyncio.run(main())
