"""Pagamentos vinculados aos agendamentos usando a API Arkhé.

Cada barbearia utiliza o seu próprio Client ID e Client Secret da Arkhé,
armazenados na tabela PERSONALIZACAO.

As credenciais nunca são enviadas para o frontend.
"""

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from flask import jsonify, request

from main import app, conectar_banco
from barbearia import obter_usuario_logado, pegar_id_barbearia_alvo
from visagismo import buscar_agendamento, pode_ver_agendamento


TIMEOUT_ARKHE = 20


# ============================================================
# RESPOSTAS
# ============================================================

def resposta_erro(texto, status=400):
    return jsonify({
        'mensagem': {
            'informacao': texto,
            'tipo': 'erro'
        }
    }), status


# ============================================================
# CREDENCIAIS ARKHÉ
# ============================================================

def _credenciais_da_barbearia(id_barbearia):
    """
    Busca Client ID e Client Secret da Arkhé da barbearia.

    PERSONALIZACAO.ID_USUARIO corresponde ao ID da barbearia.
    """

    if not id_barbearia:
        raise RuntimeError(
            'Não foi possível identificar a barbearia do agendamento.'
        )

    con = conectar_banco()
    cursor = con.cursor()

    try:
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

    finally:
        cursor.close()
        con.close()

    if not linha:
        raise RuntimeError(
            'A barbearia ainda não possui personalização cadastrada.'
        )

    client_id = str(linha[0] or '').strip()
    client_secret = str(linha[1] or '').strip()

    if not client_id or not client_secret:
        raise RuntimeError(
            'A barbearia não configurou a integração com a Arkhé. '
            'Cadastre o Client ID e o Client Secret.'
        )

    return client_id, client_secret


def _cabecalhos(id_barbearia):
    """
    Monta os headers utilizando as credenciais da barbearia
    responsável pelo agendamento.
    """

    client_id, client_secret = _credenciais_da_barbearia(
        id_barbearia
    )

    return {
        'X-Client-ID': client_id,
        'X-Client-Secret': client_secret,
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }


# ============================================================
# CLIENTE HTTP ARKHÉ
# ============================================================

def _chamar(
        metodo,
        caminho,
        corpo=None,
        id_barbearia=None
):
    base_url = (
            app.config.get('ARKHE_BASE_URL') or ''
    ).strip().rstrip('/')

    if not base_url:
        raise RuntimeError(
            'ARKHE_BASE_URL não está configurada no servidor.'
        )

    url = base_url + caminho

    dados = None

    if corpo is not None:
        dados = json.dumps(corpo).encode('utf-8')

    headers = _cabecalhos(id_barbearia)

    requisicao = Request(
        url,
        data=dados,
        method=metodo,
        headers=headers
    )

    try:
        with urlopen(
                requisicao,
                timeout=TIMEOUT_ARKHE
        ) as resposta:

            texto = resposta.read().decode('utf-8')

            if not texto:
                return {}

            try:
                return json.loads(texto)
            except ValueError:
                raise RuntimeError(
                    'A Arkhé retornou uma resposta inválida.'
                )

    except HTTPError as erro:

        try:
            texto = erro.read().decode(
                'utf-8',
                errors='replace'
            )
        except Exception:
            texto = ''

        try:
            detalhe = json.loads(texto) if texto else {}
        except ValueError:
            detalhe = {}

        print(
            'ERRO ARKHÉ:',
            erro.code,
            texto
        )

        mensagem_api = None

        if isinstance(detalhe, dict):
            mensagem_api = (
                    detalhe.get('mensagem')
                    or detalhe.get('message')
                    or detalhe.get('detail')
                    or detalhe.get('erro')
                    or detalhe.get('error')
            )

        mensagens = {
            400: 'A Arkhé recusou os dados enviados.',
            401: (
                'Client ID ou Client Secret da Arkhé '
                'estão incorretos.'
            ),
            403: (
                'A integração da Arkhé não possui permissão '
                'ou está desativada.'
            ),
            404: (
                'O recurso solicitado não foi encontrado '
                'na Arkhé.'
            ),
            500: 'A Arkhé apresentou um erro interno.'
        }

        raise RuntimeError(
            mensagem_api
            or mensagens.get(
                erro.code,
                f'Arkhé retornou HTTP {erro.code}.'
            )
        )

    except URLError as erro:
        print('ERRO DE CONEXÃO ARKHÉ:', erro)

        raise RuntimeError(
            f'Não foi possível conectar à Arkhé: '
            f'{getattr(erro, "reason", erro)}'
        )

    except RuntimeError:
        raise

    except Exception as erro:
        print('ERRO INESPERADO ARKHÉ:', erro)

        raise RuntimeError(
            f'Não foi possível falar com a Arkhé: {erro}'
        )


