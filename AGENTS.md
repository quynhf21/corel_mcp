# Hướng dẫn cho agent (Codex)

Trả lời user bằng tiếng Việt.

## Mục tiêu
Chuyển hàng loạt tấm sticker in A3 (5×5 = 25 hình khác nhau, 1 ảnh PNG tách nền nằm
trên 1 layer trong file .cdr) sang **1 trang A4** để in và cắt trên máy in/cắt khổ A4.

Yêu cầu bố cục (đã chốt với user):
- Cả 25 hình nằm trên 1 trang A4 (210×297 mm), máy in in tràn viền.
- Trang chia **2 khối trên/dưới**; tờ được cắt đôi ở giữa để mỗi nửa bỏ vừa túi
  12 × 17,1 cm. Mỗi khối 166 × 117,8 mm (x 22–188, y 34–273), cách nhau 3,5 mm.
- **Xếp lồng theo đúng đường viền hình** (không cần ô vuông, không cần thẳng hàng),
  xoay góc tuỳ ý; mép hai hình cách nhau ≥ 1,2 mm. Càng lấp đầy càng tốt.
- Được thu/phóng; cạnh dài mỗi hình ≥ 30 mm; các hình được chênh nhau khoảng ±10%.
- Chế độ cũ `--mode grid` (lưới thẳng hàng thẳng cột, cách 1,5 mm) vẫn giữ để so sánh.
- Vùng đặt hình né 4 dấu L (registration mark) của máy cắt; số đo lấy từ file mẫu
  `ST16.cdr` (do user dàn tay). Dấu L và đường cắt contour do plugin cắt của user
  tạo sau, script **không** vẽ chúng.

## Mã nguồn: `sticker_a4/`
| File | Việc |
|---|---|
| `split_stickers.py` | Tách tấm PNG thành 25 sticker theo kênh alpha, gộp mảnh rời (tim, giọt nước). |
| `nest.py` | Xếp lồng theo mặt nạ alpha, xoay tuỳ ý (mặc định). Tham số trong `NestConfig`. |
| `layout.py` | `Config` (vùng đặt, khoảng cách), `Placement` (tâm, kích thước chưa xoay, góc), chế độ lưới. |
| `preview.py` | Vẽ trang A4 ra PNG để kiểm tra bố cục. |
| `corel_build.py` | COM tới `CorelDRAW.Application.22`: xuất bitmap từ .cdr, dựng trang A4, lưu .cdr/.pdf. |
| `batch.py` | Chạy cả thư mục: `--limit`, `--dry-run`, `--pdf`, `--overwrite`, `--mode`, `--workers`, ghi `log.csv`. |
| `test_sticker_a4.py` | `pytest test_sticker_a4.py` (không cần Corel). |

## Cách chạy (Windows 11, Python 64-bit)
```powershell
cd sticker_a4
py -3 -m venv .venv
.venv\Scripts\pip install -r requirements.txt
# 1) kiểm tra bố cục, không cần Corel (đầu vào .png):
.venv\Scripts\python batch.py ..\mau_png ..\out_test --dry-run
# 2) chạy thật 10 file đầu, mở Corel:
.venv\Scripts\python batch.py D:\sticker\goc D:\sticker\a4 --limit 10 --pdf
```

## Quy tắc khi sửa / chạy
- Không bao giờ ghi đè hay sửa file gốc; đầu ra luôn ở thư mục khác (`batch.py` đã chặn).
- Luôn thử với `--limit` nhỏ (1 → 10 file) và cho user xem file kết quả trong Corel
  trước khi chạy cả vài trăm file.
- `corel_build.py` **chưa được chạy thử trên Corel thật** (viết trên Linux). Nếu lỗi COM:
  - Đọc thông báo lỗi, tra tên method/tham số trong type library
    (`win32com.client.gencache.EnsureDispatch` sinh wrapper trong `%TEMP%\gen_py`).
  - Chỗ dễ sai nhất: `ExportBitmap` (thứ tự tham số), `Page.LeftX/TopY`,
    `Layer.Import` + `doc.ActiveShape`, `GuidesLayer.CreateGuide`.
  - Sửa nhỏ nhất có thể, không đổi `layout.py` để chữa lỗi COM.
- Nếu Corel phải chạy với quyền Admin thì Python cũng phải chạy cùng quyền, nếu không
  COM sẽ báo lỗi không kết nối được.
- Sau khi đổi tham số bố cục, chạy lại `--dry-run` và xem `*_A4_preview.png`
  (khung xanh dương = khối, vạch đỏ = đường cắt đôi).
- Xếp lồng mất ~1,5 phút/file/nhân CPU; bước bố cục chạy song song (`--workers`,
  mặc định số nhân − 1). Muốn nhanh hơn (kém chặt hơn): giảm `restarts`, tăng
  `angle_step` trong `NestConfig`.
- Corel: hình được import ở chiều gốc, `SetSizeEx` theo tâm rồi `Rotate(angle)`
  (độ dương = ngược kim đồng hồ, giống Pillow). Nếu trên Corel thấy hình xoay ngược
  chiều so với preview thì đổi dấu góc ở `corel_build.py`.
- Repo của user `quynhf21/corel_mcp`: xong việc thì commit và push thẳng `main`.
