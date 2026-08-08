#!/usr/bin/env python3
from __future__ import annotations
import argparse, base64, hashlib, html, json, re, shutil
from pathlib import Path

SECRET_PATTERNS = [
    re.compile(r'(?i)(?<![A-Za-z0-9_])(?:sk|rk|pk|api|xai)[-_][A-Za-z0-9_-]{16,}'),
    re.compile(r'(?i)gh[pousr]_[A-Za-z0-9]{20,}'),
    re.compile(r'AIza[0-9A-Za-z_-]{35}'),
    re.compile(r'AKIA[0-9A-Z]{16}'),
    re.compile(r'(?i)(authorization[ \t]*:[ \t]*bearer[ \t]+)[^\s"\']+'),
    re.compile(r"(?ix)([\"']?(?:api[_-]?key|apikey|oauth[_-]?token|access[_-]?token|refresh[_-]?token|client[_-]?secret|secret|password|cookie)[\"']?[ \\t]*[=:][ \\t]*[\"']?)[^\\s,;\"'}]+"),
    re.compile(r'(?is)-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----.*?-----END (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
]
UUID = re.compile(r'(?i)\b[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b')
EMAIL = re.compile(r'(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b')
WIN_PATH = re.compile(r'(?<![A-Za-z0-9_])(?:[A-Za-z]:\\(?:[^\r\n\t"<>|]+))')
HOME_PATH = re.compile(r'(?<![A-Za-z0-9_])/(?:home|Users)/[^/\s"\']+(?:/[^\r\n\t"\']*)?')
RESPONSE = re.compile(r'(?i)\b(?:resp|response|call|msg)_(?=[A-Za-z0-9_-]{8,}\b)(?=[A-Za-z0-9_-]*[0-9])[A-Za-z0-9_-]{8,}\b')

class Redactor:
    def __init__(self): self.counts={}; self.maps={}
    def token(self, kind, value):
        table=self.maps.setdefault(kind,{})
        if value not in table: table[value]=f'[{kind}:{hashlib.sha256(value.encode("utf-8",errors="replace")).hexdigest()[:12]}]'
        self.counts[kind]=self.counts.get(kind,0)+1
        return table[value]
    def text(self, value):
        s=str(value)
        for p in SECRET_PATTERNS:
            def secret(m):
                self.counts['SECRET']=self.counts.get('SECRET',0)+1
                return (m.group(1) if m.lastindex else '')+'[REDACTED_SECRET]'
            s=p.sub(secret,s)
        s=EMAIL.sub(lambda m: m.group(0) if m.group(0).lower().endswith('@example.invalid') else self.token('EMAIL',m.group(0)),s)
        s=WIN_PATH.sub(lambda m:self.token('PATH',m.group(0)),s)
        s=HOME_PATH.sub(lambda m:self.token('PATH',m.group(0)),s)
        s=UUID.sub(lambda m:self.token('UUID',m.group(0)),s)
        s=RESPONSE.sub(lambda m:self.token('RESPONSE',m.group(0)),s)
        return s
    def value(self, obj):
        if isinstance(obj,str): return self.text(obj)
        if isinstance(obj,list): return [self.value(x) for x in obj]
        if isinstance(obj,dict): return {k:self.value(v) for k,v in obj.items()}
        return obj

def redact_html(data, r):
    text=data.decode('utf-8',errors='strict')
    pattern=re.compile(r'(<script\s+id=["\']session-data["\']\s+type=["\']application/json["\']>)(.*?)(</script>)',re.S|re.I)
    m=pattern.search(text)
    if m:
        decoded=base64.b64decode(m.group(2).strip(),validate=True)
        obj=json.loads(decoded)
        payload=base64.b64encode(json.dumps(r.value(obj),ensure_ascii=False,separators=(',',':')).encode()).decode()
        text=text[:m.start()]+m.group(1)+payload+m.group(3)+text[m.end():]
    return r.text(text).encode('utf-8')

def scan_secret(text):
    # Do not classify the redactor's own explicit placeholder as residual
    # credential material.  Removing the placeholder leaves separators such as
    # `oauth_token=` or `Authorization: Bearer` without a value, which the
    # credential patterns correctly do not match.
    scrubbed = text.replace('[REDACTED_SECRET]', '')
    return any(p.search(scrubbed) for p in SECRET_PATTERNS)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--input',required=True); ap.add_argument('--output',required=True); ap.add_argument('--report',required=True)
    a=ap.parse_args(); src=Path(a.input).resolve(); dst=Path(a.output).resolve()
    if dst.exists(): raise SystemExit(f'output exists: {dst}')
    dst.mkdir(parents=True); r=Redactor(); files=[]; residual=[]
    text_ext={'.json','.jsonl','.md','.txt','.csv','.yaml','.yml','.toml','.log','.ps1','.py','.mjs','.js','.html','.htm'}
    for p in sorted(x for x in src.rglob('*') if x.is_file()):
        rel=p.relative_to(src); out=dst/rel; out.parent.mkdir(parents=True,exist_ok=True); raw=p.read_bytes()
        if p.suffix.lower() in {'.html','.htm'}: data=redact_html(raw,r)
        elif p.suffix.lower() in text_ext:
            data=r.text(raw.decode('utf-8-sig',errors='strict')).encode('utf-8')
        else: data=raw
        out.write_bytes(data)
        if p.suffix.lower() in text_ext and scan_secret(data.decode('utf-8',errors='replace')): residual.append(rel.as_posix())
        files.append({'path':rel.as_posix(),'before_sha256':hashlib.sha256(raw).hexdigest(),'after_sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)})
    report={'schema':'bbk.alpha17-redaction-report.v1','status':'PASS' if not residual else 'FAIL','replacement_counts':dict(sorted(r.counts.items())),'files':files,'residual_secret_pattern_files':residual,'manual_inspection_required':True}
    Path(a.report).write_text(json.dumps(report,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps(report,sort_keys=True)); return 0 if report['status']=='PASS' else 1
if __name__=='__main__': raise SystemExit(main())
