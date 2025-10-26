from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
import urllib.parse

# Thông tin kết nối
username = "Lethanhanh"
password = "Cnpm@Nhom7"
cluster = "ql-ocake.s83n8.mongodb.net"
app_name = "QL-OCake"

# Mã hóa username và password
encoded_username = urllib.parse.quote_plus(username)
encoded_password = urllib.parse.quote_plus(password)

# Tạo URI với username và password đã mã hóa
uri = f"mongodb+srv://{encoded_username}:{encoded_password}@{cluster}/?retryWrites=true&w=majority&appName={app_name}"

def get_mongo_client():
    """Tạo và trả về một MongoClient mới."""
    client = MongoClient(uri, server_api=ServerApi('1'))
    return client

if __name__ == "__main__":
    # Kiểm tra kết nối
    client = get_mongo_client()
    try:
        client.admin.command('ping')
        print("Pinged your deployment. You successfully connected to MongoDB!")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()