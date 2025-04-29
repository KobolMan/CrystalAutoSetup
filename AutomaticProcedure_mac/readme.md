# Crystal Board Automated Setup System

## Overview

This project automates the setup and provisioning of Crystal boards (based on NXP i.MX6DL SoC) using a Raspberry Pi as the master controller. The system handles the complete process from OS installation to network configuration and MAC address assignment, with minimal user intervention required.

## Hardware Components

- **Raspberry Pi 5**: Acts as the master controller
- **Crystal Board**: The target device to be provisioned
- **Custom Interface PCB**: Provides connections for:
  - UART communication (RX/TX)
  - Power control (GPIO23)
  - Boot mode control (GPIO12, GPIO26)
  - Button input for starting the process (GPIO17)
  - I2C Grove LCD Display (SDA1/SCL1)
- **Custom Ethernet Cable**: 4-wire cable connecting the Raspberry Pi eth2 port to the Crystal board

## Software Architecture

The system consists of three main Python modules:

1. **autosetup.py**: Main control script that orchestrates the entire provisioning process
2. **uart_flashing.py**: Handles MAC address programming via U-Boot
3. **lcd_gpio.py**: Manages GPIO controls and LCD display

### Dependencies

```bash
# Install required software dependencies
sudo apt-get update
sudo apt-get install -y python3-pip bmaptool
pip3 install pyserial smbus2 gitpython

# GPIO tools for Raspberry Pi
sudo apt-get install -y gpiod
```

## Provisioning Workflow

The automated provisioning process follows these steps:

1. **Initialization**:
   - Setup GPIO control pins
   - Initialize LCD display
   - Wait for button press (if enabled)

2. **Power Management**:
   - Power on the Crystal board using GPIO23
   - Control boot mode pins (GPIO12, GPIO26)

3. **Network Configuration**:
   - Configure Raspberry Pi network (eth2 with IP 192.168.2.1)
   - Setup UART communication
   - Configure Crystal board network (IP 192.168.2.2)
   - Test network connectivity

4. **OS Installation**:
   - Transfer OS image and bmap files to Crystal via SCP
   - Flash OS to Crystal's eMMC using bmaptool
   - Configure system parameters

5. **MAC Address Programming**:
   - Enter U-Boot environment on Crystal board
   - Retrieve available MAC address from database
   - Program MAC address to hardware fuses
   - Update MAC database to mark address as used

6. **Finalization**:
   - Verify all steps completed successfully
   - Power off Crystal board
   - Display completion status on LCD

## Important Implementation Details

### Two Operating Environments

The Crystal board operates in two distinct environments that require different approaches:

1. **Linux OS Mode**:
   - Used for: Network configuration, file transfers, OS installation
   - Authentication: Requires login with root/vitro credentials
   - Accessed via: Normal boot to Linux shell

2. **U-Boot Mode**:
   - Used for: MAC address programming to hardware fuses
   - Authentication: None (direct command access)
   - Accessed via: Interrupting boot sequence when prompted

### Network Configuration

- The Raspberry Pi uses a direct Ethernet connection to the Crystal board
- Connection uses static IPs (Raspberry Pi: 192.168.2.1, Crystal: 192.168.2.2)
- Custom 4-wire Ethernet cable supports 10/100BaseT speeds
- Network test ensures bidirectional communication before proceeding

### MAC Address Management

- MAC addresses are stored in a remote Git repository
- Each Crystal board gets assigned a unique MAC address
- The system creates a Git branch, updates the database, and creates a PR for each assignment
- MAC addresses are permanently programmed to hardware fuses via U-Boot commands

## Troubleshooting Common Issues

### GPIO Control Issues

- **Problem**: `gpioset: invalid mode: output` errors
- **Solution**: Use compatible gpioset syntax without `-m` flag: `gpioset gpiochip0 PIN=VALUE`
- **Note**: Kill any existing gpioset processes before running the script: `pkill gpioset`

### Network Connection Failures

- **Problem**: "No carrier" errors despite blinking Ethernet LEDs
- **Solution**: Check physical connection, force speed/duplex settings: `ethtool -s eth2 speed 100 duplex full autoneg off`
- **Note**: Custom Ethernet cables require proper pinout: 1,2,3,6 connected properly

### UART Communication Issues

- **Problem**: Login failures or no response from Crystal board
- **Solution**: Verify you're in the correct environment (Linux OS vs U-Boot)
- **Debugging**: Use `minicom -D /dev/ttyAMA0 -b 115200` to test UART communication manually

## Usage Instructions

### Standard Operation

```bash
# Run with button start requirement
sudo python3 AutomaticProcedure2/AutoSetup.py
```

### Debug Mode

```bash
# Skip button press requirement for debugging
sudo python3 AutomaticProcedure2/AutoSetup.py --no-button
```

### Before Running

1. Ensure Crystal board is connected via UART and Ethernet
2. Verify power connections are secure
3. Check that required files exist:
   - OS image file: vitro-gateway-imx6dl-crystal-emmc-3.3.1-debug.wic.gz
   - BMAP file: vitro-gateway-imx6dl-crystal-emmc-3.3.1-debug.wic.bmap
   - SSH key file: vitrotv_root_rsa

## Directory Structure

```
projects/
├── mac-db/               # Git repository for MAC addresses
│   └── db.csv            # MAC address database file
└── Vitro/
    ├── AutomaticProcedure2/
    │   ├── AutoSetup.py  # Main control script
    │   ├── uart_flashing.py # MAC programming functionality
    │   ├── lcd_gpio.py   # GPIO and LCD management
    │   └── macdb.py      # MAC database interaction
    ├── vitro-gateway-imx6dl-crystal-emmc-3.3.1-debug.wic.gz  # OS image
    ├── vitro-gateway-imx6dl-crystal-emmc-3.3.1-debug.wic.bmap # Block map file
    └── vitrotv_root_rsa  # SSH key for secure file transfer
```

## Monitoring Progress

The system provides multiple ways to monitor the provisioning process:

1. **LCD Display**: Shows current operation and status
2. **Console Output**: Detailed logging of all operations
3. **LED Indicators**: Both Raspberry Pi and Crystal board have status LEDs

If any step fails, the process will halt, display an error message on the LCD, and log detailed information to the console.