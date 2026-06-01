import base64
import html
import json
import os
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

from pypdf import PdfReader, PdfWriter, Transformation
from pypdf._page import PageObject
import websocket  # pip install websocket-client


MM_PER_INCH = 25.4
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}
WEB_EXTS = {".html", ".htm", ".txt", ".url"}
PDF_EXTS = {".pdf"}


class CDP:
    def __init__(self, ws_url):
        self.ws = websocket.create_connection(
            ws_url,
            timeout=15,
            suppress_origin=True,
        )
        self._id = 0

    def call(self, method, params=None):
        self._id += 1
        msg = {
            "id": self._id,
            "method": method,
            "params": params or {},
        }
        self.ws.send(json.dumps(msg))

        while True:
            resp = json.loads(self.ws.recv())

            if resp.get("id") == self._id:
                if "error" in resp:
                    raise RuntimeError(resp["error"])
                return resp.get("result")

    def eval(self, js, await_promise=False, timeout_ms=None):
        params = {
            "expression": js,
            "awaitPromise": await_promise,
            "returnByValue": True,
        }
        if timeout_ms is not None:
            params["timeout"] = int(timeout_ms)
        return self.call("Runtime.evaluate", params)

    def close(self):
        try:
            self.ws.close()
        except Exception:
            pass


class ChromePdfRenderer:
    def __init__(self, engine_config):
        self.chrome_exe = engine_config["chrome_exe"]
        self.debug_port = int(engine_config.get("debug_port", 9222))
        self.profile_dir = engine_config["profile_dir"]
        self.chrome_headless = bool(engine_config.get("chrome_headless", True))
        self.terminate_chrome_after_job = bool(engine_config.get("terminate_chrome_after_job", True))

    def http_text(self, url, method="GET", timeout=5):
        req = urllib.request.Request(url, method=method)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="replace")

    def http_json(self, url, method="GET", timeout=5):
        text = self.http_text(url, method=method, timeout=timeout)
        return json.loads(text)

    def start_chrome(self):
        Path(self.profile_dir).mkdir(parents=True, exist_ok=True)

        args = [
            self.chrome_exe,
            f"--remote-debugging-port={self.debug_port}",
            "--remote-debugging-address=127.0.0.1",
            f"--remote-allow-origins=http://127.0.0.1:{self.debug_port}",
            f"--user-data-dir={self.profile_dir}",
            "--no-first-run",
            "--disable-session-crashed-bubble",
            "--disable-popup-blocking",
            "--disable-background-timer-throttling",
            "--disable-renderer-backgrounding",
            "--disable-features=CalculateNativeWinOcclusion",
            "--allow-file-access-from-files",
        ]

        if self.chrome_headless:
            args += [
                "--headless=new",
                "--disable-gpu",
                "--window-size=900,1400",
            ]
        else:
            args += [
                "--new-window",
                "--start-maximized",
                "--window-size=1000,1400",
                "--window-position=50,50",
            ]

        print("Starting Chrome renderer:", self.chrome_exe)
        return subprocess.Popen(args)

    def wait_devtools_ready(self, timeout=15):
        end = time.time() + float(timeout)
        last_error = None

        while time.time() < end:
            try:
                return self.http_json(f"http://127.0.0.1:{self.debug_port}/json/version")
            except Exception as e:
                last_error = e
                time.sleep(0.25)

        raise RuntimeError(f"Chrome DevTools not ready. Last error: {last_error}")

    def list_targets(self):
        return self.http_json(f"http://127.0.0.1:{self.debug_port}/json")

    def close_target(self, target_id):
        try:
            return self.http_text(
                f"http://127.0.0.1:{self.debug_port}/json/close/{target_id}",
                method="GET",
            )
        except Exception as e:
            print(f"[WARN] Could not close target {target_id}: {e}")
            return None

    def open_new_tab(self, url="about:blank"):
        encoded = urllib.parse.quote(url, safe="")
        api_url = f"http://127.0.0.1:{self.debug_port}/json/new?{encoded}"

        try:
            return self.http_json(api_url, method="PUT")
        except Exception:
            return self.http_json(api_url, method="GET")

    def close_old_tabs_except(self, keep_id=None):
        closed = 0
        for t in self.list_targets():
            if t.get("type") != "page":
                continue
            tid = t.get("id")
            if keep_id and tid == keep_id:
                continue
            self.close_target(tid)
            closed += 1
        if closed:
            time.sleep(0.3)
        return closed


