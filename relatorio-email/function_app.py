import azure.functions as func
import logging
import os
import requests
from grafico_score import gerar_grafico_multicategorias
from mini_graficos_score import obter_dados_evolucao_todas_categorias
#from dotenv import load_dotenv
from jinja2 import Template

#load_dotenv()

# Variáveis de Ambiente
TENANT_ID = os.getenv("TENANT_ID")
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
SUBSCRIPTION_ID = os.getenv("SUBSCRIPTION_ID")

# Azure AD token endpoint
TOKEN_URL = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/token"

# Constantes
ADVISOR_CATEGORIES = ["Security", "Cost", "HighAvailability", "OperationalExcellence", "Performance"]

# Função para obter o Azure access token
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
     

# Função para obter recomendações de alto impacto ("High")
def get_recommendations(token):
    url = f"https://management.azure.com/subscriptions/{SUBSCRIPTION_ID}/providers/Microsoft.Advisor/recommendations?api-version=2025-01-01"
    headers = {'Authorization': f'Bearer {token}'}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    data = response.json()

    # Usar um dicionário para contar recomendações por (descrição, categoria)
    rec_count = {}
    for item in data.get("value", []):
        category = item["properties"]["category"]
        impact = item["properties"]["impact"]
        if category in ADVISOR_CATEGORIES and impact == "High":
            description = item["properties"]["shortDescription"]["problem"]
            key = (description, category)
            rec_count[key] = rec_count.get(key, 0) + 1

    # Construir a lista de recomendações com descrições e contagens únicas
    recommendations = [
        {
            "description": desc,
            "category": cat,
            "count": count
        }
        for (desc, cat), count in rec_count.items()
    ]

    return recommendations

# Função para obter contadores de recomendações por categoria e impacto
def get_recommendations_summary(token):
    """
    Obtém resumo de quantidades de recomendações por categoria e impacto
    Considera apenas a recomendação mais recente para cada recurso/problema
    
    Returns:
        dict: Dicionário com contadores por categoria e impacto
    """
    url = f"https://management.azure.com/subscriptions/{SUBSCRIPTION_ID}/providers/Microsoft.Advisor/recommendations?api-version=2025-01-01"
    headers = {'Authorization': f'Bearer {token}'}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    data = response.json()

    # Inicializar contadores
    summary = {}
    for category in ADVISOR_CATEGORIES:
        summary[category] = {"High": 0, "Medium": 0, "Low": 0}

    # Dicionário para armazenar apenas a recomendação mais recente por chave única
    latest_recommendations = {}
    
    # Processar todas as recomendações e manter apenas a mais recente de cada
    for item in data.get("value", []):
        category = item["properties"]["category"]
        impact = item["properties"]["impact"]
        
        if category in ADVISOR_CATEGORIES:
            # Criar chave única baseada no recurso afetado e problema
            resource_id = item["properties"].get("resourceId", "")
            problem = item["properties"]["shortDescription"]["problem"]
            solution = item["properties"]["shortDescription"].get("solution", "")
            
            # Chave única para identificar recomendações similares
            unique_key = f"{category}_{resource_id}_{problem}_{solution}"
            
            # Obter data da última atualização
            last_updated = item["properties"].get("lastUpdated", "1900-01-01T00:00:00Z")
            
            # Se é a primeira vez que vemos esta chave ou se é mais recente
            if unique_key not in latest_recommendations or last_updated > latest_recommendations[unique_key]["lastUpdated"]:
                latest_recommendations[unique_key] = {
                    "category": category,
                    "impact": impact,
                    "lastUpdated": last_updated
                }

    # Contar apenas as recomendações mais recentes
    for rec in latest_recommendations.values():
        category = rec["category"]
        impact = rec["impact"]
        summary[category][impact] += 1

    return summary

