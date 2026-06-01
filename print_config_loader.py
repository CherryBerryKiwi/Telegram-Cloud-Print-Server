import copy
import json
import re
from pathlib import Path
from typing import Any, Optional


MM_PER_INCH = 25.4


def get_config_path_for_file(file_path=None):
    current_dir = Path(__file__).resolve().parent
    return current_dir / "printing" / "print_settings.config"


def deep_merge(defaults: dict, override: Any) -> dict:
    result = copy.deepcopy(defaults)

    if not isinstance(override, dict):
        return result

    for key, value in override.items():
        if value is None:
            continue

        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value

    return result


def as_bool(value, default=False):
    if isinstance(value, bool):
        return value

    if isinstance(value, str):
        v = value.strip().lower()
        if v in {"true", "yes", "y", "1", "on"}:
            return True
        if v in {"false", "no", "n", "0", "off"}:
            return False

    return default


def as_int(value, default=0, minimum: Optional[int] = None, maximum: Optional[int] = None):
    try:
        v = int(value)
    except Exception:
        return default

    if minimum is not None and v < minimum:
        return default
    if maximum is not None and v > maximum:
        return default

    return v


def as_float(value, default=0.0, minimum: Optional[float] = None, maximum: Optional[float] = None):
    try:
        v = float(value)
    except Exception:
        return default

    if minimum is not None and v < minimum:
        return default
    if maximum is not None and v > maximum:
        return default

    return v


def as_str(value, default=""):
    if value is None:
        return default
    return str(value).strip()


def parse_paper_size_mm(text: str):
    """
    Đọc kiểu: 76mm * 130mm, 76 x 130, 76×130mm.
    Trả về (width_mm, height_mm) hoặc None.
    """
    if not text:
        return None

    s = str(text).lower().replace("×", "x").replace("*", "x")
    nums = re.findall(r"(\d+(?:\.\d+)?)\s*mm?", s)

    if len(nums) < 2:
        nums = re.findall(r"\d+(?:\.\d+)?", s)

    if len(nums) >= 2:
        try:
            return float(nums[0]), float(nums[1])
        except Exception:
            return None

    return None


