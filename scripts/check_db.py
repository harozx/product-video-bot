"""Quick test script for database and module imports."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
from database import init_database, execute_insert, execute_query


async def test():
    await init_database()

    # Test product insert
    pid = await execute_insert(
        "INSERT INTO products (name, price) VALUES (?, ?)",
        ("Test Product", "199K"),
    )
    print(f"✅ Product #{pid} created")

    # Test query
    products = await execute_query("SELECT * FROM products WHERE id = ?", (pid,))
    print(f"✅ Query OK: {products[0]['name']}")

    # Test account insert
    aid = await execute_insert(
        "INSERT INTO accounts (platform, account_name, username) VALUES (?, ?, ?)",
        ("tiktok", "TestShop", "testshop01"),
    )
    print(f"✅ Account #{aid} created")

    # Test schedule
    vid = await execute_insert(
        "INSERT INTO videos (product_id, template, status) VALUES (?, ?, ?)",
        (pid, "slideshow", "ready"),
    )
    print(f"✅ Video #{vid} created")

    # Verify counts
    products = await execute_query("SELECT COUNT(*) as c FROM products")
    accounts = await execute_query("SELECT COUNT(*) as c FROM accounts")
    videos = await execute_query("SELECT COUNT(*) as c FROM videos")

    print(f"\n📊 Database: {products[0]['c']} products, {accounts[0]['c']} accounts, {videos[0]['c']} videos")
    print("\n🎉 All tests passed!")


asyncio.run(test())