#Funtion to get Service health Alerts
def query_resource_graph(token):
    url = "https://management.azure.com/providers/Microsoft.ResourceGraph/resources?api-version=2021-03-01"
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }

    query = """
    alertsmanagementresources
    | extend MonitorService = tostring(properties.essentials.monitorService)
    | where MonitorService =~ 'ServiceHealth'
    | extend activitylogproperties = (properties.context.context.activityLog.properties)
    | extend Title = tostring(activitylogproperties.['title'])
    | extend Service = tostring(activitylogproperties.['service'])
    | extend status = tostring(properties.context.context.activityLog.status)
    | extend IncidentType = tostring(activitylogproperties.['incidentType'])
    | project startDateTime = todatetime(properties.essentials.startDateTime), monitorCondition = tostring(properties.essentials.monitorCondition), subscriptionId, Title, Service, status, IncidentType
    | summarize count() by Title, Service, subscriptionId
    | order by ['count_'] desc
    """

    body = {
        "query": query,
        "subscriptions": [SUBSCRIPTION_ID]
    }

    response = requests.post(url, headers=headers, json=body)
    response.raise_for_status()
    result = response.json()

    # Garante que 'data' seja sempre um dicionário com 'columns' e 'rows'
    if isinstance(result.get("data"), list):
        result["data"] = {
            "columns": ["Title", "Service", "subscriptionId", "count_"],
            "rows": [
                [item["Title"], item["Service"], item["subscriptionId"], item["count_"]]
                for item in result["data"]
            ]
        }
    elif isinstance(result.get("data"), dict):
        result["data"].setdefault("columns", [])
        result["data"].setdefault("rows", [])

    return result

# Função para obter o access token do Log Analytics
def get_access_law_token():
    payload = {
        'grant_type': 'client_credentials',
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'resource': 'https://api.loganalytics.io/'
    }
    response = requests.post(TOKEN_URL, data=payload)
    response.raise_for_status()
    return response.json()['access_token']

# Função para obter informações de certificados do Log Analytics
def get_kv_certificates_expiration(token):
    workspace_id = "63ffa334-8ba1-430d-b851-8a0895443ae3"
    url = f"https://api.loganalytics.azure.com/v1/workspaces/{workspace_id}/query"
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }

    query = """
    let ItemNameRegex = @"(?i)https://.+?.vault.azure.net/.+?/(.*)";
    KVCertificateInfo_CL
    | summarize arg_max(TimeGenerated, *) by ItemID
    | where ItemType in ("Certificate")
    | extend Name = extract(ItemNameRegex, 1, ItemID)
    | extend HasExpirationDate = iif(Expiration > todatetime("1970-01-01"), true, false)
    | extend DaysToExpire = iif(HasExpirationDate == true, toint((Expiration - now()) / 1d), -99999)
    | extend State = iif(DaysToExpire == -99999, "No Expiration", iif(DaysToExpire <= 30, "Critical", iif(DaysToExpire <= 60, "Warning", "Healthy")))
    | extend Subscription = extract(@"/subscriptions/(.+?)/", 1, KVResourceID)
    | project State, Subscription, KVResourceID, Name, ItemType, DaysToExpire
    | top 1000 by DaysToExpire asc
    """

    body = { "query": query }
    response = requests.post(url, headers=headers, json=body)
    response.raise_for_status()
    result = response.json()

    certs = []
    if "tables" in result and result["tables"]:
        columns = [col["name"] for col in result["tables"][0]["columns"]]
        for row in result["tables"][0]["rows"]:
            certs.append(dict(zip(columns, row)))

    return certs

# Função para obter informações de outros itens KV do Log Analytics
def get_kv_items_expiration(token):
    workspace_id = "63ffa334-8ba1-430d-b851-8a0895443ae3"
    url = f"https://api.loganalytics.azure.com/v1/workspaces/{workspace_id}/query"
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }

    query = """
    let ItemNameRegex = @"(?i)https://.+?.vault.azure.net/.+?/(.*)";
    KVCertificateInfo_CL
    | summarize arg_max(TimeGenerated, *) by ItemID
    | where ItemType has_any ("Key", "Secret")
    | extend Name = extract(ItemNameRegex, 1, ItemID)
    | extend HasExpirationDate = iif(Expiration > todatetime("1970-01-01"), true, false)
    | extend DaysToExpire = iif(HasExpirationDate == true, toint((Expiration - now()) / 1d), -99999)
    | extend State = iif(DaysToExpire == -99999, "No Expiration", iif(DaysToExpire <= 30, "Critical", iif(DaysToExpire <= 60, "Warning", "Healthy")))
    | extend Subscription = extract(@"/subscriptions/(.+?)/", 1, KVResourceID)
    | project State, Subscription, KVResourceID, Name, ItemType, DaysToExpire
    | top 1000 by DaysToExpire asc
    """

    body = { "query": query }
    response = requests.post(url, headers=headers, json=body)
    response.raise_for_status()
    result = response.json()

    kv_items = []
    if "tables" in result and result["tables"]:
        columns = [col["name"] for col in result["tables"][0]["columns"]]
        for row in result["tables"][0]["rows"]:
            kv_items.append(dict(zip(columns, row)))

    return kv_items

