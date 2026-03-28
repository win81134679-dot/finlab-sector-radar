"""
main.py — FinLab 台股板塊偵測系統 CLI 入口

依賴：rich + questionary
選單架構：
  [1] 全部執行（一鍵 7 燈）
  [2-7] 個別燈號分析
  [8] 彙總表（幾燈亮）
  [A] 掃描/讀取歷史報告
  [B] 設定（Token / 清快取）
  [0] 離開
"""
import logging
import os
import sys
from pathlib import Path

# ── 路徑設定（讓 src. 模組可被解析）───────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import src.ssl_fix  # noqa: F401 — 修正 curl_cffi 中文路徑 SSL 錯誤；必須在所有 yfinance 呼叫前執行

# ── 延遲引入（需 venv 啟動後才能 import）────────────────────────────────
import questionary
from rich import print as rprint
from rich.columns import Columns
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.table import Table
from rich.text import Text

# ── 內部模組 ───────────────────────────────────────────────────────────
from src import config
from src.data_fetcher import fetcher
from src.sector_map import sector_map
from src.reporters import file_scanner
from src.reporters.markdown_writer import write_report

console = Console()

logging.basicConfig(
    level=logging.WARNING,
    format="%(levelname)s %(name)s — %(message)s",
)

# ── 表格樣式 ───────────────────────────────────────────────────────────
_LEVEL_STYLE = {
    "強烈關注": "bold red",
    "觀察中":   "bold yellow",
    "忽略":     "dim",
}

MENU_ITEMS = [
    ("1", "🚀 全部執行（一鍵 7 燈完整分析）"),
    ("2", "💰 燈1：月營收 YoY 拐點"),
    ("3", "🏦 燈2：法人籌碼共振"),
    ("4", "📦 燈3：庫存循環偵測"),
    ("5", "📈 燈4：技術突破偵測"),
    ("6", "🔀 燈5：板塊相對強度 RRG"),
    ("7", "💎 燈6：籌碼集中掃描"),
    ("8", "🌐 燈7：宏觀環境濾網（FRED + SOX）"),
    ("9", "🔦 多維訊號彙總表（幾燈亮）"),
    ("A", "📁 掃描 / 讀取歷史報告"),
    ("B", "⚙️  設定（Token 管理 / 清快取）"),
    ("0", "離開"),
]


# ══════════════════════════════════════════════════════════════════════════
# 工具函式
# ══════════════════════════════════════════════════════════════════════════

def _header():
    console.print(Panel.fit(
        "[bold cyan]FinLab 台股板塊偵測系統[/bold cyan]  [dim]v1.0[/dim]",
        border_style="cyan",
    ))


def _ensure_login() -> bool:
    """確保 FinLab 已登入；若尚未登入則嘗試自動登入。"""
    if fetcher.is_logged_in():
        return True
    if not config.is_finlab_token_set():
        console.print("[bold red]⚠ FINLAB_API_TOKEN 未設定！[/bold red]")
        console.print("請選擇 [B] 設定，或直接編輯 [bold].env[/bold] 填入 Token")
        return False
    with console.status("[cyan]連線至 FinLab...[/cyan]"):
        ok = fetcher.login()
    if ok:
        console.print("[green]✅ FinLab 登入成功[/green]")
    else:
        console.print("[red]❌ FinLab 登入失敗，請確認 Token 正確[/red]")
    return ok


def _ensure_sectors() -> bool:
    """確保板塊定義已載入。"""
    if sector_map.loaded:
        return True
    n = sector_map.load()
    if n == 0:
        console.print(f"[red]⚠ 板塊定義載入失敗，請確認 custom_sectors.csv 存在[/red]")
        return False
    console.print(f"[dim]已載入 {n} 個板塊定義[/dim]")
    return True


def _progress_run(steps_total: int = 7):
    """回傳一個 Progress context manager。"""
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console,
    )


