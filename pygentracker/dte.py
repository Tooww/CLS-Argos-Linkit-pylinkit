from .dte_nus import DTENUS
from .dte_params import DTEParamMap
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
        return [self._decode_response(r + '\r') for r in resp.split('\r')]

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
        log_d = ['system', 'sensor']
        resp = self._nus.send(self._encode_command('DUMPD', args=['{log_d}'.format(log_d=log_d.index(log_type))]), timeout=1.0, multi_response=True)
        return self._decode_multi_response(resp)

    def factw(self):
        resp = self._nus.send(self._encode_command('FACTW'))
        self._decode_response(resp)
    
    def rstvw(self):
        resp = self._nus.send(self._encode_command('RSTVW', args=['1']))
        self._decode_response(resp)
    
    def rstbw(self):
        resp = self._nus.send(self._encode_command('RSTBW'))
        self._decode_response(resp)
