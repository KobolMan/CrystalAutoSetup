#!/usr/bin/env python3
import subprocess
import time
import serial
import logging
import sys
import os
import uuid
import csv
import argparse
from git import Repo

class BoardSetup:
    def __init__(self):
        # Setup logging first
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
        # Network configuration
        self.raspi_ip = "192.168.2.1"
        self.crystal_ip = "192.168.2.2"
        self.netmask = "24"
        self.interface = "eth0"
        
        # File transfer configuration
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.image_file = os.path.join(self.base_dir, "vitro-gateway-imx6dl-crystal-emmc-3.3.1-debug.wic.gz")
        self.bmap_file = os.path.join(self.base_dir, "vitro-gateway-imx6dl-crystal-emmc-3.3.1-debug.wic.bmap")
        self.key_file = os.path.join(self.base_dir, "vitrotv_root_rsa")
        self.remote_path = "/tmp/"
        self.remote_user = "root"
        
        # UART configuration
        self.uart_device = "/dev/ttyAMA0"
        self.uart_baudrate = 115200
        self.uart_timeout = 1
        
        # Credentials
        self.crystal_login = "root"
        self.crystal_password = "vitro"
        
        # Initialize connections and cleanup
        self.cleanup_ssh_known_hosts()
        
        # Initialize UART as None
        self.uart = None

    def cleanup_ssh_known_hosts(self):
        """Remove old SSH known hosts entries for the Crystal board"""
        self.logger.info("Cleaning up SSH known hosts...")
        cleanup_command = f"ssh-keygen -f \"$HOME/.ssh/known_hosts\" -R \"{self.crystal_ip}\" 2>/dev/null || true"
        self.run_command(cleanup_command)

    def run_command(self, command):
        """Execute a shell command and return the result"""
        try:
            result = subprocess.run(
                command,
                shell=True,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            return True, result.stdout
        except subprocess.CalledProcessError as e:
            return False, e.stderr

    def setup_raspi_network(self):
        """Configure network on Raspberry Pi"""
        self.logger.info("Configuring Raspberry Pi network...")
        
        # First, remove existing IP if present
        if not self.remove_ip(self.raspi_ip, self.interface):
            return False
            
        commands = [
            f"sudo ip addr add {self.raspi_ip}/{self.netmask} dev {self.interface}",
            f"sudo ip link set {self.interface} up"
        ]
        
        for cmd in commands:
            success, output = self.run_command(cmd)
            if not success:
                self.logger.error(f"Failed to configure Raspberry Pi network: {output}")
                return False
        
        self.logger.info("Raspberry Pi network configuration completed")
        return True

    def setup_uart_connection(self):
        """Setup UART connection to Crystal board"""
        self.logger.info("Setting up UART connection...")
        try:
            self.uart = serial.Serial(
                port=self.uart_device,
                baudrate=self.uart_baudrate,
                timeout=self.uart_timeout
            )
            # Send a newline and wait briefly to ensure connection is ready
            self.uart.write(b"\n")
            time.sleep(0.5)
            self.uart.reset_input_buffer()
            self.uart.reset_output_buffer()
            
            self.logger.info("UART connection established")
            return True
        except serial.SerialException as e:
            self.logger.error(f"Failed to setup UART connection: {e}")
            return False

    def send_uart_command(self, command, wait_time=1):
        """Send command through UART and wait for response"""
        try:
            self.logger.debug(f"Sending UART command: {command}")
            self.uart.write(f"{command}\n".encode())
            time.sleep(wait_time)
            
            response = self.uart.read_all().decode()
            if response:
                self.logger.debug(f"Received response: {response.strip()}")
            else:
                self.logger.debug("No response received")
                
            return response
        except serial.SerialTimeoutException:
            self.logger.error("UART command timed out")
            return None
        except serial.SerialException as e:
            self.logger.error(f"UART communication error: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Failed to send UART command: {e}")
            return None

    def attempt_login(self):
        """Attempt to login to Crystal board via UART"""
        self.logger.info("Attempting to login to Crystal board...")
        
        # Send initial newline to clear any pending input
        self.uart.write(b"\n")
        time.sleep(1)
        self.uart.reset_input_buffer()
        self.uart.reset_output_buffer()
        
        # Wait for login prompt
        time.sleep(2)
        
        # Send login
        self.logger.debug("Sending login...")
        response = self.send_uart_command(self.crystal_login, wait_time=2)
        if not response:
            self.logger.error("No response received after sending login")
            return False
        
        # Wait before sending password
        time.sleep(1)
        
        # Send password
        self.logger.debug("Sending password...")
        response = self.send_uart_command(self.crystal_password, wait_time=2)
        if not response:
            self.logger.error("No response received after sending password")
            return False
        
        # Wait for login to complete
        time.sleep(2)
        
        # Send another newline to verify we're logged in
        response = self.send_uart_command("")
        if response and ("login" in response.lower() or "password" in response.lower()):
            self.logger.error("Login failed - system still requesting credentials")
            return False
            
        self.logger.info("Successfully logged into Crystal board")
        return True

    def setup_crystal_network(self):
        """Configure network on Crystal board through UART"""
        self.logger.info("Configuring Crystal board network...")
        
        # Attempt login
        if not self.attempt_login():
            self.logger.error("Failed to login to Crystal board - check credentials")
            return False
            
        # Configure network
        commands = [
            f"ip addr add {self.crystal_ip}/{self.netmask} dev {self.interface}",
            f"ip link set {self.interface} up"
        ]
        
        for cmd in commands:
            response = self.send_uart_command(cmd, wait_time=2)
            if not response:
                self.logger.error("Failed to configure Crystal network")
                return False
        
        self.logger.info("Crystal network configuration completed")
        return True

    def test_connection(self):
        """Test network connection between Raspberry Pi and Crystal"""
        self.logger.info("Testing network connection...")
        
        # Test ping from Raspberry Pi to Crystal
        success, output = self.run_command(f"ping -c 3 {self.crystal_ip}")
        if not success:
            self.logger.error("Failed to ping Crystal from Raspberry Pi")
            return False
        
        self.logger.info("Network connection test successful")
        return True

    def check_ip_exists(self, ip, interface):
        """Check if an IP address is already assigned to the interface"""
        success, output = self.run_command(f"ip addr show {interface}")
        if success:
            return ip in output
        return False

    def remove_ip(self, ip, interface):
        """Remove an IP address from the interface"""
        if self.check_ip_exists(ip, interface):
            success, output = self.run_command(f"sudo ip addr del {ip}/{self.netmask} dev {interface}")
            if success:
                self.logger.info(f"Removed existing IP {ip} from {interface}")
                return True
            else:
                self.logger.error(f"Failed to remove IP {ip}: {output}")
                return False
        return True

    def transfer_files(self):
        """Transfer both image and bmap files using SCP"""
        self.logger.info("Starting file transfer to Crystal board...")
        
        # Check if files exist and get their sizes
        files_to_transfer = {
            'Image file': self.image_file,
            'BMAP file': self.bmap_file,
            'SSH key': self.key_file
        }
        
        file_sizes = {}
        for file_desc, filepath in files_to_transfer.items():
            if not os.path.exists(filepath):
                self.logger.error(f"{file_desc} not found at: {filepath}")
                return False
            if file_desc != 'SSH key':
                size_bytes = os.path.getsize(filepath)
                size_mb = size_bytes / (1024 * 1024)
                file_sizes[filepath] = size_mb
                self.logger.info(f"{file_desc} size: {size_mb:.2f} MB")
            
        self.logger.info(f"Using base directory: {self.base_dir}")
        
        # Ensure key file has correct permissions
        os.chmod(self.key_file, 0o600)
        
        # Transfer each file
        files_to_send = [self.image_file, self.bmap_file]
        total_transferred = 0
        start_time = time.time()
        
        for filepath in files_to_send:
            filename = os.path.basename(filepath)
            file_size = file_sizes[filepath]
            
            self.logger.info(f"\nStarting transfer of {filename} ({file_size:.2f} MB)...")
            
            transfer_start = time.time()
            scp_command = (
                f"scp -v -i {self.key_file} -o StrictHostKeyChecking=no "
                f"{filepath} {self.remote_user}@{self.crystal_ip}:{self.remote_path}"
            )
            
            success, output = self.run_command(scp_command)
            transfer_end = time.time()
            
            if not success:
                self.logger.error(f"Failed to transfer {filename}: {output}")
                return False
            
            # Calculate transfer statistics
            transfer_time = transfer_end - transfer_start
            transfer_speed = file_size / transfer_time if transfer_time > 0 else 0
            
            self.logger.info(f"Successfully transferred {filename}")
            self.logger.info(f"Transfer time: {transfer_time:.2f} seconds")
            self.logger.info(f"Transfer speed: {transfer_speed:.2f} MB/s")
            
            total_transferred += file_size
            
        # Final statistics
        total_time = time.time() - start_time
        avg_speed = total_transferred / total_time if total_time > 0 else 0
        
        self.logger.info("\nTransfer Summary:")
        self.logger.info(f"Total data transferred: {total_transferred:.2f} MB")
        self.logger.info(f"Total time: {total_time:.2f} seconds")
        self.logger.info(f"Average transfer speed: {avg_speed:.2f} MB/s")
        
        self.logger.info("All files transferred successfully")
        return True

    def install_os(self):
        """Install OS using bmaptool and configure the system"""
        self.logger.info("Starting OS installation and configuration...")

        # Install OS using bmaptool
        self.logger.info("Installing OS using bmaptool...")
        bmaptool_cmd = (
            f"bmaptool copy --bmap {self.remote_path}{os.path.basename(self.bmap_file)} "
            f"{self.remote_path}{os.path.basename(self.image_file)} /dev/mmcblk2"
        )
        
        response = self.send_uart_command(bmaptool_cmd)
        if not response:
            self.logger.error("Failed to initiate OS installation")
            return False
        
        # Wait for installation to complete (this might take several minutes)
        self.logger.info("Waiting for OS installation to complete... (This may take several minutes)")
        time.sleep(300)  # Initial wait of 5 minutes
        
        # Update endpoint name in node_adaptors.config
        self.logger.info("Updating endpoint name...")
        sed_cmd = "sed -i 's/dummy-app-dev/mitre-poc/' /opt/vitro_io/node_adaptors.config"
        response = self.send_uart_command(sed_cmd)
        if not response:
            self.logger.error("Failed to update endpoint name")
            return False
            
        # Sync and unmount eMMC
        self.logger.info("Syncing and unmounting eMMC...")
        sync_cmd = "sync; umount /media"
        response = self.send_uart_command(sync_cmd)
        if not response:
            self.logger.error("Failed to sync and unmount eMMC")
            return False
            
        # Check and create device_data file if needed
        self.logger.info("Configuring device data...")
        check_create_cmd = (
            '[[ ! -f /opt/vitro_io/gateway/device_data ]] && '
            'echo -e "[provisioning]\\ncustomerId=testCustomer" > /opt/vitro_io/gateway/device_data'
        )
        response = self.send_uart_command(check_create_cmd)
        
        self.logger.info("OS installation and configuration completed successfully")
        return True

    def cleanup(self):
        """Cleanup resources"""
        if hasattr(self, 'uart') and self.uart and self.uart.is_open:
            self.uart.close()
            self.logger.info("UART connection closed")

class MACDatabase:
    def __init__(self, csv_path, prefix='70:b3:d5:f1:9'):
        self.csv_path = csv_path
        self.prefix = prefix
        
    def get_available_mac(self):
        try:
            with open(self.csv_path, 'r') as f:
                reader = csv.reader(f)
                for row in reader:
                    if row[1] == '0':
                        return row[0]
            return None
        except Exception as e:
            print(f"Error reading CSV: {e}")
            return None
        
    def assign_mac(self, mac_addr, serial):
        rows = []
        updated = False
        
        with open(self.csv_path, 'r') as f:
            reader = csv.reader(f)
            for row in reader:
                if row[0] == mac_addr:
                    rows.append([mac_addr, serial])
                    updated = True
                else:
                    rows.append(row)
                    
        if updated:
            with open(self.csv_path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerows(rows)
            return True
        return False

class MACSetup:
    def __init__(self, repo_url, local_path):
        self.repo_url = repo_url
        self.local_path = local_path
        self.db = None
        self.repo = None
        
    def setup_git_config(self):
        subprocess.run(['git', 'config', '--global', 'user.email', 'automation@company.com'])
        subprocess.run(['git', 'config', '--global', 'user.name', 'Automation Bot'])

    def clone_repo(self):
        try:
            if not os.path.exists(self.local_path):
                self.repo = Repo.clone_from(self.repo_url, self.local_path)
            else:
                self.repo = Repo(self.local_path)
            return self.repo
        except Exception as e:
            print(f"Clone failed: {e}")
            return None

    def get_mac_address(self):
        self.db = MACDatabase(os.path.join(self.local_path, 'db.csv'))
        return self.db.get_available_mac()

    def assign_mac(self, mac_addr, serial):
        return self.db.assign_mac(mac_addr, serial)

    def create_branch(self, mac_addr, serial):
        try:
            branch_name = f"mac-assign-{uuid.uuid4().hex[:8]}"
            current = self.repo.create_head(branch_name)
            current.checkout()
            return branch_name
        except Exception as e:
            print(f"Branch creation failed: {e}")
            return None

    def commit_changes(self, mac_addr, serial):
        try:
            if self.assign_mac(mac_addr, serial):
                self.repo.index.add(['db.csv'])
                self.repo.index.commit(f"Assign MAC {mac_addr} to serial {serial}")
                return True
            return False
        except Exception as e:
            print(f"Commit failed: {e}")
            return False

    def push_branch(self, branch_name):
        try:
            origin = self.repo.remote('origin')
            origin.push(branch_name)
            return True
        except Exception as e:
            print(f"Push failed: {e}")
            return False

    def create_pull_request(self, branch_name, mac_addr, serial, base_branch='main'):
        try:
            title = f"Assign MAC {mac_addr} to device {serial}"
            body = f"Automated MAC address assignment\nMAC: {mac_addr}\nSerial: {serial}"
            
            result = subprocess.run([
                'gh', 'pr', 'create',
                '--title', title,
                '--body', body,
                '--base', base_branch,
                '--head', branch_name
            ], cwd=self.local_path, capture_output=True, text=True)
            
            return result.returncode == 0, result.stdout
        except Exception as e:
            print(f"PR creation failed: {e}")
            return False, str(e)

    def merge_pull_request(self, pr_number):
        try:
            result = subprocess.run([
                'gh', 'pr', 'merge',
                str(pr_number),
                '--merge',
                '--delete-branch'
            ], cwd=self.local_path, capture_output=True, text=True)
            
            return result.returncode == 0
        except Exception as e:
            print(f"PR merge failed: {e}")
            return False

class BoardSetupExtended(BoardSetup):
    def __init__(self, github_token, repo_url):
        super().__init__()
        os.environ['GH_TOKEN'] = github_token
        self.mac_setup = MACSetup(repo_url, '/tmp/mac-db')
        self.serial_number = None

    def get_serial_number(self):
        """Get serial number from the board through UART"""
        response = self.send_uart_command("cat /proc/cpuinfo | grep Serial")
        if response:
            self.serial_number = response.strip().split(':')[1].strip()
            return self.serial_number
        return None

    def assign_mac_address(self):
        """Handle MAC address assignment process"""
        self.logger.info("Starting MAC address assignment...")
        
        if not self.serial_number:
            if not self.get_serial_number():
                self.logger.error("Failed to get serial number")
                return False
        
        try:
            # Setup git and clone repo
            self.mac_setup.setup_git_config()
            self.mac_setup.clone_repo()
            
            # Get available MAC address
            mac_addr = self.mac_setup.get_mac_address()
            if not mac_addr:
                self.logger.error("No available MAC addresses")
                return False
            
            # Create branch and commit changes
            branch_name = self.mac_setup.create_branch(mac_addr, self.serial_number)
            self.mac_setup.commit_changes(mac_addr, self.serial_number)
            
            # Push branch and create PR
            if not self.mac_setup.push_branch(branch_name):
                self.logger.error("Failed to push branch")
                return False
            
            success, pr_output = self.mac_setup.create_pull_request(
                branch_name, mac_addr, self.serial_number
            )
            if not success:
                self.logger.error("Failed to create pull request")
                return False
            
            # Extract PR number and merge
            pr_number = int(pr_output.split('/')[-1])
            if not self.mac_setup.merge_pull_request(pr_number):
                self.logger.error("Failed to merge pull request")
                return False
            
            # Write MAC address to board
            self.logger.info(f"Writing MAC address {mac_addr} to board...")
            write_cmd = f"fw_setenv ethaddr {mac_addr}"
            response = self.send_uart_command(write_cmd)
            if not response:
                self.logger.error("Failed to write MAC address to board")
                return False
            
            self.logger.info("MAC address assignment completed successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"MAC address assignment failed: {e}")
            return False
               
def main():
   parser = argparse.ArgumentParser(description='Board Setup and MAC Assignment Tool')
   parser.add_argument('--github-token', required=True, help='GitHub token for authentication')
   parser.add_argument('--repo-url', required=True, help='MAC database repository URL')
   args = parser.parse_args()
   
   setup = BoardSetupExtended(args.github_token, args.repo_url)
   
   try:
       steps = [
           ('Setup Raspberry Pi network', setup.setup_raspi_network),
           ('Setup UART connection', setup.setup_uart_connection),
           ('Setup Crystal network', setup.setup_crystal_network),
           ('Test connection', setup.test_connection),
           ('Transfer files', setup.transfer_files),
           ('Install OS', setup.install_os),
           ('Assign MAC address', setup.assign_mac_address)
       ]
       
       for step_name, step_func in steps:
           setup.logger.info(f"Starting: {step_name}")
           if not step_func():
               setup.logger.error(f"Failed at: {step_name}")
               sys.exit(1)
           setup.logger.info(f"Completed: {step_name}")
           
       setup.logger.info("Setup completed successfully")
       
   except KeyboardInterrupt:
       setup.logger.info("Setup interrupted by user")
   except Exception as e:
       setup.logger.error(f"Unexpected error: {e}")
   finally:
       setup.cleanup()

if __name__ == "__main__":
   main()

if __name__ == "__main__":
    main()