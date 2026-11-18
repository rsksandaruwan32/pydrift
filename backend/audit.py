"""PyDrift: bounded read-only Python configuration audit. Python 3.10+."""
import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path, PureWindowsPath
LIMIT=524288

def jsonc(text):
    chars=list(text); i=0; quoted=False; escaped=False
    while i<len(chars):
        c=chars[i]
        if quoted:
            if escaped: escaped=False
            elif c=='\\': escaped=True
            elif c=='"': quoted=False
            i+=1
        elif c=='"': quoted=True; i+=1
        elif text[i:i+2]=='//':
            while i<len(chars) and chars[i]!='\n': chars[i]=' '; i+=1
        elif text[i:i+2]=='/*':
            end=text.find('*/',i+2)
            if end<0: raise ValueError('Unterminated comment')
            for j in range(i,end+2):
                if chars[j] not in '\r\n': chars[j]=' '
            i=end+2
        else: i+=1
    i=0; quoted=False; escaped=False
    while i<len(chars):
        c=chars[i]
        if quoted:
            if escaped: escaped=False
            elif c=='\\': escaped=True
            elif c=='"': quoted=False
        elif c=='"': quoted=True
        elif c==',':
            j=i+1
            while j<len(chars) and chars[j].isspace(): j+=1
            if j<len(chars) and chars[j] in '}]': chars[i]=' '
        i+=1
    def pairs(items):
        out={}
        for k,v in items:
            if k in out: raise ValueError('Duplicate JSON key: '+k)
            out[k]=v
        return out
    return json.loads(''.join(chars),object_pairs_hook=pairs)

def read(root,rel):
    current=root
    for part in Path(rel).parts:
        current=current/part
        if current.is_symlink() or getattr(current,'is_junction',lambda:False)():
            raise ValueError('Symlink/junction skipped')
    if not current.resolve().is_relative_to(root): raise ValueError('External path skipped')
    with current.open('rb') as f: data=f.read(LIMIT+1)
    if len(data)>LIMIT: raise ValueError('File exceeds 512 KiB')
    return data.decode('utf-8-sig')

def norm(value,root):
    value=value.replace('${workspaceFolder}',str(root)).replace('\\','/').rstrip('/')
    return value.casefold() if os.name=='nt' else value

