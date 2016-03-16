from unittest import TestCase
from stream import Stream


class TestStream(TestCase):
    def test_consume(self):
        stream = Stream()

        # test consume without filter
        stream.queue.put(1)
        stream.queue.put(2)
        self.assertEqual(stream.consume(), 1)
        self.assertEqual(stream.consume(), 2)

        # test consume with filter
        stream.queue.put(1)
        stream.queue.put(2)
        stream.queue.put(3)

        self.assertEqual(stream.consume(lambda data: data == 2), 2)
        self.assertEqual(stream.consume(), 3)

    def test_produce(self):
        test = []

        def test_produce_cb(stream, data):
            test.append(data)

        stream = Stream()
        stream.produce_cb = test_produce_cb
        stream.produce("test")
        self.assertEqual(test, ["test"])