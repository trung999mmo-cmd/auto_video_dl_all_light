from __future__ import annotations

import shutil
import tempfile
import time
from pathlib import Path
from typing import List

import recap_core_v2 as base
import recap_core_v4 as v4
from recap_core_v2 import Segment


def _composer_text(box) -> str:
    try:
        val = box.get_attribute("value")
        if val:
            return val
    except Exception:
        pass
    for attr in ("innerText", "textContent"):
        try:
            val = box.get_attribute(attr)
            if val:
                return val
        except Exception:
            pass
    try:
        return box.text or ""
    except Exception:
        return ""


def _fill_prompt_all_at_once(driver, prompt: str, log=print):
    """Điền toàn bộ prompt nhiều dòng mà KHÔNG phát phím Enter.

    V4 dùng send_keys(prompt). Với contenteditable, ký tự xuống dòng có thể bị
    Selenium hiểu thành ENTER và gửi ngay đoạn đầu tiên. V5 luôn điền xong toàn
    bộ prompt trước, kiểm tra đủ ký tự rồi mới bấm nút Gửi đúng một lần.
    """
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.common.action_chains import ActionChains

    box = v4._find_prompt_box(driver)
    if box is None:
        raise RuntimeError("Không tìm thấy ô nhập prompt trên Web AI")
    box.click()

    script = r"""
const el = arguments[0];
const text = arguments[1];
el.focus();
function dispatchAll() {
  try { el.dispatchEvent(new InputEvent('input', {bubbles:true, inputType:'insertText', data:text})); }
  catch(e) { el.dispatchEvent(new Event('input', {bubbles:true})); }
  el.dispatchEvent(new Event('change', {bubbles:true}));
}
if (el.tagName === 'TEXTAREA') {
  const setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value').set;
  setter.call(el, text);
  dispatchAll();
} else if (el.tagName === 'INPUT') {
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
  setter.call(el, text);
  dispatchAll();
} else {
  el.innerHTML = '';
  const lines = text.split('\n');
  for (let i = 0; i < lines.length; i++) {
    const p = document.createElement('p');
    if (lines[i].length) p.textContent = lines[i];
    else p.appendChild(document.createElement('br'));
    el.appendChild(p);
  }
  dispatchAll();
}
"""

    js_ok = False
    try:
        driver.execute_script(script, box, prompt)
        time.sleep(0.8)
        current = _composer_text(box)
        js_ok = len(current.strip()) >= max(20, int(len(prompt.strip()) * 0.80))
        if js_ok:
            log(f"INFO: Da dien TOAN BO prompt: {len(current)} ky tu, CHUA GUI.")
    except Exception as e:
        log(f"INFO: Dien prompt bang DOM chua duoc, thu go an toan: {e}")

    if not js_ok:
        try:
            box.click()
            box.send_keys(Keys.CONTROL, "a")
            box.send_keys(Keys.BACKSPACE)
        except Exception:
            pass

        lines = prompt.split("\n")
        for i, line in enumerate(lines):
            if line:
                box.send_keys(line)
            if i != len(lines) - 1:
                ActionChains(driver).key_down(Keys.SHIFT).send_keys(Keys.ENTER).key_up(Keys.SHIFT).perform()

        time.sleep(0.8)
        current = _composer_text(box)
        if len(current.strip()) < max(20, int(len(prompt.strip()) * 0.70)):
            raise RuntimeError(
                f"Prompt chưa được điền đầy đủ ({len(current)}/{len(prompt)} ký tự). "
                "Tool dừng để tránh gửi thiếu prompt."
            )
        log(f"INFO: Da dien TOAN BO prompt bang go an toan: {len(current)} ky tu, CHUA GUI.")

    return box


