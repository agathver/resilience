from resilience.utils import RingBuffer


def test_ring_buffer_keeps_last_n_contents():
    ring_buffer_size = 3

    ring_buffer = RingBuffer(ring_buffer_size)

    ring_buffer.add(1)
    ring_buffer.add(2)
    ring_buffer.add(3)
    ring_buffer.add(4)

    assert [2, 3, 4] == list(ring_buffer)


def test_ring_buffer_clear_clears_the_ring_buffer():
    ring_buffer_size = 3

    ring_buffer = RingBuffer(ring_buffer_size)

    ring_buffer.add(1)
    ring_buffer.add(2)
    ring_buffer.add(3)
    ring_buffer.add(4)

    ring_buffer.clear()

    assert [] == list(ring_buffer)
