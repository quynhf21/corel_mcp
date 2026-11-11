# Task: chế độ `--quality max` — xếp lồng bằng tối thiểu hoá phần chồng

Đọc trước: `AGENTS.md`, `docs/nesting_math.md`. Trả lời user bằng tiếng Việt.

## Mục tiêu
Thêm chế độ thứ ba `max` cho bước bố cục, dùng **tối thiểu hoá phần chồng có trọng số
(guided local search)** thay cho dựng dần tham lam, để hình to hơn `high` với cùng thời
gian. Không đổi hành vi của `fast`, `high`, `grid`, contour, Corel.

Mục tiêu số (không phải điều kiện bắt buộc, nhưng phải báo cáo): với `--time-budget 300`,
tổng diện tích hình của `max` ≥ `high` + 5% trên 2 ảnh mẫu. Nếu không đạt, báo cáo trung
thực số đo và nhận định nguyên nhân, không "chỉnh" benchmark.

## Ràng buộc bắt buộc (không được vi phạm)
- Kết quả cuối phải đo lại bằng `nest.min_gap` (0,1 mm) và **≥ `cfg.gap` (1,2 mm)**; mọi hình
  nằm trong khối (`Placement.bbox` trong `Config` left/right/top/bottom, không vắt qua
  đường cắt đôi); cạnh dài ≥ 30 mm; giữ tỉ lệ khung gốc của từng hình.
- `max` **không bao giờ trả kết quả kém hơn điểm xuất phát** (warm start) — nếu tìm kiếm
  không cải thiện, trả nguyên lời giải warm start.
- Tất định với cùng `seed` và cùng số lần lặp (để test được). Giới hạn thời gian dùng
  `time.monotonic()`.
- Không thêm dependency nặng ngoài `requirements.txt` hiện có (numpy, scipy, pillow,
  opencv). Không viết lại `_Packer`/`plan_nest` hiện có; thêm module mới.
- Contour (`contour.py`) và Corel (`corel_build.py`) dùng `Layout`/`Placement` như cũ —
  không đổi định dạng `Placement` (tâm `cx, cy`, kích thước chưa xoay `w, h`, `angle`).

## Thiết kế đề xuất (`sticker_a4/overlap.py`)
Dùng lại từ `nest.py`: `RES`, `_mask`, `_alphas`, `_disk`, `_to_layout`/`min_gap`,
`NestConfig`, cache mặt nạ theo `(index, góc, scale)`.

### Trạng thái
Ở một cỡ cố định `S` (cạnh dài trung vị, mm): mỗi hình `i` có `(b_i, θ_i, y_i, x_i)` (ô
lưới, góc trên-trái mặt nạ) và `α_i` (giữ 1,0 ở giai đoạn 1). Mỗi khối có lưới
`bh × bw` như `_Packer`.

### Hàm phạt
- `D_j` = mặt nạ hình `j` đã nới `r = ceil(gap / RES)` ô (như `_Packer._stamp`).
- Chồng của cặp: `o_ij = Σ_p M_i(p) · D_j(p)` (đếm ô; 0 ⇔ đủ khoảng cách trên raster).
- Phạt tổng: `F = Σ_{i<j, b_i=b_j} w_ij · o_ij`, trọng số `w_ij ≥ 1` (ban đầu 1).
- Nằm trong khối: chỉ xét vị trí mặt nạ nằm trọn trong khối (tương quan `mode="valid"`),
  nên không cần phạt lòi ra.

### Bước di chuyển (một hình)
Với hình `i` đang chồng (chọn ngẫu nhiên có trọng số theo phần chồng của nó):
1. Với mỗi khối `b` và mỗi góc thử `θ`: bản đồ trọng số `W_b^{(i)} = Σ_{j≠i, b_j=b} w_ij · D_j`
   (đặt đúng vị trí); chi phí mọi vị trí = tương quan `W_b^{(i)}` với `M_i^θ`
   (`fftconvolve(W, M[::-1, ::-1], mode="valid")`).
2. Chọn (b, θ, vị trí) chi phí nhỏ nhất; hoà thì ưu tiên ít dời (gần vị trí cũ) rồi áp sát
   (tái dùng ý tưởng `_ring` của `_Packer`).
3. Góc thử: góc hiện tại ± 1–2 bước, cộng ~6 góc ngẫu nhiên trong 36 góc (bước 10°) — không
   thử cả 36 góc mỗi bước để đủ nhanh.

### Vòng GLS ở cỡ S
```
lặp tới khi F == 0 hoặc hết lượt/thời gian:
    di chuyển các hình đang chồng (mỗi vòng duyệt hết các hình chồng một lần)
    nếu một vòng không giảm F (cực tiểu địa phương):
        với cặp có tiện ích lớn nhất  u_ij = o_ij / (1 + p_ij):  w_ij += 1, p_ij += 1
        (hoặc tăng w_ij ∝ o_ij / max o) — để đẩy hình ra khỏi cực tiểu
```

