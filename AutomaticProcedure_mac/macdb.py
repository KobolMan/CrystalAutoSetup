#!/usr/bin/env python3
import os
import csv
import uuid
import logging
import shutil
from git import Repo
import subprocess

class MACDatabase:
    def __init__(self, local_path="/tmp/mac-db"):
        self.local_path = local_path
        self.repo_url = "git@github.com:KobolMan/mac-db.git"
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.board_info_path = os.path.join(self.script_dir, "boardInfo.txt")
        self.setup_git()

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

    def sync_and_verify_db(self):
        try:
            cmd = f'cd {self.local_path} && git fetch && git reset --hard origin/main'
            subprocess.run(cmd, shell=True)
            return True
        except Exception as e:
            self.logger.error(f"Failed to sync DB: {e}")
            return False

    def get_available_mac(self):
        if not self.sync_and_verify_db():
            return None
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
    def get_mac_for_serial(self, serial):
        """Check if a serial number already has a MAC address assigned"""
        if not self.sync_and_verify_db():
            return None
            
        try:
            csv_path = os.path.join(self.local_path, 'db.csv')
            with open(csv_path, 'r') as f:
                reader = csv.reader(f)
                for row in reader:
                    if len(row) > 1 and row[1] == serial and row[1] != "0":
                        self.logger.info(f"Serial {serial} already assigned to MAC {row[0]}")
                        return row[0]  # Return the existing MAC
            return None  # No assignment found
        except Exception as e:
            self.logger.error(f"Error checking serial in database: {e}")
            return None
    
    def read_serial_number(self):
        try:
            with open(self.board_info_path, 'r') as f:
                serial = f.read().strip()
                self.logger.info(f"Found serial number: {serial}")
                return serial
        except Exception as e:
            self.logger.error(f"Failed to read serial number: {e}")
            return None

    def verify_pr_changes(self, branch_name):
        try:
            cmd = f'cd {self.local_path} && git diff origin/main..{branch_name} --numstat'
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            
            if result.returncode == 0:
                changes = result.stdout.strip().split('\t')
                if len(changes) == 3:
                    additions = int(changes[0])
                    deletions = int(changes[1])
                    return changes[2] == 'db.csv' and additions == 1 and deletions == 1
            return False
        except Exception as e:
            self.logger.error(f"Failed to verify PR changes: {e}")
            return False

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
            cmd = f'cd {self.local_path} && git push origin {branch_name}'
            subprocess.run(cmd, shell=True)
            
            cmd = f'cd {self.local_path} && gh pr create --title "Assign MAC {mac_addr} to {serial}" ' \
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
            if result.returncode == 0:
                self.cleanup_local_repo()
            return result.returncode == 0
        except Exception as e:
            self.logger.error(f"PR merge failed: {e}")
            return False

    def cleanup_local_repo(self):
        try:
            if os.path.exists(self.local_path):
                shutil.rmtree(self.local_path)
                self.logger.info("Cleaned up local repository")
            return True
        except Exception as e:
            self.logger.error(f"Failed to cleanup repository: {e}")
            return False

    def update_board_info(self, serial, mac_addr):
        try:
            with open(self.board_info_path, 'w') as f:
                f.write(f"{serial},{mac_addr}")
            self.logger.info(f"Updated board info with MAC {mac_addr}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to update board info: {e}")
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
                    return self.update_board_info(serial, mac_addr)
            return False
        except Exception as e:
            self.logger.error(f"Failed to mark MAC as used: {e}")
            return False

def main():
    db = MACDatabase()
    serial = db.read_serial_number()
    if not serial:
        print("Failed to read serial number")
        return

    mac = db.get_available_mac()
    if mac:
        print(f"Found available MAC: {mac}")
        if db.mark_mac_as_used(mac, serial):
            print("Successfully marked MAC as used")

if __name__ == "__main__":
    main()