from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from func_Anh_rap import router_rap
from func_Anh_dashboard import router_dashboard
from func_chi import router as router_chi
from func_lam import router as router_lam
from func_toan import Toan
from func_truc import router as ve_router

#-------call class--------
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router_rap) #anh
app.include_router(router_dashboard)
app.include_router(router_chi) #chi
app.include_router(router_lam) #lam
app.include_router(Toan().router) #toan
app.include_router(ve_router) #Trực

#-------end call class--------


if __name__ == "__main__":
    uvicorn.run((app), host="0.0.0.0", port=8888)