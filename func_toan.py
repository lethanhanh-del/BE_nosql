from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from datetime import datetime
from bson import ObjectId
from conn import get_mongo_client
from pydantic import BaseModel, EmailStr, Field
from typing import Optional
import hashlib, os, re

# ====== KẾT NỐI MONGO ======
client = get_mongo_client()
db = client["QL_DatVeTrucTuyen"]
nguoi_dung_col = db["NguoiDung"]

# ====== HỖ TRỢ CHUYỂN ObjectId ======
def convert_objectid(data):
    if isinstance(data, list):
        for d in data:
            if "_id" in d:
                d["_id"] = str(d["_id"])
    elif isinstance(data, dict) and "_id" in data:
        data["_id"] = str(data["_id"])
    return data

# ====== HASH PASSWORD ======
def hash_password(password: str) -> str:
    salt = os.urandom(16)  # 16 bytes random salt
    hashed = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100_000)
    return salt.hex() + ":" + hashed.hex()

def verify_password(password: str, hashed: str) -> bool:
    salt_hex, hash_hex = hashed.split(":")
    salt = bytes.fromhex(salt_hex)
    new_hash = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100_000)
    return new_hash.hex() == hash_hex

# ====== SCHEMA ======
class UserRegister(BaseModel):
    tenDangNhap: str = Field(..., min_length=3, max_length=20)
    matKhau: str = Field(..., min_length=6)
    hoTen: Optional[str] = ""
    email: Optional[EmailStr] = None
    soDienThoai: Optional[str] = None
    vaiTro: Optional[str] = "user"

class UserLogin(BaseModel):
    tenDangNhap: str
    matKhau: str

class UserUpdate(BaseModel):
    hoTen: Optional[str] = None
    email: Optional[EmailStr] = None
    soDienThoai: Optional[str] = None
    vaiTro: Optional[str] = None
    matKhau: Optional[str] = None

# ====== CLASS TOAN ======
class Toan:
    def __init__(self):
        self.router = APIRouter(prefix="/api/NguoiDung", tags=["NguoiDung"])

        # ---- Đăng ký ----
        @self.router.post("/register")
        def register(user: UserRegister):
            if nguoi_dung_col.find_one({"tenDangNhap": user.tenDangNhap}):
                raise HTTPException(status_code=400, detail="Tên đăng nhập đã tồn tại")

            # Kiểm tra mật khẩu hợp lệ
            if not re.search(r"[A-Z]", user.matKhau) or not re.search(r"[a-z]", user.matKhau) or not re.search(r"[0-9]", user.matKhau):
                raise HTTPException(status_code=400, detail="Mật khẩu phải có ít nhất 1 chữ hoa, 1 chữ thường và 1 số")

            # Kiểm tra số điện thoại
            if user.soDienThoai and not re.match(r"^\d{10,11}$", user.soDienThoai):
                raise HTTPException(status_code=400, detail="Số điện thoại phải từ 10-11 chữ số")

            hashed_pw = hash_password(user.matKhau)
            new_user = {
                "tenDangNhap": user.tenDangNhap,
                "matKhau": hashed_pw,
                "hoTen": user.hoTen,
                "email": user.email,
                "soDienThoai": user.soDienThoai,
                "vaiTro": user.vaiTro,
                "ngayDangKy": datetime.now()
            }
            nguoi_dung_col.insert_one(new_user)
            convert_objectid(new_user)
            return {"message": "Đăng ký thành công", "user": new_user}

        # ---- Đăng nhập ----
        @self.router.post("/login")
        def login(user: UserLogin):
            db_user = nguoi_dung_col.find_one({"tenDangNhap": user.tenDangNhap})
            if not db_user or not verify_password(user.matKhau, db_user["matKhau"]):
                raise HTTPException(status_code=401, detail="Sai tên đăng nhập hoặc mật khẩu")

            convert_objectid(db_user)
            return {
                "message": "Đăng nhập thành công",
                "user": {
                    "tenDangNhap": db_user["tenDangNhap"],
                    "email": db_user.get("email", ""),
                    "vaiTro": db_user.get("vaiTro", "user")
                }
            }

        # ---- Xem tất cả người dùng ----
        @self.router.get("/")
        def get_all_users():
            users = list(nguoi_dung_col.find({}, {"matKhau": 0}))
            convert_objectid(users)
            return JSONResponse(content=jsonable_encoder(users))

        # ---- Xem chi tiết người dùng ----
        @self.router.get("/{tenDangNhap}")
        def get_user(tenDangNhap: str):
            user = nguoi_dung_col.find_one({"tenDangNhap": tenDangNhap}, {"matKhau": 0})
            if not user:
                raise HTTPException(status_code=404, detail="Người dùng không tồn tại")
            convert_objectid(user)
            return user

        # ---- Cập nhật người dùng ----
        @self.router.put("/{tenDangNhap}")
        def update_user(tenDangNhap: str, update: UserUpdate):
            data = {k: v for k, v in update.dict(exclude_unset=True).items() if v is not None}

            # Validate mật khẩu
            if "matKhau" in data:
                pw = data["matKhau"]
                if not isinstance(pw, str):
                    raise HTTPException(status_code=400, detail="Mật khẩu không hợp lệ")
                if not re.search(r"[A-Z]", pw) or not re.search(r"[a-z]", pw) or not re.search(r"[0-9]", pw):
                    raise HTTPException(status_code=400, detail="Mật khẩu phải có ít nhất 1 chữ hoa, 1 chữ thường và 1 số")
                data["matKhau"] = hash_password(pw)

            # Validate số điện thoại
            if "soDienThoai" in data and data["soDienThoai"]:
                if not re.match(r"^\d{10,11}$", data["soDienThoai"]):
                    raise HTTPException(status_code=400, detail="Số điện thoại phải từ 10-11 chữ số")

            result = nguoi_dung_col.update_one({"tenDangNhap": tenDangNhap}, {"$set": data})
            if result.matched_count == 0:
                raise HTTPException(status_code=404, detail="Người dùng không tồn tại")

            user = nguoi_dung_col.find_one({"tenDangNhap": tenDangNhap}, {"matKhau": 0})
            convert_objectid(user)
            return {"message": "Cập nhật thành công", "user": user}

        # ---- Xóa người dùng ----
        @self.router.delete("/{tenDangNhap}")
        def delete_user(tenDangNhap: str):
            result = nguoi_dung_col.delete_one({"tenDangNhap": tenDangNhap})
            if result.deleted_count == 0:
                raise HTTPException(status_code=404, detail="Người dùng không tồn tại")
            return {"message": "Xóa người dùng thành công"}
