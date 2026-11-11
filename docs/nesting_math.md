# Bài toán xếp lồng sticker: mô hình toán

Tài liệu nền cho agent. Đọc trước khi sửa `sticker_a4/nest.py` hoặc làm `docs/task_quality_max.md`.

## 1. Bài toán
Xếp lồng hình bất quy tắc 2 chiều (*2D irregular packing / nesting*), biến thể **tối đa
kích thước** (*maximal homothetic packing*): vật liệu cố định, tìm cỡ hình lớn nhất.

| Đặc điểm | Giá trị |
|---|---|
| Hình | 25 hình bất quy tắc, không lồi (vùng alpha > 0 của từng sticker) |
| Thùng | 2 khối chữ nhật 166 × 117,8 mm (trên/dưới, cắt đôi tờ A4) |
| Xoay | tuỳ ý trong [0°, 360°) |
| Kích thước | biến số: hệ số chung `s` + mỗi hình lệch `α_i ∈ [0,9; 1,1]` |
| Ràng buộc | mép 2 hình cách ≥ `d` = 1,2 mm; cạnh dài mỗi hình ≥ 30 mm |
| Mục tiêu | max `s` (≈ max tổng diện tích hình) |

## 2. Mô hình
Dữ liệu: hình `P_i` (tập điểm, gốc tại tâm ảnh), diện tích `A_i`, cạnh dài `ℓ_i` (px);
khối `B_1, B_2` (W × H); `d`; `L_min` = 30 mm.

Biến: `s > 0` (mm/px); với mỗi hình `i`: khối `b_i ∈ {1,2}`, góc `θ_i`, tâm `t_i = (x_i, y_i)`,
hệ số `α_i`.

Hình sau khi đặt: `P_i(v_i) = t_i + s·α_i·R(θ_i)·P_i`, `R(θ)` là ma trận xoay
(trong code: trục y hướng xuống, góc dương = ngược kim đồng hồ khi nhìn, như Pillow).

```
max  s
s.t. P_i(v_i) ⊆ B_{b_i}                                  ∀ i          (nằm trong khối)
     dist(P_i(v_i), P_j(v_j)) ≥ d     ∀ i ≠ j, b_i = b_j               (không chồng + khoảng cách)
     s·α_i·ℓ_i ≥ L_min                                    ∀ i
     0,9 ≤ α_i ≤ 1,1                                      ∀ i
```
Ràng buộc khoảng cách tương đương: nới mỗi hình ra `d/2` (tổng Minkowski với đĩa `D_{d/2}`)
thì phần trong của hai hình đã nới không giao nhau.

## 3. Vì sao NP-hard
- Quy dẫn từ PARTITION: các số `a_i` → hình chữ nhật `a_i × 1` (a_i > 1), 2 khối
  `(Σa/2) × 1`. Xếp được ⇔ chia được 2 nhóm bằng tổng. Cấu trúc 2 khối của bài này chính
  là PARTITION khi hình là chữ nhật.
- Xoay tự do còn làm bài thuộc lớp ∃ℝ-complete (Abrahamsen, Miltzow, Seiferth 2020).
- Không gian (sau rời rạc hoá): 25! thứ tự × 36²⁵ góc × 2²⁵ cách chia khối × vị trí.
  → Chỉ dùng heuristic; không có lời giải "tối ưu toàn cục" chứng minh được.

## 4. Các cách mô hình ràng buộc không chồng
- **No-fit polygon (NFP)**: `NFP_ij = P_i ⊕ (−P_j)`; chồng ⇔ `t_j − t_i ∈ int(NFP_ij)`.
  Inner-fit polygon (IFP) cho ràng buộc nằm trong khối. Dùng cho MIP (Fischetti & Luzzi
  2009) khi góc và cỡ cố định: chia ngoài NFP thành vùng lồi, biến nhị phân chọn vùng,
  big-M. Giải chính xác được cỡ ≤ 15–20 hình — không đủ cho bài này.
- **Phi-function** (Stoyan): `Φ_ij ≥ 0` ⇔ không chồng; bản chuẩn hoá `Φ_ij ≥ d`. Ra NLP góc
  liên tục; ép chặt cục bộ tốt, chỉ tối ưu địa phương.
- **Raster / dotted-board** (code đang dùng): lưới ô `RES` = 0,4 mm, mặt nạ hình
  `M_i^θ`, biến nhị phân `x_{i,θ,b,p}`; mỗi ô thuộc tối đa một hình đã nới. ILP ~2·10⁸ biến
  → không giải chính xác, nhưng "thử mọi vị trí cùng lúc" = tương quan 2 chiều = FFT.

## 5. Thuật toán hiện tại (`nest.py`)
| Thành phần | Cách làm |
|---|---|
| max s | tìm nhị phân trên cạnh dài trung vị (bước 0,5 mm) |
| nằm trong khối, không chồng | raster 0,4 mm, hình đã đặt nới `r = ceil(d/RES)` ô, va chạm bằng `fftconvolve` |
| b, θ, t | **tham lam dựng dần**: đặt theo thứ tự π, mỗi hình chọn ô trống áp sát nhất (`_Packer._best_spot`) |
| θ | 24 góc (`fast`) / 36 góc + lệch pha (`high`) |
| α | thu 0,9–0,95 khi không vừa (`shrink`), phóng 1,05–1,1 khi còn chỗ (`grow`) |
| π | 6 thứ tự; `high` thêm tìm cục bộ (tráo 1–3 cặp, dựng lại từ đầu) |
| kiểm chứng | `min_gap` đo lại ở 0,1 mm |

Điểm yếu: hình đã đặt không bao giờ dời; mỗi lần thử phải dựng lại cả 25 hình (~4 s).
Số liệu mẫu: hình chiếm ~65% diện tích 2 khối (~70% tính vành 0,6 mm); `high` 300 s chỉ
+2–4% diện tích so với `fast`, 900 s gần như không thêm. Cận trên lý thuyết (lấp 100%,
không đạt được): cạnh dài ~51 mm; hiện ~42,5–43,3 mm.

## 6. Hướng vượt trần: tối thiểu hoá phần chồng
Các thuật toán mạnh nhất (GLS — Egeblad et al. 2007; ILS — Imamichi et al. 2009;
sparrow/jagua-rs — Gardeyn & Wauters) cùng ý: **cố định s, cho phép chồng tạm, tối thiểu
hàm phạt chồng bằng cách dời/xoay từng hình; phạt = 0 thì tăng s**. Đặc tả triển khai:
`docs/task_quality_max.md`.
