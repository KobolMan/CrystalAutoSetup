```
# Automatic NXP 6dl SOC Board Setup Script

Automates Crystal board setup using Raspberry Pi 5, including MAC address assignment and OS installation.

## Features

- Network configuration (Raspberry Pi and Crystal board)
- UART communication management 
- OS installation and configuration
- MAC address assignment with GitHub integration
- Secure file transfer
- Automatic endpoint configuration

## Prerequisites

### Hardware
- Raspberry Pi 5 (master)
- Crystal Board (slave) 
- UART and Ethernet connections

### Software
```bash
pip install pyserial gitpython PyGithub
gh auth login  # GitHub CLI
```

### Required Files
```
projects/
├── mac-db/
│   └── db.csv
└── Vitro/
    ├── AutomaticProcedure/
    │   └── AutoSetup.py
    ├── vitro-gateway-imx6dl-crystal-emmc-3.3.1-debug.wic.gz
    ├── vitro-gateway-imx6dl-crystal-emmc-3.3.1-debug.wic.bmap
    └── vitrotv_root_rsa
```

## Configuration

1. Network settings in script:
```python
self.raspi_ip = "192.168.2.1"
self.crystal_ip = "192.168.2.2"
```

2. GitHub setup:
```bash
# Generate deploy key for MAC database
ssh-keygen -t ed25519 -C "mac-db-automation" -f ~/.ssh/mac_db_key

# Add to SSH config
Host github.com-mac-db
    HostName github.com
    User git
    IdentityFile ~/.ssh/mac_db_key
```

## Usage

```bash
python AutoSetup.py --github-token YOUR_TOKEN --repo-url git@github.com-mac-db:your-org/mac-db.git
```

## Process Flow

1. Network setup
2. UART connection  
3. File transfer
4. OS installation
5. MAC address assignment:
   - Fetch serial number
   - Get available MAC
   - Create PR for assignment
   - Write MAC to board

## Error Handling

- Network configuration failures
- UART issues
- File transfer errors  
- MAC assignment conflicts
- GitHub API errors

## Troubleshooting

1. MAC Assignment Issues:
   - Verify GitHub token permissions
   - Check SSH key setup
   - Ensure db.csv format is correct

2. Network Issues:
   - Both devices physically connected
   - IP addresses not in use
   - Network interface names correct

3. UART Issues:
   - Verify device path (/dev/ttyAMA0)
   - Check physical connections
   - Verify baud rate settings

4. File Transfer:
   - SSH key permissions (600)
   - File paths and permissions
   - Sufficient disk space

## Contributing

Submit issues and enhancement requests via GitHub.

## License

MIT License
```