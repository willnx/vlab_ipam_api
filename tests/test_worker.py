# -*- coding: UTF-8 -*-
"""A suite of unit tests for the worker.py module"""
import unittest
from unittest.mock import patch, MagicMock

from vlab_ipam_api import worker


class TestWorker(unittest.TestCase):
    """A suite of test cases for the worker.py module"""

    @patch.object(worker, 'pingable')
    @patch.object(worker, 'update_record')
    def test_worker_thread(self, fake_update_record, fake_pingable):
        """``Worker`` correctly subclasses threading.Thread"""
        fake_queue = MagicMock()
        fake_queue.get.return_value = ('myBox', '1.2.3.4')
        fake_logger = MagicMock()
        t = worker.Worker(tid=1, logger=fake_logger, work_queue=fake_queue)
        t.start()
        t.keep_running = False
        t.join()

        self.assertTrue(isinstance(t, worker.threading.Thread))

    @patch.object(worker, 'pingable')
    @patch.object(worker, 'update_record')
    def test_worker_thread_not_pingable(self, fake_update_record, fake_pingable):
        """``Worker.run`` updates the IPAM database if the IP is not pingable"""
        fake_queue = MagicMock()
        fake_queue.get.return_value = ('myBox', '1.2.3.4')
        fake_logger = MagicMock()
        fake_pingable.return_value = False
        t = worker.Worker(tid=1, logger=fake_logger, work_queue=fake_queue)
        t.start()
        t.keep_running = False
        t.join()

        args, kwargs = fake_update_record.call_args
        expected_args = ('myBox', '1.2.3.4')
        expected_kwargs = {'routable': False}

        self.assertEqual(args, expected_args)
        self.assertEqual(kwargs, expected_kwargs)

    @patch.object(worker, 'pingable')
    @patch.object(worker, 'update_record')
    def test_worker_thread_pingable(self, fake_update_record, fake_pingable):
        """``Worker.run`` updates the IPAM database if the IP is pingable"""
        fake_queue = MagicMock()
        fake_queue.get.return_value = ('myBox', '1.2.3.4')
        fake_logger = MagicMock()
        fake_pingable.return_value = True
        t = worker.Worker(tid=1, logger=fake_logger, work_queue=fake_queue)
        t.start()
        t.keep_running = False
        t.join()

        args, kwargs = fake_update_record.call_args
        expected_args = ('myBox', '1.2.3.4')
        expected_kwargs = {'routable': True}

        self.assertEqual(args, expected_args)
        self.assertEqual(kwargs, expected_kwargs)

    @patch.object(worker, 'pingable')
    @patch.object(worker, 'update_record')
    def test_worker_thread_empty_queue(self, fake_update_record, fake_pingable):
        """``Worker.run`` does not block indefinitely when pulling from the work queue"""
        fake_queue = MagicMock()
        fake_queue.get.side_effect = [worker.queue.Empty('testing') for x in range(500)]
        fake_logger = MagicMock()
        t = worker.Worker(tid=1, logger=fake_logger, work_queue=fake_queue)
        t.start()
        t.keep_running = False
        t.join()

        args, _ = fake_logger.debug.call_args
        message = args[0]
        expected = 'Nothing in queue, looping back'

        self.assertEqual(message, expected)

    @patch.object(worker, 'pingable')
    @patch.object(worker, 'update_record')
    def test_worker_thread_crash(self, fake_update_record, fake_pingable):
        """``Worker.run`` terminates upon error"""
        # NOTE - this test case creates a traceback in the unittest output
        # even though everything works as expected; i.e. a SPAM traceback
        fake_queue = MagicMock()
        fake_queue.get.side_effect = [Exception('SPAM from thread; ignore')]
        fake_logger = MagicMock()

        t = worker.Worker(tid=1, logger=fake_logger, work_queue=fake_queue)
        t.start()
        t.join()

        self.assertFalse(t.keep_running)

    @patch.object(worker.shell, 'run_cmd')
    def test_pingable_true(self, fake_run_cmd):
        """``pingable`` returns True if the target IP can be pinged"""
        ok = worker.pingable('1.2.3.4')

        self.assertTrue(ok)

    @patch.object(worker.shell, 'run_cmd')
    def test_pingable_false(self, fake_run_cmd):
        """``pingable`` returns False if the target IP can be pinged"""
        fake_run_cmd.side_effect = [worker.shell.CliError(command='foo', stdout='testing', stderr='testing', exit_code=1)]
        ok = worker.pingable('1.2.3.4')

        self.assertFalse(ok)

    @patch.object(worker, 'Database')
    def test_update_record_is_routable(self, fake_Database):
        """``update_record`` generates the correct SQL when the target is routable"""
        fake_db = MagicMock()
        fake_Database.return_value.__enter__.return_value = fake_db
        worker.update_record('someBox', '1.2.3.4', True)

        args, kwargs = fake_db.execute.call_args
        sql = args[0]
        expected_sql = "UPDATE ipam SET routable=true WHERE target_name LIKE (%s) and target_addr LIKE (%s);"
        expected_kwargs = {'params': ('someBox', '1.2.3.4')}

        self.assertEqual(sql.lower(), expected_sql.lower())
        self.assertEqual(kwargs, expected_kwargs)

    @patch.object(worker, 'Database')
    def test_update_record_is_not_routable(self, fake_Database):
        """``update_record`` generates the correct SQL when the target is not routable"""
        fake_db = MagicMock()
        fake_Database.return_value.__enter__.return_value = fake_db
        worker.update_record('someBox', '1.2.3.4', False)

        args, kwargs = fake_db.execute.call_args
        sql = args[0]
        expected_sql = "UPDATE ipam SET routable=false WHERE target_name LIKE (%s) and target_addr LIKE (%s);"
        expected_kwargs = {'params': ('someBox', '1.2.3.4')}

        self.assertEqual(sql.lower(), expected_sql.lower())
        self.assertEqual(kwargs, expected_kwargs)

    def test_workers_ok(self):
        """``workers_ok`` returns True if all threads are alive"""
        fake_thread = MagicMock()
        fake_thread.is_alive.return_value = True
        fake_threads = [fake_thread for x in range(10)]

        output = worker.workers_ok(fake_threads)
        expected = True

        self.assertEqual(output, expected)

    def test_workers_ok_false(self):
        """``workers_ok`` returns False if any thread is not alive"""
        fake_thread = MagicMock()
        fake_thread.is_alive.return_value = True
        fake_threads = [fake_thread for x in range(10)]
        fake_threads[3] = fake_thread.is_alive.return_value = False

        output = worker.workers_ok(fake_threads)
        expected = False

        self.assertEqual(output, expected)

    def test_drain_queue(self):
        """``drain_queue`` iterates the work queue until it's completely empty"""
        fake_queue = MagicMock()
        fake_queue.empty.side_effect = [False, False, True]

        worker.drain_queue(fake_queue)

        self.assertEqual(2, fake_queue.get.call_count)

    @patch.object(worker, 'Database')
    def test_do_work(self, fake_Database):
        """``do_work`` returns None upon exit"""
        fake_db = MagicMock()
        fake_db.execute.return_value = [('someBox', '1.2.3.4')]
        fake_Database.return_value.__enter__.return_value = fake_db
        fake_thread = MagicMock()
        fake_thread.is_alive.return_value = False
        fake_threads = [fake_thread]
        fake_logger = MagicMock()
        fake_work_queue = MagicMock()

        output = worker.do_work(worker_threads=fake_threads, work_queue=fake_work_queue, logger=fake_logger)
        expected = None

        self.assertEqual(output, expected)

    @patch.object(worker, 'Database')
    def test_do_work_producer(self, fake_Database):
        """``do_work`` is the producer thread, and puts tasks into the work queue"""
        fake_db = MagicMock()
        fake_db.execute.return_value = [('someBox', '1.2.3.4')]
        fake_Database.return_value.__enter__.return_value = fake_db
        fake_thread = MagicMock()
        fake_thread.is_alive.return_value = False
        fake_threads = [fake_thread]
        fake_logger = MagicMock()
        fake_work_queue = MagicMock()

        worker.do_work(worker_threads=fake_threads, work_queue=fake_work_queue, logger=fake_logger)

        self.assertTrue(fake_work_queue.put.called)

    @patch.object(worker, 'drain_queue')
    @patch.object(worker, 'Database')
    def test_do_work_drains_queue(self, fake_Database, fake_drain_queue):
        """``do_work`` empties any tasks in the queue if a worker crashes"""
        fake_db = MagicMock()
        fake_db.execute.return_value = [('someBox', '1.2.3.4')]
        fake_Database.return_value.__enter__.return_value = fake_db
        fake_thread = MagicMock()
        fake_thread.is_alive.return_value = False
        fake_threads = [fake_thread]
        fake_logger = MagicMock()
        fake_work_queue = MagicMock()

        worker.do_work(worker_threads=fake_threads, work_queue=fake_work_queue, logger=fake_logger)

        self.assertTrue(fake_drain_queue.called)

    @patch.object(worker.time, 'sleep')
    @patch.object(worker, 'drain_queue')
    @patch.object(worker, 'Database')
    def test_do_work_sleeps(self, fake_Database, fake_drain_queue, fake_sleep):
        """``do_work`` sleeps after producing work tasks"""
        fake_db = MagicMock()
        fake_db.execute.return_value = [('someBox', '1.2.3.4')]
        fake_Database.return_value.__enter__.return_value = fake_db
        fake_thread = MagicMock()
        fake_thread.is_alive.side_effect = [True, False]
        fake_threads = [fake_thread]
        fake_logger = MagicMock()
        fake_work_queue = MagicMock()

        worker.do_work(worker_threads=fake_threads, work_queue=fake_work_queue, logger=fake_logger)

        self.assertTrue(fake_sleep.called)



    def test_terminate_workers(self):
        """``terminate_workers`` returns None upon success"""
        fake_thread = MagicMock()
        fake_threads = [fake_thread]

        output = worker.terminate_workers(fake_threads)
        expected = None

        self.assertEqual(output, expected)

    @patch.object(worker, 'Worker')
    def test_make_workers(self, fake_Worker):
        """``make_workers`` creates and starts the worker threads"""
        fake_worker_thread = MagicMock()
        fake_Worker.return_value = fake_worker_thread
        fake_queue = MagicMock()
        fake_logger = MagicMock()

        worker_threads = worker.make_workers(fake_queue, fake_logger)
        started = worker_threads[0].start.called

        self.assertTrue(started)
        self.assertEqual(len(worker_threads), worker.THREAD_COUNT)

    @patch.object(worker, 'do_work')
    @patch.object(worker, 'make_workers')
    @patch.object(worker, 'get_logger')
    def test_main_logger(self, fake_get_logger, fake_make_workers, fake_do_work):
        """``main`` creates the logging object"""
        worker.main()

        self.assertTrue(fake_get_logger.called)


if __name__ == '__main__':
    unittest.main()
