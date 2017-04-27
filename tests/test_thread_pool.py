from unittest import TestCase
from bitcallback.thread_pool import ThreadPool
import threading
import queue
import copy
from time import sleep, time


class TestThreadPool(TestCase):

    @staticmethod
    def id_func(job, q):
        q.put(threading.current_thread().ident)
        sleep(0.05)

    def test_number_of_threads(self):
        """Test the requested number of threads are created"""
        nthreads = 11

        # Check correct number ot threads created
        q = queue.Queue()
        pool = ThreadPool(nthreads, TestThreadPool.id_func, args=[q,])

        for i in range(nthreads*2):
            pool.add_job(i)

        # Wait until all jobs are completed
        sleep(3*0.05*nthreads)
        seen = set()
        while True:
            try:
                tid = q.get(block=False)
                seen.add(tid)
            except queue.Empty:
                break

        # Check nthreads were used
        self.assertEqual(len(seen), nthreads)
        pool.close()

    @staticmethod
    def args_func(job, q, *args):
        q.put(args)

    def test_func_args(self):
        """Test args are passed to function"""
        q = queue.Queue()
        pool = ThreadPool(func=TestThreadPool.args_func, args=(q, 1, 2, 3))
        pool.add_job(1)

        processed = q.get()
        self.assertEqual(processed, (1, 2, 3))
        pool.close()

    @staticmethod
    def kwargs_func(job, q, **kwargs):
        q.put(copy.copy(kwargs))

    def test_kwargs(self):
        """Test kwargs are passed to function"""
        q = queue.Queue()
        d = {"a": 1, "b": 2}
        pool = ThreadPool(func=TestThreadPool.kwargs_func, args=(q,), kwargs=d)
        pool.add_job(1)

        processed = q.get()
        self.assertEqual(len(d), len(processed))
        for arg, value in processed.items():
            self.assertTrue(value, d[arg])
            
        pool.close()

    @staticmethod
    def close_func(job, q):
        q.put(job)
        sleep(0.05)

    def test_close(self):
        """Close pool after finishing without discarding job queue"""
        q = queue.Queue()
        pool = ThreadPool(nthreads=1, func=TestThreadPool.close_func, args=(q,))
        
        for i in range(20): # 1 Seconds processing
            pool.add_job(i)

        sleep(0.1)
        pool.close(now=False)

        # Check all jobs where finished before exit
        seen = set()
        while True:
            try:      
                tid = q.get(timeout=0.2)
                seen.add(tid)
            except queue.Empty:
                break

        self.assertEqual(len(seen), 20)

    def test_close_now(self):
        """Close pool discarding pending jobs"""
        q = queue.Queue()
        pool = ThreadPool(nthreads=1, func=TestThreadPool.close_func, args=(q,))
        
        for i in range(20): # 1 Seconds processing
            pool.add_job(i)

        sleep(0.1)
        pool.close(now=True)

        # Check some jobs where discarded
        seen = set()
        while True:
            try:      
                tid = q.get(timeout=0.2)
                seen.add(tid)
            except queue.Empty:
                break

        self.assertLess(len(seen), 10)

    @staticmethod
    def length_func(job):
        sleep(0.1)

    def test_queue_length(self):
        """Test job queue max length"""
        pool = ThreadPool(nthreads=1, func=TestThreadPool.length_func, maxlen=5)
        
        # Add jobs until the queue is filled
        with self.assertRaises(queue.Full):
            for i in range(30):
                pool.add_job(i, block=False)

        self.assertLess(i, 30)
        pool.close()

    def test_blocking_add_job(self):
        """Test add_job blocks until some jobs are processed by the threads"""
        pool = ThreadPool(nthreads=1, func=TestThreadPool.length_func, maxlen=1)

        initial_time = time()
        for i in range(10):
            pool.add_job(i, block=True)
        final_time = time()
        self.assertLess(0.5, final_time-initial_time)

