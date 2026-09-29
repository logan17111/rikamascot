#!/usr/bin/env python3
import base64
import io
import json
import subprocess
from PIL import Image, ImageFilter


def get_focused_output() -> str:
    try:
        res = subprocess.run(
            ["niri", "msg", "-j", "focused-output"],
            capture_output=True,
            text=True,
            timeout=2
        )
        if res.returncode == 0 and res.stdout:
            data = json.loads(res.stdout)
            return data.get("name", "")
    except Exception:
        pass
    return ""


def get_smart_crop_b64(app_id: str = "", title: str = "") -> str:
    # 1. Capture brute en RAM (uniquement sur l'écran actif si détecté)
    output = get_focused_output()
    cmd = ["grim", "-o", output, "-t", "png", "-"] if output else ["grim", "-t", "png", "-"]
    res = subprocess.run(cmd, capture_output=True, timeout=5)
    if res.returncode != 0 or not res.stdout:
        return ""

    img = Image.open(io.BytesIO(res.stdout)).convert("RGB")
    w, h = img.size
    context = f"{app_id} {title}".lower()

    # 2. Découpage intelligent selon ce que tu fais
    if any(k in context for k in ["twitter", " / x", "x.com", "reddit"]):
        crop_box = (int(w * 0.28), int(h * 0.12), int(w * 0.68), int(h * 0.88))
        img = img.crop(crop_box)

    elif any(k in context for k in ["manga", "komga", "mangadex", "lecteur"]):
        crop_box = (int(w * 0.18), int(h * 0.08), int(w * 0.82), int(h * 0.95))
        img = img.crop(crop_box)

    else:
        base_crop = img.crop((int(w * 0.05), int(h * 0.06), int(w * 0.95), int(h * 0.94)))
        edges = base_crop.convert("L").filter(ImageFilter.FIND_EDGES)
        bbox = edges.point(lambda p: 255 if p > 40 else 0).getbbox()
        if bbox:
            img = base_crop.crop(bbox)
        else:
            img = base_crop

    # 3. Export en JPEG haute qualité pour l'IA
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return base64.b64encode(buf.getvalue()).decode("utf-8")