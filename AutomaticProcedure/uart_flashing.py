import serial
import time
import logging
import sys
from macdb import MACDatabase

def convert_mac_to_fuse_values(mac_str):
    """
    Convert a MAC address string (e.g. "ab:cd:ef:12:34:56")
    into two integers:
      - high (16-bit): representing the first two bytes (ab and cd)
      - low (32-bit): representing the remaining four bytes (ef,12,34,56)
    """
    try:
        parts = mac_str.split(':')
        if len(parts) != 6:
            raise ValueError("Invalid MAC address format")
        # Concatenate first two bytes for high part
        high = int(parts[0] + parts[1], 16)
        # Concatenate the remaining four bytes for low part
        low = int(parts[2] + parts[3] + parts[4] + parts[5], 16)
        return high, low
    except Exception as e:
        logging.error(f"MAC conversion error: {e}")
        return None, None

class UARTFlasher:
    def __init__(self, port="/dev/ttyAMA0", baudrate=115200):
        self.uart = None
        self.port = port
        self.baudrate = baudrate
        self.mac_db = MACDatabase()
        
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(__name__)

    def setup_uart(self):
        try:
            self.uart = serial.Serial(port=self.port, baudrate=self.baudrate, timeout=1)
            self.logger.info(f"UART opened on {self.port}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to open UART: {e}")
            return False

    def read_uart(self, timeout=1):
        """
        Read from UART with improved buffering and response detection.
        """
        end_time = time.time() + timeout
        buffer = ""
        while time.time() < end_time:
            if self.uart.in_waiting:
                # Read chunks instead of single chars for better performance
                chunk = self.uart.read(self.uart.in_waiting).decode(errors='ignore')
                buffer += chunk
                
                # Check for various important response patterns
                if "Really perform this fuse programming? <y/N>" in buffer:
                    # Give extra time for the full prompt to arrive
                    time.sleep(0.2)
                    return buffer + self.uart.read(self.uart.in_waiting).decode(errors='ignore')
                    
                # Check for error conditions
                if "Unknown command" in buffer or "command '" in buffer:
                    return buffer
                    
                # Check for successful programming confirmation
                if "Programming bank 4 word" in buffer:
                    # Give extra time for completion
                    time.sleep(0.2)
                    return buffer + self.uart.read(self.uart.in_waiting).decode(errors='ignore')
                    
            # Small sleep to prevent CPU spinning
            time.sleep(0.01)
        return buffer

    def wait_for_boot_prompt(self, timeout=30):
        self.logger.info("Waiting for boot prompt...")
        start_time = time.time()
        while (time.time() - start_time) < timeout:
            response = self.read_uart()
            if response:
                self.logger.info(f"Boot: {response}")
                if "Loading Environment from MMC... OK" in response:
                    self.logger.info("Sending interrupt...")
                    self.uart.write(b' ')
                    time.sleep(0.5)
                    return True
        return False

    def send_command(self, command, wait_for_confirmation=False):
        """
        Sends a command over UART and returns the response.
        If wait_for_confirmation is True, it will handle the interactive prompt.
        """
        # Clear any pending input
        self.uart.reset_input_buffer()
        
        # Send command with proper line ending
        self.uart.write(f"{command}\r\n".encode())
        self.uart.flush()
        time.sleep(1)  # Increased delay to ensure command is processed
        
        response = self.read_uart(timeout=2)  # Increased timeout
        if not response:
            return None

        # Handle the confirmation prompt if expected
        if wait_for_confirmation and "Really perform this fuse programming? <y/N>" in response:
            self.logger.info("Sending confirmation for fuse programming...")
            self.uart.write(b'y\r\n')
            self.uart.flush()
            time.sleep(1)  # Increased delay after confirmation
            final_response = self.read_uart(timeout=2)
            response += final_response
            
            # Verify the command wasn't split
            if "Unknown command" in response or "command '" in response:
                self.logger.error("Command was corrupted during transmission")
                return None

        if response:
            self.logger.info(f"Command: {command}\nResponse: {response}")
        return response

    def write_mac_address(self, mac_addr):
        """
        Programs the MAC fuses with the given MAC address.
        Handles the interactive confirmation prompts from U-Boot.
        Returns True only if both fuse programmings are confirmed successful.
        """
        self.logger.info(f"Attempting to flash MAC: {mac_addr}")
        high, low = convert_mac_to_fuse_values(mac_addr)
        if high is None or low is None:
            self.logger.error("MAC conversion failed.")
            return False

        # Program low fuse value first (4 bytes)
        cmd_low = f"fuse prog 4 2 0x{low:08x}"
        low_result = self.send_command(cmd_low, wait_for_confirmation=True)
        if not low_result or "Programming bank 4 word" not in low_result:
            self.logger.error("Failed to program low fuse value")
            return False

        # Program high fuse value (2 bytes)
        cmd_high = f"fuse prog 4 3 0x{high:04x}"
        high_result = self.send_command(cmd_high, wait_for_confirmation=True)
        if not high_result or "Programming bank 4 word" not in high_result:
            self.logger.error("Failed to program high fuse value")
            return False

        # After successful fuse programming, set the MAC in U-Boot environment
        self.logger.info("MAC address successfully programmed to fuses. Setting environment variables...")
        
        # Set the MAC address in U-Boot environment
        setenv_cmd = f"setenv ethaddr {mac_addr}"
        setenv_result = self.send_command(setenv_cmd)
        if not setenv_result:
            self.logger.error("Failed to set MAC address in U-Boot environment")
            return False
            
        # Save the environment
        save_result = self.send_command("saveenv")
        if not save_result:
            self.logger.error("Failed to save U-Boot environment")
            return False
            
        self.logger.info("Environment saved successfully. Initiating reset...")
        
        # Send reset command
        # Note: We don't check the response here as the device will reset immediately
        self.send_command("reset")
        
        return True

    def cleanup(self):
        if self.uart and self.uart.is_open:
            self.uart.close()
            self.logger.info("UART closed")

def main():
    uart = UARTFlasher()
    try:
        if not uart.setup_uart():
            sys.exit(1)

        mac_addr = uart.mac_db.get_available_mac()
        if not mac_addr:
            uart.logger.error("No available MAC address found")
            sys.exit(1)

        if uart.wait_for_boot_prompt():
            uart.logger.info("Successfully entered U-Boot")
            # Write MAC address and verify success before updating database
            if uart.write_mac_address(mac_addr):
                serial = uart.mac_db.read_serial_number()
                if uart.mac_db.mark_mac_as_used(mac_addr, serial):
                    uart.logger.info("Database successfully updated with the new MAC address.")
                else:
                    uart.logger.error("Failed to update database after successful flashing.")
            else:
                uart.logger.error("MAC fuse programming failed; not updating database.")
        else:
            uart.logger.error("Failed to reach boot prompt; aborting flashing procedure.")
            
    except KeyboardInterrupt:
        uart.logger.info("Test interrupted")
    finally:
        uart.cleanup()

if __name__ == "__main__":
    main()

#This version is now able to flash the MAC address to the device and update the database accordingly. One feature to add is a check that the serial number is not already flashed with a MAC address. This should be done before attempting to flash the OS, so the check should be added to the AutoSetup.py script before even attempting to flash the OS to the eMMC.