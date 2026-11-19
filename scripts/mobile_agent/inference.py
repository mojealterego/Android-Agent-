"""Bounded local OpenAI-compatible text/vision transport for Termux (Python 3.10+)."""
import base64
import http.client
import json
import os
import re
import stat

MAX_IMAGE = 4 * 1024 * 1024
MAX_RESPONSE = 256 * 1024
MAX_REQUEST = 6 * 1024 * 1024


class ModelError(Exception):
    """Sanitized transport or input error."""


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate JSON field')
            result[key] = value
        return result
    def invalid_constant(_):
        raise ValueError('Non-finite JSON number')
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid_constant)


def read_image(path):
    """Read only the explicitly selected regular file; never resolve model-supplied paths."""
    fd = None
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW | os.O_CLOEXEC)
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= MAX_IMAGE:
            raise ModelError('Image must be a regular file of at most 4 MiB')
        with os.fdopen(fd, 'rb') as stream:
            fd = None
            data = stream.read(MAX_IMAGE + 1)
        if len(data) > MAX_IMAGE:
            raise ModelError('Image size limit exceeded')
        if data.startswith(b'\x89PNG\r\n\x1a\n'):
            mime = 'image/png'
        elif data.startswith(b'\xff\xd8\xff'):
            mime = 'image/jpeg'
        else:
            raise ModelError('Only PNG and JPEG signatures are accepted')
        return 'data:' + mime + ';base64,' + base64.b64encode(data).decode('ascii')
    except (OSError, TypeError, ValueError):
        raise ModelError('Unable to read selected image') from None
    finally:
        if fd is not None:
            os.close(fd)


class LocalModel:
    """Connects only to a user-selected port on IPv4 loopback. No redirects or tools."""
    def __init__(self, *, port=8082, model='local', token='', timeout=60, max_tokens=512):
        if (type(port) is not int or not 1 <= port <= 65535 or
                type(timeout) is not int or not 1 <= timeout <= 180 or
                type(max_tokens) is not int or not 64 <= max_tokens <= 1024 or
                not isinstance(model, str) or not re.fullmatch(r'[A-Za-z0-9_.:/-]{1,128}', model) or
                not isinstance(token, str) or (token and not re.fullmatch(r'[\x21-\x7e]{1,4096}', token))):
            raise ModelError('Invalid local model configuration')
        self.port, self.model, self.token = port, model, token
        self.timeout, self.max_tokens = timeout, max_tokens

    def complete(self, system, prompt, image=None):
        if (not isinstance(system, str) or not isinstance(prompt, str) or
                len(system) > 4096 or len(prompt) > 48000):
            raise ModelError('Prompt limit exceeded')
        content = prompt
        if image is not None:
            if (not isinstance(image, str) or len(image) > (MAX_IMAGE+2)//3*4+24 or
                    not image.startswith(('data:image/png;base64,', 'data:image/jpeg;base64,'))):
                raise ModelError('Only local inline JPEG/PNG is supported')
            content = [{'type':'text','text':prompt}, {'type':'image_url','image_url':{'url':image}}]
        payload = json.dumps({'model':self.model, 'messages':[{'role':'system','content':system},
            {'role':'user','content':content}], 'stream':False, 'temperature':0,
            'max_tokens':self.max_tokens}, ensure_ascii=True, allow_nan=False).encode('ascii')
        if len(payload) > MAX_REQUEST:
            raise ModelError('Model request size limit exceeded')
        headers = {'Content-Type':'application/json','Accept':'application/json','Connection':'close'}
        if self.token:
            headers['Authorization'] = 'Bearer ' + self.token
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=self.timeout)
        try:
            conn.request('POST','/v1/chat/completions',body=payload,headers=headers)
            response = conn.getresponse()
            if response.status != 200 or response.getheader('Content-Type','').split(';',1)[0].strip().lower() != 'application/json':
                raise ModelError('Local model returned unsuccessful HTTP response')
            raw = response.read(MAX_RESPONSE+1)
            if len(raw) > MAX_RESPONSE:
                raise ModelError('Model response size limit exceeded')
            reply = strict_json(raw)
            choices = reply.get('choices') if isinstance(reply,dict) else None
            if not isinstance(choices,list) or len(choices)!=1 or not isinstance(choices[0],dict):
                raise ModelError('Invalid model response envelope')
            choice=choices[0]; msg=choice.get('message')
            if (choice.get('finish_reason')!='stop' or not isinstance(msg,dict) or
                    msg.get('tool_calls') or msg.get('function_call') or not isinstance(msg.get('content'),str) or
                    not 0 < len(msg['content']) <= 8192):
                raise ModelError('Invalid, truncated or tool-bearing model response')
            return msg['content']
        except (OSError, http.client.HTTPException, ValueError, RecursionError):
            raise ModelError('Local model transport or decoding failure') from None
        finally:
            conn.close()