def _render_sector_table(sector_results: dict, title: str = "板塊燈號總表"):
    """用 Rich Table 顯示板塊燈號矩陣。"""
    table = Table(title=title, show_header=True, header_style="bold magenta")
    table.add_column("板塊",   style="bold",  min_width=12)
    table.add_column("燈1",    justify="center")
    table.add_column("燈2",    justify="center")
    table.add_column("燈3",    justify="center")
    table.add_column("燈4",    justify="center")
    table.add_column("燈5",    justify="center")
    table.add_column("燈6",    justify="center")
    table.add_column("燈7",    justify="center")
    table.add_column("總分",   justify="center", style="bold")
    table.add_column("等級",   min_width=8)

    for sid, v in sector_results.items():
        sigs    = v["signals"]
        total   = v["total"]
        level   = v["level"]
        style   = _LEVEL_STYLE.get(level, "")
        emojis  = ["🟢" if s else "⚫" for s in sigs]
        table.add_row(
            v["name"],
            *emojis,
            str(total),
            Text(f"{'🔥' if level=='強烈關注' else '👀' if level=='觀察中' else '💤'} {level}",
                 style=style),
        )
    console.print(table)


def _ask_export(result: dict) -> None:
    """詢問是否輸出 Markdown 報告。"""
    if not questionary.confirm("是否輸出 Markdown 報告？", default=True).ask():
        return
    mode = questionary.select(
        "選擇輸出格式",
        choices=["標準模式", "Notion 友善模式（可直接貼入 Notion）"],
    ).ask()
    notion = "Notion" in mode
    path = write_report(result, config, notion_mode=notion)
    console.print(f"[green]✅ 報告已儲存：[bold]{path}[/bold][/green]")


# ══════════════════════════════════════════════════════════════════════════
# 個別燈號分析（選單 2‑7）
# ══════════════════════════════════════════════════════════════════════════

def _run_single_analyzer(name: str, fn_key: str) -> None:
    if not _ensure_login() or not _ensure_sectors():
        return

    with console.status(f"[cyan]執行 {name}...[/cyan]"):
        try:
            from src.analyzers import revenue, institutional, inventory
            from src.analyzers import technical, rs_ratio, chipset, macro

            dispatch = {
                "revenue":       lambda: revenue.analyze(fetcher, sector_map, config),
                "institutional": lambda: institutional.analyze(fetcher, sector_map, config),
                "inventory":     lambda: inventory.analyze(fetcher, sector_map, config),
                "technical":     lambda: technical.analyze(fetcher, sector_map, config),
                "rs_ratio":      lambda: rs_ratio.analyze(fetcher, sector_map, config),
                "chipset":       lambda: chipset.analyze(fetcher, sector_map, config),
                "macro":         lambda: macro.analyze(fetcher, config),
            }
            result = dispatch[fn_key]()
        except Exception as e:
            console.print(f"[red]執行失敗: {e}[/red]")
            return

    if fn_key == "macro":
        _display_macro(result)
        return

    # 板塊層級結果
    table = Table(title=name, header_style="bold cyan")
    table.add_column("板塊",  style="bold", min_width=12)
    table.add_column("燈號",  justify="center")
    table.add_column("亮燈%", justify="right")
    table.add_column("說明",  overflow="fold")

    for sid in sector_map.all_sector_ids():
        d     = result.get(sid, {})
        sig   = d.get("signal", False)
        pct   = d.get("pct_lit", 0)
        info  = d.get("details", "-")
        style = "green" if sig else "dim"
        table.add_row(
            sector_map.get_sector_name(sid),
            "🟢" if sig else "⚫",
            f"{pct:.0f}%",
            Text(info, style=style),
        )
    console.print(table)


