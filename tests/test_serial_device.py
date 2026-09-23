from hmi.device.messages import Fault, Heartbeat, Sample
from hmi.device.protocol import encode_fault, encode_heartbeat, encode_sample
from hmi.device.serial_device import SerialDevice
from hmi.model.settings import VentSettings


class FakeSerial:
    def __init__(self):
        self.incoming = b""
        self.written = []

    @property
    def in_waiting(self):
        return len(self.incoming)

    def read(self, n):
        data, self.incoming = self.incoming[:n], self.incoming[n:]
        return data

    def write(self, data):
        self.written.append(data.decode("ascii"))

    def close(self):
        pass


def make(qapp, clock_value):
    fake = FakeSerial()
    dev = SerialDevice("TEST", serial_factory=lambda: fake, clock=lambda: clock_value[0])
    dev.open()
    return dev, fake


def test_parses_samples_and_faults(qapp):
    now = [0.0]
    dev, fake = make(qapp, now)
    samples, faults = [], []
    dev.sample_received.connect(samples.append)
    dev.fault_changed.connect(lambda code, active: faults.append((code, active)))
    fake.incoming = (encode_sample(Sample(20, 5.0, 30.0, 10.0, "I")) + encode_fault(Fault("FLOW_SENSOR", True))).encode()
    dev.poll()
    assert samples == [Sample(20, 5.0, 30.0, 10.0, "I")]
    assert faults == [("FLOW_SENSOR", True)]
    dev.close()


def test_bad_lines_are_counted_not_raised(qapp):
    now = [0.0]
    dev, fake = make(qapp, now)
    fake.incoming = b"garbage\n$H,1*00\n"
    dev.poll()
    assert dev.bad_lines == 2
    dev.close()


def test_link_goes_up_on_heartbeat_and_down_after_timeout(qapp):
    now = [0.0]
    dev, fake = make(qapp, now)
    links = []
    dev.link_changed.connect(links.append)
    fake.incoming = encode_heartbeat(1).encode()
    dev.poll()
    assert links == [True]
    now[0] = 1.5
    dev.heartbeat()
    assert links == [True, False]
    assert fake.written[-1].startswith("$H,")
    dev.close()


def test_settings_are_written_as_protocol_lines(qapp):
    now = [0.0]
    dev, fake = make(qapp, now)
    dev.apply_settings(VentSettings(), 40)
    assert len(fake.written) == 9 and fake.written[0].startswith("$S,MODE,VC*")
    dev.close()


def test_serial_read_failure_closes_port_and_reports_link_lost(qapp):
    now = [0.0]

    class FailingSerial(FakeSerial):
        def read(self, n):
            raise OSError("USB unplugged")

    dev = SerialDevice("TEST", serial_factory=lambda: FailingSerial(), clock=lambda: now[0])
    dev.open()
    links = []
    dev.link_changed.connect(links.append)
    # Set incoming data so in_waiting > 0 and read() gets called
    dev._serial.incoming = b"x"
    dev.poll()
    assert links == [False]
    assert dev._serial is None
    # Second poll should not raise and should not emit again
    dev.poll()
    assert links == [False]
    dev.close()


def test_serial_open_failure_reports_link_lost(qapp):
    now = [0.0]

    def failing_factory():
        raise OSError("Port not found")

    dev = SerialDevice("TEST", serial_factory=failing_factory, clock=lambda: now[0])
    links = []
    dev.link_changed.connect(links.append)
    dev.open()
    assert links == [False]
    assert dev._serial is None
    dev.close()


def test_partial_line_buffering(qapp):
    now = [0.0]
    dev, fake = make(qapp, now)
    samples = []
    dev.sample_received.connect(samples.append)
    # First half of a sample line
    sample_line = encode_sample(Sample(20, 5.0, 30.0, 10.0, "I"))
    first_half = sample_line[:len(sample_line) // 2].encode()
    fake.incoming = first_half
    dev.poll()
    assert samples == []
    # Second half
    fake.incoming = sample_line[len(sample_line) // 2:].encode()
    dev.poll()
    assert samples == [Sample(20, 5.0, 30.0, 10.0, "I")]
    dev.close()
