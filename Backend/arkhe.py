"""Integração com a API Arkhé (conta PJ + cobranças Pix).

Cada barbearia utiliza suas próprias credenciais Arkhé, armazenadas na tabela
PERSONALIZACAO nos campos ARKHE_CLIENT_ID e ARKHE_CLIENT_SECRET.

O navegador nunca recebe essas credenciais. Todas as chamadas para a Arkhé
são realizadas exclusivamente pelo backend.
"""

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta

from flask import Response, jsonify, request

from main import app, conectar_banco
from funcoes import decodificar_token


TIMEOUT_SEGUNDOS = 20
REGEX_DATA = re.compile(r'^\d{4}-\d{2}-\d{2}$')


# ==========================================================
# RESPOSTAS
# ==========================================================

def _erro(mensagem, status):
    return jsonify({
        'mensagem': {
            'informacao': mensagem,
            'tipo': 'erro'
        }
    }), status


# ==========================================================
# EXCEÇÃO ARKHÉ
# ==========================================================

class ArkheErro(Exception):
    def __init__(self, mensagem, status=502):
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.status = status


# ==========================================================
# CLIENTE HTTP DA ARKHÉ
# ==========================================================

def _chamar_arkhe(
        metodo,
        caminho,
        params=None,
        corpo=None,
        credenciais=None
):
    client_id, client_secret = credenciais or (None, None)

    if not client_id or not client_secret:
        raise ArkheErro(
            'Conta Arkhé da barbearia não configurada. '
            'Cadastre o Client ID e o Client Secret '
            'na personalização da barbearia.',
            503
        )

    base_url = (
            app.config.get('ARKHE_BASE_URL') or ''
    ).strip().rstrip('/')

    if not base_url:
        raise ArkheErro(
            'ARKHE_BASE_URL não está configurada no servidor.',
            503
        )

    url = base_url + caminho

    if params:
        url += '?' + urllib.parse.urlencode(params)

    headers = {
        'X-Client-ID': client_id,
        'X-Client-Secret': client_secret,
        'Accept': 'application/json'
    }

    dados = None

    if corpo is not None:
        dados = json.dumps(corpo).encode('utf-8')
        headers['Content-Type'] = 'application/json'

    requisicao = urllib.request.Request(
        url,
        data=dados,
        headers=headers,
        method=metodo
    )

    try:
        with urllib.request.urlopen(
                requisicao,
                timeout=TIMEOUT_SEGUNDOS
        ) as resposta:
            texto = resposta.read().decode('utf-8')

    except urllib.error.HTTPError as erro:
        texto = erro.read().decode(
            'utf-8',
            errors='replace'
        )

        try:
            detalhe_json = json.loads(texto) if texto else {}
        except ValueError:
            detalhe_json = {}

        detalhe = None

        if isinstance(detalhe_json, dict):
            detalhe = (
                    detalhe_json.get('mensagem')
                    or detalhe_json.get('message')
                    or detalhe_json.get('detail')
                    or detalhe_json.get('erro')
                    or detalhe_json.get('error')
            )

            if isinstance(detalhe, dict):
                detalhe = (
                        detalhe.get('informacao')
                        or detalhe.get('message')
                        or detalhe.get('mensagem')
                )

        if erro.code == 400:
            mensagem = detalhe or (
                'A Arkhé recusou os dados enviados.'
            )
            raise ArkheErro(mensagem, 400)

        if erro.code == 401:
            raise ArkheErro(
                'Client ID ou Client Secret da Arkhé inválidos.',
                502
            )

        if erro.code == 403:
            raise ArkheErro(
                'A integração Arkhé está sem permissão '
                'ou desativada.',
                502
            )

        if erro.code == 404:
            raise ArkheErro(
                detalhe or 'Recurso não encontrado na Arkhé.',
                404
            )

        if erro.code >= 500:
            raise ArkheErro(
                'A API da Arkhé apresentou um erro interno.',
                502
            )

        raise ArkheErro(
            detalhe or f'Arkhé retornou HTTP {erro.code}.',
            502
        )

    except urllib.error.URLError as erro:

        raise ArkheErro(
            'Não foi possível conectar à Arkhé.',
            502
        )

    except TimeoutError as erro:

        raise ArkheErro(
            'A Arkhé demorou demais para responder.',
            504
        )

    try:
        return json.loads(texto) if texto else {}

    except ValueError:

        raise ArkheErro(
            'A Arkhé retornou uma resposta inválida.',
            502
        )


# ==========================================================
# CONTROLE DE ACESSO
# ==========================================================

def _autorizado():
    token = decodificar_token()

    if not token:
        return None, _erro(
            'Sessão ausente ou expirada.',
            401
        )

    try:
        tipo = int(token.get('tipo', -1))
    except (TypeError, ValueError):
        tipo = -1

    if tipo not in (0, 2):
        return None, _erro(
            'Acesso exclusivo para barbearias '
            'e administradores.',
            403
        )

    return token, None


# ==========================================================
# PERÍODO
# ==========================================================

def _periodo():
    params = {}

    for campo in ('data_inicio', 'data_fim'):
        valor = request.args.get(campo)

        if valor:
            if not REGEX_DATA.match(valor):
                raise ArkheErro(
                    f'{campo} deve estar no formato AAAA-MM-DD.',
                    400
                )

            try:
                ano, mes, dia = map(
                    int,
                    valor.split('-')
                )

                date(ano, mes, dia)

            except ValueError:
                raise ArkheErro(
                    f'{campo} contém uma data inválida.',
                    400
                )

            params[campo] = valor

    return params


# ==========================================================
# CREDENCIAIS DA BARBEARIA
# ==========================================================

def _credenciais_da_barbearia(id_barbearia):

    if not id_barbearia:
        return None, None

    con = None
    cursor = None

    try:
        con = conectar_banco()
        cursor = con.cursor()

        cursor.execute(
            """
            SELECT
                ARKHE_CLIENT_ID,
                ARKHE_CLIENT_SECRET
            FROM PERSONALIZACAO
            WHERE ID_USUARIO = ?
            """,
            (int(id_barbearia),)
        )

        linha = cursor.fetchone()

        if not linha:
            return None, None

        client_id = str(
            linha[0] or ''
        ).strip()

        client_secret = str(
            linha[1] or ''
        ).strip()

        if not client_id or not client_secret:
            return None, None

        return client_id, client_secret

    except Exception as erro:

        return None, None

    finally:
        if cursor:
            try:
                cursor.close()
            except Exception:
                pass

        if con:
            try:
                con.close()
            except Exception:
                pass


