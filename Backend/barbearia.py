import os
import json
import re
import jwt

from flask import jsonify, request, send_from_directory

from main import app, conectar_banco


# ==========================================================
# CONFIGURAÇÕES
# ==========================================================

EXTENSOES_PERMITIDAS = {
    'jpg',
    'jpeg',
    'png',
    'webp'
}


# ==========================================================
# USUÁRIO LOGADO
# ==========================================================

def obter_usuario_logado():

    token = request.cookies.get('access_token')

    if not token:
        return None

    try:

        dados = jwt.decode(
            token,
            app.config['SECRET_KEY'],
            algorithms=['HS256']
        )

        return dados

    except jwt.ExpiredSignatureError:

        return None

    except jwt.InvalidTokenError:

        return None


# ==========================================================
# ID DO USUÁRIO
# ==========================================================

def pegar_id_usuario():

    usuario = obter_usuario_logado()

    if not usuario:
        return None

    return usuario.get('id_usuario')


def pegar_id_barbearia_alvo():
    """Retorna exclusivamente o ID de uma conta do tipo barbearia.

    Em alterações administrativas, o alvo é obrigatório. Nunca há fallback
    para o ID do ADM, portanto todas as gravações operacionais ficam ligadas
    somente à barbearia que está sendo administrada.
    """
    usuario = obter_usuario_logado()
    if not usuario:
        return None

    id_logado = usuario.get('id_usuario')
    id_solicitado = (
        request.args.get('id_usuario') or request.args.get('usuario')
        or request.form.get('id_usuario') or request.form.get('usuario')
    )
    dados_json = request.get_json(silent=True) or {}
    id_solicitado = id_solicitado or dados_json.get('id_usuario') or dados_json.get('usuario')

    if not id_solicitado:
        # ADM não pode gravar dados operacionais em sua própria conta.
        if int(usuario.get('tipo', -1)) == 0:
            return None
        id_solicitado = id_logado

    try:
        id_solicitado = int(id_solicitado)
    except (ValueError, TypeError):
        return None

    # ADM pode editar qualquer barbearia
    if int(usuario.get('tipo', -1)) == 0:
        return id_solicitado

    if (
        id_solicitado != id_logado
        and request.method != 'GET'
    ):
        return None

    # Impede que um ID de cliente ou de ADM seja usado como uma barbearia.
    con = None
    cursor = None
    try:
        con = conectar_banco()
        cursor = con.cursor()
        cursor.execute(
            'SELECT ID_USUARIO FROM USUARIO WHERE ID_USUARIO = ? AND TIPO = 2',
            (id_solicitado,)
        )
        return id_solicitado if cursor.fetchone() else None
    except Exception:
        return None
    finally:
        if cursor:
            cursor.close()
        if con:
            con.close()


# ==========================================================
# OBTER SERVIÇOS DO FUNCIONÁRIO
# ==========================================================
#
# IMPORTANTE:
#
# Os serviços DEVEM estar previamente cadastrados
# na tabela SERVICO.
#
# Esta função NÃO cadastra serviços.
#
# Ela somente recebe os IDs dos serviços enviados
# pelo frontend/Postman.
#
# Aceita:
#
# funcionarios[0][servicos] = 1,2,3
#
# funcionarios[0][servicos][] = 1
# funcionarios[0][servicos][] = 2
#
# funcionarios[0][servicos][0] = 1
# funcionarios[0][servicos][1] = 2
#
# funcionarios[0][servicos] = [1,2,3]
#
# ==========================================================

def obter_servicos_funcionario(indice):

    prefixo = (
        f'funcionarios[{indice}][servicos]'
    )

    valores = []


    # ======================================================
    # FORMATO:
    #
    # funcionarios[0][servicos] = 1,2,3
    # ======================================================

    valores_diretos = request.form.getlist(
        prefixo
    )

    for valor in valores_diretos:

        if valor is not None and str(valor).strip():

            valores.append(valor)


    # ======================================================
    # FORMATO:
    #
    # funcionarios[0][servicos][] = 1
    # funcionarios[0][servicos][] = 2
    #
    # OU:
    #
    # funcionarios[0][servicos][0] = 1
    # funcionarios[0][servicos][1] = 2
    # ======================================================

    for chave in request.form.keys():

        if chave.startswith(prefixo + '['):

            valores_chave = request.form.getlist(
                chave
            )

            for valor in valores_chave:

                if (
                    valor is not None
                    and str(valor).strip()
                ):

                    valores.append(valor)


    ids_servicos = []


    # ======================================================
    # PROCESSAR VALORES
    # ======================================================

    for valor in valores:

        if valor is None:
            continue


        valor = str(valor).strip()


        if not valor:
            continue


        # ==================================================
        # JSON
        #
        # Exemplo:
        #
        # [1,2,3]
        # ==================================================

        if (
            valor.startswith('[')
            and valor.endswith(']')
        ):

            try:

                lista_json = json.loads(
                    valor
                )


                if isinstance(
                    lista_json,
                    list
                ):

                    for item in lista_json:

                        try:

                            id_servico = int(
                                item
                            )

                        except (
                            ValueError,
                            TypeError
                        ):

                            continue


                        if (
                            id_servico
                            not in ids_servicos
                        ):

                            ids_servicos.append(
                                id_servico
                            )


                    continue


            except (
                json.JSONDecodeError,
                TypeError
            ):

                pass


        # ==================================================
        # VÍRGULA OU PONTO E VÍRGULA
        # ==================================================

        partes = re.split(
            r'[,;]',
            valor
        )


        for parte in partes:

            parte = parte.strip()


            if not parte:
                continue


            try:

                id_servico = int(
                    parte
                )

            except (
                ValueError,
                TypeError
            ):

                continue


            if (
                id_servico
                not in ids_servicos
            ):

                ids_servicos.append(
                    id_servico
                )


    return ids_servicos


# ==========================================================
# VINCULAR SERVIÇOS AO FUNCIONÁRIO
# ==========================================================
#
# IMPORTANTE:
#
# Esta função NÃO cria serviços.
#
# Ela verifica se cada ID_SERVICO:
#
# 1. Existe na tabela SERVICO
# 2. Pertence ao usuário logado
#
# Depois cria a relação:
#
# SERVICO_POR_FUNCIONARIO
#
# ==========================================================

def vincular_servicos_funcionario(
    cursor,
    id_funcionario,
    id_usuario,
    indice
):

    ids_servicos = obter_servicos_funcionario(
        indice
    )


    print(
        '========================================='
    )

    print(
        f'FUNCIONÁRIO ID: {id_funcionario}'
    )

    print(
        'SERVIÇOS RECEBIDOS:',
        ids_servicos
    )


    for id_servico in ids_servicos:

        # ==================================================
        # VERIFICAR SE O SERVIÇO EXISTE
        # E PERTENCE AO USUÁRIO
        # ==================================================

        cursor.execute("""
            SELECT
                ID_SERVICO
            FROM SERVICO
            WHERE
                ID_SERVICO = ?
                AND ID_USUARIO = ?
        """, (
            id_servico,
            id_usuario
        ))


        servico = cursor.fetchone()


        if not servico:

            print(
                f'SERVIÇO {id_servico} '
                f'NÃO EXISTE OU NÃO PERTENCE '
                f'AO USUÁRIO {id_usuario}'
            )

            continue


        # ==================================================
        # EVITAR DUPLICIDADE
        # ==================================================

        cursor.execute("""
            SELECT
                ID_SERVI_FUNCI
            FROM SERVICO_POR_FUNCIONARIO
            WHERE
                ID_FUNCIONARIO = ?
                AND ID_SERVICO = ?
        """, (
            id_funcionario,
            id_servico
        ))


        vinculo_existente = (
            cursor.fetchone()
        )


        if vinculo_existente:

            print(
                f'SERVIÇO {id_servico} '
                f'JÁ ESTÁ VINCULADO '
                f'AO FUNCIONÁRIO {id_funcionario}'
            )

            continue


        # ==================================================
        # CRIAR VÍNCULO
        # ==================================================

        cursor.execute("""
            INSERT INTO SERVICO_POR_FUNCIONARIO (
                ID_SERVI_FUNCI,
                ID_FUNCIONARIO,
                ID_SERVICO
            )
            VALUES (NEXT VALUE FOR SEQ_SERVICO_POR_FUNCIONARIO, ?, ?)
        """, (
            id_funcionario,
            id_servico
        ))


        print(
            f'SERVIÇO {id_servico} '
            f'VINCULADO AO FUNCIONÁRIO '
            f'{id_funcionario}'
        )


    print(
        '========================================='
    )


    return ids_servicos


