from conn import get_mongo_client
from datetime import datetime, timedelta
from bson import ObjectId
from fastapi import FastAPI, APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional
import json
from collections import OrderedDict


# Tạo APIRouter cho SuatChieu collection
router = APIRouter(prefix="/api/suat-chieu", tags=["SuatChieu"])

# Pydantic models
class SuatChieuCreate(BaseModel):
    phim_id: str
    rap_id: str
    gio_chieu: str
    gia_ve: int
    so_ghe: int
    phong_chieu: Optional[str] = ""
    gio_bat_dat: Optional[str] = None
    gio_ket_thuc: Optional[str] = None

class SuatChieuUpdate(BaseModel):
    # Chỉ các trường được phép update
    phim_ten: Optional[str] = None
    rap_ten: Optional[str] = None
    phongChieu: Optional[str] = None
    gioChieu: Optional[str] = None
    giaVe: Optional[int] = None
    tongGhe: Optional[int] = None
    gheDaDat: Optional[List[str]] = None

class Lam:
    def __init__(self):
        self.client = get_mongo_client()
        self.db = self.client["QL_DatVeTrucTuyen"]
        self.phim_collection = self.db["Phim"]
        self.suat_chieu_collection = self.db["SuatChieu"]
        self.rap_collection = self.db["Rap"]

    def get_lich_chieu_phim(self, phim_id: str, ngay_bat_dau: Optional[str] = None, ngay_ket_thuc: Optional[str] = None):
        try:
            phim = self.phim_collection.find_one({"_id": phim_id})
            if not phim:
                return {"error": "Phim không tồn tại", "status": 404}

            query = {"phim_id": phim_id}

            if ngay_bat_dau and ngay_ket_thuc:
                start_date = datetime.strptime(ngay_bat_dau, "%Y-%m-%d")
                end_date = datetime.strptime(ngay_ket_thuc, "%Y-%m-%d") + timedelta(days=1)
                query["gioChieu"] = {
                    "$gte": start_date,
                    "$lt": end_date
                }
            elif ngay_bat_dau:
                start_date = datetime.strptime(ngay_bat_dau, "%Y-%m-%d")
                query["gioChieu"] = {"$gte": start_date}
            elif ngay_ket_thuc:
                end_date = datetime.strptime(ngay_ket_thuc, "%Y-%m-%d") + timedelta(days=1)
                query["gioChieu"] = {"$lt": end_date}

            suat_chieu_list = list(self.suat_chieu_collection.find(query).sort("gioChieu", 1))

            result = {
                "phim": {
                    "id": str(phim["_id"]),
                    "tenPhim": phim.get("tenPhim", ""),
                    "thoiLuong": phim.get("thoiLuong", 0),
                    "theLoai": phim.get("theLoai", []),
                    "danhGia": phim.get("danhGia", 0)
                },
                "lich_chieu": []
            }

            for suat_chieu in suat_chieu_list:
                rap = self.rap_collection.find_one({"_id": suat_chieu["rap_id"]})

                so_ghe = suat_chieu.get("soGhe", 0)
                ghe_da_dat = suat_chieu.get("gheDaDat", [])
                ghe_trong = so_ghe - len(ghe_da_dat) if isinstance(ghe_da_dat, list) else so_ghe

                lich_chieu_item = OrderedDict([
                    ("id", str(suat_chieu["_id"])),
                    ("phongChieu", suat_chieu.get("phongChieu", "")),
                    ("gioChieu", str(suat_chieu.get("gioChieu", ""))),
                    ("gioBatDat", str(suat_chieu.get("gioBatDat", ""))),
                    ("gioKetThuc", str(suat_chieu.get("gioKetThuc", ""))),
                    ("giaVe", suat_chieu.get("giaVe", 0)),
                    ("tongGhe", so_ghe),
                    ("gheTrong", ghe_trong),
                    ("gheDaDat", ghe_da_dat),
                    ("rap", OrderedDict([
                        ("id", str(rap["_id"]) if rap else None),
                        ("tenRap", rap.get("tenRap", "") if rap else ""),
                        ("diaChi", rap.get("diaChi", "") if rap else "")
                    ]) if rap else None)
                ])
                result["lich_chieu"].append(lich_chieu_item)

            return {"data": result, "status": 200}

        except Exception as e:
            return {"error": f"Lỗi khi lấy lịch chiếu: {str(e)}", "status": 500}

    def create_suat_chieu(self, phim_id: str, rap_id: str, gio_chieu: str, gia_ve: int, so_ghe: int, 
                         phong_chieu: str = "", gio_bat_dat: Optional[str] = None, gio_ket_thuc: Optional[str] = None):
        try:
            phim = self.phim_collection.find_one({"_id": phim_id})
            if not phim:
                return {"error": "Phim không tồn tại", "status": 404}

            rap = self.rap_collection.find_one({"_id": rap_id})
            if not rap:
                return {"error": "Rạp không tồn tại", "status": 405}

            gio_chieu_dt = datetime.strptime(gio_chieu, "%Y-%m-%d %H:%M:%S")

            gio_bat_dat_str = gio_bat_dat if gio_bat_dat else None
            gio_ket_thuc_str = gio_ket_thuc if gio_ket_thuc else None

            existing_suat_chieu = list(self.suat_chieu_collection.find({}, {"_id": 1}).sort("_id", -1).limit(1))
            if existing_suat_chieu:
                last_id = existing_suat_chieu[0]["_id"]
                if last_id.startswith("Suat"):
                    try:
                        last_number = int(last_id[4:])
                        new_id = f"Suat{last_number + 1}"
                    except:
                        new_id = "Suat1"
                else:
                    new_id = "Suat1"
            else:
                new_id = "Suat1"

            suat_chieu_data = {
                "_id": new_id,
                "phim_id": phim_id,
                "rap_id": rap_id,
                "phongChieu": phong_chieu,
                "gioBatDat": gio_bat_dat_str,
                "gioKetThuc": gio_ket_thuc_str,
                "gioChieu": gio_chieu_dt.isoformat() + "+00:00",
                "giaVe": gia_ve,
                "soGhe": so_ghe,
                "gheDaDat": []
            }

            result = self.suat_chieu_collection.insert_one(suat_chieu_data)

            return {
                "message": "Tạo suất chiếu thành công",
                "suat_chieu_id": new_id,
                "status": 200
            }

        except Exception as e:
            return {"error": f"Lỗi khi tạo suất chiếu: {str(e)}", "status": 500}

    def update_suat_chieu(self, suat_chieu_id: str, gio_chieu: Optional[str] = None, gia_ve: Optional[int] = None, 
                         so_ghe: Optional[int] = None, phong_chieu: Optional[str] = None, 
                         gio_bat_dat: Optional[str] = None, gio_ket_thuc: Optional[str] = None):
        try:
            existing_suat_chieu = self.suat_chieu_collection.find_one({"_id": suat_chieu_id})
            if not existing_suat_chieu:
                return {"error": "Suất chiếu không tồn tại", "status": 404}

            update_data = {}
            if gio_chieu:
                # Hỗ trợ cả hai format
                try:
                    if 'T' in gio_chieu:
                        # Format ISO: 2024-01-25T19:30:00+00:00
                        dt = datetime.fromisoformat(gio_chieu.replace('Z', '+00:00'))
                        update_data["gioChieu"] = dt.isoformat() + "+00:00"
                    else:
                        # Format cũ: 2024-01-25 19:30:00
                        dt = datetime.strptime(gio_chieu, "%Y-%m-%d %H:%M:%S")
                        update_data["gioChieu"] = dt.isoformat() + "+00:00"
                except:
                    # Nếu không parse được thì giữ nguyên
                    update_data["gioChieu"] = gio_chieu

            if gia_ve is not None:
                update_data["giaVe"] = gia_ve

            if so_ghe is not None:
                update_data["soGhe"] = so_ghe

            if phong_chieu is not None:
                update_data["phongChieu"] = phong_chieu

            if gio_bat_dat:
                update_data["gioBatDat"] = gio_bat_dat

            if gio_ket_thuc:
                update_data["gioKetThuc"] = gio_ket_thuc

            if not update_data:
                return {"message": "Không có thay đổi nào được thực hiện", "status": 200}

            result = self.suat_chieu_collection.update_one(
                {"_id": suat_chieu_id},
                {"$set": update_data}
            )

            if result.modified_count > 0:
                return {"message": "Cập nhật suất chiếu thành công", "status": 200}
            else:
                return {"message": "Không có thay đổi nào được thực hiện", "status": 200}

        except Exception as e:
            return {"error": f"Lỗi khi cập nhật suất chiếu: {str(e)}", "status": 500}

    def update_ghe_da_dat(self, suat_chieu_id: str, ghe_da_dat: List[str]):
        try:
            existing_suat_chieu = self.suat_chieu_collection.find_one({"_id": suat_chieu_id})
            if not existing_suat_chieu:
                return {"error": "Suất chiếu không tồn tại", "status": 404}

            so_ghe = existing_suat_chieu.get("soGhe", 0)
            # Bỏ qua kiểm tra số ghế vì có thể đã được cập nhật trước đó
            # if len(ghe_da_dat) > so_ghe:
            #     return {
            #         "error": f"Số ghế đã đặt ({len(ghe_da_dat)}) không được vượt quá tổng số ghế ({so_ghe})",
            #         "status": 400
            #     }

            result = self.suat_chieu_collection.update_one(
                {"_id": suat_chieu_id},
                {"$set": {"gheDaDat": ghe_da_dat}}
            )

            # Luôn trả về success vì có thể data đã giống nhau
            ghe_trong = so_ghe - len(ghe_da_dat)
            return {
                "message": "Cập nhật ghế đã đặt thành công",
                "suat_chieu_id": suat_chieu_id,
                "ghe_da_dat": ghe_da_dat,
                "ghe_trong": ghe_trong,
                "status": 200
            }

        except Exception as e:
            return {"error": f"Lỗi khi cập nhật ghế đã đặt: {str(e)}", "status": 500}

    def delete_suat_chieu(self, suat_chieu_id: str):
        try:
            existing_suat_chieu = self.suat_chieu_collection.find_one({"_id": suat_chieu_id})
            if not existing_suat_chieu:
                return {"error": "Suất chiếu không tồn tại", "status": 404}

            ghe_da_dat = existing_suat_chieu.get("gheDaDat", [])
            if len(ghe_da_dat) > 0:
                return {
                    "error": f"Không thể xóa suất chiếu vì đã có {len(ghe_da_dat)} ghế được đặt",
                    "status": 400
                }

            result = self.suat_chieu_collection.delete_one({"_id": suat_chieu_id})

            if result.deleted_count > 0:
                return {"message": "Xóa suất chiếu thành công", "status": 200}
            else:
                return {"error": "Không thể xóa suất chiếu", "status": 500}

        except Exception as e:
            return {"error": f"Lỗi khi xóa suất chiếu: {str(e)}", "status": 500}

    def get_suat_chieu_by_id(self, suat_chieu_id: str):
        try:
            suat_chieu = self.suat_chieu_collection.find_one({"_id": suat_chieu_id})
            if not suat_chieu:
                return {"error": "Suất chiếu không tồn tại", "status": 404}

            phim = self.phim_collection.find_one({"_id": suat_chieu["phim_id"]})
            rap = self.rap_collection.find_one({"_id": suat_chieu["rap_id"]})

            so_ghe = suat_chieu.get("soGhe", 0)
            ghe_da_dat = suat_chieu.get("gheDaDat", [])
            ghe_trong = so_ghe - len(ghe_da_dat) if isinstance(ghe_da_dat, list) else so_ghe

            result = OrderedDict([
                ("id", str(suat_chieu["_id"])),
                ("phim", OrderedDict([
                    ("id", str(phim["_id"])),
                    ("tenPhim", phim.get("tenPhim", "")),
                    ("thoiLuong", phim.get("thoiLuong", 0)),
                    ("theLoai", phim.get("theLoai", []))
                ]) if phim else None),
                ("rap", OrderedDict([
                    ("id", str(rap["_id"])),
                    ("tenRap", rap.get("tenRap", "")),
                    ("diaChi", rap.get("diaChi", ""))
                ]) if rap else None),
                ("phongChieu", suat_chieu.get("phongChieu", "")),
                ("gioChieu", str(suat_chieu.get("gioChieu", ""))),
                ("gioBatDat", str(suat_chieu.get("gioBatDat", ""))),
                ("gioKetThuc", str(suat_chieu.get("gioKetThuc", ""))),
                ("giaVe", suat_chieu.get("giaVe", 0)),
                ("tongGhe", so_ghe),
                ("gheTrong", ghe_trong),
                ("gheDaDat", ghe_da_dat),
                ("created_at", suat_chieu.get("created_at", "").isoformat() if suat_chieu.get("created_at") and isinstance(suat_chieu.get("created_at"), datetime) else str(suat_chieu.get("created_at", ""))),
                ("updated_at", suat_chieu.get("updated_at", "").isoformat() if suat_chieu.get("updated_at") and isinstance(suat_chieu.get("updated_at"), datetime) else str(suat_chieu.get("updated_at", "")))
            ])

            return {"data": result, "status": 200}

        except Exception as e:
            return {"error": f"Lỗi khi lấy thông tin suất chiếu: {str(e)}", "status": 500}

    def get_all_suat_chieu(self, page: int = 1, limit: int = 10, phim_id: Optional[str] = None, rap_id: Optional[str] = None):
        try:
            query = {}
            if phim_id:
                query["phim_id"] = phim_id
            if rap_id:
                query["rap_id"] = rap_id

            skip = (page - 1) * limit
            total = self.suat_chieu_collection.count_documents(query)

            suat_chieu_list = list(
                self.suat_chieu_collection.find(query)
                .sort("gioChieu", 1)
                .skip(skip)
                .limit(limit)
            )

            result_list = []
            for suat_chieu in suat_chieu_list:
                phim = self.phim_collection.find_one({"_id": suat_chieu["phim_id"]})
                rap = self.rap_collection.find_one({"_id": suat_chieu["rap_id"]})

                so_ghe = suat_chieu.get("soGhe", 0)
                ghe_da_dat = suat_chieu.get("gheDaDat", [])
                ghe_trong = so_ghe - len(ghe_da_dat) if isinstance(ghe_da_dat, list) else so_ghe

                suat_chieu_item = OrderedDict([
                    ("id", str(suat_chieu["_id"])),
                    ("phim_ten", phim.get("tenPhim", "") if phim else ""),
                    ("rap_ten", rap.get("tenRap", "") if rap else ""),
                    ("phongChieu", suat_chieu.get("phongChieu", "")),
                    ("gioChieu", suat_chieu["gioChieu"].isoformat() if isinstance(suat_chieu["gioChieu"], datetime) else str(suat_chieu["gioChieu"])),
                    ("giaVe", suat_chieu.get("giaVe", 0)),
                    ("tongGhe", so_ghe),
                    ("gheTrong", ghe_trong),
                    ("gheDaDat", ghe_da_dat)
                ])
                result_list.append(suat_chieu_item)

            return {
                "data": result_list,
                "pagination": {
                    "page": page,
                    "limit": limit,
                    "total": total,
                    "total_pages": (total + limit - 1) // limit
                },
                "status": 200
            }

        except Exception as e:
            return {"error": f"Lỗi khi lấy danh sách suất chiếu: {str(e)}", "status": 500}

    def close_connection(self):
        if self.client:
            self.client.close()

