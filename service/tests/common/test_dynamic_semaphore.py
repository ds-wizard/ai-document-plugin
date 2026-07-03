"""Tests for DynamicSemaphore.

These tests drive the event loop directly with ``asyncio.run`` so they need no
pytest-asyncio / anyio plugin. Several tests deliberately exercise cancellation
races to probe the bookkeeping of ``_active_count``.
"""

import asyncio
import threading

import pytest

from ai_document_plugin_service.ai.common.dynamic_semaphore import DynamicSemaphore


def run(coro):
    """Run a coroutine on a fresh event loop."""
    return asyncio.run(coro)


# --------------------------------------------------------------------------- #
# Construction / validation
# --------------------------------------------------------------------------- #


def test_negative_initial_limit_raises():
    with pytest.raises(ValueError):
        DynamicSemaphore(-1)


def test_zero_initial_limit_allowed():
    sem = DynamicSemaphore(0)
    assert sem.limit == 0


def test_set_negative_limit_raises():
    sem = DynamicSemaphore(1)
    with pytest.raises(ValueError):
        sem.set_limit(-1)


# --------------------------------------------------------------------------- #
# Basic acquire / release
# --------------------------------------------------------------------------- #


def test_acquire_release_single():
    async def main():
        sem = DynamicSemaphore(1)
        await sem.acquire()
        assert sem._active_count == 1
        await sem.release()
        assert sem._active_count == 0

    run(main())


def test_context_manager():
    async def main():
        sem = DynamicSemaphore(1)
        async with sem:
            assert sem._active_count == 1
        assert sem._active_count == 0

    run(main())


def test_release_too_many_raises():
    async def main():
        sem = DynamicSemaphore(1)
        with pytest.raises(ValueError):
            await sem.release()

    run(main())


def test_acquire_blocks_when_full_then_released():
    async def main():
        sem = DynamicSemaphore(1)
        await sem.acquire()

        order = []

        async def waiter():
            await sem.acquire()
            order.append("got it")

        task = asyncio.create_task(waiter())
        await asyncio.sleep(0)  # let the waiter enqueue
        assert order == []  # still blocked

        await sem.release()
        await asyncio.wait_for(task, timeout=1)
        assert order == ["got it"]

    run(main())


def test_limit_zero_blocks_everything():
    async def main():
        sem = DynamicSemaphore(0)
        task = asyncio.create_task(sem.acquire())
        await asyncio.sleep(0)
        assert not task.done()
        # raising the limit should let it through
        sem.set_limit(1)
        await asyncio.wait_for(task, timeout=1)

    run(main())


def test_concurrency_never_exceeds_limit():
    async def main():
        sem = DynamicSemaphore(3)
        active = 0
        max_seen = 0

        async def worker():
            nonlocal active, max_seen
            async with sem:
                active += 1
                max_seen = max(max_seen, active)
                await asyncio.sleep(0.01)
                active -= 1

        await asyncio.gather(*(worker() for _ in range(20)))
        assert max_seen <= 3
        assert sem._active_count == 0
        assert len(sem._waiters) == 0

    run(main())


# --------------------------------------------------------------------------- #
# Dynamic limit changes
# --------------------------------------------------------------------------- #


def test_raising_limit_wakes_multiple_waiters():
    async def main():
        sem = DynamicSemaphore(1)
        await sem.acquire()

        tasks = [asyncio.create_task(sem.acquire()) for _ in range(3)]
        await asyncio.sleep(0)
        assert all(not t.done() for t in tasks)

        sem.set_limit(4)  # 1 active + 3 waiters == 4
        await asyncio.wait_for(asyncio.gather(*tasks), timeout=1)
        assert sem._active_count == 4

    run(main())


def test_lowering_limit_does_not_break_active_holders():
    async def main():
        sem = DynamicSemaphore(3)
        await sem.acquire()
        await sem.acquire()
        await sem.acquire()
        assert sem._active_count == 3

        sem.set_limit(1)  # below current active count

        # new acquire must block
        task = asyncio.create_task(sem.acquire())
        await asyncio.sleep(0)
        assert not task.done()

        # releasing brings count down but still above limit, stays blocked
        await sem.release()  # 2
        await asyncio.sleep(0)
        assert not task.done()
        await sem.release()  # 1
        await asyncio.sleep(0)
        assert not task.done()
        await sem.release()  # 0 -> waiter wakes
        await asyncio.wait_for(task, timeout=1)
        assert sem._active_count == 1

    run(main())


