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

        doc = ezdxf.readfile(file_path)
        msp = doc.modelspace()

        block_details = []
        wire_lengths = {}

        for entity in msp:
            if entity.dxftype() == 'INSERT':
                block_name = entity.dxf.name
                layer = entity.dxf.layer
                x = round(entity.dxf.insert.x, 2)
                y = round(entity.dxf.insert.y, 2)
                block_details.append({"name": block_name, "layer": layer, "x": x, "y": y})

            elif entity.dxftype() in ['LINE', 'LWPOLYLINE']:
                layer_name = entity.dxf.layer
                if any(k in layer_name.lower() for k in ['wire', 'cable', '배선']):
                    try:
                        length = entity.length() / 1000
                        wire_lengths[layer_name] = wire_lengths.get(layer_name, 0) + round(length, 2)
                    except Exception:
                        pass

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "물량산출"
        ws.append(["항목명", "Layer", "X 좌표", "Y 좌표"])

        for item in block_details:
            ws.append([item['name'], item['layer'], item['x'], item['y']])

        ws2 = wb.create_sheet("배선길이")
        ws2.append(["Layer", "길이 (m)"])
        for layer, length in wire_lengths.items():
            ws2.append([layer, length])

        result_path = os.path.join(RESULT_DIR, f"{file_id}_물량산출서.xlsx")
        wb.save(result_path)

        return JSONResponse(content={
            "message": "물량 산출 완료",
            "result_file": result_path,
            "summary": {
                "block_count": len(block_details),
                "wire_layer_count": len(wire_lengths),
                "file_name": f"{file_id}_물량산출서.xlsx"
            }
        })
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/download/{file_name}")
def download_estimate(file_name: str):
    file_path = os.path.join(RESULT_DIR, file_name)
    if os.path.exists(file_path):
        return FileResponse(path=file_path, filename=file_name, media_type='application/octet-stream')
    return JSONResponse(status_code=404, content={"error": "파일을 찾을 수 없습니다."})
