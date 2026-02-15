import os
import shutil
from datetime import datetime

class VersionManager:
    def __init__(self, base_data_dir="data"):
        self.base_data_dir = base_data_dir
        self.runs_dir = os.path.join(base_data_dir, "runs")
        os.makedirs(self.runs_dir, exist_ok=True)

    def create_run(self, picos_data):
        """
        Creates a new run directory with a timestamp and saves the current config.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_name = f"run_{timestamp}"
        run_path = os.path.join(self.runs_dir, run_name)
        os.makedirs(run_path, exist_ok=True)
        
        # Save config to the run folder
        import yaml
        with open(os.path.join(run_path, "config.yaml"), 'w', encoding='utf-8') as f:
            yaml.dump({'picos': picos_data}, f, allow_unicode=True, sort_keys=False)
            
        return run_path

    def backup_file(self, source_path, run_path):
        """
        Backs up a file to the specified run directory.
        """
        if os.path.exists(source_path):
            filename = os.path.basename(source_path)
            shutil.copy2(source_path, os.path.join(run_path, filename))
            return True
        return False

    def archive_current_data(self, run_path, tables_dir="data/tables", raw_dir="data/raw"):
        """
        Archives current tables and raw data to the run directory.
        """
        if os.path.exists(tables_dir):
            shutil.copytree(tables_dir, os.path.join(run_path, "tables"), dirs_exist_ok=True)
        if os.path.exists(raw_dir):
            shutil.copytree(raw_dir, os.path.join(run_path, "raw"), dirs_exist_ok=True)
