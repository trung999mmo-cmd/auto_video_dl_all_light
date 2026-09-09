from __future__ import annotations
import asyncio, json, os, re, shutil, subprocess, sys, tempfile, time, wave
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Tuple

LogFn = Callable[[str], None]

LANGUAGES = {
    "Tiếng Việt":"vi-VN", "English":"en-US", "日本語":"ja-JP", "한국어":"ko-KR",
    "中文":"zh-CN", "ไทย":"th-TH", "Français":"fr-FR", "Deutsch":"de-DE",
    "Español":"es-ES", "Indonesia":"id-ID", "Português":"pt-BR", "Italiano":"it-IT",
    "Русский":"ru-RU", "العربية":"ar-SA", "हिन्दी":"hi-IN"
}

EDGE_VOICES = {
    "vi-VN-HoaiMyNeural":"Nữ Việt - Hoài My", "vi-VN-NamMinhNeural":"Nam Việt - Nam Minh",
    "en-US-AriaNeural":"US Nữ - Aria", "en-US-GuyNeural":"US Nam - Guy",
    "en-US-JennyNeural":"US Nữ - Jenny", "en-US-DavisNeural":"US Nam - Davis",
    "en-GB-SoniaNeural":"UK Nữ - Sonia", "en-GB-RyanNeural":"UK Nam - Ryan",
    "ja-JP-NanamiNeural":"Nhật Nữ - Nanami", "ja-JP-KeitaNeural":"Nhật Nam - Keita",
    "ko-KR-SunHiNeural":"Hàn Nữ - SunHi", "ko-KR-InJoonNeural":"Hàn Nam - InJoon",
    "zh-CN-XiaoxiaoNeural":"Trung Nữ - Xiaoxiao", "zh-CN-YunxiNeural":"Trung Nam - Yunxi",
    "th-TH-PremwadeeNeural":"Thái Nữ - Premwadee", "th-TH-NiwatNeural":"Thái Nam - Niwat",
    "fr-FR-DeniseNeural":"Pháp Nữ - Denise", "fr-FR-HenriNeural":"Pháp Nam - Henri",
    "de-DE-KatjaNeural":"Đức Nữ - Katja", "de-DE-ConradNeural":"Đức Nam - Conrad",
    "es-ES-ElviraNeural":"TBN Nữ - Elvira", "es-ES-AlvaroNeural":"TBN Nam - Alvaro",
    "id-ID-GadisNeural":"Indonesia Nữ - Gadis", "id-ID-ArdiNeural":"Indonesia Nam - Ardi",
    "pt-BR-FranciscaNeural":"Brazil Nữ - Francisca", "pt-BR-AntonioNeural":"Brazil Nam - Antonio",
    "it-IT-ElsaNeural":"Ý Nữ - Elsa", "it-IT-DiegoNeural":"Ý Nam - Diego",
    "ru-RU-SvetlanaNeural":"Nga Nữ - Svetlana", "ru-RU-DmitryNeural":"Nga Nam - Dmitry",
    "ar-SA-ZariyahNeural":"Ả Rập Nữ - Zariyah", "ar-SA-HamedNeural":"Ả Rập Nam - Hamed",
    "hi-IN-SwaraNeural":"Hindi Nữ - Swara", "hi-IN-MadhurNeural":"Hindi Nam - Madhur",
}

@dataclass
class Segment:
    src_start: float
    src_end: float
    out_start: float
    out_end: float


