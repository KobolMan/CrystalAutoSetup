How to Use the Script

Save the script to a file, for example update_zpl.py
Run the script with the required arguments:

bashpython board-info-update.py input.zpl output.zpl --mac "aa:bb:cc:dd:ee:ff" --ecc_id "0123456789ABCDEF" --serial "CN057BQ99999999"
How the Script Works

MAC Address Processing:

Converts the MAC to uppercase
Replaces colons (:) with (Z) for Code 39 barcode format
Handles the special case where "FF" appears as "F)F" in the barcode


ECC ID Processing:

The ECC ID in Code 128 format follows the pattern: >;[first 4 chars]>6[rest of chars]
The script formats the new ECC ID accordingly


Serial Number Processing:

The Serial in Code 128 format follows the pattern: >:[first 7 chars]>5[rest of chars]
The script formats the new Serial accordingly


QR Code Update:

The QR code contains both the ECC ID and MAC in a specific format
The script maintains this format while updating the values



The script maintains all formatting, positions, and sizes as in the original ZPL file, ensuring that the updated label will print correctly.

To print with Zebra thermal printer run: sudo cat vitro-label-zpl.zpl > /dev/usb/lp0