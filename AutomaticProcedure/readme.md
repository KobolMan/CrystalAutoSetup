# Automatic NXP i.MX6DL SoC Board Setup System

Complete automation system for initializing and configuring Crystal boards using a Raspberry Pi 5 as the master controller. The system handles everything from network setup to OS installation, MAC address management and provisioning.

## Project Status

Current software implementation status of key features, 10/02 (95%):

- ✅ Board OS Installation
  - Complete OS image transfer and installation
  - Verified boot sequence
  - Successful system initialization

- ✅ MAC Address Management
  - MAC address fusing implementation
  - Database management with error handling
  - GitHub integration for tracking

- ✅ eMMC Boot Configuration
  - Boot sequence configuration using boot fuse
  - U-Boot environment setup
  - Verified boot from eMMC

- 🔄 Provisioning System
  - Implementation pending
  - Requirements analysis in progress
  - Integration planning phase

## System Architecture

```mermaid
graph LR
    %% AutoSetup Controller
    subgraph AC[AutoSetup Controller]
        direction TB
        Main[Main Coordinator] --> NS[Network Setup]
        Main --> FT[File Transfer]
        Main --> OS[OS Installation]
        Main --> CO[Component Orchestration]
        
        style Main fill:#ffd6eb,stroke:#333,stroke-width:2px,color:#000
        style NS fill:#ffd6eb,stroke:#333,stroke-width:2px,color:#000
        style FT fill:#ffd6eb,stroke:#333,stroke-width:2px,color:#000
        style OS fill:#ffd6eb,stroke:#333,stroke-width:2px,color:#000
        style CO fill:#ffd6eb,stroke:#333,stroke-width:2px,color:#000
    end

    %% MAC Database Manager
    subgraph DB[MAC Database Manager]
        direction TB
        GH[GitHub Integration] --> MA[MAC Assignment]
        MA --> DU[Database Updates]
        DU --> PR[Pull Request Management]
        
        style GH fill:#e6e6ff,stroke:#333,stroke-width:2px,color:#000
        style MA fill:#e6e6ff,stroke:#333,stroke-width:2px,color:#000
        style DU fill:#e6e6ff,stroke:#333,stroke-width:2px,color:#000
        style PR fill:#e6e6ff,stroke:#333,stroke-width:2px,color:#000
    end

    %% UART Communication
    subgraph UC[UART Communication]
        direction TB
        SC[Serial Communication] --> BM[Boot Management]
        BM --> MP[MAC Programming]
        MP --> ES[Environment Setup]
        
        style SC fill:#e6ffe6,stroke:#333,stroke-width:2px,color:#000
        style BM fill:#e6ffe6,stroke:#333,stroke-width:2px,color:#000
        style MP fill:#e6ffe6,stroke:#333,stroke-width:2px,color:#000
        style ES fill:#e6ffe6,stroke:#333,stroke-width:2px,color:#000
    end

    %% Connections between subgraphs
    Main --> DB
    Main --> UC

    %% Force vertical alignment of right subgraphs
    DB --- UC
    
    %% Style subgraph titles
    style AC fill:#444,stroke:#333,stroke-width:2px,color:white
    style DB fill:#444,stroke:#333,stroke-width:2px,color:white
    style UC fill:#444,stroke:#333,stroke-width:2px,color:white
```

## Hardware Overview

```mermaid
graph TB
    subgraph master["MASTER CONTROLLER(RPi5)"]
        subgraph Network["Network Management"]
            M1[Network Controller]
        end
        subgraph Communication["Communication"]
            M2[UART Interface]
            M4[Boot Control]
        end
        subgraph Storage["Storage"]
            M3[File System]
        end
        M1 --> M2
        M1 --> M3
        M2 --> M4
    end

    subgraph target["TARGET BOARD(Crystal)"]
        subgraph InterfaceGroup["Network & UART"]
            T1[Network Interface]
            T2[UART]
        end
        subgraph Boot["Boot System"]
            T3[U-Boot]
            T4[eMMC Storage]
        end
        T1 --> T2
        T2 --> T3
        T3 --> T4
    end

    M1 -->|Ethernet| T1
    M2 -->|Serial| T2
    M3 -->|OS Image| T4

    classDef master fill:#ff9966,stroke:#333,stroke-width:3px,color:#000
    classDef target fill:#6699ff,stroke:#333,stroke-width:3px,color:#000
    classDef subgroup fill:none,stroke:#666,stroke-width:2px,stroke-dasharray:5 5,color:#000
    classDef default color:#000

    class M1,M2,M3,M4 master
    class T1,T2,T3,T4 target
    class Network,Communication,Storage,InterfaceGroup,Boot subgroup

```


