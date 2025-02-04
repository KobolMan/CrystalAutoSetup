#!/usr/bin/env python3
import serial
import time
import logging
import sys
import threading

class UARTTest:
    def __init__(self, port="/dev/ttyAMA0", baudrate=115200):
        self.uart = None
        self.port = port
        self.baudrate = baudrate
        self.running = True
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(__name__)

    def setup_uart(self):
        try:
            self.uart = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=1
            )
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

    def read_mac_address(self):
        self.logger.info("Reading MAC address...")
        high_bits = self.send_command("fuse read 4 3")
        low_bits = self.send_command("fuse read 4 2")
        return high_bits, low_bits

    def interactive_mode(self):
        print("\nEntering interactive mode. Type commands or 'exit' to quit.")
        while self.running:
            try:
                command = input("U-Boot> ")
                if command.lower() == 'exit':
                    self.running = False
                    break
                self.send_command(command)
            except KeyboardInterrupt:
                self.running = False
                break

    def cleanup(self):
        if self.uart and self.uart.is_open:
            self.uart.close()
            self.logger.info("UART closed")

def main():
    uart = UARTTest()
    try:
        if not uart.setup_uart():
            sys.exit(1)

        if uart.wait_for_boot_prompt():
            uart.logger.info("Successfully entered U-Boot")
            high_bits, low_bits = uart.read_mac_address()
            uart.interactive_mode()
        else:
            uart.logger.error("Failed to enter U-Boot")
            
    except KeyboardInterrupt:
        uart.logger.info("Test interrupted")
    finally:
        uart.cleanup()

if __name__ == "__main__":
    main()