def audit(directory):
    root=Path(directory).resolve(strict=True)
    if not root.is_dir(): raise ValueError('Workspace must be a directory')
    findings=[]; skipped=[]; refs=[]; versions=[]; inputs=[]
    def emit(rel,rule,message,line=1,severity='warning',evidence=None):
        item=dict(file=rel,rule=rule,message=message,line=line,severity=severity,evidence=evidence)
        item['fingerprint']=hashlib.sha256(json.dumps(item,sort_keys=True).encode()).hexdigest()[:20]
        findings.append(item)
    targets=['.vscode/settings.json','.vscode/launch.json','.vscode/tasks.json','.python-version']
    wd=root/'.github/workflows'
    if wd.is_dir() and not wd.is_symlink():
        try: targets += [str(p.relative_to(root)) for p in sorted(wd.iterdir())[:196] if p.suffix in ('.yaml','.yml')]
        except OSError as e: skipped.append(dict(file='.github/workflows',reason=str(e)))
    for rel in targets:
        p=root/rel
        if not p.exists() and not p.is_symlink(): continue
        try:
            text=read(root,rel)
            inputs.append(dict(file=rel,sha256=hashlib.sha256(text.encode()).hexdigest()))
            if rel=='.python-version':
                value=text.strip()
                if re.fullmatch(r'3\.\d+(?:\.\d+)?',value): versions.append((rel,1,value))
                continue
            if p.suffix in ('.yaml','.yml'):
                for n,line in enumerate(text.splitlines(),1):
                    if line.lstrip().startswith('#'): continue
                    if re.search(r'(?<![\w-])pip3?\s+install\b',line) and not re.search(r'\bpython[\d.]*\s+-m\s+pip',line):
                        emit(rel,'PD003','Bare pip install may use a different Python. Review python -m pip.',n)
                    value=line.strip().split('#',1)[0].strip()
                    if value.startswith('python-version:'):
                        value=value.split(':',1)[1].strip().strip("\"'")
                        if re.fullmatch(r'3\.\d+(?:\.\d+)?',value): versions.append((rel,n,value))
                continue
            try: data=jsonc(text)
            except (ValueError,RecursionError) as e:
                emit(rel,'PD000','Invalid JSONC: '+str(e),severity='error'); continue
            if not isinstance(data,dict):
                emit(rel,'PD000','Expected a JSON object.',severity='error'); continue
            def walk(obj,depth=0):
                if depth>60: raise ValueError('Nesting limit exceeded')
                if isinstance(obj,dict):
                    for key,value in obj.items():
                        pos=text.find(json.dumps(key)); line=text[:max(pos,0)].count('\n')+1
                        if key in ('python','pythonPath','python.defaultInterpreterPath') and isinstance(value,str):
                            refs.append((rel,line,key,value))
                            if key=='pythonPath': emit(rel,'PD004','Legacy pythonPath configuration; review migration.',line)
                        if key=='command' and isinstance(value,str) and re.match(r'^\s*pip(?:3|\.exe)?(?:\s|$)',value):
                            emit(rel,'PD003','Task uses bare pip; review explicit Python with -m pip.',line)
                        walk(value,depth+1)
                elif isinstance(obj,list):
                    for value in obj: walk(value,depth+1)
            walk(data)
        except (OSError,UnicodeError,ValueError,RecursionError) as e:
            skipped.append(dict(file=rel,reason=str(e)))
    explicit=[]
    for rel,line,key,value in refs:
        if value in ('python','python3','${command:python.interpreterPath}'): continue
        explicit.append((rel,line,key,value))
        expanded=value.replace('${workspaceFolder}',str(root))
        if '${' in expanded or expanded.startswith('~'): continue
        foreign=os.name!='nt' and PureWindowsPath(expanded).is_absolute()
        if not foreign and Path(expanded).is_absolute() and not Path(expanded).exists():
            emit(rel,'PD002','Absolute Python path is missing on this host.',line,evidence={'key':key,'value':value})
    defaults=[x for x in explicit if x[2]=='python.defaultInterpreterPath']
    for rel,line,key,value in explicit:
        if key not in ('python','pythonPath') or not rel.endswith('launch.json'): continue
        for source,_,_,default in defaults:
            if norm(value,root)!=norm(default,root):
                emit(rel,'PD001','Debugger path differs from editor default. May be intentional; active interpreter not observed.',line,evidence={'debugger':value,'default':default,'source':source})
    local=[x for x in versions if x[0]=='.python-version']
    for rel,line,value in versions:
        if rel=='.python-version': continue
        for _,_,expected in local:
            if value.split('.')[:2]!=expected.split('.')[:2]:
                emit(rel,'PD005','CI major/minor differs from .python-version; may be an intentional compatibility test.',line,evidence={'ci':value,'local':expected})
    findings.sort(key=lambda x:(x['file'],x['line'],x['rule'],x['fingerprint']))
    return dict(schema_version=1,tool='PyDrift',version='0.2.0',files_scanned=len(inputs),inputs=inputs,findings=findings,skipped=skipped,limitations=[
        'Static review signals, not proof of runtime failure.',
        'No active interpreter, terminal, notebook or remote-state inspection.',
        'Workflow checks are lexical; YAML matrices and shell semantics are not resolved.',
        'Key locations use first matching key; maximum 200 named configuration files, 512 KiB each.',
        'Reports may contain private configuration paths. No code execution or automatic fixes.'
    ])

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('workspace')
    p.add_argument('--fail-on',choices=['never','error','warning'],default='never');args=p.parse_args()
    try: result=audit(args.workspace)
    except (ValueError,OSError) as e: print(str(e),file=sys.stderr);return 2
    print(json.dumps(result,ensure_ascii=True))
    levels={'error'} if args.fail_on=='error' else {'error','warning'}
    return int(args.fail_on!='never' and any(f['severity'] in levels for f in result['findings']))
if __name__=='__main__':
    if sys.version_info<(3,10): raise SystemExit('Python 3.10+ required')
    raise SystemExit(main())