def normalize_job_config(config, defaults):
    raw_config = config if isinstance(config, dict) else {}
    cfg = deep_merge(defaults, raw_config)

    # Alias ngắn để sửa config cho tiện.
    if "printer" in raw_config and "printer_name" not in raw_config:
        cfg["printer_name"] = raw_config.get("printer")

    if "paper_size" in raw_config and "paper_size_text" not in raw_config:
        cfg["paper_size_text"] = raw_config.get("paper_size")

    if "pages" in raw_config and "print_pages" not in raw_config:
        cfg["print_pages"] = raw_config.get("pages")

    if "pdf_to_printer_exe" in raw_config and "pdftoprinter_exe" not in raw_config:
        cfg["pdftoprinter_exe"] = raw_config.get("pdf_to_printer_exe")

    if "copies" in raw_config:
        cfg["copies"] = raw_config.get("copies")

    cfg["printer_name"] = as_str(cfg.get("printer_name"), defaults.get("printer_name", ""))
    cfg["pdftoprinter_exe"] = as_str(cfg.get("pdftoprinter_exe"), defaults.get("pdftoprinter_exe", ""))
    cfg["paper_size_text"] = as_str(cfg.get("paper_size_text"), defaults.get("paper_size_text", ""))
    cfg["print_pages"] = as_str(cfg.get("print_pages"), defaults.get("print_pages", "All"))

    parsed_size = parse_paper_size_mm(cfg.get("paper_size_text", ""))
    default_width = defaults.get("paper_width_mm", 76)
    default_height = defaults.get("paper_height_mm", 130)

    cfg["paper_width_mm"] = as_float(cfg.get("paper_width_mm"), default_width, minimum=1)
    cfg["paper_height_mm"] = as_float(cfg.get("paper_height_mm"), default_height, minimum=1)

    # Nếu config chỉ có paper_size_text thì lấy kích thước từ text.
    if parsed_size and "paper_width_mm" not in raw_config and "paper_height_mm" not in raw_config:
        cfg["paper_width_mm"], cfg["paper_height_mm"] = parsed_size

    cfg["copies"] = as_int(cfg.get("copies"), defaults.get("copies", 1), minimum=1, maximum=99)
    cfg["direct_print_pdf"] = as_bool(cfg.get("direct_print_pdf"), defaults.get("direct_print_pdf", True))
    cfg["render_pdf_files_with_chrome"] = as_bool(
        cfg.get("render_pdf_files_with_chrome"),
        defaults.get("render_pdf_files_with_chrome", False),
    )
    cfg["keep_temp_pdf"] = as_bool(cfg.get("keep_temp_pdf"), defaults.get("keep_temp_pdf", True))
    cfg["cleanup_temp_pdf_after_success"] = as_bool(
        cfg.get("cleanup_temp_pdf_after_success"),
        defaults.get("cleanup_temp_pdf_after_success", False),
    )
    cfg["fail_on_pdftoprinter_nonzero"] = as_bool(
        cfg.get("fail_on_pdftoprinter_nonzero"),
        defaults.get("fail_on_pdftoprinter_nonzero", True),
    )

    cfg["web_render_wait_sec"] = as_float(cfg.get("web_render_wait_sec"), defaults.get("web_render_wait_sec", 3), minimum=0)
    cfg["after_document_ready_wait_sec"] = as_float(
        cfg.get("after_document_ready_wait_sec"),
        defaults.get("after_document_ready_wait_sec", 1),
        minimum=0,
    )
    cfg["pdftoprinter_wait_sec"] = as_float(
        cfg.get("pdftoprinter_wait_sec"),
        defaults.get("pdftoprinter_wait_sec", 2),
        minimum=0,
    )
    cfg["pdftoprinter_timeout_sec"] = as_float(
        cfg.get("pdftoprinter_timeout_sec"),
        defaults.get("pdftoprinter_timeout_sec", 60),
        minimum=1,
    )
    cfg["chrome_start_timeout_sec"] = as_float(
        cfg.get("chrome_start_timeout_sec"),
        defaults.get("chrome_start_timeout_sec", 15),
        minimum=1,
    )
    cfg["page_load_timeout_sec"] = as_float(
        cfg.get("page_load_timeout_sec"),
        defaults.get("page_load_timeout_sec", 25),
        minimum=1,
    )

    cfg["print_background"] = as_bool(cfg.get("print_background"), defaults.get("print_background", True))
    cfg["prefer_css_page_size"] = as_bool(
        cfg.get("prefer_css_page_size"),
        defaults.get("prefer_css_page_size", False),
    )
    cfg["landscape"] = as_bool(cfg.get("landscape"), defaults.get("landscape", False))
    cfg["scale"] = as_float(cfg.get("scale"), defaults.get("scale", 1.0), minimum=0.1, maximum=2.0)
    cfg["margin_top_mm"] = as_float(cfg.get("margin_top_mm"), defaults.get("margin_top_mm", 0), minimum=0)
    cfg["margin_bottom_mm"] = as_float(cfg.get("margin_bottom_mm"), defaults.get("margin_bottom_mm", 0), minimum=0)
    cfg["margin_left_mm"] = as_float(cfg.get("margin_left_mm"), defaults.get("margin_left_mm", 0), minimum=0)
    cfg["margin_right_mm"] = as_float(cfg.get("margin_right_mm"), defaults.get("margin_right_mm", 0), minimum=0)

    cfg["normalize_pdf_before_print"] = as_bool(
        cfg.get("normalize_pdf_before_print"),
        defaults.get("normalize_pdf_before_print", True),
    )
    cfg["pdf_fit_margin_mm"] = as_float(
        cfg.get("pdf_fit_margin_mm"),
        defaults.get("pdf_fit_margin_mm", 1.5),
        minimum=0,
        maximum=20,
    )
    cfg["pdf_fit_margin_left_mm"] = as_float(
        cfg.get("pdf_fit_margin_left_mm"),
        cfg.get("pdf_fit_margin_mm", defaults.get("pdf_fit_margin_mm", 1.5)),
        minimum=0,
        maximum=20,
    )
    cfg["pdf_fit_margin_right_mm"] = as_float(
        cfg.get("pdf_fit_margin_right_mm"),
        cfg.get("pdf_fit_margin_mm", defaults.get("pdf_fit_margin_mm", 1.5)),
        minimum=0,
        maximum=20,
    )
    cfg["pdf_fit_margin_top_mm"] = as_float(
        cfg.get("pdf_fit_margin_top_mm"),
        cfg.get("pdf_fit_margin_mm", defaults.get("pdf_fit_margin_mm", 1.5)),
        minimum=0,
        maximum=20,
    )
    cfg["pdf_fit_margin_bottom_mm"] = as_float(
        cfg.get("pdf_fit_margin_bottom_mm"),
        cfg.get("pdf_fit_margin_mm", defaults.get("pdf_fit_margin_mm", 1.5)),
        minimum=0,
        maximum=20,
    )
    cfg["pdf_fit_scale"] = as_float(
        cfg.get("pdf_fit_scale"),
        defaults.get("pdf_fit_scale", 0.96),
        minimum=0.1,
        maximum=2.0,
    )
    cfg["pdf_fit_allow_upscale"] = as_bool(
        cfg.get("pdf_fit_allow_upscale"),
        defaults.get("pdf_fit_allow_upscale", True),
    )

    cfg["image_fit"] = as_str(cfg.get("image_fit"), defaults.get("image_fit", "contain")).lower()
    if cfg["image_fit"] not in {"contain", "cover", "fill"}:
        cfg["image_fit"] = defaults.get("image_fit", "contain")

    return cfg


def load_print_job_config(file_path, defaults):
    config_path = get_config_path_for_file(file_path)

    if not config_path.exists():
        cfg = normalize_job_config({}, defaults)
        return cfg, config_path, "CONFIG MISSING -> USING DEFAULTS"

    try:
        with open(config_path, "r", encoding="utf-8-sig") as f:
            raw = json.load(f)

        if not isinstance(raw, dict):
            cfg = normalize_job_config({}, defaults)
            return cfg, config_path, "CONFIG ROOT INVALID -> USING DEFAULTS"

        cfg = normalize_job_config(raw, defaults)
        return cfg, config_path, "CONFIG LOADED"

    except json.JSONDecodeError as e:
        cfg = normalize_job_config({}, defaults)
        return cfg, config_path, f"CONFIG JSON INVALID -> USING DEFAULTS | {e}"

    except Exception as e:
        cfg = normalize_job_config({}, defaults)
        return cfg, config_path, f"CONFIG READ FAILED -> USING DEFAULTS | {e}"
