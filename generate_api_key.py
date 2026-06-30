#!/usr/bin/env python3
"""
Generate API keys for RAG API

Usage:
    python generate_api_key.py --username john --email john@example.com
    python generate_api_key.py  # Interactive mode
"""
#source venv/bin/activate

import argparse
import sys
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent))

from app.db.database import init_db, SessionLocal
from app.db.crud import UserCRUD, APIKeyCRUD
from app.core.security import generate_api_key


def interactive_mode():
    """Interactive mode for creating user and API key."""
    print("\n" + "=" * 60)
    print("RAG API - Generate API Key")
    print("=" * 60 + "\n")

    username = input("Enter username: ").strip()
    if not username:
        print("❌ Username cannot be empty")
        return

    email = input("Enter email: ").strip()
    if not email or "@" not in email:
        print("❌ Invalid email")
        return

    create_api_key(username, email)


def create_api_key(username: str, email: str):
    """Create user and generate API key."""
    try:
        # Initialize database
        init_db()
        db = SessionLocal()

        # Check if user exists
        existing_user = UserCRUD.get_user_by_username(db, username)
        if existing_user:
            print(f"⚠️  User '{username}' already exists")
            user = existing_user
        else:
            # Create new user
            print(f"Creating user '{username}'...", end=" ")
            user = UserCRUD.create_user(db, username, email)
            print("✓")

        # Generate API key
        print("Generating API key...", end=" ")
        api_key = APIKeyCRUD.create_api_key(db, user.id)
        print("✓\n")

        # Display results
        print("=" * 60)
        print("USER CREATED / RETRIEVED")
        print("=" * 60)
        print(f"User ID:  {user.id}")
        print(f"Username: {user.username}")
        print(f"Email:    {user.email}")
        print(f"Active:   {user.active}")
        print()
        print("=" * 60)
        print("API KEY GENERATED")
        print("=" * 60)
        print(f"API Key: {api_key}\n")
        print("Usage in requests:")
        print(f'Authorization: Bearer {api_key}')
        print()
        print("Example curl:")
        print(f'curl -H "Authorization: Bearer {api_key}" \\')
        print('  http://localhost:8000/api/v1/collections')
        print()
        print("=" * 60)

        db.close()

    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Generate API keys for RAG API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python generate_api_key.py --username john --email john@example.com
  python generate_api_key.py -u admin -e admin@example.com
  python generate_api_key.py  # Interactive mode
        """
    )

    parser.add_argument(
        "-u", "--username",
        help="Username for the new user",
        type=str
    )
    parser.add_argument(
        "-e", "--email",
        help="Email for the new user",
        type=str
    )

    args = parser.parse_args()

    # If both username and email provided, use them
    if args.username and args.email:
        create_api_key(args.username, args.email)
    else:
        # Interactive mode
        interactive_mode()


if __name__ == "__main__":
    main()
