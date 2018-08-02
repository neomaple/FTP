from threading import Thread
import queue


class MyPool:
    def __init__(self, maxsize):
        self.queue = queue.Queue(maxsize)

        for i in range(maxsize):
            self.queue.put(Thread)

    def get_thread(self):
        return self.queue.get()

    def add_thread(self):
        self.queue.put(Thread)
