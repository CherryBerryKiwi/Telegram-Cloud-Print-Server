README - AUTO TELEGRAM AND SAMBA PRINT SYSTEM USING PDFtoPrinter
=============================================

HOW TO USE:
- Download this, install_requirements.bat
- Copy everything to C:\chrome-auto-print, 
- Share C:\chrome-auto-print\printing over the LAN using Samba.
- Edit the [set token and rename this file to telegram_listener.py].py 
- Then run run_all.bat
=======


The logic:
- start.py continuously watches the "printing" folder.
- When a new file appears, it opens the file in Chrome to render, then save as PDF.
- It reads settings from printing/print_settings.config and print with PDFtoPrinter.exe
- After printing, the original file is moved to Done Jobs.
- telegram_listener.py receives files/links from Telegram and saves them to the printing folder.
- You can also share the "printing" folder over the LAN using Samba. Just copy files into that folder, and the printer server will handle the rest.

Main changes:
- No Chrome Print Preview.
- No window.print().
- No Print button clicking.
- No pyautogui or pywinauto.
- No need to focus Chrome windows.
- Nothing popped up

PRINT FLOW
==========

1. PDF files:
   Original PDF -> PDFtoPrinter.exe -> Printer

2. .url / web links / HTML / images / TXT:
   Chrome headless renders the file/link into a temporary 76x130mm PDF,
   then PDFtoPrinter.exe sends it to the printer.

FILES
=====

start.py
Main program. It watches:

    C:\chrome-auto-print\printing

To change the print folder, edit:

    PRINT_FOLDER = Path(r"C:\chrome-auto-print\printing")

print_engine.py
Handles printing:
- Renders links/HTML/images/TXT into PDF using Chrome DevTools.
- Sends PDF files to the printer using PDFtoPrinter.exe.

print_config_loader.py
Reads:

    printing/print_settings.config

If the config is missing or invalid, default settings are used.

telegram_listener.py
Receives files/links from Telegram.
HTTP/HTTPS links are saved as .url files and later rendered by Chrome headless.

run_all.bat
Runs both:
- start.py
- telegram_listener.py

run_start_only.bat
Runs only the auto printer.

install_requirements.bat
Installs required Python packages:
- websocket-client
- python-telegram-bot

SETUP
=====

1. Install Python.
2. Install Google Chrome.
3. Run:

    install_requirements.bat

4. Download PDFtoPrinter.exe and place it here:

    tools\PDFtoPrinter.exe

5. Edit:

    printing\print_settings.config

6. Run:

    run_start_only.bat

Or, if using Telegram:

    run_all.bat

IMPORTANT CONFIG NOTES
======================

printer_name
Windows printer name. It must match the printer name exactly.

pdftoprinter_exe
Path to PDFtoPrinter.exe.

paper_width_mm / paper_height_mm
Temporary PDF size for links, HTML, images, and TXT files.
For 76x130mm labels, use:

    76 x 130

For original PDF files, the printer driver’s default paper size is important.
Set the HPRT printer default paper size in Windows to 76x130mm.

copies
The program prints multiple times if copies > 1.
This is more reliable than using Chrome’s Copies box.

direct_print_pdf
Recommended: true.
Original PDF files are sent directly to PDFtoPrinter.

render_pdf_files_with_chrome
Recommended: false.
Do not enable unless you intentionally want Chrome to re-render PDFs.

web_render_wait_sec
Wait time for web pages to finish rendering.
Increase to 5 or 8 if pages load slowly.

image_fit
For images:
- contain = keep ratio, no crop
- cover = fill page, may crop
- fill = stretch, may distort

keep_temp_pdf
true = keep rendered PDFs for checking.
false = delete them after printing.

HOW LINKS WORK
==============

Telegram links are saved as .url files:

    [InternetShortcut]
    URL=https://example.com/label

The program reads the real URL, opens it in Chrome headless, waits for rendering,
creates a PDF using Page.printToPDF, then prints it using PDFtoPrinter.exe.