def vincular_dias_funcionario(cursor, id_funcionario, ids_dias):
    """Salva a relação N:N entre o funcionário e todos os dias selecionados."""
    for id_dia in set(ids_dias):
        cursor.execute("""
            INSERT INTO FUNCIONARIO_DIA (ID_FUNCIONARIO_DIA, ID_FUNCIONARIO, ID_DIA)
            VALUES (NEXT VALUE FOR SEQ_FUNCIONARIO_DIA, ?, ?)
        """, (id_funcionario, id_dia))


# ==========================================================
# PASTA DA BARBEARIA
# ==========================================================

def criar_pasta_barbearia():

    pasta = os.path.join(
        app.config['UPLOAD_FOLDER'],
        'barbearia'
    )

    os.makedirs(
        pasta,
        exist_ok=True
    )

    return pasta


# ==========================================================
# EXTENSÃO DA IMAGEM
# ==========================================================

def extensao_permitida(nome):

    if not nome:
        return False

    if '.' not in nome:
        return False

    extensao = nome.rsplit(
        '.',
        1
    )[-1].lower()

    return (
        extensao
        in EXTENSOES_PERMITIDAS
    )


# ==========================================================
# SERVIÇOS DA BARBEARIA
# ==========================================================

@app.route('/barbearia/servicos', methods=['GET'])
def listar_servicos_barbearia():
    """Lista somente os serviços pertencentes à barbearia autenticada."""
    con = None
    cursor = None

    try:
        id_usuario = pegar_id_barbearia_alvo()
        if not id_usuario:
            return jsonify({'mensagem': {'informacao': 'Usuário não autenticado.', 'tipo': 'erro'}}), 401

        con = conectar_banco()
        cursor = con.cursor()
        cursor.execute("""
            SELECT ID_SERVICO, NOME_SERVICO, PRECO, DURACAO, DESCRICAO_BREVE, GENERO
            FROM SERVICO
            WHERE ID_USUARIO = ?
            ORDER BY NOME_SERVICO
        """, (id_usuario,))

        return jsonify({'mensagem': {'informacao': 'Serviços listados.', 'tipo': 'sucesso'}, 'servicos': [
            {
                'id_servico': servico[0],
                'nome': servico[1],
                'preco': float(servico[2]) if servico[2] is not None else 0,
                'duracao': servico[3],
                'descricao': servico[4],
                'genero': servico[5] or 'unissex'
            }
            for servico in cursor.fetchall()
        ]}), 200
    except Exception as erro:
        return jsonify({'mensagem': {'informacao': 'Erro ao listar serviços.', 'tipo': 'erro'}, 'detalhes': str(erro)}), 500
    finally:
        if cursor:
            cursor.close()
        if con:
            con.close()


# ==========================================================
# CATÁLOGO DE BARBEARIAS DISPONÍVEIS
# ==========================================================
# Esta rota alimenta a tela BarbeariasDisponiveis no frontend. Ela retorna
# todas as contas do tipo 2. As que ainda não finalizaram a personalização
# recebem o status "Em configuração" para que o ADM consiga encontrá-las.

@app.route('/barbearias-disponiveis', methods=['GET'])
def listar_barbearias_disponiveis():
    con = None
    cursor = None

    try:
        con = conectar_banco()
        cursor = con.cursor()
        cursor.execute("""
            SELECT U.ID_USUARIO, U.NOME, P.LOCALIZACAO, P.ID_PERSONALIZACAO
            FROM USUARIO U
            LEFT JOIN PERSONALIZACAO P ON P.ID_USUARIO = U.ID_USUARIO
            WHERE U.TIPO = 2 AND U.ATIVO = 1
            ORDER BY U.NOME
        """)

        resultado = []
        pasta = criar_pasta_barbearia()
        for id_usuario, nome, localizacao, id_personalizacao in cursor.fetchall():
            # A logo cadastrada é usada como imagem do card.
            imagem = None
            for extensao in EXTENSOES_PERMITIDAS:
                caminho = os.path.join(pasta, f'{id_usuario}.{extensao}')
                if os.path.exists(caminho):
                    imagem = f'/uploads/barbearia/{id_usuario}.{extensao}'
                    break

            # Os horários são salvos por dia; o card exibe um resumo curto.
            cursor.execute("""
                SELECT DIAS, ENTRADA_MANHA, SAIDA_TARDE
                FROM DIAS_DE_SERVICO
                WHERE ID_USUARIO = ?
                ORDER BY ID_DIA
            """, (id_usuario,))
            dias = cursor.fetchall()
            nomes_dias = [str(dia[0]).capitalize() for dia in dias if dia[0]]
            primeiro_horario = dias[0] if dias else None
            horario = (
                f'{str(primeiro_horario[1])[:5]} - {str(primeiro_horario[2])[:5]}'
                if primeiro_horario and primeiro_horario[1] and primeiro_horario[2]
                else 'Horário a consultar'
            )

            resultado.append({
                'id': id_usuario,
                'nome': nome,
                'endereco': localizacao,
                'imagem': imagem,
                'dias': ', '.join(nomes_dias) or 'Em configuração',
                'horario': horario,
                # O frontend usa este campo para não oferecer agendamento
                # antes de a barbearia informar serviços e horários.
                'personalizada': bool(id_personalizacao)
            })

        return jsonify({'mensagem': {'informacao': 'Barbearias listadas.', 'tipo': 'sucesso'}, 'barbearias': resultado}), 200
    except Exception as erro:
        return jsonify({
            'mensagem': {'informacao': 'Erro ao listar barbearias.', 'tipo': 'erro'},
            'detalhes': str(erro)
        }), 500
    finally:
        if cursor:
            cursor.close()
        if con:
            con.close()


