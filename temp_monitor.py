#!/usr/bin/env python3
"""
Raspberry Pi 5 Temperature Monitor with Headless Options

This script monitors the CPU temperature of a Raspberry Pi 5 and provides
multiple display options including text-based graphs for SSH sessions.

Options:
--save-graph     Save graph images instead of displaying them
--ascii-graph    Show an ASCII graph in the terminal (good for SSH)
--log            Log temperatures to a file
--csv            Save temperatures to a CSV file
"""

import time
import subprocess
import datetime
import signal
import sys
import os
import argparse
from collections import deque

# Global variables for storing temperature data
MAX_POINTS = 60  # Store up to 60 data points
temp_data = deque(maxlen=MAX_POINTS)
time_labels = deque(maxlen=MAX_POINTS)

def get_temp_from_thermal_zone():
    """Get temperature from thermal_zone0"""
    try:
        with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
            temp = float(f.read().strip()) / 1000.0
        return temp
    except Exception as e:
        print(f"Error reading from thermal zone: {e}")
        return None

def get_temp_from_vcgencmd():
    """Get temperature using vcgencmd"""
    try:
        output = subprocess.check_output(['vcgencmd', 'measure_temp'], 
                                        stderr=subprocess.STDOUT).decode('utf-8')
        # Extract the temperature value
        temp = float(output.replace('temp=', '').replace('\'C', '').strip())
        return temp
    except Exception as e:
        print(f"Error using vcgencmd: {e}")
        return None

def get_cpu_temperature():
    """Try both methods to get the CPU temperature"""
    # First try vcgencmd
    temp = get_temp_from_vcgencmd()
    
    # If that fails, try thermal zone
    if temp is None:
        temp = get_temp_from_thermal_zone()
        
    return temp

def signal_handler(sig, frame):
    """Handle interrupt signals for clean exit"""
    print("\nExiting temperature monitor...")
    sys.exit(0)