# ==========================================================
# CONTEXTO FINANCEIRO
# ==========================================================

def _contexto_financeiro():
    token, negado = _autorizado()

    if negado:
        raise ArkheErro(
            'Sessão ausente, expirada ou sem permissão.',
            401
        )

    try:
        tipo = int(
            token.get('tipo', -1)
        )
    except (TypeError, ValueError):
        tipo = -1

    id_barbearia = None

    if tipo == 2:
        try:
            id_barbearia = int(
                token['id_usuario']
            )
        except (KeyError, TypeError, ValueError):
            raise ArkheErro(
                'Não foi possível identificar '
                'a barbearia logada.',
                401
            )

    elif tipo == 0:
        id_barbearia = request.args.get(
            'id_barbearia',
            type=int
        )

    credenciais = _credenciais_da_barbearia(
        id_barbearia
    )

    return id_barbearia, credenciais


# ==========================================================
# MOVIMENTAÇÕES LOCAIS
# ==========================================================

TIPOS_PAGOS_LOCAIS = (
    'pix_pago',
    'boleto_pago',
    'cartao_pago',
    'na_hora'
)

RE_AGENDAMENTO = re.compile(
    r'ag#(\d+)'
)


def _movimentacoes_locais(
        id_barbearia,
        data_inicio,
        data_fim,
        tipos=None
):
    data_inicio = (
            data_inicio or '2000-01-01'
    )

    data_fim = (
            data_fim or date.today().isoformat()
    )

    con = conectar_banco()
    cursor = con.cursor()

    try:
        tipos = tuple(tipos or TIPOS_PAGOS_LOCAIS)
        marcadores_tipos = ','.join('?' for _ in tipos)

        cursor.execute(
            """
            SELECT
                ID_FINANCEIRO,
                TIPO,
                DESCRICAO,
                VALOR,
                DATA_TRANSACAO
            FROM FINANCEIRO
            WHERE TIPO IN (""" + marcadores_tipos + """)
              AND CAST(DATA_TRANSACAO AS DATE)
                BETWEEN ? AND ?
            """,
            [
                *tipos,
                data_inicio,
                data_fim
            ]
        )

        linhas = cursor.fetchall()

        ids_agendamento = set()

        for linha in linhas:
            achado = RE_AGENDAMENTO.search(
                str(linha[2] or '')
            )

            if achado:
                ids_agendamento.add(
                    int(achado.group(1))
                )

        barbearias = {}

        if ids_agendamento:
            marcadores = ','.join(
                '?' for _ in ids_agendamento
            )

            cursor.execute(
                f"""
                SELECT
                    A.ID_AGENDAMENTO,
                    A.ID_BARBEARIA,
                    U.NOME
                FROM AGENDAMENTO A
                         LEFT JOIN USUARIO U
                                   ON U.ID_USUARIO = A.ID_BARBEARIA
                WHERE ID_AGENDAMENTO
                IN ({marcadores})
                """,
                list(ids_agendamento)
            )

            barbearias = {
                registro[0]: {
                    'id_barbearia': registro[1],
                    'nome': registro[2]
                }
                for registro in cursor.fetchall()
            }

    finally:
        cursor.close()
        con.close()

    movimentacoes = []

    for (
            id_financeiro,
            tipo,
            descricao,
            valor,
            data_transacao
    ) in linhas:

        achado = RE_AGENDAMENTO.search(
            str(descricao or '')
        )

        id_agendamento = (
            int(achado.group(1))
            if achado
            else None
        )

        barbearia = barbearias.get(id_agendamento)

        if id_barbearia and (
                not barbearia
                or barbearia['id_barbearia'] != id_barbearia
        ):
            continue

        if hasattr(data_transacao, 'date'):
            data_movimentacao = (
                data_transacao.date().isoformat()
            )
        else:
            data_movimentacao = str(
                data_transacao or ''
            )[:10]

        movimentacoes.append({
            'id_movimentacao':
                f'local-{id_financeiro}',

            'tipo':
                'entrada',

            'valor':
                float(valor or 0),

            'data_movimentacao':
                data_movimentacao,

            'origem': {
                'pix_pago': 'pix',
                'boleto_pago': 'boleto',
                'cartao_pago': 'cartao',
                'na_hora': 'na_hora'
            }.get(str(tipo or '').lower(), 'outros'),

            'id_barbearia': (
                barbearia['id_barbearia']
                if barbearia else None
            ),

            'barbearia_nome': (
                barbearia['nome']
                if barbearia else None
            ),

            'nome_contraparte':
                (
                    f'Pagamento na hora · Agendamento #{id_agendamento}'
                    if tipo == 'na_hora' else f'Agendamento #{id_agendamento}'
                    if id_agendamento
                    else (
                            descricao
                            or 'Recebimento'
                    )
                )
        })

    movimentacoes.sort(
        key=lambda item:
        item['data_movimentacao'] or ''
    )

    return movimentacoes


# ==========================================================
# EXECUTOR
# ==========================================================

def _executar(funcao):
    _, negado = _autorizado()

    if negado:
        return negado

    try:
        return jsonify(
            funcao()
        ), 200

    except ArkheErro as erro:
        return _erro(
            erro.mensagem,
            erro.status
        )

    except Exception as erro:


        return _erro(
            'Erro interno ao consultar a Arkhé.',
            500
        )


# ==========================================================
# NORMALIZAÇÃO
# ==========================================================

def _numero(valor, padrao=0.0):
    try:
        if isinstance(valor, str):
            valor = valor.strip()

            if ',' in valor:
                valor = (
                    valor
                    .replace('.', '')
                    .replace(',', '.')
                )

        return float(valor)

    except (TypeError, ValueError):
        return padrao


def _primeiro(dicionario, *chaves):
    if not isinstance(
            dicionario,
            dict
    ):
        return None

    for chave in chaves:
        valor = dicionario.get(chave)

        if valor not in (None, ''):
            return valor

    return None


