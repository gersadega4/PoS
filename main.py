import time
import os
import zipfile
import random
import string
import imaplib
import email
import re
import threading
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# ─────────────────────────────────────────────
# KONFIGURASI
# ─────────────────────────────────────────────
PROXY_FILE = "proxy.txt"
AKUN_FILE = "akun.txt"
DOCKER_IMAGE = "millicen/gas20262:latest"

GMAIL_BASE = "maximus.sale1"
GMAIL_DOMAIN = "gmail.com"
GMAIL_USERNAME = "maximus.sale1@gmail.com"
GMAIL_PASSWORD = "etnv ileo azii egtb"

def generate_plus_email():
    suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
    return f"{GMAIL_BASE}+{suffix}@{GMAIL_DOMAIN}"

def ambil_kode_railway(target_email, timeout=120):
    """Ambil login code Railway dari inbox via IMAP. Polling sampai timeout."""
    print("     -> Menghubungkan ke Gmail via IMAP...")
    deadline = time.time() + timeout
    seen_uids = set()

    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(GMAIL_USERNAME, GMAIL_PASSWORD)
        mail.select("inbox")
        _, data = mail.search(None, 'FROM', '"noreply@trymagic.com"')
        existing = set(data[0].split()) if data[0] else set()
        seen_uids = existing
        mail.logout()
    except Exception as e:
        print(f"     -> Gagal inisialisasi IMAP: {e}")

    while time.time() < deadline:
        try:
            mail = imaplib.IMAP4_SSL("imap.gmail.com")
            mail.login(GMAIL_USERNAME, GMAIL_PASSWORD)
            mail.select("inbox")

            _, data = mail.search(None, 'FROM', '"noreply@trymagic.com"')
            uids = set(data[0].split()) if data[0] else set()
            new_uids = uids - seen_uids

            for uid in new_uids:
                _, msg_data = mail.fetch(uid, "(RFC822)")
                raw = msg_data[0][1]
                msg = email.message_from_bytes(raw)
                subject = msg.get("Subject", "")
                to_field = msg.get("To", "")

                if target_email.lower() not in to_field.lower():
                    print(f"     -> Skip email (To: {to_field} bukan {target_email})")
                    continue

                match = re.match(r"(\d{6}) is your Railway login code", subject)
                if match:
                    kode = match.group(1)
                    mail.logout()
                    print(f"     -> Kode ditemukan untuk {target_email}: {kode}")
                    return kode

            mail.logout()
        except Exception as e:
            print(f"     -> Error IMAP: {e}")

        print("     -> Belum ada kode, coba lagi dalam 5 detik...")
        time.sleep(5)

    print("     -> Timeout, kode tidak ditemukan.")
    return None

def baca_proxy(filepath):
    try:
        with open(filepath, "r") as f:
            proxy_raw = f.read().strip()
        if not proxy_raw:
            return None
        proxy_raw = proxy_raw.replace("http://", "")
        auth_host = proxy_raw.split("@")
        user_pass = auth_host[0].split(":")
        host_port = auth_host[1].split(":")
        return {
            "username": user_pass[0],
            "password": user_pass[1],
            "host": host_port[0],
            "port": host_port[1]
        }
    except:
        return None

def simpan_akun(filepath, email_used):
    with open(filepath, "a") as f:
        f.write(email_used + "\n")
    print(f"     -> Akun disimpan ke {filepath}: {email_used}")

def cek_ip_proxy(proxy):
    try:
        if proxy:
            proxy_url = f"http://{proxy['username']}:{proxy['password']}@{proxy['host']}:{proxy['port']}"
            r = requests.get(
                "https://api.ipify.org?format=json",
                proxies={"http": proxy_url, "https": proxy_url},
                timeout=15
            )
        else:
            r = requests.get("https://api.ipify.org?format=json", timeout=15)
        return r.json().get("ip", "Tidak diketahui")
    except Exception as e:
        return f"Gagal ({e})"

def buat_plugin_proxy(proxy):
    plugin_dir = "proxy_plugin"
    os.makedirs(plugin_dir, exist_ok=True)

    manifest_json = """
    {
        "version": "1.0.0",
        "manifest_version": 2,
        "name": "Proxy Auth Plugin",
        "permissions": [
            "proxy",
            "tabs",
            "unlimitedStorage",
            "storage",
            "",
            "webRequest",
            "webRequestBlocking"
        ],
        "background": {
            "scripts": ["background.js"]
        }
    }
    """

    background_js = f"""
    var config = {{
        mode: "fixed_servers",
        rules: {{
            singleProxy: {{
                scheme: "http",
                host: "{proxy['host']}",
                port: parseInt("{proxy['port']}")
            }},
            bypassList: ["localhost"]
        }}
    }};
    chrome.proxy.settings.set({{value: config, scope: "regular"}}, function() {{}});

    function callbackFn(details) {{
        return {{
            authCredentials: {{
                username: "{proxy['username']}",
                password: "{proxy['password']}"
            }}
        }};
    }}

    chrome.webRequest.onAuthRequired.addListener(
        callbackFn,
        {{urls: [""]}},
        ["blocking"]
    );
    """

    plugin_path = os.path.join(plugin_dir, "proxy_auth.zip")
    with zipfile.ZipFile(plugin_path, "w") as zp:
        zp.writestr("manifest.json", manifest_json)
        zp.writestr("background.js", background_js)

    return plugin_path

