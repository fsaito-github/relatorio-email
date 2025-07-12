import azure.functions as func
import logging
import os
import requests
#from dotenv import load_dotenv
from jinja2 import Template

#load_dotenv()

# Environment variables
TENANT_ID = os.getenv("TENANT_ID")
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
SUBSCRIPTION_ID = os.getenv("SUBSCRIPTION_ID")

# Azure AD token endpoint
TOKEN_URL = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/token"

# Function to get Azure access token
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

# Function to get secure score from Microsoft Defender for Cloud
def get_security_score(token):
    url = f"https://management.azure.com/subscriptions/{SUBSCRIPTION_ID}/providers/Microsoft.Security/securescores?api-version=2020-01-01"
    headers = {'Authorization': f'Bearer {token}'}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    data = response.json()

    try:
        percentage = data["value"][0]["properties"]["score"]["percentage"]
        return round(percentage*100,2)
    except (KeyError, IndexError):
        return None
    

# Function to get cost score
def get_cost_score(token):
    url = f"https://management.azure.com/subscriptions/{SUBSCRIPTION_ID}/providers/Microsoft.Advisor/advisorScore/Cost?api-version=2025-01-01"
    headers = {'Authorization': f'Bearer {token}'}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    data = response.json()

    try:
        score = data["properties"]["lastRefreshedScore"]["score"]
        return round(score,2)
    except (KeyError, IndexError):
        return None

# Function to get reliability score (placeholder)
def get_reliability_score(token):
    url = f"https://management.azure.com/subscriptions/{SUBSCRIPTION_ID}/providers/Microsoft.Advisor/advisorScore/HighAvailability?api-version=2025-01-01"
    headers = {'Authorization': f'Bearer {token}'}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    data = response.json()

    try:
        score = data["properties"]["lastRefreshedScore"]["score"]
        return round(score,2)
    except (KeyError, IndexError):
        return None
    
# Funtion to get security, cost , and reliability recommendations.
# Only High impact recommendations are considered.
def get_recommendations(token):
    url = f"https://management.azure.com/subscriptions/{SUBSCRIPTION_ID}/providers/Microsoft.Advisor/recommendations?api-version=2025-01-01"
    headers = {'Authorization': f'Bearer {token}'}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    data = response.json()

    # Use a dict to count recommendations by (description, category)
    rec_count = {}
    for item in data.get("value", []):
        category = item["properties"]["category"]
        impact = item["properties"]["impact"]
        if category in ["Cost", "Security", "HighAvailability"] and impact == "High":
            description = item["properties"]["shortDescription"]["problem"]
            key = (description, category)
            rec_count[key] = rec_count.get(key, 0) + 1

    # Build the recommendations list with unique descriptions and counts
    recommendations = [
        {
            "description": desc,
            "category": cat,
            "count": count
        }
        for (desc, cat), count in rec_count.items()
    ]

    return recommendations

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

# Function to get Log Analytics access token
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

# Function to get certificates information from Log Analytics
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

# Function to get other KV items information from Log Analytics
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
    
