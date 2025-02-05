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
        end_time = time.time() + timeout
        buffer = ""
        while time.time() < end_time:
            if self.uart.in_waiting:
                char = self.uart.read().decode(errors='ignore')
                buffer += char
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

    def send_command(self, command):
        """
        Sends a command over UART and returns the response.
        """
        self.uart.write(f"{command}\n".encode())
        time.sleep(1)
        response = self.read_uart()
        if response:
            self.logger.info(f"Command: {command}\nResponse: {response}")
        return response

    def write_mac_address(self, mac_addr):
        """
        Programs the MAC fuses with the given MAC address.
        This function:
          1. Converts the MAC string into fuse values.
          2. Issues the fuse programming commands for the high and low registers,
             piping in a confirmation to bypass the interactive warning.
          3. Checks the command output for an expected confirmation message.
        """
        self.logger.info(f"Attempting to flash MAC: {mac_addr}")
        high, low = convert_mac_to_fuse_values(mac_addr)
        if high is None or low is None:
            self.logger.error("MAC conversion failed.")
            return False

        # Prepare commands with confirmation piped in via "echo y |"
        cmd_high = f"echo y | fuse prog 4 3 0x{high:04x}"
        cmd_low = f"echo y | fuse prog 4 2 0x{low:08x}"

        # Execute the high fuse programming command
        high_result = self.send_command(cmd_high)
        if "Programming bank 4 word" not in high_result:
            self.logger.error("Failed to program high fuse value")
            return False

        # Execute the low fuse programming command
        low_result = self.send_command(cmd_low)
        if "Programming bank 4 word" not in low_result:
            self.logger.error("Failed to program low fuse value")
            return False

        self.logger.info("Fuse programming commands executed successfully. (Please check the U-Boot output for confirmation.)")
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
            # Only update the DB if the fuse programming appears to have been triggered
            if uart.write_mac_address(mac_addr):
                serial = uart.mac_db.read_serial_number()
                if uart.mac_db.mark_mac_as_used(mac_addr, serial):
                    uart.logger.info("Database successfully updated with the new MAC address.")
                else:
                    uart.logger.error("Failed to update database after flashing.")
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
#The current version cohoperates with macdb.py (It gets an available MAC address from the database, writes it to the device, and updates the database only if the flashing is succesful).
#Note: The actual MAC flashing is missing. We need to handle the interactive prompt for uboot MAC flashing confirmation.