STRENGTHS
=========

1. No Chrome Print button.
2. No window focus required.
3. No Chrome Print Preview dependency.
4. Can run with Chrome headless.
5. JavaScript-rendered web pages can still be printed.
6. Temporary PDFs make layout debugging easier.
7. If printing fails, the original file is not moved to Done Jobs.

NOTES
=====

1. PDFtoPrinter.exe must exist.
2. Set the HPRT N41 default paper size in Windows to 76x130mm.
3. If a web page requires login, the Chrome dev_profile must still be logged in.
4. If login expires or captcha appears, Chrome may print the login/captcha page.
5. Printer or driver errors such as offline, paper jam, or spooler issues may still show Windows popups.

TEST ORDER
==========

Test 1: Copy a PDF label into the printing folder.
Test 2: Copy a JPG/PNG image into the printing folder.
Test 3: Create a .url file and test a simple link.
Test 4: If web labels miss data, increase:

    web_render_wait_sec

RUNNING MORE HIDDEN
===================

Chrome already runs headless.
The .bat file still opens a console window.

For fully hidden running, use Windows Task Scheduler with pythonw.exe,
or create a service with NSSM.

Do not do this before testing successfully with the console.

TELEGRAM SECURITY
=================

In telegram_listener.py, set:

    BOT_TOKEN = "YOUR_BOT_TOKEN"

Also set ALLOWED_CHAT_IDS to prevent strangers from sending print jobs:

    ALLOWED_CHAT_IDS = [123456789]

Send /start to the bot once to get your Chat ID.

ANTI-CROP / FIT TO PAPER UPDATE
===============================

PDFtoPrinter has limited control over fit-to-paper or scaling.
So this version can normalize PDFs before printing:

    normalize_pdf_before_print = true

When enabled, every PDF is converted into a new PDF with the exact paper size:

    76 x 130 mm

The original content is scaled using contain mode and centered.

Recommended settings:

    "normalize_pdf_before_print": true,
    "pdf_fit_margin_mm": 1.5,
    "pdf_fit_scale": 0.96,
    "pdf_fit_allow_upscale": true

If the printer still crops edges, try:

    "pdf_fit_margin_mm": 2,
    "pdf_fit_scale": 0.94

If it still crops:

    "pdf_fit_margin_mm": 3,
    "pdf_fit_scale": 0.90


README - HỆ THỐNG AUTO PRINT BẰNG PDFtoPrinter
==============================================

MỤC TIÊU
========

Logic:
- start.py đọc liên tục thư mục printing.
- Khi có file mới, chờ file ổn định.
- Đọc config từ printing/print_settings.config.
- In xong thì chuyển file gốc vào Done Jobs.
- telegram_listener.py nhận file/link từ Telegram và lưu vào thư mục printing.

Phần thay đổi lớn:
- Không dùng Chrome Print Preview.
- Không gọi window.print().
- Không click nút Print.
- Không pyautogui.
- Không pywinauto.
- Không cần focus cửa sổ Chrome.

Luồng in mới:

1. Nếu file là PDF:
   PDF gốc -> PDFtoPrinter.exe -> máy in

2. Nếu file là .url / link web / html / ảnh / txt:
   Chrome headless mở file/link -> Page.printToPDF tạo PDF tạm 76x130mm -> PDFtoPrinter.exe -> máy in


CẤU TRÚC FILE
=============

start.py
--------
File chạy chính.
Nó đọc thư mục:

    C:\chrome-auto-print\printing

Nếu muốn đổi thư mục in, sửa dòng trong start.py:

    PRINT_FOLDER = Path(r"C:\chrome-auto-print\printing")

print_engine.py
---------------
Engine in mới.
Nó có 2 nhiệm vụ:
- Dùng Chrome DevTools Protocol để render link/html/ảnh/txt thành PDF.
- Gọi PDFtoPrinter.exe để gửi PDF ra máy in.

print_config_loader.py
----------------------
Đọc file config:

    printing/print_settings.config