# Função para gerar relatório HTML
def generate_html(recommendations_by_category, recommendations_summary, service_health, certificates, kv_items):
    
    # Obter dados de evolução para todos os cards
    dados_evolucao = obter_dados_evolucao_todas_categorias()
    
# Categorizar certificados por faixa de vencimento
    expired = [c for c in certificates if c['DaysToExpire'] < 0]
    exp_0_30 = [c for c in certificates if 0 <= c['DaysToExpire'] <= 30]
    exp_31_60 = [c for c in certificates if 31 <= c['DaysToExpire'] <= 60]
    exp_61_90 = [c for c in certificates if 61 <= c['DaysToExpire'] <= 90]

    cert_groups = [
        ("Vencidos", expired),
        ("Expira em 0–30 dias", exp_0_30),
        ("Expira em 31–60 dias", exp_31_60),
        ("Expira em 61–90 dias", exp_61_90)
    ]

   # Categorizar KV items por faixa de vencimento
    expired = [c for c in kv_items if c['DaysToExpire'] < 0]
    exp_0_30 = [c for c in kv_items if 0 <= c['DaysToExpire'] <= 30]
    exp_31_60 = [c for c in kv_items if 31 <= c['DaysToExpire'] <= 60]
    exp_61_90 = [c for c in kv_items if 61 <= c['DaysToExpire'] <= 90]

    kv_items_groups = [
        ("Vencidos", expired),
        ("Expira em 0–30 dias", exp_0_30),
        ("Expira em 31–60 dias", exp_31_60),
        ("Expira em 61–90 dias", exp_61_90)
    ] 

    # Gerar gráfico de histórico de scores
    grafico_base64 = gerar_grafico_multicategorias()

    html_template = """
    <html>
        <head>
            <meta charset="UTF-8">
            <title>Relatório Semanal</title>
        </head>

        <body style="font-family: Arial, sans-serif; background-color: white; padding: 20px;">
            <h2 style="color: #324469;">Relatório Semanal</h2>

            <h3 style="margin-top: 30px; color: #324469;">Azure Advisor Scores</h3>
            <table width="100%" cellpadding="0" cellspacing="0" border="0">
                <tr>
                    {% for categoria_key in ["Security", "Cost", "HighAvailability", "OperationalExcellence", "Performance"] %}
                    <td style="background-color: #f4f4f4; border-radius: 12px; padding: 15px; width: 18%; text-align: center; box-shadow: 0 4px 8px rgba(0,0,0,0.1); position: relative;">
                        <!-- Cabeçalho do card -->
                        <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-bottom: 8px;">
                            <tr>
                                <td style="font-size: 12px; font-weight: bold; color: #324469; text-transform: uppercase; letter-spacing: 0.5px;">
                                    {{ dados_evolucao[categoria_key].nome_pt }}
                                </td>
                                <td style="text-align: right;">
                                    <!-- Indicador de evolução -->
                                    {% if dados_evolucao[categoria_key].tendencia == 'up' %}
                                        <span style="font-size: 10px; color: #10B981; font-weight: bold;">
                                            ▲ {% set abs_var = dados_evolucao[categoria_key].variacao_percentual if dados_evolucao[categoria_key].variacao_percentual >= 0 else -dados_evolucao[categoria_key].variacao_percentual %}{{ abs_var }}%
                                        </span>
                                    {% elif dados_evolucao[categoria_key].tendencia == 'down' %}
                                        <span style="font-size: 10px; color: #EF4444; font-weight: bold;">
                                            ▼ {% set abs_var = dados_evolucao[categoria_key].variacao_percentual if dados_evolucao[categoria_key].variacao_percentual >= 0 else -dados_evolucao[categoria_key].variacao_percentual %}{{ abs_var }}%
                                        </span>
                                    {% else %}
                                        <span style="font-size: 10px; color: #6B7280; font-weight: bold;">
                                            ● 0%
                                        </span>
                                    {% endif %}
                                </td>
                            </tr>
                        </table>
                        
                        <!-- Score principal -->
                        <div style="font-size: 28px; font-weight: bold; color: #1F2937; margin-bottom: 8px;">
                            {{ dados_evolucao[categoria_key].score_atual }}%
                        </div>
                        
                        <!-- Mini-gráfico -->
                        <div style="height: 40px; text-align: center; margin: 5px 0;">
                            {% if dados_evolucao[categoria_key].mini_grafico_base64 %}
                                <img src="data:image/png;base64,{{ dados_evolucao[categoria_key].mini_grafico_base64 }}" 
                                     alt="Evolução {{ dados_evolucao[categoria_key].nome_pt }}" 
                                     style="max-width: 100%; height: 35px; opacity: 0.8; vertical-align: middle;" />
                            {% else %}
                                <div style="height: 35px; background-color: #D1D5DB; border-radius: 4px; width: 100%;"></div>
                            {% endif %}
                        </div>
                    </td>
                    {% if not loop.last %}
                        <td style="width: 13px;"></td>
                    {% endif %}
                    {% endfor %}
                </tr>    
            </table>

            <h3 style="margin-top: 30px; color: #324469;">Histórico de Scores por Categoria</h3>
            <div style="text-align: center; margin-bottom: 30px;">
                <img src="data:image/png;base64,{{ grafico_base64 }}" alt="Histórico de Scores" style="max-width:100%; height:auto; border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.1);" />
            </div>

            <h3 style="margin-top: 30px; color: #324469;">Resumo de Recomendações por Impacto</h3>
            <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-bottom: 20px;">
                <tr>
                    {% for category in ["Security", "Cost", "HighAvailability", "OperationalExcellence", "Performance"] %}
                        <td width="18%" valign="top" style="background-color: #f4f4f4; padding: 15px; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); text-align: center;">
                            <div style="font-size: 14px; font-weight: bold; margin-bottom: 10px; color: #324469;">
                                {{ category_names[category] }}
                            </div>
                            <!-- High Impact -->
                            <table width="100%" cellpadding="4" cellspacing="0" border="0" style="margin-bottom: 3px; background-color: #FEE2E2; border-radius: 4px; border-left: 4px solid #EF4444;">
                                <tr>
                                    <td style="font-size: 11px; font-weight: bold; color: #7F1D1D;">High</td>
                                    <td style="font-size: 11px; font-weight: bold; color: #7F1D1D; text-align: right;">{{ recommendations_summary[category]['High'] }}</td>
                                </tr>
                            </table>
                            <!-- Medium Impact -->
                            <table width="100%" cellpadding="4" cellspacing="0" border="0" style="margin-bottom: 3px; background-color: #FEF3C7; border-radius: 4px; border-left: 4px solid #F59E0B;">
                                <tr>
                                    <td style="font-size: 11px; font-weight: bold; color: #92400E;">Medium</td>
                                    <td style="font-size: 11px; font-weight: bold; color: #92400E; text-align: right;">{{ recommendations_summary[category]['Medium'] }}</td>
                                </tr>
                            </table>
                            <!-- Low Impact -->
                            <table width="100%" cellpadding="4" cellspacing="0" border="0" style="background-color: #DCFCE7; border-radius: 4px; border-left: 4px solid #10B981;">
                                <tr>
                                    <td style="font-size: 11px; font-weight: bold; color: #166534;">Low</td>
                                    <td style="font-size: 11px; font-weight: bold; color: #166534; text-align: right;">{{ recommendations_summary[category]['Low'] }}</td>
                                </tr>
                            </table>
                        </td>
                        {% if not loop.last %}
                            <td style="width: 10px;"></td>
                        {% endif %}
                    {% endfor %}
                </tr>
            </table>

            <h3 style="margin-top: 30px; color: #324469;">Recomendações "High" por Categoria</h3>
            <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-bottom: 20px;">
                <tr>
                    {% for category in ["Security", "Cost", "HighAvailability"] %}
                        <td width="32%" valign="top" style="background-color: #f4f4f4; padding: 15px; border-radius: 12px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); margin-right: 2%;">
                            <div style="margin-bottom: 12px; padding: 8px; background-color: #324469; border-radius: 8px; text-align: center;">
                                <div style="font-size: 14px; font-weight: bold; color: white;">
                                    {{ category_names[category] }}
                                </div>
                            </div>
                            {% for rec in recommendations.get(category, []) %}
                                <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-bottom: 8px; background-color: white; border-radius: 6px; border-left: 4px solid #EF4444;">
                                    <tr>
                                        <td width="20" style="padding: 8px 8px 8px 8px; color: #EF4444; font-weight: bold; font-size: 14px; vertical-align: top;">●</td>
                                        <td style="padding: 8px 8px 8px 0; font-size: 12px; color: #374151; line-height: 1.4;">{{ rec.description }}</td>
                                    </tr>
                                </table>
                            {% else %}
                                <table width="100%" cellpadding="15" cellspacing="0" border="0" style="background-color: white; border-radius: 6px; border: 2px dashed #D1D5DB;">
                                    <tr>
                                        <td style="text-align: center;">
                                            <span style="color: #10B981; font-size: 16px;">✓</span>
                                            <span style="font-size: 12px; color: #6B7280; font-style: italic; margin-left: 8px;">Nenhuma recomendação</span>
                                        </td>
                                    </tr>
                                </table>
                            {% endfor %}
                        </td>
                        {% if not loop.last %}
                            <td style="width: 13px;"></td>
                        {% endif %}
                    {% endfor %}
                </tr>
            </table>

            <table width="100%" cellpadding="0" cellspacing="0" border="0">
                <tr>
                    {% for category in ["OperationalExcellence", "Performance"] %}
                        <td width="48%" valign="top" style="background-color: #f4f4f4; padding: 15px; border-radius: 12px; box-shadow: 0 4px 8px rgba(0,0,0,0.1);">
                            <div style="margin-bottom: 12px; padding: 8px; background-color: #324469; border-radius: 8px; text-align: center;">
                                <div style="font-size: 14px; font-weight: bold; color: white;">
                                    {{ category_names[category] }}
                                </div>
                            </div>
                            {% for rec in recommendations.get(category, []) %}
                                <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-bottom: 8px; background-color: white; border-radius: 6px; border-left: 4px solid #EF4444;">
                                    <tr>
                                        <td width="20" style="padding: 8px 8px 8px 8px; color: #EF4444; font-weight: bold; font-size: 14px; vertical-align: top;">●</td>
                                        <td style="padding: 8px 8px 8px 0; font-size: 12px; color: #374151; line-height: 1.4;">{{ rec.description }}</td>
                                    </tr>
                                </table>
                            {% else %}
                                <table width="100%" cellpadding="15" cellspacing="0" border="0" style="background-color: white; border-radius: 6px; border: 2px dashed #D1D5DB;">
                                    <tr>
                                        <td style="text-align: center;">
                                            <span style="color: #10B981; font-size: 16px;">✓</span>
                                            <span style="font-size: 12px; color: #6B7280; font-style: italic; margin-left: 8px;">Nenhuma recomendação</span>
                                        </td>
                                    </tr>
                                </table>
                            {% endfor %}
                        </td>
                        {% if not loop.last %}
                            <td style="width: 13px;"></td>
                        {% endif %}
                    {% endfor %}
                </tr>
            </table>            <h3 style="margin-top: 30px; color: #324469;">Service Health</h3>
            <div style="background-color: #f4f4f4; border-radius: 12px; padding: 20px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); overflow: hidden;">
                <table style="width:100%; border-collapse: collapse; background-color: transparent;">
                    <thead>
                        <tr style="background-color: #324469; color: white;">
                            <th style="padding: 12px 15px; font-size: 13px; font-weight: bold; text-align: left; border-radius: 8px 0 0 0;">Alerta</th>
                            <th style="padding: 12px 15px; font-size: 13px; font-weight: bold; text-align: left;">Serviço</th>
                            <th style="padding: 12px 15px; font-size: 13px; font-weight: bold; text-align: center;">Itens afetados</th>
                            <th style="padding: 12px 15px; font-size: 13px; font-weight: bold; text-align: left; border-radius: 0 8px 0 0;">Subscription ID</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for item in service_health %}
                        <tr style="background-color: white; border-bottom: 1px solid #E5E7EB;">
                            <td style="padding: 12px 15px; font-size: 12px; color: #374151; font-weight: 500;">{{ item.Title }}</td>
                            <td style="padding: 12px 15px; font-size: 12px; color: #6B7280;">{{ item.Service }}</td>
                            <td style="padding: 12px 15px; font-size: 12px; color: #374151; text-align: center; font-weight: bold;">
                                <span style="background-color: #FEE2E2; color: #DC2626; padding: 4px 8px; border-radius: 12px; font-size: 11px;">{{ item.count_ }}</span>
                            </td>
                            <td style="padding: 12px 15px; font-size: 11px; color: #6B7280; font-family: monospace;">{{ item.subscriptionId }}</td>
                        </tr>
                        {% else %}
                        <tr style="background-color: white;">
                            <td colspan="4" style="padding: 20px; text-align: center; font-size: 13px; color: #6B7280; font-style: italic;">
                                <span style="color: #10B981; font-size: 16px; margin-right: 8px;">✓</span>
                                Nenhum incidente encontrado
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>

            <h3 style="margin-top: 30px; color: #324469;">Expiração de Certificados</h3>
            <table width="100%" cellpadding="0" cellspacing="0" border="0">
                <tr>
                    {% for title, certs in cert_groups %}
                        <td width="24%" valign="top" style="background-color: #f4f4f4; padding: 15px; border-radius: 12px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); margin-right: 2%;">
                            <table width="100%" cellpadding="8" cellspacing="0" border="0" style="margin-bottom: 12px; background-color: #324469; border-radius: 8px;">
                                <tr>
                                    <td style="font-size: 13px; font-weight: bold; color: white; text-align: center;">
                                        {{ title }}
                                    </td>
                                </tr>
                            </table>
                            {% for cert in certs %}
                                {% if cert.DaysToExpire < 0 %}
                                    {% set status_color = "#DC2626" %}
                                    {% set bg_color = "#FEE2E2" %}
                                    {% set icon = "⚠" %}
                                {% elif cert.DaysToExpire <= 30 %}
                                    {% set status_color = "#DC2626" %}
                                    {% set bg_color = "#FEE2E2" %}
                                    {% set icon = "🔴" %}
                                {% elif cert.DaysToExpire <= 60 %}
                                    {% set status_color = "#D97706" %}
                                    {% set bg_color = "#FEF3C7" %}
                                    {% set icon = "🟡" %}
                                {% else %}
                                    {% set status_color = "#059669" %}
                                    {% set bg_color = "#DCFCE7" %}
                                    {% set icon = "🟢" %}
                                {% endif %}
                                <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-bottom: 6px; background-color: {{ bg_color }}; border-radius: 6px; border-left: 4px solid {{ status_color }};">
                                    <tr>
                                        <td width="25" style="padding: 8px 8px 8px 8px; vertical-align: middle;">{{ icon }}</td>
                                        <td style="padding: 8px 8px 8px 0; vertical-align: middle;">
                                            <div style="font-size: 11px; font-weight: bold; color: {{ status_color }};">{{ cert.Name }}</div>
                                            <div style="font-size: 10px; color: #6B7280;">{{ cert.DaysToExpire }} dias</div>
                                        </td>
                                    </tr>
                                </table>
                            {% else %}
                                <table width="100%" cellpadding="15" cellspacing="0" border="0" style="background-color: white; border-radius: 6px; border: 2px dashed #D1D5DB;">
                                    <tr>
                                        <td style="text-align: center;">
                                            <span style="color: #10B981; font-size: 11px; margin-right: 8px;">✓</span>
                                            <span style="font-size: 11px; color: #6B7280; font-style: italic;">Nenhum certificado</span>
                                        </td>
                                    </tr>
                                </table>
                            {% endfor %}
                        </td>
                        {% if not loop.last %}
                            <td style="width: 8px;"></td>
                        {% endif %}
                    {% endfor %}
                </tr>
            </table>  

            <h3 style="margin-top: 30px; color: #324469;">Expiração Itens de Key Vault</h3>
            <table width="100%" cellpadding="0" cellspacing="0" border="0">
                <tr>
                    {% for title, kv_items in kv_items_groups %}
                        <td width="24%" valign="top" style="background-color: #f4f4f4; padding: 15px; border-radius: 12px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); margin-right: 2%;">
                            <table width="100%" cellpadding="8" cellspacing="0" border="0" style="margin-bottom: 12px; background-color: #324469; border-radius: 8px;">
                                <tr>
                                    <td style="font-size: 13px; font-weight: bold; color: white; text-align: center;">
                                        {{ title }}
                                    </td>
                                </tr>
                            </table>
                            {% for kv_item in kv_items %}
                                {% if kv_item.DaysToExpire < 0 %}
                                    {% set status_color = "#DC2626" %}
                                    {% set bg_color = "#FEE2E2" %}
                                    {% set icon = "⚠" %}
                                {% elif kv_item.DaysToExpire <= 30 %}
                                    {% set status_color = "#DC2626" %}
                                    {% set bg_color = "#FEE2E2" %}
                                    {% set icon = "🔴" %}
                                {% elif kv_item.DaysToExpire <= 60 %}
                                    {% set status_color = "#D97706" %}
                                    {% set bg_color = "#FEF3C7" %}
                                    {% set icon = "🟡" %}
                                {% else %}
                                    {% set status_color = "#059669" %}
                                    {% set bg_color = "#DCFCE7" %}
                                    {% set icon = "🟢" %}
                                {% endif %}
                                <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-bottom: 6px; background-color: {{ bg_color }}; border-radius: 6px; border-left: 4px solid {{ status_color }};">
                                    <tr>
                                        <td width="25" style="padding: 8px 8px 8px 8px; vertical-align: middle;">{{ icon }}</td>
                                        <td style="padding: 8px 8px 8px 0; vertical-align: middle;">
                                            <div style="font-size: 11px; font-weight: bold; color: {{ status_color }};">{{ kv_item.Name }}</div>
                                            <div style="font-size: 10px; color: #6B7280;">{{ kv_item.DaysToExpire }} dias - {{ kv_item.ItemType }}</div>
                                        </td>
                                    </tr>
                                </table>
                            {% else %}
                                <table width="100%" cellpadding="15" cellspacing="0" border="0" style="background-color: white; border-radius: 6px; border: 2px dashed #D1D5DB;">
                                    <tr>
                                        <td style="text-align: center;">
                                            <span style="color: #10B981; font-size: 11px; margin-right: 8px;">✓</span>
                                            <span style="font-size: 11px; color: #6B7280; font-style: italic;">Nenhum item</span>
                                        </td>
                                    </tr>
                                </table>
                            {% endfor %}
                        </td>
                        {% if not loop.last %}
                            <td style="width: 8px;"></td>
                        {% endif %}
                    {% endfor %}
                </tr>
            </table>        </body>
    </html>
    """
    template = Template(html_template)
    return template.render(
        dados_evolucao=dados_evolucao,
        recommendations=recommendations_by_category,
        recommendations_summary=recommendations_summary,
        category_names={
            "Security": "Segurança",
            "Cost": "Custos",
            "HighAvailability": "Resiliência",
            "OperationalExcellence": "Exc. Operacional",
            "Performance": "Performance"
        },
        service_health=service_health,
        cert_groups=cert_groups,
        kv_items_groups=kv_items_groups,
        grafico_base64=grafico_base64
)

