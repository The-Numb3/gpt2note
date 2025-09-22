import re

def build_weakness_hints(conversation: list[dict]) -> dict:
    patt_confuse = re.compile(r"(다시|무슨 뜻|헷갈|모르겠|why|explain|proof|example)", re.I)
    patt_ok = re.compile(r"(알겠|이해|오케이|clear|맞네)", re.I)
    confuse_turns, ok_turns = [], []
    for i, m in enumerate(conversation, start=1):
        if m["role"] == "user":
            t = m.get("content","")
            if patt_confuse.search(t): confuse_turns.append(i)
            if patt_ok.search(t): ok_turns.append(i)
    return {"confuse_turns": confuse_turns, "ok_turns": ok_turns}
