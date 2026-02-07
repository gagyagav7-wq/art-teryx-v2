import os
import time
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

load_dotenv()

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT_IG = os.path.join(BASE_DIR, "cookies_instagram.txt")
OUT_X  = os.path.join(BASE_DIR, "cookies_x.txt")

def _mk_driver():
    opt = Options()
    opt.add_argument("--headless=new")
    opt.add_argument("--no-sandbox")
    opt.add_argument("--disable-dev-shm-usage")
    opt.add_argument("--disable-gpu")
    opt.add_argument("--window-size=1280,900")
    opt.add_argument("--lang=en-US")
    opt.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36")
    return webdriver.Chrome(options=opt)

def _export_netscape_cookies(driver, path):
    cookies = driver.get_cookies()
    with open(path, "w", encoding="utf-8") as f:
        f.write("# Netscape HTTP Cookie File\n")
        for c in cookies:
            domain = c.get("domain", "")
            if domain.startswith("."):
                include_sub = "TRUE"
            else:
                include_sub = "FALSE"
            cookie_domain = domain
            cookie_path = c.get("path", "/")
            secure = "TRUE" if c.get("secure", False) else "FALSE"
            expiry = str(int(c.get("expiry", 0) or 0))
            name = c.get("name", "")
            value = c.get("value", "")
            # domain \t include_subdomains \t path \t secure \t expiry \t name \t value
            f.write(f"{cookie_domain}\t{include_sub}\t{cookie_path}\t{secure}\t{expiry}\t{name}\t{value}\n")

def gen_instagram():
    user = os.getenv("IG_USER", "")
    pw = os.getenv("IG_PASS", "")
    if not user or not pw:
        raise RuntimeError("IG_USER/IG_PASS belum diisi di .env")

    d = _mk_driver()
    try:
        d.get("https://www.instagram.com/accounts/login/")
        time.sleep(3)

        # isi login
        d.find_element(By.NAME, "username").send_keys(user)
        d.find_element(By.NAME, "password").send_keys(pw)
        d.find_element(By.NAME, "password").submit()

        time.sleep(8)

        # buka halaman utama biar cookie lengkap
        d.get("https://www.instagram.com/")
        time.sleep(3)

        _export_netscape_cookies(d, OUT_IG)
        print("OK: cookies_instagram.txt generated")
    finally:
        d.quit()

def gen_x():
    user = os.getenv("X_USER", "")
    pw = os.getenv("X_PASS", "")
    if not user or not pw:
        raise RuntimeError("X_USER/X_PASS belum diisi di .env")

    d = _mk_driver()
    try:
        d.get("https://x.com/login")
        time.sleep(4)

        # X login flow sering berubah; ini pattern umum
        inputs = d.find_elements(By.TAG_NAME, "input")
        # cari input pertama untuk username/email
        if inputs:
            inputs[0].send_keys(user)
            inputs[0].submit()
        time.sleep(4)

        # cari input password
        pw_in = None
        for inp in d.find_elements(By.TAG_NAME, "input"):
            if inp.get_attribute("type") == "password":
                pw_in = inp
                break
        if not pw_in:
            raise RuntimeError("Tidak menemukan input password (flow X berubah).")

        pw_in.send_keys(pw)
        pw_in.submit()
        time.sleep(8)

        d.get("https://x.com/home")
        time.sleep(3)

        _export_netscape_cookies(d, OUT_X)
        print("OK: cookies_x.txt generated")
    finally:
        d.quit()

if __name__ == "__main__":
    # pilih salah satu:
    # gen_instagram()
    # gen_x()
    gen_instagram()
