import asyncio
import threading

from concurrent.futures import Future

# Procured from https://github.com/jamesmccannon02/OctoPrint-Tplinkautoshutdown


class ThreadedWorker:
    def __init__(self):
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.loop_future = Future()
        self.thread.start()

    @property
    def loop(self):
        return self.loop_future.result()

    def run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self.loop_future.set_result(loop)
        return loop.run_forever()
