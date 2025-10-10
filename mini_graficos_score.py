import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import io
import base64
from datetime import datetime
from azure.data.tables import TableClient
from azure.identity import DefaultAzureCredential

def converter_data_string(data_str):
    """Converte string de data para objeto datetime, tentando vários formatos"""
    # Limpar a string removendo 'Z' e microsegundos se existirem
    data_limpa = str(data_str).strip()
    if data_limpa.endswith('Z'):
        data_limpa = data_limpa[:-1]  # Remove o 'Z'
    
    # Se contém microsegundos, remover
    if '.' in data_limpa and 'T' in data_limpa:
        partes = data_limpa.split('.')
        if len(partes) == 2:
            data_limpa = partes[0]  # Mantém apenas a parte antes dos microsegundos
    
    formatos = [
        "%Y-%m-%dT%H:%M:%S",    # 2025-09-25T00:00:00
        "%Y-%m-%d",             # 2025-09-25
        "%Y-%m-%dT%H:%M",       # 2025-09-25T00:00
        "%d/%m/%Y",             # 25/09/2025
        "%d-%m-%Y",             # 25-09-2025
        "%Y/%m/%d",             # 2025/09/25
    ]
    
    for formato in formatos:
        try:
            return datetime.strptime(data_limpa, formato)
        except ValueError:
            continue
    
    # Se não conseguir converter, retorna a string original
    return data_str

def gerar_mini_grafico_categoria(categoria):
    """
    Gera um mini-gráfico de linha para uma categoria específica
    
    Args:
        categoria (str): Nome da categoria (Cost, Security, HighAvailability, etc.)
    
    Returns:
        tuple: (base64_image, variacao_percentual, dados_scores)
    """
    try:
        credential = DefaultAzureCredential()
        table_url = "https://storagescores.table.core.windows.net"
        table_client = TableClient(endpoint=table_url, table_name="AdvisorScores", credential=credential)
        
        # Buscar dados da categoria específica
        entidades = table_client.query_entities(f"PartitionKey eq '{categoria}'")
        ordenados = sorted(entidades, key=lambda x: x["RowKey"])
        
        if not ordenados:
            return None, 0, []
        
        # Converter datas e extrair scores
        datas_convertidas = []
        scores = []
        
        for item in ordenados:
            data_convertida = converter_data_string(item["RowKey"])
            datas_convertidas.append(data_convertida)
            scores.append(round(item["Score"]))
        
        # Calcular variação percentual (último vs penúltimo)
        variacao_percentual = 0
        if len(scores) >= 2:
            score_atual = scores[-1]
            score_anterior = scores[-2]
            if score_anterior != 0:
                variacao_percentual = ((score_atual - score_anterior) / score_anterior) * 100
        
        # Configurar cores por categoria
        cores_categoria = {
            "Cost": "#10B981",           
            "Security": "#EF4444",        
            "HighAvailability": "#3B82F6", 
            "OperationalExcellence": "#F59E0B", 
            "Performance": "#8B5CF6"      
        }
        
        cor = cores_categoria.get(categoria, "#6B7280")
        
        # Criar mini-gráfico
        plt.style.use('default')
        fig, ax = plt.subplots(figsize=(2.5, 1.2), dpi=80)
        
        # Se as datas não são datetime, usar índices
        if datas_convertidas and not isinstance(datas_convertidas[0], datetime):
            x_values = range(len(datas_convertidas))
        else:
            x_values = datas_convertidas
        
        # Plotar linha simples
        ax.plot(x_values, scores, color=cor, linewidth=2, alpha=0.8)
        ax.fill_between(x_values, scores, alpha=0.1, color=cor)
        
        # Remover todos os elementos visuais desnecessários
        ax.set_xticks([])
        ax.set_yticks([])
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['bottom'].set_visible(False)
        ax.spines['left'].set_visible(False)
        
        # Ajustar limites para mostrar tendência
        if scores:
            y_min = min(scores) - 2
            y_max = max(scores) + 2
            ax.set_ylim(y_min, y_max)
        
        # Layout minimalista
        plt.tight_layout()
        plt.subplots_adjust(left=0, right=1, top=1, bottom=0)
        
        # Salvar como base64
        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', dpi=80, bbox_inches='tight', 
                   pad_inches=0, transparent=True)
        buffer.seek(0)
        imagem_base64 = base64.b64encode(buffer.read()).decode('utf-8')
        plt.close()
        
        return imagem_base64, variacao_percentual, scores
        
    except Exception as e:
        print(f"Erro ao gerar mini-gráfico para {categoria}: {e}")
        return None, 0, []

def obter_dados_evolucao_todas_categorias():
    """
    Obtém dados de evolução para todas as categorias do Azure Advisor
    
    Returns:
        dict: Dicionário com dados de cada categoria
    """
    categorias = ["Cost", "Security", "HighAvailability", "OperationalExcellence", "Performance"]
    dados_evolucao = {}
    
    for categoria in categorias:
        mini_grafico, variacao, scores = gerar_mini_grafico_categoria(categoria)
        
        # Mapear nomes para português
        nomes_pt = {
            "Cost": "Custo",
            "Security": "Segurança",
            "HighAvailability": "Resiliência",
            "OperationalExcellence": "Exc. Operacional",
            "Performance": "Performance"
        }
        
        dados_evolucao[categoria] = {
            'nome_pt': nomes_pt.get(categoria, categoria),
            'mini_grafico_base64': mini_grafico,
            'variacao_percentual': round(variacao, 1),
            'scores_historicos': scores,
            'score_atual': scores[-1] if scores else 0,
            'tendencia': 'up' if variacao > 0 else 'down' if variacao < 0 else 'stable'
        }
    
    return dados_evolucao