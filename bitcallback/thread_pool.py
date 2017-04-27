import threading
import queue
from copy import copy

MSG_JOB = 0
MSG_EXIT = 1
JOB_QUEUE_MAX_LENGTH = 1000


class ThreadPool(object):

    def __init__(self, nthreads=5, 
            func=None, args=None, kwargs=None, 
            daemon=True, maxlen=JOB_QUEUE_MAX_LENGTH):
        """
        Arguments:
            nthread (int): Number of threads available in the pool
            func (function): Job processing function. It will called with
                the job as it first arguments, followed of args and kwargs.
                funct(job, *args, **kwargs)
            args (list|tuple):
            kwargs (dict): Extra arguments passed to worker func each
                time it's called.
            daemon (bool): Launch threads as daemon
            maxlen (integer): job queue max size (0: infinite)
        """
        # Pending jobs queue
        self._pending_q = queue.Queue(maxsize=maxlen)
        self._close_flag = threading.Event()
        self._daemon = daemon
        self._maxlen = maxlen

        # 
        self._func= func

        # Convert to tuple to avoid modifications
        self._args = tuple(args) if args else ()

        # function keyword arguments
        self._kwargs = kwargs if kwargs else {}
  
        # Initialize all 
        self._thread_pool = [self._create_thread() for _ in range(nthreads)]

    @staticmethod
    def worker_thread(self):
        """
        Argument:
            thread_pool (ThreadPool):
            process_func (function): function 
        """
        job_q = self._pending_q

        while True:
            msg, job = job_q.get()
            if msg == MSG_EXIT:
                break
        
            args = (job,) + self._args
            kwargs = copy(self._kwargs) # Just a precaution
            self._func(*args, **kwargs)

    def _create_thread(self):
        t = threading.Thread(target=ThreadPool.worker_thread, 
                args=(self,), daemon=True)
        t.start()
        return t

    def add_job(self, job, block=True, timeout=None):
        """Add job to the queue. If block is true and timeout is None (the default), 
        block if necessary until a free slot is available. If timeout is a positive number, 
        it blocks at most timeout seconds and raises the Full exception if no free slot 
        was available within that time. 
        Otherwise (block is false), put the job on the queue if a free slot is immediately 
        available, else raise the Full exception (timeout is ignored in that case).
        """
        # Prevent adding more jobs when closing
        if self._close_flag.is_set():
            raise queue.Full
        self._pending_q.put((MSG_JOB, job), block, timeout)

    def close(self, now=True, timeout=None):
        """
        Arguments:
            now(bool): When False it will wait until all queued jobs are
                processed, otherwise it will exit after each thread finish
                its current job. 
            timeout(float|None): Timeout for thread join
        """
        self._close_flag.set()

        # Purge job queue for inmmediate exit
        while now:
            try:
                self._pending_q.get_nowait()
            except queue.Empty:
                break

        # Enqueue Exit messages to wakeup all blocked threads
        for _ in range(len(self._thread_pool)*2):
            self._pending_q.put((MSG_EXIT, None))

        # Join...
        for t in self._thread_pool:
            t.join(timeout)
