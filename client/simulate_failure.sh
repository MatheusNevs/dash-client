#!/bin/bash

# Script para simular falha no Servidor Principal (Porta 8080)
# Requer privilégios de sudo para manipular o iptables.

DURATION=${1:-5} # Padrão: 5 segundos de queda

echo "--- Simulação de Falha Iniciada ---"
echo "[1/3] Bloqueando tráfego para o Servidor A (porta 8080)..."

# Adiciona a regra de bloqueio
sudo iptables -A OUTPUT -p tcp --dport 8080 -j DROP

echo "[2/3] Servidor A está 'caído'. Aguardando $DURATION segundos..."
sleep $DURATION

echo "[3/3] Restaurando conexão com o Servidor A..."
# Remove a regra de bloqueio
sudo iptables -D OUTPUT -p tcp --dport 8080 -j DROP

echo "--- Simulação Concluída. O Servidor A deve estar acessível novamente. ---"
