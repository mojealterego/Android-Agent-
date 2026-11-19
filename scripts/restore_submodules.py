#!/usr/bin/env python3
"""Restore an exact original gitlink from public HTTPS or an offline Git bundle; never build."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
class RestoreError(Exception): pass


def _git(root,*args,local=False,timeout=120):
    # No user/system Git config, credential prompts, hooks, or external protocol helpers.
    env={k:v for k,v in os.environ.items() if not k.startswith('GIT_')}
    env.update(GIT_CONFIG_NOSYSTEM='1',GIT_CONFIG_GLOBAL=os.devnull,GIT_TERMINAL_PROMPT='0',GIT_NO_REPLACE_OBJECTS='1')
    cmd=['git','-c','core.hooksPath='+os.devnull,'-c','protocol.allow=never','-c','protocol.https.allow=always','-c','protocol.file.allow='+('always' if local else 'never'),'-C',str(root),*args]
    try: result=subprocess.run(cmd,env=env,capture_output=True,text=True,timeout=timeout,check=False)
    except (OSError,subprocess.TimeoutExpired): raise RestoreError('Git unavailable or timed out') from None
    if result.returncode: raise RestoreError(f'Git operation failed ({args[0]}, exit {result.returncode})')
    return result.stdout.strip()


def _identity(root,pin,tree):
    if _git(root,'rev-parse','HEAD')!=pin or _git(root,'rev-parse','HEAD^{tree}')!=tree or _git(root,'status','--porcelain','--untracked-files=all'):
        raise RestoreError('Checkout identity or cleanliness mismatch')
    _git(root,'fsck','--full','--no-reflogs')


def restore(root,spec,*,bundle=None):
    root=Path(root).resolve()
    try: path,remote,pin,tree=(spec[k] for k in ('path','repo','commit','tree'))
    except (KeyError,TypeError): raise RestoreError('Invalid dependency spec') from None
    if not re.fullmatch(r'vendor/[A-Za-z0-9_-]+',path) or not re.fullmatch(r'https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\.git',remote) or not all(re.fullmatch('[0-9a-f]{40}',x) for x in (pin,tree)):
        raise RestoreError('Invalid dependency spec')
    if _git(root,'ls-files','--stage','--',path)!=f'160000 {pin} 0\t{path}': raise RestoreError('Project gitlink differs from lock')
    parent=root/'vendor'; dest=root/path
    if parent.is_symlink() or not parent.is_dir() or dest.is_symlink() or (dest.exists() and not dest.is_dir()): raise RestoreError('Unsafe target')
    if (dest/'.git').exists():
        _identity(dest,pin,tree)
        return {'path':path,'commit':pin,'tree':tree,'status':'already_verified'}
    if dest.exists() and any(dest.iterdir()): raise RestoreError('Destination contains existing data')
    source=remote
    if bundle is not None:
        bundle=Path(bundle).absolute()
        try: s=bundle.lstat()
        except OSError: raise RestoreError('Bundle unavailable') from None
        if not stat.S_ISREG(s.st_mode) or not 0<s.st_size<=2**31: raise RestoreError('Bundle must be a bounded regular file')
        source=str(bundle)
    stage=Path(tempfile.mkdtemp(prefix='.omega-submodule-',dir=parent))
    try:
        _git(stage,'init','--quiet')
        if bundle is not None: _git(stage,'bundle','verify',source,local=True)
        _git(stage,'fetch','--no-tags','--no-recurse-submodules',source,pin,local=bundle is not None,timeout=600)
        if _git(stage,'rev-parse','FETCH_HEAD')!=pin or _git(stage,'rev-parse',pin+'^{tree}')!=tree: raise RestoreError('Fetched commit/tree differs from pin')
        _git(stage,'fsck','--full','--no-reflogs')
        # A standalone clean checkout is valid under the parent's original gitlink.
        _git(stage,'checkout','--detach','--quiet',pin)
        _identity(stage,pin,tree)
        _git(stage,'remote','add','origin',remote)
        if dest.exists(): dest.rmdir()  # never remove a nonempty target
        stage.rename(dest)
        return {'path':path,'commit':pin,'tree':tree,'status':'restored'}
    except OSError: raise RestoreError('Checkout publication failed; inspect destination') from None
    finally:
        if stage.exists(): shutil.rmtree(stage)


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('name',choices=['cloudflared','ngrok-java']); p.add_argument('--bundle',type=Path); args=p.parse_args(argv)
    try:
        specs=json.loads((ROOT/'docs/release/upstream-submodules.json').read_text())['submodules']; spec=next(x for x in specs if x['path']=='vendor/'+args.name)
        print(json.dumps(restore(ROOT,spec,bundle=args.bundle),indent=2)); return 0
    except (RestoreError,OSError,ValueError,KeyError,StopIteration) as e: print(str(e) if isinstance(e,RestoreError) else 'Restore failed',file=sys.stderr); return 1
    except KeyboardInterrupt: return 130

if __name__=='__main__': sys.exit(main())