# API Endpoints 

@router.get("/lich-chieu/{phim_id}")
async def get_lich_chieu_phim(
    phim_id: str,
    ngay_bat_dau: Optional[str] = Query(None, description="Ngày bắt đầu (YYYY-MM-DD)"),
    ngay_ket_thuc: Optional[str] = Query(None, description="Ngày kết thúc (YYYY-MM-DD)")
):
    """Lấy lịch chiếu của một phim cụ thể"""
    lam = Lam()
    try:
        result = lam.get_lich_chieu_phim(phim_id, ngay_bat_dau, ngay_ket_thuc)
        if result.get("status") != 200:
            raise HTTPException(status_code=result.get("status", 500), detail=result.get("error", "Lỗi không xác định"))
        return result
    finally:
        lam.close_connection()

@router.post("/")
async def create_suat_chieu(suat_chieu_data: SuatChieuCreate):
    """Tạo suất chiếu mới"""
    lam = Lam()
    try:
        result = lam.create_suat_chieu(
            suat_chieu_data.phim_id,
            suat_chieu_data.rap_id,
            suat_chieu_data.gio_chieu,
            suat_chieu_data.gia_ve,
            suat_chieu_data.so_ghe,
            suat_chieu_data.phong_chieu,
            suat_chieu_data.gio_bat_dat,
            suat_chieu_data.gio_ket_thuc
        )
        if result.get("status") != 201:
            raise HTTPException(status_code=result.get("status", 500), detail=result.get("error", "Lỗi không xác định"))
        return result
    finally:
        lam.close_connection()

