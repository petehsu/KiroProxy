#!/usr/bin/env python3
"""Kiro Proxy CLI - 轻量命令行工具"""
import argparse
import asyncio
import json
import sys
from pathlib import Path


def cmd_serve(args):
    """启动代理服务"""
    from .main import run
    run(port=args.port)


def cmd_accounts_list(args):
    """列出所有账号"""
    from .core import state
    accounts = state.get_accounts_status()
    if not accounts:
        print("暂无账号")
        return
    print(f"{'ID':<10} {'名称':<20} {'状态':<10} {'请求数':<8}")
    print("-" * 50)
    for acc in accounts:
        print(f"{acc['id']:<10} {acc['name']:<20} {acc['status']:<10} {acc['request_count']:<8}")


def cmd_accounts_export(args):
    """导出账号配置"""
    from .core import state
    accounts_data = []
    for acc in state.accounts:
        creds = acc.get_credentials()
        if creds:
            accounts_data.append({
                "name": acc.name,
                "enabled": acc.enabled,
                "credentials": {
                    "accessToken": creds.access_token,
                    "refreshToken": creds.refresh_token,
                    "expiresAt": creds.expires_at,
                    "region": creds.region,
                    "authMethod": creds.auth_method,
                }
            })
    
    output = {"accounts": accounts_data, "version": "1.0"}
    
    if args.output:
        Path(args.output).write_text(json.dumps(output, indent=2, ensure_ascii=False))
        print(f"已导出 {len(accounts_data)} 个账号到 {args.output}")
    else:
        print(json.dumps(output, indent=2, ensure_ascii=False))


def cmd_accounts_import(args):
    """导入账号配置"""
    import uuid
    from .core import state, Account
    from .auth import save_credentials_to_file
    
    data = json.loads(Path(args.file).read_text())
    accounts_data = data.get("accounts", [])
    imported = 0
    
    for acc_data in accounts_data:
        creds = acc_data.get("credentials", {})
        if not creds.get("accessToken"):
            print(f"跳过 {acc_data.get('name', '未知')}: 缺少 accessToken")
            continue
        
        # 保存凭证到文件
        file_path = asyncio.run(save_credentials_to_file({
            "accessToken": creds.get("accessToken"),
            "refreshToken": creds.get("refreshToken"),
            "expiresAt": creds.get("expiresAt"),
            "region": creds.get("region", "us-east-1"),
            "authMethod": creds.get("authMethod", "social"),
        }, f"imported-{uuid.uuid4().hex[:8]}"))
        
        account = Account(
            id=uuid.uuid4().hex[:8],
            name=acc_data.get("name", "导入账号"),
            token_path=file_path,
            enabled=acc_data.get("enabled", True)
        )
        state.accounts.append(account)
        account.load_credentials()
        imported += 1
        print(f"已导入: {account.name}")
    
    state._save_accounts()
    print(f"\n共导入 {imported} 个账号")


def cmd_accounts_add(args):
    """手动添加 Token"""
    import uuid
    from .core import state, Account
    from .auth import save_credentials_to_file
    
    print("手动添加 Kiro 账号")
    print("-" * 40)
    
    name = input("账号名称 [我的账号]: ").strip() or "我的账号"
    print("\n请粘贴 Access Token:")
    access_token = input().strip()
    
    if not access_token:
        print("错误: Access Token 不能为空")
        return
    
    print("\n请粘贴 Refresh Token (可选，直接回车跳过):")
    refresh_token = input().strip() or None
    
    # 保存凭证
    file_path = asyncio.run(save_credentials_to_file({
        "accessToken": access_token,
        "refreshToken": refresh_token,
        "region": "us-east-1",
        "authMethod": "social",
    }, f"manual-{uuid.uuid4().hex[:8]}"))
    
    account = Account(
        id=uuid.uuid4().hex[:8],
        name=name,
        token_path=file_path
    )
    state.accounts.append(account)
    account.load_credentials()
    state._save_accounts()
    
    print(f"\n✅ 账号已添加: {name} (ID: {account.id})")