def _normalizar_movimentacao(
        item,
        indice
):
    if not isinstance(item, dict):
        item = {}

    tipo_bruto = str(
        _primeiro(
            item,
            'tipo',
            'type',
            'natureza',
            'operacao'
        ) or ''
    ).strip().lower()

    valor = _numero(
        _primeiro(
            item,
            'valor',
            'amount',
            'total',
            'quantia'
        )
    )

    if tipo_bruto in (
            'entrada',
            'in',
            'credit',
            'credito',
            'receita',
            'receitas',
            'ganho',
            'ganhos'
    ):
        tipo = 'entrada'

    elif tipo_bruto in (
            'saida',
            'saída',
            'out',
            'debit',
            'debito',
            'despesa',
            'despesas',
            'custo',
            'custos'
    ):
        tipo = 'saida'

    else:
        tipo = (
            'entrada'
            if valor >= 0
            else 'saida'
        )

    return {
        'id_movimentacao':
            _primeiro(
                item,
                'id_movimentacao',
                'id',
                'codigo'
            ) or indice,

        'tipo':
            tipo,

        'valor':
            abs(valor),

        'data_movimentacao':
            str(
                _primeiro(
                    item,
                    'data_movimentacao',
                    'data',
                    'date',
                    'created_at',
                    'criado_em'
                ) or ''
            )[:10],

        'origem':
            str(
                _primeiro(
                    item,
                    'origem',
                    'metodo',
                    'method',
                    'canal'
                ) or 'outros'
            ).lower(),

        'nome_contraparte':
            _primeiro(
                item,
                'nome_contraparte',
                'contraparte',
                'descricao',
                'description',
                'nome'
            ) or '—'
    }


def _lista_de_movimentacoes(resposta):
    if isinstance(resposta, list):
        return resposta

    if isinstance(resposta, dict):
        for chave in (
                'movimentacoes',
                'movimentacao',
                'items',
                'data',
                'dados',
                'resultados',
                'results',
                'lista'
        ):
            valor = resposta.get(chave)

            if isinstance(valor, list):
                return valor

    return []


# ==========================================================
# FONTE DAS MOVIMENTAÇÕES
# ==========================================================

def _movimentacoes_fonte(
        params,
        credenciais,
        id_barbearia
):
    if (
            credenciais
            and credenciais[0]
            and credenciais[1]
    ):
        try:
            resposta = _chamar_arkhe(
                'GET',
                '/api/v1/movimentacoes',
                params=params,
                credenciais=credenciais
            )

            movimentacoes = [
                _normalizar_movimentacao(
                    item,
                    indice + 1
                )
                for indice, item
                in enumerate(
                    _lista_de_movimentacoes(
                        resposta
                    )
                )
            ]

            if params.get('data_inicio'):
                movimentacoes = [
                    mov
                    for mov in movimentacoes
                    if (
                               mov['data_movimentacao']
                               or ''
                       ) >= params['data_inicio']
                ]

            if params.get('data_fim'):
                movimentacoes = [
                    mov
                    for mov in movimentacoes
                    if (
                               mov['data_movimentacao']
                               or ''
                       ) <= params['data_fim']
                ]

            # Cobranças Pix, cartão e boleto já estão na Arkhé. O pagamento
            # presencial não passa por ela, então acrescentamos SOMENTE os
            # lançamentos ``na_hora`` do sistema local para não duplicar os
            # demais valores no controle de caixa.
            movimentacoes.extend(
                _movimentacoes_locais(
                    id_barbearia,
                    params.get('data_inicio'),
                    params.get('data_fim'),
                    tipos=('na_hora',)
                )
            )
            movimentacoes.sort(
                key=lambda mov: str(mov.get('data_movimentacao') or ''),
                reverse=True
            )
            return movimentacoes, 'arkhe+na_hora'

        except ArkheErro as erro:
            print(
                '===== ARKHÉ INDISPONÍVEL ====='
            )
            print(
                'MOTIVO:',
                erro.mensagem
            )

    else:
        print(
            '===== SEM CREDENCIAIS ARKHÉ ====='
        )
        print(
            'ID BARBEARIA:',
            id_barbearia
        )

    return (
        _movimentacoes_locais(
            id_barbearia,
            params.get('data_inicio'),
            params.get('data_fim')
        ),
        'local'
    )


def _movimentacoes_gerais_adm(params):
    """Combina, por barbearia, a conta Arkhé e o caixa local.

    Pix/cartão/boleto vêm da Arkhé quando ela responde. ``na_hora`` é local e
    entra sempre junto. Se uma conta não puder ser consultada, os lançamentos
    locais daquela barbearia continuam visíveis para o ADM.
    """
    con = conectar_banco()
    cursor = con.cursor()
    try:
        cursor.execute("""
            SELECT U.ID_USUARIO, U.NOME, P.ARKHE_CLIENT_ID, P.ARKHE_CLIENT_SECRET
            FROM USUARIO U
            LEFT JOIN PERSONALIZACAO P ON P.ID_USUARIO = U.ID_USUARIO
            WHERE U.TIPO = 2 AND U.ATIVO = 1
            ORDER BY U.ID_USUARIO
        """)
        barbearias = cursor.fetchall()
    finally:
        cursor.close()
        con.close()

    locais = _movimentacoes_locais(
        None, params.get('data_inicio'), params.get('data_fim')
    )
    locais_por_barbearia = {}
    for movimentacao in locais:
        locais_por_barbearia.setdefault(
            movimentacao.get('id_barbearia'), []
        ).append(movimentacao)

    resultado = []
    consultadas_na_arkhe = set()
    falhas_arkhe = []

    for id_barbearia, nome, client_id, client_secret in barbearias:
        credenciais = (str(client_id or '').strip(), str(client_secret or '').strip())
        locais_da_barbearia = locais_por_barbearia.get(id_barbearia, [])

        if all(credenciais):
            try:
                resposta = _chamar_arkhe(
                    'GET', '/api/v1/movimentacoes', params=params,
                    credenciais=credenciais
                )
                movimentos_arkhe = [
                    _normalizar_movimentacao(item, indice + 1)
                    for indice, item in enumerate(_lista_de_movimentacoes(resposta))
                ]
                movimentos_arkhe = [
                    mov for mov in movimentos_arkhe
                    if (not params.get('data_inicio') or mov['data_movimentacao'] >= params['data_inicio'])
                    and (not params.get('data_fim') or mov['data_movimentacao'] <= params['data_fim'])
                ]

                # Mantém uma cópia de consulta no banco da plataforma. Assim,
                # o administrador vê o extrato que veio da Arkhé mesmo que a
                # conta da barbearia fique temporariamente indisponível depois.
                _salvar_snapshot_arkhe(
                    id_barbearia, movimentos_arkhe,
                    params.get('data_inicio'), params.get('data_fim')
                )

                # Com dados bancários disponíveis, eles são a fonte oficial
                # para cobranças online. Apenas o presencial vem do caixa local.
                if movimentos_arkhe:
                    consultadas_na_arkhe.add(id_barbearia)
                    for mov in movimentos_arkhe:
                        mov['id_movimentacao'] = f'arkhe-{id_barbearia}-{mov["id_movimentacao"]}'
                        mov['id_barbearia'] = id_barbearia
                        mov['barbearia_nome'] = nome
                    resultado.extend(movimentos_arkhe)
                else:
                    # Sem dados no extrato, preserva os pagamentos locais para
                    # que um atraso de sincronização não esconda valores do ADM.
                    resultado.extend(locais_da_barbearia)
                    continue
            except ArkheErro as erro:
                falhas_arkhe.append({'id_barbearia': id_barbearia, 'mensagem': erro.mensagem})

        if id_barbearia in consultadas_na_arkhe:
            resultado.extend(
                mov for mov in locais_da_barbearia
                if mov.get('origem') == 'na_hora'
            )
        else:
            resultado.extend(locais_da_barbearia)

    resultado.sort(
        key=lambda mov: str(mov.get('data_movimentacao') or ''), reverse=True
    )
    origem = 'arkhe+local' if consultadas_na_arkhe else 'financeiro_local'
    return resultado, origem, falhas_arkhe


