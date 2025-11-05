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
    gia_ve: int
    phong_chieu: str  # Tên phòng chiếu (bắt buộc)
    gio_bat_dat: str  # Giờ bắt đầu (bắt buộc)
    gio_ket_thuc: str  # Giờ kết thúc (bắt buộc)
    so_ghe: Optional[int] = None  # Optional: sẽ tự động lấy từ Rap collection dựa trên phong_chieu

class SuatChieuUpdate(BaseModel):
    # Chỉ các trường được phép update
    phim_id: Optional[str] = None  # ID phim
    rap_id: Optional[str] = None  # ID rạp
    ten_Phong: Optional[str] = None  # Tên phòng chiếu
    gioBatDau: Optional[str] = None  # Giờ bắt đầu
    gioKetThuc: Optional[str] = None  # Giờ kết thúc
    giaVe: Optional[int] = None  # Giá vé

class Lam:
    def __init__(self):
        self.client = get_mongo_client()
        self.db = self.client["QL_DatVeTrucTuyen"]
        self.phim_collection = self.db["Phim"]
        self.suat_chieu_collection = self.db["SuatChieu"]
        self.rap_collection = self.db["Rap"]
        self.ve_collection = self.db["Ve"]

    def _get_so_ghe_from_rap(self, rap_id: str, ten_phong: str) -> int:
        """
        Lấy số lượng ghế từ Rap collection dựa trên rap_id và ten_Phong
        Tìm trong mảng phongChieu của Rap
        """
        try:
            rap = self.rap_collection.find_one({"_id": rap_id})
            if not rap:
                return 0
            
            phong_chieu_list = rap.get("phongChieu", [])
            if not isinstance(phong_chieu_list, list):
                return 0
            
            # Tìm phòng chiếu có ten_Phong khớp
            for phong in phong_chieu_list:
                if isinstance(phong, dict):
                    ten_phong_rap = phong.get("ten_Phong", "").strip()
                    # So sánh không phân biệt hoa thường và loại bỏ dấu phẩy
                    if ten_phong_rap.rstrip(',').strip().lower() == ten_phong.strip().lower():
                        return phong.get("so_Luong_Ghe", 0)
            
            return 0
        except Exception as e:
            return 0

    def _get_ghe_da_dat_from_ve(self, suat_chieu_id: str) -> List[str]:
        """
        Lấy danh sách ghế đã đặt từ Ve collection dựa trên suatChieu_id
        Chỉ lấy vé có trangThai không phải "Đã hủy" (lấy vé "Đã thanh toán" hoặc các trạng thái khác hợp lệ)
        """
        try:
            if not suat_chieu_id:
                print(f"DEBUG: suat_chieu_id is empty")
                return []
            
            # Kiểm tra collection có tồn tại không (Phải dùng `is None` thay vì `not` vì PyMongo Collection không hỗ trợ boolean context)
            if self.ve_collection is None:
                print(f"DEBUG: ve_collection is None!")
                return []
            
            # Đảm bảo suat_chieu_id là string và loại bỏ khoảng trắng
            suat_chieu_id = str(suat_chieu_id).strip()
            
            # Test query đơn giản để đảm bảo collection có dữ liệu
            total_ves = self.ve_collection.count_documents({})
            print(f"DEBUG: Total tickets in Ve collection: {total_ves}")
            
            # Query: Tìm tất cả vé có suatChieu_id khớp và trangThai không phải "Đã hủy"
            query = {
                "suatChieu_id": suat_chieu_id,
                "trangThai": {"$ne": "Đã hủy"}
            }
            
            print(f"DEBUG: Querying Ve collection with: {query}")
            ves = list(self.ve_collection.find(query))
            print(f"DEBUG: Found {len(ves)} tickets for suatChieu_id='{suat_chieu_id}'")
            
            if ves:
                print(f"DEBUG: Sample ticket: suatChieu_id={ves[0].get('suatChieu_id')}, soGhe={ves[0].get('soGhe')}, trangThai={ves[0].get('trangThai')}")
            
            ghe_da_dat = []
            for ve in ves:
                so_ghe_list = ve.get("soGhe", [])
                if isinstance(so_ghe_list, list) and len(so_ghe_list) > 0:
                    ghe_da_dat.extend(so_ghe_list)
                    print(f"DEBUG: Added seats {so_ghe_list} from ticket {ve.get('_id')}")
            
            # Loại bỏ trùng lặp và sắp xếp
            result = sorted(list(set(ghe_da_dat)))
            print(f"DEBUG: Final ghe_da_dat for suatChieu_id='{suat_chieu_id}': {result}")
            return result
            
        except Exception as e:
            import traceback
            print(f"ERROR in _get_ghe_da_dat_from_ve for suat_chieu_id={suat_chieu_id}: {e}")
            print(f"ERROR traceback: {traceback.format_exc()}")
            return []

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

                # Lấy soGhe từ Rap collection dựa trên rap_id và ten_Phong
                ten_phong = suat_chieu.get("ten_Phong") or suat_chieu.get("phongChieu", "")
                so_ghe = self._get_so_ghe_from_rap(suat_chieu["rap_id"], ten_phong)
                
                # Lấy gheDaDat từ Ve collection
                suat_chieu_id = str(suat_chieu.get("_id", ""))
                ghe_da_dat = self._get_ghe_da_dat_from_ve(suat_chieu_id) if suat_chieu_id else []
                ghe_trong = so_ghe - len(ghe_da_dat) if so_ghe > 0 else 0

                # Xử lý gioBatDau - chuyển datetime object sang ISO format
                gio_bat_dau_value = suat_chieu.get("gioBatDau")
                if isinstance(gio_bat_dau_value, datetime):
                    gio_bat_dau_str = gio_bat_dau_value.isoformat()
                else:
                    gio_bat_dau_str = str(gio_bat_dau_value) if gio_bat_dau_value else ""

                # Xử lý gioKetThuc - chuyển datetime object sang ISO format
                gio_ket_thuc_value = suat_chieu.get("gioKetThuc")
                if isinstance(gio_ket_thuc_value, datetime):
                    gio_ket_thuc_str = gio_ket_thuc_value.isoformat()
                else:
                    gio_ket_thuc_str = str(gio_ket_thuc_value) if gio_ket_thuc_value else ""

                lich_chieu_item = OrderedDict([
                    ("id", str(suat_chieu["_id"])),
                    ("ten_Phong", suat_chieu.get("ten_Phong", "")),
                    ("gioBatDau", gio_bat_dau_str),
                    ("gioKetThuc", gio_ket_thuc_str),
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

    def create_suat_chieu(self, phim_id: str, rap_id: str, gia_ve: int, phong_chieu: str, 
                         gio_bat_dat: str, gio_ket_thuc: str, so_ghe: Optional[int] = None):
        try:
            phim = self.phim_collection.find_one({"_id": phim_id})
            if not phim:
                return {"error": "Phim không tồn tại", "status": 404}

            rap = self.rap_collection.find_one({"_id": rap_id})
            if not rap:
                return {"error": "Rạp không tồn tại", "status": 405}

            # Xử lý gio_bat_dat - chuyển sang datetime object (Date trong MongoDB)
            try:
                if 'T' in gio_bat_dat:
                    gio_bat_dat_dt = datetime.fromisoformat(gio_bat_dat.replace('Z', '+00:00'))
                else:
                    gio_bat_dat_dt = datetime.strptime(gio_bat_dat, "%Y-%m-%d %H:%M:%S")
            except Exception as e:
                return {"error": f"Format gio_bat_dat không hợp lệ: {str(e)}", "status": 400}

            # Xử lý gio_ket_thuc - chuyển sang datetime object (Date trong MongoDB)
            try:
                if 'T' in gio_ket_thuc:
                    gio_ket_thuc_dt = datetime.fromisoformat(gio_ket_thuc.replace('Z', '+00:00'))
                else:
                    gio_ket_thuc_dt = datetime.strptime(gio_ket_thuc, "%Y-%m-%d %H:%M:%S")
            except Exception as e:
                return {"error": f"Format gio_ket_thuc không hợp lệ: {str(e)}", "status": 400}

            # Tạo ID mới - tìm số lớn nhất trong các ID dạng "Suat{number}"
            existing_suat_chieus = list(self.suat_chieu_collection.find({}, {"_id": 1}))
            max_number = 0
            
            for suat in existing_suat_chieus:
                suat_id = suat.get("_id", "")
                if isinstance(suat_id, str) and suat_id.startswith("Suat"):
                    try:
                        number = int(suat_id[4:])
                        if number > max_number:
                            max_number = number
                    except:
                        continue
            
            # Tạo ID mới và đảm bảo không trùng
            new_id = f"Suat{max_number + 1}"
            
            # Kiểm tra ID mới có tồn tại chưa (phòng trường hợp có gap trong số)
            max_retries = 100
            retry_count = 0
            while self.suat_chieu_collection.find_one({"_id": new_id}) and retry_count < max_retries:
                max_number += 1
                new_id = f"Suat{max_number + 1}"
                retry_count += 1
            
            if retry_count >= max_retries:
                return {"error": "Không thể tạo ID mới cho suất chiếu", "status": 500}

            # Kiểm tra số ghế từ Rap collection
            so_ghe_rap = self._get_so_ghe_from_rap(rap_id, phong_chieu)
            if so_ghe_rap == 0:
                return {"error": f"Không tìm thấy phòng chiếu '{phong_chieu}' trong rạp", "status": 404}
            
            # Nếu có truyền so_ghe, validate với số ghế thực tế từ Rap
            if so_ghe and so_ghe != so_ghe_rap:
                return {
                    "error": f"Số ghế không khớp. Phòng '{phong_chieu}' có {so_ghe_rap} ghế, nhưng bạn nhập {so_ghe}",
                    "status": 400
                }

            # Kiểm tra trùng lặp: phim_id, rap_id, ten_Phong, và overlap thời gian
            existing_suat_chieus = list(self.suat_chieu_collection.find({
                "phim_id": phim_id,
                "rap_id": rap_id,
                "ten_Phong": phong_chieu
            }))

            # Kiểm tra overlap thời gian với các suất chiếu đã có
            for existing_suat in existing_suat_chieus:
                existing_gio_bat_dau = existing_suat.get("gioBatDau")
                existing_gio_ket_thuc = existing_suat.get("gioKetThuc")
                
                if existing_gio_bat_dau and existing_gio_ket_thuc:
                    try:
                        # Parse datetime từ database (có thể là datetime object hoặc string)
                        if isinstance(existing_gio_bat_dau, datetime):
                            existing_bat_dau_dt = existing_gio_bat_dau
                        elif isinstance(existing_gio_bat_dau, str):
                            if 'T' in existing_gio_bat_dau:
                                existing_bat_dau_dt = datetime.fromisoformat(existing_gio_bat_dau.replace('Z', '+00:00'))
                            else:
                                existing_bat_dau_dt = datetime.strptime(existing_gio_bat_dau, "%Y-%m-%d %H:%M:%S")
                        else:
                            continue

                        if isinstance(existing_gio_ket_thuc, datetime):
                            existing_ket_thuc_dt = existing_gio_ket_thuc
                        elif isinstance(existing_gio_ket_thuc, str):
                            if 'T' in existing_gio_ket_thuc:
                                existing_ket_thuc_dt = datetime.fromisoformat(existing_gio_ket_thuc.replace('Z', '+00:00'))
                            else:
                                existing_ket_thuc_dt = datetime.strptime(existing_gio_ket_thuc, "%Y-%m-%d %H:%M:%S")
                        else:
                            continue

                        # Kiểm tra overlap: khoảng thời gian mới overlap với khoảng thời gian đã có
                        # Overlap xảy ra khi: gioBatDau mới < gioKetThuc cũ VÀ gioKetThuc mới > gioBatDau cũ
                        if (gio_bat_dat_dt < existing_ket_thuc_dt) and (gio_ket_thuc_dt > existing_bat_dau_dt):
                            return {
                                "error": f"Suất chiếu trùng lặp thời gian với suất '{existing_suat.get('_id')}'. "
                                        f"Thời gian mới ({gio_bat_dat_dt.strftime('%Y-%m-%d %H:%M:%S')} - {gio_ket_thuc_dt.strftime('%Y-%m-%d %H:%M:%S')}) "
                                        f"trùng với thời gian đã có ({existing_bat_dau_dt.strftime('%Y-%m-%d %H:%M:%S')} - {existing_ket_thuc_dt.strftime('%Y-%m-%d %H:%M:%S')})",
                                "status": 400
                            }
                    except Exception as e:
                        # Nếu không parse được datetime thì bỏ qua
                        print(f"WARNING: Không thể parse datetime từ suất chiếu {existing_suat.get('_id')}: {e}")
                        continue

            # Tạo timestamp cho updated_at - dùng datetime object (Date trong MongoDB)
            updated_at_dt = datetime.utcnow()

            suat_chieu_data = {
                "_id": new_id,
                "phim_id": phim_id,
                "rap_id": rap_id,
                "ten_Phong": phong_chieu,  # Tên phòng chiếu - dùng để query từ Rap
                "gioBatDau": gio_bat_dat_dt,  # Giờ bắt đầu - Date object
                "gioKetThuc": gio_ket_thuc_dt,  # Giờ kết thúc - Date object
                "giaVe": gia_ve,
                "updated_at": updated_at_dt  # Date object
                # Không lưu: soGhe, gheDaDat, phongChieu, gioChieu
            }

            result = self.suat_chieu_collection.insert_one(suat_chieu_data)

            return {
                "message": "Tạo suất chiếu thành công",
                "suat_chieu_id": new_id,
                "status": 201
            }

        except Exception as e:
            return {"error": f"Lỗi khi tạo suất chiếu: {str(e)}", "status": 500}

    def update_suat_chieu(self, suat_chieu_id: str, gia_ve: Optional[int] = None, 
                         phim_id: Optional[str] = None, rap_id: Optional[str] = None,
                         ten_Phong: Optional[str] = None, 
                         gio_bat_dat: Optional[str] = None, gio_ket_thuc: Optional[str] = None):
        try:
            existing_suat_chieu = self.suat_chieu_collection.find_one({"_id": suat_chieu_id})
            if not existing_suat_chieu:
                return {"error": "Suất chiếu không tồn tại", "status": 404}

            update_data = {}
            
            # Kiểm tra và validate phim_id nếu có update (loại bỏ empty string và None)
            if phim_id is not None and str(phim_id).strip():
                phim_id_clean = str(phim_id).strip()
                phim = self.phim_collection.find_one({"_id": phim_id_clean})
                if not phim:
                    return {"error": f"Phim không tồn tại với id='{phim_id_clean}'", "status": 404}
                update_data["phim_id"] = phim_id_clean

            # Kiểm tra và validate rap_id nếu có update (loại bỏ empty string và None)
            if rap_id is not None and str(rap_id).strip():
                rap_id_clean = str(rap_id).strip()
                rap = self.rap_collection.find_one({"_id": rap_id_clean})
                if not rap:
                    return {"error": f"Rạp không tồn tại với id='{rap_id_clean}'", "status": 404}
                update_data["rap_id"] = rap_id_clean
            
            if gia_ve is not None:
                update_data["giaVe"] = gia_ve

            if ten_Phong is not None:
                # Xác định rap_id để kiểm tra (dùng rap_id mới nếu có update, không thì dùng rap_id cũ)
                rap_id_to_check = update_data.get("rap_id") if "rap_id" in update_data else existing_suat_chieu.get("rap_id")
                if rap_id_to_check:
                    # Kiểm tra ten_Phong có tồn tại trong rạp không
                    so_ghe_rap = self._get_so_ghe_from_rap(rap_id_to_check, ten_Phong)
                    if so_ghe_rap == 0:
                        return {"error": f"Không tìm thấy phòng chiếu '{ten_Phong}' trong rạp", "status": 404}
                update_data["ten_Phong"] = ten_Phong

            if gio_bat_dat:
                # Chuyển sang datetime object (Date trong MongoDB)
                try:
                    if 'T' in gio_bat_dat:
                        gio_bat_dat_dt = datetime.fromisoformat(gio_bat_dat.replace('Z', '+00:00'))
                    else:
                        gio_bat_dat_dt = datetime.strptime(gio_bat_dat, "%Y-%m-%d %H:%M:%S")
                    update_data["gioBatDau"] = gio_bat_dat_dt
                except Exception as e:
                    return {"error": f"Format gio_bat_dat không hợp lệ: {str(e)}", "status": 400}

            if gio_ket_thuc:
                # Chuyển sang datetime object (Date trong MongoDB)
                try:
                    if 'T' in gio_ket_thuc:
                        gio_ket_thuc_dt = datetime.fromisoformat(gio_ket_thuc.replace('Z', '+00:00'))
                    else:
                        gio_ket_thuc_dt = datetime.strptime(gio_ket_thuc, "%Y-%m-%d %H:%M:%S")
                    update_data["gioKetThuc"] = gio_ket_thuc_dt
                except Exception as e:
                    return {"error": f"Format gio_ket_thuc không hợp lệ: {str(e)}", "status": 400}
            
            # Kiểm tra trùng lặp nếu có update gioBatDau, gioKetThuc, ten_Phong, phim_id, hoặc rap_id
            if "gioBatDau" in update_data or "gioKetThuc" in update_data or "ten_Phong" in update_data or "phim_id" in update_data or "rap_id" in update_data:
                # Xác định các giá trị để kiểm tra (dùng giá trị mới nếu có update, không thì dùng giá trị cũ)
                phim_id_check = update_data.get("phim_id") if "phim_id" in update_data else existing_suat_chieu.get("phim_id")
                rap_id_check = update_data.get("rap_id") if "rap_id" in update_data else existing_suat_chieu.get("rap_id")
                ten_Phong_check = update_data.get("ten_Phong") if "ten_Phong" in update_data else existing_suat_chieu.get("ten_Phong", "")
                
                # Xác định gioBatDau và gioKetThuc để kiểm tra
                gio_bat_dau_check = update_data.get("gioBatDau") if "gioBatDau" in update_data else existing_suat_chieu.get("gioBatDau")
                gio_ket_thuc_check = update_data.get("gioKetThuc") if "gioKetThuc" in update_data else existing_suat_chieu.get("gioKetThuc")
                
                # Parse datetime nếu chưa phải datetime object
                try:
                    if isinstance(gio_bat_dau_check, datetime):
                        gio_bat_dau_check_dt = gio_bat_dau_check
                    elif isinstance(gio_bat_dau_check, str):
                        if 'T' in gio_bat_dau_check:
                            gio_bat_dau_check_dt = datetime.fromisoformat(gio_bat_dau_check.replace('Z', '+00:00'))
                        else:
                            gio_bat_dau_check_dt = datetime.strptime(gio_bat_dau_check, "%Y-%m-%d %H:%M:%S")
                    else:
                        gio_bat_dau_check_dt = None
                    
                    if isinstance(gio_ket_thuc_check, datetime):
                        gio_ket_thuc_check_dt = gio_ket_thuc_check
                    elif isinstance(gio_ket_thuc_check, str):
                        if 'T' in gio_ket_thuc_check:
                            gio_ket_thuc_check_dt = datetime.fromisoformat(gio_ket_thuc_check.replace('Z', '+00:00'))
                        else:
                            gio_ket_thuc_check_dt = datetime.strptime(gio_ket_thuc_check, "%Y-%m-%d %H:%M:%S")
                    else:
                        gio_ket_thuc_check_dt = None
                    
                    if not gio_bat_dau_check_dt or not gio_ket_thuc_check_dt:
                        return {"error": "Không thể xác định thời gian để kiểm tra trùng lặp", "status": 400}
                    
                except Exception as e:
                    return {"error": f"Không thể parse thời gian: {str(e)}", "status": 400}
                
                # Query các suất chiếu khác (loại trừ chính nó) có cùng phim_id, rap_id, ten_Phong
                query = {
                    "phim_id": phim_id_check,
                    "rap_id": rap_id_check,
                    "ten_Phong": ten_Phong_check,
                    "_id": {"$ne": suat_chieu_id}  # Loại trừ chính suất chiếu đang update
                }
                
                existing_suat_chieus = list(self.suat_chieu_collection.find(query))
                
                # Kiểm tra overlap thời gian với các suất chiếu khác
                for existing_suat in existing_suat_chieus:
                    existing_gio_bat_dau = existing_suat.get("gioBatDau")
                    existing_gio_ket_thuc = existing_suat.get("gioKetThuc")
                    
                    if existing_gio_bat_dau and existing_gio_ket_thuc:
                        try:
                            # Parse datetime từ database
                            if isinstance(existing_gio_bat_dau, datetime):
                                existing_bat_dau_dt = existing_gio_bat_dau
                            elif isinstance(existing_gio_bat_dau, str):
                                if 'T' in existing_gio_bat_dau:
                                    existing_bat_dau_dt = datetime.fromisoformat(existing_gio_bat_dau.replace('Z', '+00:00'))
                                else:
                                    existing_bat_dau_dt = datetime.strptime(existing_gio_bat_dau, "%Y-%m-%d %H:%M:%S")
                            else:
                                continue
                            
                            if isinstance(existing_gio_ket_thuc, datetime):
                                existing_ket_thuc_dt = existing_gio_ket_thuc
                            elif isinstance(existing_gio_ket_thuc, str):
                                if 'T' in existing_gio_ket_thuc:
                                    existing_ket_thuc_dt = datetime.fromisoformat(existing_gio_ket_thuc.replace('Z', '+00:00'))
                                else:
                                    existing_ket_thuc_dt = datetime.strptime(existing_gio_ket_thuc, "%Y-%m-%d %H:%M:%S")
                            else:
                                continue
                            
                            # Kiểm tra overlap
                            if (gio_bat_dau_check_dt < existing_ket_thuc_dt) and (gio_ket_thuc_check_dt > existing_bat_dau_dt):
                                return {
                                    "error": f"Không thể cập nhật: Suất chiếu trùng lặp thời gian với suất '{existing_suat.get('_id')}'. "
                                            f"Thời gian sau khi cập nhật ({gio_bat_dau_check_dt.strftime('%Y-%m-%d %H:%M:%S')} - {gio_ket_thuc_check_dt.strftime('%Y-%m-%d %H:%M:%S')}) "
                                            f"trùng với thời gian đã có ({existing_bat_dau_dt.strftime('%Y-%m-%d %H:%M:%S')} - {existing_ket_thuc_dt.strftime('%Y-%m-%d %H:%M:%S')})",
                                    "status": 400
                                }
                        except Exception as e:
                            # Nếu không parse được datetime thì bỏ qua
                            print(f"WARNING: Không thể parse datetime từ suất chiếu {existing_suat.get('_id')}: {e}")
                            continue
            
            # Thêm updated_at khi cập nhật - dùng datetime object (Date trong MongoDB)
            if update_data:
                update_data["updated_at"] = datetime.utcnow()

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
        """
        DEPRECATED: Function này không còn cần thiết vì gheDaDat được tính động từ Ve collection.
        Giữ lại để backward compatibility nhưng sẽ không cập nhật database nữa.
        Thông tin ghế đã đặt nên được quản lý thông qua Ve collection.
        """
        try:
            existing_suat_chieu = self.suat_chieu_collection.find_one({"_id": suat_chieu_id})
            if not existing_suat_chieu:
                return {"error": "Suất chiếu không tồn tại", "status": 404}

            # Lấy soGhe từ Rap collection
            ten_phong = existing_suat_chieu.get("ten_Phong") or existing_suat_chieu.get("phongChieu", "")
            so_ghe = self._get_so_ghe_from_rap(existing_suat_chieu["rap_id"], ten_phong)
            
            # Lấy gheDaDat thực tế từ Ve collection
            ghe_da_dat_thuc_te = self._get_ghe_da_dat_from_ve(suat_chieu_id)
            
            # So sánh với dữ liệu được truyền vào (có thể dùng để validate)
            if set(ghe_da_dat) != set(ghe_da_dat_thuc_te):
                return {
                    "warning": "Dữ liệu ghế đã đặt không khớp với Ve collection. Sử dụng dữ liệu từ Ve collection.",
                    "ghe_da_dat_from_ve": ghe_da_dat_thuc_te,
                    "ghe_da_dat_requested": ghe_da_dat,
                    "suat_chieu_id": suat_chieu_id,
                    "ghe_trong": so_ghe - len(ghe_da_dat_thuc_te),
                    "status": 200
                }

            # Không cập nhật database vì gheDaDat được tính động từ Ve
            ghe_trong = so_ghe - len(ghe_da_dat_thuc_te)
            return {
                "message": "Thông tin ghế đã đặt được lấy từ Ve collection",
                "suat_chieu_id": suat_chieu_id,
                "ghe_da_dat": ghe_da_dat_thuc_te,
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

            # Kiểm tra vé đã đặt từ Ve collection (loại trừ vé đã hủy)
            ghe_da_dat = self._get_ghe_da_dat_from_ve(suat_chieu_id)
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

            # Lấy soGhe từ Rap collection dựa trên rap_id và ten_Phong
            ten_phong = suat_chieu.get("ten_Phong") or suat_chieu.get("phongChieu", "")
            so_ghe = self._get_so_ghe_from_rap(suat_chieu["rap_id"], ten_phong)
            
            # Lấy gheDaDat từ Ve collection
            ghe_da_dat = self._get_ghe_da_dat_from_ve(suat_chieu_id)
            ghe_trong = so_ghe - len(ghe_da_dat) if so_ghe > 0 else 0

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
                ("ten_Phong", suat_chieu.get("ten_Phong", "")),
                # Xử lý gioBatDau - chuyển datetime object sang ISO format
                ("gioBatDau", suat_chieu.get("gioBatDau").isoformat() if isinstance(suat_chieu.get("gioBatDau"), datetime) else str(suat_chieu.get("gioBatDau", ""))),
                # Xử lý gioKetThuc - chuyển datetime object sang ISO format
                ("gioKetThuc", suat_chieu.get("gioKetThuc").isoformat() if isinstance(suat_chieu.get("gioKetThuc"), datetime) else str(suat_chieu.get("gioKetThuc", ""))),
                ("giaVe", suat_chieu.get("giaVe", 0)),
                ("tongGhe", so_ghe),
                ("gheTrong", ghe_trong),
                ("gheDaDat", ghe_da_dat),
                ("created_at", suat_chieu.get("created_at").isoformat() if isinstance(suat_chieu.get("created_at"), datetime) else str(suat_chieu.get("created_at", ""))),
                ("updated_at", suat_chieu.get("updated_at").isoformat() if isinstance(suat_chieu.get("updated_at"), datetime) else str(suat_chieu.get("updated_at", "")))
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

            # Lấy danh sách suất chiếu, sort theo gioChieu nếu có
            # Nếu một số document không có gioChieu, MongoDB sẽ tự xử lý (null sẽ ở đầu hoặc cuối)
            suat_chieu_list = list(
                self.suat_chieu_collection.find(query)
                .sort("gioChieu", 1)
                .skip(skip)
                .limit(limit)
            )

            result_list = []
            for suat_chieu in suat_chieu_list:
                # Lấy phim_id và rap_id an toàn
                phim_id = suat_chieu.get("phim_id")
                rap_id = suat_chieu.get("rap_id")
                
                if not phim_id or not rap_id:
                    continue  # Bỏ qua document không có phim_id hoặc rap_id
                
                phim = self.phim_collection.find_one({"_id": phim_id})
                rap = self.rap_collection.find_one({"_id": rap_id})

                # Lấy soGhe từ Rap collection dựa trên rap_id và ten_Phong
                ten_phong = suat_chieu.get("ten_Phong") or suat_chieu.get("phongChieu", "")
                so_ghe = self._get_so_ghe_from_rap(rap_id, ten_phong)
                
                # Lấy gheDaDat từ Ve collection
                suat_chieu_id = suat_chieu.get("_id")
                if not suat_chieu_id:
                    ghe_da_dat = []
                else:
                    ghe_da_dat = self._get_ghe_da_dat_from_ve(str(suat_chieu_id))
                ghe_trong = so_ghe - len(ghe_da_dat) if so_ghe > 0 else 0

                # Xử lý gioBatDau
                gio_bat_dau_value = suat_chieu.get("gioBatDau")
                if isinstance(gio_bat_dau_value, datetime):
                    gio_bat_dau_str = gio_bat_dau_value.isoformat()
                else:
                    gio_bat_dau_str = str(gio_bat_dau_value) if gio_bat_dau_value else ""

                # Xử lý gioKetThuc
                gio_ket_thuc_value = suat_chieu.get("gioKetThuc")
                if isinstance(gio_ket_thuc_value, datetime):
                    gio_ket_thuc_str = gio_ket_thuc_value.isoformat()
                else:
                    gio_ket_thuc_str = str(gio_ket_thuc_value) if gio_ket_thuc_value else ""

                suat_chieu_item = OrderedDict([
                    ("id", str(suat_chieu["_id"])),
                    ("phim_ten", phim.get("tenPhim", "") if phim else ""),
                    ("rap_ten", rap.get("tenRap", "") if rap else ""),
                    ("ten_Phong", suat_chieu.get("ten_Phong", "")),
                    ("gioBatDau", gio_bat_dau_str),
                    ("gioKetThuc", gio_ket_thuc_str),
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
            suat_chieu_data.gia_ve,
            suat_chieu_data.phong_chieu,
            suat_chieu_data.gio_bat_dat,
            suat_chieu_data.gio_ket_thuc,
            suat_chieu_data.so_ghe
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
        # Sử dụng các trường được phép: phim_id, rap_id, giaVe, ten_Phong, gioBatDau, gioKetThuc
        phim_id = suat_chieu_data.phim_id
        rap_id = suat_chieu_data.rap_id
        gia_ve = suat_chieu_data.giaVe
        ten_Phong = suat_chieu_data.ten_Phong
        gio_bat_dau = suat_chieu_data.gioBatDau
        gio_ket_thuc = suat_chieu_data.gioKetThuc
        
        # Cập nhật thông tin suất chiếu
        result = lam.update_suat_chieu(
            suat_chieu_id,
            gia_ve,
            phim_id,
            rap_id,
            ten_Phong,
            gio_bat_dau,
            gio_ket_thuc
        )
        
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

