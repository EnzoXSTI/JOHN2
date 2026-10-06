import os

from flask import (
    request,
    jsonify,
    send_from_directory,
    current_app
)

from main import (
    app,
    conectar_banco
)

from funcoes import (
    verificar_senha_forte,
    criptografar_senha,
    decodificar_token,
    salvar_foto_perfil,
    buscar_foto_perfil
)


# ==========================================================
# BUSCAR DADOS DO PERFIL
# ==========================================================

@app.route(
    '/dados-perfil/<int:id_usuario>',
    methods=['GET']
)
def dados_perfil(id_usuario):

    con = None
    cursor = None

    try:
        # ==================================================
        # VERIFICAR TOKEN
        # ==================================================

        token_data = decodificar_token()

        if not token_data:

            return jsonify({

                'mensagem': {

                    'informacao':
                        'Token necessário. Faça login novamente.',

                    'tipo':
                        'erro'

                }

            }), 401

        # ==================================================
        # ID DO TOKEN
        # ==================================================

        try:

            id_token = int(
                token_data.get(
                    'id_usuario'
                )
            )

        except Exception:

            return jsonify({

                'mensagem': {

                    'informacao':
                        'Token inválido.',

                    'tipo':
                        'erro'

                }

            }), 401

        # ==================================================
        # TIPO DO USUÁRIO
        # ==================================================

        try:

            tipo_token = int(
                token_data.get(
                    'tipo',
                    1
                )
            )

        except Exception:

            tipo_token = 1

        # ==================================================
        # VERIFICAR PERMISSÃO
        # ==================================================

        if (
                id_token != id_usuario
                and tipo_token != 0
        ):

            return jsonify({

                'mensagem': {

                    'informacao':
                        'Você não pode acessar este perfil.',

                    'tipo':
                        'erro'

                }

            }), 403

        # ==================================================
        # CONECTAR BANCO
        # ==================================================

        con = conectar_banco()

        cursor = con.cursor()

        # ==================================================
        # BUSCAR USUÁRIO
        # ==================================================

        cursor.execute(
            '''
            SELECT
                ID_USUARIO,
                NOME,
                EMAIL,
                TELEFONE,
                TIPO,
                GENERO
            FROM USUARIO
            WHERE ID_USUARIO = ?
            ''',
            (
                id_usuario,
            )
        )

        usuario = cursor.fetchone()

        # ==================================================
        # USUÁRIO NÃO ENCONTRADO
        # ==================================================

        if not usuario:

            return jsonify({

                'mensagem': {

                    'informacao':
                        'Usuário não encontrado.',

                    'tipo':
                        'erro'

                }

            }), 404

        # ==================================================
        # BUSCAR FOTO
        # ==================================================

        foto_perfil = buscar_foto_perfil(
            id_usuario
        )

        # ==================================================
        # RESPOSTA
        # ==================================================

        resposta = {

            'usuario': {

                'id_usuario':
                    usuario[0],

                'id':
                    usuario[0],

                'nome':
                    usuario[1] or '',

                'email':
                    usuario[2] or '',

                'telefone':
                    usuario[3] or '',

                'tipo':
                    int(usuario[4] or 0),

                'genero':
                    usuario[5] or '',

                'foto_perfil':
                    foto_perfil

            }

        }

        return jsonify(
            resposta
        ), 200

    except Exception as erro:

        return jsonify({

            'mensagem': {

                'informacao':
                    'Erro ao buscar dados do perfil.',

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
# EDITAR USUÁRIO
# ==========================================================

@app.route(
    '/editar-usuario/<int:id_usuario>',
    methods=['PUT']
)
def editar_usuario(id_usuario):

    con = None
    cursor = None

    try:

        # ==================================================
        # VERIFICAR TOKEN
        # ==================================================

        token_data = decodificar_token()

        if not token_data:

            return jsonify({

                'mensagem': {

                    'informacao':
                        'Token necessário. Faça login novamente.',

                    'tipo':
                        'erro'

                }

            }), 401

        # ==================================================
        # ID DO TOKEN
        # ==================================================

        try:

            id_token = int(
                token_data.get(
                    'id_usuario'
                )
            )

        except Exception:

            return jsonify({

                'mensagem': {

                    'informacao':
                        'Token inválido.',

                    'tipo':
                        'erro'

                }

            }), 401

        # ==================================================
        # TIPO DO TOKEN
        # ==================================================

        try:

            tipo_token = int(
                token_data.get(
                    'tipo',
                    1
                )
            )

        except Exception:

            tipo_token = 1

        # ==================================================
        # VERIFICAR PERMISSÃO
        # ==================================================

        if (
                id_token != id_usuario
                and tipo_token != 0
        ):

            return jsonify({

                'mensagem': {

                    'informacao':
                        'Você só pode editar seu próprio perfil.',

                    'tipo':
                        'erro'

                }

            }), 403

        # ==================================================
        # RECEBER DADOS
        # ==================================================

        nome = request.form.get(
            'nome'
        )

        email = request.form.get(
            'email'
        )

        telefone = request.form.get(
            'telefone'
        )

        senha = request.form.get(
            'senha'
        )

        foto = request.files.get(
            'foto'
        )

        genero = request.form.get(
            'genero'
        )

        # ==================================================
        # CONECTAR BANCO
        # ==================================================

        con = conectar_banco()

        cursor = con.cursor()

        # ==================================================
        # BUSCAR USUÁRIO
        # ==================================================

        cursor.execute(
            '''
            SELECT
                ID_USUARIO,
                NOME,
                EMAIL,
                TELEFONE,
                SENHA_HASH,
                TIPO,
                GENERO
            FROM USUARIO
            WHERE ID_USUARIO = ?
            ''',
            (
                id_usuario,
            )
        )

        usuario = cursor.fetchone()

        # ==================================================
        # VERIFICAR USUÁRIO
        # ==================================================

        if not usuario:

            return jsonify({

                'mensagem': {

                    'informacao':
                        'Usuário não encontrado.',

                    'tipo':
                        'erro'

                }

            }), 404

        # ==================================================
        # DADOS ANTIGOS
        # ==================================================

        nome_antigo = usuario[1]

        email_antigo = usuario[2]

        telefone_antigo = usuario[3]

        senha_hash = usuario[4]
        tipo_usuario = int(usuario[5] or -1)
        genero_atual = usuario[6]

        # Gênero é uma informação do perfil de cliente. Para os demais
        # perfis, preservamos o valor já salvo independentemente do formulário.
        if tipo_usuario == 1:
            genero = str(genero or '').strip().lower()
            if genero not in ('', 'masculino', 'feminino', 'outro'):
                return jsonify({'mensagem': {'informacao': 'Gênero inválido.', 'tipo': 'erro'}}), 400
        else:
            genero = genero_atual

        # ==================================================
        # MANTER DADOS ANTIGOS
        # ==================================================

        if (
                nome is None
                or not str(nome).strip()
        ):

            nome = nome_antigo

        if (
                email is None
                or not str(email).strip()
        ):

            email = email_antigo

        if (
                telefone is None
                or not str(telefone).strip()
        ):

            telefone = telefone_antigo

        # ==================================================
        # LIMPAR NOME
        # ==================================================

        nome = ' '.join(
            str(nome)
            .strip()
            .split()
        )

        # ==================================================
        # LIMPAR EMAIL
        # ==================================================

        email = (
            str(email)
            .strip()
            .replace(
                ' ',
                ''
            )
            .lower()
        )

        # ==================================================
        # LIMPAR TELEFONE
        # ==================================================

        telefone = str(
            telefone
        ).strip()

        telefone_numeros = ''.join(
            filter(
                str.isdigit,
                telefone
            )
        )

        # ==================================================
        # VALIDAR NOME
        # ==================================================

        if not nome:

            return jsonify({

                'mensagem': {

                    'informacao':
                        'Nome é obrigatório.',

                    'tipo':
                        'erro'

                }

            }), 400

        # ==================================================
        # VALIDAR EMAIL
        # ==================================================

        if not email:

            return jsonify({

                'mensagem': {

                    'informacao':
                        'E-mail é obrigatório.',

                    'tipo':
                        'erro'

                }

            }), 400

        # ==================================================
        # VALIDAR TELEFONE
        # ==================================================

        if len(telefone_numeros) not in (
                10,
                11
        ):

            return jsonify({

                'mensagem': {

                    'informacao':
                        'Telefone inválido.',

                    'tipo':
                        'erro'

                }

            }), 400

        # ==================================================
        # VERIFICAR EMAIL DUPLICADO
        # ==================================================

        if email.lower() != str(
                email_antigo
        ).lower():

            cursor.execute(
                '''
                SELECT
                    ID_USUARIO
                FROM USUARIO
                WHERE LOWER(EMAIL) = ?
                  AND ID_USUARIO <> ?
                ''',
                (
                    email.lower(),
                    id_usuario
                )
            )

            email_existente = (
                cursor.fetchone()
            )

            if email_existente:

                return jsonify({

                    'mensagem': {

                        'informacao':
                            'Este e-mail já está cadastrado.',

                        'tipo':
                            'erro'

                    }

                }), 409

        # ==================================================
        # ALTERAR SENHA
        # ==================================================

        if (
                senha
                and senha.strip()
        ):

            senha = senha.strip()

            senha_valida, mensagem_senha = (
                verificar_senha_forte(
                    senha
                )
            )

            if not senha_valida:

                return jsonify({

                    'mensagem': {

                        'informacao':
                            mensagem_senha,

                        'tipo':
                            'erro'

                    }

                }), 400

            senha_hash = (
                criptografar_senha(
                    senha
                )
            )

        # ==================================================
        # ATUALIZAR BANCO
        # ==================================================

        cursor.execute(
            '''
            UPDATE USUARIO
            SET
                NOME = ?,
                EMAIL = ?,
                TELEFONE = ?,
                SENHA_HASH = ?,
                GENERO = ?
            WHERE ID_USUARIO = ?
            ''',
            (
                nome,
                email,
                telefone_numeros,
                senha_hash,
                genero if genero else None,
                id_usuario
            )
        )

        # ==================================================
        # SALVAR FOTO
        # ==================================================

        if foto:

            salvar_foto_perfil(
                foto,
                id_usuario
            )

        # ==================================================
        # COMMIT
        # ==================================================

        con.commit()

        # ==================================================
        # BUSCAR FOTO ATUAL
        # ==================================================

        foto_perfil = buscar_foto_perfil(
            id_usuario
        )

        # ==================================================
        # RESPOSTA
        # ==================================================

        resposta = {

            'mensagem': {

                'informacao':
                    'Usuário editado com sucesso!',

                'tipo':
                    'sucesso'

            },

            'usuario': {

                'id_usuario':
                    id_usuario,

                'id':
                    id_usuario,

                'nome':
                    nome,

                'email':
                    email,

                'telefone':
                    telefone_numeros,

                'tipo':
                    tipo_usuario,

                'genero':
                    genero if tipo_usuario == 1 else None,

                'foto_perfil':
                    foto_perfil

            }

        }

        return jsonify(
            resposta
        ), 200

    # ======================================================
    # ERRO DE VALIDAÇÃO
    # ======================================================

    except ValueError as erro:

        if con:

            try:

                con.rollback()

            except Exception:

                pass

        return jsonify({

            'mensagem': {

                'informacao':
                    str(erro),

                'tipo':
                    'erro'

            }

        }), 400

    # ======================================================
    # ERRO GERAL
    # ======================================================

    except Exception as erro:

        if con:

            try:

                con.rollback()

            except Exception:

                pass

        return jsonify({

            'mensagem': {

                'informacao':
                    'Erro ao editar usuário.',

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
# SERVIR FOTOS DE PERFIL
# ==========================================================
#
# Estrutura:
#
# uploads/
# └── perfil/
#     ├── 1.jpg
#     ├── 2.png
#     └── 3.webp
#
# URL:
#
# /uploads/perfil/1.jpg
#
# ==========================================================

@app.route(
    '/uploads/perfil/<path:nome_arquivo>',
    methods=['GET']
)
def servir_foto_perfil(nome_arquivo):

    # ======================================================
    # PEGAR PASTA CONFIGURADA
    # ======================================================

    pasta_perfil = current_app.config.get(
        'PERFIL_FOLDER'
    )

    if not pasta_perfil:

        return jsonify({

            'mensagem': {'informacao': 'Pasta de perfil não configurada.', 'tipo': 'erro'}

        }), 500

    # ======================================================
    # GARANTIR QUE A PASTA EXISTE
    # ======================================================

    if not os.path.isdir(
            pasta_perfil
    ):

        try:

            os.makedirs(
                pasta_perfil,
                exist_ok=True
            )

        except Exception as erro:

            return jsonify({

                'mensagem': {'informacao': 'Não foi possível criar a pasta de fotos.', 'tipo': 'erro'}

            }), 500

    # ======================================================
    # SEGURANÇA
    # ======================================================

    # Não permitir caminhos externos.
    nome_seguro = os.path.basename(
        nome_arquivo
    )

    if nome_seguro != nome_arquivo:

        return jsonify({

            'mensagem': {'informacao': 'Nome de arquivo inválido.', 'tipo': 'erro'}

        }), 400

    # ======================================================
    # VERIFICAR EXTENSÃO
    # ======================================================

    extensoes_permitidas = {

        '.jpg',
        '.jpeg',
        '.png',
        '.webp'

    }

    extensao = os.path.splitext(
        nome_seguro
    )[1].lower()

    if extensao not in extensoes_permitidas:

        return jsonify({

            'mensagem': {'informacao': 'Formato de imagem inválido.', 'tipo': 'erro'}

        }), 400

    # ======================================================
    # CAMINHO COMPLETO
    # ======================================================

    caminho = os.path.join(
        pasta_perfil,
        nome_seguro
    )

    # ======================================================
    # VERIFICAR ARQUIVO
    # ======================================================

    if not os.path.isfile(
            caminho
    ):

        return jsonify({

            'mensagem': {'informacao': 'Foto não encontrada.', 'tipo': 'erro'}

        }), 404

    # ======================================================
    # ENVIAR FOTO
    # ======================================================

    return send_from_directory(
        pasta_perfil,
        nome_seguro
    )

# ==========================================================
# EXCLUIR FOTO DE PERFIL
# ==========================================================

@app.route(
    '/excluir-foto-perfil/<int:id_usuario>',
    methods=['DELETE']
)
def excluir_foto_perfil(id_usuario):

    con = None
    cursor = None

    try:

        # ==================================================
        # VERIFICAR TOKEN
        # ==================================================

        token_data = decodificar_token()

        if not token_data:

            return jsonify({

                'mensagem': {

                    'informacao':
                        'Token necessário. Faça login novamente.',

                    'tipo':
                        'erro'

                }

            }), 401

        # ==================================================
        # ID DO TOKEN
        # ==================================================

        try:

            id_token = int(
                token_data.get(
                    'id_usuario'
                )
            )

        except Exception:

            return jsonify({

                'mensagem': {

                    'informacao':
                        'Token inválido.',

                    'tipo':
                        'erro'

                }

            }), 401

        # ==================================================
        # TIPO DO USUÁRIO
        # ==================================================

        try:

            tipo_token = int(
                token_data.get(
                    'tipo',
                    1
                )
            )

        except Exception:

            tipo_token = 1

        # ==================================================
        # VERIFICAR PERMISSÃO
        # ==================================================

        if (
                id_token != id_usuario
                and tipo_token != 0
        ):

            return jsonify({

                'mensagem': {

                    'informacao':
                        'Você só pode excluir sua própria foto.',

                    'tipo':
                        'erro'

                }

            }), 403

        # ==================================================
        # PEGAR PASTA DE PERFIL
        # ==================================================

        pasta_perfil = current_app.config.get(
            'PERFIL_FOLDER'
        )

        if not pasta_perfil:

            return jsonify({

                'mensagem': {

                    'informacao':
                        'Pasta de perfil não configurada.',

                    'tipo':
                        'erro'

                }

            }), 500

        # ==================================================
        # VERIFICAR SE A PASTA EXISTE
        # ==================================================

        if not os.path.isdir(
                pasta_perfil
        ):

            return jsonify({

                'mensagem': {

                    'informacao':
                        'A pasta de fotos não existe.',

                    'tipo':
                        'erro'

                }

            }), 404

        # ==================================================
        # EXTENSÕES PERMITIDAS
        # ==================================================

        extensoes_permitidas = {

            '.jpg',
            '.jpeg',
            '.png',
            '.webp'

        }

        # ==================================================
        # PROCURAR FOTO DO USUÁRIO
        # ==================================================
        #
        # Como suas fotos são salvas usando o ID do usuário,
        # procuramos:
        #
        # 1.jpg
        # 1.jpeg
        # 1.png
        # 1.webp
        #
        # ==================================================

        foto_encontrada = None

        for extensao in extensoes_permitidas:

            nome_arquivo = (
                f'{id_usuario}{extensao}'
            )

            caminho = os.path.join(
                pasta_perfil,
                nome_arquivo
            )

            if os.path.isfile(
                    caminho
            ):

                foto_encontrada = caminho

                print(
                    "Foto encontrada:",
                    caminho
                )

                break

        # ==================================================
        # FOTO NÃO EXISTE
        # ==================================================

        if not foto_encontrada:

            return jsonify({

                'mensagem': {

                    'informacao':
                        'Este usuário não possui uma foto de perfil.',

                    'tipo':
                        'erro'

                },

                'usuario': {

                    'id_usuario':
                        id_usuario,

                    'foto_perfil':
                        None

                }

            }), 404

        # ==================================================
        # EXCLUIR ARQUIVO
        # ==================================================

        try:

            os.remove(
                foto_encontrada
            )

        except Exception as erro:

            print(
                "ERRO AO EXCLUIR FOTO:",
                erro
            )

            return jsonify({

                'mensagem': {

                    'informacao':
                        'Não foi possível excluir a foto.',

                    'tipo':
                        'erro'

                },

                'detalhes':
                    str(erro)

            }), 500

        # ==================================================
        # CONFIRMAR EXCLUSÃO
        # ==================================================

        if os.path.exists(
                foto_encontrada
        ):

            return jsonify({

                'mensagem': {

                    'informacao':
                        'A foto não pôde ser excluída.',

                    'tipo':
                        'erro'

                }

            }), 500

        # ==================================================
        # RESPOSTA
        # ==================================================

        return jsonify({

            'mensagem': {

                'informacao':
                    'Foto de perfil excluída com sucesso!',

                'tipo':
                    'sucesso'

            },

            'usuario': {

                'id_usuario':
                    id_usuario,

                'id':
                    id_usuario,

                'foto_perfil':
                    None

            }

        }), 200

    # ======================================================
    # ERRO GERAL
    # ======================================================

    except Exception as erro:

        print()
        print("==========================================")
        print("ERRO AO EXCLUIR FOTO DE PERFIL")
        print("==========================================")
        print(
            erro
        )
        print("==========================================")

        return jsonify({

            'mensagem': {

                'informacao':
                    'Erro ao excluir foto de perfil.',

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
