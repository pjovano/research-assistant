from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

from _port_fakes import FakeScheduler
from _ports.host import Job, Scheduler

JOB = Job("local.example.sample", ("true",), interval_seconds=60)


class SchedulerContract:
    def scheduler(self) -> Scheduler:
        raise NotImplementedError

    def test_an_installed_job_reads_as_installed(self) -> None:
        scheduler = self.scheduler()
        scheduler.install(JOB)
        self.assertTrue(scheduler.installed(JOB))

    def test_a_job_never_installed_reads_as_not_installed(self) -> None:
        self.assertFalse(self.scheduler().installed(JOB))

    def test_a_removed_job_reads_as_not_installed(self) -> None:
        scheduler = self.scheduler()
        scheduler.install(JOB)
        scheduler.remove(JOB)
        self.assertFalse(scheduler.installed(JOB))

    def test_installing_twice_leaves_one_job_that_one_removal_removes(self) -> None:
        scheduler = self.scheduler()
        scheduler.install(JOB)
        scheduler.install(JOB)
        scheduler.remove(JOB)
        self.assertFalse(scheduler.installed(JOB))

    def test_removing_a_job_never_installed_is_harmless(self) -> None:
        scheduler = self.scheduler()
        scheduler.remove(JOB)
        self.assertFalse(scheduler.installed(JOB))


class TestFakeSchedulerKeepsTheContract(SchedulerContract, unittest.TestCase):
    def scheduler(self) -> Scheduler:
        return FakeScheduler()


if __name__ == "__main__":
    unittest.main()
