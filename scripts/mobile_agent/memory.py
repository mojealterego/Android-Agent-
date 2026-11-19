"""Request-scoped bounded provenance DAG. Content never implies authorization."""
from dataclasses import dataclass
import json
import re

MAX_EVIDENCE = 24
MAX_TEXT = 4096
MAX_CONTEXT = 24000


class GraphError(Exception):
    """Sanitized graph validation failure."""


@dataclass(frozen=True)
class Node:
    id: str
    kind: str
    text: str
    parents: tuple[str, ...] = ()


class EvidenceGraph:
    def __init__(self):
        self._nodes: dict[str, Node] = {}
        self._evidence_count = 0

    def add_evidence(self, kind, text):
        self.add_batch([(kind,text)])
        return f'e{self._evidence_count}'

    def add_batch(self, records):
        if (len(records)+self._evidence_count > MAX_EVIDENCE or
                any(kind not in ('note','image','workflow','file') or not isinstance(text,str) or
                    not 0 < len(text) <= MAX_TEXT for kind,text in records)):
            raise GraphError('Invalid evidence or evidence count limit exceeded')
        candidate = self.context() + [{'id':f'e{self._evidence_count+i+1}','kind':kind,'text':text}
            for i,(kind,text) in enumerate(records)]
        if len(json.dumps(candidate,ensure_ascii=True,separators=(',',':'))) > MAX_CONTEXT:
            raise GraphError('Evidence context limit exceeded')
        for kind,text in records:
            self._evidence_count += 1
            key=f'e{self._evidence_count}'; self._nodes[key] = Node(key,kind,text)

    def add_derived(self, kind, text, parents):
        if (kind not in ('analyst','critic','synthesizer') or kind in self._nodes or
                not isinstance(text,str) or not 0 < len(text) <= MAX_TEXT or
                not isinstance(parents,(tuple,list)) or any(not isinstance(p,str) or p not in self._nodes for p in parents)):
            raise GraphError('Invalid derived node or parent')
        selected=set(parents)
        self._nodes[kind] = Node(kind,kind,text,tuple(p for p in self._nodes if p in selected))
        return kind

    def evidence_ids(self):
        return [key for key in self._nodes if key.startswith('e')]

    def context(self):
        return [{'id':key,'kind':self._nodes[key].kind,'text':self._nodes[key].text} for key in self.evidence_ids()]

    def ancestors(self, key):
        if key not in self._nodes:
            raise GraphError('Unknown graph node')
        seen=set(); todo=list(self._nodes[key].parents)
        while todo:
            parent=todo.pop()
            if parent not in seen:
                seen.add(parent); todo.extend(self._nodes[parent].parents)
        return [p for p in self._nodes if p in seen]

    def export(self):
        # No raw evidence text or image bytes in exported provenance structure.
        return {'nodes':[{'id':n.id,'kind':n.kind} for n in self._nodes.values()],
                'edges':[{'from':n.id,'to':p} for n in self._nodes.values() for p in n.parents]}


def ingest_workflow(graph, data):
    """Atomically ingest a bounded prefix of validated, untrusted MCP metadata."""
    if (not isinstance(data,dict) or data.get('contract')!='omega.storage.workflow/1' or
            type(data.get('complete')) is not bool or not isinstance(data.get('steps'),list) or
            not 1 <= len(data['steps']) <= 4):
        raise GraphError('Invalid workflow envelope')
    records=[]; summaries=[]; count=0; seen=set()
    for step in data['steps']:
        if (not isinstance(step,dict) or not isinstance(step.get('id'),str) or
                not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',step['id']) or step['id'] in seen or
                step.get('status') not in ('matched','no_match_observed','indeterminate','skipped') or
                type(step.get('results_truncated')) is not bool or not isinstance(step.get('matches'),list) or
                len(step['matches'])>50):
            raise GraphError('Invalid workflow step')
        seen.add(step['id']); summaries.append({'id':step['id'],'status':step['status'],'results_truncated':step['results_truncated']})
        for item in step['matches']:
            if (not isinstance(item,dict) or any(not isinstance(item.get(k),str) or not 0<len(item[k])<=2048 for k in ('name','path'))):
                raise GraphError('Invalid file metadata')
            count+=1
            if len(records)<20:
                record=json.dumps({'step':step['id'],'name':item['name'],'path':item['path']},ensure_ascii=True,separators=(',',':'))
                if len(record)>MAX_TEXT:
                    raise GraphError('File metadata limit exceeded')
                records.append(('file',record))
    summary=json.dumps({'complete':data['complete'],'steps':summaries,'omitted_matches':count-len(records)},separators=(',',':'))
    graph.add_batch([('workflow',summary)]+records)