def cmd_accounts_scan(args):
    """扫描本地 Token"""
    import uuid
    from .core import state, Account
    from .config import TOKEN_DIR
    
    # 扫描新目录
    found = []
    if TOKEN_DIR.exists():
        for f in TOKEN_DIR.glob("*.json"):
            try:
                data = json.loads(f.read_text())
                if "accessToken" in data:
                    already = any(a.token_path == str(f) for a in state.accounts)
                    found.append({"path": str(f), "name": f.stem, "already": already})
            except:
                pass
    
    # 兼容旧目录
    sso_cache = Path.home() / ".aws/sso/cache"
    if sso_cache.exists():
        for f in sso_cache.glob("*.json"):
            try:
                data = json.loads(f.read_text())
                if "accessToken" in data:
                    already = any(a.token_path == str(f) for a in state.accounts)
                    found.append({"path": str(f), "name": f.stem + " (旧目录)", "already": already})
            except:
                pass
    
    if not found:
        print("未找到 Token 文件")
        print(f"Token 目录: {TOKEN_DIR}")
        return
    
    print(f"找到 {len(found)} 个 Token:\n")
    for i, t in enumerate(found):
        status = "[已添加]" if t["already"] else ""
        print(f"  {i+1}. {t['name']} {status}")
    
    if args.auto:
        # 自动添加所有未添加的
        added = 0
        for t in found:
            if not t["already"]:
                account = Account(
                    id=uuid.uuid4().hex[:8],
                    name=t["name"],
                    token_path=t["path"]
                )
                state.accounts.append(account)
                account.load_credentials()
                added += 1
        state._save_accounts()
        print(f"\n已添加 {added} 个账号")
    else:
        print("\n使用 --auto 自动添加所有未添加的账号")


def cmd_login_remote(args):
    """生成远程登录链接"""
    import uuid
    import time
    
    session_id = uuid.uuid4().hex
    host = args.host or "localhost:8080"
    scheme = "https" if args.https else "http"
    
    print("远程登录链接")
    print("-" * 40)
    print(f"\n将以下链接发送到有浏览器的机器上完成登录:\n")
    print(f"  {scheme}://{host}/remote-login/{session_id}")
    print(f"\n链接有效期 10 分钟")
    print("\n登录完成后，在那台机器上导出账号，然后在这里导入:")
    print(f"  python -m kiro_proxy accounts import xxx.json")


def cmd_login_social(args):
    """Social 登录 (Google/GitHub)"""
    from .auth import start_social_auth
    
    provider = args.provider
    print(f"启动 {provider.title()} 登录...")
    
    success, result = asyncio.run(start_social_auth(provider))
    if not success:
        print(f"错误: {result.get('error', '未知错误')}")
        return
    
    print(f"\n请在浏览器中打开以下链接完成授权:\n")
    print(f"  {result['login_url']}")
    print(f"\n授权完成后，将浏览器地址栏中的完整 URL 粘贴到这里:")
    callback_url = input().strip()
    
    if not callback_url:
        print("已取消")
        return
    
    try:
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(callback_url)
        params = parse_qs(parsed.query)
        code = params.get("code", [None])[0]
        oauth_state = params.get("state", [None])[0]
        
        if not code or not oauth_state:
            print("错误: 无效的回调 URL")
            return
        
        from .auth import exchange_social_auth_token
        success, result = asyncio.run(exchange_social_auth_token(code, oauth_state))
        
        if success and result.get("completed"):
            import uuid
            from .core import state, Account
            from .auth import save_credentials_to_file
            
            credentials = result["credentials"]
            file_path = asyncio.run(save_credentials_to_file(
                credentials, f"cli-{provider}"
            ))
            
            account = Account(
                id=uuid.uuid4().hex[:8],
                name=f"{provider.title()} 登录",
                token_path=file_path
            )
            state.accounts.append(account)
            account.load_credentials()
            state._save_accounts()
            
            print(f"\n✅ 登录成功! 账号已添加: {account.name}")
        else:
            print(f"错误: {result.get('error', '登录失败')}")
    except Exception as e:
        print(f"错误: {e}")


