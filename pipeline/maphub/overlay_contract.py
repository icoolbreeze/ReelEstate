"""Shared preflight rules for production room labels and annotation data."""
import math

def validate_overlay_contract(episode, hub, annotations):
    errors = []
    real = episode.get("sampleData") is not True
    labels = []
    for i, room in enumerate(hub.get("rooms", [])):
        labels.append(("hub.rooms[%d].label" % i, room.get("label", "")))
    for key, value in hub.get("clipTitles", {}).items():
        labels.append(("hub.clipTitles." + key, value))
    for cid, ann in annotations.items():
        for target in ann.get("targets", []):
            labels.append(("annotations.%s.%s.label" % (cid, target.get("id", "?")), target.get("label", "")))
            previous = None
            for row in target.get("kf", []):
                if len(row) < 5 or not all(isinstance(x, (int, float)) and math.isfinite(x) for x in row[:5]):
                    errors.append("invalid tracking keyframe: " + cid + "/" + target.get("id", "?"))
                    break
                if row[3] <= 0 or row[4] <= 0 or previous is not None and row[0] <= previous:
                    errors.append("tracking times must increase and boxes must be positive: " + cid + "/" + target.get("id", "?"))
                    break
                previous = row[0]
    if real:
        for field, text in labels:
            if any(word in str(text) for word in ("样板间", "示例房源", "模拟房源")):
                errors.append("real listing has a demo room label: " + field)
    return errors
