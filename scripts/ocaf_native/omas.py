"""Native OMAs v2 signed STAGED admission over the OCAF mTLS JSON-lines listener."""
import argparse
import hashlib
import hmac
import json
import re
import secrets
import socket
import ssl
import struct
import sys
import time
from pathlib import Path

from .common import NativeError, canonical, digest_hex, read_credential, segment, strict_decode

MAX_FRAME = 65536


class OmasError(NativeError):
    """OMAs admission denied or unconfirmed: never auto-retry."""


def build_registration(tenant, agent_id, sender, manifest_sha256, signing_key, *, now=None, nonce=None, request_id=None):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    if (not all(segment(v) for v in (tenant, agent_id, sender)) or
            len(f'{tenant}/agents/{agent_id}') > 256 or not digest_hex(manifest_sha256) or
            not isinstance(signing_key, Ed25519PrivateKey)):
        raise OmasError('Invalid identity, manifest digest or signing key')
    now = int(time.time()) if now is None else now
    nonce = secrets.token_hex(24) if nonce is None else nonce
    request_id = secrets.token_hex(16) if request_id is None else request_id
    if (type(now) is not int or not 0 <= now < 2**63 or not segment(nonce) or len(nonce) < 16 or not segment(request_id)):
        raise OmasError('Invalid signed operation metadata')
    # Struct field order is part of the Rust serde_json signature binding.
    request = {'request_id':request_id, 'agent_id':agent_id, 'tenant':tenant,
               'manifest_digest':'sha256:'+manifest_sha256, 'declared_state':'STAGED',
               'readiness':False, 'ostc_enabled':False, 'source_access':'disabled'}
    payload = canonical(request)
    namespace = f'{tenant}/agents'; target = f'{namespace}/{agent_id}'
    fuel = 1000
    parts = (tenant.encode(), namespace.encode(), target.encode(), b'\x05',
             struct.pack('>Q',fuel), struct.pack('>q',now), nonce.encode(),
             hashlib.sha256(payload).digest(), sender.encode())
    signed = b'OCAF-OMAS-SIGNED-OPERATION-v2' + b''.join(struct.pack('>Q',len(p))+p for p in parts)
    operation = {'tenant':tenant,'namespace':namespace,'target':target,'opcode':5,
                 'fuel':fuel,'issued_at':now,'nonce':nonce,'payload':list(payload),
                 'rpc_sender':sender,'signature':list(signing_key.sign(signed))}
    return {'request':request,'operation':operation}


def _decision(raw, request):
    try:
        if not 0 < len(raw) <= MAX_FRAME or not raw.endswith(b'\n'):
            raise ValueError()
        reply = strict_decode(raw)
        if not isinstance(reply,dict) or set(reply) != {'ok','decision'} or reply['ok'] is not True:
            raise ValueError()
        d=reply['decision']
        if (not isinstance(d,dict) or set(d) != {'request_id','agent_id','admitted','lifecycle','reason'} or
                d['request_id'] != request['request_id'] or d['agent_id'] != request['agent_id'] or
                d['admitted'] is not True or d['lifecycle'] != 'STAGED' or
                d['reason'] != 'staged_registration_admitted'):
            raise ValueError()
        return d
    except (ValueError, TypeError, RecursionError):
        raise OmasError('OMAs admission denied or invalid response; verify server state before retry') from None


def _readline(tls, deadline):
    data=bytearray()
    while len(data) <= MAX_FRAME:
        remaining=deadline-time.monotonic()
        if remaining <= 0:
            raise TimeoutError()
        tls.settimeout(remaining)
        chunk=tls.recv(min(4096,MAX_FRAME+1-len(data)))
        if not chunk:
            break
        data.extend(chunk)
        if b'\n' in chunk:
            if data.count(b'\n') != 1 or not data.endswith(b'\n'):
                raise OmasError('Unexpected multiple response lines')
            break
    return bytes(data)


def register_staged(*, host, port, ca_file, cert_file, key_file, server_sha256,
                    signing_key_file, tenant, agent_id, sender, manifest_sha256, timeout=5):
    """One explicit admission. CA+hostname+DER pin and client certificate required."""
    from cryptography.hazmat.primitives.serialization import load_pem_private_key
    if (not isinstance(host,str) or not re.fullmatch(r'[A-Za-z0-9.:-]{1,253}',host) or
            type(port) is not int or not 1<=port<=65535 or not digest_hex(server_sha256) or
            type(timeout) not in (int,float) or not 1<=timeout<=30):
        raise OmasError('Invalid OMAs endpoint, pin or timeout')
    try:
        ca=read_credential(ca_file)
        read_credential(cert_file); read_credential(key_file,private=True)
        key=load_pem_private_key(read_credential(signing_key_file,private=True,max_bytes=16384),password=None)
        env=build_registration(tenant,agent_id,sender,manifest_sha256,key)
        frame=canonical(env)+b'\n'
        if len(frame)>MAX_FRAME:
            raise OmasError('OMAs frame exceeds limit')
        ctx=ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.minimum_version=ssl.TLSVersion.TLSv1_2
        ctx.load_verify_locations(cadata=ca.decode('ascii'))
        # Python/OpenSSL reopens certificate paths; operator-controlled parents required.
        ctx.load_cert_chain(str(cert_file),str(key_file),password=lambda: '')
        deadline=time.monotonic()+timeout
        with socket.create_connection((host,port),timeout=timeout) as raw:
            raw.settimeout(max(0.001,deadline-time.monotonic()))
            with ctx.wrap_socket(raw,server_hostname=host) as tls:
                cert=tls.getpeercert(binary_form=True)
                if not cert or not hmac.compare_digest(hashlib.sha256(cert).hexdigest(),server_sha256):
                    raise OmasError('OMAs server certificate pin mismatch')
                remaining=deadline-time.monotonic()
                if remaining<=0: raise TimeoutError()
                tls.settimeout(remaining); tls.sendall(frame)
                return _decision(_readline(tls,deadline),env['request'])
    except OmasError:
        raise
    except (NativeError, OSError, ValueError, TypeError, UnicodeError, RecursionError):
        raise OmasError('OMAs transport, credential or admission failed; verify server state before retry') from None


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    for field in ('host','tenant','agent-id','sender','manifest-sha256','server-sha256'):
        p.add_argument('--'+field,required=True)
    p.add_argument('--port',type=int,required=True)
    for field in ('ca-file','cert-file','key-file','signing-key-file'):
        p.add_argument('--'+field,required=True,type=Path)
    p.add_argument('--timeout',type=int,default=5)
    try:
        result=register_staged(**vars(p.parse_args(argv)))
        print(json.dumps(result,ensure_ascii=True)); return 0
    except (OmasError, ImportError) as e:
        print(str(e) if isinstance(e,OmasError) else 'Install approved cryptography package',file=sys.stderr); return 1
    except KeyboardInterrupt:
        return 130


if __name__=='__main__': sys.exit(main())