def mm_to_in(mm_value):
    return float(mm_value) / MM_PER_INCH


def mm_to_pt(mm_value):
    return float(mm_value) * 72.0 / MM_PER_INCH


def safe_float(value, default):
    try:
        return float(value)
    except Exception:
        return float(default)


def safe_int(value, default):
    try:
        return int(value)
    except Exception:
        return int(default)


def safe_stem(text, fallback="job"):
    text = str(text or fallback)
    text = re.sub(r'[<>:"/\\|?*\r\n\t]+', "_", text)
    text = re.sub(r"\s+", " ", text).strip(" .")
    if not text:
        text = fallback
    return text[:120]


def ensure_dir(path):
    Path(path).mkdir(parents=True, exist_ok=True)


def make_temp_pdf_path(target_file, job_config, engine_config):
    target_file = Path(target_file)
    project_dir = Path(__file__).resolve().parent
    configured = engine_config.get("rendered_pdf_dir") or job_config.get("rendered_pdf_dir")

    if configured:
        temp_dir = Path(configured)
    else:
        temp_dir = project_dir / "_rendered_jobs"

    ensure_dir(temp_dir)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
    name = f"{stamp}_{safe_stem(target_file.stem)}.pdf"
    return temp_dir / name


def read_url_shortcut(path: Path) -> str:
    """
    Đọc file Windows .url dạng:
    [InternetShortcut]
    URL=https://example.com
    """
    text = path.read_text(encoding="utf-8-sig", errors="ignore")

    for line in text.splitlines():
        line = line.strip()
        if line.lower().startswith("url="):
            url = line[4:].strip()
            parsed = urllib.parse.urlparse(url)
            if parsed.scheme.lower() not in {"http", "https"}:
                raise RuntimeError(f"URL scheme không hỗ trợ trong file .url: {url}")
            return url

    raise RuntimeError(f"File .url không có dòng URL=: {path}")


def html_wrapper_for_image(image_path: Path, job_config):
    fit = job_config.get("image_fit", "contain")
    image_uri = image_path.resolve().as_uri()
    title = html.escape(image_path.name)

    return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>{title}</title>
<style>
  @page {{ size: {job_config['paper_width_mm']}mm {job_config['paper_height_mm']}mm; margin: 0; }}
  html, body {{ width: 100%; height: 100%; margin: 0; padding: 0; overflow: hidden; background: white; }}
  .page {{ width: 100vw; height: 100vh; display: flex; align-items: center; justify-content: center; }}
  img {{ width: 100%; height: 100%; object-fit: {fit}; display: block; }}
</style>
</head>
<body>
  <div class="page"><img src="{image_uri}"></div>
</body>
</html>"""


def html_wrapper_for_text(text_path: Path, job_config):
    text = text_path.read_text(encoding="utf-8-sig", errors="replace")
    escaped = html.escape(text)
    title = html.escape(text_path.name)

    return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>{title}</title>
<style>
  @page {{ size: {job_config['paper_width_mm']}mm {job_config['paper_height_mm']}mm; margin: 0; }}
  html, body {{ margin: 0; padding: 0; background: white; }}
  body {{ font-family: Arial, sans-serif; font-size: 12px; line-height: 1.25; }}
  .page {{ box-sizing: border-box; width: 100vw; min-height: 100vh; padding: 4mm; white-space: pre-wrap; word-break: break-word; }}
</style>
</head>
<body>
<div class="page">{escaped}</div>
</body>
</html>"""


def create_render_input_if_needed(target_file: Path, job_config, engine_config):
    """
    Trả về URL để Chrome mở.
    - .url: mở URL thật.
    - ảnh: tạo HTML wrapper để ảnh fit đúng tem.
    - .txt: tạo HTML wrapper để text dễ đọc hơn.
    - .html/.htm/.pdf: mở file trực tiếp.
    """
    suffix = target_file.suffix.lower()

    if suffix == ".url":
        return read_url_shortcut(target_file), None

    if suffix in IMAGE_EXTS or suffix == ".txt":
        project_dir = Path(__file__).resolve().parent
        wrapper_dir = Path(engine_config.get("wrapper_html_dir") or project_dir / "_render_wrappers")
        ensure_dir(wrapper_dir)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        wrapper_path = wrapper_dir / f"{stamp}_{safe_stem(target_file.stem)}.html"

        if suffix in IMAGE_EXTS:
            wrapper_path.write_text(html_wrapper_for_image(target_file, job_config), encoding="utf-8")
        else:
            wrapper_path.write_text(html_wrapper_for_text(target_file, job_config), encoding="utf-8")

        return wrapper_path.resolve().as_uri(), wrapper_path

    return target_file.resolve().as_uri(), None


