from fastapi import FastAPI, File, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import shutil
import os
import uuid
import ezdxf
import openpyxl

app = FastAPI()

UPLOAD_DIR = "./uploads"
RESULT_DIR = "./results"

# 디렉토리 생성
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(RESULT_DIR, exist_ok=True)

app.mount("/", StaticFiles(directory="static", html=True), name="static")

@app.post("/upload/")
async def upload_dwg(file: UploadFile = File(...)):
    try:
        file_id = str(uuid.uuid4())
        file_path = os.path.join(UPLOAD_DIR, f"{file_id}_{file.filename}")

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # DWG 파일 읽기
        doc = ezdxf.readfile(file_path)
        msp = doc.modelspace()

        block_counts = {}
        wire_length = 0.0

        for entity in msp:
            if entity.dxftype() == 'INSERT':
                block_name = entity.dxf.name
                block_counts[block_name] = block_counts.get(block_name, 0) + 1
            elif entity.dxftype() in ['LINE', 'LWPOLYLINE']:
                layer_name = entity.dxf.layer.lower()
                if 'wire' in layer_name or 'cable' in layer_name or '배선' in layer_name:
                    try:
                        length = entity.length()
                        wire_length += length
                    except Exception:
                        pass

        # 물량 산출표 생성
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "물량산출"
        ws.append(["항목명", "수량"])

        for name, count in block_counts.items():
            ws.append([name, count])

        if wire_length > 0:
            wire_m = round(wire_length / 1000, 2)  # mm -> m
            ws.append(["배선길이 (m)", wire_m])

        result_path = os.path.join(RESULT_DIR, f"{file_id}_물량산출서.xlsx")
        wb.save(result_path)

        return JSONResponse(content={
            "message": "물량 산출 완료",
            "result_file": result_path
        })
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/download/{file_name}")
def download_estimate(file_name: str):
    file_path = os.path.join(RESULT_DIR, file_name)
    if os.path.exists(file_path):
        return FileResponse(path=file_path, filename=file_name, media_type='application/octet-stream')
    return JSONResponse(status_code=404, content={"error": "파일을 찾을 수 없습니다."})