# Funtion to generate HTML report
def generate_html(scores, recommendations_by_category, service_health, certificates, kv_items): # AQUI
    
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
                    <td style="background-color: #f4f4f4; border-radius: 8px; padding: 20px; width: "32%"; text-align: center; box-shadow: 0 2px 5px rgba(0,0,0,0.1);">
                        <div style="font-size: 14px; font-weight: bold; color: #324469; text-align: center; ">Segurança</div>
                        <div style="font-size: 24px; font-weight: bold; text-align: center;">{{ security }}%</div>
                    </td>
                    <td style="width: 13px;"></td>
                    <td style="background-color: #f4f4f4; border-radius: 8px; padding: 20px; width: "32%"; text-align: center; box-shadow: 0 2px 5px rgba(0,0,0,0.1);">
                        <div style="font-size: 14px; font-weight: bold; color: #324469; text-align: center; ">Custos</div>
                        <div style="font-size: 24px; font-weight: bold; text-align: center; ">{{ cost }}%</div>
                    </td>
                    <td style="width: 13px;"></td>
                    <td style="background-color: #f4f4f4; border-radius: 8px; padding: 20px; width: "32%"; text-align: center; box-shadow: 0 2px 5px rgba(0,0,0,0.1);">
                        <div style="font-size: 14px; font-weight: bold; color: #324469; text-align: center; ">Resiliência</div>
                        <div style="font-size: 24px; font-weight: bold; text-align: center; ">{{ reliability }}%</div>
                    </td>
                </tr>    
            </table>

            <h3 style="margin-top: 30px; color: #324469;">Recomendações por Categoria</h3>
            <table width="100%" cellpadding="0" cellspacing="0" border="0">
                <tr>
                    {% for category in ["Security", "Cost", "HighAvailability"] %}
                        <td width="32%" valign="top" style="background-color: #f4f4f4; padding: 10px; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); margin-right: 2%;">
                            <div style="font-size: 14px; font-weight: bold; margin-bottom: 0px; color: #324469; text-align: center;">
                                {{ category_names[category] }}
                            </div>
                            {% for rec in recommendations.get(category, []) %}
                                <div style="font-size: 12px; margin-bottom: 0px; color: #555;">• {{ rec.description }}</div>
                            {% else %}
                                <div style="font-size: 12px; margin-bottom: 0px; color: #555;">Nenhuma recomendação.</div>
                            {% endfor %}
                        </td>
                        {% if not loop.last %}
                            <td style="width: 13px;"></td>
                        {% endif %}
                    {% endfor %}
                </tr>
            </table>

            <h3 style="margin-top: 30px; color: #324469;">Service Health</h3>
            <table style="width:100%; border-collapse: collapse; background-color: white; box-shadow: 0 2px 5px rgba(0,0,0,0.1);">
                <thead>
                    <tr style="background-color: #324469; color: #f4f4f4;">
                        <th style="padding: 10px; border: 1px solid #ddd; font-size: 12.5px;">Alerta</th>
                        <th style="padding: 10px; border: 1px solid #ddd; font-size: 12.5px;">Serviço</th>
                        <th style="padding: 10px; border: 1px solid #ddd; font-size: 12.5px;">Itens afetados</th>
                        <th style="padding: 10px; border: 1px solid #ddd; font-size: 12.5px;">Subscription ID</th>
                    </tr>
                </thead>
                <tbody>
                    {% for item in service_health %}
                    <tr>
                        <td style="padding: 8px; border: 1px solid #ddd; font-size: 12px;">{{ item.Title }}</td>
                        <td style="padding: 8px; border: 1px solid #ddd; font-size: 12px;">{{ item.Service }}</td>
                        <td style="padding: 8px; border: 1px solid #ddd; font-size: 12px;">{{ item.count_ }}</td>
                        <td style="padding: 8px; border: 1px solid #ddd; font-size: 12px;">{{ item.subscriptionId }}</td>
                    </tr>
                    {% else %}
                    <tr>
                        <td colspan="4" style="padding: 8px; border: 1px solid #ddd; text-align: center; font-size: 12px;">Nenhum incidente encontrado.</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>

            <h3 style="margin-top: 30px; color: #324469;">Expiração de Certificados</h3>
            <table width="100%" cellpadding="0" cellspacing="0" border="0">
                <tr>
                    {% for title, certs in cert_groups %}
                        <td width="24%" valign="top" style="background-color: #f4f4f4; padding: 10px; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); margin-right: 2%;">
                            <div style="font-size: 14px; font-weight: bold; margin-bottom: -10px; color: #324469; text-align: center;">
                                {{ title }}
                            </div>
                            {% for cert in certs %}
                                <div style="font-size: 12px; margin-bottom: 0px; color: #555;">• {{ cert.Name }} ({{ cert.DaysToExpire }} dias)</div>
                            {% else %}
                                <div style="font-size: 12px; margin-bottom: 0px; color: #555;">Nenhum certificado.</div>
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
                        <td width="24%" valign="top" style="background-color: #f4f4f4; padding: 10px; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); margin-right: 2%;">
                            <div style="font-size: 14px; font-weight: bold; margin-bottom: -10px; color: #324469; text-align: center;">
                                {{ title }}
                            </div>
                            {% for kv_item in kv_items %}
                                <div style="font-size: 12px; margin-bottom: 0px; color: #555;">• {{ kv_item.Name }} ({{ kv_item.DaysToExpire }} dias) - {{kv_item.ItemType}}</div>
                            {% else %}
                                <div style="font-size: 12px; margin-bottom: 0px; color: #555;">Nenhum item.</div>
                            {% endfor %}
                        </td>
                        {% if not loop.last %}
                            <td style="width: 8px;"></td>
                        {% endif %}
                    {% endfor %}
                </tr>
            </table>              

        </body>
    </html>
    """
    template = Template(html_template)
    return template.render(
        security=scores.get("Security", "N/A"),
        cost=scores.get("Cost", "N/A"),
        reliability=scores.get("Reliability", "N/A"),
        recommendations=recommendations_by_category,
        category_names={
            "Security": "Segurança",
            "Cost": "Custos",
            "HighAvailability": "Resiliência"
        },
        service_health=service_health,
        cert_groups=cert_groups,
        kv_items_groups=kv_items_groups
)

# Azure Function App

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)

@app.route(route="getDataAdvisor")
def getDataAdvisor(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Azure Function getDataAdvisor foi acionada.')

    try:
        token = get_access_token()
        law_token = get_access_law_token()
        scoreSec = get_security_score(token)
        scoreCost = get_cost_score(token)
        scoreReliability = get_reliability_score(token)

        scores = {
            "Security": scoreSec if scoreSec is not None else "N/A",
            "Cost": scoreCost if scoreCost is not None else "N/A",
            "Reliability": scoreReliability if scoreReliability is not None else "N/A"
        }

        
        # Obter e organizar recomendações por categoria
        raw_recommendations = get_recommendations(token)
        recommendations_by_category = {
            "Security": [],
            "Cost": [],
            "HighAvailability": []
        }
        for rec in raw_recommendations:
            cat = rec["category"]
            if cat in recommendations_by_category:
                recommendations_by_category[cat].append(rec)

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

        
        html_report = generate_html(scores,recommendations_by_category, service_health_data, certificates, kv_items)

        return func.HttpResponse(
            body=html_report,
            mimetype="text/html",
            status_code=200
        )
    except Exception as e:
        logging.error(f"Erro ao gerar relatório: {e}")
        return func.HttpResponse(
            "Erro ao obter dados.",
            status_code=500
        )