def wait_for_document_ready(page, timeout_sec):
    timeout_ms = int(float(timeout_sec) * 1000)

    js = """
    new Promise(resolve => {
        const start = Date.now();

        const timer = setInterval(() => {
            const href = location.href || "";
            const ready = document.readyState;
            const title = document.title || "";

            const notBlank = href && href !== "about:blank";
            const loaded = ready === "complete";

            if (notBlank && loaded) {
                clearInterval(timer);
                resolve({
                    ok: true,
                    readyState: ready,
                    url: href,
                    title: title
                });
                return;
            }

            if (Date.now() - start > %d) {
                clearInterval(timer);
                resolve({
                    ok: false,
                    readyState: ready,
                    url: href,
                    title: title,
                    reason: "timeout"
                });
            }
        }, 200);
    });
    """ % timeout_ms

    result = page.eval(js, await_promise=True, timeout_ms=timeout_ms + 1000)
    return result.get("result", {}).get("value")


def print_to_pdf_with_chrome(target_file, job_config, engine_config):
    target_file = Path(target_file)
    renderer = ChromePdfRenderer(engine_config)
    chrome = None
    page = None
    wrapper_path = None

    try:
        chrome = renderer.start_chrome()
        renderer.wait_devtools_ready(timeout=job_config.get("chrome_start_timeout_sec", 15))

        open_url, wrapper_path = create_render_input_if_needed(target_file, job_config, engine_config)

        # Mở tab trắng trước, không nhét URL dài vào /json/new?... nữa
        page_target = renderer.open_new_tab("about:blank")
        renderer.close_old_tabs_except(keep_id=page_target.get("id"))

        page = CDP(page_target["webSocketDebuggerUrl"])
        page.call("Runtime.enable")
        page.call("Page.enable")
        if not renderer.chrome_headless:
            page.call("Page.bringToFront")
        page.call("Emulation.setEmulatedMedia", {"media": "print"})

        print("Render target:", open_url)

        nav = page.call("Page.navigate", {"url": open_url})
        print("Navigate result:", json.dumps(nav, ensure_ascii=False))

        time.sleep(0.5)

        ready_value = wait_for_document_ready(page, job_config.get("page_load_timeout_sec", 25))
        print("Document ready:", json.dumps(ready_value, ensure_ascii=False))
        page_state = page.eval("""
        (() => ({
            url: location.href,
            title: document.title,
            text: (document.body ? document.body.innerText : "").slice(0, 500)
        }))()
        """)

        print("Actual page state:")
        print(json.dumps(page_state.get("result", {}).get("value"), indent=2, ensure_ascii=False))
        
        suffix = target_file.suffix.lower()

        if suffix == ".url":
            wait1 = float(job_config.get("web_render_wait_sec", 0))
            wait2 = float(job_config.get("after_document_ready_wait_sec", 0))
            extra_wait = max(wait1, wait2)
        elif suffix in IMAGE_EXTS:
            extra_wait = float(job_config.get("image_render_wait_sec", 0.3))
        elif suffix in {".html", ".htm"}:
            extra_wait = float(job_config.get("local_html_render_wait_sec", 0.5))
        elif suffix == ".txt":
            extra_wait = float(job_config.get("text_render_wait_sec", 0.2))
        else:
            extra_wait = 0

        if extra_wait > 0:
            print(f"Wait for render: {extra_wait} sec")
            time.sleep(extra_wait)

        # Cố gắng chờ font sẵn sàng. Nếu browser không hỗ trợ thì bỏ qua.
        try:
            page.eval("document.fonts ? document.fonts.ready.then(() => true) : true", await_promise=True, timeout_ms=5000)
        except Exception as e:
            print("[WARN] Font wait skipped:", e)

        params = {
            "landscape": bool(job_config.get("landscape", False)),
            "displayHeaderFooter": False,
            "printBackground": bool(job_config.get("print_background", True)),
            "scale": float(job_config.get("scale", 1.0)),
            "paperWidth": mm_to_in(job_config.get("paper_width_mm", 76)),
            "paperHeight": mm_to_in(job_config.get("paper_height_mm", 130)),
            "marginTop": mm_to_in(job_config.get("margin_top_mm", 0)),
            "marginBottom": mm_to_in(job_config.get("margin_bottom_mm", 0)),
            "marginLeft": mm_to_in(job_config.get("margin_left_mm", 0)),
            "marginRight": mm_to_in(job_config.get("margin_right_mm", 0)),
            "preferCSSPageSize": bool(job_config.get("prefer_css_page_size", False)),
            "transferMode": "ReturnAsBase64",
        }

        pages = str(job_config.get("print_pages", "All") or "All").strip()
        if pages and pages.lower() != "all":
            params["pageRanges"] = pages

        print("Page.printToPDF params:")
        print(json.dumps(params, indent=2, ensure_ascii=False))

        pdf_result = page.call("Page.printToPDF", params)
        if not pdf_result or "data" not in pdf_result:
            raise RuntimeError("Page.printToPDF did not return PDF data.")

        temp_pdf = make_temp_pdf_path(target_file, job_config, engine_config)
        temp_pdf.write_bytes(base64.b64decode(pdf_result["data"]))

        print("Rendered PDF:", temp_pdf)
        return {
            "ok": True,
            "source": str(target_file),
            "open_url": open_url,
            "rendered_pdf": str(temp_pdf),
            "wrapper_html": str(wrapper_path) if wrapper_path else None,
        }

    finally:
        if page:
            page.close()

        if chrome and renderer.terminate_chrome_after_job:
            try:
                chrome.terminate()
                try:
                    chrome.wait(timeout=5)
                except Exception:
                    chrome.kill()
            except Exception:
                pass

        # Wrapper HTML chỉ là file trung gian; giữ lại nếu keep_temp_pdf=True để dễ debug.
        if wrapper_path and not bool(job_config.get("keep_temp_pdf", True)):
            try:
                Path(wrapper_path).unlink(missing_ok=True)
            except Exception:
                pass


