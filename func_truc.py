from conn import *                     # Hàm get_mongo_client() trả về MongoClient()
from pydantic import BaseModel
from typing import List
from datetime import datetime
from bson import ObjectId
from fastapi import APIRouter, HTTPException

# ==========================
# 🔗 Khởi tạo router & MongoDB
# ==========================
router = APIRouter(prefix="/api/ve", tags=["Vé xem phim"])
client = get_mongo_client()
db = client["QL_DatVeTrucTuyen"]
ve_collection = db["Ve"]
suat_collection = db["SuatChieu"]

# ==========================
# 📦 Schema / Model
# ==========================
class VeCreate(BaseModel):
    suatChieu_id: str
    nguoiDung_id: str
    soGhe: List[str]
    tongTien: int
    phuongThuc: str

# ==========================
# 🧰 Serializer (chuyển từ MongoDB object sang dict JSON)
# ==========================
def ve_serializer(ve) -> dict:
    return {
        "id": str(ve["_id"]),
        "suatChieu_id": ve["suatChieu_id"],
        "nguoiDung_id": ve["nguoiDung_id"],
        "soGhe": ve["soGhe"],
        "tongTien": ve["tongTien"],
        "trangThai": ve["trangThai"],
        "ngayThanhToan": ve["ngayThanhToan"],
        "phuongThuc": ve["phuongThuc"],
    }

# ==========================
# 🚀 API Routes
# ==========================

@router.post("/dat-ve")
def dat_ve(ve_data: VeCreate):
    """API đặt vé xem phim"""
    # Tìm suất chiếu
    suat = suat_collection.find_one({"_id": ve_data.suatChieu_id})
    if not suat:
        raise HTTPException(status_code=404, detail="Không tìm thấy suất chiếu")
    
    # Kiểm tra còn đủ ghế không
    if suat.get("soGhe", 0) < len(ve_data.soGhe):
        raise HTTPException(status_code=400, detail="Không đủ ghế trống")

    #Kiểm tra ghế đã được đặt chưa
    ves = list(ve_collection.find({
        "suatChieu_id": ve_data.suatChieu_id,
        "trangThai": "Đã thanh toán"
    }))
    print(ves)
    if not ves:
        ves = []
    for ve in ves:
        for ghe in ve.get("soGhe", []):
            if ghe in ve_data.soGhe:
                raise HTTPException(status_code=400, detail=f"Ghế {ghe} đã được đặt")

    # Cập nhật số ghế còn lại
    suat_collection.update_one(
        {"_id": ve_data.suatChieu_id},
        {"$inc": {"soGhe": -len(ve_data.soGhe)}}  # Giảm số ghế
    )

    # Tạo vé
    new_ve = {
        "suatChieu_id": ve_data.suatChieu_id,
        "nguoiDung_id": ve_data.nguoiDung_id,
        "soGhe": ve_data.soGhe,
        "tongTien": ve_data.tongTien,
        "trangThai": "Đã thanh toán",
        "ngayThanhToan": datetime.utcnow(),
        "phuongThuc": ve_data.phuongThuc,
    }

    result = ve_collection.insert_one(new_ve)
    created_ve = ve_collection.find_one({"_id": result.inserted_id})
    return {"message": "Đặt vé thành công!", "data": ve_serializer(created_ve)}



@router.get("/{user_id}")
def lay_ve_theo_nguoi_dung(user_id: str):
    ves = list(ve_collection.find({"nguoiDung_id": user_id}))
    # không tìm thấy vé nào trả mảng rỗng
    if not ves:
        raise HTTPException(status_code=404, detail="Không tìm thấy vé nào cho người dùng này")
    return [ve_serializer(v) for v in ves]


@router.put("/huy-ve/{ve_id}")
def huy_ve(ve_id: str):
    ve = ve_collection.find_one({"_id": ObjectId(ve_id)})
    if not ve:
        raise HTTPException(status_code=404, detail="Không tìm thấy vé")

    if ve.get("trangThai") == "Đã hủy":
        return {"message": "Vé này đã được hủy trước đó."}
    
    suat = suat_collection.find_one({"_id": ve["suatChieu_id"]})
    if not suat:
        raise HTTPException(status_code=404, detail="Không tìm thấy suất chiếu")

    so_ghe_hoan = len(ve.get("soGhe", []))
    suat_collection.update_one(
        {"_id": ve["suatChieu_id"]},
        {
            "$inc": {"soGhe": so_ghe_hoan},  
        }
    )

    result = ve_collection.update_one(
        {"_id": ObjectId(ve_id)},
        {"$set": {"trangThai": "Đã hủy"}}
    )

    if result.modified_count == 0:
        raise HTTPException(status_code=400, detail="Không thể cập nhật trạng thái vé")

    return {"message": "Hủy vé thành công!"}
