# 🚀 Guia de Deployment - Azure Advisor Report Generator

Este guia fornece instruções detalhadas para fazer o deploy do projeto Azure Advisor Report Generator no Azure Functions.

## 📋 Pré-requisitos

### 1. Conta Azure
- Assinatura ativa do Azure
- Permissões para criar recursos
- Acesso ao Azure Portal

### 2. Ferramentas Necessárias
- [Azure CLI](https://docs.microsoft.com/en-us/cli/azure/install-azure-cli) (opcional)
- [Visual Studio Code](https://code.visualstudio.com/) com extensão Azure Functions
- [Python 3.8+](https://www.python.org/downloads/)

### 3. Service Principal
Crie um Service Principal com as seguintes permissões:
- **Azure Advisor**: Reader
- **Azure Resource Graph**: Reader
- **Azure Log Analytics**: Reader
- **Azure Storage**: Storage Table Data Contributor

## 🛠️ Configuração Passo a Passo

### Passo 1: Criar Function App

1. **No Azure Portal:**
   - Navegue para "Function Apps"
   - Clique em "Create"
   - Configure:
     - **Name**: `funcazudvbraingegovadvisor` (ou seu nome preferido)
     - **Runtime**: Python 3.8 ou superior
     - **Region**: Escolha a região mais próxima
     - **Storage Account**: Crie uma nova conta de armazenamento

### Passo 2: Configurar Storage Account

1. **Criar Storage Account:**
   - Nome: `storagescores` (ou seu nome preferido)
   - Performance: Standard
   - Replication: LRS (Local Redundant Storage)

2. **Criar Tabela:**
   - Nome da tabela: `AdvisorScores`
   - Partition Key: Nome da categoria
   - Row Key: Data do score

### Passo 3: Configurar Log Analytics

1. **Criar Workspace:**
   - Nome: Escolha um nome descritivo
   - Resource Group: Mesmo do Function App
   - Location: Mesma região do Function App

2. **Configurar Coleta de Dados:**
   - Adicione o Key Vault como fonte de dados
   - Configure a coleta de certificados

### Passo 4: Configurar Variáveis de Ambiente

No Azure Portal, vá para o Function App > Configuration > Application settings:

```bash
TENANT_ID=seu-tenant-id-aqui
CLIENT_ID=seu-client-id-aqui
CLIENT_SECRET=seu-client-secret-aqui
SUBSCRIPTION_ID=sua-subscription-id-aqui
```

### Passo 5: Deploy do Código

#### Opção A: Via Visual Studio Code

1. **Instalar Extensões:**
   - Azure Functions
   - Python

2. **Configurar:**
   ```bash
   # Fazer login no Azure
   az login
   
   # Configurar Azure Functions Core Tools
   npm install -g azure-functions-core-tools@4 --unsafe-perm true
   ```

3. **Deploy:**
   - Abra o projeto no VS Code
   - Pressione `Ctrl+Shift+P`
   - Digite "Azure Functions: Deploy to Function App"
   - Selecione sua Function App

#### Opção B: Via Azure CLI

1. **Preparar arquivos:**
   ```bash
   # Criar arquivo de configuração
   func init --python
   func new --name getDataAdvisor --template "HTTP trigger"
   func new --name registroScores --template "HTTP trigger"
   ```

2. **Deploy:**
   ```bash
   func azure functionapp publish funcazudvbraingegovadvisor
   ```

#### Opção C: Via Azure Portal

1. **Upload Manual:**
   - Vá para Function App > App files
   - Faça upload dos arquivos Python
   - Configure as funções manualmente

## 🔧 Configuração Avançada

### Configuração de Autenticação

1. **Service Principal:**
   ```bash
   # Criar Service Principal
   az ad sp create-for-rbac --name "azure-advisor-reporter" --role contributor
   ```

2. **Permissões Específicas:**
   ```bash
   # Dar permissões ao Storage Account
   az role assignment create --assignee <client-id> --role "Storage Table Data Contributor" --scope <storage-account-id>
   ```

### Configuração de Rede

1. **Firewall Rules:**
   - Configure regras de firewall se necessário
   - Adicione IPs de saída do Function App

2. **VNet Integration:**
   - Configure integração com VNet se necessário
   - Configure private endpoints

### Monitoramento

1. **Application Insights:**
   - Habilite Application Insights
   - Configure alertas personalizados

2. **Logs:**
   - Configure retenção de logs
   - Configure alertas de erro

## 🧪 Teste do Deployment

### 1. Testar Função `registroScores`

```bash
# URL da função
https://funcazudvbraingegovadvisor.azurewebsites.net/api/registroScores

# Teste via curl
curl -X GET "https://funcazudvbraingegovadvisor.azurewebsites.net/api/registroScores"
```

### 2. Testar Função `getDataAdvisor`

```bash
# URL da função
https://funcazudvbraingegovadvisor.azurewebsites.net/api/getDataAdvisor

# Teste via curl
curl -X GET "https://funcazudvbraingegovadvisor.azurewebsites.net/api/getDataAdvisor"
```

### 3. Verificar Logs

1. **No Azure Portal:**
   - Vá para Function App > Monitor > Logs
   - Verifique se não há erros
   - Confirme que as funções estão executando

## 🔍 Troubleshooting

### Erro de Autenticação

```bash
# Verificar variáveis de ambiente
az functionapp config appsettings list --name funcazudvbraingegovadvisor --resource-group <resource-group>
```

### Erro de Permissões

```bash
# Verificar permissões do Service Principal
az role assignment list --assignee <client-id>
```

### Erro de Storage

```bash
# Verificar conexão com Storage Account
az storage account show --name storagescores --resource-group <resource-group>
```

## 📊 Monitoramento Pós-Deploy

### 1. Métricas Importantes

- **Execuções**: Número de execuções por função
- **Duração**: Tempo de execução médio
- **Erros**: Taxa de erro por função
- **Throttling**: Limitações de recursos

### 2. Alertas Recomendados

- **Taxa de Erro > 5%**: Alerta quando taxa de erro for alta
- **Duração > 5 minutos**: Alerta para execuções longas
- **Falhas de Autenticação**: Alerta para problemas de credenciais

### 3. Logs Importantes

- **Erros de Autenticação**: Problemas com Service Principal
- **Timeouts**: Execuções que excedem o tempo limite
- **Erros de Storage**: Problemas de acesso ao Table Storage

## 🚀 Próximos Passos

1. **Configurar Agendamento**: Use Azure Logic Apps ou Timer Trigger
2. **Configurar Notificações**: Integre com Teams/Slack
3. **Implementar Cache**: Use Redis para melhor performance
4. **Configurar Backup**: Backup automático dos dados

## 📞 Suporte

Se encontrar problemas:

1. **Verifique os logs** no Azure Portal
2. **Consulte a documentação** do Azure Functions
3. **Abra uma issue** no GitHub
4. **Verifique as permissões** do Service Principal

---

**🎉 Parabéns! Seu Azure Advisor Report Generator está funcionando!**