def _resumo_de_movimentacoes(
        movimentacoes
):
    receitas = round(
        sum(
            mov['valor']
            for mov in movimentacoes
            if mov['tipo'] == 'entrada'
        ),
        2
    )

    despesas = round(
        sum(
            mov['valor']
            for mov in movimentacoes
            if mov['tipo'] == 'saida'
        ),
        2
    )

    return {
        'total_receitas':
            receitas,

        'total_despesas':
            despesas,

        'saldo_periodo':
            round(
                receitas - despesas,
                2
            )
    }


def _parse_data_opt(valor):
    try:
        if (
                valor
                and REGEX_DATA.match(
            str(valor)
        )
        ):
            ano, mes, dia = map(
                int,
                str(valor).split('-')
            )

            return date(
                ano,
                mes,
                dia
            )

    except (
            TypeError,
            ValueError
    ):
        pass

    return None


# ==========================================================
# SNAPSHOT
# ==========================================================

def _garantir_snapshot(cursor):
    cursor.execute(
        """
        SELECT 1
        FROM RDB$RELATIONS
        WHERE TRIM(RDB$RELATION_NAME)
                  = 'FINANCEIRO_SNAPSHOT'
        """
    )

    if cursor.fetchone() is None:
        cursor.execute(
            """
            CREATE TABLE FINANCEIRO_SNAPSHOT (
                                                 ID_SNAPSHOT INTEGER NOT NULL PRIMARY KEY,
                                                 ID_BARBEARIA INTEGER NOT NULL,
                                                 DATA_MOV DATE NOT NULL,
                                                 TIPO VARCHAR(10) NOT NULL,
                                                 ORIGEM VARCHAR(30),
                                                 DESCRICAO VARCHAR(255),
                                                 VALOR NUMERIC(12,2)
                                                     DEFAULT 0 NOT NULL,
                                                 FONTE VARCHAR(10),
                                                 ATUALIZADO_EM TIMESTAMP
                                                     DEFAULT CURRENT_TIMESTAMP
                                                     NOT NULL
            )
            """
        )

    cursor.execute(
        """
        SELECT 1
        FROM RDB$GENERATORS
        WHERE TRIM(RDB$GENERATOR_NAME)
                  = 'SEQ_FINANCEIRO_SNAPSHOT'
        """
    )

    if cursor.fetchone() is None:
        cursor.execute(
            'CREATE SEQUENCE '
            'SEQ_FINANCEIRO_SNAPSHOT'
        )

    cursor.execute(
        """
        SELECT 1
        FROM RDB$INDICES
        WHERE TRIM(RDB$INDEX_NAME)
                  = 'IDX_FINSNAP_BARB_DATA'
        """
    )

    if cursor.fetchone() is None:
        cursor.execute(
            """
            CREATE INDEX IDX_FINSNAP_BARB_DATA
                ON FINANCEIRO_SNAPSHOT
                    (ID_BARBEARIA, DATA_MOV)
            """
        )


def _sincronizar_snapshot(
        cursor,
        id_barbearia,
        movimentacoes,
        data_inicio,
        data_fim,
        fonte
):
    if not id_barbearia:
        return

    try:
        _garantir_snapshot(cursor)

        di = (
                _parse_data_opt(data_inicio)
                or (
                        date.today()
                        - timedelta(days=92)
                )
        )

        df = (
                _parse_data_opt(data_fim)
                or date.today()
        )

        cursor.execute(
            """
            DELETE FROM FINANCEIRO_SNAPSHOT
            WHERE ID_BARBEARIA = ?
              AND DATA_MOV BETWEEN ? AND ?
            """,
            (
                id_barbearia,
                di,
                df
            )
        )

        for mov in movimentacoes or []:
            dm = _parse_data_opt(
                mov.get(
                    'data_movimentacao'
                )
            )

            if not dm:
                continue

            cursor.execute(
                """
                INSERT INTO FINANCEIRO_SNAPSHOT
                (
                    ID_SNAPSHOT,
                    ID_BARBEARIA,
                    DATA_MOV,
                    TIPO,
                    ORIGEM,
                    DESCRICAO,
                    VALOR,
                    FONTE
                )
                VALUES
                    (
                        NEXT VALUE FOR
                             SEQ_FINANCEIRO_SNAPSHOT,
                             ?, ?, ?, ?, ?, ?, ?
                    )
                """,
                (
                    id_barbearia,
                    dm,
                    mov.get('tipo'),
                    str(
                        mov.get('origem')
                        or ''
                    )[:30],
                    str(
                        mov.get(
                            'nome_contraparte'
                        )
                        or ''
                    )[:255],
                    float(
                        mov.get('valor')
                        or 0
                    ),
                    fonte
                )
            )

    except Exception as erro:
        print(
            'SNAPSHOT: falha ao salvar:',
            repr(erro)
        )