@app.route('/barbearias/<int:id_barbearia>/funcionarios', methods=['GET'])
def listar_funcionarios_barbearia(id_barbearia):
    """Lista os profissionais de uma barbearia para o cliente escolher o barbeiro.

    Query opcional `servicos=1,2` filtra só quem atende TODOS os serviços.
    """
    con = None
    cursor = None
    try:
        filtro = set()
        for parte in str(request.args.get('servicos', '')).split(','):
            parte = parte.strip()
            if parte:
                try:
                    filtro.add(int(parte))
                except (TypeError, ValueError):
                    pass
        con = conectar_banco()
        cursor = con.cursor()
        cursor.execute('SELECT ID_USUARIO FROM USUARIO WHERE ID_USUARIO = ? AND TIPO = 2',
                       (id_barbearia,))
        if not cursor.fetchone():
            return jsonify({'mensagem': {'informacao': 'Barbearia não encontrada.', 'tipo': 'erro'}}), 404
        # Dias em que a barbearia realmente funciona.
        cursor.execute("""
            SELECT DISTINCT DIAS
            FROM DIAS_DE_SERVICO
            WHERE ID_USUARIO = ?
            ORDER BY ID_DIA
        """, (id_barbearia,))
        dias_abertos = [str(linha[0]).strip().lower() for linha in cursor.fetchall() if linha[0]]

        cursor.execute("""
            SELECT DISTINCT F.ID_FUNCIONARIO, F.NOME, F.DESCRICAO
            FROM FUNCIONARIO F
            INNER JOIN FUNCIONARIO_DIA FD ON FD.ID_FUNCIONARIO = F.ID_FUNCIONARIO
            INNER JOIN DIAS_DE_SERVICO D ON D.ID_DIA = FD.ID_DIA
            WHERE D.ID_USUARIO = ?
            ORDER BY F.NOME
        """, (id_barbearia,))
        resultado = []
        for id_func, nome, descricao in cursor.fetchall():
            cursor.execute("""
                SELECT SPF.ID_SERVICO
                FROM SERVICO_POR_FUNCIONARIO SPF
                INNER JOIN SERVICO S ON S.ID_SERVICO = SPF.ID_SERVICO
                WHERE SPF.ID_FUNCIONARIO = ? AND S.ID_USUARIO = ?
            """, (id_func, id_barbearia))
            servicos = [linha[0] for linha in cursor.fetchall()]
            if filtro and not filtro <= set(servicos):
                continue
            cursor.execute("""
                SELECT DISTINCT D.DIAS
                FROM FUNCIONARIO_DIA FD
                INNER JOIN DIAS_DE_SERVICO D ON D.ID_DIA = FD.ID_DIA
                WHERE FD.ID_FUNCIONARIO = ?
            """, (id_func,))
            dias = [str(linha[0]) for linha in cursor.fetchall() if linha[0]]
            resultado.append({
                'id_funcionario': id_func,
                'nome': nome,
                'descricao': descricao,
                'servicos': servicos,
                'dias': dias,
            })
        return jsonify({
            'mensagem': {'informacao': 'Profissionais listados.', 'tipo': 'sucesso'},
            'funcionarios': resultado,
            'dias_abertos': dias_abertos
        }), 200
    except Exception as erro:
        return jsonify({'mensagem': {'informacao': 'Erro ao listar profissionais.', 'tipo': 'erro'}, 'detalhes': str(erro)}), 500
    finally:
        if cursor:
            cursor.close()
        if con:
            con.close()


@app.route('/barbearia/servicos', methods=['POST'])
def criar_servico_barbearia():
    """Cria um serviço que poderá ser associado a um ou mais funcionários."""
    con = None
    cursor = None

    try:
        id_usuario = pegar_id_barbearia_alvo()
        if not id_usuario:
            return jsonify({'mensagem': {'informacao': 'Usuário não autenticado.', 'tipo': 'erro'}}), 401

        dados = request.get_json(silent=True) or request.form
        nome = str(dados.get('nome', '')).strip()
        descricao = str(dados.get('descricao', '')).strip() or None
        genero = str(dados.get('genero', '')).strip().lower()
        preco = dados.get('preco')
        duracao = dados.get('duracao')

        if not nome:
            return jsonify({'mensagem': {'informacao': 'Nome do serviço é obrigatório.', 'tipo': 'erro'}}), 400
        if genero not in ('masculino', 'feminino', 'unissex'):
            return jsonify({'mensagem': {'informacao': 'Selecione Masculino, Feminino ou Unissex para o serviço.', 'tipo': 'erro'}}), 400

        try:
            preco_texto = str(preco).strip()
            preco = float(
                preco_texto.replace('.', '').replace(',', '.')
                if ',' in preco_texto else preco_texto
            )
            duracao = int(duracao)
        except (TypeError, ValueError):
            return jsonify({'mensagem': {'informacao': 'Preço e duração válidos são obrigatórios.', 'tipo': 'erro'}}), 400

        if preco < 0 or duracao <= 0:
            return jsonify({'mensagem': {'informacao': 'Preço e duração devem ser positivos.', 'tipo': 'erro'}}), 400

        con = conectar_banco()
        cursor = con.cursor()

        cursor.execute(
            '''
            SELECT NOME_SERVICO
            FROM SERVICO
            WHERE LOWER(TRIM(NOME_SERVICO)) = ?
            ''',
            (nome.lower(),)
        )

        existe = cursor.fetchone()

        if existe:
            return jsonify({
                "mensagem": {
                    "informacao": "Esse serviço já existe e não pode ser cadastrado novamente.",
                    "tipo": "erro"
                }
            }), 400

        cursor.execute("""
            INSERT INTO SERVICO (ID_SERVICO, ID_USUARIO, NOME_SERVICO, PRECO, DURACAO, DESCRICAO_BREVE, GENERO)
            VALUES (NEXT VALUE FOR SEQ_SERVICO, ?, ?, ?, ?, ?, ?)
            RETURNING ID_SERVICO
        """, (id_usuario, nome, preco, duracao, descricao, genero))
        id_servico = cursor.fetchone()[0]
        con.commit()

        return jsonify({
            'mensagem': {'informacao': 'Serviço adicionado com sucesso.', 'tipo': 'sucesso'},
            'servico': {'id_servico': id_servico, 'nome': nome, 'preco': preco, 'duracao': duracao, 'descricao': descricao, 'genero': genero}
        }), 201
    except Exception as erro:
        if con:
            con.rollback()
        return jsonify({'mensagem': {'informacao': 'Erro ao adicionar serviço.', 'tipo': 'erro'}, 'detalhes': str(erro)}), 500
    finally:
        if cursor:
            cursor.close()
        if con:
            con.close()


@app.route('/barbearia/servicos/<int:id_servico>', methods=['PUT'])
def editar_servico_barbearia(id_servico):
    con = None
    cursor = None
    try:
        id_usuario = pegar_id_barbearia_alvo()
        if not id_usuario:
            return jsonify({'mensagem': {'informacao': 'Usuário não autenticado.', 'tipo': 'erro'}}), 401
        dados = request.get_json(silent=True) or request.form
        nome = str(dados.get('nome', '')).strip()
        descricao = str(dados.get('descricao', '')).strip() or None
        genero = str(dados.get('genero', '')).strip().lower()
        preco = dados.get('preco')
        duracao = dados.get('duracao')
        if not nome:
            return jsonify({'mensagem': {'informacao': 'Nome do serviço é obrigatório.', 'tipo': 'erro'}}), 400
        if genero not in ('masculino', 'feminino', 'unissex'):
            return jsonify({'mensagem': {'informacao': 'Selecione Masculino, Feminino ou Unissex para o serviço.', 'tipo': 'erro'}}), 400
        try:
            preco_texto = str(preco).strip()
            preco = float(preco_texto.replace('.', '').replace(',', '.') if ',' in preco_texto else preco_texto)
            duracao = int(duracao)
        except (TypeError, ValueError):
            return jsonify({'mensagem': {'informacao': 'Preço e duração válidos são obrigatórios.', 'tipo': 'erro'}}), 400
        if preco < 0 or duracao <= 0:
            return jsonify({'mensagem': {'informacao': 'Preço e duração devem ser positivos.', 'tipo': 'erro'}}), 400
        con = conectar_banco()
        cursor = con.cursor()
        cursor.execute('SELECT ID_SERVICO FROM SERVICO WHERE ID_SERVICO = ? AND ID_USUARIO = ?', (id_servico, id_usuario))
        if not cursor.fetchone():
            return jsonify({'mensagem': {'informacao': 'Serviço não encontrado.', 'tipo': 'erro'}}), 404
        cursor.execute('SELECT ID_SERVICO FROM SERVICO WHERE LOWER(TRIM(NOME_SERVICO)) = ? AND ID_SERVICO <> ? AND ID_USUARIO = ?', (nome.lower(), id_servico, id_usuario))
        if cursor.fetchone():
            return jsonify({'mensagem': {'informacao': 'Já existe outro serviço com esse nome.', 'tipo': 'erro'}}), 400
        cursor.execute('UPDATE SERVICO SET NOME_SERVICO = ?, PRECO = ?, DURACAO = ?, DESCRICAO_BREVE = ?, GENERO = ? WHERE ID_SERVICO = ? AND ID_USUARIO = ?', (nome, preco, duracao, descricao, genero, id_servico, id_usuario))
        con.commit()
        return jsonify({'mensagem': {'informacao': 'Serviço atualizado com sucesso.', 'tipo': 'sucesso'}, 'servico': {'id_servico': id_servico, 'nome': nome, 'preco': preco, 'duracao': duracao, 'descricao': descricao, 'genero': genero}}), 200
    except Exception as erro:
        if con:
            con.rollback()
        return jsonify({'mensagem': {'informacao': 'Erro ao editar serviço.', 'tipo': 'erro'}, 'detalhes': str(erro)}), 500
    finally:
        if cursor:
            cursor.close()
        if con:
            con.close()


