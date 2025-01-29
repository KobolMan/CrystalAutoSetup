# Automatic NXP 6dl SOC Board Setup Script

This script automates the setup process for the Crystal board configuration using a Raspberry Pi 5 as the master device and the Crystal board as the slave device.

## Features

- Automatic network configuration for both Raspberry Pi and Crystal board
- UART communication setup and management
- Secure file transfer of system images
- OS installation and configuration
- Automatic endpoint name configuration
- Device data initialization

## Prerequisites

### Hardware Requirements
- Raspberry Pi 5 (master)
- Crystal Board (slave)
- UART connection between devices
- Ethernet connection between devices

### Software Requirements
- Python 3.x
- Required Python packages:
  ```bash
  pip install pyserial
  ```
- SSH key for secure file transfer
- bmaptool installed on the Crystal board

### Required Files
The following files should be present in your project directory:
```
Vitro/
├── AutomaticProcedure/
│   └── AutoSetup.py
├── vitro-gateway-imx6dl-crystal-emmc-3.3.1-debug.wic.gz
├── vitro-gateway-imx6dl-crystal-emmc-3.3.1-debug.wic.bmap
└── vitrotv_root_rsa
```

## Configuration

Before running the script, ensure you set the correct:
1. Login credentials in the script:
   ```python
   self.crystal_login = "SETLOGIN"
   self.crystal_password = "SETPWS"
   ```
2. Network configuration if needed:
   ```python
   self.raspi_ip = "192.168.2.1"
   self.crystal_ip = "192.168.2.2"
   self.netmask = "24"
   self.interface = "eth0"
   ```

## Usage

1. Navigate to the script directory:
   ```bash
   cd /path/to/Vitro/AutomaticProcedure
   ```

2. Execute the script:
   ```bash
   python AutoSetup.py
   ```

## Process Flow

The script executes the following steps:
1. Cleans up any existing SSH known hosts entries
2. Configures Raspberry Pi network
3. Establishes UART connection
4. Configures Crystal board network
5. Tests network connectivity
6. Transfers system image files
7. Installs and configures the OS
8. Sets up device-specific configurations

## Example Output

```
2025-01-28 18:11:53,579 - INFO - Cleaning up SSH known hosts...
2025-01-28 18:11:53,585 - INFO - Configuring Raspberry Pi network...
2025-01-28 18:11:53,595 - INFO - Removed existing IP 192.168.2.1 from eth0
2025-01-28 18:11:53,615 - INFO - Raspberry Pi network configuration completed
2025-01-28 18:11:53,615 - INFO - Setting up UART connection...
2025-01-28 18:11:53,615 - INFO - UART connection established
2025-01-28 18:11:53,615 - INFO - Configuring Crystal board network...
2025-01-28 18:11:53,615 - INFO - Attempting to login to Crystal board...
2025-01-28 18:11:55,616 - INFO - Successfully logged into Crystal board
2025-01-28 18:03:11,084 - INFO - Crystal network configuration completed
2025-01-28 18:03:11,084 - INFO - Testing network connection...
2025-01-28 18:03:13,133 - INFO - Network connection test successful
2025-01-28 18:03:13,133 - INFO - Starting file transfer to Crystal board...
2025-01-28 18:03:13,133 - INFO - Image file size: 478.57 MB
2025-01-28 18:03:13,133 - INFO - BMAP file size: 0.01 MB
2025-01-28 18:03:13,133 - INFO - Using base directory: /home/Faradex/Desktop/Vitro
2025-01-28 18:03:13,133 - INFO - Starting transfer of vitro-gateway-imx6dl-crystal-emmc-3.3.1-debug.wic.gz...
2025-01-28 18:03:58,248 - INFO - Successfully transferred vitro-gateway-imx6dl-crystal-emmc-3.3.1-debug.wic.gz
2025-01-28 18:03:58,249 - INFO - Transfer time: 45.12 seconds
2025-01-28 18:03:58,249 - INFO - Transfer speed: 10.61 MB/s
```

## Error Handling

The script includes comprehensive error handling for:
- Network configuration failures
- UART communication issues
- File transfer problems
- OS installation errors
- Configuration failures

All errors are logged with descriptive messages to help diagnose issues.

## Troubleshooting

1. UART Connection Issues:
   - Verify the UART device path (/dev/ttyAMA0)
   - Check physical connections
   - Verify baud rate settings

2. Network Issues:
   - Ensure both devices are physically connected
   - Verify IP addresses are not in use
   - Check network interface names

3. File Transfer Problems:
   - Verify SSH key permissions (must be 600)
   - Check file paths and permissions
   - Ensure sufficient disk space

## Contributing

Feel free to submit issues and enhancement requests!

## License

[Your License Here]