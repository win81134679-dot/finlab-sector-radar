"""ssl_fix.py — 修正 curl_cffi (yfinance 底層) 無法讀取含中文路徑 CA 憑證的問題

Windows 上若工作目錄或 Python 環境路徑含中文（如 FinLab板塊偵測），
curl_cffi 會拋出 curl: (77) SSL 錯誤，導致 yfinance 無法連線。
解法：將 cacert.pem 複製到純 ASCII 路徑並設定對應環境變數。

此模組在被 import 時立即執行，只需在 yfinance 首次使用前 import 一次。
"""
import os
import shutil


def _apply() -> None:
    try:
        import certifi
        cert = certifi.where()

        # 測試路徑是否純 ASCII；含中文時 encode 會失敗
        try:
            cert.encode("ascii")
        except UnicodeEncodeError:
            ascii_cert = os.path.join(os.path.expanduser("~"), "cacert.pem")
            # 只在來源有更新時才複製（省略重複 IO）
            if (
                not os.path.exists(ascii_cert)
                or os.path.getsize(ascii_cert) != os.path.getsize(cert)
            ):
                shutil.copy2(cert, ascii_cert)
            cert = ascii_cert

        os.environ["SSL_CERT_FILE"]      = cert
        os.environ["REQUESTS_CA_BUNDLE"] = cert
        os.environ["CURL_CA_BUNDLE"]     = cert
    except ImportError:
        pass  # certifi 未安裝時靜默略過


_apply()