Nếu config thiếu hoặc sai JSON, chương trình dùng default trong start.py.

telegram_listener.py
--------------------
Nhận file/link từ Telegram.
Nếu gửi một link HTTP/HTTPS đơn, bot sẽ lưu thành file .url.
start.py sẽ mở file .url, lấy URL thật, dùng Chrome headless render trang đó thành PDF rồi in.

run_all.bat
-----------
Chạy cùng lúc:
- start.py
- telegram_listener.py

run_start_only.bat
------------------
Chỉ chạy auto printer, không chạy Telegram bot.

install_requirements.bat
------------------------
Cài thư viện Python cần thiết:
- websocket-client
- python-telegram-bot


CÀI ĐẶT
=======

1. Cài Python.
2. Cài Google Chrome.
3. Chạy:

    install_requirements.bat

4. Tải PDFtoPrinter.exe và đặt vào:

    tools\PDFtoPrinter.exe

5. Sửa file:

    printing\print_settings.config

6. Chạy:

    run_start_only.bat

hoặc nếu dùng Telegram:

    run_all.bat


FILE CONFIG MẪU
===============

File config nằm ở:

    printing\print_settings.config

Nội dung mẫu:

{
    "printer_name": "HPRT N41",
    "pdftoprinter_exe": "tools\\PDFtoPrinter.exe",

    "paper_size_text": "76mm * 130mm",
    "paper_width_mm": 76,
    "paper_height_mm": 130,

    "print_pages": "All",
    "copies": 1,

    "direct_print_pdf": true,
    "render_pdf_files_with_chrome": false,

    "web_render_wait_sec": 3,
    "after_document_ready_wait_sec": 1,

    "print_background": true,
    "prefer_css_page_size": false,
    "landscape": false,
    "scale": 1.0,

    "margin_top_mm": 0,
    "margin_bottom_mm": 0,
    "margin_left_mm": 0,
    "margin_right_mm": 0,

    "image_fit": "contain",

    "pdftoprinter_wait_sec": 2,
    "pdftoprinter_timeout_sec": 60,
    "fail_on_pdftoprinter_nonzero": true,

    "keep_temp_pdf": true,
    "cleanup_temp_pdf_after_success": false
}


GIẢI THÍCH CONFIG
=================

printer_name
------------
Tên máy in trong Windows.
Ví dụ:

    "printer_name": "HPRT N41"

Tên này phải đúng tên máy in Windows đang thấy.

pdftoprinter_exe
----------------
Đường dẫn PDFtoPrinter.exe.
Mặc định:

    "pdftoprinter_exe": "tools\\PDFtoPrinter.exe"

Nghĩa là đặt PDFtoPrinter.exe trong thư mục tools cạnh start.py.

paper_width_mm / paper_height_mm
--------------------------------
Khổ PDF tạm khi render link/html/ảnh/txt bằng Chrome.
Với tem 76 x 130 mm:

    "paper_width_mm": 76,
    "paper_height_mm": 130

Lưu ý:
- Với PDF gốc in thẳng bằng PDFtoPrinter, khổ thật phụ thuộc PDF gốc và default driver máy in.
- Hãy set default khổ giấy của printer HPRT trong Windows đúng 76x130mm.

print_pages
-----------
Với link/html/ảnh/txt render qua Chrome, có thể dùng:

    "All"
    "1"
    "1-2"

Với PDF gốc gửi thẳng PDFtoPrinter, nên để:

    "All"

Vì PDFtoPrinter thường không chắc hỗ trợ page range qua dòng lệnh đơn giản.

copies
------
Số bản in.
Code sẽ gọi PDFtoPrinter nhiều lần nếu copies > 1.

    "copies": 2

Đây là cách chắc hơn thay vì dựa vào ô Copies của Chrome Preview.

direct_print_pdf
----------------
Nên để true.

    "direct_print_pdf": true

Ý nghĩa:
- PDF gốc không render lại bằng Chrome.
- Gửi thẳng PDFtoPrinter.