def _display_macro(result: dict) -> None:
    sig   = result.get("signal", False)
    pos   = result.get("positive_count", 0)
    tot   = result.get("total_available", 0)
    color = "green" if sig else "yellow"
    console.print(Panel(
        f"[{color}]{'✅ 宏觀正面' if sig else '⚠️ 宏觀警戒'} — {pos}/{tot} 指標正面[/{color}]\n\n"
        + "\n".join(f"  • {v}" for v in result.get("details_dict", {}).values()),
        title="燈7 宏觀環境",
        border_style=color,
    ))


# ══════════════════════════════════════════════════════════════════════════
# 全部執行
# ══════════════════════════════════════════════════════════════════════════

def menu_run_all() -> None:
    if not _ensure_login() or not _ensure_sectors():
        return

    from src.analyzers.multi_signal import run_all
    completed_steps = []

    with _progress_run(7) as progress:
        task = progress.add_task("分析中...", total=7)

        def cb(step_name, step_n, total):
            progress.update(task, description=f"[cyan]{step_name}[/cyan]", completed=step_n - 1)
            completed_steps.append(step_name)

        result = run_all(fetcher, sector_map, config, progress_cb=cb)
        progress.update(task, completed=7, description="[green]完成![/green]")

    macro_ok = not result["macro_warning"]
    if not macro_ok:
        console.print("[bold yellow]⚠ 宏觀燈未亮，所有板塊訊號請謹慎參考[/bold yellow]")

    _render_sector_table(result["sector_results"], "🔦 7 燈彙總排行")

    strong = result["summary"]["strong"]
    if strong:
        names = [result["sector_results"][s]["name"] for s in strong]
        console.print(f"\n[bold red]🔥 強烈關注：{', '.join(names)}[/bold red]")
    else:
        console.print("\n[dim]目前無板塊達到強烈關注門檻（≥4燈）[/dim]")

    _ask_export(result)


# ══════════════════════════════════════════════════════════════════════════
# 多維彙總（快速版，只跑 multi_signal）
# ══════════════════════════════════════════════════════════════════════════

def menu_summary() -> None:
    """只顯示上次執行的快照（不重新拉資料）。"""
    from src.analyzers.multi_signal import load_history

    scan = file_scanner.scan_all(config.OUTPUT_DIR)
    snaps = scan["snapshots"]
    if not snaps:
        console.print("[yellow]找不到歷史快照，請先執行 [1] 全部執行[/yellow]")
        return

    latest = snaps[0]
    import json
    data = json.loads(Path(latest["path"]).read_text(encoding="utf-8"))
    history = load_history(config, n=4)

    from src.analyzers.multi_signal import build_trend_string

    table = Table(title=f"板塊訊號摘要 ({latest['date']})", header_style="bold magenta")
    table.add_column("板塊",     style="bold", min_width=12)
    table.add_column("4週趨勢",  justify="center")
    table.add_column("總燈",     justify="center", style="bold")
    table.add_column("等級")

    sectors = data.get("sectors", {})
    for sid, v in sorted(sectors.items(), key=lambda x: -x[1]["total"]):
        level  = v.get("level", "")
        total  = v.get("total", 0)
        trend  = build_trend_string(sid, history)
        style  = _LEVEL_STYLE.get(level, "")
        name   = sector_map.get_sector_name(sid) if sector_map.loaded else sid
        table.add_row(name, trend, str(total), Text(level, style=style))

    console.print(table)


# ══════════════════════════════════════════════════════════════════════════
# 歷史報告
# ══════════════════════════════════════════════════════════════════════════

def menu_history() -> None:
    scan = file_scanner.scan_all(config.OUTPUT_DIR)
    reports = scan["reports"]

    if not reports:
        console.print(f"[yellow]output/ 資料夾中沒有任何 .md 報告[/yellow]")
        console.print(f"[dim]路徑：{config.OUTPUT_DIR}[/dim]")
        return

    choices = [f"{r['name']}  ({r['size_kb']} KB)" for r in reports] + ["← 返回"]
    selected = questionary.select("選擇要查看的報告", choices=choices).ask()

    if selected == "← 返回":
        return

    idx = choices.index(selected)
    content = file_scanner.read_report(reports[idx]["path"])
    if content:
        console.print(Markdown(content))