# --------------------------------------------------------------------------- #
# Cancellation
# --------------------------------------------------------------------------- #


def test_cancel_while_waiting_removes_waiter():
    async def main():
        sem = DynamicSemaphore(1)
        await sem.acquire()

        task = asyncio.create_task(sem.acquire())
        await asyncio.sleep(0)
        assert len(sem._waiters) == 1

        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert len(sem._waiters) == 0

        # the slot is still available for a fresh waiter
        await sem.release()
        await asyncio.wait_for(sem.acquire(), timeout=1)

    run(main())


def test_cancel_one_of_many_waiters_leaves_others_working():
    async def main():
        sem = DynamicSemaphore(1)
        await sem.acquire()

        t1 = asyncio.create_task(sem.acquire())
        t2 = asyncio.create_task(sem.acquire())
        await asyncio.sleep(0)

        t1.cancel()
        with pytest.raises(asyncio.CancelledError):
            await t1

        await sem.release()
        await asyncio.wait_for(t2, timeout=1)
        assert sem._active_count == 1

    run(main())


# --------------------------------------------------------------------------- #
# Cancellation races against waking — these probe _active_count bookkeeping.
# --------------------------------------------------------------------------- #


def test_cancel_after_being_woken_does_not_leak_slot():
    """A waiter that is granted the slot and then cancelled must give it back.

    The except-handler in ``acquire`` is supposed to detect that the future was
    resolved (woken) before cancellation took effect, and decrement the count.
    """

    async def main():
        sem = DynamicSemaphore(1)
        await sem.acquire()

        task = asyncio.create_task(sem.acquire())
        await asyncio.sleep(0)  # task enqueued

        # Release: this wakes `task` via call_soon_threadsafe(set_result).
        # The set_result callback is now scheduled but task hasn't resumed.
        await sem.release()

        # Cancel before the woken task gets a chance to run.
        task.cancel()

        # task was woken (got the slot) but cancelled -> should release it back.
        try:
            await task
        except asyncio.CancelledError:
            pass

        # Whether cancellation won or the slot was kept, a fresh acquire must
        # eventually succeed and count must not be leaked above the limit.
        await asyncio.wait_for(sem.acquire(), timeout=1)
        assert sem._active_count <= sem.limit

    run(main())


def test_cancelled_waiter_processed_by_wake_does_not_leak_slot():
    """Reproduce a wake/cancel race that can permanently leak a slot.

    Cancelling a task synchronously cancels the future it is awaiting, but the
    task's except-handler only runs when the task next resumes. If a release()
    (or set_limit) runs ``_wake_waiters`` in that window, the still-queued but
    already-cancelled waiter is popped, ``_active_count`` is incremented, and the
    grant is skipped -- leaking a slot that nobody holds.
    """

    async def main():
        sem = DynamicSemaphore(1)
        await sem.acquire()  # active_count = 1, at limit

        task = asyncio.create_task(sem.acquire())
        await asyncio.sleep(0)  # task is now an enqueued waiter
        assert len(sem._waiters) == 1

        # Cancel synchronously cancels the awaited future, but does NOT yet run
        # the task's except handler (task hasn't resumed).
        task.cancel()
        assert len(sem._waiters) == 1  # still queued

        # Release now. _wake_waiters pops the cancelled waiter, bumps
        # _active_count to account for a holder that will never exist.
        await sem.release()

        with pytest.raises(asyncio.CancelledError):
            await task

        # Semaphore should be fully free now: nobody holds a slot.
        assert sem._active_count == 0, (
            f"leaked slot: _active_count={sem._active_count} but no holders"
        )

        # And a fresh acquire must succeed without blocking.
        await asyncio.wait_for(sem.acquire(), timeout=1)

    run(main())


# --------------------------------------------------------------------------- #
# Single-loop binding — using a bound semaphore from another loop is rejected.
# --------------------------------------------------------------------------- #


def test_rejects_use_from_a_second_loop():
    sem = DynamicSemaphore(1)

    # Bind it to a first loop.
    run(sem.acquire())

    # A second, distinct loop must be refused rather than silently corrupting
    # cross-loop futures.
    with pytest.raises(RuntimeError):
        run(sem.acquire())


def test_reused_on_same_loop_is_fine():
    async def main():
        sem = DynamicSemaphore(2)
        await sem.acquire()
        await sem.acquire()
        await sem.release()
        await sem.acquire()
        assert sem._active_count == 2

    run(main())
