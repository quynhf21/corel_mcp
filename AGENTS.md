# Hướng dẫn cho agent (Codex)

Trả lời user bằng tiếng Việt.

## Mục tiêu
Chuyển hàng loạt tấm sticker in A3 (5×5 = 25 hình khác nhau, 1 ảnh PNG tách nền nằm
trên 1 layer trong file .cdr) sang **1 trang A4** để in và cắt trên máy in/cắt khổ A4.

Yêu cầu bố cục (đã chốt với user):
- Cả 25 hình nằm trên 1 trang A4 (210×297 mm), máy in in tràn viền.
- Trang chia **2 khối trên/dưới**; tờ được cắt đôi ở giữa để mỗi nửa bỏ vừa túi
  12 × 17,1 cm. Mỗi khối 166 × 116 mm (x 22–188, y 35,75–271,25), cách nhau 3,5 mm.
- **Xếp lồng theo đúng đường viền hình** (không cần ô vuông, không cần thẳng hàng),
  xoay góc tuỳ ý; mép hai hình cách nhau ≥ 1,2 mm. Càng lấp đầy càng tốt.
- Được thu/phóng; cạnh dài mỗi hình ≥ 30 mm; các hình được chênh nhau khoảng ±10%.
- Chế độ cũ `--mode grid` (lưới thẳng hàng thẳng cột, cách 1,5 mm) vẫn giữ để so sánh.
- Vùng đặt hình né 4 dấu L (registration mark) của máy cắt; số đo lấy từ file mẫu
  `ST16.cdr` (do user dàn tay bằng plugin AidCut).
- Script **tự tạo contour cắt và 4 dấu L** giống hệt AidCut trong file mẫu (tắt bằng `--no-cut`):
  - layer `TraceLayer` (trên cùng, không in): mỗi sticker một đường `TraceLine` kín, gấp khúc,
    ngoài mép hình 0,4 mm (`--cut-offset`), nét 0,5 pt đỏ RGB(233,78,54), không tô;
  - layer ảnh (`Layer 1`): một đối tượng `LMarkLine1` gồm 4 dấu L dài 20 mm, nét 1 mm,
    K100; góc trong tại x 9,93 / 199,93 mm, y 30,01 / 277,01 mm.
  Tham số trong `CutConfig` (`contour.py`). Mép hình cách ≥ 1,2 mm nên giữa 2 contour
  chỉ còn ≈ 1,2 − 2×0,4 mm; muốn đường cắt cách nhau ≥ 1,2 mm thì tăng `gap` lên 2,0.
- Plugin AidCut **không tự kết nối máy cắt** khi Corel do script mở: mở Corel bằng tay
  trước rồi mới chạy batch; không kill Corel.

## Tài liệu
- `docs/nesting_math.md`: mô hình toán của bài xếp lồng, vì sao NP-hard, thuật toán hiện tại.
- `docs/task_quality_max.md`: **việc tiếp theo** — chế độ `--quality max` (tối thiểu hoá
  phần chồng, GLS). Làm theo đúng ràng buộc, test và bảng benchmark trong đó.

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
Sau mỗi lần `git pull` có đổi `requirements.txt` (ví dụ thêm `opencv-python-headless`
cho contour), chạy lại `pip install -r requirements.txt`.

## Trạng thái & việc cần kiểm tra (cập nhật 2026-11-09)
| Phần | Trạng thái |
|---|---|
| Tách sticker, xếp lồng, preview | Chạy tốt trên 2 ảnh mẫu (Linux, 10 test pass). |
| Dựng trang A4 trong Corel (import, kích thước, tâm, xoay, lưu CDR/PDF) | **Đã chạy thật** trên Corel 2020 (commit 1a1ec91), user báo OK. |
| Contour `TraceLine` + 4 dấu L `LMarkLine1` trong Corel | **Đã chạy thật** trên trang 2 ST264: 25 contour, 4 dấu L, xoay khớp ảnh; trang 1 giữ nguyên cả đối tượng và ảnh render. |
| AidCut nhận contour/dấu L do script tạo để gửi máy cắt | **Chưa biết** — chỉ mô phỏng tên, layer, hình dạng từ file mẫu. |

Checklist lần chạy đầu có contour:
1. Mở Corel **bằng tay** trước (để AidCut kết nối máy cắt), rồi chạy
   `batch.py <gốc> <ra> --limit 1`.
