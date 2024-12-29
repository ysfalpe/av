import datetime

def format_timestamp(seconds: float, format_type: str = "srt") -> str:
    """Saniye cinsinden zamanı SRT veya VTT formatına dönüştür"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    msecs = int((seconds - int(seconds)) * 1000)
    
    if format_type == "srt":
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{msecs:03d}"
    else:  # vtt
        return f"{hours:02d}:{minutes:02d}:{secs:02d}.{msecs:03d}"

def create_srt(subtitles: list) -> str:
    """Alt yazıları SRT formatına dönüştür"""
    srt_content = []
    for i, sub in enumerate(subtitles, 1):
        start = format_timestamp(sub["start"])
        end = format_timestamp(sub["end"])
        text = sub["text"]
        color = sub.get("color", "white")  # Varsayılan renk beyaz
        
        # SRT formatında renk için HTML tag'leri kullan
        srt_content.append(f"{i}\n{start} --> {end}\n<font color='{color}'>{text}</font>\n")
    
    return "\n".join(srt_content)

def create_vtt(subtitles: list) -> str:
    """Alt yazıları VTT formatına dönüştür"""
    vtt_content = ["WEBVTT\n"]
    for i, sub in enumerate(subtitles, 1):
        start = format_timestamp(sub["start"], "vtt")
        end = format_timestamp(sub["end"], "vtt")
        text = sub["text"]
        color = sub.get("color", "white")  # Varsayılan renk beyaz
        
        # VTT formatında renk için CSS kullan
        vtt_content.append(f"cue-{i}\n{start} --> {end}\n<c.{color}>{text}</c>\n")
    
    return "\n".join(vtt_content)

def adjust_timing(subtitles: list, offset: float) -> list:
    """Alt yazı zamanlamasını ayarla"""
    adjusted = []
    for sub in subtitles:
        adjusted.append({
            "start": max(0, sub["start"] + offset),
            "end": max(0, sub["end"] + offset),
            "text": sub["text"],
            "color": sub.get("color", "white")
        })
    return adjusted

def merge_nearby_subtitles(subtitles: list, threshold: float = 0.3) -> list:
    """Yakın zamanlı alt yazıları birleştir"""
    if not subtitles:
        return []
        
    merged = []
    current = subtitles[0].copy()
    
    for next_sub in subtitles[1:]:
        if next_sub["start"] - current["end"] <= threshold:
            current["end"] = next_sub["end"]
            current["text"] = f"{current['text']} {next_sub['text']}"
        else:
            merged.append(current)
            current = next_sub.copy()
    
    merged.append(current)
    return merged 