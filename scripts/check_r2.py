"""Quick test for R2 upload."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from storage.r2_client import get_r2_client, upload_file
from config import R2Config

print(f"🪣 R2 Config:")
print(f"   Account: {R2Config.ACCOUNT_ID}")
print(f"   Bucket: {R2Config.BUCKET}")
print(f"   Endpoint: {R2Config.ENDPOINT}")
print(f"   Public URL: {R2Config.PUBLIC_URL}")
print()

# Test connection
client = get_r2_client()
if client:
    print("✅ R2 client connected!")

    # Test upload a small text file
    test_file = "data/temp/test_upload.txt"
    with open(test_file, "w") as f:
        f.write("Hello from auto-content pipeline!")

    url = upload_file(test_file, "test/hello.txt")
    if url:
        print(f"✅ Upload success! URL: {url}")
    else:
        print("❌ Upload failed")
else:
    print("❌ R2 client failed to initialize")