@app.route('/barbearia/servicos/<int:id_servico>', methods=['DELETE'])
def remover_servico_barbearia(id_servico):
    con = None
    cursor = None

    try:
        id_usuario = pegar_id_barbearia_alvo()
        if not id_usuario:
            return jsonify({'mensagem': {'informacao': 'Usuário não autenticado.', 'tipo': 'erro'}}), 401

        con = conectar_banco()
        cursor = con.cursor()
        cursor.execute('SELECT ID_SERVICO FROM SERVICO WHERE ID_SERVICO = ? AND ID_USUARIO = ?', (id_servico, id_usuario))
        if not cursor.fetchone():
            return jsonify({'mensagem': {'informacao': 'Serviço não encontrado.', 'tipo': 'erro'}}), 404

        cursor.execute('DELETE FROM SERVICO_POR_FUNCIONARIO WHERE ID_SERVICO = ?', (id_servico,))
        cursor.execute('DELETE FROM SERVICO WHERE ID_SERVICO = ? AND ID_USUARIO = ?', (id_servico, id_usuario))
        con.commit()
        return jsonify({'mensagem': {'informacao': 'Serviço removido.', 'tipo': 'sucesso'}}), 200
    except Exception as erro:
        if con:
            con.rollback()
        return jsonify({'mensagem': {'informacao': 'Erro ao remover serviço.', 'tipo': 'erro'}, 'detalhes': str(erro)}), 500
    finally:
        if cursor:
            cursor.close()
        if con:
            con.close()


# ==========================================================
# EXCLUIR ARQUIVO
# ==========================================================

def excluir_arquivo(caminho):

    if os.path.exists(caminho):

        try:

            os.remove(caminho)

        except Exception as erro:

            print(
                'ERRO AO EXCLUIR ARQUIVO:',
                erro
            )


# ==========================================================
# SALVAR IMAGEM
# ==========================================================

def salvar_imagem(
    arquivo,
    nome_base
):

    if not arquivo:
        return None

    if not arquivo.filename:
        return None

    if not extensao_permitida(
        arquivo.filename
    ):

        raise ValueError(
            'Formato de imagem não permitido. '
            'Use JPG, JPEG, PNG ou WEBP.'
        )


    pasta = criar_pasta_barbearia()


    extensao = (
        arquivo.filename
        .rsplit('.', 1)[-1]
        .lower()
    )


    # ------------------------------------------------------
    # EXCLUIR VERSÕES ANTIGAS
    # ------------------------------------------------------

    for ext in EXTENSOES_PERMITIDAS:

        antigo = os.path.join(
            pasta,
            f'{nome_base}.{ext}'
        )

        excluir_arquivo(
            antigo
        )


    # ------------------------------------------------------
    # SALVAR
    # ------------------------------------------------------

    nome_arquivo = (
        f'{nome_base}.{extensao}'
    )


    caminho = os.path.join(
        pasta,
        nome_arquivo
    )


    arquivo.save(
        caminho
    )


    return (
        f'/uploads/barbearia/'
        f'{nome_arquivo}'
    )


# ==========================================================
# ==========================================================
# CRIAR PERSONALIZAÇÃO
# ==========================================================
# ==========================================================

