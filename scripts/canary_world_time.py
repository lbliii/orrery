#!/usr/bin/env python3
"""Non-blocking public world-time + public-key signature canary."""
from __future__ import annotations
import argparse, ast, base64, json, sys, urllib.request
from datetime import UTC, datetime
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

def parse_envelope(text: str) -> dict[str, object]:
    node=ast.parse(text,mode="eval").body
    if not isinstance(node,ast.Call) or not isinstance(node.func,ast.Name) or node.func.id!="Envelope" or node.args:
        raise ValueError("expected Envelope keyword literal")
    return {keyword.arg:ast.literal_eval(keyword.value) for keyword in node.keywords if keyword.arg}

def request(url:str, body:bytes|None=None)->bytes:
    req=urllib.request.Request(url,data=body,headers={"Content-Type":"application/json"} if body else {})
    with urllib.request.urlopen(req,timeout=15) as response:return response.read()

def verify(envelope:dict[str,object], keys:dict[str,object])->None:
    kid=str(envelope["key_id"]); jwk=next(item for item in keys["keys"] if item["kid"]==kid)
    fields={name:envelope[name] for name in ("payload","skill","version","tool","nonce","input_digest","key_id","alg")}
    message=json.dumps(fields,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
    raw=base64.urlsafe_b64decode(str(jwk["x"])+"="*(-len(str(jwk["x"]))%4))
    Ed25519PublicKey.from_public_bytes(raw).verify(base64.b64decode(str(envelope["signature"])),message)

def run(origin:str)->None:
    payload={"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"fetch","arguments":{}}}
    wire=json.loads(request(origin+"/stars/world-time/mcp",json.dumps(payload).encode()))
    text=wire["result"]["content"][0]["text"]
    envelope=parse_envelope(text); verify(envelope,json.loads(request(origin+"/.well-known/orrery/keys.json")))
    value=envelope["payload"]
    if envelope["skill"]!="world-time" or envelope["tool"]!="fetch" or value["timezone"]!="UTC" or not value["live_at_call"]:raise ValueError("unexpected world-time receipt")
    when=datetime.fromisoformat(value["datetime"].replace("Z","+00:00"))
    if abs((datetime.now(UTC)-when).total_seconds())>900:raise ValueError("UTC response outside 15 minute skew")

if __name__=="__main__":
    parser=argparse.ArgumentParser(); parser.add_argument("--origin",default="https://orrery.lol")
    try: run(parser.parse_args().origin.rstrip("/"))
    except Exception as error: print(f"world-time canary failed: {error}",file=sys.stderr); raise
