"""Owner-invoked Termux companion: read one JSON task from stdin, emit one JSON result."""
import argparse
from contextlib import nullcontext
import json
import os
from pathlib import Path
import sys
from .advanced import ResourceLease, AdvancedError
from .inference import LocalModel, ModelError, read_image, strict_json
from .memory import GraphError
from .recovery import CheckpointStore, RecoveryError, ResourceGuard, thermal_reader
from .orchestrator import run_task, validate_input, TaskError
from ocaf.storage_bridge import call_storage_workflow, BridgeError, MAX_REQUEST


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--port',type=int,default=8082,help='Trusted local llama-server port (127.0.0.1 only)')
    p.add_argument('--model',default='local')
    p.add_argument('--timeout',type=int,default=60,help='Socket timeout per inference call')
    p.add_argument('--max-tokens',type=int,default=512)
    p.add_argument('--image',type=Path,help='Explicitly selected local JPEG/PNG, <=4 MiB')
    p.add_argument('--workflow',type=Path,help='Explicit owner-prepared storage workflow JSON file')
    p.add_argument('--endpoint',help='Trusted HTTPS /mcp endpoint, required with --workflow')
    p.add_argument('--tool',default='android_storage_workflow')
    p.add_argument('--ca-file',help='Optional trusted CA PEM for MCP')
    p.add_argument('--checkpoint-dir',type=Path,help='Private directory; explicitly persist sensitive model outputs')
    p.add_argument('--job-id',help='Stable checkpoint identifier')
    p.add_argument('--purge-job',action='store_true',help='Delete checkpoint and exit without inference')
    p.add_argument('--lease-dir',type=Path,help='Existing private directory shared with semantic search for cooperative inference exclusion')
    p.add_argument('--min-memory-mib',type=int,help='Optional per-role memory admission')
    p.add_argument('--thermal-sensor',type=Path,help='Owner-selected millicelsius sysfs sensor')
    p.add_argument('--max-temperature',type=float,default=43.0)
    args=p.parse_args(argv)
    try:
        if bool(args.workflow)!=bool(args.endpoint) or (args.ca_file and not args.workflow):
            raise TaskError('Workflow and trusted endpoint must be specified together')
        if bool(args.checkpoint_dir)!=bool(args.job_id) or (args.purge_job and not args.job_id):
            raise RecoveryError("Checkpoint directory and job ID must be specified together")
        if args.checkpoint_dir and (args.workflow or args.image):
            raise RecoveryError("Persistent checkpoints accept only explicit local text")
        config={"model":args.model,"port":args.port,"max_tokens":args.max_tokens}
        manager=CheckpointStore(args.checkpoint_dir,args.job_id,config) if args.checkpoint_dir else nullcontext()
        if args.purge_job:
            with manager as c: c.purge()
            return 0
        guard=ResourceGuard(min_memory_mib=args.min_memory_mib if args.min_memory_mib is not None else 1024,
                            max_temperature=args.max_temperature if args.thermal_sensor else None,
                            temperature_reader=thermal_reader(args.thermal_sensor) if args.thermal_sensor else None) if args.min_memory_mib is not None or args.thermal_sensor or args.lease_dir else None
        raw=sys.stdin.buffer.read(MAX_REQUEST+1)
        if len(raw)>MAX_REQUEST: raise TaskError('Task input exceeds 32 KiB')
        task=strict_json(raw)
        if not isinstance(task,dict) or set(task)-{'question','notes'} or 'question' not in task:
            raise TaskError('Task accepts only question and notes')
        notes=task.get('notes',[])
        validate_input(task['question'],notes)
        model=LocalModel(port=args.port,model=args.model,token=os.environ.get('OMEGA_LOCAL_MODEL_TOKEN',''),
                         timeout=args.timeout,max_tokens=args.max_tokens)
        image=read_image(args.image) if args.image else None
        workflow=None
        if args.workflow:
            with args.workflow.open('rb') as stream: plan_raw=stream.read(MAX_REQUEST+1)
            if len(plan_raw)>MAX_REQUEST: raise TaskError('Workflow input exceeds 32 KiB')
            plan=strict_json(plan_raw)
            workflow=call_storage_workflow(args.endpoint,os.environ.get('OMEGA_MCP_TOKEN',''),args.tool,plan,ca_file=args.ca_file)
        with (ResourceLease(args.lease_dir) if args.lease_dir else nullcontext()), manager as checkpoint:
            result=run_task(model,task['question'],notes=notes,image=image,workflow=workflow,checkpoint=checkpoint,before_call=guard.check if guard else None)
        print(json.dumps(result,ensure_ascii=True,allow_nan=False,separators=(',',':')))
        return 0
    except (ModelError,GraphError,TaskError,BridgeError,RecoveryError,AdvancedError) as exc:
        print(str(exc),file=sys.stderr)
        return 1
    except (OSError,ValueError,RecursionError):
        print('Unable to read or decode input',file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print('Task cancelled',file=sys.stderr)
        return 130


if __name__=='__main__':
    sys.exit(main())
