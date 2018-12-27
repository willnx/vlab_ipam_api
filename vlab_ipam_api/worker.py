# -*- coding: UTF-8 -*-
"""Verify that the IP addresses in the IPAM records are ping-able"""
import sys
import time
import queue
import threading

from setproctitle import setproctitle

from vlab_ipam_api.lib import shell, Database, get_logger


LOOP_INTERVAL = 300 # seconds
THREAD_POLL_TIMEOUT = 10 # seconds
THREAD_COUNT = 10
LOG_FILE = '/var/log/vlab_ipam_worker.log'
PING_SYNTAX = '/bin/ping -W 2 -c 3 -4 -I ens192 {}'


class Worker(threading.Thread):
    """Validates that IP records are routable"""
    def __init__(self, tid, logger, work_queue):
        super(Worker, self).__init__()
        self.keep_running = True
        self.tid = tid
        self.work_queue = work_queue
        self.logger = logger

    def run(self):
        """Perform the IP address validation"""
        self.name = 'IPAM-worker-thread-{}'.format(self.tid)
        self.logger.info('{} started'.format(self.name))
        while self.keep_running:
            try:
                task = self.work_queue.get(timeout=THREAD_POLL_TIMEOUT)
                owner, addr = task
                self.logger.info('{}: Checking IP {} belonging to {}'.format(self.name, addr, owner))
                if not pingable(addr):
                    update_record(owner, addr, routable=False)
                    self.logger.info('{}: IP {} owned by {} not pingable'.format(self.name, addr, owner))
                else:
                    update_record(owner, addr, routable=True)
            except queue.Empty:
                # timeout so we can terminate if needed
                # without the timeout, we'll be stuck in this while loop forever
                self.logger.debug('Nothing in queue, looping back')
            except Exception as doh:
                self.keep_running = False
                self.logger.error('{} crashing'.format(self.name))
                self.logger.exception(doh)
                raise doh


def pingable(addr):
    """Issue a ping command to check if the target address is routable.

    :Returns: Boolean

    :param addr: The IPv4 address that is not ping-able
    :type addr: String
    """
    try:
        shell.run_cmd(PING_SYNTAX.format(addr))
    except shell.CliError:
        ok = False
    else:
        ok = True
    return ok


def update_record(owner, addr, routable):
    """Update the IPAM database to reflect the ability to route to the supplied IP

    :Returns: Boolean

    :param owner: The vLab componet that owns a given IP
    :type owner: String

    :param addr: The IPv4 address that is not ping-able
    :type addr: String

    :param routable: Set to True if the IP can be pinged
    :type routable: Boolean
    """
    sql = "UPDATE ipam SET routable={} WHERE target_name LIKE (%s) and target_addr LIKE (%s);".format(routable).lower()
    with Database() as db:
        db.execute(sql, params=(owner, addr))


def workers_ok(worker_threads):
    """If any worker is not alive, return False

    :Returns: Boolean

    :param worker_threads: A list of threading.Thread objects
    :type worker_threads: List
    """
    for worker_thread in worker_threads:
        if not worker_thread.is_alive():
            return False
    else:
        return True


def drain_queue(work_queue):
    """Must empty the queue in order for proper process termination

    :Returns: None

    :param work_queue: How the worker threads pull tasks from the producer thread.
    :type work_queue: queue.Queue
    """
    while not work_queue.empty():
        work_queue.get()


def do_work(worker_threads, work_queue, logger):
    """Produce tasks and add it to worker's Queue on a regular interval.

    When/if this function terminates, the entire program must terminate.

    :Returns: None

    :param worker_threads: A list of threading.Thread objects
    :type worker_threads: List

    :param work_queue: How the worker threads pull tasks from the producer thread.
    :type work_queue: queue.Queue

    :param logger: An object for logging events.
    :type logger: logging.Logger
    """
    keep_running = True
    while keep_running:
        start_time = time.time()
        logger.info('Looking up IP records')
        with Database() as db:
            records = db.execute("SELECT DISTINCT target_name, target_addr FROM ipam;")
            logger.info('Found {} IP records to check'.format(len(records)))
            for record in records:
                work_queue.put(record)

        if not workers_ok(worker_threads):
            logger.error('Worker failure detected. Draining work queue in order to terminate')
            drain_queue(work_queue)
            keep_running = False
            break

        interval_delta = max(0, LOOP_INTERVAL - (time.time() - start_time))
        time.sleep(interval_delta)
    logger.error('Terminating remaining worker threads')
    terminate_workers(worker_threads)


def terminate_workers(worker_threads):
    """Must terminate workers before main exits

    :Returns: None

    :param worker_threads: A list of threading.Thread objects
    :type worker_threads: List
    """
    # Iterating twice is faster because we wont have to wait for
    # THREAD_POLL_TIMEOUT in every thread
    for worker_thread in worker_threads:
        worker_thread.keep_running = False
    for worker_thread in worker_threads:
        worker_thread.join(timeout=THREAD_POLL_TIMEOUT * 2)


def make_workers(work_queue, logger):
    """Create all the worker threads that perform the literal address checking

    :Returns: List

    :param work_queue: How the worker threads pull tasks from the producer thread.
    :type work_queue: queue.Queue
    """
    worker_threads = []
    for thread_id in range(THREAD_COUNT):
        t = Worker(tid=thread_id, logger=logger, work_queue=work_queue)
        t.start()
        worker_threads.append(t)
    return worker_threads


def main():
    """Entry point logic for validating IP records"""
    work_queue = queue.Queue()
    logger = get_logger(name=__name__, log_file=LOG_FILE)
    logger.info('IPAM Address Probe Starting')
    logger.info('Starting {} worker threads'.format(THREAD_COUNT))
    worker_threads = make_workers(work_queue, logger)
    logger.info('Processing IP address records')
    # do_work blocks
    do_work(worker_threads, work_queue, logger)
    logger.info('IPAM Addres Probe terminating')


if __name__ == '__main__':
    setproctitle('IPAM-worker')
    main()
