from function_app import app
import azure.functions as func
import logging
import os
import requests

from azure.data.tables import TableClient
from azure.identity import DefaultAzureCredential
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
    credential = DefaultAzureCredential()
    table_url = f"https://storagescores.table.core.windows.net"
    table_client = TableClient(endpoint=table_url, table_name="AdvisorScores", credential=credential)

    for categoria, dados in scores.items():
        if not dados["score"] or not dados["date"]:
            continue

        row_key = dados["date"]
        partition_key = categoria

        try:
            table_client.get_entity(partition_key=partition_key, row_key=row_key)
            logging.info(f"Já existe score para {categoria} em {row_key}. Ignorando.")
        except ResourceNotFoundError:
            entidade = {
                "PartitionKey": partition_key,
                "RowKey": row_key,
                "Score": dados["score"],
                "LastRefreshed": dados["date"]
            }
            table_client.create_entity(entity=entidade)
            logging.info(f"Score registrado para {categoria} em {row_key}.")

@app.route(route="registroScores")
def registroScores(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Processando requisição HTTP para registrar scores do Azure Advisor.')

    
    token = get_access_token()
    scores = get_scores(token)
    registrar_scores_em_tabela(scores)

    return func.HttpResponse("Scores processados e registrados com sucesso.", status_code=200)