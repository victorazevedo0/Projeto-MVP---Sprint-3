from fastapi import FastAPI, HTTPException, Request, Depends
from pydantic import BaseModel
import sqlite3
import math
import os
import uuid
import datetime
from contextlib import contextmanager

app = FastAPI()

# Configuração do banco de dados
DATABASE_URL = os.getenv("DATABASE_URL", "distance_calculations.db")

# Funções de banco de dados
@contextmanager
def get_db_connection():
    conn = sqlite3.connect(DATABASE_URL)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    with get_db_connection() as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS calculations (
            id TEXT PRIMARY KEY,
            origin_city TEXT NOT NULL,
            origin_state TEXT NOT NULL,
            origin_address TEXT NOT NULL,
            destination_city TEXT NOT NULL,
            destination_state TEXT NOT NULL,
            destination_address TEXT NOT NULL,
            mode TEXT NOT NULL,
            distance REAL NOT NULL,
            unit TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """)
        
        conn.execute("""
        CREATE TABLE IF NOT EXISTS configurations (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """)
        
        # Inserir configurações padrão se não existirem
        default_configs = [
            ("direct_multiplier", "1.2", "Multiplicador para ajuste de distância em linha reta"),
            ("walking_multiplier", "1.4", "Multiplicador para ajuste de distância a pé"),
            ("driving_multiplier", "1.1", "Multiplicador para ajuste de distância de carro"),
            ("default_unit", "km", "Unidade padrão para distâncias (km ou mi)")
        ]
        
        for key, value, name in default_configs:
            conn.execute("""
            INSERT OR IGNORE INTO configurations (id, name, value, updated_at)
            VALUES (?, ?, ?, ?)
            """, (key, name, value, datetime.datetime.now().isoformat()))
        
        conn.commit()

# Inicializar o banco de dados ao iniciar a aplicação
init_db()

# Funções auxiliares para cálculo de distância
def get_coordinates(city, state, address):
    city_hash = sum(ord(c) for c in city.lower())
    state_hash = sum(ord(c) for c in state.lower())
    lat = -30 + (city_hash % 25)
    lng = -70 + (state_hash % 35)
    addr_hash = sum(ord(c) for c in address.lower())
    lat_variation = (addr_hash % 100) / 1000
    lng_variation = (addr_hash % 100) / 1000
    return lat + lat_variation, lng + lng_variation

def calculate_haversine_distance(lat1, lon1, lat2, lon2):
    R = 6371.0
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)
    dlon = lon2_rad - lon1_rad
    dlat = lat2_rad - lat1_rad
    a = math.sin(dlat / 2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2)**2
    c = 2 * math.asin(math.sqrt(a))
    distance = R * c
    return distance

def get_config_value(key, default=None):
    with get_db_connection() as conn:
        result = conn.execute("SELECT value FROM configurations WHERE id = ?", (key,)).fetchone()
        if result:
            return result["value"]
        return default

# Modelos Pydantic para validação de dados
class OriginDestination(BaseModel):
    city: str
    state: str
    address: str

class CalculateRequest(BaseModel):
    origin: OriginDestination
    destination: OriginDestination
    mode: str = "direct"

class ConfigurationUpdate(BaseModel):
    configurations: dict

# Rotas da API
@app.get("/")
def home():
    return {
        "message": "API Secundária para cálculo de distâncias funcionando",
        "endpoints": {
            "POST /calculate": "Calcula a distância entre dois endereços",
            "GET /calculations": "Lista cálculos realizados",
            "PUT /configurations": "Atualiza configurações do serviço",
            "DELETE /calculations/{calculation_id}": "Remove um cálculo do histórico"
        }
    }

@app.post("/calculate")
def calculate_distance(request: CalculateRequest):
    origin = request.origin
    destination = request.destination
    mode = request.mode

    try:
        origin_lat, origin_lng = get_coordinates(origin.city, origin.state, origin.address)
        dest_lat, dest_lng = get_coordinates(destination.city, destination.state, destination.address)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao obter coordenadas: {str(e)}")

    base_distance = calculate_haversine_distance(origin_lat, origin_lng, dest_lat, dest_lng)
    multiplier_key = f"{mode}_multiplier"
    multiplier = float(get_config_value(multiplier_key, 1.0))
    distance = base_distance * multiplier
    unit = get_config_value("default_unit", "km")

    if unit.lower() == "mi":
        distance = distance * 0.621371

    distance = round(distance, 2)
    calculation_id = str(uuid.uuid4())
    now = datetime.datetime.now().isoformat()

    with get_db_connection() as conn:
        conn.execute("""
        INSERT INTO calculations 
        (id, origin_city, origin_state, origin_address, 
         destination_city, destination_state, destination_address, 
         mode, distance, unit, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            calculation_id,
            origin.city,
            origin.state,
            origin.address,
            destination.city,
            destination.state,
            destination.address,
            mode,
            distance,
            unit,
            now
        ))
        conn.commit()

    response = {
        "id": calculation_id,
        "origin": {
            "city": origin.city,
            "state": origin.state,
            "coordinates": [origin_lat, origin_lng]
        },
        "destination": {
            "city": destination.city,
            "state": destination.state,
            "coordinates": [dest_lat, dest_lng]
        },
        "distance": distance,
        "unit": unit,
        "mode": mode,
        "created_at": now
    }

    return response

@app.get("/calculations")
def get_calculations(limit: int = 10, offset: int = 0):
    with get_db_connection() as conn:
        result = conn.execute(
            "SELECT * FROM calculations ORDER BY created_at DESC LIMIT ? OFFSET ?", 
            (limit, offset)
        ).fetchall()
        calculations = [dict(row) for row in result]
        return calculations

@app.put("/configurations")
def update_configuration(config_update: ConfigurationUpdate):
    updated_configs = []
    now = datetime.datetime.now().isoformat()

    with get_db_connection() as conn:
        for key, value in config_update.configurations.items():
            existing = conn.execute("SELECT id FROM configurations WHERE id = ?", (key,)).fetchone()
            if existing:
                conn.execute(
                    "UPDATE configurations SET value = ?, updated_at = ? WHERE id = ?",
                    (str(value), now, key)
                )
                updated_configs.append(key)
        conn.commit()

    if not updated_configs:
        raise HTTPException(status_code=400, detail="Nenhuma configuração válida foi fornecida")

    return {"updated": updated_configs, "timestamp": now}

@app.delete("/calculations/{calculation_id}")
def delete_calculation(calculation_id: str):
    with get_db_connection() as conn:
        existing = conn.execute("SELECT id FROM calculations WHERE id = ?", (calculation_id,)).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Cálculo não encontrado")
        conn.execute("DELETE FROM calculations WHERE id = ?", (calculation_id,))
        conn.commit()
    return {"status": "deleted", "id": calculation_id}

@app.get("/health")
def health_check():
    return {"status": "ok", "timestamp": datetime.datetime.now().isoformat()}

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)