# ══════════════════════════════════════════════════════════════════════════
# 設定
# ══════════════════════════════════════════════════════════════════════════

def menu_settings() -> None:
    choices = [
        "設定 / 更新 FinLab API Token",
        "查看快取狀態",
        "清除所有快取",
        "查看 .env 設定（無 Token 顯示）",
        "← 返回",
    ]
    action = questionary.select("設定選項", choices=choices).ask()

    if "Token" in action:
        token = questionary.password("輸入 FinLab API Token（輸入後不顯示）：").ask()
        if token:
            _update_env("FINLAB_API_TOKEN", token)
            # 同步更新 config 運行時值
            import importlib
            config.FINLAB_API_TOKEN = token
            fetcher._logged_in = False  # 強制重新登入
            console.print("[green]✅ Token 已更新，下次操作時自動重新登入[/green]")

    elif "快取狀態" in action:
        status = fetcher.cache_status()
        console.print(
            f"快取目錄：[bold]{status['cache_dir']}[/bold]\n"
            f"檔案數：{status['file_count']}  大小：{status['total_mb']} MB"
        )

    elif "清除" in action:
        if questionary.confirm("確定清除所有快取？", default=False).ask():
            n = fetcher.clear_cache()
            console.print(f"[green]已清除 {n} 個快取檔案[/green]")

    elif ".env" in action:
        console.print(
            f"FINLAB_API_TOKEN = {'已設定' if config.is_finlab_token_set() else '[red]未設定[/red]'}\n"
            f"FRED_API_KEY     = {'已設定' if config.is_fred_key_set() else '[red]未設定[/red]'}\n"
            f"ALPHA_VANTAGE_KEY= {'已設定' if config.is_av_key_set() else '[red]未設定[/red]'}\n"
            f"CACHE_EXPIRE_HOURS = {config.CACHE_EXPIRE_HOURS}\n"
            f"RS_LOOKBACK_DAYS   = {config.RS_LOOKBACK_DAYS}"
        )


def _update_env(key: str, value: str) -> None:
    """更新 .env 檔案中指定 key 的值。"""
    env_path = config.BASE_DIR / ".env"
    if not env_path.exists():
        env_path.write_text(f"{key}={value}\n", encoding="utf-8")
        return
    lines = env_path.read_text(encoding="utf-8").splitlines()
    updated = False
    for i, line in enumerate(lines):
        if line.startswith(f"{key}=") or line.startswith(f"{key} ="):
            lines[i] = f"{key}={value}"
            updated = True
            break
    if not updated:
        lines.append(f"{key}={value}")
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ══════════════════════════════════════════════════════════════════════════
# 主選單
# ══════════════════════════════════════════════════════════════════════════

def main() -> None:
    os.system("cls" if os.name == "nt" else "clear")
    _header()

    # 預載板塊定義
    _ensure_sectors()

    DISPATCH = {
        "1": menu_run_all,
        "2": lambda: _run_single_analyzer("燈1 月營收拐點",   "revenue"),
        "3": lambda: _run_single_analyzer("燈2 法人籌碼共振", "institutional"),
        "4": lambda: _run_single_analyzer("燈3 庫存循環",     "inventory"),
        "5": lambda: _run_single_analyzer("燈4 技術突破",     "technical"),
        "6": lambda: _run_single_analyzer("燈5 相對強度 RRG", "rs_ratio"),
        "7": lambda: _run_single_analyzer("燈6 籌碼集中",     "chipset"),
        "8": lambda: _run_single_analyzer("燈7 宏觀濾網",     "macro"),
        "9": menu_summary,
        "A": menu_history,
        "a": menu_history,
        "B": menu_settings,
        "b": menu_settings,
    }

    while True:
        console.print()
        choices = [f"[{k}] {label}" for k, label in MENU_ITEMS]
        selected = questionary.select(
            "請選擇功能",
            choices=choices,
            use_shortcuts=False,
        ).ask()

        if selected is None or selected.startswith("[0]"):
            console.print("[dim]再見！[/dim]")
            break

        key = selected[1]   # e.g. "[1]..." → "1"
        fn  = DISPATCH.get(key)
        if fn:
            try:
                fn()
            except KeyboardInterrupt:
                console.print("\n[dim]已中斷[/dim]")
            except Exception as e:
                console.print(f"[bold red]執行錯誤: {e}[/bold red]")
                logging.exception(e)


