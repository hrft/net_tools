#!/usr/bin/env bash
set -e
SRC="$(pwd)/vpngate-219-100-37-61.nmconnection"
DST="/etc/NetworkManager/system-connections/vpngate-219-100-37-61.nmconnection"
echo "Copying $SRC to $DST"
cp "$SRC" "$DST"
chown root:root "$DST"
chmod 600 "$DST"
echo "Reloading NetworkManager connections"
nmcli connection reload
echo "Ensuring vpn.user-name and vpn.secrets are set for vpngate-219-100-37-61"
nmcli connection modify "vpngate-219-100-37-61" vpn.user-name "vpngate"
nmcli connection modify "vpngate-219-100-37-61" vpn.password-flags 0
nmcli connection modify "vpngate-219-100-37-61" +vpn.secrets "password=vpn"
nmcli connection modify "vpngate-219-100-37-61" connection.permissions ""
echo "Reloading again"
nmcli connection reload
echo "Bringing up connection vpngate-219-100-37-61"
nmcli connection up "vpngate-219-100-37-61"
