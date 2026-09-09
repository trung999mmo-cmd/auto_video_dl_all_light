VIDEO RECAP CUTTER V2 - HƯỚNG DẪN

1. GIAO DIỆN
- Bản V2 dùng một trang kéo từ trên xuống dưới giống bố cục mẫu, không chia tab.
- Các phần lần lượt: Hướng dẫn -> 1. Video và đầu ra -> 2. Tạo SRT bằng AI -> 3. Giọng đọc và TikTok session -> 4. Chạy tool -> Log.

2. VIDEO VÀ ĐẦU RA
- Bấm Chọn video.
- Tool tự điền Nơi lưu video, Map JSON, SRT API/Web, SRT template và WAV.
- Nhịp khuyến nghị: Giữ 2 / Bỏ 8 hoặc Giữ 2 / Bỏ 10.

3. GEMINI API
- Tick Tạo SRT recap bằng Gemini API. Tool tự bỏ chọn Web AI để tránh chạy hai nguồn cùng lúc.
- Có thể nhập nhiều key cách nhau bằng dấu ; hoặc dấu phẩy.
- Có nút Test key, model chỉnh được, có 2-pass và delay.
- SRT tạo từ video recap đã cắt theo mặc định để timeline khớp video cuối.

4. GEMINI WEB / CHATGPT WEB
- Tick Dùng Web AI tạo SRT khi bấm Cắt video.
- Chọn Gemini Web / Gemini Web 2 pass / ChatGPT Nhanh / 2 pass / 3 pass / 4 pass.
- Chọn chunk 10, 15, 20, 25 hoặc 30 phút.
- Có Chrome user-data-dir để giữ phiên đăng nhập riêng.
- Website có thể đổi giao diện; nếu selector không còn hợp lệ, xem Log.

5. NGÔN NGỮ
Tool có 15 lựa chọn:
- Tiếng Việt
- English
- 日本語
- 한국어
- 中文
- ไทย
- Français
- Deutsch
- Español
- Indonesia
- Português
- Italiano
- Русский
- العربية
- हिन्दी

6. GIỌNG ĐỌC
Có 4 hệ giọng:
A. Piper Offline
- Bản V2 đóng gói sẵn piper.exe và một model Việt vi_VN-vais1000-medium.
- Muốn thêm model Piper: chép đủ 2 file ten.onnx + ten.onnx.json vào thư mục voices rồi bấm Làm mới giọng.

B. Edge TTS
- Có nhiều giọng cho các ngôn ngữ, cần Internet.
- Chọn ngôn ngữ sẽ lọc giọng phù hợp.

C. TikTok / CapCut
- Nhập TikTok session ID.
- Đây là endpoint không chính thức và TikTok có thể thay đổi bất cứ lúc nào.

D. Voice Clone XTTS
- Dùng file WAV/MP3 giọng mẫu.
- Chạy INSTALL-VOICE-CLONE.bat một lần để tạo engine riêng.
- Model XTTS có danh sách ngôn ngữ riêng; nếu ngôn ngữ không được model hỗ trợ, tool sẽ báo lỗi thay vì giả lập sai.

7. THÊM / SỬA TOOL SAU NÀY
Bản V2 không chỉ có EXE. Trong gói có thư mục source gồm:
- app_v2.py
- recap_core_v2.py
- voice_clone_worker.py
- requirements.txt
- BUILD-V2-WINDOWS.bat
- build-windows.yml
Bạn có thể sửa source rồi build lại bằng GitHub Actions hoặc BUILD-V2-WINDOWS.bat.

8. FILE KÈM THEO
- VideoRecapCutter.exe
- ffmpeg.exe
- ffprobe.exe
- thư mục piper (piper.exe + DLL/data)
- thư mục voices (có sẵn model Việt + README)
- INSTALL-VOICE-CLONE.bat
- voice_clone_worker.py
- thư mục source
- HUONG-DAN.txt

LƯU Ý
- Không cấu hình cắt nào bảo đảm tránh hệ thống bản quyền.
- Không chia sẻ API key hoặc TikTok session ID.