def _click_send_once(driver, box, log=print):
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys

    selectors = [
        "button[data-testid='send-button']",
        "button[aria-label='Send prompt']",
        "button[aria-label*='Send']",
        "button[aria-label*='Gửi']",
        "button[aria-label*='Submit']",
    ]
    for sel in selectors:
        try:
            buttons = [b for b in driver.find_elements(By.CSS_SELECTOR, sel) if b.is_displayed() and b.is_enabled()]
            if buttons:
                buttons[-1].click()
                log("INFO: DA GUI 1 LAN: VIDEO + TOAN BO PROMPT trong CUNG MOT TIN NHAN.")
                return
        except Exception:
            pass

    box.click()
    box.send_keys(Keys.ENTER)
    log("INFO: DA GUI 1 LAN bang ENTER: VIDEO + TOAN BO PROMPT.")


def _submit_prompt_v5(driver, prompt: str, log=print):
    box = _fill_prompt_all_at_once(driver, prompt, log)
    time.sleep(0.5)
    _click_send_once(driver, box, log)


def web_ai_srt_mapped(video_path: str, provider: str, language: str, keep_sec: float, drop_sec: float,
                      density: str, note: str, wait_seconds: int, profile_dir: str | None,
                      segs: List[Segment], log=print, passes: int = 1, keep_chrome_open: bool = True) -> str:
    url = "https://chatgpt.com/" if provider.lower().startswith("chatgpt") else "https://gemini.google.com/"
    log(f"INFO: {provider} web video: {video_path}")
    log(f"INFO: {provider} web mapping: {len(segs)} block, duration={base.duration(video_path):.3f}s")
    size_mb = Path(video_path).stat().st_size / 1024 / 1024
    log(f"INFO: {provider} upload: file {size_mb:.1f}MB")
    log("INFO: Dang mo Chrome...")
    driver = v4.open_automation_driver(profile_dir, log)
    try:
        log(f"INFO: Dang vao: {url}...")
        driver.get(url)
        log(f"INFO: Chrome da vao trang {provider}.")
        log(f"INFO: Neu chua dang nhap {provider}, dang nhap ngay trong cua so Chrome.")
        time.sleep(8)

        file_input = None
        for attempt in range(1, 4):
            log(f"INFO: Thu upload file {provider} lan {attempt}/3.")
            file_input = v4._find_upload_input(driver, 25)
            if file_input is not None:
                try:
                    file_input.send_keys(str(Path(video_path).resolve()))
                    log(f"INFO: {provider} da nhan video vao o dinh kem.")
                    break
                except Exception as e:
                    log(f"INFO: Upload lan {attempt} loi: {e}")
                    file_input = None
            time.sleep(2)
        if file_input is None:
            raise RuntimeError(f"Không tìm thấy/không dùng được ô upload video trên {provider}")

        log(f"INFO: Video da dinh kem: {Path(video_path).name}")
        log("INFO: CHUA GUI. Cho video upload xong -> dien DU prompt -> moi gui 1 lan.")
        for sec in range(10, 61, 10):
            time.sleep(10)
            if sec in (30, 60):
                log(f"INFO: Dang cho {provider} on dinh sau upload: {sec}s/60s.")

        prompt = v4.build_recap_prompt(keep_sec, drop_sec, language, density, note)
        log(f"INFO: Dien TOAN BO prompt {len(prompt)} ky tu. Tuyet doi khong Enter giua cac dong.")
        before = len(v4._assistant_elements(driver, provider))
        _submit_prompt_v5(driver, prompt, log)
        answer = v4._wait_new_response(driver, provider, before, wait_seconds, log)

        expected = len(segs)
        got = len(base.parse_srt(answer))
        log(f"INFO: SRT nhap tu video goc: {got}/{expected} block.")
        if got != expected:
            fix = f"""SRT vừa rồi có {got} block nhưng cần đúng {expected} block. Hãy sửa lại, chỉ xuất SRT thuần.
Đây là mapping do tool đã tính chính xác; mỗi dòng phải có đúng một block và nội dung phải bám cảnh video gốc tương ứng:
{v4.mapping_hint(segs)}
Giữ văn phong recap liền mạch, không bịa."""
            before = len(v4._assistant_elements(driver, provider))
            _submit_prompt_v5(driver, fix, log)
            answer = v4._wait_new_response(driver, provider, before, wait_seconds, log)
            got = len(base.parse_srt(answer))
            log(f"INFO: Sau sua mapping: {got}/{expected} block.")

        exact = v4.force_exact_timeline(answer, segs)
        log(f"INFO: SRT da du {expected}/{expected} block. Timeline khoa theo video sau cat.")

        for p in range(2, max(1, passes) + 1):
            follow = "Kiểm tra lại toàn bộ SRT vừa tạo, sửa nội dung cho bám cảnh và liền mạch như recap hơn. Không thay đổi số block. Chỉ trả về SRT thuần."
            if p == 3:
                follow = "Rà soát lần 3: sửa câu máy móc/lặp, tên nhân vật, ý nghĩa cảnh và mạch nối. Giữ đúng số block. Chỉ trả về SRT."
            elif p >= 4:
                follow = "Rà soát cuối: loại câu bịa/trùng, làm lời kể tự nhiên và liên tục. Giữ đúng số block. Chỉ trả về SRT."
            before = len(v4._assistant_elements(driver, provider))
            _submit_prompt_v5(driver, follow, log)
            candidate = v4._wait_new_response(driver, provider, before, wait_seconds, log)
            try:
                exact = v4.force_exact_timeline(candidate, segs)
                log(f"INFO: Web AI pass {p}/{passes}: hop le {len(segs)}/{len(segs)} block")
            except Exception as e:
                log(f"INFO: Pass {p} khong hop le, giu ket qua pass truoc: {e}")

        try:
            log(f"INFO: Khoa chat Web AI: {driver.current_url}")
        except Exception:
            pass
        if keep_chrome_open:
            v4._OPEN_WEB_DRIVERS.append(driver)
            log(f"INFO: Giu Chrome mo de ban kiem tra ket qua {provider}.")
            driver = None
        return exact
    finally:
        if driver is not None:
            try:
                driver.quit()
            except Exception:
                pass