def make_normalized_pdf_path(target_file, job_config, engine_config):
    target_file = Path(target_file)
    project_dir = Path(__file__).resolve().parent
    configured = engine_config.get("rendered_pdf_dir") or job_config.get("rendered_pdf_dir")

    if configured:
        temp_dir = Path(configured)
    else:
        temp_dir = project_dir / "_rendered_jobs"

    ensure_dir(temp_dir)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
    name = f"{stamp}_{safe_stem(target_file.stem)}_fit.pdf"
    return temp_dir / name


def normalize_pdf_to_label(input_pdf, job_config, engine_config):
    """
    Tạo PDF mới có đúng page size tem và scale nội dung vào vùng in.

    Lý do: PDFtoPrinter hầu như không cho điều khiển fit/scale qua command line.
    Nếu PDF gốc lớn hơn giấy driver, driver sẽ crop. Hàm này xử lý trước: 
    mỗi trang PDF gốc được đặt vào một trang 76x130mm mới, scale contain và căn giữa.
    """
    input_pdf = Path(input_pdf)
    if not input_pdf.exists():
        raise FileNotFoundError(f"PDF cần normalize không tồn tại: {input_pdf}")

    target_w = mm_to_pt(job_config.get("paper_width_mm", 76))
    target_h = mm_to_pt(job_config.get("paper_height_mm", 130))

    # Có thể dùng 1-3mm nếu máy in có vùng chết ở mép.
    margin_all = safe_float(job_config.get("pdf_fit_margin_mm", 0), 0)
    margin_left = safe_float(job_config.get("pdf_fit_margin_left_mm", margin_all), margin_all)
    margin_right = safe_float(job_config.get("pdf_fit_margin_right_mm", margin_all), margin_all)
    margin_top = safe_float(job_config.get("pdf_fit_margin_top_mm", margin_all), margin_all)
    margin_bottom = safe_float(job_config.get("pdf_fit_margin_bottom_mm", margin_all), margin_all)

    left_pt = mm_to_pt(margin_left)
    right_pt = mm_to_pt(margin_right)
    top_pt = mm_to_pt(margin_top)
    bottom_pt = mm_to_pt(margin_bottom)

    fit_w = max(1.0, target_w - left_pt - right_pt)
    fit_h = max(1.0, target_h - top_pt - bottom_pt)
    extra_scale = safe_float(job_config.get("pdf_fit_scale", 1.0), 1.0)

    reader = PdfReader(str(input_pdf))
    writer = PdfWriter()

    page_infos = []
    for index, src_page in enumerate(reader.pages, start=1):
        # Đưa rotation của trang vào content để width/height tính đúng hơn.
        try:
            src_page.transfer_rotation_to_content()
        except Exception:
            pass

        box = src_page.cropbox
        src_x0 = float(box.left)
        src_y0 = float(box.bottom)
        src_w = float(box.width)
        src_h = float(box.height)

        if src_w <= 0 or src_h <= 0:
            box = src_page.mediabox
            src_x0 = float(box.left)
            src_y0 = float(box.bottom)
            src_w = float(box.width)
            src_h = float(box.height)

        base_scale = min(fit_w / src_w, fit_h / src_h)
        scale = base_scale * extra_scale

        # Không phóng to PDF nhỏ nếu không muốn. Mặc định vẫn phóng to để giống Fit to paper.
        if not bool(job_config.get("pdf_fit_allow_upscale", True)):
            scale = min(scale, 1.0)

        draw_w = src_w * scale
        draw_h = src_h * scale

        tx = left_pt + (fit_w - draw_w) / 2.0
        ty = bottom_pt + (fit_h - draw_h) / 2.0

        blank = PageObject.create_blank_page(width=target_w, height=target_h)

        transform = (
            Transformation()
            .translate(tx=-src_x0, ty=-src_y0)
            .scale(scale)
            .translate(tx=tx, ty=ty)
        )

        blank.merge_transformed_page(src_page, transform)
        writer.add_page(blank)

        page_infos.append({
            "page": index,
            "source_width_pt": round(src_w, 3),
            "source_height_pt": round(src_h, 3),
            "target_width_pt": round(target_w, 3),
            "target_height_pt": round(target_h, 3),
            "scale": round(scale, 5),
            "margin_mm": {
                "left": margin_left,
                "right": margin_right,
                "top": margin_top,
                "bottom": margin_bottom,
            },
        })

    output_pdf = make_normalized_pdf_path(input_pdf, job_config, engine_config)
    with open(output_pdf, "wb") as f:
        writer.write(f)

    print("Normalized/Fitted PDF:", output_pdf)
    print("Normalize info:")
    print(json.dumps(page_infos[:10], indent=2, ensure_ascii=False))
    if len(page_infos) > 10:
        print(f"... {len(page_infos) - 10} more page(s)")

    return {
        "ok": True,
        "source_pdf": str(input_pdf),
        "normalized_pdf": str(output_pdf),
        "paper_width_mm": job_config.get("paper_width_mm", 76),
        "paper_height_mm": job_config.get("paper_height_mm", 130),
        "page_count": len(page_infos),
        "pages": page_infos,
    }