def save_graph_to_file(temps, times, filename):
    """Save the temperature graph to an image file"""
    try:
        import matplotlib
        matplotlib.use('Agg')  # Use a non-interactive backend
        import matplotlib.pyplot as plt
        
        plt.figure(figsize=(10, 6))
        
        # Create numeric x-axis data
        x_data = list(range(len(temps)))
        
        # Plot the data
        plt.plot(x_data, list(temps), 'r-o')
        
        # Set labels
        plt.ylabel("Temperature (°C)")
        plt.xlabel("Time")
        plt.title("Raspberry Pi 5 CPU Temperature")
        
        # Set ticks
        if len(times) > 10:
            n = max(1, len(times) // 10)
            tick_positions = x_data[::n]
            tick_labels = list(times)[::n]
        else:
            tick_positions = x_data
            tick_labels = list(times)
        
        plt.xticks(tick_positions, tick_labels, rotation=45)
        
        # Adjust y-axis
        if temps:
            min_temp = min(temps)
            max_temp = max(temps)
            padding = (max_temp - min_temp) * 0.1 if len(temps) > 1 else 5
            min_display = max(0, min_temp - padding)
            max_display = max_temp + padding
            plt.ylim(min_display, max_display)
        
        plt.grid(True)
        plt.tight_layout()
        
        # Save the plot
        plt.savefig(filename)
        plt.close()
        
        print(f"Graph saved to {filename}")
        
    except ImportError:
        print("Warning: matplotlib not available, cannot save graph")
    except Exception as e:
        print(f"Error saving graph: {e}")

def display_ascii_graph(temps, width=60, height=15):
    """Display an ASCII art graph in the terminal"""
    if not temps:
        print("No temperature data to display")
        return
    
    # Calculate graph dimensions
    min_temp = min(temps)
    max_temp = max(temps)
    
    # Add padding to min/max
    padding = (max_temp - min_temp) * 0.1 if len(temps) > 1 else 5
    min_display = max(0, min_temp - padding)
    max_display = max_temp + padding
    
    # Create a blank graph
    graph = [[' ' for _ in range(width)] for _ in range(height)]
    
    # Draw the axis
    for i in range(height):
        graph[i][0] = '│'
    for i in range(width):
        graph[height-1][i] = '─'
    graph[height-1][0] = '└'
    
    # Plot the data points
    for i, temp in enumerate(temps):
        # Calculate x position (scale to width)
        x = int((i / (len(temps) - 1 if len(temps) > 1 else 1)) * (width - 2)) + 1 if len(temps) > 1 else width // 2
        
        # Calculate y position (scale to height, inverted)
        normalized_temp = (temp - min_display) / (max_display - min_display) if max_display > min_display else 0.5
        y = int((1 - normalized_temp) * (height - 2)) if height > 2 else 0
        
        # Ensure within bounds
        x = min(max(x, 1), width - 1)
        y = min(max(y, 0), height - 2)
        
        # Plot the point
        graph[y][x] = '●'
    
    # Add temperature scale on the y-axis
    for i in range(height - 1):
        # Calculate temperature at this y position
        position = 1 - (i / (height - 2) if height > 2 else 0.5)
        temp_at_position = min_display + position * (max_display - min_display)
        
        # Add temperature label every few lines
        if i % (height // 4 + 1) == 0:
            temp_str = f"{temp_at_position:.1f}°C"
            # Place the label to the left of the y-axis
            for j, char in enumerate(temp_str):
                if j < 8 and i < height:  # Prevent index errors
                    # Position the label to the left of y-axis
                    graph[i][max(0, -j + -1)] = char
    
    # Print the graph
    print("\n" + "=" * (width + 10))
    print("Raspberry Pi 5 Temperature Graph")
    print("=" * (width + 10))
    
    for row in graph:
        print(''.join(row))
    
    # Print current temperature
    current_temp = temps[-1] if temps else None
    if current_temp is not None:
        print(f"Current: {current_temp:.1f}°C")
    
    print("=" * (width + 10) + "\n")

def log_to_file(temp, timestamp, filename):
    """Log temperature to a text file"""
    with open(filename, 'a') as f:
        f.write(f"{timestamp}, {temp:.1f}°C\n")

def save_to_csv(temp, timestamp, filename):
    """Save temperature to a CSV file"""
    # Check if file exists and create with header if not
    file_exists = os.path.isfile(filename)
    with open(filename, 'a') as f:
        if not file_exists:
            f.write("timestamp,temperature_celsius\n")
        f.write(f"{timestamp},{temp:.1f}\n")

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Raspberry Pi 5 Temperature Monitor")
    parser.add_argument("--interval", type=int, default=5, help="Seconds between temperature readings (default: 5)")
    parser.add_argument("--save-graph", action="store_true", help="Save graph to image files instead of displaying")
    parser.add_argument("--graph-dir", type=str, default="./graphs", help="Directory to save graph images (default: ./graphs)")
    parser.add_argument("--ascii-graph", action="store_true", help="Display an ASCII graph in the terminal")
    parser.add_argument("--log", action="store_true", help="Log temperatures to a text file")
    parser.add_argument("--log-file", type=str, default="temperature.log", help="Log file name (default: temperature.log)")
    parser.add_argument("--csv", action="store_true", help="Save temperatures to a CSV file")
    parser.add_argument("--csv-file", type=str, default="temperature_data.csv", help="CSV file name (default: temperature_data.csv)")
    
    args = parser.parse_args()
    
    # Create graph directory if needed
    if args.save_graph and not os.path.exists(args.graph_dir):
        os.makedirs(args.graph_dir)
    
    # Register signal handler for clean exit
    signal.signal(signal.SIGINT, signal_handler)
    
    print("Raspberry Pi 5 Temperature Monitor")
    print("Press Ctrl+C to exit")
    print("------------------------------------------")
    
    # Counter for saving graph files
    graph_counter = 0
    
    # Main loop
    try:
        while True:
            # Get current temperature
            temp = get_cpu_temperature()
            
            if temp is not None:
                # Get current time
                timestamp = datetime.datetime.now()
                time_str = timestamp.strftime("%H:%M:%S")
                full_time_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")
                
                # Add data to our collections
                temp_data.append(temp)
                time_labels.append(time_str)
                
                # Print to console
                print(f"[{time_str}] CPU Temperature: {temp:.1f}°C")
                
                # Log to file if enabled
                if args.log:
                    log_to_file(temp, full_time_str, args.log_file)
                
                # Save to CSV if enabled
                if args.csv:
                    save_to_csv(temp, full_time_str, args.csv_file)
                
                # Display ASCII graph if enabled
                if args.ascii_graph and len(temp_data) > 1:
                    # Only update the graph every 5 readings to avoid too much output
                    if len(temp_data) % 5 == 0 or len(temp_data) == 2:
                        display_ascii_graph(list(temp_data))
                
                # Save graph to file if enabled
                if args.save_graph and len(temp_data) >= 2:
                    # Save a graph every 10 readings
                    if len(temp_data) % 10 == 0 or len(temp_data) == 2:
                        graph_filename = os.path.join(args.graph_dir, f"temp_graph_{graph_counter:04d}.png")
                        save_graph_to_file(temp_data, time_labels, graph_filename)
                        graph_counter += 1
            
            # Wait for next update
            time.sleep(args.interval)
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()