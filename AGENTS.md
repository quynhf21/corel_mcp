# Hướng dẫn cho agent (Codex)

Trả lời user bằng tiếng Việt.

## Mục tiêu
Chuyển hàng loạt tấm sticker in A3 (5×5 = 25 hình khác nhau, 1 ảnh PNG tách nền nằm
trên 1 layer trong file .cdr) sang **1 trang A4** để in và cắt trên máy in/cắt khổ A4.

Yêu cầu bố cục (đã chốt với user):
- Cả 25 hình nằm trên 1 trang A4 (210×297 mm), máy in in tràn viền.
- Trang chia **2 khối trên/dưới**; tờ được cắt đôi ở giữa để mỗi nửa bỏ vừa túi
  12 × 17,1 cm. Mỗi khối khoảng 160 × 117,8 mm, cách nhau 3,5 mm.
- Các hình cách nhau ≥ 1,5 mm, thẳng hàng, thẳng cột (lưới).
- Được thu/phóng; cạnh dài mỗi hình ≥ 30 mm; kích thước các hình được chênh nhau
  một ít; càng lấp đầy giấy càng tốt. Được xoay 90° nếu hình to hơn hẳn.
- Vùng đặt hình né 4 dấu L (registration mark) của máy cắt; số đo lấy từ file mẫu
  `ST16.cdr` (do user dàn tay). Dấu L và đường cắt contour do plugin cắt của user
  tạo sau, script **không** vẽ chúng.

## Mã nguồn: `sticker_a4/`
| File | Việc |
|---|---|
| `split_stickers.py` | Tách tấm PNG thành 25 sticker theo kênh alpha, gộp mảnh rời (tim, giọt nước). |
| `layout.py` | Tính lưới tối ưu (thuần Python, không cần Corel). Tham số trong `Config`. |
| `preview.py` | Vẽ trang A4 ra PNG để kiểm tra bố cục. |
| `corel_build.py` | COM tới `CorelDRAW.Application.22`: xuất bitmap từ .cdr, dựng trang A4, lưu .cdr/.pdf. |
| `batch.py` | Chạy cả thư mục, có `--limit`, `--dry-run`, `--pdf`, `--overwrite`, ghi `log.csv`. |

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
  (khung xanh lá = hình, khung xanh dương = khối, vạch đỏ = đường cắt đôi).
