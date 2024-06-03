from .dte_nus import DTENUS
from .dte_params import DTEParamMap
from .dte_types import BASE64, PASPW
import re
import logging


logger = logging.getLogger(__name__)


class DTE():

    def __init__(self, device):
        self._nus = DTENUS(device)

    def _encode_command(self, command, params=[], param_values={}, args=[]):
        if params:
            payload = ','.join([DTEParamMap.param_to_key(x) for x in params])
        elif args:
            payload = ','.join(args)
        elif param_values:
            payload = ','.join(['{}={}'.format(DTEParamMap.param_to_key(x), DTEParamMap.encode(x, param_values[x])) for x in param_values])
        else:
            payload = ''
        return '${cmd}#{length:03x};{payload}\r'.format(cmd=command, length=len(payload), payload=payload)

    def _decode_response(self, resp):
        success_regexp = '^\\$O;(?P<cmd>[A-Z]+)#(?P<len>[0-9a-fA-F]+);(?P<payload>.*)\r$'
        fail_regexp = '^\\$N;(?P<cmd>[A-Z]+)#(?P<len>[0-9a-fA-F]+);(?P<error>[0-9]+)\r$'
        success = re.match(success_regexp, resp)
        if success:
            return success.group('payload')
        fail = re.match(fail_regexp, resp)
        if fail:
            raise Exception('{} - error {}'.format(fail.group('cmd'), fail.group('error')))
        raise Exception('Bad response - {}'.format(resp))

    def _decode_multi_response(self, resp):
        return [self._decode_response(r + '\r') for r in resp.split('\r') if r]

    def _decode_key_values(self, payload):
        m = {}
        for x in payload.strip().split(','):
            key,value = x.split('=')
            m[DTEParamMap.key_to_param(key)] = DTEParamMap.decode(key, value)
        return m

    def parmr(self, params=[]):
        resp = self._nus.send(self._encode_command('PARMR', params=params))
        return self._decode_key_values(self._decode_response(resp))

    def statr(self, params=[]):
        resp = self._nus.send(self._encode_command('STATR', params=params))
        return self._decode_key_values(self._decode_response(resp))

    def parmw(self, param_values={}):
        resp = self._nus.send(self._encode_command('PARMW', param_values=param_values))
        self._decode_response(resp)

    def dumpd(self, log_type='sensor'):
        log_d = {'system': 0,
                 'sensor': 1,
                 'gnss': 1,
                 'als': 2,
                 'ph': 3,
                 'rtd': 4,
                 'cdt': 5,
                 'axl': 6,
                 'pressure': 7,
                 'baro': 8 } #Tom 
        resp = self._nus.send(self._encode_command('DUMPD', args=['{}'.format(log_d[log_type])]), multi_response=True)
        responses = self._decode_multi_response(resp)
        raw_data = b''
        for r in responses:
            _, _, data = r.split(',')
            decoded_data = BASE64.decode(data)
            raw_data += decoded_data
        return raw_data

    def paspw(self, json_file_data):
        resp = self._nus.send(self._encode_command('PASPW', args=[PASPW.encode(json_file_data)]), timeout=5.0)
        self._decode_response(resp)

    def erase(self, log_type):
        log_d = {'all': 3,
                 'system': 2,
                 'sensor': 1,
                 'gnss': 1,
                 'als': 4,
                 'ph': 5,
                 'rtd': 6,
                 'cdt': 7,
                 'axl': 8,
                 'pressure': 9 }
        resp = self._nus.send(self._encode_command('ERASE', args=['{}'.format(log_d[log_type])]))
        self._decode_response(resp)

    def factw(self):
        resp = self._nus.send(self._encode_command('FACTW'))
        self._decode_response(resp)

    def rstvw(self, var_id):
        resp = self._nus.send(self._encode_command('RSTVW', args=[str(var_id)]))
        self._decode_response(resp)

    def rstbw(self):
        resp = self._nus.send(self._encode_command('RSTBW'))
        self._decode_response(resp)

    def scalw(self, sensor, step, value):
        sensor_d = {'axl': 0,
                    'pressure': 1,
                    'als': 2,
                    'ph': 3,
                    'rtd': 4,
                    'cdt': 5,
                    'mcp47x6': 6 }
        resp = self._nus.send(self._encode_command('SCALW', args=[str(sensor_d[sensor]), str(step), str(value)]))
        self._decode_response(resp)

    def argostx(self, mod, power, freq, size, tcxo):
        mod_d = {'A2': 0,
                 'A3': 1,
                 'A4': 2}
        resp = self._nus.send(self._encode_command('SATTX', args=[str(mod_d[mod]), str(power), str(freq), str(size), str(tcxo)]))
        self._decode_response(resp)
