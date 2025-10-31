from fastapi import APIRouter, HTTPException, FastAPI
from pydantic import BaseModel
from typing import Optional, List
from bson import ObjectId
from conn import get_mongo_client
from datetime import datetime

router_rap = APIRouter(prefix="/api/rap", tags=["rap"])

# Pydantic models
class PhongChieu(BaseModel):
    ten_Phong: str
    loai_Phong: str = "2D"  # Thêm loai_Phong mặc định
    so_Luong_Ghe: int
    so_Cot: int
    so_Hang: int


class RapBase(BaseModel):
    _id: Optional[str] = None
    ten_rap: str
    dia_chi: str
    so_dien_thoai: str
    so_phong: Optional[int] = 0
    mo_ta: Optional[str] = ""
    danh_sach_phong_chieu: List[PhongChieu] = []


class RapResponse(RapBase):
    ma_rap: str

class RapCreate(RapBase):
    pass

class RapUpdate(BaseModel):
    ten_rap: Optional[str] = None
    dia_chi: Optional[str] = None
    so_dien_thoai: Optional[str] = None
    so_phong: Optional[int] = None
    mo_ta: Optional[str] = None
    danh_sach_phong_chieu: Optional[List[PhongChieu]] = None


class PhongChieuCreate(BaseModel):
    ten_Phong: str
    loai_Phong: str = "2D"  # Thêm loai_Phong mặc định
    so_Luong_Ghe: int
    so_Cot: int
    so_Hang: int

