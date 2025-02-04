#!/usr/bin/env python3
import os
import csv
import uuid
import logging
from git import Repo
import subprocess

class MACDatabase:
    def __init__(self, local_path="/tmp/mac-db"):
        self.local_path = local_path
        self.repo_url = "git@github.com:KobolMan/mac-db.git"
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        self.setup_git()
        
        # Get script directory
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.board_info_path = os.path.join(self.script_dir, "boardInfo.txt")
        self.logger.info(f"Board info path: {self.board_info_path}")

    def read_serial_number(self):
        try:
            with open(self.board_info_path, 'r') as f:
                serial = f.read().strip()
                self.logger.info(f"Found serial number: {serial}")
                return serial
        except Exception as e:
            self.logger.error(f"Failed to read serial number: {e}")
            return None

    def update_board_info(self, serial, mac_addr):
        try:
            with open(self.board_info_path, 'w') as f:
                f.write(f"{serial},{mac_addr}")
            self.logger.info(f"Updated board info with MAC {mac_addr}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to update board info: {e}")
            return False

    def setup_git(self):
        try:
            if not os.path.exists(self.local_path):
                self.repo = Repo.clone_from(self.repo_url, self.local_path)
            else:
                self.repo = Repo(self.local_path)
            
            with self.repo.config_writer() as git_config:
                git_config.set_value('user', 'email', 'enrico.garo95@gmail.com')
                git_config.set_value('user', 'name', 'Enrico Garo')
            
            return True
        except Exception as e:
            self.logger.error(f"Git setup failed: {e}")
            return False

    def get_available_mac(self):
        try:
            csv_path = os.path.join(self.local_path, 'db.csv')
            with open(csv_path, 'r') as f:
                reader = csv.reader(f)
                for row in reader:
                    if row[1] == '0':
                        return row[0]
            return None
        except Exception as e:
            self.logger.error(f"Error reading MAC database: {e}")
            return None

    def create_branch(self, mac_addr):
        try:
            branch_name = f"mac-assign-{uuid.uuid4().hex[:8]}"
            current = self.repo.create_head(branch_name)
            current.checkout()
            return branch_name
        except Exception as e:
            self.logger.error(f"Branch creation failed: {e}")
            return None

    def create_pull_request(self, branch_name, mac_addr, serial):
        try:
            cmd = f'cd {self.local_path} && git push origin {branch_name} && ' \
                  f'gh pr create --title "Assign MAC {mac_addr} to {serial}" ' \
                  f'--body "Automated MAC address assignment for board {serial}" ' \
                  f'--base main --head {branch_name}'
            
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            if result.returncode == 0:
                pr_url = result.stdout.strip()
                pr_number = pr_url.split('/')[-1]
                return int(pr_number)
            return None
        except Exception as e:
            self.logger.error(f"PR creation failed: {e}")
            return None

    def merge_pull_request(self, pr_number):
        try:
            cmd = f'cd {self.local_path} && gh pr merge {pr_number} --merge --delete-branch'
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            return result.returncode == 0
        except Exception as e:
            self.logger.error(f"PR merge failed: {e}")
            return False

    def mark_mac_as_used(self, mac_addr, serial):
        try:
            branch_name = self.create_branch(mac_addr)
            if not branch_name:
                return False

            csv_path = os.path.join(self.local_path, 'db.csv')
            rows = []
            updated = False

            with open(csv_path, 'r') as f:
                reader = csv.reader(f)
                for row in reader:
                    if row[0] == mac_addr:
                        rows.append([mac_addr, serial])
                        updated = True
                    else:
                        rows.append(row)

            if updated:
                with open(csv_path, 'w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerows(rows)

                self.repo.index.add(['db.csv'])
                self.repo.index.commit(f"Mark MAC {mac_addr} as used by {serial}")
                
                pr_number = self.create_pull_request(branch_name, mac_addr, serial)
                if pr_number and self.merge_pull_request(pr_number):
                    return True

            return False
        except Exception as e:
            self.logger.error(f"Failed to mark MAC as used: {e}")
            return False

def main():
    db = MACDatabase()
    
    # Read serial number
    serial = db.read_serial_number()
    if not serial:
        print("Failed to read serial number")
        return
        
    # Get and assign MAC
    mac = db.get_available_mac()
    if mac:
        print(f"Found available MAC: {mac}")
        if db.mark_mac_as_used(mac, serial):
            print("Successfully marked MAC as used")
            if db.update_board_info(serial, mac):
                print("Updated board info file")

if __name__ == "__main__":
    main()


##Note: 04/02/2025 This script deals with the MAC address database and the board information file. 
# It reads the serial number from the board information file, gets an available MAC address from the database, marks it as used, and updates the board information file with the MAC address.
# It also creates a branch, a pull request, and merges it to update the MAC address database. The script is designed to be run as part of an automated procedure for assigning MAC addresses to devices.

#NOTE: Add local repo cleaning after PR merge; Check that during PR merge operation the changes are just +1 line in the db.csv file and no line removals; 