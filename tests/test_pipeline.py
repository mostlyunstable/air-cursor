"""
Unit tests for Air Cursor Action Pipeline and ActionQueue.
Runs standalone without requiring an active Blender process.
"""

import unittest
import threading
import time
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from air_cursor.pipeline import Action, ActionQueue, resolve_target


class TestPipeline(unittest.TestCase):

    def test_action_initialization(self):
        """Action fields and default types must initialize properly."""
        act = Action(target=(300, 400), action_type="CLICK", action_text="Test Click")
        self.assertEqual(act.action_type, "CLICK")
        self.assertTrue(act.click)
        self.assertFalse(act.hover)
        self.assertFalse(act.drag)
        self.assertEqual(act.status, "PENDING")
        self.assertEqual(act.action_text, "Test Click")

    def test_action_execution_success(self):
        """Action operator_func must execute and record result and completion timestamp."""
        executed = []
        def my_op():
            executed.append("done")
            return 42

        act = Action(target=(100, 200), operator_func=my_op)
        res = act.execute()
        self.assertEqual(res, 42)
        self.assertEqual(act.result, 42)
        self.assertEqual(act.status, "COMPLETED")
        self.assertIsNotNone(act.completed_at)
        self.assertEqual(executed, ["done"])

    def test_action_execution_error(self):
        """Action must catch operator exceptions and set status to FAILED."""
        def bad_op():
            raise ValueError("Blender context invalid")

        act = Action(target=(100, 200), operator_func=bad_op)
        res = act.execute()
        self.assertIsNone(res)
        self.assertEqual(act.status, "FAILED")
        self.assertIn("Blender context invalid", act.error)

    def test_action_queue_fifo(self):
        """ActionQueue must maintain strict FIFO ordering."""
        q = ActionQueue()
        self.assertTrue(q.is_empty())
        self.assertEqual(q.size(), 0)

        a1 = Action(target=(10, 10), action_text="First")
        a2 = Action(target=(20, 20), action_text="Second")
        a3 = Action(target=(30, 30), action_text="Third")

        q.enqueue(a1)
        q.enqueue(a2)
        q.enqueue(a3)

        self.assertEqual(q.size(), 3)
        self.assertFalse(q.is_empty())

        self.assertEqual(q.dequeue().action_text, "First")
        self.assertEqual(q.dequeue().action_text, "Second")
        self.assertEqual(q.dequeue().action_text, "Third")
        self.assertIsNone(q.dequeue())
        self.assertTrue(q.is_empty())

    def test_action_queue_thread_safety(self):
        """ActionQueue must handle high-concurrency multi-threaded enqueues."""
        q = ActionQueue()
        total_items = 500
        threads = 10
        items_per_thread = total_items // threads

        def worker(thread_idx):
            for i in range(items_per_thread):
                act = Action(target=(thread_idx, i), action_text=f"T{thread_idx}_{i}")
                q.enqueue(act)

        worker_threads = [threading.Thread(target=worker, args=(t,)) for t in range(threads)]
        for t in worker_threads:
            t.start()
        for t in worker_threads:
            t.join()

        self.assertEqual(q.size(), total_items)
        popped_count = 0
        while q.dequeue() is not None:
            popped_count += 1
        self.assertEqual(popped_count, total_items)

    def test_resolve_target_numeric(self):
        """Numeric coordinates must resolve directly to float pairs."""
        x, y = resolve_target((640, 480))
        self.assertAlmostEqual(x, 640.0)
        self.assertAlmostEqual(y, 480.0)


if __name__ == '__main__':
    unittest.main()