def buat_driver(proxy):
    chrome_options = Options()

    if proxy:
        plugin_path = buat_plugin_proxy(proxy)
        chrome_options.add_extension(plugin_path)

    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--log-level=3")
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
    chrome_options.add_experimental_option("useAutomationExtension", False)

    service = Service(
        ChromeDriverManager().install(),
        log_output=os.devnull
    )
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return driver

def tunggu_dan_klik(driver, wait, by, selector, timeout=60, klik=True):
    try:
        element = wait.until(EC.element_to_be_clickable((by, selector)))
        if klik:
            driver.execute_script("arguments[0].scrollIntoView(true);", element)
            time.sleep(0.5)
            element.click()
        return element
    except Exception as e:
        print(f"  [!] Gagal: {selector[:80]}... | Error: {e}")
        return None

def klik_dengan_js(driver, wait, by, selector):
    """Klik elemen via JavaScript untuk bypass element click intercepted."""
    try:
        el = wait.until(EC.presence_of_element_located((by, selector)))
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", el)
        time.sleep(0.5)
        driver.execute_script("arguments[0].click();", el)
        print(f"     -> Diklik (JS): {selector[:80]}")
        return el
    except Exception as e:
        print(f"  [!] Gagal JS click: {selector[:80]}... | Error: {e}")
        return None

