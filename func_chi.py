from datetime import datetime
import re
from fastapi import FastAPI, APIRouter, Body, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from conn import get_mongo_client

# ==========================================================
# 🔗 KẾT NỐI MONGODB
# ==========================================================
client = get_mongo_client()
db = client["QL_DatVeTrucTuyen"]
collection = db["Phim"]

# ==========================================================
# 🎬 MODEL
# ==========================================================
class PhimBase(BaseModel):
    tenPhim: str
    theLoai: str
    daoDien: str
    thoiLuong: int
    ngayKhoiChieu: datetime
    moTa: str
    trailerURL: str
    hinhAnh: str
    danhGia: float

# ==========================================================
# 🎞️ SERIALIZER
# ==========================================================
def phim_serializer(doc):
    return {
        "id": str(doc.get("_id")),
        "tenPhim": doc.get("tenPhim", ""),
        "theLoai": doc.get("theLoai", ""),
        "daoDien": doc.get("daoDien", ""),
        "thoiLuong": doc.get("thoiLuong", 0),
        "ngayKhoiChieu": (
            doc.get("ngayKhoiChieu").isoformat()
            if isinstance(doc.get("ngayKhoiChieu"), datetime)
            else doc.get("ngayKhoiChieu")
        ),
        "moTa": doc.get("moTa", ""),
        "trailerURL": doc.get("trailerURL", ""),
        "hinhAnh": doc.get("hinhAnh", ""),
        "danhGia": doc.get("danhGia", 0),
    }

def phim_list_serializer(docs):
    return [phim_serializer(d) for d in docs]

# ==========================================================
# 🔢 HÀM TẠO PHẢN HỒI CHUẨN
# ==========================================================
def api_response(status_code: int, message: str, data=None) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "status_code": status_code,
            "message": message,
            "data": data
        },
    )

# ==========================================================
# 🧩 VALIDATE
# ==========================================================
def validate_ten_phim_unique(tenPhim: str, current_id: str = None):
    query = {"tenPhim": {"$regex": f"^{tenPhim}$", "$options": "i"}}
    existing = collection.find_one(query)
    if existing and (not current_id or existing["_id"] != current_id):
        return f"Tên phim '{tenPhim}' đã tồn tại."
    return None

def validate_ngay_khoi_chieu(ngay):
    try:
        if isinstance(ngay, str):
            ngay = datetime.fromisoformat(ngay)
    except Exception:
        return "Ngày khởi chiếu phải có định dạng ISO hợp lệ (YYYY-MM-DDTHH:MM:SS)."
    if ngay < datetime.now():
        return "Ngày khởi chiếu không được nhỏ hơn ngày hiện tại."
    return None

def validate_thoi_luong(thoiLuong):
    if thoiLuong is None or thoiLuong <= 0:
        return "Thời lượng phim phải lớn hơn 0 phút."
    return None

def validate_danh_gia(danhGia):
    if danhGia is None or not (0 <= danhGia <= 10):
        return "Điểm đánh giá (danhGia) phải nằm trong khoảng từ 0 đến 10."
    return None

# ==========================================================
# 🔢 SINH ID TỰ ĐỘNG
# ==========================================================
def _generate_phim_id() -> str:
    try:
        cursor = collection.find({"_id": {"$regex": r"^Phim\d+$"}}, {"_id": 1})
        max_n = 0
        for d in cursor:
            m = re.match(r"^Phim(\d+)$", d.get("_id", ""))
            if m:
                n = int(m.group(1))
                if n > max_n:
                    max_n = n
        return f"Phim{max_n + 1}"
    except Exception:
        return f"Phim{int(datetime.utcnow().timestamp())}"

# ==========================================================
# ⚙️ ROUTER
# ==========================================================
router = APIRouter(prefix="/api/phim", tags=["Phim"])