@app.route(
    '/barbearia/personalizacao',
    methods=['POST']
)
def personalizacao_barbearia():

    con = None
    cursor = None

    try:

        # ==================================================
        # AUTENTICAÇÃO
        # ==================================================

        id_usuario = pegar_id_barbearia_alvo()

        if not id_usuario:

            return jsonify({

                'mensagem': {

                    'informacao':
                        'Usuário não autenticado.',

                    'tipo':
                        'erro'

                }

            }), 401


        # ==================================================
        # CONEXÃO
        # ==================================================

        con = conectar_banco()

        cursor = con.cursor()


        # ==================================================
        # VERIFICAR PERSONALIZAÇÃO EXISTENTE
        # ==================================================

        cursor.execute("""
            SELECT ID_PERSONALIZACAO
            FROM PERSONALIZACAO
            WHERE ID_USUARIO = ?
        """, (
            id_usuario,
        ))


        existente = (
            cursor.fetchone()
        )


        if existente:

            return jsonify({

                'mensagem': {

                    'informacao':
                        'A barbearia já possui uma personalização.',

                    'tipo':
                        'aviso'

                },

                'id_personalizacao':
                    existente[0]

            }), 409


        # ==================================================
        # DADOS
        # ==================================================

        cor_primaria = request.form.get(
            'cor_primaria'
        )

        cor_secundaria = request.form.get(
            'cor_secundaria'
        )

        cor_terciaria = request.form.get(
            'cor_terciaria'
        )

        # Cores específicas para textos sobre fundos claros e escuros.
        cor_texto_primario = request.form.get('cor_texto_primario')
        cor_texto_secundario = request.form.get('cor_texto_secundario')

        # Contatos exibidos publicamente na página do estabelecimento.
        contato_telefone = request.form.get('contato_telefone')
        contato_email = request.form.get('contato_email')
        instagram = request.form.get('instagram')

        # Chave PIX / Arkhé (integração bancária para pagamentos)
        chave_pix = request.form.get('chave_pix')
        arkhe_client_id = request.form.get('arkhe_client_id')
        arkhe_client_secret = request.form.get('arkhe_client_secret')

        historia = request.form.get(
            'historia'
        )

        localizacao = request.form.get(
            'localizacao'
        )

        num_funcionarios = request.form.get(
            'num_funcionarios',
            '0'
        )


        try:

            num_funcionarios = int(
                num_funcionarios
            )

        except (
            ValueError,
            TypeError
        ):

            num_funcionarios = 0


        if num_funcionarios < 0:

            num_funcionarios = 0


        # A barbearia só fica disponível depois de informar uma equipe e os
        # dados necessários para receber pagamentos. Esta validação também
        # protege a API contra envios que não passaram pela tela.
        tem_funcionario = any(
            str(request.form.get(f'funcionarios[{i}][nome]') or '').strip()
            for i in range(num_funcionarios)
        )
        if not tem_funcionario:
            return jsonify({'mensagem': {
                'informacao': 'Cadastre pelo menos um barbeiro na equipe.',
                'tipo': 'erro'
            }}), 400

        if not all(str(valor or '').strip() for valor in (chave_pix, arkhe_client_id, arkhe_client_secret)):
            return jsonify({'mensagem': {
                'informacao': 'Informe a chave PIX, o Client ID e o Client Secret da Arkhé para receber pagamentos.',
                'tipo': 'erro'
            }}), 400


        # ==================================================
        # PERSONALIZAÇÃO
        # ==================================================

        cursor.execute("""
            INSERT INTO PERSONALIZACAO (
                ID_PERSONALIZACAO,
                ID_USUARIO,
                COR_PRIMARIA,
                COR_SECUNDARIA,
                COR_TERCIARIA,
                COR_TEXTO_PRIMARIO,
                COR_TEXTO_SECUNDARIO,
                TEXTO,
                LOCALIZACAO,
                CONTATO_TELEFONE,
                CONTATO_EMAIL,
                INSTAGRAM,
                NUM_FUNCIONARIOS,
                CHAVE_PIX,
                ARKHE_CLIENT_ID,
                ARKHE_CLIENT_SECRET
            )
            VALUES (NEXT VALUE FOR SEQ_PERSONALIZACAO, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            RETURNING ID_PERSONALIZACAO
        """, (
            id_usuario,
            cor_primaria,
            cor_secundaria,
            cor_terciaria,
            cor_texto_primario,
            cor_texto_secundario,
            historia,
            localizacao,
            contato_telefone,
            contato_email,
            instagram,
            num_funcionarios,
            chave_pix,
            arkhe_client_id,
            arkhe_client_secret
        ))


        id_personalizacao = (
            cursor.fetchone()[0]
        )


        # ==================================================
        # DIAS DE SERVIÇO
        # ==================================================

        dias = [

            'segunda',
            'terca',
            'quarta',
            'quinta',
            'sexta',
            'sabado',
            'domingo'

        ]


        ids_dias = {}


        for dia in dias:

            entrada_manha = request.form.get(
                f'{dia}_entrada_manha'
            )

            saida_manha = request.form.get(
                f'{dia}_saida_manha'
            )

            entrada_tarde = request.form.get(
                f'{dia}_entrada_tarde'
            )

            saida_tarde = request.form.get(
                f'{dia}_saida_tarde'
            )

            # Tratar strings vazias como None
            entrada_manha = entrada_manha if entrada_manha else None
            saida_manha = saida_manha if saida_manha else None
            entrada_tarde = entrada_tarde if entrada_tarde else None
            saida_tarde = saida_tarde if saida_tarde else None


            # ==========================================================
            # VALIDAÇÃO DOS HORÁRIOS
            # ==========================================================

            # Se o dia não possui nenhum horário, ignora o dia
            if not any([
                entrada_manha,
                saida_manha,
                entrada_tarde,
                saida_tarde
            ]):
                continue


            # Entrada da manhã não pode ser depois da saída da manhã
            if entrada_manha and saida_manha:
                if entrada_manha > saida_manha:
                    return jsonify({
                        'mensagem': {
                            'informacao':
                                "A entrada de manhã não pode ser maior que a saída de manhã",
                            'tipo':
                                'erro'
                        }
                    }), 400


            # Saída da manhã não pode ser depois da entrada da tarde
            if saida_manha and entrada_tarde:
                if saida_manha > entrada_tarde:
                    return jsonify({
                        'mensagem': {
                            'informacao':
                                "A saída de manhã não pode ser maior que a entrada de tarde",
                            'tipo':
                                'erro'
                        }
                    }), 400


            # Entrada da tarde não pode ser depois da saída da tarde
            if entrada_tarde and saida_tarde:
                if entrada_tarde > saida_tarde:
                    return jsonify({
                        'mensagem': {
                            'informacao':
                                "A entrada de tarde não pode ser maior que a saída de tarde",
                            'tipo':
                                'erro'
                        }
                    }), 400

            cursor.execute("""
                INSERT INTO DIAS_DE_SERVICO (
                    ID_DIA,
                    ID_USUARIO,
                    DIAS,
                    ENTRADA_MANHA,
                    SAIDA_MANHA,
                    ENTRADA_TARDE,
                    SAIDA_TARDE
                )
                VALUES (NEXT VALUE FOR SEQ_DIA, ?, ?, ?, ?, ?, ?)
                RETURNING ID_DIA
            """, (
                id_usuario,
                dia,
                entrada_manha,
                saida_manha,
                entrada_tarde,
                saida_tarde
            ))


            id_dia = (
                cursor.fetchone()[0]
            )


            ids_dias[dia] = id_dia


        # ==================================================
        # FUNCIONÁRIOS
        # ==================================================

        funcionarios_criados = []


        for i in range(
            num_funcionarios
        ):

            nome = request.form.get(
                f'funcionarios[{i}][nome]'
            )

            descricao = request.form.get(
                f'funcionarios[{i}][descricao]'
            )

            # O frontend envia os dias como "segunda,terca". Mantemos a
            # leitura de "dia" para compatibilidade com cadastros antigos.
            dias_funcionario = request.form.get(f'funcionarios[{i}][dias]') or request.form.get(f'funcionarios[{i}][dia]') or ''


            if not nome:

                continue


            ids_dias_funcionario = [ids_dias[dia.strip()] for dia in dias_funcionario.split(',') if dia.strip() in ids_dias]


            # ==================================================
            # FUNCIONÁRIO
            # ==================================================

            cursor.execute("""
                INSERT INTO FUNCIONARIO (
                    ID_FUNCIONARIO,
                    NOME,
                    DESCRICAO
                )
                VALUES (NEXT VALUE FOR SEQ_FUNCIONARIO, ?, ?)
                RETURNING ID_FUNCIONARIO
            """, (
                nome,
                descricao
            ))


            id_funcionario = (
                cursor.fetchone()[0]
            )

            vincular_dias_funcionario(cursor, id_funcionario, ids_dias_funcionario)


            # ==================================================
            # SERVIÇOS DO FUNCIONÁRIO
            # ==================================================
            #
            # IMPORTANTE:
            #
            # Aqui NÃO cadastramos serviços.
            #
            # Os serviços já precisam existir em SERVICO.
            #
            # Apenas criamos a relação:
            #
            # FUNCIONARIO
            #       ↓
            # SERVICO_POR_FUNCIONARIO
            #       ↓
            # SERVICO
            #
            # ==================================================

            ids_servicos = (
                vincular_servicos_funcionario(
                    cursor,
                    id_funcionario,
                    id_usuario,
                    i
                )
            )


            funcionarios_criados.append({

                'id_funcionario':
                    id_funcionario,

                'dias':
                    ids_dias_funcionario,

                'nome':
                    nome,

                'descricao':
                    descricao,

                'servicos':
                    ids_servicos

            })


        # ==================================================
        # LOGO
        # ==================================================

        logo_url = None


        if 'logo' in request.files:

            arquivo_logo = (
                request.files['logo']
            )


            if (
                arquivo_logo
                and arquivo_logo.filename
            ):

                logo_url = salvar_imagem(
                    arquivo_logo,
                    str(id_usuario)
                )


        # ==================================================
        # FOTOS
        # ==================================================

        fotos = []


        for numero in range(1, 6):

            campo = f'foto{numero}'


            if campo not in request.files:

                continue


            foto = request.files[campo]


            if (
                not foto
                or not foto.filename
            ):

                continue


            nome_base = (
                f'{id_usuario}_{numero}'
            )


            url = salvar_imagem(
                foto,
                nome_base
            )


            if url:

                fotos.append({

                    'numero':
                        numero,

                    'url':
                        url

                })


        # ==================================================
        # COMMIT
        # ==================================================

        con.commit()


        # ==================================================
        # RESPOSTA
        # ==================================================

        return jsonify({

            'mensagem': {

                'informacao':
                    'Personalização criada com sucesso.',

                'tipo':
                    'sucesso'

            },

            'primeira_personalizacao':
                True,

            'id_personalizacao':
                id_personalizacao,

            'personalizacao': {

                'cor_primaria':
                    cor_primaria,

                'cor_secundaria':
                    cor_secundaria,

                'cor_terciaria':
                    cor_terciaria,

                'historia':
                    historia,

                'localizacao':
                    localizacao,

                'num_funcionarios':
                    num_funcionarios,

                'chave_pix':
                    chave_pix,

                'arkhe_client_id':
                    arkhe_client_id,

                'arkhe_client_secret':
                    arkhe_client_secret

            },

            'funcionarios':
                funcionarios_criados,

            'dias_servico':
                list(
                    ids_dias.values()
                ),

            'logo':
                logo_url,

            'fotos':
                fotos

        }), 201


    except ValueError as erro:

        if con:

            con.rollback()


        return jsonify({

            'mensagem': {

                'informacao':
                    str(erro),

                'tipo':
                    'erro'

            }

        }), 400


    except Exception as erro:

        if con:

            try:

                con.rollback()

            except Exception:

                pass


        print(
            'ERRO AO CRIAR PERSONALIZAÇÃO:',
            erro
        )


        return jsonify({

            'mensagem': {

                'informacao':
                    'Erro ao criar personalização.',

                'tipo':
                    'erro'

            },

            'detalhes':
                str(erro)

        }), 500


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
# ==========================================================
# EDITAR PERSONALIZAÇÃO
# ==========================================================
# ==========================================================