# Azure Function App

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)

@app.route(route="testConnection")
def testConnection(req: func.HttpRequest) -> func.HttpResponse:
    """Função para testar a conexão com Azure Storage"""
    logging.info('Testando conexão com Azure Storage...')
    
    try:
        from azure.data.tables import TableClient
        from azure.identity import ClientSecretCredential
        from azure.core.exceptions import ClientAuthenticationError, ResourceNotFoundError
        
        # Verificar variáveis de ambiente
        if not all([TENANT_ID, CLIENT_ID, CLIENT_SECRET]):
            return func.HttpResponse(
                "Variáveis de ambiente não configuradas",
                status_code=500
            )
        
        # Testar autenticação
        credential = ClientSecretCredential(
            tenant_id=TENANT_ID,
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET
        )
        
        table_url = "https://storagescores.table.core.windows.net"
        table_client = TableClient(endpoint=table_url, table_name="AdvisorScores", credential=credential)
        
        # Testar consulta
        test_entities = list(table_client.query_entities("PartitionKey eq 'Security'", select=["PartitionKey"], limit=1))
        
        return func.HttpResponse(
            f"Conexão com Azure Storage bem-sucedida! Encontradas {len(test_entities)} entidades de teste.",
            status_code=200
        )
        
    except ClientAuthenticationError as e:
        return func.HttpResponse(
            f"Erro de autenticação: {e}",
            status_code=401
        )
    except ResourceNotFoundError as e:
        return func.HttpResponse(
            f"Tabela não encontrada: {e}",
            status_code=404
        )
    except Exception as e:
        return func.HttpResponse(
            f"Erro inesperado: {e}",
            status_code=500
        )

