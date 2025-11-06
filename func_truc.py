from conn import *                     # Hàm get_mongo_client() trả về MongoClient()
from pydantic import BaseModel
from typing import List
from datetime import datetime
from bson import ObjectId
from fastapi import APIRouter, HTTPException
import math
from typing import List, Optional
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

class VeUpdate(BaseModel):
    soGhe: Optional[List[str]] = None
    tongTien: Optional[int] = None
    phuongThuc: Optional[str] = None
    trangThai: Optional[str] = None
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
@router.get("/{user_id}")
def lay_ve_theo_nguoi_dung(user_id: str):
    ves = list(ve_collection.find({"nguoiDung_id": user_id}))
    # không tìm thấy vé nào trả mảng rỗng
    if not ves:
        return []
    return [ve_serializer(v) for v in ves]
@router.post("/dat-ve")
def dat_ve(ve_data: VeCreate):
    """API đặt vé xem phim"""
    # Tìm suất chiếu
    suat = suat_collection.find_one({"_id": ve_data.suatChieu_id})
    if not suat:
        raise HTTPException(status_code=404, detail="Không tìm thấy suất chiếu")

    #Kiểm tra ghế đã được đặt chưa
    ves = list(ve_collection.find({
        "suatChieu_id": ve_data.suatChieu_id,
        "trangThai": "Đã thanh toán"
    }))
    if not ves:
        ves = []
    for ve in ves:
        for ghe in ve.get("soGhe", []):
            if ghe in ve_data.soGhe:
                raise HTTPException(status_code=400, detail=f"Ghế {ghe} đã được đặt")

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
    suat_collection.update_one(
        {"_id": ve_data.suatChieu_id},
        {"$addToSet": {"gheDaDat": {"$each": ve_data.soGhe}}}
    )
    return {"message": "Đặt vé thành công!", "data": ve_serializer(created_ve)}



