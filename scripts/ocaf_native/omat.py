"""Native OMAt authenticated Zenoh discovery and digest-pinned schema retrieval.
No execution path: upstream OCAF registry currently returns ExecutorUnavailable.
"""
import argparse
import base64
import hashlib
import hmac
import ipaddress
import json
from pathlib import Path
import re
import secrets
import sys

from .common import NativeError, canonical, digest_hex, read_credential, segment, strict_decode

MAX_RESPONSE=256*1024


def omat_id(value):
    return isinstance(value,str) and re.fullmatch(r'[A-Za-z0-9._:-]{1,128}',value) is not None


def manifest_digest(value):
    return isinstance(value,str) and value.startswith('sha256:') and digest_hex(value[7:])


class OmatError(NativeError):
    """Invalid configuration, discovery denial or unconfirmed result."""


def build_discovery(tenant,principal,key,*,tool_id=None,manifest_sha256=None,nonce=None):
    if (not segment(tenant) or not segment(principal) or not isinstance(key,bytes) or len(key)!=32 or key==bytes(32) or
            ((tool_id is None)!=(manifest_sha256 is None)) or
            (tool_id is not None and (not omat_id(tool_id) or not manifest_digest(manifest_sha256)))):
        raise OmatError('Invalid discovery binding')
    nonce=secrets.token_hex(24) if nonce is None else nonce
    if not isinstance(nonce,str) or not re.fullmatch(r'[A-Za-z0-9]{16,128}',nonce):
        raise OmatError('Invalid discovery nonce')
    topic=f'ocaf/omat/{tenant}/discovery'
    operation='discover' if tool_id is None else 'schemas'
    values=[principal,topic,nonce,operation,tool_id,manifest_sha256]
    frame=dict(zip(('principal','topic','nonce','operation','tool_id','manifest_sha256'),values))
    frame['mac_hex']=hmac.new(key,canonical(values),hashlib.sha256).hexdigest()
    return topic,canonical(frame)


def parse_discovery(raw,tenant,manifest_sha256=None):
    if not segment(tenant) or (manifest_sha256 is not None and not manifest_digest(manifest_sha256)):
        raise OmatError('Invalid local discovery expectation')
    try:
        if not isinstance(raw,bytes) or not 0<len(raw)<=MAX_RESPONSE: raise ValueError()
        reply=strict_decode(raw)
        if not isinstance(reply,dict) or set(reply)!={'descriptors','schemas'}: raise ValueError()
        if manifest_sha256 is not None:
            s=reply['schemas']
            if (reply['descriptors'] is not None or not isinstance(s,dict) or
                set(s)!={'manifest_sha256','input_schema','output_schema'} or s['manifest_sha256']!=manifest_sha256 or
                any(not isinstance(s[k],(dict,bool)) for k in ('input_schema','output_schema'))): raise ValueError()
        else:
            ds=reply['descriptors']; seen=set()
            if reply['schemas'] is not None or not isinstance(ds,list) or len(ds)>4096: raise ValueError()
            for d in ds:
                if (not isinstance(d,dict) or set(d)!={'tenant_id','tool_id','version','manifest_sha256','risk','capabilities'} or
                    d['tenant_id']!=tenant or not omat_id(d['tool_id']) or d['tool_id'] in seen or
                    not omat_id(d['version']) or not manifest_digest(d['manifest_sha256']) or
                    d['risk'] not in ('read_only','bounded_write','external_side_effect') or
                    not isinstance(d['capabilities'],list) or len(d['capabilities'])>64 or
                    any(not omat_id(c) for c in d['capabilities']) or
                    len(set(d['capabilities']))!=len(d['capabilities'])): raise ValueError()
                seen.add(d['tool_id'])
        return reply
    except (ValueError,TypeError,UnicodeError,RecursionError):
        raise OmatError('OMAt discovery response rejected') from None


