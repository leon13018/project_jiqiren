# Python 3.11 重編（加 _tkinter）+ Pillow source build（避開 libtiff.so.6）

**建立日期：** 2026-05-23
**對應提交：** 本檔自身

> 接續 `2026-05-23_python311_vendor_deps.md`。原檔列了「廠商 SDK 第三方套件補裝到 Python 3.11」的計畫；實際迭代時多踩了兩個 Buster + piwheels 相關的坑，本檔紀錄**實際額外執行**的修補動作,供日後查閱「為何 Python 3.11 是 source build」「為何 Pillow 是 9.5.0 而不是最新版」。

---

## 踩到的坑

### 坑 1：piwheels 預編譯 wheel 跟 Buster GLIBC 不相容

`pyserial / RPi.GPIO / pigpio / smbus2` 用 `python3.11 -m pip install` 一次裝齊後,跑 `python3.11 myProgram.py` 在 `import RPi.GPIO` 階段:

```
ImportError: /lib/arm-linux-gnueabihf/libc.so.6: version `GLIBC_2.34' not found
(required by /home/pi/.local/lib/python3.11/site-packages/RPi/_GPIO.cpython-311-arm-linux-gnueabihf.so)
```

**原因:** piwheels 把 `RPi.GPIO` 編成需要 GLIBC 2.34;Pi 是 **Debian Buster**,只有 **GLIBC 2.28**。

**解法:強迫從原始碼編譯,跳過 piwheels:**

```bash
python3.11 -m pip uninstall RPi.GPIO -y
python3.11 -m pip install --no-binary :all: --index-url https://pypi.org/simple/ RPi.GPIO
```

- `--no-binary :all:` → 強迫從 .tar.gz source 編
- `--index-url https://pypi.org/simple/` → 跳過 piwheels(預設 index),只去 PyPI 拿
- 編譯用你 Pi 自己的 GLIBC,自然相容

> ⚠️ **此修補對所有 piwheels 提供 C extension 的套件都可能適用**(`pyserial` / `pigpio` / `smbus2` 是純 Python,不會踩;C extension 比如 `RPi.GPIO`、`Pillow`、未來可能的 numpy/opencv 升級都要留意)

---

### 坑 2：Python 3.11.9 source build 預設不含 `_tkinter`

修完 RPi.GPIO 後,跑 `python3.11 myProgram.py` 換 `screen_display.py` 在 `import tkinter as tk` 階段炸:

```
ModuleNotFoundError: No module named '_tkinter'
```

**原因:** `_tkinter` 是 CPython 內建 C extension,**編譯 Python 時**就要 link `Tcl/Tk` 開發標頭才會被編進去。先前 source build Python 3.11.9 時系統沒裝 `tk-dev` / `tcl-dev`,該 module 直接被略過。`tkinter` 不存在於 PyPI,**只能重編 Python**。

**解法:裝 dev headers + 重編 Python(altinstall):**

```bash
sudo apt install tk-dev tcl-dev

cd ~/Python-3.11.9
make clean
./configure --enable-optimizations --prefix=/usr/local
make -j4
sudo make altinstall
```

- `make altinstall` **不要寫 `make install`**,避免覆蓋系統 python
- Pi 4 編譯約 **20~40 分鐘**(`--enable-optimizations` 跑 PGO benchmark)
- 重編後 `~/.local/lib/python3.11/` 的既有 pip 套件**不受影響**(site-packages 跟 interpreter 分離)

驗證:
```bash
python3.11 -c "import _tkinter; print('OK')"
```

> ⚠️ **未來若再缺其他 Python stdlib C extension**(`_ssl` / `_curses` / `_sqlite3` 之類),都是同樣的 rebuild 模式:先 `apt install <對應-dev>`,再 `cd ~/Python-3.11.9 && make clean && ./configure ... && make -j4 && sudo make altinstall`。

---

### 坑 3：piwheels 連 Pillow 9.x 都 rebuild 過了,連結 libtiff.so.6

裝完 Pillow 12 → `ImportError: libtiff.so.6` → 試降版 `pip install "Pillow<10"` 得 Pillow 9.5.0 piwheels 版 → **依然 `libtiff.so.6` 缺**。

**原因:** Buster 系統的 libtiff 是 4.1.x → SONAME `libtiff.so.5`;Pillow 從某版開始連結 `libtiff.so.6`(libtiff 4.4+),piwheels 把舊版 wheel 也 rebuild 了。降版 wheel 路線堵死。

**選項評估:**

| 方案 | 工程量 | 缺點 |
|---|---|---|
| ✅ source build Pillow,連結系統 libtiff5 | 5 分鐘 | 沒缺點 |
| ❌ from-source 編 libtiff 6 到 `/usr/local/lib/` | 10 分鐘 + ld 設定 | 雙版本共存,管理複雜 |
| ❌ apt 升級 libtiff | N/A | Buster 官方 repo 沒 libtiff 6;只能跳發行版 |

**採用:source build Pillow:**

```bash
sudo apt install libjpeg-dev zlib1g-dev libfreetype6-dev liblcms2-dev libtiff5-dev libwebp-dev

python3.11 -m pip uninstall -y Pillow
python3.11 -m pip install --no-binary :all: --index-url https://pypi.org/simple/ "Pillow<10"
```

編譯時 Pillow setup.py 偵測到系統有 `libtiff5-dev` → 連結到 `libtiff.so.5`(系統現有)。約 3~5 分鐘。

驗證:
```bash
python3.11 -c "from PIL import ImageTk; print('OK')"
```

---

## 驗證段（成功判定）

✅ **逐項通過 = 本輪修補完成:**

1. `python3.11 -c "import _tkinter; print('OK')"` 印 `OK`
2. `python3.11 -c "from PIL import ImageTk; print('OK')"` 印 `OK`
3. `cd /home/pi/Desktop/project_jiqiren/myProgram && python3.11 myProgram.py` 進入主迴圈無 traceback
4. `hawking_loop` 自動跑、按 `y` 進顧客模式,**喇叭有出聲**

(2026-05-23 使用者已回報全數通過)

---

## 通用心法（給未來的 Pi 端 debug）

1. **Pi 是 Debian Buster + GLIBC 2.28**(2026-05-23 確認)。任何 piwheels 預編譯 wheel 報 `GLIBC_X.XX not found` → 一律 `pip install --no-binary :all: --index-url https://pypi.org/simple/ <package>` 跳過 piwheels source build。
2. **Python 3.11 是 source build 在 `~/Python-3.11.9/`**。未來缺任何 stdlib C extension → apt 裝對應 `*-dev` → `cd ~/Python-3.11.9 && make clean && ./configure --enable-optimizations --prefix=/usr/local && make -j4 && sudo make altinstall`。
3. **C extension wheel(如 Pillow)依賴的 `.so.X` 版本可能高於 Buster** → 用 source build 配上系統現有 `*-dev` 版本即可,不必升級系統 lib。
