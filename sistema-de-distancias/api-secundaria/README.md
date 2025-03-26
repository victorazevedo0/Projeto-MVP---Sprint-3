# API Secundária - Cálculo de Distâncias entre Endereços

Esta API é um componente especializado do sistema de consulta de endereços e cálculo de distâncias. Ela é responsável por calcular a distância entre dois endereços utilizando algoritmos geográficos.

## Funcionalidades

- Cálculo de distâncias entre endereços utilizando o algoritmo de Haversine
- Suporte a diferentes modos de viagem (linha reta, a pé, de carro)
- Configurações ajustáveis para cálculos
- Histórico de cálculos realizados

## Endpoints

- `POST /calculate` - Calcula a distância entre dois endereços
- `GET /calculations` - Lista cálculos realizados
- `PUT /configurations` - Atualiza configurações do serviço
- `DELETE /calculations/{calculation_id}` - Remove um cálculo do histórico

## Tecnologias Utilizadas

- Python 3.11
- Flask
- SQLite (banco de dados)
- Docker para containerização

## Requisitos

- Docker
- Python 3.8+

## Instalação e Execução

### Usando Docker

1. Clone este repositório:
```bash
git clone https://github.com/seu-usuario/api-secundaria.git
cd api-secundaria
```

2. Construa e inicie o container Docker:
```bash
docker build -t api-secundaria .
docker run -p 5000:5000 api-secundaria
```

### Instalação local (sem Docker)

1. Clone este repositório:
```bash
git clone https://github.com/seu-usuario/api-secundaria.git
cd api-secundaria
```

2. Crie e ative um ambiente virtual:
```bash
python -m venv venv
source venv/bin/activate  # No Windows: venv\Scripts\activate
```

3. Instale as dependências:
```bash
pip install -r requirements.txt
```

4. Execute a aplicação:
```bash
flask run --host=0.0.0.0 --port=5000
```

## Algoritmo de Cálculo de Distância

Esta API utiliza o algoritmo de Haversine para calcular a distância entre dois pontos na Terra usando suas coordenadas de latitude e longitude. O algoritmo leva em consideração a curvatura da Terra e retorna a distância em linha reta.

Para diferentes modos de viagem, aplicamos multiplicadores específicos:
- Linha reta (direct): multiplicador de 1.2
- A pé (walking): multiplicador de 1.4
- De carro (driving): multiplicador de 1.1

## Variáveis de Ambiente

- `DATABASE_URL`: Caminho para o banco de dados SQLite (padrão: distance_calculations.db)

## Testando a API

Você pode testar a API usando curl ou qualquer cliente HTTP:

```bash
curl -X POST http://localhost:5000/calculate \
  -H "Content-Type: application/json" \
  -d '{
    "origin": {
      "city": "São Paulo", 
      "state": "SP", 
      "address": "Avenida Paulista, 1000"
    },
    "destination": {
      "city": "Rio de Janeiro", 
      "state": "RJ", 
      "address": "Avenida Atlântica, 500"
    },
    "mode": "driving"
  }'
```

## Contribuições

Contribuições são bem-vindas! Para contribuir:

1. Faça um fork do projeto
2. Crie uma branch para sua feature (`git checkout -b feature/nova-feature`)
3. Faça commit das suas alterações (`git commit -m 'Adiciona nova feature'`)
4. Faça push para a branch (`git push origin feature/nova-feature`)
5. Abra um Pull Request