def web_ai_srt_mapped_chunked(video_path: str, provider: str, language: str, keep_sec: float, drop_sec: float,
                              density: str, note: str, wait_seconds: int, profile_dir: str | None,
                              chunk_minutes: int, log=print, passes: int = 1) -> str:
    total = base.duration(video_path)
    all_segs = base.build_segments(total, keep_sec, drop_sec)
    if total <= chunk_minutes * 60 + 1:
        return web_ai_srt_mapped(video_path, provider, language, keep_sec, drop_sec, density, note,
                                 wait_seconds, profile_dir, all_segs, log, passes, True)

    cycle = keep_sec + drop_sec
    cycles_per_chunk = max(1, int((chunk_minutes * 60) // cycle))
    chunk_span = cycles_per_chunk * cycle
    tmp = Path(tempfile.mkdtemp(prefix="recap_web_mapped_chunks_v5_"))
    merged_parts = []
    out_offset = 0.0
    try:
        start = 0.0
        idx = 0
        while start < total - 0.02:
            idx += 1
            end = min(total, start + chunk_span)
            chunk = tmp / f"chunk_{idx:03}.mp4"
            log(f"INFO: Web AI chunk {idx}: source {start:.1f}s -> {end:.1f}s")
            v4._make_chunk(video_path, start, end, str(chunk), log)
            local_total = end - start
            local_segs = base.build_segments(local_total, keep_sec, drop_sec)
            txt = web_ai_srt_mapped(str(chunk), provider, language, keep_sec, drop_sec, density, note,
                                    wait_seconds, profile_dir, local_segs, log, passes, False)
            merged_parts.append(base.shift_srt(txt, out_offset))
            out_offset += v4.output_duration(local_segs)
            start = end
        return "\n\n".join(x.strip() for x in merged_parts if x.strip()) + "\n"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