# ============================================================
# FINANCEIRO
# ============================================================

def _proximo_financeiro(cursor):
    cursor.execute(
        'SELECT NEXT VALUE FOR SEQ_FINANCEIRO '
        'FROM RDB$DATABASE'
    )

    return cursor.fetchone()[0]


# ============================================================
# VALOR DO AGENDAMENTO
# ============================================================

def _valor_do_agendamento(cursor, linha):

    ids = json.loads(
        str(linha[6])
    ) if linha[6] else []

    if not ids:
        return 0.0

    marcadores = ','.join(
        '?' for _ in ids
    )

    cursor.execute(
        f"""
        SELECT PRECO
        FROM SERVICO
        WHERE ID_SERVICO IN ({marcadores})
        """,
        list(ids)
    )

    total = sum(
        float(registro[0] or 0)
        for registro in cursor.fetchall()
    )

    return round(float(total), 2)


# ============================================================
# VALIDAÇÃO DO AGENDAMENTO
# ============================================================

def _agendamento_pagavel(
        cursor,
        usuario,
        id_agendamento
):

    try:
        id_agendamento = int(id_agendamento)

    except (TypeError, ValueError):
        return None, 'Agendamento inválido.'

    linha = buscar_agendamento(
        cursor,
        id_agendamento
    )

    if not linha:
        return None, 'Agendamento não encontrado.'

    if not pode_ver_agendamento(
            usuario,
            linha,
            pegar_id_barbearia_alvo()
    ):
        return None, (
            'Sem permissão para pagar este agendamento.'
        )

    if linha[9] == 'cancelado':
        return None, (
            'Agendamento cancelado não pode ser pago.'
        )

    if linha[9] == 'concluido':
        return None, (
            'Agendamento concluído não pode ser pago.'
        )

    valor = _valor_do_agendamento(
        cursor,
        linha
    )

    if valor <= 0:
        return None, (
            'Não foi possível calcular o valor '
            'deste agendamento.'
        )

    return (linha, valor), None


# ============================================================
# DESCOBRIR BARBEARIA DE UMA COBRANÇA
# ============================================================

def _barbearia_da_cobranca(cursor, id_cobranca):
    """
    Localiza a cobrança no FINANCEIRO, pega o agendamento
    relacionado e retorna a barbearia responsável.
    """

    cursor.execute(
        """
        SELECT DESCRICAO
        FROM FINANCEIRO
        WHERE DESCRICAO STARTING WITH ?
        """,
        (f'ARKHE:{id_cobranca} ',)
    )

    registro = cursor.fetchone()

    if not registro:
        raise RuntimeError(
            'Cobrança não encontrada no financeiro.'
        )

    descricao = str(registro[0] or '')

    marcador = 'ag#'

    if marcador not in descricao:
        raise RuntimeError(
            'Não foi possível identificar o agendamento '
            'desta cobrança.'
        )

    try:
        id_agendamento = int(
            descricao.split(marcador, 1)[1]
            .split()[0]
            .split('|')[0]
        )

    except (ValueError, IndexError):
        raise RuntimeError(
            'Identificador de agendamento inválido '
            'na cobrança.'
        )

    linha = buscar_agendamento(
        cursor,
        id_agendamento
    )

    if not linha:
        raise RuntimeError(
            'Agendamento da cobrança não encontrado.'
        )

    # buscar_agendamento:
    #
    # 0 = ID_AGENDAMENTO
    # 1 = ID_USUARIO
    # 2 = ID_BARBEARIA
    #
    return linha[2], linha