def discover(tenant,principal,key,exchange,*,tool_id=None,manifest_sha256=None):
    topic,frame=build_discovery(tenant,principal,key,tool_id=tool_id,manifest_sha256=manifest_sha256)
    return parse_discovery(exchange(topic,frame),tenant,manifest_sha256)


def make_zenoh_config(endpoint,ca_file,cert_file,key_file):
    """Construct TLS-only client settings matching OCAF transport_policy."""
    if not isinstance(endpoint,str): raise OmatError('Invalid Zenoh TLS endpoint')
    m=re.fullmatch(r'tls/([A-Za-z0-9.-]{1,253}|\[[0-9A-Fa-f:]+\]):([0-9]{1,5})',endpoint)
    if not m or not 1<=int(m[2])<=65535: raise OmatError('Invalid Zenoh TLS endpoint')
    if m[1].startswith('['):
        try: ipaddress.IPv6Address(m[1][1:-1])
        except ValueError: raise OmatError('Invalid IPv6 endpoint') from None
    try:
        read_credential(ca_file); read_credential(cert_file); read_credential(key_file,private=True)
    except NativeError:
        raise OmatError('Invalid Zenoh credential') from None
    return {'mode':'client','connect':{'endpoints':[endpoint]},'listen':{'endpoints':[]},
            'scouting':{'multicast':{'enabled':False},'gossip':{'enabled':False}},
            'transport':{'unicast':{'compression':{'enabled':False},'open_timeout':5000},
                         'multicast':{'compression':{'enabled':False}},
                         'link':{'protocols':['tls'],'tls':{'enable_mtls':True,'verify_name_on_connect':True,
                            'close_link_on_expiration':True,'root_ca_certificate':str(ca_file),
                            'connect_certificate':str(cert_file),'connect_private_key':str(key_file)}}}}


def zenoh_exchange(config,topic,frame):
    """Use official Zenoh Python SDK. Require exactly one successful expected-topic reply."""
    try:
        import zenoh
        with zenoh.open(zenoh.Config.from_json5(json.dumps(config))) as session:
            replies=session.get(topic,payload=frame,timeout=5,target=zenoh.QueryTarget.ALL,
                                consolidation=zenoh.ConsolidationMode.NONE)
            result=None
            for reply in replies:
                sample=reply.ok
                if result is not None or sample is None or str(sample.key_expr)!=topic:
                    raise OmatError('Ambiguous or denied OMAt reply')
                result=sample.payload.to_bytes()
                if len(result)>MAX_RESPONSE: raise OmatError('Oversized OMAt reply')
            if result is None: raise OmatError('OMAt returned no reply')
            return result
    except OmatError:
        raise
    except Exception:
        raise OmatError('Zenoh unavailable or discovery failed; no fallback') from None


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    for field in ('endpoint','tenant','principal'):
        p.add_argument('--'+field,required=True)
    for field in ('ca-file','cert-file','key-file','hmac-key-file'):
        p.add_argument('--'+field,required=True,type=Path)
    p.add_argument('--tool-id'); p.add_argument('--manifest-sha256')
    a=p.parse_args(argv)
    try:
        config=make_zenoh_config(a.endpoint,a.ca_file,a.cert_file,a.key_file)
        key=base64.b64decode(read_credential(a.hmac_key_file,private=True,max_bytes=128).strip(),validate=True)
        reply=discover(a.tenant,a.principal,key,lambda topic,frame:zenoh_exchange(config,topic,frame),tool_id=a.tool_id,manifest_sha256=a.manifest_sha256)
        print(json.dumps({'untrusted_catalog_data':True,'execution_authorized':False,'result':reply},ensure_ascii=True)); return 0
    except (NativeError, ValueError, TypeError):
        print('OMAt discovery rejected or unavailable; no execution',file=sys.stderr); return 1
    except KeyboardInterrupt:
        return 130


if __name__=='__main__': sys.exit(main())