2. Mở file kết quả: layer `TraceLayer` có 25 `TraceLine` (đỏ, không tô), `Layer 1`
   có ảnh + `LMarkLine1` (4 dấu L đen). Contour phải ôm đúng viền trắng của từng hình,
   kể cả hình bị xoay. Nếu lệch: kiểm tra chiều `Rotate` / toạ độ trong `corel_build.py`,
   không sửa `contour.py` (contour đã khớp preview, có test).
3. Thử gửi sang máy cắt bằng AidCut. Nếu AidCut không nhận, ghi lại thông báo lỗi /
   chụp màn hình cho user; có thể AidCut cần đối tượng do chính nó tạo hoặc thuộc tính
   khác không thấy trong file mẫu. Lúc đó dùng `--no-cut` và để AidCut tự trace.
4. Lỗi COM thường gặp khi vẽ curve: `Application.CreateCurve(doc)`,
   `Curve.CreateSubPath(x, y)`, `SubPath.AppendLineSegment(x, y)`, `SubPath.Closed`,
   `Layer.CreateCurve(curve)`, `Outline.Width` (đơn vị tài liệu = mm),
   `Outline.Color.RGBAssign/CMYKAssign`, `Page.CreateLayer(name)`.

## Ghi chú kỹ thuật & quyết định đã chốt
- **AidCut**: không tự kết nối máy cắt nếu Corel do script/COM khởi động -> luôn mở Corel
  bằng tay trước, chạy batch dưới user Windows thường (không Admin/sandbox), không kill
  Corel (tắt ngang có thể làm hỏng workspace, mất toolbar). Không giữ F8 khi mở Corel
  (reset workspace, mất toolbar AidCut). Toolbar mất: Window -> Toolbars để bật lại.
- **Khoảng cách**: `gap` 1,2 mm là giữa **mép hình** (viền trắng). Contour lệch ra 0,4 mm
  mỗi bên nên giữa 2 đường cắt chỉ còn ~0,4–0,5 mm. Muốn đường cắt cách nhau ≥ 1,2 mm
  thì đặt `gap` ≈ 2,0 (hình sẽ nhỏ đi chút) — hỏi user trước khi đổi.
- **Mảnh rời** của một sticker (cuộn giấy, tim, giọt nước... nằm tách hẳn khỏi hình)
  có contour riêng -> thành miếng cắt rời. Mảnh cách hình < ~0,8 mm thì dính chung contour.
- **Tối ưu**: xếp lồng là bài NP-hard, kết quả là heuristic, không phải tối ưu toàn cục.
  Mẫu: hình chiếm ~65% diện tích 2 khối (~70% tính cả vành 0,6 mm); cận trên lý thuyết
  (lấp 100%, không đạt được) cạnh dài ~51 mm, hiện ~42,5–43,3 mm.
  `--quality high` 300 s: diện tích hình +2,3–4,3% so với fast; 900 s: +4,3%, gần như
  chững -> thêm thời gian không đáng; muốn hơn nữa phải đổi thuật toán (GA/no-fit polygon).
- Đã thử và **bỏ**: nới hình ít hơn 1 ô lưới (tight gap) -> khoảng cách thật < 1,2 mm.
  Khoảng cách đo được hiện 1,20–1,36 mm (dư ≤ 0,16 mm), không còn gì để ép ở đây.
- Kích thước: hình được nhỏ/to ±10% quanh cỡ chung để lấp hốc, nên hình to nhất có thể
  hơn hình nhỏ nhất ~25%. Muốn đều hơn: thu hẹp `shrink`/`grow` trong `NestConfig`.
- Vùng đặt hình 22–188 × 35,75–271,25 mm: giữ tâm vùng mẫu, thu chiều cao mỗi khối
  còn 116 mm theo yêu cầu user; rộng 166 mm để mỗi nửa tờ vẫn vừa túi 171 mm.
  Cần user xác nhận không đè dấu L nếu đổi thông số AidCut.

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
- Tài liệu nhiều trang: `Page.SetSize` có thể tự đổi `DrawingOriginX/Y`, nên phải
  khôi phục gốc thước sau khi dựng. `Page.GuidesLayer.CreateGuide` vẫn có thể tạo
  guide trên master; dùng `MoveToLayer` chuyển về layer guide local của trang đang sửa.
  Khi sửa một trang, lưu bản sao, so sánh đối tượng và ảnh render của trang cần giữ
  trước/sau khi lưu, không chỉ so sánh hình nhìn thấy trên trang được sửa.
- Repo của user `quynhf21/corel_mcp`: xong việc thì commit và push thẳng `main`.