# ============================================================
# PIX - CRIAR
# ============================================================

@app.route('/pagamentos/pix', methods=['POST'])
def criar_cobranca_pix():

    usuario = obter_usuario_logado()

    if not usuario:
        return resposta_erro(
            'Faça login para pagar.',
            401
        )

    try:

        dados = request.get_json(
            silent=True
        ) or {}

        if not dados.get('id_agendamento'):
            return resposta_erro(
                'Informe o agendamento.'
            )

        con = conectar_banco()
        cursor = con.cursor()

        try:

            resultado, erro = _agendamento_pagavel(
                cursor,
                usuario,
                dados['id_agendamento']
            )

            if erro:
                return resposta_erro(
                    erro,
                    400
                )

            linha, valor_calculado = resultado

            # ------------------------------------------------
            # ID DA BARBEARIA
            # ------------------------------------------------

            id_barbearia = linha[2]

            if not id_barbearia:
                return resposta_erro(
                    'O agendamento não possui '
                    'uma barbearia vinculada.',
                    400
                )

            # ------------------------------------------------
            # VALOR
            # ------------------------------------------------

            # Preferimos sempre o valor calculado pelo servidor.
            # Isso impede o cliente de alterar o valor pelo frontend.
            valor = valor_calculado

            if valor <= 0:
                return resposta_erro(
                    'Não foi possível calcular '
                    'o valor do agendamento.'
                )

            print(
                'ARKHE PIX:',
                'agendamento=',
                linha[0],
                'barbearia=',
                id_barbearia,
                'valor=',
                valor
            )

            # ------------------------------------------------
            # CRIAR COBRANÇA NA CONTA DA BARBEARIA
            # ------------------------------------------------

            cobranca = _chamar(
                'POST',
                '/api/v1/cobrancas/pix',
                {
                    'valor': round(
                        valor,
                        2
                    )
                },
                id_barbearia=id_barbearia
            )

            if not isinstance(cobranca, dict):
                raise RuntimeError(
                    'Resposta inválida ao criar cobrança.'
                )

            id_cobranca = (
                    cobranca.get('id_cobranca')
                    or cobranca.get('id')
            )

            codigo_pagamento = (
                    cobranca.get('codigo_pagamento')
                    or cobranca.get('pix_copia_cola')
                    or cobranca.get('pix')
                    or cobranca.get('codigo_pix')
            )

            if not id_cobranca:
                raise RuntimeError(
                    'A Arkhé não retornou o ID '
                    'da cobrança.'
                )

            # ------------------------------------------------
            # SALVAR
            # ------------------------------------------------

            cursor.execute(
                """
                INSERT INTO FINANCEIRO
                (
                    ID_FINANCEIRO,
                    ID_USUARIO,
                    TIPO,
                    DESCRICAO,
                    VALOR,
                    DATA_TRANSACAO
                )
                VALUES
                    (
                        NEXT VALUE FOR SEQ_FINANCEIRO,
                             ?,
                             'pix_pendente',
                             ?,
                             ?,
                             CURRENT_TIMESTAMP
                    )
                """,
                (
                    linha[1],
                    (
                        f'ARKHE:{id_cobranca} '
                        f'ag#{linha[0]}'
                    ),
                    round(valor, 2)
                )
            )

            con.commit()

            return jsonify({
                'mensagem': {
                    'informacao':
                        'Cobrança Pix gerada com sucesso.',
                    'tipo': 'sucesso'
                },

                'id_cobranca': id_cobranca,

                'codigo_pagamento':
                    codigo_pagamento,

                'valor': cobranca.get(
                    'valor',
                    round(valor, 2)
                ),

                'status': cobranca.get(
                    'status',
                    0
                )

            }), 201

        finally:
            cursor.close()
            con.close()

    except RuntimeError as erro:
        print(
            'ERRO PAGAMENTO PIX:',
            erro
        )

        return resposta_erro(
            str(erro),
            502
        )

    except Exception as erro:
        print(
            'ERRO INTERNO PIX:',
            erro
        )

        return resposta_erro(
            f'Não foi possível gerar a cobrança: {erro}',
            500
        )