def _salvar_snapshot_arkhe(
        id_barbearia,
        movimentacoes,
        data_inicio,
        data_fim
):
    """Persiste o extrato já normalizado sem interromper a consulta ao ADM."""
    con = conectar_banco()
    cursor = con.cursor()

    try:
        _sincronizar_snapshot(
            cursor, id_barbearia, movimentacoes,
            data_inicio, data_fim, 'arkhe'
        )
        con.commit()
    except Exception as erro:
        con.rollback()
        print('SNAPSHOT ARKHE: falha ao salvar:', repr(erro))
    finally:
        cursor.close()
        con.close()


def _ler_snapshot(
        cursor,
        data_inicio,
        data_fim,
        id_barbearia=None
):
    _garantir_snapshot(cursor)

    di = (
            _parse_data_opt(data_inicio)
            or (
                    date.today()
                    - timedelta(days=29)
            )
    )

    df = (
            _parse_data_opt(data_fim)
            or date.today()
    )

    if id_barbearia:
        cursor.execute(
            """
            SELECT
                S.ID_SNAPSHOT,
                S.ID_BARBEARIA,
                U.NOME,
                S.DATA_MOV,
                S.TIPO,
                S.ORIGEM,
                S.DESCRICAO,
                S.VALOR
            FROM FINANCEIRO_SNAPSHOT S
                     LEFT JOIN USUARIO U
                               ON U.ID_USUARIO =
                                  S.ID_BARBEARIA
            WHERE S.ID_BARBEARIA = ?
              AND S.DATA_MOV BETWEEN ? AND ?
            ORDER BY
                S.DATA_MOV DESC,
                S.ID_SNAPSHOT DESC
            """,
            (
                id_barbearia,
                di,
                df
            )
        )

    else:
        cursor.execute(
            """
            SELECT
                S.ID_SNAPSHOT,
                S.ID_BARBEARIA,
                U.NOME,
                S.DATA_MOV,
                S.TIPO,
                S.ORIGEM,
                S.DESCRICAO,
                S.VALOR
            FROM FINANCEIRO_SNAPSHOT S
                     LEFT JOIN USUARIO U
                               ON U.ID_USUARIO =
                                  S.ID_BARBEARIA
            WHERE S.DATA_MOV BETWEEN ? AND ?
            ORDER BY
                S.DATA_MOV DESC,
                S.ID_SNAPSHOT DESC
            """,
            (
                di,
                df
            )
        )

    movimentacoes = []

    for (
            id_snapshot,
            id_barb,
            nome,
            data_mov,
            tipo,
            origem,
            descricao,
            valor
    ) in cursor.fetchall():

        data_formatada = (
            data_mov.date().isoformat()
            if hasattr(
                data_mov,
                'date'
            )
            else str(
                data_mov or ''
            )[:10]
        )

        movimentacoes.append({
            'id_movimentacao':
                id_snapshot,

            'id_barbearia':
                id_barb,

            'barbearia_nome':
                nome
                or f'Barbearia #{id_barb}',

            'tipo':
                tipo,

            'valor':
                float(valor or 0),

            'data_movimentacao':
                data_formatada,

            'origem':
                origem or 'outros',

            'nome_contraparte':
                descricao or '—'
        })

    return movimentacoes, di, df


# ==========================================================
# GRÁFICO
# ==========================================================

def _brl(valor):
    texto = f'{float(valor):,.2f}'

    return (
            'R$ '
            + texto
            .replace(',', 'X')
            .replace('.', ',')
            .replace('X', '.')
    )


def _resposta_grafico_linha(
        data_inicio,
        data_fim,
        movimentacoes,
        tipo,
        subtitulo
):
    import pygal
    from pygal.style import Style

    dias = []
    ganhos = []
    custos = []

    cursor_data = data_inicio

    while cursor_data <= data_fim:
        chave = cursor_data.isoformat()

        dias.append(
            cursor_data.strftime('%d/%m')
        )

        ganhos.append(
            round(
                sum(
                    mov['valor']
                    for mov in movimentacoes
                    if (
                            mov['tipo']
                            == 'entrada'
                            and
                            mov['data_movimentacao']
                            == chave
                    )
                ),
                2
            )
        )

        custos.append(
            round(
                sum(
                    mov['valor']
                    for mov in movimentacoes
                    if (
                            mov['tipo']
                            == 'saida'
                            and
                            mov['data_movimentacao']
                            == chave
                    )
                ),
                2
            )
        )

        cursor_data += timedelta(
            days=1
        )

    passo = max(
        1,
        len(dias) // 8
    )

    estilo = Style(
        background='transparent',
        plot_background='#ffffff',
        foreground='#333333',
        foreground_strong='#111111',
        foreground_subtle='#9aa0a6',
        opacity='.9',
        colors=(
            '#e03131',
        ) if tipo == 'custos' else (
            '#16a34a',
        ) if tipo == 'ganhos' else (
            '#16a34a',
            '#e03131'
        ),
        label_font_size=11,
        major_label_font_size=11,
        value_font_size=10,
        title_font_size=15,
        legend_font_size=12
    )

    grafico = pygal.Line(
        style=estilo,
        width=1000,
        height=380,
        explicit_size=True,
        title=(
            'Desempenho financeiro — '
            f'{subtitulo}'
        ),
        x_labels=dias,
        x_label_rotation=0,
        x_labels_major=dias[::passo],
        show_minor_x_labels=False,
        show_dots=True,
        dots_size=2,
        stroke_style={
            'width': 2.5
        },
        interpolate='cubic',
        fill=False,
        show_legend=(
                tipo == 'todos'
        ),
        legend_at_bottom=True,
        show_y_guides=True,
        value_formatter=_brl,
        y_label_formatter=_brl,
        margin=24
    )

    if tipo in (
            'todos',
            'ganhos'
    ):
        grafico.add(
            'Ganhos',
            ganhos
        )

    if tipo in (
            'todos',
            'custos'
    ):
        grafico.add(
            'Custos',
            custos
        )

    svg = grafico.render().decode(
        'utf-8'
    )

    svg = re.sub(
        r'<svg([^>]*?)width="\d+"([^>]*?)height="\d+"',
        r'<svg\1width="100%"\2height="auto"',
        svg,
        count=1
    )

    if 'viewBox' not in svg[:3000]:
        svg = svg.replace(
            '<svg ',
            '<svg viewBox="0 0 1000 380" ',
            1
        )

    return Response(
        svg,
        mimetype='image/svg+xml'
    )


