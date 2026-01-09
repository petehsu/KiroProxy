"""设备指纹生成"""
import hashlib
import platform
import subprocess
import time
from pathlib import Path
from typing import Optional


def get_raw_machine_id() -> Optional[str]:
    """获取系统原始 Machine ID"""
    system = platform.system()
    
    try:
        if system == "Darwin":
            result = subprocess.run(
                ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
                capture_output=True, text=True, timeout=5
            )
            for line in result.stdout.split("\n"):
                if "IOPlatformUUID" in line:
                    return line.split("=")[1].strip().strip('"').lower()
        
        elif system == "Linux":
            for path in ["/etc/machine-id", "/var/lib/dbus/machine-id"]:
                if Path(path).exists():
                    return Path(path).read_text().strip().lower()
        
        elif system == "Windows":
            result = subprocess.run(
                ["wmic", "csproduct", "get", "UUID"],
                capture_output=True, text=True, timeout=5,
                creationflags=0x08000000
            )
            lines = [l.strip() for l in result.stdout.split("\n") if l.strip()]
            if len(lines) > 1:
                return lines[1].lower()
    except Exception:
        pass
    
    return None


def generate_machine_id(
    profile_arn: Optional[str] = None, 
    client_id: Optional[str] = None
) -> str:
    """生成基于凭证的唯一 Machine ID
    
    每个凭证生成独立的 Machine ID，避免多账号共用同一指纹被检测。
    优先级：profileArn > clientId > 系统硬件 ID
    添加时间因子：按小时变化，避免指纹完全固化。
    """
    unique_key = None
    if profile_arn:
        unique_key = profile_arn
    elif client_id:
        unique_key = client_id
    else:
        unique_key = get_raw_machine_id() or "KIRO_DEFAULT_MACHINE"
    
    hour_slot = int(time.time()) // 3600
    
    hasher = hashlib.sha256()
    hasher.update(unique_key.encode())
    hasher.update(hour_slot.to_bytes(8, 'little'))
    
    return hasher.hexdigest()


def get_kiro_version() -> str:
    """获取 Kiro IDE 版本号
    
    优先检测本地安装的 Kiro，否则使用默认版本 (与 kiro.rs 保持一致)
    """
    if platform.system() == "Darwin":
        kiro_paths = [
            "/Applications/Kiro.app/Contents/Info.plist",
            str(Path.home() / "Applications/Kiro.app/Contents/Info.plist"),
        ]
        for plist_path in kiro_paths:
            try:
                result = subprocess.run(
                    ["defaults", "read", plist_path, "CFBundleShortVersionString"],
                    capture_output=True, text=True, timeout=5
                )
                version = result.stdout.strip()
                if version:
                    return version
            except Exception:
                pass
    
    # 默认版本与 kiro.rs 保持一致
    return "0.8.0"


def get_system_info() -> tuple:
    """获取系统运行时信息 (os_name, node_version)
    
    node_version 与 kiro.rs 保持一致
    """
    system = platform.system()
    
    if system == "Darwin":
        try:
            result = subprocess.run(
                ["sw_vers", "-productVersion"], 
                capture_output=True, text=True, timeout=5
            )
            version = result.stdout.strip() or "14.0"
            os_name = f"macos#{version}"
        except Exception:
            os_name = "macos#14.0"
    elif system == "Linux":
        try:
            result = subprocess.run(
                ["uname", "-r"], 
                capture_output=True, text=True, timeout=5
            )
            version = result.stdout.strip() or "5.15.0"
            os_name = f"linux#{version}"
        except Exception:
            os_name = "linux#5.15.0"
    elif system == "Windows":
        os_name = "windows#10.0"
    else:
        os_name = "other#1.0"
    
    # Node 版本与 kiro.rs 保持一致
    node_version = "22.11.0"
    return os_name, node_version