# ============================================================
# PIX - CONSULTAR
# ============================================================

@app.route(
    '/pagamentos/pix/<string:id_cobranca>',
    methods=['GET']
)
def consultar_cobranca_pix(id_cobranca):

    usuario = obter_usuario_logado()

    if not usuario:
        return resposta_erro(
            'Faça login para consultar.',
            401
        )

    try:

        con = conectar_banco()
        cursor = con.cursor()

        try:

            id_barbearia, linha = _barbearia_da_cobranca(
                cursor,
                id_cobranca
            )

            # Verifica se o usuário pode acessar
            # o agendamento relacionado.
            if not pode_ver_agendamento(
                    usuario,
                    linha,
                    pegar_id_barbearia_alvo()
            ):
                return resposta_erro(
                    'Sem permissão para consultar '
                    'esta cobrança.',
                    403
                )

            cobranca = _chamar(
                'GET',
                f'/api/v1/cobrancas/pix/{id_cobranca}',
                id_barbearia=id_barbearia
            )

            status_bruto = cobranca.get(
                'status',
                0
            )

            pago = (
                    status_bruto == 1
                    or str(status_bruto).lower()
                    in (
                        '1',
                        'pago',
                        'paid',
                        'aprovado',
                        'approved',
                        'confirmado',
                        'confirmed'
                    )
            )

            if pago:

                cursor.execute(
                    """
                    UPDATE FINANCEIRO
                    SET TIPO = 'pix_pago'
                    WHERE DESCRICAO STARTING WITH ?
                    """,
                    (
                        f'ARKHE:{id_cobranca} ',
                    )
                )

                con.commit()

                return jsonify({
                    'mensagem': {
                        'informacao':
                            'Pagamento confirmado!',
                        'tipo': 'sucesso'
                    },

                    'id_cobranca':
                        cobranca.get(
                            'id_cobranca',
                            id_cobranca
                        ),

                    'valor':
                        cobranca.get('valor'),

                    'status': status_bruto,

                    'pago': True
                })

            return jsonify({
                'mensagem': {
                    'informacao':
                        'Pagamento ainda pendente.',
                    'tipo': 'aviso'
                },

                'id_cobranca':
                    cobranca.get(
                        'id_cobranca',
                        id_cobranca
                    ),

                'valor':
                    cobranca.get('valor'),

                'status':
                    status_bruto,

                'pago': False
            })

        finally:
            cursor.close()
            con.close()

    except RuntimeError as erro:

        return resposta_erro(
            str(erro),
            502
        )

    except Exception as erro:

        print(
            'ERRO CONSULTAR PIX:',
            erro
        )

        return resposta_erro(
            f'Não foi possível consultar: {erro}',
            500
        )


# ============================================================
# BOLETO
# ============================================================

