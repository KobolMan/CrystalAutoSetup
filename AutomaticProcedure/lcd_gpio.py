from smbus2 import SMBus
import time
import threading
import subprocess
import logging

class GroveLCD:
    def __init__(self, bus_number=1, lcd_addr=0x3e):
        self.bus = SMBus(bus_number)
        self.lcd_addr = lcd_addr
        self.initialize()
    
    def send_command(self, cmd):
        self.bus.write_byte_data(self.lcd_addr, 0x80, cmd)
        time.sleep(0.0001)
    
    def send_data(self, data):
        self.bus.write_byte_data(self.lcd_addr, 0x40, ord(data))
        time.sleep(0.0001)
    
    def initialize(self):
        # Initialize display
        self.send_command(0x38) # 8bit, 2 line, 5x8 dots
        self.send_command(0x0C) # Display ON, cursor OFF
        self.send_command(0x01) # Clear display
        time.sleep(0.002)
        self.send_command(0x06) # Entry mode set
    
    def clear(self):
        self.send_command(0x01)
        time.sleep(0.002)
    
    def write(self, text, line=0, start_col=0):
        if line == 0:
            self.send_command(0x80 + start_col)
        else:
            self.send_command(0xC0 + start_col)
        
        for char in text:
            self.send_data(char)

class GPIOManager:
    def __init__(self):
        # GPIO pin definitions
        self.BUTTON_PIN = 17
        self.CRYSTAL_POWER_PIN = 23
        self.BOOT_CONTROL_PIN1 = 12
        self.BOOT_CONTROL_PIN2 = 26
        
        # Button debounce state
        self.button_pressed = False
        self.button_lock = threading.Lock()
        
        # Setup logging
        self.logger = logging.getLogger(__name__)
        
    def set_gpio(self, pin, value):
        """Set a GPIO pin using gpioset"""
        try:
            subprocess.run(['gpioset', 'gpiochip0', f'{pin}={value}'], check=True)
            return True
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to set GPIO {pin}: {e}")
            return False
            
    def get_gpio(self, pin):
        """Get GPIO pin state using gpioget"""
        try:
            result = subprocess.run(['gpioget', 'gpiochip0', f'{pin}'], check=True, 
                                   capture_output=True, text=True)
            return int(result.stdout.strip())
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to get GPIO {pin}: {e}")
            return None
            
    def setup_button(self):
        """Configure button pin as input"""
        try:
            # Just check if the pin can be accessed without configuring pull-up
            # Pull-ups are usually already enabled in hardware or config.txt
            subprocess.run(['gpioget', 'gpiochip0', f'{self.BUTTON_PIN}'], check=True)
            return True
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to setup button: {e}")
            return False
            
    def setup_output_pins(self):
        """Configure all output pins"""
        try:
            # Configure all output pins with initial low state
            for pin in [self.CRYSTAL_POWER_PIN, self.BOOT_CONTROL_PIN1, self.BOOT_CONTROL_PIN2]:
                subprocess.run(['gpioset', 'gpiochip0', f'{pin}=0'], check=True)
            return True
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to setup output pins: {e}")
            return False
            
    def power_on_crystal(self):
        """Power on the Crystal board and enable boot controls"""
        self.set_gpio(self.CRYSTAL_POWER_PIN, 1)
        self.set_gpio(self.BOOT_CONTROL_PIN1, 1)
        self.set_gpio(self.BOOT_CONTROL_PIN2, 1)
        time.sleep(1)  # Wait for power to stabilize
        
    def power_off_crystal(self):
        """Power off the Crystal board"""
        self.set_gpio(self.CRYSTAL_POWER_PIN, 0)
        self.set_gpio(self.BOOT_CONTROL_PIN1, 0)
        self.set_gpio(self.BOOT_CONTROL_PIN2, 0)
        time.sleep(1)  # Wait for power to fully turn off
        
    def power_cycle_crystal(self):
        """Power cycle the Crystal board"""
        self.power_off_crystal()
        time.sleep(2)  # Wait between power cycles
        self.power_on_crystal()
        time.sleep(2)  # Wait for boot
        
    def wait_for_button_press(self, timeout=None):
        """
        Wait for button press with debounce.
        Returns True if button was pressed, False if timeout occurred.
        """
        if timeout:
            end_time = time.time() + timeout
            
        def button_monitor():
            """Button debounce handler"""
            with self.button_lock:
                if self.button_pressed:
                    return
                    
                # Debounce logic
                initial_state = self.get_gpio(self.BUTTON_PIN)
                if initial_state != 0:  # Not pressed
                    return
                    
                # Wait for debounce
                time.sleep(0.05)
                confirmed_state = self.get_gpio(self.BUTTON_PIN)
                if confirmed_state == 0:  # Still pressed after debounce
                    self.button_pressed = True
        
        # Start monitoring
        self.button_pressed = False
        
        while True:
            # Check for timeout
            if timeout and time.time() > end_time:
                return False
                
            # Check button
            button_monitor()
            if self.button_pressed:
                return True
                
            time.sleep(0.05)  # Small delay to avoid CPU thrashing