def resource_path(name: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / name


def find_bin(name: str) -> str:
    exe = name + (".exe" if os.name == "nt" else "")
    bundled = resource_path(exe)
    if bundled.exists(): return str(bundled)
    hit = shutil.which(name) or shutil.which(exe)
    if hit: return hit
    raise FileNotFoundError(f"Không tìm thấy {exe}. Hãy đặt cạnh tool hoặc cài FFmpeg.")


def run(cmd: List[str], log: LogFn = print) -> None:
    log("$ " + " ".join(f'\"{x}\"' if ' ' in x else x for x in cmd))
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", creationflags=(0x08000000 if os.name=="nt" else 0))
    assert p.stdout
    for line in p.stdout:
        t=line.rstrip()
        if t: log(t)
    if p.wait()!=0: raise RuntimeError(f"Lệnh lỗi mã {p.returncode}")


def duration(path: str) -> float:
    ffprobe=find_bin("ffprobe")
    out=subprocess.check_output([ffprobe,"-v","error","-show_entries","format=duration","-of","default=nw=1:nk=1",path], text=True, creationflags=(0x08000000 if os.name=="nt" else 0))
    return float(out.strip())


def build_segments(total: float, keep: float, drop: float) -> List[Segment]:
    if keep<=0 or drop<0: raise ValueError("Giữ phải > 0 và bỏ phải >= 0")
    segs=[]; src=0.0; out=0.0
    while src < total-0.02:
        end=min(src+keep,total)
        if end-src>0.03:
            segs.append(Segment(src,end,out,out+(end-src)))
            out += end-src
        src += keep+drop
    return segs


def save_map(segs: List[Segment], path: str):
    data={"version":1,"segments":[s.__dict__ for s in segs]}
    Path(path).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")


def fmt_srt(sec: float)->str:
    ms=max(0,int(round(sec*1000))); h,ms=divmod(ms,3600000); m,ms=divmod(ms,60000); s,ms=divmod(ms,1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def template_srt(segs: List[Segment], path: str):
    rows=[]
    for i,s in enumerate(segs,1):
        rows += [str(i),f"{fmt_srt(s.out_start)} --> {fmt_srt(s.out_end)}",f"[Đoạn {i}]",""]
    Path(path).write_text("\n".join(rows),encoding="utf-8")


def cut_video(input_path: str, output_path: str, segs: List[Segment], log: LogFn=print):
    ffmpeg=find_bin("ffmpeg")
    temp=Path(tempfile.mkdtemp(prefix="recap_segments_"))
    try:
        parts=[]
        for i,s in enumerate(segs):
            p=temp/f"seg_{i:05}.mp4"
            run([ffmpeg,"-y","-ss",f"{s.src_start:.3f}","-to",f"{s.src_end:.3f}","-i",input_path,"-map","0:v:0","-map","0:a?","-c:v","libx264","-preset","veryfast","-crf","20","-c:a","aac","-b:a","160k","-movflags","+faststart",str(p)],log)
            parts.append(p)
        lst=temp/"concat.txt"
        lst.write_text("\n".join("file '"+str(p).replace("'","'\\''")+"'" for p in parts),encoding="utf-8")
        run([ffmpeg,"-y","-f","concat","-safe","0","-i",str(lst),"-c","copy",output_path],log)
    finally:
        shutil.rmtree(temp,ignore_errors=True)


def parse_srt(text: str)->List[Tuple[float,float,str]]:
    text=text.replace("\r\n","\n").strip()
    blocks=re.split(r"\n\s*\n",text)
    out=[]
    rx=re.compile(r"(\d{2}):(\d{2}):(\d{2})[,.](\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})[,.](\d{3})")
    for b in blocks:
        lines=[x.strip() for x in b.splitlines() if x.strip()]
        ti=next((i for i,x in enumerate(lines) if "-->" in x),None)
        if ti is None: continue
        m=rx.search(lines[ti])
        if not m: continue
        a=list(map(int,m.groups()))
        st=a[0]*3600+a[1]*60+a[2]+a[3]/1000; en=a[4]*3600+a[5]*60+a[6]+a[7]/1000
        body=" ".join(lines[ti+1:]).strip()
        if body: out.append((st,en,body))
    return out


def normalize_srt(text: str, max_duration: float|None=None)->str:
    rows=[]
    for i,(st,en,body) in enumerate(parse_srt(text),1):
        if max_duration is not None:
            st=min(st,max_duration); en=min(en,max_duration)
        if en<=st: continue
        rows += [str(i),f"{fmt_srt(st)} --> {fmt_srt(en)}",body,""]
    return "\n".join(rows).strip()+"\n"


def gemini_api_srt(video_path: str, api_key: str, model: str, language: str, note: str, density: str, log: LogFn=print)->str:
    import google.generativeai as genai
    genai.configure(api_key=api_key.strip())
    log("Đang upload video lên Gemini API...")
    f=genai.upload_file(video_path)
    while getattr(f,"state",None) and getattr(f.state,"name","")=="PROCESSING":
        time.sleep(3); f=genai.get_file(f.name); log("Gemini đang xử lý video...")
    if getattr(getattr(f,"state",None),"name","")=="FAILED": raise RuntimeError("Gemini xử lý file thất bại")
    density_hint={"Ít chữ":"ngắn gọn, ít câu","Vừa":"mật độ vừa phải","Nhiều chữ":"chi tiết, nhiều lời dẫn"}.get(density,density)
    prompt=f"""Hãy xem toàn bộ video và viết lời thuyết minh recap bằng {language}.
Yêu cầu: trả về DUY NHẤT SRT hợp lệ, timeline bám nội dung hình ảnh, không Markdown, không ```.
Mức lời: {density_hint}. Không bịa chi tiết không thấy/nghe được trong video.
Ghi chú thêm: {note or 'không có'}"""
    log(f"Đang gọi model {model}...")
    res=genai.GenerativeModel(model).generate_content([f,prompt],request_options={"timeout":1800})
    txt=(res.text or "").strip(); txt=re.sub(r"^```(?:srt)?\s*|\s*```$","",txt,flags=re.I|re.S)
    return txt


async def _edge_save(text: str, voice: str, path: str, rate: str="+0%"):
    import edge_tts
    await edge_tts.Communicate(text,voice,rate=rate).save(path)


def srt_to_wav_edge(srt_path: str, wav_path: str, voice: str, log: LogFn=print):
    ffmpeg=find_bin("ffmpeg"); items=parse_srt(Path(srt_path).read_text(encoding="utf-8-sig"))
    if not items: raise ValueError("SRT không có câu hợp lệ")
    tmp=Path(tempfile.mkdtemp(prefix="recap_tts_")); clips=[]
    try:
        for i,(st,en,text) in enumerate(items):
            mp3=tmp/f"tts_{i:05}.mp3"; wav=tmp/f"tts_{i:05}.wav"
            log(f"TTS {i+1}/{len(items)}: {text[:70]}")
            asyncio.run(_edge_save(text,voice,str(mp3)))
            target=max(0.25,en-st)
            actual=duration(str(mp3)); ratio=actual/target
            filters=[]
            # atempo supports 0.5..2 per stage
            while ratio>2.0: filters.append("atempo=2.0"); ratio/=2.0
            while ratio<0.5: filters.append("atempo=0.5"); ratio/=0.5
            filters.append(f"atempo={ratio:.5f}")
            delay=int(st*1000)
            af=",".join(filters)+f",adelay={delay}|{delay}"
            run([ffmpeg,"-y","-i",str(mp3),"-af",af,"-ac","2","-ar","44100",str(wav)],lambda x:None)
            clips.append(wav)
        cmd=[ffmpeg,"-y"]
        for c in clips: cmd += ["-i",str(c)]
        cmd += ["-filter_complex",f"amix=inputs={len(clips)}:normalize=0:dropout_transition=0","-ac","2","-ar","44100",wav_path]
        run(cmd,log)
    finally: shutil.rmtree(tmp,ignore_errors=True)


def mix_video_audio(video_path: str, wav_path: str, output_path: str, keep_original: bool=True, original_volume: float=0.12, log: LogFn=print):
    ffmpeg=find_bin("ffmpeg")
    if keep_original:
        fc=f"[0:a]volume={original_volume}[a0];[a0][1:a]amix=inputs=2:duration=first:normalize=0[a]"
        run([ffmpeg,"-y","-i",video_path,"-i",wav_path,"-filter_complex",fc,"-map","0:v:0","-map","[a]","-c:v","copy","-c:a","aac","-b:a","192k","-shortest",output_path],log)
    else:
        run([ffmpeg,"-y","-i",video_path,"-i",wav_path,"-map","0:v:0","-map","1:a:0","-c:v","copy","-c:a","aac","-b:a","192k","-shortest",output_path],log)


def split_for_web(video_path: str, minutes: int, out_dir: str, log: LogFn=print)->List[str]:
    ffmpeg=find_bin("ffmpeg"); Path(out_dir).mkdir(parents=True,exist_ok=True)
    pattern=str(Path(out_dir)/"chunk_%03d.mp4")
    run([ffmpeg,"-y","-i",video_path,"-map","0","-c","copy","-f","segment","-segment_time",str(minutes*60),"-reset_timestamps","1",pattern],log)
    return [str(p) for p in sorted(Path(out_dir).glob("chunk_*.mp4"))]


def shift_srt(text: str, offset: float)->str:
    rows=[]
    for i,(st,en,body) in enumerate(parse_srt(text),1): rows += [str(i),f"{fmt_srt(st+offset)} --> {fmt_srt(en+offset)}",body,""]
    return "\n".join(rows)


def web_ai_srt(video_path: str, provider: str, language: str, note: str, density: str, wait_seconds: int, profile_dir: str|None, log: LogFn=print)->str:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    opts=webdriver.ChromeOptions(); opts.add_argument("--start-maximized")
    if profile_dir: opts.add_argument(f"--user-data-dir={profile_dir}")
    driver=webdriver.Chrome(options=opts)
    url="https://gemini.google.com/app" if provider.lower().startswith("gemini") else "https://chatgpt.com/"
    prompt=f"""Xem video đã tải lên và tạo SRT lời thuyết minh recap bằng {language}. Chỉ trả SRT, không Markdown. Timeline phải bám đúng video. Mức lời: {density}. Ghi chú: {note or 'không có'}."""
    try:
        driver.get(url); log("Chrome đã mở. Nếu cần, hãy đăng nhập trong cửa sổ này.")
        time.sleep(4)
        # Try common file inputs. Sites can change, so this deliberately has fallbacks.
        inputs=driver.find_elements(By.CSS_SELECTOR,"input[type='file']")
        if not inputs:
            for sel in ["button[aria-label*='Upload']","button[aria-label*='Tải']","button[aria-label*='Add']","button[aria-label*='Thêm']"]:
                els=driver.find_elements(By.CSS_SELECTOR,sel)
                if els:
                    els[0].click(); time.sleep(1); break
            inputs=driver.find_elements(By.CSS_SELECTOR,"input[type='file']")
        if not inputs: raise RuntimeError("Không tìm thấy nút upload. Website có thể đã đổi giao diện.")
        inputs[-1].send_keys(os.path.abspath(video_path)); log("Đã gửi video, đang chờ upload..."); time.sleep(8)
        candidates=["textarea","div[contenteditable='true']","rich-textarea div[contenteditable='true']"]
        box=None
        for s in candidates:
            els=driver.find_elements(By.CSS_SELECTOR,s)
            if els: box=els[-1]; break
        if box is None: raise RuntimeError("Không tìm thấy ô nhập prompt")
        box.click(); box.send_keys(prompt); box.send_keys(Keys.ENTER); log("Đã gửi prompt, đang chờ phản hồi...")
        end=time.time()+wait_seconds; last=""
        while time.time()<end:
            time.sleep(5)
            texts=[]
            for s in [".markdown","message-content","model-response","[data-message-author-role='assistant']"]:
                for e in driver.find_elements(By.CSS_SELECTOR,s):
                    t=e.text.strip()
                    if "-->" in t: texts.append(t)
            if texts:
                cur=max(texts,key=len)
                if cur==last and len(cur)>40: return re.sub(r"^```(?:srt)?\s*|\s*```$","",cur,flags=re.I|re.S)
                last=cur
        if last: return last
        raise TimeoutError("Hết thời gian chờ nhưng chưa lấy được SRT")
    finally:
        try: driver.quit()
        except Exception: pass
