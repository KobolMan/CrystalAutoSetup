#!/usr/bin/env python3
import os
import time
import subprocess

print("=== GPIO Diagnostic Tool ===")

# Check for running processes using GPIO
print("\nChecking for processes using GPIO...")
try:
    result = subprocess.run("ps aux | grep -i gpio | grep -v grep", 
                         shell=True, text=True, capture_output=True)
    if result.stdout:
        print("Found processes possibly using GPIO:")
        print(result.stdout)
    else:
        print("No processes explicitly using GPIO found.")
except Exception as e:
    print(f"Error checking processes: {str(e)}")

# Check for exported GPIO pins
print("\nChecking for exported GPIO pins...")
try:
    result = subprocess.run("ls -l /sys/class/gpio/", 
                         shell=True, text=True, capture_output=True)
    if "gpio" in result.stdout:
        print("Found exported GPIO pins:")
        print(result.stdout)
    else:
        print("No exported GPIO pins found.")
except Exception as e:
    print(f"Error checking exported pins: {str(e)}")

# Check if I2C is enabled
print("\nChecking I2C status...")
try:
    result = subprocess.run("ls -l /dev/i2c*", 
                         shell=True, text=True, capture_output=True)
    if "i2c" in result.stdout:
        print("I2C is enabled and available:")
        print(result.stdout)
    else:
        print("I2C devices not found - might be disabled.")
except Exception as e:
    print(f"Error checking I2C: {str(e)}")

# Try to fix GPIO issue
print("\nAttempting to release all GPIO pins...")
try:
    # Attempt to unexport all possible GPIO pins
    for i in range(2, 28):
        os.system(f"sudo sh -c 'echo {i} > /sys/class/gpio/unexport' 2>/dev/null")
    print("Attempted to release all GPIO pins.")
except Exception as e:
    print(f"Error releasing pins: {str(e)}")

print("\nTesting direct GPIO access...")
try:
    # Test if we can export a GPIO pin (e.g., GPIO 18)
    test_pin = 18
    # First unexport it to be safe
    os.system(f"sudo sh -c 'echo {test_pin} > /sys/class/gpio/unexport' 2>/dev/null")
    # Try to export it
    export_result = os.system(f"sudo sh -c 'echo {test_pin} > /sys/class/gpio/export'")
    if export_result == 0:
        print(f"Successfully exported GPIO {test_pin}")
        # Set it as output
        os.system(f"sudo sh -c 'echo out > /sys/class/gpio/gpio{test_pin}/direction'")
        # Toggle it a few times
        for i in range(3):
            os.system(f"sudo sh -c 'echo 1 > /sys/class/gpio/gpio{test_pin}/value'")
            time.sleep(0.1)
            os.system(f"sudo sh -c 'echo 0 > /sys/class/gpio/gpio{test_pin}/value'")
            time.sleep(0.1)
        # Unexport it again
        os.system(f"sudo sh -c 'echo {test_pin} > /sys/class/gpio/unexport'")
        print("GPIO access test successful")
    else:
        print(f"Failed to export GPIO {test_pin}")
except Exception as e:
    print(f"Error testing GPIO: {str(e)}")

print("\n=== Diagnostic Complete ===")
print("Run your script again now - GPIO access might be fixed.")