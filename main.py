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

GMAIL_BASE = "barbieanay003"
GMAIL_DOMAIN = "gmail.com"
GMAIL_USERNAME = "barbieanay003@gmail.com"
GMAIL_PASSWORD = "hfkk ftuh aksf dfxc"

DAFTAR_REGION = [ "europe-west4-drams3a", "asia-southeast1-eqsg3a", "us-east4-eqdc4a" ]

# --- KONFIGURASI REPOSITORI UNTUK DEPLOY ---
REPO_URL_1 = "https://github.com/gersadega4/class.git"
REPO_URL_2 = "https://github.com/gersadega4/class.git"
# ─────────────────────────────────────────────

def generate_plus_email():
    suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
    return f"{GMAIL_BASE}+{suffix}@{GMAIL_DOMAIN}"

def ambil_kode_railway(target_email, timeout=120):
    print("     -> Menghubungkan ke Gmail via IMAP...")
    deadline = time.time() + timeout
    seen_uids = set()

    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(GMAIL_USERNAME, GMAIL_PASSWORD)
        mail.select("inbox")
        
        _, data = mail.uid('SEARCH', None, 'FROM', '"noreply@trymagic.com"')
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

            _, data = mail.uid('SEARCH', None, 'FROM', '"noreply@trymagic.com"')
            uids = set(data[0].split()) if data[0] else set()
            new_uids = uids - seen_uids

            for uid in new_uids:
                seen_uids.add(uid)
                
                _, msg_data = mail.uid('FETCH', uid, "(RFC822)")
                if not msg_data or not msg_data[0]:
                    continue
                    
                raw = msg_data[0][1]
                msg = email.message_from_bytes(raw)
                subject = msg.get("Subject", "")
                to_field = msg.get("To", "")

                if target_email.lower() not in to_field.lower():
                    continue

                match = re.match(r"(\d{6}) is your Railway login code", subject)
                if match:
                    kode = match.group(1)
                    
                    mail.uid('STORE', uid, '+FLAGS', '\\Deleted')
                    mail.expunge()
                    
                    mail.logout()
                    print(f"     -> Kode ditemukan untuk {target_email}: {kode} (Email dibersihkan)")
                    return kode

            mail.logout()
        except Exception as e:
            pass 

        jeda = random.uniform(4.5, 7.5)
        print(f"     -> [{target_email.split('+')[1][:5]}] Menunggu kode dalam {jeda:.1f} detik...")
        time.sleep(jeda)

    print(f"     -> Timeout, kode tidak ditemukan untuk {target_email}.")
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
        "manifest_version":
