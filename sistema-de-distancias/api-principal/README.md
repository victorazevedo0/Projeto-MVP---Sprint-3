# API Principal - Sistema de Consulta de Endereços e Distâncias

Esta API é o componente principal do sistema de consulta de endereços e cálculo de distâncias. Ela é responsável por consultar o serviço externo ViaCEP para obter informações detalhadas de endereços e se comunicar com a API Secundária para calcular a distância entre dois endereços.

## Arquitetura do Sistema

![Arquitetura do Sistema](https://i.imgur.com/VZUDy6z.png)

A arquitetura do sistema é composta por três componentes principais:

1. **API Principal (Este componente)**: Gerencia requisições dos usuários, consulta o ViaCEP e se comunica com a API Secundária.
2. **API Secundária**: Especializada em cálculos de distâncias entre endereços.
3. **ViaCEP (Serviço externo)**: Fornece dados de endereços a partir de CEPs.

## Funcionalidades

- Consulta de endereços por CEP
- Cálculo de distância entre dois endereços
- Gerenciamento de usuários
- Histórico de consultas realizadas

## Endpoints Principais

- `GET /address/{cep}` - Obtém informações de um endereço por CEP
- `POST /distances` - Calcula a distância entre dois endereços
- `PUT /users/{user_id}` - Atualiza informações de um usuário
- `DELETE /history/{history_id}` - Remove um registro do histórico

## Tecnologias Utilizadas

- Python 3.11
- FastAPI
- SQLite (banco de dados)
- httpx (para requisições HTTP assíncronas)
- Docker para containerização

## Requisitos

- Docker
- Python 3.8+

## Instalação e Execução

### Usando Docker

1. Clone este repositório:
```bash
git clone https://github.com/seu-usuario/api-principal.git
cd api-principal
```

2. Construa e inicie o container Docker:
```bash
docker build -t api-principal .
docker run -p 8000:8000 -e SECONDARY_API_URL=http://api-secundaria:5000 api-principal
```

### Instalação local (sem Docker)

1. Clone este repositório:
```bash
git clone https://github.com/seu-usuario/api-principal.git
cd api-principal
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
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## Variáveis de Ambiente

- `SECONDARY_API_URL`: URL da API Secundária (padrão: http://api-secundaria:5000)
- `DATABASE_URL`: Caminho para o banco de dados SQLite (padrão: addresses.db)

## Documentação da API

Após iniciar a aplicação, acesse a documentação interativa da API em:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Serviço Externo Utilizado

Esta API utiliza o serviço externo ViaCEP para consulta de endereços por CEP.

- **Nome do serviço**: ViaCEP
- **URL do serviço**: https://viacep.com.br/ws/
- **Documentação**: https://viacep.com.br/
- **Licença**: Uso gratuito
- **Formato**: JSON
- **Exemplo de uso**: `https://viacep.com.br/ws/01001000/json/`

## Testes

Para executar os testes (quando implementados):

```bash
pytest
```

## Contribuições

Contribuições são bem-vindas! Para contribuir:

1. Faça um fork do projeto
2. Crie uma branch para sua feature (`git checkout -b feature/nova-feature`)
3. Faça commit das suas alterações (`git commit -m 'Adiciona nova feature'`)
4. Faça push para a branch (`git push origin feature/nova-feature`)
5. Abra um Pull Request