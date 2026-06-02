from __future__ import annotations

import argparse
import getpass
import os
import sys

import pymysql
from sqlalchemy import create_engine, text


TABLE_DEFINITIONS = {
    "conversations": """
        CREATE TABLE IF NOT EXISTS conversations (
            id BIGINT PRIMARY KEY AUTO_INCREMENT,
            conversation_id VARCHAR(64) NOT NULL UNIQUE,
            title VARCHAR(255) NOT NULL,
            mode VARCHAR(32) NOT NULL DEFAULT 'agent',
            message_count INT NOT NULL DEFAULT 0,
            last_message_preview VARCHAR(500) NOT NULL DEFAULT '',
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            INDEX idx_conversations_updated_at (updated_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """,
    "conversation_messages": """
        CREATE TABLE IF NOT EXISTS conversation_messages (
            id BIGINT PRIMARY KEY AUTO_INCREMENT,
            message_id VARCHAR(64) NOT NULL UNIQUE,
            conversation_id VARCHAR(64) NOT NULL,
            role VARCHAR(32) NOT NULL,
            content LONGTEXT NOT NULL,
            created_at DATETIME NOT NULL,
            INDEX idx_messages_conversation_id_created_at (conversation_id, created_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """,
    "conversation_documents": """
        CREATE TABLE IF NOT EXISTS conversation_documents (
            id BIGINT PRIMARY KEY AUTO_INCREMENT,
            document_id VARCHAR(64) NOT NULL UNIQUE,
            conversation_id VARCHAR(64) NOT NULL,
            original_name VARCHAR(255) NOT NULL,
            stored_name VARCHAR(255) NOT NULL,
            stored_path VARCHAR(500) NOT NULL,
            parsed_text_path VARCHAR(500) NOT NULL,
            file_type VARCHAR(16) NOT NULL,
            status VARCHAR(32) NOT NULL,
            char_count INT NOT NULL DEFAULT 0,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            INDEX idx_documents_conversation_id_created_at (conversation_id, created_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="初始化 llmrag 所需的 MySQL 数据库与表")
    parser.add_argument("--root-host", default=os.environ.get("MYSQL_ROOT_HOST", "127.0.0.1"), help="MySQL 管理连接主机")
    parser.add_argument("--root-port", type=int, default=int(os.environ.get("MYSQL_ROOT_PORT", "3306")), help="MySQL 管理连接端口")
    parser.add_argument("--root-user", default=os.environ.get("MYSQL_ROOT_USER", "root"), help="MySQL 管理员用户名")
    parser.add_argument("--root-password", default=os.environ.get("MYSQL_ROOT_PASSWORD"), help="MySQL 管理员密码")
    parser.add_argument("--db-name", default=os.environ.get("MYSQL_DATABASE", "llmrag"), help="要创建的数据库名")
    parser.add_argument("--db-charset", default=os.environ.get("MYSQL_CHARSET", "utf8mb4"), help="数据库字符集")
    parser.add_argument("--db-collation", default=os.environ.get("MYSQL_COLLATION", "utf8mb4_unicode_ci"), help="数据库排序规则")
    parser.add_argument("--app-host", default=os.environ.get("MYSQL_HOST", "127.0.0.1"), help="应用连接数据库使用的主机")
    parser.add_argument("--app-port", type=int, default=int(os.environ.get("MYSQL_PORT", "3306")), help="应用连接数据库使用的端口")
    parser.add_argument("--app-user", default=os.environ.get("MYSQL_USER", "root"), help="应用连接数据库使用的用户名")
    parser.add_argument("--app-password", default=os.environ.get("MYSQL_PASSWORD"), help="应用连接数据库使用的密码")
    parser.add_argument("--create-user", action="store_true", help="同时创建业务用户并授权")
    parser.add_argument("--skip-tables", action="store_true", help="只创建数据库和用户，不创建表")
    return parser.parse_args()


def normalize_password_args(args: argparse.Namespace) -> argparse.Namespace:
    if args.root_password is None:
        args.root_password = getpass.getpass("请输入 MySQL 管理员密码（直接回车表示空密码）: ")

    if args.create_user and args.app_password is None:
        args.app_password = getpass.getpass("请输入应用账号密码（直接回车表示空密码）: ")

    if args.app_password is None:
        args.app_password = args.root_password if args.app_user == args.root_user else ""

    return args


def create_database(args: argparse.Namespace) -> None:
    connection = pymysql.connect(
        host=args.root_host,
        port=args.root_port,
        user=args.root_user,
        password=args.root_password,
        charset="utf8mb4",
        autocommit=True,
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{args.db_name}` CHARACTER SET {args.db_charset} COLLATE {args.db_collation};"
            )
            if args.create_user:
                cursor.execute(
                    f"CREATE USER IF NOT EXISTS '{args.app_user}'@'%' IDENTIFIED BY %s;",
                    (args.app_password,),
                )
                cursor.execute(
                    f"GRANT ALL PRIVILEGES ON `{args.db_name}`.* TO '{args.app_user}'@'%';"
                )
                cursor.execute("FLUSH PRIVILEGES;")
    finally:
        connection.close()


def build_sqlalchemy_url(args: argparse.Namespace) -> str:
    return (
        f"mysql+pymysql://{args.app_user}:{args.app_password}"
        f"@{args.app_host}:{args.app_port}/{args.db_name}?charset={args.db_charset}"
    )


def create_tables(args: argparse.Namespace) -> None:
    engine = create_engine(build_sqlalchemy_url(args), pool_pre_ping=True, future=True)
    with engine.begin() as connection:
        connection.execute(text("SELECT 1"))
        for ddl in TABLE_DEFINITIONS.values():
            connection.execute(text(ddl))


def print_summary(args: argparse.Namespace) -> None:
    print("MySQL 初始化完成。")
    print("")
    print("建议在环境变量或配置中使用以下参数:")
    print(f"MYSQL_HOST={args.app_host}")
    print(f"MYSQL_PORT={args.app_port}")
    print(f"MYSQL_USER={args.app_user}")
    print(f"MYSQL_PASSWORD={args.app_password}")
    print(f"MYSQL_DATABASE={args.db_name}")
    print(f"MYSQL_CHARSET={args.db_charset}")
    print("")
    print("已覆盖的表:")
    for table_name in TABLE_DEFINITIONS:
        print(f"- {table_name}")


def main() -> int:
    args = normalize_password_args(parse_args())
    try:
        create_database(args)
        if not args.skip_tables:
            create_tables(args)
        print_summary(args)
        return 0
    except pymysql.err.OperationalError as exc:
        error_code = exc.args[0] if exc.args else None
        if error_code == 1045:
            print(
                "MySQL 初始化失败: 管理员账号认证失败。请确认 root 用户名、密码和主机是否正确。\n"
                "可直接这样重试:\n"
                "python setup_mysql.py --root-user root --root-host 127.0.0.1 --root-password 你的真实密码",
                file=sys.stderr,
            )
            return 1
        print(f"MySQL 初始化失败: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"MySQL 初始化失败: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())