def proses_akun(proxy):
    generated_email = generate_plus_email()

    print(f"\n{'='*60}")
    print(f"  Akun    : {generated_email}")
    print(f"{'='*60}")

    driver = buat_driver(proxy)
    wait = WebDriverWait(driver, 60)

    try:
        print("[1] Membuka https://railway.com/")
        driver.get("https://railway.com/?referralCode=xS8VnG")
        time.sleep(3)

        print("[2] Klik tombol Sign in...")
        tunggu_dan_klik(driver, wait, By.XPATH,
            "//button[normalize-space()='Sign in' and contains(@class,'h-10')]")
        time.sleep(2)

        print("[3] Klik 'Log in using email'...")
        tunggu_dan_klik(driver, wait, By.XPATH,
            "//button[normalize-space()='Log in using email']")
        time.sleep(2)

        # ── STEP 4 ──────────────────────────────────────────────────
        print("[4] Isi email di input Railway...")

        imap_result = {"kode": None}

        def fetch_imap():
            imap_result["kode"] = ambil_kode_railway(generated_email, timeout=120)

        imap_thread = threading.Thread(target=fetch_imap, daemon=True)
        imap_thread.start()

        email_input = tunggu_dan_klik(driver, wait, By.CSS_SELECTOR,
            "input[name='email'][type='email']", klik=True)
        if email_input:
            email_input.clear()
            email_input.send_keys(generated_email)
            time.sleep(1)
            email_input.send_keys(Keys.ENTER)

        # ── STEP 5 ──────────────────────────────────────────────────
        print("[5] Mengambil login code dari Gmail (background)...")
        imap_thread.join(timeout=120)
        login_code = imap_result["kode"]

        if not login_code:
            print("  [!] Gagal mendapatkan login code, skip akun ini.")
            return

        # ── STEP 6 ──────────────────────────────────────────────────
        print("[6] Menunggu form PIN code muncul di browser...")
        try:
            WebDriverWait(driver, 60).until(
                EC.frame_to_be_available_and_switch_to_it(
                    (By.CSS_SELECTOR, "iframe[src*='auth.magic.link']")
                )
            )
            print("     -> Switched ke iframe Magic Link.")

            WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.ID, "pin-code-input-0"))
            )
            time.sleep(0.5)
            print(f"     -> Form PIN siap. Mengisi kode: {login_code}")

            pin_0 = driver.find_element(By.ID, "pin-code-input-0")
            driver.execute_script("arguments[0].click();", pin_0)
            time.sleep(0.3)
            pin_0.send_keys(login_code)

            print("     -> Kode berhasil dimasukkan.")
            time.sleep(3)

        except Exception as e:
            print(f"  [!] Gagal mengisi PIN code: {e}")
            return
        finally:
            driver.switch_to.default_content()

        # ── Simpan akun ke file setelah login berhasil ───────────────
        simpan_akun(AKUN_FILE, generated_email)

        print("[7] Klik 'I agree with Railway Terms of Service'...")
        tunggu_dan_klik(driver, wait, By.XPATH,
            "//button[.//span[normalize-space()=\"I agree with Railway's Terms of Service\"]]")
        time.sleep(5)

        print("[8] Cek 'I will not deploy any of that'...")
        try:
            WebDriverWait(driver, 15).until(
                EC.element_to_be_clickable(
                    (By.XPATH, "//button[.//span[normalize-space()='I will not deploy any of that']]")
                )).click()
            print("     -> Diklik.")
            time.sleep(3)
        except:
            print("     -> Tidak muncul, lanjut.")

        tunggu_dan_klik(driver, wait, By.XPATH,
            "//a[contains(@href,'/new') and .//span[normalize-space()='New']]")
        time.sleep(3)

        print("[9] Tunggu dan klik Empty Project...")
        tunggu_dan_klik(driver, wait, By.CSS_SELECTOR, "[data-value='empty-project']")
        time.sleep(2)

        print("[10] Tunggu dan klik Empty Service...")
        tunggu_dan_klik(driver, wait, By.CSS_SELECTOR, "[data-value='empty-service']")
        time.sleep(2)

        print("[11] Tunggu dan klik Connect Image...")
        klik_dengan_js(driver, wait, By.XPATH, "//button[.//span[normalize-space()='Connect Image']]")
        time.sleep(2)

        print("[12] Isi Docker image dan tekan ENTER...")
        docker_input = tunggu_dan_klik(driver, wait, By.CSS_SELECTOR,
            "input[data-testid='create-image-service-input']", klik=True)
        if docker_input:
            docker_input.clear()
            docker_input.send_keys(DOCKER_IMAGE)
            time.sleep(1)
            docker_input.send_keys(Keys.ENTER)
        time.sleep(2)

        print("[13] Tunggu dan klik Deploy...")
        klik_dengan_js(driver, wait, By.CSS_SELECTOR, "button[data-testid='apply-changes']")
        print("     -> Menunggu 10 detik untuk review...")
        time.sleep(10)

        print("[14] Buka dashboard Railway...")
        driver.get("https://railway.com/dashboard")
        time.sleep(4)

        print("[15] Tunggu dan klik New...")
        tunggu_dan_klik(driver, wait, By.XPATH,
            "//a[contains(@href,'/new') and .//span[normalize-space()='New']]")
        time.sleep(3)

        print("[16] Tunggu dan klik Empty Project...")
        tunggu_dan_klik(driver, wait, By.CSS_SELECTOR, "[data-value='empty-project']")
        time.sleep(2)

        print("[17] Tunggu dan klik Empty Service...")
        tunggu_dan_klik(driver, wait, By.CSS_SELECTOR, "[data-value='empty-service']")
        time.sleep(2)

        print("[18] Tunggu dan klik Connect Image...")
        klik_dengan_js(driver, wait, By.XPATH, "//button[.//span[normalize-space()='Connect Image']]")
        time.sleep(2)

        print("[19] Isi Docker image dan tekan ENTER...")
        docker_input2 = tunggu_dan_klik(driver, wait, By.CSS_SELECTOR,
            "input[data-testid='create-image-service-input']", klik=True)
        if docker_input2:
            docker_input2.clear()
            docker_input2.send_keys(DOCKER_IMAGE)
            time.sleep(1)
            docker_input2.send_keys(Keys.ENTER)
        time.sleep(2)

        print("[20] Tunggu dan klik Deploy...")
        klik_dengan_js(driver, wait, By.CSS_SELECTOR, "button[data-testid='apply-changes']")
        print("     -> Menunggu 10 detik untuk review...")
        time.sleep(10)

        print(f"[OK] Akun {generated_email} selesai.")

    except Exception as e:
        print(f"[ERROR] {generated_email} gagal: {e}")

    finally:
        driver.quit()
        print("     -> Browser ditutup.")
        time.sleep(2)

# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
if __name__ == "__main__":
    proxy = baca_proxy(PROXY_FILE)

    print("="*60)
    print("  RAILWAY AUTOMATION SCRIPT")
    print("="*60)
    if proxy:
        print(f"  IP aktif  : {cek_ip_proxy(proxy)} (via proxy)")
    else:
        print(f"  IP aktif  : {cek_ip_proxy(None)} (tanpa proxy)")
    print("="*60)

    # Cek environment variable dulu, baru tanya user
    jumlah_env = os.environ.get("JUMLAH_AKUN")
    if jumlah_env:
        JUMLAH_AKUN = int(jumlah_env)
        print(f"\n  Jumlah akun dari env: {JUMLAH_AKUN}")
    else:
        try:
            JUMLAH_AKUN = int(input("\n  Berapa akun yang ingin dibuat? : "))
            if JUMLAH_AKUN < 1:
                print("  Jumlah akun harus minimal 1. Script dihentikan.")
                exit()
        except ValueError:
            print("  Input tidak valid. Masukkan angka bulat. Script dihentikan.")
            exit()

    print(f"  Akan membuat {JUMLAH_AKUN} akun.")
    print("="*60)

    for i in range(1, JUMLAH_AKUN + 1):
        print(f"\n[*] Memproses akun {i}/{JUMLAH_AKUN}")
        proses_akun(proxy)

    print("\n" + "="*60)
    print("  Semua akun selesai diproses.")
    print("="*60)
