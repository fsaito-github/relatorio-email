#!/usr/bin/env python3
"""
Teste rápido e simples para Azure Storage
Execute: python teste_rapido.py
"""

import os
from azure.data.tables import TableClient
from azure.identity import ClientSecretCredential

def teste_rapido():
    print("🔍 Teste Rápido - Azure Storage")
    print("=" * 40)
    
    # Configurar credenciais (substitua pelos seus valores)
    TENANT_ID = "SEU_TENANT_ID_AQUI"
    CLIENT_ID = "SEU_CLIENT_ID_AQUI" 
    CLIENT_SECRET = "SEU_CLIENT_SECRET_AQUI"
    
    print("⚠️  IMPORTANTE: Edite este arquivo e substitua as credenciais!")
    print()
    
    if "SEU_" in TENANT_ID:
        print("❌ Configure as credenciais primeiro!")
        print("   Edite o arquivo teste_rapido.py e substitua:")
        print("   - SEU_TENANT_ID_AQUI")
        print("   - SEU_CLIENT_ID_AQUI") 
        print("   - SEU_CLIENT_SECRET_AQUI")
        return
    
    try:
        print("🔐 Testando autenticação...")
        credential = ClientSecretCredential(
            tenant_id=TENANT_ID,
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET
        )
        
        print("📊 Conectando ao Azure Storage...")
        table_url = "https://storagescores.table.core.windows.net"
        table_client = TableClient(endpoint=table_url, table_name="AdvisorScores", credential=credential)
        
        print("🔍 Fazendo consulta de teste...")
        entities = list(table_client.query_entities("PartitionKey eq 'Security'", limit=3))
        
        print(f"✅ SUCESSO! Encontradas {len(entities)} entidades")
        for entity in entities:
            print(f"   - {entity.get('PartitionKey', 'N/A')} | {entity.get('RowKey', 'N/A')} | Score: {entity.get('Score', 'N/A')}")
            
    except Exception as e:
        print(f"❌ ERRO: {e}")
        print("\n💡 Possíveis soluções:")
        print("   1. Verifique se as credenciais estão corretas")
        print("   2. Verifique se a tabela 'AdvisorScores' existe")
        print("   3. Verifique se o Service Principal tem permissões")

if __name__ == "__main__":
    teste_rapido()