### Hardware Implementation

<img src="VitroFixture.png" alt="Hardware Setup Diagram" />

*Figure: Physical setup showing the complete fixture design with RPi 5 (Master) inside the fixture case connected to Crystal Board (Target) via UART, Ethernet and SD adapter. Note: The connections will be enstablished thanks to the linear cart.*


## System Components

### 1. AutoSetup Controller (Main Coordinator)
- Orchestrates the entire setup process
- Manages network configuration for both devices
- Handles file transfers and OS installation
- Coordinates between MAC database and UART operations

### 2. MAC Database Manager
- Manages MAC address allocation
- Handles GitHub repository interactions
- Processes pull requests for MAC assignments
- Maintains synchronization with central database

### 3. UART Communication Manager
- Manages serial communication with the board
- Handles boot sequence and interrupts
- Programs MAC addresses into hardware
- Configures U-Boot environment

## Prerequisites

### Hardware Requirements
- Raspberry Pi 5 (Master Controller)
- Crystal Board (Target Device)
- Physical Connections:
  - UART Connection (3.3V TTL)
  - Ethernet Connection (Cat5e/Cat6)
  - Custom SD adapter
  - Power Supply (5V/3A for RPi, 12V/1A for Crystal)

### Software Requirements
```bash
# Python dependencies
pip install pyserial gitpython PyGithub

# GitHub CLI setup
gh auth login

# System packages
sudo apt update
sudo apt install bmaptool
```

### Required Files Structure
```
project_root/
├── autosetup/
│   ├── autosetup.py        # Main coordinator
│   ├── mac_manager.py      # MAC database handler
│   └── uart_manager.py     # UART communication
├── config/
│   ├── network.yaml        # Network configuration
│   └── github.yaml         # GitHub credentials
├── images/
│   ├── os_image.wic.gz     # OS image
│   └── os_image.wic.bmap   # Block map
└── keys/
    └── vitrotv_root_rsa    # SSH key
```

## Configuration

### Network Configuration
```yaml
# config/network.yaml
master:
  ip: "192.168.2.1"
  interface: "eth0"
  netmask: "255.255.255.0"

target:
  ip: "192.168.2.2"
  interface: "eth0"
  netmask: "255.255.255.0"
```

### GitHub Integration
```bash
# Generate deployment key
ssh-keygen -t ed25519 -C "mac-db-automation" -f ~/.ssh/mac_db_key

# Configure SSH
cat >> ~/.ssh/config << EOL
Host github.com-mac-db
    HostName github.com
    User git
    IdentityFile ~/.ssh/mac_db_key
EOL
```

## Usage

### Basic Usage
```bash
python autosetup.py --config config/setup.yaml
```

### Advanced Options
```bash
python autosetup.py \
  --config config/setup.yaml \
  --github-token YOUR_TOKEN \
  --repo-url git@github.com-mac-db:org/mac-db.git \
  --skip-os-install \
  --verbose
```

## Process Flow

1. **Initialization Phase**
   - Load configurations
   - Verify hardware connections
   - Check file availability

2. **Network Setup**
   - Configure master network
   - Initialize UART connection
   - Setup target network

3. **MAC Address Management**
   - Read board serial number
   - Check MAC availability
   - Create GitHub pull request
   - Program MAC to hardware

4. **OS Installation**
   - Transfer image files
   - Program eMMC
   - Configure system settings

5. **Verification**
   - Test network connectivity
   - Verify MAC assignment
   - Validate OS installation

## Error Handling

### Network Issues
- Connection timeouts
- IP address conflicts
- Interface configuration failures

### MAC Assignment Failures
- Database synchronization errors
- GitHub API issues
- Hardware programming failures

### OS Installation Problems
- Transfer interruptions
- eMMC programming failures
- Boot configuration errors

## Troubleshooting Guide

### Network Configuration
```bash
# Check interface status
ip addr show eth0

# Test connectivity
ping -c 3 192.168.2.2

# Reset interface
sudo ip link set eth0 down
sudo ip link set eth0 up
```

### UART Communication
```bash
# Verify device
ls -l /dev/ttyAMA0

# Test serial connection
screen /dev/ttyAMA0 115200

# Check permissions
sudo usermod -a -G dialout $USER
```

### MAC Database
```bash
# Test GitHub access
ssh -T git@github.com-mac-db

# Verify database
git clone git@github.com-mac-db:org/mac-db.git
cat mac-db/db.csv
```

## Contributing

1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- NXP i.MX6 Development Team
- Raspberry Pi Foundation
- GitHub API Contributors
