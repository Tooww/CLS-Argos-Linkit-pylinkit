import logging
import re
from threading import Event


logger = logging.getLogger(__name__)


NUS_CHAR_LENGTH = 20
NUS_RX_CHAR_UUID = '6E400002-B5A3-F393-E0A9-E50E24DCCA9E'
NUS_TX_CHAR_UUID = '6E400003-B5A3-F393-E0A9-E50E24DCCA9E'


class DTENUSProtocol():
    def __init__(self):
        self.reset()
        self._queued_data = ''

    def data(self):
        return self._queued_data

    def push(self, buffer):
        self._queued_data += buffer
        if self._expected_length == 0:
            buffer = self._extract_header(buffer)
        if buffer:
            if self._is_header(buffer):
                self.reset()
                logger.error(f'Unexpected header received: {buffer}')
                raise Exception()
            if self._expected_length < len(buffer):
                self.reset()
                logger.error(f'Too many bytes received: remaining {self._expected_length} got {len(buffer)}')
                raise Exception()
            self._expected_length -= len(buffer)
            if self._expected_length == 0:
                if self._expected_MMM is not None:
                    if self._last_nnn == self._expected_MMM:
                        self.reset()
                else:
                    self.reset()

    def is_terminated(self):
        return self._is_terminated

    def reset(self):
        self._expected_length = 0
        self._expected_MMM = None
        self._is_terminated = True
        self._last_nnn = None

    def _is_header(self, buffer):
        return buffer[0] == '$'

    def _extract_header(self, buffer):
        success_regexp = '^\\$O;(?P<cmd>[A-Z]+)#(?P<len>[0-9a-fA-F]+);(?P<payload>.*)'
        fail_regexp = '^\\$N;(?P<cmd>[A-Z]+)#(?P<len>[0-9a-fA-F]+);(?P<error>[0-9]+)\r$'
        success = re.match(success_regexp, buffer)
        if success:
            self._is_terminated = False
            self._expected_length = int(success.group('len'), 16) + 1  # +1 for \r terminator
            buffer = success.group('payload')
            if success.group('cmd') == 'DUMPD':
                try:
                    args = buffer.split(',')
                    nnn = int(args[0],16)
                    mmm = int(args[1],16)
                    if self._last_nnn is None:
                        if nnn != 0:
                            self.reset()
                            logger.error(f'First DUMPD nnn must be zero: got {nnn}')
                            raise Exception()
                        if mmm <= 0:
                            self.reset()
                            logger.error(f'First DUMPD MMM must be >0: got {mmm}')
                            raise Exception()
                        self._last_nnn = 0
                        self._expected_MMM = mmm
                    else:
                        self._last_nnn += 1
                        if nnn != self._last_nnn:
                            self.reset()
                            logger.error(f'Unexpected DUMPD nnn: got {nnn} but expected {nnn}')
                            raise Exception()
                        if nnn > self._expected_MMM:
                            self.reset()
                            logger.error(f'Unexpected DUMPD nnn: got {nnn} which exceeds {self._expected_MMM}')
                            raise Exception()
                except:
                    self.reset()
                    logger.error(f'Unexpected DUMPD payload: {buffer}')
                    raise Exception()
            return buffer

        fail = re.match(fail_regexp, buffer)
        if fail:
            self.reset()
            return ''

        self.reset()
        raise Exception(f'Malformed header received: {buffer}')

class DTENUS():
    def __init__(self, device):
        self._device = device
        self._event = Event()
        self._queued_data = ''
        device.subscribe(NUS_TX_CHAR_UUID, self._data_handler)
    
    def send(self, data, timeout=2.0, multi_response=False):
        self._protocol = DTENUSProtocol()
        self._queued_data = ''
        self._terminate = False
        self._event.clear()
        for x in [ data[0+i:NUS_CHAR_LENGTH+i] for i in range(0, len(data), NUS_CHAR_LENGTH) ]:
            logger.debug('PC -> DTE: %s', x.encode('ascii'))
            self._device.char_write(NUS_RX_CHAR_UUID, x.encode('ascii'))
        while True:
            is_set = self._event.wait(timeout)
            if not is_set:
                raise Exception('Timeout')
            else:
                if self._terminate:
                    break
        return self._protocol.data()

    def _data_handler(self, _, data):
        logger.debug('PC <- DTE: %s', data.decode('ascii'))
        try:
            self._protocol.push(data.decode('ascii'))
            self._terminate = self._protocol.is_terminated()
        except:
            self._terminate = True
        self._event.set()
        self._event.clear()
