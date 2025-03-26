from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional
import httpx
import sqlite3
import os
import datetime
from contextlib import contextmanager
import uuid
import json
from http import HTTPStatus
import uvicorn

app = FastAPI(title="API Principal - Sistema de Consulta de Endereços e Distâncias")

# Configuração de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuração do banco de dados
DATABASE_URL = os.getenv("DATABASE_URL", "addresses.db")

# Modelos de dados
class Address(BaseModel):
    cep: str
    logradouro: str
    complemento: Optional[str] = None
    bairro: str
    localidade: str
    uf: str
    ibge: Optional[str] = None
    gia: Optional[str] = None
    ddd: Optional[str] = None
    siafi: Optional[str] = None

class DistanceRequest(BaseModel):
    origin_cep: str
    destination_cep: str
    travel_mode: Optional[str] = "direct"  # direct, walking, driving

class DistanceResponse(BaseModel):
    origin: Address
    destination: Address
    distance: float
    unit: str = "km"
    travel_mode: str

class HistoryItem(BaseModel):
    id: str
    query_type: str
    query_data: str
    result: str
    created_at: str

class User(BaseModel):
    id: Optional[str] = None
    name: str = Field(..., min_length=3)
    email: str = Field(..., min_length=5)
    preferences: Optional[dict] = None

class UserUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=3)
    email: Optional[str] = Field(None, min_length=5)
    preferences: Optional[dict] = None

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
        CREATE TABLE IF NOT EXISTS history (
            id TEXT PRIMARY KEY,
            query_type TEXT NOT NULL,
            query_data TEXT NOT NULL,
            result TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """)
        
        conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            preferences TEXT
        )
        """)
        
        conn.execute("""
        CREATE TABLE IF NOT EXISTS addresses (
            cep TEXT PRIMARY KEY,
            logradouro TEXT NOT NULL,
            complemento TEXT,
            bairro TEXT NOT NULL,
            localidade TEXT NOT NULL,
            uf TEXT NOT NULL,
            ibge TEXT,
            gia TEXT,
            ddd TEXT,
            siafi TEXT,
            last_updated TEXT NOT NULL
        )
        """)
        conn.commit()

# Inicializar o banco de dados ao iniciar a aplicação
@app.on_event("startup")
async def startup_event():
    init_db()

# Rotas da API
@app.get("/")
async def root():
    return {"message": "API Principal funcionando. Acesse /docs para ver a documentação."}