@app.route('/pagamentos/boleto', methods=['POST'])
def criar_cobranca_boleto():

    usuario = obter_usuario_logado()

    if not usuario:
        return resposta_erro(
            'Faça login para pagar.',
            401
        )

    try:

        dados = request.get_json(
            silent=True
        ) or {}

        if not dados.get('id_agendamento'):
            return resposta_erro(
                'Informe o agendamento.'
            )

        con = conectar_banco()
        cursor = con.cursor()

        try:

            resultado, erro = _agendamento_pagavel(
                cursor,
                usuario,
                dados['id_agendamento']
            )

            if erro:
                return resposta_erro(
                    erro,
                    400
                )

            linha, valor = resultado

            id_barbearia = linha[2]

            try:

                cobranca = _chamar(
                    'POST',
                    '/api/v1/cobrancas/boleto',
                    {
                        'valor': round(
                            valor,
                            2
                        )
                    },
                    id_barbearia=id_barbearia
                )

                boleto = {
                    'id_cobranca':
                        cobranca.get(
                            'id_cobranca'
                        ),

                    'codigo_pagamento':
                        cobranca.get(
                            'codigo_pagamento'
                        ),

                    'url_boleto':
                        cobranca.get(
                            'url_boleto'
                        ),

                    'valor':
                        cobranca.get(
                            'valor',
                            round(valor, 2)
                        ),

                    'status':
                        cobranca.get(
                            'status',
                            0
                        )
                }

            except RuntimeError as erro_arkhe:
                # Não mascara falhas reais da Arkhé com uma cobrança simulada.
                raise RuntimeError(f'Falha ao gerar boleto na Arkhé: {erro_arkhe}')

            cursor.execute(
                """
                INSERT INTO FINANCEIRO
                (
                    ID_FINANCEIRO,
                    ID_USUARIO,
                    TIPO,
                    DESCRICAO,
                    VALOR,
                    DATA_TRANSACAO
                )
                VALUES
                    (
                        NEXT VALUE FOR SEQ_FINANCEIRO,
                             ?,
                             'boleto_pendente',
                             ?,
                             ?,
                             CURRENT_TIMESTAMP
                    )
                """,
                (
                    linha[1],
                    (
                        f'ag#{linha[0]}|boleto|'
                        f'{boleto.get("codigo_pagamento")}'
                    ),
                    round(valor, 2)
                )
            )

            con.commit()

            return jsonify({
                'mensagem': {
                    'informacao':
                        'Boleto gerado.',
                    'tipo': 'sucesso'
                },

                'metodo': 'boleto',

                **boleto
            }), 201

        finally:
            cursor.close()
            con.close()

    except Exception as erro:

        print(
            'ERRO BOLETO:',
            erro
        )

        return resposta_erro(
            f'Não foi possível gerar o boleto: {erro}',
            500
        )


# ============================================================
# CARTÃO
# ============================================================

@app.route('/pagamentos/cartao', methods=['POST'])
def criar_cobranca_cartao():

    usuario = obter_usuario_logado()

    if not usuario:
        return resposta_erro(
            'Faça login para pagar.',
            401
        )

    try:

        dados = request.get_json(
            silent=True
        ) or {}

        if not dados.get('id_agendamento'):
            return resposta_erro(
                'Informe o agendamento.'
            )

        con = conectar_banco()
        cursor = con.cursor()

        try:

            resultado, erro = _agendamento_pagavel(
                cursor,
                usuario,
                dados['id_agendamento']
            )

            if erro:
                return resposta_erro(
                    erro,
                    400
                )

            linha, valor = resultado

            id_barbearia = linha[2]

            try:

                cobranca = _chamar(
                    'POST',
                    '/api/v1/cobrancas/cartao',
                    {
                        'valor': round(
                            valor,
                            2
                        )
                    },
                    id_barbearia=id_barbearia
                )

                cartao = {
                    'id_cobranca':
                        cobranca.get(
                            'id_cobranca'
                        ),

                    'url_checkout':
                        cobranca.get(
                            'url_checkout'
                        ),

                    'valor':
                        cobranca.get(
                            'valor',
                            round(valor, 2)
                        ),

                    'status':
                        cobranca.get(
                            'status',
                            0
                        )
                }

            except RuntimeError as erro_arkhe:
                # Não cria URL/checkout fictício quando a API falha.
                raise RuntimeError(f'Falha ao gerar checkout na Arkhé: {erro_arkhe}')

            cursor.execute(
                """
                INSERT INTO FINANCEIRO
                (
                    ID_FINANCEIRO,
                    ID_USUARIO,
                    TIPO,
                    DESCRICAO,
                    VALOR,
                    DATA_TRANSACAO
                )
                VALUES
                    (
                        NEXT VALUE FOR SEQ_FINANCEIRO,
                             ?,
                             'cartao_pendente',
                             ?,
                             ?,
                             CURRENT_TIMESTAMP
                    )
                """,
                (
                    linha[1],
                    f'ag#{linha[0]}|cartao',
                    round(valor, 2)
                )
            )

            con.commit()

            return jsonify({
                'mensagem': {
                    'informacao':
                        'Checkout gerado.',
                    'tipo': 'sucesso'
                },

                'metodo': 'cartao',

                **cartao
            }), 201

        finally:
            cursor.close()
            con.close()

    except Exception as erro:

        print(
            'ERRO CARTÃO:',
            erro
        )

        return resposta_erro(
            f'Não foi possível gerar o checkout: {erro}',
            500
        )