render_pdf_files_with_chrome
----------------------------
Mặc định false.

    "render_pdf_files_with_chrome": false

Không nên bật trừ khi bạn cố tình muốn Chrome render lại PDF.
Với tem vận đơn PDF, gửi PDF gốc thẳng cho PDFtoPrinter thường sạch hơn.

web_render_wait_sec
-------------------
Thời gian chờ sau khi trang web load để JS/ảnh/font render xong.
Nếu link render chậm, tăng lên 5 hoặc 8.

    "web_render_wait_sec": 3

print_background
----------------
In background của trang web/html.
Nên để true.

scale
-----
Scale khi Chrome tạo PDF tạm.

    1.0 = 100%
    0.95 = 95%
    1.05 = 105%

margin_*_mm
-----------
Lề PDF tạm.
Với tem nên để 0.

image_fit
---------
Chỉ áp dụng cho ảnh.

    "contain" = giữ nguyên tỉ lệ, không cắt ảnh
    "cover"   = phủ kín trang, có thể bị cắt
    "fill"    = kéo đầy trang, có thể méo ảnh

keep_temp_pdf
-------------
true = giữ PDF tạm trong thư mục _rendered_jobs để kiểm tra.
false = xóa PDF tạm sau khi in.

Khuyên khi test để true.
Khi chạy ổn định lâu dài có thể để false.

cleanup_temp_pdf_after_success
------------------------------
true = in xong thành công thì xóa PDF tạm.
false = giữ lại.


CÁCH HOẠT ĐỘNG VỚI LINK
=======================

Nếu bạn gửi link vào Telegram, bot sẽ lưu thành file .url:

    [InternetShortcut]
    URL=https://example.com/label

start.py phát hiện file .url, print_engine.py đọc dòng URL=, mở URL bằng Chrome headless.
Sau đó code chờ:
- document.readyState complete
- web_render_wait_sec giây để JS render tiếp
- font ready nếu browser hỗ trợ

Rồi gọi:

    Page.printToPDF

để tạo PDF đúng khổ 76x130mm.
Sau đó PDF tạm được gửi ra máy in bằng PDFtoPrinter.exe.


ĐIỂM MẠNH CỦA BẢN NÀY
=====================

1. Không còn phải bấm nút Print trong Chrome.
2. Không còn cần focus cửa sổ.
3. Không còn phụ thuộc Chrome Print Preview.
4. Có thể chạy ẩn bằng Chrome headless.
5. Link web render bằng JS vẫn xử lý được vì Chrome thật vẫn mở trang.
6. PDF tạm giúp kiểm tra lỗi layout dễ hơn.
7. Nếu in lỗi, file gốc không bị move vào Done Jobs.


ĐIỂM CẦN LƯU Ý
==============

1. PDFtoPrinter.exe phải tồn tại.
Nếu chưa đặt đúng file, chương trình sẽ báo:

    Không tìm thấy PDFtoPrinter.exe

2. Máy in HPRT N41 nên được set default khổ giấy 76x130mm trong Windows.
Điều này rất quan trọng với PDF gốc.

3. Nếu web cần đăng nhập, Chrome dev_profile phải còn session đăng nhập.
Thư mục profile riêng nằm ở:

    dev_profile

4. Nếu trang web có captcha hoặc login expired, Chrome vẫn render được nhưng có thể render ra trang login/captcha chứ không phải tem.

5. Nếu driver/máy in báo lỗi như hết giấy/offline/kẹt spooler, Windows vẫn có thể hiện popup. Hướng này loại bỏ Chrome UI, không thể loại bỏ 100% popup từ driver.


THỨ TỰ TEST NÊN LÀM
===================

Test 1: PDF gốc
---------------
Copy một file PDF Shopee/Viettel vào:

    C:\chrome-auto-print\printing

Nếu in đúng, phần PDFtoPrinter + driver OK.

