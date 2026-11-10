"""Testa os requisitos da carga com dados FICTÍCIOS (CONSINCO_MODO=mock).

    python tests/testar_processo.py

ATENÇÃO: recria o banco configurado no .env. Use um banco de teste.
A planilha fictícia fica em tests/dados_ficticios/entrada/ — a pasta entrada/ (planilha real)
não é lida nem alterada pelos testes.

Cenários:
  1. carga inicial
  2. idempotência: rodar de novo não muda nenhum total
  3. dado retroativo: inclusão, alteração e exclusão dentro da janela
  4. nova versão da planilha (até outubro) substitui a anterior sem duplicar
  4b. versão que traz só o mês novo não apaga os meses anteriores
  5. concorrência: segunda execução é bloqueada enquanto a primeira roda
  6. falha controlada: Consinco fora do ar, planilha segue
  7. carga manual de um dia isolado não esconde o resto do período da carga diária
"""
from __future__ import annotations

import csv
import os
import subprocess
import sys
from pathlib import Path

import psycopg

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
from etl.config import Config  # noqa: E402
from etl.trava import CHAVE_TRAVA  # noqa: E402

cfg = Config()
assert cfg.consinco_modo == "mock", "Rode com CONSINCO_MODO=mock no .env"
assert set(cfg.categorias) == {110, 120}, (
    f"Para os dados fictícios use CATEGORIAS_ESCOPO=AÇOUGUE:110,HORTIFRUTI:120 no .env (hoje: {cfg.categorias})")
DATA_REF = "2026-11-10"
PASTA_TESTE = RAIZ / "tests" / "dados_ficticios" / "entrada"
TOTAIS = """SELECT (SELECT COUNT(*) FROM analitico.fato_avaria), (SELECT SUM(vlr_avaria) FROM analitico.fato_avaria),
                   (SELECT COUNT(*) FROM analitico.fato_venda), (SELECT SUM(vlr_venda_liquida) FROM analitico.fato_venda),
                   (SELECT COUNT(*) FROM analitico.fato_perda_inventario), (SELECT SUM(vlr_falta) FROM analitico.fato_perda_inventario)"""


