# Point-to-Point Ethernet Connection Setup Guide
## Raspberry Pi 5 to NXP i.MX 6DL Board

This guide explains how to establish a direct point-to-point Ethernet connection between a Raspberry Pi 5 and an NXP i.MX 6DL-based board using a 4-wire Ethernet cable. We'll configure both ends to use 10Mbps half-duplex mode with auto-negotiation disabled and address common stability issues.

## Requirements

- Raspberry Pi 5
- NXP i.MX 6DL board (VitroTech)
- Custom 4-wire Ethernet cable
- NetworkManager installed on both devices

## Network Configuration

We'll set up a direct connection with the following parameters:
- Connection type: 10Mbps half-duplex
- Auto-negotiation: Disabled
- IP addressing:
  - Raspberry Pi: 192.168.2.1/24
  - NXP board: 192.168.2.2/24

## Setup Instructions

### NXP i.MX 6DL Board (VitroTech)

1. **Check NetworkManager status**:
   ```bash
   systemctl status NetworkManager
   which nmcli
   ```

2. **Identify the current connection**:
   ```bash
   nmcli connection show
   ```
   Note the name of the Ethernet connection (e.g., "Wired connection 1").

3. **Configure the connection**:
   ```bash
   # Disable auto-negotiation and set speed/duplex
   nmcli connection modify "Wired connection 1" 802-3-ethernet.auto-negotiate false
   nmcli connection modify "Wired connection 1" 802-3-ethernet.speed 10
   nmcli connection modify "Wired connection 1" 802-3-ethernet.duplex half

   # Set static IP address
   nmcli connection modify "Wired connection 1" ipv4.method manual ipv4.addresses 192.168.2.2/24
   nmcli connection modify "Wired connection 1" ipv4.gateway 0.0.0.0
   ```

4. **Apply and verify the settings**:
   ```bash
   # Apply changes
   nmcli connection down "Wired connection 1"
   nmcli connection up "Wired connection 1"

   # Verify settings
   nmcli connection show "Wired connection 1" | grep -E 'auto-negotiate|speed|duplex|ipv4'
   ip addr show eth0
   ```

### Raspberry Pi 5

1. **Install NetworkManager if not already installed**:
   ```bash
   sudo apt update
   sudo apt install network-manager
   ```

2. **Enable NetworkManager service**:
   ```bash
   sudo systemctl enable NetworkManager
   sudo systemctl start NetworkManager
   ```

3. **Check network devices and their status**:
   ```bash
   sudo nmcli device status
   ```
   Identify your Ethernet interface (e.g., eth2).

4. **Ensure the interface is managed by NetworkManager**:
   ```bash
   sudo nmcli device set eth2 managed yes
   ```

5. **Create a new connection with desired settings**:
   ```bash
   sudo nmcli connection add type ethernet con-name "eth2-fixed" ifname eth2 \
     802-3-ethernet.auto-negotiate false \
     802-3-ethernet.speed 10 \
     802-3-ethernet.duplex half \
     ipv4.method manual \
     ipv4.addresses 192.168.2.1/24 \
     ipv4.gateway 0.0.0.0 \
     connection.autoconnect yes
   ```

6. **Apply and verify the settings**:
   ```bash
   # Apply changes
   sudo nmcli connection up "eth2-fixed"

   # Verify settings
   sudo nmcli connection show "eth2-fixed" | grep -E 'auto-negotiate|speed|duplex|ipv4'
   ip addr show eth2
   ```

## Testing the Connection

1. **Ping test from Raspberry Pi to NXP board**:
   ```bash
   ping 192.168.2.2
   ```

2. **Ping test from NXP board to Raspberry Pi**:
   ```bash
   ping 192.168.2.1
   ```

3. **Check connection speed and duplex**:
   If `ethtool` is available on the Raspberry Pi, you can verify:
   ```bash
   sudo ethtool eth2
   ```

## Stability Optimizations

### Disabling Energy-Efficient Ethernet (EEE)

Energy-Efficient Ethernet (IEEE 802.3az) can cause link instability, especially in direct point-to-point connections. Symptoms include frequent link flapping (interface rapidly cycling between "Link is Up" and "Link is Down" states).

**To permanently disable EEE on Raspberry Pi:**

1. Create a simple startup script:
   ```bash
   sudo nano /etc/network/if-up.d/disable-eee
   ```

2. Add the following content to the file:
   ```bash
   #!/bin/bash
   
   # Only run for eth2
   if [ "$IFACE" = "eth2" ]; then
       /sbin/ethtool --set-eee eth2 eee off
   fi
   ```

3. Make the script executable:
   ```bash
   sudo chmod +x /etc/network/if-up.d/disable-eee
   ```

4. Test it by bringing the interface down and up:
   ```bash
   sudo nmcli connection down eth2-fixed
   sudo nmcli connection up eth2-fixed
   ```

5. Verify EEE is disabled:
   ```bash
   sudo ethtool --show-eee eth2
   # Should show: EEE status: disabled
   ```

This script will run automatically whenever the eth2 interface is brought up.

### Additional Network Tuning (Optional)

If you continue to experience stability issues, try disabling TCP offloading features:
```bash
sudo ethtool -K eth2 tso off gso off gro off
```

## Troubleshooting

### Connection Issues
1. Verify physical connection (cable connections, power)
2. Check IP configurations on both devices:
   ```bash
   ip addr show
   ```
3. Ensure both devices have auto-negotiation disabled:
   ```bash
   nmcli connection show "connection-name" | grep auto-negotiate
   ```

### Link Flapping Issues
If you see "Link is Up"/"Link is Down" cycling in logs:
```bash
dmesg | grep -i eth
```

1. Disable EEE as described above
2. Try different speed/duplex settings:
   ```bash
   sudo nmcli connection modify eth2-fixed 802-3-ethernet.speed 100
   sudo nmcli connection modify eth2-fixed 802-3-ethernet.duplex full
   ```
3. Check cable quality and consider using shielded cables
4. For custom 4-wire setups, consider adding 100Ω termination resistors

### Speed/Duplex Issues
1. Verify settings applied correctly:
   ```bash
   nmcli connection show "connection-name" | grep -E 'speed|duplex'
   ```
2. Try bringing the interface down and up:
   ```bash
   nmcli connection down "connection-name"
   nmcli connection up "connection-name"
   ```

## Notes
- These settings will persist across reboots since they are managed by NetworkManager
- For any changes, simply modify the connection using `nmcli connection modify`
- The 4-wire Ethernet cable should connect TX+/TX- from one device to RX+/RX- on the other device and vice versa

## Alternative Manual Setup (if NetworkManager is unavailable)

### On Raspberry Pi
```bash
sudo ethtool -s eth2 speed 10 duplex half autoneg off
sudo ip link set eth2 down
sudo ip addr flush dev eth2
sudo ip addr add 192.168.2.1/24 broadcast 192.168.2.255 dev eth2
sudo ip link set eth2 up
```

### On NXP board
```bash
ip link set eth0 down
ip addr flush dev eth0
ip addr add 192.168.2.2/24 broadcast 192.168.2.255 dev eth0
ip link set eth0 up
```

Note: This manual configuration will not persist after reboot.