# ==========================================================
# ADMIN
# ==========================================================

def _exigir_admin():
    token, negado = _autorizado()

    if negado:
        raise ArkheErro(
            'Sessão ausente ou expirada.',
            401
        )

    if int(
            token.get('tipo', -1)
    ) != 0:
        raise ArkheErro(
            'Análise geral exclusiva '
            'do administrador.',
            403
        )

    return token


# ==========================================================
# CONTA
# ==========================================================

@app.route(
    '/financeiro/conta',
    methods=['GET']
)
def financeiro_conta():

    def buscar():
        _, credenciais = (
            _contexto_financeiro()
        )

        if (
                not credenciais
                or not credenciais[0]
                or not credenciais[1]
        ):
            raise ArkheErro(
                'Conta Arkhé não configurada. '
                'Cadastre o Client ID e '
                'o Client Secret na personalização '
                'da barbearia.',
                503
            )

        return _chamar_arkhe(
            'GET',
            '/api/v1/conta',
            credenciais=credenciais
        )

    return _executar(buscar)


# ==========================================================
# SALDO
# ==========================================================

@app.route(
    '/financeiro/saldo',
    methods=['GET']
)
def financeiro_saldo():

    def buscar():
        id_barbearia, credenciais = (
            _contexto_financeiro()
        )

        if (
                credenciais
                and credenciais[0]
                and credenciais[1]
        ):
            try:
                resposta = _chamar_arkhe(
                    'GET',
                    '/api/v1/saldo',
                    credenciais=credenciais
                )

                if isinstance(
                        resposta,
                        dict
                ):
                    return {
                        'saldo':
                            _numero(
                                _primeiro(
                                    resposta,
                                    'saldo',
                                    'saldo_atual',
                                    'balance',
                                    'valor',
                                    'total'
                                )
                            ),

                        'origem_dados':
                            'arkhe'
                    }

                return {
                    'saldo':
                        _numero(resposta),

                    'origem_dados':
                        'arkhe'
                }

            except ArkheErro as erro:
                print(
                    'ARKHE: saldo local:',
                    erro.mensagem
                )

        movimentacoes = (
            _movimentacoes_locais(
                id_barbearia,
                None,
                None
            )
        )

        return {
            'saldo':
                round(
                    sum(
                        mov['valor']
                        for mov
                        in movimentacoes
                    ),
                    2
                ),

            'origem_dados':
                'local'
        }

    return _executar(buscar)


# ==========================================================
# MOVIMENTAÇÕES
# ==========================================================

@app.route(
    '/financeiro/movimentacoes',
    methods=['GET']
)
def financeiro_movimentacoes():

    _, negado = _autorizado()

    if negado:
        return negado

    try:
        params = _periodo()

        id_barbearia, credenciais = (
            _contexto_financeiro()
        )

        movimentacoes, origem = (
            _movimentacoes_fonte(
                params,
                credenciais,
                id_barbearia
            )
        )

        con = conectar_banco()
        cursor = con.cursor()

        try:
            _sincronizar_snapshot(
                cursor,
                id_barbearia,
                movimentacoes,
                params.get(
                    'data_inicio'
                ),
                params.get(
                    'data_fim'
                ),
                origem
            )

            try:
                con.commit()
            except Exception:
                pass

        finally:
            cursor.close()
            con.close()

        return jsonify({
            'movimentacoes':
                movimentacoes,

            'total':
                len(movimentacoes),

            'origem_dados':
                origem
        }), 200

    except ArkheErro as erro:
        return _erro(
            erro.mensagem,
            erro.status
        )

    except Exception as erro:
        print(
            'ERRO MOVIMENTACOES:',
            repr(erro)
        )

        return _erro(
            'Erro interno ao buscar movimentações.',
            500
        )


# ==========================================================
# RESUMO
# ==========================================================

@app.route(
    '/financeiro/resumo',
    methods=['GET']
)
def financeiro_resumo():

    def buscar():
        params = _periodo()

        id_barbearia, credenciais = (
            _contexto_financeiro()
        )

        # O resumo é calculado sobre a mesma lista exibida no caixa. Assim
        # ele inclui as movimentações da Arkhé e os pagamentos presenciais.
        movimentacoes, origem = (
            _movimentacoes_fonte(
                params,
                credenciais,
                id_barbearia
            )
        )

        return {
            **_resumo_de_movimentacoes(
                movimentacoes
            ),
            'origem_dados':
                origem
        }

    return _executar(buscar)


# ==========================================================
# ANÁLISE GERAL DO ADMINISTRADOR
# ==========================================================

@app.route(
    '/financeiro/geral/resumo',
    methods=['GET']
)
def financeiro_geral_resumo():

    def buscar():
        _exigir_admin()

        params = _periodo()

        # O painel do ADM não pode depender de um cache ser preenchido quando
        # cada barbearia abre o próprio painel. Lê os lançamentos persistidos
        # no FINANCEIRO, que são criados no momento do pagamento.
        movimentacoes, origem, falhas_arkhe = _movimentacoes_gerais_adm(params)
        di = _parse_data_opt(params.get('data_inicio')) or (date.today() - timedelta(days=29))
        df = _parse_data_opt(params.get('data_fim')) or date.today()

        por_barbearia = {}

        for mov in movimentacoes:
            if not mov.get('id_barbearia'):
                continue

            grupo = por_barbearia.setdefault(
                mov['id_barbearia'],
                {
                    'id_barbearia': mov['id_barbearia'],
                    'nome': mov['barbearia_nome'] or f"Barbearia #{mov['id_barbearia']}",
                    'total_receitas': 0.0,
                    'total_despesas': 0.0
                }
            )

            if mov['tipo'] == 'entrada':
                grupo['total_receitas'] = round(
                    grupo['total_receitas'] + mov['valor'], 2
                )
            else:
                grupo['total_despesas'] = round(
                    grupo['total_despesas'] + mov['valor'], 2
                )

        lista = []

        for grupo in por_barbearia.values():
            grupo['saldo_periodo'] = round(
                grupo['total_receitas'] - grupo['total_despesas'], 2
            )
            lista.append(grupo)

        lista.sort(key=lambda grupo: grupo['nome'] or '')

        totais = _resumo_de_movimentacoes(movimentacoes)

        return {
            **totais,
            'por_barbearia': lista,
            'data_inicio': di.isoformat(),
            'data_fim': df.isoformat(),
            'origem_dados': origem,
            'falhas_arkhe': falhas_arkhe
        }

    return _executar(buscar)


