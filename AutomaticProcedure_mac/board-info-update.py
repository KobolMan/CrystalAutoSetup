import re
import argparse

def update_zpl(input_file, output_file, mac, ecc_id, serial):
    # Read the original ZPL file
    with open(input_file, 'r') as f:
        zpl_content = f.read()
    
    # Format the MAC for Code 39 barcode
    # Replace colons with (Z) and capitalize hex letters
    mac_barcode = mac.upper().replace(':', '(Z)')
    # Special handling for "FF" in the MAC (appears as F)F in the barcode)
    mac_barcode = mac_barcode.replace('FF', 'F)F')
    
    # Format the ECC ID for Code 128 barcode
    # Format follows pattern: >;[first 4 chars]>6[rest of the chars]
    ecc_barcode = ">;{}>6{}".format(ecc_id[:4], ecc_id[4:])
    
    # Format the Serial for Code 128 barcode
    # Format follows pattern: >:[first 7 chars]>5[rest of the chars]
    serial_barcode = ">:{}>5{}".format(serial[:7], serial[7:])
    
    # Update the MAC in the Code 39 barcode
    zpl_content = re.sub(r'(\^BY2,3,61\^FT57,734\^BAN,,Y,N\n\^FD).*?(\^FS)', 
                         r'\g<1>' + mac_barcode + r'\g<2>', zpl_content)
    
    # Update the ECC ID in the Code 128 barcode
    zpl_content = re.sub(r'(\^BY2,3,61\^FT57,848\^BCN,,Y,N\n\^FD).*?(\^FS)', 
                         r'\g<1>' + ecc_barcode + r'\g<2>', zpl_content)
    
    # Update the Serial in the Code 128 barcode
    zpl_content = re.sub(r'(\^BY2,3,61\^FT57,959\^BCN,,Y,N\n\^FD).*?(\^FS)', 
                         r'\g<1>' + serial_barcode + r'\g<2>', zpl_content)
    
    # Update the QR code that contains both ECC ID and MAC
    zpl_content = re.sub(r'(\^FH\\\^FDLA,).*?(\\0D\\0A).*?(\^FS)', 
                         r'\g<1>' + ecc_id + r'\g<2>' + mac + r'\g<3>', zpl_content)
    
    # Write the updated ZPL file
    with open(output_file, 'w') as f:
        f.write(zpl_content)
    
    print(f"ZPL file updated successfully and saved to {output_file}")
    print(f"Updated MAC: {mac}")
    print(f"Updated ECC ID: {ecc_id}")
    print(f"Updated Serial: {serial}")

def main():
    parser = argparse.ArgumentParser(description='Update MAC, ECC ID, and Serial in ZPL file')
    parser.add_argument('input_file', help='Path to the input ZPL file')
    parser.add_argument('output_file', help='Path to save the updated ZPL file')
    parser.add_argument('--mac', required=True, help='New MAC address (format: xx:xx:xx:xx:xx:xx)')
    parser.add_argument('--ecc_id', required=True, help='New ECC ID')
    parser.add_argument('--serial', required=True, help='New Serial number')
    
    args = parser.parse_args()
    
    update_zpl(args.input_file, args.output_file, args.mac, args.ecc_id, args.serial)

if __name__ == "__main__":
    main()