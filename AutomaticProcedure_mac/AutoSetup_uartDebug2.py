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
            level=logging.DEBUG,
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

        # Add a flag to track failure status
        self._failed = False

        # Initialize the mac_newly_assigned flag
        self.mac_newly_assigned = False

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
        #start_time = time.time()

        # Clear any existing data in the buffer
        self.uart.reset_input_buffer()

        time.sleep(10) #Give time for the board to start initialization

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
        """Setup UART connection to Crystal board and verify it's booting properly"""
        self.logger.info("Setting up UART connection...")
        self.lcd.clear()
        self.lcd.write("Setting up", 0)
        self.lcd.write("UART...", 1)

        try:
            # Initialize the serial connection
            self.uart = serial.Serial(
                port=self.uart_device,
                baudrate=self.uart_baudrate,
                timeout=self.uart_timeout
            )

            # Clear any buffer data
            self.uart.reset_input_buffer()
            self.uart.reset_output_buffer()

            # Passively listen for boot messages without sending anything
            self.logger.info("Listening for boot messages without disturbing boot process...")

            # Set a timeout for verification
            max_wait_time = 25  # 1 minute to detect boot messages
            start_time = time.time()
            boot_verified = False

            while (time.time() - start_time) < max_wait_time:
                # Check if there's data in the buffer
                if self.uart.in_waiting > 0:
                    # Read what's in the buffer without clearing it
                    response = self.uart.read(self.uart.in_waiting).decode(errors='replace')

                    # Log the received data when in debug mode
                    if self.debug_uart:
                        self.debug_uart_log("received", "Boot data", response)

                    # Check for boot messages that indicate the board is functioning
                    boot_indicators = [
                        "Welcome to vitro",
                        "Starting kernel",
                        "systemd[1]",
                        "login:",
                        "# ",
                        "$ "
                    ]

                    if any(indicator in response for indicator in boot_indicators):
                        indicator_found = next((ind for ind in boot_indicators if ind in response), "boot message")
                        self.logger.info(f"Boot verification successful: '{indicator_found}' detected")
                        boot_verified = True
                        break
                    
                # Small delay to prevent CPU thrashing while waiting for data
                time.sleep(0.5)

            if boot_verified:
                self.logger.info("UART connection established and board boot verified")
                return True
            else:
                self.logger.error("Board boot verification failed - no boot messages detected")
                self.lcd.clear()
                self.lcd.write("Boot Verification", 0)
                self.lcd.write("Failed!", 1)
                return False

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
        """Test network connection between Raspberry Pi and Crystal with packet loss analysis"""
        self.logger.info("Testing network connection...")
        self.lcd.clear()
        self.lcd.write("Testing", 0)
        self.lcd.write("Connection...", 1)
    
        # Wait for everything to stabilize
        self.logger.info("Waiting for network to fully stabilize...")
        time.sleep(15)
        
        # Function to analyze ping results
        def analyze_ping_results(output):
            try:
                # Extract packet statistics from ping output
                if "packet loss" in output:
                    loss_line = next((line for line in output.split('\n') if "packet loss" in line), "")
                    loss_percentage = float(loss_line.split('%')[0].split(' ')[-1])
                    self.logger.info(f"Packet loss: {loss_percentage}%")
                    return loss_percentage
                return 100  # Assume 100% loss if we can't parse the output
            except Exception as e:
                self.logger.error(f"Error parsing ping results: {e}")
                return 100  # Assume 100% loss on parsing error
        
        # Function to reinitialize the network interface
        def reinitialize_interface():
            self.logger.info(f"Reinitializing network interface {self.raspi_interface}...")
            self.lcd.clear()
            self.lcd.write("Reinitializing", 0)
            self.lcd.write("Network...", 1)
            
            # Bring interface down
            down_success, _ = self.run_command(f"sudo ip link set {self.raspi_interface} down")
            if not down_success:
                self.logger.error("Failed to bring interface down")
                return False
            
            # Wait for interface to settle
            time.sleep(2)
            
            # Bring interface up
            up_success, _ = self.run_command(f"sudo ip link set {self.raspi_interface} up")
            if not up_success:
                self.logger.error("Failed to bring interface up")
                return False
            
            # Wait for interface to initialize
            self.logger.info("Waiting for interface to initialize...")
            time.sleep(5)
            return True
        
        # Try connection test up to 3 times
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            self.logger.info(f"Connection test attempt {attempt}/{max_attempts}")
            
            # Send 20 packets for reliable packet loss measurement
            self.logger.info(f"Pinging Crystal board with 20 packets...")
            success, output = self.run_command(f"ping -c 20 -W 2 {self.crystal_ip}")
            
            if not success:
                self.logger.error(f"Ping command failed completely: {output}")
                if attempt < max_attempts:
                    self.logger.info("Reinitializing network and retrying...")
                    if not reinitialize_interface():
                        break
                    continue
                else:
                    self.lcd.clear()
                    self.lcd.write("Connection Test", 0)
                    self.lcd.write("Failed!", 1)
                    return False
            
            # Analyze packet loss
            packet_loss = analyze_ping_results(output)
            
            # If packet loss is less than 3%, connection is good
            if packet_loss < 3:
                self.logger.info(f"Network connection test successful (packet loss: {packet_loss}%)")
                return True
            
            # If packet loss is too high, reinitialize and retry
            self.logger.warning(f"High packet loss ({packet_loss}%), reinitializing connection...")
            if attempt < max_attempts:
                if not reinitialize_interface():
                    break
            else:
                self.logger.error("Max retry attempts reached with high packet loss")
                self.lcd.clear()
                self.lcd.write("Network Test", 0)
                self.lcd.write(f"Fail: {packet_loss}% loss", 1)
                return False
        
        self.logger.error("All connection tests failed")
        self.lcd.clear()
        self.lcd.write("Connection Test", 0)
        self.lcd.write("Failed!", 1)
        return False

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

        # Make sure UART is properly initialized before proceeding
        if self.uart is None or not self.uart.is_open:
            self.logger.info("UART connection not established, attempting to reconnect...")
            if not self.setup_uart_connection():
                self.logger.error("Failed to establish UART connection for U-Boot")
                return False

        response = self.uart.read_all().decode('utf-8', errors='replace')
        # Debug log
        self.logger.debug(f"UART response after version command: {repr(response)}")
        # Send 'b' to enter U-Boot
        self.uart.write(b'b')
        #time.sleep(.1)
        # Read response
        response = self.uart.read_all().decode('utf-8', errors='replace')

        # Debug log
        response = self.uart.read(self.uart.in_waiting).decode('utf-8', errors='replace')

        # Check for U-Boot version information
        if "" in response:
            self.logger.info("Successfully entered U-Boot")
            return True
        else:
            self.logger.error("Failed to enter U-Boot")
            self.lcd.clear()
            self.lcd.write("U-Boot Entry", 0)
            self.lcd.write("Failed!", 1)
            return False

    def transfer_files(self):
        """Transfer both image and bmap files using SCP with LCD progress display"""
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
        overall_start_time = time.time()

        for filepath in files_to_send:
            filename = os.path.basename(filepath)
            file_size = file_sizes[filepath]

            # Define transfer_start here, outside any if/else blocks
            transfer_start = time.time()

            # Small files don't need progress tracking
            if file_size < 1:  # Less than 1MB
                self.lcd.clear()
                self.lcd.write(f"Sending {filename}", 0)
                self.lcd.write("Small file...", 1)

                self.logger.info(f"\nStarting transfer of {filename} ({file_size:.2f} MB)...")

                scp_command = f"scp -O -v -i {self.key_file} -o StrictHostKeyChecking=no {filepath} {self.remote_user}@{self.crystal_ip}:{self.remote_path}"
                success, output = self.run_command(scp_command)

                if not success:
                    self.logger.error(f"Failed to transfer {filename}: {output}")
                    return False
            else:
                # For large files, use time-based progress estimation with timeout
                self.lcd.clear()
                self.lcd.write(f"Sending {int(file_size)}MB", 0)
                self.lcd.write("Progress: 0%", 1)

                self.logger.info(f"\nStarting transfer of {filename} ({file_size:.2f} MB)...")

                # Add a 10-minute (600 seconds) timeout for large file transfers
                transfer_timeout = 600  # 10 minutes in seconds

                # Based on your actual observed transfer rate (approx 1.1 MB/s)
                # Add a 10% buffer to make sure we don't overestimate
                transfer_rate = 1.0  # MB/s
                expected_seconds = min(file_size / transfer_rate, transfer_timeout)

                # Create SCP command
                scp_command = f"scp -O -v -i {self.key_file} -o StrictHostKeyChecking=no {filepath} {self.remote_user}@{self.crystal_ip}:{self.remote_path}"

                # Start the transfer process
                process = subprocess.Popen(
                    scp_command,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )

                # We don't redefine transfer_start here anymore
                last_percentage = 0

                # Add timeout tracking
                transfer_timed_out = False

                # Simple progress loop that updates every 3 seconds
                while process.poll() is None:
                    current_time = time.time()
                    elapsed = current_time - transfer_start

                    # Check if we've exceeded our timeout
                    if elapsed > transfer_timeout:
                        self.logger.error(f"Transfer of {filename} timed out after {transfer_timeout} seconds")
                        self.lcd.clear()
                        self.lcd.write("Transfer Timeout", 0)
                        self.lcd.write("Terminating...", 1)

                        # Terminate the process
                        process.terminate()
                        try:
                            process.wait(timeout=5)  # Give it 5 seconds to terminate gracefully
                        except subprocess.TimeoutExpired:
                            process.kill()  # Force kill if it doesn't terminate

                        transfer_timed_out = True
                        break

                    # Calculate percentage based on elapsed time and expected duration
                    # Cap at 95% until complete
                    percentage = min(95, int((elapsed / expected_seconds) * 100))

                    # Only update in 5% increments - round down to nearest 5%
                    display_percentage = (percentage // 5) * 5

                    # Update LCD if percentage has changed by at least 5%
                    if display_percentage > last_percentage:
                        self.lcd.write(f"Progress: {display_percentage}%", 1)
                        self.logger.info(f"Transfer progress: {display_percentage}%")
                        last_percentage = display_percentage

                    time.sleep(3)  # Check every 3 seconds

                # Handle timeout case
                if transfer_timed_out:
                    self.logger.error(f"Transfer of {filename} failed due to timeout")
                    return False

                # Check if process completed successfully
                returncode = process.poll()
                if returncode != 0:
                    stdout, stderr = process.communicate()
                    self.logger.error(f"Failed to transfer {filename}: {stderr.decode() if stderr else 'Unknown error'}")
                    return False

                # Show 100% when complete
                self.lcd.write("Progress: 100%", 1)
                self.logger.info("Transfer progress: 100%")

            transfer_end = time.time()
            transfer_time = transfer_end - transfer_start
            transfer_speed = file_size / transfer_time if transfer_time > 0 else 0

            self.logger.info(f"Successfully transferred {filename}")
            self.logger.info(f"Transfer time: {transfer_time:.2f} seconds")
            self.logger.info(f"Transfer speed: {transfer_speed:.2f} MB/s")

            total_transferred += file_size

        # Final statistics
        total_time = time.time() - overall_start_time
        avg_speed = total_transferred / total_time if total_time > 0 else 0

        self.logger.info("\nTransfer Summary:")
        self.logger.info(f"Total data transferred: {total_transferred:.2f} MB")
        self.logger.info(f"Total time: {total_time:.2f} seconds")
        self.logger.info(f"Average transfer speed: {avg_speed:.2f} MB/s")

        self.lcd.clear()
        self.lcd.write("File Transfer", 0)
        self.lcd.write("Complete!", 1)
        time.sleep(1)

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
        """Get serial number from the board through UART using ecc_toolkit"""
        self.lcd.clear()
        self.lcd.write("Getting Serial", 0)
        self.lcd.write("Number...", 1)
        
        # Ensure we're in Linux mode and logged in
        if not self.attempt_login():
            self.logger.error("Cannot get serial number - not logged in")
            return None
        
        # Clear buffers for a clean start
        self.uart.reset_input_buffer()
        self.uart.reset_output_buffer()
        
        # Send the command with proper termination
        self.logger.info("Using ecc_toolkit to get serial number...")
        self.uart.write(b"ecc_toolkit get_serial\r\n")
        self.uart.flush()
        
        # Wait longer for the response
        time.sleep(3)
        
        # Read response in chunks to ensure we get everything
        response = ""
        start_time = time.time()
        while (time.time() - start_time) < 5:  # Wait up to 5 seconds
            if self.uart.in_waiting > 0:
                chunk = self.uart.read(self.uart.in_waiting).decode(errors='replace')
                response += chunk
            # If we have a substantial response, break early
            if len(response.strip()) > 10:
                break
            time.sleep(0.5)
        
        # Log the complete response for debugging
        self.logger.debug(f"Raw response: {repr(response)}")
        
        # Parse the response line by line to find the serial number
        lines = response.strip().split('\n')
        for line in lines:
            # Look for a line that contains only hexadecimal characters (and is long enough)
            clean_line = line.strip()
            if len(clean_line) >= 16 and all(c in '0123456789ABCDEFabcdef' for c in clean_line):
                self.serial_number = clean_line
                self.logger.info(f"Found serial number: {clean_line}")
                return clean_line
        
        self.logger.error("Could not parse serial number from ecc_toolkit output")
        self.lcd.clear()
        self.lcd.write("Serial Number", 0)
        self.lcd.write("Not Found!", 1)
        return None
        
    def send_uboot_command(self, command, wait_time=1):
        """
        Send a command to U-Boot and read the response.

        Args:
            command: Command to send
            wait_time: Time to wait for response

        Returns:
            Response string or None on failure
        """
        self.logger.info(f"Sending U-Boot command: {command}")

        if self.uart is None or not self.uart.is_open:
            self.logger.error("UART not connected, cannot send command")
            return None

        # Clear input buffer
        self.uart.reset_input_buffer()

        # Send command with proper line ending
        self.uart.write(f"{command}\r\n".encode())
        self.uart.flush()

        # Wait for response
        time.sleep(wait_time)

        # Read response using proper approach
        response = ""
        max_attempts = 5
        attempts = 0

        while attempts < max_attempts:
            if self.uart.in_waiting > 0:
                chunk = self.uart.read(self.uart.in_waiting).decode('utf-8', errors='replace')
                response += chunk

                # If we got a significant response, we can stop waiting
                if len(response) > 20:
                    break

            # Small delay to allow more data to arrive
            time.sleep(0.2)
            attempts += 1

        # Debug log
        self.logger.debug(f"Raw response to '{command}':\n{repr(response)}")

        return response

    def test_uboot_version(self):
        """Test U-Boot with version command using multiple reads"""
        self.logger.info("Testing U-Boot version command...")
        
        # Send version command
        self.uart.write(b"version\r\n")
        self.uart.flush()
        
        # The key issue: Need to wait longer and read multiple times
        response = ""
        for attempt in range(5):  # Try reading 5 times
            time.sleep(1)  # Wait a full second between reads
            
            if self.uart.in_waiting > 0:
                chunk = self.uart.read(self.uart.in_waiting).decode(errors='ignore')
                response += chunk
                self.logger.info(f"Read attempt {attempt+1}: Got {len(chunk)} bytes")
            else:
                self.logger.info(f"Read attempt {attempt+1}: No data available")
        
        # Log the final response
        self.logger.info(f"Combined response: {repr(response)}")
        
        # Check response
        if response and len(response) > 0:
            self.logger.info("Got response from U-Boot")
            return True
        else:
            self.logger.error("No response from U-Boot")
            return False

    def assign_mac_address(self):
        """Handle MAC address assignment process"""
        self.logger.info("Starting MAC address assignment...")
        self.lcd.clear()
        self.lcd.write("Assigning MAC", 0)
        self.lcd.write("Address...", 1)

        # Setup UART connection if not already done
        if self.uart is None or not self.uart.is_open:
            if not self.setup_uart_connection():
                self.logger.error("Cannot assign MAC - UART connection failed")
                return False

        # Get serial number FIRST while in Linux mode
        self.serial_number = self.get_serial_number()
        if not self.serial_number:
            self.logger.error("Failed to get serial number")
            return False

        # Create UARTFlasher with existing UART
        from uart_flashing import UARTFlasher
        flasher = UARTFlasher(existing_uart=self.uart, existing_logger=self.logger)

        # Check if this serial already has a MAC in database
        existing_mac = flasher.mac_db.get_mac_for_serial(self.serial_number)
        if existing_mac:
            self.logger.info(f"Board already has MAC {existing_mac}")
            self.lcd.clear()
            self.lcd.write("Board Already Has", 0)
            self.lcd.write(f"MAC: {existing_mac}", 1)
            time.sleep(2)
            # Store MAC address as instance variable for label printing
            self.mac_addr = existing_mac
            # Set flag to indicate MAC was already assigned
            self.mac_newly_assigned = False
            return True

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

        # Now enter U-Boot mode
        if not self.enter_uboot():
            self.logger.error("Cannot assign MAC - failed to enter U-Boot")
            return False

        # Reset UART buffers after U-Boot entry
        self.uart.reset_input_buffer()
        self.uart.reset_output_buffer()

        # Wait for U-Boot prompt
        if flasher.wait_for_boot_prompt():
            self.logger.info("Successfully confirmed U-Boot prompt")
            self.lcd.clear()
            self.lcd.write("Writing MAC...", 0)

            if flasher.write_mac_address(mac_addr):
                if flasher.mac_db.mark_mac_as_used(mac_addr, self.serial_number):
                    self.logger.info(f"MAC address {mac_addr} successfully assigned to {self.serial_number}")
                    # Store MAC address as instance variable for label printing
                    self.mac_addr = mac_addr
                    # Set flag to indicate MAC was newly assigned
                    self.mac_newly_assigned = True
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

    def print_label(self, mac_address, ecc_id):
        """Print a label with the board's information"""
        self.logger.info("Preparing to print label...")
        self.lcd.clear()
        self.lcd.write("Preparing", 0)
        self.lcd.write("Board Label...", 1)

        # Get the directory where the current script is located
        script_dir = os.path.dirname(os.path.abspath(__file__))

        # Setup paths for label files
        label_template = os.path.join(self.base_dir, "labels/Label-large-crystal.zpl")
        label_output = os.path.join(self.base_dir, "labels/output-label.zpl")

        # Check if the template file exists
        if not os.path.exists(label_template):
            self.logger.error(f"Label template file not found: {label_template}")
            self.lcd.clear()
            self.lcd.write("Label Template", 0)
            self.lcd.write("Not Found!", 1)
            return False

        # Generate a unique serial number for the board (CN057BQ + 8 random digits)
        # This is separate from the ECC ID
        board_serial = "CN057BQ0123456789" #+ ''.join(random.choices('0123456789', k=8)) ##FIX THIS WITH PROPER BOARD_SERIAL

        # Run the board-info-update.py script to generate the label
        update_cmd = f"python {os.path.join(script_dir, 'board-info-update.py')} {label_template} {label_output} --mac \"{mac_address}\" --ecc_id \"{ecc_id}\" --serial \"{board_serial}\""

        success, output = self.run_command(update_cmd)
        if not success:
            self.logger.error(f"Failed to update label: {output}")
            self.lcd.clear()
            self.lcd.write("Label Update", 0)
            self.lcd.write("Failed!", 1)
            return False

        return self.try_print_label(label_output)

    def try_print_label(self, label_file):
        """Try to print the label and handle retry if needed"""
        max_attempts = 3
        attempt = 0

        while attempt < max_attempts:
            attempt += 1
            self.lcd.clear()
            self.lcd.write("Printing", 0)
            self.lcd.write(f"Label... ({attempt}/{max_attempts})", 1)

            # Send the label to the printer
            print_cmd = f"cat {label_file} > /dev/usb/lp0"
            success, output = self.run_command(print_cmd)

            if success:
                self.logger.info("Label printed successfully")
                self.lcd.clear()
                self.lcd.write("Label Printed", 0)
                self.lcd.write("Successfully", 1)
                time.sleep(2)
                return True

            # Print failed, ask user to check printer and try again
            self.logger.error(f"Failed to print label (attempt {attempt}/{max_attempts}): {output}")

            if attempt >= max_attempts:
                self.lcd.clear()
                self.lcd.write("Label Printing", 0)
                self.lcd.write("Failed!", 1)
                time.sleep(2)
                return False

            # Prompt user to check printer and press button to retry
            self.lcd.clear()
            self.lcd.write("Check Printer", 0)
            self.lcd.write("Press button to retry", 1)

            # Wait for button press if button is enabled
            if self.use_button:
                self.logger.info("Waiting for button press to retry printing...")
                self.gpio_mgr.wait_for_button_press()
            else:
                # If button is disabled, wait a few seconds and retry automatically
                self.logger.info("Button disabled, waiting 5 seconds before retrying...")
                time.sleep(5)

    def print_board_label(self):
        """Print a label with the board information after all steps are complete"""
        # Check if we should print a label (only for newly assigned MACs)
        if not hasattr(self, 'mac_newly_assigned') or not self.mac_newly_assigned:
            self.logger.info("Skipping label printing - MAC was already assigned")
            self.lcd.clear()
            self.lcd.write("Label Printing", 0)
            self.lcd.write("Skipped", 1)
            time.sleep(2)
            return True

        if hasattr(self, 'mac_addr') and hasattr(self, 'serial_number'):
            self.logger.info("Starting label printing process...")
            return self.print_label(self.mac_addr, self.serial_number)
        else:
            self.logger.error("Cannot print label - MAC address or serial number missing")
            self.lcd.clear()
            self.lcd.write("Label Printing", 0)
            self.lcd.write("Error: Missing Info", 1)
            return False

    def cleanup(self):
        """Cleanup resources"""
        if hasattr(self, 'uart') and self.uart and self.uart.is_open:
            self.uart.close()
            self.logger.info("UART connection closed")

        # Power off Crystal when done
        if hasattr(self, 'gpio_mgr'):
            self.gpio_mgr.power_off_crystal()

            # Handle LEDs based on success/failure status
            if not hasattr(self, '_failed') or not self._failed:
                # Success - green LED on, red LED off
                self.gpio_mgr.green_led_on()
                self.gpio_mgr.red_led_off()

                # Success LCD message
                if hasattr(self, 'lcd'):
                    self.lcd.clear()
                    self.lcd.write("Setup Complete", 0)
                    self.lcd.write("System Ready", 1)
            else:
                # Failure - keep red LED on, green LED off
                self.gpio_mgr.red_led_on()  # Keep red LED ON for failure (not just blinking)
                self.gpio_mgr.green_led_off()

                # We don't want to overwrite the error message that was already displayed
                # LCD message should already show the specific error

def main():
    parser = argparse.ArgumentParser(description='Board Setup and MAC Assignment Tool')
    parser.add_argument('--no-button', action='store_true', help='Disable button requirement to start')
    parser.add_argument('--debug-uart', action='store_true', help='Enable UART debugging and interactive mode')
    args = parser.parse_args()
    
    # Create the setup object outside the retry loop so we don't reinitialize everything
    setup = BoardSetup(use_button=not args.no_button, debug_uart=args.debug_uart)
    
    try:
        # Wait for button press if enabled - this happens only once at the start
        setup.wait_for_start()
        
        retry = True
        while retry:
            retry = False  # Will be set to True if we need to retry
            setup._failed = False  # Reset failure flag on each attempt
            setup.gpio_mgr.red_led_off()
            
            try:
                # Power on Crystal board
                setup.power_on_crystal()
                
                steps = [
                    ('Setup UART connection', setup.setup_uart_connection), 
                    ('Test connection', setup.test_connection),
                    ('Transfer files', setup.transfer_files),
                    ('Install OS', setup.install_os),
                    ('Assign MAC address', setup.assign_mac_address),
                    ('Print Board Label', setup.print_board_label)
                ]
                
                for step_name, step_func in steps:
                    setup.logger.info(f"Starting: {step_name}")
                    if not step_func():
                        setup.logger.error(f"Failed at: {step_name}")
                        setup._failed = True  # Set the failure flag
                        
                        # Blink the red LED to indicate failure
                        setup.gpio_mgr.blink_red_led(times=5, interval=0.2)
                        setup.gpio_mgr.red_led_on()  # Then keep it on
                        
                        setup.gpio_mgr.power_off_crystal()  # Power off the board on failure
                        setup.lcd.clear()
                        setup.lcd.write("Setup Failed", 0)
                        setup.lcd.write(f"At: {step_name[:16]}", 1)
                        
                        # Ask user to retry
                        time.sleep(3)  # Show error message for 3 seconds
                        
                        # Only prompt for retry if button use is enabled
                        if setup.use_button:
                            setup.lcd.clear()
                            setup.lcd.write("Press button", 0)
                            setup.lcd.write("to retry", 1)
                            
                            # Wait for button press
                            setup.logger.info("Waiting for button press to retry...")
                            setup.gpio_mgr.wait_for_button_press()
                            retry = True
                        else:
                            setup.logger.info("Button disabled, cannot prompt for retry")
                            # Exit if we can't retry
                            sys.exit(1)
                        
                        # Break out of the step loop
                        break
                    
                    setup.logger.info(f"Completed: {step_name}")
                
                # If we got through all steps without failure, turn on green LED
                if not setup._failed:
                    setup.gpio_mgr.green_led_on()
                    setup.gpio_mgr.red_led_off()
                    setup.logger.info("Setup completed successfully")
                    setup.lcd.clear()
                    setup.lcd.write("Setup Complete", 0)
                    setup.lcd.write("System Ready", 1)
                    
            except KeyboardInterrupt:
                setup.logger.info("Setup interrupted by user")
                setup._failed = True
                # Blink red LED on interruption
                setup.gpio_mgr.blink_red_led(times=3, interval=0.5)
                setup.gpio_mgr.red_led_on()  # Keep red LED on
                setup.lcd.clear()
                setup.lcd.write("Setup Interrupted", 0)
                setup.lcd.write("By User", 1)
                
                # Ask user to retry after interruption
                if setup.use_button:
                    time.sleep(3)
                    setup.lcd.clear()
                    setup.lcd.write("Press button", 0)
                    setup.lcd.write("to retry", 1)
                    setup.gpio_mgr.wait_for_button_press()
                    retry = True
                
            except Exception as e:
                setup.logger.error(f"Unexpected error: {e}")
                setup._failed = True
                # Blink red LED on unexpected errors
                setup.gpio_mgr.blink_red_led(times=10, interval=0.1)
                setup.gpio_mgr.red_led_on()  # Keep red LED on
                setup.lcd.clear()
                setup.lcd.write("Error:", 0)
                setup.lcd.write(f"{str(e)[:16]}", 1)
                
                # Ask user to retry after unexpected error
                if setup.use_button:
                    time.sleep(3)
                    setup.lcd.clear()
                    setup.lcd.write("Press button", 0)
                    setup.lcd.write("to retry", 1)
                    setup.gpio_mgr.wait_for_button_press()
                    retry = True
                else:
                    # Exit if we can't retry
                    sys.exit(1)
    
    finally:
        # Only perform cleanup if we're completely exiting the program
        # This modified cleanup doesn't change the LCD message or LED states
        if hasattr(setup, 'uart') and setup.uart and setup.uart.is_open:
            setup.uart.close()
            setup.logger.info("UART connection closed")
        
        # Make sure crystal is powered off on exit
        if hasattr(setup, 'gpio_mgr'):
            setup.gpio_mgr.power_off_crystal()


if __name__ == "__main__":
    main()