from __future__ import annotations
import json, os, queue, threading, traceback
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from recap_core import *

APP_NAME="Video Recap Cutter"
CFG=Path.home()/".video_recap_cutter.json"

class App(tk.Tk):
    def __init__(self):
        super().__init__(); self.title(APP_NAME); self.geometry("1180x850"); self.minsize(1050,760)
        self.q=queue.Queue(); self.cfg=self.load_cfg(); self.vars={}
        self.style=ttk.Style(self); 
        try: self.style.theme_use("vista")
        except: pass
        self.build(); self.after(100,self.flush_log)

    def load_cfg(self):
        try: return json.loads(CFG.read_text(encoding="utf-8"))
        except: return {}
    def save_cfg(self):
        d={k:v.get() for k,v in self.vars.items() if k not in {"api_keys","sessionid"}}
        # secrets only saved if user explicitly ticks options
        if self.vars["save_api"].get(): d["api_keys"]=self.vars["api_keys"].get()
        if self.vars["save_session"].get(): d["sessionid"]=self.vars["sessionid"].get()
        try: CFG.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding="utf-8")
        except: pass
    def V(self,name,default=""):
        val=self.cfg.get(name,default); v=tk.StringVar(value=val); self.vars[name]=v; return v
    def B(self,name,default=False):
        val=self.cfg.get(name,default); v=tk.BooleanVar(value=val); self.vars[name]=v; return v
    def add_row(self,parent,label,var,browse=None,width=82):
        r=ttk.Frame(parent); r.pack(fill="x",padx=8,pady=3)
        ttk.Label(r,text=label,width=24).pack(side="left")
        ttk.Entry(r,textvariable=var,width=width).pack(side="left",fill="x",expand=True)
        if browse: ttk.Button(r,text=browse[0],command=browse[1],width=14).pack(side="left",padx=(6,0))
        return r
    def build(self):
        top=ttk.Frame(self); top.pack(fill="x",padx=10,pady=(8,2))
        ttk.Label(top,text="VIDEO RECAP CUTTER",font=("Segoe UI",20,"bold")).pack(side="left")
        ttk.Label(top,text="Clean-room Windows build",font=("Segoe UI",10)).pack(side="left",padx=12)
        self.tabs=ttk.Notebook(self); self.tabs.pack(fill="both",expand=True,padx=10,pady=6)
        self.tab_main=ttk.Frame(self.tabs); self.tab_ai=ttk.Frame(self.tabs); self.tab_tts=ttk.Frame(self.tabs); self.tab_log=ttk.Frame(self.tabs)
        self.tabs.add(self.tab_main,text="1. Video và cắt"); self.tabs.add(self.tab_ai,text="2. SRT AI"); self.tabs.add(self.tab_tts,text="3. Giọng đọc"); self.tabs.add(self.tab_log,text="Log")
        self.build_main(); self.build_ai(); self.build_tts(); self.build_log()
        foot=ttk.Frame(self); foot.pack(fill="x",padx=10,pady=(0,10))
        self.status=tk.StringVar(value="Sẵn sàng")
        ttk.Label(foot,textvariable=self.status).pack(side="left")
        ttk.Button(foot,text="CẮT VIDEO / TẠO RECAP",command=self.run_pipeline,width=28).pack(side="right")

    def build_main(self):
        f=ttk.LabelFrame(self.tab_main,text="Video và đầu ra"); f.pack(fill="x",padx=10,pady=10)
        self.add_row(f,"Video gốc",self.V("input_video"), ("Chọn video",self.pick_video))
        self.add_row(f,"Video recap",self.V("recap_video"), ("Chọn nơi lưu",lambda:self.pick_save("recap_video","MP4","*.mp4")))
        self.add_row(f,"Map JSON",self.V("map_json"), ("Chọn",lambda:self.pick_save("map_json","JSON","*.json")))
        self.add_row(f,"SRT template",self.V("template_srt"), ("Chọn",lambda:self.pick_save("template_srt","SRT","*.srt")))
        cut=ttk.LabelFrame(self.tab_main,text="Nhịp cắt"); cut.pack(fill="x",padx=10,pady=5)
        r=ttk.Frame(cut); r.pack(fill="x",padx=8,pady=8)
        ttk.Label(r,text="Giữ (giây)").pack(side="left"); ttk.Entry(r,textvariable=self.V("keep_sec","2"),width=10).pack(side="left",padx=5)
        ttk.Label(r,text="Bỏ (giây)").pack(side="left",padx=(20,0)); ttk.Entry(r,textvariable=self.V("drop_sec","8"),width=10).pack(side="left",padx=5)
        presets=ttk.Combobox(r,values=["Giữ 2 / Bỏ 8","Giữ 2 / Bỏ 10","Giữ 3 / Bỏ 7","Giữ 5 / Bỏ 5"],state="readonly",width=22); presets.set("Giữ 2 / Bỏ 8"); presets.pack(side="left",padx=20)
        presets.bind("<<ComboboxSelected>>",lambda e:self.set_preset(presets.get()))
        ttk.Checkbutton(cut,text="Tạo map JSON",variable=self.B("make_map",True)).pack(anchor="w",padx=10,pady=2)
        ttk.Checkbutton(cut,text="Tạo SRT template",variable=self.B("make_template",True)).pack(anchor="w",padx=10,pady=(0,8))

    def build_ai(self):
        f=ttk.LabelFrame(self.tab_ai,text="Nguồn tạo SRT"); f.pack(fill="x",padx=10,pady=10)
        r=ttk.Frame(f); r.pack(fill="x",padx=8,pady=7)
        ttk.Label(r,text="Chế độ",width=24).pack(side="left")
        cb=ttk.Combobox(r,textvariable=self.V("ai_mode","Gemini Web"),state="readonly",values=["Không tạo SRT","Gemini API","Gemini Web","ChatGPT Web - Nhanh","ChatGPT Web - 2 pass","ChatGPT Web - 3 pass","ChatGPT Web - 4 pass"],width=30); cb.pack(side="left")
        self.add_row(f,"SRT AI đầu ra",self.V("ai_srt"),("Chọn",lambda:self.pick_save("ai_srt","SRT","*.srt")))
        r=ttk.Frame(f); r.pack(fill="x",padx=8,pady=4); ttk.Label(r,text="Ngôn ngữ",width=24).pack(side="left")
        ttk.Combobox(r,textvariable=self.V("language","Tiếng Việt"),state="readonly",values=list(LANGUAGES.keys()),width=28).pack(side="left")
        ttk.Label(r,text="Mức lời").pack(side="left",padx=(20,5)); ttk.Combobox(r,textvariable=self.V("density","Vừa"),state="readonly",values=["Ít chữ","Vừa","Nhiều chữ"],width=12).pack(side="left")
        self.add_row(f,"Ghi chú gửi trợ lý",self.V("note"),width=82)
        api=ttk.LabelFrame(self.tab_ai,text="Gemini API"); api.pack(fill="x",padx=10,pady=5)
        self.add_row(api,"API key(s), cách nhau ;",self.V("api_keys"))
        r=ttk.Frame(api); r.pack(fill="x",padx=8,pady=5); ttk.Label(r,text="Model",width=24).pack(side="left"); ttk.Combobox(r,textvariable=self.V("gemini_model","gemini-2.5-pro"),values=["gemini-2.5-pro","gemini-2.5-flash","gemini-2.0-flash"],width=28).pack(side="left"); ttk.Checkbutton(r,text="Lưu API key trên máy",variable=self.B("save_api",False)).pack(side="left",padx=15)
        web=ttk.LabelFrame(self.tab_ai,text="Gemini / ChatGPT Web"); web.pack(fill="x",padx=10,pady=5)
        self.add_row(web,"Chrome user-data-dir",self.V("chrome_profile"),("Chọn thư mục",self.pick_profile))
        r=ttk.Frame(web); r.pack(fill="x",padx=8,pady=5); ttk.Label(r,text="Chunk video (phút)",width=24).pack(side="left"); ttk.Combobox(r,textvariable=self.V("chunk_min","20"),state="readonly",values=["10","15","20","25","30"],width=10).pack(side="left"); ttk.Label(r,text="Chờ phản hồi (giây)").pack(side="left",padx=(20,5)); ttk.Entry(r,textvariable=self.V("web_wait","600"),width=10).pack(side="left")
        ttk.Label(web,text="Web mode dùng Chrome thật. Nếu website đổi giao diện, xem Log để biết selector nào không còn hợp lệ.",foreground="#555").pack(anchor="w",padx=8,pady=(0,7))

    def build_tts(self):
        f=ttk.LabelFrame(self.tab_tts,text="Giọng đọc và audio"); f.pack(fill="x",padx=10,pady=10)
        r=ttk.Frame(f); r.pack(fill="x",padx=8,pady=5); ttk.Label(r,text="Hệ giọng",width=24).pack(side="left"); ttk.Combobox(r,textvariable=self.V("tts_engine","Edge TTS"),state="readonly",values=["Edge TTS","Piper local"],width=20).pack(side="left")
        r=ttk.Frame(f); r.pack(fill="x",padx=8,pady=5); ttk.Label(r,text="Giọng",width=24).pack(side="left"); self.voice_cb=ttk.Combobox(r,textvariable=self.V("voice","vi-VN-HoaiMyNeural"),values=list(EDGE_VOICES.keys()),width=38); self.voice_cb.pack(side="left"); ttk.Button(r,text="Nghe thử",command=self.preview_voice).pack(side="left",padx=8)
        self.add_row(f,"Audio WAV",self.V("wav_path"),("Chọn",lambda:self.pick_save("wav_path","WAV","*.wav")))
        self.add_row(f,"Video cuối",self.V("final_video"),("Chọn",lambda:self.pick_save("final_video","MP4","*.mp4")))
        r=ttk.Frame(f); r.pack(fill="x",padx=8,pady=5); ttk.Checkbutton(r,text="Giữ tiếng gốc nhỏ phía dưới",variable=self.B("keep_original_audio",True)).pack(side="left"); ttk.Label(r,text="Âm lượng gốc").pack(side="left",padx=(20,5)); ttk.Entry(r,textvariable=self.V("original_volume","0.12"),width=8).pack(side="left")
        sess=ttk.LabelFrame(self.tab_tts,text="TikTok session (tùy chọn / tương thích về sau)"); sess.pack(fill="x",padx=10,pady=5)
        self.add_row(sess,"TikTok session ID",self.V("sessionid"))
        ttk.Checkbutton(sess,text="Lưu session ID trên máy này",variable=self.B("save_session",False)).pack(anchor="w",padx=10,pady=(0,7))
        ttk.Label(sess,text="Không chia sẻ session ID cho người khác. Phiên bản hiện tại không gửi session ID ra ngoài.",foreground="#555").pack(anchor="w",padx=10,pady=(0,7))

    def build_log(self):
        self.logbox=tk.Text(self.tab_log,wrap="word",font=("Consolas",10)); self.logbox.pack(fill="both",expand=True,padx=10,pady=10)
    def log(self,s): self.q.put(str(s))
    def flush_log(self):
        try:
            while True:
                s=self.q.get_nowait(); self.logbox.insert("end",s+"\n"); self.logbox.see("end")
        except queue.Empty: pass
        self.after(100,self.flush_log)
    def set_status(self,s): self.after(0,lambda:self.status.set(s))
    def set_preset(self,t):
        import re; m=re.search(r"Giữ (\d+) / Bỏ (\d+)",t)
        if m: self.vars["keep_sec"].set(m.group(1)); self.vars["drop_sec"].set(m.group(2))
    def pick_video(self):
        p=filedialog.askopenfilename(filetypes=[("Video","*.mp4 *.mkv *.mov *.avi *.webm *.m4v"),("Tất cả","*.*")])
        if not p:return
        self.vars["input_video"].set(p); base=str(Path(p).with_suffix(""))
        self.vars["recap_video"].set(base+"_recap.mp4"); self.vars["map_json"].set(base+"_segments.json"); self.vars["template_srt"].set(base+"_template.srt"); self.vars["ai_srt"].set(base+"_ai.srt"); self.vars["wav_path"].set(base+"_tts.wav"); self.vars["final_video"].set(base+"_final.mp4")
    def pick_save(self,key,label,pattern):
        p=filedialog.asksaveasfilename(defaultextension=pattern.replace("*",""),filetypes=[(label,pattern),("Tất cả","*.*")]);
        if p:self.vars[key].set(p)
    def pick_profile(self):
        p=filedialog.askdirectory();
        if p:self.vars["chrome_profile"].set(p)
    def preview_voice(self):
        def work():
            try:
                import tempfile, asyncio, subprocess
                from recap_core import _edge_save, find_bin
                mp3=str(Path(tempfile.gettempdir())/"video_recap_preview.mp3")
                asyncio.run(_edge_save("Xin chào, đây là giọng đọc thử của Video Recap Cutter.",self.vars["voice"].get(),mp3))
                if os.name=="nt": os.startfile(mp3)
                else: subprocess.Popen(["xdg-open",mp3])
            except Exception as e: messagebox.showerror("Lỗi",str(e))
        threading.Thread(target=work,daemon=True).start()
    def run_pipeline(self):
        self.save_cfg(); self.tabs.select(self.tab_log); threading.Thread(target=self.pipeline,daemon=True).start()
    def pipeline(self):
        try:
            inp=self.vars["input_video"].get().strip()
            if not inp or not Path(inp).exists(): raise FileNotFoundError("Chưa chọn video gốc")
            keep=float(self.vars["keep_sec"].get()); drop=float(self.vars["drop_sec"].get()); recap=self.vars["recap_video"].get().strip()
            self.set_status("Đang phân tích video..."); total=duration(inp); segs=build_segments(total,keep,drop); self.log(f"Video {total:.1f}s -> {len(segs)} đoạn giữ")
            if self.vars["make_map"].get(): save_map(segs,self.vars["map_json"].get()); self.log("Đã tạo map JSON")
            if self.vars["make_template"].get(): template_srt(segs,self.vars["template_srt"].get()); self.log("Đã tạo SRT template")
            self.set_status("Đang cắt video..."); cut_video(inp,recap,segs,self.log); self.log("Đã tạo video recap: "+recap)
            mode=self.vars["ai_mode"].get(); srt_path=self.vars["ai_srt"].get().strip(); srt_text=""
            if mode!="Không tạo SRT":
                self.set_status("Đang tạo SRT AI...")
                lang=self.vars["language"].get(); note=self.vars["note"].get(); den=self.vars["density"].get()
                if mode=="Gemini API":
                    keys=[x.strip() for x in self.vars["api_keys"].get().split(";") if x.strip()]
                    if not keys: raise ValueError("Chưa nhập Gemini API key")
                    last=None
                    for k in keys:
                        try: srt_text=gemini_api_srt(recap,k,self.vars["gemini_model"].get(),lang,note,den,self.log); break
                        except Exception as e: last=e; self.log("API key lỗi, thử key tiếp theo: "+str(e))
                    if not srt_text: raise last or RuntimeError("Không tạo được SRT")
                else:
                    provider="Gemini" if mode.startswith("Gemini") else "ChatGPT"
                    # multi-pass currently reruns generation and keeps longest normalized answer
                    passes=1
                    if "2 pass" in mode: passes=2
                    if "3 pass" in mode: passes=3
                    if "4 pass" in mode: passes=4
                    answers=[]
                    for i in range(passes):
                        self.log(f"Web AI pass {i+1}/{passes}")
                        answers.append(web_ai_srt(recap,provider,lang,note,den,int(self.vars["web_wait"].get()),self.vars["chrome_profile"].get().strip() or None,self.log))
                    srt_text=max(answers,key=lambda x:len(parse_srt(x)))
                srt_text=normalize_srt(srt_text,duration(recap)); Path(srt_path).write_text(srt_text,encoding="utf-8"); self.log("Đã lưu SRT: "+srt_path)
            if srt_path and Path(srt_path).exists():
                self.set_status("Đang tạo giọng đọc...")
                eng=self.vars["tts_engine"].get()
                if eng=="Edge TTS": srt_to_wav_edge(srt_path,self.vars["wav_path"].get(),self.vars["voice"].get(),self.log)
                else: raise NotImplementedError("Piper local cần piper.exe + model .onnx riêng; bản build này chưa cấu hình model cụ thể.")
                self.set_status("Đang ghép video cuối...")
                mix_video_audio(recap,self.vars["wav_path"].get(),self.vars["final_video"].get(),self.vars["keep_original_audio"].get(),float(self.vars["original_volume"].get()),self.log)
                self.log("HOÀN TẤT: "+self.vars["final_video"].get())
            else: self.log("Hoàn tất phần cắt video. Không có SRT để tạo giọng.")
            self.set_status("Hoàn tất")
            self.after(0,lambda:messagebox.showinfo("Hoàn tất","Tool đã xử lý xong. Xem tab Log để biết chi tiết."))
        except Exception as e:
            self.log("\nLỖI: "+str(e)); self.log(traceback.format_exc()); self.set_status("Có lỗi")
            self.after(0,lambda:messagebox.showerror("Lỗi",str(e)))

if __name__=="__main__": App().mainloop()