@app.route(
    '/barbearia/personalizacao',
    methods=['PUT']
)
def editar_personalizacao():

    con = None
    cursor = None

    try:

        # ==================================================
        # AUTENTICAÇÃO
        # ==================================================

        id_usuario = pegar_id_barbearia_alvo()


        if not id_usuario:

            return jsonify({

                'mensagem': {

                    'informacao':
                        'Usuário não autenticado.',

                    'tipo':
                        'erro'

                }

            }), 401


        # ==================================================
        # CONEXÃO
        # ==================================================

        con = conectar_banco()

        cursor = con.cursor()


        # ==================================================
        # VERIFICAR PERSONALIZAÇÃO
        # ==================================================

        cursor.execute("""
            SELECT ID_PERSONALIZACAO
            FROM PERSONALIZACAO
            WHERE ID_USUARIO = ?
        """, (
            id_usuario,
        ))


        personalizacao = (
            cursor.fetchone()
        )


        if not personalizacao:

            return jsonify({

                'mensagem': {

                    'informacao':
                        'A barbearia ainda não possui personalização. '
                        'Utilize a rota POST para criar.',

                    'tipo':
                        'aviso'

                }

            }), 404


        # ==================================================
        # DADOS
        # ==================================================

        dados = request.form.to_dict()


        cor_primaria = dados.get(
            'cor_primaria'
        )

        cor_secundaria = dados.get(
            'cor_secundaria'
        )

        cor_terciaria = dados.get(
            'cor_terciaria'
        )

        cor_texto_primario = dados.get('cor_texto_primario')
        cor_texto_secundario = dados.get('cor_texto_secundario')

        historia = dados.get(
            'historia'
        )

        localizacao = dados.get(
            'localizacao'
        )

        contato_telefone = dados.get('contato_telefone')
        contato_email = dados.get('contato_email')
        instagram = dados.get('instagram')

        # Chave PIX / Arkhé
        chave_pix = dados.get('chave_pix')
        arkhe_client_id = dados.get('arkhe_client_id')
        arkhe_client_secret = dados.get('arkhe_client_secret')

        try:
            quantidade_funcionarios = int(dados.get('num_funcionarios') or 0)
        except (ValueError, TypeError):
            quantidade_funcionarios = 0
        if quantidade_funcionarios < 0:
            quantidade_funcionarios = 0

        tem_funcionario = any(
            str(dados.get(f'funcionarios[{i}][nome]') or '').strip()
            for i in range(quantidade_funcionarios)
        )
        if not tem_funcionario:
            return jsonify({'mensagem': {
                'informacao': 'Cadastre pelo menos um barbeiro na equipe.',
                'tipo': 'erro'
            }}), 400

        if not all(str(valor or '').strip() for valor in (chave_pix, arkhe_client_id, arkhe_client_secret)):
            return jsonify({'mensagem': {
                'informacao': 'Informe a chave PIX, o Client ID e o Client Secret da Arkhé para receber pagamentos.',
                'tipo': 'erro'
            }}), 400


        # ==================================================
        # ATUALIZAR PERSONALIZAÇÃO
        # ==================================================

        cursor.execute("""
            UPDATE PERSONALIZACAO
            SET
                COR_PRIMARIA = ?,
                COR_SECUNDARIA = ?,
                COR_TERCIARIA = ?,
                COR_TEXTO_PRIMARIO = ?,
                COR_TEXTO_SECUNDARIO = ?,
                TEXTO = ?,
                LOCALIZACAO = ?,
                CONTATO_TELEFONE = ?,
                CONTATO_EMAIL = ?,
                INSTAGRAM = ?,
                CHAVE_PIX = ?,
                ARKHE_CLIENT_ID = ?,
                ARKHE_CLIENT_SECRET = ?
            WHERE ID_USUARIO = ?
        """, (
            cor_primaria,
            cor_secundaria,
            cor_terciaria,
            cor_texto_primario,
            cor_texto_secundario,
            historia,
            localizacao,
            contato_telefone,
            contato_email,
            instagram,
            chave_pix,
            arkhe_client_id,
            arkhe_client_secret,
            id_usuario
        ))


        # ==================================================
        # BUSCAR FUNCIONÁRIOS ANTIGOS
        # ==================================================

        cursor.execute("""
            SELECT DISTINCT F.ID_FUNCIONARIO
            FROM FUNCIONARIO F
            INNER JOIN FUNCIONARIO_DIA FD ON FD.ID_FUNCIONARIO = F.ID_FUNCIONARIO
            INNER JOIN DIAS_DE_SERVICO D ON D.ID_DIA = FD.ID_DIA
            WHERE D.ID_USUARIO = ?
        """, (
            id_usuario,
        ))


        funcionarios_antigos = (
            cursor.fetchall()
        )


        # ==================================================
        # EXCLUIR VÍNCULOS DE SERVIÇOS
        # ==================================================

        for funcionario in funcionarios_antigos:

            cursor.execute("""
                DELETE FROM SERVICO_POR_FUNCIONARIO
                WHERE ID_FUNCIONARIO = ?
            """, (
                funcionario[0],
            ))

            # Remove os vínculos de dias antes de excluir o funcionário.
            cursor.execute("""
                DELETE FROM FUNCIONARIO_DIA
                WHERE ID_FUNCIONARIO = ?
            """, (funcionario[0],))


        # ==================================================
        # EXCLUIR FUNCIONÁRIOS
        # ==================================================

        for funcionario in funcionarios_antigos:

            cursor.execute("""
                DELETE FROM FUNCIONARIO
                WHERE ID_FUNCIONARIO = ?
            """, (
                funcionario[0],
            ))


        # ==================================================
        # EXCLUIR DIAS ANTIGOS
        # ==================================================

        cursor.execute("""
            DELETE FROM DIAS_DE_SERVICO
            WHERE ID_USUARIO = ?
        """, (
            id_usuario,
        ))


        # ==================================================
        # NOVOS DIAS
        # ==================================================

        dias = [

            'segunda',
            'terca',
            'quarta',
            'quinta',
            'sexta',
            'sabado',
            'domingo'

        ]


        ids_dias = {}


        for dia in dias:

            entrada_manha = dados.get(
                f'{dia}_entrada_manha'
            )

            saida_manha = dados.get(
                f'{dia}_saida_manha'
            )

            entrada_tarde = dados.get(
                f'{dia}_entrada_tarde'
            )

            saida_tarde = dados.get(
                f'{dia}_saida_tarde'
            )

            # Tratar strings vazias como None
            entrada_manha = entrada_manha if entrada_manha else None
            saida_manha = saida_manha if saida_manha else None
            entrada_tarde = entrada_tarde if entrada_tarde else None
            saida_tarde = saida_tarde if saida_tarde else None


            # ==========================================================
            # VALIDAÇÃO DOS HORÁRIOS
            # ==========================================================

            # Se o dia não possui nenhum horário, ignora o dia
            if not any([
                entrada_manha,
                saida_manha,
                entrada_tarde,
                saida_tarde
            ]):
                continue


            # Entrada da manhã não pode ser depois da saída da manhã
            if entrada_manha and saida_manha:
                if entrada_manha > saida_manha:
                    return jsonify({
                        'mensagem': {
                            'informacao':
                                "A entrada de manhã não pode ser maior que a saída de manhã",
                            'tipo':
                                'erro'
                        }
                    }), 400


            # Saída da manhã não pode ser depois da entrada da tarde
            if saida_manha and entrada_tarde:
                if saida_manha > entrada_tarde:
                    return jsonify({
                        'mensagem': {
                            'informacao':
                                "A saída de manhã não pode ser maior que a entrada de tarde",
                            'tipo':
                                'erro'
                        }
                    }), 400


            # Entrada da tarde não pode ser depois da saída da tarde
            if entrada_tarde and saida_tarde:
                if entrada_tarde > saida_tarde:
                    return jsonify({
                        'mensagem': {
                            'informacao':
                                "A entrada de tarde não pode ser maior que a saída de tarde",
                            'tipo':
                                'erro'
                        }
                    }), 400


            cursor.execute("""
                INSERT INTO DIAS_DE_SERVICO (
                    ID_DIA,
                    ID_USUARIO,
                    DIAS,
                    ENTRADA_MANHA,
                    SAIDA_MANHA,
                    ENTRADA_TARDE,
                    SAIDA_TARDE
                )
                VALUES (NEXT VALUE FOR SEQ_DIA, ?, ?, ?, ?, ?, ?)
                RETURNING ID_DIA
            """, (
                id_usuario,
                dia,
                entrada_manha,
                saida_manha,
                entrada_tarde,
                saida_tarde
            ))


            id_dia = (
                cursor.fetchone()[0]
            )


            ids_dias[dia] = id_dia


        # ==================================================
        # FUNCIONÁRIOS NOVOS
        # ==================================================

        for i in range(
            quantidade_funcionarios
        ):

            nome = dados.get(
                f'funcionarios[{i}][nome]'
            )

            descricao = dados.get(
                f'funcionarios[{i}][descricao]'
            )

            dias_funcionario = dados.get(f'funcionarios[{i}][dias]') or dados.get(f'funcionarios[{i}][dia]') or ''


            if not nome:

                continue


            ids_dias_funcionario = [ids_dias[dia.strip()] for dia in dias_funcionario.split(',') if dia.strip() in ids_dias]


            # ==================================================
            # FUNCIONÁRIO
            # ==================================================

            cursor.execute("""
                INSERT INTO FUNCIONARIO (
                    ID_FUNCIONARIO,
                    NOME,
                    DESCRICAO
                )
                VALUES (NEXT VALUE FOR SEQ_FUNCIONARIO, ?, ?)
                RETURNING ID_FUNCIONARIO
            """, (
                nome,
                descricao
            ))


            id_funcionario = (
                cursor.fetchone()[0]
            )

            vincular_dias_funcionario(cursor, id_funcionario, ids_dias_funcionario)


            # ==================================================
            # SERVIÇOS DO FUNCIONÁRIO
            # ==================================================
            #
            # NÃO CADASTRA SERVIÇOS.
            #
            # SOMENTE VINCULA SERVIÇOS JÁ EXISTENTES.
            #
            # ==================================================

            vincular_servicos_funcionario(
                cursor,
                id_funcionario,
                id_usuario,
                i
            )


        # ==================================================
        # ATUALIZAR QUANTIDADE
        # ==================================================

        cursor.execute("""
            UPDATE PERSONALIZACAO
            SET NUM_FUNCIONARIOS = ?
            WHERE ID_USUARIO = ?
        """, (
            quantidade_funcionarios,
            id_usuario
        ))


        # ==================================================
        # LOGO
        # ==================================================

        logo_url = None


        if 'logo' in request.files:

            arquivo_logo = (
                request.files['logo']
            )


            if (
                arquivo_logo
                and arquivo_logo.filename
            ):

                logo_url = salvar_imagem(
                    arquivo_logo,
                    str(id_usuario)
                )


        # ==================================================
        # FOTOS
        # ==================================================

        fotos = []


        for numero in range(1, 6):

            campo = f'foto{numero}'


            if campo not in request.files:

                continue


            foto = request.files[campo]


            if (
                not foto
                or not foto.filename
            ):

                continue


            url = salvar_imagem(
                foto,
                f'{id_usuario}_{numero}'
            )


            if url:

                fotos.append({

                    'numero':
                        numero,

                    'url':
                        url

                })


        # ==================================================
        # COMMIT
        # ==================================================

        con.commit()


        # ==================================================
        # RESPOSTA
        # ==================================================

        return jsonify({

            'mensagem': {

                'informacao':
                    'Personalização atualizada com sucesso.',

                'tipo':
                    'sucesso'

            },

            'primeira_personalizacao':
                False,

            'logo':
                logo_url,

            'fotos':
                fotos

        }), 200


    except ValueError as erro:

        if con:

            con.rollback()


        return jsonify({

            'mensagem': {

                'informacao':
                    str(erro),

                'tipo':
                    'erro'

            }

        }), 400


    except Exception as erro:

        if con:

            try:

                con.rollback()

            except Exception:

                pass


        print(
            'ERRO AO EDITAR PERSONALIZAÇÃO:',
            erro
        )


        return jsonify({

            'mensagem': {

                'informacao':
                    'Erro ao editar personalização.',

                'tipo':
                    'erro'

            },

            'detalhes':
                str(erro)

        }), 500


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
# ==========================================================
# BUSCAR PERSONALIZAÇÃO
# ==========================================================
# ==========================================================

