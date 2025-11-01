from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List
from bson import ObjectId
from conn import get_mongo_client
from datetime import datetime

router_dashboard = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

# ================== Pydantic Models cho Dashboard ==================
class DoanhThuTheoThoiGian(BaseModel):
    thoi_gian: str  # "2025-11-01" hoặc "2025-11"
    doanh_thu: int
    so_ve: int

class TrangThaiVe(BaseModel):
    trang_thai: str
    so_ve: int
    so_ghe: int

class TopPhim(BaseModel):
    phim_id: str
    ten_phim: str
    so_ghe_dat: int
    doanh_thu: int

class DoanhThuRap(BaseModel):
    rap_id: str
    ten_rap: str
    dia_chi: str
    doanh_thu: int
    so_ve: int

class TyLeGheSuat(BaseModel):
    suat_id: str
    ten_phim: str
    ten_rap: str
    ten_phong: str
    so_ghe_da_dat: int
    tong_ghe: int
    ty_le: float  # phần trăm

class PhuongThucThanhToan(BaseModel):
    phuong_thuc: str
    so_lan: int
    doanh_thu: int

class NguoiDungMoi(BaseModel):
    thang: str  # "2025-10"
    so_nguoi_dung: int

class TopGhe(BaseModel):
    ghe: str
    so_lan_chon: int