@app.route(
    '/financeiro/geral/movimentacoes',
    methods=['GET']
)
def financeiro_geral_movimentacoes():

    def buscar():
        _exigir_admin()

        params = _periodo()

        movimentacoes, origem, falhas_arkhe = _movimentacoes_gerais_adm(params)

        return {
            'movimentacoes': movimentacoes,
            'total': len(movimentacoes),
            'origem_dados': origem,
            'falhas_arkhe': falhas_arkhe
        }

    return _executar(buscar)


# ==========================================================
# GRÁFICO GERAL
# ==========================================================

@app.route(
    '/financeiro/geral/grafico',
    methods=['GET']
)
def financeiro_geral_grafico():

    _, negado = _autorizado()

    if negado:
        return negado

    try:
        import pygal  # noqa: F401
    except ImportError:
        return _erro(
            'Gráfico indisponível: '
            'instale com pip install pygal.',
            503
        )

    try:
        _exigir_admin()

        tipo = (
                request.args.get('tipo')
                or 'todos'
        ).strip().lower()

        if tipo not in (
                'todos',
                'ganhos',
                'custos'
        ):
            raise ArkheErro(
                'tipo deve ser todos, '
                'ganhos ou custos.',
                400
            )

        params = _periodo()

        movimentacoes, _, _ = _movimentacoes_gerais_adm(params)
        di = _parse_data_opt(params.get('data_inicio')) or (date.today() - timedelta(days=29))
        df = _parse_data_opt(params.get('data_fim')) or date.today()

        return _resposta_grafico_linha(
            di,
            df,
            movimentacoes,
            tipo,
            (
                'geral — '
                f'{di.strftime("%d/%m/%Y")} '
                'a '
                f'{df.strftime("%d/%m/%Y")}'
            )
        )

    except ArkheErro as erro:
        return _erro(
            erro.mensagem,
            erro.status
        )

    except Exception as erro:
        print(
            'ERRO GRAFICO GERAL:',
            repr(erro)
        )

        return _erro(
            'Erro interno ao gerar o gráfico.',
            500
        )


# ==========================================================
# GRÁFICO DA BARBEARIA
# ==========================================================

@app.route(
    '/financeiro/grafico',
    methods=['GET']
)
def financeiro_grafico():

    _, negado = _autorizado()

    if negado:
        return negado

    try:
        import pygal  # noqa: F401
    except ImportError:
        return _erro(
            'Gráfico indisponível: '
            'instale com pip install pygal.',
            503
        )

    try:
        tipo = (
                request.args.get('tipo')
                or 'todos'
        ).strip().lower()

        if tipo not in (
                'todos',
                'ganhos',
                'custos'
        ):
            raise ArkheErro(
                'tipo deve ser todos, '
                'ganhos ou custos.',
                400
            )

        hoje = date.today()

        def ler_data(
                campo,
                padrao
        ):
            valor = request.args.get(
                campo
            )

            if not valor:
                return padrao

            if not REGEX_DATA.match(
                    valor
            ):
                raise ArkheErro(
                    f'{campo} deve estar no '
                    'formato AAAA-MM-DD.',
                    400
                )

            try:
                ano, mes, dia = map(
                    int,
                    valor.split('-')
                )

                return date(
                    ano,
                    mes,
                    dia
                )

            except ValueError:
                raise ArkheErro(
                    f'{campo} contém '
                    'uma data inválida.',
                    400
                )

        data_fim = ler_data(
            'data_fim',
            hoje
        )

        data_inicio = ler_data(
            'data_inicio',
            data_fim
            - timedelta(days=29)
        )

        if data_inicio > data_fim:
            raise ArkheErro(
                'data_inicio não pode ser '
                'depois de data_fim.',
                400
            )

        if (
                data_fim
                - data_inicio
        ).days > 92:
            raise ArkheErro(
                'Período máximo de 92 dias.',
                400
            )

        params = {
            'data_inicio':
                data_inicio.isoformat(),

            'data_fim':
                data_fim.isoformat()
        }

        id_barbearia, credenciais = (
            _contexto_financeiro()
        )

        movimentacoes, origem = (
            _movimentacoes_fonte(
                params,
                credenciais,
                id_barbearia
            )
        )

        con = conectar_banco()
        cursor = con.cursor()

        try:
            _sincronizar_snapshot(
                cursor,
                id_barbearia,
                movimentacoes,
                params['data_inicio'],
                params['data_fim'],
                origem
            )

            try:
                con.commit()
            except Exception:
                pass

        finally:
            cursor.close()
            con.close()

        return _resposta_grafico_linha(
            data_inicio,
            data_fim,
            movimentacoes,
            tipo,
            (
                f'{data_inicio.strftime("%d/%m/%Y")} '
                'a '
                f'{data_fim.strftime("%d/%m/%Y")}'
            )
        )

    except ArkheErro as erro:
        return _erro(
            erro.mensagem,
            erro.status
        )

    except Exception as erro:
        print(
            'ERRO GRAFICO:',
            repr(erro)
        )

        return _erro(
            'Erro interno ao gerar o gráfico.',
            500
        )


# ==========================================================
# PIX - CRIAR
# ==========================================================

@app.route(
    '/financeiro/cobrancas/pix',
    methods=['POST']
)
def financeiro_criar_cobranca():

    def criar():
        dados = (
                request.get_json(
                    silent=True
                )
                or {}
        )

        try:
            valor = round(
                float(
                    str(
                        dados.get('valor')
                    ).replace(',', '.')
                ),
                2
            )

        except (
                TypeError,
                ValueError
        ):
            raise ArkheErro(
                'Informe um valor válido.',
                400
            )

        if (
                valor <= 0
                or valor > 1_000_000
        ):
            raise ArkheErro(
                'O valor deve ser maior que zero.',
                400
            )

        _, credenciais = (
            _contexto_financeiro()
        )

        return _chamar_arkhe(
            'POST',
            '/api/v1/cobrancas/pix',
            corpo={
                'valor': valor
            },
            credenciais=credenciais
        )

    return _executar(criar)


