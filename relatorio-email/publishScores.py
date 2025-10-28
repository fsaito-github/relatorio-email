from function_app import app
import azure.functions as func
import logging
import os
import requests

from azure.data.tables import TableClient
from azure.identity import ClientSecretCredential
from azure.core.exceptions import ResourceNotFoundError


# Variáveis de ambiente
TENANT_ID = os.getenv("TENANT_ID")
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
SUBSCRIPTION_ID = os.getenv("SUBSCRIPTION_ID")
# STORAGE_ACCOUNT_NAME = "storagescores"
# TABLE_NAME = "AdvisorScores"


# Endpoint para obeter o token
TOKEN_URL = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/token"

# Função para obter o token de acesso
def get_access_token():
    payload = {
        'grant_type': 'client_credentials',
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'resource': 'https://management.azure.com/'
    }
    response = requests.post(TOKEN_URL, data=payload)
    response.raise_for_status()
    return response.json()['access_token']

# Função para obter a pontuação do Azure Advisor
def get_advisor_score(token, category):
    url = f"https://management.azure.com/subscriptions/{SUBSCRIPTION_ID}/providers/Microsoft.Advisor/advisorScore/{category}?api-version=2025-01-01"
    headers = {'Authorization': f'Bearer {token}'}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    data = response.json()
    try:
        
        score_data = data["properties"]["lastRefreshedScore"]
        return {
                "score": round(score_data["score"], 2),
                "date": score_data["date"]
        }
    except (KeyError, IndexError):
        return {
            "score": None,
            "date": None
        }

def get_scores(token):
    advisor_categories = ["Cost", "HighAvailability", "OperationalExcellence", "Performance", "Security"]
    return {cat: get_advisor_score(token, cat) for cat in advisor_categories}



def registrar_scores_em_tabela(scores):
    from azure.core.exceptions import ClientAuthenticationError, ResourceNotFoundError
    
    # Verificar se as variáveis de ambiente estão configuradas
    if not all([TENANT_ID, CLIENT_ID, CLIENT_SECRET]):
        raise ValueError("Variáveis de ambiente TENANT_ID, CLIENT_ID ou CLIENT_SECRET não estão configuradas")
    
    try:
        credential = ClientSecretCredential(
            tenant_id=TENANT_ID,
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET
        )
        table_url = f"https://storagescores.table.core.windows.net"
        table_client = TableClient(endpoint=table_url, table_name="AdvisorScores", credential=credential)
        
        # Testar a conexão fazendo uma consulta simples
        test_entities = list(table_client.query_entities("PartitionKey eq 'Security'", select=["PartitionKey"], limit=1))
        
    except ClientAuthenticationError as e:
        raise ValueError(f"Falha na autenticação com Azure Storage: {e}")
    except ResourceNotFoundError as e:
        raise ValueError(f"Tabela 'AdvisorScores' não encontrada: {e}")
    except Exception as e:
        raise ValueError(f"Erro ao conectar com Azure Storage: {e}")

    for categoria, dados in scores.items():
        if not dados["score"] or not dados["date"]:
            continue

        # Normalizar a data para formato de dia (YYYY-MM-DD) para evitar duplicatas
        from datetime import datetime
        try:
            # Converter a data da API para datetime e depois para string no formato de dia
            if 'T' in dados["date"]:
                date_obj = datetime.fromisoformat(dados["date"].replace('Z', '+00:00'))
            else:
                date_obj = datetime.strptime(dados["date"], '%Y-%m-%d')
            row_key = date_obj.strftime('%Y-%m-%d')
        except (ValueError, TypeError):
            # Se não conseguir converter, usar a data original
            row_key = dados["date"]
        
        partition_key = categoria

        entidade = {
            "PartitionKey": partition_key,
            "RowKey": row_key,
            "Score": dados["score"],
            "LastRefreshed": dados["date"]  # Manter data/hora original para referência
        }
        
        # Sempre criar/atualizar o registro para garantir que o gráfico tenha dados atualizados
        table_client.upsert_entity(entity=entidade)
        logging.info(f"Score registrado/atualizado para {categoria} em {row_key} com valor {dados['score']}.")
    
@app.route(route="registroScores")
def registroScores(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Processando requisição HTTP para registrar scores do Azure Advisor.')

    
    token = get_access_token()
    scores = get_scores(token)
    registrar_scores_em_tabela(scores)

    return func.HttpResponse("Scores processados e registrados com sucesso.", status_code=200)