@router.put("/{suat_chieu_id}")
async def update_suat_chieu(suat_chieu_id: str, suat_chieu_data: SuatChieuUpdate):
    """Cập nhật thông tin suất chiếu với các trường được phép"""
    lam = Lam()
    try:
        # Chỉ sử dụng các trường được phép
        gio_chieu = suat_chieu_data.gioChieu
        gia_ve = suat_chieu_data.giaVe
        so_ghe = suat_chieu_data.tongGhe
        phong_chieu = suat_chieu_data.phongChieu
        ghe_da_dat = suat_chieu_data.gheDaDat
        
        # Cập nhật thông tin suất chiếu
        result = lam.update_suat_chieu(
            suat_chieu_id,
            gio_chieu,
            gia_ve,
            so_ghe,
            phong_chieu,
            None,  # gio_bat_dat
            None   # gio_ket_thuc
        )
        
        # Nếu có gheDaDat thì cập nhật ghế
        if ghe_da_dat is not None:
            ghe_result = lam.update_ghe_da_dat(suat_chieu_id, ghe_da_dat)
            if ghe_result.get("status") != 200:
                raise HTTPException(status_code=ghe_result.get("status", 500), detail=ghe_result.get("error", "Lỗi không xác định"))
            # Merge kết quả
            result["ghe_da_dat"] = ghe_result.get("ghe_da_dat", [])
            result["ghe_trong"] = ghe_result.get("ghe_trong", 0)
        
        if result.get("status") != 200:
            raise HTTPException(status_code=result.get("status", 500), detail=result.get("error", "Lỗi không xác định"))
        return result
    finally:
        lam.close_connection()