@app.route(
    '/barbearia/personalizacao',
    methods=['GET']
)
def buscar_personalizacao():

    con = None
    cursor = None

    try:

        # ==================================================
        # AUTENTICAÇÃO
        # ==================================================

        id_usuario = pegar_id_barbearia_alvo()


        if not id_usuario:

            return jsonify({

                'mensagem': {

                    'informacao':
                        'Usuário não autenticado.',

                    'tipo':
                        'erro'

                }

            }), 401


        # ==================================================
        # CONEXÃO
        # ==================================================

        con = conectar_banco()

        cursor = con.cursor()


        # ==================================================
        # PERSONALIZAÇÃO
        # ==================================================

        cursor.execute("""
            SELECT
                ID_PERSONALIZACAO,
                ID_USUARIO,
                COR_PRIMARIA,
                COR_SECUNDARIA,
                COR_TERCIARIA,
                COR_TEXTO_PRIMARIO,
                COR_TEXTO_SECUNDARIO,
                TEXTO,
                LOCALIZACAO,
                CONTATO_TELEFONE,
                CONTATO_EMAIL,
                INSTAGRAM,
                NUM_FUNCIONARIOS,
                CHAVE_PIX,
                ARKHE_CLIENT_ID,
                ARKHE_CLIENT_SECRET
            FROM PERSONALIZACAO
            WHERE ID_USUARIO = ?
        """, (
            id_usuario,
        ))


        personalizacao = (
            cursor.fetchone()
        )


        # ==================================================
        # NÃO PERSONALIZADO
        # ==================================================

        if not personalizacao:

            return jsonify({

                'mensagem': {
                    'informacao':
                        'Barbearia ainda sem personalização.',
                    'tipo':
                        'aviso'
                },

                'personalizado':
                    False,

                'personalizacao':
                    None,

                'funcionarios':
                    [],

                'dias_servico':
                    [],

                'logo':
                    None,

                'fotos':
                    []

            }), 200


        # ==================================================
        # DIAS
        # ==================================================

        cursor.execute("""
            SELECT
                ID_DIA,
                DIAS,
                ENTRADA_MANHA,
                SAIDA_MANHA,
                ENTRADA_TARDE,
                SAIDA_TARDE
            FROM DIAS_DE_SERVICO
            WHERE ID_USUARIO = ?
            ORDER BY ID_DIA
        """, (
            id_usuario,
        ))


        dias_db = (
            cursor.fetchall()
        )


        dias = []


        for dia in dias_db:

            dias.append({

                'id_dia':
                    dia[0],

                'dia':
                    dia[1],

                'entrada_manha':
                    str(dia[2])
                    if dia[2]
                    else None,

                'saida_manha':
                    str(dia[3])
                    if dia[3]
                    else None,

                'entrada_tarde':
                    str(dia[4])
                    if dia[4]
                    else None,

                'saida_tarde':
                    str(dia[5])
                    if dia[5]
                    else None

            })


        # ==================================================
        # FUNCIONÁRIOS
        # ==================================================

        cursor.execute("""
            SELECT DISTINCT F.ID_FUNCIONARIO, F.NOME, F.DESCRICAO
            FROM FUNCIONARIO F
            INNER JOIN FUNCIONARIO_DIA FD ON FD.ID_FUNCIONARIO = F.ID_FUNCIONARIO
            INNER JOIN DIAS_DE_SERVICO D ON D.ID_DIA = FD.ID_DIA
            WHERE D.ID_USUARIO = ?
            ORDER BY F.ID_FUNCIONARIO
        """, (id_usuario,))


        funcionarios_db = (
            cursor.fetchall()
        )


        funcionarios = []


        for funcionario in funcionarios_db:

            id_funcionario = (
                funcionario[0]
            )


            # =================================================
            # SERVIÇOS
            # =================================================

            cursor.execute("""
                SELECT
                    SPF.ID_SERVICO
                FROM SERVICO_POR_FUNCIONARIO SPF
                INNER JOIN SERVICO S
                    ON S.ID_SERVICO = SPF.ID_SERVICO
                WHERE
                    SPF.ID_FUNCIONARIO = ?
                    AND S.ID_USUARIO = ?
                ORDER BY SPF.ID_SERVI_FUNCI
            """, (
                id_funcionario,
                id_usuario
            ))


            servicos_db = (
                cursor.fetchall()
            )

            # A resposta inclui todos os dias selecionados para o frontend.
            cursor.execute("""
                SELECT ID_DIA FROM FUNCIONARIO_DIA
                WHERE ID_FUNCIONARIO = ?
                ORDER BY ID_DIA
            """, (id_funcionario,))
            dias_funcionario = [linha[0] for linha in cursor.fetchall()]


            funcionarios.append({

                'id_funcionario':
                    funcionario[0],

                'dias':
                    dias_funcionario,

                'nome':
                    funcionario[1],

                'descricao':
                    funcionario[2],

                'servicos': [

                    servico[0]

                    for servico in servicos_db

                ]

            })


        # ==================================================
        # LOGO
        # ==================================================

        pasta = (
            criar_pasta_barbearia()
        )


        logo = None


        for extensao in EXTENSOES_PERMITIDAS:

            caminho = os.path.join(
                pasta,
                f'{id_usuario}.{extensao}'
            )


            if os.path.exists(
                caminho
            ):

                logo = (
                    f'/uploads/barbearia/'
                    f'{id_usuario}.{extensao}'
                )

                break


        # ==================================================
        # FOTOS
        # ==================================================

        fotos = []


        for numero in range(1, 6):

            for extensao in EXTENSOES_PERMITIDAS:

                caminho = os.path.join(
                    pasta,
                    f'{id_usuario}_{numero}.{extensao}'
                )


                if os.path.exists(
                    caminho
                ):

                    fotos.append({

                        'numero':
                            numero,

                        'url':
                            f'/uploads/barbearia/'
                            f'{id_usuario}_{numero}.{extensao}'

                    })

                    break


        # ==================================================
        # RESPOSTA
        # ==================================================

        cursor.execute('SELECT NOME FROM USUARIO WHERE ID_USUARIO = ?', (id_usuario,))
        usuario_barbearia = cursor.fetchone()

        return jsonify({

            'mensagem': {
                'informacao':
                    'Personalização encontrada.',
                'tipo':
                    'sucesso'
            },

            'personalizado':
                True,

            'nome_barbearia':
                usuario_barbearia[0] if usuario_barbearia else 'Barbearia',

            'personalizacao': {

                'id_personalizacao':
                    personalizacao[0],

                'id_usuario':
                    personalizacao[1],

                'cor_primaria':
                    personalizacao[2],

                'cor_secundaria':
                    personalizacao[3],

                'cor_terciaria':
                    personalizacao[4],

                'cor_texto_primario':
                    personalizacao[5],

                'cor_texto_secundario':
                    personalizacao[6],

                'historia':
                    personalizacao[7],

                'localizacao':
                    personalizacao[8],

                'contato_telefone':
                    personalizacao[9],

                'contato_email':
                    personalizacao[10],

                'instagram':
                    personalizacao[11],

                'num_funcionarios':
                    personalizacao[12],

                'chave_pix':
                    personalizacao[13],

                'arkhe_client_id':
                    personalizacao[14],

                'arkhe_client_secret':
                    personalizacao[15]

            },

            'funcionarios':
                funcionarios,

            'dias_servico':
                dias,

            'logo':
                logo,

            'fotos':
                fotos

        }), 200


    except Exception as erro:

        print(
            'ERRO AO BUSCAR PERSONALIZAÇÃO:',
            erro
        )


        return jsonify({

            'mensagem': {

                'informacao':
                    'Erro ao buscar personalização.',

                'tipo':
                    'erro'

            },

            'detalhes':
                str(erro)

        }), 500


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
# IMAGENS
# ==========================================================

@app.route(
    '/uploads/barbearia/<path:nome_arquivo>',
    methods=['GET']
)
def imagem_barbearia(nome_arquivo):

    return send_from_directory(

        os.path.join(
            app.config['UPLOAD_FOLDER'],
            'barbearia'
        ),

        nome_arquivo

    )