# ==========================================================
# PIX - CONSULTAR
# ==========================================================

@app.route(
    '/financeiro/cobrancas/pix/<string:id_cobranca>',
    methods=['GET']
)
def financeiro_consultar_cobranca(
        id_cobranca
):

    def consultar():
        _, credenciais = (
            _contexto_financeiro()
        )

        if (
                not credenciais
                or not credenciais[0]
                or not credenciais[1]
        ):
            raise ArkheErro(
                'Conta Arkhé não configurada '
                'para esta barbearia.',
                503
            )

        id_seguro = urllib.parse.quote(
            str(id_cobranca),
            safe=''
        )

        return _chamar_arkhe(
            'GET',
            (
                '/api/v1/cobrancas/pix/'
                f'{id_seguro}'
            ),
            credenciais=credenciais
        )

    return _executar(consultar)


# ==========================================================
# BOLETO - CRIAR
# ==========================================================

@app.route(
    '/financeiro/cobrancas/boleto',
    methods=['POST']
)
def financeiro_criar_boleto():

    def criar():
        dados = (
                request.get_json(
                    silent=True
                )
                or {}
        )

        try:
            valor = round(
                float(
                    str(
                        dados.get('valor')
                    ).replace(',', '.')
                ),
                2
            )

        except (
                TypeError,
                ValueError
        ):
            raise ArkheErro(
                'Informe um valor válido.',
                400
            )

        if (
                valor <= 0
                or valor > 1_000_000
        ):
            raise ArkheErro(
                'O valor deve ser maior que zero.',
                400
            )

        _, credenciais = (
            _contexto_financeiro()
        )

        return _chamar_arkhe(
            'POST',
            '/api/v1/cobrancas/boleto',
            corpo={
                'valor': valor
            },
            credenciais=credenciais
        )

    return _executar(criar)


# ==========================================================
# CARTÃO - CRIAR
# ==========================================================

@app.route(
    '/financeiro/cobrancas/cartao',
    methods=['POST']
)
def financeiro_criar_cartao():

    def criar():
        dados = (
                request.get_json(
                    silent=True
                )
                or {}
        )

        try:
            valor = round(
                float(
                    str(
                        dados.get('valor')
                    ).replace(',', '.')
                ),
                2
            )

        except (
                TypeError,
                ValueError
        ):
            raise ArkheErro(
                'Informe um valor válido.',
                400
            )

        if (
                valor <= 0
                or valor > 1_000_000
        ):
            raise ArkheErro(
                'O valor deve ser maior que zero.',
                400
            )

        _, credenciais = (
            _contexto_financeiro()
        )

        return _chamar_arkhe(
            'POST',
            '/api/v1/cobrancas/cartao',
            corpo={
                'valor': valor
            },
            credenciais=credenciais
        )

    return _executar(criar)


# ==========================================================
# PAGAMENTO NA HORA
# ==========================================================

@app.route(
    '/financeiro/cobrancas/na-hora',
    methods=['POST']
)
def financeiro_confirmar_na_hora():

    def confirmar():
        dados = (
                request.get_json(
                    silent=True
                )
                or {}
        )

        try:
            valor = round(
                float(
                    str(
                        dados.get('valor')
                    ).replace(',', '.')
                ),
                2
            )

        except (
                TypeError,
                ValueError
        ):
            raise ArkheErro(
                'Informe um valor válido.',
                400
            )

        if (
                valor <= 0
                or valor > 1_000_000
        ):
            raise ArkheErro(
                'O valor deve ser maior que zero.',
                400
            )

        return {
            'valor':
                valor,

            'status':
                'confirmado',

            'metodo':
                'na_hora'
        }

    return _executar(confirmar)


# ==========================================================
# BOLETO - CONSULTAR
# ==========================================================

@app.route(
    '/financeiro/cobrancas/boleto/<string:id_cobranca>',
    methods=['GET']
)
def financeiro_consultar_boleto(
        id_cobranca
):

    def consultar():
        _, credenciais = (
            _contexto_financeiro()
        )

        id_seguro = urllib.parse.quote(
            str(id_cobranca),
            safe=''
        )

        return _chamar_arkhe(
            'GET',
            (
                '/api/v1/cobrancas/boleto/'
                f'{id_seguro}'
            ),
            credenciais=credenciais
        )

    return _executar(consultar)


# ==========================================================
# CARTÃO - CONSULTAR
# ==========================================================

@app.route(
    '/financeiro/cobrancas/cartao/<string:id_cobranca>',
    methods=['GET']
)
def financeiro_consultar_cartao(
        id_cobranca
):

    def consultar():
        _, credenciais = (
            _contexto_financeiro()
        )

        id_seguro = urllib.parse.quote(
            str(id_cobranca),
            safe=''
        )

        return _chamar_arkhe(
            'GET',
            (
                '/api/v1/cobrancas/cartao/'
                f'{id_seguro}'
            ),
            credenciais=credenciais
        )

    return _executar(consultar)


# ==========================================================
# WEBHOOK ARKHÉ
# ==========================================================

@app.route(
    '/financeiro/webhook/arkhe',
    methods=['POST']
)
def financeiro_webhook_arkhe():
    try:
        dados = (
                request.get_json(
                    silent=True
                )
                or {}
        )

        print(
            'WEBHOOK ARKHÉ RECEBIDO:',
            dados
        )

        return jsonify({
            'mensagem': {
                'informacao':
                    'Webhook recebido.',
                'tipo':
                    'sucesso'
            }
        }), 200

    except Exception as erro:
        print(
            'ERRO WEBHOOK ARKHÉ:',
            repr(erro)
        )

        return jsonify({
            'mensagem': {
                'informacao':
                    'Erro ao processar webhook.',
                'tipo':
                    'erro'
            }
        }), 500


        return None, None

    print('ID DA BARBEARIA NÃO FOI INFORMADO')

    cid = (app.config.get('ARKHE_CLIENT_ID') or '').strip()
    segredo = (app.config.get('ARKHE_CLIENT_SECRET') or '').strip()

    return (
        (cid, segredo)
        if cid and segredo
        else (None, None)
    )