def resolve_pdftoprinter_exe(job_config, engine_config):
    candidates = []

    for value in [
        job_config.get("pdftoprinter_exe"),
        engine_config.get("pdftoprinter_exe"),
        Path(__file__).resolve().parent / "tools" / "PDFtoPrinter.exe",
        "PDFtoPrinter.exe",
    ]:
        if value:
            candidates.append(str(value))

    for candidate in candidates:
        expanded = os.path.expandvars(candidate)
        p = Path(expanded)

        if p.is_file():
            return str(p)

        found = shutil.which(expanded)
        if found:
            return found

    raise FileNotFoundError(
        "Không tìm thấy PDFtoPrinter.exe. Hãy đặt file vào thư mục tools hoặc sửa pdftoprinter_exe trong printing/print_settings.config."
    )


def run_pdftoprinter(pdf_path, job_config, engine_config):
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF cần in không tồn tại: {pdf_path}")

    exe = resolve_pdftoprinter_exe(job_config, engine_config)
    printer_name = str(job_config.get("printer_name", "") or "").strip()
    copies = int(job_config.get("copies", 1) or 1)
    timeout_sec = float(job_config.get("pdftoprinter_timeout_sec", 60))
    wait_sec = float(job_config.get("pdftoprinter_wait_sec", 2))
    fail_on_nonzero = bool(job_config.get("fail_on_pdftoprinter_nonzero", True))

    all_runs = []

    for copy_index in range(1, copies + 1):
        cmd = [exe, str(pdf_path)]
        if printer_name:
            cmd.append(printer_name)

        print(f"PDFtoPrinter copy {copy_index}/{copies}:", cmd)
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
        )

        run_info = {
            "copy": copy_index,
            "returncode": completed.returncode,
            "stdout": completed.stdout[-2000:],
            "stderr": completed.stderr[-2000:],
        }
        all_runs.append(run_info)

        if completed.returncode != 0 and fail_on_nonzero:
            raise RuntimeError(f"PDFtoPrinter returned non-zero code: {run_info}")

        if wait_sec > 0:
            time.sleep(wait_sec)

    return {
        "ok": True,
        "exe": exe,
        "pdf": str(pdf_path),
        "printer_name": printer_name,
        "copies": copies,
        "runs": all_runs,
    }


