#!/usr/bin/env python3
"""
Script de teste manual para verificar conexão com Azure Storage
Execute este script para testar se as credenciais estão funcionando
"""

import os
from azure.data.tables import TableClient, TableServiceClient
from azure.identity import ClientSecretCredential
from azure.core.exceptions import ClientAuthenticationError, ResourceNotFoundError
from dotenv import load_dotenv

def test_azure_storage_connection():
    """Testa a conexão com Azure Storage"""
    
    print("🔍 Testando conexão com Azure Storage...")
    print("=" * 50)
    
    # Carregar variáveis de ambiente do arquivo .env (se existir)
    load_dotenv()
    
    # Verificar variáveis de ambiente
    tenant_id = os.getenv("TENANT_ID")
    client_id = os.getenv("CLIENT_ID")
    client_secret = os.getenv("CLIENT_SECRET")
    
    print(f"📋 Verificando variáveis de ambiente:")
    print(f"   TENANT_ID: {'✅ Configurado' if tenant_id else '❌ Não configurado'}")
    print(f"   CLIENT_ID: {'✅ Configurado' if client_id else '❌ Não configurado'}")
    print(f"   CLIENT_SECRET: {'✅ Configurado' if client_secret else '❌ Não configurado'}")
    print()
    
    if not all([tenant_id, client_id, client_secret]):
        print("❌ ERRO: Variáveis de ambiente não estão configuradas!")
        print("Configure as seguintes variáveis:")
        print("   TENANT_ID=seu-tenant-id")
        print("   CLIENT_ID=seu-client-id") 
        print("   CLIENT_SECRET=seu-client-secret")
        return False
    
    try:
        # Criar credencial
        print("🔐 Criando credencial...")
        credential = ClientSecretCredential(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret
        )
        print("✅ Credencial criada com sucesso!")
        
        # Testar conexão com Table Service
        print("\n📊 Testando conexão com Table Service...")
        table_url = "https://storagescores.table.core.windows.net"
        table_service = TableServiceClient(endpoint=table_url, credential=credential)
        
        # Listar tabelas existentes
        print("📋 Listando tabelas existentes...")
        tables = list(table_service.list_tables())
        print(f"   Encontradas {len(tables)} tabelas:")
        for table in tables:
            print(f"   - {table.name}")
        
        # Verificar se a tabela AdvisorScores existe
        print("\n🎯 Verificando se a tabela 'AdvisorScores' existe...")
        advisor_scores_exists = any(table.name == "AdvisorScores" for table in tables)
        
        if advisor_scores_exists:
            print("✅ Tabela 'AdvisorScores' encontrada!")
            
            # Testar consulta na tabela
            print("\n🔍 Testando consulta na tabela AdvisorScores...")
            table_client = TableClient(endpoint=table_url, table_name="AdvisorScores", credential=credential)
            
            # Fazer uma consulta simples
            entities = list(table_client.query_entities("PartitionKey eq 'Security'", select=["PartitionKey", "RowKey", "Score"], limit=5))
            print(f"   Encontradas {len(entities)} entidades de Security:")
            for entity in entities:
                print(f"   - {entity['PartitionKey']} | {entity['RowKey']} | Score: {entity.get('Score', 'N/A')}")
                
        else:
            print("❌ Tabela 'AdvisorScores' NÃO encontrada!")
            print("\n💡 Para criar a tabela, execute:")
            print("   az storage table create --name AdvisorScores --account-name storagescores")
            print("   OU crie manualmente no Azure Portal")
            
            # Tentar criar a tabela automaticamente
            print("\n🔧 Tentando criar a tabela automaticamente...")
            try:
                table_service.create_table("AdvisorScores")
                print("✅ Tabela 'AdvisorScores' criada com sucesso!")
            except Exception as e:
                print(f"❌ Erro ao criar tabela: {e}")
                print("   Crie manualmente no Azure Portal")
        
        print("\n🎉 Teste de conexão concluído com sucesso!")
        return True
        
    except ClientAuthenticationError as e:
        print(f"❌ ERRO DE AUTENTICAÇÃO: {e}")
        print("\n💡 Possíveis soluções:")
        print("   1. Verifique se TENANT_ID, CLIENT_ID e CLIENT_SECRET estão corretos")
        print("   2. Verifique se o Service Principal tem permissões no Storage Account")
        print("   3. Verifique se o CLIENT_SECRET não expirou")
        return False
        
    except ResourceNotFoundError as e:
        print(f"❌ RECURSO NÃO ENCONTRADO: {e}")
        print("\n💡 Possíveis soluções:")
        print("   1. Verifique se a Storage Account 'storagescores' existe")
        print("   2. Verifique se o nome da conta está correto")
        return False
        
    except Exception as e:
        print(f"❌ ERRO INESPERADO: {e}")
        print(f"   Tipo do erro: {type(e).__name__}")
        return False

def test_table_operations():
    """Testa operações básicas na tabela"""
    
    print("\n🧪 Testando operações na tabela...")
    print("=" * 50)
    
    try:
        from datetime import datetime
        
        # Configurações
        tenant_id = os.getenv("TENANT_ID")
        client_id = os.getenv("CLIENT_ID")
        client_secret = os.getenv("CLIENT_SECRET")
        
        credential = ClientSecretCredential(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret
        )
        
        table_url = "https://storagescores.table.core.windows.net"
        table_client = TableClient(endpoint=table_url, table_name="AdvisorScores", credential=credential)
        
        # Teste de escrita
        print("📝 Testando escrita na tabela...")
        test_entity = {
            "PartitionKey": "Test",
            "RowKey": f"test-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
            "Score": 85,
            "LastRefreshed": datetime.now().isoformat()
        }
        
        table_client.create_entity(entity=test_entity)
        print("✅ Entidade de teste criada com sucesso!")
        
        # Teste de leitura
        print("📖 Testando leitura da tabela...")
        entities = list(table_client.query_entities("PartitionKey eq 'Test'", limit=5))
        print(f"   Encontradas {len(entities)} entidades de teste")
        
        # Limpeza
        print("🧹 Limpando entidades de teste...")
        for entity in entities:
            table_client.delete_entity(partition_key=entity["PartitionKey"], row_key=entity["RowKey"])
        print("✅ Entidades de teste removidas!")
        
        print("🎉 Teste de operações concluído com sucesso!")
        return True
        
    except Exception as e:
        print(f"❌ Erro no teste de operações: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Iniciando teste manual do Azure Storage")
    print("=" * 60)
    
    # Teste de conexão
    connection_ok = test_azure_storage_connection()
    
    if connection_ok:
        # Teste de operações
        operations_ok = test_table_operations()
        
        if operations_ok:
            print("\n🎉 TODOS OS TESTES PASSARAM!")
            print("✅ Sua configuração está funcionando corretamente!")
        else:
            print("\n⚠️  Conexão OK, mas operações falharam")
    else:
        print("\n❌ TESTES FALHARAM!")
        print("🔧 Verifique a configuração antes de continuar")
    
    print("\n" + "=" * 60)
    print("Teste concluído!")