class Anh:
    def __init__(self):
        self.client = get_mongo_client()
        try:
            self.db = self.client["QL_DatVeTrucTuyen"]
            self.collection = self.db["Rap"]
            self.suat_chieu_collection = self.db["SuatChieu"]
            print("Kết nối thành công đến MongoDB!")
        except Exception as e:
            print(f"Lỗi kết nối: {e}")
            raise HTTPException(status_code=500, detail=f"Lỗi kết nối cơ sở dữ liệu: {str(e)}")

    def lay_danh_sach_rap(self):
        try:
            danh_sach_rap = list(self.collection.find())
            ket_qua = []
            for rap in danh_sach_rap:
                rap_data = {
                    "ma_rap": str(rap["_id"]),
                    "ten_rap": rap.get("tenRap", ""),
                    "dia_chi": rap.get("diaChi", ""),
                    "so_dien_thoai": rap.get("soDienThoai", ""),
                    "so_phong": rap.get("soPhong", 0),
                    "mo_ta": rap.get("moTa", ""),
                    "danh_sach_phong_chieu": [
                        {
                            "ten_Phong": phong.get("ten_Phong", ""),
                            "loai_Phong": phong.get("loai_Phong", "2D"),
                            "so_Luong_Ghe": phong.get("so_Luong_Ghe", 0),
                            "so_Cot": phong.get("so_Cot", 0),
                            "so_Hang": phong.get("so_Hang", 0),
                        } for phong in rap.get("phongChieu", [])
                    ]
                }
                ket_qua.append(rap_data)
            return {"data": ket_qua, "status": 200}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Lỗi khi lấy danh sách rạp: {str(e)}")

    def lay_rap_theo_id(self, ma_rap: str):
        try:
            rap = self.collection.find_one({"_id": ma_rap})
            if not rap:
                raise HTTPException(status_code=404, detail="Rạp không tồn tại")
            
            ket_qua = {
                "ma_rap": str(rap["_id"]),
                "ten_rap": rap.get("tenRap", ""),
                "dia_chi": rap.get("diaChi", ""),
                "so_dien_thoai": rap.get("soDienThoai", ""),
                "so_phong": rap.get("soPhong", 0),
                "mo_ta": rap.get("moTa", ""),
                "danh_sach_phong_chieu": [
                    {
                        "ten_Phong": phong.get("ten_Phong", ""),
                        "loai_Phong": phong.get("loai_Phong", "2D"),
                        "so_Luong_Ghe": phong.get("so_Luong_Ghe", 0),
                        "so_Cot": phong.get("so_Cot", 0),
                        "so_Hang": phong.get("so_Hang", 0),
                    } for phong in rap.get("phongChieu", [])
                ]
            }
            return {"data": ket_qua, "status": 200}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Lỗi khi lấy thông tin rạp: {str(e)}")

    def tao_rap(self, rap_data: RapCreate):
        try:
            if not all([rap_data.ten_rap, rap_data.dia_chi, rap_data.so_dien_thoai]):
                raise HTTPException(status_code=400, detail="Thiếu thông tin bắt buộc")

            existing_rap = self.collection.find_one({"tenRap": rap_data.ten_rap, "diaChi": rap_data.dia_chi})
            if existing_rap:
                raise HTTPException(status_code=409, detail="Rạp với tên và địa chỉ này đã tồn tại")

            danh_sach_rap = list(self.collection.find({}, {"_id": 1}).sort("_id", -1).limit(1))
            if danh_sach_rap:
                ma_cuoi = danh_sach_rap[0]["_id"]
                if ma_cuoi.startswith("Rap"):
                    try:
                        so_cuoi = int(ma_cuoi[3:])
                        ma_moi = f"Rap{so_cuoi + 1}"
                    except:
                        ma_moi = "Rap1"
                else:
                    ma_moi = "Rap1"
            else:
                ma_moi = "Rap1"

            rap_doc = {
                "_id": ma_moi,
                "tenRap": rap_data.ten_rap,
                "diaChi": rap_data.dia_chi,
                "soDienThoai": rap_data.so_dien_thoai,
                "soPhong": rap_data.so_phong,
                "moTa": rap_data.mo_ta,
                "phongChieu": [
                    {
                        "ten_Phong": phong.ten_Phong,
                        "loai_Phong": phong.loai_Phong,
                        "so_Luong_Ghe": phong.so_Luong_Ghe,
                        "so_Cot": phong.so_Cot,
                        "so_Hang": phong.so_Hang,
                    } for phong in rap_data.danh_sach_phong_chieu
                ],
                "created_at": datetime.now(),
                "updated_at": datetime.now()
            }

            result = self.collection.insert_one(rap_doc)
            return {
                "message": "Tạo rạp thành công",
                "ma_rap": ma_moi,
                "status": 200,
                "data": {
                    "ma_rap": ma_moi,
                    "ten_rap": rap_data.ten_rap,
                    "dia_chi": rap_data.dia_chi,
                    "so_dien_thoai": rap_data.so_dien_thoai,
                    "so_phong": rap_data.so_phong,
                    "mo_ta": rap_data.mo_ta,
                    "danh_sach_phong_chieu": [
                        {
                            "ten_Phong": phong.ten_Phong,
                            "loai_Phong": phong.loai_Phong,
                            "so_Luong_Ghe": phong.so_Luong_Ghe,
                            "so_Cot": phong.so_Cot,
                            "so_Hang": phong.so_Hang,
                        } for phong in rap_data.danh_sach_phong_chieu
                    ]
                }
            }
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Lỗi khi tạo rạp: {str(e)}")

    def cap_nhat_rap(self, ma_rap: str, rap_data: RapUpdate):
        try:
            existing_rap = self.collection.find_one({"_id": ma_rap})
            if not existing_rap:
                raise HTTPException(status_code=404, detail="Rạp không tồn tại")

            update_data = {"updated_at": datetime.now()}
            if rap_data.ten_rap is not None:
                update_data["tenRap"] = rap_data.ten_rap
            if rap_data.dia_chi is not None:
                update_data["diaChi"] = rap_data.dia_chi
            if rap_data.so_dien_thoai is not None:
                update_data["soDienThoai"] = rap_data.so_dien_thoai
            if rap_data.so_phong is not None:
                update_data["soPhong"] = rap_data.so_phong
            if rap_data.mo_ta is not None:
                update_data["moTa"] = rap_data.mo_ta
            if rap_data.danh_sach_phong_chieu is not None:
                update_data["phongChieu"] = [
                    {
                        "ten_Phong": phong.ten_Phong,
                        "loai_Phong": phong.loai_Phong,
                        "so_Luong_Ghe": phong.so_Luong_Ghe,
                        "so_Cot": phong.so_Cot,
                        "so_Hang": phong.so_Hang,
                    } for phong in rap_data.danh_sach_phong_chieu
                ]

            result = self.collection.update_one(
                {"_id": ma_rap},
                {"$set": update_data}
            )

            if result.modified_count > 0:
                return {"message": "Cập nhật rạp thành công", "status": 200}
            else:
                return {"message": "Không có thay đổi nào được thực hiện", "status": 200}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Lỗi khi cập nhật rạp: {str(e)}")

    def xoa_rap(self, ma_rap: str):
        try:
            existing_rap = self.collection.find_one({"_id": ma_rap})
            if not existing_rap:
                raise HTTPException(status_code=404, detail="Rạp không tồn tại")

            suat_chieu = self.suat_chieu_collection.find_one({"rap_id": ma_rap})
            if suat_chieu:
                raise HTTPException(
                    status_code=409,
                    detail="Không thể xóa rạp vì vẫn còn suất chiếu liên quan"
                )

            result = self.collection.delete_one({"_id": ma_rap})
            if result.deleted_count > 0:
                return {"message": "Xóa rạp thành công", "status": 200}
            else:
                raise HTTPException(status_code=500, detail="Không thể xóa rạp")
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Lỗi khi xóa rạp: {str(e)}")

    def them_phong_chieu(self, ma_rap: str, phong_data: PhongChieuCreate):
        try:
            if not all([phong_data.ten_Phong, phong_data.so_Luong_Ghe, phong_data.so_Cot, phong_data.so_Hang]):
                raise HTTPException(status_code=400, detail="Thiếu thông tin phòng chiếu")

            existing_rap = self.collection.find_one({"_id": ma_rap})
            if not existing_rap:
                raise HTTPException(status_code=404, detail="Rạp không tồn tại")

            danh_sach_phong_chieu = existing_rap.get("phongChieu", [])
            if any(phong.get("ten_Phong") == phong_data.ten_Phong for phong in danh_sach_phong_chieu):
                raise HTTPException(status_code=409, detail=f"Phòng chiếu {phong_data.ten_Phong} đã tồn tại")

            phong_moi = {
                "ten_Phong": phong_data.ten_Phong,
                "loai_Phong": phong_data.loai_Phong,
                "so_Luong_Ghe": phong_data.so_Luong_Ghe,
                "so_Cot": phong_data.so_Cot,
                "so_Hang": phong_data.so_Hang
            }

            result = self.collection.update_one(
                {"_id": ma_rap},
                {
                    "$push": {
                        "phongChieu": phong_moi
                    },
                    "$set": {
                        "soPhong": len(danh_sach_phong_chieu) + 1,
                        "updated_at": datetime.now()
                    }
                }
            )

            if result.modified_count > 0:
                return {
                    "message": "Thêm phòng chiếu thành công",
                    "status": 200,
                    "data": {
                        "ten_Phong": phong_data.ten_Phong,
                        "loai_Phong": phong_data.loai_Phong,
                        "so_Luong_Ghe": phong_data.so_Luong_Ghe,
                        "so_Cot": phong_data.so_Cot,
                        "so_Hang": phong_data.so_Hang
                    }
                }
            else:
                return {"message": "Không có thay đổi nào được thực hiện", "status": 200}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Lỗi khi thêm phòng chiếu: {str(e)}")

    def xoa_phong_chieu(self, ma_rap: str, ten_Phong: str):
        try:
            existing_rap = self.collection.find_one({"_id": ma_rap})
            if not existing_rap:
                raise HTTPException(status_code=404, detail="Rạp không tồn tại")

            danh_sach_phong_chieu = existing_rap.get("phongChieu", [])
            if not any(phong.get("ten_Phong") == ten_Phong for phong in danh_sach_phong_chieu):
                raise HTTPException(status_code=409, detail=f"Phòng chiếu {ten_Phong} không tồn tại")

            result = self.collection.update_one(
                {"_id": ma_rap},
                {
                    "$pull": {
                        "phongChieu": {"ten_Phong": ten_Phong}
                    },
                    "$set": {
                        "soPhong": len(danh_sach_phong_chieu) - 1,
                        "updated_at": datetime.now()
                    }
                }
            )

            if result.modified_count > 0:
                return {"message": "Xóa phòng chiếu thành công", "status": 200}
            else:
                return {"message": "Không có thay đổi nào được thực hiện", "status": 200}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Lỗi khi xóa phòng chiếu: {str(e)}")

    def __del__(self):
        if hasattr(self, 'client'):
            self.client.close()

