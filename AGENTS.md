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
  `ST16.cdr` (do user dàn tay bằng plugin AidCut).
- Script **tự tạo contour cắt và 4 dấu L** giống hệt AidCut trong file mẫu (tắt bằng `--no-cut`):
  - layer `TraceLayer` (trên cùng): mỗi sticker một đường `TraceLine` kín, gấp khúc,
    ngoài mép hình 0,4 mm (`--cut-offset`), nét 0,5 pt đỏ RGB(233,78,54), không tô;
  - layer ảnh (`Layer 1`): một đối tượng `LMarkLine1` gồm 4 dấu L dài 20 mm, nét 1 mm,
    K100; góc trong tại x 9,93 / 199,93 mm, y 30,01 / 277,01 mm.
  Tham số trong `CutConfig` (`contour.py`). Mép hình cách ≥ 1,2 mm nên giữa 2 contour
  chỉ còn ≈ 1,2 − 2×0,4 mm; muốn đường cắt cách nhau ≥ 1,2 mm thì tăng `gap` lên 2,0.
- Plugin AidCut **không tự kết nối máy cắt** khi Corel do script mở: mở Corel bằng tay
  trước rồi mới chạy batch; không kill Corel.

## Mã nguồn: `sticker_a4/`
| File | Việc |
|---|---|
| `split_stickers.py` | Tách tấm PNG thành 25 sticker theo kênh alpha, gộp mảnh rời (tim, giọt nước). |
| `nest.py` | Xếp lồng theo mặt nạ alpha, xoay tuỳ ý (mặc định). Tham số trong `NestConfig`. |
| `layout.py` | `Config` (vùng đặt, khoảng cách), `Placement` (tâm, kích thước chưa xoay, góc), chế độ lưới. |
| `contour.py` | Contour cắt quanh từng sticker (OpenCV) + 4 dấu L, theo `CutConfig`. |
| `preview.py` | Vẽ trang A4 ra PNG để kiểm tra bố cục (contour đỏ, dấu L đen). |
| `corel_build.py` | COM tới `CorelDRAW.Application.22`: xuất bitmap từ .cdr, dựng trang A4, lưu .cdr/.pdf. |
| `batch.py` | Chạy cả thư mục: `--limit`, `--dry-run`, `--pdf`, `--overwrite`, `--mode`, `--quality`, `--workers`, `--no-cut`, `--cut-offset`, ghi `log.csv`. |
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
- `corel_build.py` đã chạy thử dựng A4 trên CorelDRAW 2020/Windows với 25 PNG,
  lưu CDR/PDF và kiểm tra tâm hình (sai số tối đa 0,0001 mm). Nếu lỗi COM:
  - Đọc thông báo lỗi, tra tên method/tham số trong type library
    (`win32com.client.gencache.EnsureDispatch` sinh wrapper trong `%TEMP%\gen_py`).
  - Chỗ dễ sai nhất: `ExportBitmap` (thứ tự tham số), `Page.LeftX/TopY`,
    `Layer.Import` + `doc.ActiveShape`, `GuidesLayer.CreateGuide`.
  - Sửa nhỏ nhất có thể, không đổi `layout.py` để chữa lỗi COM.
- Nếu Corel phải chạy với quyền Admin thì Python cũng phải chạy cùng quyền, nếu không
  COM sẽ báo lỗi không kết nối được.
- Sau khi đổi tham số bố cục, chạy lại `--dry-run` và xem `*_A4_preview.png`
  (khung xanh dương = khối, vạch đỏ ngang = đường cắt đôi tờ, viền đỏ mảnh = contour).
- Sau khi dựng trong Corel, mở thử 1 file: contour phải ôm đúng viền trắng của hình.
  Nếu contour lệch/xoay sai so với ảnh, kiểm tra chiều `Rotate` (xem dưới).
- Xếp lồng `--quality fast` (mặc định) mất ~1,5 phút/file/nhân CPU; `--quality high`
  (góc 10°, tìm kiếm cục bộ) mất `--time-budget` giây/file (mặc định 300). Bước bố cục
  chạy song song (`--workers`, mặc định số nhân − 1). Máy user: Intel Core Ultra 7 155H
  (16 nhân / 22 luồng), chạy qua đêm được.
- Đổi tham số khác: `NestConfig` và `QUALITY` trong `nest.py`.
- Corel: hình được import ở chiều gốc, `SetSizeEx` để đổi kích thước,
  `SetPositionEx(cdrCenter, cx, cy)` để đặt tâm, rồi `Rotate(angle)`
  (độ dương = ngược kim đồng hồ, giống Pillow). Nếu trên Corel thấy hình xoay ngược
  chiều so với preview thì đổi dấu góc ở `corel_build.py`.
- Repo của user `quynhf21/corel_mcp`: xong việc thì commit và push thẳng `main`.