### Vòng ngoài trên S
```
warm start: kết quả high (hoặc fast) của cùng ảnh → S0, vị trí, góc
best = warm start
S = S0 * (1 + step)                     # step ~1% cạnh dài
phóng mọi hình lên S, giữ tâm và góc → xuất hiện chồng
lặp tới hết time_budget:
    chạy GLS ở S
    nếu F == 0 và min_gap(layout) >= gap:   best = layout; S *= (1 + step)
    nếu không: S giảm nửa bước giữa best và S (thu hẹp), hoặc dừng khi bước < 0,1 mm
cuối cùng: chạy _Packer.grow-tương-đương (tuỳ chọn, giai đoạn 2) để phóng α_i từng hình
trả best
```

### Tối ưu hiệu năng (nên làm, đo trước/sau)
- Cache FFT của kernel mặt nạ theo `(i, θ, S)` dùng `scipy.fft.rfft2` với kích thước đệm cố
  định của khối; bản đồ `W_b` chỉ FFT một lần cho mỗi lượt di chuyển.
- Bản đồ `W_b^{(i)}` = bản đồ tổng của khối trừ đóng góp của chính `i` (không dựng lại từ đầu).
- Đo thời gian một bước di chuyển; mục tiêu ≤ 0,2 s trên laptop i7 (in ra trong log).

## Tích hợp
- `nest.py`: thêm `QUALITY["max"]` (ví dụ `{"time_budget": 300.0, "angle_step": 10.0}`) và
  để `plan_nest` (hoặc hàm mới gọi từ `preview.make_layout`) chạy: warm start bằng đường
  `high` với khoảng 1/3 ngân sách, phần còn lại cho `overlap.py`.
- `batch.py`: `--quality` thêm `max` (hiện đang hard-code `["fast", "high"]`).
- `preview.py`: đã đọc `list(QUALITY)` nên tự có `max`.
- `AGENTS.md`: thêm mô tả `max`, thời gian, số liệu benchmark.

## Test (thêm vào `test_sticker_a4.py`, chạy nhanh < 60 s tổng)
1. Hàm phạt: 2 hình vuông đặt chồng → `o_ij > 0`; tách ra đúng `gap` → `o_ij == 0`.
2. Một bước di chuyển không bao giờ làm tăng `F` (với trọng số cố định).
3. `max` với ngân sách nhỏ (vd. 20 s, `angle_step=45`) trên `anh_goc_1.png`:
   `score ≥ warm start`, `min_gap ≥ 1,2 − VERIFY_RES`, đủ 25 hình, nằm trong khối.
4. Tất định: cùng seed, cùng số lượt lặp (không theo thời gian) → cùng kết quả.

## Benchmark & báo cáo (bắt buộc trước khi commit)
Chạy trên `anh_goc_1.png`, `anh_goc_2.png`, cùng `--time-budget 300`, cùng máy, `--workers 1`:

| | fast | high 300 s | max 300 s | max 900 s |
|---|---|---|---|---|
| ảnh 1: diện tích hình (mm²) / cạnh dài trung vị / min_gap | | | | |
| ảnh 2: ... | | | | |

Số liệu tham chiếu đo trên VPS (Linux, 4 nhân) ngày 2026-11-09:
fast 37 081 / 38 416 mm²; high 300 s 38 672 / 39 312 mm²; high 900 s 38 672 / 40 054 mm².
(Diện tích = Σ w·h của khung hình, như cách tính trong preview log.)

Lưu ảnh `preview_mau/anh_goc_{1,2}_A4_preview_max.png`. Ghi bảng vào `AGENTS.md`.

## Các bước gợi ý (commit sau mỗi bước chạy được, push thẳng `main`)
1. `overlap.py`: trạng thái + hàm phạt + bước di chuyển + test 1–2.
2. Vòng GLS ở cỡ cố định; thử: lấy lời giải `fast`, phóng 3% → GLS có đưa về F = 0 không.
3. Vòng ngoài trên S + tích hợp `QUALITY["max"]`, `batch.py`; test 3–4.
4. Tối ưu FFT/caching, đo thời gian một bước.
5. Benchmark, preview, cập nhật `AGENTS.md`.

## Bẫy thường gặp
- Raster: mặt nạ "phủ dư" (`_mask` dùng `Image.BOX` > 0) nên `o_ij == 0` trên raster vẫn có
  thể cho `min_gap` thật hơi khác — luôn kiểm bằng `min_gap` trước khi nhận lời giải.
- Phóng S làm mặt nạ đổi kích thước → toạ độ góc trên-trái phải tính lại từ tâm.
- Hai khối độc lập: di chuyển sang khối kia là nước đi hợp lệ, cần cho phép (cân tải).
- Đừng để trọng số `w_ij` tăng vô hạn: chuẩn hoá hoặc reset khi đổi S.
- Đừng đổi `RES` toàn cục (ảnh hưởng fast/high); nếu cần lưới mịn hơn, tham số riêng cho `max`.