Test 2: Ảnh
-----------
Copy một file .jpg hoặc .png vào thư mục printing.
Nếu in đúng khổ, phần Chrome render PDF tạm OK.

Test 3: Link
------------
Tạo file .url trong thư mục printing:

    test_link.url

Nội dung:

    [InternetShortcut]
    URL=https://example.com

Nếu in được, phần mở link + render web OK.

Test 4: Link render chậm
------------------------
Nếu tem web thiếu dữ liệu, tăng:

    "web_render_wait_sec": 5

hoặc:

    "web_render_wait_sec": 8


NẾU MUỐN CHẠY ẨN HƠN
====================

Chrome đã chạy headless mặc định:

    "chrome_headless": True

trong start.py / ENGINE_CONFIG.

Nhưng start.py vẫn có cửa sổ console nếu chạy bằng .bat.
Muốn ẩn console hoàn toàn thì nên tạo Windows Task Scheduler chạy pythonw.exe hoặc dùng NSSM tạo service.
Đừng làm bước này khi chưa test ổn bằng console, vì console giúp xem log lỗi.


LƯU Ý BẢO MẬT TELEGRAM
======================

Trong telegram_listener.py:

    BOT_TOKEN = "PASTE_YOUR_BOT_TOKEN_HERE"

Bạn phải tự điền token.

Nên điền ALLOWED_CHAT_IDS để tránh ai biết bot cũng gửi file in được:

    ALLOWED_CHAT_IDS = [123456789]

Chạy bot lần đầu, gửi /start để lấy Chat ID.



CẬP NHẬT CHỐNG CROP / FIT TO PAPER
==================================

PDFtoPrinter.exe in PDF rất đơn giản, nhưng gần như không có tham số ổn định để ép Fit to paper hoặc Scale.
Vì vậy bản này có thêm bước normalize PDF trước khi in:

    normalize_pdf_before_print = true

Khi bật, mọi PDF trước khi gửi sang PDFtoPrinter sẽ được tạo lại thành một PDF trung gian có đúng khổ:

    paper_width_mm  = 76
    paper_height_mm = 130

Nội dung trang PDF gốc sẽ được scale kiểu contain và căn giữa vào trang mới. Điều này giúp tránh lỗi bị crop khi PDF gốc lớn hơn khổ giấy của driver.

Các thông số mới trong printing/print_settings.config:

    "normalize_pdf_before_print": true,
    "pdf_fit_margin_mm": 1.5,
    "pdf_fit_scale": 0.96,
    "pdf_fit_allow_upscale": true

Ý nghĩa:

1. normalize_pdf_before_print
   true = luôn fit PDF vào khổ tem trước khi in.
   Khuyên để true.

2. pdf_fit_margin_mm
   Chừa mép an toàn quanh nội dung, đơn vị mm.
   Nếu vẫn bị crop mép, tăng lên 2 hoặc 3.
   Nếu bản in quá nhỏ, giảm về 1 hoặc 0.

3. pdf_fit_scale
   Hệ số thu/phóng thêm sau khi fit.
   0.96 = nhỏ hơn 4% để tránh vùng chết của máy in nhiệt.
   Nếu bản in vẫn bị crop, thử 0.92 hoặc 0.90.
   Nếu bản in quá nhỏ, thử 0.98 hoặc 1.0.

4. pdf_fit_allow_upscale
   true = PDF nhỏ hơn tem có thể được phóng to cho vừa.
   false = không phóng to PDF nhỏ.

Lưu ý:
- Thông số "scale" cũ chỉ ảnh hưởng bước Chrome Page.printToPDF cho HTML/link/ảnh/text.
- Với PDF gốc, muốn chống crop thì chỉnh "pdf_fit_scale" và "pdf_fit_margin_mm".

Nếu máy in HPRT vẫn crop, thử lần lượt:

    "pdf_fit_margin_mm": 2,
    "pdf_fit_scale": 0.94

rồi nếu vẫn crop:

    "pdf_fit_margin_mm": 3,
    "pdf_fit_scale": 0.90