# ==========================================================
# 🟢 CREATE
# ==========================================================
@router.post("/create/")
def create_phim(phim_data: dict = Body(...)):
    try:
        # Kiểm tra payload hợp lệ
        if not isinstance(phim_data, dict):
            return api_response(400, "Payload không hợp lệ.", None)

        #  Kiểm tra các field bắt buộc
        required_fields = [
            "tenPhim", "theLoai", "daoDien", "thoiLuong",
            "ngayKhoiChieu", "moTa", "trailerURL", "hinhAnh", "danhGia"
        ]
        missing_fields = [f for f in required_fields if f not in phim_data]
        if missing_fields:
            return api_response(400, "Thiếu dữ liệu bắt buộc.", {"missing_fields": missing_fields})

        #  Validate trùng tên
        err = validate_ten_phim_unique(phim_data["tenPhim"])
        if err:
            return api_response(409, err, {"tenPhim": phim_data["tenPhim"]})

        # Validate ngày khởi chiếu
        if "ngayKhoiChieu" in phim_data:
            err = validate_ngay_khoi_chieu(phim_data["ngayKhoiChieu"])
            if err:
                return api_response(404, err, {"ngayKhoiChieu": phim_data["ngayKhoiChieu"]})
            # Chuẩn hóa datetime
            if isinstance(phim_data["ngayKhoiChieu"], str):
                phim_data["ngayKhoiChieu"] = datetime.fromisoformat(phim_data["ngayKhoiChieu"])

        # Validate thời lượng
        if "thoiLuong" in phim_data:
            err = validate_thoi_luong(phim_data["thoiLuong"])
            if err:
                return api_response(405, err, {"thoiLuong": phim_data["thoiLuong"]})

        # Validate đánh giá
        if "danhGia" in phim_data:
            err = validate_danh_gia(phim_data["danhGia"])
            if err:
                return api_response(406, err, {"danhGia": phim_data["danhGia"]})

        # Sinh ID và thêm vào MongoDB
        new_id = _generate_phim_id()
        phim_data["_id"] = new_id
        collection.insert_one(phim_data)

        # Lấy lại document và serialize datetime
        created_doc = collection.find_one({"_id": new_id})
        serialized_doc = phim_serializer(created_doc)

        return api_response(200, "Thêm phim thành công.", serialized_doc)

    except Exception as e:
        return api_response(500, "Không thể thêm phim.", {"error": str(e)})

# ==========================================================
# 🟡 READ ALL
# ==========================================================
@router.get("/")
def get_all_phim():
    try:
        docs = list(collection.find())
        return api_response(200, "Lấy danh sách phim thành công.", phim_list_serializer(docs))
    except Exception as e:
        return api_response(500, "Không thể lấy danh sách phim.", {"error": str(e)})

# ==========================================================
# 🔵 READ BY ID
# ==========================================================
@router.get("/{phim_id}")
def get_phim_by_id(phim_id: str):
    try:
        phim = collection.find_one({"_id": phim_id})
        if not phim:
            return api_response(404, "Không tìm thấy phim.", {"id": phim_id})
        return api_response(200, "Lấy phim thành công.", phim_serializer(phim))
    except Exception as e:
        return api_response(500, "Không thể lấy phim.", {"error": str(e)})

# ==========================================================
# 🟠 UPDATE
# ==========================================================
@router.put("/{phim_id}")
def update_phim(phim_id: str, update_data: dict = Body(...)):
    try:
        required_fields = [
            "tenPhim", "theLoai", "daoDien", "thoiLuong",
            "ngayKhoiChieu", "moTa", "trailerURL", "hinhAnh", "danhGia"
        ]
        missing_fields = [f for f in required_fields if f not in update_data]
        if missing_fields:
            return api_response(400, "Thiếu dữ liệu bắt buộc.", {"missing_fields": missing_fields})

        phim_exist = collection.find_one({"_id": phim_id})
        if not phim_exist:
            return api_response(404, "Không tìm thấy phim để cập nhật.", {"id": phim_id})

        if "tenPhim" in update_data:
            err = validate_ten_phim_unique(update_data["tenPhim"], current_id=phim_id)
            if err:
                return api_response(409, err, {"tenPhim": update_data["tenPhim"]})

        if "ngayKhoiChieu" in update_data:
            err = validate_ngay_khoi_chieu(update_data["ngayKhoiChieu"])
            if err:
                return api_response(406, err, {"ngayKhoiChieu": update_data["ngayKhoiChieu"]})
            if isinstance(update_data["ngayKhoiChieu"], str):
                update_data["ngayKhoiChieu"] = datetime.fromisoformat(update_data["ngayKhoiChieu"])

        if "thoiLuong" in update_data:
            err = validate_thoi_luong(update_data["thoiLuong"])
            if err:
                return api_response(407, err, {"thoiLuong": update_data["thoiLuong"]})

        if "danhGia" in update_data:
            err = validate_danh_gia(update_data["danhGia"])
            if err:
                return api_response(408, err, {"danhGia": update_data["danhGia"]})

        collection.update_one({"_id": phim_id}, {"$set": update_data})
        updated_doc = collection.find_one({"_id": phim_id})
        return api_response(200, "Cập nhật phim thành công.", phim_serializer(updated_doc))
    except Exception as e:
        return api_response(500, "Không thể cập nhật phim.", {"error": str(e)})

# ==========================================================
# 🔴 DELETE
# ==========================================================
@router.delete("/{phim_id}")
def delete_phim(phim_id: str):
    try:
        phim = collection.find_one({"_id": phim_id})
        if not phim:
            return api_response(404, "Không tìm thấy phim để xóa.", {"id": phim_id})
        collection.delete_one({"_id": phim_id})
        return api_response(200, "Xóa phim thành công.", {"id": phim_id})
    except Exception as e:
        return api_response(500, "Không thể xóa phim.", {"error": str(e)})