@router.get("/get-all")
def lay_tat_ca_ve():
    """Lấy toàn bộ danh sách vé (không phân trang)."""
    try:
        ves = list(ve_collection.find().sort("ngayThanhToan", -1))
        total = len(ves)
        return {
            "total": total,
            "data": [ve_serializer(v) for v in ves]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi lấy vé: {str(e)}")



@router.put("/sua-ve/{ve_id}")
def sua_ve(ve_id: str, ve_data: VeUpdate):
    """Sửa thông tin vé (soGhe, tongTien, phuongThuc, trangThai).
    - Nếu thay đổi soGhe hoặc trangThai ảnh hưởng tới số ghế đã đặt, cập nhật trường `soGhe` của suất chiếu tương ứng.
    - Kiểm tra xung đột ghế nếu vé ở trạng thái 'Đã thanh toán' hoặc sẽ chuyển sang 'Đã thanh toán'.
    """
    try:
        obj_id = ObjectId(ve_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"ID vé không hợp lệ: {str(e)}")

    ve = ve_collection.find_one({"_id": obj_id})
    if not ve:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy vé với ID: {ve_id}")

    updates = {}
    current_soGhe = ve.get("soGhe", [])
    current_status = ve.get("trangThai", "")

    # Nếu muốn đổi danh sách ghế
    if ve_data.soGhe is not None:
        new_soGhe = ve_data.soGhe
        # Nếu vé hiện hoặc sẽ ở trạng thái 'Đã thanh toán' thì phải kiểm tra xung đột và cập nhật soGhe của suất
        will_be_paid = (ve_data.trangThai == "Đã thanh toán") if ve_data.trangThai is not None else (current_status == "Đã thanh toán")

        # Kiểm tra xung đột ghế với các vé khác đã thanh toán (không tính vé hiện tại)
        if will_be_paid:
            other_paid = ve_collection.find({
                "suatChieu_id": ve["suatChieu_id"],
                "trangThai": "Đã thanh toán",
                "_id": {"$ne": ObjectId(ve_id)}
            })
            booked = set()
            for o in other_paid:
                for g in o.get("soGhe", []):
                    booked.add(g)
            conflict = set(new_soGhe) & booked
            if conflict:
                raise HTTPException(status_code=400, detail=f"Các ghế đã được đặt: {sorted(list(conflict))}")

        # Điều chỉnh số lượng ghế còn lại trong suat_collection
        diff = len(new_soGhe) - len(current_soGhe)
        if diff != 0:
            # Nếu tăng số ghế đặt (diff > 0), cần kiểm tra suất còn đủ ghế
            suat = suat_collection.find_one({"_id": ve["suatChieu_id"]})
            if not suat:
                raise HTTPException(status_code=404, detail="Không tìm thấy suất chiếu")

            available = suat.get("soGhe", 0)
            # Nếu vé đang/ sẽ là 'Đã thanh toán', phải thay đổi soGhe trong suat
            if will_be_paid:
                if diff > 0 and available < diff:
                    raise HTTPException(status_code=400, detail="Không đủ ghế trống để thêm")
                suat_collection.update_one(
                    {"_id": ve["suatChieu_id"]},
                    {"$inc": {"soGhe": -diff}}
                )
            else:
                # nếu vé không ở trạng thái đã thanh toán thì chỉ cập nhật internal list, không chạm soGhe suat
                pass

        updates["soGhe"] = new_soGhe

    # Nếu thay đổi trạng thái vé
    if ve_data.trangThai is not None:
        new_status = ve_data.trangThai
        if new_status != current_status:
            suat = suat_collection.find_one({"_id": ve["suatChieu_id"]})
            if not suat:
                raise HTTPException(status_code=404, detail="Không tìm thấy suất chiếu")

            # Chuyển sang 'Đã hủy' từ trạng thái khác -> trả lại ghế
            if new_status == "Đã hủy" and current_status != "Đã hủy":
                suat_collection.update_one(
                    {"_id": ve["suatChieu_id"]},
                    {"$inc": {"soGhe": len(updates.get("soGhe", current_soGhe))}}
                )
            # Chuyển sang 'Đã thanh toán' từ trạng thái khác -> kiểm tra và trừ ghế
            if new_status == "Đã thanh toán" and current_status != "Đã thanh toán":
                # kiểm tra xung đột ghế
                checking_soGhe = updates.get("soGhe", current_soGhe)
                other_paid = ve_collection.find({
                    "suatChieu_id": ve["suatChieu_id"],
                    "trangThai": "Đã thanh toán",
                    "_id": {"$ne": ObjectId(ve_id)}
                })
                booked = set()
                for o in other_paid:
                    for g in o.get("soGhe", []):
                        booked.add(g)
                conflict = set(checking_soGhe) & booked
                if conflict:
                    raise HTTPException(status_code=400, detail=f"Các ghế đã được đặt: {sorted(list(conflict))}")
                # kiểm tra số lượng ghế còn lại
                available = suat.get("soGhe", 0)
                need = len(checking_soGhe)
                # Nếu vé trước đó là 'Đã hủy' thì hiện suat đã có ghế trả về, cần trừ need
                if available < need:
                    raise HTTPException(status_code=400, detail="Không đủ ghế trống để thanh toán vé")
                suat_collection.update_one(
                    {"_id": ve["suatChieu_id"]},
                    {"$inc": {"soGhe": -need}}
                )

            updates["trangThai"] = new_status

    # Cập nhật các trường còn lại
    if ve_data.tongTien is not None:
        updates["tongTien"] = ve_data.tongTien
    if ve_data.phuongThuc is not None:
        updates["phuongThuc"] = ve_data.phuongThuc

    if not updates:
        return {"message": "Không có trường nào để cập nhật."}

    result = ve_collection.update_one({"_id": ObjectId(ve_id)}, {"$set": updates})
    if result.modified_count == 0:
        # có thể không có thay đổi thực sự
        updated = ve_collection.find_one({"_id": ObjectId(ve_id)})
        return {"message": "Không có thay đổi mới", "data": ve_serializer(updated)}

    updated = ve_collection.find_one({"_id": ObjectId(ve_id)})
    return {"message": "Cập nhật vé thành công", "data": ve_serializer(updated)}





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