# ================== Class Dashboard ==================
class DashboardManager:
    def __init__(self):
        self.client = get_mongo_client()
        self.db = self.client["QL_DatVeTrucTuyen"]
        self.ve = self.db["Ve"]
        self.suat = self.db["SuatChieu"]
        self.phim = self.db["Phim"]
        self.rap = self.db["Rap"]
        self.nguoi_dung = self.db["NguoiDung"]

    # 1. Tổng doanh thu theo ngày/tháng
    def get_doanh_thu_theo_thoi_gian(self, loai: str = "day"):
        format_str = "%Y-%m-%d" if loai == "day" else "%Y-%m"
        pipeline = [
            {"$match": {"trangThai": "Đã thanh toán"}},
            {
                "$addFields": {
                    "thoiGian": {
                        "$dateToString": {"format": format_str, "date": "$ngayThanhToan"}
                    }
                }
            },
            {
                "$group": {
                    "_id": "$thoiGian",
                    "doanh_thu": {"$sum": "$tongTien"},
                    "so_ve": {"$sum": {"$size": "$soGhe"}}
                }
            },
            {"$sort": {"_id": 1}},
            {
                "$project": {
                    "thoi_gian": "$_id",
                    "doanh_thu": 1,
                    "so_ve": 1,
                    "_id": 0
                }
            }
        ]
        return list(self.ve.aggregate(pipeline))

    # 2. Số lượng vé đã bán / đã hủy
    def get_trang_thai_ve(self):
        pipeline = [
            {
                "$group": {
                    "_id": "$trangThai",
                    "so_ve": {"$sum": 1},
                    "so_ghe": {"$sum": {"$size": "$soGhe"}}
                }
            },
            {
                "$project": {
                    "trang_thai": "$_id",
                    "so_ve": 1,
                    "so_ghe": 1,
                    "_id": 0
                }
            },
            {"$sort": {"so_ve": -1}}
        ]
        return list(self.ve.aggregate(pipeline))

    # 3. Top 5 phim được đặt nhiều nhất
    def get_top_5_phim(self):
        pipeline = [
            {"$match": {"trangThai": "Đã thanh toán"}},
            {"$lookup": {"from": "SuatChieu", "localField": "suatChieu_id", "foreignField": "_id", "as": "suat"}},
            {"$unwind": "$suat"},
            {"$lookup": {"from": "Phim", "localField": "suat.phim_id", "foreignField": "_id", "as": "phim"}},
            {"$unwind": "$phim"},
            {
                "$group": {
                    "_id": "$phim._id",
                    "ten_phim": {"$first": "$phim.tenPhim"},
                    "so_ghe_dat": {"$sum": {"$size": "$soGhe"}},
                    "doanh_thu": {"$sum": "$tongTien"}
                }
            },
            {"$sort": {"so_ghe_dat": -1}},
            {"$limit": 5},
            {
                "$project": {
                    "phim_id": "$_id",
                    "ten_phim": 1,
                    "so_ghe_dat": 1,
                    "doanh_thu": 1,
                    "_id": 0
                }
            }
        ]
        return list(self.ve.aggregate(pipeline))

    # 4. Doanh thu theo rạp
    def get_doanh_thu_theo_rap(self):
        pipeline = [
            {"$match": {"trangThai": "Đã thanh toán"}},
            {"$lookup": {"from": "SuatChieu", "localField": "suatChieu_id", "foreignField": "_id", "as": "suat"}},
            {"$unwind": "$suat"},
            {"$lookup": {"from": "Rap", "localField": "suat.rap_id", "foreignField": "_id", "as": "rap"}},
            {"$unwind": "$rap"},
            {
                "$group": {
                    "_id": "$rap._id",
                    "ten_rap": {"$first": "$rap.tenRap"},
                    "dia_chi": {"$first": "$rap.diaChi"},
                    "doanh_thu": {"$sum": "$tongTien"},
                    "so_ve": {"$sum": 1}
                }
            },
            {"$sort": {"doanh_thu": -1}},
            {
                "$project": {
                    "rap_id": "$_id",
                    "ten_rap": 1,
                    "dia_chi": 1,
                    "doanh_thu": 1,
                    "so_ve": 1,
                    "_id": 0
                }
            }
        ]
        return list(self.ve.aggregate(pipeline))

    # 5. Tỷ lệ ghế đã đặt theo suất chiếu
    def get_ty_le_ghe_suat_chieu(self, suat_id: str):
        pipeline = [
            # 1. Lọc vé đã thanh toán của suất chiếu
            {"$match": {"suatChieu_id": suat_id, "trangThai": "Đã thanh toán"}},

            # 2. Join với SuatChieu
            {"$lookup": {
                "from": "SuatChieu",
                "localField": "suatChieu_id",
                "foreignField": "_id",
                "as": "suat"
            }},
            {"$unwind": "$suat"},

            # 3. Join với Phim
            {"$lookup": {
                "from": "Phim",
                "localField": "suat.phim_id",
                "foreignField": "_id",
                "as": "phim"
            }},
            {"$unwind": "$phim"},

            # 4. Join với Rap để lấy thông tin phòng
            {"$lookup": {
                "from": "Rap",
                "localField": "suat.rap_id",
                "foreignField": "_id",
                "as": "rap"
            }},
            {"$unwind": "$rap"},

            # 5. Lấy thông tin phòng chiếu (so_Luong_Ghe)
            {
                "$addFields": {
                    "phong_info": {
                        "$arrayElemAt": [
                            {
                                "$filter": {
                                    "input": "$rap.phongChieu",
                                    "cond": {"$eq": ["$$this.ten_Phong", "$suat.ten_Phong"]}
                                }
                            }, 0
                        ]
                    }
                }
            },

            # 6. Group để tính tổng ghế đã đặt
            {
                "$group": {
                    "_id": "$suat._id",
                    "ten_phim": {"$first": "$phim.tenPhim"},
                    "ten_rap": {"$first": "$rap.tenRap"},
                    "ten_phong": {"$first": "$suat.ten_Phong"},
                    "tong_ghe": {"$first": "$phong_info.so_Luong_Ghe"},
                    "so_ghe_da_dat": {"$sum": {"$size": "$soGhe"}}
                }
            },

            # 7. Tính tỷ lệ + format kết quả
            {
                "$project": {
                    "suat_id": "$_id",
                    "ten_phim": 1,
                    "ten_rap": 1,
                    "ten_phong": 1,
                    "so_ghe_da_dat": 1,
                    "tong_ghe": {"$ifNull": ["$tong_ghe", 0]},
                    "ty_le": {
                        "$round": [
                            {
                                "$multiply": [
                                    {
                                        "$divide": [
                                            "$so_ghe_da_dat",
                                            {"$ifNull": [{"$max": ["$tong_ghe", 1]}, 1]}  # Tránh chia cho 0
                                        ]
                                    },
                                    100
                                ]
                            },
                            2
                        ]
                    },
                    "_id": 0
                }
            }
        ]

        result = list(self.ve.aggregate(pipeline))
        return result[0] if result else None
    # 6. Phương thức thanh toán phổ biến
    def get_phuong_thuc_thanh_toan(self):
        pipeline = [
            {"$match": {"trangThai": "Đã thanh toán"}},
            {
                "$group": {
                    "_id": "$phuongThuc",
                    "so_lan": {"$sum": 1},
                    "doanh_thu": {"$sum": "$tongTien"}
                }
            },
            {"$sort": {"so_lan": -1}},
            {
                "$project": {
                    "phuong_thuc": "$_id",
                    "so_lan": 1,
                    "doanh_thu": 1,
                    "_id": 0
                }
            }
        ]
        return list(self.ve.aggregate(pipeline))

    # 7. Số lượng người dùng mới theo tháng
    def get_nguoi_dung_moi_theo_thang(self):
        pipeline = [
            {
                "$addFields": {
                    "thang": {"$dateToString": {"format": "%Y-%m", "date": "$ngayDangKy"}}
                }
            },
            {
                "$group": {
                    "_id": "$thang",
                    "so_nguoi_dung": {"$sum": 1}
                }
            },
            {"$sort": {"_id": 1}},
            {
                "$project": {
                    "thang": "$_id",
                    "so_nguoi_dung": 1,
                    "_id": 0
                }
            }
        ]
        return list(self.nguoi_dung.aggregate(pipeline))

    # 8. Top 5 ghế được chọn nhiều nhất
    def get_top_5_ghe(self):
        pipeline = [
            {"$match": {"trangThai": "Đã thanh toán"}},
            {"$unwind": "$soGhe"},
            {
                "$group": {
                    "_id": "$soGhe",
                    "so_lan_chon": {"$sum": 1}
                }
            },
            {"$sort": {"so_lan_chon": -1}},
            {"$limit": 5},
            {
                "$project": {
                    "ghe": "$_id",
                    "so_lan_chon": 1,
                    "_id": 0
                }
            }
        ]
        return list(self.ve.aggregate(pipeline))

    def __del__(self):
        if hasattr(self, 'client'):
            self.client.close()
