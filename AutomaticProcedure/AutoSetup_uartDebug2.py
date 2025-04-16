#!/usr/bin/env python3
import subprocess
import time
import serial
import logging
import sys
import os
import argparse
from lcd_gpio import GroveLCD, GPIOManager

class BoardSetup:
    def __init__(self, use_button=True, debug_uart=False):
        # Setup logging first
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
        # Initialize GPIO and LCD
        self.gpio_mgr = GPIOManager()
        self.lcd = GroveLCD()
        self.use_button = use_button
        # Add debug_uart flag
        self.debug_uart = debug_uart
        if self.debug_uart:
            # Create or clear debug log file
            with open("uart_debug.log", "w") as f:
                f.write(f"UART Debug Log - Started at {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("-" * 60 + "\n")

        # Network configuration
        self.raspi_ip = "192.168.2.1"
        self.crystal_ip = "192.168.2.2"
        self.netmask = "24"
        self.raspi_interface = "eth2"  # Interface on Raspberry Pi
        self.crystal_interface = "eth0"  # Interface on Crystal board
        
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
        
        # Initialize the LCD
        self.lcd.clear()
        self.lcd.write("Crystal Setup", 0)
        self.lcd.write("Initializing...", 1)
        
        # Setup GPIO
        self.gpio_mgr.setup_output_pins()
        if self.use_button:
            self.gpio_mgr.setup_button()
        
        # Initialize connections and cleanup
        self.cleanup_ssh_known_hosts()
        
        # Initialize UART as None
        self.uart = None
        
        # Serial number storage
        self.serial_number = None

    def debug_uart_log(self, direction, message, data):
        """Log UART communication when debug is enabled"""
        if not self.debug_uart:
            return

        if direction == "sent":
            prefix = ">>> SENT TO CRYSTAL:"
        else:
            prefix = "<<< RECEIVED FROM CRYSTAL:"

        # Format the data for better readability
        if data:
            formatted_data = repr(data)
        else:
            formatted_data = "[NO DATA]"

        # Log to console with colors
        print(f"\n\033[93m{prefix}\033[0m [{message}]")
        print(f"\033[96m{formatted_data}\033[0m")
        print("\033[90m" + "-" * 60 + "\033[0m")

        # Also log to a file for later inspection
        with open("uart_debug.log", "a") as f:
            f.write(f"\n{prefix} [{message}] - {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"{formatted_data}\n")
            f.write("-" * 60 + "\n")


    def wait_for_start(self):
        """Wait for button press if button is enabled"""
        if self.use_button:
            self.lcd.clear()
            self.lcd.write("Press button", 0)
            self.lcd.write("to start setup", 1)
            
            self.logger.info("Waiting for button press to start...")
            self.gpio_mgr.wait_for_button_press()
            
            self.lcd.clear()
            self.lcd.write("Starting setup", 0)
            self.lcd.write("Please wait...", 1)
            
            self.logger.info("Button pressed, starting setup...")
            time.sleep(1)  # Give user time to see status
        else:
            self.logger.info("Button disabled, starting setup immediately")

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

    def power_on_crystal(self):
        """Power on the Crystal board"""
        self.logger.info("Powering on Crystal board...")
        self.lcd.clear()
        self.lcd.write("Powering on", 0)
        self.lcd.write("Crystal...", 1)
        
        self.gpio_mgr.power_on_crystal()
        time.sleep(5)  # Wait for crystal to boot
        
        return True
    def wait_for_boot_completion(self):
        """Wait for Crystal board to complete booting"""
        self.logger.info("Waiting for Crystal boot to complete...")
        self.lcd.clear()
        self.lcd.write("Waiting for", 0)
        self.lcd.write("Boot completion", 1)

        max_wait_time = 120  # Maximum 2 minutes to wait
        start_time = time.time()

        # Clear any existing data in the buffer
        self.uart.reset_input_buffer()

        while (time.time() - start_time) < max_wait_time:
            # Send a newline to prompt output
            self.uart.write(b"\r\n")
            time.sleep(2)

            # Read what's in the buffer
            response = self.uart.read_all().decode(errors='replace')

            # Check for login prompt - this indicates boot is complete
            if "login:" in response:
                self.logger.info("Boot complete, login prompt detected")
                return True

            # Check for shell prompt (# or $) - this indicates already logged in
            if "# " in response or "$ " in response:
                self.logger.info("Boot complete, shell prompt detected")
                return True

            # Look for systemd boot messages
            if "[OK]" in response or "Starting" in response:
                self.logger.info("Boot still in progress, continuing to wait...")

            time.sleep(5)  # Check every 5 seconds

        self.logger.warning("Timeout waiting for boot completion")
        return False

    def power_cycle_crystal(self):
        """Power cycle the Crystal board"""
        self.logger.info("Power cycling Crystal board...")
        self.lcd.clear()
        self.lcd.write("Power cycling", 0)
        self.lcd.write("Crystal...", 1)
        
        self.gpio_mgr.power_cycle_crystal()
        
        return True

    def setup_uart_connection(self):
        """Setup UART connection to Crystal board"""
        self.logger.info("Setting up UART connection...")
        self.lcd.clear()
        self.lcd.write("Setting up", 0)
        self.lcd.write("UART...", 1)
        
        try:
            self.uart = serial.Serial(
                port=self.uart_device,
                baudrate=self.uart_baudrate,
                timeout=self.uart_timeout
            )
            # Just send a newline without trying to interrupt boot
            self.uart.write(b"\n")
            time.sleep(0.5)
            self.uart.reset_input_buffer()
            self.uart.reset_output_buffer()
            
            self.logger.info("UART connection established")
            return True
        except serial.SerialException as e:
            self.logger.error(f"Failed to setup UART connection: {e}")
            self.lcd.clear()
            self.lcd.write("UART Setup", 0)
            self.lcd.write("Failed!", 1)
            return False

    def send_uart_command(self, command, wait_time=1):
        """Send command through UART and wait for response"""
        try:
            self.logger.debug(f"Sending UART command: {command}")

            # Clear input buffer before sending
            self.uart.reset_input_buffer()

            # Debug log before sending
            if self.debug_uart:
                self.debug_uart_log("sent", "Command", command)

            # Send command with proper line ending
            self.uart.write(f"{command}\r\n".encode())
            self.uart.flush()
            time.sleep(wait_time)

            # Read and log response
            response = self.uart.read_all().decode(errors='replace')
            if self.debug_uart:
                self.debug_uart_log("received", "Response", response)

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
        # First make sure boot is complete
        if not self.wait_for_boot_completion():
            self.logger.error("Cannot login - boot not completed")
            return False

        self.logger.info("Attempting to login to Crystal board...")
        self.lcd.clear()
        self.lcd.write("Logging in to", 0)
        self.lcd.write("Crystal...", 1)

        # Clear buffers
        self.uart.reset_input_buffer()
        self.uart.reset_output_buffer()

        # Check if we need to login at all
        self.uart.write(b"\r\n")
        time.sleep(1)
        response = self.uart.read_all().decode(errors='replace')

        # If we already have a shell prompt, no need to login
        if "# " in response:
            self.logger.info("Already logged in as root")
            return True

        # We need to login - look for the login prompt
        if "login:" not in response:
            self.logger.info("No login prompt found, sending newline to trigger it")
            self.uart.write(b"\r\n")
            time.sleep(2)
            response = self.uart.read_all().decode(errors='replace')

        if "login:" not in response:
            self.logger.error("Cannot find login prompt")
            return False

        # Send login
        self.logger.debug("Sending login...")
        self.uart.write(f"{self.crystal_login}\r".encode())
        time.sleep(2)

        # Look for password prompt
        response = self.uart.read_all().decode(errors='replace')
        if "Password:" not in response and "password:" not in response:
            self.logger.error("No password prompt received")
            return False
    
        # Send password
        self.logger.debug("Sending password...")
        self.uart.write(f"{self.crystal_password}\r".encode())
        time.sleep(4)

        # Verify login by looking for shell prompt
        self.uart.write(b"\r\n")
        time.sleep(1)
        response = self.uart.read_all().decode(errors='replace')

        if "# " in response:  # Root shell prompt
            self.logger.info("Successfully logged in as root")
            return True
        elif "$ " in response:  # Regular user shell prompt
            self.logger.info("Successfully logged in as user")
            return True
        else:
            self.logger.error("Login failed - no shell prompt detected")
            self.lcd.clear()
            self.lcd.write("Login Failed", 0)
            return False

    def test_connection(self):
        """Test network connection between Raspberry Pi and Crystal"""
        self.logger.info("Testing network connection...")
        self.lcd.clear()
        self.lcd.write("Testing", 0)
        self.lcd.write("Connection...", 1)

        # Wait for everything to stabilize
        self.logger.info("Waiting for network to fully stabilize...")
        time.sleep(10)

        # Final ARP cache clearing
        #self.run_command(f"sudo ip neigh flush dev {self.raspi_interface}")

        # Simple ping test from Pi to Crystal
        self.logger.info("Pinging Crystal board...")
        success, output = self.run_command(f"ping -c 3 -W 10 {self.crystal_ip}")

        if not success:
            # One retry with longer timeout
            self.logger.info("First ping failed, retrying once...")
            time.sleep(2)
            success, output = self.run_command(f"ping -c 3 -W 10 {self.crystal_ip}")

        if not success:
            self.logger.error(f"Failed to ping Crystal: {output}")
            self.lcd.clear()
            self.lcd.write("Connection Test", 0)
            self.lcd.write("Failed!", 1)
            return False

        self.logger.info("Network connection test successful")
        return True

    def check_ip_exists(self, ip, interface):
        """Check if an IP address is already assigned to the interface"""
        success, output = self.run_command(f"ip addr show {interface}")
        if success:
            return ip in output
        return False

    def enter_uboot(self):
        """Interrupt boot and enter U-Boot"""
        self.logger.info("Interrupting boot to enter U-Boot...")
        self.lcd.clear()
        self.lcd.write("Entering U-Boot", 0)
        self.lcd.write("Please wait...", 1)

        # Power cycle to ensure clean boot
        self.gpio_mgr.power_cycle_crystal()

        # Wait for the board to start booting
        time.sleep(1)

        # Send 'b' key multiple times to increase chances of catching the boot window
        for _ in range(3):
            self.uart.write(b'b')
            time.sleep(0.2)  # Short pause between key presses

        # Wait for U-Boot to initialize
        time.sleep(2)

        # Read response and handle UTF-8 decoding errors
        response = self.uart.read_all().decode('utf-8', errors='replace')

        # Add debug logging to see what we're getting back
        self.logger.debug(f"UART response after sending 'b': {repr(response)}")

        if "=>" in response:
            self.logger.info("Successfully entered U-Boot")
            return True
        else:
            self.logger.error("Failed to enter U-Boot")
            self.lcd.clear()
            self.lcd.write("U-Boot Entry", 0)
            self.lcd.write("Failed!", 1)
            return False

    def transfer_files(self):
        """Transfer both image and bmap files using SCP"""
        self.logger.info("Starting file transfer to Crystal board...")
        self.lcd.clear()
        self.lcd.write("Transferring", 0)
        self.lcd.write("Image Files...", 1)
        
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
        files_to_send = [self.bmap_file, self.image_file]
        total_transferred = 0
        start_time = time.time()
        
        for filepath in files_to_send:
            filename = os.path.basename(filepath)
            file_size = file_sizes[filepath]
            
            self.logger.info(f"\nStarting transfer of {filename} ({file_size:.2f} MB)...")
            
            transfer_start = time.time()
            scp_command = (
                f"scp -O -v -i {self.key_file} -o StrictHostKeyChecking=no "
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
        self.lcd.clear()
        self.lcd.write("Installing OS", 0)
        self.lcd.write("Please wait...", 1)

        # Install OS using bmaptool
        self.logger.info("Installing OS using bmaptool...")
        bmaptool_cmd = (
            f"bmaptool copy --bmap {self.remote_path}{os.path.basename(self.bmap_file)} "
            f"{self.remote_path}{os.path.basename(self.image_file)} /dev/mmcblk2"
        )
        
        response = self.send_uart_command(bmaptool_cmd)
        if not response:
            self.logger.error("Failed to initiate OS installation")
            self.lcd.clear()
            self.lcd.write("OS Installation", 0)
            self.lcd.write("Failed!", 1)
            return False
        
        # Wait for installation to complete (this might take several minutes)
        self.logger.info("Waiting for OS installation to complete... (This may take several minutes)")
        self.lcd.clear()
        self.lcd.write("Installing OS", 0)
        
        # Show progress on LCD
        total_wait = 300  # 5 minutes
        for i in range(total_wait):
            if i % 30 == 0:  # Update every 30 seconds
                percent = int((i / total_wait) * 100)
                self.lcd.write(f"Progress: {percent}%", 1)
            time.sleep(1)
        
        # Update endpoint name in node_adaptors.config
        self.logger.info("Updating endpoint name...")
        self.lcd.clear()
        self.lcd.write("Configuring OS", 0)
        self.lcd.write("Settings...", 1)
        
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
        
        self.lcd.clear()
        self.lcd.write("OS Installation", 0)
        self.lcd.write("Complete!", 1)
        time.sleep(2)
        
        self.logger.info("OS installation and configuration completed successfully")
        return True

    def get_serial_number(self):
        """Get serial number from the board through UART"""
        self.lcd.clear()
        self.lcd.write("Getting Serial", 0)
        self.lcd.write("Number...", 1)
        
        response = self.send_uart_command("cat /proc/cpuinfo | grep Serial")
        if response:
            serial = response.strip().split(':')[1].strip()
            self.serial_number = serial
            self.logger.info(f"Found serial number: {serial}")
            return serial
        
        self.lcd.clear()
        self.lcd.write("Serial Number", 0)
        self.lcd.write("Not Found!", 1)
        return None

    def assign_mac_address(self):
        """Handle MAC address assignment process"""
        self.logger.info("Starting MAC address assignment...")
        self.lcd.clear()
        self.lcd.write("Assigning MAC", 0)
        self.lcd.write("Address...", 1)

        # First enter U-Boot mode
        if not self.enter_uboot():
            self.logger.error("Cannot assign MAC - failed to enter U-Boot")
            return False

        # Import UARTFlasher at runtime to avoid circular imports
        from uart_flashing import UARTFlasher

        try:
            # Get serial number if not already available
            if not self.serial_number:
                self.serial_number = self.get_serial_number()
                if not self.serial_number:
                    self.logger.error("Failed to get serial number")
                    return False

            # Create a UARTFlasher with our existing UART connection and logger
            flasher = UARTFlasher(existing_uart=self.uart, existing_logger=self.logger)
            
            # Since we're using the existing UART, we don't need to call setup_uart()
            # but we should reset buffers to ensure clean state
            self.uart.reset_input_buffer()
            self.uart.reset_output_buffer()
            
            # Get available MAC address
            mac_addr = flasher.mac_db.get_available_mac()
            if not mac_addr:
                self.logger.error("No available MAC addresses")
                self.lcd.clear()
                self.lcd.write("No Available", 0)
                self.lcd.write("MAC Addresses!", 1)
                return False
            
            # Display MAC address on LCD
            self.lcd.clear()
            self.lcd.write("Using MAC:", 0)
            self.lcd.write(f"{mac_addr}", 1)
            
            # Follow the boot sequence but without closing our UART
            if flasher.wait_for_boot_prompt():
                self.logger.info("Successfully entered U-Boot")
                self.lcd.clear()
                self.lcd.write("Writing MAC...", 0)
                
                if flasher.write_mac_address(mac_addr):
                    if flasher.mac_db.mark_mac_as_used(mac_addr, self.serial_number):
                        self.logger.info(f"MAC address {mac_addr} successfully assigned to {self.serial_number}")
                        self.lcd.clear()
                        self.lcd.write("MAC Assignment", 0)
                        self.lcd.write("Complete!", 1)
                        time.sleep(2)
                        return True
                    else:
                        self.logger.error("Failed to mark MAC as used in database")
                        self.lcd.clear()
                        self.lcd.write("Database Update", 0)
                        self.lcd.write("Failed!", 1)
                else:
                    self.logger.error("Failed to write MAC address to the board")
                    self.lcd.clear()
                    self.lcd.write("MAC Writing", 0)
                    self.lcd.write("Failed!", 1)
            else:
                self.logger.error("Failed to reach boot prompt")
                self.lcd.clear()
                self.lcd.write("Boot Prompt", 0)
                self.lcd.write("Not Found!", 1)
            
            return False
        except Exception as e:
            self.logger.error(f"MAC address assignment failed: {e}")
            self.lcd.clear()
            self.lcd.write("MAC Assignment", 0)
            self.lcd.write("Error!", 1)
            return False

    def cleanup(self):
        """Cleanup resources"""
        if hasattr(self, 'uart') and self.uart and self.uart.is_open:
            self.uart.close()
            self.logger.info("UART connection closed")
        
        # Power off Crystal when done
        if hasattr(self, 'gpio_mgr'):
            self.gpio_mgr.power_off_crystal()
        
        # Final LCD message
        if hasattr(self, 'lcd'):
            self.lcd.clear()
            self.lcd.write("Setup Complete", 0)
            self.lcd.write("System Ready", 1)

def main():
    parser = argparse.ArgumentParser(description='Board Setup and MAC Assignment Tool')
    parser.add_argument('--no-button', action='store_true', help='Disable button requirement to start')
    parser.add_argument('--debug-uart', action='store_true', help='Enable UART debugging and interactive mode')
    args = parser.parse_args()
    
    setup = BoardSetup(use_button=not args.no_button, debug_uart=args.debug_uart)
    
    try:
        # Wait for button press if enabled
        setup.wait_for_start()
        
        # Power on Crystal board
        setup.power_on_crystal()
        
        steps = [
            
            ('Setup UART connection', setup.setup_uart_connection), 
            ('Test connection', setup.test_connection),
            ('Transfer files', setup.transfer_files),
            ('Install OS', setup.install_os),
            ('Assign MAC address', setup.assign_mac_address)
            
  
        ]
        
        for step_name, step_func in steps:
            setup.logger.info(f"Starting: {step_name}")
            if not step_func():
                setup.logger.error(f"Failed at: {step_name}")
                setup.gpio_mgr.power_off_crystal()  # Power off the board on failure
                setup.lcd.clear()
                setup.lcd.write("Setup Failed", 0)
                setup.lcd.write(f"At: {step_name[:16]}", 1)
                time.sleep(5)  # Show error for 5 seconds
                sys.exit(1)
            setup.logger.info(f"Completed: {step_name}")
            
        setup.logger.info("Setup completed successfully")
        
    except KeyboardInterrupt:
        setup.logger.info("Setup interrupted by user")
        setup.lcd.clear()
        setup.lcd.write("Setup Interrupted", 0)
        setup.lcd.write("By User", 1)
    except Exception as e:
        setup.logger.error(f"Unexpected error: {e}")
        setup.lcd.clear()
        setup.lcd.write("Error:", 0)
        setup.lcd.write(f"{str(e)[:16]}", 1)
    finally:
        setup.cleanup()

if __name__ == "__main__":
    main()