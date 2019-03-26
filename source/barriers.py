"""
Barriers
"""

from threading import Condition, Event, Lock

class ReusableBarrier(object):
    """
    Reusable thread barrier
    """
    def __init__(self, num_threads):
        """
        Constructor

        @type num_threads: Integer
        @param num_threads: number of threads that will stop at the barrier
        """
        self.num_threads = num_threads
        self.count_threads = self.num_threads
        self.cond = Condition()

    def wait(self):
        """
        A thread will wait for all other thread to stop at the barrier
        before it will continue its execution
        """
        self.cond.acquire()
        self.count_threads -= 1
        if self.count_threads == 0:
            self.cond.notify_all()
            self.count_threads = self.num_threads
        else:
            self.cond.wait()
        self.cond.release()

class SimpleBarrier(object):
    """
    Thread barrier which is only usable once.
    """
    def __init__(self, num_threads):
        """
        Constructor

        @type num_threads: Integer
        @param num_threads: number of threads that will stop at the barrier
        """
        self.num_threads = num_threads
        self.count_threads = self.num_threads
        self.count_lock = Lock()
        self.threads_event = Event()

    def wait(self):
        """
        A thread will wait for all other thread to stop at the barrier
        before it will continue its execution
        """
        with self.count_lock:
            self.count_threads -= 1
            if self.count_threads == 0:
                self.threads_event.set()
        self.threads_event.wait()
