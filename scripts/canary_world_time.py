#!/usr/bin/env python3
"""Non-blocking public world-time + public-key signature canary."""
from __future__ import annotations
import argparse, ast, base64, json, sys, urllib.request
from datetime import UTC, datetime
from chirp.skill import Envelope, verify_envelope

REQUIRED = frozenset({"payload", "skill", "version", "tool", "nonce", "input_digest", "signature", "key_id", "alg"})

def parse_envelope(text: str) -> dict[str, object]:
    node=ast.parse(text,mode="eval").body
    if not isinstance(node,ast.Call) or not isinstance(node.func,ast.Name) or node.func.id!="Envelope" or node.args or any(keyword.arg is None for keyword in node.keywords):
        raise ValueError("expected Envelope keyword literal")
    result={keyword.arg:ast.literal_eval(keyword.value) for keyword in node.keywords}
    if set(result)!=REQUIRED: raise ValueError("unexpected Envelope fields")
    return result

def request(url:str, body:bytes|None=None)->bytes:
    req=urllib.request.Request(url,data=body,headers={"Content-Type":"application/json"} if body else {})
    with urllib.request.urlopen(req,timeout=15) as response:return response.read()

def verify(envelope:dict[str,object], keys:dict[str,object])->None:
    kid=str(envelope["key_id"]); jwk=next(item for item in keys["keys"] if item["kid"]==kid and item.get("star")=="orrery/world-time")
    raw=base64.urlsafe_b64decode(str(jwk["x"])+"="*(-len(str(jwk["x"]))%4))
    env=Envelope(**envelope)
    if not verify_envelope(env,raw): raise ValueError("invalid Envelope signature")

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