def rodar(*args: str, env: dict | None = None) -> int:
    cmd = [sys.executable, str(RAIZ / "etl.py"), "--data-referencia", DATA_REF, "--ignorar-horario", *args]
    # PASTA_ENTRADA aponta para a pasta dos testes: a planilha real em entrada/ nunca é usada nem apagada
    env = {**os.environ, "PASTA_ENTRADA": str(PASTA_TESTE), **(env or {})}
    return subprocess.run(cmd, cwd=RAIZ, env=env,
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode


def sql(q: str, p=None):
    with psycopg.connect(cfg.dsn_pg()) as c:
        return c.execute(q, p).fetchall()


def ultima(fonte: str):
    return sql("""SELECT status, linhas_inseridas, linhas_atualizadas, linhas_removidas FROM controle.carga
                  WHERE fonte = %s ORDER BY id_carga DESC LIMIT 1""", (fonte,))[0]


def ok(cond: bool, msg: str):
    print(("  OK   " if cond else "  ERRO ") + msg)
    if not cond:
        logs = sorted(cfg.pasta_logs.glob("etl_*.log"), key=lambda p: p.stat().st_mtime)
        if logs:
            print("\n----- final do log (" + logs[-1].name + ") -----")
            print("\n".join(logs[-1].read_text(encoding="utf-8").splitlines()[-40:]))
        sys.exit(1)


def main():
    py = sys.executable
    subprocess.run([py, "tests/gerar_dados_ficticios.py"], cwd=RAIZ, check=True, stdout=subprocess.DEVNULL)
    subprocess.run([py, "criar_banco.py", "--recriar"], cwd=RAIZ, check=True, stdout=subprocess.DEVNULL)

    print("1. Carga inicial")
    ok(rodar() == 0, "execução com sucesso")
    t1 = sql(TOTAIS)[0]
    print("     totais:", t1)

    print("2. Idempotência (mesmos dados, segunda execução)")
    ok(rodar() == 0, "execução com sucesso")
    ok(sql(TOTAIS)[0] == t1, "totais idênticos")
    ok(ultima("consinco_avaria")[1:] == (0, 0, 0), "avaria: nada inserido/alterado/removido")
    ok(ultima("planilha_inventario")[0] == "IGNORADA", "planilha sem alteração não é reprocessada")

    print("3. Lançamentos retroativos dentro da janela")
    arq = cfg.mock_dir / "avarias.csv"
    linhas = list(csv.DictReader(open(arq, encoding="utf-8")))
    alvo_alt = next(l for l in linhas if l["dta_lancamento"] == "2026-10-15")
    alvo_alt["vlr_movimentacao"] = str(float(alvo_alt["vlr_movimentacao"]) + 100)
    alvo_del = next(l for l in linhas if l["dta_lancamento"] == "2026-10-20")
    linhas.remove(alvo_del)
    linhas.append({"nro_empresa": "1", "seq_produto": "1000", "dta_lancamento": "2026-10-05", "cgo": "999",
                   "seq_categoria": "110", "qtd_lancada": "1", "vlr_movimentacao": "50"})
    with open(arq, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0].keys()))
        w.writeheader()
        w.writerows(linhas)
    ok(rodar() == 0, "execução com sucesso")
    ok(ultima("consinco_avaria")[1:] == (1, 1, 1), "avaria: +1 inserida, ~1 alterada, -1 removida")
    ok(rodar() == 0 and ultima("consinco_avaria")[1:] == (0, 0, 0), "e rodar de novo não muda nada")

    print("4. Nova versão da planilha (até outubro)")
    antes = sql("SELECT COUNT(*) FROM analitico.fato_perda_inventario WHERE data < '2026-10-01'")[0][0]
    subprocess.run([py, "tests/gerar_dados_ficticios.py", "--outubro"], cwd=RAIZ, check=True, stdout=subprocess.DEVNULL)
    ok(rodar() == 0, "execução com sucesso")
    meses = dict(sql("""SELECT to_char(data,'YYYY-MM'), COUNT(*) FROM analitico.fato_perda_inventario GROUP BY 1"""))
    ok("2026-10" in meses, f"outubro carregado {meses}")
    ok(sql("""SELECT COUNT(*) FROM (SELECT nro_empresa, seq_produto, data FROM analitico.fato_perda_inventario
              GROUP BY 1,2,3 HAVING COUNT(*) > 1) d""")[0][0] == 0, "sem duplicidade")
    ok(sql("SELECT COUNT(DISTINCT id_carga) FROM analitico.fato_perda_inventario")[0][0] == 2,
       "todas as linhas vêm da versão nova (1 carga por aba)")
    print(f"     setembro antes={antes} depois={meses.get('2026-09')}")
    ok(rodar() == 0 and ultima("planilha_inventario")[0] == "IGNORADA", "rodar de novo: planilha ignorada")

    print("4b. Versão que traz SÓ outubro não apaga setembro")
    set_antes = sql("SELECT COUNT(*), SUM(vlr_falta) FROM analitico.fato_perda_inventario WHERE data < '2026-10-01'")[0]
    subprocess.run([py, "tests/gerar_dados_ficticios.py", "--so-outubro"], cwd=RAIZ, check=True, stdout=subprocess.DEVNULL)
    ok(rodar() == 0, "execução com sucesso")
    ok(sql("SELECT COUNT(*), SUM(vlr_falta) FROM analitico.fato_perda_inventario WHERE data < '2026-10-01'")[0] == set_antes,
       "setembro mantido da versão anterior (e avisado no log)")

    print("5. Concorrência")
    with psycopg.connect(cfg.dsn_pg(), autocommit=True) as outra:
        outra.execute("SELECT pg_advisory_lock(%s)", (CHAVE_TRAVA,))      # simula execução em andamento
        t = sql(TOTAIS)[0]
        ok(rodar() == 3, "segunda execução sai com código 3 (BLOQUEADA)")
        ok(sql(TOTAIS)[0] == t, "nenhum dado alterado")
    ok(sql("SELECT status FROM controle.execucao ORDER BY id_execucao DESC LIMIT 1")[0][0] == "BLOQUEADA",
       "registrada em controle.execucao")

    print("6. Falha controlada (Consinco fora do ar)")
    code = rodar("--forcar-planilha", env={"MOCK_FALHAR": "1"})
    ok(code == 1, "execução termina como SUCESSO_PARCIAL (código 1)")
    st = dict(sql("""SELECT fonte, status FROM controle.carga WHERE id_execucao =
                     (SELECT MAX(id_execucao) FROM controle.execucao)"""))
    ok(st.get("consinco_lojas") == "FALHA" and st.get("planilha_inventario") == "SUCESSO", f"status por fonte {st}")

    print("7. Carga manual de um dia isolado (teste em produção) + carga diária")
    subprocess.run([py, "criar_banco.py", "--recriar"], cwd=RAIZ, check=True, stdout=subprocess.DEVNULL)
    ok(rodar("--fontes", "consinco", "--inicio", "2026-10-15", "--fim", "2026-10-15") == 0,
       "carga de 1 dia com --inicio/--fim no modo diário")
    dias = sql("SELECT MIN(data), MAX(data) FROM analitico.fato_venda")[0]
    ok(dias[0] == dias[1] and str(dias[0]) == "2026-10-15", f"carregou só o dia pedido {dias}")
    ok(rodar("--fontes", "consinco") == 0, "carga diária em seguida")
    ini = sql("SELECT MIN(data) FROM analitico.fato_venda")[0][0]
    ok(str(ini) == "2026-09-01", f"a diária recuperou desde o início do período (começa em {ini})")
    print("\nTodos os cenários passaram.")


if __name__ == "__main__":
    main()
