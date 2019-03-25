# -*- coding: utf-8 -*-
#
# test_event.py
# Guillaume Smaha, 2018-05-01
# Copyright (c) 2018 ElementAI. All rights reserved.
#

from __future__ import absolute_import

from tests import BaseTestCase
from borgy_process_agent.event import Observable, Event, CallbackOrder


class TestEvent(BaseTestCase):
    """Event integration test"""

    def test_subscribe_uncallable(self):
        """Test case for excpetion when callback is not callable
        """
        obs = Observable()

        callback = "mycallback"
        self.assertRaises(TypeError, obs.subscribe, [callback])

        cbs = obs.get_callbacks()
        self.assertEqual(len(cbs), 0)

    def test_get_subscribe_returned_name(self):
        """Test case to get callbacks
        """
        obs = Observable()

        def callback(event):
            pass
        name = obs.subscribe(callback)

        cbs = obs.get_callbacks()
        self.assertEqual(len(cbs), 1)
        self.assertEqual(cbs[0]['callback'], callback)
        self.assertEqual(cbs[0]['name'], name)

    def test_get_callblacks(self):
        """Test case to get callbacks
        """
        obs = Observable()

        def callback(event):
            pass
        obs.subscribe(callback)

        cbs = obs.get_callbacks()
        self.assertEqual(len(cbs), 1)
        self.assertEqual(cbs[0]['callback'], callback)

    def test_get_callblacks_with_name(self):
        """Test case to get callbacks by name
        """
        obs = Observable()

        def callback(event):
            pass
        obs.subscribe(callback, 'my-callback')

        cbs = obs.get_callbacks()
        self.assertEqual(len(cbs), 1)
        self.assertEqual(cbs[0]['callback'], callback)
        self.assertEqual(cbs[0]['name'], 'my-callback')

        cbs = obs.get_callbacks_by_name('my-callback')
        self.assertEqual(len(cbs), 1)
        self.assertEqual(cbs[0]['callback'], callback)
        self.assertEqual(cbs[0]['name'], 'my-callback')

    def test_get_callblacks_multiple_with_name(self):
        """Test case to get multiple callbacks by name
        """
        obs = Observable()

        def callback(event):
            pass

        def callback2(event):
            pass
        obs.subscribe(callback, 'my-callback')
        obs.subscribe(callback2, 'my-callback')

        cbs = obs.get_callbacks()
        self.assertEqual(len(cbs), 2)
        self.assertEqual(cbs[0]['callback'], callback)
        self.assertEqual(cbs[0]['name'], 'my-callback')
        self.assertEqual(cbs[1]['callback'], callback2)
        self.assertEqual(cbs[1]['name'], 'my-callback')

        cbs = obs.get_callbacks_by_name('my-callback')
        self.assertEqual(len(cbs), 2)
        self.assertEqual(cbs[0]['callback'], callback)
        self.assertEqual(cbs[0]['name'], 'my-callback')
        self.assertEqual(cbs[1]['callback'], callback2)
        self.assertEqual(cbs[1]['name'], 'my-callback')

    def test_unsubscribe_without_parameter(self):
        """Test case for excpetion when callback is not callable
        """
        obs = Observable()

        def callback(event):
            pass
        obs.subscribe(callback, 'my-callback')

        self.assertRaises(TypeError, obs.unsubscribe)

        cbs = obs.get_callbacks()
        self.assertEqual(len(cbs), 1)

    def test_unsubscribe_by_function(self):
        """Test case to unsubscribe by function
        """
        obs = Observable()
        # Use list to be able to modify the value in the callback
        called = [False, False]

        def callback(event):
            called[0] = True

        def callback2(event):
            called[1] = True
        obs.subscribe(callback)
        obs.subscribe(callback2)

        cbs = obs.get_callbacks()
        self.assertEqual(len(cbs), 2)

        removed = obs.unsubscribe(callback)
        self.assertEqual(len(removed), 1)
        self.assertEqual(removed[0]['callback'], callback)

        removed = obs.unsubscribe(callback=callback2)
        self.assertEqual(len(removed), 1)
        self.assertEqual(removed[0]['callback'], callback2)

        cbs = obs.get_callbacks()
        self.assertEqual(len(cbs), 0)

        obs.dispatch(test=True)
        self.assertFalse(called[0])
        self.assertFalse(called[1])

    def test_unsubscribe_multiple_by_function(self):
        """Test case to unsubscribe multiple callbacks by function
        """
        obs = Observable()
        # Use list to be able to modify the value in the callback
        called = [0, 0]

        def callback(event):
            called[0] += 1

        def callback2(event):
            called[1] += 1
        obs.subscribe(callback)
        obs.subscribe(callback)
        obs.subscribe(callback2)
        obs.subscribe(callback2)

        cbs = obs.get_callbacks()
        self.assertEqual(len(cbs), 4)

        removed = obs.unsubscribe(callback)
        self.assertEqual(len(removed), 2)
        self.assertEqual(removed[0]['callback'], callback)
        self.assertEqual(removed[1]['callback'], callback)

        removed = obs.unsubscribe(callback=callback2)
        self.assertEqual(len(removed), 2)
        self.assertEqual(removed[0]['callback'], callback2)
        self.assertEqual(removed[1]['callback'], callback2)

        cbs = obs.get_callbacks()
        self.assertEqual(len(cbs), 0)

        obs.dispatch(test=True)
        self.assertEqual(called[0], 0)
        self.assertEqual(called[1], 0)

    def test_unsubscribe_by_name(self):
        """Test case to unsubscribe by name
        """
        obs = Observable()
        # Use list to be able to modify the value in the callback
        called = [False]

        def callback(event):
            called[0] = True
        obs.subscribe(callback, 'my-callback')

        cbs = obs.get_callbacks()
        self.assertEqual(len(cbs), 1)

        removed = obs.unsubscribe(name='my-callback')
        self.assertEqual(len(removed), 1)
        self.assertEqual(removed[0]['callback'], callback)
        self.assertEqual(removed[0]['name'], 'my-callback')

        cbs = obs.get_callbacks()
        self.assertEqual(len(cbs), 0)

        obs.dispatch(test=True)
        self.assertFalse(called[0])

    def test_unsubscribe_multiple_by_name(self):
        """Test case to unsubscribe multiple callbacks by name
        """
        obs = Observable()
        # Use list to be able to modify the value in the callback
        called = [False, False]

        def callback(event):
            called[0] = True

        def callback2(event):
            called[1] = True
        obs.subscribe(callback, 'my-callback')
        obs.subscribe(callback2, 'my-callback')

        cbs = obs.get_callbacks()
        self.assertEqual(len(cbs), 2)

        removed = obs.unsubscribe(name='my-callback')
        self.assertEqual(len(removed), 2)
        self.assertEqual(removed[0]['callback'], callback)
        self.assertEqual(removed[0]['name'], 'my-callback')
        self.assertEqual(removed[1]['callback'], callback2)
        self.assertEqual(removed[1]['name'], 'my-callback')

        cbs = obs.get_callbacks()
        self.assertEqual(len(cbs), 0)

        obs.dispatch(test=True)
        self.assertFalse(called[0])
        self.assertFalse(called[1])

    def test_unsubscribe_by_function_and_name(self):
        """Test case to unsubscribe multiple callbacks by name
        """
        obs = Observable()
        # Use list to be able to modify the value in the callback
        called = [0, 0]

        def callback(event):
            called[0] += 1

        def callback2(event):
            called[1] += 1
        obs.subscribe(callback, 'my-callback1')
        obs.subscribe(callback2, 'my-callback1')
        obs.subscribe(callback, 'my-callback2')
        obs.subscribe(callback2, 'my-callback2')

        cbs = obs.get_callbacks()
        self.assertEqual(len(cbs), 4)

        removed = obs.unsubscribe(callback=callback, name='my-callback1')
        self.assertEqual(len(removed), 1)
        self.assertEqual(removed[0]['callback'], callback)
        self.assertEqual(removed[0]['name'], 'my-callback1')

        cbs = obs.get_callbacks()
        self.assertEqual(len(cbs), 3)

        obs.dispatch(test=True)
        self.assertEqual(called, [1, 2])

    def test_dispatch_called(self):
        """Test case to check if callback is called on dispatch
        """
        obs = Observable()
        # Use list to be able to modify the value in the callback
        called = [False]

        def callback(event):
            called[0] = True
        obs.subscribe(callback)

        obs.dispatch(test=True)
        self.assertTrue(called[0])

    def test_dispatch_event_type(self):
        """Test case for event type returned in callback
        """
        obs = Observable()

        def callback(event):
            self.assertIsInstance(event, Event)
        obs.subscribe(callback)

        obs.dispatch()

    def test_dispatch_value(self):
        """Test case for dispatch value
        """
        obs = Observable()

        def callback(event):
            self.assertEqual(event.test, True)
            self.assertEqual(event.my_value, 100)
        obs.subscribe(callback)

        obs.dispatch(test=True, my_value=100)

    def test_dispatch_value_like_dict(self):
        """Test case for dispatch value like dict
        """
        obs = Observable()

        def callback(event):
            self.assertEqual(event['test'], True)
            self.assertEqual(event['my_value'], 100)
        obs.subscribe(callback)

        obs.dispatch(test=True, my_value=100)

    def test_dispatch_source(self):
        """Test case for dispatch observable source
        """
        obs = Observable()

        def callback(event):
            self.assertEqual(event.source, obs)
        obs.subscribe(callback)

        obs.dispatch()

    def test_dispatch_source_overwrite(self):
        """Test case when source is overwrite on dispatch
        """
        obs = Observable()

        def callback(event):
            self.assertNotEqual(event.source, obs)
            self.assertEqual(event.source, 1000)
        obs.subscribe(callback)

        obs.dispatch(source=1000)

    def test_dispatch_get_result(self):
        """Test case for results returned by dispatch
        """
        obs = Observable()
        called = [0, 0, 0]

        def callback(event):
            called[0] += 1
            return "MyResult"

        def callback2(event):
            called[1] += 1
            pass

        def callback3(event):
            called[2] += 1
            return event.test
        obs.subscribe(callback)
        obs.subscribe(callback2)
        obs.subscribe(callback3)

        results = obs.dispatch(test=True)
        self.assertEqual(called, [1, 1, 1])
        self.assertEqual(results, ["MyResult", None, True])

        results = obs.dispatch(test=2212)
        self.assertEqual(called, [2, 2, 2])
        self.assertEqual(results, ["MyResult", None, 2212])

    def test_dispatch_breakable(self):
        """Test case for dispatch_breakable
        """
        obs = Observable()
        called = [0, 0, 0]

        def callback(event):
            called[0] += 1
            return "MyResult"

        def callback2(event):
            called[1] += 1
            return True

        def callback3(event):
            called[2] += 1
            return event.test
        obs.subscribe(callback)
        obs.subscribe(callback2)
        obs.subscribe(callback3)

        results = obs.dispatch_breakable(test=True)
        self.assertEqual(called, [1, 1, 1])
        self.assertEqual(results, ["MyResult", True, True])

        results = obs.dispatch_breakable(test=2212)
        self.assertEqual(called, [2, 2, 2])
        self.assertEqual(results, ["MyResult", True, 2212])

    def test_dispatch_breakable_stop_dispatch(self):
        """Test case for dispatch_breakable: stop dispatch when return None in callback
        """
        obs = Observable()
        called = [0, 0, 0]

        def callback(event):
            called[0] += 1
            return "MyResult"

        def callback2(event):
            called[1] += 1
            # return None

        def callback3(event):
            called[2] += 1
            return event.test
        obs.subscribe(callback)
        obs.subscribe(callback2)
        obs.subscribe(callback3)

        results = obs.dispatch_breakable(test=True)
        self.assertEqual(called, [1, 1, 0])
        self.assertEqual(results, ["MyResult", None])

        results = obs.dispatch_breakable(test=2212)
        self.assertEqual(called, [2, 2, 0])
        self.assertEqual(results, ["MyResult", None])

    def test_dispatch_breakable_inject_callback_dict(self):
        """Test case for dispatch_breakable
        Pass values between callbacks with dict or Event
        """
        obs = Observable()
        called = [0, 0, 0, 0]

        def callback(event):
            self.assertIn('test', event)
            self.assertIn('abc', event)
            called[0] += 1
            return {'my-result': 88}

        def callback2(event):
            self.assertIn('my-result', event)
            self.assertEqual(event['my-result'], 88)
            event.inject = 11
            event['inject2'] = 22
            del event['abc']
            called[1] += 1
            return event

        def callback3(event):
            self.assertIn('my-result', event)
            self.assertEqual(event['my-result'], 88)
            self.assertIn('inject', event)
            self.assertEqual(event.inject, 11)
            self.assertEqual(event['inject'], 11)
            self.assertIn('inject2', event)
            self.assertEqual(event.inject2, 22)
            self.assertEqual(event['inject2'], 22)
            called[2] += 1
            return None

        def callback4(event):
            called[3] += 1
            return event.test
        obs.subscribe(callback)
        obs.subscribe(callback2)
        obs.subscribe(callback3)
        obs.subscribe(callback4)

        results = obs.dispatch_breakable(test=True, abc="def")
        self.assertEqual(called, [1, 1, 1, 0])
        self.assertEqual(len(results), 3)
        self.assertEqual(results[0], {'my-result': 88})
        self.assertIsInstance(results[1], Event)
        self.assertEqual(results[1].to_dict(), {
            'source': obs,
            'test': True,
            'my-result': 88,
            'inject': 11,
            'inject2': 22
        })
        self.assertIsNone(results[2])

        results = obs.dispatch_breakable(test=2212, abc="def")
        self.assertEqual(called, [2, 2, 2, 0])
        self.assertEqual(len(results), 3)
        self.assertEqual(results[0], {'my-result': 88})
        self.assertIsInstance(results[1], Event)
        self.assertEqual(results[1].to_dict(), {
            'source': obs,
            'test': 2212,
            'my-result': 88,
            'inject': 11,
            'inject2': 22
        })
        self.assertIsNone(results[2])

    def test_dispatch_order(self):
        """Test case for results returned by dispatch
        """
        obs = Observable()

        called = []

        def callback(i):
            def callback_fct(event):
                while len(called) <= i:
                    called.append(0)
                called[i] += 1
                return i
            return callback_fct

        obs.subscribe(callback(0), order=CallbackOrder.End)
        obs.subscribe(callback(1), order=CallbackOrder.Begin)
        c2 = callback(2)
        obs.subscribe(c2)

        results = obs.dispatch()
        self.assertEqual(called, [1, 1, 1])
        self.assertEqual(results, [1, 2, 0])

        called = []
        obs.subscribe(callback(3))
        results = obs.dispatch()
        self.assertEqual(called, [1, 1, 1, 1])
        self.assertEqual(results, [1, 2, 3, 0])

        called = []
        obs.subscribe(callback(4), order=CallbackOrder.Begin)
        results = obs.dispatch()
        self.assertEqual(called, [1, 1, 1, 1, 1])
        self.assertEqual(results, [1, 4, 2, 3, 0])

        called = []
        obs.unsubscribe(c2)
        results = obs.dispatch()
        self.assertEqual(called, [1, 1, 0, 1, 1])
        self.assertEqual(results, [1, 4, 3, 0])


if __name__ == '__main__':
    import unittest
    unittest.main()
