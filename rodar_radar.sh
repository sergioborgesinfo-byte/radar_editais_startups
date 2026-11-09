#!/bin/bash
# Roda o pipeline a cada hora, por 24 horas
cd ~/Projetos/radar-editais
source .venv/bin/activate 2>/dev/null
for i in $(seq 1 24); do
    echo "=== Rodada $i — $(date) ==="
    python executar_pipeline.py >> rodar_radar.log 2>&1
    echo "=== Fim da rodada $i — $(date) ==="
    if [ $i -lt 24 ]; then
        sleep 3600
    fi
done
echo "=== Loop concluído ==="
