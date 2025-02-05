# MAC Database Manager

## Overview
Python script for managing MAC address assignments with GitHub integration. Handles MAC address allocation, updating board information, and maintaining a centralized database via Git.

## Key Components

### MACDatabase Class
Main class managing MAC assignments and Git operations.

### Configuration
- Local repository: `/tmp/mac-db`
- Remote: `git@github.com:KobolMan/mac-db.git`
- Board info file: Local `boardInfo.txt`

### Key Functions

#### Database Operations
- `get_available_mac()`: Finds unassigned MAC (marked with '0')
- `mark_mac_as_used()`: Assigns MAC to serial number
- `sync_and_verify_db()`: Ensures local DB is current

#### Git Operations
- `setup_git()`: Clones/configures repository
- `create_branch()`: Creates unique branch for changes
- `create_pull_request()`: Opens PR for MAC assignment
- `merge_pull_request()`: Merges and cleans up

#### Board Info Management
- `read_serial_number()`: Gets serial from boardInfo.txt
- `update_board_info()`: Updates file with MAC assignment

### Process Flow
1. Read board serial number
2. Get available MAC address
3. Create branch for changes
4. Update CSV database
5. Create and merge pull request
6. Update board info file
7. Clean up local repository

### Requirements
- Git and GitHub CLI
- SSH key or GitHub token authentication
- Python packages: gitpython

### Security Features
- PR change verification (1 addition, 1 deletion)
- Database sync before operations
- Local repo cleanup after PR merge

## Usage
```bash
python macdb.py
```

### Input
- `boardInfo.txt`: Contains board serial number
- `db.csv`: MAC address database

### Output
- Updated GitHub database
- Updated boardInfo.txt with assigned MAC
- Git PR history of assignments