def should_render_with_chrome(target_file: Path, job_config):
    suffix = target_file.suffix.lower()

    if suffix in PDF_EXTS:
        # Mặc định: PDF gốc gửi thẳng PDFtoPrinter để tránh render lại PDF bằng Chrome viewer.
        return bool(job_config.get("render_pdf_files_with_chrome", False))

    return True


def print_file(target_file, job_config, engine_config):
    target_file = Path(target_file)

    result = {
        "ok": False,
        "printed": False,
        "file": str(target_file),
        "backend": "PDFtoPrinter",
        "renderer": None,
        "rendered_pdf": None,
        "direct_pdf": None,
        "normalized_pdf": None,
        "normalize_info": None,
    }

    if not target_file.exists():
        raise FileNotFoundError(f"Target file does not exist: {target_file}")

    suffix = target_file.suffix.lower()
    if suffix not in PDF_EXTS | WEB_EXTS | IMAGE_EXTS:
        raise RuntimeError(f"File type chưa hỗ trợ: {target_file.suffix}")

    pdf_to_print = target_file
    render_info = None

    if should_render_with_chrome(target_file, job_config):
        result["renderer"] = "Chrome Page.printToPDF"
        render_info = print_to_pdf_with_chrome(target_file, job_config, engine_config)
        pdf_to_print = Path(render_info["rendered_pdf"])
        result["rendered_pdf"] = str(pdf_to_print)
        result["render_info"] = render_info
    else:
        result["renderer"] = "direct original PDF"
        result["direct_pdf"] = str(pdf_to_print)

        pages = str(job_config.get("print_pages", "All") or "All").strip()
        if pages.lower() != "all":
            print("[WARN] PDFtoPrinter thường không xử lý page range. Với PDF gốc nên để print_pages = All.")

    # Quan trọng: PDFtoPrinter không có nút fit/scale đáng tin cậy qua command line.
    # Vì vậy normalize PDF về đúng khổ giấy và fit nội dung trước khi in để tránh crop.
    normalize_before_print = bool(job_config.get("normalize_pdf_before_print", True))
    normalize_info = None

    if normalize_before_print:
        normalize_info = normalize_pdf_to_label(pdf_to_print, job_config, engine_config)
        pdf_to_print = Path(normalize_info["normalized_pdf"])
        result["normalized_pdf"] = str(pdf_to_print)
        result["normalize_info"] = normalize_info

    print_info = run_pdftoprinter(pdf_to_print, job_config, engine_config)

    result["ok"] = True
    result["printed"] = True
    result["print_info"] = print_info

    cleanup = bool(job_config.get("cleanup_temp_pdf_after_success", False))
    keep_temp = bool(job_config.get("keep_temp_pdf", True))
    if cleanup or not keep_temp:
        if render_info and pdf_to_print.exists():
            try:
                pdf_to_print.unlink()
                result["temp_pdf_deleted"] = True
            except Exception as e:
                result["temp_pdf_deleted"] = False
                result["temp_pdf_delete_error"] = str(e)

    return result
