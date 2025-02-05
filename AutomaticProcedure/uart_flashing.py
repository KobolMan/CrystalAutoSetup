#!/usr/bin/env python3
import serial
import time
import logging
import sys
from macdb import MACDatabase

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
        self.uart.write(f"{command}\n".encode())
        time.sleep(1)
        response = self.read_uart()
        if response:
            self.logger.info(f"Command: {command}\nResponse: {response}")
        return response

    def write_mac_address(self, mac_addr):
       """Temporarily just reads MAC via fuses instead of writing"""
       self.logger.info(f"Would flash MAC: {mac_addr}")
       high_bits = self.send_command("fuse read 4 3")
       low_bits = self.send_command("fuse read 4 2")
       self.logger.info(f"Current MAC high bits: {high_bits}")
       self.logger.info(f"Current MAC low bits: {low_bits}")
       return True  # Simulating success for testing

    def prepare_mac_flash(self):
        serial = self.mac_db.read_serial_number()
        if not serial:
            self.logger.error("Failed to read serial number")
            return None
            
        mac = self.mac_db.get_available_mac()
        if mac:
            self.logger.info(f"Found available MAC: {mac}")
            self.logger.info("I CAN FLASH THE MAC")
            return mac
        return None

    def cleanup(self):
        if self.uart and self.uart.is_open:
            self.uart.close()
            self.logger.info("UART closed")

def main():
    uart = UARTFlasher()
    try:
        if not uart.setup_uart():
            sys.exit(1)

        mac_addr = uart.prepare_mac_flash()
        if mac_addr and uart.wait_for_boot_prompt():
            uart.logger.info("Successfully entered U-Boot")
            if uart.write_mac_address(mac_addr):
                serial = uart.mac_db.read_serial_number()
                uart.mac_db.mark_mac_as_used(mac_addr, serial)
        else:
            uart.logger.error("Failed to prepare for flashing")
            
    except KeyboardInterrupt:
        uart.logger.info("Test interrupted")
    finally:
        uart.cleanup()

if __name__ == "__main__":
    main()