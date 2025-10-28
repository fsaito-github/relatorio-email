import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import io
import base64
from datetime import datetime
from azure.data.tables import TableClient
from azure.identity import ClientSecretCredential

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

def obter_mapeamento_meses_portugues():
    """Retorna o mapeamento de abreviações de meses do inglês para português"""
    months_pt = {
        'Jan': 'Jan', 'Feb': 'Fev', 'Mar': 'Mar', 'Apr': 'Abr',
        'May': 'Mai', 'Jun': 'Jun', 'Jul': 'Jul', 'Aug': 'Ago',
        'Sep': 'Set', 'Oct': 'Out', 'Nov': 'Nov', 'Dec': 'Dez'
    }
    return months_pt

def gerar_grafico_multicategorias():
    # Limpar posições ocupadas da geração anterior
    if hasattr(gerar_grafico_multicategorias, '_occupied_positions'):
        gerar_grafico_multicategorias._occupied_positions = {}
    
    import os
    from azure.core.exceptions import ClientAuthenticationError, ResourceNotFoundError
    
    # Verificar se as variáveis de ambiente estão configuradas
    tenant_id = os.getenv("TENANT_ID")
    client_id = os.getenv("CLIENT_ID")
    client_secret = os.getenv("CLIENT_SECRET")
    
    if not all([tenant_id, client_id, client_secret]):
        raise ValueError("Variáveis de ambiente TENANT_ID, CLIENT_ID ou CLIENT_SECRET não estão configuradas")
    
    try:
        credential = ClientSecretCredential(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret
        )
        table_url = "https://storagescores.table.core.windows.net"
        table_client = TableClient(endpoint=table_url, table_name="AdvisorScores", credential=credential)
        
        # Testar a conexão fazendo uma consulta simples
        test_entities = list(table_client.query_entities("PartitionKey eq 'Security'", select=["PartitionKey"], limit=1))
        
    except ClientAuthenticationError as e:
        raise ValueError(f"Falha na autenticação com Azure Storage: {e}")
    except ResourceNotFoundError as e:
        raise ValueError(f"Tabela 'AdvisorScores' não encontrada: {e}")
    except Exception as e:
        raise ValueError(f"Erro ao conectar com Azure Storage: {e}")

    categorias = ["Cost", "Security", "HighAvailability", "OperationalExcellence", "Performance"]
    # Paleta de cores
    cores = {
        "Cost": "#10B981",           
        "Security": "#EF4444",        
        "HighAvailability": "#3B82F6", 
        "OperationalExcellence": "#F59E0B", 
        "Performance": "#8B5CF6"      
    }
    
    # Nomes mais amigáveis para a legenda
    nomes_categorias = {
        "Cost": "Custo",
        "Security": "Segurança", 
        "HighAvailability": "Alta Disponibilidade",
        "OperationalExcellence": "Excelência Operacional",
        "Performance": "Performance"
    }
    
    dados_por_categoria = {}

    for categoria in categorias:
        entidades = table_client.query_entities(f"PartitionKey eq '{categoria}'")
        ordenados = sorted(entidades, key=lambda x: x["RowKey"])
        
        # Converter strings de data para objetos datetime para melhor formatação
        datas_convertidas = []
        for data_str in [e["RowKey"] for e in ordenados]:
            data_convertida = converter_data_string(data_str)
            datas_convertidas.append(data_convertida)
        
        scores = [e["Score"] for e in ordenados]
        dados_por_categoria[categoria] = (datas_convertidas, scores)

    # Configurar o estilo do matplotlib para melhor aparência
    plt.style.use('default')  # Usar estilo padrão limpo
    
    # Gerar gráfico com tamanho otimizado (sem título)
    fig, ax = plt.subplots(figsize=(14, 6), dpi=100)
    
    for categoria, (datas, scores) in dados_por_categoria.items():
        cor = cores.get(categoria, "#1f77b4")  # Cor padrão se não encontrar
        nome_categoria = nomes_categorias.get(categoria, categoria)
        
        # Se as datas não são datetime, criar índices numéricos para plotagem
        if datas and not isinstance(datas[0], datetime):
            x_values = range(len(datas))
        else:
            x_values = datas
        
        # Plotar linha com marcadores maiores e efeito de sombra
        line = ax.plot(x_values, scores, marker='o', label=nome_categoria, 
                      color=cor, linewidth=3, markersize=10, 
                      markerfacecolor=cor, markeredgecolor='white', 
                      markeredgewidth=2, alpha=0.9)
        
        # Adicionar rótulos em todos os pontos 
        if datas and scores:  # Verificar se há dados
            num_pontos = len(scores)
            
            # Se temos muitos pontos, mostrar apenas alguns para não poluir
            if num_pontos > 6:
                # Mostrar primeiro, último e alguns pontos intermediários
                indices_mostrar = [0, num_pontos//3, 2*num_pontos//3, num_pontos-1]
                indices_mostrar = list(set(indices_mostrar))  # Remove duplicatas
                indices_mostrar.sort()
            else:
                # Se poucos pontos, mostrar todos
                indices_mostrar = list(range(num_pontos))
            
            # Armazenar posições ocupadas por índice e valor para evitar sobreposição
            if not hasattr(gerar_grafico_multicategorias, '_occupied_positions'):
                gerar_grafico_multicategorias._occupied_positions = {}
            
            for i in indices_mostrar:
                if isinstance(x_values, range):
                    x_pos = x_values[i]
                else:
                    x_pos = x_values[i]
                score_val = scores[i]
                
                # Criar chave baseada no índice e score (sem usar coordenadas datetime)
                pos_key = f"{i}_{score_val:.0f}"
                
                # Verificar quantas posições já ocupadas neste ponto
                occupied_count = 0
                for existing_key in gerar_grafico_multicategorias._occupied_positions:
                    existing_i, existing_score = existing_key.split('_')
                    if int(existing_i) == i and abs(float(existing_score) - score_val) < 1:
                        occupied_count += 1
                
                # Adicionar esta posição
                gerar_grafico_multicategorias._occupied_positions[pos_key] = True
                
                # Calcular offset baseado na sobreposição
                if occupied_count == 0:
                    xytext_offset = (0, 15)  # Primeiro: acima
                    va_alignment = 'bottom'
                    ha_alignment = 'center'
                elif occupied_count == 1:
                    xytext_offset = (-25, 5)  # Segundo: esquerda
                    va_alignment = 'center'
                    ha_alignment = 'right'
                elif occupied_count == 2:
                    xytext_offset = (25, 5)  # Terceiro: direita
                    va_alignment = 'center'
                    ha_alignment = 'left'
                elif occupied_count == 3:
                    xytext_offset = (0, -15)  # Quarto: abaixo
                    va_alignment = 'top'
                    ha_alignment = 'center'
                else:
                    # Alternativa para casos extremos
                    xytext_offset = (0, 15)
                    va_alignment = 'bottom'
                    ha_alignment = 'center'
                
                ax.annotate(f'{score_val:.0f}%', 
                           (x_pos, score_val), 
                           textcoords="offset points", 
                           xytext=xytext_offset, 
                           ha=ha_alignment, 
                           va=va_alignment,
                           fontsize=9, 
                           fontweight='bold',
                           color=cor,
                           bbox=dict(boxstyle="round,pad=0.2", 
                                    facecolor='white', 
                                    edgecolor=cor, 
                                    alpha=0.95,
                                    linewidth=1))

    # Configurações do gráfico 
    ax.set_xlabel("Data", fontsize=12, fontweight='bold')
    ax.set_ylabel("Score (%)", fontsize=12, fontweight='bold')
    
    # Configurar formatação do eixo X para mês/ano
    if dados_por_categoria:
        # Verificar se temos dados e se são datetime
        primeira_categoria = list(dados_por_categoria.keys())[0]
        datas_exemplo = dados_por_categoria[primeira_categoria][0]
        
        if datas_exemplo and isinstance(datas_exemplo[0], datetime):
            # Determinar intervalo baseado na quantidade de dados
            num_pontos = len(datas_exemplo)
            if num_pontos > 10:
                interval = max(1, num_pontos // 8)  # Mostrar ~8 labels
            else:
                interval = 1
                
            ax.xaxis.set_major_locator(mdates.DayLocator(interval=interval))
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%d/%b'))
            
            # Aplicar formatação brasileira
            months_pt = obter_mapeamento_meses_portugues()
            
            # Forçar o matplotlib a atualizar e aplicar formatação portuguesa
            fig.canvas.draw()
            labels = []
            for tick in ax.get_xticklabels():
                text = tick.get_text()
                for eng, pt in months_pt.items():
                    text = text.replace(eng, pt)
                labels.append(text)
            ax.set_xticklabels(labels)
        else:
            # Se não são datetime, tentar formatar as strings de data diretamente
            if datas_exemplo:
                # Pegar uma amostra das datas para formatação
                datas_formatadas = []
                for data in datas_exemplo:
                    if isinstance(data, str):
                        # Tentar converter e formatar a string de data
                        try:
                            if 'T' in data:  # Formato ISO
                                data_clean = data.split('T')[0]  # Remove hora
                                dt = datetime.strptime(data_clean, '%Y-%m-%d')
                                datas_formatadas.append(dt.strftime('%d/%b'))
                            else:
                                datas_formatadas.append(data)
                        except:
                            datas_formatadas.append(data)
                    else:
                        datas_formatadas.append(str(data))
                
                # Aplicar formatação brasileira nas datas
                months_pt = obter_mapeamento_meses_portugues()
                datas_pt = []
                for data in datas_formatadas:
                    data_pt = data
                    for eng, pt in months_pt.items():
                        data_pt = data_pt.replace(eng, pt)
                    datas_pt.append(data_pt)
                
                # Configurar os ticks do eixo X
                num_ticks = min(8, len(datas_pt))  # Máximo 8 labels
                if len(datas_pt) > num_ticks:
                    indices = [i * (len(datas_pt) - 1) // (num_ticks - 1) for i in range(num_ticks)]
                    ax.set_xticks([i for i in range(len(datas_pt)) if i in indices])
                    ax.set_xticklabels([datas_pt[i] for i in indices])
                else:
                    ax.set_xticks(range(len(datas_pt)))
                    ax.set_xticklabels(datas_pt)
    
    plt.xticks(rotation=45)
    
    # Adicionar grade sutil para melhor legibilidade
    ax.grid(True, linestyle='--', alpha=0.3, color='#E5E7EB', linewidth=0.5)
    ax.set_axisbelow(True)  # Grid atrás das linhas
    
    # Configurar legenda
    legend = ax.legend(loc='upper left', bbox_to_anchor=(1.02, 1), 
                      frameon=True, fancybox=True, shadow=False, 
                      ncol=1, fontsize=11, 
                      facecolor='white', edgecolor='#E5E7EB',
                      title="Categorias", title_fontsize=12)
    legend.get_title().set_fontweight('bold')
    
    # Configurar limites do eixo Y automaticamente baseado nos dados
    if dados_por_categoria:
        todos_scores = []
        for _, scores in dados_por_categoria.values():
            todos_scores.extend(scores)
        
        if todos_scores:
            score_min = min(todos_scores)
            score_max = max(todos_scores)
            
            # Calcular margem baseada no range dos dados
            range_dados = score_max - score_min
            margem = max(5, range_dados * 0.15)  # Mínimo 5 pontos, ou 15% do range
            
            # Se o score máximo for 100%, garantir margem mínima de 3 pontos acima
            if score_max >= 100:
                margem_superior = 3
            else:
                margem_superior = margem
            
            y_min = max(0, score_min - margem)
            y_max = min(105, score_max + margem_superior)  # Permitir até 105 para margem
            
            # Se a diferença for muito pequena, garantir um range mínimo
            if y_max - y_min < 20:
                centro = (y_max + y_min) / 2
                y_min = max(0, centro - 10)
                y_max = min(105, centro + 10)
            
            # Garantir que nunca ultrapasse 105% para manter proporção
            y_max = min(105, y_max)
            
            ax.set_ylim(y_min, y_max)
            
            # Adicionar linha de referência para score médio (opcional)
            score_medio = sum(todos_scores) / len(todos_scores)
            if y_min <= score_medio <= y_max:  # Só mostrar se estiver na faixa visível
                ax.axhline(y=score_medio, color='#9CA3AF', linestyle=':', 
                          alpha=0.7, linewidth=1)
    else:
        # Fallback para o range completo se não houver dados
        ax.set_ylim(0, 100)
    
    # Estilizar os eixos
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color('#E5E7EB')
    ax.spines['bottom'].set_color('#E5E7EB')
    
    # Personalizar ticks
    ax.tick_params(colors='#6B7280', which='both')
    ax.tick_params(axis='x', labelsize=10)
    ax.tick_params(axis='y', labelsize=10)
    
    # Melhorar o layout
    plt.tight_layout()
    
    # Adicionar margem extra para a legenda e garantir espaço superior
    plt.subplots_adjust(right=0.85, top=0.95)

    # Salvar com alta qualidade
    buffer = io.BytesIO()
    plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
    buffer.seek(0)
    imagem_base64 = base64.b64encode(buffer.read()).decode('utf-8')
    plt.close()

    return imagem_base64