@app.get("/address/{cep}", response_model=Address)
async def get_address(cep: str):
    # Remover caracteres não numéricos do CEP
    cep = ''.join(filter(str.isdigit, cep))
    
    if len(cep) != 8:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail="CEP deve conter 8 dígitos")
    
    # Verificar se o endereço está no banco de dados local
    with get_db_connection() as conn:
        result = conn.execute("SELECT * FROM addresses WHERE cep = ?", (cep,)).fetchone()
        
        if result:
            # Converter o resultado para um dicionário
            address_dict = dict(result)
            # Verificar se o endereço foi atualizado recentemente (menos de 30 dias)
            last_updated = datetime.datetime.fromisoformat(address_dict["last_updated"])
            if (datetime.datetime.now() - last_updated).days < 30:
                return Address(**address_dict)
    
    # Se não estiver no banco ou estiver desatualizado, consultar a API do ViaCEP
    async with httpx.AsyncClient() as client:
        response = await client.get(f"https://viacep.com.br/ws/{cep}/json/")
        
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail="Erro ao consultar ViaCEP")
        
        data = response.json()
        
        if "erro" in data and data["erro"]:
            raise HTTPException(status_code=404, detail="CEP não encontrado")
        
        # Salvar o endereço no banco de dados local
        with get_db_connection() as conn:
            now = datetime.datetime.now().isoformat()
            conn.execute("""
            INSERT OR REPLACE INTO addresses 
            (cep, logradouro, complemento, bairro, localidade, uf, ibge, gia, ddd, siafi, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data.get("cep", "").replace("-", ""),
                data.get("logradouro", ""),
                data.get("complemento", ""),
                data.get("bairro", ""),
                data.get("localidade", ""),
                data.get("uf", ""),
                data.get("ibge", ""),
                data.get("gia", ""),
                data.get("ddd", ""),
                data.get("siafi", ""),
                now
            ))
            conn.commit()
            
            # Registrar a consulta no histórico
            history_id = str(uuid.uuid4())
            conn.execute("""
            INSERT INTO history (id, query_type, query_data, result, created_at)
            VALUES (?, ?, ?, ?, ?)
            """, (
                history_id,
                "address_query",
                cep,
                str(data),
                now
            ))
            conn.commit()
        
        return Address(**data)

@app.post("/distances", response_model=DistanceResponse)
async def calculate_distance(request: DistanceRequest):
    # Obter os endereços de origem e destino
    async with httpx.AsyncClient() as client:
        # Obter endereço de origem
        origin_response = await client.get(f"https://viacep.com.br/ws/{request.origin_cep}/json/")
        if origin_response.status_code != 200:
            raise HTTPException(status_code=origin_response.status_code, detail="Erro ao consultar endereço de origem")
        origin_data = origin_response.json()
        if "erro" in origin_data and origin_data["erro"]:
            raise HTTPException(status_code=404, detail="CEP de origem não encontrado")
        
        # Obter endereço de destino
        dest_response = await client.get(f"https://viacep.com.br/ws/{request.destination_cep}/json/")
        if dest_response.status_code != 200:
            raise HTTPException(status_code=dest_response.status_code, detail="Erro ao consultar endereço de destino")
        dest_data = dest_response.json()
        if "erro" in dest_data and dest_data["erro"]:
            raise HTTPException(status_code=404, detail="CEP de destino não encontrado")
        
        # Enviar os dados para a API secundária para calcular a distância
        secondary_api_url = os.getenv("SECONDARY_API_URL", "http://api-secundaria:5000")
        
        # Preparar os dados para enviar à API secundária
        payload = {
            "origin": {
                "city": origin_data["localidade"],
                "state": origin_data["uf"],
                "address": f"{origin_data['logradouro']}, {origin_data['bairro']}"
            },
            "destination": {
                "city": dest_data["localidade"],
                "state": dest_data["uf"],
                "address": f"{dest_data['logradouro']}, {dest_data['bairro']}"
            },
            "mode": request.travel_mode
        }
        
        # Chamar a API secundária
        calc_response = await client.post(f"{secondary_api_url}/calculate", json=payload)
        
        if calc_response.status_code != 200:
            raise HTTPException(
                status_code=calc_response.status_code, 
                detail=f"Erro ao calcular distância: {calc_response.text}"
            )
        
        distance_data = calc_response.json()
        
        # Registrar a consulta no histórico
        with get_db_connection() as conn:
            history_id = str(uuid.uuid4())
            now = datetime.datetime.now().isoformat()
            conn.execute("""
            INSERT INTO history (id, query_type, query_data, result, created_at)
            VALUES (?, ?, ?, ?, ?)
            """, (
                history_id,
                "distance_calculation",
                str(request.dict()),
                str(distance_data),
                now
            ))
            conn.commit()
        
        # Construir a resposta
        response = DistanceResponse(
            origin=Address(**origin_data),
            destination=Address(**dest_data),
            distance=distance_data["distance"],
            unit=distance_data["unit"],
            travel_mode=request.travel_mode
        )
        
        return response

@app.get("/history", response_model=List[HistoryItem])
async def get_history(limit: int = 10, skip: int = 0):
    with get_db_connection() as conn:
        result = conn.execute(
            "SELECT * FROM history ORDER BY created_at DESC LIMIT ? OFFSET ?", 
            (limit, skip)
        ).fetchall()
        
        history_items = [
            HistoryItem(
                id=row["id"],
                query_type=row["query_type"],
                query_data=row["query_data"],
                result=row["result"],
                created_at=row["created_at"]
            )
            for row in result
        ]
        
        return history_items

@app.delete("/history/{history_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_history_item(history_id: str):
    with get_db_connection() as conn:
        result = conn.execute("SELECT id FROM history WHERE id = ?", (history_id,)).fetchone()
        
        if not result:
            raise HTTPException(status_code=404, detail="Histórico não encontrado")
        
        conn.execute("DELETE FROM history WHERE id = ?", (history_id,))
        conn.commit()
    
    return None

@app.post("/users", response_model=User, status_code=status.HTTP_201_CREATED)
async def create_user(user: User):
    user_id = str(uuid.uuid4())
    
    with get_db_connection() as conn:
        # Verificar se o e-mail já está em uso
        existing = conn.execute("SELECT id FROM users WHERE email = ?", (user.email,)).fetchone()
        if existing:
            raise HTTPException(status_code=400, detail="E-mail já cadastrado")
        
        # Criar o usuário
        conn.execute(
            "INSERT INTO users (id, name, email, preferences) VALUES (?, ?, ?, ?)",
            (user_id, user.name, user.email, str(user.preferences or {}))
        )
        conn.commit()
    
    return User(id=user_id, name=user.name, email=user.email, preferences=user.preferences)

@app.put("/users/{user_id}", response_model=User)
async def update_user(user_id: str, user_update: UserUpdate):
    with get_db_connection() as conn:
        # Verificar se o usuário existe
        existing = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Usuário não encontrado")
        
        existing_dict = dict(existing)
        
        # Atualizar apenas os campos fornecidos
        update_fields = []
        params = []
        
        if user_update.name is not None:
            update_fields.append("name = ?")
            params.append(user_update.name)
        
        if user_update.email is not None:
            # Verificar se o novo e-mail já está em uso por outro usuário
            if user_update.email != existing_dict["email"]:
                email_check = conn.execute(
                    "SELECT id FROM users WHERE email = ? AND id != ?", 
                    (user_update.email, user_id)
                ).fetchone()
                if email_check:
                    raise HTTPException(status_code=400, detail="E-mail já cadastrado por outro usuário")
            
            update_fields.append("email = ?")
            params.append(user_update.email)
        
        if user_update.preferences is not None:
            update_fields.append("preferences = ?")
            params.append(str(user_update.preferences))
        
        if update_fields:
            # Construir e executar a query de atualização
            query = f"UPDATE users SET {', '.join(update_fields)} WHERE id = ?"
            params.append(user_id)
            conn.execute(query, params)
            conn.commit()
        
        # Obter os dados atualizados do usuário
        updated = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        updated_dict = dict(updated)
        
        return User(
            id=updated_dict["id"],
            name=updated_dict["name"],
            email=updated_dict["email"],
            preferences = json.loads(updated_dict["preferences"]) if updated_dict["preferences"] else {}
        )

@app.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: str):
    with get_db_connection() as conn:
        # Verificar se o usuário existe
        existing = conn.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Usuário não encontrado")
        
        # Excluir o usuário
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
    
    return None

# Rota de saúde para verificação de funcionamento
@app.get("/health")
async def health_check():
    return {"status": "ok", "timestamp": datetime.datetime.now().isoformat()}

if __name__ == "__main__":    
    uvicorn.run(app, host="0.0.0.0", port=8000)