# FastAPI Routes
@router_rap.get("/")
async def lay_danh_sach_rap():
    quan_ly_rap = Anh()
    try:
        return quan_ly_rap.lay_danh_sach_rap()
    finally:
        quan_ly_rap.__del__()

@router_rap.get("/{ma_rap}")
async def lay_rap_theo_id(ma_rap: str):
    quan_ly_rap = Anh()
    try:
        return quan_ly_rap.lay_rap_theo_id(ma_rap)
    finally:
        quan_ly_rap.__del__()

@router_rap.post("/")
async def tao_rap(rap: RapCreate):
    quan_ly_rap = Anh()
    try:
        return quan_ly_rap.tao_rap(rap)
    finally:
        quan_ly_rap.__del__()

@router_rap.put("/{ma_rap}")
async def cap_nhat_rap(ma_rap: str, rap: RapUpdate):
    quan_ly_rap = Anh()
    try:
        return quan_ly_rap.cap_nhat_rap(ma_rap, rap)
    finally:
        quan_ly_rap.__del__()

@router_rap.delete("/{ma_rap}")
async def xoa_rap(ma_rap: str):
    quan_ly_rap = Anh()
    try:
        return quan_ly_rap.xoa_rap(ma_rap)
    finally:
        quan_ly_rap.__del__()

@router_rap.post("/{ma_rap}/phong-chieu")
async def them_phong_chieu(ma_rap: str, phong: PhongChieuCreate):
    quan_ly_rap = Anh()
    try:
        return quan_ly_rap.them_phong_chieu(ma_rap, phong)
    finally:
        quan_ly_rap.__del__()

@router_rap.delete("/{ma_rap}/phong-chieu/{ten_Phong}")
async def xoa_phong_chieu(ma_rap: str, ten_Phong: str):
    quan_ly_rap = Anh()
    try:
        return quan_ly_rap.xoa_phong_chieu(ma_rap, ten_Phong)
    finally:
        quan_ly_rap.__del__()