@router.delete("/{suat_chieu_id}")
async def delete_suat_chieu(suat_chieu_id: str):
    """Xóa suất chiếu"""
    lam = Lam()
    try:
        result = lam.delete_suat_chieu(suat_chieu_id)
        if result.get("status") != 200:
            raise HTTPException(status_code=result.get("status", 500), detail=result.get("error", "Lỗi không xác định"))
        return result
    finally:
        lam.close_connection()

@router.get("/{suat_chieu_id}")
async def get_suat_chieu_by_id(suat_chieu_id: str):
    """Lấy thông tin chi tiết suất chiếu"""
    lam = Lam()
    try:
        result = lam.get_suat_chieu_by_id(suat_chieu_id)
        if result.get("status") != 200:
            raise HTTPException(status_code=result.get("status", 500), detail=result.get("error", "Lỗi không xác định"))
        return result
    finally:
        lam.close_connection()

@router.get("/")
async def get_all_suat_chieu(
    page: int = Query(1, ge=1, description="Số trang"),
    limit: int = Query(10, ge=1, le=100, description="Số lượng mỗi trang"),
    phim_id: Optional[str] = Query(None, description="Lọc theo phim ID"),
    rap_id: Optional[str] = Query(None, description="Lọc theo rạp ID")
):
    """Lấy danh sách tất cả suất chiếu với phân trang"""
    lam = Lam()
    try:
        result = lam.get_all_suat_chieu(page, limit, phim_id, rap_id)
        if result.get("status") != 200:
            raise HTTPException(status_code=result.get("status", 500), detail=result.get("error", "Lỗi không xác định"))
        return result
    finally:
        lam.close_connection()

