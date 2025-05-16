# 🔓 Wicrack - Interactive TUI for Wi-Fi Attacks (PMKID & Handshake)

**Wicrack** is a simple, interactive, terminal-based tool (TUI) for automating Wi-Fi network attacks using popular tools available on Kali Linux. It guides the user step-by-step, from selecting a wireless interface to capturing handshakes and cracking passwords.

## 🚀 Features

- Interactive TUI powered by [Questionary](https://github.com/tmbo/questionary)
- Automatically enables monitor mode on the selected interface
- Scans for Wi-Fi networks
- Lets you select a target from the detected networks
- Supports:
  - **PMKID attack**
  - **Handshake capture**
  - **DoS Attack**
  - **Evil Twin**
- Allows you to choose a custom wordlist for cracking
- Generates a markdown report in the `wicrack_output/` directory

## 🛠 Installation

```bash
sudo apt update && sudo apt install -y aircrack-ng hcxdumptool mdk4
git clone https://github.com/predatorx-0/WiCrack.git
cd WiCrack
pip install -r requirements.pip  # Only needed for Python dependencies like questionary