def cmd_status(args):
    """查看服务状态"""
    from .core import state
    stats = state.get_stats()
    
    print("Kiro Proxy 状态")
    print("-" * 40)
    print(f"运行时间: {stats['uptime_seconds']} 秒")
    print(f"总请求数: {stats['total_requests']}")
    print(f"错误数: {stats['total_errors']}")
    print(f"错误率: {stats['error_rate']}")
    print(f"账号总数: {stats['accounts_total']}")
    print(f"可用账号: {stats['accounts_available']}")
    print(f"冷却中: {stats['accounts_cooldown']}")


def main():
    parser = argparse.ArgumentParser(
        prog="kiro-proxy",
        description="Kiro API Proxy CLI"
    )
    parser.add_argument("-v", "--version", action="version", version="1.7.1")
    
    subparsers = parser.add_subparsers(dest="command", help="命令")
    
    # serve
    serve_parser = subparsers.add_parser("serve", help="启动代理服务")
    serve_parser.add_argument("-p", "--port", type=int, default=8080, help="端口号")
    serve_parser.set_defaults(func=cmd_serve)
    
    # status
    status_parser = subparsers.add_parser("status", help="查看状态")
    status_parser.set_defaults(func=cmd_status)
    
    # accounts
    accounts_parser = subparsers.add_parser("accounts", help="账号管理")
    accounts_sub = accounts_parser.add_subparsers(dest="accounts_cmd")
    
    # accounts list
    list_parser = accounts_sub.add_parser("list", help="列出账号")
    list_parser.set_defaults(func=cmd_accounts_list)
    
    # accounts export
    export_parser = accounts_sub.add_parser("export", help="导出账号")
    export_parser.add_argument("-o", "--output", help="输出文件")
    export_parser.set_defaults(func=cmd_accounts_export)
    
    # accounts import
    import_parser = accounts_sub.add_parser("import", help="导入账号")
    import_parser.add_argument("file", help="JSON 文件路径")
    import_parser.set_defaults(func=cmd_accounts_import)
    
    # accounts add
    add_parser = accounts_sub.add_parser("add", help="手动添加 Token")
    add_parser.set_defaults(func=cmd_accounts_add)
    
    # accounts scan
    scan_parser = accounts_sub.add_parser("scan", help="扫描本地 Token")
    scan_parser.add_argument("--auto", action="store_true", help="自动添加")
    scan_parser.set_defaults(func=cmd_accounts_scan)
    
    # login
    login_parser = subparsers.add_parser("login", help="登录")
    login_sub = login_parser.add_subparsers(dest="login_cmd")
    
    # login remote
    remote_parser = login_sub.add_parser("remote", help="生成远程登录链接")
    remote_parser.add_argument("--host", help="服务器地址 (如 example.com:8080)")
    remote_parser.add_argument("--https", action="store_true", help="使用 HTTPS")
    remote_parser.set_defaults(func=cmd_login_remote)
    
    # login google
    google_parser = login_sub.add_parser("google", help="Google 登录")
    google_parser.set_defaults(func=cmd_login_social, provider="google")
    
    # login github
    github_parser = login_sub.add_parser("github", help="GitHub 登录")
    github_parser.set_defaults(func=cmd_login_social, provider="github")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    if args.command == "accounts" and not args.accounts_cmd:
        accounts_parser.print_help()
        return
    
    if args.command == "login" and not args.login_cmd:
        login_parser.print_help()
        return
    
    if hasattr(args, "func"):
        args.func(args)


if __name__ == "__main__":
    main()