# 1. Doanh thu theo ngày/tháng
@router_dashboard.get("/doanh-thu", response_model=List[DoanhThuTheoThoiGian])
async def doanh_thu_theo_thoi_gian(
    loai: str = Query("day", regex="^(day|month)$", description="day hoặc month")
):
    ql = DashboardManager()
    try:
        return ql.get_doanh_thu_theo_thoi_gian(loai)
    finally:
        ql.__del__()

# 2. Trạng thái vé
@router_dashboard.get("/trang-thai-ve", response_model=List[TrangThaiVe])
async def trang_thai_ve():
    ql = DashboardManager()
    try:
        return ql.get_trang_thai_ve()
    finally:
        ql.__del__()

# 3. Top 5 phim
@router_dashboard.get("/top-phim", response_model=List[TopPhim])
async def top_5_phim():
    ql = DashboardManager()
    try:
        return ql.get_top_5_phim()
    finally:
        ql.__del__()

# 4. Doanh thu theo rạp
@router_dashboard.get("/doanh-thu-rap", response_model=List[DoanhThuRap])
async def doanh_thu_rap():
    ql = DashboardManager()
    try:
        return ql.get_doanh_thu_theo_rap()
    finally:
        ql.__del__()

# 5. Tỷ lệ ghế suất chiếu
@router_dashboard.get("/ty-le-ghe/{suat_id}", response_model=TyLeGheSuat)
async def ty_le_ghe_suat(suat_id: str):
    ql = DashboardManager()
    try:
        result = ql.get_ty_le_ghe_suat_chieu(suat_id)
        if not result:
            raise HTTPException(404, "Không tìm thấy suất chiếu hoặc chưa có vé")
        return result
    finally:
        ql.__del__()

# 6. Phương thức thanh toán
@router_dashboard.get("/phuong-thuc", response_model=List[PhuongThucThanhToan])
async def phuong_thuc_thanh_toan():
    ql = DashboardManager()
    try:
        return ql.get_phuong_thuc_thanh_toan()
    finally:
        ql.__del__()

# 7. Người dùng mới theo tháng
@router_dashboard.get("/nguoi-dung-moi", response_model=List[NguoiDungMoi])
async def nguoi_dung_moi():
    ql = DashboardManager()
    try:
        return ql.get_nguoi_dung_moi_theo_thang()
    finally:
        ql.__del__()

# 8. Top 5 ghế
@router_dashboard.get("/top-ghe", response_model=List[TopGhe])
async def top_5_ghe():
    ql = DashboardManager()
    try:
        return ql.get_top_5_ghe()
    finally:
        ql.__del__()