if __name__ == "__main__":
    # ── --auto 模式：GitHub Actions 非互動式全自動執行 ──────────────────
    if "--auto" in sys.argv:
        import zoneinfo
        import logging as _logging
        _logging.basicConfig(level=_logging.INFO, format="%(levelname)s — %(message)s")

        def _auto_log(msg: str) -> None:
            print(msg, flush=True)

        # 1. 台灣時區日期（避免 UTC 與 TST 跨日邊界差異）
        try:
            import holidays as _hol
            tz_tst = zoneinfo.ZoneInfo("Asia/Taipei")
            today_tst = __import__("datetime").datetime.now(tz_tst).date()
            tw_hols = _hol.TW(years=today_tst.year)
            if today_tst in tw_hols:
                _auto_log(f"[SKIP] 今日 {today_tst} 為台灣國定假日（{tw_hols[today_tst]}），跳過執行。")
                sys.exit(0)
            _auto_log(f"[INFO] 今日 {today_tst}，非假日，開始分析...")
        except Exception as _e:
            _auto_log(f"[WARN] 假日判斷失敗（{_e}），繼續執行...")

        # 2. 確保板塊 + 登入
        if not _ensure_sectors():
            _auto_log("[ERROR] 板塊定義載入失敗")
            sys.exit(1)
        if not _ensure_login():
            _auto_log("[ERROR] FinLab 登入失敗，請確認 FINLAB_API_TOKEN")
            sys.exit(1)

        # 3. 執行完整 7 燈分析
        from src.analyzers.multi_signal import run_all
        _auto_log("[INFO] 開始執行 7 燈分析...")

        def _auto_cb(step_name, step_n, total):
            _auto_log(f"[{step_n}/{total}] {step_name}")

        try:
            result = run_all(fetcher, sector_map, config, progress_cb=_auto_cb)
        except Exception as _e:
            _auto_log(f"[ERROR] 7 燈分析失敗: {_e}")
            # 通知 Discord 系統頻道
            try:
                from src.notifier import send_error
                send_error(config, str(_e))
            except Exception:
                pass
            sys.exit(1)

        # 4. 輸出報告（Markdown）
        try:
            report_path = write_report(result, config, notion_mode=False)
            _auto_log(f"[INFO] Markdown 報告：{report_path.name}")
        except Exception as _e:
            _auto_log(f"[WARN] Markdown 報告輸出失敗: {_e}")

        # 5. 送出 Discord 通知
        try:
            from src.notifier import send_daily_report, send_sector_alert, send_macro_alert, send_system_ok
            send_daily_report(config, result)
            send_sector_alert(config, result)
            send_macro_alert(config, result)
            send_system_ok(config, result)
        except Exception as _e:
            _auto_log(f"[WARN] Discord 通知失敗: {_e}")

        # 6. 完成
        strong = result["summary"]["strong"]
        watch  = result["summary"]["watch"]
        _auto_log(f"[DONE] 分析完成 ✅ 強烈關注={len(strong)} 觀察中={len(watch)}")
        sys.exit(0)

    # ── 互動式 CLI ──────────────────────────────────────────────────────
    main()
