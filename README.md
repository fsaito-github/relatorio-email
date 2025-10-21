# Azure Advisor Report Generator

Um sistema automatizado de geração de relatórios para Azure Advisor que coleta dados de scores, recomendações, certificados e Service Health, gerando relatórios HTML com visualizações gráficas.

## 🚀 Funcionalidades

- **Scores do Azure Advisor**: Monitoramento de scores por categoria (Security, Cost, HighAvailability, OperationalExcellence, Performance)
- **Recomendações**: Análise de recomendações de alto impacto por categoria
- **Certificados**: Monitoramento de expiração de certificados no Key Vault
- **Service Health**: Alertas e incidentes de Service Health
- **Relatórios HTML**: Geração de relatórios visuais com gráficos embarcados
- **Histórico**: Armazenamento e visualização de histórico de scores

## 📋 Pré-requisitos

- Azure Functions (Python 3.8+)
- Azure Storage Account (Table Storage)
- Azure Log Analytics Workspace
- Service Principal com permissões adequadas
- Python 3.8+

## 🛠️ Instalação

### 1. Clone o repositório
```bash
git clone https://github.com/seu-usuario/azure-advisor-report-generator.git
cd azure-advisor-report-generator
```

### 2. Instale as dependências
```bash
pip install -r requirements.txt
```

### 3. Configure as variáveis de ambiente

No Azure Functions, configure as seguintes variáveis de ambiente:

```bash
TENANT_ID=seu-tenant-id
CLIENT_ID=seu-client-id
CLIENT_SECRET=seu-client-secret
SUBSCRIPTION_ID=sua-subscription-id
```

## 📁 Estrutura do Projeto

```
relatorio-email/
├── function_app.py          # Função principal que gera o relatório HTML
├── grafico_score.py         # Geração de gráficos de histórico de scores
├── mini_graficos_score.py   # Mini-gráficos para cards individuais
├── publishScores.py         # Registro de scores no Azure Table Storage
├── requirements.txt         # Dependências Python
├── host.json               # Configuração do Azure Functions
└── README.md               # Documentação do projeto
```

## 🔧 Configuração

### Permissões Necessárias

O Service Principal precisa das seguintes permissões:

- **Azure Advisor**: Leitura de recomendações e scores
- **Azure Resource Graph**: Consulta de recursos
- **Azure Log Analytics**: Leitura de dados
- **Azure Table Storage**: Leitura e escrita de dados

### Configuração do Storage Account

1. Crie uma conta de armazenamento
2. Crie uma tabela chamada `AdvisorScores`
3. Configure as permissões de acesso

### Configuração do Log Analytics

1. Configure a coleta de dados do Key Vault
2. Ajuste o `workspace_id` no código se necessário

## 🚀 Deployment

### Deploy no Azure Functions

1. **Via Azure CLI**:
```bash
func azure functionapp publish funcazudvbraingegovadvisor
```

2. **Via Visual Studio Code**:
   - Instale a extensão Azure Functions
   - Faça login na sua conta Azure
   - Deploy diretamente do VS Code

3. **Via Azure Portal**:
   - Crie um Function App
   - Configure as variáveis de ambiente
   - Faça upload dos arquivos

## 📊 Endpoints

### `getDataAdvisor`
- **Método**: GET
- **Descrição**: Gera relatório HTML completo
- **Retorno**: HTML com relatório visual

### `registroScores`
- **Método**: GET
- **Descrição**: Registra scores atuais no Table Storage
- **Retorno**: Confirmação de sucesso

## 🎨 Recursos Visuais

- **Cards de Score**: Exibição de scores atuais com mini-gráficos
- **Gráfico de Histórico**: Evolução temporal dos scores
- **Tabelas de Recomendações**: Lista organizada por categoria e impacto
- **Alertas de Certificados**: Status de expiração por faixa de tempo
- **Service Health**: Incidentes ativos e afetados

## 🔍 Monitoramento

### Logs
Os logs são gerados automaticamente pelo Azure Functions e podem ser visualizados no Azure Portal.

### Métricas
- Tempo de execução das funções
- Taxa de sucesso/erro
- Uso de recursos

## 🛡️ Segurança

- Autenticação via Service Principal
- Variáveis de ambiente para credenciais
- Acesso baseado em permissões mínimas necessárias

## 📈 Melhorias Futuras

- [ ] Implementar cache para melhor performance
- [ ] Adicionar testes automatizados
- [ ] Configurar alertas automáticos
- [ ] Implementar agendamento de relatórios
- [ ] Adicionar exportação em PDF

## 🤝 Contribuição

1. Fork o projeto
2. Crie uma branch para sua feature (`git checkout -b feature/AmazingFeature`)
3. Commit suas mudanças (`git commit -m 'Add some AmazingFeature'`)
4. Push para a branch (`git push origin feature/AmazingFeature`)
5. Abra um Pull Request

## 📝 Licença

Este projeto está sob a licença MIT. Veja o arquivo `LICENSE` para mais detalhes.

## 🆘 Suporte

Para suporte e dúvidas:
- Abra uma issue no GitHub
- Consulte a documentação do Azure Functions
- Verifique os logs no Azure Portal

## 📚 Documentação Adicional

- [Azure Functions Python](https://docs.microsoft.com/en-us/azure/azure-functions/functions-reference-python)
- [Azure Advisor](https://docs.microsoft.com/en-us/azure/advisor/)
- [Azure Table Storage](https://docs.microsoft.com/en-us/azure/storage/tables/)
- [Azure Log Analytics](https://docs.microsoft.com/en-us/azure/azure-monitor/logs/)

---

**Desenvolvido com ❤️ para monitoramento eficiente do Azure Advisor**
