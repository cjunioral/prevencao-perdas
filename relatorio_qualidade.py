"""Gera a tabela de problemas de qualidade (Markdown) a partir do banco.

    python relatorio_qualidade.py > docs/qualidade.md

Junta duas coisas da última carga bem-sucedida de cada fonte/aba:
  * linhas rejeitadas, por motivo (controle.rejeitado);
  * tratamentos aplicados sem rejeitar a linha (controle.carga.avisos).
Cole o resultado na seção de qualidade do README: os números saem do banco,
não de anotação manual.
"""
from __future__ import annotations

from collections import defaultdict

import psycopg

from etl.config import Config

TRATAMENTOS = {
    # motivos de rejeição -> tratamento
    "LOJA_AUSENTE": "Rejeitada. Sem loja não há como atribuir a perda; não se completa por suposição.",
    "LOJA_NAO_ENCONTRADA": "Rejeitada. Aceita nº, 'Loja 05', '05 - Nome' ou nome; só rejeita se nada casar com o cadastro.",
    "PRODUTO_AUSENTE": "Rejeitada.",
    "PRODUTO_NAO_ENCONTRADO": "Rejeitada. Busca por SEQPRODUTO e por EAN; a área deve corrigir o código.",
    "PRODUTO_FORA_ESCOPO": "Rejeitada. Produto existe na Consinco, mas não é Açougue/Hortifruti (diagnóstico consultando a Consinco).",
    "PRODUTO_SEM_CATEGORIA": "Rejeitada.",
    "DATA_AUSENTE": "Rejeitada (quando nem a linha nem o bloco/título informam a data).",
    "DATA_INVALIDA": "Rejeitada. Data impossível (ex.: 31/02) ou futura.",
    "FORA_DO_PERIODO": "Rejeitada por regra de negócio (fora de PERIODO_INICIO/PERIODO_FIM). Registrada para rastreio.",
    "VALOR_AUSENTE": "Rejeitada. Valor em branco não é tratado como zero.",
    "VALOR_INVALIDO": "Rejeitada. Erro de fórmula (#N/D, #REF!) ou texto não numérico.",
    "LINHA_DUPLICADA": "Mantida a 1ª ocorrência; as cópias idênticas são rejeitadas.",
    "DUPLICIDADE_CONFLITANTE": "Todas as ocorrências rejeitadas (não há como saber qual vale). Configurável: somar.",
    "LINHA_TOTALIZADORA": "Rejeitada (estrutura). Somar total + itens duplicaria a perda.",
    "CABECALHO_REPETIDO": "Rejeitada (estrutura).",
    "LINHA_SEM_DADOS": "Rejeitada (estrutura): observação solta, sem loja/produto/data/valor.",
    "LOJA_NAO_CADASTRADA": "Rejeitada (Consinco).",
    "VALOR_NULO_CONSINCO": "Rejeitada (Consinco).",
    # avisos -> tratamento (linha carregada)
    "linhas_de_titulo_antes_do_cabecalho": "Cabeçalho localizado automaticamente; título ignorado.",
    "intervalos_mesclados_propagados": "Valor da célula mesclada copiado para todas as linhas do bloco.",
    "linhas_em_branco_ignoradas": "Ignoradas (não são registros).",
    "linhas_ocultas_lidas": "Lidas normalmente (dado oculto continua sendo dado). Decisão registrada.",
    "valor_texto_convertido": "Texto 'R$ -1.234,56' convertido para número.",
    "valor_formato_contabil": "'(1.234,56)' interpretado como negativo.",
    "data_texto_convertida": "Texto dd/mm/aaaa convertido para data.",
    "data_numero_serial": "Número serial do Excel convertido para data.",
    "codigo_interpretado_como_ean": "Código na coluna de produto era EAN; ligado pelo cadastro de códigos.",
    "loja_ou_data_herdada_do_bloco": "Loja/data vindas da linha de título do bloco.",
    "linhas_de_contexto": "Linha de título de bloco (loja/data) usada como contexto, não como dado.",
    "categoria_consinco_difere_da_aba": "Carregada com a categoria da Consinco (fonte da verdade); sinalizada.",
    "formula_sem_valor_calculado": "Fórmula sem valor em cache (arquivo salvo fora do Excel): tratada como valor ausente.",
    "linhas_somadas_mesma_chave": "Somadas (DUPLICIDADE_CONFLITANTE=somar).",
    "ean_com_mais_de_um_produto": "EAN ligado a mais de um produto: usado o menor SEQPRODUTO; sinalizado.",
    "estoque_sistema_negativo": "Carregada e sinalizada: estoque negativo no sistema não gera falta, só sobra.",
    "meses_mantidos_da_versao_anterior": "Mês ausente na nova versão mantido da versão anterior (log com WARNING).",
    "loja_sem_regional": "Loja carregada na regional 'SEM REGIONAL' (não some do painel).",
    "produto_em_mais_de_uma_categoria": "Família com 2 ligações ativas: mantida a 1ª; sinalizado.",
}


def main() -> None:
    cfg = Config()
    with psycopg.connect(cfg.dsn_pg()) as con:
        rej = con.execute("""SELECT fonte, COALESCE(aba, '-'), motivo, tipo_motivo, descricao_motivo, COUNT(*)
                             FROM controle.vw_rejeitado_vigente GROUP BY 1,2,3,4,5 ORDER BY 1,2,6 DESC""").fetchall()
        avisos = con.execute("""
            SELECT DISTINCT ON (fonte, COALESCE(aba, '')) fonte, COALESCE(aba, '-'), avisos
            FROM controle.carga WHERE status = 'SUCESSO' AND avisos IS NOT NULL
            ORDER BY fonte, COALESCE(aba, ''), inicio DESC""").fetchall()

    print("### Linhas rejeitadas (não entram no analítico)\n")
    print("| Fonte / aba | Problema | Tipo | Linhas | Tratamento |")
    print("|---|---|---|---:|---|")
    for fonte, aba, motivo, tipo, desc, n in rej:
        print(f"| {fonte} / {aba.strip()} | {desc} (`{motivo}`) | {tipo} | {n} | {TRATAMENTOS.get(motivo, '')} |")

    print("\n### Tratamentos aplicados (linha corrigida e carregada)\n")
    print("| Fonte / aba | Problema | Ocorrências | Tratamento |")
    print("|---|---|---:|---|")
    por = defaultdict(dict)
    for fonte, aba, av in avisos:
        por[(fonte, aba)] = av
    for (fonte, aba), av in sorted(por.items()):
        for k, n in sorted(av.items(), key=lambda x: -x[1]):
            if k == "codigos_ean":
                continue
            print(f"| {fonte} / {aba.strip()} | `{k}` | {n} | {TRATAMENTOS.get(k, '')} |")


if __name__ == "__main__":
    main()