# ============================================================
# PAGAMENTO NA HORA
# ============================================================

@app.route('/pagamentos/na-hora', methods=['POST'])
def confirmar_pagamento_na_hora():

    usuario = obter_usuario_logado()

    if not usuario:
        return resposta_erro(
            'Faça login para confirmar.',
            401
        )

    try:

        dados = request.get_json(
            silent=True
        ) or {}

        if not dados.get('id_agendamento'):
            return resposta_erro(
                'Informe o agendamento.'
            )

        con = conectar_banco()
        cursor = con.cursor()

        try:

            resultado, erro = _agendamento_pagavel(
                cursor,
                usuario,
                dados['id_agendamento']
            )

            if erro:
                return resposta_erro(
                    erro,
                    400
                )

            linha, valor = resultado

            cursor.execute(
                """
                INSERT INTO FINANCEIRO
                (
                    ID_FINANCEIRO,
                    ID_USUARIO,
                    TIPO,
                    DESCRICAO,
                    VALOR,
                    DATA_TRANSACAO
                )
                VALUES
                    (
                        NEXT VALUE FOR SEQ_FINANCEIRO,
                             ?,
                             'na_hora',
                             ?,
                             ?,
                             CURRENT_TIMESTAMP
                    )
                """,
                (
                    linha[1],
                    f'ag#{linha[0]}|na_hora',
                    round(valor, 2)
                )
            )

            con.commit()

            return jsonify({
                'mensagem': {
                    'informacao':
                        'Pagamento na hora confirmado!',
                    'tipo': 'sucesso'
                },

                'metodo': 'na_hora',

                'valor':
                    round(valor, 2),

                'status': 1

            }), 201

        finally:
            cursor.close()
            con.close()

    except Exception as erro:

        return resposta_erro(
            f'Não foi possível confirmar: {erro}',
            500
        )


# ============================================================
# COBRANÇAS DO AGENDAMENTO
# ============================================================

@app.route(
    '/pagamentos/agendamento/<int:id_agendamento>',
    methods=['GET']
)
def cobrancas_do_agendamento(id_agendamento):

    usuario = obter_usuario_logado()

    if not usuario:
        return resposta_erro(
            'Faça login.',
            401
        )

    try:

        con = conectar_banco()
        cursor = con.cursor()

        try:

            linha = buscar_agendamento(
                cursor,
                id_agendamento
            )

            if not linha:
                return resposta_erro(
                    'Agendamento não encontrado.',
                    404
                )

            if not pode_ver_agendamento(
                    usuario,
                    linha,
                    pegar_id_barbearia_alvo()
            ):
                return resposta_erro(
                    'Sem permissão.',
                    403
                )

            cursor.execute(
                """
                SELECT
                    ID_FINANCEIRO,
                    TIPO,
                    DESCRICAO,
                    VALOR,
                    DATA_TRANSACAO
                FROM FINANCEIRO
                WHERE DESCRICAO CONTAINING ?
                ORDER BY DATA_TRANSACAO
                """,
                (
                    f'ag#{id_agendamento}',
                )
            )

            cobrancas = []

            for registro in cursor.fetchall():

                data = registro[4]

                cobrancas.append({
                    'id_financeiro':
                        registro[0],

                    'tipo':
                        registro[1],

                    'descricao':
                        registro[2],

                    'valor':
                        float(
                            registro[3] or 0
                        ),

                    'data':
                        data.isoformat()
                        if data
                        else None
                })

            return jsonify({
                'mensagem': {
                    'informacao':
                        'Cobranças listadas.',
                    'tipo': 'sucesso'
                },

                'cobrancas':
                    cobrancas
            })

        finally:
            cursor.close()
            con.close()

    except Exception as erro:

        return resposta_erro(
            f'Não foi possível listar cobranças: {erro}',
            500
        )