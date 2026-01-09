"""配置持久化"""
import json
from pathlib import Path
from typing import List, Dict, Any

# 统一使用 config.py 中的 DATA_DIR
from ..config import DATA_DIR

# 配置文件路径
CONFIG_DIR = DATA_DIR
CONFIG_FILE = CONFIG_DIR / "config.json"


def ensure_config_dir():
    """确保配置目录存在"""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def save_accounts(accounts: List[Dict[str, Any]]) -> bool:
    """保存账号配置"""
    try:
        ensure_config_dir()
        config = load_config()
        config["accounts"] = accounts
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"[Persistence] 保存配置失败: {e}")
        return False


def load_accounts() -> List[Dict[str, Any]]:
    """加载账号配置"""
    config = load_config()
    return config.get("accounts", [])


def load_config() -> Dict[str, Any]:
    """加载完整配置"""
    try:
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        print(f"[Persistence] 加载配置失败: {e}")
    return {}


def save_config(config: Dict[str, Any]) -> bool:
    """保存完整配置"""
    try:
        ensure_config_dir()
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"[Persistence] 保存配置失败: {e}")
        return False


def export_config() -> Dict[str, Any]:
    """导出配置（用于备份）"""
    return load_config()


def import_config(config: Dict[str, Any]) -> bool:
    """导入配置（用于恢复）"""
    return save_config(config)
