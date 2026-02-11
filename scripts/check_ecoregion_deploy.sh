#!/bin/bash
# Verifica progresso do deploy de ecoregion raster no servidor

echo "=================================================="
echo "ECOREGION RASTER DEPLOY - STATUS"
echo "=================================================="
echo ""

# Verificar se processo está rodando
ssh diversiplant "ps aux | grep 'create_ecoregion_lookup.py' | grep -v grep" > /dev/null
if [ $? -eq 0 ]; then
    echo "✅ Processo rodando"
else
    echo "⚠️  Processo não encontrado (pode ter terminado)"
fi

echo ""
echo "📊 Progresso:"
ssh diversiplant "tail -3 /opt/diversiplant/logs/ecoregion_raster_deploy.log | grep -oE '[0-9]+%|[0-9]+/[0-9]+' | tail -2"

echo ""
echo "📝 Últimas linhas do log:"
ssh diversiplant "tail -10 /opt/diversiplant/logs/ecoregion_raster_deploy.log | grep -E '(Sampling|✅|⚠️|❌|COMPLETED)'"

echo ""
echo "=================================================="
echo "Para ver log completo:"
echo "ssh diversiplant 'tail -f /opt/diversiplant/logs/ecoregion_raster_deploy.log'"
echo "=================================================="
