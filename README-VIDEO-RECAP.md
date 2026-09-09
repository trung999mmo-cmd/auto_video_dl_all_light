VIDEO RECAP CUTTER - HƯỚNG DẪN NHANH

1. Chọn video
- Mở tab "1. Video và cắt".
- Bấm "Chọn video".
- Tool tự điền đường dẫn video recap, map JSON, SRT template, SRT AI, WAV và video cuối.

2. Nhịp cắt
- Nhập "Giữ" và "Bỏ" theo số giây bạn muốn.
- Preset có sẵn: 2/8, 2/10, 3/7, 5/5.
- Đây là tính năng biên tập nhịp video. Không có cấu hình nào bảo đảm tránh hệ thống bản quyền.

3. Tạo SRT
Gemini API:
- Chọn "Gemini API".
- Dán API key. Có thể nhập nhiều key cách nhau bằng dấu ;
- Chọn model và ngôn ngữ.

Gemini Web / ChatGPT Web:
- Chọn chế độ Web.
- Nếu muốn giữ phiên đăng nhập riêng, chọn Chrome user-data-dir.
- Tool mở Chrome, upload video, gửi prompt và đọc kết quả SRT.
- Website có thể thay giao diện nên nếu thất bại, xem tab Log.

4. Giọng đọc
- Bản build mặc định hỗ trợ Edge TTS với nhiều giọng/ngôn ngữ.
- Chọn giọng và bấm "Nghe thử".
- Khi có SRT, tool tạo WAV theo timeline rồi ghép vào video.

5. TikTok session ID
- Giao diện có ô session để tương thích với cấu hình người dùng, nhưng bản hiện tại KHÔNG gửi session ID ra ngoài và chưa dùng session để gọi TikTok TTS.
- Không chia sẻ session ID cho người khác.

6. Piper local
- Giao diện có lựa chọn Piper local nhưng cần piper.exe + model .onnx riêng. Vì model giọng là tài nguyên riêng nên không được nhúng mặc định.

7. FFmpeg
- Bản EXE do GitHub Actions build đã nhúng ffmpeg.exe và ffprobe.exe.

8. File đầu ra
- *_recap.mp4: video đã cắt.
- *_segments.json: map các đoạn nguồn/đầu ra.
- *_template.srt: timeline template.
- *_ai.srt: SRT AI.
- *_tts.wav: giọng đọc.
- *_final.mp4: video cuối.

LƯU Ý
- Đây là bản clean-room, viết mới theo chức năng/luồng sử dụng được mô tả, không sao chép license hay mã nguồn độc quyền từ phần mềm mẫu.