@app.route(route="getDataAdvisor")
def getDataAdvisor(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Azure Function getDataAdvisor foi acionada.')

    try:
        token = get_access_token()
        law_token = get_access_law_token()
        
        # Obter e organizar recomendações por categoria
        raw_recommendations = get_recommendations(token)
        recommendations_by_category = {cat: [] for cat in ADVISOR_CATEGORIES}
        
        for rec in raw_recommendations:
            cat = rec["category"]
            if cat in recommendations_by_category:
                recommendations_by_category[cat].append(rec)

        # Obter resumo de recomendações por impacto
        recommendations_summary = get_recommendations_summary(token)

        # Obter dados de Service Health
        resource_graph_data = query_resource_graph(token)
        service_health_data = []

        data_section = resource_graph_data.get("data", {})

        # Verifica se 'data' é um dicionário e contém 'rows'
        if isinstance(data_section, dict) and "rows" in data_section:
            rows = data_section["rows"]
            if rows:
                for row in rows:
                    service_health_data.append({
                        "Title": row[0],
                        "Service": row[1],
                        "subscriptionId": row[2],
                        "count_": row[3]
                    })
            else:
                service_health_data.append({
                    "Title": "Nenhum incidente encontrado",
                    "Service": "N/A",
                    "subscriptionId": "N/A",
                    "count_": 0
                })
        else:
            # Caso 'data' não seja um dicionário ou não tenha 'rows'
            service_health_data.append({
                "Title": "Dados de Service Health indisponíveis",
                "Service": "N/A",
                "subscriptionId": "N/A",
                "count_": 0
            })
        
        # Obter certificados do Log Analytics
        certificates = get_kv_certificates_expiration(law_token)

        # Obter outros itens do Key Vault do Log Analytics
        kv_items = get_kv_items_expiration(law_token)

        
        html_report = generate_html(recommendations_by_category, recommendations_summary, service_health_data, certificates, kv_items)

        return func.HttpResponse(
            body=html_report,
            mimetype="text/html",
            status_code=200
        )
    except ValueError as e:
        logging.error(f"Erro de configuração: {e}")
        return func.HttpResponse(
            f"Erro de configuração: {e}",
            status_code=500
        )
    except Exception as e:
        logging.error(f"Erro ao gerar relatório: {e}")
        return func.HttpResponse(
            f"Erro ao obter dados: {e}",
            status_code=500
        )
import publishScores