"""Shared-reference audio alignment; positive offset means the second file is late."""
import json
import wave
from pathlib import Path
import numpy as np

def _match(reference, other, rate, start, window_ms):
    size = round(window_ms * rate / 1000)
    a = np.asarray(reference[start:start+size], dtype=np.float64)
    b = np.asarray(other[start:start+size], dtype=np.float64)
    if min(len(a),len(b)) < size:
        return None, 0.0
    a -= a.mean(); b -= b.mean()
    if min(np.linalg.norm(a),np.linalg.norm(b)) < 1e-8:
        return None, 0.0
    # A few isolated peaks are not evidence of matching speech.
    if min(np.mean(np.abs(a)>np.max(np.abs(a))*0.02), np.mean(np.abs(b)>np.max(np.abs(b))*0.02)) < 0.04:
        return None, 0.0
    n = 1 << (2*size-1).bit_length()
    c = np.fft.irfft(np.fft.rfft(b,n)*np.conj(np.fft.rfft(a,n)),n)
    lag = min(round(0.5*rate), size//3)
    offsets = np.arange(-lag,lag+1)
    scores = c[offsets % n] / (np.linalg.norm(a)*np.linalg.norm(b))
    best = int(np.argmax(scores))
    confidence = float(scores[best])
    return round(int(offsets[best])*1000/rate), confidence

def measure_buffers(reference, other, rate, window_ms=2000):
    length = min(len(reference),len(other))
    size = round(window_ms*rate/1000)
    head,hc = _match(reference,other,rate,0,window_ms)
    tail,tc = _match(reference,other,rate,max(0,length-size),window_ms)
    return assess(head,tail,hc,tc,min_confidence=0.65)

def assess(head_offset_ms, tail_offset_ms, head_confidence, tail_confidence, drift_limit_ms=40, min_confidence=0.65):
    reasons=[]
    if head_offset_ms is None or head_confidence is None or head_confidence<min_confidence:
        reasons.append("开头相关性不足")
    if tail_offset_ms is None or tail_confidence is None or tail_confidence<min_confidence:
        reasons.append("尾部相关性不足")
    if head_offset_ms is not None and tail_offset_ms is not None and abs(tail_offset_ms-head_offset_ms)>drift_limit_ms:
        reasons.append("尾部漂移超过 %d ms" % drift_limit_ms)
    return {"head_offset_ms":head_offset_ms,"tail_offset_ms":tail_offset_ms,
            "tail_drift_ms":None if head_offset_ms is None or tail_offset_ms is None else tail_offset_ms-head_offset_ms,
            "head_confidence":head_confidence,"tail_confidence":tail_confidence,
            "needs_human":bool(reasons),"completed":not reasons,"reasons":reasons,"atempo":1}

def read_wav(path):
    with wave.open(str(path),"rb") as f:
        if f.getsampwidth()!=2:
            raise ValueError("sync expects PCM16 WAV")
        channels,rate=f.getnchannels(),f.getframerate()
        a=np.frombuffer(f.readframes(f.getnframes()),dtype="<i2").astype(np.float64)
    return a.reshape(-1,channels).mean(axis=1).tolist(),rate

def write_status(path,payload):
    Path(path).write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8",newline="\n")
